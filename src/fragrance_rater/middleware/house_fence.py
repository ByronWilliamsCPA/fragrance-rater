"""Confine fragrance house contributors to the house-intake routes.

Every account on this deployment was a household member until house intake
existed, and most routers rely on that: ``GET /reviewers`` lists family
members without asking who is calling, and any authenticated identity may
create or delete catalog fragrances. A house representative is an external
party, so their identity is fenced here, in one place, rather than by adding
a check to every existing and future route.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from fragrance_rater.core.auth import AUTHENTIK_USERNAME_HEADER
from fragrance_rater.core.config import settings

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

_USERNAME_HEADER = AUTHENTIK_USERNAME_HEADER.lower().encode("latin-1")


def _allowed_prefixes() -> tuple[str, ...]:
    return (f"{settings.api_v1_prefix}/house-intake", "/health")


def _is_allowed(path: str) -> bool:
    return any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in _allowed_prefixes()
    )


class HouseContributorFenceMiddleware:
    """Refuse a house contributor's request outside the intake routes.

    # #CRITICAL: security: this is an allowlist, not a denylist. A router
    # added later is closed to house contributors by default; opening one
    # requires adding its prefix to `_allowed_prefixes` deliberately.
    # #VERIFY: test_house_fence.py asserts a house identity receives 403 on
    # /reviewers, /fragrances, /calibration/access, and /docs, and is let
    # through on /house-intake/*. Prefix matching is segment-aware, so
    # /house-intake-admin would not match /house-intake.
    # #ASSUME: security: the username header is trustworthy only because
    # Traefik strips any client-supplied copy before forward-auth sets it
    # (see core/auth.py); this middleware inherits that trust boundary and
    # adds no other.

    Args:
        app (ASGIApp): The application to protect.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request through unless a house contributor strays.

        Args:
            scope (Scope): ASGI connection scope.
            receive (Receive): ASGI receive callable.
            send (Send): ASGI send callable.
        """
        if scope["type"] != "http" or not settings.house_contributors:
            await self.app(scope, receive, send)
            return
        headers = cast("list[tuple[bytes, bytes]]", scope.get("headers", []))
        username = next(
            (
                value.decode("latin-1")
                for key, value in headers
                if key == _USERNAME_HEADER
            ),
            None,
        )
        path = cast("str", scope.get("path", ""))
        if username in settings.house_contributors and not _is_allowed(path):
            body = json.dumps(
                {
                    "detail": {
                        "error": "HOUSE_CONTRIBUTOR_FENCED",
                        "message": (
                            "House contributor accounts can only use the house "
                            "submission pages."
                        ),
                    }
                }
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
