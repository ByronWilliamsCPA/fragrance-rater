"""Prove a backup restores: restore it into a scratch database and inventory it.

A backup that has never been restored is a hope, not a backup. This restores a
dump produced by ``scripts/backup_database.sh`` into a throwaway database on a
server you name, reads the same inventory ``scripts/p1_migration_inventory.py``
takes (row counts, timestamp ranges, duplicate keys, invalid foreign keys, and
redacted hashes of the preserved tables), optionally compares it with an
inventory taken from the live database, and drops the scratch database. It also
measures the two numbers a recovery plan needs: how long the restore took (the
recovery time) and how old the backup is (the recovery point).

Usage:
    export P1_ADMIN_DATABASE_URL='postgresql://<user>:<password>@<host>/postgres'
    uv run python scripts/verify_restore.py \\
        --backup /backups/fragrance_rater-20261031T020000Z.dump \\
        --output /secure/path/restore-evidence.json \\
        [--source-inventory /secure/path/live-inventory.json]

The account in ``P1_ADMIN_DATABASE_URL`` must be able to create and drop
databases. Point it at a server that is NOT the live one, or at least one where
creating a short-lived database is acceptable. The URL is read from the
environment, never the command line, and the password reaches ``pg_restore``
through ``PGPASSWORD``, so credentials stay out of process listings.

Exit codes: 0 verified; 1 the restore did not match the source inventory or the
checksum sidecar disagreed; 2 the tool could not do its job (missing file,
unreachable server, failed restore). Only 0 means "verified".
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_migration_inventory as inventory_tool

ADMIN_URL_ENV = "P1_ADMIN_DATABASE_URL"
_SCRATCH_NAME = re.compile(r"^restore_verify_[0-9]{8}t[0-9]{6}z_[0-9a-f]{6}$")
_STAMP = re.compile(r"-(\d{8}T\d{6}Z)\.dump$")


class RestoreError(RuntimeError):
    """The tool could not complete the check (as opposed to the check failing)."""


def scratch_name(now: datetime | None = None) -> str:
    """Return a unique, safely quotable scratch database name."""
    moment = (now or datetime.now(UTC)).strftime("%Y%m%dt%H%M%Sz")
    return f"restore_verify_{moment}_{secrets.token_hex(3)}"


def connection_environment(url: str, database: str | None = None) -> dict[str, str]:
    """Translate a ``postgresql://`` URL into ``PG*`` variables.

    ``pg_restore`` reads these, so the password never appears on its command
    line.

    Args:
        url: A ``postgresql://`` or ``postgres://`` URL.
        database: Overrides the database named in the URL.

    Returns:
        The environment variables ``libpq`` tools read.

    Raises:
        RestoreError: If the URL is not a PostgreSQL URL.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"postgresql", "postgres"} or not parts.hostname:
        message = f"{ADMIN_URL_ENV} must be a postgresql:// URL with a host"
        raise RestoreError(message)
    env = {"PGHOST": parts.hostname}
    if parts.port:
        env["PGPORT"] = str(parts.port)
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    env["PGDATABASE"] = database or unquote(parts.path.lstrip("/")) or "postgres"
    return env


def database_url(url: str, database: str) -> str:
    """Return ``url`` pointing at a different database."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{database}"))


def sha256_of(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_checksum(backup: Path) -> bool | None:
    """Compare the backup with its ``.sha256`` sidecar.

    Returns:
        True when they agree, False when they differ, None when no sidecar exists.
    """
    sidecar = backup.with_name(backup.name + ".sha256")
    if not sidecar.is_file():
        return None
    recorded = sidecar.read_text(encoding="utf-8").split()[0]
    return recorded == sha256_of(backup)


def backup_created_at(backup: Path) -> datetime:
    """Read when a backup was taken from its name, falling back to its mtime."""
    match = _STAMP.search(backup.name)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    return datetime.fromtimestamp(backup.stat().st_mtime, tz=UTC)


def summarize(inventory: dict[str, Any]) -> dict[str, Any]:
    """Keep the counts and revision from an inventory, never row content."""
    return {
        "alembic_version": inventory.get("alembic_version"),
        "row_counts": inventory.get("row_counts", {}),
    }


def _inspect_backup(backup: Path) -> tuple[bool | None, datetime]:
    """Check the dump exists and read its checksum result and age.

    Raises:
        RestoreError: If the backup is missing or empty.
    """
    if not backup.is_file() or backup.stat().st_size == 0:
        message = f"backup {backup} is missing or empty"
        raise RestoreError(message)
    return check_checksum(backup), backup_created_at(backup)


async def _admin_statement(admin_url: str, statement: str) -> None:
    connection = await asyncpg.connect(admin_url)
    try:
        await connection.execute(statement)
    finally:
        await connection.close()


def _run_restore(admin_url: str, scratch: str, backup: Path) -> None:
    environment = {**os.environ, **connection_environment(admin_url, scratch)}
    try:
        result = subprocess.run(
            [
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                "--dbname",
                scratch,
                str(backup),
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        message = "pg_restore is not installed on this machine"
        raise RestoreError(message) from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()[-1:] or ["no output"]
        message = f"pg_restore failed (exit {result.returncode}): {detail[0]}"
        raise RestoreError(message)


async def verify(
    admin_url: str,
    backup: Path,
    source_inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Restore ``backup`` into a scratch database and report what came back.

    Args:
        admin_url: URL of a server where a scratch database may be created.
        backup: A custom-format dump.
        source_inventory: An inventory of the live database to compare against.

    Returns:
        The evidence document. ``verified`` is true only when the checksum
        agreed (or no sidecar exists) and any comparison found no violation.

    Raises:
        RestoreError: If the restore itself could not be carried out.
    """
    checksum_ok, created = await asyncio.to_thread(_inspect_backup, backup)
    scratch = scratch_name()
    if not _SCRATCH_NAME.fullmatch(scratch):  # pragma: no cover - guards the format
        message = "internal error: unsafe scratch database name"
        raise RestoreError(message)

    started = time.monotonic()
    try:
        await _admin_statement(admin_url, f'CREATE DATABASE "{scratch}"')
        _run_restore(admin_url, scratch, backup)
        restore_seconds = time.monotonic() - started
        restored = await inventory_tool.build_inventory(
            database_url(admin_url, scratch)
        )
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        raise RestoreError(message) from exc
    finally:
        try:
            await _admin_statement(
                admin_url, f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)'
            )
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
            print(f"warning: could not drop {scratch}: {exc}", file=sys.stderr)

    violations = (
        inventory_tool.compare(source_inventory, restored) if source_inventory else []
    )
    now = datetime.now(UTC)
    return {
        "verified": checksum_ok is not False and not violations,
        "backup_file": backup.name,
        "checksum_matches_sidecar": checksum_ok,
        "backup_created_at": created.isoformat(),
        "backup_age_seconds": round((now - created).total_seconds()),
        "restore_seconds": round(restore_seconds, 1),
        "verified_at": now.isoformat(),
        "compared_with_source": source_inventory is not None,
        "violations": violations,
        "restored": summarize(restored),
    }


def _fail(message: str) -> int:
    print(f"verify_restore: {message}", file=sys.stderr)
    return 2


def main() -> int:
    """Run the check from the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-inventory", type=Path)
    args = parser.parse_args()

    admin_url = os.environ.get(ADMIN_URL_ENV, "").strip()
    if not admin_url:
        return _fail(
            f"set {ADMIN_URL_ENV} to a postgresql:// URL (never pass it as an argument)"
        )
    source: dict[str, Any] | None = None
    if args.source_inventory:
        try:
            loaded = json.loads(args.source_inventory.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return _fail(
                f"could not read the source inventory {args.source_inventory}: {exc}"
            )
        if not isinstance(loaded, dict):
            return _fail(
                f"the source inventory {args.source_inventory} is not an inventory object"
            )
        source = loaded

    try:
        evidence = asyncio.run(verify(admin_url, args.backup, source))
    except RestoreError as exc:
        return _fail(str(exc))

    rendered = json.dumps(evidence, indent=2)
    if args.output:
        try:
            args.output.write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            return _fail(f"could not write the evidence to {args.output} ({exc})")
    else:
        print(rendered)

    if not evidence["verified"]:
        if evidence["checksum_matches_sidecar"] is False:
            print(
                "RESTORE CHECK FAILED: the backup does not match its checksum",
                file=sys.stderr,
            )
        for violation in evidence["violations"]:
            print(f"RESTORE CHECK FAILED: {violation}", file=sys.stderr)
        return 1
    print(
        f"Verified: {evidence['backup_file']} restored in {evidence['restore_seconds']}s "
        f"(backup age {evidence['backup_age_seconds']}s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
