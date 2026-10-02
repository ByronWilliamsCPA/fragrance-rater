"""Unit tests for the Reviewer model's ORM relationship configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


# The shared tests/conftest.py engines turn on SQLite foreign-key enforcement
# for every connection (R2, architecture review D-07), so the RESTRICT path
# this module verifies runs against the standard fixture. The alias keeps the
# tests' intent visible at the call site.
@pytest_asyncio.fixture(scope="function")
async def fk_enforced_session(
    async_session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """Async session whose engine enforces foreign keys, as PostgreSQL does."""
    yield async_session


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
