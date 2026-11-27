"""Shared label enrollment against a PostgreSQL 16 database at head.

The unit suite proves the code assignment on SQLite; this proves the same
enrollments pass the production partial unique index
(``WHERE shared_blind_code = false``) and ``UNIQUE(session_id, blind_code)``:
two evaluators hold the identical shared code for a sample, a third inherits it,
and no code repeats inside a session. Every test runs in one transaction and
rolls it back.

Skipped unless ``P1_DATABASE_URL`` points at a migrated PostgreSQL database.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Membership,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import EnrollmentInput, MembershipInput
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.shared_triples import SHARED_TRIPLES_ALGORITHM

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


async def _fragrance(db: AsyncSession) -> Fragrance:
    suffix = uuid4().hex
    fragrance = Fragrance(
        name=f"S {suffix}",
        brand="S house",
        concentration="EDP",
        version_key=f"s-{suffix}",
        gender_target="Unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="s",
    )
    db.add(fragrance)
    await db.flush()
    return fragrance


@pytest.mark.asyncio
async def test_shared_label_enrollments_run_on_postgres(session: AsyncSession) -> None:
    program = Program(name=f"S {uuid4().hex}", version="1", reveal_policy="HOUSEHOLD")
    session.add(program)
    reviewers = [Reviewer(name=f"S {uuid4().hex}") for _ in range(3)]
    session.add_all(reviewers)
    await session.flush()
    service = CalibrationService(session)
    for _ in range(6):
        fragrance = await _fragrance(session)
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
    member_ids = list(
        await session.scalars(
            select(Membership.id)
            .where(Membership.program_id == program.id)
            .order_by(Membership.id)
        )
    )
    codes = {
        mid: f"B{index:02d}-{uuid4().hex[:6].upper()}"
        for index, mid in enumerate(member_ids, 1)
    }

    enrollments = []
    for index, reviewer in enumerate(reviewers):
        enrollments.append(
            await service.enroll(
                program.id,
                EnrollmentInput(
                    reviewer_id=reviewer.id,
                    recorder_usernames=["r"],
                    session_size=3,
                    randomization_algorithm=SHARED_TRIPLES_ALGORITHM,
                    label_scheme="shared",
                    membership_codes=codes if index == 0 else None,
                ),
                "manager",
            )
        )

    for enrollment in enrollments:
        rows = list(
            await session.scalars(
                select(Presentation)
                .join(CalibrationSession)
                .where(CalibrationSession.enrollment_id == enrollment.id)
            )
        )
        assert {p.membership_id: p.blind_code for p in rows} == codes
        assert all(p.shared_blind_code for p in rows)
        per_session: dict[str, list[str]] = {}
        for row in rows:
            per_session.setdefault(row.session_id, []).append(row.blind_code)
        assert all(len(set(c)) == len(c) for c in per_session.values())
