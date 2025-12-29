"""FastAPI application entry point for Fragrance Rater.

This module creates and configures the FastAPI application with:
- CORS middleware for frontend communication
- Health check endpoints for Kubernetes probes
- API v1 routers
- Security middleware
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fragrance_rater.api import (
    evaluations_router,
    fragrances_router,
    health_router,
    imports_router,
    recommendations_router,
    reviewers_router,
)
from fragrance_rater.core.config import settings
from fragrance_rater.middleware import CorrelationMiddleware, add_security_middleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for the application.

    Args:
        _app: The FastAPI application instance (unused but required by signature).

    Yields:
        None: Control to the application.
    """
    # Startup
    # Import models to ensure they're registered with SQLAlchemy
    from fragrance_rater import models as _models  # noqa: PLC0415

    del _models  # Silence pyright unused import warning

    yield
    # Shutdown
    # Add any cleanup code here (e.g., close connections)


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description="Personal fragrance evaluation and recommendation system",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add correlation ID middleware (should be added first)
app.add_middleware(CorrelationMiddleware)

# Add security middleware
add_security_middleware(app)

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
        dict: Welcome message with documentation links.
    """
    return {
        "message": f"Welcome to {settings.project_name}",
        "docs": "/docs",
        "health": "/health/live",
    }
