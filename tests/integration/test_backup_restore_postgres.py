"""Backup and restore against a real PostgreSQL 16 (R14, D-18).

Takes a real backup of the migrated test database with
``scripts/backup_database.sh``, then proves it with ``scripts/verify_restore.py``:
a restore into a scratch database, an inventory comparison against the live
database, and the failure paths (a tampered checksum, a truncated dump, a source
that does not match, a failed dump). The unit tests in
``tests/unit/test_backup_script.py`` and ``tests/unit/test_verify_restore.py``
cover the decisions with stand-in tools; this runs the real ones.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import asyncpg
import pytest

if TYPE_CHECKING:
    from types import ModuleType

DATABASE_URL = os.getenv("P1_DATABASE_URL")
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="P1_DATABASE_URL is not configured"),
    pytest.mark.skipif(
        not all(shutil.which(tool) for tool in ("pg_dump", "pg_restore", "psql")),
        reason="the PostgreSQL client tools are not installed",
    ),
]


def _load(name: str) -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


restore_tool = _load("verify_restore")
inventory_tool = _load("p1_migration_inventory")


def plain_url() -> str:
    """The application's SQLAlchemy URL, in the plain form libpq tools take."""
    assert DATABASE_URL is not None
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


def admin_url() -> str:
    return restore_tool.database_url(plain_url(), "postgres")


def take_backup(directory: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        **restore_tool.connection_environment(plain_url()),
        "BACKUP_DIR": str(directory),
        **overrides,
    }
    return subprocess.run(  # noqa: S603 - fixed argv, test-controlled environment
        ["sh", str(SCRIPTS / "backup_database.sh"), "backup"],  # noqa: S607
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def live_inventory() -> dict[str, Any]:
    return asyncio.run(inventory_tool.build_inventory(plain_url()))


def scratch_databases() -> list[str]:
    async def names() -> list[str]:
        connection = await asyncpg.connect(admin_url())
        try:
            rows = await connection.fetch(
                "SELECT datname FROM pg_database WHERE datname LIKE 'restore_verify_%'"
            )
        finally:
            await connection.close()
        return [row["datname"] for row in rows]

    return asyncio.run(names())


@pytest.fixture
def backup(tmp_path: Path) -> Path:
    result = take_backup(tmp_path)
    assert result.returncode == 0, result.stderr
    (dump,) = tmp_path.glob("fragrance_rater-*.dump")
    return dump


def test_the_backup_script_writes_a_readable_dump_with_the_live_revision(
    backup: Path,
) -> None:
    manifest = json.loads((backup.parent / f"{backup.name}.json").read_text())

    assert manifest["alembic_revision"] == live_inventory()["alembic_version"]
    assert manifest["bytes"] == backup.stat().st_size > 0
    assert restore_tool.check_checksum(backup) is True
    listing = subprocess.run(  # noqa: S603 - fixed argv
        ["pg_restore", "--list", str(backup)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    assert "alembic_version" in listing.stdout


def test_a_backup_restores_and_matches_the_live_database(backup: Path) -> None:
    evidence = asyncio.run(restore_tool.verify(admin_url(), backup, live_inventory()))

    assert evidence["verified"] is True
    assert evidence["violations"] == []
    assert evidence["checksum_matches_sidecar"] is True
    assert evidence["compared_with_source"] is True
    assert evidence["restore_seconds"] >= 0
    assert (
        evidence["restored"]["alembic_version"] == live_inventory()["alembic_version"]
    )
    assert scratch_databases() == []


def test_a_backup_is_verified_without_a_source_inventory_too(backup: Path) -> None:
    evidence = asyncio.run(restore_tool.verify(admin_url(), backup, None))

    assert evidence["verified"] is True
    assert evidence["compared_with_source"] is False


def test_a_tampered_checksum_fails_verification(backup: Path) -> None:
    sidecar = backup.parent / f"{backup.name}.sha256"
    sidecar.write_text(f"{'0' * 64}  {backup.name}\n")

    evidence = asyncio.run(restore_tool.verify(admin_url(), backup, None))

    assert evidence["verified"] is False
    assert evidence["checksum_matches_sidecar"] is False
    assert scratch_databases() == []


def test_a_truncated_dump_is_a_tool_failure_and_leaves_no_scratch_database(
    backup: Path,
) -> None:
    data = backup.read_bytes()
    backup.write_bytes(data[: len(data) // 3])

    with pytest.raises(restore_tool.RestoreError, match="pg_restore failed"):
        asyncio.run(restore_tool.verify(admin_url(), backup, None))

    assert scratch_databases() == []


def test_a_restore_that_does_not_match_the_source_is_reported(backup: Path) -> None:
    source = live_inventory()
    source["row_counts"] = {**source["row_counts"], "fragrances": 10_000_000}

    evidence = asyncio.run(restore_tool.verify(admin_url(), backup, source))

    assert evidence["verified"] is False
    assert evidence["violations"]


def test_the_command_line_exits_zero_for_a_good_backup(
    backup: Path, tmp_path: Path
) -> None:
    output = tmp_path / "evidence.json"
    result = subprocess.run(  # noqa: S603 - fixed argv, test-controlled environment
        [
            sys.executable,
            str(SCRIPTS / "verify_restore.py"),
            "--backup",
            str(backup),
            "--output",
            str(output),
        ],
        env={**os.environ, "P1_ADMIN_DATABASE_URL": admin_url()},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["verified"] is True
    assert "Verified:" in result.stdout


def test_a_dump_that_cannot_connect_leaves_nothing_behind(tmp_path: Path) -> None:
    result = take_backup(tmp_path, PGPASSWORD="definitely-wrong-password")

    assert result.returncode == 1
    assert "pg_dump failed" in result.stderr
    assert list(tmp_path.iterdir()) == []
