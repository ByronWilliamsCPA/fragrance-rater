"""Tests for evaluation API endpoints.

Covers Major finding 9: creating an evaluation against a nonexistent
fragrance_id or reviewer_id must return a clean 404, not silently succeed
(SQLite, FKs off by default in tests) or 500 (Postgres, FK violation).
"""

import pytest

API_PREFIX = "/api/v1"


@pytest.mark.asyncio
class TestCreateEvaluationAPI:
    """Tests for POST /evaluations."""

    async def test_create_evaluation_success(self, test_app):
        """A valid fragrance_id and reviewer_id should create the evaluation."""
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Eval Create Tester"},
        )
        assert reviewer_resp.status_code == 201
        reviewer_id = reviewer_resp.json()["id"]

        fragrance_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Eval Create Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        assert fragrance_resp.status_code == 201
        fragrance_id = fragrance_resp.json()["id"]

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": reviewer_id,
                "rating": 5,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["fragrance_id"] == fragrance_id
        assert data["reviewer_id"] == reviewer_id

    async def test_create_evaluation_nonexistent_fragrance_returns_404(self, test_app):
        """A nonexistent fragrance_id must 404, not 500 or silently insert."""
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Eval FK Tester Fragrance"},
        )
        reviewer_id = reviewer_resp.json()["id"]

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": "nonexistent-fragrance",
                "reviewer_id": reviewer_id,
                "rating": 4,
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "FRAGRANCE_NOT_FOUND"

    async def test_create_evaluation_nonexistent_reviewer_returns_404(self, test_app):
        """A nonexistent reviewer_id must 404, not 500 or silently insert."""
        fragrance_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Eval FK Tester Reviewer Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        fragrance_id = fragrance_resp.json()["id"]

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": "nonexistent-reviewer",
                "rating": 4,
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "REVIEWER_NOT_FOUND"

    async def test_create_evaluation_both_fk_missing_reports_fragrance_first(
        self, test_app
    ):
        """When both FKs are invalid, the fragrance check runs first and is
        reported; this pins down the documented check order.
        """
        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": "nonexistent-fragrance",
                "reviewer_id": "nonexistent-reviewer",
                "rating": 3,
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "FRAGRANCE_NOT_FOUND"
