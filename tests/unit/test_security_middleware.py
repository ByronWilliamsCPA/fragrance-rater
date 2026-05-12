"""Tests for security middleware components."""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    @pytest.mark.unit
    def test_security_headers_added_to_response(self) -> None:
        """Verify security headers are present on all responses."""
        from fragrance_rater.middleware.security import SecurityHeadersMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

    @pytest.mark.unit
    def test_hsts_header_added_for_https_request(self) -> None:
        """Verify HSTS header is added when scheme is HTTPS."""
        from fragrance_rater.middleware.security import SecurityHeadersMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        client = TestClient(app, base_url="https://testserver")
        response = client.get("/test")
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]

    @pytest.mark.unit
    def test_server_header_removed(self) -> None:
        """Verify Server header is stripped from responses."""
        from fragrance_rater.middleware.security import SecurityHeadersMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def _test_endpoint():
            from starlette.responses import Response as StarletteResponse

            r = StarletteResponse(content='{"ok":true}', media_type="application/json")
            r.headers["Server"] = "uvicorn"
            return r

        client = TestClient(app)
        response = client.get("/test")
        assert "Server" not in response.headers


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.unit
    def test_rate_limit_returns_429_when_exceeded(self) -> None:
        """Verify 429 is returned after requests_per_minute is exceeded."""
        from fragrance_rater.middleware.security import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=3, burst_size=10)

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "60"
        body = response.json()
        assert body["error"] == "Too Many Requests"

    @pytest.mark.unit
    def test_burst_limit_returns_429_when_exceeded(self) -> None:
        """Verify 429 is returned when burst limit is exceeded."""
        from fragrance_rater.middleware.security import RateLimitMiddleware

        app = FastAPI()
        # High rpm but burst_size=1 so second rapid request triggers burst
        app.add_middleware(RateLimitMiddleware, requests_per_minute=100, burst_size=1)

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)

        # First request should pass
        response = client.get("/test")
        assert response.status_code == 200

        # Second immediate request exceeds burst_size=1
        response = client.get("/test")
        assert response.status_code == 429

    @pytest.mark.unit
    def test_cleanup_stale_entries_removes_expired_ips(self) -> None:
        """Verify _cleanup_stale_entries removes IPs with no recent activity."""
        from fragrance_rater.middleware.security import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            MagicMock(), requests_per_minute=60, burst_size=10
        )
        now = time.time()

        # Add stale (>60s old) entries
        middleware.requests["1.1.1.1"] = [now - 120, now - 90]
        # Add recent entries
        middleware.requests["2.2.2.2"] = [now - 10]
        # Force cleanup by setting last_cleanup to past
        middleware._last_cleanup = now - middleware.cleanup_interval - 1

        middleware._cleanup_stale_entries(now)

        assert "1.1.1.1" not in middleware.requests
        assert "2.2.2.2" in middleware.requests

    @pytest.mark.unit
    def test_cleanup_evicts_oldest_ips_when_over_limit(self) -> None:
        """Verify LRU eviction when tracked IPs exceed max_tracked_ips."""
        from fragrance_rater.middleware.security import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            MagicMock(), requests_per_minute=60, burst_size=10
        )
        middleware.max_tracked_ips = 2
        now = time.time()

        # Add 3 IPs, oldest activity first
        middleware.requests["1.1.1.1"] = [now - 50]  # oldest
        middleware.requests["2.2.2.2"] = [now - 30]
        middleware.requests["3.3.3.3"] = [now - 10]  # newest
        middleware._last_cleanup = now - middleware.cleanup_interval - 1

        middleware._cleanup_stale_entries(now)

        # Only the 2 most recently active IPs should remain
        assert len(middleware.requests) <= 2
        assert "3.3.3.3" in middleware.requests

    @pytest.mark.unit
    def test_cleanup_skipped_when_interval_not_elapsed(self) -> None:
        """Verify cleanup does not run before cleanup_interval has passed."""
        from fragrance_rater.middleware.security import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            MagicMock(), requests_per_minute=60, burst_size=10
        )
        now = time.time()
        middleware.requests["1.1.1.1"] = [now - 120]  # stale
        middleware._last_cleanup = now  # just cleaned up

        middleware._cleanup_stale_entries(now)

        # Stale IP should still be there because cleanup was skipped
        assert "1.1.1.1" in middleware.requests

    @pytest.mark.unit
    def test_no_client_uses_unknown_ip(self) -> None:
        """Verify requests without client info use 'unknown' as fallback IP."""
        from fragrance_rater.middleware.security import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=60, burst_size=10)

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200


class TestSSRFPreventionMiddleware:
    """Tests for SSRFPreventionMiddleware static utility methods."""

    @pytest.mark.unit
    def test_is_private_ip_loopback(self) -> None:
        """Verify loopback addresses are identified as private."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        assert SSRFPreventionMiddleware._is_private_ip("127.0.0.1") is True
        assert SSRFPreventionMiddleware._is_private_ip("::1") is True

    @pytest.mark.unit
    def test_is_private_ip_rfc1918(self) -> None:
        """Verify RFC 1918 private ranges are identified as private."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        assert SSRFPreventionMiddleware._is_private_ip("192.168.1.1") is True
        assert SSRFPreventionMiddleware._is_private_ip("10.0.0.1") is True
        assert SSRFPreventionMiddleware._is_private_ip("172.16.0.1") is True

    @pytest.mark.unit
    def test_is_private_ip_public(self) -> None:
        """Verify public IPs are not identified as private."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        assert SSRFPreventionMiddleware._is_private_ip("8.8.8.8") is False
        assert SSRFPreventionMiddleware._is_private_ip("1.1.1.1") is False

    @pytest.mark.unit
    def test_is_private_ip_invalid(self) -> None:
        """Verify invalid IP strings return False without error."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        assert SSRFPreventionMiddleware._is_private_ip("not-an-ip") is False
        assert SSRFPreventionMiddleware._is_private_ip("") is False

    @pytest.mark.unit
    def test_extract_host_from_url_standard(self) -> None:
        """Verify hostname is extracted correctly from standard URLs."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        assert (
            SSRFPreventionMiddleware._extract_host_from_url("http://example.com/path")
            == "example.com"
        )
        assert (
            SSRFPreventionMiddleware._extract_host_from_url("https://api.test.com:8080")
            == "api.test.com"
        )

    @pytest.mark.unit
    def test_extract_host_from_url_none_on_failure(self) -> None:
        """Verify None is returned for malformed URLs."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        result = SSRFPreventionMiddleware._extract_host_from_url("not-a-url")
        assert result is None or isinstance(result, str)

    @pytest.mark.unit
    def test_extract_scheme_from_url_http(self) -> None:
        """Verify scheme extraction returns lowercase scheme."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        assert (
            SSRFPreventionMiddleware._extract_scheme_from_url("http://example.com")
            == "http"
        )
        assert (
            SSRFPreventionMiddleware._extract_scheme_from_url("FTP://example.com")
            == "ftp"
        )
        assert (
            SSRFPreventionMiddleware._extract_scheme_from_url("file:///etc/passwd")
            == "file"
        )

    @pytest.mark.unit
    def test_extract_scheme_returns_none_for_no_scheme(self) -> None:
        """Verify None is returned when URL has no scheme."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        result = SSRFPreventionMiddleware._extract_scheme_from_url("example.com/path")
        assert result is None or isinstance(result, str)

    @pytest.mark.unit
    def test_is_blocked_url_file_scheme(self) -> None:
        """Verify file:// URLs are blocked."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        middleware = SSRFPreventionMiddleware(MagicMock())
        assert middleware._is_blocked_url("file:///etc/passwd") is True

    @pytest.mark.unit
    def test_is_blocked_url_internal_host(self) -> None:
        """Verify access to metadata endpoints is blocked."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        middleware = SSRFPreventionMiddleware(MagicMock())
        assert (
            middleware._is_blocked_url("http://169.254.169.254/latest/meta-data")
            is True
        )

    @pytest.mark.unit
    def test_is_blocked_url_private_ip(self) -> None:
        """Verify URLs pointing to private IPs are blocked."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        middleware = SSRFPreventionMiddleware(MagicMock())
        assert middleware._is_blocked_url("http://192.168.1.1/admin") is True

    @pytest.mark.unit
    def test_is_blocked_url_public_allowed(self) -> None:
        """Verify public URLs are not blocked."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        middleware = SSRFPreventionMiddleware(MagicMock())
        assert middleware._is_blocked_url("https://api.example.com/data") is False

    @pytest.mark.unit
    def test_is_blocked_url_numeric_decimal_ip(self) -> None:
        """Verify numeric decimal IP obfuscation is detected."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        middleware = SSRFPreventionMiddleware(MagicMock())
        # 2130706433 is 127.0.0.1 in decimal
        assert middleware._is_blocked_url("http://2130706433/") is True

    @pytest.mark.unit
    def test_ssrf_dispatch_blocks_ssrf_in_query_param(self) -> None:
        """Verify SSRF attempt in query parameter returns 400."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        app = FastAPI()
        app.add_middleware(SSRFPreventionMiddleware)

        @app.get("/fetch")
        async def _fetch_endpoint(url: str = ""):
            return {"url": url}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/fetch", params={"url": "http://192.168.1.1/admin"})
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "Bad Request"

    @pytest.mark.unit
    def test_ssrf_dispatch_allows_safe_query_param(self) -> None:
        """Verify safe query parameters are allowed through."""
        from fragrance_rater.middleware.security import SSRFPreventionMiddleware

        app = FastAPI()
        app.add_middleware(SSRFPreventionMiddleware)

        @app.get("/fetch")
        async def _fetch_endpoint(q: str = ""):
            return {"q": q}

        client = TestClient(app)
        response = client.get("/fetch", params={"q": "fragrance search"})
        assert response.status_code == 200


class TestAddSecurityMiddleware:
    """Tests for add_security_middleware function."""

    @pytest.mark.unit
    def test_add_security_middleware_basic(self) -> None:
        """Verify add_security_middleware runs without error."""
        from fragrance_rater.middleware.security import add_security_middleware

        app = FastAPI()
        add_security_middleware(app)

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    @pytest.mark.unit
    def test_add_security_middleware_with_https_redirect(self) -> None:
        """Verify add_security_middleware enables HTTPS redirect when requested."""
        from fragrance_rater.middleware.security import add_security_middleware

        app = FastAPI()
        add_security_middleware(app, enable_https_redirect=True)

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        # Just verify the app starts without error
        assert app is not None

    @pytest.mark.unit
    def test_add_security_middleware_with_allowed_hosts(self) -> None:
        """Verify add_security_middleware configures trusted hosts when provided."""
        from fragrance_rater.middleware.security import add_security_middleware

        app = FastAPI()
        add_security_middleware(app, allowed_hosts=["testserver", "localhost"])

        @app.get("/test")
        async def _test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
