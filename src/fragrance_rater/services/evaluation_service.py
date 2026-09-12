"""Evaluation service for CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.services.llm_service import get_llm_service
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.evaluation import EvaluationCreate, EvaluationUpdate
    from fragrance_rater.services.llm_service import LLMService


class EvaluationService:
    """Service for evaluation CRUD operations.

    Args:
        session (AsyncSession): Async database session.
        llm_service (LLMService | None): LLM service whose per-reviewer
            explanation cache is invalidated after create/update/delete
            (Major finding 7). Defaults to the process-wide singleton.
    """

    def __init__(
        self, session: AsyncSession, llm_service: LLMService | None = None
    ) -> None:
        self.session = session
        # #ASSUME: data-integrity: an evaluation's rating/notes are inputs to
        # cached LLM explanations (see llm_service.py); any create, update,
        # or delete can make a previously-cached explanation for this
        # reviewer stale.
        # #VERIFY: every mutating method below invalidates this reviewer's
        # cache entries after the database write succeeds.
        self._llm_service = (
            llm_service if llm_service is not None else get_llm_service()
        )

    async def get_by_id(self, evaluation_id: str) -> Evaluation | None:
        """Get an evaluation by ID.

        Args:
            evaluation_id (str): UUID of the evaluation.

        Returns:
            Evaluation | None: Evaluation if found, None otherwise.
        """
        stmt = (
            select(Evaluation)
            .where(Evaluation.id == evaluation_id, Evaluation.deleted_at.is_(None))
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
            reviewer_id (str): UUID of the reviewer.

        Returns:
            list[Evaluation]: List of evaluations.
        """
        stmt = (
            select(Evaluation)
            .where(
                Evaluation.reviewer_id == reviewer_id, Evaluation.deleted_at.is_(None)
            )
            .options(selectinload(Evaluation.fragrance))
            .order_by(
                Evaluation.evaluated_at.desc(),
                Evaluation.created_at.desc(),
                Evaluation.id.desc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_fragrance(self, fragrance_id: str) -> list[Evaluation]:
        """Get all evaluations for a fragrance.

        Args:
            fragrance_id (str): UUID of the fragrance.

        Returns:
            list[Evaluation]: List of evaluations.
        """
        stmt = (
            select(Evaluation)
            .where(
                Evaluation.fragrance_id == fragrance_id, Evaluation.deleted_at.is_(None)
            )
            .options(selectinload(Evaluation.reviewer))
            .order_by(
                Evaluation.evaluated_at.desc(),
                Evaluation.created_at.desc(),
                Evaluation.id.desc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_reviewer_and_fragrance(
        self, reviewer_id: str, fragrance_id: str
    ) -> Evaluation | None:
        """Get the latest active encounter for a reviewer and fragrance.

        Args:
            reviewer_id (str): UUID of the reviewer.
            fragrance_id (str): UUID of the fragrance.

        Returns:
            Evaluation | None: Evaluation if found, None otherwise.
        """
        stmt = (
            select(Evaluation)
            .where(
                Evaluation.reviewer_id == reviewer_id,
                Evaluation.fragrance_id == fragrance_id,
                Evaluation.deleted_at.is_(None),
            )
            .order_by(
                Evaluation.evaluated_at.desc(),
                Evaluation.created_at.desc(),
                Evaluation.id.desc(),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self, data: EvaluationCreate, recorded_by: str | None = None
    ) -> Evaluation:
        """Create a new evaluation.

        Args:
            data (EvaluationCreate): Evaluation creation data.
            recorded_by (str | None): Authentik username of whoever was
                logged in when this evaluation was submitted (Critical
                finding 2). Independent of `data.reviewer_id`; None when no
                Authentik identity is available.

        Returns:
            Evaluation: Created evaluation.
        """
        evaluation = Evaluation(
            id=str(uuid4()),
            fragrance_id=data.fragrance_id,
            reviewer_id=data.reviewer_id,
            rating=data.rating,
            notes=data.notes,
            longevity_rating=data.longevity_rating,
            sillage_rating=data.sillage_rating,
            worn_by_reviewer_id=data.worn_by_reviewer_id,
            recorded_by=recorded_by,
            evaluated_at=data.evaluated_at or now_naive_utc(),
        )
        self.session.add(evaluation)
        await self.session.flush()
        self._llm_service.invalidate_reviewer_cache(evaluation.reviewer_id)
        return evaluation

    async def update(
        self, evaluation_id: str, data: EvaluationUpdate
    ) -> Evaluation | None:
        """Update an existing evaluation.

        Args:
            evaluation_id (str): UUID of the evaluation.
            data (EvaluationUpdate): Update data.

        Returns:
            Evaluation | None: Updated evaluation if found, None otherwise.
        """
        evaluation = await self.get_by_id(evaluation_id)
        if not evaluation:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(evaluation, field, value)

        await self.session.flush()
        self._llm_service.invalidate_reviewer_cache(evaluation.reviewer_id)
        return evaluation

    async def delete(self, evaluation_id: str) -> bool:
        """Soft-delete an evaluation by ID.

        Critical finding 2: this sets `deleted_at` instead of issuing a real
        DELETE.

        Args:
            evaluation_id (str): UUID of the evaluation.

        Returns:
            bool: True if soft-deleted, False if not found (or already
                soft-deleted, since get_by_id excludes it).
        """
        evaluation = await self.get_by_id(evaluation_id)
        if not evaluation:
            return False

        reviewer_id = evaluation.reviewer_id
        evaluation.deleted_at = now_naive_utc()
        await self.session.flush()
        self._llm_service.invalidate_reviewer_cache(reviewer_id)
        return True
