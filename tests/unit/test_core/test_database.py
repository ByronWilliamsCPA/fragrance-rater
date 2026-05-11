"""Unit tests for database session management."""

import contextlib
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError


class TestGetSession:
    """Tests for get_session async context manager."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_yields_session_and_commits_on_success(self) -> None:
        """Verify get_session yields session and commits on clean exit."""
        from fragrance_rater.core.database import get_session

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("fragrance_rater.core.database.async_session_maker", return_value=mock_ctx):
            async with get_session() as session:
                assert session is mock_session

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rolls_back_on_sqlalchemy_error(self) -> None:
        """Verify get_session rolls back and re-raises on SQLAlchemyError."""
        from fragrance_rater.core.database import get_session

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("fragrance_rater.core.database.async_session_maker", return_value=mock_ctx), pytest.raises(SQLAlchemyError):
            async with get_session() as _session:
                raise SQLAlchemyError("connection lost")

        mock_session.rollback.assert_awaited_once()


class TestGetDb:
    """Tests for get_db async generator (FastAPI dependency)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_yields_session_and_commits_on_success(self) -> None:
        """Verify get_db yields session and commits after iteration."""
        from fragrance_rater.core.database import get_db

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("fragrance_rater.core.database.async_session_maker", return_value=mock_ctx):
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session
            with contextlib.suppress(StopAsyncIteration):
                await gen.__anext__()

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rolls_back_on_sqlalchemy_error(self) -> None:
        """Verify get_db rolls back and re-raises on SQLAlchemyError."""
        from fragrance_rater.core.database import get_db

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("fragrance_rater.core.database.async_session_maker", return_value=mock_ctx):
            gen = get_db()
            _session = await gen.__anext__()
            with pytest.raises(SQLAlchemyError):
                await gen.athrow(SQLAlchemyError("deadlock"))

        mock_session.rollback.assert_awaited_once()
