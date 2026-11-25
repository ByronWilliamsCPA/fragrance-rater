"""Migration a7f3c2d91e04: ``calibration_programs.reveal_policy``.

Pins the migration's literal vocabulary and CHECK to the model and the request
schema, and runs the real upgrade and downgrade against SQLite through Alembic
operations, including the downgrade's refusal while a HOUSEHOLD program exists.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, get_args

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base
from fragrance_rater.models.calibration import DEFAULT_REVEAL_POLICY, REVEAL_POLICIES
from fragrance_rater.schemas.calibration import RevealPolicy

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


MIGRATION = _load("a7f3c2d91e04")


def test_the_migration_alters_the_program_table() -> None:
    assert MIGRATION.TABLE == "calibration_programs"
    assert MIGRATION.down_revision == "d7f3a91c5b28"


def test_the_vocabularies_agree() -> None:
    assert MIGRATION.REVEAL_POLICIES == REVEAL_POLICIES
    assert get_args(RevealPolicy) == REVEAL_POLICIES
    assert DEFAULT_REVEAL_POLICY == "ENROLLMENT"


def test_the_migration_check_equals_the_model_check() -> None:
    constraints = {
        c.name: str(c.sqltext)
        for c in Base.metadata.tables[MIGRATION.TABLE].constraints
        if isinstance(c, CheckConstraint)
    }
    assert constraints[MIGRATION.CHECK] == MIGRATION.CHECK_SQL


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
        conn.execute(sa.text("INSERT INTO calibration_programs VALUES ('old', 'Old')"))
        yield conn
    engine.dispose()


def _run(monkeypatch: pytest.MonkeyPatch, conn: sa.Connection, step: str) -> None:
    operations = Operations(MigrationContext.configure(conn))
    monkeypatch.setattr(MIGRATION, "op", operations)
    getattr(MIGRATION, step)()


def _columns(conn: sa.Connection) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(MIGRATION.TABLE)}


def test_upgrade_defaults_existing_programs_and_downgrade_drops_the_column(
    monkeypatch: pytest.MonkeyPatch, connection: sa.Connection
) -> None:
    _run(monkeypatch, connection, "upgrade")

    policy = connection.execute(
        sa.text("SELECT reveal_policy FROM calibration_programs WHERE id = 'old'")
    ).scalar_one()
    assert policy == "ENROLLMENT"
    connection.execute(
        sa.text(
            "INSERT INTO calibration_programs (id, name, reveal_policy) "
            "VALUES ('new', 'New', 'ENROLLMENT')"
        )
    )
    with pytest.raises(IntegrityError):
        connection.execute(
            sa.text(
                "INSERT INTO calibration_programs (id, name, reveal_policy) "
                "VALUES ('bad', 'Bad', 'EVERYONE')"
            )
        )

    _run(monkeypatch, connection, "downgrade")

    assert "reveal_policy" not in _columns(connection)
    count = connection.execute(
        sa.text("SELECT count(*) FROM calibration_programs")
    ).scalar_one()
    assert count == 2


def test_downgrade_refuses_while_a_household_program_exists(
    monkeypatch: pytest.MonkeyPatch, connection: sa.Connection
) -> None:
    _run(monkeypatch, connection, "upgrade")
    connection.execute(
        sa.text("UPDATE calibration_programs SET reveal_policy = 'HOUSEHOLD'")
    )

    with pytest.raises(RuntimeError, match=r"a7f3c2d91e04 .*1 household-reveal"):
        _run(monkeypatch, connection, "downgrade")
    assert "reveal_policy" in _columns(connection)
