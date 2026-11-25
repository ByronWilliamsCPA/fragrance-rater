"""Shared-session enrollment: six evaluators on one template (F1 decisions 3, 7)."""

import secrets
from collections import Counter
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import EnrollmentInput, MembershipInput
from fragrance_rater.services.calibration_service import (
    RANDOMIZATION_ALGORITHM,
    CalibrationService,
)
from fragrance_rater.services.shared_triples import (
    SHARED_TRIPLES_ALGORITHM,
    parse_randomization_record,
)

SHARED = SHARED_TRIPLES_ALGORITHM


@pytest_asyncio.fixture
async def f1_program(async_session):
    """An active program of 33 baseline, 6 hidden repeats, and 10 holdouts."""
    service = CalibrationService(async_session)
    program = Program(name="F1 baseline", version="shared-1")
    async_session.add(program)
    for index in range(43):
        async_session.add(
            Fragrance(
                id=f"version-{index:02d}",
                name=f"Concealed {index:02d}",
                brand="Concealed House",
                concentration="EDP",
                gender_target="unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="manual",
            )
        )
    for index in range(7):
        async_session.add(Reviewer(id=f"evaluator-{index}", name=f"Evaluator {index}"))
    await async_session.flush()
    originals = []
    for index in range(33):
        member = await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=f"version-{index:02d}",
                role="UNIVERSAL_BASELINE",
                identity_evidence="Verified label",
                selection={"persistent_or_animalic": "true"} if index == 32 else {},
            ),
        )
        originals.append(member)
    for original in originals[:6]:
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=original.fragrance_id,
                role="HIDDEN_REPEAT",
                repeat_of_id=original.id,
                identity_evidence="Same decant",
            ),
        )
    for index in range(33, 43):
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=f"version-{index:02d}",
                role="HOLDOUT",
                identity_evidence="Verified label",
            ),
        )
    program.status = "active"
    await async_session.flush()
    return service, program


def shared_input(reviewer: str, **extra) -> EnrollmentInput:
    return EnrollmentInput(
        reviewer_id=reviewer,
        recorder_usernames=["facilitator"],
        randomization_algorithm=SHARED,
        **extra,
    )


async def sessions_of(service, enrollment) -> list[list[Presentation]]:
    grouped: dict[str, list[Presentation]] = {}
    for row in await service.presentations(enrollment.id):
        grouped.setdefault(row.session_id, []).append(row)
    return list(grouped.values())


async def enroll_six(service, program):
    return [
        await service.enroll(program.id, shared_input(f"evaluator-{k}"))
        for k in range(6)
    ]


@pytest.mark.asyncio
async def test_six_evaluators_share_sessions_with_balanced_rotation(f1_program):
    service, program = f1_program
    enrollments = await enroll_six(service, program)
    schedules = [await sessions_of(service, e) for e in enrollments]
    compositions = [
        [sorted(p.membership_id for p in s) for s in sch] for sch in schedules
    ]
    assert all(c == compositions[0] for c in compositions)
    assert [len(s) for s in schedules[0]] == [3] * 13 + [3, 3, 3, 1]
    for index, session in enumerate(compositions[0]):
        if len(session) < 3:
            continue
        for position in range(3):
            counts = Counter(sch[index][position].membership_id for sch in schedules)
            assert counts == dict.fromkeys(session, 2)
    for schedule in schedules:
        flat = [p for s in schedule for p in s]
        assert all(p.intended_position == p.position for p in flat)
        positions = Counter(p.position for s in schedule[:13] for p in s)
        assert positions == {1: 13, 2: 13, 3: 13}


@pytest.mark.asyncio
async def test_records_rotation_and_one_template_digest(f1_program):
    service, program = f1_program
    enrollments = await enroll_six(service, program)
    records = [parse_randomization_record(e.randomization_seed) for e in enrollments]
    assert [r[0] for r in records] == list(range(6))
    assert len({r[1] for r in records}) == 1
    assert len({r[2] for r in records}) == 1
    assert records[0][2] is not None
    assert all(e.randomization_algorithm == SHARED for e in enrollments)


@pytest.mark.asyncio
async def test_codes_are_random_unique_and_evaluator_specific(f1_program):
    service, program = f1_program
    enrollments = await enroll_six(service, program)
    codes = [
        p.blind_code for e in enrollments for p in await service.presentations(e.id)
    ]
    assert len(codes) == 6 * 49
    assert len(set(codes)) == len(codes)
    assert all(len(c) == 8 and c == c.upper() and int(c, 16) >= 0 for c in codes)
    assert not any(c.startswith("E0") and "-S" in c for c in codes)


@pytest.mark.asyncio
async def test_holdouts_last_and_repeats_separated(f1_program):
    service, program = f1_program
    enrollments = await enroll_six(service, program)
    members = {
        m.id: m
        for m in await service.db.scalars(
            select(Membership).where(Membership.program_id == program.id)
        )
    }
    for enrollment in enrollments:
        flat = [
            p.membership_id for s in await sessions_of(service, enrollment) for p in s
        ]
        roles = [members[mid].role for mid in flat]
        assert roles[-10:] == ["HOLDOUT"] * 10
        assert "HOLDOUT" not in roles[:-10]
        for mid, member in members.items():
            if member.repeat_of_id:
                assert flat.index(mid) - flat.index(member.repeat_of_id) >= 6


@pytest.mark.asyncio
async def test_persistent_limit_holds_for_supplied_and_flagged_stimuli(f1_program):
    service, program = f1_program
    baseline = list(
        await service.db.scalars(
            select(Membership.id)
            .where(
                Membership.program_id == program.id,
                Membership.role == "UNIVERSAL_BASELINE",
            )
            .order_by(Membership.fragrance_id)
        )
    )
    enrollment = await service.enroll(
        program.id, shared_input("evaluator-0", persistent_membership_ids=baseline[:4])
    )
    flagged = await service.db.scalar(
        select(Membership.id).where(Membership.fragrance_id == "version-32")
    )
    persistent = set(baseline[:4]) | {flagged}
    # Hidden repeats of a persistent original are the same juice.
    persistent |= set(
        await service.db.scalars(
            select(Membership.id).where(Membership.repeat_of_id.in_(persistent))
        )
    )
    for session in await sessions_of(service, enrollment):
        assert len(persistent & {p.membership_id for p in session}) <= 1


@pytest.mark.asyncio
async def test_unknown_persistent_stimulus_is_rejected(f1_program):
    service, program = f1_program
    with pytest.raises(HTTPException, match="persistent stimulus") as error:
        await service.enroll(
            program.id, shared_input("evaluator-0", persistent_membership_ids=["nope"])
        )
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_supplied_template_is_used_and_later_ones_must_match(f1_program):
    service, program = f1_program
    template, *_ = await service.shared_template(
        program.id, shared_input("evaluator-0")
    )
    first = await service.enroll(
        program.id, shared_input("evaluator-0", session_template=template)
    )
    assert parse_randomization_record(first.randomization_seed)[2] is None
    composition = [
        sorted(p.membership_id for p in s) for s in await sessions_of(service, first)
    ]
    assert composition == [sorted(s) for s in template]
    second = await service.enroll(
        program.id, shared_input("evaluator-1", session_template=template)
    )
    assert parse_randomization_record(second.randomization_seed)[0] == 1
    reordered = [template[1], template[0], *template[2:]]
    with pytest.raises(HTTPException, match="differs") as error:
        await service.enroll(
            program.id, shared_input("evaluator-2", session_template=reordered)
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_invalid_supplied_template_is_rejected(f1_program):
    service, program = f1_program
    template, *_ = await service.shared_template(
        program.id, shared_input("evaluator-0")
    )
    with pytest.raises(HTTPException, match="last block") as error:
        await service.enroll(
            program.id,
            shared_input(
                "evaluator-0", session_template=[template[-1], *template[:-1]]
            ),
        )
    assert error.value.status_code == 422
    assert await service.db.scalar(select(Enrollment.id)) is None


@pytest.mark.asyncio
async def test_tampered_recorded_template_fails_loudly(f1_program):
    service, program = f1_program
    first = await service.enroll(program.id, shared_input("evaluator-0"))
    sessions = await sessions_of(service, first)
    a, b = sessions[0][0], sessions[1][0]
    a.membership_id, b.membership_id = b.membership_id, a.membership_id
    await service.db.flush()
    with pytest.raises(HTTPException, match="inconsistent"):
        await service.enroll(program.id, shared_input("evaluator-1"))


@pytest.mark.asyncio
async def test_program_cannot_mix_randomization_algorithms(f1_program):
    service, program = f1_program
    await service.enroll(program.id, shared_input("evaluator-0"))
    with pytest.raises(HTTPException, match="same randomization"):
        await service.enroll(
            program.id,
            EnrollmentInput(
                reviewer_id="evaluator-1", recorder_usernames=["facilitator"]
            ),
        )


@pytest.mark.asyncio
async def test_shared_enrollment_refused_after_independent_ones(f1_program):
    service, program = f1_program
    legacy = await service.enroll(
        program.id,
        EnrollmentInput(reviewer_id="evaluator-0", recorder_usernames=["facilitator"]),
    )
    assert legacy.randomization_algorithm == RANDOMIZATION_ALGORITHM
    assert legacy.randomization_seed is None
    with pytest.raises(HTTPException, match="same randomization"):
        await service.enroll(program.id, shared_input("evaluator-1"))


@pytest.mark.asyncio
async def test_colliding_codes_are_redrawn(f1_program):
    service, program = f1_program
    first = await service.enroll(program.id, shared_input("evaluator-0"))
    taken = (await service.presentations(first.id))[0].blind_code
    real = secrets.token_hex
    calls = {"n": 0}

    def colliding(nbytes):
        calls["n"] += 1
        return taken.lower() if calls["n"] == 1 else real(nbytes)

    with patch(
        "fragrance_rater.services.calibration_service.secrets.token_hex", colliding
    ):
        second = await service.enroll(program.id, shared_input("evaluator-1"))
    codes = [p.blind_code for p in await service.presentations(second.id)]
    assert taken not in codes
    assert len(set(codes)) == 49


@pytest.mark.asyncio
async def test_small_program_that_cannot_separate_repeats_fails(async_session):
    service = CalibrationService(async_session)
    program = Program(name="Tiny", version="1")
    async_session.add(program)
    async_session.add(
        Fragrance(
            id="tiny-0",
            name="Tiny",
            brand="House",
            concentration="EDT",
            gender_target="unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
    )
    async_session.add(Reviewer(id="tiny-reviewer", name="Tiny"))
    await async_session.flush()
    base = await service.add_member(
        program.id,
        MembershipInput(
            fragrance_id="tiny-0", role="UNIVERSAL_BASELINE", identity_evidence="ok"
        ),
    )
    await service.add_member(
        program.id,
        MembershipInput(
            fragrance_id="tiny-0",
            role="HIDDEN_REPEAT",
            repeat_of_id=base.id,
            identity_evidence="ok",
        ),
    )
    program.status = "active"
    await async_session.flush()
    with pytest.raises(HTTPException, match="Could not build") as error:
        await service.enroll(program.id, shared_input("tiny-reviewer"))
    assert error.value.status_code == 422
    assert await async_session.scalar(select(CalibrationSession.id)) is None


def test_shared_triples_reject_standard_labels():
    with pytest.raises(ValidationError, match="random blind codes"):
        shared_input("evaluator-0", label_scheme="standard")
    assert not shared_input("evaluator-0").uses_standard_labels
    assert not shared_input("evaluator-0", label_scheme="random").uses_standard_labels


def test_template_options_need_the_shared_algorithm():
    with pytest.raises(ValidationError, match="apply only"):
        EnrollmentInput(
            reviewer_id="r",
            recorder_usernames=["x"],
            session_template=[["a"]],
        )
    with pytest.raises(ValidationError, match="apply only"):
        EnrollmentInput(
            reviewer_id="r", recorder_usernames=["x"], persistent_membership_ids=["a"]
        )
    default = EnrollmentInput(reviewer_id="r", recorder_usernames=["x"])
    assert default.randomization_algorithm == RANDOMIZATION_ALGORITHM
    assert default.uses_standard_labels
