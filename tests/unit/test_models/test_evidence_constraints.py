"""Database-level guards on evidence tables (R2 PR 2).

Covers the CHECKs added for architecture review D-02 and D-15 / ML review
X-25, and the D-09 change that makes a hard delete of a fragrance or reviewer
fail instead of cascading into encounter history. The shared SQLite fixtures
enforce foreign keys and CHECKs the same way PostgreSQL does.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, get_args

import pytest
from sqlalchemy import CheckConstraint, delete
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base
from fragrance_rater.models.calibration import Membership, Program
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import Role, Stage

if TYPE_CHECKING:
    from sqlalchemy import Table
    from sqlalchemy.ext.asyncio import AsyncSession


def _in_values(table: Table, rule: str) -> set[str]:
    """Return the quoted values of the ``ck_<table>_<rule>`` IN (...) CHECK."""
    name = f"ck_{table.name}_{rule}"
    (constraint,) = (
        c
        for c in table.constraints
        if isinstance(c, CheckConstraint) and c.name == name
    )
    return set(re.findall(r"'([^']*)'", str(constraint.sqltext)))


def test_role_check_matches_schema_role() -> None:
    """The DB role list and the API's Role literal cannot drift apart."""
    assert _in_values(
        Base.metadata.tables["calibration_memberships"], "role_valid"
    ) == set(get_args(Role))


def test_stage_check_matches_schema_stage() -> None:
    """The DB stage list and the API's Stage literal cannot drift apart."""
    assert _in_values(
        Base.metadata.tables["calibration_observations"], "stage_valid"
    ) == set(get_args(Stage))


async def _fragrance_and_reviewer(
    session: AsyncSession,
) -> tuple[Fragrance, Reviewer]:
    fragrance = Fragrance(
        name="Guard",
        brand="House",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="unit",
    )
    reviewer = Reviewer(name="guard")
    session.add_all([fragrance, reviewer])
    await session.flush()
    return fragrance, reviewer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"rating": 0},
        {"rating": 6},
        {"rating": 3, "longevity_rating": 0},
        {"rating": 3, "sillage_rating": 6},
    ],
)
async def test_evaluation_scales_reject_out_of_range(
    async_session: AsyncSession, fields: dict[str, int]
) -> None:
    """D-02: the 1-5 scales hold even when a write bypasses Pydantic."""
    fragrance, reviewer = await _fragrance_and_reviewer(async_session)
    async_session.add(
        Evaluation(fragrance_id=fragrance.id, reviewer_id=reviewer.id, **fields)
    )
    with pytest.raises(IntegrityError, match="rating_range"):
        await async_session.flush()


@pytest.mark.asyncio
async def test_evaluation_scales_accept_bounds_and_nulls(
    async_session: AsyncSession,
) -> None:
    """The CHECKs admit the full documented range and the optional NULLs."""
    fragrance, reviewer = await _fragrance_and_reviewer(async_session)
    async_session.add_all(
        [
            Evaluation(
                fragrance_id=fragrance.id,
                reviewer_id=reviewer.id,
                rating=1,
                longevity_rating=1,
                sillage_rating=5,
            ),
            Evaluation(fragrance_id=fragrance.id, reviewer_id=reviewer.id, rating=5),
        ]
    )
    await async_session.flush()


@pytest.mark.asyncio
async def test_misspelled_role_is_rejected(async_session: AsyncSession) -> None:
    """X-25: a typo can no longer turn a holdout into trainable data."""
    fragrance, _ = await _fragrance_and_reviewer(async_session)
    program = Program(name="guard", version="1")
    async_session.add(program)
    await async_session.flush()
    async_session.add(
        Membership(program_id=program.id, fragrance_id=fragrance.id, role="HOLD_OUT")
    )
    with pytest.raises(IntegrityError, match="role_valid"):
        await async_session.flush()


@pytest.mark.asyncio
async def test_unknown_program_status_is_rejected(
    async_session: AsyncSession,
) -> None:
    """D-15: program status is limited to the states the service gates on."""
    async_session.add(Program(name="guard", version="1", status="archived"))
    with pytest.raises(IntegrityError, match="status_valid"):
        await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["fragrance", "reviewer"])
async def test_hard_delete_with_evaluations_is_restricted(
    async_session: AsyncSession, target: str
) -> None:
    """D-09: deleting a rated fragrance or a reviewer keeps their history.

    Covers both paths: the ORM must not cascade or orphan the evaluations
    (``passive_deletes="all"``), and the database must reject the DELETE.
    """
    fragrance, reviewer = await _fragrance_and_reviewer(async_session)
    evaluation = Evaluation(
        fragrance_id=fragrance.id, reviewer_id=reviewer.id, rating=4
    )
    async_session.add(evaluation)
    await async_session.commit()
    model = Fragrance if target == "fragrance" else Reviewer
    victim = fragrance if target == "fragrance" else reviewer
    victim_id, evaluation_id = victim.id, evaluation.id

    await async_session.delete(victim)
    with pytest.raises(IntegrityError):
        await async_session.commit()
    await async_session.rollback()

    with pytest.raises(IntegrityError):
        await async_session.execute(delete(model).where(model.id == victim_id))
    await async_session.rollback()

    assert await async_session.get(Evaluation, evaluation_id) is not None
