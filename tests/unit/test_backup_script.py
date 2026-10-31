"""``scripts/backup_database.sh`` against stand-in PostgreSQL tools (R14, D-18).

The script runs in the postgres image on a schedule, so what matters is its
decisions: it only records a backup that was verified, it never leaves a
half-written file that could pass for one, it prunes by age but never below a
floor, and its health check goes red when backups stop. The stand-ins let those
decisions run without a database; ``tests/integration/test_backup_restore_postgres.py``
runs the real tools.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_database.sh"

_PG_DUMP = """#!/bin/sh
[ -n "${STUB_FAIL_DUMP:-}" ] && { echo "pg_dump: connection refused" >&2; exit 1; }
for arg in "$@"; do
  case "$arg" in --file=*) target="${arg#--file=}";; esac
done
printf '%s' "${STUB_DUMP_BODY-PGDMP stand-in}" > "$target"
"""
_PG_RESTORE = """#!/bin/sh
[ -n "${STUB_FAIL_LIST:-}" ] && { echo "pg_restore: unreadable" >&2; exit 1; }
exit 0
"""
_PSQL = """#!/bin/sh
[ -n "${STUB_NO_REVISION:-}" ] && exit 1
echo "${STUB_REVISION:-abc123def456}"
"""


@pytest.fixture
def tools(tmp_path: Path) -> Path:
    """A directory of stand-in ``pg_dump``, ``pg_restore``, and ``psql``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (
        ("pg_dump", _PG_DUMP),
        ("pg_restore", _PG_RESTORE),
        ("psql", _PSQL),
    ):
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    return bin_dir


def run(
    action: str, tools: Path, backups: Path, **env: str
) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": f"{tools}:{os.environ['PATH']}",
        "BACKUP_DIR": str(backups),
        **env,
    }
    return subprocess.run(  # noqa: S603 - fixed argv, test-controlled environment
        ["sh", str(SCRIPT), action],  # noqa: S607
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def dumps(backups: Path) -> list[Path]:
    return sorted(backups.glob("fragrance_rater-*.dump"))


def test_a_backup_is_written_with_checksum_manifest_and_marker(
    tools: Path, tmp_path: Path
) -> None:
    backups = tmp_path / "backups"

    result = run("backup", tools, backups, STUB_REVISION="f74bf7ff9c2d")

    assert result.returncode == 0, result.stderr
    (dump,) = dumps(backups)
    manifest = json.loads((backups / f"{dump.name}.json").read_text())
    assert manifest["file"] == dump.name
    assert manifest["alembic_revision"] == "f74bf7ff9c2d"
    assert manifest["bytes"] == dump.stat().st_size
    recorded = (backups / f"{dump.name}.sha256").read_text().split()
    assert recorded == [manifest["sha256"], dump.name]
    assert (backups / "latest.ok").read_text().strip() == dump.name


def test_backups_are_private_to_their_owner(tools: Path, tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    run("backup", tools, backups)

    for path in backups.iterdir():
        assert path.stat().st_mode & 0o077 == 0, path.name


def test_the_revision_is_unknown_when_it_cannot_be_read(
    tools: Path, tmp_path: Path
) -> None:
    backups = tmp_path / "backups"

    result = run("backup", tools, backups, STUB_NO_REVISION="1")

    assert result.returncode == 0
    (dump,) = dumps(backups)
    assert (
        json.loads((backups / f"{dump.name}.json").read_text())["alembic_revision"]
        == "unknown"
    )


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"STUB_FAIL_DUMP": "1"}, "pg_dump failed"),
        ({"STUB_DUMP_BODY": ""}, "the dump is empty"),
        ({"STUB_FAIL_LIST": "1"}, "cannot be read back"),
    ],
)
def test_a_backup_that_is_not_verified_leaves_nothing_behind(
    tools: Path, tmp_path: Path, env: dict[str, str], message: str
) -> None:
    """No dump, no partial file, and no success marker (so `check` stays red)."""
    backups = tmp_path / "backups"

    result = run("backup", tools, backups, **env)

    assert result.returncode == 1
    assert message in result.stderr
    assert sorted(path.name for path in backups.iterdir()) == []


def test_a_failed_backup_does_not_move_the_success_marker(
    tools: Path, tmp_path: Path
) -> None:
    backups = tmp_path / "backups"
    run("backup", tools, backups)
    before = (backups / "latest.ok").read_text()

    result = run("backup", tools, backups, STUB_FAIL_DUMP="1")

    assert result.returncode == 1
    assert (backups / "latest.ok").read_text() == before


def _age(path: Path, days: int) -> None:
    moment = time.time() - days * 86400
    os.utime(path, (moment, moment))


def _old_backup(backups: Path, stamp: str, days: int) -> Path:
    backups.mkdir(exist_ok=True)
    dump = backups / f"fragrance_rater-{stamp}.dump"
    dump.write_text("old")
    for suffix in (".sha256", ".json"):
        (backups / f"{dump.name}{suffix}").write_text("old")
    _age(dump, days)
    return dump


def test_old_backups_are_pruned_with_their_checksum_and_manifest(
    tools: Path, tmp_path: Path
) -> None:
    backups = tmp_path / "backups"
    for index, stamp in enumerate(
        ["20260101T000000Z", "20260102T000000Z", "20260103T000000Z"]
    ):
        _old_backup(backups, stamp, days=60 - index)

    result = run(
        "backup", tools, backups, BACKUP_RETENTION_DAYS="14", BACKUP_KEEP_MIN="1"
    )

    assert result.returncode == 0
    names = [dump.name for dump in dumps(backups)]
    assert len(names) == 1
    assert names[0] > "fragrance_rater-2026103"  # only the fresh backup survives
    assert not list(backups.glob("*20260101*"))
    assert "pruned" in result.stdout


def test_the_newest_backups_are_never_pruned_however_old(
    tools: Path, tmp_path: Path
) -> None:
    """A floor protects against pruning everything when the clock or job is off."""
    backups = tmp_path / "backups"
    for stamp in ["20260101T000000Z", "20260102T000000Z", "20260103T000000Z"]:
        _old_backup(backups, stamp, days=400)

    run("backup", tools, backups, BACKUP_RETENTION_DAYS="1", BACKUP_KEEP_MIN="3")

    # The new dump plus the two newest old ones: three kept in total.
    assert len(dumps(backups)) == 3
    assert not list(backups.glob("*20260101*"))


def test_recent_backups_are_kept_even_beyond_the_floor(
    tools: Path, tmp_path: Path
) -> None:
    backups = tmp_path / "backups"
    for stamp in ["20261001T000000Z", "20261002T000000Z", "20261003T000000Z"]:
        _old_backup(backups, stamp, days=2)

    run("backup", tools, backups, BACKUP_RETENTION_DAYS="14", BACKUP_KEEP_MIN="1")

    assert len(dumps(backups)) == 4


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("BACKUP_RETENTION_DAYS", "forever"),
        ("BACKUP_KEEP_MIN", "-1"),
        ("BACKUP_MAX_AGE_HOURS", "1.5"),
    ],
)
def test_non_numeric_settings_are_refused_before_anything_runs(
    tools: Path, tmp_path: Path, name: str, value: str
) -> None:
    backups = tmp_path / "backups"

    result = run("backup", tools, backups, **{name: value})

    assert result.returncode == 1
    assert name in result.stderr
    assert not backups.exists()


def test_check_passes_for_a_fresh_backup(tools: Path, tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    run("backup", tools, backups)

    result = run("check", tools, backups)

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_check_fails_when_no_backup_was_ever_recorded(
    tools: Path, tmp_path: Path
) -> None:
    result = run("check", tools, tmp_path / "empty")

    assert result.returncode == 1
    assert "no successful backup" in result.stderr


def test_check_fails_when_the_last_backup_is_stale(tools: Path, tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    run("backup", tools, backups)
    _age(backups / "latest.ok", days=3)

    result = run("check", tools, backups, BACKUP_MAX_AGE_HOURS="30")

    assert result.returncode == 1
    assert "older than 30 hours" in result.stderr


def test_check_fails_when_the_recorded_dump_has_gone(
    tools: Path, tmp_path: Path
) -> None:
    backups = tmp_path / "backups"
    run("backup", tools, backups)
    (dump,) = dumps(backups)
    dump.unlink()

    result = run("check", tools, backups)

    assert result.returncode == 1
    assert "is missing" in result.stderr


def test_an_unknown_action_is_refused(tools: Path, tmp_path: Path) -> None:
    result = run("restore", tools, tmp_path / "backups")

    assert result.returncode == 1
    assert "usage" in result.stderr
