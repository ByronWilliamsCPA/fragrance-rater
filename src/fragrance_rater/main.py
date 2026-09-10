"""FastAPI application entry point for Fragrance Rater.

This module creates and configures the FastAPI application with:
- CORS middleware for frontend communication
- Health check endpoints for Kubernetes probes
- API v1 routers
- Security middleware

Run locally with::

    uv run uvicorn fragrance_rater.main:app --reload

In CI the app is started with ``TEST_MODE=true`` so that the
LLM rating endpoint returns a deterministic fixture instead of
issuing a real OpenRouter call. See
``.github/workflows/postman-api-tests.yml``.

Auth and rate limiting: ``POST /ratings`` (the only mutating, LLM-backed
endpoint) requires a shared household ``X-API-Key`` header (see
``fragrance_rater.middleware.auth``) and is rate limited (see
``fragrance_rater.middleware.rate_limit``) to bound OpenRouter spend. Set
``FRAGRANCE_RATER_API_KEY`` before deploying outside a fully trusted,
single-household network.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from fragrance_rater.api import (
    catalog_stub_router,
    evaluations_router,
    fragrances_router,
    health_router,
    imports_router,
    ratings_router,
    recommendations_router,
    reviewers_router,
)
from fragrance_rater.core.config import settings
from fragrance_rater.middleware import (
    CorrelationMiddleware,
    DefaultRateLimitMiddleware,
    add_security_middleware,
    limiter,
    rate_limit_exceeded_handler,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for the application.

    Args:
        _app (FastAPI): The FastAPI application instance (unused but required
            by signature).

    Yields:
        None: Control to the application.
    """
    # Startup: nothing to initialise yet. The ORM models are already registered
    # on Base.metadata because the API routers imported above import them.
    yield
    # Shutdown: nothing to clean up yet (e.g., close connections)


app = FastAPI(
    title=settings.project_name,
    description=(
        "HTTP API for the Fragrance Rater service: a personal fragrance "
        "evaluation and recommendation system. Provides the fragrance "
        "catalog and an LLM-powered rating endpoint that scores a "
        "fragrance description and returns the model's reasoning. The "
        "rating endpoint calls OpenRouter (default model: "
        "`anthropic/claude-3.5-sonnet`); set `TEST_MODE=true` to use the "
        "bundled fixture response instead, which is what the Newman "
        "contract tests rely on. `POST /ratings` requires a shared "
        "household `X-API-Key` header and is rate limited; read-only "
        "endpoints do not require it."
    ),
    version=settings.version,
    contact={
        "name": "Byron Williams",
        "email": "byron@williamshome.family",
        "url": "https://github.com/ByronWilliamsCPA/fragrance-rater",
    },
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting (slowapi): in-memory, per-client-IP fixed window. See
# fragrance_rater.middleware.rate_limit for the rationale and the
# single-instance/single-worker assumption this relies on. Registered before
# the other middleware so DefaultRateLimitMiddleware sits innermost and its
# 429s still pass out through the correlation, security-header, and CORS
# layers below. This is the ONE rate-limiting mechanism for the whole API
# (the old OWASP RateLimitMiddleware duplicate has been removed); gated on
# settings.rate_limit_enabled so test suites and local dev can disable it the
# same way the removed layer used to be disabled.
#
# DefaultRateLimitMiddleware is a local stand-in for slowapi's own
# SlowAPIMiddleware; see its docstring in rate_limit.py for why the upstream
# middleware does not actually enforce default_limits on this codebase's
# FastAPI version.
#
# #CRITICAL: security: `limiter` is a process-wide singleton, and its own
# `.enabled` flag (checked by every `@limiter.limit(...)` route decorator,
# e.g. POST /ratings' RATINGS_RATE_LIMIT) defaults to True independently of
# whether DefaultRateLimitMiddleware/app.state.limiter get registered below.
# Without the explicit assignment, setting RATE_LIMIT_ENABLED=false only
# disabled the general DEFAULT_RATE_LIMIT middleware while POST /ratings
# kept enforcing RATINGS_RATE_LIMIT, silently defeating the "disable rate
# limiting entirely" toggle documented on settings.rate_limit_enabled.
# #VERIFY: empirically confirmed with a live TestClient burst against
# POST /ratings under RATE_LIMIT_ENABLED=false (see
# tests/unit/test_main.py::test_rate_limit_enabled_false_disables_decorator_too);
# re-run that test after any slowapi upgrade in case `Limiter.enabled`
# semantics change.
limiter.enabled = settings.rate_limit_enabled
if settings.rate_limit_enabled:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(DefaultRateLimitMiddleware)

# Add correlation ID middleware (should be added first)
app.add_middleware(CorrelationMiddleware)

# Add security middleware (CORS, security headers, SSRF prevention; rate
# limiting is handled separately above by the slowapi limiter).
#
# #CRITICAL: security: this must be the ONLY CORSMiddleware registration in
# the app. `add_security_middleware` registers its own CORSMiddleware
# internally (locked down to `allowed_origins or []` when not passed), and a
# second, independent `app.add_middleware(CORSMiddleware, ...)` call used to
# exist right after this one. Starlette treats the most-recently-added
# middleware as outermost, so that second call silently shadowed this one's
# (then-empty) allow-list for every request, defeating the intended
# lockdown. `settings.cors_allowed_origins` is now the single source of
# truth for the allow-list, passed straight into this one call.
# #VERIFY: `tests/unit/test_main.py` asserts exactly one CORSMiddleware is
# registered on `app` and that only origins in
# `settings.cors_allowed_origins` receive CORS headers; re-check that test
# before adding any other CORSMiddleware registration in this module.
add_security_middleware(app, allowed_origins=settings.cors_allowed_origins)

# Include routers
app.include_router(health_router)
app.include_router(ratings_router)
# Root-mounted sample catalog retained for the Postman contract suite; the
# database-backed catalog is the /api/v1/fragrances router below
app.include_router(catalog_stub_router)

# API v1 routers
app.include_router(fragrances_router, prefix=settings.api_v1_prefix)
app.include_router(reviewers_router, prefix=settings.api_v1_prefix)
app.include_router(evaluations_router, prefix=settings.api_v1_prefix)
app.include_router(recommendations_router, prefix=settings.api_v1_prefix)
app.include_router(imports_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint redirecting to API documentation.

    Returns:
        dict[str, str]: Welcome message with documentation links.
    """
    return {
        "message": f"Welcome to {settings.project_name}",
        "docs": "/docs",
        "health": "/health/live",
    }
