"""Tests for recommendation API endpoints."""

import pytest

API_PREFIX = "/api/v1"


@pytest.mark.asyncio
class TestRecommendationExplainAPI:
    """Tests for the /recommendations/{reviewer_id}/{fragrance_id}/explain endpoint."""

    async def test_explain_returns_200_with_explanation(self, test_app):
        """The explain endpoint must not 500 (MissingGreenlet) and must return
        a real explanation payload once notes and accords are both eager-loaded.
        """
        # Seed a reviewer
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Explain Tester"},
        )
        assert reviewer_resp.status_code == 201
        reviewer_id = reviewer_resp.json()["id"]

        # Seed 3 fragrances with notes and accords so we can build a profile
        fragrance_ids: list[str] = []
        for i in range(3):
            resp = await test_app.post(
                f"{API_PREFIX}/fragrances",
                json={
                    "name": f"Explain Fragrance {i}",
                    "brand": "Explain Brand",
                    "concentration": "EDP",
                    "gender_target": "Unisex",
                    "primary_family": "woody",
                    "subfamily": "aromatic",
                    "notes": [
                        {
                            "note_name": "Bergamot",
                            "note_category": "citrus",
                            "position": "top",
                        }
                    ],
                    "accords": [{"accord_type": "woody", "intensity": 0.8}],
                },
            )
            assert resp.status_code == 201
            fragrance_ids.append(resp.json()["id"])

        # Rate all three fragrances so the profile has >= MIN_EVALUATIONS
        for fid in fragrance_ids:
            eval_resp = await test_app.post(
                f"{API_PREFIX}/evaluations",
                json={
                    "fragrance_id": fid,
                    "reviewer_id": reviewer_id,
                    "rating": 5,
                },
            )
            assert eval_resp.status_code == 201

        target_fragrance_id = fragrance_ids[0]
        response = await test_app.get(
            f"{API_PREFIX}/recommendations/{reviewer_id}/{target_fragrance_id}/explain"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fragrance_id"] == target_fragrance_id
        assert data["fragrance_name"] == "Explain Fragrance 0"
        assert data["explanation"]
        assert data["model"]

    async def test_explain_fragrance_not_found(self, test_app):
        """Explaining a nonexistent fragrance returns 404, not a 500."""
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Explain 404 Tester"},
        )
        reviewer_id = reviewer_resp.json()["id"]

        # Rate 3 real fragrances to clear the insufficient-data gate.
        fragrance_ids: list[str] = []
        for i in range(3):
            resp = await test_app.post(
                f"{API_PREFIX}/fragrances",
                json={
                    "name": f"404 Fragrance {i}",
                    "brand": "Brand",
                    "concentration": "EDP",
                    "gender_target": "Unisex",
                    "primary_family": "woody",
                    "subfamily": "aromatic",
                },
            )
            fragrance_ids.append(resp.json()["id"])
        for fid in fragrance_ids:
            await test_app.post(
                f"{API_PREFIX}/evaluations",
                json={"fragrance_id": fid, "reviewer_id": reviewer_id, "rating": 4},
            )

        response = await test_app.get(
            f"{API_PREFIX}/recommendations/{reviewer_id}/nonexistent-fragrance/explain"
        )
        assert response.status_code == 404
