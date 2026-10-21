"""Assert the migrated PostgreSQL schema equals the ORM metadata (R2, D-05).

Every other migration test builds its pre-migration state from
``Base.metadata.create_all()`` and hand-reverts it, so none of them can see
drift between the models and what the migration chain actually produces.
These tests run against a database that CI has upgraded with
``alembic upgrade head`` (``postgres-integration`` job) and compare the two
directly:

* ``compare_metadata`` with type and server-default comparison catches
  structural drift (columns, types, defaults, indexes, unique constraints,
  foreign keys). It is what ``alembic check`` and autogenerate use.
* ``compare_metadata`` ignores CHECK constraints and primary-key and
  foreign-key names entirely, so a second test compares every constraint and
  index name against the names the naming convention gives the models.
  Without it, a migration could drop or misname a CHECK and nothing would
  notice.

Skipped unless ``P1_DATABASE_URL`` points at a migrated PostgreSQL database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import (
    CheckConstraint,
    Connection,
    Constraint,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine

from fragrance_rater.models import Base

DATABASE_URL = os.getenv("P1_DATABASE_URL")
PROJECT_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="P1_DATABASE_URL is not configured"),
]

_KIND: dict[type[Constraint], str] = {
    CheckConstraint: "check",
    ForeignKeyConstraint: "foreign key",
    PrimaryKeyConstraint: "primary key",
    UniqueConstraint: "unique",
}

_DB_NAMES_SQL = text(
    """
    SELECT conrelid::regclass::text, contype::text, conname
    FROM pg_constraint
    WHERE connamespace = 'public'::regnamespace
      AND conrelid::regclass::text <> 'alembic_version'
    UNION ALL
    SELECT tablename, 'i', indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname NOT IN (SELECT conname FROM pg_constraint)
    """
)
_PG_KIND = {"c": "check", "f": "foreign key", "p": "primary key", "u": "unique"}


def _metadata_names() -> set[tuple[str, str, str]]:
    """Return (table, kind, name) for every ORM constraint and index.

    Names are rendered through the PostgreSQL dialect so they are exactly
    what ``CREATE TABLE`` would emit there.
    """
    preparer = postgresql.dialect().identifier_preparer
    names: set[tuple[str, str, str]] = set()
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            names.add(
                (
                    table.name,
                    _KIND[type(constraint)],
                    str(preparer.format_constraint(constraint)),
                )
            )
        for index in table.indexes:
            names.add((table.name, "index", str(preparer.format_constraint(index))))
    return names


async def _run_on_db(fn: Any) -> Any:
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(fn)
    finally:
        await engine.dispose()


def _structural_diff(connection: Connection) -> list[Any]:
    context = MigrationContext.configure(
        connection,
        opts={"compare_type": True, "compare_server_default": True},
    )
    return compare_metadata(context, Base.metadata)


def _db_names(connection: Connection) -> set[tuple[str, str, str]]:
    rows = connection.execute(_DB_NAMES_SQL).all()
    return {(table, _PG_KIND.get(kind, "index"), name) for table, kind, name in rows}


@pytest.mark.asyncio
async def test_migrated_schema_matches_orm_structure() -> None:
    """``alembic upgrade head`` produces exactly what the models declare."""
    diff = await _run_on_db(_structural_diff)
    assert diff == [], (
        "Migrated PostgreSQL schema differs from Base.metadata. Write a "
        "migration (or fix the model) so these operations disappear:\n"
        + "\n".join(repr(op) for op in diff)
    )


@pytest.mark.asyncio
async def test_migrated_constraint_and_index_names_match_orm() -> None:
    """Every DB constraint and index carries the name the models give it."""
    actual = await _run_on_db(_db_names)
    expected = _metadata_names()
    assert actual == expected, (
        f"Only in the migrated database: {sorted(actual - expected)}\n"
        f"Only in Base.metadata: {sorted(expected - actual)}"
    )


def _alembic(*args: str) -> None:
    assert DATABASE_URL is not None
    subprocess.run(  # noqa: S603 - fixed argv, no shell, test-only
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env={**os.environ, "DATABASE_URL": DATABASE_URL},
        check=True,
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_head_migration_round_trips() -> None:
    """The head revision downgrades and re-upgrades back to parity.

    #ASSUME: concurrency: nothing else uses this database while the test
    runs; the postgres-integration job runs pytest serially.
    #VERIFY: re-upgrades to head before asserting, so the database is left
    at head for any later test even if an assertion fails.
    """
    _alembic("downgrade", "-1")
    _alembic("upgrade", "head")
    assert await _run_on_db(_structural_diff) == []
    assert await _run_on_db(_db_names) == _metadata_names()
