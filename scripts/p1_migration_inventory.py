"""Capture or compare the P1 pre/post-migration inventory.

Implements the "Restore and pre-upgrade inventory" and "Migration and data
assertions" steps of docs/deployment/p1-release-readiness.md as one
repeatable command instead of hand-run SQL: row counts, timestamp ranges,
duplicate natural keys, invalid foreign keys, and a redacted hash of sorted
IDs and timestamps for fragrances, reviewers, and evaluations (the three
tables the runbook names as must-preserve). The hash is computed per column
and covers every column of those tables, not only ``id`` and ``created_at``,
so a changed rating, a changed reviewer/fragrance link, or a rewritten
timestamp changes it instead of passing as "preserved".

Usage:
    # Before the migration, against the isolated restored clone:
    export P1_DATABASE_URL='postgresql://<user>:<password>@<clone-host>/<db>'
    uv run python scripts/p1_migration_inventory.py \\
        --output /secure/path/before.json

    # After `alembic upgrade head`, against the same clone:
    uv run python scripts/p1_migration_inventory.py \\
        --output /secure/path/after.json --compare /secure/path/before.json

The connection string is read from the ``P1_DATABASE_URL`` environment
variable, never from the command line, so production credentials stay out of
`ps`, process listings, and shell history. It must use the plain
``postgresql://`` scheme (asyncpg's DSN form), not the application's
``postgresql+asyncpg://`` SQLAlchemy URL.

Exit codes: 0 when the inventory was captured (and, with --compare, showed no
preservation violation), 1 on a preservation violation, 2 when the tool could
not do its job (unreachable database, unwritable --output, unreadable
--compare). Only 0 means "verified".

Output handling: the JSON is mostly counts, ranges, and SHA-256 digests, but
it is not free of raw content. ``duplicate_natural_keys`` carries the literal
name, brand, concentration, and version_key of any duplicated live fragrance,
and ``alembic_version`` carries the raw revision string. No reviewer identity,
blind mapping, evaluation text, or other personal content is included: every
per-row value is hashed, never emitted. Retain it under the same handling
rules as the rest of the release evidence.

The script writes wherever ``--output`` points, which may well be a private
evidence path, and reads whatever ``--compare`` points at. It has no
hardcoded knowledge of either location; choosing and protecting those paths
is the operator's job.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

PRESERVED_TABLES = ("fragrances", "reviewers", "evaluations")

DATABASE_URL_ENV = "P1_DATABASE_URL"

MEMBERSHIP_TABLE = "calibration_memberships"
PROGRAM_TABLE = "calibration_programs"

# Distinguishes a SQL NULL from the empty string when hashing a column value,
# so clearing a text field cannot leave the column hash unchanged.
_NULL_MARKER = "\x00NULL"

_ORPHANED_EVALUATIONS_SQL = (
    "SELECT count(*) FROM evaluations e "
    "WHERE NOT EXISTS ("
    "SELECT 1 FROM fragrances f WHERE f.id = e.fragrance_id) "
    "OR NOT EXISTS (SELECT 1 FROM reviewers r WHERE r.id = e.reviewer_id)"
)

_ORPHANED_MEMBERSHIPS_SQL = (
    "SELECT count(*) FROM calibration_memberships m "
    "WHERE NOT EXISTS ("
    "SELECT 1 FROM fragrances f WHERE f.id = m.fragrance_id) "
    "OR NOT EXISTS ("
    "SELECT 1 FROM calibration_programs p WHERE p.id = m.program_id)"
)


def _default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _cell(value: object) -> str:
    """Render one column value for hashing, keeping NULL distinct from ''."""
    if value is None:
        return _NULL_MARKER
    return _default(value)


async def _table_names(conn: asyncpg.Connection) -> list[str]:
    """List every table in the public schema, alphabetically."""
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
    )
    return [row["tablename"] for row in rows]


async def _count(conn: asyncpg.Connection, query: str, label: str) -> int:
    """Run a count query and fail loudly rather than return a silent None."""
    result = await conn.fetchval(query)
    if result is None:
        msg = f"{label} count query returned no row"
        raise RuntimeError(msg)
    return int(result)


async def _row_count(conn: asyncpg.Connection, table: str) -> int:
    """Count every row of one table, soft-deleted rows included."""
    # The only interpolated value is a table name that came from pg_tables
    # or the hardcoded PRESERVED_TABLES tuple, quoted as an identifier. No
    # external or user input can reach this string.
    query = f'SELECT count(*) FROM "{table}"'  # noqa: S608  # nosec B608
    return await _count(conn, query, f"COUNT(*) on {table}")


async def _timestamp_range(
    conn: asyncpg.Connection, table: str, column: str = "created_at"
) -> dict[str, str | None]:
    """Report the oldest and newest value of one timestamp column."""
    exists = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = $1 AND column_name = $2",
        table,
        column,
    )
    if not exists:
        return {"min": None, "max": None}
    # Table and column names are hardcoded constants (PRESERVED_TABLES and
    # this function's literal "created_at" default), never external input.
    bounds = f'min("{column}") AS lo, max("{column}") AS hi'
    query = f'SELECT {bounds} FROM "{table}"'  # noqa: S608  # nosec B608
    row = await conn.fetchrow(query)
    if row is None:
        msg = f"min/max query on {table} returned no row"
        raise RuntimeError(msg)
    return {
        "min": _default(row["lo"]) if row["lo"] else None,
        "max": _default(row["hi"]) if row["hi"] else None,
    }


async def _redacted_hash(conn: asyncpg.Connection, table: str) -> dict[str, str] | None:
    """Hash every column over id-sorted rows; None if the table has no id.

    One SHA-256 digest per column, each built from ``id|value`` pairs read in
    ``id`` order, so a changed rating, a relinked reviewer or fragrance, or a
    rewritten timestamp changes that column's digest while leaving the rest
    alone, and compare() can name the field that moved. Values are hashed and
    discarded, never stored, so the output still carries no raw identity or
    personal content.
    """
    columns = sorted(
        row["column_name"]
        for row in await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = $1",
            table,
        )
    )
    if "id" not in columns:
        return None
    cols = ", ".join(f'"{column}"' for column in columns)
    # Both interpolations are identifiers read back from
    # information_schema.columns for a table named in PRESERVED_TABLES, and
    # each is double-quoted. No external or user input can reach this string.
    query = f'SELECT {cols} FROM "{table}" ORDER BY "id"'  # noqa: S608  # nosec B608
    digests = {column: hashlib.sha256() for column in columns}
    # #ASSUME: concurrency: the restored clone is quiescent, so streaming the
    # rows in a single read transaction sees one consistent snapshot. The
    # runbook restores into a database with no route from application
    # clients, which is what makes that true.
    # #VERIFY: if this is ever pointed at a live database, the hash is a
    # point-in-time digest of that transaction's snapshot, not a lock; run it
    # only against the isolated clone the runbook describes.
    async with conn.transaction():
        async for row in conn.cursor(query):
            row_id = row["id"]
            for column in columns:
                digests[column].update(f"{row_id}|{_cell(row[column])}\n".encode())
    return {column: digest.hexdigest() for column, digest in digests.items()}


async def _duplicate_natural_keys(conn: asyncpg.Connection) -> dict[str, int]:
    """Duplicate (name, brand, concentration, version_key) rows among live fragrances."""
    rows = await conn.fetch(
        "SELECT name, brand, concentration, version_key, count(*) AS n "
        "FROM fragrances WHERE deleted_at IS NULL "
        "GROUP BY name, brand, concentration, version_key HAVING count(*) > 1"
    )
    return {
        f"{row['name']} / {row['brand']} / {row['concentration']} / {row['version_key']}": row[
            "n"
        ]
        for row in rows
    }


async def _invalid_foreign_keys(
    conn: asyncpg.Connection, tables: set[str]
) -> dict[str, int]:
    """Count evaluations and calibration memberships whose parent rows are gone.

    Covers evaluations pointing at a fragrance or reviewer that no longer
    exists, and calibration memberships pointing at a fragrance or program
    that no longer exists. Each check is skipped, and its key omitted, when
    one of the tables it needs is absent from this database.
    """
    counts: dict[str, int] = {}
    if {"evaluations", "fragrances", "reviewers"}.issubset(tables):
        counts["orphaned_evaluations"] = await _count(
            conn, _ORPHANED_EVALUATIONS_SQL, "orphaned-evaluations"
        )
    if {MEMBERSHIP_TABLE, PROGRAM_TABLE, "fragrances"}.issubset(tables):
        counts["orphaned_calibration_memberships"] = await _count(
            conn, _ORPHANED_MEMBERSHIPS_SQL, "orphaned-calibration-memberships"
        )
    return counts


async def _alembic_version(conn: asyncpg.Connection) -> str:
    """Return the single applied Alembic revision, or raise a clear error."""
    # #CRITICAL: data-integrity: assumes alembic_version exists and holds
    # exactly one revision. A clone restored from a backup that was never
    # stamped has no such table at all, and a branched chain leaves several
    # rows; in either case a before/after comparison would be comparing
    # against an unknown schema state.
    # #VERIFY: the UndefinedTableError branch and the two row-count checks
    # below turn both cases into an actionable operator error instead of an
    # unhandled traceback or a silently unanchored inventory.
    try:
        rows = await conn.fetch("SELECT version_num FROM alembic_version")
    except asyncpg.UndefinedTableError as exc:
        msg = (
            "no alembic_version table in this database, so its migration "
            "state is unknown. Either the restored clone never had Alembic "
            f"applied, or {DATABASE_URL_ENV} points at the wrong database. "
            "Confirm the restore target, then run `uv run alembic current` "
            "against it before capturing the pre-upgrade inventory."
        )
        raise RuntimeError(msg) from exc
    if not rows:
        msg = (
            "alembic_version exists but is empty, so the clone's migration "
            "state is unknown. Stamp or upgrade it before capturing the "
            "pre-upgrade inventory."
        )
        raise RuntimeError(msg)
    if len(rows) > 1:
        heads = ", ".join(sorted(str(row["version_num"]) for row in rows))
        msg = (
            f"alembic_version holds {len(rows)} revisions ({heads}), so the "
            "migration chain has multiple heads and the upgrade path is "
            "ambiguous. Resolve the heads before running the migration gate."
        )
        raise RuntimeError(msg)
    return str(rows[0]["version_num"])


async def build_inventory(database_url: str) -> dict[str, Any]:
    """Connect and assemble the full inventory record."""
    # #CRITICAL: external-resources: assumes the PostgreSQL clone named by
    # P1_DATABASE_URL is reachable and accepts these credentials. During a
    # migration window a failure here must never be mistaken for a clean
    # inventory or an empty set of findings.
    # #VERIFY: main() wraps asyncio.run(build_inventory(...)) and turns any
    # connection, DSN, or query failure into an operator-facing error with
    # exit code 2, so no output file is written from a failed read.
    conn = await asyncpg.connect(database_url)
    try:
        alembic_version = await _alembic_version(conn)
        tables = await _table_names(conn)
        inventory: dict[str, Any] = {
            "alembic_version": alembic_version,
            "row_counts": {t: await _row_count(conn, t) for t in tables},
            "timestamp_ranges": {
                t: await _timestamp_range(conn, t)
                for t in PRESERVED_TABLES
                if t in tables
            },
            "redacted_hashes": {
                t: await _redacted_hash(conn, t)
                for t in PRESERVED_TABLES
                if t in tables
            },
            "duplicate_natural_keys": await _duplicate_natural_keys(conn)
            if "fragrances" in tables
            else {},
            "invalid_foreign_keys": await _invalid_foreign_keys(conn, set(tables)),
        }
        return inventory
    finally:
        await conn.close()


def _section(snapshot: dict[str, Any], name: str) -> dict[str, Any]:
    """Return one inventory section, or {} when missing or malformed."""
    value = snapshot.get(name)
    return value if isinstance(value, dict) else {}


def _unverifiable(table: str, detail: str) -> str:
    """Phrase the "before-snapshot cannot answer this" violation."""
    return (
        f"before-snapshot missing or unreadable for table {table} "
        f"({detail}), cannot verify preservation"
    )


def _compare_row_counts(
    before: dict[str, Any], after: dict[str, Any], table: str
) -> list[str]:
    """Diff one table's row count across the two snapshots."""
    before_count = _section(before, "row_counts").get(table)
    after_count = _section(after, "row_counts").get(table)
    if before_count is None:
        return [_unverifiable(table, "no row count")]
    if after_count is None:
        return [f"{table}: no row count in the after-snapshot; the table is gone"]
    if before_count != after_count:
        return [f"{table}: row count changed ({before_count} -> {after_count})"]
    return []


def _compare_timestamp_ranges(
    before: dict[str, Any], after: dict[str, Any], table: str
) -> list[str]:
    """Diff one table's created_at bounds across the two snapshots."""
    before_range = _section(before, "timestamp_ranges").get(table)
    after_range = _section(after, "timestamp_ranges").get(table)
    if not isinstance(before_range, dict):
        return [_unverifiable(table, "no created_at range")]
    if not isinstance(after_range, dict):
        return [f"{table}: no created_at range in the after-snapshot"]
    return [
        f"{table}: created_at {bound} changed "
        f"({before_range.get(bound)} -> {after_range.get(bound)})"
        for bound in ("min", "max")
        if before_range.get(bound) != after_range.get(bound)
    ]


def _compare_hashes(
    before: dict[str, Any], after: dict[str, Any], table: str
) -> list[str]:
    """Diff one table's per-column content hashes across the two snapshots."""
    before_hashes = _section(before, "redacted_hashes").get(table)
    after_hashes = _section(after, "redacted_hashes").get(table)
    if not isinstance(before_hashes, dict) or not before_hashes:
        return [_unverifiable(table, "no per-column content hashes")]
    if not isinstance(after_hashes, dict):
        return [f"{table}: no per-column content hashes in the after-snapshot"]
    violations: list[str] = []
    for column, digest in sorted(before_hashes.items()):
        if column not in after_hashes:
            violations.append(
                f"{table}.{column}: column existed before the migration and "
                "is missing after it"
            )
        elif after_hashes[column] != digest:
            violations.append(
                f"{table}.{column}: content hash changed -- values in this "
                "column were not preserved"
            )
    return violations


def _compare_duplicate_natural_keys(
    before: dict[str, Any], after: dict[str, Any]
) -> list[str]:
    """Diff the duplicate live-fragrance natural keys across the snapshots."""
    raw_before = before.get("duplicate_natural_keys")
    if not isinstance(raw_before, dict):
        return [
            (
                "before-snapshot has no readable duplicate_natural_keys "
                "section, cannot verify preservation"
            )
        ]
    raw_after = _section(after, "duplicate_natural_keys")
    violations: list[str] = []
    for key in sorted(set(raw_before) | set(raw_after)):
        count_before = raw_before.get(key, 0)
        count_after = raw_after.get(key, 0)
        if count_before != count_after:
            violations.append(
                f"duplicate natural key '{key}': live row count changed "
                f"({count_before} -> {count_after})"
            )
    return violations


def _compare_invalid_foreign_keys(
    before: dict[str, Any], after: dict[str, Any]
) -> list[str]:
    """Diff the orphaned-row checks across the two snapshots."""
    raw_before = before.get("invalid_foreign_keys")
    if not isinstance(raw_before, dict):
        return [
            (
                "before-snapshot has no readable invalid_foreign_keys "
                "section, cannot verify preservation"
            )
        ]
    raw_after = _section(after, "invalid_foreign_keys")
    violations: list[str] = []
    for check in sorted(set(raw_before) | set(raw_after)):
        if check not in raw_after:
            violations.append(
                f"{check}: ran before the migration but not after it, "
                "cannot verify preservation"
            )
        elif check not in raw_before:
            if raw_after[check]:
                violations.append(
                    f"{check}: {raw_after[check]} orphaned rows after the "
                    "migration (this check could not run before it)"
                )
        elif raw_before[check] != raw_after[check]:
            violations.append(
                f"{check}: orphaned row count changed "
                f"({raw_before[check]} -> {raw_after[check]})"
            )
    return violations


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return preservation violations; empty means the migration preserved history.

    Every section the inventory captures is diffed: row counts, created_at
    ranges, per-column content hashes, duplicate natural keys, and the
    orphaned-row checks. A before-snapshot that cannot answer one of those
    questions (truncated, empty, or missing the table) is itself a violation:
    "nothing to compare" must never read as "nothing changed".
    """
    violations: list[str] = []
    for table in PRESERVED_TABLES:
        violations.extend(_compare_row_counts(before, after, table))
        violations.extend(_compare_timestamp_ranges(before, after, table))
        violations.extend(_compare_hashes(before, after, table))
    violations.extend(_compare_duplicate_natural_keys(before, after))
    violations.extend(_compare_invalid_foreign_keys(before, after))
    return violations


def _fail(message: str) -> int:
    """Print an operator-facing error and return the tool-failure exit code."""
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def _database_url() -> str:
    """Read the asyncpg DSN from the environment, or raise a clear error."""
    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url:
        msg = (
            f"{DATABASE_URL_ENV} is not set. Export the asyncpg DSN for the "
            "restored clone before running this script, e.g. "
            f"export {DATABASE_URL_ENV}='postgresql://<user>:<password>@<host>/<db>'. It "
            "is read from the environment rather than the command line so "
            "production credentials stay out of `ps` and shell history."
        )
        raise RuntimeError(msg)
    if url.startswith("postgresql+"):
        scheme = url.split("://", 1)[0]
        msg = (
            f"{DATABASE_URL_ENV} uses the SQLAlchemy driver scheme "
            f"({scheme}://). This script connects with asyncpg directly and "
            "needs the plain postgresql:// DSN form."
        )
        raise RuntimeError(msg)
    return url


def main() -> int:
    """Parse arguments, build the inventory, optionally compare, and report."""
    parser = argparse.ArgumentParser(
        description=(
            "Capture or compare the P1 pre/post-migration inventory. The "
            f"database DSN is read from ${DATABASE_URL_ENV}."
        )
    )
    parser.add_argument(
        "--output", help="write the JSON inventory to this path instead of stdout"
    )
    parser.add_argument(
        "--compare",
        help="a prior inventory JSON to diff against; nonzero exit on any preservation violation",
    )
    args = parser.parse_args()

    try:
        database_url = _database_url()
    except RuntimeError as exc:
        return _fail(str(exc))

    try:
        inventory = asyncio.run(build_inventory(database_url))
    except RuntimeError as exc:
        return _fail(str(exc))
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, ValueError) as exc:
        return _fail(
            f"could not read the inventory from the database "
            f"({type(exc).__name__}: {exc}). Check that {DATABASE_URL_ENV} "
            "points at the restored clone, that the clone is reachable, and "
            "that the credentials are valid. Nothing was written."
        )

    rendered = json.dumps(inventory, indent=2, default=_default)
    if args.output:
        # #CRITICAL: external-resources: assumes --output names a path this
        # process may create or overwrite. It is typically inside a private
        # evidence directory this script knows nothing about, so a missing
        # directory or a permission denial is an ordinary outcome, not a bug.
        # #VERIFY: the OSError branch below reports the path and the reason
        # and exits 2, so a silently unwritten inventory cannot be mistaken
        # for retained gate evidence.
        try:
            Path(args.output).write_text(rendered)
        except OSError as exc:
            return _fail(
                f"could not write the inventory to {args.output} ({exc}). "
                "Check that the directory exists and is writable, then "
                "re-run; no inventory file was produced."
            )
    else:
        print(rendered)

    if args.compare:
        # #CRITICAL: external-resources: assumes --compare names a readable,
        # complete inventory JSON written by an earlier run. A truncated or
        # half-written before.json must not be read as "no differences".
        # #VERIFY: the OSError and JSONDecodeError branches below reject an
        # unreadable file outright, and compare() records a structurally
        # incomplete snapshot as a violation rather than an empty result.
        try:
            before = json.loads(Path(args.compare).read_text())
        except OSError as exc:
            return _fail(
                f"could not read the before-snapshot {args.compare} ({exc}). "
                "The post-migration comparison did not run."
            )
        except json.JSONDecodeError as exc:
            return _fail(
                f"the before-snapshot {args.compare} is not valid JSON "
                f"({exc}). It may be truncated or half-written; the "
                "post-migration comparison did not run."
            )
        if not isinstance(before, dict):
            return _fail(
                f"the before-snapshot {args.compare} is not an inventory "
                "object; the post-migration comparison did not run."
            )
        violations = compare(before, inventory)
        if violations:
            for violation in violations:
                print(f"PRESERVATION VIOLATION: {violation}", file=sys.stderr)
            return 1
        print(
            f"Preserved: {', '.join(PRESERVED_TABLES)} unchanged across the migration."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
