"""Fragrance Rater FastAPI application entry point.

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

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from fragrance_rater import __version__
from fragrance_rater.api import (
    fragrances_router,
    health_router,
    ratings_router,
)
from fragrance_rater.middleware import limiter, rate_limit_exceeded_handler

app = FastAPI(
    title="Fragrance Rater API",
    description=(
        "HTTP API for the Fragrance Rater service. Provides a "
        "small fragrance catalog and an LLM-powered rating "
        "endpoint that scores a fragrance description and returns "
        "the model's reasoning. The rating endpoint calls "
        "OpenRouter (default model: `anthropic/claude-3.5-sonnet`); "
        "set `TEST_MODE=true` to use the bundled fixture response "
        "instead, which is what the Newman contract tests rely on. "
        "`POST /ratings` requires a shared household `X-API-Key` header "
        "and is rate limited; read-only endpoints do not require it."
    ),
    version=__version__,
    contact={
        "name": "Byron Williams",
        "email": "byron@williamshome.family",
        "url": "https://github.com/ByronWilliamsCPA/fragrance-rater",
    },
    license_info={"name": "MIT"},
)

# Rate limiting (slowapi): in-memory, per-client-IP fixed window. See
# fragrance_rater.middleware.rate_limit for the rationale and the
# single-instance/single-worker assumption this relies on.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(health_router)
app.include_router(ratings_router)
app.include_router(fragrances_router)
