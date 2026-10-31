"""Ranking and quality-flag endpoints for the participant instrument (R7b)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import VerifiedIdentity, actor, manager
from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.capture import QualityFlagInput, RankingInput
from fragrance_rater.services.capture_service import CaptureService
from fragrance_rater.services.evidence_export import build_evidence_export
from fragrance_rater.utils.logging import get_logger, log_audit_event

router = APIRouter(prefix="/calibration", tags=["calibration"])
logger = get_logger(__name__)

DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Identity = VerifiedIdentity


@router.post("/sessions/{session_id}/rankings", status_code=201)
async def record_ranking(
    session_id: str, data: RankingInput, db: DB, identity: Identity
) -> dict[str, object]:
    """Append one ranking event over the session's detected samples."""
    username, admin = actor(identity)
    event, eligible = await CaptureService(db).record_ranking(
        session_id, data, username, admin
    )
    log_audit_event(
        logger,
        action="ranking_record",
        actor=username,
        target_type="rank_event",
        target_id=event.id,
        session_id=session_id,
        stage=event.stage,
        phase=event.phase,
        response_status=event.response_status,
    )
    return {"id": event.id, "phase": event.phase, "eligible": eligible}


@router.get("/sessions/{session_id}/rankings")
async def list_rankings(
    session_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """List a session's ranking events; manager or assigned recorder only."""
    return await CaptureService(db).rankings(session_id, *actor(identity))


@router.post("/quality-flags", status_code=201)
async def record_flag(
    data: QualityFlagInput, db: DB, identity: Identity
) -> dict[str, object]:
    """Raise a quality flag, or close one with a later resolved or invalidated row."""
    username, admin = actor(identity)
    flag, changes = await CaptureService(db).record_flag_with_eligibility(
        data, username, admin
    )
    log_audit_event(
        logger,
        action=f"quality_flag_{flag.action}",
        actor=username,
        target_type="quality_flag",
        target_id=flag.id,
        code=flag.code,
        severity=flag.severity,
        source=flag.source,
        supersedes_id=flag.supersedes_id,
        training_outcome=data.training_outcome,
        training_eligibility_changes=len(changes),
    )
    return {"id": flag.id, "training_eligibility_changes": len(changes)}


@router.get("/sessions/{session_id}/quality-flags")
async def list_flags(
    session_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """List every flag on a session and its samples; assigned people only."""
    return await CaptureService(db).flags(session_id, *actor(identity))


@router.get("/enrollments/{enrollment_id}/evidence-export")
async def evidence_export(
    enrollment_id: str, db: DB, identity: Identity
) -> dict[str, object]:
    """Export every captured field for one enrollment; manager only."""
    username = manager(identity)
    document = await build_evidence_export(db, enrollment_id, username)
    log_audit_event(
        logger,
        action="evidence_export",
        actor=username,
        target_type="enrollment",
        target_id=enrollment_id,
    )
    return document
