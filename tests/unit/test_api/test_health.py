"""Tests for health check endpoints (Major finding 4: no error leakage)."""

from unittest.mock import patch

import pytest

from fragrance_rater.core.database import get_db
from fragrance_rater.main import app


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

        Critical finding 1 (PR #66 review) made `check_database` take its
        session via the `get_db` FastAPI dependency instead of opening one
        itself through `core.database.get_session`, so failure now has to be
        injected at that same seam (overriding `get_db`, as `conftest.py`'s
        `test_app` fixture already does for the happy path) rather than by
        patching `get_session`, which `check_database` no longer calls.
        """
        sensitive_message = (
            "connection to server at "
            '"prod-db.internal.example.com" (10.0.0.5), port 5432 failed: '
            "FATAL: password authentication failed for user "
            '"fragrance_rater"'
        )

        class _RaisingSession:
            """Stand-in session whose only method `check_database` calls
            raises, mirroring a real connection failure surfaced through
            `session.execute(...)`."""

            async def execute(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError(sensitive_message)

        async def _raising_get_db():
            yield _RaisingSession()

        previous_override = app.dependency_overrides[get_db]
        app.dependency_overrides[get_db] = _raising_get_db
        try:
            with patch("fragrance_rater.api.health.logger") as mock_logger:
                response = await test_app.get("/health/ready")
        finally:
            # test_app's own fixture teardown clears all overrides at the end
            # of the test, but restoring the happy-path override immediately
            # keeps this test from leaking a broken get_db into any
            # assertion added after this block later.
            app.dependency_overrides[get_db] = previous_override

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
        assert logged_kwargs.get("error_type") == "RuntimeError"


@pytest.mark.asyncio
class TestStartup:
    """Tests for the startup probe."""

    async def test_startup_ok(self, test_app):
        """Startup should report "started" once the app object exists."""
        response = await test_app.get("/health/startup")
        assert response.status_code == 200
        assert response.json()["status"] == "started"
