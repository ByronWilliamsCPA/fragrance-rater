"""Tests for the pure, database-free logic in ``scripts/p1_migration_inventory.py``.

Covers ``compare()`` and its ``_compare_*``/``_section``/``_unverifiable``
helpers (pure dict-diffing, no I/O), the ``--compare`` file error handling in
``main()`` (with ``build_inventory`` mocked out so no live PostgreSQL
connection is required), and ``_database_url()``. Anything that talks to a
real database (``build_inventory``, ``_row_count``, ``_timestamp_range``,
``_redacted_hash``, ``_alembic_version``, the DB-calling ``_invalid_foreign_keys``)
is intentionally left uncovered; it needs ``P1_DATABASE_URL`` against a live
clone, which this sandbox does not have.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parents[3]


def load_script(name: str) -> ModuleType:
    """Load a repository script as a module."""
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module() -> ModuleType:
    """Load the script fresh for each test."""
    return load_script("p1_migration_inventory")


def _full_snapshot() -> dict[str, Any]:
    """A realistic full inventory as ``build_inventory()`` would produce it."""
    return {
        "alembic_version": "abc123",
        "row_counts": {
            "fragrances": 10,
            "reviewers": 3,
            "evaluations": 25,
            "calibration_programs": 1,
            "calibration_memberships": 5,
        },
        "timestamp_ranges": {
            "fragrances": {"min": "2026-01-01T00:00:00", "max": "2026-06-01T00:00:00"},
            "reviewers": {"min": "2026-01-01T00:00:00", "max": "2026-01-02T00:00:00"},
            "evaluations": {"min": "2026-01-01T00:00:00", "max": "2026-07-01T00:00:00"},
        },
        "redacted_hashes": {
            "fragrances": {
                "id": "hash-frag-id",
                "name": "hash-frag-name",
                "brand": "hash-frag-brand",
            },
            "reviewers": {
                "id": "hash-rev-id",
                "display_name": "hash-rev-name",
            },
            "evaluations": {
                "id": "hash-eval-id",
                "rating": "hash-eval-rating",
                "fragrance_id": "hash-eval-fragrance-id",
            },
        },
        "duplicate_natural_keys": {"Scent / House / EDT / v1": 2},
        "invalid_foreign_keys": {
            "orphaned_evaluations": 0,
            "orphaned_calibration_memberships": 0,
        },
    }


# ---------------------------------------------------------------------------
# compare(): identical snapshots
# ---------------------------------------------------------------------------


def test_compare_identical_snapshots_reports_no_violations(module: ModuleType) -> None:
    """An unchanged migration (before == after) preserves everything."""
    before = _full_snapshot()
    after = copy.deepcopy(before)

    violations = module.compare(before, after)

    assert violations == []


# ---------------------------------------------------------------------------
# compare(): missing/malformed before-snapshot must not read as "no changes"
# ---------------------------------------------------------------------------


def test_compare_empty_before_snapshot_is_flagged_unverifiable(
    module: ModuleType,
) -> None:
    """An empty before-snapshot triggers unverifiable violations, not []."""
    after = _full_snapshot()

    violations = module.compare({}, after)

    assert violations != []
    # One unverifiable violation per preserved table per check (row counts,
    # timestamp ranges, hashes), plus the two top-level sections.
    assert len(violations) == 3 * 3 + 2
    assert all("cannot verify preservation" in v for v in violations)
    assert any("missing or unreadable for table fragrances" in v for v in violations)
    assert any("missing or unreadable for table reviewers" in v for v in violations)
    assert any("missing or unreadable for table evaluations" in v for v in violations)
    assert any(
        "before-snapshot has no readable duplicate_natural_keys section" in v
        for v in violations
    )
    assert any(
        "before-snapshot has no readable invalid_foreign_keys section" in v
        for v in violations
    )


def test_compare_malformed_before_section_is_flagged_unverifiable(
    module: ModuleType,
) -> None:
    """A before-snapshot with a non-dict section is unverifiable, not silent."""
    before = _full_snapshot()
    before["row_counts"] = "not-a-dict"
    after = _full_snapshot()

    violations = module.compare(before, after)

    assert any(
        "missing or unreadable for table fragrances (no row count)" in v
        for v in violations
    )


# ---------------------------------------------------------------------------
# compare(): per-column hash diffs
# ---------------------------------------------------------------------------


def test_compare_hashes_flags_changed_column_by_name(module: ModuleType) -> None:
    """A changed per-column hash names the exact table.column that moved."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["redacted_hashes"]["evaluations"]["rating"] = "hash-eval-rating-CHANGED"
    after["redacted_hashes"]["fragrances"]["name"] = "hash-frag-name-CHANGED"

    violations = module.compare(before, after)

    assert (
        "evaluations.rating: content hash changed -- values in this column "
        "were not preserved" in violations
    )
    assert (
        "fragrances.name: content hash changed -- values in this column "
        "were not preserved" in violations
    )
    # Unrelated columns in the same tables are untouched.
    assert not any(
        v.startswith(("evaluations.id:", "fragrances.brand:")) for v in violations
    )


def test_compare_hashes_flags_dropped_column(module: ModuleType) -> None:
    """A column present before the migration but absent after it is flagged."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    del after["redacted_hashes"]["reviewers"]["display_name"]

    violations = module.compare(before, after)

    assert (
        "reviewers.display_name: column existed before the migration and "
        "is missing after it" in violations
    )


def test_compare_hashes_does_not_flag_added_column(module: ModuleType) -> None:
    """A brand-new column in after (a legitimate schema addition) is not a violation."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["redacted_hashes"]["fragrances"]["new_column"] = "hash-brand-new"

    violations = module.compare(before, after)

    assert violations == []


# ---------------------------------------------------------------------------
# compare(): row counts and timestamp ranges
# ---------------------------------------------------------------------------


def test_compare_row_counts_flags_mismatch(module: ModuleType) -> None:
    """A row-count delta on a preserved table is a violation."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["row_counts"]["evaluations"] = 20

    violations = module.compare(before, after)

    assert "evaluations: row count changed (25 -> 20)" in violations


def test_compare_timestamp_ranges_flags_mismatch(module: ModuleType) -> None:
    """A changed created_at min or max on a preserved table is a violation."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["timestamp_ranges"]["fragrances"]["max"] = "2026-09-01T00:00:00"

    violations = module.compare(before, after)

    assert (
        "fragrances: created_at max changed "
        "(2026-06-01T00:00:00 -> 2026-09-01T00:00:00)" in violations
    )


def test_compare_row_counts_flags_table_gone_after_migration(
    module: ModuleType,
) -> None:
    """A table with no row count in the after-snapshot is flagged as gone."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    del after["row_counts"]["evaluations"]

    violations = module.compare(before, after)

    assert (
        "evaluations: no row count in the after-snapshot; the table is gone"
        in violations
    )


def test_compare_timestamp_ranges_flags_missing_in_after(module: ModuleType) -> None:
    """A table with no created_at range in the after-snapshot is flagged."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    del after["timestamp_ranges"]["fragrances"]

    violations = module.compare(before, after)

    assert "fragrances: no created_at range in the after-snapshot" in violations


def test_compare_hashes_flags_missing_table_in_after(module: ModuleType) -> None:
    """A table with no per-column hashes at all in the after-snapshot is flagged."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    del after["redacted_hashes"]["fragrances"]

    violations = module.compare(before, after)

    assert (
        "fragrances: no per-column content hashes in the after-snapshot" in violations
    )


# ---------------------------------------------------------------------------
# compare(): duplicate natural keys
# ---------------------------------------------------------------------------


def test_compare_duplicate_natural_keys_flags_count_delta(module: ModuleType) -> None:
    """A changed live-duplicate count for an existing key is flagged."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["duplicate_natural_keys"]["Scent / House / EDT / v1"] = 3

    violations = module.compare(before, after)

    assert (
        "duplicate natural key 'Scent / House / EDT / v1': live row count "
        "changed (2 -> 3)" in violations
    )


def test_compare_duplicate_natural_keys_flags_new_key_after_migration(
    module: ModuleType,
) -> None:
    """A duplicate key that only exists after the migration is flagged."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["duplicate_natural_keys"]["Other / House / EDT / v1"] = 2

    violations = module.compare(before, after)

    assert (
        "duplicate natural key 'Other / House / EDT / v1': live row count "
        "changed (0 -> 2)" in violations
    )


# ---------------------------------------------------------------------------
# compare(): invalid foreign keys / orphaned-row checks
# ---------------------------------------------------------------------------


def test_compare_invalid_foreign_keys_flags_count_delta(module: ModuleType) -> None:
    """A changed orphaned-row count for a check run both times is flagged."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["invalid_foreign_keys"]["orphaned_evaluations"] = 4

    violations = module.compare(before, after)

    assert "orphaned_evaluations: orphaned row count changed (0 -> 4)" in violations


def test_compare_invalid_foreign_keys_flags_check_not_rerun(module: ModuleType) -> None:
    """A check that ran before but not after is flagged, not silently dropped."""
    before = _full_snapshot()
    before["invalid_foreign_keys"]["orphaned_memberships_legacy"] = 0
    after = _full_snapshot()

    violations = module.compare(before, after)

    assert (
        "orphaned_memberships_legacy: ran before the migration but not "
        "after it, cannot verify preservation" in violations
    )


def test_compare_invalid_foreign_keys_flags_new_check_with_orphans(
    module: ModuleType,
) -> None:
    """A check that only exists after the migration, and finds orphans, is flagged."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["invalid_foreign_keys"]["orphaned_new_thing"] = 3

    violations = module.compare(before, after)

    assert (
        "orphaned_new_thing: 3 orphaned rows after the migration (this "
        "check could not run before it)" in violations
    )


def test_compare_invalid_foreign_keys_ignores_new_check_with_no_orphans(
    module: ModuleType,
) -> None:
    """A new check that finds zero orphans after the migration is not a violation."""
    before = _full_snapshot()
    after = copy.deepcopy(before)
    after["invalid_foreign_keys"]["orphaned_new_thing"] = 0

    violations = module.compare(before, after)

    assert violations == []


# ---------------------------------------------------------------------------
# main(): --compare file handling (build_inventory mocked, no live DB)
# ---------------------------------------------------------------------------


async def _fake_build_inventory(_database_url: str) -> dict[str, Any]:
    """Stand in for the real, DB-calling build_inventory()."""
    return _full_snapshot()


def _run_main_with_compare(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    compare_path: Path,
) -> int:
    """Invoke main() with a mocked build_inventory and the given --compare file."""
    monkeypatch.setenv("P1_DATABASE_URL", "postgresql://<user>:<password>@<host>/<db>")
    monkeypatch.setattr(module, "build_inventory", _fake_build_inventory)
    output_path = tmp_path / "after.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "p1_migration_inventory.py",
            "--output",
            str(output_path),
            "--compare",
            str(compare_path),
        ],
    )
    return module.main()


def test_main_missing_compare_file_exits_2_with_clear_message(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A --compare path that does not exist fails cleanly, not with a traceback."""
    missing = tmp_path / "does-not-exist.json"

    exit_code = _run_main_with_compare(module, monkeypatch, tmp_path, missing)

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "could not read the before-snapshot" in captured.err
    assert "post-migration comparison did not run" in captured.err


def test_main_invalid_json_compare_file_exits_2_with_clear_message(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A truncated/corrupted --compare JSON file fails cleanly, not with a traceback."""
    corrupt = tmp_path / "before.json"
    corrupt.write_text("{not valid json", encoding="utf-8")

    exit_code = _run_main_with_compare(module, monkeypatch, tmp_path, corrupt)

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "is not valid JSON" in captured.err
    assert "post-migration comparison did not run" in captured.err


def test_main_non_object_compare_file_exits_2_with_clear_message(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Valid JSON that is not an inventory object (e.g. a list) fails cleanly."""
    non_object = tmp_path / "before.json"
    non_object.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    exit_code = _run_main_with_compare(module, monkeypatch, tmp_path, non_object)

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "is not an inventory object" in captured.err
    assert "post-migration comparison did not run" in captured.err


def test_main_valid_compare_file_with_violation_exits_1(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A readable before-snapshot that genuinely differs exits 1, not 2."""
    before = _full_snapshot()
    before["row_counts"]["evaluations"] = 999
    compare_path = tmp_path / "before.json"
    compare_path.write_text(json.dumps(before), encoding="utf-8")

    exit_code = _run_main_with_compare(module, monkeypatch, tmp_path, compare_path)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "PRESERVATION VIOLATION" in captured.err


# ---------------------------------------------------------------------------
# _database_url()
# ---------------------------------------------------------------------------


def test_database_url_missing_raises_clear_error(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unset P1_DATABASE_URL raises a clear, actionable error."""
    monkeypatch.delenv("P1_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="P1_DATABASE_URL is not set"):
        module._database_url()


def test_database_url_rejects_sqlalchemy_scheme(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A postgresql+asyncpg:// SQLAlchemy DSN is rejected with a clear error."""
    monkeypatch.setenv("P1_DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")

    with pytest.raises(RuntimeError, match="SQLAlchemy driver scheme"):
        module._database_url()


def test_database_url_accepts_plain_postgresql_scheme(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain postgresql:// asyncpg DSN passes through unchanged."""
    monkeypatch.setenv(
        "P1_DATABASE_URL", "  postgresql://<user>:<password>@<host>/<db>  "
    )

    assert module._database_url() == "postgresql://<user>:<password>@<host>/<db>"
