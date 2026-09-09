"""Middleware for API applications.

This package exposes the request-correlation middleware, the shared
household API key auth dependency (``auth.require_api_key``), and the
``slowapi``-backed rate limiter (``rate_limit.limiter``). The OWASP-aligned
`SecurityHeadersMiddleware` and `SSRFPreventionMiddleware` helpers were
removed during the scaffold-cleanup sweep; reintroduce them when an API
layer actually needs them (this API layer now has explicit auth and rate
limiting again as of the API compliance remediation pass).
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
    limiter,
    rate_limit_exceeded_handler,
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
