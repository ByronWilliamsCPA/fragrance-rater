"""Rate limiting for the Fragrance Rater API.

Uses ``slowapi`` (backed by the ``limits`` package) with its default
in-memory storage backend. An in-memory fixed-window limiter is proportionate
for a single-instance, single-household deployment (see
``project-vision.md``), but the counters are process-local: they are not
shared across replicas.

The limiter keys on client IP by default (``get_remote_address``), which is
adequate behind a home router / reverse proxy where all household callers
share a small, stable set of source addresses.

#CRITICAL: resource-consumption: docker-compose.prod.yml's ``app`` service
defaults ``deploy.replicas`` to 1 specifically because of this. Each replica
keeps its own independent counter, so running N replicas silently multiplies
the effective rate limit on the billed, LLM-backed ``POST /ratings`` endpoint
by N, defeating the abuse/cost protection ``RATINGS_RATE_LIMIT`` exists for.
#VERIFY: before setting ``REPLICAS`` above 1 (or running more than one
uvicorn worker), switch ``Limiter`` to a shared backend (e.g.
``storage_uri="redis://..."``); do not rely on process count staying at 1
without also enforcing it in deployment config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

_PROBLEM_TYPE = "https://api.fragrance-rater.internal/errors/rate-limit-exceeded"
"""Problem type URI for 429 responses, matching the auth.py RFC 7807 shape."""

# #CRITICAL: resource-consumption: POST /ratings calls a billed OpenRouter
# model per request (ADR-003). Without a limit, a single caller could drive
# unbounded upstream spend.
# #VERIFY: RATINGS_RATE_LIMIT below stays tighter than the household's
# realistic usage pattern; raise DEFAULT_RATE_LIMIT only for endpoints that
# do not call a billed upstream.
DEFAULT_RATE_LIMIT = "60/minute"
"""Fallback limit applied to any route that does not set its own."""

RATINGS_RATE_LIMIT = "10/minute"
"""Tighter limit for the LLM-backed rating endpoint (cost/abuse vector)."""

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE_LIMIT])
"""Shared ``slowapi`` limiter instance, registered on the app in ``main.py``."""


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """Adapt slowapi's typed handler to Starlette's generic exception-handler shape.

    ``app.add_exception_handler`` expects a callable typed as
    ``(Request, Exception) -> Response``, but slowapi's own
    ``_rate_limit_exceeded_handler`` is narrowly typed to
    ``RateLimitExceeded``. Starlette only ever invokes this wrapper for the
    ``RateLimitExceeded`` exception class it is registered against, so the
    ``isinstance`` check below is a real runtime guarantee, not just a type
    checker workaround.

    slowapi's own handler returns a plain ``{"error": ...}`` body as
    ``application/json``, not the RFC 7807 problem-details shape the rest of
    this API's error responses use (see
    ``fragrance_rater.middleware.auth._problem_detail``). This wrapper
    delegates to slowapi for the response (so its rate-limit headers, such as
    ``Retry-After``, are still computed correctly) and then re-shapes the
    body and content type to match.

    Args:
        request (Request): The request that triggered the rate limit.
        exc (Exception): The raised exception; always a ``RateLimitExceeded``
            in practice since that's the only type this handler is
            registered for.

    Returns:
        Response: An RFC 7807 problem-details 429 response
            (``application/problem+json``).

    Raises:
        TypeError: If invoked for an exception type other than
            ``RateLimitExceeded`` (should never happen given the
            registration in ``main.py``).
    """
    if not isinstance(exc, RateLimitExceeded):
        msg = f"rate_limit_exceeded_handler received unexpected exception type: {type(exc)!r}"
        raise TypeError(msg)

    slowapi_response = _rate_limit_exceeded_handler(request, exc)
    # Carry over slowapi's rate-limit headers (Retry-After, X-RateLimit-*),
    # but drop content-length/content-type so Response recomputes them for
    # the new problem-details body instead of keeping slowapi's stale values.
    headers = dict(slowapi_response.headers)
    headers.pop("content-length", None)
    headers.pop("content-type", None)

    return JSONResponse(
        {
            "type": _PROBLEM_TYPE,
            "title": "Rate Limit Exceeded",
            "status": status.HTTP_429_TOO_MANY_REQUESTS,
            "detail": f"Rate limit exceeded: {exc.detail}",
        },
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers=headers,
        media_type="application/problem+json",
    )


__all__ = [
    "DEFAULT_RATE_LIMIT",
    "RATINGS_RATE_LIMIT",
    "limiter",
    "rate_limit_exceeded_handler",
]
