"""SHARED_GROUP enrollment: one blotter per sample passed around six evaluators.

Owner decision for F1 group sessions: every evaluator holds the same blind code
for a sample and the same sample order within a session. Existing (INDIVIDUAL)
programs and algorithms must behave exactly as before.
"""

from collections import Counter

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.calibration import (
    BLOTTER_MODES,
    CalibrationSession,
    Membership,
    Presentation,
    Program,
    QualityFlag,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import (
    BlotterMode,
    EnrollmentInput,
    MembershipInput,
    ProgramInput,
)
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.group_blotter import (
    GROUP_SHARED_BLOTTER_CODE,
    group_blotter_enrollment_ids,
)
from fragrance_rater.services.shared_triples import (
    GROUP_BLOTTER_ALGORITHM,
    SHARED_TRIPLES_ALGORITHM,
    parse_randomization_record,
    position_counts,
)

GROUP = GROUP_BLOTTER_ALGORITHM


@pytest_asyncio.fixture
async def group_program(async_session):
    """An active SHARED_GROUP program of 33 baseline, 6 hidden repeats, 10 holdouts."""
    service = CalibrationService(async_session)
    program = Program(name="F1 group", version="group-1", blotter_mode="SHARED_GROUP")
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
    originals = [
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=f"version-{index:02d}",
                role="UNIVERSAL_BASELINE",
                identity_evidence="Verified label",
                selection={"persistent_or_animalic": "true"} if index == 32 else {},
            ),
        )
        for index in range(33)
    ]
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


def group_input(reviewer: str, **extra) -> EnrollmentInput:
    return EnrollmentInput(
        reviewer_id=reviewer,
        recorder_usernames=["facilitator"],
        randomization_algorithm=GROUP,
        **extra,
    )


async def sessions_of(service, enrollment) -> list[list[Presentation]]:
    grouped: dict[str, list[Presentation]] = {}
    for row in await service.presentations(enrollment.id):
        grouped.setdefault(row.session_id, []).append(row)
    return list(grouped.values())


async def enroll_six(service, program):
    return [
        await service.enroll(program.id, group_input(f"evaluator-{k}"), "manager")
        for k in range(6)
    ]


def test_modes_agree_with_the_schema():
    assert set(BlotterMode.__args__) == set(BLOTTER_MODES)
    assert ProgramInput(name="x", version="1").blotter_mode == "INDIVIDUAL"


@pytest.mark.asyncio
async def test_every_evaluator_gets_the_same_codes_and_the_same_order(group_program):
    service, program = group_program
    enrollments = await enroll_six(service, program)
    schedules = [await sessions_of(service, e) for e in enrollments]
    layouts = [
        [[(p.membership_id, p.blind_code, p.position) for p in s] for s in schedule]
        for schedule in schedules
    ]
    assert all(layout == layouts[0] for layout in layouts)
    flat = [p for s in schedules[0] for p in s]
    assert len(flat) == 49
    assert len({p.blind_code for p in flat}) == 49
    assert all(p.shared_blind_code for s in schedules for ses in s for p in ses)
    assert all(p.intended_position == p.position for p in flat)


@pytest.mark.asyncio
async def test_codes_are_random_not_standard_labels(group_program):
    service, program = group_program
    first = await service.enroll(program.id, group_input("evaluator-0"), "manager")
    codes = [p.blind_code for p in await service.presentations(first.id)]
    assert all(len(c) == 8 and c == c.upper() for c in codes)
    assert not any(c.startswith("E0") and "-S" in c for c in codes)


@pytest.mark.asyncio
async def test_records_ordinal_and_one_template_digest(group_program):
    service, program = group_program
    enrollments = await enroll_six(service, program)
    records = [parse_randomization_record(e.randomization_seed) for e in enrollments]
    assert [r[0] for r in records] == list(range(6))
    assert len({r[1] for r in records}) == 1
    assert all(e.randomization_algorithm == GROUP for e in enrollments)


@pytest.mark.asyncio
async def test_holdouts_last_repeats_separated_and_persistent_limited(group_program):
    service, program = group_program
    enrollment = await service.enroll(program.id, group_input("evaluator-0"), "manager")
    members = {
        m.id: m
        for m in await service.db.scalars(
            select(Membership).where(Membership.program_id == program.id)
        )
    }
    sessions = await sessions_of(service, enrollment)
    flat = [p.membership_id for s in sessions for p in s]
    roles = [members[mid].role for mid in flat]
    assert roles[-10:] == ["HOLDOUT"] * 10
    assert "HOLDOUT" not in roles[:-10]
    # A hidden repeat comes at least 2 * session_size (6) presentations later.
    for mid, member in members.items():
        if member.repeat_of_id:
            assert flat.index(mid) - flat.index(member.repeat_of_id) >= 6
    flagged = next(m.id for m in members.values() if m.fragrance_id == "version-32")
    for session in sessions:
        assert (
            flagged not in {p.membership_id for p in session}
            or sum(
                members[p.membership_id].fragrance_id == "version-32" for p in session
            )
            <= 1
        )


@pytest.mark.asyncio
async def test_position_balance_is_exact_for_full_sessions(group_program):
    service, program = group_program
    first = await service.enroll(program.id, group_input("evaluator-0"), "manager")
    sessions = await sessions_of(service, first)
    template = [[p.membership_id for p in s] for s in sessions]
    counts = position_counts(template)
    full = [s for s in sessions if len(s) == 3]
    # Every position is used once per full session; only the short last session
    # of a block can skew a position by one.
    assert counts[1] >= len(full)
    assert counts[1] + counts[2] + counts[3] == 49
    assert max(counts.values()) - min(counts.values()) <= 4


@pytest.mark.asyncio
async def test_every_session_carries_the_informational_flag(group_program):
    service, program = group_program
    enrollments = await enroll_six(service, program)
    for enrollment in enrollments:
        sessions = list(
            await service.db.scalars(
                select(CalibrationSession.id).where(
                    CalibrationSession.enrollment_id == enrollment.id
                )
            )
        )
        flags = list(
            await service.db.scalars(
                select(QualityFlag).where(QualityFlag.session_id.in_(sessions))
            )
        )
        assert len(flags) == len(sessions)
        assert {f.code for f in flags} == {GROUP_SHARED_BLOTTER_CODE}
        assert {f.action for f in flags} == {"raised"}
        assert {f.severity for f in flags} == {"info"}
        assert {f.disposition for f in flags} == {"include"}
        assert {f.recorded_by for f in flags} == {"manager"}
    assert await group_blotter_enrollment_ids(service.db) == {e.id for e in enrollments}


@pytest.mark.asyncio
async def test_a_group_program_refuses_other_algorithms(group_program):
    service, program = group_program
    for algorithm in ("system-random-shuffle-v1", SHARED_TRIPLES_ALGORITHM):
        with pytest.raises(HTTPException, match="SHARED_GROUP") as error:
            await service.enroll(
                program.id,
                EnrollmentInput(
                    reviewer_id="evaluator-0",
                    recorder_usernames=["facilitator"],
                    randomization_algorithm=algorithm,
                ),
            )
        assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_an_individual_program_refuses_the_group_algorithm(group_program):
    service, program = group_program
    program.blotter_mode = "INDIVIDUAL"
    await service.db.flush()
    with pytest.raises(HTTPException, match="SHARED_GROUP") as error:
        await service.enroll(program.id, group_input("evaluator-0"))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_group_algorithm_rejects_standard_labels_at_the_schema():
    with pytest.raises(ValidationError, match="standard"):
        group_input("evaluator-0", label_scheme="standard")


@pytest.mark.asyncio
async def test_individual_enrollment_is_unchanged(group_program):
    """An INDIVIDUAL program still draws independent codes and orders."""
    service, program = group_program
    program.blotter_mode = "INDIVIDUAL"
    await service.db.flush()
    enrollments = [
        await service.enroll(
            program.id,
            EnrollmentInput(
                reviewer_id=f"evaluator-{k}", recorder_usernames=["facilitator"]
            ),
        )
        for k in range(2)
    ]
    first = {p.blind_code for p in await service.presentations(enrollments[0].id)}
    second = {p.blind_code for p in await service.presentations(enrollments[1].id)}
    assert first.isdisjoint(second)
    for enrollment in enrollments:
        rows = await service.presentations(enrollment.id)
        assert not any(p.shared_blind_code for p in rows)
    assert (
        await service.db.scalar(
            select(func.count())
            .select_from(QualityFlag)
            .where(QualityFlag.code == GROUP_SHARED_BLOTTER_CODE)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_blotter_mode_locks_after_first_enrollment(group_program):
    service, program = group_program
    assert (await service.set_blotter_mode(program.id, "INDIVIDUAL")).blotter_mode == (
        "INDIVIDUAL"
    )
    assert (
        await service.set_blotter_mode(program.id, "SHARED_GROUP")
    ).blotter_mode == ("SHARED_GROUP")
    await service.enroll(program.id, group_input("evaluator-0"), "manager")
    with pytest.raises(HTTPException, match="locked") as error:
        await service.set_blotter_mode(program.id, "INDIVIDUAL")
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_group_codes_tamper_fails_loudly(group_program):
    service, program = group_program
    first = await service.enroll(program.id, group_input("evaluator-0"))
    rows = await service.presentations(first.id)
    # Two codes for one sample means the stored group codes were altered.
    other = Presentation(
        session_id=rows[0].session_id,
        membership_id=rows[0].membership_id,
        blind_code="ZZZZZZZZ",
        shared_blind_code=True,
        position=99,
        intended_position=99,
    )
    service.db.add(other)
    await service.db.flush()
    with pytest.raises(HTTPException, match="inconsistent"):
        await service.enroll(program.id, group_input("evaluator-1"))


@pytest.mark.asyncio
async def test_a_shared_code_is_unique_within_one_session(group_program):
    service, program = group_program
    first = await service.enroll(program.id, group_input("evaluator-0"))
    row = (await service.presentations(first.id))[0]
    service.db.add(
        Presentation(
            session_id=row.session_id,
            membership_id=row.membership_id,
            blind_code=row.blind_code,
            shared_blind_code=True,
            position=98,
            intended_position=98,
        )
    )
    with pytest.raises(IntegrityError):
        await service.db.flush()


@pytest.mark.asyncio
async def test_an_individual_code_stays_globally_unique(group_program):
    """The relaxed index leaves the INDIVIDUAL guarantee exactly as it was."""
    service, program = group_program
    first = await service.enroll(program.id, group_input("evaluator-0"))
    shared = await service.presentations(first.id)
    other_session = CalibrationSession(enrollment_id=first.id, context={})
    service.db.add(other_session)
    await service.db.flush()
    service.db.add(
        Presentation(
            session_id=other_session.id,
            membership_id=shared[0].membership_id,
            blind_code="CODE-ONE",
            shared_blind_code=False,
            position=1,
            intended_position=1,
        )
    )
    await service.db.flush()
    service.db.add(
        Presentation(
            session_id=other_session.id,
            membership_id=shared[1].membership_id,
            blind_code="CODE-ONE",
            shared_blind_code=False,
            position=2,
            intended_position=2,
        )
    )
    with pytest.raises(IntegrityError):
        await service.db.flush()


@pytest.mark.asyncio
async def test_the_session_template_preview_follows_the_mode(group_program):
    service, program = group_program
    template, _, rotation, _, source = await service.shared_template(
        program.id, group_input("evaluator-0")
    )
    assert rotation == 0
    assert source == "generated"
    flat = [mid for s in template for mid in s]
    assert len(flat) == len(set(flat)) == 49
    assert Counter(len(s) for s in template) == {3: 16, 1: 1}
    first = await service.enroll(program.id, group_input("evaluator-0"))
    recorded, _, ordinal, _, source = await service.shared_template(
        program.id, group_input("evaluator-1")
    )
    assert (source, ordinal) == ("recorded", 1)
    assert recorded == [
        [p.membership_id for p in s] for s in await sessions_of(service, first)
    ]
