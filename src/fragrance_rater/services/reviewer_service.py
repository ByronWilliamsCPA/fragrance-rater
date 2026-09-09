"""Reviewer service for CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime
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
    """Service for reviewer CRUD operations.

    Args:
        session (AsyncSession): Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, reviewer_id: str) -> Reviewer | None:
        """Get a reviewer by ID.

        Args:
            reviewer_id (str): UUID of the reviewer.

        Returns:
            Reviewer | None: Reviewer if found, None otherwise.
        """
        stmt = (
            select(Reviewer)
            .where(Reviewer.id == reviewer_id, Reviewer.deleted_at.is_(None))
            .options(selectinload(Reviewer.evaluations))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_evaluations(self, reviewer_id: str) -> int:
        """Count a reviewer's active (non-soft-deleted) evaluations.

        Critical finding 2: `Reviewer.evaluations`, eager-loaded in
        get_by_id, is a raw ORM relationship with no deleted_at filter (a
        relationship's primaryjoin can't safely carry that filter without
        also affecting its cascade="all, delete-orphan" semantics). This
        method is the filtered count api/reviewers.py's get_reviewer should
        use instead of `len(reviewer.evaluations)`.

        Args:
            reviewer_id (str): UUID of the reviewer.

        Returns:
            int: Number of non-deleted evaluations for this reviewer.
        """
        stmt = select(func.count(Evaluation.id)).where(
            Evaluation.reviewer_id == reviewer_id, Evaluation.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_name(self, name: str) -> Reviewer | None:
        """Get a reviewer by name.

        Args:
            name (str): Reviewer name.

        Returns:
            Reviewer | None: Reviewer if found, None otherwise.
        """
        stmt = select(Reviewer).where(
            Reviewer.name == name, Reviewer.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[tuple[Reviewer, int]]:
        """List all reviewers with evaluation counts.

        Returns:
            list[tuple[Reviewer, int]]: List of tuples (Reviewer, evaluation_count).
        """
        # Critical finding 2: a correlated scalar subquery (rather than an
        # outerjoin + group_by) so the count only ever includes
        # non-soft-deleted evaluations, without depending on the SQL
        # FILTER clause (portability across SQLite/Postgres versions).
        eval_count_subq = (
            select(func.count(Evaluation.id))
            .where(
                Evaluation.reviewer_id == Reviewer.id,
                Evaluation.deleted_at.is_(None),
            )
            .correlate(Reviewer)
            .scalar_subquery()
        )
        stmt = (
            select(Reviewer, eval_count_subq.label("eval_count"))
            .where(Reviewer.deleted_at.is_(None))
            .order_by(Reviewer.name)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def create(self, name: str) -> Reviewer:
        """Create a new reviewer.

        Args:
            name (str): Reviewer name.

        Returns:
            Reviewer: Created reviewer.
        """
        reviewer = Reviewer(id=str(uuid4()), name=name)
        self.session.add(reviewer)
        await self.session.flush()
        return reviewer

    async def seed_default_reviewers(self) -> list[Reviewer]:
        """Create default family reviewers if they don't exist.

        Returns:
            list[Reviewer]: List of created or existing reviewers.
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
        """Soft-delete a reviewer by ID.

        Critical finding 2: this sets `deleted_at` instead of issuing a real
        DELETE, so a reviewer's past evaluations are never cascade-deleted.

        Args:
            reviewer_id (str): UUID of the reviewer.

        Returns:
            bool: True if soft-deleted, False if not found (or already
                soft-deleted, since get_by_id excludes it).
        """
        reviewer = await self.get_by_id(reviewer_id)
        if not reviewer:
            return False

        reviewer.deleted_at = datetime.now(UTC)
        await self.session.flush()
        return True
