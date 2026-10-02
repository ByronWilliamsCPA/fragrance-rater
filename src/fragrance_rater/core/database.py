"""Database connection and session management.

This module provides async database connectivity using SQLAlchemy 2.0.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from fragrance_rater.core.config import settings
from fragrance_rater.utils.logging import get_logger

logger = get_logger(__name__)


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
