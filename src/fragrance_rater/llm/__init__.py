"""LLM client package for Fragrance Rater.

Provides a thin client wrapper used by API routes to request
LLM-powered fragrance ratings. When ``TEST_MODE=true`` is set in
the environment, the client returns a deterministic fixture
response instead of issuing a network call. This is the seam that
``newman``-based contract tests in CI use to keep responses stable.
"""

from __future__ import annotations

from fragrance_rater.llm.client import (
    LLMRatingClient,
    LLMRatingResult,
    get_llm_client,
)

__all__ = ["LLMRatingClient", "LLMRatingResult", "get_llm_client"]
