"""Tests for Redis caching utilities.

This module provides comprehensive tests for the cache module covering:
- Redis connection pool management (get_redis / close_redis)
- The @cached decorator (hit, miss, error, custom key_builder)
- The @cache_invalidate decorator
- get_cached / set_cached / delete_cached operations
- invalidate_pattern (scan + delete in batches)
- warm_cache and get_cache_stats

All tests mock Redis via unittest.mock so they do not require a running
Redis instance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

# ============================================================================
# Helpers
# ============================================================================


class _AsyncIter:
    """Lightweight async iterator returning a fixed sequence of items.

    Used to mock ``redis.scan_iter`` which yields keys asynchronously.
    """

    def __init__(self, items: list[str]) -> None:
        self._items = list(items)

    def __aiter__(self) -> _AsyncIter:
        return self

    async def __anext__(self) -> str:
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


@pytest.fixture
def reset_pool() -> Any:
    """Reset the module-level Redis pool before and after each test."""
    from fragrance_rater.core.cache import _PoolState

    _PoolState.pool = None
    yield
    _PoolState.pool = None


@pytest.fixture
def mock_redis(reset_pool: Any) -> AsyncMock:
    """Install a fresh AsyncMock as the Redis pool for tests."""
    from fragrance_rater.core.cache import _PoolState

    fake = AsyncMock()
    _PoolState.pool = fake
    return fake


# ============================================================================
# Connection management
# ============================================================================


class TestGetRedis:
    """Tests for get_redis pool initialization and reuse."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_redis_initializes_pool(self, reset_pool: Any) -> None:
        """Verify get_redis creates a new pool on first call."""
        from fragrance_rater.core import cache as cache_mod

        sentinel = AsyncMock()
        with patch.object(cache_mod, "from_url", return_value=sentinel) as factory:
            result = await cache_mod.get_redis()

        assert result is sentinel
        factory.assert_called_once()
        assert cache_mod._PoolState.pool is sentinel

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_redis_uses_env_url(
        self, reset_pool: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify get_redis reads REDIS_URL from environment."""
        from fragrance_rater.core import cache as cache_mod

        monkeypatch.setenv("REDIS_URL", "redis://example.test:6379/2")
        sentinel = AsyncMock()
        with patch.object(cache_mod, "from_url", return_value=sentinel) as factory:
            await cache_mod.get_redis()

        # First positional argument should be the URL.
        args, _kwargs = factory.call_args
        assert args[0] == "redis://example.test:6379/2"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_redis_returns_cached_pool(self, reset_pool: Any) -> None:
        """Verify subsequent calls reuse the existing pool."""
        from fragrance_rater.core import cache as cache_mod

        existing = AsyncMock()
        cache_mod._PoolState.pool = existing

        with patch.object(cache_mod, "from_url") as factory:
            result = await cache_mod.get_redis()

        assert result is existing
        factory.assert_not_called()


class TestCloseRedis:
    """Tests for close_redis pool teardown."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_redis_closes_existing_pool(self, reset_pool: Any) -> None:
        """Verify close_redis calls close and clears the pool."""
        from fragrance_rater.core import cache as cache_mod

        pool = AsyncMock()
        cache_mod._PoolState.pool = pool

        await cache_mod.close_redis()

        pool.close.assert_awaited_once()
        assert cache_mod._PoolState.pool is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_redis_no_pool_is_noop(self, reset_pool: Any) -> None:
        """Verify close_redis is safe when pool is None."""
        from fragrance_rater.core import cache as cache_mod

        cache_mod._PoolState.pool = None
        # Should not raise.
        await cache_mod.close_redis()
        assert cache_mod._PoolState.pool is None


# ============================================================================
# cached decorator
# ============================================================================


class TestCachedDecorator:
    """Tests for the @cached decorator."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cached_hit_returns_cached_value(self, mock_redis: AsyncMock) -> None:
        """Verify cache hit returns the deserialized stored value."""
        from fragrance_rater.core.cache import cached

        mock_redis.get.return_value = '{"x": 1}'
        called = {"n": 0}

        @cached(ttl=60, key_prefix="t")
        async def fn(a: int) -> dict:
            called["n"] += 1
            return {"x": a}

        result = await fn(1)
        assert result == {"x": 1}
        assert called["n"] == 0
        mock_redis.setex.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cached_miss_calls_function_and_stores(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify cache miss invokes function and stores the result."""
        from fragrance_rater.core.cache import cached

        mock_redis.get.return_value = None

        @cached(ttl=120, key_prefix="users")
        async def fn(uid: str) -> dict:
            return {"id": uid}

        result = await fn("abc")
        assert result == {"id": "abc"}
        mock_redis.setex.assert_awaited_once()
        args, _ = mock_redis.setex.call_args
        assert args[1] == 120
        # Stored payload should be JSON.
        assert '"id"' in args[2]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cached_redis_error_falls_back_to_function(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify RedisError leads to graceful degradation (call function)."""
        from fragrance_rater.core.cache import cached

        mock_redis.get.side_effect = RedisError("down")

        @cached(ttl=60)
        async def fn(value: int) -> int:
            return value * 2

        result = await fn(3)
        assert result == 6

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cached_custom_key_builder_used(self, mock_redis: AsyncMock) -> None:
        """Verify the key_builder branch is used for cache key generation."""
        from fragrance_rater.core.cache import cached

        mock_redis.get.return_value = None

        def builder(uid: str) -> str:
            return f"custom:{uid}"

        @cached(ttl=30, key_builder=builder)
        async def fn(uid: str) -> str:
            return uid.upper()

        result = await fn("xyz")
        assert result == "XYZ"
        # The cache key passed to redis.get and redis.setex must be from the
        # builder, not the default hashed prefix.
        mock_redis.get.assert_awaited_with("custom:xyz")
        args, _ = mock_redis.setex.call_args
        assert args[0] == "custom:xyz"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cached_default_key_prefix_uses_function_name(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify the default key prefix falls back to the function name."""
        from fragrance_rater.core.cache import cached

        mock_redis.get.return_value = None

        @cached(ttl=10)
        async def my_function(a: int, b: int = 2) -> int:
            return a + b

        result = await my_function(1, b=3)
        assert result == 4
        args, _ = mock_redis.setex.call_args
        assert args[0].startswith("my_function:")


# ============================================================================
# cache_invalidate decorator
# ============================================================================


class TestCacheInvalidateDecorator:
    """Tests for the @cache_invalidate decorator."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_calls_pattern_after_function(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify the decorator calls invalidate_pattern after the wrapped fn."""
        from fragrance_rater.core import cache as cache_mod

        mock_redis.scan_iter = MagicMock(return_value=_AsyncIter(["k1"]))
        mock_redis.delete.return_value = 1

        @cache_mod.cache_invalidate("user:*")
        async def updater(uid: str) -> str:
            return f"ok-{uid}"

        result = await updater("42")
        assert result == "ok-42"
        mock_redis.delete.assert_awaited()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_swallows_redis_error(self, mock_redis: AsyncMock) -> None:
        """Verify a RedisError in invalidation does not propagate."""
        from fragrance_rater.core import cache as cache_mod

        # Make invalidate_pattern raise by having get_redis-backed scan fail.
        async def boom(*_a: Any, **_k: Any) -> None:
            raise RedisError("boom")

        with patch.object(cache_mod, "invalidate_pattern", side_effect=boom):

            @cache_mod.cache_invalidate("things:*")
            async def fn() -> str:
                return "value"

            result = await fn()

        assert result == "value"


# ============================================================================
# Single-key operations
# ============================================================================


class TestGetCached:
    """Tests for get_cached."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cached_hit(self, mock_redis: AsyncMock) -> None:
        """Verify get_cached deserializes a hit value."""
        from fragrance_rater.core.cache import get_cached

        mock_redis.get.return_value = '{"a": 1}'
        assert await get_cached("k") == {"a": 1}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cached_miss_returns_default(self, mock_redis: AsyncMock) -> None:
        """Verify get_cached returns the default when key is missing."""
        from fragrance_rater.core.cache import get_cached

        mock_redis.get.return_value = None
        assert await get_cached("k", default="dflt") == "dflt"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cached_redis_error_returns_default(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify get_cached returns default on RedisError."""
        from fragrance_rater.core.cache import get_cached

        mock_redis.get.side_effect = RedisError("nope")
        assert await get_cached("k", default=99) == 99


class TestSetCached:
    """Tests for set_cached."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_cached_success(self, mock_redis: AsyncMock) -> None:
        """Verify set_cached returns True and calls setex."""
        from fragrance_rater.core.cache import set_cached

        assert await set_cached("k", {"a": 1}, ttl=42) is True
        args, _ = mock_redis.setex.call_args
        assert args[0] == "k"
        assert args[1] == 42

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_cached_redis_error(self, mock_redis: AsyncMock) -> None:
        """Verify set_cached returns False on RedisError."""
        from fragrance_rater.core.cache import set_cached

        mock_redis.setex.side_effect = RedisError("nope")
        assert await set_cached("k", "v") is False


class TestDeleteCached:
    """Tests for delete_cached."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_cached_existing_returns_true(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify delete_cached returns True when a key is removed."""
        from fragrance_rater.core.cache import delete_cached

        mock_redis.delete.return_value = 1
        assert await delete_cached("k") is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_cached_missing_returns_false(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify delete_cached returns False when nothing was removed."""
        from fragrance_rater.core.cache import delete_cached

        mock_redis.delete.return_value = 0
        assert await delete_cached("k") is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_cached_redis_error(self, mock_redis: AsyncMock) -> None:
        """Verify delete_cached returns False on RedisError."""
        from fragrance_rater.core.cache import delete_cached

        mock_redis.delete.side_effect = RedisError("nope")
        assert await delete_cached("k") is False


# ============================================================================
# invalidate_pattern
# ============================================================================


class TestInvalidatePattern:
    """Tests for invalidate_pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_pattern_deletes_matched_keys(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify invalidate_pattern issues a batched delete for found keys."""
        from fragrance_rater.core.cache import invalidate_pattern

        mock_redis.scan_iter = MagicMock(return_value=_AsyncIter(["a", "b", "c"]))
        mock_redis.delete.return_value = 3

        count = await invalidate_pattern("things:*")
        assert count == 3
        args, _ = mock_redis.delete.call_args
        assert args == ("a", "b", "c")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_matches_returns_zero(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify invalidate_pattern returns 0 when scan yields nothing."""
        from fragrance_rater.core.cache import invalidate_pattern

        mock_redis.scan_iter = MagicMock(return_value=_AsyncIter([]))
        count = await invalidate_pattern("nope:*")
        assert count == 0
        mock_redis.delete.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalidate_pattern_redis_error_returns_zero(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify invalidate_pattern returns 0 on RedisError."""
        from fragrance_rater.core.cache import invalidate_pattern

        def raise_err(*_a: Any, **_k: Any) -> None:
            raise RedisError("scan failed")

        mock_redis.scan_iter = MagicMock(side_effect=raise_err)
        count = await invalidate_pattern("things:*")
        assert count == 0


# ============================================================================
# warm_cache
# ============================================================================


class TestWarmCache:
    """Tests for warm_cache."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_warm_cache_skips_when_key_exists(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify warm_cache returns False when key exists and not forced."""
        from fragrance_rater.core.cache import warm_cache

        mock_redis.exists.return_value = 1

        async def producer() -> dict:
            return {"v": 1}

        result = await warm_cache("k", producer)
        assert result is False
        mock_redis.setex.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_warm_cache_writes_when_missing(self, mock_redis: AsyncMock) -> None:
        """Verify warm_cache computes and stores the value when missing."""
        from fragrance_rater.core.cache import warm_cache

        mock_redis.exists.return_value = 0
        called = {"n": 0}

        async def producer() -> dict:
            called["n"] += 1
            return {"v": 7}

        result = await warm_cache("k", producer, ttl=30)
        assert result is True
        assert called["n"] == 1
        mock_redis.setex.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_warm_cache_force_overwrites(self, mock_redis: AsyncMock) -> None:
        """Verify force=True bypasses the exists check."""
        from fragrance_rater.core.cache import warm_cache

        mock_redis.exists.return_value = 1

        async def producer() -> dict:
            return {"v": 9}

        result = await warm_cache("k", producer, force=True)
        assert result is True
        mock_redis.setex.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_warm_cache_redis_error_returns_false(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify warm_cache returns False on RedisError."""
        from fragrance_rater.core.cache import warm_cache

        mock_redis.exists.side_effect = RedisError("nope")

        async def producer() -> dict:
            return {"v": 1}

        result = await warm_cache("k", producer)
        assert result is False


# ============================================================================
# get_cache_stats
# ============================================================================


class TestGetCacheStats:
    """Tests for get_cache_stats."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cache_stats_returns_calculated_hit_rate(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify get_cache_stats computes hit_rate as a percentage."""
        from fragrance_rater.core.cache import get_cache_stats

        mock_redis.info.return_value = {
            "keyspace_hits": 75,
            "keyspace_misses": 25,
            "used_memory_human": "1M",
            "connected_clients": 3,
        }

        stats = await get_cache_stats()
        assert stats["hits"] == 75
        assert stats["misses"] == 25
        assert stats["hit_rate"] == 75.0
        assert stats["memory_used"] == "1M"
        assert stats["connected_clients"] == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cache_stats_redis_error_returns_error_dict(
        self, mock_redis: AsyncMock
    ) -> None:
        """Verify get_cache_stats returns {'error': ...} on RedisError."""
        from fragrance_rater.core.cache import get_cache_stats

        mock_redis.info.side_effect = RedisError("info failed")
        stats = await get_cache_stats()
        assert "error" in stats
