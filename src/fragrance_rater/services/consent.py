"""Consent text and consent events (R7b; capture assessment 13.11 and 18.5).

Consent is recorded per scope as an append-only log of grants and withdrawals,
each stamped with the version and SHA-256 of the exact text the evaluator was
shown. The current state of a scope is its latest event.

The text lives in ``fragrance_rater/consent/`` as a Markdown file whose first
two lines are ``Version: ...`` and ``Status: DRAFT|APPROVED``. The system will
not record a *grant* against a draft: a person has to approve the wording (and
settle the policy decisions marked in it) before any consent can be recorded.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from fastapi import HTTPException
from sqlalchemy import select

from fragrance_rater.models.consent import CONSENT_SCOPES, ConsentEvent
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

CONSENT_TEXT_PATH = Path(__file__).parents[1] / "consent" / "family-consent-v1.md"


def reject(message: str, status: int = 409) -> NoReturn:
    """Raise a public domain error.

    Args:
        message (str): The detail returned to the caller.
        status (int): The HTTP status; 409 unless a caller says otherwise.

    Raises:
        HTTPException: Always.
    """
    raise HTTPException(status_code=status, detail=message)


@dataclass(frozen=True)
class ConsentText:
    """The wording evaluators are shown, with the identity it is recorded under.

    Attributes:
        version (str): The ``Version:`` header; stored on every grant.
        status (str): The ``Status:`` header, upper-cased.
        sha256 (str): Hex SHA-256 of the file's exact bytes.
        body (str): The full file contents, header lines included.
    """

    version: str
    status: str
    sha256: str
    body: str

    @property
    def approved(self) -> bool:
        """Return whether a person has approved this wording for use."""
        return self.status == "APPROVED"


@cache
def load_consent_text(path: Path = CONSENT_TEXT_PATH) -> ConsentText:
    """Read and fingerprint a consent text file.

    Args:
        path (Path): The Markdown file; defaults to the shipped text.

    Returns:
        ConsentText: Its version, status, digest, and body.

    Raises:
        ValueError: If the ``Version:`` or ``Status:`` header is missing.
    """
    raw = path.read_bytes()
    body = raw.decode("utf-8")
    headers: dict[str, str] = {}
    for line in body.splitlines()[:5]:
        key, _, value = line.partition(":")
        if key in {"Version", "Status"} and value.strip():
            headers[key] = value.strip()
    if "Version" not in headers or "Status" not in headers:
        message = f"{path.name} must start with 'Version:' and 'Status:' lines"
        raise ValueError(message)
    return ConsentText(
        version=headers["Version"],
        status=headers["Status"].upper(),
        sha256=hashlib.sha256(raw).hexdigest(),
        body=body,
    )


class ConsentService:
    """Record and read consent events for one database session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def events(self, reviewer_id: str) -> list[ConsentEvent]:
        """List a reviewer's consent events, oldest first.

        Args:
            reviewer_id (str): Whose consent log to read.

        Returns:
            list[ConsentEvent]: Every grant and withdrawal, in the order recorded.
        """
        return list(
            await self.db.scalars(
                select(ConsentEvent)
                .where(ConsentEvent.reviewer_id == reviewer_id)
                .order_by(
                    ConsentEvent.created_at, ConsentEvent.occurred_at, ConsentEvent.id
                )
            )
        )

    async def state(self, reviewer_id: str) -> dict[str, str]:
        """Return each scope's current state: ``granted``, ``withdrawn``, or ``none``.

        Args:
            reviewer_id (str): Whose consent to read.

        Returns:
            dict[str, str]: One entry per scope; ``none`` means never asked.
        """
        current = dict.fromkeys(CONSENT_SCOPES, "none")
        for event in await self.events(reviewer_id):
            current[event.scope] = event.event_type
        return current

    async def require_granted(self, reviewer_id: str, scope: str) -> None:
        """Refuse unless ``scope`` is currently granted for the reviewer.

        Refuses with HTTP 403 if the scope was never granted or was withdrawn.

        Args:
            reviewer_id (str): Whose consent to check.
            scope (str): The consent scope.
        """
        # #CRITICAL: security: sensitive self-reported context may be recorded
        # only while consent for it stands. A withdrawal later in the log must
        # win over an earlier grant, so this reads the latest event, never "any
        # grant exists". #VERIFY: tests/unit/test_services/test_consent.py
        # covers grant, withdraw, and re-grant.
        if (await self.state(reviewer_id)).get(scope) != "granted":
            reject(f"Consent for {scope} has not been granted", 403)

    async def record(
        self,
        reviewer_id: str,
        scope: str,
        event_type: str,
        username: str,
        *,
        enrollment_id: str | None = None,
        note: str | None = None,
    ) -> ConsentEvent:
        """Append a grant or withdrawal, stamped with the shown text.

        Refuses with HTTP 409 for a grant against draft wording, or for a change
        that would not change the scope's current state.

        Args:
            reviewer_id (str): Whose consent this is.
            scope (str): What is being consented to.
            event_type (str): ``granted`` or ``withdrawn``.
            username (str): The verified user recording it.
            enrollment_id (str | None): Optional enrollment the consent was given in.
            note (str | None): Free text, for example how a withdrawal was made.

        Returns:
            ConsentEvent: The stored event.
        """
        text = load_consent_text()
        current = (await self.state(reviewer_id)).get(scope, "none")
        if event_type == "granted":
            if not text.approved:
                reject(
                    "The consent text has not been approved; consent cannot be recorded"
                )
            if current == "granted":
                reject(f"Consent for {scope} is already granted")
        elif current != "granted":
            reject(
                f"Consent for {scope} is not granted, so there is nothing to withdraw"
            )
        event = ConsentEvent(
            reviewer_id=reviewer_id,
            enrollment_id=enrollment_id,
            event_type=event_type,
            scope=scope,
            consent_text_version=text.version,
            consent_text_sha256=text.sha256,
            occurred_at=now_naive_utc(),
            recorded_by=username,
            note=note,
        )
        self.db.add(event)
        await self.db.flush()
        return event
