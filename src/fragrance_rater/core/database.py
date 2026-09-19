"""Database connection and session management.

This module provides async database connectivity using SQLAlchemy 2.0.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from fragrance_rater.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


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
            would otherwise provide.

    Example:
        async with get_session() as session:
            result = await session.execute(select(Fragrance))
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session for the request lifecycle.

    Raises:
        Exception: Whatever the request handler raised, after an explicit
            rollback (see ``get_session`` above for why this is not narrowed
            to ``SQLAlchemyError``).
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
