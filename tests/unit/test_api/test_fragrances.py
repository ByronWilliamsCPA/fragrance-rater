"""Tests for fragrance API endpoints."""

import pytest

from fragrance_rater.core.config import settings

API_PREFIX = "/api/v1"


@pytest.mark.asyncio
class TestFragranceAPI:
    """Tests for fragrance API endpoints."""

    async def test_list_fragrances_empty(self, test_app):
        """Test listing fragrances when empty."""
        response = await test_app.get(f"{API_PREFIX}/fragrances")
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_fragrance(self, test_app):
        """Test creating a fragrance."""
        response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Aventus",
                "brand": "Creed",
                "concentration": "EDP",
                "gender_target": "Masculine",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Aventus"
        assert data["brand"] == "Creed"
        assert data["concentration"] == "EDP"
        assert "id" in data

    async def test_create_fragrance_with_notes(self, test_app):
        """Test creating a fragrance with notes."""
        response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Fragrance With Notes",
                "brand": "Test Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "fresh",
                "subfamily": "citrus",
                "notes": [
                    {
                        "note_name": "Bergamot",
                        "note_category": "citrus",
                        "position": "top",
                    },
                    {
                        "note_name": "Rose",
                        "note_category": "floral",
                        "position": "heart",
                    },
                    {"note_name": "Musk", "note_category": "musk", "position": "base"},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["notes"]) == 3

    async def test_create_fragrance_with_accords(self, test_app):
        """Test creating a fragrance with accords."""
        response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Fragrance With Accords",
                "brand": "Test Brand",
                "concentration": "EDT",
                "gender_target": "Feminine",
                "primary_family": "floral",
                "subfamily": "rose",
                "accords": [
                    {"accord_type": "floral", "intensity": 0.8},
                    {"accord_type": "powdery", "intensity": 0.5},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["accords"]) == 2

    async def test_get_fragrance_by_id(self, test_app):
        """Test getting a fragrance by ID."""
        # Create fragrance first
        create_response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Get Test",
                "brand": "Test Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "amber",
            },
        )
        fragrance_id = create_response.json()["id"]

        # Get the fragrance
        response = await test_app.get(f"{API_PREFIX}/fragrances/{fragrance_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Test"
        assert data["id"] == fragrance_id

    async def test_get_fragrance_not_found(self, test_app):
        """Test getting a non-existent fragrance returns 404."""
        response = await test_app.get(f"{API_PREFIX}/fragrances/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert "FRAGRANCE_NOT_FOUND" in str(data)

    async def test_search_fragrances_by_name(self, test_app):
        """Test searching fragrances by name."""
        # Create some fragrances
        await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Aventus",
                "brand": "Creed",
                "concentration": "EDP",
                "gender_target": "Masculine",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Sauvage",
                "brand": "Dior",
                "concentration": "EDT",
                "gender_target": "Masculine",
                "primary_family": "fresh",
                "subfamily": "aromatic",
            },
        )

        # Search by name
        response = await test_app.get(f"{API_PREFIX}/fragrances?q=Aventus")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Aventus"

    async def test_search_fragrances_by_brand(self, test_app):
        """Test filtering fragrances by brand."""
        # Create fragrances with same brand
        for name in ["Fragrance 1", "Fragrance 2"]:
            await test_app.post(
                f"{API_PREFIX}/fragrances",
                json={
                    "name": name,
                    "brand": "Test Brand",
                    "concentration": "EDP",
                    "gender_target": "Unisex",
                    "primary_family": "woody",
                    "subfamily": "aromatic",
                },
            )

        # Create fragrance with different brand
        await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Other Fragrance",
                "brand": "Other Brand",
                "concentration": "EDT",
                "gender_target": "Unisex",
                "primary_family": "fresh",
                "subfamily": "citrus",
            },
        )

        # Filter by brand
        response = await test_app.get(f"{API_PREFIX}/fragrances?brand=Test%20Brand")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(f["brand"] == "Test Brand" for f in data)

    async def test_search_fragrances_with_limit(self, test_app):
        """Test search respects limit parameter."""
        # Create multiple fragrances
        for i in range(5):
            await test_app.post(
                f"{API_PREFIX}/fragrances",
                json={
                    "name": f"Limit Test {i}",
                    "brand": "Brand",
                    "concentration": "EDP",
                    "gender_target": "Unisex",
                    "primary_family": "woody",
                    "subfamily": "aromatic",
                },
            )

        # Get with limit
        response = await test_app.get(f"{API_PREFIX}/fragrances?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_search_fragrances_rejects_unknown_gender_target(self, test_app):
        """An unknown gender_target is a 422 validation error, not a 500."""
        response = await test_app.get(f"{API_PREFIX}/fragrances?gender_target=bogus")
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail[0]["loc"] == ["query", "gender_target"]

    async def test_update_fragrance(self, test_app):
        """Test updating a fragrance."""
        # Create fragrance first
        create_response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Original Name",
                "brand": "Original Brand",
                "concentration": "EDT",
                "gender_target": "Masculine",
                "primary_family": "fresh",
                "subfamily": "citrus",
            },
        )
        fragrance_id = create_response.json()["id"]

        # Update the fragrance
        response = await test_app.patch(
            f"{API_PREFIX}/fragrances/{fragrance_id}",
            json={
                "name": "Updated Name",
                "concentration": "EDP",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["concentration"] == "EDP"
        assert data["brand"] == "Original Brand"  # Unchanged

    async def test_update_fragrance_not_found(self, test_app):
        """Test updating a non-existent fragrance returns 404."""
        response = await test_app.patch(
            f"{API_PREFIX}/fragrances/nonexistent-id",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    async def test_delete_fragrance(self, test_app):
        """Test deleting a fragrance."""
        # Create fragrance first
        create_response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Delete Me",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        fragrance_id = create_response.json()["id"]

        # Delete the fragrance
        response = await test_app.delete(f"{API_PREFIX}/fragrances/{fragrance_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = await test_app.get(f"{API_PREFIX}/fragrances/{fragrance_id}")
        assert get_response.status_code == 404

    async def test_delete_fragrance_not_found(self, test_app):
        """Test deleting a non-existent fragrance returns 404."""
        response = await test_app.delete(f"{API_PREFIX}/fragrances/nonexistent-id")
        assert response.status_code == 404

    async def test_create_duplicate_name_brand_returns_409(self, test_app):
        """Major finding 8: a second (name, brand) pair is rejected, not a 500."""
        payload = {
            "name": "Duplicate Scent",
            "brand": "Duplicate Brand",
            "concentration": "EDP",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        }
        first = await test_app.post(f"{API_PREFIX}/fragrances", json=payload)
        assert first.status_code == 201

        second = await test_app.post(f"{API_PREFIX}/fragrances", json=payload)
        assert second.status_code == 409
        assert second.json()["detail"]["error"] == "FRAGRANCE_EXISTS"

        # The session must still be usable after the rollback.
        listing = await test_app.get(f"{API_PREFIX}/fragrances?q=Duplicate Scent")
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    async def test_update_fragrance_rename_collision_returns_409(self, test_app):
        """Important finding: renaming a fragrance into an existing (name,
        brand) pair is rejected with 409, not an unhandled 500.
        """
        first = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "First Scent",
                "brand": "Shared Brand",
                "concentration": "EDT",
                "gender_target": "Masculine",
                "primary_family": "fresh",
                "subfamily": "citrus",
            },
        )
        assert first.status_code == 201

        second = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Second Scent",
                "brand": "Shared Brand",
                "concentration": "EDT",
                "gender_target": "Masculine",
                "primary_family": "fresh",
                "subfamily": "citrus",
            },
        )
        assert second.status_code == 201
        second_id = second.json()["id"]

        response = await test_app.patch(
            f"{API_PREFIX}/fragrances/{second_id}",
            json={"name": "First Scent"},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["error"] == "FRAGRANCE_EXISTS"

        # The session must still be usable after the rollback, and the
        # rename must not have been applied.
        unchanged = await test_app.get(f"{API_PREFIX}/fragrances/{second_id}")
        assert unchanged.status_code == 200
        assert unchanged.json()["name"] == "Second Scent"


@pytest.mark.asyncio
class TestFragranceAuthentikRequired:
    """Important finding: of the ~9 mutating routes gated by
    ``Depends(get_current_identity)``, only ``create_reviewer`` (see
    ``TestReviewerAuthentikRequired`` in test_reviewers.py) had a test
    actually confirming the dependency is enforced. This class adds that
    coverage for all three fragrances mutating routes.
    """

    async def _create_fragrance(self, test_app, name: str) -> str:
        """Create a fragrance via the API (auth disabled) and return its id."""
        response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": name,
                "brand": "Auth Test Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        assert response.status_code == 201
        return response.json()["id"]

    async def test_create_fragrance_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required
        is True.
        """
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Should Fail Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_create_fragrance_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the mutation through."""
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Should Succeed Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
            headers={"X-Authentik-Username": "byron"},
        )
        assert response.status_code == 201

    async def test_update_fragrance_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required
        is True.
        """
        fragrance_id = await self._create_fragrance(test_app, "Auth Patch Fragrance")
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.patch(
            f"{API_PREFIX}/fragrances/{fragrance_id}",
            json={"name": "Renamed"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_update_fragrance_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the mutation through."""
        fragrance_id = await self._create_fragrance(test_app, "Auth Patch OK Fragrance")
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.patch(
            f"{API_PREFIX}/fragrances/{fragrance_id}",
            json={"name": "Renamed OK"},
            headers={"X-Authentik-Username": "byron"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed OK"

    async def test_delete_fragrance_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required
        is True.
        """
        fragrance_id = await self._create_fragrance(test_app, "Auth Delete Fragrance")
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.delete(f"{API_PREFIX}/fragrances/{fragrance_id}")
        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_delete_fragrance_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the mutation through."""
        fragrance_id = await self._create_fragrance(
            test_app, "Auth Delete OK Fragrance"
        )
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.delete(
            f"{API_PREFIX}/fragrances/{fragrance_id}",
            headers={"X-Authentik-Username": "byron"},
        )
        assert response.status_code == 204
