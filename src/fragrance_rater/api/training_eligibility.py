"""Manager-only training-eligibility decisions and linkage (R8 PR 2).

Option C promotes evidence automatically at write time
(``services/training_eligibility.py``); these routes are the manager's
explicit decisions on top of it, and the one read path for the role and
repeat linkage that ``v_training_rows`` deliberately omits (X-06). Every route
answers 401 without a named caller and 403 for anyone but a configured
calibration manager.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import VerifiedIdentity, actor, manager
from fragrance_rater.core.database import get_db
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.training_eligibility import (
    ManagerDecision,
    TrainingEligibilityService,
    manager_linkage,
)
from fragrance_rater.utils.logging import get_logger, log_audit_event

router = APIRouter(tags=["training-eligibility"])
logger = get_logger(__name__)

DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Identity = VerifiedIdentity
TargetType = Literal["evaluation", "observation"]


class EligibilityDecision(BaseModel):
    """A manager's decision on one evidence row."""

    model_config = ConfigDict(extra="forbid")

    training_eligibility: ManagerDecision
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_is_not_blank(cls, value: str) -> str:
        """A blank reason is no reason."""
        if not value.strip():
            message = "A reason is required"
            raise ValueError(message)
        return value.strip()


@router.put("/training-eligibility/{target_type}/{target_id}")
async def decide(
    target_type: TargetType,
    target_id: str,
    data: EligibilityDecision,
    db: DB,
    identity: Identity,
) -> dict[str, str]:
    """Set one evidence row to ``eligible``, ``withheld``, or ``invalidated``.

    Manager only. The decision and its reason are an audit event
    (``training_eligibility_set``, cause ``manager_decision``).

    Args:
        target_type (TargetType): ``evaluation`` or ``observation``.
        target_id (str): The row id.
        data (EligibilityDecision): The code and the reason.
        db (DB): Database session.
        identity (Identity): The verified caller.

    Returns:
        dict[str, str]: The row, its previous code, and its code now.

    Raises:
        HTTPException: 404 when the row does not exist.
    """
    username = manager(identity)
    try:
        change = await TrainingEligibilityService(db).set_by_manager(
            target_type,
            target_id,
            data.training_eligibility,
            reason=data.reason,
            actor=username,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=f"{target_type} not found") from (
            error
        )
    return {
        "target_type": target_type,
        "target_id": target_id,
        "previous": change.previous,
        "training_eligibility": change.current,
    }


@router.get("/calibration/enrollments/{enrollment_id}/linkage")
async def linkage(
    enrollment_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """Role and hidden-repeat linkage per observation; manager only.

    Each row carries the same ``row_id`` as ``v_training_rows``, so a manager
    can tell which trained row came from which membership. Every retrieval is
    an audit event, like the blind mapping's (B-03).

    Args:
        enrollment_id (str): The enrollment.
        db (DB): Database session.
        identity (Identity): The verified caller.

    Returns:
        list[dict[str, object]]: One row per observation.
    """
    username = manager(identity)
    await CalibrationService(db).enrollment(enrollment_id, *actor(identity))
    log_audit_event(
        logger,
        action="linkage_retrieve",
        actor=username,
        target_type="enrollment",
        target_id=enrollment_id,
    )
    return await manager_linkage(db, enrollment_id)
