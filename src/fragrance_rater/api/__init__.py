"""API package for Fragrance Rater.

This package contains FastAPI routers and API-related functionality.
"""

from __future__ import annotations

from fragrance_rater.api.fragrances import router as fragrances_router
from fragrance_rater.api.health import router as health_router
from fragrance_rater.api.imports import router as imports_router
from fragrance_rater.api.reviewers import router as reviewers_router

__all__ = [
    "fragrances_router",
    "health_router",
    "imports_router",
    "reviewers_router",
]
