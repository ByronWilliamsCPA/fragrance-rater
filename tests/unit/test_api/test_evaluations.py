"""Tests for evaluation API endpoints.

Covers Major finding 9: creating an evaluation against a nonexistent
fragrance_id or reviewer_id must return a clean 404, not silently succeed
(SQLite, FKs off by default in tests) or 500 (Postgres, FK violation).
"""

from unittest.mock import AsyncMock, patch

import pytest

from fragrance_rater.services.evaluation_service import EvaluationService

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

    async def test_create_duplicate_evaluation_returns_409(self, test_app):
        """Major finding 8: a second evaluation for the same reviewer and
        fragrance is rejected by the existing application-level pre-check
        (the common, non-racy path).
        """
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers", json={"name": "Dup Eval Tester"}
        )
        reviewer_id = reviewer_resp.json()["id"]
        fragrance_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Dup Eval Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        fragrance_id = fragrance_resp.json()["id"]
        payload = {
            "fragrance_id": fragrance_id,
            "reviewer_id": reviewer_id,
            "rating": 4,
        }

        first = await test_app.post(f"{API_PREFIX}/evaluations", json=payload)
        assert first.status_code == 201

        second = await test_app.post(f"{API_PREFIX}/evaluations", json=payload)
        assert second.status_code == 409
        assert second.json()["detail"]["error"] == "EVALUATION_EXISTS"

    async def test_create_evaluation_race_condition_hits_integrity_error_path(
        self, test_app
    ):
        """Major finding 8: if the pre-check races and misses an already
        committed duplicate, the DB-level UNIQUE(reviewer_id, fragrance_id)
        constraint is the actual backstop, and the endpoint must translate
        the resulting IntegrityError into the same 409 the pre-check
        produces for the common case, not an unhandled 500.

        The race is simulated by patching the pre-check to always report
        "no existing evaluation" so the request falls through to the
        insert. That patch also covers the endpoint's post-IntegrityError
        lookup, so `existing_id` in the 409 body comes back None here; this
        pins the "still a clean 409, not a 500" behavior, not the
        existing_id enrichment.
        """
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers", json={"name": "Race Eval Tester"}
        )
        reviewer_id = reviewer_resp.json()["id"]
        fragrance_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Race Eval Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        fragrance_id = fragrance_resp.json()["id"]
        payload = {
            "fragrance_id": fragrance_id,
            "reviewer_id": reviewer_id,
            "rating": 4,
        }

        first = await test_app.post(f"{API_PREFIX}/evaluations", json=payload)
        assert first.status_code == 201

        with patch.object(
            EvaluationService,
            "get_by_reviewer_and_fragrance",
            AsyncMock(return_value=None),
        ):
            second = await test_app.post(f"{API_PREFIX}/evaluations", json=payload)

        assert second.status_code == 409
        detail = second.json()["detail"]
        assert detail["error"] == "EVALUATION_EXISTS"
        assert detail["existing_id"] is None
