"""HouseSubmission CHECK constraints: a submitted row is always complete evidence."""

import pytest
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.house_intake import HouseSubmission
from fragrance_rater.utils.timestamps import now_naive_utc


def submitted(**overrides: object) -> HouseSubmission:
    values: dict[str, object] = {
        "house": "Maison A",
        "created_by": "maison-a-rep",
        "status": "submitted",
        "submitted_at": now_naive_utc(),
        "submitted_by": "maison-a-rep",
        "permission_state": "retain_and_train",
        "payload": {"fragrance_name": "X"},
    }
    values.update(overrides)
    return HouseSubmission(**values)


@pytest.mark.asyncio
async def test_complete_submitted_row_is_accepted(async_session):
    async_session.add(submitted())
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "approved"},
        {"permission_state": "excluded_no_new_writes"},
        {"permission_state": None},
        {"submitted_at": None},
        {"submitted_by": None},
    ],
)
async def test_house_submission_constraints(async_session, overrides):
    async_session.add(submitted(**overrides))
    with pytest.raises(IntegrityError):
        await async_session.flush()


@pytest.mark.asyncio
async def test_a_record_can_be_superseded_only_once(async_session):
    original = submitted()
    async_session.add(original)
    await async_session.flush()
    for _ in range(2):
        async_session.add(
            HouseSubmission(
                house="Maison A",
                created_by="maison-a-rep",
                status="draft",
                supersedes_id=original.id,
                payload={"fragrance_name": "X"},
            )
        )
    with pytest.raises(IntegrityError):
        await async_session.flush()
