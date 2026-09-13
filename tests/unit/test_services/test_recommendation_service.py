"""Unit tests for RecommendationService.

Tests the weighted affinity scoring algorithm per ADR-004.
"""

import math

import pytest

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)
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
class TestCalculateMatchScore:
    """Direct unit tests for calculate_match_score with known inputs/outputs
    per the ADR-004 weighted affinity formula (Major finding 10).

    calculate_match_score does not touch the database, so these build the
    fragrance/note/accord object graph purely in memory (no session
    add/commit) and only use `async_session` to satisfy the service
    constructor's signature.
    """

    def _fragrance(
        self,
        *,
        primary_family: str = "woody",
        subfamily: str = "aromatic",
        notes: list[tuple[str, str]] | None = None,
        accords: list[tuple[str, float]] | None = None,
    ) -> Fragrance:
        fragrance = Fragrance(
            id="score-frag",
            name="Score Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="unisex",
            primary_family=primary_family,
            subfamily=subfamily,
            data_source="manual",
        )
        fragrance.notes = [
            FragranceNote(
                note=Note(id=note_id, name=note_name, category="misc"),
                position="top",
            )
            for note_id, note_name in (notes or [])
        ]
        fragrance.accords = [
            FragranceAccord(accord_type=accord_type, intensity=intensity)
            for accord_type, intensity in (accords or [])
        ]
        return fragrance

    async def test_empty_profile_and_fragrance_scores_neutral(self, async_session):
        """No notes, no accords, no family match: raw_score is 0.0, which
        sigmoid-normalizes to exactly 0.5 (50%), and the result is not vetoed.
        """
        service = RecommendationService(async_session)
        profile = UserProfile(reviewer_id="empty-profile")
        fragrance = self._fragrance(
            primary_family="unmatched-family", subfamily="unmatched-sub"
        )

        result = await service.calculate_match_score(profile, fragrance)

        assert result.vetoed is False
        assert result.components["raw"] == 0.0
        assert result.score == pytest.approx(0.5)
        assert result.score_percent == 50

    async def test_family_only_match_uses_family_component_weight(self, async_session):
        """A family-only affinity match is weighted at COMPONENT_WEIGHTS['family']
        (0.20) with no contribution from notes/accords/subfamily.
        """
        service = RecommendationService(async_session)
        profile = UserProfile(
            reviewer_id="family-profile",
            family_affinities={"woody": 5.0},
        )
        fragrance = self._fragrance(primary_family="woody", subfamily="unmatched-sub")

        result = await service.calculate_match_score(profile, fragrance)

        expected_raw = COMPONENT_WEIGHTS["family"] * 5.0
        expected_normalized = 1 / (1 + math.exp(-expected_raw))

        assert result.vetoed is False
        assert result.components["family"] == 5.0
        assert result.components["subfamily"] == 0.0
        assert result.components["raw"] == pytest.approx(expected_raw)
        assert result.score == pytest.approx(expected_normalized)
        assert result.score_percent == int(expected_normalized * 100)

    async def test_notes_and_accords_weighted_and_summed(self, async_session):
        """Note and accord affinities are averaged across the fragrance's
        notes/accords, each weighted by their COMPONENT_WEIGHTS entry, and
        combined with family/subfamily into the sigmoid-normalized score.
        """
        service = RecommendationService(async_session)
        profile = UserProfile(
            reviewer_id="full-profile",
            note_affinities={"n1": 4.0, "n2": 0.0},
            accord_affinities={"citrus": 2.0},
        )
        fragrance = self._fragrance(
            primary_family="unmatched-family",
            subfamily="unmatched-sub",
            notes=[("n1", "Bergamot"), ("n2", "Musk")],
            accords=[("citrus", 1.0)],
        )

        result = await service.calculate_match_score(profile, fragrance)

        expected_note_score = (4.0 + 0.0) / 2  # 2.0
        expected_accord_score = (2.0 * 1.0) / 1  # 2.0
        expected_raw = (
            COMPONENT_WEIGHTS["notes"] * expected_note_score
            + COMPONENT_WEIGHTS["accords"] * expected_accord_score
        )
        expected_normalized = 1 / (1 + math.exp(-expected_raw))

        assert result.components["notes"] == pytest.approx(expected_note_score)
        assert result.components["accords"] == pytest.approx(expected_accord_score)
        assert result.components["raw"] == pytest.approx(expected_raw)
        assert result.score == pytest.approx(expected_normalized)
        assert result.score_percent == int(expected_normalized * 100)

    async def test_veto_triggers_below_threshold_note_affinity(self, async_session):
        """A note affinity strictly below VETO_THRESHOLD short-circuits scoring
        to the fixed vetoed result, regardless of other components.
        """
        service = RecommendationService(async_session)
        profile = UserProfile(
            reviewer_id="veto-profile",
            note_affinities={"n-veto": VETO_THRESHOLD - 0.5},
            family_affinities={"woody": 10.0},  # would otherwise score very high
        )
        fragrance = self._fragrance(
            primary_family="woody",
            notes=[("n-veto", "Patchouli")],
        )

        result = await service.calculate_match_score(profile, fragrance)

        assert result.vetoed is True
        assert result.veto_note == "Patchouli"
        assert result.score == 0.1
        assert result.score_percent == 10

    async def test_veto_threshold_boundary_is_not_vetoed(self, async_session):
        """A note affinity exactly at VETO_THRESHOLD does not trigger the veto
        (the check is strictly `< VETO_THRESHOLD`, not `<=`).
        """
        service = RecommendationService(async_session)
        profile = UserProfile(
            reviewer_id="boundary-profile",
            note_affinities={"n-boundary": VETO_THRESHOLD},
        )
        fragrance = self._fragrance(notes=[("n-boundary", "Oud")])

        result = await service.calculate_match_score(profile, fragrance)

        assert result.vetoed is False

    async def test_extreme_positive_raw_score_does_not_overflow(self, async_session):
        """Critical finding 3: math.exp(-raw_score) overflows once raw_score
        grows large and negative enough that -raw_score exceeds ~709.78 (the
        float64 boundary for math.exp). A very large positive family
        affinity (plausible after many evaluations accumulate) must still
        produce a valid, non-overflowing score that saturates at ~1.0.
        """
        service = RecommendationService(async_session)
        profile = UserProfile(
            reviewer_id="extreme-positive-profile",
            family_affinities={"woody": 1_000_000.0},
        )
        fragrance = self._fragrance(primary_family="woody", subfamily="unmatched-sub")

        result = await service.calculate_match_score(profile, fragrance)

        assert result.vetoed is False
        assert math.isfinite(result.score)
        assert not math.isnan(result.score)
        assert result.score == pytest.approx(1.0)
        assert result.score_percent == 100

    async def test_extreme_negative_raw_score_does_not_overflow(self, async_session):
        """Critical finding 3, negative side: a very large negative family
        affinity must still produce a valid, non-overflowing score that
        saturates at ~0.0 instead of raising OverflowError.
        """
        service = RecommendationService(async_session)
        profile = UserProfile(
            reviewer_id="extreme-negative-profile",
            family_affinities={"woody": -1_000_000.0},
        )
        fragrance = self._fragrance(primary_family="woody", subfamily="unmatched-sub")

        result = await service.calculate_match_score(profile, fragrance)

        assert result.vetoed is False
        assert math.isfinite(result.score)
        assert not math.isnan(result.score)
        assert result.score == pytest.approx(0.0, abs=1e-9)
        assert result.score_percent == 0


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

    async def test_build_preference_profile_excludes_worn_by_evaluation(
        self, async_session
    ):
        """ADR-011: an "on others" rating (worn_by_reviewer_id set) must not
        contribute to the rater's own affinity profile, even though it is a
        live, non-soft-deleted evaluation authored by that reviewer.
        """
        rater = Reviewer(id="rater-worn-by", name="Rater")
        subject = Reviewer(id="subject-worn-by", name="Subject")
        async_session.add_all([rater, subject])

        note = Note(id="note-worn-by", name="Oud", category="woody")
        async_session.add(note)

        fragrance = Fragrance(
            id="frag-worn-by",
            name="Worn By Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="unisex",
            primary_family="woody",
            subfamily="",
            data_source="manual",
        )
        async_session.add(fragrance)

        fn = FragranceNote(
            fragrance_id="frag-worn-by", note_id="note-worn-by", position="top"
        )
        async_session.add(fn)

        # An "on others" rating: rater's opinion of this fragrance as worn
        # by subject. It must be excluded from rater's own profile.
        eval_on_others = Evaluation(
            id="eval-worn-by-on-others",
            fragrance_id="frag-worn-by",
            reviewer_id="rater-worn-by",
            worn_by_reviewer_id="subject-worn-by",
            rating=5,
        )
        async_session.add(eval_on_others)
        await async_session.commit()

        service = RecommendationService(async_session)
        profile = await service.build_preference_profile("rater-worn-by")

        assert profile.evaluation_count == 0
        assert profile.note_affinities == {}

    async def test_build_preference_profile_empty_subfamily_not_bucketed(
        self, async_session
    ):
        """An empty-string subfamily must not pollute family_affinities with
        a "" bucket that every other unknown-subfamily fragrance would then
        match against (Major finding 6).
        """
        reviewer = Reviewer(id="reviewer-nosub", name="No Subfamily User")
        async_session.add(reviewer)

        fragrance = Fragrance(
            id="frag-nosub",
            name="No Subfamily Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="unisex",
            primary_family="woody",
            subfamily="",
            data_source="scraped",
        )
        async_session.add(fragrance)

        eval1 = Evaluation(
            id="eval-nosub",
            fragrance_id="frag-nosub",
            reviewer_id="reviewer-nosub",
            rating=5,
        )
        async_session.add(eval1)
        await async_session.commit()

        service = RecommendationService(async_session)
        profile = await service.build_preference_profile("reviewer-nosub")

        assert "" not in profile.family_affinities
        assert profile.family_affinities.get("woody", 0) == 2.0

    async def test_build_preference_profile_excludes_soft_deleted_fragrance(
        self, async_session
    ):
        """Critical finding 2: an evaluation whose fragrance has since been
        soft-deleted (Fragrance.deleted_at IS NOT NULL) must not contribute
        to the reviewer's preference profile, even though the evaluation
        row itself is still active (Evaluation.deleted_at IS NULL). A live
        evaluation pointing at a "ghost" fragrance must not leak that
        fragrance's notes/family into the profile.
        """
        from fragrance_rater.utils.timestamps import now_naive_utc

        reviewer = Reviewer(id="reviewer-ghost", name="Ghost Fragrance User")
        async_session.add(reviewer)

        note_active = Note(id="note-active", name="Rose", category="floral")
        note_ghost = Note(id="note-ghost", name="Patchouli", category="woody")
        async_session.add_all([note_active, note_ghost])

        # An active fragrance the reviewer rated.
        active_fragrance = Fragrance(
            id="frag-active",
            name="Active Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="unisex",
            primary_family="floral",
            subfamily="rose",
            data_source="manual",
        )
        # A fragrance that has since been soft-deleted out of the catalog.
        ghost_fragrance = Fragrance(
            id="frag-ghost",
            name="Ghost Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="unisex",
            primary_family="oriental",
            subfamily="oud",
            data_source="manual",
            deleted_at=now_naive_utc(),
        )
        async_session.add_all([active_fragrance, ghost_fragrance])

        async_session.add_all(
            [
                FragranceNote(
                    fragrance_id="frag-active", note_id="note-active", position="heart"
                ),
                FragranceNote(
                    fragrance_id="frag-ghost", note_id="note-ghost", position="base"
                ),
            ]
        )

        # Both evaluations are themselves active (not soft-deleted); only
        # the ghost fragrance they point at has been removed from the
        # catalog.
        async_session.add_all(
            [
                Evaluation(
                    id="eval-active",
                    fragrance_id="frag-active",
                    reviewer_id="reviewer-ghost",
                    rating=5,
                ),
                Evaluation(
                    id="eval-ghost",
                    fragrance_id="frag-ghost",
                    reviewer_id="reviewer-ghost",
                    rating=5,
                ),
            ]
        )
        await async_session.commit()

        service = RecommendationService(async_session)
        profile = await service.build_preference_profile("reviewer-ghost")

        # The soft-deleted evaluation must be excluded entirely: only the
        # active fragrance's evaluation counts.
        assert profile.evaluation_count == 1
        assert profile.note_affinities.get("note-active", 0) == 2.0
        assert "note-ghost" not in profile.note_affinities
        assert profile.family_affinities.get("floral", 0) == 2.0
        assert "oriental" not in profile.family_affinities

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

    async def test_get_recommendations_worn_by_evaluation_does_not_exclude_candidate(
        self, async_session
    ):
        """ADR-011: an "on others" rating of the candidate fragrance (the
        reviewer smelled it on someone else, not on themselves) must not
        remove it from `exclude_rated`'s "already rated" set.
        """
        reviewer = Reviewer(id="reviewer-worn-by-candidate", name="Active User")
        subject = Reviewer(id="subject-worn-by-candidate", name="Partner")
        async_session.add_all([reviewer, subject])

        note = Note(id="note-worn-by-candidate", name="Vanilla", category="sweet")
        async_session.add(note)

        for i in range(4):
            frag = Fragrance(
                id=f"frag-wbc-{i}",
                name=f"Fragrance {i}",
                brand="Brand",
                concentration="EDP",
                gender_target="unisex",
                primary_family="oriental" if i < 2 else "woody",
                subfamily="vanilla" if i < 2 else "cedar",
                data_source="manual",
            )
            async_session.add(frag)
            async_session.add(
                FragranceNote(
                    fragrance_id=f"frag-wbc-{i}",
                    note_id="note-worn-by-candidate",
                    position="base",
                )
            )

        for i in range(3):
            async_session.add(
                Evaluation(
                    id=f"eval-wbc-{i}",
                    fragrance_id=f"frag-wbc-{i}",
                    reviewer_id="reviewer-worn-by-candidate",
                    rating=5,
                )
            )
        # An "on others" rating of the would-be unrated candidate: the
        # reviewer smelled frag-wbc-3 on their partner, not on themselves.
        async_session.add(
            Evaluation(
                id="eval-wbc-3-on-others",
                fragrance_id="frag-wbc-3",
                reviewer_id="reviewer-worn-by-candidate",
                worn_by_reviewer_id="subject-worn-by-candidate",
                rating=5,
            )
        )
        await async_session.commit()

        service = RecommendationService(async_session)
        recommendations = await service.get_recommendations(
            "reviewer-worn-by-candidate",
            limit=10,
            exclude_rated=True,
        )

        assert len(recommendations) == 1
        assert recommendations[0].fragrance_id == "frag-wbc-3"

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
        fn1 = FragranceNote(
            fragrance_id="frag-s1", note_id="note-liked", position="heart"
        )
        fn2 = FragranceNote(
            fragrance_id="frag-s2", note_id="note-disliked", position="base"
        )
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
        assert (
            len(summary["top_liked_notes"]) > 0
            or len(summary["top_disliked_notes"]) > 0
        )
