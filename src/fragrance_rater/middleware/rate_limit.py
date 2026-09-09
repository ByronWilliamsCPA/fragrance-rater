"""Rate limiting for the Fragrance Rater API.

Uses ``slowapi`` (backed by the ``limits`` package) with its default
in-memory storage backend. This is a single-instance, single-household
deployment (see ``project-vision.md``); an in-memory fixed-window limiter is
proportionate here. Do not swap in a Redis-backed or distributed limiter
without a real multi-instance deployment need.

The limiter keys on client IP by default (``get_remote_address``), which is
adequate behind a home router / reverse proxy where all household callers
share a small, stable set of source addresses.

#EDGE: concurrency: the in-memory limiter resets on process restart and does
not share state across multiple uvicorn workers. #VERIFY: if this service is
ever run with more than one worker process, switch ``Limiter`` to a shared
backend (e.g. ``storage_uri="redis://..."``) or pin ``--workers 1``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

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

    Args:
        request (Request): The request that triggered the rate limit.
        exc (Exception): The raised exception; always a ``RateLimitExceeded``
            in practice since that's the only type this handler is
            registered for.

    Returns:
        Response: The RFC 7807-shaped 429 response built by slowapi.

    Raises:
        TypeError: If invoked for an exception type other than
            ``RateLimitExceeded`` (should never happen given the
            registration in ``main.py``).
    """
    if not isinstance(exc, RateLimitExceeded):
        msg = f"rate_limit_exceeded_handler received unexpected exception type: {type(exc)!r}"
        raise TypeError(msg)
    return _rate_limit_exceeded_handler(request, exc)


__all__ = [
    "DEFAULT_RATE_LIMIT",
    "RATINGS_RATE_LIMIT",
    "limiter",
    "rate_limit_exceeded_handler",
]
