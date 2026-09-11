"""Authentik forward-auth identity dependency.

Critical finding 2: zero auth surface existed anywhere in ``api/``. This app
is deployed behind Authentik/Traefik forward-auth (same pattern as
``plan.williamshome.family`` in this homelab; the ``authentik-auth``
forwardAuth middleware in ``services/traefik/dynamic/middleware.yml`` of the
``homelab-infra`` repo runs with ``trustForwardHeader: false``). On a
verified request, Traefik injects ``X-authentik-uid``, ``X-authentik-username``,
and ``X-authentik-email`` (among others), stripping any client-supplied
header of the same name first. That makes these headers a trustworthy signal
of who is calling, if and only if the request actually transited that
middleware.

This module does not implement a separate shared-secret auth scheme; the
proxy layer is the auth boundary. It only reads the identity Traefik already
verified and, when ``settings.authentik_required`` is true, refuses to treat
a request that skipped the proxy as anonymous.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from fragrance_rater.core.config import settings

AUTHENTIK_USERNAME_HEADER = "X-Authentik-Username"
AUTHENTIK_UID_HEADER = "X-Authentik-Uid"
AUTHENTIK_EMAIL_HEADER = "X-Authentik-Email"


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """The acting identity for a request, as forwarded by Authentik/Traefik.

    Attributes:
        username (str | None): Authentik username, or None if not present.
        uid (str | None): Authentik user id, or None if not present.
        email (str | None): Authentik email, or None if not present.
    """

    username: str | None
    uid: str | None
    email: str | None

    @property
    def is_authenticated(self) -> bool:
        """Whether any Authentik identity signal was present on the request.

        Returns:
            bool: True if a username or uid header was present.
        """
        return self.username is not None or self.uid is not None


async def get_current_identity(request: Request) -> AuthenticatedIdentity:
    """FastAPI dependency exposing the Authentik forward-auth identity.

    Args:
        request (Request): The incoming request.

    Returns:
        AuthenticatedIdentity: The acting identity for this request. All
            fields are None when Authentik is not required and the request
            carries no Authentik headers (local dev/tests).

    Raises:
        HTTPException: 401 if ``settings.authentik_required`` is true and
            the request carries no Authentik username header, meaning it
            did not transit the Traefik forward-auth middleware.
    """
    username = request.headers.get(AUTHENTIK_USERNAME_HEADER)
    uid = request.headers.get(AUTHENTIK_UID_HEADER)
    email = request.headers.get(AUTHENTIK_EMAIL_HEADER)

    # #CRITICAL: security: a request that bypassed Traefik's forward-auth
    # middleware carries none of these headers. Treating that as
    # "anonymous" would let anyone who can reach this service directly
    # (skipping the proxy) mutate data with no identity attached at all.
    # #VERIFY: fail closed (401) whenever settings.authentik_required is
    # true and the username header is absent, rather than silently falling
    # back to an unauthenticated identity. Tests and local dev disable this
    # via AUTHENTIK_REQUIRED=false (see core/config.py).
    if settings.authentik_required and username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTIK_IDENTITY_REQUIRED",
                "message": (
                    "This request did not carry a verified Authentik "
                    "identity header. Requests must transit the Traefik "
                    "forward-auth middleware."
                ),
            },
        )

    return AuthenticatedIdentity(username=username, uid=uid, email=email)
