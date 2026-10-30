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
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from fragrance_rater.core.config import settings
from fragrance_rater.models.calibration import Enrollment

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

AUTHENTIK_USERNAME_HEADER = "X-Authentik-Username"
AUTHENTIK_UID_HEADER = "X-Authentik-Uid"
AUTHENTIK_EMAIL_HEADER = "X-Authentik-Email"
#: Pipe-separated group names (``group-a|group-b``), as Authentik's proxy
#: outpost sends them.
AUTHENTIK_GROUPS_HEADER = "X-Authentik-Groups"


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
    # A present but blank header is not an identity; treat it as missing so
    # the fail-closed check below still applies.
    username = (request.headers.get(AUTHENTIK_USERNAME_HEADER) or "").strip() or None
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


_IDENTITY_REQUIRED_DETAIL = {
    "error": "AUTHENTIK_IDENTITY_REQUIRED",
    "message": (
        "This request did not carry a verified Authentik identity header. "
        "Requests must transit the Traefik forward-auth middleware."
    ),
}


async def require_identity(
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> AuthenticatedIdentity:
    """Require a named caller, whatever ``AUTHENTIK_REQUIRED`` says.

    The one identity dependency for every mutating route and every read of
    reviewer data (architecture review S-06, B-11). Unlike
    ``get_current_identity``, it never returns an anonymous identity, so a
    serving environment that set ``AUTHENTIK_REQUIRED=false`` by mistake
    still cannot accept anonymous writes, and every write records who made
    it.

    #CRITICAL: security: the username is trustworthy only because the
    production nginx forwards it solely from Traefik (ADR-008, 2026-10-21
    amendment).
    #VERIFY: tests/unit/test_api/test_authorization_matrix.py sends every
    protected route without the header and expects 401.

    Args:
        identity (Annotated[AuthenticatedIdentity, Depends(get_current_identity)]):
            The forwarded identity.

    Returns:
        AuthenticatedIdentity: The same identity, with a non-empty username.

    Raises:
        HTTPException: 401 when no username was forwarded.
    """
    if not identity.username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_IDENTITY_REQUIRED_DETAIL,
        )
    return identity


VerifiedIdentity = Annotated[AuthenticatedIdentity, Depends(require_identity)]
"""Route parameter type for a caller who must be named."""


def is_manager(username: str) -> bool:
    """Whether ``username`` is on the calibration manager allowlist.

    Args:
        username (str): A verified Authentik username.

    Returns:
        bool: True for a configured manager.
    """
    return username in settings.calibration_admin_usernames


def actor(identity: AuthenticatedIdentity) -> tuple[str, bool]:
    """Return the caller's username and manager flag, failing closed.

    Moved from ``api/calibration.py`` so every router shares one policy
    (architecture review B-11).

    Args:
        identity (AuthenticatedIdentity): The forwarded identity.

    Returns:
        tuple[str, bool]: The username and whether it belongs to a manager.

    Raises:
        HTTPException: 401 without a named caller, including in local
            development.
    """
    if not identity.username:
        raise HTTPException(status_code=401, detail="A named recorder is required")
    return identity.username, is_manager(identity.username)


def manager(identity: AuthenticatedIdentity) -> str:
    """Require an explicitly configured manager.

    Args:
        identity (AuthenticatedIdentity): The forwarded identity.

    Returns:
        str: The manager's username.

    Raises:
        HTTPException: 401 without a named caller, 403 for a non-manager.
    """
    username, admin = actor(identity)
    if not admin:
        raise HTTPException(status_code=403, detail="Calibration manager required")
    return username


async def assigned_reviewer_ids(db: AsyncSession, username: str) -> set[str]:
    """Return the reviewers whose enrollments list ``username`` as a recorder.

    Args:
        db (AsyncSession): Database session.
        username (str): A verified Authentik username.

    Returns:
        set[str]: Reviewer ids this user may read as a recorder.
    """
    enrollments = await db.scalars(select(Enrollment))
    return {
        enrollment.reviewer_id
        for enrollment in enrollments
        if username in enrollment.recorder_usernames
    }


async def authorize_reviewer(
    db: AsyncSession, reviewer_id: str, username: str, admin: bool
) -> None:
    """Allow managers, or recorders assigned to the reviewer, and no one else.

    The owner's read policy (architecture review Q5, decided 2026-10-21):
    household members do not read each other's evidence; a manager reads
    everyone, and a recorder reads only reviewers whose enrollment lists
    them.

    Args:
        db (AsyncSession): Database session.
        reviewer_id (str): The reviewer whose data is requested.
        username (str): A verified Authentik username.
        admin (bool): Whether the caller is a manager.

    Raises:
        HTTPException: 403 when the caller may not read this reviewer.
    """
    if admin:
        return
    if reviewer_id not in await assigned_reviewer_ids(db, username):
        raise HTTPException(
            status_code=403, detail="Recorder is not assigned to reviewer"
        )
