"""Middleware for API applications.

This package exposes the request-correlation middleware. The OWASP-aligned
`SecurityHeadersMiddleware`, `RateLimitMiddleware`, `SSRFPreventionMiddleware`,
and the `add_security_middleware` helper were removed during the scaffold-
cleanup sweep; reintroduce them when an API layer actually needs them.
"""

from __future__ import annotations

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

__all__ = [
    "CORRELATION_ID_HEADER",
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
    "set_correlation_id",
]
