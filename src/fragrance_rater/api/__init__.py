"""API package for Fragrance Rater.

Exports the FastAPI routers mounted by ``fragrance_rater.main``.
"""

from __future__ import annotations

from fragrance_rater.api.catalog_stub import router as catalog_stub_router
from fragrance_rater.api.evaluations import router as evaluations_router
from fragrance_rater.api.fragrances import router as fragrances_router
from fragrance_rater.api.health import router as health_router
from fragrance_rater.api.imports import router as imports_router
from fragrance_rater.api.ratings import router as ratings_router
from fragrance_rater.api.recommendations import router as recommendations_router
from fragrance_rater.api.reviewers import router as reviewers_router

__all__ = [
    "catalog_stub_router",
    "evaluations_router",
    "fragrances_router",
    "health_router",
    "imports_router",
    "ratings_router",
    "recommendations_router",
    "reviewers_router",
]
