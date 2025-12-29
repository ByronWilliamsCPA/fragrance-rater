"""API package for Fragrance Rater.

This package contains FastAPI routers and API-related functionality.
"""

from __future__ import annotations

from fragrance_rater.api.health import router as health_router

__all__ = ["health_router"]
