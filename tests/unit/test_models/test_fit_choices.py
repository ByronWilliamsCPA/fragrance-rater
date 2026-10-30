"""Database guards on ``calibration_fit_choices`` and its migration (R7b PR 1a).

Migration ``f74bf7ff9c2d`` turns ML Decisions Q9's season and setting answers
from one code per field into multi-select child rows.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from sqlalchemy import CheckConstraint, select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base
from fragrance_rater.models.calibration import (
    FIT_DIMENSIONS,
    SEASON_FIT_CODES,
    SETTING_FIT_CODES,
    CalibrationSession,
    Enrollment,
    FitChoice,
    Membership,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MIGRATION = next(
    (Path(__file__).parents[3] / "alembic" / "versions").glob("f74bf7ff9c2d_*.py")
)
TABLE = Base.metadata.tables["calibration_fit_choices"]


def _migration():
    spec = importlib.util.spec_from_file_location("fit_choices_migration", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check(rule: str) -> CheckConstraint:
    (constraint,) = (
        c
        for c in TABLE.constraints
        if isinstance(c, CheckConstraint)
        and c.name == f"ck_calibration_fit_choices_{rule}"
    )
    return constraint


async def _observation(session: AsyncSession) -> Observation:
    program = Program(name="fit", version="1")
    reviewer = Reviewer(name="fit")
    fragrance = Fragrance(
        name="Fit",
        brand="House",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="unit",
    )
    session.add_all([program, reviewer, fragrance])
    await session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    session.add(enrollment)
    await session.flush()
    calibration = CalibrationSession(enrollment_id=enrollment.id)
    member = Membership(
        program_id=program.id, fragrance_id=fragrance.id, role="HOLDOUT"
    )
    session.add_all([calibration, member])
    await session.flush()
    presentation = Presentation(
        session_id=calibration.id, membership_id=member.id, blind_code="F1", position=1
    )
    session.add(presentation)
    await session.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage="SKIN",
        phase="PRE_REVEAL",
        recorded_by="rec",
    )
    session.add(observation)
    await session.flush()
    return observation


async def _rejects(session: AsyncSession, row: object) -> None:
    session.add(row)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


# --- the single-select columns are gone ------------------------------------


def test_the_single_select_columns_no_longer_exist() -> None:
    columns = Base.metadata.tables["calibration_observations"].columns

    assert "season_fit" not in columns
    assert "setting_fit" not in columns


def test_the_single_select_checks_no_longer_exist() -> None:
    names = {
        c.name for c in Base.metadata.tables["calibration_observations"].constraints
    }

    assert not {n for n in names if n and ("season_fit" in n or "setting_fit" in n)}


# --- the child table -------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dimension", "code"),
    [("season", c) for c in SEASON_FIT_CODES]
    + [("setting", c) for c in SETTING_FIT_CODES],
)
async def test_every_valid_code_is_accepted_for_its_dimension(
    async_session: AsyncSession, dimension: str, code: str
) -> None:
    observation = await _observation(async_session)
    async_session.add(
        FitChoice(observation_id=observation.id, dimension=dimension, code=code)
    )
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dimension", "code"),
    [
        ("season", "home"),
        ("season", "social_outing"),
        ("season", "other"),
        ("setting", "spring"),
        ("setting", "year_round"),
        ("setting", "winter"),
        ("season", "monsoon"),
        ("setting", "beach"),
        ("weather", "spring"),
        ("", "none"),
    ],
)
async def test_a_code_must_belong_to_its_dimension(
    async_session: AsyncSession, dimension: str, code: str
) -> None:
    observation = await _observation(async_session)

    await _rejects(
        async_session,
        FitChoice(observation_id=observation.id, dimension=dimension, code=code),
    )


@pytest.mark.asyncio
async def test_none_and_cannot_judge_are_valid_in_both_dimensions(
    async_session: AsyncSession,
) -> None:
    observation = await _observation(async_session)
    async_session.add_all(
        [
            FitChoice(observation_id=observation.id, dimension=d, code=c)
            for d in FIT_DIMENSIONS
            for c in ("none", "cannot_judge")
        ]
    )
    await async_session.flush()


@pytest.mark.asyncio
async def test_an_option_is_recorded_once_per_observation(
    async_session: AsyncSession,
) -> None:
    observation = await _observation(async_session)
    async_session.add(
        FitChoice(observation_id=observation.id, dimension="season", code="spring")
    )
    await async_session.flush()

    await _rejects(
        async_session,
        FitChoice(observation_id=observation.id, dimension="season", code="spring"),
    )


@pytest.mark.asyncio
async def test_the_same_code_may_appear_in_different_dimensions(
    async_session: AsyncSession,
) -> None:
    """``none`` for season and ``none`` for setting are two different answers."""
    observation = await _observation(async_session)
    async_session.add_all(
        [
            FitChoice(observation_id=observation.id, dimension="season", code="none"),
            FitChoice(observation_id=observation.id, dimension="setting", code="none"),
        ]
    )
    await async_session.flush()

    rows = (await async_session.execute(select(FitChoice))).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_a_fit_choice_needs_a_real_observation(
    async_session: AsyncSession,
) -> None:
    await _observation(async_session)

    await _rejects(
        async_session,
        FitChoice(
            observation_id="no-such-observation", dimension="season", code="none"
        ),
    )


@pytest.mark.asyncio
async def test_an_observation_with_fit_choices_cannot_be_hard_deleted(
    async_session: AsyncSession,
) -> None:
    """Answers are evidence: the foreign key does not cascade."""
    observation = await _observation(async_session)
    async_session.add(
        FitChoice(observation_id=observation.id, dimension="season", code="spring")
    )
    await async_session.flush()

    await async_session.delete(observation)
    with pytest.raises(IntegrityError):
        await async_session.flush()


# --- the migration ----------------------------------------------------------


def test_the_code_check_matches_the_model_vocabularies() -> None:
    text = str(_check("code_valid").sqltext)
    season, setting = text.split(" OR ")

    assert set(re.findall(r"'([^']*)'", season)) == {"season", *SEASON_FIT_CODES}
    assert set(re.findall(r"'([^']*)'", setting)) == {"setting", *SETTING_FIT_CODES}


def test_the_dimension_check_matches_the_model_tuple() -> None:
    assert set(re.findall(r"'([^']*)'", str(_check("dimension_valid").sqltext))) == set(
        FIT_DIMENSIONS
    )


class _Batch:
    """Context manager standing in for ``op.batch_alter_table``."""

    def __enter__(self) -> _Batch:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def drop_constraint(self, *_args: object, **_kwargs: object) -> None:
        return None

    def drop_column(self, *_args: object, **_kwargs: object) -> None:
        return None


class _RecordingOp:
    """Stand-in for ``alembic.op`` that records each CHECK ``upgrade`` creates."""

    def __init__(self) -> None:
        self.created: dict[str, str] = {}

    def get_bind(self) -> sa.Connection:
        return _sqlite_with_observations(None, None)

    def create_table(self, _name: str, *items: object) -> None:
        for item in items:
            if isinstance(item, sa.CheckConstraint):
                self.created[str(item.name)] = str(item.sqltext)

    def create_index(self, *_args: object, **_kwargs: object) -> None:
        return None

    def batch_alter_table(self, _table: str) -> _Batch:
        return _Batch()


@pytest.mark.parametrize("rule", ["dimension_valid", "code_valid"])
def test_the_migration_writes_the_same_checks_as_the_model(
    monkeypatch: pytest.MonkeyPatch, rule: str
) -> None:
    """Run ``upgrade`` against a recorder and compare each CHECK by name."""
    migration = _migration()
    recorder = _RecordingOp()
    monkeypatch.setattr(migration, "op", recorder)

    migration.upgrade()

    name = f"ck_calibration_fit_choices_{rule}"
    assert name in recorder.created, name
    assert re.findall(r"'([^']*)'", recorder.created[name]) == re.findall(
        r"'([^']*)'", str(_check(rule).sqltext)
    ), name


def _sqlite_with_observations(season: str | None, setting: str | None):
    connection = sa.create_engine("sqlite://").connect()
    connection.execute(
        sa.text(
            "CREATE TABLE calibration_observations (season_fit TEXT, setting_fit TEXT)"
        )
    )
    connection.execute(
        sa.text("INSERT INTO calibration_observations VALUES (:a, :b)"),
        {"a": season, "b": setting},
    )
    return connection


def test_the_upgrade_guard_sees_nothing_when_the_old_columns_are_empty() -> None:
    connection = _sqlite_with_observations(None, None)

    assert _migration()._populated_single_select_columns(connection) == []


def test_the_upgrade_guard_names_each_populated_column() -> None:
    connection = _sqlite_with_observations("spring", "home")

    found = _migration()._populated_single_select_columns(connection)

    assert found == [
        "calibration_observations.season_fit: 1 non-NULL row(s)",
        "calibration_observations.setting_fit: 1 non-NULL row(s)",
    ]


def test_the_upgrade_refuses_to_drop_populated_columns(monkeypatch) -> None:
    migration = _migration()

    class _Op:
        @staticmethod
        def get_bind() -> object:
            return _sqlite_with_observations("spring", None)

    monkeypatch.setattr(migration, "op", _Op)

    with pytest.raises(RuntimeError, match=r"f74bf7ff9c2d.*season_fit: 1 non-NULL"):
        migration.upgrade()


@pytest.mark.asyncio
async def test_the_downgrade_guard_counts_fit_choices(
    async_session: AsyncSession,
) -> None:
    migration = _migration()
    connection = await async_session.connection()
    assert await connection.run_sync(migration._fit_choice_count) == 0

    observation = await _observation(async_session)
    async_session.add_all(
        [
            FitChoice(observation_id=observation.id, dimension="season", code="spring"),
            FitChoice(observation_id=observation.id, dimension="season", code="fall"),
        ]
    )
    await async_session.flush()

    assert await connection.run_sync(migration._fit_choice_count) == 2


def test_the_downgrade_refuses_while_fit_choices_exist(monkeypatch) -> None:
    migration = _migration()

    class _Result:
        @staticmethod
        def scalar_one() -> int:
            return 3

    class _Bind:
        @staticmethod
        def execute(_statement: object) -> _Result:
            return _Result()

    class _Op:
        @staticmethod
        def get_bind() -> _Bind:
            return _Bind()

    monkeypatch.setattr(migration, "op", _Op)

    with pytest.raises(RuntimeError, match=r"f74bf7ff9c2d.*fit_choices: 3 row"):
        migration.downgrade()
