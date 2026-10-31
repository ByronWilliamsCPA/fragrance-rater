"""Database connection and session management.

This module provides async database connectivity using SQLAlchemy 2.0.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast

from sqlalchemy import JSON, DateTime, MetaData, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.functions import FunctionElement

from fragrance_rater.core.config import settings
from fragrance_rater.core.exceptions import ConfigurationError
from fragrance_rater.utils.logging import get_logger

logger = get_logger(__name__)


def portable_json(*, none_as_null: bool = False) -> JSON:
    """Return the project's JSON column type: ``jsonb`` on PostgreSQL.

    Architecture review D-12: every JSON column was plain ``json``, which
    PostgreSQL cannot index or compare. ``with_variant`` keeps the generic
    ``JSON`` type for SQLite (the unit suite) while PostgreSQL gets ``jsonb``.

    Args:
        none_as_null (bool): Store a Python ``None`` as SQL NULL rather than
            the JSON text ``null`` (needed wherever a CHECK special-cases
            SQL NULL only).

    Returns:
        JSON: ``JSON`` with a PostgreSQL ``JSONB`` variant.
    """
    return JSON(none_as_null=none_as_null).with_variant(
        JSONB(none_as_null=none_as_null), "postgresql"
    )


class utc_now(FunctionElement[datetime]):  # noqa: N801 - reads like func.now()
    """The current UTC time as a timezone-naive timestamp, on any engine.

    Architecture review D-16 and Q16: every timestamp column is ``timestamp
    without time zone`` holding naive UTC (``utils/timestamps.py``), but
    ``now()`` returns a ``timestamptz`` that PostgreSQL converts to the
    *session* ``TimeZone`` on assignment, so a non-UTC server would silently
    write local time beside the application's UTC. ``timezone('utc', now())``
    is UTC whatever the session says. SQLite's ``CURRENT_TIMESTAMP`` is UTC
    already, and is what ``func.now()`` rendered there before.
    """

    type = DateTime()
    inherit_cache = True


@compiles(utc_now, "postgresql")
def _utc_now_postgresql(
    _element: utc_now, _compiler: SQLCompiler, **_kw: object
) -> str:
    return "timezone('utc', now())"


@compiles(utc_now)
def _utc_now_default(_element: utc_now, _compiler: SQLCompiler, **_kw: object) -> str:
    return "CURRENT_TIMESTAMP"


UTC_TIMEZONE_NAMES = frozenset({"utc", "etc/utc", "etc/uct", "uct", "etc/universal"})
"""``TimeZone`` values PostgreSQL treats as plain UTC (compared lower-case)."""


async def assert_database_timezone_is_utc(db_engine: AsyncEngine) -> str | None:
    """Fail loudly unless a PostgreSQL session's ``TimeZone`` is UTC.

    The models write naive UTC from Python and use ``utc_now`` for server
    defaults, so a non-UTC ``TimeZone`` no longer corrupts new rows, but any
    raw ``now()`` (a manual backfill, an operator's ``psql`` session) still
    would, and ``timestamp`` reads would disagree with ``timestamptz`` ones.
    The deployment therefore must run UTC (Q16), and this makes that a
    startup failure instead of a silent drift. SQLite has no ``TimeZone``.

    Args:
        db_engine (AsyncEngine): The application's engine.

    Returns:
        str | None: The reported ``TimeZone`` on PostgreSQL, ``None`` on any
            other dialect (skipped).

    Raises:
        ConfigurationError: When the PostgreSQL session ``TimeZone`` is not UTC.
    """
    if db_engine.dialect.name != "postgresql":
        return None
    # #ASSUME: external-resources: the database is reachable at startup;
    # a connection failure propagates and fails startup, which is the
    # existing behaviour of the first request anyway.
    # #VERIFY: tests/integration/test_r8_hardening_postgres.py runs this
    # against PostgreSQL with a UTC and a non-UTC session.
    async with db_engine.connect() as connection:
        zone = cast("str", await connection.scalar(text("SHOW TimeZone")))
    if zone.lower() not in UTC_TIMEZONE_NAMES:
        msg = (
            f"PostgreSQL TimeZone is {zone!r}; it must be UTC. Set "
            "`timezone = 'UTC'` in postgresql.conf, or ALTER DATABASE ... "
            "SET timezone TO 'UTC'."
        )
        raise ConfigurationError(msg, details={"timezone": zone})
    return zone


# Deterministic constraint and index names (architecture review D-03).
#
# Without a convention, PostgreSQL invents names for unnamed constraints
# (`<table>_<col>_check`, `<table>_pkey`, ...) while SQLite and
# `Base.metadata.create_all()` leave them anonymous, so a migration cannot
# drop or alter a constraint by a name it can know in advance, and SQLite
# batch-mode migrations cannot address it at all.
#
# `ck` requires every CheckConstraint to carry a short `name=` (the rule,
# e.g. `liking_range`); the table prefix is added here, so do not repeat it
# in the model. `fk` deliberately omits the referred table so every
# generated name stays within PostgreSQL's 63-character identifier limit
# without SQLAlchemy's hash-suffixed truncation, which would make the
# PostgreSQL name differ from the SQLite one;
# tests/integration/test_schema_parity_postgres.py asserts both properties.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def _safe_rollback(session: AsyncSession) -> None:
    """Roll back a session without letting a rollback failure mask the caller's error.

    If ``session.rollback()`` itself raises (for example, the connection was
    already dropped), that new exception would otherwise propagate in place
    of the original exception that triggered the rollback, silently
    replacing the real error with a misleading one. This helper logs a
    rollback failure and swallows it so the original exception always
    survives.

    Args:
        session (AsyncSession): The database session to roll back.
    """
    try:
        await session.rollback()
    except Exception:
        logger.exception("session rollback failed; original exception still propagates")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.

    Yields:
        AsyncSession: Database session for executing queries.

    Raises:
        Exception: Whatever the caller's block raised, after an explicit
            rollback. Not narrowed to ``SQLAlchemyError``: a caller can raise
            a domain error (``ValueError``, ``BusinessLogicError``, and
            similar) mid-transaction, and that path must roll back exactly
            like a database-layer failure rather than relying on the
            implicit abort-on-close that `async with async_session_maker()`
            would otherwise provide. If the rollback itself fails, that
            failure is logged (see ``_safe_rollback``) and the original
            exception is still what propagates.

    Example:
        async with get_session() as session:
            result = await session.execute(select(Fragrance))
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await _safe_rollback(session)
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session for the request lifecycle.

    Raises:
        Exception: Whatever the request handler raised, after an explicit
            rollback (see ``get_session`` above for why this is not narrowed
            to ``SQLAlchemyError``, and for why a rollback failure is logged
            rather than allowed to replace the original exception).
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await _safe_rollback(session)
            raise
