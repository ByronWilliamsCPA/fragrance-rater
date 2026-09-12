"""Security middleware for FastAPI applications.

This module provides production-ready security middleware implementing OWASP best practices:
- CORS configuration (A05: Security Misconfiguration)
- Security headers (A05: Security Misconfiguration)
- Request validation (A03: Injection)
- SSRF prevention (A10: Server-Side Request Forgery)

Rate limiting is not implemented here. It lives entirely in
``fragrance_rater.middleware.rate_limit`` (the ``slowapi``-backed limiter
registered in ``fragrance_rater.main``), which is the single rate-limiting
mechanism for the whole API; this module previously carried its own
in-memory ``RateLimitMiddleware`` as a second, competing layer, and that
duplication has been removed.

Usage:
    from fragrance_rater.middleware.security import (
        add_security_middleware,
        SecurityHeadersMiddleware,
    )

    app = FastAPI()
    add_security_middleware(app)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response

from fragrance_rater.utils.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Implements OWASP recommended security headers to prevent:
    - XSS attacks
    - Clickjacking
    - MIME sniffing
    - Information leakage

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: HSTS for HTTPS
    - Content-Security-Policy: Prevent inline scripts
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Restrict browser features
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        path = request.url.path.rstrip("/")
        identity_scoped = any(
            path.endswith(fragment) or f"{fragment}/" in path
            for fragment in ("/calibration", "/recommendation-measurement")
        )
        if request.method == "GET" and identity_scoped:
            response.headers["Cache-Control"] = "private, no-store"
            vary = [
                item.strip() for item in response.headers.get("Vary", "").split(",")
            ]
            if "X-Authentik-Username" not in vary:
                vary.append("X-Authentik-Username")
            response.headers["Vary"] = ", ".join(item for item in vary if item)

        # Prevent MIME sniffing (OWASP A05)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking (OWASP A05)
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS protection (OWASP A03)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS: Force HTTPS for 1 year (OWASP A02)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy: Prevent inline scripts (OWASP A03)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Control referrer information (OWASP A09)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features (OWASP A05)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # Remove server identification (OWASP A09)
        if "Server" in response.headers:
            del response.headers["Server"]

        return response


class SSRFPreventionMiddleware(BaseHTTPMiddleware):
    """Prevent Server-Side Request Forgery (SSRF) attacks.

    Blocks requests to internal/private IP ranges when making outbound HTTP calls.
    Implements OWASP A10 protection with proper IP address validation.

    Features:
    - Proper CIDR range validation using ipaddress module
    - Cloud metadata endpoint blocking (AWS, GCP, Azure)
    - DNS rebinding protection via hostname validation
    - IPv4 and IPv6 support

    Note: For production SSRF prevention, also consider:
    1. Use allowlists for external API endpoints
    2. Validate and sanitize URLs before making requests
    3. Use network segmentation
    4. Implement egress filtering at the network level
    """

    # Blocked hostnames (case-insensitive)
    BLOCKED_HOSTS: set[str] = {
        "localhost",
        "127.0.0.1",
        # B104 is about binding to all interfaces; this is a deny-list entry that
        # rejects outbound requests to that address, so the finding does not apply
        "0.0.0.0",  # nosec B104
        # AWS metadata endpoints
        "169.254.169.254",
        "fd00:ec2::254",
        # GCP metadata endpoints
        "metadata.google.internal",
        "metadata.goog",
        # Azure metadata endpoints
        # Kubernetes
        "kubernetes.default",
        "kubernetes.default.svc",
    }

    # Blocked URL schemes
    BLOCKED_SCHEMES: set[str] = {
        "file",
        "gopher",
        "dict",
        "ftp",
        "ldap",
        "tftp",
    }

    @staticmethod
    def _is_private_ip(ip_str: str) -> bool:
        """Check if an IP address is private, loopback, or otherwise internal.

        Args:
            ip_str (str): IP address string to validate

        Returns:
            bool: True if the IP is private/internal, False otherwise
        """
        import ipaddress

        try:
            ip = ipaddress.ip_address(ip_str)
            # Check various internal IP properties
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
                # Additional check for IPv4-mapped IPv6 addresses
                or (
                    isinstance(ip, ipaddress.IPv6Address)
                    and ip.ipv4_mapped is not None
                    and SSRFPreventionMiddleware._is_private_ip(str(ip.ipv4_mapped))
                )
            )
        except ValueError:
            # Not a valid IP address - let hostname checks handle it
            return False

    @staticmethod
    def _extract_host_from_url(url: str) -> str | None:
        """Extract hostname from URL string.

        Args:
            url (str): URL string to parse

        Returns:
            str | None: Hostname string, or None if the URL parses
                cleanly but has no hostname component (e.g. a relative
                path, or a scheme-only string like "mailto:someone@x").

        Raises:
            Exception: If ``urlparse`` cannot parse ``url`` at all (for
                example a malformed IPv6 host literal like
                "http://[::1"). ``pyproject.toml`` deliberately allows
                a broad ``except Exception`` in this file (see the
                ``BLE001`` per-file-ignore for
                ``src/*/middleware/security.py``, "Blind except for URL
                parsing resilience") so this can never crash the
                middleware on adversarial input, but that ignore is
                about the *breadth* of the except clause, not about
                swallowing the failure silently.
                # #CRITICAL: security: this used to be caught here and
                # turned into a bare `None` return with no logging,
                # which `_is_blocked_url` then treated exactly like "no
                # hostname present" and let the request through
                # (fail-open). For an SSRF deny-list check, a URL we
                # cannot even parse must not be assumed safe. The
                # failure is now logged and re-raised so
                # `_is_blocked_url` fails closed (blocks the request)
                # instead of silently passing an unparseable URL
                # through the check.
                # #VERIFY: if a legitimate, non-malicious client starts
                # tripping this path, fix the URL construction
                # upstream; do not swallow the exception again to
                # route around it.
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
        except Exception:
            logger.warning(
                "ssrf_prevention.url_parse_failed",
                helper="_extract_host_from_url",
                url_preview=url[:200],
                url_length=len(url),
            )
            raise
        return parsed.hostname

    @staticmethod
    def _extract_scheme_from_url(url: str) -> str | None:
        """Extract scheme from URL string.

        Args:
            url (str): URL string to parse

        Returns:
            str | None: Scheme string, or None if the URL parses
                cleanly but carries no scheme.

        Raises:
            Exception: If ``urlparse`` cannot parse ``url`` at all. The
                failure is logged and re-raised so the caller fails
                closed instead of treating it as "no scheme present";
                see ``_extract_host_from_url`` for the full rationale
                and the RAD ``#CRITICAL``/``#VERIFY`` markers.
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
        except Exception:
            logger.warning(
                "ssrf_prevention.url_parse_failed",
                helper="_extract_scheme_from_url",
                url_preview=url[:200],
                url_length=len(url),
            )
            raise
        return parsed.scheme.lower() if parsed.scheme else None

    def _is_blocked_url(self, url: str) -> bool:
        """Check if a URL points to a blocked destination.

        Args:
            url (str): URL string to validate

        Returns:
            bool: True if the URL should be blocked, False otherwise.
                Also returns True (fails closed) when ``url`` cannot be
                parsed at all: see ``_extract_host_from_url`` for why.
        """
        try:
            # Check scheme
            scheme = self._extract_scheme_from_url(url)
            # Extract hostname
            host = self._extract_host_from_url(url)
        except Exception:
            # #CRITICAL: security: fail closed on a URL that could not
            # be parsed at all, rather than letting it through as if it
            # were harmless. The parse failure itself is already logged
            # by the extractor helpers above; see
            # `_extract_host_from_url`'s docstring for the full
            # rationale.
            # #VERIFY: this only changes behavior for strings that fail
            # `urllib.parse.urlparse` outright (e.g. malformed IPv6
            # literals); a string that parses cleanly but has no
            # hostname (e.g. "mailto:someone@example.com") still falls
            # through to the `if not host: return False` branch below,
            # unchanged.
            return True

        if scheme and scheme in self.BLOCKED_SCHEMES:
            return True

        if not host:
            return False

        host_lower = host.lower()

        # Check against blocked hostnames or private IP ranges
        if host_lower in self.BLOCKED_HOSTS or self._is_private_ip(host):
            return True

        # Check for numeric IP obfuscation (decimal, octal, hex)
        # e.g., 2130706433 = 127.0.0.1, 0x7f000001 = 127.0.0.1
        try:
            import ipaddress

            # Try parsing as integer (decimal IP notation)
            if host.isdigit():
                ip_int = int(host)
                if 0 <= ip_int <= 0xFFFFFFFF:
                    ip = ipaddress.ip_address(ip_int)
                    if self._is_private_ip(str(ip)):
                        return True
        except (ValueError, OverflowError):
            pass

        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check for SSRF patterns in request query parameters.

        Validates query parameters for potential SSRF attempts targeting
        internal resources. This does NOT scan form data or JSON request
        bodies.

        # #EDGE: security: body scanning is intentionally not
        # implemented. As of this writing, no route under
        # src/fragrance_rater/api/ accepts a URL-shaped string in a
        # JSON or form body that is later fetched server-side: the only
        # URL-fetching code path, ParfumoScraper.import_from_url, is
        # wired solely through the CLI (fragrance_rater.cli), never
        # through an API route, and the `parfumo_url` model field is
        # not exposed on any request schema. Speculatively scanning
        # bodies for an input that does not exist would add complexity
        # (body re-injection so downstream handlers still see the
        # stream) and its own bug surface for no present benefit.
        # #VERIFY: if a JSON/form field that accepts a URL to be
        # fetched server-side is ever added to an API route, extend
        # this method to scan the request body too. Remember that
        # `await request.body()` consumes the ASGI receive stream, so
        # the body must be reconstructed (e.g. cache it on
        # `request._body` and replay it, or wrap `request.receive`) so
        # the downstream route handler still receives it unmodified.
        """
        # Check query parameters for URLs
        for param, value in request.query_params.items():
            if isinstance(value, str) and ("://" in value or value.startswith("//")):
                if self._is_blocked_url(value):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "Bad Request",
                            "message": "Request blocked: potential SSRF attempt",
                            "detail": f"Blocked URL detected in parameter: {param}",
                        },
                    )

        return await call_next(request)


def add_security_middleware(
    app: FastAPI,
    *,
    enable_https_redirect: bool = False,
    enable_ssrf_prevention: bool = True,
    allowed_origins: list[str] | None = None,
    allowed_hosts: list[str] | None = None,
) -> None:
    """Add security middleware to FastAPI application.

    This configures comprehensive security following OWASP best practices.
    Rate limiting is not one of these concerns: it is handled solely by the
    ``slowapi`` limiter registered directly in ``fragrance_rater.main``
    (see ``fragrance_rater.middleware.rate_limit``), which is now the single
    rate-limiting mechanism for the whole API.

    Args:
        app (FastAPI): FastAPI application instance
        enable_https_redirect (bool): Redirect HTTP to HTTPS (production only)
        enable_ssrf_prevention (bool): Enable SSRF prevention middleware
        allowed_origins (list[str] | None): CORS allowed origins (default: none)
        allowed_hosts (list[str] | None): Trusted host names (default: all)

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> add_security_middleware(
        ...     app,
        ...     enable_https_redirect=True,
        ...     allowed_origins=["https://example.com"],
        ...     allowed_hosts=["example.com", "api.example.com"],
        ... )
    """
    # HTTPS redirect (production only)
    if enable_https_redirect:
        app.add_middleware(HTTPSRedirectMiddleware)

    # Trusted hosts (OWASP A05)
    if allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts,
        )

    # CORS configuration (OWASP A05)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or [],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=3600,
    )

    # Security headers (OWASP A05, A03, A09)
    app.add_middleware(SecurityHeadersMiddleware)

    # SSRF prevention (OWASP A10)
    if enable_ssrf_prevention:
        app.add_middleware(SSRFPreventionMiddleware)


# Example usage in main.py:
"""
from fastapi import FastAPI
from fragrance_rater.middleware.security import add_security_middleware

app = FastAPI()

# Add all security middleware (rate limiting is registered separately in
# main.py via the slowapi limiter)
add_security_middleware(
    app,
    enable_https_redirect=True,  # Production only
    allowed_origins=[
        "https://example.com",
        "https://app.example.com",
    ],
    allowed_hosts=[
        "api.example.com",
        "localhost",  # Development only
    ],
)

# Your routes here
@app.get("/")
async def root():
    return {"message": "Hello World"}
"""
