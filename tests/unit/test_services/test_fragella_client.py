"""Tests for the Fragella reference-lookup client.

Fixture provenance: response shapes below are modeled on Fragella's own
published API documentation (https://api.fragella.com/docs.html, read
2026-09-13) - not a live authenticated response, since no API key was
available in this environment. See fragella_client.py's module docstring
for why this integration is explicitly flagged as documentation-derived
rather than live-verified, unlike ParfumoScraper's fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fragrance_rater.services.fragella_client import (
    FragellaClient,
    FragellaError,
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
        with pytest.raises(FragellaError, match="not configured"):
            await client.search("Aimez-Moi")

    async def test_requires_at_least_three_characters(self):
        client = _client()
        with pytest.raises(FragellaError, match="at least 3 characters"):
            await client.search("Ai")

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
            pytest.raises(FragellaError, match="quota exhausted"),
        ):
            await client.search("Aimez-Moi Caron")

    @pytest.mark.parametrize("status_code", [401, 403])
    async def test_raises_on_auth_failure(self, status_code):
        client = _client()
        mock_response = _mock_response(status_code, {})
        with (
            patch.object(
                httpx.AsyncClient, "get", AsyncMock(return_value=mock_response)
            ),
            pytest.raises(FragellaError, match="rejected the API key"),
        ):
            await client.search("Aimez-Moi Caron")

    async def test_raises_on_request_failure(self):
        client = _client()
        with (
            patch.object(
                httpx.AsyncClient,
                "get",
                AsyncMock(side_effect=httpx.ConnectTimeout("timed out")),
            ),
            pytest.raises(FragellaError, match="request failed"),
        ):
            await client.search("Aimez-Moi Caron")

    async def test_clamps_limit_to_documented_maximum(self):
        client = _client()
        mock_response = _mock_response(200, [])
        get_mock = AsyncMock(return_value=mock_response)
        with patch.object(httpx.AsyncClient, "get", get_mock):
            await client.search("Aimez-Moi Caron", limit=999)

        assert get_mock.call_args.kwargs["params"]["limit"] == FragellaClient.MAX_LIMIT


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
        with pytest.raises(FragellaError, match="not configured"):
            await client.usage()
