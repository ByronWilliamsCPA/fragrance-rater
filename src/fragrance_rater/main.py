"""Fragrance Rater FastAPI application entry point.

Run locally with::

    uv run uvicorn fragrance_rater.main:app --reload

In CI the app is started with ``TEST_MODE=true`` so that the
LLM rating endpoint returns a deterministic fixture instead of
issuing a real OpenRouter call. See
``.github/workflows/postman-api-tests.yml``.
"""

from __future__ import annotations

from fastapi import FastAPI

from fragrance_rater import __version__
from fragrance_rater.api import (
    fragrances_router,
    health_router,
    ratings_router,
)

app = FastAPI(
    title="Fragrance Rater API",
    description=(
        "HTTP API for the Fragrance Rater service. Provides a "
        "small fragrance catalog and an LLM-powered rating "
        "endpoint that scores a fragrance description and returns "
        "the model's reasoning. The rating endpoint calls "
        "OpenRouter (default model: `anthropic/claude-3.5-sonnet`); "
        "set `TEST_MODE=true` to use the bundled fixture response "
        "instead, which is what the Newman contract tests rely on."
    ),
    version=__version__,
    contact={
        "name": "Byron Williams",
        "email": "byron@williamshome.family",
        "url": "https://github.com/ByronWilliamsCPA/fragrance-rater",
    },
    license_info={"name": "MIT"},
)

app.include_router(health_router)
app.include_router(ratings_router)
app.include_router(fragrances_router)
