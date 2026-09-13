"""Unit tests for the Reviewer model's ORM relationship configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from fragrance_rater.core.database import Base
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# #CRITICAL: data-integrity: SQLite does not enforce foreign key constraints
# (including ondelete="RESTRICT") unless "PRAGMA foreign_keys = ON" is issued
# per connection. The shared tests/conftest.py async_session/async_engine
# fixtures never set this pragma, so they cannot exercise the RESTRICT path
# this test is built to verify. A dedicated engine/session pair with FK
# enforcement turned on is used instead, scoped to this module only, so no
# other suite's behavior (which may rely on today's relaxed FK enforcement)
# changes as a side effect of this fix.
# #VERIFY: if a future test needs FK enforcement more broadly, promote this
# fixture to tests/conftest.py deliberately rather than assuming it already
# applies there.


@pytest_asyncio.fixture(scope="function")
async def fk_enforced_engine():
    """Async SQLite engine with real foreign key (RESTRICT/CASCADE) enforcement."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # StaticPool keeps one underlying DBAPI connection alive for the whole
    # engine (required for an in-memory SQLite database to persist across
    # checkouts), so setting the pragma once here applies for every session
    # created against this engine afterward. A sync "connect" event listener
    # (the usual pysqlite recipe) does not work against the aiosqlite async
    # driver: the DBAPI connection it receives requires a greenlet context
    # to await, which isn't present in a plain event callback.
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def fk_enforced_session(
    fk_enforced_engine,
) -> AsyncGenerator[AsyncSession, None]:
    """Async session bound to the FK-enforced engine."""
    session_maker = async_sessionmaker(
        fk_enforced_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session


def _make_fragrance(fragrance_id: str) -> Fragrance:
    """Build a minimal valid Fragrance row for FK targets in these tests."""
    return Fragrance(
        id=fragrance_id,
        name="Test Fragrance",
        brand="Test Brand",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="manual",
    )


@pytest.mark.asyncio
class TestWornByEvaluationsRestrictOnDelete:
    """Reviewer.worn_by_evaluations must not bypass ondelete=RESTRICT.

    Regression coverage for the Copilot-flagged finding: without
    ``passive_deletes="all"`` on ``Reviewer.worn_by_evaluations``,
    SQLAlchemy's default ORM delete behavior loads and NULLs out every
    child ``Evaluation.worn_by_reviewer_id`` before issuing the DELETE, so
    the DB-level RESTRICT constraint never sees a referencing row and the
    delete silently succeeds, converting someone else's "on others" rating
    into a rating with no worn-by subject.
    """

    async def test_deleting_worn_by_subject_is_rejected(self, fk_enforced_session):
        """Deleting a reviewer who is another reviewer's worn-by subject
        must raise, not silently null the FK and succeed.
        """
        subject = Reviewer(id="restrict-subject", name="Subject Reviewer")
        rater = Reviewer(id="restrict-rater", name="Rater Reviewer")
        fragrance = _make_fragrance("restrict-frag")
        fk_enforced_session.add_all([subject, rater, fragrance])
        await fk_enforced_session.commit()

        evaluation = Evaluation(
            id="restrict-eval",
            fragrance_id=fragrance.id,
            reviewer_id=rater.id,
            rating=4,
            worn_by_reviewer_id=subject.id,
        )
        fk_enforced_session.add(evaluation)
        await fk_enforced_session.commit()

        await fk_enforced_session.delete(subject)
        with pytest.raises(IntegrityError):
            await fk_enforced_session.commit()
        await fk_enforced_session.rollback()

        # The evaluation and its worn-by reference must be untouched: the
        # rejected delete must not have nulled the FK as a side effect.
        # A fresh `select` (rather than `.get()`) is used deliberately: the
        # rollback above expires every attribute on identity-mapped
        # instances, and `AsyncSession.get()` can return that expired
        # instance without eagerly reloading it, which then fails on plain
        # attribute access (no implicit lazy-load IO is possible outside an
        # explicit `await` in async SQLAlchemy).
        # Compare against the literal id, not `subject.id`: the rollback
        # above expires `subject` too, and attribute access on an expired
        # instance needs IO that can't happen implicitly outside an
        # explicit `await` in async SQLAlchemy.
        result = await fk_enforced_session.execute(
            select(Evaluation).where(Evaluation.id == "restrict-eval")
        )
        refreshed = result.scalar_one()
        assert refreshed.worn_by_reviewer_id == "restrict-subject"

    async def test_deleting_reviewer_with_no_worn_by_subjects_succeeds(
        self, fk_enforced_session
    ):
        """Sanity check: ``passive_deletes="all"`` must not block ordinary
        deletes of a reviewer who is nobody's worn-by subject.
        """
        reviewer = Reviewer(id="restrict-lone", name="Lone Reviewer")
        fk_enforced_session.add(reviewer)
        await fk_enforced_session.commit()

        await fk_enforced_session.delete(reviewer)
        await fk_enforced_session.commit()  # Must not raise.

        assert await fk_enforced_session.get(Reviewer, "restrict-lone") is None
