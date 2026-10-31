"""Migration 4edb5c967539 (R8 PR 2): literal lists, guards, and ordering.

The PostgreSQL behaviour (triggers, jsonb, UTC defaults) is proved in
tests/integration/test_r8_hardening_postgres.py; these pin what can be pinned
without PostgreSQL: the migration's literal lists agree with the models, the
view is dropped first and recreated last, and the downgrade refuses while an
idempotency key would be lost.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from sqlalchemy import JSON, text

from fragrance_rater.core.database import utc_now
from fragrance_rater.models import Base

if TYPE_CHECKING:
    from types import ModuleType

MIGRATION = next(
    (Path(__file__).parents[3] / "alembic" / "versions").glob("4edb5c967539_*.py")
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("r8_pr2", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_json_list_is_every_model_json_column() -> None:
    models = {
        (table.name, column.name, bool(column.nullable))
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, JSON)
    }
    assert set(_migration().JSON_COLUMNS) == models


def test_the_clock_list_is_every_utc_default() -> None:
    models = {
        (table.name, column.name)
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(getattr(column.server_default, "arg", None), utc_now)
    }
    assert {(t, c) for t, c, _ in _migration().TIMESTAMP_DEFAULTS} == models


def test_the_identity_trigger_guards_the_services_identity_columns() -> None:
    """Same set FragranceService.update refuses on a referenced version."""
    migration = _migration()
    assert set(migration.IDENTITY_COLUMNS) == {
        "id",
        "name",
        "brand",
        "concentration",
        "launch_year",
        "version_key",
        "gender_target",
        "primary_family",
        "subfamily",
        "intensity",
    }
    for column in migration.IDENTITY_COLUMNS:
        assert f"NEW.{column}" in migration.IDENTITY_FUNCTION_SQL
        assert f"OLD.{column}" in migration.IDENTITY_FUNCTION_SQL


def test_the_observation_trigger_exempts_only_training_eligibility() -> None:
    sql = _migration().OBSERVATION_FUNCTION_SQL
    assert sql.count("- 'training_eligibility'") == 2
    assert "DELETE" in sql


def test_each_trigger_names_a_created_function() -> None:
    migration = _migration()
    functions = {name for name, _ in migration.FUNCTIONS}
    assert {function for *_, function in migration.TRIGGERS} <= functions
    for name, body in migration.FUNCTIONS:
        assert f"CREATE FUNCTION {name}()" in body


class _RecordingOp:
    def __init__(self, bind: sa.Connection) -> None:
        self.bind = bind
        self.calls: list[str] = []

    def get_bind(self) -> sa.Connection:
        return self.bind

    def execute(self, statement: str) -> None:
        self.calls.append(statement.strip().split("\n")[0])

    def alter_column(self, table: str, column: str, **_kw: object) -> None:
        self.calls.append(f"alter {table}.{column}")

    def batch_alter_table(self, table: str) -> _RecordingOp:
        self.calls.append(f"batch {table}")
        return self

    def __enter__(self) -> _RecordingOp:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def add_column(self, column: sa.Column[object]) -> None:
        self.calls.append(f"add {column.name}")

    def create_unique_constraint(self, name: str, *_a: object) -> None:
        self.calls.append(f"unique {name}")

    def create_check_constraint(self, name: str, *_a: object) -> None:
        self.calls.append(f"check {name}")

    def drop_constraint(self, name: str, **_kw: object) -> None:
        self.calls.append(f"drop {name}")

    def drop_column(self, name: str) -> None:
        self.calls.append(f"drop column {name}")


def _observations(keyed: int) -> sa.Connection:
    connection = sa.create_engine("sqlite://").connect()
    connection.execute(
        text("CREATE TABLE calibration_observations (id TEXT, idempotency_key TEXT)")
    )
    for index in range(keyed):
        connection.execute(
            text("INSERT INTO calibration_observations VALUES (:i, :k)"),
            {"i": str(index), "k": f"key-{index:08d}"},
        )
    connection.execute(text("INSERT INTO calibration_observations VALUES ('x', NULL)"))
    return connection


def test_the_upgrade_drops_the_view_first_and_creates_the_views_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration()
    recorder = _RecordingOp(_observations(0))
    monkeypatch.setattr(migration, "op", recorder)

    migration.upgrade()

    assert recorder.calls[0] == "DROP VIEW IF EXISTS v_training_rows"
    assert recorder.calls[-2:] == [
        "CREATE VIEW v_training_rows AS",
        "CREATE VIEW v_manager_linkage AS",
    ]
    # SQLite: no jsonb, no clock defaults, no triggers; the key still lands.
    assert not [c for c in recorder.calls if c.startswith(("alter", "CREATE TRIGGER"))]
    assert "add idempotency_key" in recorder.calls


def test_the_downgrade_refuses_while_a_key_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration()
    recorder = _RecordingOp(_observations(2))
    monkeypatch.setattr(migration, "op", recorder)

    with pytest.raises(RuntimeError, match=r"4edb5c967539.*2 observation.*backup"):
        migration.downgrade()
    assert recorder.calls == []


def test_the_downgrade_restores_pr_ones_view_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration()
    recorder = _RecordingOp(_observations(0))
    monkeypatch.setattr(migration, "op", recorder)

    migration.downgrade()

    assert recorder.calls[:2] == [
        "DROP VIEW IF EXISTS v_manager_linkage",
        "DROP VIEW IF EXISTS v_training_rows",
    ]
    assert recorder.calls[-1] == "CREATE VIEW v_training_rows AS"
    assert "drop column idempotency_key" in recorder.calls
    assert "revealed" not in migration.V_TRAINING_ROWS_PR1_SQL


def test_the_downgrade_view_is_pr_ones_verbatim() -> None:
    path = next(MIGRATION.parent.glob("620c8c861268_*.py"))
    spec = importlib.util.spec_from_file_location("r8_pr1", path)
    assert spec is not None
    assert spec.loader is not None
    pr1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pr1)
    assert _migration().V_TRAINING_ROWS_PR1_SQL == pr1.V_TRAINING_ROWS_SQL
