"""Tests for the Authentik forward-auth identity dependency (Critical 2).

Covers the fail-closed behavior when AUTHENTIK_REQUIRED is true and the
verified identity header is missing, plus the pass-through/optional
behavior otherwise.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, Request

from fragrance_rater.core.auth import (
    AUTHENTIK_EMAIL_HEADER,
    AUTHENTIK_UID_HEADER,
    AUTHENTIK_USERNAME_HEADER,
    AuthenticatedIdentity,
    get_current_identity,
)
from fragrance_rater.core.config import settings


def _make_request(headers: dict[str, str] | None = None) -> Request:
    """Build a minimal ASGI Request carrying the given headers."""
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "method": "GET",
        "path": "/",
    }
    return Request(scope)


class TestAuthenticatedIdentity:
    """Tests for the AuthenticatedIdentity dataclass."""

    def test_is_authenticated_true_with_username(self) -> None:
        identity = AuthenticatedIdentity(username="byron", uid=None, email=None)
        assert identity.is_authenticated is True

    def test_is_authenticated_true_with_uid_only(self) -> None:
        identity = AuthenticatedIdentity(username=None, uid="123", email=None)
        assert identity.is_authenticated is True

    def test_is_authenticated_false_when_empty(self) -> None:
        identity = AuthenticatedIdentity(username=None, uid=None, email=None)
        assert identity.is_authenticated is False


@pytest.mark.asyncio
class TestGetCurrentIdentity:
    """Tests for the get_current_identity FastAPI dependency."""

    async def test_required_and_missing_raises_401(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Critical finding 2: fail closed, not anonymous, when required."""
        monkeypatch.setattr(settings, "authentik_required", True)
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_identity(request)

        assert exc_info.value.status_code == 401
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert detail["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_required_and_present_returns_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "authentik_required", True)
        request = _make_request(
            {
                AUTHENTIK_USERNAME_HEADER: "byron",
                AUTHENTIK_UID_HEADER: "42",
                AUTHENTIK_EMAIL_HEADER: "byron@example.com",
            }
        )

        identity = await get_current_identity(request)

        assert identity.username == "byron"
        assert identity.uid == "42"
        assert identity.email == "byron@example.com"
        assert identity.is_authenticated is True

    async def test_not_required_and_missing_returns_anonymous(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Local dev/tests: no header, no exception, anonymous identity."""
        monkeypatch.setattr(settings, "authentik_required", False)
        request = _make_request()

        identity = await get_current_identity(request)

        assert identity.username is None
        assert identity.is_authenticated is False

    async def test_not_required_and_present_still_returns_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "authentik_required", False)
        request = _make_request({AUTHENTIK_USERNAME_HEADER: "veronica"})

        identity = await get_current_identity(request)

        assert identity.username == "veronica"
