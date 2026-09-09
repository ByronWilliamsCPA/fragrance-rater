"""Unit tests for the health check endpoints.

``check_database``'s exception handling is the specific regression target:
the PR #40 follow-up fixed a silent (unlogged) failure path, and this file
previously shipped with zero coverage of that fix.

``fragrance_rater.core.database`` is a real module on this branch, so the
failure path is exercised by patching ``get_session`` to raise a
connection-style error rather than relying on the absence of a database on
the test host (which would make these tests flip depending on whether a
local Postgres happens to be listening).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from fragrance_rater.api.health import check_database, readiness
from fragrance_rater.main import app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

client = TestClient(app)

_CONNECTION_ERROR = "connection to server at 127.0.0.1, port 5432 failed"


@asynccontextmanager
async def _raising_get_session() -> AsyncIterator[None]:
    raise ConnectionRefusedError(_CONNECTION_ERROR)
    yield  # pragma: no cover - unreachable, satisfies generator shape


@pytest.fixture(autouse=True)
def _database_unavailable() -> Iterator[None]:
    """Make every database readiness check in this module fail deterministically."""
    with patch("fragrance_rater.core.database.get_session", _raising_get_session):
        yield


def test_liveness_returns_ok() -> None:
    """The liveness probe never depends on external services."""
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_startup_returns_started() -> None:
    """The startup probe reports ``started`` once the app object exists."""
    response = client.get("/health/startup")

    assert response.status_code == 200
    assert response.json()["status"] == "started"


@pytest.mark.asyncio
async def test_check_database_logs_the_failure() -> None:
    """check_database's except branch must log, not silently swallow, a failure.

    This is the direct regression test for the PR #40 follow-up: before that
    fix, a database-connectivity failure was reported in the response body
    but never logged server-side, leaving operators with no trace of *why*
    readiness failed.
    """
    with patch("fragrance_rater.api.health.logger") as mock_logger:
        result = await check_database()

    assert result.status is False
    assert result.error == "dependency unreachable"
    mock_logger.exception.assert_called_once()
    logged_kwargs = mock_logger.exception.call_args.kwargs
    assert _CONNECTION_ERROR in logged_kwargs.get("error", "")
    assert logged_kwargs.get("error_type") == "ConnectionRefusedError"


@pytest.mark.asyncio
async def test_readiness_returns_503_and_does_not_leak_exception_detail() -> None:
    """The readiness probe must fail closed (503) without leaking driver internals.

    The response body carries only the generic error string, never the raw
    exception text (which could embed a DSN, host, or credential).
    """
    with pytest.raises(HTTPException) as exc_info:
        await readiness()

    detail = exc_info.value.detail
    assert detail["checks"]["database"]["error"] == "dependency unreachable"
    assert _CONNECTION_ERROR not in str(detail)


def test_readiness_endpoint_returns_503_via_http() -> None:
    """End-to-end: GET /health/ready returns 503 while the database check fails."""
    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["checks"]["database"]["status"] is False
    assert _CONNECTION_ERROR not in response.text
