"""Integration tests for the ``POST /ratings`` auth and rate-limit behavior.

These tests exercise the wired-up FastAPI app (auth dependency + slowapi
rate limiting) end-to-end via ``TestClient`` rather than unit-testing the
dependency function in isolation, since the interaction between the two
(and with the read-only routes that must remain unauthenticated) is the
actual thing being remediated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from fragrance_rater.core.config import settings
from fragrance_rater.middleware import limiter

if TYPE_CHECKING:
    from collections.abc import Iterator

RATING_PAYLOAD = {
    "name": "Aventus",
    "brand": "Creed",
    "description": "Smoky pineapple opening settling into a musky vanilla dry-down.",
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    """Reset slowapi's in-memory limiter storage between tests.

    The limiter is a module-level singleton shared across the whole test
    session; without a reset, request counts from one test would bleed
    into the next and produce order-dependent 429s.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """FastAPI TestClient with TEST_MODE enabled (LLM fixture, no network call)."""
    monkeypatch.setenv("TEST_MODE", "true")
    from fragrance_rater.main import app

    return TestClient(app)


def test_ratings_fails_closed_when_no_api_key_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No FRAGRANCE_RATER_API_KEY configured -> 503, not a silent 200."""
    monkeypatch.setattr(settings, "api_key", None)

    response = client.post("/ratings", json=RATING_PAYLOAD)

    assert response.status_code == 503
    assert response.json()["detail"]["title"] == "Auth Not Configured"


def test_ratings_rejects_missing_api_key_header(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Configured key, no header sent -> 401."""
    monkeypatch.setattr(settings, "api_key", "household-secret")

    response = client.post("/ratings", json=RATING_PAYLOAD)

    assert response.status_code == 401
    assert response.json()["detail"]["title"] == "Unauthorized"


def test_ratings_rejects_wrong_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Configured key, wrong header value -> 401."""
    monkeypatch.setattr(settings, "api_key", "household-secret")

    response = client.post(
        "/ratings", json=RATING_PAYLOAD, headers={"X-API-Key": "not-the-secret"}
    )

    assert response.status_code == 401


def test_ratings_accepts_correct_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Configured key, matching header -> 200 with the LLM fixture body."""
    monkeypatch.setattr(settings, "api_key", "household-secret")

    response = client.post(
        "/ratings", json=RATING_PAYLOAD, headers={"X-API-Key": "household-secret"}
    )

    assert response.status_code == 200
    body = response.json()
    assert 1 <= body["score"] <= 10
    assert body["model"] == "test-mode-stub"


def test_ratings_rate_limited_after_threshold(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """More than 10 requests/minute from one caller -> 429 on the 11th+.

    The 429 must be RFC 7807 problem-details (application/problem+json), not
    slowapi's default {"error": ...} shape, matching the rest of this API's
    error responses (see rate_limit.rate_limit_exceeded_handler).
    """
    monkeypatch.setattr(settings, "api_key", "household-secret")
    headers = {"X-API-Key": "household-secret"}

    responses = [
        client.post("/ratings", json=RATING_PAYLOAD, headers=headers) for _ in range(11)
    ]
    statuses = [response.status_code for response in responses]

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429

    limited_response = responses[10]
    assert limited_response.headers["content-type"] == "application/problem+json"
    body = limited_response.json()
    assert body["status"] == 429
    assert body["title"] == "Rate Limit Exceeded"


def test_fragrances_list_does_not_require_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only catalog endpoint stays unauthenticated regardless of api_key state."""
    monkeypatch.setattr(settings, "api_key", "household-secret")

    response = client.get("/fragrances")

    assert response.status_code == 200


def test_health_live_does_not_require_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Health probes stay unauthenticated regardless of api_key state."""
    monkeypatch.setattr(settings, "api_key", "household-secret")

    response = client.get("/health/live")

    assert response.status_code == 200
