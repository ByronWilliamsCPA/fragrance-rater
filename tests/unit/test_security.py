"""Tests for the OWASP security middleware stack."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from fragrance_rater.middleware.security import (
    SecurityHeadersMiddleware,
    SSRFPreventionMiddleware,
    add_security_middleware,
)


def _build_app(middleware_cls, **options) -> FastAPI:
    """Create a minimal app with a single middleware and a root route."""
    app = FastAPI()
    app.add_middleware(middleware_cls, **options)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/with-server-header")
    async def with_server_header() -> Response:
        return Response(content="ok", headers={"Server": "secret-server"})

    return app


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    def test_adds_owasp_headers(self) -> None:
        client = TestClient(_build_app(SecurityHeadersMiddleware))

        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "geolocation=()" in response.headers["Permissions-Policy"]

    def test_no_hsts_over_http(self) -> None:
        client = TestClient(_build_app(SecurityHeadersMiddleware))

        response = client.get("/")

        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_over_https(self) -> None:
        client = TestClient(
            _build_app(SecurityHeadersMiddleware), base_url="https://testserver"
        )

        response = client.get("/")

        assert response.headers["Strict-Transport-Security"].startswith(
            "max-age=31536000"
        )

    def test_strips_server_header(self) -> None:
        client = TestClient(_build_app(SecurityHeadersMiddleware))

        response = client.get("/with-server-header")

        assert response.status_code == 200
        assert "Server" not in response.headers


class TestSSRFPreventionMiddleware:
    """Tests for SSRFPreventionMiddleware."""

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "gopher://example.com/",
            "http://localhost/admin",
            "http://127.0.0.1/",
            "http://10.0.0.5/internal",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/",
            "http://[::1]/",
            "http://[::ffff:127.0.0.1]/",
            "http://2130706433/",
        ],
    )
    def test_blocks_internal_destinations(self, url: str) -> None:
        middleware = SSRFPreventionMiddleware(app=FastAPI())

        assert middleware._is_blocked_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/api",
            "http://8.8.8.8/",
            "http://4294967296/",
            "mailto:someone@example.com",
            "http://[::1",
            "not a url at all",
        ],
    )
    def test_allows_public_or_unparseable_destinations(self, url: str) -> None:
        middleware = SSRFPreventionMiddleware(app=FastAPI())

        assert middleware._is_blocked_url(url) is False

    def test_is_private_ip_rejects_non_ip_strings(self) -> None:
        assert SSRFPreventionMiddleware._is_private_ip("example.com") is False

    def test_url_helpers_return_none_for_malformed_urls(self) -> None:
        assert SSRFPreventionMiddleware._extract_host_from_url("http://[::1") is None
        assert SSRFPreventionMiddleware._extract_scheme_from_url("http://[::1") is None

    def test_dispatch_blocks_query_param_pointing_at_loopback(self) -> None:
        client = TestClient(_build_app(SSRFPreventionMiddleware))

        response = client.get("/", params={"url": "http://127.0.0.1/admin"})

        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "Bad Request"
        assert "url" in body["detail"]

    def test_dispatch_blocks_protocol_relative_url(self) -> None:
        client = TestClient(_build_app(SSRFPreventionMiddleware))

        response = client.get("/", params={"callback": "//localhost/hook"})

        assert response.status_code == 400

    def test_dispatch_allows_public_and_plain_params(self) -> None:
        client = TestClient(_build_app(SSRFPreventionMiddleware))

        assert client.get("/", params={"url": "https://example.com"}).status_code == 200
        assert client.get("/", params={"q": "plain text"}).status_code == 200


class TestAddSecurityMiddleware:
    """Tests for the add_security_middleware factory."""

    @staticmethod
    def _middleware_classes(app: FastAPI) -> list[type]:
        return [m.cls for m in app.user_middleware]

    def test_default_stack(self) -> None:
        app = FastAPI()

        add_security_middleware(app)

        classes = self._middleware_classes(app)
        assert CORSMiddleware in classes
        assert SecurityHeadersMiddleware in classes
        assert SSRFPreventionMiddleware in classes
        assert HTTPSRedirectMiddleware not in classes
        assert TrustedHostMiddleware not in classes

    def test_optional_layers_can_be_disabled(self) -> None:
        app = FastAPI()

        add_security_middleware(app, enable_ssrf_prevention=False)

        classes = self._middleware_classes(app)
        assert SSRFPreventionMiddleware not in classes
        assert SecurityHeadersMiddleware in classes

    def test_production_layers_enabled_on_request(self) -> None:
        app = FastAPI()

        add_security_middleware(
            app,
            enable_https_redirect=True,
            allowed_hosts=["api.example.com"],
            allowed_origins=["https://example.com"],
        )

        classes = self._middleware_classes(app)
        assert HTTPSRedirectMiddleware in classes
        assert TrustedHostMiddleware in classes

    def test_configured_app_serves_requests_with_headers(self) -> None:
        app = FastAPI()
        add_security_middleware(app)

        @app.get("/")
        async def root() -> dict[str, str]:
            return {"status": "ok"}

        response = TestClient(app).get("/")

        assert response.status_code == 200
        assert response.headers["X-Frame-Options"] == "DENY"
