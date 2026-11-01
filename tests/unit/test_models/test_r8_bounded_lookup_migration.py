"""Migration 736b7db082fb: drop ``bounded_lookup`` from the source snapshot vocabulary.

Pins that the "previous" CHECKs restored by the downgrade are the ones the earlier
migrations created, that the new ones no longer name the value, and that the upgrade
refuses rather than guessing when a row still uses it.
"""

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from sqlalchemy import CheckConstraint

from fragrance_rater.models import Base

if TYPE_CHECKING:
    from collections.abc import Iterator
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


MIGRATION = _load("736b7db082fb")
R8_PR1 = _load("620c8c861268")


class _RecordingOp:
    def __init__(self, bind: sa.Connection | None = None) -> None:
        self.bind = bind
        self.calls: list[tuple[str, str]] = []

    def get_bind(self) -> sa.Connection:
        assert self.bind is not None
        return self.bind

    @contextmanager
    def batch_alter_table(self, _table: str) -> Iterator[_RecordingOp]:
        yield self

    def drop_constraint(self, name: str, *, type_: str) -> None:
        assert type_ == "check"
        self.calls.append(("drop", name))

    def create_check_constraint(self, name: str, condition: str) -> None:
        self.calls.append(("create", name))
        self.created = getattr(self, "created", {}) | {name: condition}


def _bind_with(source_type: str | None) -> sa.Connection:
    engine = sa.create_engine("sqlite://")
    connection = engine.connect()
    metadata = sa.MetaData()
    table = sa.Table(
        MIGRATION.TABLE,
        metadata,
        sa.Column("id", sa.Integer),
        sa.Column("source_type", sa.String),
    )
    metadata.create_all(connection)
    if source_type is not None:
        connection.execute(table.insert().values(id=1, source_type=source_type))
    return connection


def test_it_follows_the_view_migration() -> None:
    assert MIGRATION.down_revision == "52e22be935d3"


def test_the_previous_pair_check_is_the_one_620c8c861268_created() -> None:
    assert MIGRATION.PREVIOUS_PAIR_SQL == R8_PR1._PAIR_CHECK


def test_the_migration_checks_equal_the_model_checks() -> None:
    constraints = {
        c.name: str(c.sqltext)
        for c in Base.metadata.tables[MIGRATION.TABLE].constraints
        if isinstance(c, CheckConstraint)
    }

    assert constraints[MIGRATION.PAIR_CHECK] == MIGRATION.PAIR_SQL
    assert constraints[MIGRATION.TYPE_CHECK] == MIGRATION.TYPE_SQL


def test_the_new_checks_no_longer_name_the_value() -> None:
    assert "bounded_lookup" not in MIGRATION.TYPE_SQL
    assert "bounded_lookup" not in MIGRATION.PAIR_SQL
    assert "bounded_lookup" in MIGRATION.PREVIOUS_TYPE_SQL
    assert "bounded_lookup" in MIGRATION.PREVIOUS_PAIR_SQL


def test_upgrade_replaces_both_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _RecordingOp(_bind_with(None))
    monkeypatch.setattr(MIGRATION, "op", recorder)

    MIGRATION.upgrade()

    assert recorder.calls == [
        ("drop", MIGRATION.TYPE_CHECK),
        ("drop", MIGRATION.PAIR_CHECK),
        ("create", MIGRATION.TYPE_CHECK),
        ("create", MIGRATION.PAIR_CHECK),
    ]
    assert recorder.created[MIGRATION.TYPE_CHECK] == MIGRATION.TYPE_SQL
    assert recorder.created[MIGRATION.PAIR_CHECK] == MIGRATION.PAIR_SQL


def test_upgrade_refuses_while_a_row_still_uses_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _RecordingOp(_bind_with("bounded_lookup"))
    monkeypatch.setattr(MIGRATION, "op", recorder)

    with pytest.raises(RuntimeError, match=r"736b7db082fb.*1 source snapshot"):
        MIGRATION.upgrade()
    assert recorder.calls == []


def test_downgrade_restores_the_previous_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _RecordingOp()
    monkeypatch.setattr(MIGRATION, "op", recorder)

    MIGRATION.downgrade()

    assert recorder.created[MIGRATION.TYPE_CHECK] == MIGRATION.PREVIOUS_TYPE_SQL
    assert recorder.created[MIGRATION.PAIR_CHECK] == MIGRATION.PREVIOUS_PAIR_SQL
