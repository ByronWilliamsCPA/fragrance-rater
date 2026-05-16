"""API package for Fragrance Rater.

This package contains FastAPI routers and API-related functionality.
"""

from __future__ import annotations

from fragrance_rater.api.fragrances import router as fragrances_router
from fragrance_rater.api.health import router as health_router
from fragrance_rater.api.ratings import router as ratings_router

__all__ = ["fragrances_router", "health_router", "ratings_router"]
