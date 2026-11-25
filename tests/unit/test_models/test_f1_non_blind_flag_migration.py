"""Migration d7f3a91c5b28: the non_blind and ceiling quality-flag codes.

Pins that the CHECK the upgrade leaves is the model's vocabulary, that the
downgrade restores cd1e2375a2e4's list exactly, and that the downgrade refuses
while a flag row carries a new code (a flag is append-only evidence).
"""

from __future__ import annotations

import importlib.util
import re
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

from fragrance_rater.models.calibration import QUALITY_FLAG_CODES

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


MIGRATION = _load("d7f3a91c5b28")
GOVERNANCE = _load("cd1e2375a2e4")


class _RecordingOp:
    def __init__(self, bind: sa.Connection | None = None) -> None:
        self.bind = bind
        self.calls: list[tuple[str, str]] = []
        self.created: dict[str, str] = {}

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
        self.created[name] = condition


def _bind_with(code: str | None) -> sa.Connection:
    connection = sa.create_engine("sqlite://").connect()
    metadata = sa.MetaData()
    table = sa.Table(
        MIGRATION.TABLE,
        metadata,
        sa.Column("id", sa.Integer),
        sa.Column("code", sa.String),
    )
    metadata.create_all(connection)
    if code is not None:
        connection.execute(table.insert().values(id=1, code=code))
    return connection


def _codes(sql: str) -> set[str]:
    return set(re.findall(r"'([^']*)'", sql))


def test_it_follows_the_bounded_lookup_migration() -> None:
    assert MIGRATION.down_revision == "736b7db082fb"


def test_the_new_list_is_the_model_vocabulary() -> None:
    assert _codes(MIGRATION.CODES_SQL) == set(QUALITY_FLAG_CODES)
    assert set(MIGRATION.NEW_CODES) <= set(QUALITY_FLAG_CODES)


def test_the_previous_list_is_what_cd1e2375a2e4_created() -> None:
    assert _codes(MIGRATION.PREVIOUS_CODES_SQL) == set(QUALITY_FLAG_CODES) - set(
        MIGRATION.NEW_CODES
    )
    source = Path(GOVERNANCE.__file__).read_text(encoding="utf-8")
    for code in _codes(MIGRATION.PREVIOUS_CODES_SQL):
        assert f"'{code}'" in source


def test_upgrade_recreates_the_code_check(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _RecordingOp()
    monkeypatch.setattr(MIGRATION, "op", recorder)

    MIGRATION.upgrade()

    assert recorder.calls == [("drop", MIGRATION.CHECK), ("create", MIGRATION.CHECK)]
    assert recorder.created[MIGRATION.CHECK] == MIGRATION.CODES_SQL


def test_downgrade_restores_the_previous_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _RecordingOp(_bind_with("competing_odor"))
    monkeypatch.setattr(MIGRATION, "op", recorder)

    MIGRATION.downgrade()

    assert recorder.created[MIGRATION.CHECK] == MIGRATION.PREVIOUS_CODES_SQL


@pytest.mark.parametrize("code", MIGRATION.NEW_CODES)
def test_downgrade_refuses_while_a_row_uses_a_new_code(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    recorder = _RecordingOp(_bind_with(code))
    monkeypatch.setattr(MIGRATION, "op", recorder)

    with pytest.raises(RuntimeError, match=r"d7f3a91c5b28.*1 quality flag"):
        MIGRATION.downgrade()
    assert recorder.calls == []
