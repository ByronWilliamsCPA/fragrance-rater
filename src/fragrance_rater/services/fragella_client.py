"""Fragella API client - a quota-capped reference lookup, not a data source.

ADR-002 considered Fragella as a primary/API-first source and rejected it
(20 requests/month free tier is far too little for routine enrichment) and
its 2026 amendment records that Fragella "was not adopted as the operational
enrichment dependency." This client does not change that: it exists only as
an operator-invoked, decision-support lookup for the same class of gap the
V3.1 baseline/holdout resolution hit by hand (see docs/planning/evidence/
baseline-v3.1-parfumo-source-resolution.md) - a same-name ambiguity Parfumo
alone did not resolve, or a concentration/year Parfumo did not publish.

# #ASSUME: external-resources: this client is built from Fragella's own
# published API documentation (https://api.fragella.com/docs.html, read
# 2026-09-13), not verified against a live authenticated response - no API
# key was available in this environment. Response field names/casing
# (`Name`, `Brand`, `Year`, `OilType`, `General Notes`, `Notes.Top/Middle/
# Base`, `Confidence`) and the unpaginated response envelope (a bare list
# vs. an object) are the documentation's best description, not something
# fetched and inspected directly - unlike ParfumoScraper, whose selectors
# were checked against real live pages. This mirrors the exact kind of gap
# that caused ParfumoScraper.search() to silently break against the live
# site (see its docstring): treat this integration as unverified until a
# real API key is used to confirm parsing against an actual response, and
# do not extend it further on the assumption the documented shape is
# already correct.
# #VERIFY: smoke-test search()/usage() against a live key before relying on
# this for a real gap-filling decision; add regression fixtures from that
# real response once one is available, the same way Parfumo's fixtures
# were built from verified live markup.

Nothing this client returns is written into the Fragrance catalog or a
SourceSnapshot automatically - adopting Fragella data as a stored source
would need its own reuse-rights review per ADR-002/ADR-006, which this
narrow, non-storing, human-in-the-loop use does not require.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import httpx

from fragrance_rater.core.config import settings


class FragellaErrorCode(Enum):
    """Distinguishes FragellaError's failure modes.

    Lets a caller react differently per failure mode (e.g. treat quota
    exhaustion as "try later" but a rejected key as "fix configuration")
    without substring-matching the exception's message text, which is
    for humans, not control flow.
    """

    NOT_CONFIGURED = "not_configured"
    INSECURE_BASE_URL = "insecure_base_url"
    QUERY_TOO_SHORT = "query_too_short"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTH_REJECTED = "auth_rejected"
    REQUEST_FAILED = "request_failed"
    RESPONSE_INVALID = "response_invalid"


class FragellaError(Exception):
    """Raised for a Fragella API failure the caller must react to.

    Distinct from returning an empty result list: an empty list means
    "the query legitimately matched nothing," while this means the
    lookup itself could not be completed (bad/missing key, quota
    exhausted, or a request/response failure) and the caller should
    not treat a resulting empty list as "no matches."

    # #ASSUME: data-integrity: `code` defaults to None, not a guessed
    # category, so an exception built without one (a test double
    # standing in for "some Fragella failure") is never mistaken for a
    # real, classified failure. Every raise site in this module passes
    # an explicit code.
    # #VERIFY: covered by a test asserting each raise site's `code`.

    Args:
        message (str): Human-readable failure description.
        code (FragellaErrorCode | None): Which failure mode this is, for
            callers that need to branch on it. None only if constructed
            without one (e.g. a test double).
    """

    def __init__(self, message: str, code: FragellaErrorCode | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class FragellaResult:
    """One `/fragrances` search result.

    Kept to the fields useful for disambiguation - not a full mirror of
    Fragella's response.
    """

    id: str
    name: str
    brand: str
    year: int | None = None
    oil_type: str | None = None
    gender: str | None = None
    general_notes: list[str] = field(default_factory=list)
    top_notes: list[str] = field(default_factory=list)
    middle_notes: list[str] = field(default_factory=list)
    base_notes: list[str] = field(default_factory=list)
    confidence: str | None = None


class FragellaClient:
    """Thin, quota-aware wrapper over the Fragella API.

    Args:
        api_key (str | None): Overrides ``settings.fragella_api_key`` (for
            tests); when None, the configured key is used.
        base_url (str | None): Overrides ``settings.fragella_base_url``.

    Attributes:
        MIN_SEARCH_LENGTH (int): Fragella's documented minimum query length.
        MAX_LIMIT (int): Fragella's documented maximum `limit` value.
    """

    MIN_SEARCH_LENGTH: int = 3
    MAX_LIMIT: int = 10

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.fragella_api_key
        self.base_url = (base_url or settings.fragella_base_url).rstrip("/")

    def _require_api_key(self) -> str:
        if not self.api_key:
            msg = "FRAGELLA_API_KEY is not configured"
            raise FragellaError(msg, code=FragellaErrorCode.NOT_CONFIGURED)
        # #CRITICAL: security: a configured or constructor-provided base_url
        # of any scheme would otherwise carry the x-api-key header in
        # cleartext over plain HTTP (CWE-319). Both callers of this method
        # (search, usage) send that header immediately afterward.
        # #VERIFY: covered by a test asserting an http:// base_url raises.
        if not self.base_url.startswith("https://"):
            msg = f"Fragella base URL must use HTTPS, got: {self.base_url!r}"
            raise FragellaError(msg, code=FragellaErrorCode.INSECURE_BASE_URL)
        return self.api_key

    async def search(self, query: str, limit: int = 5) -> list[FragellaResult]:
        """Search Fragella's fragrance database.

        # #ASSUME: external-resources: `limit` and `query` are validated
        # client-side against Fragella's documented constraints (>=3
        # chars, limit 1-10) before spending one of a very small monthly
        # quota on a request guaranteed to fail server-side.

        Args:
            query (str): Fragrance or brand name, at least 3 characters.
            limit (int): Maximum results (clamped to 1-10).

        Returns:
            list[FragellaResult]: Matches, most relevant first, per
                Fragella's own fuzzy-match ordering.

        Raises:
            FragellaError: No API key configured, the query is too
                short, the request/response failed, or the account's
                quota is exhausted (HTTP 429).
        """
        api_key = self._require_api_key()
        if len(query.strip()) < self.MIN_SEARCH_LENGTH:
            msg = f"query must be at least {self.MIN_SEARCH_LENGTH} characters"
            raise FragellaError(msg, code=FragellaErrorCode.QUERY_TOO_SHORT)
        clamped_limit = max(1, min(limit, self.MAX_LIMIT))

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/fragrances",
                    headers={"x-api-key": api_key},
                    params={"search": query, "limit": clamped_limit},
                )
        except httpx.RequestError as exc:
            msg = f"Fragella request failed: {exc}"
            raise FragellaError(msg, code=FragellaErrorCode.REQUEST_FAILED) from exc

        if response.status_code == 429:
            msg = "Fragella monthly quota exhausted (HTTP 429)"
            raise FragellaError(msg, code=FragellaErrorCode.QUOTA_EXHAUSTED)
        if response.status_code in (401, 403):
            msg = f"Fragella rejected the API key (HTTP {response.status_code})"
            raise FragellaError(msg, code=FragellaErrorCode.AUTH_REJECTED)
        if response.status_code != 200:
            msg = f"Fragella returned HTTP {response.status_code}"
            raise FragellaError(msg, code=FragellaErrorCode.RESPONSE_INVALID)

        try:
            body: object = response.json()
        except ValueError as exc:
            msg = "Fragella returned a non-JSON response"
            raise FragellaError(msg, code=FragellaErrorCode.RESPONSE_INVALID) from exc

        items = self._extract_search_items(body)
        return [
            parsed
            for item in items
            if isinstance(item, dict)
            and (parsed := self._parse_result(item)) is not None
        ]

    @staticmethod
    def _extract_search_items(body: object) -> list[object]:
        """Pull the result list out of a `/fragrances` response body.

        The documented response envelope differs when `?page=` is used
        (`{"data": [...], "pagination": {...}}`) versus the default,
        undocumented-in-detail unpaginated form; accept either a bare
        list or a `data` key rather than assuming one.

        Args:
            body (object): The parsed JSON response body.

        Returns:
            list[object]: The raw, not-yet-validated result items.

        Raises:
            FragellaError: `body` is not a list, and is either a dict
                with no `data` key at all (an error envelope, e.g.
                `{"error": "..."}` - `.get("data", [])` would default
                this to `[]` the same as a genuinely empty paginated
                result and mask the failure as a successful zero-match
                search) or `data` is present but not itself a list.
        """
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            if "data" not in body:
                msg = f"Fragella search response was an error envelope: {body!r}"
                raise FragellaError(msg, code=FragellaErrorCode.RESPONSE_INVALID)
            raw_items = body["data"]
            if isinstance(raw_items, list):
                return raw_items
        msg = "Fragella search response was not a list of fragrances"
        raise FragellaError(msg, code=FragellaErrorCode.RESPONSE_INVALID)

    async def usage(self) -> dict[str, object] | None:
        """Fetch the account's current monthly quota status.

        # #ASSUME: external-resources: whether calling this endpoint
        # itself counts against the 20/month quota is not stated in
        # Fragella's documentation. Call it deliberately (its own CLI
        # command), not automatically before every search() - if it does
        # count, doing so unconditionally would silently halve the
        # usable budget.

        Returns:
            dict[str, object] | None: The raw `/usage` response body
                (plan, billing_period, limit, usage), or None if the
                request/response failed.
        """
        api_key = self._require_api_key()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/usage", headers={"x-api-key": api_key}
                )
        except httpx.RequestError:
            return None
        if response.status_code != 200:
            return None
        try:
            body: object = response.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    @staticmethod
    def _parse_result(item: dict[str, object]) -> FragellaResult | None:
        """Parse one raw `/fragrances` item, skipping one with no name.

        Never raises: a single malformed item must not abort the whole
        search, matching ParfumoScraper's "degrade, don't crash" policy.
        """
        name = item.get("Name")
        if not isinstance(name, str) or not name.strip():
            return None
        raw_id = item.get("_id")
        raw_notes = item.get("Notes")
        notes: dict[str, object] = raw_notes if isinstance(raw_notes, dict) else {}

        def _str_list(value: object) -> list[str]:
            if not isinstance(value, list):
                return []
            return [entry for entry in value if isinstance(entry, str)]

        def _optional_str(value: object) -> str | None:
            return value if isinstance(value, str) and value.strip() else None

        year_raw = item.get("Year")
        year = year_raw if isinstance(year_raw, int) else None

        return FragellaResult(
            id=str(raw_id) if raw_id is not None else name,
            name=name,
            brand=_optional_str(item.get("Brand")) or "",
            year=year,
            oil_type=_optional_str(item.get("OilType")),
            gender=_optional_str(item.get("Gender")),
            general_notes=_str_list(item.get("General Notes")),
            top_notes=_str_list(notes.get("Top")),
            middle_notes=_str_list(notes.get("Middle")),
            base_notes=_str_list(notes.get("Base")),
            confidence=_optional_str(item.get("Confidence")),
        )
