"""Tests for the Fragella reference-lookup client.

Fixture provenance: `SAMPLE_SEARCH_RESPONSE` below is modeled on Fragella's
own published API documentation (https://api.fragella.com/docs.html, read
2026-09-12); it exercises the paginated-envelope and error-envelope paths,
which were never live-verified either way. `LIVE_VERIFIED_SEARCH_RESPONSE`
was transcribed field-shape-for-field-shape from a real, live authenticated
`/fragrances?search=Aventus` call made 2026-09-12 (see fragella_client.py's
module docstring) and exists specifically to catch the two places the
documented shape and the live shape diverge: `Year` as a numeric string
rather than an int, and `Notes.Top/Middle/Base` entries as `{"name": ...,
"imageUrl": ...}` objects rather than plain strings.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fragrance_rater.services.fragella_client import (
    FragellaClient,
    FragellaError,
    FragellaErrorCode,
    FragellaResult,
)

SAMPLE_SEARCH_RESPONSE = [
    {
        "_id": "aimez-moi-1996",
        "Name": "Aimez-Moi",
        "Brand": "Caron",
        "Year": 1996,
        "OilType": "Eau de Toilette",
        "Gender": "female",
        "General Notes": ["Violet", "Iris", "Musk"],
        "Notes": {
            "Top": ["Violet", "Star Anise"],
            "Middle": ["Iris", "Peach"],
            "Base": ["Musk", "Vanilla"],
        },
        "Confidence": "medium",
    },
    {
        "_id": "aimez-moi-comme-je-suis",
        "Name": "Aimez-Moi Comme Je Suis",
        "Brand": "Caron",
        "Year": 2020,
        "OilType": "Eau de Parfum",
        "Gender": "male",
        "General Notes": ["Ginger", "Tobacco"],
        "Notes": {"Top": ["Ginger"], "Middle": ["Hazelnut"], "Base": ["Tobacco"]},
        "Confidence": "low",
    },
]


# A single, real Aventus search result, field-shape-for-field-shape as
# returned by a live authenticated call. Trimmed to the fields
# FragellaResult captures; values are the vendor's own catalog data for a
# well-known, publicly documented fragrance, not anything sensitive.
LIVE_VERIFIED_SEARCH_RESPONSE = [
    {
        "_id": "aventus-creed",
        "Name": "Aventus",
        "Brand": "Creed",
        "Year": "2018",
        "OilType": "Eau de Parfum",
        "Gender": "male",
        "General Notes": ["Pineapple", "Birch", "Musk"],
        "Notes": {
            "Top": [
                {
                    "name": "Bergamot",
                    "imageUrl": "https://cdn.fragella.com/note_images/Bergamot.png",
                },
                {
                    "name": "Blackcurrant",
                    "imageUrl": "https://cdn.fragella.com/note_images/Blackcurrant.png",
                },
            ],
            "Middle": [
                {
                    "name": "Birch",
                    "imageUrl": "https://cdn.fragella.com/note_images/Birch.png",
                },
            ],
            "Base": [
                {
                    "name": "Musk",
                    "imageUrl": "https://cdn.fragella.com/note_images/Musk.png",
                },
            ],
        },
        "Confidence": "high",
    },
]


def _client(api_key: str | None = "test-key") -> FragellaClient:
    return FragellaClient(api_key=api_key, base_url="https://api.fragella.test/api/v1")


def _mock_response(status_code: int, json_body: object) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body
    return response


@pytest.mark.asyncio
class TestFragellaClientSearch:
    async def test_requires_an_api_key(self):
        client = _client(api_key="")
        with pytest.raises(FragellaError, match="not configured") as exc_info:
            await client.search("Aimez-Moi")
        assert exc_info.value.code is FragellaErrorCode.NOT_CONFIGURED

    async def test_requires_at_least_three_characters(self):
        client = _client()
        with pytest.raises(FragellaError, match="at least 3 characters") as exc_info:
            await client.search("Ai")
        assert exc_info.value.code is FragellaErrorCode.QUERY_TOO_SHORT

    async def test_rejects_a_non_https_base_url(self):
        """The x-api-key header must never go out over plaintext HTTP
        (CWE-319), regardless of a misconfigured or constructor-provided
        base_url."""
        client = FragellaClient(api_key="test-key", base_url="http://api.fragella.test")
        with pytest.raises(FragellaError, match="must use HTTPS") as exc_info:
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.INSECURE_BASE_URL

    async def test_parses_a_bare_list_response(self):
        client = _client()
        mock_response = _mock_response(200, SAMPLE_SEARCH_RESPONSE)
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            results = await client.search("Aimez-Moi Caron")

        assert len(results) == 2
        first, second = results
        assert first == FragellaResult(
            id="aimez-moi-1996",
            name="Aimez-Moi",
            brand="Caron",
            year=1996,
            oil_type="Eau de Toilette",
            gender="female",
            general_notes=["Violet", "Iris", "Musk"],
            top_notes=["Violet", "Star Anise"],
            middle_notes=["Iris", "Peach"],
            base_notes=["Musk", "Vanilla"],
            confidence="medium",
        )
        assert second.name == "Aimez-Moi Comme Je Suis"
        assert second.year == 2020

    async def test_parses_a_paginated_data_envelope(self):
        """The documented `?page=` response shape wraps results in `data`."""
        client = _client()
        mock_response = _mock_response(
            200,
            {
                "data": SAMPLE_SEARCH_RESPONSE[:1],
                "pagination": {"page": 1, "limit": 5, "count": 1, "has_more": False},
            },
        )
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            results = await client.search("Aimez-Moi Caron")

        assert len(results) == 1
        assert results[0].name == "Aimez-Moi"

    async def test_parses_a_genuinely_empty_paginated_envelope(self):
        """A dict that carries `data` as an empty list is a real
        zero-match result, distinct from a dict missing `data` entirely
        (see test_raises_on_a_dict_shaped_error_envelope below)."""
        client = _client()
        mock_response = _mock_response(
            200,
            {"data": [], "pagination": {"page": 1, "limit": 5, "count": 0}},
        )
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            results = await client.search("Aimez-Moi Caron")
        assert results == []

    async def test_raises_on_a_dict_shaped_error_envelope(self):
        """A 200 response whose body is a dict with no `data` key at all
        (e.g. `{"error": "..."}`) must raise, not be treated as a
        genuinely empty successful search -
        `.get("data", [])` would default both shapes to `[]` alike and
        mask the real upstream failure."""
        client = _client()
        mock_response = _mock_response(200, {"error": "internal server error"})
        with (
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
            ),
            pytest.raises(FragellaError, match="error envelope") as exc_info,
        ):
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.RESPONSE_INVALID

    async def test_skips_items_with_no_name_rather_than_crashing(self):
        client = _client()
        mock_response = _mock_response(200, [{"Brand": "Caron", "Year": 1996}])
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            results = await client.search("Aimez-Moi Caron")
        assert results == []

    async def test_raises_on_quota_exhausted(self):
        client = _client()
        mock_response = _mock_response(429, {})
        with (
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
            ),
            pytest.raises(FragellaError, match="quota exhausted") as exc_info,
        ):
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.QUOTA_EXHAUSTED

    @pytest.mark.parametrize("status_code", [401, 403])
    async def test_raises_on_auth_failure(self, status_code):
        client = _client()
        mock_response = _mock_response(status_code, {})
        with (
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
            ),
            pytest.raises(FragellaError, match="rejected the API key") as exc_info,
        ):
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.AUTH_REJECTED

    async def test_raises_on_request_failure(self):
        client = _client()
        with (
            patch.object(
                httpx.AsyncClient,
                "get",
                AsyncMock(side_effect=httpx.ConnectTimeout("timed out")),
            ),
            pytest.raises(FragellaError, match="request failed") as exc_info,
        ):
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.REQUEST_FAILED

    async def test_raises_on_a_generic_error_status(self):
        """The catch-all non-200/429/401/403 branch (e.g. a 500)."""
        client = _client()
        mock_response = _mock_response(500, {})
        with (
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
            ),
            pytest.raises(FragellaError, match="HTTP 500") as exc_info,
        ):
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.RESPONSE_INVALID

    async def test_raises_on_a_non_json_response_body(self):
        """A 200 whose body fails to parse as JSON at all - distinct
        from a well-formed JSON body of the wrong shape (see the
        dict-shaped-error-envelope and not-a-list tests above/below)."""
        client = _client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("not JSON")
        with (
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
            ),
            pytest.raises(FragellaError, match="non-JSON response") as exc_info,
        ):
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.RESPONSE_INVALID

    async def test_raises_when_the_response_is_not_a_list_or_dict(self):
        """A well-formed JSON body that is neither a bare list nor a
        dict at all (e.g. a bare string or number) - the final fallback
        in `_extract_search_items`, distinct from the dict-shaped
        error-envelope case above."""
        client = _client()
        mock_response = _mock_response(200, "unexpected scalar body")
        with (
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
            ),
            pytest.raises(FragellaError, match="not a list of fragrances") as exc_info,
        ):
            await client.search("Aimez-Moi Caron")
        assert exc_info.value.code is FragellaErrorCode.RESPONSE_INVALID

    async def test_clamps_limit_to_documented_maximum(self):
        client = _client()
        mock_response = _mock_response(200, [])
        get_mock = AsyncMock(return_value=mock_response)
        with patch.object(httpx.AsyncClient, "get", get_mock):
            await client.search("Aimez-Moi Caron", limit=999)

        assert get_mock.call_args.kwargs["params"]["limit"] == FragellaClient.MAX_LIMIT

    async def test_parses_the_live_verified_response_shape(self):
        """Regression test for the two real parsing bugs found 2026-09-12:
        `Year` as a numeric string and `Notes.*` entries as objects (see
        LIVE_VERIFIED_SEARCH_RESPONSE's docstring)."""
        client = _client()
        mock_response = _mock_response(200, LIVE_VERIFIED_SEARCH_RESPONSE)
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            results = await client.search("Aventus")

        assert len(results) == 1
        assert results[0] == FragellaResult(
            id="aventus-creed",
            name="Aventus",
            brand="Creed",
            year=2018,
            oil_type="Eau de Parfum",
            gender="male",
            general_notes=["Pineapple", "Birch", "Musk"],
            top_notes=["Bergamot", "Blackcurrant"],
            middle_notes=["Birch"],
            base_notes=["Musk"],
            confidence="high",
        )

    @pytest.mark.parametrize(
        ("year_raw", "expected"),
        [
            (2018, 2018),  # documented int shape, still accepted
            ("2018", 2018),  # live-observed numeric-string shape
            (True, None),  # bool is an int subclass; must not become 1
            ("unknown", None),  # non-digit string, never guess
            ("2018-2020", None),  # a range, never guess
            (None, None),
        ],
    )
    async def test_year_coercion(self, year_raw, expected):
        client = _client()
        item = {**LIVE_VERIFIED_SEARCH_RESPONSE[0], "Year": year_raw}
        mock_response = _mock_response(200, [item])
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            results = await client.search("Aventus")
        assert results[0].year == expected

    async def test_notes_accept_a_mix_of_string_and_object_entries(self):
        """A note list could plausibly mix shapes across a transition
        period; both forms in the same list must parse."""
        client = _client()
        item = {
            **LIVE_VERIFIED_SEARCH_RESPONSE[0],
            "Notes": {
                "Top": ["Bergamot", {"name": "Blackcurrant", "imageUrl": "x"}],
                "Middle": [],
                "Base": [{"name": "Musk"}, {"imageUrl": "no-name-key"}],
            },
        }
        mock_response = _mock_response(200, [item])
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            results = await client.search("Aventus")
        assert results[0].top_notes == ["Bergamot", "Blackcurrant"]
        assert results[0].middle_notes == []
        assert results[0].base_notes == ["Musk"]


@pytest.mark.asyncio
class TestFragellaClientUsage:
    async def test_returns_the_usage_body_on_success(self):
        client = _client()
        body = {
            "plan": "free",
            "usage": {"requests_made": 3, "requests_remaining": 17},
        }
        mock_response = _mock_response(200, body)
        with patch.object(
            httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
        ):
            result = await client.usage()
        assert result == body

    async def test_returns_none_on_failure_rather_than_raising(self):
        """usage() is a status-check helper, not on the critical path a
        lookup depends on - degrade quietly like ParfumoScraper's other
        best-effort reads."""
        client = _client()
        with patch.object(
            httpx.AsyncClient,
            "get",
            AsyncMock(side_effect=httpx.ConnectTimeout("timed out")),
        ):
            result = await client.usage()
        assert result is None

    async def test_requires_an_api_key(self):
        client = _client(api_key="")
        with pytest.raises(FragellaError, match="not configured") as exc_info:
            await client.usage()
        assert exc_info.value.code is FragellaErrorCode.NOT_CONFIGURED
