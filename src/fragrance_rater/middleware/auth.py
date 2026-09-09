"""Shared household API key authentication for mutating endpoints.

This is a personal, single-household application (see ``project-vision.md``);
there is no per-user account system. Every endpoint that mutates state or
triggers a billed upstream call (the LLM rating endpoint) must still require
*some* explicit credential rather than relying on network-level obscurity
(e.g. "it's only reachable on the home LAN"). A single shared API key sent as
the ``X-API-Key`` header is a proportionate control for this deployment size;
do not build out a full OAuth2/JWT/session system for a household app.

Read-only, non-billed endpoints (``GET /fragrances*``, ``GET /health/*``) are
intentionally left unauthenticated: they return static/local catalog data
and are not a cost or data-integrity vector.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from fragrance_rater.core.config import settings

API_KEY_HEADER = "X-API-Key"
"""Header name callers must use to send the shared household API key."""

_PROBLEM_TYPE_BASE = "https://api.fragrance-rater.internal/errors"


def _problem_detail(*, title: str, status_code: int, detail: str) -> dict[str, object]:
    """Build an RFC 7807 Problem Details body for an auth failure.

    Args:
        title (str): Short, human-readable summary of the problem type.
        status_code (int): HTTP status code repeated in the body per RFC 7807.
        detail (str): Human-readable explanation specific to this occurrence.

    Returns:
        dict[str, object]: RFC 7807-shaped problem details payload.
    """
    slug = title.lower().replace(" ", "-")
    return {
        "type": f"{_PROBLEM_TYPE_BASE}/{slug}",
        "title": title,
        "status": status_code,
        "detail": detail,
    }


def require_api_key(
    x_api_key: Annotated[
        str | None,
        Header(alias=API_KEY_HEADER),  # pyright: ignore[reportCallInDefaultInitializer]
    ] = None,
) -> None:
    """FastAPI dependency enforcing the shared household API key.

    Apply this as a ``dependencies=[Depends(require_api_key)]`` entry (or a
    direct parameter) on every mutating route (``POST``/``PUT``/``PATCH``/
    ``DELETE``). Read-only routes should not depend on this.

    #CRITICAL: security: without this check, mutating endpoints (currently
    ``POST /ratings``, which triggers a billed OpenRouter call) would be
    reachable by anyone who can route a request to the service, relying only
    on network placement for protection.
    #VERIFY: deployments outside a fully trusted, single-household LAN must
    set ``FRAGRANCE_RATER_API_KEY`` to a long random value and configure
    callers to send it as ``X-API-Key``. CI sets a fixture key so the Newman
    contract suite exercises the real check (see
    ``.github/workflows/postman-api-tests.yml``).

    Args:
        x_api_key (Annotated[str | None, Header(alias=API_KEY_HEADER)]):
            Value of the incoming ``X-API-Key`` header, injected by FastAPI.

    Raises:
        HTTPException: 503 when no API key is configured for this
            deployment (fail closed rather than silently allowing writes),
            or 401 when the header is missing or does not match the
            configured key.
    """
    configured_key = settings.api_key
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_problem_detail(
                title="Auth Not Configured",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "FRAGRANCE_RATER_API_KEY is not set. Mutating endpoints "
                    "fail closed until a household API key is configured."
                ),
            ),
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_problem_detail(
                title="Unauthorized",
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Missing or invalid {API_KEY_HEADER} header.",
            ),
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )
