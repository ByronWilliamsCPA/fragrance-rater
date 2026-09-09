"""Tests for reviewer API endpoints."""

import pytest

from fragrance_rater.core.config import settings

API_PREFIX = "/api/v1"


@pytest.mark.asyncio
class TestReviewerAPI:
    """Tests for reviewer API endpoints."""

    async def test_list_reviewers_empty(self, test_app):
        """Test listing reviewers when empty."""
        response = await test_app.get(f"{API_PREFIX}/reviewers")
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_reviewer(self, test_app):
        """Test creating a reviewer."""
        response = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Test Reviewer"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Reviewer"
        assert "id" in data
        assert data["evaluation_count"] == 0

    async def test_create_duplicate_reviewer(self, test_app):
        """Test creating a duplicate reviewer returns 409."""
        # Create first reviewer
        await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Duplicate User"},
        )

        # Try to create duplicate
        response = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Duplicate User"},
        )
        assert response.status_code == 409
        data = response.json()
        assert "REVIEWER_EXISTS" in str(data)

    async def test_get_reviewer_by_id(self, test_app):
        """Test getting a reviewer by ID."""
        # Create reviewer first
        create_response = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Get Test"},
        )
        reviewer_id = create_response.json()["id"]

        # Get the reviewer
        response = await test_app.get(f"{API_PREFIX}/reviewers/{reviewer_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Test"
        assert data["id"] == reviewer_id

    async def test_get_reviewer_not_found(self, test_app):
        """Test getting a non-existent reviewer returns 404."""
        response = await test_app.get(f"{API_PREFIX}/reviewers/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert "REVIEWER_NOT_FOUND" in str(data)

    async def test_seed_reviewers(self, test_app):
        """Test seeding default reviewers."""
        response = await test_app.post(f"{API_PREFIX}/reviewers/seed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        names = [r["name"] for r in data]
        assert "Byron" in names
        assert "Veronica" in names
        assert "Bayden" in names
        assert "Ariannah" in names

    async def test_seed_reviewers_idempotent(self, test_app):
        """Test seeding reviewers is idempotent."""
        # Seed twice
        response1 = await test_app.post(f"{API_PREFIX}/reviewers/seed")
        response2 = await test_app.post(f"{API_PREFIX}/reviewers/seed")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert len(response1.json()) == len(response2.json())

    async def test_delete_reviewer(self, test_app):
        """Test deleting a reviewer."""
        # Create reviewer first
        create_response = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Delete Test User"},
        )
        assert create_response.status_code == 201, (
            f"Create failed: {create_response.json()}"
        )
        reviewer_id = create_response.json()["id"]

        # Delete the reviewer
        response = await test_app.delete(f"{API_PREFIX}/reviewers/{reviewer_id}")
        assert response.status_code == 204

        # Verify deleted
        get_response = await test_app.get(f"{API_PREFIX}/reviewers/{reviewer_id}")
        assert get_response.status_code == 404

    async def test_delete_reviewer_not_found(self, test_app):
        """Test deleting a non-existent reviewer returns 404."""
        response = await test_app.delete(f"{API_PREFIX}/reviewers/nonexistent-id")
        assert response.status_code == 404

    async def test_list_reviewers_with_data(self, test_app):
        """Test listing reviewers returns created reviewers."""
        # Create some reviewers
        await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "User A"},
        )
        await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "User B"},
        )

        # List reviewers
        response = await test_app.get(f"{API_PREFIX}/reviewers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = [r["name"] for r in data]
        assert "User A" in names
        assert "User B" in names

    async def test_get_reviewer_evaluation_count_excludes_soft_deleted(
        self, test_app
    ):
        """Critical finding 2: evaluation_count must not include soft-deleted evals."""
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers", json={"name": "Count Test Reviewer"}
        )
        reviewer_id = reviewer_resp.json()["id"]

        fragrance_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Count Test Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        fragrance_id = fragrance_resp.json()["id"]

        eval_resp = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": reviewer_id,
                "rating": 5,
            },
        )
        evaluation_id = eval_resp.json()["id"]

        response = await test_app.get(f"{API_PREFIX}/reviewers/{reviewer_id}")
        assert response.json()["evaluation_count"] == 1

        await test_app.delete(f"{API_PREFIX}/evaluations/{evaluation_id}")

        response = await test_app.get(f"{API_PREFIX}/reviewers/{reviewer_id}")
        assert response.json()["evaluation_count"] == 0


@pytest.mark.asyncio
class TestReviewerAuthentikRequired:
    """Critical finding 2: mutating routes fail closed when Authentik is required."""

    async def test_create_reviewer_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required is True."""
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/reviewers", json={"name": "Should Fail"}
        )

        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_create_reviewer_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the mutation through."""
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Should Succeed"},
            headers={"X-Authentik-Username": "byron"},
        )

        assert response.status_code == 201
