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

from fragrance_rater.core.exceptions import BusinessLogicError, ResourceNotFoundError
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

# Fixed scales for each outcome workflow (see PredictionSnapshot.predicted_scale's
# own comment): Evaluation.rating is always reported on a 1-5 scale and
# Observation.liking is always reported on a 0-10 scale (CheckConstraint-enforced
# in models/calibration.py). Neither table carries its own "scale" column, so the
# scale a linked outcome represents is this fixed, workflow-level constant.
_ORDINARY_OUTCOME_SCALE = "1-5"
_CONTROLLED_OUTCOME_SCALE = "0-10"


class PredictionConflictError(BusinessLogicError):
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
            raise ResourceNotFoundError(
                message, resource_type="Reviewer", resource_id=data.reviewer_id
            )
        fragrance = await self.db.get(Fragrance, data.fragrance_id)
        if fragrance is None or fragrance.deleted_at is not None:
            message = "fragrance not found"
            raise ResourceNotFoundError(
                message, resource_type="Fragrance", resource_id=data.fragrance_id
            )
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
                raise ResourceNotFoundError(
                    message,
                    resource_type="ModelCheckpoint",
                    resource_id=data.checkpoint_id,
                )
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
        """Append the one real outcome a frozen prediction is measured against.

        Idempotent for retries: if the prediction already has a linked
        outcome that matches ``data`` exactly, the existing link is returned
        as a no-op success rather than raising a conflict (see #CRITICAL note
        below on why a bare retry must not be treated as a genuine conflict).
        """
        prediction = await self.db.scalar(
            select(PredictionSnapshot)
            .where(PredictionSnapshot.id == prediction_id)
            # #CRITICAL: concurrency: without this row lock, two concurrent
            # link_outcome() calls for the same prediction_id could both
            # read outcome_linked_at as NULL, both pass the conflict check
            # below, and both write an outcome, violating the
            # one-outcome-per-prediction policy this method exists to
            # enforce.
            # #VERIFY: under SQLite, the dialect this repo's test fixtures
            # run against, SQLAlchemy's own SQLite dialect implements
            # `with_for_update()` as a documented no-op (SQLite has no
            # row-level locking), so the unit tests here cannot exercise the
            # race this lock guards against. The guarantee only holds
            # against PostgreSQL (production); verify it with an
            # integration test against a real Postgres instance, not the
            # SQLite unit fixtures.
            .with_for_update()
        )
        if prediction is None:
            message = "prediction not found"
            raise ResourceNotFoundError(
                message, resource_type="PredictionSnapshot", resource_id=prediction_id
            )
        if prediction.outcome_linked_at is not None:
            if (
                prediction.outcome_evaluation_id == data.outcome_evaluation_id
                and prediction.outcome_observation_id == data.outcome_observation_id
            ):
                # Idempotent retry: the caller already succeeded once (or a
                # response was dropped in transit) and is resubmitting the
                # exact same outcome link. Return the existing, unchanged
                # link rather than raising a conflict for a no-op retry.
                return prediction
            message = "prediction already has a linked outcome"
            raise PredictionConflictError(message)
        if data.outcome_evaluation_id:
            await self._validate_evaluation_outcome(
                prediction, data.outcome_evaluation_id
            )
        elif data.outcome_observation_id:
            await self._validate_observation_outcome(
                prediction, data.outcome_observation_id
            )
        else:
            # Reachable only if PredictionOutcomeInput's own model_validator
            # (require_exactly_one_outcome) were ever bypassed, e.g. by a
            # caller constructing/mutating the schema without validation.
            # An `assert` here would vanish under `python -O` and would
            # otherwise surface as an unhandled 500 instead of a clean
            # domain error.
            message = (
                "exactly one of outcome_evaluation_id or outcome_observation_id "
                "is required"
            )
            raise BusinessLogicError(message, rule="exactly_one_outcome_id")
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
            or prediction.predicted_scale != _ORDINARY_OUTCOME_SCALE
        ):
            message = (
                "ordinary outcome must be a live encounter for this reviewer and "
                "fragrance, recorded after the prediction was frozen, and the "
                f"prediction's predicted_scale must be {_ORDINARY_OUTCOME_SCALE!r} "
                "to match Evaluation.rating's scale"
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
        # Soft-deletion check, matching the pattern `create()` already uses for
        # reviewer/fragrance (`reviewer.deleted_at is not None` /
        # `fragrance.deleted_at is not None`): a controlled observation whose
        # membership/enrollment still points at a since-soft-deleted fragrance
        # or reviewer must not silently become a valid outcome link.
        reviewer = (
            await self.db.get(Reviewer, enrollment.reviewer_id)
            if enrollment is not None
            else None
        )
        fragrance = (
            await self.db.get(Fragrance, membership.fragrance_id)
            if membership is not None
            else None
        )
        if (
            row is None
            or observation is None
            or membership is None
            or enrollment is None
            or membership.fragrance_id != prediction.fragrance_id
            or enrollment.reviewer_id != prediction.reviewer_id
            or observation.created_at < prediction.created_at
            or reviewer is None
            or reviewer.deleted_at is not None
            or fragrance is None
            or fragrance.deleted_at is not None
            or prediction.predicted_scale != _CONTROLLED_OUTCOME_SCALE
        ):
            message = (
                "controlled outcome must belong to this reviewer and fragrance, "
                "recorded after the prediction was frozen, involve an active "
                "(non-deleted) reviewer and fragrance, and the prediction's "
                f"predicted_scale must be {_CONTROLLED_OUTCOME_SCALE!r} to match "
                "Observation.liking's scale"
            )
            raise PredictionConflictError(message)

    async def list_for_reviewer(self, reviewer_id: str) -> list[PredictionSnapshot]:
        """Return every prediction snapshot for one evaluator, newest first."""
        return list(
            await self.db.scalars(
                select(PredictionSnapshot)
                .where(PredictionSnapshot.reviewer_id == reviewer_id)
                # `.id.desc()` tiebreaks rows sharing the same `created_at`
                # (e.g. two snapshots created within the same timestamp
                # tick), matching this repo's own ordering convention in
                # preference_history.py's `_ordinary()`.
                .order_by(
                    PredictionSnapshot.created_at.desc(), PredictionSnapshot.id.desc()
                )
            )
        )

    @staticmethod
    def _naive_utc(value: datetime) -> datetime:
        """Normalize a possibly tz-aware timestamp for naive-UTC comparison."""
        # #EDGE: timing-dependencies: assumes a naive `value` is already
        # expressed in UTC. A tz-aware timestamp converts correctly via
        # `astimezone()` regardless of its source offset, but a naive
        # timestamp recorded in local/non-UTC time would silently compare
        # against the wrong instant with no error raised here.
        # #VERIFY: confirm every caller's timestamp column is populated via
        # `now_naive_utc()` or another UTC-sourced value (e.g.
        # `Evaluation.evaluated_at`, `Observation.created_at`) so naive
        # inputs reaching this method are never actually non-UTC.
        if value.tzinfo is None:
            return value
        # datetime.UTC is unavailable on the supported Python 3.10 floor.
        return value.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017
