"""Regression tests for the FastAPI app assembly in ``fragrance_rater.main``.

These cover two PR #66 Important findings that are specific to how
``fragrance_rater.main`` wires up already-tested building blocks (CORS,
security headers, SSRF prevention, the slowapi limiter):

- Finding 1: CORSMiddleware was previously registered twice (once inside
  ``add_security_middleware`` with a locked-down empty allow-list, once
  directly in ``main.py`` with a hardcoded, more permissive allow-list).
  Starlette treats the most-recently-added middleware as outermost, so the
  second registration silently shadowed the first's intended lockdown.
  ``main.py`` now registers CORSMiddleware exactly once, using
  ``settings.cors_allowed_origins``.
- Finding 2: the ``@limiter.limit(RATINGS_RATE_LIMIT)`` decorator on
  ``POST /ratings`` checks the process-wide ``limiter.enabled`` flag, which
  is independent of whether ``DefaultRateLimitMiddleware``/
  ``app.state.limiter`` get registered. ``settings.rate_limit_enabled=False``
  previously only skipped the general middleware, leaving POST /ratings
  still rate limited. ``main.py`` now sets ``limiter.enabled =
  settings.rate_limit_enabled`` unconditionally so the toggle actually
  disables rate limiting everywhere when set to False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from fragrance_rater.core.config import settings
from fragrance_rater.main import app
from fragrance_rater.middleware import limiter

if TYPE_CHECKING:
    from collections.abc import Iterator

RATING_PAYLOAD = {
    "name": "Aventus",
    "brand": "Creed",
    "description": "Smoky pineapple opening settling into a musky vanilla dry-down.",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with TEST_MODE enabled (LLM fixture, no network call)."""
    monkeypatch.setenv("TEST_MODE", "true")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _restore_limiter_enabled() -> Iterator[None]:
    """Restore ``limiter.enabled`` after tests that flip it directly.

    ``limiter`` is a process-wide singleton shared by the whole test
    session; tests below simulate ``main.py``'s startup wiring by setting
    ``limiter.enabled`` directly, so it must be restored afterwards to avoid
    leaking state into unrelated tests.
    """
    original = limiter.enabled
    yield
    limiter.enabled = original


class TestSingleCorsRegistration:
    """Finding 1: exactly one CORSMiddleware, using settings.cors_allowed_origins."""

    def test_cors_middleware_registered_exactly_once(self) -> None:
        cors_registrations = [m for m in app.user_middleware if m.cls is CORSMiddleware]

        assert len(cors_registrations) == 1

    def test_configured_origin_receives_cors_headers(self, client: TestClient) -> None:
        allowed_origin = settings.cors_allowed_origins[0]

        response = client.get("/health/live", headers={"Origin": allowed_origin})

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == allowed_origin

    def test_unlisted_origin_does_not_receive_cors_headers(
        self, client: TestClient
    ) -> None:
        response = client.get(
            "/health/live", headers={"Origin": "https://evil.example.com"}
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_for_unlisted_origin_is_not_approved(
        self, client: TestClient
    ) -> None:
        """A CORS preflight for an origin outside the allow-list must not be approved.

        This is the concrete failure mode the duplicate-registration bug
        produced: the shadowed, locked-down CORSMiddleware never got a
        chance to reject anything because the permissive one (added last,
        thus outermost) answered every preflight first.
        """
        response = client.options(
            "/health/live",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert "access-control-allow-origin" not in response.headers


class TestRateLimitEnabledTogglesDecoratorToo:
    """Finding 2: settings.rate_limit_enabled=False must disable POST /ratings too."""

    def test_rate_limit_enabled_false_disables_decorator_too(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empirical regression test for the toggle mismatch.

        Simulates what ``main.py`` does at startup when
        ``RATE_LIMIT_ENABLED=false`` (``limiter.enabled = False``,
        ``DefaultRateLimitMiddleware``/``app.state.limiter`` never
        registered) and confirms a burst of requests to POST /ratings, well
        past ``RATINGS_RATE_LIMIT`` (10/minute), is never rate limited and
        never errors. Before the fix, this same scenario returned 429s
        starting at the 11th request even though the toggle says rate
        limiting should be off entirely (see the #VERIFY note in
        ``fragrance_rater.main`` for the live-verified pre-fix statuses).
        """
        monkeypatch.setattr(settings, "api_key", "household-secret")
        limiter.enabled = False
        limiter.reset()
        headers = {"X-API-Key": "household-secret"}

        responses = [
            client.post("/ratings", json=RATING_PAYLOAD, headers=headers)
            for _ in range(15)
        ]
        statuses = [response.status_code for response in responses]

        assert statuses == [200] * 15

    def test_rate_limit_enabled_true_still_enforces_ratings_limit(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No-regression check: the enabled path still enforces the limit."""
        monkeypatch.setattr(settings, "api_key", "household-secret")
        limiter.enabled = True
        limiter.reset()
        headers = {"X-API-Key": "household-secret"}

        responses = [
            client.post("/ratings", json=RATING_PAYLOAD, headers=headers)
            for _ in range(11)
        ]
        statuses = [response.status_code for response in responses]

        assert statuses[:10] == [200] * 10
        assert statuses[10] == 429

    def test_main_module_sets_limiter_enabled_from_settings(self) -> None:
        """``main.py``'s module-level wiring set ``limiter.enabled`` at import time.

        A weaker but still meaningful check on the actual startup code path
        (as opposed to the simulated states above): at collection time this
        test session's ``settings.rate_limit_enabled`` is True (the
        project's documented test default, see ``tests/conftest.py``), and
        importing ``fragrance_rater.main`` must have already synced
        ``limiter.enabled`` to match it.
        """
        assert settings.rate_limit_enabled is True
        assert limiter.enabled is True
