"""Unit tests for RecommendationService.

Tests the weighted affinity scoring algorithm per ADR-004.
"""

import pytest

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance, FragranceAccord, FragranceNote, Note
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.services.recommendation_service import (
    COMPONENT_WEIGHTS,
    MIN_EVALUATIONS,
    RATING_WEIGHTS,
    VETO_THRESHOLD,
    InsufficientDataError,
    MatchResult,
    Recommendation,
    RecommendationService,
    UserProfile,
)


class TestRatingWeights:
    """Tests for rating weight constants."""

    def test_rating_weights_correct(self):
        """Verify rating weights match ADR-004 spec."""
        assert RATING_WEIGHTS[1] == -2.0
        assert RATING_WEIGHTS[2] == -1.0
        assert RATING_WEIGHTS[3] == 0.0
        assert RATING_WEIGHTS[4] == 1.0
        assert RATING_WEIGHTS[5] == 2.0

    def test_component_weights_sum_to_one(self):
        """Verify component weights sum to 1.0."""
        total = sum(COMPONENT_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_component_weights_correct(self):
        """Verify component weights match ADR-004 spec."""
        assert COMPONENT_WEIGHTS["notes"] == 0.40
        assert COMPONENT_WEIGHTS["accords"] == 0.30
        assert COMPONENT_WEIGHTS["family"] == 0.20
        assert COMPONENT_WEIGHTS["subfamily"] == 0.10

    def test_veto_threshold(self):
        """Verify veto threshold is set correctly."""
        assert VETO_THRESHOLD == -3.0

    def test_min_evaluations(self):
        """Verify minimum evaluations requirement."""
        assert MIN_EVALUATIONS == 3


class TestUserProfile:
    """Tests for UserProfile dataclass."""

    def test_default_values(self):
        """Test UserProfile initializes with empty defaults."""
        profile = UserProfile(reviewer_id="test-123")
        assert profile.reviewer_id == "test-123"
        assert profile.note_affinities == {}
        assert profile.accord_affinities == {}
        assert profile.family_affinities == {}
        assert profile.evaluation_count == 0
        assert profile.top_liked_notes == []
        assert profile.top_disliked_notes == []

    def test_with_data(self):
        """Test UserProfile with populated data."""
        profile = UserProfile(
            reviewer_id="test-456",
            note_affinities={"bergamot": 2.0, "musk": -1.0},
            accord_affinities={"citrus": 1.5},
            family_affinities={"woody": 0.5},
            evaluation_count=5,
            top_liked_notes=[("bergamot", 2.0)],
            top_disliked_notes=[("musk", -1.0)],
        )
        assert profile.evaluation_count == 5
        assert profile.note_affinities["bergamot"] == 2.0


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_basic_match(self):
        """Test basic match result."""
        result = MatchResult(score=0.75, score_percent=75)
        assert result.score == 0.75
        assert result.score_percent == 75
        assert result.vetoed is False
        assert result.veto_note is None

    def test_vetoed_match(self):
        """Test vetoed match result."""
        result = MatchResult(
            score=0.1,
            score_percent=10,
            vetoed=True,
            veto_note="patchouli",
        )
        assert result.vetoed is True
        assert result.veto_note == "patchouli"


class TestRecommendation:
    """Tests for Recommendation dataclass."""

    def test_recommendation_creation(self):
        """Test recommendation creation."""
        rec = Recommendation(
            fragrance_id="frag-001",
            fragrance_name="Test Scent",
            fragrance_brand="Test Brand",
            match_score=0.85,
            match_percent=85,
        )
        assert rec.fragrance_id == "frag-001"
        assert rec.match_score == 0.85
        assert rec.vetoed is False

    def test_vetoed_recommendation(self):
        """Test vetoed recommendation."""
        rec = Recommendation(
            fragrance_id="frag-002",
            fragrance_name="Bad Scent",
            fragrance_brand="Some Brand",
            match_score=0.1,
            match_percent=10,
            vetoed=True,
            veto_reason="Contains patchouli which you dislike",
        )
        assert rec.vetoed is True
        assert "patchouli" in rec.veto_reason


class TestInsufficientDataError:
    """Tests for InsufficientDataError exception."""

    def test_exception_message(self):
        """Test exception can be raised with message."""
        with pytest.raises(InsufficientDataError) as exc_info:
            raise InsufficientDataError("Need more evaluations")
        assert "Need more evaluations" in str(exc_info.value)


@pytest.mark.asyncio
class TestRecommendationServiceIntegration:
    """Integration tests for RecommendationService with database."""

    async def test_build_preference_profile_empty(self, async_session):
        """Test building profile with no evaluations."""
        service = RecommendationService(async_session)
        profile = await service.build_preference_profile("nonexistent-user")

        assert profile.evaluation_count == 0
        assert profile.note_affinities == {}

    async def test_build_preference_profile_with_evaluations(self, async_session):
        """Test building profile with evaluations."""
        # Create test data
        reviewer = Reviewer(id="reviewer-001", name="Test User")
        async_session.add(reviewer)

        note = Note(id="note-001", name="Bergamot", category="citrus")
        async_session.add(note)

        fragrance = Fragrance(
            id="frag-001",
            name="Test Fragrance",
            brand="Test Brand",
            concentration="EDP",
            gender_target="unisex",
            primary_family="citrus",
            subfamily="fresh",
            data_source="manual",
        )
        async_session.add(fragrance)

        # Add note to fragrance
        fn = FragranceNote(
            fragrance_id="frag-001",
            note_id="note-001",
            position="top",
        )
        async_session.add(fn)

        # Add evaluation (5 stars = +2.0 weight)
        eval1 = Evaluation(
            id="eval-001",
            fragrance_id="frag-001",
            reviewer_id="reviewer-001",
            rating=5,
        )
        async_session.add(eval1)
        await async_session.commit()

        # Build profile
        service = RecommendationService(async_session)
        profile = await service.build_preference_profile("reviewer-001")

        assert profile.evaluation_count == 1
        assert profile.note_affinities.get("note-001", 0) == 2.0  # 5-star = +2.0

    async def test_get_recommendations_insufficient_data(self, async_session):
        """Test that insufficient evaluations raises error."""
        # Create reviewer with only 2 evaluations (need 3)
        reviewer = Reviewer(id="reviewer-002", name="New User")
        async_session.add(reviewer)

        # Create 2 fragrances and evaluations
        for i in range(2):
            frag = Fragrance(
                id=f"frag-{i}",
                name=f"Fragrance {i}",
                brand="Brand",
                concentration="EDP",
                gender_target="unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="manual",
            )
            async_session.add(frag)

            eval_item = Evaluation(
                id=f"eval-{i}",
                fragrance_id=f"frag-{i}",
                reviewer_id="reviewer-002",
                rating=4,
            )
            async_session.add(eval_item)

        await async_session.commit()

        service = RecommendationService(async_session)

        with pytest.raises(InsufficientDataError):
            await service.get_recommendations("reviewer-002")

    async def test_get_recommendations_success(self, async_session):
        """Test successful recommendation generation."""
        # Create reviewer
        reviewer = Reviewer(id="reviewer-003", name="Active User")
        async_session.add(reviewer)

        # Create note
        note = Note(id="note-002", name="Vanilla", category="sweet")
        async_session.add(note)

        # Create 4 fragrances (3 rated, 1 unrated for recommendation)
        for i in range(4):
            frag = Fragrance(
                id=f"frag-r{i}",
                name=f"Fragrance {i}",
                brand="Brand",
                concentration="EDP",
                gender_target="unisex",
                primary_family="oriental" if i < 2 else "woody",
                subfamily="vanilla" if i < 2 else "cedar",
                data_source="manual",
            )
            async_session.add(frag)

            # Add note to fragrance
            fn = FragranceNote(
                fragrance_id=f"frag-r{i}",
                note_id="note-002",
                position="base",
            )
            async_session.add(fn)

        # Create 3 evaluations (meeting minimum)
        for i in range(3):
            eval_item = Evaluation(
                id=f"eval-r{i}",
                fragrance_id=f"frag-r{i}",
                reviewer_id="reviewer-003",
                rating=5,  # High rating to build positive affinity
            )
            async_session.add(eval_item)

        await async_session.commit()

        service = RecommendationService(async_session)
        recommendations = await service.get_recommendations(
            "reviewer-003",
            limit=10,
            exclude_rated=True,
        )

        # Should recommend the unrated fragrance
        assert len(recommendations) == 1
        assert recommendations[0].fragrance_id == "frag-r3"

    async def test_get_reviewer_profile_summary(self, async_session):
        """Test profile summary generation."""
        # Create reviewer
        reviewer = Reviewer(id="reviewer-004", name="Summary User")
        async_session.add(reviewer)

        # Create notes
        note1 = Note(id="note-liked", name="Rose", category="floral")
        note2 = Note(id="note-disliked", name="Oud", category="woody")
        async_session.add_all([note1, note2])

        # Create fragrances with different notes
        frag1 = Fragrance(
            id="frag-s1",
            name="Floral Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="feminine",
            primary_family="floral",
            subfamily="rose",
            data_source="manual",
        )
        frag2 = Fragrance(
            id="frag-s2",
            name="Oud Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="masculine",
            primary_family="oriental",
            subfamily="oud",
            data_source="manual",
        )
        async_session.add_all([frag1, frag2])

        # Add notes to fragrances
        fn1 = FragranceNote(fragrance_id="frag-s1", note_id="note-liked", position="heart")
        fn2 = FragranceNote(fragrance_id="frag-s2", note_id="note-disliked", position="base")
        async_session.add_all([fn1, fn2])

        # High rating for floral, low for oud
        eval1 = Evaluation(
            id="eval-s1",
            fragrance_id="frag-s1",
            reviewer_id="reviewer-004",
            rating=5,
        )
        eval2 = Evaluation(
            id="eval-s2",
            fragrance_id="frag-s2",
            reviewer_id="reviewer-004",
            rating=1,
        )
        async_session.add_all([eval1, eval2])
        await async_session.commit()

        service = RecommendationService(async_session)
        summary = await service.get_reviewer_profile_summary("reviewer-004")

        assert summary["evaluation_count"] == 2
        # Should have liked notes (rose) and disliked notes (oud)
        assert len(summary["top_liked_notes"]) > 0 or len(summary["top_disliked_notes"]) > 0
