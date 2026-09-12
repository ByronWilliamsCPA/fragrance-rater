"""Tests for FragellaLookupService: recording attempts, not adopting data."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from fragrance_rater.models.calibration import FragellaLookup
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.services.fragella_client import FragellaError, FragellaResult
from fragrance_rater.services.fragella_lookup_service import FragellaLookupService
from fragrance_rater.utils.timestamps import now_naive_utc


def _mock_client(**overrides) -> MagicMock:
    client = MagicMock()
    client.search = AsyncMock(**overrides)
    return client


async def _make_fragrance(async_session, **overrides) -> Fragrance:
    fragrance = Fragrance(
        name=overrides.pop("name", "Aimez-Moi"),
        brand=overrides.pop("brand", "Caron"),
        concentration="EDT",
        gender_target="Unisex",
        primary_family="floral",
        subfamily="powdery",
        data_source="manual",
        **overrides,
    )
    async_session.add(fragrance)
    await async_session.flush()
    return fragrance


@pytest.mark.asyncio
class TestRunLookup:
    async def test_records_a_successful_lookup(self, async_session):
        fragrance = await _make_fragrance(async_session)
        result = FragellaResult(id="x", name="Aimez-Moi", brand="Caron", year=1996)
        service = FragellaLookupService(
            async_session, client=_mock_client(return_value=[result])
        )

        lookup = await service.run_lookup(fragrance, requested_by="manager")

        assert lookup.status == "success"
        assert lookup.query == "Caron Aimez-Moi"
        assert lookup.requested_by == "manager"
        assert lookup.error_message is None
        assert lookup.results == [
            {
                "id": "x",
                "name": "Aimez-Moi",
                "brand": "Caron",
                "year": 1996,
                "oil_type": None,
                "gender": None,
                "general_notes": [],
                "top_notes": [],
                "middle_notes": [],
                "base_notes": [],
                "confidence": None,
            }
        ]

    async def test_records_a_failed_lookup_without_raising(self, async_session):
        """A quota-exhausted or bad-key failure must be recorded, not
        raised past the caller - the manager needs to see *that* a check
        was attempted and why it failed."""
        fragrance = await _make_fragrance(async_session)
        service = FragellaLookupService(
            async_session,
            client=_mock_client(side_effect=FragellaError("quota exhausted")),
        )

        lookup = await service.run_lookup(fragrance, requested_by="manager")

        assert lookup.status == "error"
        assert lookup.error_message == "quota exhausted"
        assert lookup.results == []

    async def test_uses_an_explicit_query_override(self, async_session):
        fragrance = await _make_fragrance(async_session)
        client = _mock_client(return_value=[])
        service = FragellaLookupService(async_session, client=client)

        await service.run_lookup(
            fragrance, requested_by="manager", query="custom query"
        )

        client.search.assert_awaited_once_with("custom query")


@pytest.mark.asyncio
class TestLatestByFragrance:
    async def test_returns_empty_mapping_for_empty_input(self, async_session):
        service = FragellaLookupService(async_session, client=_mock_client())
        assert await service.latest_by_fragrance([]) == {}

    async def test_returns_only_the_most_recent_lookup_per_fragrance(
        self, async_session
    ):
        fragrance = await _make_fragrance(async_session)
        # Explicit, well-separated timestamps: two lookups created back to
        # back could otherwise land in the same instant, making "most
        # recent" nondeterministic rather than a real regression check.
        older = FragellaLookup(
            fragrance_id=fragrance.id,
            query="old query",
            requested_by="manager",
            status="success",
            results=[],
            queried_at=now_naive_utc() - timedelta(hours=1),
        )
        async_session.add(older)
        await async_session.flush()
        newer = FragellaLookup(
            fragrance_id=fragrance.id,
            query="new query",
            requested_by="manager",
            status="success",
            results=[],
            queried_at=now_naive_utc(),
        )
        async_session.add(newer)
        await async_session.flush()

        service = FragellaLookupService(async_session, client=_mock_client())
        latest = await service.latest_by_fragrance([fragrance.id])

        assert set(latest) == {fragrance.id}
        assert latest[fragrance.id].id == newer.id

    async def test_fragrances_never_looked_up_are_absent_from_the_mapping(
        self, async_session
    ):
        fragrance = await _make_fragrance(async_session)
        service = FragellaLookupService(async_session, client=_mock_client())

        latest = await service.latest_by_fragrance([fragrance.id])

        assert latest == {}
