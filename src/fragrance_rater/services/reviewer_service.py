"""Reviewer service for CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.reviewer import Reviewer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Default family reviewers per tech spec
DEFAULT_REVIEWERS = ["Byron", "Veronica", "Bayden", "Ariannah"]


class ReviewerService:
    """Service for reviewer CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: Async database session.
        """
        self.session = session

    async def get_by_id(self, reviewer_id: str) -> Reviewer | None:
        """Get a reviewer by ID.

        Args:
            reviewer_id: UUID of the reviewer.

        Returns:
            Reviewer if found, None otherwise.
        """
        stmt = (
            select(Reviewer)
            .where(Reviewer.id == reviewer_id)
            .options(selectinload(Reviewer.evaluations))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Reviewer | None:
        """Get a reviewer by name.

        Args:
            name: Reviewer name.

        Returns:
            Reviewer if found, None otherwise.
        """
        stmt = select(Reviewer).where(Reviewer.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[tuple[Reviewer, int]]:
        """List all reviewers with evaluation counts.

        Returns:
            List of tuples (Reviewer, evaluation_count).
        """
        stmt = (
            select(Reviewer, func.count(Evaluation.id).label("eval_count"))
            .outerjoin(Evaluation)
            .group_by(Reviewer.id)
            .order_by(Reviewer.name)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def create(self, name: str) -> Reviewer:
        """Create a new reviewer.

        Args:
            name: Reviewer name.

        Returns:
            Created reviewer.
        """
        reviewer = Reviewer(id=str(uuid4()), name=name)
        self.session.add(reviewer)
        await self.session.flush()
        return reviewer

    async def seed_default_reviewers(self) -> list[Reviewer]:
        """Create default family reviewers if they don't exist.

        Returns:
            List of created or existing reviewers.
        """
        reviewers: list[Reviewer] = []
        for name in DEFAULT_REVIEWERS:
            existing = await self.get_by_name(name)
            if existing:
                reviewers.append(existing)
            else:
                reviewer = await self.create(name)
                reviewers.append(reviewer)
        return reviewers

    async def delete(self, reviewer_id: str) -> bool:
        """Delete a reviewer by ID.

        Args:
            reviewer_id: UUID of the reviewer.

        Returns:
            True if deleted, False if not found.
        """
        reviewer = await self.get_by_id(reviewer_id)
        if not reviewer:
            return False

        await self.session.delete(reviewer)
        await self.session.flush()
        return True
