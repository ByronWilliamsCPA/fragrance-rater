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
