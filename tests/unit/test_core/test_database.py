"""Tests for the async database session helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase

from fragrance_rater.core import database
from fragrance_rater.core.database import Base, get_db, get_session


def _mock_session() -> AsyncMock:
    """Build an AsyncMock that behaves like an AsyncSession context manager."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def test_base_is_declarative() -> None:
    assert issubclass(Base, DeclarativeBase)


class TestGetSession:
    """Tests for the get_session async context manager."""

    @pytest.mark.asyncio
    async def test_commits_on_success(self) -> None:
        session = _mock_session()
        with patch.object(database, "async_session_maker", return_value=session):
            async with get_session() as active:
                assert active is session

        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rolls_back_and_reraises_on_sqlalchemy_error(self) -> None:
        session = _mock_session()

        async def use_session_and_fail() -> None:
            async with get_session():
                raise SQLAlchemyError("boom")

        with (
            patch.object(database, "async_session_maker", return_value=session),
            pytest.raises(SQLAlchemyError),
        ):
            await use_session_and_fail()

        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


class TestGetDb:
    """Tests for the get_db FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_yields_session_and_commits(self) -> None:
        session = _mock_session()
        with patch.object(database, "async_session_maker", return_value=session):
            generator = get_db()
            active = await anext(generator)
            assert active is session
            with pytest.raises(StopAsyncIteration):
                await anext(generator)

        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rolls_back_when_commit_fails(self) -> None:
        session = _mock_session()
        session.commit.side_effect = SQLAlchemyError("commit failed")
        with patch.object(database, "async_session_maker", return_value=session):
            generator = get_db()
            await anext(generator)
            with pytest.raises(SQLAlchemyError):
                await anext(generator)

        session.rollback.assert_awaited_once()
