"""Unit tests for the health check endpoints.

``check_database``'s exception handling is the specific regression target:
the PR #40 follow-up fixed a silent (unlogged) failure path, and this file
previously shipped with zero coverage of that fix. ``core.database`` does
not exist yet in this codebase, so ``check_database``'s try block always
raises ``ModuleNotFoundError`` today, exercising the real failure path
without needing to mock anything.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from fragrance_rater.api.health import check_database, readiness
from fragrance_rater.main import app

client = TestClient(app)


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
async def test_check_database_logs_the_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """check_database's except branch must log, not silently swallow, a failure.

    This is the direct regression test for the PR #40 follow-up: before that
    fix, a database-connectivity failure was reported in the response body
    but never logged server-side, leaving operators with no trace of *why*
    readiness failed.
    """
    with caplog.at_level(logging.ERROR):
        result = await check_database()

    assert result.status is False
    assert result.error == "dependency check failed; see server logs for detail"
    assert any(
        "readiness check failed" in record.message
        or "readiness check failed" in str(record.msg)
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_readiness_returns_503_and_does_not_leak_exception_detail() -> None:
    """The readiness probe must fail closed (503) without leaking driver internals.

    The response body carries only the generic error string, never the raw
    exception text (which could embed a DSN, host, or credential).
    """
    with pytest.raises(HTTPException) as exc_info:
        await readiness()

    detail = exc_info.value.detail
    assert detail["checks"]["database"]["error"] == (
        "dependency check failed; see server logs for detail"
    )


def test_readiness_endpoint_returns_503_via_http() -> None:
    """End-to-end: GET /health/ready returns 503 while the database check fails."""
    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["checks"]["database"]["status"] is False
