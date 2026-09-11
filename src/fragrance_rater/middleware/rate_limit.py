"""Rate limiting for the Fragrance Rater API.

Uses ``slowapi`` (backed by the ``limits`` package) with its default
in-memory storage backend. An in-memory fixed-window limiter is proportionate
for a single-instance, single-household deployment (see
``project-vision.md``), but the counters are process-local: they are not
shared across replicas.

The limiter keys on client IP by default (``get_remote_address``), which is
adequate behind a home router / reverse proxy where all household callers
share a small, stable set of source addresses.

This is now the SOLE rate limiter for the entire API: the OWASP-aligned
in-memory ``RateLimitMiddleware`` that used to run alongside it (in
``fragrance_rater.middleware.security``) has been removed, so there is no
other layer left to catch abusive traffic if this one is disabled or
misconfigured.

``POST /ratings`` is protected by its own ``@limiter.limit(RATINGS_RATE_LIMIT)``
route decorator. Every other route relies on ``DEFAULT_RATE_LIMIT`` being
applied by ``DefaultRateLimitMiddleware`` below, a local replacement for
``slowapi.middleware.SlowAPIMiddleware``; see that class's docstring for why
the upstream middleware does not work on this codebase's dependency
versions.

#CRITICAL: resource-consumption: docker-compose.prod.yml's ``app`` service
defaults ``deploy.replicas`` to 1 specifically because of this. Each replica
keeps its own independent counter, so running N replicas silently multiplies
the effective rate limit by N for every route in the API, not just the
billed, LLM-backed ``POST /ratings`` endpoint, defeating the abuse/cost
protection ``RATINGS_RATE_LIMIT`` and the general ``DEFAULT_RATE_LIMIT``
exist for. With no second limiter layer left as a backstop, this is now the
only thing standing between N replicas and unbounded request volume on every
endpoint.
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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from fragrance_rater.core.config import settings

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
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
DEFAULT_RATE_LIMIT = f"{settings.rate_limit_rpm}/minute"
"""Fallback limit applied to any route that does not set its own.

Driven by ``settings.rate_limit_rpm`` (``RATE_LIMIT_RPM``) so operators can
tune the general-purpose limit without a code change. Unlike
``RATINGS_RATE_LIMIT`` below, this is meant to scale with that setting.
"""

RATINGS_RATE_LIMIT = "10/minute"
"""Tighter limit for the LLM-backed rating endpoint (cost/abuse vector)."""

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE_LIMIT])
"""Shared ``slowapi`` limiter instance, registered on the app in ``main.py``."""

_RATINGS_PATH_PREFIX = "/ratings"
"""Mirrors ``ratings_router = APIRouter(prefix="/ratings", ...)`` in
``fragrance_rater.api.ratings``. Kept as a literal (not an import) to avoid a
circular import: that module imports ``limiter`` from this package's
``__init__``, so this module cannot import back from it.

#ASSUME: data-integrity: if the ratings router's prefix ever changes, this
constant must be updated to match, or POST /ratings would silently start
double-counting against both DEFAULT_RATE_LIMIT and RATINGS_RATE_LIMIT.
#VERIFY: grep for ``prefix="/ratings"`` in fragrance_rater/api/ratings.py
whenever this constant is touched.
"""


class DefaultRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce ``DEFAULT_RATE_LIMIT`` on every route without its own decorator.

    #CRITICAL: external-resources: ``slowapi``'s own ``SlowAPIMiddleware``
    (the library's documented way to apply ``default_limits`` to undecorated
    routes) silently does nothing on this codebase's installed
    dependencies: FastAPI >=0.141 wraps every route registered via
    ``app.include_router()`` in an internal ``_IncludedRouter`` lazy-candidate
    object instead of flattening it into ``app.routes`` as a plain
    ``APIRoute``. slowapi 0.1.10's ``_find_route_handler`` (used by
    ``SlowAPIMiddleware.dispatch``) walks ``app.routes`` expecting the old
    flattened shape and checks ``hasattr(route, "endpoint")``, which
    ``_IncludedRouter`` does not satisfy; the handler resolves to ``None``,
    ``_should_exempt`` then treats "no handler found" as "exempt", and
    ``default_limits`` are never evaluated. In this API, every route except
    the bare ``/`` root and FastAPI's own ``/docs``/``/openapi.json`` is
    registered via ``include_router()``, so ``SlowAPIMiddleware`` was
    silently a no-op for the general limit on essentially the whole surface
    (confirmed live: 10 sequential ``GET /health/live`` requests with
    ``RATE_LIMIT_RPM=5`` all returned 200, with no 429).
    #VERIFY: this was verified against slowapi 0.1.10 (the latest release on
    PyPI at the time of writing) and FastAPI 0.141.1. Re-run the live burst
    test in this module's test suite against ``/health/live`` after any
    slowapi or FastAPI upgrade; if it now enforces correctly on its own,
    this middleware can likely be deleted in favor of the upstream
    ``SlowAPIMiddleware`` again. Track upstream: no known slowapi issue
    exists yet for FastAPI's ``_IncludedRouter`` shape as of this writing;
    file one against https://github.com/laurentS/slowapi before removing
    this workaround so future upgraders know why it existed.

    This middleware sidesteps the broken route-resolution entirely: instead
    of trying to match the request against a FastAPI route object, it calls
    the same private, ``in_middleware=True`` check ``SlowAPIMiddleware``
    would have called (``Limiter._check_request_limit``), which keys the
    limit on the raw request path (``request["path"]``, since ``limiter``
    uses the default ``key_style="url"``) rather than a resolved handler.
    That keeps ``slowapi``'s ``Limiter`` (same storage, same counters) as
    the sole rate-limiting engine; only the auto-discovery wrapper is
    replaced.

    ``POST /ratings`` is exempted by path prefix: it already has its own
    ``@limiter.limit(RATINGS_RATE_LIMIT)`` decorator (a separate, unaffected
    code path that does not depend on route-object resolution at all), and
    RATINGS_RATE_LIMIT is deliberately meant to stay independent of
    DEFAULT_RATE_LIMIT (see the module docstring).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Apply the general default limit, then delegate to the route.

        Args:
            request (Request): The incoming request.
            call_next (RequestResponseEndpoint): Starlette's callable that
                invokes the rest of the middleware stack and the route.

        Returns:
            Response: Either a 429 problem-details response (limit
                exceeded) or the downstream response.
        """
        if not limiter.enabled or request.url.path.startswith(_RATINGS_PATH_PREFIX):
            return await call_next(request)

        try:
            # #VERIFY: private API (see class docstring for why); keep this
            # call in sync with how slowapi.middleware.SlowAPIMiddleware
            # invokes the same method if slowapi's signature ever changes.
            limiter._check_request_limit(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
                request, None, in_middleware=True
            )
        except RateLimitExceeded as exc:
            return rate_limit_exceeded_handler(request, exc)

        return await call_next(request)


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
    "DefaultRateLimitMiddleware",
    "limiter",
    "rate_limit_exceeded_handler",
]
