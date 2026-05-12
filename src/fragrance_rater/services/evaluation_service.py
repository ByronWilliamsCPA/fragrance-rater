"""Evaluation service for CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fragrance_rater.models.evaluation import Evaluation

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.evaluation import EvaluationCreate, EvaluationUpdate


class EvaluationService:
    """Service for evaluation CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: Async database session.
        """
        self.session = session

    async def get_by_id(self, evaluation_id: str) -> Evaluation | None:
        """Get an evaluation by ID.

        Args:
            evaluation_id: UUID of the evaluation.

        Returns:
            Evaluation if found, None otherwise.
        """
        stmt = (
            select(Evaluation)
            .where(Evaluation.id == evaluation_id)
            .options(
                selectinload(Evaluation.fragrance),
                selectinload(Evaluation.reviewer),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_reviewer(self, reviewer_id: str) -> list[Evaluation]:
        """Get all evaluations for a reviewer.

        Args:
            reviewer_id: UUID of the reviewer.

        Returns:
            List of evaluations.
        """
        stmt = (
            select(Evaluation)
            .where(Evaluation.reviewer_id == reviewer_id)
            .options(selectinload(Evaluation.fragrance))
            .order_by(Evaluation.evaluated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_fragrance(self, fragrance_id: str) -> list[Evaluation]:
        """Get all evaluations for a fragrance.

        Args:
            fragrance_id: UUID of the fragrance.

        Returns:
            List of evaluations.
        """
        stmt = (
            select(Evaluation)
            .where(Evaluation.fragrance_id == fragrance_id)
            .options(selectinload(Evaluation.reviewer))
            .order_by(Evaluation.evaluated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_reviewer_and_fragrance(
        self, reviewer_id: str, fragrance_id: str
    ) -> Evaluation | None:
        """Get an evaluation for a specific reviewer and fragrance.

        Args:
            reviewer_id: UUID of the reviewer.
            fragrance_id: UUID of the fragrance.

        Returns:
            Evaluation if found, None otherwise.
        """
        stmt = select(Evaluation).where(
            Evaluation.reviewer_id == reviewer_id,
            Evaluation.fragrance_id == fragrance_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: EvaluationCreate) -> Evaluation:
        """Create a new evaluation.

        Args:
            data: Evaluation creation data.

        Returns:
            Created evaluation.
        """
        evaluation = Evaluation(
            id=str(uuid4()),
            fragrance_id=data.fragrance_id,
            reviewer_id=data.reviewer_id,
            rating=data.rating,
            notes=data.notes,
            longevity_rating=data.longevity_rating,
            sillage_rating=data.sillage_rating,
        )
        self.session.add(evaluation)
        await self.session.flush()
        return evaluation

    async def update(
        self, evaluation_id: str, data: EvaluationUpdate
    ) -> Evaluation | None:
        """Update an existing evaluation.

        Args:
            evaluation_id: UUID of the evaluation.
            data: Update data.

        Returns:
            Updated evaluation if found, None otherwise.
        """
        evaluation = await self.get_by_id(evaluation_id)
        if not evaluation:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(evaluation, field, value)

        await self.session.flush()
        return evaluation

    async def delete(self, evaluation_id: str) -> bool:
        """Delete an evaluation by ID.

        Args:
            evaluation_id: UUID of the evaluation.

        Returns:
            True if deleted, False if not found.
        """
        evaluation = await self.get_by_id(evaluation_id)
        if not evaluation:
            return False

        await self.session.delete(evaluation)
        await self.session.flush()
        return True
