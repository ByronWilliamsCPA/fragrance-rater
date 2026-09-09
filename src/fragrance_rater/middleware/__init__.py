"""Security middleware for API applications.

This package exposes:

- the request-correlation middleware (``correlation``);
- the OWASP-aligned ``SecurityHeadersMiddleware``, ``SSRFPreventionMiddleware``
  and the ``add_security_middleware`` helper (``security``), wired in
  ``fragrance_rater.main``;
- the shared household API key dependency ``require_api_key`` (``auth``),
  applied only to the billed ``POST /ratings`` endpoint;
- the ``slowapi``-backed limiter, its RFC 7807 429 handler, and
  ``DefaultRateLimitMiddleware`` (a local replacement for
  ``slowapi.middleware.SlowAPIMiddleware``, which does not enforce
  ``default_limits`` on this codebase's FastAPI version; see that class's
  docstring) (``rate_limit``), also registered in ``fragrance_rater.main``.

Identity for mutating fragrances/evaluations/reviewers routes is a separate
concern handled by ``fragrance_rater.core.auth`` (Authentik forward-auth).
"""

from __future__ import annotations

from fragrance_rater.middleware.auth import (
    API_KEY_HEADER,
    require_api_key,
)
from fragrance_rater.middleware.correlation import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    SPAN_ID_HEADER,
    TRACE_ID_HEADER,
    CorrelationMiddleware,
    correlation_context_processor,
    generate_correlation_id,
    get_correlation_id,
    get_request_id,
    get_span_id,
    get_trace_id,
    set_correlation_id,
)
from fragrance_rater.middleware.rate_limit import (
    DEFAULT_RATE_LIMIT,
    RATINGS_RATE_LIMIT,
    DefaultRateLimitMiddleware,
    limiter,
    rate_limit_exceeded_handler,
)
from fragrance_rater.middleware.security import (
    SecurityHeadersMiddleware,
    SSRFPreventionMiddleware,
    add_security_middleware,
)

__all__ = [
    "API_KEY_HEADER",
    "CORRELATION_ID_HEADER",
    "DEFAULT_RATE_LIMIT",
    "RATINGS_RATE_LIMIT",
    "REQUEST_ID_HEADER",
    "SPAN_ID_HEADER",
    "TRACE_ID_HEADER",
    "CorrelationMiddleware",
    "DefaultRateLimitMiddleware",
    "SSRFPreventionMiddleware",
    "SecurityHeadersMiddleware",
    "add_security_middleware",
    "correlation_context_processor",
    "generate_correlation_id",
    "get_correlation_id",
    "get_request_id",
    "get_span_id",
    "get_trace_id",
    "limiter",
    "rate_limit_exceeded_handler",
    "require_api_key",
    "set_correlation_id",
]
