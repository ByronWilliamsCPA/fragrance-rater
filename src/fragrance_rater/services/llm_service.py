"""LLM service for generating recommendation explanations via OpenRouter.

This module implements ADR-003 LLM integration:
- OpenRouter as the LLM gateway
- Prompt templates for recommendations and profile summaries
- Graceful degradation when LLM is unavailable
- In-memory caching for generated explanations
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

import httpx

from fragrance_rater.core.config import settings

if TYPE_CHECKING:
    from fragrance_rater.services.recommendation_service import (
        Recommendation,
        UserProfile,
    )


# Prompt templates per ADR-003
RECOMMENDATION_PROMPT = """You are a fragrance expert. Explain why this fragrance might appeal to the user.

User's preference profile:
- Likes: {liked_notes}
- Dislikes: {disliked_notes}
- Preferred families: {preferred_families}

Fragrance: {fragrance_name} by {fragrance_brand}
- Match Score: {match_percent}%
- Family: {family}
- Top notes: {top_notes}
- Heart notes: {heart_notes}
- Base notes: {base_notes}
- Accords: {accords}

Write 2-3 sentences explaining the match. Highlight specific notes they'll enjoy.
If there are notes they typically dislike, acknowledge this as a potential concern.
Keep the response concise and helpful."""

PROFILE_SUMMARY_PROMPT = """You are a fragrance expert. Summarize this user's fragrance preferences.

User: {reviewer_name}
Number of fragrances rated: {evaluation_count}

Top liked notes: {liked_notes}
Top disliked notes: {disliked_notes}
Preferred accords: {preferred_accords}
Preferred fragrance families: {preferred_families}

Write a 2-3 sentence natural language summary of their preferences.
Be specific about what scent profiles they gravitate towards and what they avoid.
Keep the tone friendly and informative."""

VETOED_RECOMMENDATION_PROMPT = """You are a fragrance expert. Explain why this fragrance might NOT be ideal for the user.

User's preference profile:
- Likes: {liked_notes}
- Dislikes: {disliked_notes}

Fragrance: {fragrance_name} by {fragrance_brand}
- Contains: {veto_note} (which they dislike)
- Top notes: {top_notes}
- Heart notes: {heart_notes}
- Base notes: {base_notes}

Write 1-2 sentences explaining why this might not be their best choice,
but acknowledge any positive aspects if relevant."""


@dataclass
class LLMResponse:
    """Response from LLM service."""

    text: str
    model: str
    cached: bool = False
    error: str | None = None


@dataclass
class FragranceDetails:
    """Details about a fragrance for LLM prompts."""

    name: str
    brand: str
    family: str
    subfamily: str
    top_notes: list[str] = field(default_factory=list)
    heart_notes: list[str] = field(default_factory=list)
    base_notes: list[str] = field(default_factory=list)
    accords: list[str] = field(default_factory=list)


class LLMServiceError(Exception):
    """Raised when LLM service encounters an error."""


class LLMService:
    """Service for generating LLM-powered explanations via OpenRouter.

    Implements ADR-003 with:
    - OpenRouter API integration
    - Prompt templates for recommendations and profiles
    - In-memory caching for repeated requests
    - Graceful degradation when API is unavailable
    """

    def __init__(self) -> None:
        """Initialize the LLM service."""
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url
        self.model = settings.openrouter_model
        self.enabled = settings.llm_enabled and bool(self.api_key)
        self._cache: dict[str, str] = {}

    def is_available(self) -> bool:
        """Check if LLM service is available.

        Returns:
            True if LLM is enabled and configured.
        """
        return self.enabled

    async def generate_recommendation_explanation(
        self,
        recommendation: Recommendation,
        profile: UserProfile,
        fragrance_details: FragranceDetails,
    ) -> LLMResponse:
        """Generate an explanation for why a fragrance matches a user's preferences.

        Args:
            recommendation: The recommendation with match score.
            profile: User's preference profile.
            fragrance_details: Details about the fragrance.

        Returns:
            LLMResponse with the generated explanation.
        """
        if not self.enabled:
            return self._fallback_recommendation_explanation(
                recommendation, profile, fragrance_details
            )

        # Check cache
        cache_key = self._cache_key(
            "rec", recommendation.fragrance_id, profile.reviewer_id
        )
        if cache_key in self._cache:
            return LLMResponse(
                text=self._cache[cache_key], model=self.model, cached=True
            )

        # Build prompt
        if recommendation.vetoed:
            prompt = VETOED_RECOMMENDATION_PROMPT.format(
                liked_notes=", ".join(n for n, _ in profile.top_liked_notes) or "None",
                disliked_notes=", ".join(n for n, _ in profile.top_disliked_notes)
                or "None",
                fragrance_name=fragrance_details.name,
                fragrance_brand=fragrance_details.brand,
                veto_note=recommendation.veto_reason or "a disliked note",
                top_notes=", ".join(fragrance_details.top_notes) or "Unknown",
                heart_notes=", ".join(fragrance_details.heart_notes) or "Unknown",
                base_notes=", ".join(fragrance_details.base_notes) or "Unknown",
            )
        else:
            prompt = RECOMMENDATION_PROMPT.format(
                liked_notes=", ".join(n for n, _ in profile.top_liked_notes) or "None",
                disliked_notes=", ".join(n for n, _ in profile.top_disliked_notes)
                or "None",
                preferred_families=", ".join(
                    f for f, _ in sorted(
                        profile.family_affinities.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:3]
                )
                or "Various",
                fragrance_name=fragrance_details.name,
                fragrance_brand=fragrance_details.brand,
                match_percent=recommendation.match_percent,
                family=fragrance_details.family,
                top_notes=", ".join(fragrance_details.top_notes) or "Unknown",
                heart_notes=", ".join(fragrance_details.heart_notes) or "Unknown",
                base_notes=", ".join(fragrance_details.base_notes) or "Unknown",
                accords=", ".join(fragrance_details.accords) or "Unknown",
            )

        try:
            response = await self._call_openrouter(prompt)
            self._cache[cache_key] = response
            return LLMResponse(text=response, model=self.model, cached=False)
        except LLMServiceError as e:
            # Fallback on error
            fallback = self._fallback_recommendation_explanation(
                recommendation, profile, fragrance_details
            )
            fallback.error = str(e)
            return fallback

    async def generate_profile_summary(
        self,
        profile: UserProfile,
        reviewer_name: str,
    ) -> LLMResponse:
        """Generate a natural language summary of a user's preferences.

        Args:
            profile: User's preference profile.
            reviewer_name: Name of the reviewer.

        Returns:
            LLMResponse with the generated summary.
        """
        if not self.enabled:
            return self._fallback_profile_summary(profile, reviewer_name)

        # Check cache
        cache_key = self._cache_key("profile", profile.reviewer_id)
        if cache_key in self._cache:
            return LLMResponse(
                text=self._cache[cache_key], model=self.model, cached=True
            )

        # Build prompt
        prompt = PROFILE_SUMMARY_PROMPT.format(
            reviewer_name=reviewer_name,
            evaluation_count=profile.evaluation_count,
            liked_notes=", ".join(n for n, _ in profile.top_liked_notes) or "None yet",
            disliked_notes=", ".join(n for n, _ in profile.top_disliked_notes)
            or "None yet",
            preferred_accords=", ".join(
                a
                for a, _ in sorted(
                    profile.accord_affinities.items(), key=lambda x: x[1], reverse=True
                )[:5]
            )
            or "Various",
            preferred_families=", ".join(
                f
                for f, _ in sorted(
                    profile.family_affinities.items(), key=lambda x: x[1], reverse=True
                )[:5]
            )
            or "Various",
        )

        try:
            response = await self._call_openrouter(prompt)
            self._cache[cache_key] = response
            return LLMResponse(text=response, model=self.model, cached=False)
        except LLMServiceError as e:
            fallback = self._fallback_profile_summary(profile, reviewer_name)
            fallback.error = str(e)
            return fallback

    async def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API with the given prompt.

        Args:
            prompt: The prompt to send.

        Returns:
            Generated text response.

        Raises:
            LLMServiceError: If API call fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ByronWilliamsCPA/fragrance-rater",
            "X-Title": "Fragrance Rater",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            msg = f"OpenRouter API error: {e.response.status_code}"
            raise LLMServiceError(msg) from e
        except httpx.RequestError as e:
            msg = f"OpenRouter request failed: {e}"
            raise LLMServiceError(msg) from e
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            msg = f"Invalid OpenRouter response: {e}"
            raise LLMServiceError(msg) from e

    def _cache_key(self, prefix: str, *args: str) -> str:
        """Generate a cache key from arguments.

        Args:
            prefix: Cache key prefix.
            *args: Values to include in key.

        Returns:
            Hashed cache key.
        """
        key_str = f"{prefix}:{':'.join(args)}"
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def _fallback_recommendation_explanation(
        self,
        recommendation: Recommendation,
        profile: UserProfile,
        fragrance_details: FragranceDetails,
    ) -> LLMResponse:
        """Generate a simple fallback explanation without LLM.

        Args:
            recommendation: The recommendation.
            profile: User's preference profile.
            fragrance_details: Details about the fragrance.

        Returns:
            LLMResponse with rule-based explanation.
        """
        if recommendation.vetoed:
            text = (
                "This fragrance contains notes you typically dislike. "
                "You might want to explore other options first."
            )
        else:
            liked = [n for n, _ in profile.top_liked_notes[:3]]
            matching = [
                n
                for n in liked
                if n.lower()
                in [
                    note.lower()
                    for note in fragrance_details.top_notes
                    + fragrance_details.heart_notes
                    + fragrance_details.base_notes
                ]
            ]
            if matching:
                text = (
                    f"This {recommendation.match_percent}% match contains {', '.join(matching)} "
                    f"which you've enjoyed in other fragrances."
                )
            else:
                text = (
                    f"With a {recommendation.match_percent}% match score, "
                    f"this fragrance aligns well with your general preferences "
                    f"for {fragrance_details.family} scents."
                )

        return LLMResponse(text=text, model="fallback", cached=False)

    def _fallback_profile_summary(
        self,
        profile: UserProfile,
        reviewer_name: str,
    ) -> LLMResponse:
        """Generate a simple fallback profile summary without LLM.

        Args:
            profile: User's preference profile.
            reviewer_name: Name of the reviewer.

        Returns:
            LLMResponse with rule-based summary.
        """
        liked = [n for n, _ in profile.top_liked_notes[:3]]
        disliked = [n for n, _ in profile.top_disliked_notes[:3]]

        parts = [f"{reviewer_name} has rated {profile.evaluation_count} fragrances."]

        if liked:
            parts.append(f"They tend to enjoy notes like {', '.join(liked)}.")
        if disliked:
            parts.append(f"They generally avoid {', '.join(disliked)}.")

        if not liked and not disliked:
            parts.append("More evaluations needed to identify clear preferences.")

        return LLMResponse(text=" ".join(parts), model="fallback", cached=False)

    def clear_cache(self) -> None:
        """Clear the explanation cache."""
        self._cache.clear()

    def invalidate_reviewer_cache(self, reviewer_id: str) -> None:
        """Invalidate cache entries for a specific reviewer.

        Args:
            reviewer_id: UUID of the reviewer.
        """
        keys_to_remove = [k for k in self._cache if reviewer_id in k]
        for key in keys_to_remove:
            del self._cache[key]


# Global LLM service instance
@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """Get the global LLM service instance.

    Returns:
        Singleton LLMService instance.
    """
    return LLMService()
