"""Unit tests for ReviewerService."""

import pytest

from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.services.reviewer_service import DEFAULT_REVIEWERS, ReviewerService


class TestDefaultReviewers:
    """Tests for default reviewer configuration."""

    def test_default_reviewers_count(self):
        """Test that 4 default reviewers are defined."""
        assert len(DEFAULT_REVIEWERS) == 4

    def test_default_reviewers_names(self):
        """Test default reviewer names."""
        assert "Byron" in DEFAULT_REVIEWERS
        assert "Veronica" in DEFAULT_REVIEWERS
        assert "Bayden" in DEFAULT_REVIEWERS
        assert "Ariannah" in DEFAULT_REVIEWERS

    def test_default_reviewers_are_strings(self):
        """Test that default reviewers are name strings."""
        for name in DEFAULT_REVIEWERS:
            assert isinstance(name, str)
            assert len(name) > 0


@pytest.mark.asyncio
class TestReviewerService:
    """Integration tests for ReviewerService."""

    async def test_create_reviewer(self, async_session):
        """Test creating a new reviewer."""
        service = ReviewerService(async_session)
        reviewer = await service.create(name="New User")

        assert reviewer.name == "New User"
        assert reviewer.id is not None

    async def test_get_by_id(self, async_session):
        """Test getting reviewer by ID."""
        # Create reviewer first
        reviewer = Reviewer(id="test-id-001", name="Test User")
        async_session.add(reviewer)
        await async_session.commit()

        service = ReviewerService(async_session)
        found = await service.get_by_id("test-id-001")

        assert found is not None
        assert found.name == "Test User"

    async def test_get_by_id_not_found(self, async_session):
        """Test getting non-existent reviewer."""
        service = ReviewerService(async_session)
        found = await service.get_by_id("nonexistent")

        assert found is None

    async def test_get_by_name(self, async_session):
        """Test getting reviewer by name."""
        reviewer = Reviewer(id="test-id-002", name="Named User")
        async_session.add(reviewer)
        await async_session.commit()

        service = ReviewerService(async_session)
        found = await service.get_by_name("Named User")

        assert found is not None
        assert found.id == "test-id-002"

    async def test_get_by_name_not_found(self, async_session):
        """Test getting non-existent reviewer by name."""
        service = ReviewerService(async_session)
        found = await service.get_by_name("Nobody")

        assert found is None

    async def test_list_all(self, async_session):
        """Test listing all reviewers with evaluation counts."""
        # Create multiple reviewers
        async_session.add(Reviewer(id="r1", name="User 1"))
        async_session.add(Reviewer(id="r2", name="User 2"))
        async_session.add(Reviewer(id="r3", name="User 3"))
        await async_session.commit()

        service = ReviewerService(async_session)
        results = await service.list_all()

        assert len(results) == 3
        # Each result is a tuple of (Reviewer, count)
        assert all(isinstance(r[0], Reviewer) for r in results)
        assert all(r[1] == 0 for r in results)  # No evaluations yet

    async def test_seed_default_reviewers(self, async_session):
        """Test seeding default reviewers."""
        service = ReviewerService(async_session)
        reviewers = await service.seed_default_reviewers()
        await async_session.commit()

        assert len(reviewers) == 4

        names = [r.name for r in reviewers]
        assert "Byron" in names
        assert "Veronica" in names
        assert "Bayden" in names
        assert "Ariannah" in names

    async def test_seed_default_reviewers_idempotent(self, async_session):
        """Test that seeding is idempotent."""
        service = ReviewerService(async_session)

        # Seed twice
        first_seed = await service.seed_default_reviewers()
        await async_session.commit()

        second_seed = await service.seed_default_reviewers()
        await async_session.commit()

        # Should have same count
        assert len(first_seed) == len(second_seed)

        # Should only have 4 total
        all_reviewers = await service.list_all()
        assert len(all_reviewers) == 4

    async def test_delete_reviewer(self, async_session):
        """Test deleting a reviewer."""
        reviewer = Reviewer(id="delete-me", name="Delete Me")
        async_session.add(reviewer)
        await async_session.commit()

        service = ReviewerService(async_session)
        result = await service.delete("delete-me")
        await async_session.commit()

        assert result is True

        # Verify deleted
        found = await service.get_by_id("delete-me")
        assert found is None

    async def test_delete_nonexistent_reviewer(self, async_session):
        """Test deleting non-existent reviewer."""
        service = ReviewerService(async_session)
        result = await service.delete("nonexistent")

        assert result is False


@pytest.mark.asyncio
class TestReviewerSoftDeleteAndEvaluationCount:
    """Critical finding 2: soft-delete and the deleted_at-aware count."""

    async def test_delete_sets_deleted_at_without_removing_row(self, async_session):
        """The row must survive delete(), only deleted_at is set."""
        from sqlalchemy import select

        reviewer = Reviewer(id="soft-delete-rev-001", name="Soft Delete Reviewer")
        async_session.add(reviewer)
        await async_session.commit()

        service = ReviewerService(async_session)
        result = await service.delete("soft-delete-rev-001")
        await async_session.commit()

        assert result is True

        raw = await async_session.execute(
            select(Reviewer).where(Reviewer.id == "soft-delete-rev-001")
        )
        row = raw.scalar_one_or_none()
        assert row is not None
        assert row.deleted_at is not None
        assert await service.get_by_id("soft-delete-rev-001") is None

    async def test_list_all_excludes_soft_deleted_reviewers(self, async_session):
        """list_all() must never return a soft-deleted reviewer."""
        reviewer = Reviewer(id="soft-delete-rev-002", name="Hidden Reviewer")
        async_session.add(reviewer)
        await async_session.commit()

        service = ReviewerService(async_session)
        await service.delete("soft-delete-rev-002")
        await async_session.commit()

        results = await service.list_all()
        assert all(r.id != "soft-delete-rev-002" for r, _count in results)

    async def test_count_evaluations_excludes_soft_deleted_evaluations(
        self, async_session
    ):
        """count_evaluations() must not count a soft-deleted evaluation."""
        from fragrance_rater.models.evaluation import Evaluation
        from fragrance_rater.models.fragrance import Fragrance

        reviewer = Reviewer(id="count-eval-rev-001", name="Count Reviewer")
        fragrance = Fragrance(
            id="count-eval-frag-001",
            name="Count Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(reviewer)
        async_session.add(fragrance)
        await async_session.commit()

        active_eval = Evaluation(
            id="count-eval-active",
            fragrance_id=fragrance.id,
            reviewer_id=reviewer.id,
            rating=4,
        )
        async_session.add(active_eval)
        await async_session.commit()

        service = ReviewerService(async_session)
        assert await service.count_evaluations(reviewer.id) == 1

        from fragrance_rater.services.evaluation_service import EvaluationService

        eval_service = EvaluationService(async_session)
        await eval_service.delete("count-eval-active")
        await async_session.commit()

        assert await service.count_evaluations(reviewer.id) == 0

    async def test_count_evaluations_for_reviewer_with_none(self, async_session):
        """A reviewer with no evaluations counts as zero."""
        reviewer = Reviewer(id="count-eval-rev-002", name="No Evals Reviewer")
        async_session.add(reviewer)
        await async_session.commit()

        service = ReviewerService(async_session)
        assert await service.count_evaluations(reviewer.id) == 0


@pytest.mark.asyncio
class TestReviewerDedupPartialUniqueIndex:
    """`uq_reviewer_name` is a partial unique index scoped to live rows.

    Regression coverage for the soft-delete/dedup interaction: a plain
    unique constraint on `name` would let a soft-deleted reviewer block
    recreating/re-seeding a reviewer with the same name forever. See the
    resolved RAD note on `Reviewer.deleted_at`.
    """

    async def test_recreate_after_soft_delete_succeeds(self, async_session):
        """Recreating a reviewer with the same name after a soft delete succeeds."""
        from sqlalchemy import select

        original = Reviewer(id="dedup-rev-orig", name="Reused Reviewer Name")
        async_session.add(original)
        await async_session.commit()

        service = ReviewerService(async_session)
        assert await service.delete("dedup-rev-orig") is True
        await async_session.commit()

        recreated = Reviewer(id="dedup-rev-new", name="Reused Reviewer Name")
        async_session.add(recreated)
        await async_session.commit()  # Must not raise IntegrityError.

        rows = (
            (
                await async_session.execute(
                    select(Reviewer).where(Reviewer.name == "Reused Reviewer Name")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        live = [r for r in rows if r.deleted_at is None]
        deleted = [r for r in rows if r.deleted_at is not None]
        assert len(live) == 1
        assert len(deleted) == 1
        assert live[0].id == "dedup-rev-new"
        assert deleted[0].id == "dedup-rev-orig"

    async def test_two_live_reviewers_still_reject_duplicate_name(self, async_session):
        """Two LIVE reviewers sharing a name must still be rejected."""
        from sqlalchemy.exc import IntegrityError

        first = Reviewer(id="dup-rev-1", name="Duplicate Reviewer Name")
        async_session.add(first)
        await async_session.commit()

        second = Reviewer(id="dup-rev-2", name="Duplicate Reviewer Name")
        async_session.add(second)
        with pytest.raises(IntegrityError):
            await async_session.commit()
        await async_session.rollback()
