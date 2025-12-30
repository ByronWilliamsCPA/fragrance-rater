"""Tests for Redis caching utilities."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fragrance_rater.core import cache


class TestGetRedis:
    """Tests for get_redis connection management."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_creates_connection_pool(self) -> None:
        """Should create a new connection pool on first call."""
        mock_redis = MagicMock()

        with patch.object(cache, "from_url", return_value=mock_redis) as mock_from_url:
            result = await cache.get_redis()

            assert result == mock_redis
            mock_from_url.assert_called_once()
            # Verify connection parameters
            call_kwargs = mock_from_url.call_args[1]
            assert call_kwargs["decode_responses"] is True
            assert call_kwargs["max_connections"] == 50

    @pytest.mark.asyncio
    async def test_reuses_existing_pool(self) -> None:
        """Should reuse existing connection pool on subsequent calls."""
        mock_redis = MagicMock()
        cache._redis_pool = mock_redis

        result = await cache.get_redis()

        assert result == mock_redis

    @pytest.mark.asyncio
    async def test_uses_redis_url_from_env(self) -> None:
        """Should use REDIS_URL from environment."""
        with (
            patch.dict("os.environ", {"REDIS_URL": "redis://custom:6380/1"}),
            patch.object(cache, "from_url", return_value=MagicMock()) as mock_from_url,
        ):
            await cache.get_redis()

            mock_from_url.assert_called_once()
            assert mock_from_url.call_args[0][0] == "redis://custom:6380/1"


class TestCloseRedis:
    """Tests for close_redis cleanup."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_closes_connection_pool(self) -> None:
        """Should close the connection pool and reset global."""
        mock_redis = AsyncMock()
        cache._redis_pool = mock_redis

        await cache.close_redis()

        mock_redis.close.assert_called_once()
        assert cache._redis_pool is None

    @pytest.mark.asyncio
    async def test_handles_no_pool(self) -> None:
        """Should handle case when pool is None."""
        cache._redis_pool = None

        # Should not raise
        await cache.close_redis()

        assert cache._redis_pool is None


class TestCachedDecorator:
    """Tests for the @cached decorator."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_cache_miss_calls_function(self) -> None:
        """Should call the function on cache miss."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Cache miss

        with patch.object(cache, "get_redis", return_value=mock_redis):
            @cache.cached(ttl=300)
            async def my_func(x: int) -> dict[str, int]:
                return {"value": x * 2}

            result = await my_func(5)

            assert result == {"value": 10}
            mock_redis.get.assert_called_once()
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self) -> None:
        """Should return cached value on cache hit."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"value": 100}'  # Cache hit

        call_count = 0

        with patch.object(cache, "get_redis", return_value=mock_redis):
            @cache.cached(ttl=300)
            async def my_func(x: int) -> dict[str, int]:
                nonlocal call_count
                call_count += 1
                return {"value": x * 2}

            result = await my_func(5)

            assert result == {"value": 100}
            assert call_count == 0  # Function was not called
            mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_custom_key_prefix(self) -> None:
        """Should use custom key prefix."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch.object(cache, "get_redis", return_value=mock_redis):
            @cache.cached(ttl=300, key_prefix="myprefix")
            async def my_func() -> str:
                return "result"

            await my_func()

            call_args = mock_redis.get.call_args[0][0]
            assert call_args.startswith("myprefix:")

    @pytest.mark.asyncio
    async def test_uses_custom_key_builder(self) -> None:
        """Should use custom key builder function."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        def custom_key(x: int) -> str:
            return f"custom:{x}"

        with patch.object(cache, "get_redis", return_value=mock_redis):
            @cache.cached(ttl=300, key_builder=custom_key)
            async def my_func(x: int) -> int:
                return x * 2

            await my_func(42)

            mock_redis.get.assert_called_with("custom:42")

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_redis_error(self) -> None:
        """Should call function directly when Redis fails."""
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Connection failed")

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),  # Mock structlog logger
        ):
            @cache.cached(ttl=300)
            async def my_func(x: int) -> int:
                return x * 2

            result = await my_func(5)

            assert result == 10


class TestCacheInvalidateDecorator:
    """Tests for the @cache_invalidate decorator."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_invalidates_pattern_after_function(self) -> None:
        """Should invalidate cache pattern after function executes."""
        with (
            patch.object(cache, "invalidate_pattern", new_callable=AsyncMock) as mock_invalidate,
            patch.object(cache, "logger"),
        ):
            mock_invalidate.return_value = 2

            @cache.cache_invalidate("user:*")
            async def update_user(user_id: str) -> str:
                return f"updated:{user_id}"

            result = await update_user("123")

            assert result == "updated:123"
            mock_invalidate.assert_called_once_with("user:*")

    @pytest.mark.asyncio
    async def test_handles_invalidation_error(self) -> None:
        """Should not fail if invalidation raises error."""
        from redis.exceptions import RedisError

        with (
            patch.object(cache, "invalidate_pattern", side_effect=RedisError("Failed")),
            patch.object(cache, "logger"),
        ):
            @cache.cache_invalidate("user:*")
            async def update_user() -> str:
                return "done"

            # Should not raise
            result = await update_user()
            assert result == "done"


class TestGetCached:
    """Tests for get_cached function."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_returns_cached_value(self) -> None:
        """Should return parsed JSON value from cache."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"name": "test"}'

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.get_cached("mykey")

            assert result == {"name": "test"}

    @pytest.mark.asyncio
    async def test_returns_default_on_miss(self) -> None:
        """Should return default value on cache miss."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.get_cached("mykey", default="fallback")

            assert result == "fallback"

    @pytest.mark.asyncio
    async def test_returns_default_on_error(self) -> None:
        """Should return default on Redis error."""
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Failed")

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.get_cached("mykey", default="error_default")

            assert result == "error_default"


class TestSetCached:
    """Tests for set_cached function."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_sets_value_with_ttl(self) -> None:
        """Should set value with TTL."""
        mock_redis = AsyncMock()

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.set_cached("mykey", {"data": 123}, ttl=600)

            assert result is True
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args[0]
            assert call_args[0] == "mykey"
            assert call_args[1] == 600
            assert json.loads(call_args[2]) == {"data": 123}

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self) -> None:
        """Should return False on Redis error."""
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = RedisError("Failed")

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.set_cached("mykey", "value")

            assert result is False


class TestDeleteCached:
    """Tests for delete_cached function."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_deletes_key(self) -> None:
        """Should delete key and return True."""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 1

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.delete_cached("mykey")

            assert result is True
            mock_redis.delete.assert_called_with("mykey")

    @pytest.mark.asyncio
    async def test_returns_false_if_not_found(self) -> None:
        """Should return False if key didn't exist."""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 0

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.delete_cached("nonexistent")

            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self) -> None:
        """Should return False on Redis error."""
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = RedisError("Failed")

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.delete_cached("mykey")

            assert result is False


class TestInvalidatePattern:
    """Tests for invalidate_pattern function."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_deletes_matching_keys(self) -> None:
        """Should find and delete keys matching pattern."""
        mock_redis = AsyncMock()

        # Create proper async iterator for scan_iter
        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            for key in ["user:1", "user:2", "user:3"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 3

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.invalidate_pattern("user:*")

            assert result == 3
            mock_redis.delete.assert_called_once_with("user:1", "user:2", "user:3")

    @pytest.mark.asyncio
    async def test_returns_zero_for_no_matches(self) -> None:
        """Should return 0 when no keys match."""
        mock_redis = AsyncMock()

        # Create proper async iterator that yields nothing
        async def mock_scan_iter(*args: Any, **kwargs: Any) -> Any:
            return
            yield  # Makes this an async generator  # noqa: B901

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete = AsyncMock()

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.invalidate_pattern("nonexistent:*")

            assert result == 0
            mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self) -> None:
        """Should return 0 on Redis error."""
        from redis.exceptions import RedisError

        mock_redis = MagicMock()

        # Create async generator that raises an error
        async def mock_scan_iter_error(*args: Any, **kwargs: Any) -> Any:
            raise RedisError("Failed")
            yield  # Makes this an async generator  # noqa: B901

        mock_redis.scan_iter = mock_scan_iter_error

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.invalidate_pattern("user:*")

            assert result == 0


class TestWarmCache:
    """Tests for warm_cache function."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_warms_cache_when_empty(self) -> None:
        """Should warm cache when key doesn't exist."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = False

        async def get_data() -> dict[str, str]:
            return {"warm": "data"}

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.warm_cache("mykey", get_data, ttl=600)

            assert result is True
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_already_warm(self) -> None:
        """Should skip warming when key exists and not forced."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True

        async def get_data() -> dict[str, str]:
            return {"warm": "data"}

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.warm_cache("mykey", get_data, ttl=600, force=False)

            assert result is False
            mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh(self) -> None:
        """Should refresh when force=True even if key exists."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True

        async def get_data() -> dict[str, str]:
            return {"fresh": "data"}

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.warm_cache("mykey", get_data, ttl=600, force=True)

            assert result is True
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self) -> None:
        """Should return False on Redis error."""
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.exists.side_effect = RedisError("Failed")

        async def get_data() -> str:
            return "data"

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.warm_cache("mykey", get_data)

            assert result is False


class TestGetCacheStats:
    """Tests for get_cache_stats function."""

    @pytest.fixture(autouse=True)
    def reset_pool(self) -> None:
        """Reset the global Redis pool before each test."""
        cache._redis_pool = None

    @pytest.mark.asyncio
    async def test_returns_stats(self) -> None:
        """Should return cache statistics."""
        mock_redis = AsyncMock()
        mock_redis.info.return_value = {
            "keyspace_hits": 100,
            "keyspace_misses": 20,
            "used_memory_human": "1.5M",
            "connected_clients": 5,
        }

        with patch.object(cache, "get_redis", return_value=mock_redis):
            result = await cache.get_cache_stats()

            assert result["hits"] == 100
            assert result["misses"] == 20
            assert result["hit_rate"] == pytest.approx(83.33, rel=0.01)
            assert result["memory_used"] == "1.5M"
            assert result["connected_clients"] == 5

    @pytest.mark.asyncio
    async def test_returns_error_on_failure(self) -> None:
        """Should return error dict on Redis error."""
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.info.side_effect = RedisError("Connection failed")

        with (
            patch.object(cache, "get_redis", return_value=mock_redis),
            patch.object(cache, "logger"),
        ):
            result = await cache.get_cache_stats()

            assert "error" in result
            assert "Connection failed" in result["error"]


# Helper class for async iteration
class AsyncIteratorMock:
    """Mock for async iterators like scan_iter."""

    def __init__(self, items: list[Any]) -> None:
        self.items = items
        self.index = 0

    def __aiter__(self) -> "AsyncIteratorMock":
        return self

    async def __anext__(self) -> Any:
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item
