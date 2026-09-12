"""Record and retrieve Fragella reference-lookup attempts.

A thin persistence layer over `FragellaClient` so a manager can see which
fragrances in a program still have not been checked ("fill holes") without
re-spending one of the account's 20 monthly requests just to find out, and
so a completed lookup's results stay visible after the page reloads.

See `fragrance_rater.services.fragella_client` and ADR-002's 2026-09-13
amendment for why this is explicitly not adopted source evidence: nothing
here is ever written into `Fragrance` columns or a membership's evidence
fields automatically.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from sqlalchemy import select

from fragrance_rater.models.calibration import FragellaLookup
from fragrance_rater.services.fragella_client import FragellaClient, FragellaError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.models.fragrance import Fragrance

logger = logging.getLogger(__name__)


class FragellaLookupService:
    """Runs a Fragella lookup for one fragrance and records the attempt."""

    def __init__(self, db: AsyncSession, client: FragellaClient | None = None) -> None:
        self.db = db
        self.client = client or FragellaClient()

    async def run_lookup(
        self, fragrance: Fragrance, requested_by: str, query: str | None = None
    ) -> FragellaLookup:
        """Search Fragella for `fragrance` and persist the attempt.

        # #ASSUME: data-integrity: a failed lookup (bad key, quota
        # exhausted, request error) is still recorded, with `status`
        # "error" and the failure message - a manager needs to see *that*
        # a check was attempted and why it did not produce results, not
        # just silently retry against a nearly-exhausted monthly quota.

        Args:
            fragrance (Fragrance): The catalog version to look up.
            requested_by (str): The manager's identity (audit trail).
            query (str | None): Search text; defaults to
                "`brand` `name`" when omitted.

        Returns:
            FragellaLookup: The persisted attempt, success or error.
        """
        search_query = query or f"{fragrance.brand} {fragrance.name}"
        # #CRITICAL: data-integrity: the API route enforces max_length=500
        # on a caller-supplied `query`, but this brand+name fallback is
        # not bounded - `name`/`brand` are each String(255), so a
        # maximally long fragrance could produce a fallback over
        # FragellaLookup.query's own String(500) column, spending a
        # Fragella request and then failing at flush() with nothing
        # recorded.
        # #VERIFY: covered by a test with over-255-char brand/name.
        search_query = search_query[:500]
        record = FragellaLookup(
            fragrance_id=fragrance.id,
            query=search_query,
            requested_by=requested_by,
            status="error",
            results=[],
        )
        try:
            results = await self.client.search(search_query)
        except FragellaError as exc:
            record.error_message = str(exc)
        except Exception as exc:
            # A bug in FragellaClient (not a documented FragellaError
            # failure mode) must not skip persisting the attempt - the
            # "always recorded" contract above applies to any failure,
            # not only the ones FragellaClient itself anticipates.
            logger.exception(
                "Unexpected error during Fragella lookup for fragrance %s",
                fragrance.id,
            )
            record.error_message = f"Unexpected error: {exc}"
        else:
            record.status = "success"
            record.results = [asdict(result) for result in results]
        self.db.add(record)
        await self.db.flush()
        return record

    async def latest_by_fragrance(
        self, fragrance_ids: list[str]
    ) -> dict[str, FragellaLookup]:
        """Return each fragrance's most recent lookup, keyed by fragrance_id.

        Args:
            fragrance_ids (list[str]): Fragrances to look up (deduplicated
                internally; an empty list returns an empty mapping without
                a query).

        Returns:
            dict[str, FragellaLookup]: Only fragrances with at least one
                recorded lookup are present as keys.
        """
        unique_ids = list(dict.fromkeys(fragrance_ids))
        if not unique_ids:
            return {}
        rows = list(
            await self.db.scalars(
                select(FragellaLookup)
                .where(FragellaLookup.fragrance_id.in_(unique_ids))
                .order_by(FragellaLookup.queried_at.desc())
            )
        )
        latest: dict[str, FragellaLookup] = {}
        for row in rows:
            latest.setdefault(row.fragrance_id, row)
        return latest
