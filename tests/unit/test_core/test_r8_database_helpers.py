"""R8 PR 2 database helpers: jsonb variant (D-12), UTC clock (D-16, Q16)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import JSON, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine

from fragrance_rater.core.database import (
    Base,
    assert_database_timezone_is_utc,
    portable_json,
    utc_now,
)
from fragrance_rater.core.exceptions import ConfigurationError

UTC_DEFAULT_COLUMNS = {
    ("accord_types", "created_at"),
    ("evaluations", "created_at"),
    ("evaluations", "evaluated_at"),
    ("fragrance_gtins", "created_at"),
    ("fragrances", "created_at"),
    ("fragrances", "updated_at"),
    ("note_aliases", "created_at"),
    ("reviewers", "created_at"),
}


def test_utc_now_renders_utc_on_postgresql_and_current_timestamp_on_sqlite() -> None:
    statement = select(utc_now())
    assert "timezone('utc', now())" in str(
        statement.compile(dialect=postgresql.dialect())
    )
    assert "CURRENT_TIMESTAMP" in str(statement.compile(dialect=sqlite.dialect()))


def test_every_server_clock_default_is_utc() -> None:
    """D-16: no model keeps a session-TimeZone ``now()`` default."""
    found = {
        (table.name, column.name)
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if column.server_default is not None
        and isinstance(getattr(column.server_default, "arg", None), utc_now)
    }
    assert found == UTC_DEFAULT_COLUMNS
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            arg = getattr(column.server_default, "arg", None)
            assert "now()" not in str(arg).lower() or isinstance(arg, utc_now), (
                table.name,
                column.name,
            )


def test_portable_json_is_jsonb_only_on_postgresql() -> None:
    plain = portable_json()
    nullable = portable_json(none_as_null=True)
    assert isinstance(plain.dialect_impl(postgresql.dialect()), JSONB)
    assert isinstance(plain.dialect_impl(sqlite.dialect()), JSON)
    assert not isinstance(plain.dialect_impl(sqlite.dialect()), JSONB)
    assert nullable.none_as_null
    pg_nullable = nullable.dialect_impl(postgresql.dialect())
    assert isinstance(pg_nullable, JSONB)
    assert pg_nullable.none_as_null


def test_every_json_column_is_portable_json() -> None:
    """D-12: every JSON column becomes jsonb on PostgreSQL (19 columns)."""
    json_columns = [
        (table.name, column.name)
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, JSON)
    ]
    assert len(json_columns) == 19
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, JSON):
                impl = column.type.dialect_impl(postgresql.dialect())
                assert isinstance(impl, JSONB), (table.name, column.name)


@pytest.mark.asyncio
async def test_the_timezone_check_skips_sqlite() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        assert await assert_database_timezone_is_utc(engine) is None
    finally:
        await engine.dispose()


class _Connection:
    def __init__(self, zone: str) -> None:
        self.zone = zone

    async def __aenter__(self) -> _Connection:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def scalar(self, _statement: object) -> str:
        return self.zone


class _Dialect:
    name = "postgresql"


class _Engine:
    dialect = _Dialect()

    def __init__(self, zone: str) -> None:
        self.zone = zone

    def connect(self) -> _Connection:
        return _Connection(self.zone)


@pytest.mark.asyncio
@pytest.mark.parametrize("zone", ["UTC", "Etc/UTC", "utc", "Etc/UCT"])
async def test_a_utc_postgresql_session_passes(zone: str) -> None:
    engine: Any = _Engine(zone)
    assert await assert_database_timezone_is_utc(engine) == zone


@pytest.mark.asyncio
@pytest.mark.parametrize("zone", ["America/Chicago", "Europe/London", "GMT", "+00"])
async def test_a_non_utc_postgresql_session_fails_loudly(zone: str) -> None:
    engine: Any = _Engine(zone)
    with pytest.raises(ConfigurationError, match="must be UTC") as failure:
        await assert_database_timezone_is_utc(engine)
    assert failure.value.details == {"timezone": zone}
