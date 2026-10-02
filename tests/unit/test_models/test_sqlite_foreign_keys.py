"""The shared SQLite test engines enforce foreign keys (R2, D-07)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Engine, delete, text
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.calibration import Enrollment, Program
from fragrance_rater.models.reviewer import Reviewer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.mark.asyncio
async def test_async_engine_enforces_foreign_keys(async_engine: AsyncEngine) -> None:
    """The pragma is on for the async fixture's connections."""
    async with async_engine.connect() as conn:
        assert (await conn.exec_driver_sql("PRAGMA foreign_keys")).scalar() == 1


def test_sync_engine_enforces_foreign_keys(sync_engine: Engine) -> None:
    """The pragma is on for the sync fixture's connections."""
    with sync_engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


@pytest.mark.asyncio
async def test_restrict_blocks_deleting_referenced_reviewer(
    async_session: AsyncSession,
) -> None:
    """An ``ondelete="RESTRICT"`` FK now fails the delete, as on PostgreSQL."""
    reviewer = Reviewer(name="fk-guard")
    program = Program(name="fk-guard", version="1")
    async_session.add_all([reviewer, program])
    await async_session.flush()
    async_session.add(
        Enrollment(
            program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=[]
        )
    )
    await async_session.flush()

    with pytest.raises(IntegrityError):
        await async_session.execute(delete(Reviewer).where(Reviewer.id == reviewer.id))
