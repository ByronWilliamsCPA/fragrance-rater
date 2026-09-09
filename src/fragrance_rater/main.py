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
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from fragrance_rater.middleware import CorrelationMiddleware, add_security_middleware

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
        "contract tests rely on."
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

# Add correlation ID middleware (should be added first)
app.add_middleware(CorrelationMiddleware)

# Add security middleware (rate limiting is configurable so that test suites
# sharing one app instance can disable the per-client counter)
add_security_middleware(
    app,
    enable_rate_limiting=settings.rate_limit_enabled,
    rate_limit_rpm=settings.rate_limit_rpm,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
