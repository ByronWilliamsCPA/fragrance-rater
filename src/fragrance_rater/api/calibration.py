"""Calibration endpoints with separate manager and recorder authorization."""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import AuthenticatedIdentity, get_current_identity
from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    FragellaLookup,
    Membership,
    ModelCheckpoint,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import (
    CheckpointInput,
    EnrollmentInput,
    MembershipInput,
    ProgramInput,
    ResponseInput,
    SkinPlanInput,
    Stage,
)
from fragrance_rater.services.calibration_service import CalibrationService, reject
from fragrance_rater.services.evaluation_service import EvaluationService
from fragrance_rater.services.fragella_client import FragellaClient
from fragrance_rater.services.fragella_lookup_service import FragellaLookupService
from fragrance_rater.services.preference_history import PreferenceHistoryService
from fragrance_rater.utils.timestamps import now_naive_utc

router = APIRouter(prefix="/calibration", tags=["calibration"])
DB = Annotated[AsyncSession, Depends(get_db)]
Identity = Annotated[AuthenticatedIdentity, Depends(get_current_identity)]


def actor(identity: AuthenticatedIdentity) -> tuple[str, bool]:
    """Fail closed without a named recorder, including local development."""
    if not identity.username:
        raise HTTPException(status_code=401, detail="A named recorder is required")
    return identity.username, identity.username in settings.calibration_admin_usernames


def manager(identity: AuthenticatedIdentity) -> str:
    """Require an explicit configured manager for experiment mappings."""
    username, admin = actor(identity)
    if not admin:
        raise HTTPException(status_code=403, detail="Calibration manager required")
    return username


@router.get("/access")
async def access(identity: Identity) -> dict[str, object]:
    """Expose capabilities without hidden experiment data."""
    username, admin = actor(identity)
    return {"username": username, "manager": admin}


@router.get("/programs")
async def programs(db: DB, identity: Identity) -> list[dict[str, object]]:
    """List protocol descriptions without membership or blind mappings."""
    username, admin = actor(identity)
    result = list(await db.scalars(select(Program)))
    allowed: set[str] = set()
    if not admin:
        allowed = {
            e.program_id
            for e in await db.scalars(select(Enrollment))
            if username in e.recorder_usernames
        }
    return [
        {"id": p.id, "name": p.name, "version": p.version, "status": p.status}
        for p in result
        if admin or p.id in allowed
    ]


@router.post("/programs", status_code=201)
async def create_program(
    data: ProgramInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Create a draft without hard-coded baseline size."""
    manager(identity)
    if await db.scalar(
        select(Program.id).where(
            Program.name == data.name, Program.version == data.version
        )
    ):
        reject("Program version already exists")
    obj = Program(**data.model_dump())
    db.add(obj)
    await db.flush()
    return {"id": obj.id}


@router.post("/programs/{program_id}/members", status_code=201)
async def add_member(
    program_id: str, data: MembershipInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Add a canonical version with experimental role."""
    manager(identity)
    obj = await CalibrationService(db).add_member(program_id, data)
    return {"id": obj.id}


def _serialize_fragella_lookup(
    lookup: FragellaLookup | None,
) -> dict[str, object] | None:
    """Build the manager-facing summary of a fragella_lookups row.

    Args:
        lookup (FragellaLookup | None): The row to serialize, or None.

    Returns:
        dict[str, object] | None: None when `lookup` is None (never
            checked yet), so the frontend can distinguish "not checked"
            from "checked, found nothing."
    """
    if lookup is None:
        return None
    return {
        "checked_at": lookup.queried_at.isoformat(),
        "query": lookup.query,
        "status": lookup.status,
        "error_message": lookup.error_message,
        "results": lookup.results,
    }


@router.get("/programs/{program_id}/members")
async def members(
    program_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """Return setup references only to managers."""
    manager(identity)
    items = list(
        await db.scalars(
            select(Membership)
            .where(Membership.program_id == program_id)
            .order_by(Membership.group_name, Membership.id)
        )
    )
    latest_fragella = await FragellaLookupService(db).latest_by_fragrance(
        [item.fragrance_id for item in items]
    )
    result: list[dict[str, object]] = []
    for item in items:
        fragrance = await db.get(Fragrance, item.fragrance_id)
        assert fragrance is not None
        result.append(
            {
                "id": item.id,
                "fragrance_id": item.fragrance_id,
                "fragrance_name": fragrance.name,
                "fragrance_brand": fragrance.brand,
                "concentration": fragrance.concentration,
                "version_key": fragrance.version_key,
                "role": item.role,
                "repeat_of_id": item.repeat_of_id,
                "group_name": item.group_name,
                "identity_evidence": item.selection.get("identity_evidence"),
                "fragella": _serialize_fragella_lookup(
                    latest_fragella.get(item.fragrance_id)
                ),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            str(row["group_name"]),
            str(row["fragrance_brand"]),
            str(row["fragrance_name"]),
        ),
    )


@router.post("/programs/{program_id}/members/{membership_id}/fragella-lookup")
async def fragella_lookup(
    program_id: str,
    membership_id: str,
    db: DB,
    identity: Identity,
    query: str | None = None,
) -> dict[str, object]:
    """Run (or re-run) a Fragella reference lookup for one membership.

    Manual and manager-only: the account's 20-request/month quota is
    spent only when a manager deliberately asks, never automatically.
    Records the attempt (success or error) so the manager view can show
    which fragrances still have not been checked without spending
    another request to find out. Never writes into `Fragrance` fields
    or membership evidence - see ADR-002's 2026-09-13 amendment.
    """
    manager_name = manager(identity)
    member = await db.get(Membership, membership_id)
    if member is None or member.program_id != program_id:
        reject("Membership not found", 404)
    assert member is not None
    fragrance = await db.get(Fragrance, member.fragrance_id)
    if fragrance is None:
        reject("Catalog version not found", 404)
    assert fragrance is not None
    lookup = await FragellaLookupService(db).run_lookup(
        fragrance, manager_name, query=query
    )
    result = _serialize_fragella_lookup(lookup)
    assert result is not None
    return result


@router.get("/fragella/usage")
async def fragella_usage(identity: Identity) -> dict[str, object]:
    """Report the Fragella account's remaining monthly quota.

    Manager-only; fetched on demand from the manager UI rather than
    automatically before every lookup, since whether checking usage
    itself counts against the same quota is undocumented (see
    fragella_client.py's module docstring).
    """
    manager(identity)
    usage = await FragellaClient().usage()
    if usage is None:
        reject("Could not retrieve Fragella usage", 502)
    return usage


@router.post("/programs/{program_id}/activate")
async def activate(program_id: str, db: DB, identity: Identity) -> dict[str, bool]:
    """Freeze a nonempty definition before assigning evaluators."""
    manager(identity)
    obj = await CalibrationService(db).program(program_id)
    if obj.status != "draft":
        reject("Program is already locked")
    if not await db.scalar(
        select(Membership.id).where(Membership.program_id == program_id)
    ):
        reject("Add stimuli before activation")
    obj.status, obj.locked_at = "active", now_naive_utc()
    await db.flush()
    return {"locked": True}


@router.post("/programs/{program_id}/enroll", status_code=201)
async def enroll(
    program_id: str, data: EnrollmentInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Assign and randomize the program for one shared reviewer."""
    manager(identity)
    obj = await CalibrationService(db).enroll(program_id, data)
    return {"id": obj.id}


@router.get("/enrollments")
async def enrollments(db: DB, identity: Identity) -> list[dict[str, str]]:
    """List only evaluator assignments the recorder can access."""
    username, admin = actor(identity)
    return [
        {"id": e.id, "program_id": e.program_id, "reviewer_id": e.reviewer_id}
        for e in await db.scalars(select(Enrollment))
        if admin or username in e.recorder_usernames
    ]


@router.get("/manager/enrollments")
async def manager_enrollments(db: DB, identity: Identity) -> list[dict[str, object]]:
    """Summarize evaluator progress and reveal readiness for pilot operations."""
    manager(identity)
    service = CalibrationService(db)
    result: list[dict[str, object]] = []
    for item in await db.scalars(select(Enrollment).order_by(Enrollment.id)):
        program = await db.get(Program, item.program_id)
        reviewer = await db.get(Reviewer, item.reviewer_id)
        assert program is not None
        assert reviewer is not None
        presentations = await service.presentations(item.id)
        members = {
            member.id: member
            for member in await db.scalars(
                select(Membership).where(
                    Membership.id.in_({p.membership_id for p in presentations})
                )
            )
        }
        blotter_complete = sum(p.blotter_locked_at is not None for p in presentations)
        skin_planned = [p for p in presentations if p.skin_reason is not None]
        skin_complete = sum(p.skin_locked_at is not None for p in skin_planned)
        blocker = service.reveal_blocker(item, presentations, members)
        result.append(
            {
                "id": item.id,
                "program_name": program.name,
                "program_version": program.version,
                "reviewer_name": reviewer.name,
                "recorder_usernames": item.recorder_usernames,
                "total_presentations": len(presentations),
                "blotter_complete": blotter_complete,
                "skin_planned": len(skin_planned),
                "skin_complete": skin_complete,
                "reveal_eligible": blocker is None,
                "reveal_blocker": blocker,
                "revealed": item.revealed_at is not None,
            }
        )
    return sorted(
        result,
        key=lambda row: (str(row["program_name"]), str(row["reviewer_name"])),
    )


@router.get("/enrollments/{enrollment_id}")
async def enrollment(
    enrollment_id: str, db: DB, identity: Identity
) -> dict[str, object]:
    """Return the allowlisted blind session history."""
    service = CalibrationService(db)
    obj = await service.enrollment(enrollment_id, *actor(identity))
    return await service.participant_view(obj)


@router.post("/presentations/{presentation_id}/observations", status_code=201)
async def observe(
    presentation_id: str, data: ResponseInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Append a blind timepoint."""
    obj = await CalibrationService(db).observe(presentation_id, data, *actor(identity))
    return {"id": obj.id}


@router.post("/presentations/{presentation_id}/post-reveal", status_code=201)
async def post_reveal(
    presentation_id: str, data: ResponseInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Append an informed observation without changing blind responses."""
    obj = await CalibrationService(db).observe(
        presentation_id, data, *actor(identity), post_reveal=True
    )
    return {"id": obj.id}


@router.post("/presentations/{presentation_id}/lock/{stage}")
async def lock_stage(
    presentation_id: str, stage: Stage, db: DB, identity: Identity
) -> dict[str, bool]:
    """Lock the submitted stage."""
    await CalibrationService(db).lock_stage(presentation_id, stage, *actor(identity))
    return {"locked": True}


@router.post("/presentations/{presentation_id}/skin-plan")
async def skin_plan(
    presentation_id: str, data: SkinPlanInput, db: DB, identity: Identity
) -> dict[str, bool]:
    """Select a skin test before finalizing the plan."""
    obj, enrollment = await CalibrationService(db).target(
        presentation_id, *actor(identity)
    )
    if enrollment.skin_plan_locked_at or enrollment.revealed_at:
        reject("Skin plan is finalized")
    obj.skin_reason = data.reason
    await db.flush()
    return {"planned": True}


@router.post("/enrollments/{enrollment_id}/lock-skin-plan")
async def lock_skin_plan(
    enrollment_id: str, db: DB, identity: Identity
) -> dict[str, bool]:
    """Explicitly finalize the skin plan, including an intentionally empty plan."""
    obj = await CalibrationService(db).enrollment(enrollment_id, *actor(identity))
    obj.skin_plan_locked_at = obj.skin_plan_locked_at or now_naive_utc()
    await db.flush()
    return {"locked": True}


@router.post("/enrollments/{enrollment_id}/reveal")
async def reveal(enrollment_id: str, db: DB, identity: Identity) -> dict[str, bool]:
    """Apply the delayed-reveal policy on the server."""
    await CalibrationService(db).reveal(enrollment_id, *actor(identity))
    return {"revealed": True}


@router.post("/enrollments/{enrollment_id}/checkpoints", status_code=201)
async def checkpoint(
    enrollment_id: str, data: CheckpointInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Snapshot model inputs and predictions before holdout outcomes exist."""
    manager(identity)
    service = CalibrationService(db)
    obj = await service.enrollment(enrollment_id, *actor(identity))
    # A checkpoint after any holdout response is no longer prospective.
    seen = await db.scalar(
        select(Observation.id)
        .join(Presentation)
        .join(Membership)
        .join(CalibrationSession, Presentation.session_id == CalibrationSession.id)
        .where(CalibrationSession.enrollment_id == obj.id, Membership.role == "HOLDOUT")
    )
    if seen:
        reject("Holdout observations already exist; prospective checkpoint closed")
    manifest = await PreferenceHistoryService(db).training_manifest(obj.reviewer_id)
    run = ModelCheckpoint(
        enrollment_id=obj.id,
        algorithm_version=data.algorithm_version,
        manifest=manifest,
        predictions=data.predictions,
    )
    db.add(run)
    await db.flush()
    return {"id": run.id}


@router.get("/enrollments/{enrollment_id}/mapping")
async def mapping(
    enrollment_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """Manager-only decant labeling sheet; never part of participant payloads."""
    manager(identity)
    service = CalibrationService(db)
    await service.enrollment(enrollment_id, *actor(identity))
    result: list[dict[str, object]] = []
    for obj in await service.presentations(enrollment_id):
        member = await db.get(Membership, obj.membership_id)
        assert member is not None
        fragrance = await db.get(Fragrance, member.fragrance_id)
        assert fragrance is not None
        result.append(
            {
                "session_id": obj.session_id,
                "position": obj.position,
                "blind_code": obj.blind_code,
                "fragrance_id": member.fragrance_id,
                "fragrance_name": fragrance.name,
                "fragrance_brand": fragrance.brand,
                "concentration": fragrance.concentration,
                "version_key": fragrance.version_key,
                "membership_id": member.id,
                "role": member.role,
            }
        )
    return result


@router.get("/enrollments/{enrollment_id}/checkpoints")
async def checkpoints(
    enrollment_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """Retrieve frozen inputs and predictions for manager-side analysis."""
    manager(identity)
    await CalibrationService(db).enrollment(enrollment_id, *actor(identity))
    return [
        {
            "id": r.id,
            "algorithm_version": r.algorithm_version,
            "created_at": r.created_at.isoformat(),
            "manifest": r.manifest,
            "predictions": r.predictions,
        }
        for r in await db.scalars(
            select(ModelCheckpoint).where(
                ModelCheckpoint.enrollment_id == enrollment_id
            )
        )
    ]


@router.get("/history/{reviewer_id}")
async def history(
    reviewer_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """Unified history; conceal controlled identities according to reveal state."""
    username, admin = actor(identity)
    assigned = list(
        await db.scalars(
            select(Enrollment).where(Enrollment.reviewer_id == reviewer_id)
        )
    )
    if not admin and not any(username in e.recorder_usernames for e in assigned):
        reject("Recorder is not assigned to this evaluator", 403)
    ordinary = await EvaluationService(db).get_by_reviewer(reviewer_id)
    result: list[dict[str, object]] = [
        {
            "id": e.id,
            "workflow": "ORDINARY",
            "scale": "1-5",
            "fragrance_id": e.fragrance_id,
            "rating": e.rating,
            "notes": e.notes,
            "observed_at": e.evaluated_at.isoformat(),
        }
        for e in ordinary
    ]
    service = CalibrationService(db)
    for enrollment in assigned:
        if not admin and username not in enrollment.recorder_usernames:
            continue
        # Participant view remains the single source of identity-disclosure policy.
        view = await service.participant_view(enrollment)
        presentations = view["presentations"]
        assert isinstance(presentations, list)
        for presentation in cast("list[dict[str, Any]]", presentations):
            observations = cast("list[dict[str, Any]]", presentation["observations"])
            result.extend(
                {
                    **observation,
                    "workflow": "CONTROLLED",
                    "scale": "0-10",
                    "program_id": enrollment.program_id,
                    "blind_code": presentation["blind_code"],
                    "identity": presentation.get("identity"),
                }
                for observation in observations
            )
    return result
