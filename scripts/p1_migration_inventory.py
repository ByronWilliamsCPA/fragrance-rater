#!/usr/bin/env python3
"""Capture or compare the P1 pre/post-migration inventory.

Implements the "Restore and pre-upgrade inventory" and "Migration and data
assertions" steps of docs/deployment/p1-release-readiness.md as one
repeatable command instead of hand-run SQL: row counts, primary-key counts,
timestamp ranges, duplicate natural keys, and a redacted hash of sorted IDs
and timestamps for fragrances, reviewers, and evaluations (the three tables
the runbook names as must-preserve).

Usage:
    # Before the migration, against the isolated restored clone:
    uv run python scripts/p1_migration_inventory.py "$CLONE_URL" \\
        --output /secure/path/before.json

    # After `alembic upgrade head`, against the same clone:
    uv run python scripts/p1_migration_inventory.py "$CLONE_URL" \\
        --output /secure/path/after.json --compare /secure/path/before.json

The connection string uses the plain ``postgresql://`` scheme (asyncpg's
DSN form), not the application's ``postgresql+asyncpg://`` SQLAlchemy URL.
Output contains only counts, ranges, and hashes -- no raw identity, blind
mapping, or personal content -- and is safe to retain as gate evidence, but
this script never writes to the private evidence directory itself.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

PRESERVED_TABLES = ("fragrances", "reviewers", "evaluations")


def _default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def _table_names(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
    )
    return [row["tablename"] for row in rows]


async def _row_count(conn: asyncpg.Connection, table: str) -> int:
    result = await conn.fetchval(f'SELECT count(*) FROM "{table}"')  # noqa: S608  # nosec B608 - table/column identifiers come from pg_tables/information_schema.columns, never external input
    assert result is not None, f"COUNT(*) on {table} returned no row"
    return int(result)


async def _timestamp_range(
    conn: asyncpg.Connection, table: str, column: str = "created_at"
) -> dict[str, str | None]:
    exists = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = $1 AND column_name = $2",
        table,
        column,
    )
    if not exists:
        return {"min": None, "max": None}
    row = await conn.fetchrow(
        f'SELECT min("{column}") AS lo, max("{column}") AS hi FROM "{table}"'  # noqa: S608  # nosec B608 - table/column identifiers come from pg_tables/information_schema.columns, never external input
    )
    assert row is not None, f"min/max query on {table} returned no row"
    return {
        "min": _default(row["lo"]) if row["lo"] else None,
        "max": _default(row["hi"]) if row["hi"] else None,
    }


async def _redacted_hash(conn: asyncpg.Connection, table: str) -> str | None:
    """Hash sorted (id, created_at) pairs; None if the table lacks either column."""
    columns = {
        row["column_name"]
        for row in await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = $1",
            table,
        )
    }
    if not {"id", "created_at"}.issubset(columns):
        return None
    rows = await conn.fetch(
        f'SELECT id, created_at FROM "{table}" ORDER BY id'  # noqa: S608  # nosec B608 - table/column identifiers come from pg_tables/information_schema.columns, never external input
    )
    digest = hashlib.sha256()
    for row in rows:
        digest.update(f"{row['id']}|{_default(row['created_at'])}\n".encode())
    return digest.hexdigest()


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


async def _invalid_foreign_keys(conn: asyncpg.Connection) -> dict[str, int]:
    """Evaluations or memberships pointing at a fragrance/reviewer row that no longer exists."""
    result = await conn.fetchval(
        "SELECT count(*) FROM evaluations e "
        "WHERE NOT EXISTS (SELECT 1 FROM fragrances f WHERE f.id = e.fragrance_id) "
        "OR NOT EXISTS (SELECT 1 FROM reviewers r WHERE r.id = e.reviewer_id)"
    )
    assert result is not None, "orphaned-evaluations count query returned no row"
    return {"orphaned_evaluations": int(result)}


async def build_inventory(database_url: str) -> dict[str, Any]:
    """Connect and assemble the full inventory record."""
    conn = await asyncpg.connect(database_url)
    try:
        alembic_version = await conn.fetchval(
            "SELECT version_num FROM alembic_version LIMIT 1"
        )
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
            "invalid_foreign_keys": await _invalid_foreign_keys(conn)
            if {"evaluations", "fragrances", "reviewers"}.issubset(tables)
            else {},
        }
        return inventory
    finally:
        await conn.close()


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return preservation violations; empty means the migration preserved history."""
    violations: list[str] = []
    for table in PRESERVED_TABLES:
        before_count = before.get("row_counts", {}).get(table)
        after_count = after.get("row_counts", {}).get(table)
        if before_count is not None and before_count != after_count:
            violations.append(
                f"{table}: row count changed ({before_count} -> {after_count})"
            )
        before_hash = before.get("redacted_hashes", {}).get(table)
        after_hash = after.get("redacted_hashes", {}).get(table)
        if before_hash is not None and before_hash != after_hash:
            violations.append(
                f"{table}: id/created_at hash changed -- rows were not preserved"
            )
    return violations


def main() -> int:
    """Parse arguments, build the inventory, optionally compare, and report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "database_url", help="asyncpg DSN, e.g. postgresql://user:pass@host/db"
    )
    parser.add_argument(
        "--output", help="write the JSON inventory to this path instead of stdout"
    )
    parser.add_argument(
        "--compare",
        help="a prior inventory JSON to diff against; nonzero exit on any preservation violation",
    )
    args = parser.parse_args()

    inventory = asyncio.run(build_inventory(args.database_url))
    if args.output:
        Path(args.output).write_text(json.dumps(inventory, indent=2, default=_default))
    else:
        print(json.dumps(inventory, indent=2, default=_default))

    if args.compare:
        before = json.loads(Path(args.compare).read_text())
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
