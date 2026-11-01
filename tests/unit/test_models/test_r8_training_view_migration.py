"""Migration 52e22be935d3: an invalidated later answer does not supersede.

The view change is one added condition. These tests pin that, so the migration
cannot quietly redefine anything else, and check the downgrade restores the
previous definition exactly.
"""

from __future__ import annotations

import difflib
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

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


MIGRATION = _load("52e22be935d3")
R8_PR2 = _load("4edb5c967539")


class _RecordingOp:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)


def test_it_follows_the_quality_flag_outcome_migration() -> None:
    assert MIGRATION.down_revision == "50c1f75abb15"


def test_the_downgrade_target_is_the_previous_definition_verbatim() -> None:
    assert MIGRATION.V_TRAINING_ROWS_PREVIOUS_SQL == R8_PR2.V_TRAINING_ROWS_SQL


def test_the_only_change_is_the_invalidated_exemption() -> None:
    diff = [
        line
        for line in difflib.unified_diff(
            MIGRATION.V_TRAINING_ROWS_PREVIOUS_SQL.splitlines(),
            MIGRATION.V_TRAINING_ROWS_SQL.splitlines(),
            lineterm="",
            n=0,
        )
        if not line.startswith(("---", "+++", "@@"))
    ]

    assert diff == ["+        AND later.training_eligibility <> 'invalidated'"]


def test_the_exemption_sits_inside_the_supersession_subquery() -> None:
    sql = MIGRATION.V_TRAINING_ROWS_SQL
    start = sql.index("FROM calibration_observations AS later")
    end = sql.index(")", sql.index("later.id > o.id"))

    assert "later.training_eligibility <> 'invalidated'" in sql[start:end]


def test_upgrade_drops_then_recreates_only_the_training_view(monkeypatch) -> None:
    recorder = _RecordingOp()
    monkeypatch.setattr(MIGRATION, "op", recorder)

    MIGRATION.upgrade()

    assert recorder.statements == [
        "DROP VIEW IF EXISTS v_training_rows",
        MIGRATION.V_TRAINING_ROWS_SQL,
    ]


def test_downgrade_restores_the_previous_definition(monkeypatch) -> None:
    recorder = _RecordingOp()
    monkeypatch.setattr(MIGRATION, "op", recorder)

    MIGRATION.downgrade()

    assert recorder.statements == [
        "DROP VIEW IF EXISTS v_training_rows",
        R8_PR2.V_TRAINING_ROWS_SQL,
    ]
