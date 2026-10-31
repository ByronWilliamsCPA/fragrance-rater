"""Prediction snapshot endpoints for ML testing against real outcomes.

Manager-gated, like the calibration checkpoint routes this complements:
predictions are an experimental/data-science surface, not a participant
workflow, so access follows the same ``CALIBRATION_ADMIN_USERNAMES`` policy
as ``/calibration/enrollments/{id}/checkpoints``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import VerifiedIdentity, manager
from fragrance_rater.core.database import get_db
from fragrance_rater.core.exceptions import BusinessLogicError, ResourceNotFoundError
from fragrance_rater.schemas.prediction import (
    PredictionCreate,
    PredictionOutcomeInput,
    PredictionView,
)
from fragrance_rater.services.prediction_service import PredictionService
from fragrance_rater.utils.logging import get_logger, log_audit_event

router = APIRouter(prefix="/predictions", tags=["predictions"])
logger = get_logger(__name__)
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Identity = VerifiedIdentity


@router.post(
    "",
    response_model=PredictionView,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Reviewer, fragrance, or checkpoint not found"},
        409: {"description": "Checkpoint belongs to a different reviewer"},
    },
)
async def create_prediction(
    data: PredictionCreate, db: DB, identity: Identity
) -> PredictionView:
    """Freeze a model's predicted rating before the real outcome is known."""
    username = manager(identity)
    try:
        snapshot = await PredictionService(db).create(data, recorded_by=username)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessLogicError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # B-03. The fragrance is left out: a prediction may target a holdout.
    log_audit_event(
        logger,
        action="prediction_create",
        actor=username,
        target_type="prediction",
        target_id=snapshot.id,
        reviewer_id=snapshot.reviewer_id,
        checkpoint_id=snapshot.checkpoint_id,
    )
    return PredictionView.model_validate(snapshot, from_attributes=True)


@router.post(
    "/{prediction_id}/outcome",
    response_model=PredictionView,
    responses={
        404: {"description": "Prediction not found"},
        409: {
            "description": (
                "Prediction already has a different linked outcome, or the "
                "supplied outcome cannot honestly test this prediction "
                "(wrong reviewer/fragrance, recorded before the prediction, "
                "a soft-deleted reviewer/fragrance, or a predicted_scale "
                "mismatched to the outcome's scale). Retrying with the same "
                "outcome id(s) already linked is a no-op success, not a "
                "conflict."
            )
        },
    },
)
async def link_outcome(
    prediction_id: str, data: PredictionOutcomeInput, db: DB, identity: Identity
) -> PredictionView:
    """Append the one real outcome a frozen prediction is measured against."""
    username = manager(identity)
    try:
        snapshot = await PredictionService(db).link_outcome(
            prediction_id, data, recorded_by=username
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessLogicError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    log_audit_event(
        logger,
        action="prediction_link_outcome",
        actor=username,
        target_type="prediction",
        target_id=snapshot.id,
        reviewer_id=snapshot.reviewer_id,
        outcome_evaluation_id=snapshot.outcome_evaluation_id,
        outcome_observation_id=snapshot.outcome_observation_id,
    )
    return PredictionView.model_validate(snapshot, from_attributes=True)


@router.get("", response_model=list[PredictionView])
async def list_predictions(
    db: DB,
    identity: Identity,
    reviewer_id: Annotated[str, Query()],
) -> list[PredictionView]:
    """List every prediction snapshot for one evaluator, newest first."""
    manager(identity)
    return [
        PredictionView.model_validate(item, from_attributes=True)
        for item in await PredictionService(db).list_for_reviewer(reviewer_id)
    ]
