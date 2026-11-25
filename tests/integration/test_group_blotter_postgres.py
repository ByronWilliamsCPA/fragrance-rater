"""F1 group-blotter schema (e4b6c8a2d915) against a PostgreSQL 16 database at head.

The unit suite proves the relaxed blind-code uniqueness, the mode CHECK and the
group flag code on SQLite; this proves the partial unique index
(``WHERE shared_blind_code = false``) and the CHECKs behave the same on the
production engine, and that a whole SHARED_GROUP enrollment runs on it. Every
test runs in one transaction and rolls it back.

Skipped unless ``P1_DATABASE_URL`` points at a migrated PostgreSQL database.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Presentation,
    Program,
    QualityFlag,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import EnrollmentInput, MembershipInput
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.shared_triples import GROUP_BLOTTER_ALGORITHM

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

DATABASE_URL = os.getenv("P1_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="P1_DATABASE_URL is not configured"),
]


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as db:
            yield db
        await transaction.rollback()
    await engine.dispose()


async def _rejects(db: AsyncSession, row: object) -> None:
    """Flush inside a savepoint so the outer test transaction survives."""
    nested = await db.begin_nested()
    db.add(row)
    with pytest.raises(IntegrityError):
        await db.flush()
    await nested.rollback()


async def _program(db: AsyncSession, mode: str = "INDIVIDUAL") -> Program:
    program = Program(name=f"G {uuid4().hex}", version="1", blotter_mode=mode)
    db.add(program)
    await db.flush()
    return program


async def _fragrance(db: AsyncSession) -> Fragrance:
    suffix = uuid4().hex
    fragrance = Fragrance(
        name=f"G {suffix}",
        brand="G house",
        concentration="EDP",
        version_key=f"g-{suffix}",
        gender_target="Unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="g",
    )
    db.add(fragrance)
    await db.flush()
    return fragrance


async def _sessions(db: AsyncSession, count: int) -> list[CalibrationSession]:
    program = await _program(db)
    reviewer = Reviewer(name=f"G {uuid4().hex}")
    db.add(reviewer)
    await db.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["r"]
    )
    db.add(enrollment)
    await db.flush()
    sessions = [
        CalibrationSession(enrollment_id=enrollment.id, context={})
        for _ in range(count)
    ]
    db.add_all(sessions)
    await db.flush()
    return sessions


async def _membership(db: AsyncSession) -> Membership:
    program = await _program(db)
    fragrance = await _fragrance(db)
    member = Membership(
        program_id=program.id,
        fragrance_id=fragrance.id,
        role="UNIVERSAL_BASELINE",
    )
    db.add(member)
    await db.flush()
    return member


def _presentation(
    session_id: str, membership_id: str, code: str, *, shared: bool, position: int
) -> Presentation:
    return Presentation(
        session_id=session_id,
        membership_id=membership_id,
        blind_code=code,
        shared_blind_code=shared,
        position=position,
        intended_position=position,
    )


@pytest.mark.asyncio
async def test_the_mode_check_refuses_an_unknown_mode(session: AsyncSession) -> None:
    await _rejects(session, Program(name="bad", version="1", blotter_mode="EVERYONE"))


@pytest.mark.asyncio
async def test_a_program_defaults_to_the_individual_mode(session: AsyncSession) -> None:
    program = Program(name=f"D {uuid4().hex}", version="1")
    session.add(program)
    await session.flush()
    await session.refresh(program)
    assert program.blotter_mode == "INDIVIDUAL"


@pytest.mark.asyncio
async def test_an_individual_code_stays_unique_table_wide(
    session: AsyncSession,
) -> None:
    first, second = await _sessions(session, 2)
    member = await _membership(session)
    code = uuid4().hex[:8].upper()
    session.add(_presentation(first.id, member.id, code, shared=False, position=1))
    await session.flush()
    await _rejects(
        session, _presentation(second.id, member.id, code, shared=False, position=1)
    )


@pytest.mark.asyncio
async def test_a_shared_code_repeats_across_sessions_not_within_one(
    session: AsyncSession,
) -> None:
    first, second = await _sessions(session, 2)
    member = await _membership(session)
    code = uuid4().hex[:8].upper()
    session.add(_presentation(first.id, member.id, code, shared=True, position=1))
    session.add(_presentation(second.id, member.id, code, shared=True, position=1))
    await session.flush()
    await _rejects(
        session, _presentation(first.id, member.id, code, shared=True, position=2)
    )


@pytest.mark.asyncio
async def test_the_flag_code_check_accepts_the_group_code(
    session: AsyncSession,
) -> None:
    (calibration_session,) = await _sessions(session, 1)
    session.add(
        QualityFlag(
            session_id=calibration_session.id,
            action="raised",
            code="group_shared_blotter",
            severity="info",
            source="automatic_validation",
            disposition="include",
            rule_version="group-shared-blotter-v1",
            explanation="Group blotter",
            recorded_by="manager",
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_a_group_enrollment_runs_on_postgres(session: AsyncSession) -> None:
    program = await _program(session, "SHARED_GROUP")
    fragrances = [await _fragrance(session) for _ in range(6)]
    reviewers = []
    for _ in range(2):
        reviewer = Reviewer(name=f"G {uuid4().hex}")
        session.add(reviewer)
        reviewers.append(reviewer)
    await session.flush()
    service = CalibrationService(session)
    for fragrance in fragrances:
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id=fragrance.id,
                role="UNIVERSAL_BASELINE",
                identity_evidence="Verified",
            ),
        )
    program.status = "active"
    await session.flush()

    enrollments = [
        await service.enroll(
            program.id,
            EnrollmentInput(
                reviewer_id=reviewer.id,
                recorder_usernames=["r"],
                session_size=3,
                randomization_algorithm=GROUP_BLOTTER_ALGORITHM,
            ),
            "manager",
        )
        for reviewer in reviewers
    ]

    layouts = []
    for enrollment in enrollments:
        rows = list(
            await session.scalars(
                select(Presentation)
                .join(CalibrationSession)
                .where(CalibrationSession.enrollment_id == enrollment.id)
                .order_by(CalibrationSession.created_at, Presentation.position)
            )
        )
        layouts.append([(p.membership_id, p.blind_code, p.position) for p in rows])
    assert layouts[0] == layouts[1]
    assert len(layouts[0]) == 6
