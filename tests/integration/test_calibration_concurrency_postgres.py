"""P1.4 PostgreSQL concurrency gate for calibration membership and enrollment.

Exercises the two mutation races the P1 release-readiness runbook names under
"Concurrency and disclosure": simultaneous membership mutation attempts (here,
two managers racing to assign the same fragrance as a program's holdout) and
simultaneous enrollment attempts (two recorders racing to enroll the same
reviewer). Both rely on real PostgreSQL row locking (``SELECT ... FOR UPDATE``
and a unique constraint) that SQLite's test suite cannot exercise under true
concurrency, so this only runs against the target engine.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fragrance_rater.models.calibration import Enrollment, Membership, Program
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import EnrollmentInput, MembershipInput
from fragrance_rater.services.calibration_service import CalibrationService

DATABASE_URL = os.getenv("P1_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(not DATABASE_URL, reason="P1_DATABASE_URL is not configured"),
]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_holdout_assignment_leaves_exactly_one_membership() -> None:
    """Two managers racing to add the same fragrance as HOLDOUT: only one wins.

    ``add_member`` locks the target ``Fragrance`` row with
    ``with_for_update()`` before checking whether the fragrance already has a
    holdout membership. Under true concurrency (two separate connections,
    not two calls on one session) the second transaction must block on that
    lock, then see the first transaction's committed row and reject rather
    than racing past the check-then-act gap and creating two holdout rows
    for the same fragrance.
    """
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex

    async with session_factory() as setup_session:
        fragrance = Fragrance(
            name=f"P1.4 concurrency scent {suffix}",
            brand="P1 gate house",
            concentration="EDP",
            version_key=f"p1-4-{suffix}",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="p1-gate",
        )
        program = Program(
            name=f"P1.4 concurrency program {suffix}",
            version="v1",
            description=None,
            status="draft",
        )
        setup_session.add_all([fragrance, program])
        await setup_session.commit()
        fragrance_id, program_id = fragrance.id, program.id

    async def attempt() -> str:
        async with session_factory() as session:
            service = CalibrationService(session)
            member = await service.add_member(
                program_id,
                MembershipInput(
                    fragrance_id=fragrance_id,
                    role="HOLDOUT",
                    identity_evidence="P1.4 concurrency gate",
                ),
            )
            await session.commit()
            return member.id

    results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)
    successes = [r for r in results if isinstance(r, str)]
    rejections = [r for r in results if isinstance(r, HTTPException)]
    assert len(successes) == 1, f"expected exactly one winner, got {results!r}"
    assert len(rejections) == 1
    assert rejections[0].status_code == 409

    async with session_factory() as verify_session:
        rows = list(
            await verify_session.scalars(
                select(Membership).where(
                    Membership.program_id == program_id,
                    Membership.fragrance_id == fragrance_id,
                )
            )
        )
    assert len(rows) == 1, "the race must not leave two holdout memberships"

    # This suite shares a database with other PostgreSQL-gated tests within
    # one CI run (each test creates its own uniquely-suffixed rows, but
    # nothing recreates the database between files). The recommendation
    # measurement gate queries the whole fragrance catalog for a reviewer,
    # so a fragrance left behind here would silently become a candidate in
    # that unrelated test. Clean up rather than relying on run order.
    async with session_factory() as cleanup_session:
        await cleanup_session.execute(
            delete(Membership).where(Membership.program_id == program_id)
        )
        await cleanup_session.execute(delete(Program).where(Program.id == program_id))
        await cleanup_session.execute(
            delete(Fragrance).where(Fragrance.id == fragrance_id)
        )
        await cleanup_session.commit()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_duplicate_enrollment_leaves_exactly_one_enrollment() -> None:
    """Two recorders racing to enroll the same reviewer: only one row persists.

    ``enroll`` checks for an existing ``Enrollment`` before inserting, but
    that check has no row to lock (the row does not exist yet), so under true
    concurrency both transactions can pass the check before either commits.
    The last line of defense is the ``UniqueConstraint("program_id",
    "reviewer_id")`` on ``Enrollment`` itself: this asserts the constraint
    actually prevents a duplicate row, whatever shape the losing transaction's
    failure takes (a clean 409 from the app-level check winning the race, or
    the database's own integrity error surfacing when both passed it).
    """
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex

    async with session_factory() as setup_session:
        reviewer = Reviewer(name=f"P1.4 concurrency reviewer {suffix}")
        program = Program(
            name=f"P1.4 concurrency enroll program {suffix}",
            version="v1",
            description=None,
            status="active",
        )
        setup_session.add_all([reviewer, program])
        await setup_session.commit()
        reviewer_id, program_id = reviewer.id, program.id

    async def attempt() -> str:
        async with session_factory() as session:
            service = CalibrationService(session)
            enrollment = await service.enroll(
                program_id,
                EnrollmentInput(
                    reviewer_id=reviewer_id,
                    recorder_usernames=["p1-gate"],
                ),
            )
            await session.commit()
            return enrollment.id

    results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)
    successes = [r for r in results if isinstance(r, str)]
    failures = [
        r for r in results if isinstance(r, HTTPException | IntegrityError | DBAPIError)
    ]
    assert len(successes) == 1, f"expected exactly one winner, got {results!r}"
    assert len(failures) == 1

    async with session_factory() as verify_session:
        rows = list(
            await verify_session.scalars(
                select(Enrollment).where(
                    Enrollment.program_id == program_id,
                    Enrollment.reviewer_id == reviewer_id,
                )
            )
        )
    assert len(rows) == 1, "the unique constraint must prevent a duplicate enrollment"

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(
            delete(Enrollment).where(Enrollment.program_id == program_id)
        )
        await cleanup_session.execute(delete(Program).where(Program.id == program_id))
        await cleanup_session.execute(
            delete(Reviewer).where(Reviewer.id == reviewer_id)
        )
        await cleanup_session.commit()
    await engine.dispose()
