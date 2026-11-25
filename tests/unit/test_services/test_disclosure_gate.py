"""F1 holdout gate, checkpoint readiness, household reveal, and ranking phase."""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import (
    EnrollmentInput,
    ExposureInput,
    MembershipInput,
    ResponseInput,
    SessionStartInput,
)
from fragrance_rater.schemas.capture import RankingInput
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.capture_service import CaptureService
from fragrance_rater.services.checkpoint_service import (
    HAS_CHECKPOINT,
    CheckpointService,
    freeze_program_checkpoints,
)
from fragrance_rater.services.disclosure_gate import (
    BLOTTER,
    CHECKPOINT,
    CHECKPOINT_REQUIRED,
    HOLDOUT,
    HOLDOUT_OBSERVED,
    HOUSEHOLD_ONLY,
    HOUSEHOLD_WAIT,
    SKIN,
    SKIN_PLAN,
    DisclosureGate,
    EnrollmentState,
)
from fragrance_rater.utils.timestamps import now_naive_utc

RECORDER = "family-recorder"


@pytest_asyncio.fixture
async def household(async_session):
    """Build a program with a baseline, a hidden repeat, and one holdout.

    Returns a factory so each test chooses the reveal policy and whether the
    program has a holdout at all.
    """

    async def build(policy: str = "ENROLLMENT", *, with_holdout: bool = True):
        service = CalibrationService(async_session)
        program = Program(name="Household", version="f1", reveal_policy=policy)
        async_session.add(program)
        for index in range(2):
            async_session.add(
                Fragrance(
                    id=f"gate-version-{index}",
                    name=f"Gate Fragrance {index}",
                    brand="Gate House",
                    concentration="EDT",
                    gender_target="unisex",
                    primary_family="woody",
                    subfamily="aromatic",
                    data_source="manual",
                )
            )
        for index in range(2):
            async_session.add(Reviewer(id=f"gate-reviewer-{index}", name=f"E{index}"))
        await async_session.flush()
        base = await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id="gate-version-0",
                role="UNIVERSAL_BASELINE",
                identity_evidence="Verified label",
            ),
        )
        repeat = await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id="gate-version-0",
                role="HIDDEN_REPEAT",
                repeat_of_id=base.id,
                identity_evidence="Same decant",
            ),
        )
        holdout = None
        if with_holdout:
            holdout = await service.add_member(
                program.id,
                MembershipInput(
                    fragrance_id="gate-version-1",
                    role="HOLDOUT",
                    identity_evidence="Verified label",
                ),
            )
        program.status = "active"
        await async_session.flush()
        return service, program, base, repeat, holdout

    return build


async def enroll(service, program, reviewer="gate-reviewer-0"):
    """Enroll one evaluator; baseline and repeat share session 1."""
    return await service.enroll(
        program.id,
        EnrollmentInput(
            reviewer_id=reviewer, recorder_usernames=[RECORDER], session_size=2
        ),
    )


async def by_member(service, enrollment):
    """Map membership id to the enrollment's presentation of it."""
    return {p.membership_id: p for p in await service.presentations(enrollment.id)}


async def answer_and_lock(service, presentation, stage="BLOTTER"):
    """Submit a detected response and lock the stage."""
    response = await service.observe(
        presentation.id,
        ResponseInput(stage=stage, detected=True, intensity=3, liking=7),
        RECORDER,
        admin=False,
    )
    await service.lock_stage(presentation.id, stage, RECORDER, admin=False)
    return response


async def finish_baseline(service, enrollment, base, repeat):
    """Lock the non-holdout blotters and finalize an empty skin plan."""
    rows = await by_member(service, enrollment)
    await answer_and_lock(service, rows[base.id])
    await answer_and_lock(service, rows[repeat.id])
    enrollment.skin_plan_locked_at = now_naive_utc()
    await service.db.flush()


async def checkpoint(service, enrollment):
    """Freeze an empty checkpoint the way the per-enrollment endpoint does."""
    return await CheckpointService(service.db).create(enrollment, "test", [], "manager")


def test_gate_message_never_names_the_holdout_role():
    for message in (CHECKPOINT_REQUIRED, HOUSEHOLD_ONLY):
        assert "holdout" not in message.lower()


@pytest.mark.asyncio
async def test_holdout_writes_are_refused_until_a_checkpoint_exists(household):
    service, program, base, _, holdout = await household()
    enrollment = await enroll(service, program)
    rows = await by_member(service, enrollment)
    target = rows[holdout.id]
    attempts = [
        service.observe(
            target.id, ResponseInput(stage="BLOTTER"), RECORDER, admin=False
        ),
        service.record_exposure(
            target.id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
        ),
        service.lock_stage(target.id, "BLOTTER", RECORDER, admin=False),
        service.start_session(
            target.session_id,
            SessionStartInput(evaluator_timezone="America/Chicago"),
            RECORDER,
            admin=False,
        ),
    ]
    for attempt in attempts:
        with pytest.raises(HTTPException) as error:
            await attempt
        assert error.value.status_code == 409
        assert error.value.detail == CHECKPOINT_REQUIRED
    # Non-holdout work in the same enrollment is untouched by the gate.
    await service.start_session(
        rows[base.id].session_id,
        SessionStartInput(evaluator_timezone="America/Chicago"),
        RECORDER,
        admin=False,
    )
    await answer_and_lock(service, rows[base.id])
    view = await service.participant_view(enrollment)
    available = {row["id"]: row["available"] for row in view["presentations"]}
    assert available[target.id] is False
    assert available[rows[base.id].id] is True
    assert view["reveal_policy"] == "ENROLLMENT"

    await checkpoint(service, enrollment)
    session = await service.start_session(
        target.session_id,
        SessionStartInput(evaluator_timezone="America/Chicago"),
        RECORDER,
        admin=False,
    )
    assert session.started_at is not None
    await service.record_exposure(
        target.id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
    )
    blind = await answer_and_lock(service, target)
    assert blind.phase == "PRE_REVEAL"
    view = await service.participant_view(enrollment)
    assert all(row["available"] for row in view["presentations"])


@pytest.mark.asyncio
async def test_a_program_without_holdouts_needs_no_checkpoint(household):
    service, program, base, repeat, _ = await household(with_holdout=False)
    enrollment = await enroll(service, program)
    await finish_baseline(service, enrollment, base, repeat)
    view = await service.participant_view(enrollment)
    assert all(row["available"] for row in view["presentations"])
    assert view["reveal_blocker"] is None
    await service.reveal(enrollment.id, RECORDER, admin=False)
    assert enrollment.revealed_at is not None


@pytest.mark.asyncio
async def test_enrollment_policy_keeps_its_legacy_reveal_and_checkpoint_rules(
    household,
):
    service, program, base, repeat, holdout = await household()
    enrollment = await enroll(service, program)
    gate = DisclosureGate(service.db)
    # The per-enrollment checkpoint endpoint keeps no baseline precondition.
    await gate.require_checkpoint_ready(enrollment)
    await gate.require_enrollment_reveal_allowed(enrollment)
    await finish_baseline(service, enrollment, base, repeat)
    # No checkpoint and the holdout unanswered: ENROLLMENT still reveals.
    assert await gate.reveal_blocker(enrollment) is None
    await service.reveal(enrollment.id, RECORDER, admin=False)
    rows = await by_member(service, enrollment)
    # The reveal does not open the holdout; only a checkpoint does.
    with pytest.raises(HTTPException, match="not open yet"):
        await service.observe(
            rows[holdout.id].id,
            ResponseInput(stage="BLOTTER"),
            RECORDER,
            admin=False,
            post_reveal=True,
        )
    await gate.require_enrollment_open(program.id)
    with pytest.raises(HTTPException, match="reveals each evaluator separately"):
        await gate.reveal_household(program.id, "manager")


@pytest.mark.asyncio
async def test_household_blockers_run_in_order_and_wait_for_everyone(household):
    service, program, base, repeat, holdout = await household("HOUSEHOLD")
    first = await enroll(service, program)
    second = await enroll(service, program, "gate-reviewer-1")
    gate = DisclosureGate(service.db)
    rows = await by_member(service, first)

    assert await gate.reveal_blocker(first) == SKIN_PLAN
    first.skin_plan_locked_at = now_naive_utc()
    await service.db.flush()
    assert await gate.reveal_blocker(first) == BLOTTER
    await answer_and_lock(service, rows[base.id])
    # The hidden repeat is part of the blind baseline.
    assert await gate.reveal_blocker(first) == BLOTTER
    await answer_and_lock(service, rows[repeat.id])
    # A skin test planned after the plan was finalized still has to be locked.
    rows[base.id].skin_reason = "Ambiguous opening"
    await service.db.flush()
    assert await gate.reveal_blocker(first) == SKIN
    await answer_and_lock(service, rows[base.id], "SKIN")
    assert await gate.reveal_blocker(first) == CHECKPOINT
    await gate.require_checkpoint_ready(first)
    await checkpoint(service, first)
    assert await gate.reveal_blocker(first) == HOLDOUT
    await answer_and_lock(service, rows[holdout.id])
    assert await gate.reveal_blocker(first) == HOUSEHOLD_WAIT
    view = await service.participant_view(first)
    assert view["reveal_blocker"] == HOUSEHOLD_WAIT
    assert view["reveal_eligible"] is False
    assert view["reveal_policy"] == "HOUSEHOLD"

    # The second evaluator plans no skin at all: an empty plan is satisfied.
    await finish_baseline(service, second, base, repeat)
    await checkpoint(service, second)
    assert await gate.reveal_blocker(second) == HOLDOUT
    await answer_and_lock(service, (await by_member(service, second))[holdout.id])
    assert await gate.reveal_blocker(first) is None
    assert await gate.reveal_blocker(second) is None
    readiness = await gate.readiness(program.id)
    assert [state.household_blocker() for state in readiness] == [None, None]


@pytest.mark.asyncio
async def test_household_checkpoint_waits_for_the_blind_baseline(household):
    service, program, base, repeat, _ = await household("HOUSEHOLD")
    enrollment = await enroll(service, program)
    gate = DisclosureGate(service.db)
    rows = await by_member(service, enrollment)
    with pytest.raises(HTTPException, match="Finalize the skin plan"):
        await gate.require_checkpoint_ready(enrollment)
    enrollment.skin_plan_locked_at = now_naive_utc()
    await service.db.flush()
    with pytest.raises(HTTPException, match="blind baseline blotter"):
        await gate.require_checkpoint_ready(enrollment)
    await answer_and_lock(service, rows[base.id])
    await answer_and_lock(service, rows[repeat.id])
    rows[repeat.id].skin_reason = "Recheck"
    await service.db.flush()
    with pytest.raises(HTTPException, match="planned blind skin test"):
        await gate.require_checkpoint_ready(enrollment)
    await answer_and_lock(service, rows[repeat.id], "SKIN")
    await gate.require_checkpoint_ready(enrollment)


@pytest.mark.asyncio
async def test_household_refuses_per_evaluator_reveal(household):
    service, program, base, repeat, _ = await household("HOUSEHOLD")
    enrollment = await enroll(service, program)
    await finish_baseline(service, enrollment, base, repeat)
    with pytest.raises(HTTPException) as error:
        await service.reveal(enrollment.id, RECORDER, admin=False)
    assert error.value.status_code == 409
    assert error.value.detail == HOUSEHOLD_ONLY
    with pytest.raises(HTTPException, match="reveals every evaluator together"):
        await service.reveal(enrollment.id, "manager", admin=True)
    assert enrollment.revealed_at is None


@pytest.mark.asyncio
async def test_household_reveal_is_atomic_idempotent_and_closes_enrollment(
    household,
):
    service, program, base, repeat, holdout = await household("HOUSEHOLD")
    gate = DisclosureGate(service.db)
    with pytest.raises(HTTPException, match="Enroll evaluators"):
        await gate.reveal_household(program.id, "manager")
    with pytest.raises(HTTPException) as missing:
        await gate.reveal_household("no-such-program", "manager")
    assert missing.value.status_code == 404
    first = await enroll(service, program)
    second = await enroll(service, program, "gate-reviewer-1")
    for enrollment in (first, second):
        await finish_baseline(service, enrollment, base, repeat)
        await checkpoint(service, enrollment)
    await answer_and_lock(service, (await by_member(service, first))[holdout.id])
    with pytest.raises(HTTPException, match="1 of 2 evaluators still have"):
        await gate.reveal_household(program.id, "manager")
    assert first.revealed_at is None
    assert second.revealed_at is None

    second_holdout = (await by_member(service, second))[holdout.id]
    await answer_and_lock(service, second_holdout)
    revealed, at = await gate.reveal_household(program.id, "manager")
    assert sorted(revealed) == sorted([first.id, second.id])
    assert first.revealed_at == second.revealed_at == at
    assert first.revealed_by == second.revealed_by == "manager"

    again, again_at = await gate.reveal_household(program.id, "manager")
    assert sorted(again) == sorted(revealed)
    assert again_at == at
    with pytest.raises(HTTPException, match="already revealed"):
        await gate.require_enrollment_open(program.id)

    view = await service.participant_view(second)
    shown = {row["id"]: row for row in view["presentations"]}
    assert shown[second_holdout.id]["identity"]["fragrance_id"] == "gate-version-1"
    informed = await service.observe(
        second_holdout.id,
        ResponseInput(stage="BLOTTER", comments="Recognized"),
        RECORDER,
        admin=False,
        post_reveal=True,
    )
    assert informed.phase == "POST_REVEAL"


def test_checkpoint_blocker_reports_an_observed_holdout_first():
    enrollment = Enrollment(program_id="p", reviewer_id="r")
    state = EnrollmentState(
        enrollment=enrollment,
        presentations=[],
        roles={},
        checkpoint_count=0,
        holdout_observed=True,
    )
    assert state.checkpoint_blocker() == HOLDOUT_OBSERVED
    assert state.baseline_blocker() == SKIN_PLAN


@pytest.mark.asyncio
async def test_program_checkpoints_freeze_ready_enrollments_and_skip_the_rest(
    household,
):
    service, program, base, repeat, _ = await household()
    ready = await enroll(service, program)
    waiting = await enroll(service, program, "gate-reviewer-1")
    await finish_baseline(service, ready, base, repeat)
    db = service.db

    run = await freeze_program_checkpoints(
        db,
        program.id,
        algorithm_version=None,
        freeze_predictions=True,
        recorded_by="manager",
    )
    assert run.algorithm_version == "affinity-v2"
    assert [row.enrollment_id for row in run.created] == [ready.id]
    assert run.created[0].predictions_frozen == 1
    assert run.skipped == [(waiting.id, SKIN_PLAN)]
    snapshots = list(await db.scalars(select(PredictionSnapshot)))
    assert [s.checkpoint_id for s in snapshots] == [run.created[0].checkpoint_id]
    assert [s.fragrance_id for s in snapshots] == ["gate-version-1"]

    await finish_baseline(service, waiting, base, repeat)
    again = await freeze_program_checkpoints(
        db,
        program.id,
        algorithm_version=None,
        freeze_predictions=False,
        recorded_by="manager",
    )
    assert [row.enrollment_id for row in again.created] == [waiting.id]
    assert again.created[0].predictions_frozen == 0
    assert again.skipped == [(ready.id, HAS_CHECKPOINT)]
    assert await db.scalar(select(func.count()).select_from(PredictionSnapshot)) == 1


@pytest.mark.asyncio
async def test_program_checkpoints_refuse_an_unknown_model(household):
    service, program, *_ = await household()
    with pytest.raises(HTTPException) as error:
        await freeze_program_checkpoints(
            service.db,
            program.id,
            algorithm_version="no-such-model",
            freeze_predictions=True,
            recorded_by="manager",
        )
    assert error.value.status_code == 422


async def blind_ranking(capture, session_id):
    """Record a no-entry ranking so only the computed phase matters."""
    event, _ = await capture.record_ranking(
        session_id,
        RankingInput(stage="BLOTTER", response_status="skipped"),
        RECORDER,
        admin=False,
    )
    return event


@pytest.mark.asyncio
async def test_holdout_ranking_after_per_evaluator_reveal_stays_pre_reveal(
    household,
):
    service, program, base, repeat, holdout = await household()
    enrollment = await enroll(service, program)
    capture = CaptureService(service.db)
    rows = await by_member(service, enrollment)
    holdout_session = rows[holdout.id].session_id
    with pytest.raises(HTTPException, match="not open yet"):
        await blind_ranking(capture, holdout_session)
    await finish_baseline(service, enrollment, base, repeat)
    await service.reveal(enrollment.id, RECORDER, admin=False)
    # The baseline session is ranked with identities on screen.
    assert (await blind_ranking(capture, rows[base.id].session_id)).phase == (
        "POST_REVEAL"
    )
    await checkpoint(service, enrollment)
    await service.observe(
        rows[holdout.id].id,
        ResponseInput(stage="BLOTTER", detected=True, intensity=3, liking=6),
        RECORDER,
        admin=False,
    )
    # Revealed enrollment, but the holdout is still concealed: blind ranking.
    assert (await blind_ranking(capture, holdout_session)).phase == "PRE_REVEAL"


@pytest.mark.asyncio
async def test_holdout_ranking_under_household_is_pre_reveal(household):
    service, program, base, repeat, holdout = await household("HOUSEHOLD")
    enrollment = await enroll(service, program)
    capture = CaptureService(service.db)
    await finish_baseline(service, enrollment, base, repeat)
    await checkpoint(service, enrollment)
    rows = await by_member(service, enrollment)
    await answer_and_lock(service, rows[holdout.id])
    event = await blind_ranking(capture, rows[holdout.id].session_id)
    assert event.phase == "PRE_REVEAL"
    assert enrollment.revealed_at is None


@pytest.mark.asyncio
async def test_session_roles_cover_every_presentation(household):
    service, program, base, _, holdout = await household()
    enrollment = await enroll(service, program)
    rows = await by_member(service, enrollment)
    gate = DisclosureGate(service.db)
    sessions = list(
        await service.db.scalars(
            select(CalibrationSession.id)
            .join(Presentation, Presentation.session_id == CalibrationSession.id)
            .where(Presentation.id == rows[base.id].id)
        )
    )
    assert sorted(await gate.session_roles(sessions[0])) == [
        "HIDDEN_REPEAT",
        "UNIVERSAL_BASELINE",
    ]
    assert await gate.session_roles(rows[holdout.id].session_id) == ["HOLDOUT"]
