"""Tests for security middleware.

This module provides comprehensive tests for the security middleware
covering:
- SecurityHeadersMiddleware: OWASP security headers injection
- RateLimitMiddleware: per-IP rate limiting and burst detection
- SSRFPreventionMiddleware: SSRF URL validation and private IP detection
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fragrance_rater.middleware.security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    SSRFPreventionMiddleware,
    add_security_middleware,
)

if TYPE_CHECKING:
    from starlette.middleware.base import BaseHTTPMiddleware


def _build_app(
    middleware_cls: type[BaseHTTPMiddleware],
    **mw_kwargs: object,
) -> FastAPI:
    """Create a tiny FastAPI app with a single middleware and ping endpoint."""
    app = FastAPI()
    app.add_middleware(middleware_cls, **mw_kwargs)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware dispatch."""

    @pytest.mark.unit
    def test_security_headers_added(self) -> None:
        """Verify all OWASP security headers are added to the response."""
        app = _build_app(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/ping")

        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response.headers
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "geolocation=()" in response.headers["Permissions-Policy"]

    @pytest.mark.unit
    def test_hsts_added_on_https(self) -> None:
        """Verify HSTS header is added only for HTTPS requests."""
        app = _build_app(SecurityHeadersMiddleware)
        client = TestClient(app, base_url="https://testserver")

        response = client.get("/ping")

        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]

    @pytest.mark.unit
    def test_hsts_absent_on_http(self) -> None:
        """Verify HSTS header is not added on plain HTTP."""
        app = _build_app(SecurityHeadersMiddleware)
        client = TestClient(app, base_url="http://testserver")

        response = client.get("/ping")

        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.unit
    def test_server_header_removed(self) -> None:
        """Verify server header is removed if present in downstream response."""
        from starlette.responses import JSONResponse

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/leak")
        async def leak() -> JSONResponse:
            return JSONResponse({"ok": True}, headers={"server": "leaky/1.0"})

        client = TestClient(app)
        response = client.get("/leak")

        assert "server" not in {k.lower() for k in response.headers}


class TestRateLimitMiddlewareInit:
    """Tests for RateLimitMiddleware initialization."""

    @pytest.mark.unit
    def test_init_defaults(self) -> None:
        """Verify default constructor values."""
        app = FastAPI()
        middleware = RateLimitMiddleware(app)

        assert middleware.requests_per_minute == 60
        assert middleware.burst_size == 10
        assert middleware.max_tracked_ips == 10000
        assert middleware.cleanup_interval == 300
        assert middleware.requests == {}

    @pytest.mark.unit
    def test_init_custom_values(self) -> None:
        """Verify custom constructor values are honored."""
        app = FastAPI()
        middleware = RateLimitMiddleware(
            app,
            requests_per_minute=5,
            burst_size=2,
            max_tracked_ips=100,
            cleanup_interval=10,
        )

        assert middleware.requests_per_minute == 5
        assert middleware.burst_size == 2
        assert middleware.max_tracked_ips == 100
        assert middleware.cleanup_interval == 10


class TestRateLimitMiddlewareDispatch:
    """Tests for RateLimitMiddleware dispatch behavior."""

    @pytest.mark.unit
    def test_allows_request_under_limit(self) -> None:
        """Verify requests under the limit pass through."""
        app = _build_app(
            RateLimitMiddleware,
            requests_per_minute=10,
            burst_size=10,
        )
        client = TestClient(app)

        response = client.get("/ping")

        assert response.status_code == 200

    @pytest.mark.unit
    def test_returns_429_over_limit(self) -> None:
        """Verify 429 returned once requests_per_minute is exceeded."""
        app = _build_app(
            RateLimitMiddleware,
            requests_per_minute=2,
            burst_size=100,
        )
        client = TestClient(app)

        first = client.get("/ping")
        second = client.get("/ping")
        third = client.get("/ping")

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        body = third.json()
        assert body["error"] == "Too Many Requests"
        assert third.headers["Retry-After"] == "60"

    @pytest.mark.unit
    def test_returns_429_on_burst(self) -> None:
        """Verify burst limit triggers 429 with retry-after 1."""
        app = _build_app(
            RateLimitMiddleware,
            requests_per_minute=1000,
            burst_size=1,
        )
        client = TestClient(app)

        first = client.get("/ping")
        second = client.get("/ping")

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers["Retry-After"] == "1"
        assert "Burst limit" in second.json()["message"]


class TestRateLimitCleanup:
    """Tests for _cleanup_stale_entries."""

    @pytest.mark.unit
    def test_cleanup_skips_when_interval_not_elapsed(self) -> None:
        """Verify cleanup is skipped if cleanup_interval has not passed."""
        app = FastAPI()
        middleware = RateLimitMiddleware(app, cleanup_interval=300)
        now = time.time()
        middleware._last_cleanup = now
        middleware.requests["1.1.1.1"] = [
            now - 1000
        ]  # stale, but should not be cleaned

        middleware._cleanup_stale_entries(now + 10)

        assert "1.1.1.1" in middleware.requests

    @pytest.mark.unit
    def test_cleanup_removes_expired_timestamps(self) -> None:
        """Verify expired timestamps are removed and empty IPs deleted."""
        app = FastAPI()
        middleware = RateLimitMiddleware(app, cleanup_interval=1)
        now = time.time()
        middleware._last_cleanup = now - 1000
        middleware.requests["recent"] = [now - 10, now - 5]
        middleware.requests["stale"] = [now - 200]

        middleware._cleanup_stale_entries(now)

        assert "recent" in middleware.requests
        assert middleware.requests["recent"] == [now - 10, now - 5]
        assert "stale" not in middleware.requests

    @pytest.mark.unit
    def test_cleanup_lru_evicts_when_over_max(self) -> None:
        """Verify LRU eviction when tracked IPs exceed max_tracked_ips."""
        app = FastAPI()
        middleware = RateLimitMiddleware(
            app,
            max_tracked_ips=2,
            cleanup_interval=1,
        )
        now = time.time()
        middleware._last_cleanup = now - 1000
        # All recent so the timestamp filter retains them.
        middleware.requests["oldest"] = [now - 50]
        middleware.requests["middle"] = [now - 30]
        middleware.requests["newest"] = [now - 5]

        middleware._cleanup_stale_entries(now)

        assert len(middleware.requests) == 2
        assert "newest" in middleware.requests
        assert "middle" in middleware.requests
        assert "oldest" not in middleware.requests


class TestSSRFPrivateIP:
    """Tests for SSRFPreventionMiddleware._is_private_ip."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.5",
            "192.168.1.1",
            "169.254.169.254",
            ".".join(["0"] * 4),
            "::1",
        ],
    )
    def test_private_ips_blocked(self, ip: str) -> None:
        """Verify private/loopback/link-local IPs are blocked."""
        assert SSRFPreventionMiddleware._is_private_ip(ip) is True

    @pytest.mark.unit
    @pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34"])
    def test_public_ips_allowed(self, ip: str) -> None:
        """Verify public IPs are not flagged as private."""
        assert SSRFPreventionMiddleware._is_private_ip(ip) is False

    @pytest.mark.unit
    def test_invalid_ip_returns_false(self) -> None:
        """Verify non-IP strings return False (hostname check handles them)."""
        assert SSRFPreventionMiddleware._is_private_ip("not-an-ip") is False


class TestSSRFBlockedURL:
    """Tests for SSRFPreventionMiddleware._is_blocked_url and helpers."""

    @pytest.mark.unit
    def test_extract_host_valid(self) -> None:
        """Verify host extraction from a valid URL."""
        assert (
            SSRFPreventionMiddleware._extract_host_from_url("http://example.com/x")
            == "example.com"
        )

    @pytest.mark.unit
    def test_extract_scheme_valid(self) -> None:
        """Verify scheme extraction."""
        assert (
            SSRFPreventionMiddleware._extract_scheme_from_url("HTTPS://example.com")
            == "https"
        )

    @pytest.mark.unit
    def test_extract_scheme_empty(self) -> None:
        """Verify scheme extraction returns None for schemeless URL."""
        assert SSRFPreventionMiddleware._extract_scheme_from_url("//host/x") is None

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/x",
            "http://10.0.0.1/x",
            "http://192.168.1.5/x",
            "http://localhost/x",
            "http://169.254.169.254/latest/meta-data/",
            "file:///etc/passwd",
            "gopher://example.com",
            "http://metadata.google.internal/x",
        ],
    )
    def test_blocked_urls(self, url: str) -> None:
        """Verify malicious or internal URLs are blocked."""
        middleware = SSRFPreventionMiddleware(app=FastAPI())
        assert middleware._is_blocked_url(url) is True

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/x",
            "https://1.1.1.1/path",
            "https://api.github.com/repos",
        ],
    )
    def test_allowed_urls(self, url: str) -> None:
        """Verify external/public URLs are not blocked."""
        middleware = SSRFPreventionMiddleware(app=FastAPI())
        assert middleware._is_blocked_url(url) is False

    @pytest.mark.unit
    def test_blocked_url_no_host(self) -> None:
        """Verify URL with no parseable host returns False."""
        middleware = SSRFPreventionMiddleware(app=FastAPI())
        assert middleware._is_blocked_url("not a url at all") is False

    @pytest.mark.unit
    def test_blocked_url_decimal_ip(self) -> None:
        """Verify decimal IP obfuscation (2130706433 = 127.0.0.1) is blocked."""
        middleware = SSRFPreventionMiddleware(app=FastAPI())
        assert middleware._is_blocked_url("http://2130706433/x") is True


class TestSSRFDispatch:
    """Tests for SSRFPreventionMiddleware dispatch."""

    @pytest.mark.unit
    def test_blocks_request_with_blocked_url_query(self) -> None:
        """Verify request with SSRF query param is rejected with 400."""
        app = _build_app(SSRFPreventionMiddleware)
        client = TestClient(app)

        response = client.get("/ping", params={"target": "http://127.0.0.1/admin"})

        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "Bad Request"
        assert "target" in body["detail"]

    @pytest.mark.unit
    def test_allows_request_without_url_query(self) -> None:
        """Verify requests without URL-looking query params pass through."""
        app = _build_app(SSRFPreventionMiddleware)
        client = TestClient(app)

        response = client.get("/ping", params={"name": "vanilla"})

        assert response.status_code == 200

    @pytest.mark.unit
    def test_allows_request_with_safe_url_query(self) -> None:
        """Verify requests with public URL query params pass through."""
        app = _build_app(SSRFPreventionMiddleware)
        client = TestClient(app)

        response = client.get("/ping", params={"url": "https://example.com/api"})

        assert response.status_code == 200


class TestAddSecurityMiddleware:
    """Tests for add_security_middleware integration helper."""

    @pytest.mark.unit
    def test_add_all_middleware(self) -> None:
        """Verify add_security_middleware wires up middleware without error."""
        app = FastAPI()

        @app.get("/ping")
        async def ping() -> dict[str, str]:
            return {"status": "ok"}

        add_security_middleware(
            app,
            enable_https_redirect=False,
            enable_rate_limiting=True,
            enable_ssrf_prevention=True,
            allowed_origins=["https://example.com"],
            allowed_hosts=["testserver"],
            rate_limit_rpm=100,
        )

        client = TestClient(app)
        response = client.get("/ping")

        assert response.status_code == 200
        assert response.headers["X-Frame-Options"] == "DENY"
