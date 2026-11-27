"""Shared label enrollment: one blind code per physical sample (F1, 2026-11-27).

``label_scheme="shared"`` on the shared-triples algorithm gives every
evaluator the same blind code per membership (the atomizer label), written
with ``shared_blind_code`` true. The first enrollment supplies the codes; later
enrollments inherit them exactly.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select

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
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.shared_triples import (
    GROUP_BLOTTER_ALGORITHM,
    SHARED_TRIPLES_ALGORITHM,
)

SHARED = SHARED_TRIPLES_ALGORITHM


async def build_program(
    async_session,
    *,
    name: str = "F1 shared labels",
    reveal_policy: str = "HOUSEHOLD",
    fragrance_prefix: str = "version",
    baseline: int = 33,
    repeats: int = 6,
    holdouts: int = 10,
    reviewers: int = 7,
):
    """An active F1-shaped program (33 baseline, 6 repeats, 10 holdouts)."""
    service = CalibrationService(async_session)
    program = Program(name=name, version="shared-label", reveal_policy=reveal_policy)
    async_session.add(program)
    for index in range(baseline + holdouts):
        async_session.add(
            Fragrance(
                id=f"{fragrance_prefix}-{index:02d}",
                name=f"Concealed {fragrance_prefix} {index:02d}",
                brand="Concealed House",
                concentration="EDP",
                gender_target="unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="manual",
            )
        )
    for index in range(reviewers):
        if await async_session.get(Reviewer, f"evaluator-{index}") is None:
            async_session.add(
                Reviewer(id=f"evaluator-{index}", name=f"Evaluator {index}")
            )
    await async_session.flush()
    originals = [
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=f"{fragrance_prefix}-{index:02d}",
                role="UNIVERSAL_BASELINE",
                identity_evidence="Verified label",
            ),
        )
        for index in range(baseline)
    ]
    for original in originals[:repeats]:
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=original.fragrance_id,
                role="HIDDEN_REPEAT",
                repeat_of_id=original.id,
                identity_evidence="Same decant",
            ),
        )
    for index in range(baseline, baseline + holdouts):
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=f"{fragrance_prefix}-{index:02d}",
                role="HOLDOUT",
                identity_evidence="Verified label",
            ),
        )
    program.status = "active"
    await async_session.flush()
    return service, program


@pytest_asyncio.fixture
async def f1_program(async_session):
    return await build_program(async_session)


async def label_codes(async_session, program) -> dict[str, str]:
    """Atomizer-style labels: B.. for everything but holdouts, H.. for those."""
    members = list(
        await async_session.scalars(
            select(Membership)
            .where(Membership.program_id == program.id)
            .order_by(Membership.id)
        )
    )
    codes: dict[str, str] = {}
    counts = {"B": 0, "H": 0}
    for member in members:
        letter = "H" if member.role == "HOLDOUT" else "B"
        counts[letter] += 1
        codes[member.id] = f"{letter}{counts[letter]:02d}"
    return codes


def shared_input(reviewer: str, **extra) -> EnrollmentInput:
    return EnrollmentInput(
        reviewer_id=reviewer,
        recorder_usernames=["facilitator"],
        randomization_algorithm=SHARED,
        label_scheme="shared",
        **extra,
    )


async def code_map(async_session, enrollment) -> dict[str, str]:
    rows = await async_session.execute(
        select(Presentation.membership_id, Presentation.blind_code)
        .join(CalibrationSession)
        .where(CalibrationSession.enrollment_id == enrollment.id)
    )
    return dict(rows.all())


async def enrollment_count(async_session) -> int:
    return await async_session.scalar(select(func.count()).select_from(Enrollment))


# Schema ------------------------------------------------------------------


def test_shared_scheme_is_valid_only_with_the_shared_triples_algorithm():
    assert shared_input("r", membership_codes={"a": "B01"}).label_scheme == "shared"
    assert not shared_input("r").uses_standard_labels
    with pytest.raises(ValidationError, match="shared-triples-latin-rotation-v1"):
        EnrollmentInput(
            reviewer_id="r", recorder_usernames=["x"], label_scheme="shared"
        )
    with pytest.raises(ValidationError, match="shared-triples-latin-rotation-v1"):
        EnrollmentInput(
            reviewer_id="r",
            recorder_usernames=["x"],
            label_scheme="shared",
            randomization_algorithm=GROUP_BLOTTER_ALGORITHM,
        )


def test_standard_labels_are_still_rejected_with_shared_algorithms():
    with pytest.raises(ValidationError, match="random blind codes"):
        EnrollmentInput(
            reviewer_id="r",
            recorder_usernames=["x"],
            randomization_algorithm=SHARED,
            label_scheme="standard",
        )


def test_membership_codes_need_the_shared_scheme():
    with pytest.raises(ValidationError, match="membership_codes"):
        EnrollmentInput(
            reviewer_id="r",
            recorder_usernames=["x"],
            randomization_algorithm=SHARED,
            label_scheme="random",
            membership_codes={"a": "B01"},
        )
    with pytest.raises(ValidationError, match="membership_codes"):
        EnrollmentInput(
            reviewer_id="r",
            recorder_usernames=["x"],
            membership_codes={"a": "B01"},
        )


@pytest.mark.parametrize(
    "codes",
    [
        {"a": "B01", "b": "B01"},  # duplicate
        {"a": ""},  # empty
        {"a": " B01"},  # not trimmed
        {"a": "B01 "},
        {"a": "b01"},  # not upper-case
        {"a": "B" * 25},  # over String(24)
        {"a": "B_01"},  # outside letters, digits, dash
        {"a": "B 01"},
        {},  # nothing to assign
    ],
)
def test_malformed_membership_codes_are_rejected(codes):
    with pytest.raises(ValidationError):
        shared_input("r", membership_codes=codes)


def test_a_code_may_use_dashes_and_fill_the_column():
    assert shared_input("r", membership_codes={"a": "B-" + "1" * 22})


# Service -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_enrollment_uses_the_supplied_codes_and_flags_them(
    async_session, f1_program
):
    service, program = f1_program
    codes = await label_codes(async_session, program)
    enrollment = await service.enroll(
        program.id, shared_input("evaluator-0", membership_codes=codes)
    )
    assert await code_map(async_session, enrollment) == codes
    rows = await service.presentations(enrollment.id)
    assert len(rows) == 49
    assert all(row.shared_blind_code for row in rows)
    # Hidden repeats are their own memberships and carry their own codes.
    assert len(set(codes.values())) == len(codes) == 49


@pytest.mark.asyncio
async def test_a_seventh_evaluator_inherits_every_code_from_six_shared_enrollments(
    async_session, f1_program
):
    """The case that matters for F1: an evaluator added after six enrolled."""
    service, program = f1_program
    codes = await label_codes(async_session, program)
    first = await service.enroll(
        program.id, shared_input("evaluator-0", membership_codes=codes)
    )
    enrollments = [first]
    enrollments.extend(
        [
            await service.enroll(program.id, shared_input(f"evaluator-{k}"))
            for k in range(1, 6)
        ]
    )
    seventh = await service.enroll(program.id, shared_input("evaluator-6"))
    for enrollment in [*enrollments, seventh]:
        assert await code_map(async_session, enrollment) == codes
        assert all(
            r.shared_blind_code for r in await service.presentations(enrollment.id)
        )
    # The rotation still advances: shared codes do not freeze the order.
    orders = [
        [r.membership_id for r in await service.presentations(e.id)]
        for e in (first, enrollments[1])
    ]
    assert orders[0] != orders[1]


@pytest.mark.asyncio
async def test_a_code_never_repeats_inside_one_session_or_enrollment(
    async_session, f1_program
):
    service, program = f1_program
    codes = await label_codes(async_session, program)
    await service.enroll(
        program.id, shared_input("evaluator-0", membership_codes=codes)
    )
    second = await service.enroll(program.id, shared_input("evaluator-1"))
    rows = await service.presentations(second.id)
    per_session: dict[str, list[str]] = {}
    for row in rows:
        per_session.setdefault(row.session_id, []).append(row.blind_code)
    assert all(len(set(c)) == len(c) for c in per_session.values())
    assert len({row.blind_code for row in rows}) == len(rows)
    # The database constraint agrees: flushing the whole schedule did not trip
    # UNIQUE(session_id, blind_code) or the individual-code partial index.
    total = await async_session.scalar(select(func.count()).select_from(Presentation))
    assert total == 2 * 49


@pytest.mark.asyncio
async def test_first_enrollment_without_codes_is_refused_and_leaves_nothing(
    async_session, f1_program
):
    service, program = f1_program
    with pytest.raises(HTTPException, match="membership_codes") as error:
        await service.enroll(program.id, shared_input("evaluator-0"))
    assert error.value.status_code == 422
    assert await enrollment_count(async_session) == 0
    assert await async_session.scalar(select(CalibrationSession.id)) is None
    assert await async_session.scalar(select(Presentation.id)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing", "unknown", "empty_after_pop"])
async def test_codes_must_cover_exactly_the_programs_memberships(
    async_session, f1_program, fault
):
    service, program = f1_program
    codes = await label_codes(async_session, program)
    if fault == "missing":
        codes.pop(next(iter(codes)))
    elif fault == "unknown":
        codes["not-a-membership"] = "Z99"
    else:
        codes = {next(iter(codes)): "B01"}
    with pytest.raises(HTTPException) as error:
        await service.enroll(
            program.id, shared_input("evaluator-0", membership_codes=codes)
        )
    assert error.value.status_code == 422
    assert "every membership" in error.value.detail
    assert await enrollment_count(async_session) == 0
    assert await async_session.scalar(select(Presentation.id)) is None


@pytest.mark.asyncio
async def test_a_code_colliding_with_an_existing_individual_code_is_refused(
    async_session, f1_program
):
    service, program = f1_program
    other, other_program = await build_program(
        async_session,
        name="Independent",
        reveal_policy="ENROLLMENT",
        fragrance_prefix="other",
        baseline=2,
        repeats=0,
        holdouts=1,
    )
    legacy = await other.enroll(
        other_program.id,
        EnrollmentInput(reviewer_id="evaluator-6", recorder_usernames=["f"]),
    )
    taken = (await other.presentations(legacy.id))[0].blind_code
    assert not (await other.presentations(legacy.id))[0].shared_blind_code
    codes = await label_codes(async_session, program)
    codes[next(iter(codes))] = taken
    with pytest.raises(HTTPException, match="already used") as error:
        await service.enroll(
            program.id, shared_input("evaluator-0", membership_codes=codes)
        )
    assert error.value.status_code == 409
    assert (
        await async_session.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.program_id == program.id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_codes_supplied_later_must_equal_the_recorded_assignment(
    async_session, f1_program
):
    service, program = f1_program
    codes = await label_codes(async_session, program)
    await service.enroll(
        program.id, shared_input("evaluator-0", membership_codes=codes)
    )
    again = await service.enroll(
        program.id, shared_input("evaluator-1", membership_codes=codes)
    )
    assert await code_map(async_session, again) == codes
    changed = dict(codes)
    first, second = list(changed)[:2]
    changed[first], changed[second] = changed[second], changed[first]
    with pytest.raises(HTTPException, match="differ") as error:
        await service.enroll(
            program.id, shared_input("evaluator-2", membership_codes=changed)
        )
    assert error.value.status_code == 409
    assert await enrollment_count(async_session) == 2


@pytest.mark.asyncio
async def test_earlier_enrollments_that_disagree_are_refused_not_guessed(
    async_session, f1_program
):
    service, program = f1_program
    codes = await label_codes(async_session, program)
    first = await service.enroll(
        program.id, shared_input("evaluator-0", membership_codes=codes)
    )
    await service.enroll(program.id, shared_input("evaluator-1"))
    row = (await service.presentations(first.id))[0]
    row.blind_code = "TAMPERED"
    await async_session.flush()
    with pytest.raises(HTTPException, match="disagree") as error:
        await service.enroll(program.id, shared_input("evaluator-2"))
    assert error.value.status_code == 409
    assert await enrollment_count(async_session) == 2


@pytest.mark.asyncio
async def test_earlier_non_shared_codes_block_a_shared_enrollment(
    async_session, f1_program
):
    service, program = f1_program
    random_input = EnrollmentInput(
        reviewer_id="evaluator-0",
        recorder_usernames=["f"],
        randomization_algorithm=SHARED,
        label_scheme="random",
    )
    await service.enroll(program.id, random_input)
    codes = await label_codes(async_session, program)
    with pytest.raises(HTTPException, match="random blind codes") as error:
        await service.enroll(
            program.id, shared_input("evaluator-1", membership_codes=codes)
        )
    assert error.value.status_code == 409
    assert await enrollment_count(async_session) == 1


@pytest.mark.asyncio
async def test_random_codes_are_refused_once_shared_codes_exist(
    async_session, f1_program
):
    service, program = f1_program
    codes = await label_codes(async_session, program)
    await service.enroll(
        program.id, shared_input("evaluator-0", membership_codes=codes)
    )
    with pytest.raises(HTTPException, match="shared blind codes") as error:
        await service.enroll(
            program.id,
            EnrollmentInput(
                reviewer_id="evaluator-1",
                recorder_usernames=["f"],
                randomization_algorithm=SHARED,
                label_scheme="random",
            ),
        )
    assert error.value.status_code == 409
    assert await enrollment_count(async_session) == 1


@pytest.mark.asyncio
async def test_shared_scheme_requires_household_reveal(async_session):
    service, program = await build_program(async_session, reveal_policy="ENROLLMENT")
    codes = await label_codes(async_session, program)
    with pytest.raises(HTTPException, match="HOUSEHOLD") as error:
        await service.enroll(
            program.id, shared_input("evaluator-0", membership_codes=codes)
        )
    assert error.value.status_code == 409
    assert await enrollment_count(async_session) == 0
    # The same program still enrolls with random codes, as before.
    plain = await service.enroll(
        program.id,
        EnrollmentInput(
            reviewer_id="evaluator-0",
            recorder_usernames=["f"],
            randomization_algorithm=SHARED,
        ),
    )
    assert not any(r.shared_blind_code for r in await service.presentations(plain.id))


@pytest.mark.asyncio
async def test_the_random_path_is_unchanged(async_session, f1_program):
    service, program = f1_program
    enrollment = await service.enroll(
        program.id,
        EnrollmentInput(
            reviewer_id="evaluator-0",
            recorder_usernames=["f"],
            randomization_algorithm=SHARED,
        ),
    )
    rows = await service.presentations(enrollment.id)
    codes = [r.blind_code for r in rows]
    assert len(set(codes)) == 49
    assert all(len(c) == 8 and int(c, 16) >= 0 for c in codes)
    assert not any(r.shared_blind_code for r in rows)


@pytest.mark.asyncio
async def test_an_enrolled_reviewer_still_gets_409_and_no_partial_rows(
    async_session, f1_program
):
    service, program = f1_program
    codes = await label_codes(async_session, program)
    await service.enroll(
        program.id, shared_input("evaluator-0", membership_codes=codes)
    )
    with pytest.raises(HTTPException, match="already enrolled") as error:
        await service.enroll(program.id, shared_input("evaluator-0"))
    assert error.value.status_code == 409
    assert await enrollment_count(async_session) == 1
    assert (
        await async_session.scalar(select(func.count()).select_from(Presentation)) == 49
    )
