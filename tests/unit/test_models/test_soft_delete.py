"""The shared soft-delete helpers (architecture review D-21)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.models.soft_delete import is_live, live
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.parametrize("model", [Fragrance, Evaluation, Reviewer])
def test_live_is_the_deleted_at_is_null_predicate(model: type) -> None:
    rendered = str(live(model).compile(dialect=postgresql.dialect()))
    assert rendered == f"{model.__tablename__}.deleted_at IS NULL"


def test_is_live_rejects_none_and_deleted_rows() -> None:
    assert not is_live(None)
    assert not is_live(Reviewer(name="Gone", deleted_at=now_naive_utc()))
    assert is_live(Reviewer(name="Here"))


@pytest.mark.asyncio
async def test_live_filters_exactly_the_soft_deleted_rows(
    async_session: AsyncSession,
) -> None:
    async_session.add_all(
        [
            Reviewer(id="here", name="Here"),
            Reviewer(id="gone", name="Gone", deleted_at=now_naive_utc()),
        ]
    )
    await async_session.flush()

    kept = set(await async_session.scalars(select(Reviewer.id).where(live(Reviewer))))

    assert kept == {"here"}
