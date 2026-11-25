"""Migration e4b6c8a2d915: program blotter mode, shared blind codes, group flag code.

Pins the migration's literal vocabularies to the model and the request schema,
runs the real upgrade and downgrade against SQLite through Alembic operations
(including the relaxed blind-code uniqueness and the downgrade's refusal while
group data exists), and checks that the CHECK the chain leaves is the model's.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import TYPE_CHECKING, get_args

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base
from fragrance_rater.models.calibration import (
    BLOTTER_MODES,
    DEFAULT_BLOTTER_MODE,
    QUALITY_FLAG_CODES,
)
from fragrance_rater.schemas.calibration import BlotterMode

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

VERSIONS = Path(__file__).parents[3] / "alembic" / "versions"


def _load(prefix: str) -> ModuleType:
    path = next(VERSIONS.glob(f"{prefix}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{prefix}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load("e4b6c8a2d915")
PRIOR_FLAG_MIGRATION = _load("d7f3a91c5b28")


def _codes(sql: str) -> set[str]:
    return set(re.findall(r"'([^']*)'", sql))


def test_it_follows_the_reveal_policy_migration() -> None:
    assert MIGRATION.down_revision == "a7f3c2d91e04"


def test_the_vocabularies_agree() -> None:
    assert MIGRATION.BLOTTER_MODES == BLOTTER_MODES
    assert get_args(BlotterMode) == BLOTTER_MODES
    assert DEFAULT_BLOTTER_MODE == "INDIVIDUAL"
    assert _codes(MIGRATION.MODE_CHECK_SQL) == set(BLOTTER_MODES)


def test_the_flag_code_lists_are_the_models_and_the_prior_ones() -> None:
    assert _codes(MIGRATION.CODES_SQL) == set(QUALITY_FLAG_CODES)
    assert _codes(MIGRATION.PREVIOUS_CODES_SQL) == set(QUALITY_FLAG_CODES) - {
        MIGRATION.NEW_CODE
    }
    assert _codes(MIGRATION.PREVIOUS_CODES_SQL) == _codes(
        PRIOR_FLAG_MIGRATION.CODES_SQL
    )


def test_the_migration_check_equals_the_model_check() -> None:
    constraints = {
        c.name: str(c.sqltext)
        for c in Base.metadata.tables[MIGRATION.PROGRAMS].constraints
        if isinstance(c, CheckConstraint)
    }
    assert constraints[MIGRATION.MODE_CHECK] == MIGRATION.MODE_CHECK_SQL


def test_the_model_uniqueness_matches_the_migration() -> None:
    table = Base.metadata.tables[MIGRATION.PRESENTATIONS]
    uniques = {c.name for c in table.constraints if isinstance(c, sa.UniqueConstraint)}
    assert MIGRATION.SESSION_UNIQUE in uniques
    assert MIGRATION.OLD_UNIQUE not in uniques
    (index,) = [i for i in table.indexes if i.name == MIGRATION.INDIVIDUAL_INDEX]
    assert index.unique
    assert [c.name for c in index.columns] == ["blind_code"]


@pytest.fixture
def connection():
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE calibration_programs "
                "(id VARCHAR(36) PRIMARY KEY, name VARCHAR(200))"
            )
        )
        conn.execute(
            sa.text(
                "CREATE TABLE calibration_presentations ("
                "id VARCHAR(36) PRIMARY KEY, session_id VARCHAR(36), "
                "blind_code VARCHAR(40) NOT NULL, "
                "CONSTRAINT uq_calibration_presentations_blind_code "
                "UNIQUE (blind_code))"
            )
        )
        conn.execute(
            sa.text(
                "CREATE TABLE calibration_quality_flags ("
                "id VARCHAR(36) PRIMARY KEY, code VARCHAR(40) NOT NULL, "
                "CONSTRAINT ck_calibration_quality_flags_code_valid "
                f"CHECK ({MIGRATION.PREVIOUS_CODES_SQL}))"
            )
        )
        conn.execute(sa.text("INSERT INTO calibration_programs VALUES ('old', 'Old')"))
        conn.execute(
            sa.text(
                "INSERT INTO calibration_presentations VALUES ('p1', 's1', 'AAAA1111')"
            )
        )
        conn.execute(
            sa.text("INSERT INTO calibration_quality_flags VALUES ('f1', 'non_blind')")
        )
        yield conn
    engine.dispose()


def _run(monkeypatch: pytest.MonkeyPatch, conn: sa.Connection, step: str) -> None:
    operations = Operations(MigrationContext.configure(conn))
    monkeypatch.setattr(MIGRATION, "op", operations)
    getattr(MIGRATION, step)()


def _columns(conn: sa.Connection, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table)}


def test_upgrade_defaults_existing_rows_and_keeps_every_guarantee(
    monkeypatch: pytest.MonkeyPatch, connection: sa.Connection
) -> None:
    _run(monkeypatch, connection, "upgrade")

    mode = connection.execute(
        sa.text("SELECT blotter_mode FROM calibration_programs WHERE id = 'old'")
    ).scalar_one()
    shared = connection.execute(
        sa.text("SELECT shared_blind_code FROM calibration_presentations")
    ).scalar_one()
    assert (mode, shared) == ("INDIVIDUAL", 0)
    with pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO calibration_programs (id, name, blotter_mode) "
                "VALUES ('bad', 'Bad', 'EVERYONE')"
            )
        )
    # An individual code is still unique across the table.
    with pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO calibration_presentations "
                "(id, session_id, blind_code, shared_blind_code) "
                "VALUES ('p2', 's2', 'AAAA1111', 0)"
            )
        )
    # A shared code may repeat across sessions, but not within one.
    connection.execute(
        sa.text(
            "INSERT INTO calibration_presentations "
            "(id, session_id, blind_code, shared_blind_code) VALUES "
            "('p3', 's3', 'GROUP001', 1), ('p4', 's4', 'GROUP001', 1)"
        )
    )
    with pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO calibration_presentations "
                "(id, session_id, blind_code, shared_blind_code) "
                "VALUES ('p5', 's3', 'GROUP001', 1)"
            )
        )
    connection.execute(
        sa.text(
            "INSERT INTO calibration_quality_flags VALUES ('f2', 'group_shared_blotter')"
        )
    )


def test_downgrade_restores_the_old_shape_when_no_group_data_exists(
    monkeypatch: pytest.MonkeyPatch, connection: sa.Connection
) -> None:
    _run(monkeypatch, connection, "upgrade")

    _run(monkeypatch, connection, "downgrade")

    assert "blotter_mode" not in _columns(connection, "calibration_programs")
    assert "shared_blind_code" not in _columns(connection, "calibration_presentations")
    with pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO calibration_presentations (id, session_id, blind_code) "
                "VALUES ('p9', 's9', 'AAAA1111')"
            )
        )
    with pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO calibration_quality_flags VALUES ('f9', 'group_shared_blotter')"
            )
        )
    assert (
        connection.execute(
            sa.text("SELECT count(*) FROM calibration_presentations")
        ).scalar_one()
        == 1
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE calibration_programs SET blotter_mode = 'SHARED_GROUP'",
        "UPDATE calibration_presentations SET shared_blind_code = 1",
        "INSERT INTO calibration_quality_flags VALUES ('g', 'group_shared_blotter')",
    ],
)
def test_downgrade_refuses_while_group_data_exists(
    monkeypatch: pytest.MonkeyPatch, connection: sa.Connection, statement: str
) -> None:
    _run(monkeypatch, connection, "upgrade")
    connection.execute(sa.text(statement))

    with pytest.raises(RuntimeError, match=r"e4b6c8a2d915.*1 "):
        _run(monkeypatch, connection, "downgrade")

    assert "blotter_mode" in _columns(connection, "calibration_programs")
