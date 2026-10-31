"""Calibration endpoints with separate manager and recorder authorization."""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import (
    VerifiedIdentity,
    actor,
    authorize_reviewer,
    manager,
)
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
    ExposureInput,
    MembershipInput,
    ProgramInput,
    ResponseInput,
    SessionEndInput,
    SessionStartInput,
    SkinPlanInput,
    Stage,
)
from fragrance_rater.schemas.consent import ConsentEventInput, SessionContextInput
from fragrance_rater.services.calibration_service import (
    CalibrationService,
    activation_instrument_version,
    reject,
)
from fragrance_rater.services.checkpoint_service import CheckpointService
from fragrance_rater.services.consent import ConsentService, load_consent_text
from fragrance_rater.services.evaluation_service import EvaluationService
from fragrance_rater.services.fragella_client import FragellaClient, FragellaError
from fragrance_rater.services.fragella_lookup_service import FragellaLookupService
from fragrance_rater.utils.logging import get_logger, log_audit_event
from fragrance_rater.utils.timestamps import now_naive_utc

router = APIRouter(prefix="/calibration", tags=["calibration"])
logger = get_logger(__name__)
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Identity = VerifiedIdentity


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
    query: Annotated[str | None, Query(max_length=500)] = None,
) -> dict[str, object]:
    """Run (or re-run) a Fragella reference lookup for one membership.

    Manual and manager-only: the account's 20-request/month quota is
    spent only when a manager deliberately asks, never automatically.
    Records the attempt (success or error) so the manager view can show
    which fragrances still have not been checked without spending
    another request to find out. Never writes into `Fragrance` fields
    or membership evidence - see ADR-002's 2026-09-13 amendment.
    """
    # #ASSUME: data-integrity: `query` is a raw query-string parameter,
    # not a Pydantic-validated body field; `max_length` above rejects an
    # overlong value with a clean 400 before it can spend a Fragella
    # request and then fail at flush() against FragellaLookup.query's
    # String(500) column. A NUL byte is separately rejected here since
    # it is valid in a Python str but not in a Postgres text column,
    # which would otherwise surface as an unhandled 500 at flush() too.
    if query is not None and "\x00" in query:
        reject("query must not contain a NUL byte", 400)
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
    try:
        usage = await FragellaClient().usage()
    except FragellaError:
        usage = None
    if usage is None:
        reject("Could not retrieve Fragella usage", 502)
    return usage


@router.post("/programs/{program_id}/activate")
async def activate(program_id: str, db: DB, identity: Identity) -> dict[str, bool]:
    """Freeze a nonempty definition before assigning evaluators."""
    username = manager(identity)
    obj = await CalibrationService(db).program(program_id)
    if obj.status != "draft":
        reject("Program is already locked")
    if not await db.scalar(
        select(Membership.id).where(Membership.program_id == program_id)
    ):
        reject("Add stimuli before activation")
    obj.status, obj.locked_at = "active", now_naive_utc()
    # Capture assessment 13.2: freeze which instrument the program runs under.
    obj.instrument_version = activation_instrument_version(settings.instrument_version)
    await db.flush()
    log_audit_event(
        logger,
        action="program_activate",
        actor=username,
        target_type="calibration_program",
        target_id=program_id,
        instrument_version=obj.instrument_version,
    )
    return {"locked": True}


@router.post("/programs/{program_id}/enroll", status_code=201)
async def enroll(
    program_id: str, data: EnrollmentInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Assign and randomize the program for one shared reviewer."""
    username = manager(identity)
    obj = await CalibrationService(db).enroll(program_id, data)
    log_audit_event(
        logger,
        action="enroll",
        actor=username,
        target_type="enrollment",
        target_id=obj.id,
        program_id=program_id,
        reviewer_id=obj.reviewer_id,
        recorder_usernames=list(obj.recorder_usernames or []),
    )
    return {"id": obj.id}


@router.get("/enrollments")
async def enrollments(db: DB, identity: Identity) -> list[dict[str, object]]:
    """List evaluator assignments the recorder can access, enriched for routing.

    Enriches the same participant-safe fields manager_enrollments already
    computes for the pilot-operations console (see that handler below), plus
    one new signal: has_started. Same permission filter as before.
    """
    # #EDGE: External Resources: this issues 3 unbatched queries per row
    # (program, presentations, has_started) with no pagination, mirroring
    # manager_enrollments' existing per-row pattern below rather than a new
    # regression. Runs on every app load for every identity now, not just the
    # manager console, but at this app's scale (a handful of family
    # reviewers) the per-row cost stays negligible; batch-fetching would be
    # worth doing if either handler's row count grows materially.
    username, admin = actor(identity)
    service = CalibrationService(db)
    result: list[dict[str, object]] = []
    for item in await db.scalars(select(Enrollment).order_by(Enrollment.id)):
        if not (admin or username in item.recorder_usernames):
            continue
        program = await db.get(Program, item.program_id)
        # #EDGE: Data Integrity: an enrollment whose program row is gone
        # (deleted after enrollment) must not 500 this list for every other
        # row; skip only the malformed one rather than asserting.
        # #VERIFY: no known path deletes a Program with live enrollments, but
        # this endpoint runs on every app load, so a stray orphan can't be
        # allowed to take the whole response down.
        if program is None:
            continue
        presentations = await service.presentations(item.id)
        skin_planned = [p for p in presentations if p.skin_reason is not None]
        result.append(
            {
                "id": item.id,
                "program_id": item.program_id,
                "reviewer_id": item.reviewer_id,
                "revealed": item.revealed_at is not None,
                "has_started": await service.has_started({p.id for p in presentations}),
                "total_presentations": len(presentations),
                "blotter_complete": sum(
                    p.blotter_locked_at is not None for p in presentations
                ),
                "skin_planned": len(skin_planned),
                "skin_complete": sum(
                    p.skin_locked_at is not None for p in skin_planned
                ),
                "program_name": program.name,
                "program_version": program.version,
            }
        )
    return result


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
    presentation_id: str,
    data: ResponseInput,
    db: DB,
    identity: Identity,
    response: Response,
) -> dict[str, object]:
    """Append a blind timepoint; a same-key retry answers 200 with the original."""
    obj, replayed = await CalibrationService(db).observe_once(
        presentation_id, data, *actor(identity)
    )
    if replayed:
        response.status_code = 200
    return {"id": obj.id, "replayed": replayed}


@router.post("/presentations/{presentation_id}/post-reveal", status_code=201)
async def post_reveal(
    presentation_id: str,
    data: ResponseInput,
    db: DB,
    identity: Identity,
    response: Response,
) -> dict[str, object]:
    """Append an informed observation without changing blind responses."""
    obj, replayed = await CalibrationService(db).observe_once(
        presentation_id, data, *actor(identity), post_reveal=True
    )
    if replayed:
        response.status_code = 200
    return {"id": obj.id, "replayed": replayed}


@router.post("/presentations/{presentation_id}/exposure")
async def exposure(
    presentation_id: str, data: ExposureInput, db: DB, identity: Identity
) -> dict[str, object]:
    """Stamp the first blotter smell or skin application of a sample."""
    obj = await CalibrationService(db).record_exposure(
        presentation_id, data, *actor(identity)
    )
    return {
        "id": obj.id,
        "presented_at": obj.presented_at,
        "applied_at": obj.applied_at,
        "application_timezone": obj.application_timezone,
    }


@router.post("/sessions/{session_id}/start")
async def start_session(
    session_id: str, data: SessionStartInput, db: DB, identity: Identity
) -> dict[str, object]:
    """Record when and where a session actually began."""
    obj = await CalibrationService(db).start_session(session_id, data, *actor(identity))
    return {
        "id": obj.id,
        "started_at": obj.started_at,
        "occurred_on": obj.occurred_on,
        "evaluator_timezone": obj.evaluator_timezone,
    }


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str, data: SessionEndInput, db: DB, identity: Identity
) -> dict[str, object]:
    """Record when a started session actually ended."""
    obj = await CalibrationService(db).end_session(session_id, data, *actor(identity))
    return {"id": obj.id, "ended_at": obj.ended_at}


_CONTEXT_FIELDS = (
    "illness",
    "nasal_congestion",
    "allergy_symptoms",
    "hunger",
    "hours_since_food",
    "hours_since_caffeine",
    "personal_fragrance_worn",
    "ambient_odor",
    "ambient_odor_detail",
    "room_temperature_c",
    "room_humidity_pct",
    "hormonal_context",
    "note",
)


@router.post("/sessions/{session_id}/context", status_code=201)
async def record_session_context(
    session_id: str, data: SessionContextInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Record refusable self-reported conditions, only while consent stands."""
    username, admin = actor(identity)
    obj = await CalibrationService(db).record_session_context(
        session_id, data, username, admin
    )
    # The answers themselves are sensitive and are never logged, only that they
    # were recorded and which of them were answered.
    log_audit_event(
        logger,
        action="session_context_record",
        actor=username,
        target_type="session_context",
        target_id=obj.id,
        session_id=session_id,
        answered=sorted(
            name for name in _CONTEXT_FIELDS if getattr(obj, name) is not None
        ),
    )
    return {"id": obj.id}


@router.get("/sessions/{session_id}/context")
async def read_session_context(
    session_id: str, db: DB, identity: Identity
) -> dict[str, object]:
    """Read a session's recorded conditions; manager or assigned recorder only."""
    service = CalibrationService(db)
    username, admin = actor(identity)
    obj = await service.session_context(session_id, username, admin)
    if obj is None:
        return {"recorded": False}
    # Same rule as the evidence export: withdrawn or absent consent withholds the
    # answers (the owner decides who may see raw answers; see the consent text).
    _, enrollment = await service.session_target(session_id, username, admin)
    consent = await ConsentService(db).state(enrollment.reviewer_id)
    if consent.get("session_context") != "granted":
        return {"recorded": True, "withheld": True}
    return {
        "recorded": True,
        "id": obj.id,
        "recorded_by": obj.recorded_by,
        **{name: getattr(obj, name) for name in _CONTEXT_FIELDS},
    }


@router.get("/consent/text")
async def consent_text(identity: Identity) -> dict[str, object]:
    """Return the consent wording, its version, digest, and approval state."""
    actor(identity)
    text = load_consent_text()
    return {
        "version": text.version,
        "sha256": text.sha256,
        "approved": text.approved,
        "text": text.body,
    }


@router.get("/reviewers/{reviewer_id}/consent")
async def reviewer_consent(
    reviewer_id: str, db: DB, identity: Identity
) -> dict[str, object]:
    """Return each consent scope's current state and the full event log."""
    username, admin = actor(identity)
    await authorize_reviewer(db, reviewer_id, username, admin)
    service = ConsentService(db)
    return {
        "state": await service.state(reviewer_id),
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "scope": event.scope,
                "consent_text_version": event.consent_text_version,
                "occurred_at": event.occurred_at,
                "recorded_by": event.recorded_by,
            }
            for event in await service.events(reviewer_id)
        ],
    }


@router.post("/reviewers/{reviewer_id}/consent", status_code=201)
async def record_consent(
    reviewer_id: str, data: ConsentEventInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Append a consent grant or withdrawal, stamped with the shown text."""
    username, admin = actor(identity)
    await authorize_reviewer(db, reviewer_id, username, admin)
    if await db.get(Reviewer, reviewer_id) is None:
        reject("Reviewer not found", 404)
    if data.enrollment_id is not None:
        enrolled = await db.get(Enrollment, data.enrollment_id)
        if enrolled is None or enrolled.reviewer_id != reviewer_id:
            reject("Enrollment not found for this reviewer", 404)
    event = await ConsentService(db).record(
        reviewer_id,
        data.scope,
        data.event_type,
        username,
        enrollment_id=data.enrollment_id,
        note=data.note,
    )
    log_audit_event(
        logger,
        action=f"consent_{event.event_type}",
        actor=username,
        target_type="consent_event",
        target_id=event.id,
        reviewer_id=reviewer_id,
        scope=event.scope,
        consent_text_version=event.consent_text_version,
    )
    return {"id": event.id}


@router.post("/presentations/{presentation_id}/lock/{stage}")
async def lock_stage(
    presentation_id: str, stage: Stage, db: DB, identity: Identity
) -> dict[str, bool]:
    """Lock the submitted stage."""
    username, admin = actor(identity)
    await CalibrationService(db).lock_stage(presentation_id, stage, username, admin)
    log_audit_event(
        logger,
        action="lock_stage",
        actor=username,
        target_type="presentation",
        target_id=presentation_id,
        stage=stage,
    )
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
    username, admin = actor(identity)
    obj = await CalibrationService(db).enrollment(enrollment_id, username, admin)
    obj.skin_plan_locked_at = obj.skin_plan_locked_at or now_naive_utc()
    await db.flush()
    log_audit_event(
        logger,
        action="lock_skin_plan",
        actor=username,
        target_type="enrollment",
        target_id=enrollment_id,
    )
    return {"locked": True}


@router.post("/enrollments/{enrollment_id}/reveal")
async def reveal(enrollment_id: str, db: DB, identity: Identity) -> dict[str, bool]:
    """Apply the delayed-reveal policy on the server."""
    username, admin = actor(identity)
    await CalibrationService(db).reveal(enrollment_id, username, admin)
    log_audit_event(
        logger,
        action="reveal",
        actor=username,
        target_type="enrollment",
        target_id=enrollment_id,
    )
    return {"revealed": True}


@router.post("/enrollments/{enrollment_id}/checkpoints", status_code=201)
async def checkpoint(
    enrollment_id: str, data: CheckpointInput, db: DB, identity: Identity
) -> dict[str, str]:
    """Snapshot model inputs and predictions before holdout outcomes exist."""
    username = manager(identity)
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
    # R8 (M-07, M-08, X-17): manifest and digest from v_training_rows, every
    # reproduction column, a feature snapshot, and typed predictions.
    run = await CheckpointService(db).create(
        obj, data.algorithm_version, data.predictions, username
    )
    log_audit_event(
        logger,
        action="checkpoint_create",
        actor=username,
        target_type="model_checkpoint",
        target_id=run.id,
        enrollment_id=obj.id,
        algorithm_version=data.algorithm_version,
        input_digest=run.input_digest,
        feature_snapshot_id=run.feature_snapshot_id,
    )
    return {"id": run.id}


@router.get("/enrollments/{enrollment_id}/mapping")
async def mapping(
    enrollment_id: str, db: DB, identity: Identity
) -> list[dict[str, object]]:
    """Manager-only decant labeling sheet; never part of participant payloads."""
    username = manager(identity)
    service = CalibrationService(db)
    await service.enrollment(enrollment_id, *actor(identity))
    # B-03: every retrieval of the blind mapping is recorded: who and which
    # enrollment, never the blind codes, fragrances, or roles it returns.
    log_audit_event(
        logger,
        action="mapping_retrieve",
        actor=username,
        target_type="enrollment",
        target_id=enrollment_id,
    )
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
            "exclusions": r.exclusions,
            "filters": r.filters,
            "feature_space_version": r.feature_space_version,
            "taxonomy_version": r.taxonomy_version,
            "model_params": r.model_params,
            "input_digest": r.input_digest,
            "feature_snapshot_id": r.feature_snapshot_id,
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
            # ADR-011: surfaced so a consumer can tell an "on others" entry
            # (evidence only, excluded from this reviewer's own affinity
            # scoring) apart from an ordinary "on me" rating.
            "worn_by_reviewer_id": e.worn_by_reviewer_id,
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
