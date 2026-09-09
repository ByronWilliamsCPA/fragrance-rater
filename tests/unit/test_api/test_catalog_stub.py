"""Tests for the root-mounted sample catalog kept for the Postman contract suite."""

import pytest


@pytest.mark.asyncio
class TestCatalogStub:
    """Contract checks mirroring docs/api/postman-collection.json."""

    async def test_list_returns_items_and_total(self, test_app):
        """GET /fragrances returns an items array with a matching total."""
        response = await test_app.get("/fragrances")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["items"], list)
        assert body["total"] == len(body["items"]) == 3
        assert {"id", "name", "brand"} <= body["items"][0].keys()

    async def test_get_by_id(self, test_app):
        """GET /fragrances/1 returns the entry with integer id 1."""
        response = await test_app.get("/fragrances/1")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 1
        assert body["name"] == "Aventus"
        assert body["brand"] == "Creed"

    async def test_unknown_id_returns_404_with_detail(self, test_app):
        """GET /fragrances/99999 is a 404 with an error detail."""
        response = await test_app.get("/fragrances/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Fragrance 99999 not found"

    async def test_non_integer_id_returns_422(self, test_app):
        """A non-integer path parameter fails validation."""
        response = await test_app.get("/fragrances/not-an-int")
        assert response.status_code == 422
