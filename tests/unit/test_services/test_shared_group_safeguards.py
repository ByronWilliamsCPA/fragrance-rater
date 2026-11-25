"""F1 shared-group safeguards: program-wide holdout gate, evidence timing, reveal.

A ``SHARED_GROUP`` program passes ONE physical blotter per sample around every
evaluator. Three consequences are enforced here, independently of any UI:

* holdouts open only when EVERY enrollment has a checkpoint;
* explicit evidence instants on a holdout cannot pre-date the checkpoint that
  opens it (a paper sheet is transcribed up to days late);
* the program reveals only as a household, never per evaluator.
"""

from datetime import timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    ModelCheckpoint,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import (
    EnrollmentInput,
    ExposureInput,
    MembershipInput,
    ProgramInput,
    ResponseInput,
)
from fragrance_rater.schemas.capture import RankingInput
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.capture_service import CaptureService
from fragrance_rater.services.checkpoint_service import (
    CheckpointService,
    freeze_program_checkpoints,
)
from fragrance_rater.services.disclosure_gate import (
    CHECKPOINT_REQUIRED,
    EVIDENCE_BEFORE_CHECKPOINT,
    GROUP_CHECKPOINT_REQUIRED,
    GROUP_ENROLLMENT_CLOSED,
    HOUSEHOLD,
    HOUSEHOLD_ONLY,
    DisclosureGate,
    effective_reveal_policy,
)
from fragrance_rater.services.shared_triples import GROUP_BLOTTER_ALGORITHM
from fragrance_rater.utils.timestamps import now_naive_utc

RECORDER = "family-recorder"


@pytest_asyncio.fixture
async def make_program(async_session):
    """Build a program with a baseline, a hidden repeat and one holdout."""

    async def build(mode: str, policy: str = "HOUSEHOLD", evaluators: int = 2):
        service = CalibrationService(async_session)
        program = Program(
            name=f"Safeguard {mode}",
            version="f1",
            blotter_mode=mode,
            reveal_policy=policy,
        )
        async_session.add(program)
        for index in range(2):
            async_session.add(
                Fragrance(
                    id=f"sg-version-{index}",
                    name=f"Safeguard Fragrance {index}",
                    brand="Safeguard House",
                    concentration="EDT",
                    gender_target="unisex",
                    primary_family="woody",
                    subfamily="aromatic",
                    data_source="manual",
                )
            )
        for index in range(evaluators):
            async_session.add(Reviewer(id=f"sg-reviewer-{index}", name=f"E{index}"))
        await async_session.flush()
        base = await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id="sg-version-0",
                role="UNIVERSAL_BASELINE",
                identity_evidence="Verified label",
            ),
        )
        holdout = await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id="sg-version-1",
                role="HOLDOUT",
                identity_evidence="Verified label",
            ),
        )
        program.status = "active"
        await async_session.flush()
        extra = (
            {"randomization_algorithm": GROUP_BLOTTER_ALGORITHM}
            if mode == "SHARED_GROUP"
            else {}
        )
        enrollments = [
            await service.enroll(
                program.id,
                EnrollmentInput(
                    reviewer_id=f"sg-reviewer-{index}",
                    recorder_usernames=[RECORDER],
                    session_size=2,
                    **extra,
                ),
                "manager",
            )
            for index in range(evaluators)
        ]
        return service, program, base, holdout, enrollments

    return build


async def by_member(service, enrollment):
    return {p.membership_id: p for p in await service.presentations(enrollment.id)}


async def freeze(service, enrollment, *, minutes_ago: float | None = None):
    """Freeze an empty checkpoint, optionally creation-dated in the past."""
    row = await CheckpointService(service.db).create(enrollment, "test", [], "manager")
    if minutes_ago is not None:
        row.created_at = now_naive_utc() - timedelta(minutes=minutes_ago)
        await service.db.flush()
    return row


async def backdate_sessions(db, *, days: float = 2) -> None:
    for session in await db.scalars(select(CalibrationSession)):
        session.created_at = now_naive_utc() - timedelta(days=days)
    await db.flush()


def ago(**delta: float):
    return now_naive_utc() - timedelta(**delta)


# --- B: the SHARED_GROUP holdout gate is program-wide ----------------------


@pytest.mark.asyncio
async def test_shared_group_holdouts_wait_for_every_enrollments_checkpoint(
    make_program,
):
    service, program, _, holdout, (first, second) = await make_program("SHARED_GROUP")
    gate = DisclosureGate(service.db)
    await freeze(service, first)

    assert await gate.missing_checkpoints(program.id) == [second.id]
    for enrollment in (first, second):
        assert await gate.holdouts_open(enrollment) is False
        view = await service.participant_view(enrollment)
        available = {r["id"]: r["available"] for r in view["presentations"]}
        target = (await by_member(service, enrollment))[holdout.id]
        assert available[target.id] is False
    # The evaluator who HAS a checkpoint is still refused: the physical
    # holdout blotter is shared with the evaluator who has none.
    target = (await by_member(service, first))[holdout.id]
    for attempt in (
        service.observe(
            target.id, ResponseInput(stage="BLOTTER"), RECORDER, admin=False
        ),
        service.record_exposure(
            target.id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
        ),
        service.lock_stage(target.id, "BLOTTER", RECORDER, admin=False),
    ):
        with pytest.raises(HTTPException) as error:
            await attempt
        assert error.value.status_code == 409
        assert error.value.detail == GROUP_CHECKPOINT_REQUIRED

    await freeze(service, second)

    assert await gate.missing_checkpoints(program.id) == []
    for enrollment in (first, second):
        assert await gate.holdouts_open(enrollment) is True
        view = await service.participant_view(enrollment)
        assert all(r["available"] for r in view["presentations"])
    await service.record_exposure(
        target.id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
    )


@pytest.mark.asyncio
async def test_a_partial_program_freeze_does_not_open_the_group_holdouts(
    make_program,
):
    """freeze_program_checkpoints freezes only ready evaluators; that is not enough."""
    service, program, base, holdout, (first, second) = await make_program(
        "SHARED_GROUP"
    )
    gate = DisclosureGate(service.db)
    first.skin_plan_locked_at = now_naive_utc()
    rows = await by_member(service, first)
    await service.observe(
        rows[base.id].id,
        ResponseInput(stage="BLOTTER", detected=True, intensity=3, liking=7),
        RECORDER,
        admin=False,
    )
    await service.lock_stage(rows[base.id].id, "BLOTTER", RECORDER, admin=False)

    run = await freeze_program_checkpoints(
        service.db,
        program.id,
        algorithm_version=None,
        freeze_predictions=False,
        recorded_by="manager",
    )

    assert [row.enrollment_id for row in run.created] == [first.id]
    assert [enrollment_id for enrollment_id, _ in run.skipped] == [second.id]
    assert await gate.holdouts_open(first) is False
    with pytest.raises(HTTPException, match="every evaluator in this group"):
        await service.record_exposure(
            rows[holdout.id].id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
        )


@pytest.mark.asyncio
async def test_individual_programs_keep_the_per_enrollment_gate(make_program):
    service, program, _, holdout, (first, second) = await make_program(
        "INDIVIDUAL", "ENROLLMENT"
    )
    gate = DisclosureGate(service.db)
    await freeze(service, first)

    assert await gate.holdouts_open(first) is True
    assert await gate.holdouts_open(second) is False
    assert await gate.missing_checkpoints(program.id) == [second.id]
    refused = (await by_member(service, second))[holdout.id]
    with pytest.raises(HTTPException) as error:
        await service.record_exposure(
            refused.id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
        )
    assert error.value.detail == CHECKPOINT_REQUIRED
    opened = (await by_member(service, first))[holdout.id]
    await service.record_exposure(
        opened.id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
    )


@pytest.mark.asyncio
async def test_a_shared_group_refuses_enrollment_once_holdouts_open(make_program):
    service, program, _, _, (first, second) = await make_program("SHARED_GROUP")
    gate = DisclosureGate(service.db)
    await gate.require_enrollment_open(program.id)
    await freeze(service, first)
    # Only some evaluators are frozen: a late evaluator can still join.
    await gate.require_enrollment_open(program.id)
    await freeze(service, second)

    with pytest.raises(HTTPException) as error:
        await gate.require_enrollment_open(program.id)

    assert error.value.status_code == 409
    assert error.value.detail == GROUP_ENROLLMENT_CLOSED


# --- A: holdout evidence cannot pre-date the checkpoint --------------------


@pytest.mark.asyncio
async def test_holdout_evidence_before_the_checkpoint_is_refused(make_program):
    service, _, _, holdout, (first, _) = await make_program("INDIVIDUAL", "ENROLLMENT")
    await backdate_sessions(service.db)
    await freeze(service, first, minutes_ago=60)
    target = (await by_member(service, first))[holdout.id]

    early = ago(hours=3)
    expected = EVIDENCE_BEFORE_CHECKPOINT.format(label="The first-smell time")
    with pytest.raises(HTTPException) as exposure:
        await service.record_exposure(
            target.id,
            ExposureInput(stage="BLOTTER", at=early),
            RECORDER,
            admin=False,
        )
    assert exposure.value.status_code == 422
    assert exposure.value.detail == expected
    with pytest.raises(HTTPException, match="The spray time"):
        await service.record_exposure(
            target.id,
            ExposureInput(stage="BLOTTER", at=ago(minutes=30), sprayed_at=early),
            RECORDER,
            admin=False,
        )
    with pytest.raises(HTTPException) as observation:
        await service.observe(
            target.id,
            ResponseInput(stage="BLOTTER", observed_at=early),
            RECORDER,
            admin=False,
        )
    assert observation.value.status_code == 422
    assert "The column-finished time" in observation.value.detail
    with pytest.raises(HTTPException, match="The spray time"):
        await service.observe(
            target.id,
            ResponseInput(
                stage="BLOTTER", sprayed_at=early, observed_at=ago(minutes=10)
            ),
            RECORDER,
            admin=False,
        )
    # Refused writes leave no trace.
    assert target.presented_at is None
    assert (await service.participant_view(first))["presentations"]
    views = {
        r["id"]: r for r in (await service.participant_view(first))["presentations"]
    }
    assert views[target.id]["observations"] == []


@pytest.mark.asyncio
async def test_holdout_evidence_after_the_checkpoint_is_accepted(make_program):
    service, _, _, holdout, (first, _) = await make_program("INDIVIDUAL", "ENROLLMENT")
    await backdate_sessions(service.db)
    await freeze(service, first, minutes_ago=60)
    target = (await by_member(service, first))[holdout.id]

    await service.record_exposure(
        target.id,
        ExposureInput(stage="BLOTTER", at=ago(minutes=30), sprayed_at=ago(minutes=31)),
        RECORDER,
        admin=False,
    )
    row = await service.observe(
        target.id,
        ResponseInput(stage="BLOTTER", observed_at=ago(minutes=10)),
        RECORDER,
        admin=False,
    )

    assert target.presented_at is not None
    assert row.observed_at is not None


@pytest.mark.asyncio
async def test_holdout_evidence_without_an_instant_uses_receipt_time(make_program):
    """No explicit instant: receipt time is after the checkpoint the gate demanded."""
    service, _, _, holdout, (first, _) = await make_program("INDIVIDUAL", "ENROLLMENT")
    await freeze(service, first)
    target = (await by_member(service, first))[holdout.id]

    await service.record_exposure(
        target.id, ExposureInput(stage="BLOTTER"), RECORDER, admin=False
    )

    assert target.presented_at is not None
    assert target.presented_at >= (await first_checkpoint(service, first)).created_at


async def first_checkpoint(service, enrollment):
    return await service.db.scalar(
        select(ModelCheckpoint).where(ModelCheckpoint.enrollment_id == enrollment.id)
    )


@pytest.mark.asyncio
async def test_baseline_evidence_may_pre_date_the_checkpoint(make_program):
    service, _, base, _, (first, _) = await make_program("INDIVIDUAL", "ENROLLMENT")
    await backdate_sessions(service.db)
    await freeze(service, first, minutes_ago=60)
    target = (await by_member(service, first))[base.id]

    await service.record_exposure(
        target.id,
        ExposureInput(stage="BLOTTER", at=ago(hours=3)),
        RECORDER,
        admin=False,
    )

    assert target.presented_at is not None


@pytest.mark.asyncio
async def test_a_shared_group_holdout_is_judged_against_the_last_checkpoint(
    make_program,
):
    """The group gate opens at the LAST checkpoint, so evidence before it is refused."""
    service, _, _, holdout, (first, second) = await make_program("SHARED_GROUP")
    await backdate_sessions(service.db)
    await freeze(service, first, minutes_ago=120)
    await freeze(service, second, minutes_ago=30)
    target = (await by_member(service, first))[holdout.id]

    # After first's own checkpoint (120 min) but before the group's last (30 min).
    with pytest.raises(HTTPException) as error:
        await service.record_exposure(
            target.id,
            ExposureInput(stage="BLOTTER", at=ago(minutes=60)),
            RECORDER,
            admin=False,
        )
    assert error.value.status_code == 422
    await service.record_exposure(
        target.id,
        ExposureInput(stage="BLOTTER", at=ago(minutes=10)),
        RECORDER,
        admin=False,
    )
    assert target.presented_at is not None


@pytest.mark.asyncio
async def test_a_holdout_ranking_time_before_the_checkpoint_is_refused(make_program):
    service, _, _, holdout, (first, _) = await make_program("INDIVIDUAL", "ENROLLMENT")
    await backdate_sessions(service.db)
    await freeze(service, first, minutes_ago=60)
    target = (await by_member(service, first))[holdout.id]
    session_id = target.session_id
    capture = CaptureService(service.db)

    with pytest.raises(HTTPException) as error:
        await capture.record_ranking(
            session_id,
            RankingInput(
                stage="BLOTTER", response_status="skipped", ranked_at=ago(hours=3)
            ),
            RECORDER,
            admin=False,
        )
    assert error.value.status_code == 422
    assert "The ranking time" in error.value.detail
    await service.observe(
        target.id,
        ResponseInput(stage="BLOTTER", detected=False, intensity=0),
        RECORDER,
        admin=False,
    )
    event, _ = await capture.record_ranking(
        session_id,
        RankingInput(
            stage="BLOTTER", response_status="skipped", ranked_at=ago(minutes=5)
        ),
        RECORDER,
        admin=False,
    )
    assert event is not None


# --- D: SHARED_GROUP reveals only as a household ---------------------------


@pytest.mark.asyncio
async def test_setting_shared_group_forces_household_reveal(async_session):
    service = CalibrationService(async_session)
    program = Program(name="Mode", version="1", reveal_policy="ENROLLMENT")
    async_session.add(program)
    await async_session.flush()

    changed = await service.set_blotter_mode(program.id, "SHARED_GROUP")

    assert changed.blotter_mode == "SHARED_GROUP"
    assert changed.reveal_policy == HOUSEHOLD
    # Going back to individual blotters does not silently weaken the reveal.
    back = await service.set_blotter_mode(program.id, "INDIVIDUAL")
    assert back.reveal_policy == HOUSEHOLD


@pytest.mark.asyncio
async def test_individual_mode_leaves_the_reveal_policy_alone(async_session):
    service = CalibrationService(async_session)
    program = Program(name="Mode2", version="1", reveal_policy="ENROLLMENT")
    async_session.add(program)
    await async_session.flush()

    changed = await service.set_blotter_mode(program.id, "INDIVIDUAL")

    assert changed.reveal_policy == "ENROLLMENT"


def test_a_program_input_couples_shared_group_to_the_household_reveal():
    assert ProgramInput(name="x", version="1").reveal_policy == "ENROLLMENT"
    defaulted = ProgramInput(name="x", version="1", blotter_mode="SHARED_GROUP")
    assert defaulted.reveal_policy == "HOUSEHOLD"
    explicit = ProgramInput(
        name="x", version="1", blotter_mode="SHARED_GROUP", reveal_policy="HOUSEHOLD"
    )
    assert explicit.reveal_policy == "HOUSEHOLD"
    with pytest.raises(ValidationError, match="reveals every evaluator together"):
        ProgramInput(
            name="x",
            version="1",
            blotter_mode="SHARED_GROUP",
            reveal_policy="ENROLLMENT",
        )
    individual = ProgramInput(
        name="x", version="1", blotter_mode="INDIVIDUAL", reveal_policy="ENROLLMENT"
    )
    assert individual.reveal_policy == "ENROLLMENT"


@pytest.mark.asyncio
async def test_shared_group_with_stored_enrollment_policy_still_refuses_own_reveal(
    make_program,
):
    """Data that somehow holds ENROLLMENT must not allow a per-evaluator reveal."""
    service, program, _, _, (first, _) = await make_program(
        "SHARED_GROUP", "ENROLLMENT"
    )
    gate = DisclosureGate(service.db)

    assert program.reveal_policy == "ENROLLMENT"
    assert effective_reveal_policy(program) == HOUSEHOLD
    assert await gate.policy(program.id) == HOUSEHOLD
    with pytest.raises(HTTPException) as error:
        await service.reveal(first.id, "manager", admin=True)
    assert error.value.status_code == 409
    assert error.value.detail == HOUSEHOLD_ONLY
    assert first.revealed_at is None
    # The household path treats the stored ENROLLMENT row as HOUSEHOLD too.
    with pytest.raises(HTTPException, match="evaluators still have"):
        await gate.reveal_household(program.id, "manager")
    view = await service.participant_view(first)
    assert view["reveal_policy"] == HOUSEHOLD


def test_an_individual_enrollment_policy_is_unchanged():
    program = Program(name="p", version="1", reveal_policy="ENROLLMENT")
    program.blotter_mode = "INDIVIDUAL"
    assert effective_reveal_policy(program) == "ENROLLMENT"


@pytest.mark.asyncio
async def test_enrollments_stay_enrolled_in_the_fixture(make_program):
    """Guard the fixture: two enrollments on one program."""
    service, program, *_ = await make_program("SHARED_GROUP")
    count = len(
        list(
            await service.db.scalars(
                select(Enrollment).where(Enrollment.program_id == program.id)
            )
        )
    )
    assert count == 2
