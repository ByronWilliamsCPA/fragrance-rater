"""Tests for health check endpoints (Major finding 4: no error leakage)."""

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
class TestLiveness:
    """Tests for the liveness probe."""

    async def test_liveness_ok(self, test_app):
        """Liveness should always report ok without touching dependencies."""
        response = await test_app.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
class TestReadiness:
    """Tests for the readiness probe and its error-handling behavior."""

    async def test_readiness_ok(self, test_app):
        """Readiness should be 200 when the database check succeeds."""
        response = await test_app.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["checks"]["database"]["status"] is True

    async def test_readiness_never_leaks_raw_db_error(self, test_app):
        """A failed database check must return a generic message to the
        client and never the raw exception text (which can carry host,
        user, or auth-failure details).
        """
        sensitive_message = (
            "connection to server at "
            '"prod-db.internal.example.com" (10.0.0.5), port 5432 failed: '
            "FATAL: password authentication failed for user "
            '"fragrance_rater"'
        )

        @asynccontextmanager
        async def _raising_get_session():
            raise RuntimeError(sensitive_message)
            yield  # pragma: no cover - unreachable, satisfies generator shape

        with (
            patch(
                "fragrance_rater.core.database.get_session",
                _raising_get_session,
            ),
            patch("fragrance_rater.api.health.logger") as mock_logger,
        ):
            response = await test_app.get("/health/ready")

        assert response.status_code == 503
        body = response.text
        assert "password authentication failed" not in body
        assert "prod-db.internal.example.com" not in body

        detail = response.json()["detail"]
        assert detail["checks"]["database"]["status"] is False
        assert detail["checks"]["database"]["error"] == "dependency unreachable"

        # The real error must still be logged server-side for diagnosis.
        mock_logger.exception.assert_called_once()
        logged_kwargs = mock_logger.exception.call_args.kwargs
        assert sensitive_message in logged_kwargs.get("error", "")
