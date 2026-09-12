"""Freeze model predictions and link them to real outcomes after the fact.

Supports refining recommendation/liking projections: a candidate model
predicts a rating before the real encounter exists (``create``), and once
that encounter happens, exactly one outcome is linked to the prediction
(``link_outcome``) so prediction error is measurable without ever
recomputing the frozen prediction itself (ADR-009).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    ModelCheckpoint,
    Observation,
    Presentation,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.prediction import (
        PredictionCreate,
        PredictionOutcomeInput,
    )


class PredictionConflictError(ValueError):
    """The requested outcome link would violate the one-outcome-per-prediction policy."""


class PredictionService:
    """Create immutable prediction snapshots and append a one-time outcome link."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, data: PredictionCreate, *, recorded_by: str | None
    ) -> PredictionSnapshot:
        """Freeze a predicted rating for one evaluator/fragrance pair."""
        reviewer = await self.db.get(Reviewer, data.reviewer_id)
        if reviewer is None or reviewer.deleted_at is not None:
            message = "reviewer not found"
            raise LookupError(message)
        fragrance = await self.db.get(Fragrance, data.fragrance_id)
        if fragrance is None or fragrance.deleted_at is not None:
            message = "fragrance not found"
            raise LookupError(message)
        if data.checkpoint_id is not None:
            # Join through Enrollment rather than a plain existence check so a
            # checkpoint frozen for a *different* reviewer's calibration
            # program can't be attached, which would make the snapshot's own
            # provenance internally inconsistent (predicting for reviewer A
            # while citing reviewer B's frozen inputs).
            checkpoint_reviewer_id = await self.db.scalar(
                select(Enrollment.reviewer_id)
                .join(ModelCheckpoint, ModelCheckpoint.enrollment_id == Enrollment.id)
                .where(ModelCheckpoint.id == data.checkpoint_id)
            )
            if checkpoint_reviewer_id is None:
                message = "checkpoint not found"
                raise LookupError(message)
            if checkpoint_reviewer_id != data.reviewer_id:
                message = (
                    "checkpoint belongs to a different reviewer than this prediction"
                )
                raise PredictionConflictError(message)
        snapshot = PredictionSnapshot(recorded_by=recorded_by, **data.model_dump())
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def link_outcome(
        self,
        prediction_id: str,
        data: PredictionOutcomeInput,
        *,
        recorded_by: str | None,
    ) -> PredictionSnapshot:
        """Append the one real outcome a frozen prediction is measured against."""
        prediction = await self.db.scalar(
            select(PredictionSnapshot)
            .where(PredictionSnapshot.id == prediction_id)
            .with_for_update()
        )
        if prediction is None:
            message = "prediction not found"
            raise LookupError(message)
        if prediction.outcome_linked_at is not None:
            message = "prediction already has a linked outcome"
            raise PredictionConflictError(message)
        if data.outcome_evaluation_id:
            await self._validate_evaluation_outcome(
                prediction, data.outcome_evaluation_id
            )
        else:
            assert data.outcome_observation_id is not None
            await self._validate_observation_outcome(
                prediction, data.outcome_observation_id
            )
        prediction.outcome_evaluation_id = data.outcome_evaluation_id
        prediction.outcome_observation_id = data.outcome_observation_id
        prediction.outcome_linked_at = now_naive_utc()
        prediction.outcome_recorded_by = recorded_by
        await self.db.flush()
        return prediction

    async def _validate_evaluation_outcome(
        self, prediction: PredictionSnapshot, evaluation_id: str
    ) -> None:
        """Reject an ordinary outcome that cannot honestly test this prediction."""
        evaluation = await self.db.get(Evaluation, evaluation_id)
        if (
            evaluation is None
            or evaluation.deleted_at is not None
            or evaluation.reviewer_id != prediction.reviewer_id
            or evaluation.fragrance_id != prediction.fragrance_id
            or self._naive_utc(evaluation.evaluated_at) < prediction.created_at
        ):
            message = (
                "ordinary outcome must be a live encounter for this reviewer and "
                "fragrance, recorded after the prediction was frozen"
            )
            raise PredictionConflictError(message)

    async def _validate_observation_outcome(
        self, prediction: PredictionSnapshot, observation_id: str
    ) -> None:
        """Reject a controlled outcome that cannot honestly test this prediction."""
        row = (
            await self.db.execute(
                select(Observation, Membership, Enrollment)
                .join(Presentation, Presentation.id == Observation.presentation_id)
                .join(Membership, Membership.id == Presentation.membership_id)
                .join(
                    CalibrationSession,
                    CalibrationSession.id == Presentation.session_id,
                )
                .join(Enrollment, Enrollment.id == CalibrationSession.enrollment_id)
                .where(Observation.id == observation_id)
            )
        ).one_or_none()
        observation = row[0] if row else None
        membership = row[1] if row else None
        enrollment = row[2] if row else None
        if (
            row is None
            or observation is None
            or membership is None
            or enrollment is None
            or membership.fragrance_id != prediction.fragrance_id
            or enrollment.reviewer_id != prediction.reviewer_id
            or observation.created_at < prediction.created_at
        ):
            message = (
                "controlled outcome must belong to this reviewer and fragrance, "
                "recorded after the prediction was frozen"
            )
            raise PredictionConflictError(message)

    async def list_for_reviewer(self, reviewer_id: str) -> list[PredictionSnapshot]:
        """Return every prediction snapshot for one evaluator, newest first."""
        return list(
            await self.db.scalars(
                select(PredictionSnapshot)
                .where(PredictionSnapshot.reviewer_id == reviewer_id)
                .order_by(PredictionSnapshot.created_at.desc())
            )
        )

    @staticmethod
    def _naive_utc(value: datetime) -> datetime:
        """Normalize a possibly tz-aware timestamp for naive-UTC comparison."""
        if value.tzinfo is None:
            return value
        # datetime.UTC is unavailable on the supported Python 3.10 floor.
        return value.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017
