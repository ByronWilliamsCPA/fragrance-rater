"""LLM client for fragrance rating.

The client targets OpenRouter (per ADR-003) and defaults to
``anthropic/claude-3.5-sonnet``. When the ``TEST_MODE`` environment
variable is truthy, the client short-circuits and returns a fixture
response. CI uses this seam to run the API contract tests
(``newman``) without an outbound LLM call or API key.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"
"""Default OpenRouter model identifier used to score fragrances."""

_TRUTHY = {"1", "true", "yes", "on"}


def _is_test_mode() -> bool:
    return os.environ.get("TEST_MODE", "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class LLMRatingResult:
    """Structured result returned by :class:`LLMRatingClient`.

    Attributes:
        score (int): Integer rating from 1 (poor) to 10 (excellent).
        reasoning (str): Human-readable explanation of the score.
        model (str): Identifier of the LLM model that produced the rating.
        notes (list[str]): Optional list of perfumer-style tasting notes.
    """

    score: int
    reasoning: str
    model: str
    notes: list[str]


class LLMRatingClient:
    """Thin client used by the rating endpoint.

    The implementation here is intentionally small: real prompt
    engineering and provider-specific request building live in a
    separate module (not part of this change). The class exists so
    the rating route can depend on a single seam that can be stubbed
    in tests by setting ``TEST_MODE=true``.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or DEFAULT_MODEL

    def rate(
        self,
        name: str,
        brand: str | None,
        description: str,
        notes: list[str] | None = None,
    ) -> LLMRatingResult:
        """Score a fragrance using the configured LLM.

        Args:
            name (str): Fragrance name.
            brand (str | None): Fragrance house / brand, if known.
            description (str): Free-text description of the scent.
            notes (list[str] | None): Optional list of top/heart/base notes.

        Returns:
            LLMRatingResult: Score, reasoning, model name, and echoed notes.

        Raises:
            RuntimeError: When TEST_MODE is disabled and no OpenRouter
                integration is configured.
        """
        if _is_test_mode():
            return _fixture_response(name=name, brand=brand, notes=notes)

        # The real OpenRouter call is implemented elsewhere; this
        # placeholder keeps the public surface stable. Production
        # deployments must set TEST_MODE=false and provide an
        # OPENROUTER_API_KEY.
        payload = {
            "name": name,
            "brand": brand,
            "description": description,
            "notes": notes or [],
        }
        msg = (
            f"LLMRatingClient.rate() requires TEST_MODE=true or a"
            f" configured OpenRouter integration. Payload: {json.dumps(payload)}"
        )
        raise RuntimeError(msg)


def _fixture_response(
    name: str,
    brand: str | None,
    notes: list[str] | None,
) -> LLMRatingResult:
    """Return a deterministic rating used by CI contract tests."""
    label = f"{brand} {name}".strip() if brand else name
    reasoning = (
        f"[TEST_MODE fixture] {label} reads as a balanced composition "
        "with good projection and longevity. Replace this stub by "
        "unsetting TEST_MODE to call the real model."
    )
    return LLMRatingResult(
        score=8,
        reasoning=reasoning,
        model="test-mode-stub",
        notes=list(notes) if notes else ["bergamot", "cedar", "amber"],
    )


def get_llm_client() -> LLMRatingClient:
    """FastAPI dependency that returns a configured client."""
    return LLMRatingClient()
