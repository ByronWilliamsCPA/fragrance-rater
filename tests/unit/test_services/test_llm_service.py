"""Unit tests for LLMService.

Tests the OpenRouter LLM integration for recommendation explanations.
"""

from unittest.mock import patch

import pytest

from fragrance_rater.services.llm_service import (
    FragranceDetails,
    LLMResponse,
    LLMService,
    get_llm_service,
)
from fragrance_rater.services.recommendation_service import (
    Recommendation,
    UserProfile,
)


class TestFragranceDetails:
    """Tests for FragranceDetails dataclass."""

    def test_creation(self):
        """Test FragranceDetails creation."""
        details = FragranceDetails(
            name="Test Fragrance",
            brand="Test Brand",
            family="woody",
            subfamily="aromatic",
            top_notes=["bergamot", "lemon"],
            heart_notes=["lavender"],
            base_notes=["cedar", "musk"],
            accords=["fresh", "woody"],
        )
        assert details.name == "Test Fragrance"
        assert len(details.top_notes) == 2
        assert "cedar" in details.base_notes

    def test_default_empty_lists(self):
        """Test default empty lists."""
        details = FragranceDetails(
            name="Minimal",
            brand="Brand",
            family="fresh",
            subfamily="citrus",
        )
        assert details.top_notes == []
        assert details.heart_notes == []
        assert details.base_notes == []
        assert details.accords == []


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_creation(self):
        """Test LLMResponse creation."""
        response = LLMResponse(
            text="This is an explanation",
            model="anthropic/claude-3-haiku",
            cached=False,
        )
        assert response.text == "This is an explanation"
        assert response.model == "anthropic/claude-3-haiku"
        assert response.cached is False

    def test_cached_response(self):
        """Test cached response flag."""
        response = LLMResponse(
            text="Cached explanation",
            model="anthropic/claude-3-haiku",
            cached=True,
        )
        assert response.cached is True

    def test_with_error(self):
        """Test response with error."""
        response = LLMResponse(
            text="Fallback text",
            model="fallback",
            cached=False,
            error="API unavailable",
        )
        assert response.error == "API unavailable"


class TestLLMService:
    """Tests for LLMService."""

    def test_is_available_without_api_key(self):
        """Test service unavailable without API key."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_enabled = True
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"
            service = LLMService()
            assert service.is_available() is False

    def test_is_available_when_disabled(self):
        """Test service unavailable when disabled."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.llm_enabled = False
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"
            service = LLMService()
            assert service.is_available() is False

    def test_is_available_with_key_and_enabled(self):
        """Test service available with key and enabled."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.llm_enabled = True
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"
            service = LLMService()
            assert service.is_available() is True

    def test_cache_key_generation(self):
        """Test cache key generation."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.llm_enabled = True
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"
            service = LLMService()

            key1 = service._cache_key("rec", "frag1", "user1")
            key2 = service._cache_key("rec", "frag1", "user1")
            key3 = service._cache_key("rec", "frag2", "user1")

            # Same inputs should produce same key
            assert key1 == key2
            # Different inputs should produce different key
            assert key1 != key3

    def test_clear_cache(self):
        """Test clearing the entire cache."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.llm_enabled = True
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"
            service = LLMService()

            service._cache["key1"] = "value1"
            service._cache["key2"] = "value2"
            assert len(service._cache) == 2

            service.clear_cache()
            assert len(service._cache) == 0

    def test_invalidate_reviewer_cache(self):
        """Test invalidating cache for a specific reviewer."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.llm_enabled = True
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"
            service = LLMService()

            # Add cached items with reviewer IDs in keys
            service._cache["user1_frag1"] = "value1"
            service._cache["user1_frag2"] = "value2"
            service._cache["user2_frag1"] = "value3"

            service.invalidate_reviewer_cache("user1")

            assert "user1_frag1" not in service._cache
            assert "user1_frag2" not in service._cache
            assert "user2_frag1" in service._cache


@pytest.mark.asyncio
class TestLLMServiceFallback:
    """Tests for LLMService fallback explanations."""

    async def test_fallback_explanation_vetoed(self):
        """Test fallback explanation for vetoed fragrance."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""  # Disabled
            mock_settings.llm_enabled = False
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"

            service = LLMService()

            recommendation = Recommendation(
                fragrance_id="frag-001",
                fragrance_name="Bad Scent",
                fragrance_brand="Brand",
                match_score=0.1,
                match_percent=10,
                vetoed=True,
                veto_reason="Contains patchouli",
            )

            profile = UserProfile(reviewer_id="user-001")

            details = FragranceDetails(
                name="Bad Scent",
                brand="Brand",
                family="woody",
                subfamily="earthy",
            )

            response = await service.generate_recommendation_explanation(
                recommendation, profile, details
            )

            assert "dislike" in response.text.lower()
            assert response.model == "fallback"

    async def test_fallback_explanation_good_match_with_matching_notes(self):
        """Test fallback explanation for good match with matching notes."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_enabled = False
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"

            service = LLMService()

            recommendation = Recommendation(
                fragrance_id="frag-002",
                fragrance_name="Good Scent",
                fragrance_brand="Brand",
                match_score=0.85,
                match_percent=85,
                vetoed=False,
            )

            profile = UserProfile(
                reviewer_id="user-002",
                top_liked_notes=[("bergamot", 2.0), ("rose", 1.5)],
            )

            details = FragranceDetails(
                name="Good Scent",
                brand="Brand",
                family="floral",
                subfamily="rose",
                top_notes=["bergamot"],
                heart_notes=["rose"],
            )

            response = await service.generate_recommendation_explanation(
                recommendation, profile, details
            )

            assert response.model == "fallback"
            # Should mention the match percentage and matching notes
            assert "85%" in response.text
            assert "bergamot" in response.text.lower()

    async def test_fallback_explanation_good_match_no_matching_notes(self):
        """Test fallback explanation for good match without matching notes."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_enabled = False
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"

            service = LLMService()

            recommendation = Recommendation(
                fragrance_id="frag-003",
                fragrance_name="Other Scent",
                fragrance_brand="Brand",
                match_score=0.75,
                match_percent=75,
                vetoed=False,
            )

            profile = UserProfile(
                reviewer_id="user-003",
                top_liked_notes=[("vanilla", 2.0)],  # Not in fragrance
            )

            details = FragranceDetails(
                name="Other Scent",
                brand="Brand",
                family="woody",
                subfamily="aromatic",
                top_notes=["bergamot"],
            )

            response = await service.generate_recommendation_explanation(
                recommendation, profile, details
            )

            assert response.model == "fallback"
            assert "75%" in response.text
            assert "woody" in response.text.lower()

    async def test_fallback_profile_summary_with_preferences(self):
        """Test fallback profile summary with preferences."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_enabled = False
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"

            service = LLMService()

            profile = UserProfile(
                reviewer_id="user-summary",
                evaluation_count=10,
                top_liked_notes=[("rose", 3.0), ("jasmine", 2.0)],
                top_disliked_notes=[("oud", -2.0)],
            )

            response = await service.generate_profile_summary(profile, "Byron")

            assert response.model == "fallback"
            assert "Byron" in response.text
            assert "10" in response.text
            assert "rose" in response.text.lower()
            assert "oud" in response.text.lower()

    async def test_fallback_profile_summary_no_preferences(self):
        """Test fallback profile summary with no preferences."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_enabled = False
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"

            service = LLMService()

            profile = UserProfile(
                reviewer_id="new-user",
                evaluation_count=2,
            )

            response = await service.generate_profile_summary(profile, "New User")

            assert response.model == "fallback"
            assert "New User" in response.text
            assert "more" in response.text.lower()  # "More evaluations needed"


@pytest.mark.asyncio
class TestLLMServiceCaching:
    """Tests for LLMService caching."""

    async def test_recommendation_caching(self):
        """Test that recommendations are cached."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.llm_enabled = True
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"

            service = LLMService()

            recommendation = Recommendation(
                fragrance_id="frag-cache",
                fragrance_name="Cached Scent",
                fragrance_brand="Brand",
                match_score=0.75,
                match_percent=75,
            )

            profile = UserProfile(reviewer_id="cache-user")

            details = FragranceDetails(
                name="Cached Scent",
                brand="Brand",
                family="fresh",
                subfamily="citrus",
            )

            # Pre-populate cache
            cache_key = service._cache_key("rec", "frag-cache", "cache-user")
            service._cache[cache_key] = "Pre-cached response"

            response = await service.generate_recommendation_explanation(
                recommendation, profile, details
            )

            assert response.cached is True
            assert response.text == "Pre-cached response"

    async def test_profile_summary_caching(self):
        """Test that profile summaries are cached."""
        with patch("fragrance_rater.services.llm_service.settings") as mock_settings:
            mock_settings.openrouter_api_key = "test-key"
            mock_settings.llm_enabled = True
            mock_settings.openrouter_base_url = "https://test.api"
            mock_settings.openrouter_model = "test-model"

            service = LLMService()

            profile = UserProfile(
                reviewer_id="profile-cache-user",
                evaluation_count=5,
            )

            # Pre-populate cache
            cache_key = service._cache_key("profile", "profile-cache-user")
            service._cache[cache_key] = "Pre-cached profile summary"

            response = await service.generate_profile_summary(profile, "Byron")

            assert response.cached is True
            assert response.text == "Pre-cached profile summary"


class TestGetLLMService:
    """Tests for the get_llm_service factory function."""

    def test_returns_llm_service(self):
        """Test factory returns LLMService instance."""
        # Clear cache to ensure fresh instance
        get_llm_service.cache_clear()
        service = get_llm_service()
        assert isinstance(service, LLMService)

    def test_singleton_pattern(self):
        """Test that factory returns the same instance."""
        get_llm_service.cache_clear()
        service1 = get_llm_service()
        service2 = get_llm_service()
        assert service1 is service2
