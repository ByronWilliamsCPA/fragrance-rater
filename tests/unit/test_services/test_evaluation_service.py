"""Unit tests for EvaluationService."""

from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.evaluation import EvaluationCreate, EvaluationUpdate
from fragrance_rater.services.evaluation_service import EvaluationService


@pytest_asyncio.fixture
async def setup_fragrance_and_reviewer(async_session):
    """Create a fragrance and reviewer for evaluation tests."""
    fragrance = Fragrance(
        id="eval-frag-001",
        name="Test Fragrance",
        brand="Test Brand",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="manual",
    )
    reviewer = Reviewer(id="eval-reviewer-001", name="Test Reviewer")

    async_session.add(fragrance)
    async_session.add(reviewer)
    await async_session.commit()

    return fragrance, reviewer


@pytest.mark.asyncio
class TestEvaluationService:
    """Integration tests for EvaluationService."""

    async def test_create_evaluation(self, async_session, setup_fragrance_and_reviewer):
        """Test creating an evaluation."""
        fragrance, reviewer = setup_fragrance_and_reviewer

        service = EvaluationService(async_session)
        data = EvaluationCreate(
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=5,
            notes="Excellent fragrance!",
        )
        evaluation = await service.create(data)

        assert evaluation.rating == 5
        assert evaluation.notes == "Excellent fragrance!"
        assert evaluation.fragrance_id == fragrance.id
        assert evaluation.reviewer_id == reviewer.id

    async def test_create_evaluation_with_optional_fields(
        self, async_session, setup_fragrance_and_reviewer
    ):
        """Test creating evaluation with longevity and sillage ratings."""
        fragrance, reviewer = setup_fragrance_and_reviewer

        service = EvaluationService(async_session)
        data = EvaluationCreate(
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=4,
            longevity_rating=5,
            sillage_rating=3,
        )
        evaluation = await service.create(data)

        assert evaluation.longevity_rating == 5
        assert evaluation.sillage_rating == 3

    async def test_get_by_id(self, async_session, setup_fragrance_and_reviewer):
        """Test getting evaluation by ID."""
        fragrance, reviewer = setup_fragrance_and_reviewer

        evaluation = Evaluation(
            id="get-eval-001",
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=4,
        )
        async_session.add(evaluation)
        await async_session.commit()

        service = EvaluationService(async_session)
        found = await service.get_by_id("get-eval-001")

        assert found is not None
        assert found.rating == 4

    async def test_get_by_id_not_found(self, async_session):
        """Test getting non-existent evaluation."""
        service = EvaluationService(async_session)
        found = await service.get_by_id("nonexistent")

        assert found is None

    async def test_get_by_reviewer(self, async_session, setup_fragrance_and_reviewer):
        """Test getting evaluations by reviewer."""
        _fragrance, reviewer = setup_fragrance_and_reviewer

        # Create multiple evaluations
        for i in range(3):
            # Create additional fragrances
            frag = Fragrance(
                id=f"multi-frag-{i}",
                name=f"Fragrance {i}",
                brand="Brand",
                concentration="EDP",
                gender_target="unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="manual",
            )
            async_session.add(frag)
            await async_session.flush()

            eval_item = Evaluation(
                id=f"multi-eval-{i}",
                fragrance_id=f"multi-frag-{i}",
                reviewer_id=reviewer.id,
                rating=3 + i,
            )
            async_session.add(eval_item)

        await async_session.commit()

        service = EvaluationService(async_session)
        evaluations = await service.get_by_reviewer(reviewer.id)

        assert len(evaluations) == 3

    async def test_get_by_fragrance(self, async_session, setup_fragrance_and_reviewer):
        """Test getting evaluations by fragrance."""
        fragrance, _reviewer = setup_fragrance_and_reviewer

        # Create multiple reviewers and evaluations
        for i in range(2):
            rev = Reviewer(id=f"multi-rev-{i}", name=f"Reviewer {i}")
            async_session.add(rev)
            await async_session.flush()

            eval_item = Evaluation(
                id=f"frag-eval-{i}",
                fragrance_id=fragrance.id,
                reviewer_id=f"multi-rev-{i}",
                rating=4,
            )
            async_session.add(eval_item)

        await async_session.commit()

        service = EvaluationService(async_session)
        evaluations = await service.get_by_fragrance(fragrance.id)

        assert len(evaluations) == 2

    async def test_get_by_reviewer_and_fragrance(
        self, async_session, setup_fragrance_and_reviewer
    ):
        """Test getting specific reviewer-fragrance evaluation."""
        fragrance, reviewer = setup_fragrance_and_reviewer

        evaluation = Evaluation(
            id="specific-eval-001",
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=5,
        )
        async_session.add(evaluation)
        await async_session.commit()

        service = EvaluationService(async_session)
        found = await service.get_by_reviewer_and_fragrance(reviewer.id, fragrance.id)

        assert found is not None
        assert found.rating == 5

    async def test_get_by_reviewer_and_fragrance_not_found(self, async_session):
        """Test getting non-existent reviewer-fragrance evaluation."""
        service = EvaluationService(async_session)
        found = await service.get_by_reviewer_and_fragrance(
            "nonexistent", "nonexistent"
        )

        assert found is None

    async def test_update_evaluation(self, async_session, setup_fragrance_and_reviewer):
        """Test updating an evaluation."""
        fragrance, reviewer = setup_fragrance_and_reviewer

        evaluation = Evaluation(
            id="update-eval-001",
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=3,
            notes="Initial notes",
        )
        async_session.add(evaluation)
        await async_session.commit()

        service = EvaluationService(async_session)
        update_data = EvaluationUpdate(rating=5, notes="Updated notes")
        updated = await service.update("update-eval-001", update_data)

        assert updated is not None
        assert updated.rating == 5
        assert updated.notes == "Updated notes"

    async def test_update_nonexistent_evaluation(self, async_session):
        """Test updating non-existent evaluation."""
        service = EvaluationService(async_session)
        update_data = EvaluationUpdate(rating=5)
        updated = await service.update("nonexistent", update_data)

        assert updated is None

    async def test_delete_evaluation(self, async_session, setup_fragrance_and_reviewer):
        """Test deleting an evaluation."""
        fragrance, reviewer = setup_fragrance_and_reviewer

        evaluation = Evaluation(
            id="delete-eval-001",
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=3,
        )
        async_session.add(evaluation)
        await async_session.commit()

        service = EvaluationService(async_session)
        result = await service.delete("delete-eval-001")

        assert result is True

        # Verify deleted
        found = await service.get_by_id("delete-eval-001")
        assert found is None

    async def test_delete_nonexistent_evaluation(self, async_session):
        """Test deleting non-existent evaluation."""
        service = EvaluationService(async_session)
        result = await service.delete("nonexistent")

        assert result is False


@pytest.mark.asyncio
class TestEvaluationServiceCacheInvalidation:
    """Tests for Major finding 7: mutations invalidate the reviewer's LLM cache."""

    async def test_create_invalidates_reviewer_cache(
        self, async_session, setup_fragrance_and_reviewer
    ):
        """Creating an evaluation invalidates that reviewer's cached explanations."""
        fragrance, reviewer = setup_fragrance_and_reviewer
        mock_llm = MagicMock()

        service = EvaluationService(async_session, llm_service=mock_llm)
        data = EvaluationCreate(
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=5,
        )
        await service.create(data)

        mock_llm.invalidate_reviewer_cache.assert_called_once_with(reviewer.id)

    async def test_update_invalidates_reviewer_cache(
        self, async_session, setup_fragrance_and_reviewer
    ):
        """Updating an evaluation invalidates that reviewer's cached explanations."""
        fragrance, reviewer = setup_fragrance_and_reviewer
        evaluation = Evaluation(
            id="cache-update-eval",
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=3,
        )
        async_session.add(evaluation)
        await async_session.commit()

        mock_llm = MagicMock()
        service = EvaluationService(async_session, llm_service=mock_llm)
        await service.update("cache-update-eval", EvaluationUpdate(rating=4))

        mock_llm.invalidate_reviewer_cache.assert_called_once_with(reviewer.id)

    async def test_update_nonexistent_does_not_invalidate_cache(self, async_session):
        """Updating a missing evaluation must not touch the cache."""
        mock_llm = MagicMock()
        service = EvaluationService(async_session, llm_service=mock_llm)
        result = await service.update("nonexistent", EvaluationUpdate(rating=5))

        assert result is None
        mock_llm.invalidate_reviewer_cache.assert_not_called()

    async def test_delete_invalidates_reviewer_cache(
        self, async_session, setup_fragrance_and_reviewer
    ):
        """Deleting an evaluation invalidates that reviewer's cached explanations."""
        fragrance, reviewer = setup_fragrance_and_reviewer
        evaluation = Evaluation(
            id="cache-delete-eval",
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=3,
        )
        async_session.add(evaluation)
        await async_session.commit()

        mock_llm = MagicMock()
        service = EvaluationService(async_session, llm_service=mock_llm)
        result = await service.delete("cache-delete-eval")

        assert result is True
        mock_llm.invalidate_reviewer_cache.assert_called_once_with(reviewer.id)

    async def test_delete_nonexistent_does_not_invalidate_cache(self, async_session):
        """Deleting a missing evaluation must not touch the cache."""
        mock_llm = MagicMock()
        service = EvaluationService(async_session, llm_service=mock_llm)
        result = await service.delete("nonexistent")

        assert result is False
        mock_llm.invalidate_reviewer_cache.assert_not_called()

    async def test_default_llm_service_is_the_singleton(self, async_session):
        """Omitting llm_service falls back to the process-wide singleton."""
        from fragrance_rater.services.llm_service import get_llm_service

        service = EvaluationService(async_session)

        assert service._llm_service is get_llm_service()
