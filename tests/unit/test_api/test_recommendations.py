"""Tests for recommendation API endpoints."""

import math

import pytest

from fragrance_rater.core.config import settings
from fragrance_rater.middleware import limiter

API_PREFIX = "/api/v1"

# #ASSUME: security: /explain requires the shared household X-API-Key (see
# fragrance_rater.middleware.auth.require_api_key), mirroring POST /ratings,
# because it always triggers a billed OpenRouter call. Every request in this
# module must send AUTH_HEADERS below with settings.api_key patched to match.
# #VERIFY: if require_api_key is ever removed from this route, drop the
# monkeypatch/header plumbing here too so tests don't mask a regression.
API_KEY = "test-explain-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.mark.asyncio
class TestRecommendationExplainAPI:
    """Tests for the /recommendations/{reviewer_id}/{fragrance_id}/explain endpoint."""

    async def test_explain_returns_200_with_explanation(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """The explain endpoint must not 500 (MissingGreenlet) and must return
        a real explanation payload once notes and accords are both eager-loaded.
        """
        monkeypatch.setattr(settings, "api_key", API_KEY)
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
            f"{API_PREFIX}/recommendations/{reviewer_id}/{target_fragrance_id}/explain",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fragrance_id"] == target_fragrance_id
        assert data["fragrance_name"] == "Explain Fragrance 0"
        assert data["explanation"]
        assert data["model"]

    async def test_explain_requires_api_key(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """No X-API-Key header sent -> 401, not a silent 200.

        Regression test for the LLM-backed /explain route being reachable
        without the same credential POST /ratings requires (see
        fragrance_rater.middleware.auth.require_api_key).
        """
        monkeypatch.setattr(settings, "api_key", API_KEY)

        response = await test_app.get(
            f"{API_PREFIX}/recommendations/some-reviewer/some-fragrance/explain"
        )

        assert response.status_code == 401

    async def test_explain_fails_closed_when_no_api_key_configured(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """No FRAGRANCE_RATER_API_KEY configured -> 503, not a silent 200."""
        monkeypatch.setattr(settings, "api_key", None)

        response = await test_app.get(
            f"{API_PREFIX}/recommendations/some-reviewer/some-fragrance/explain",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 503

    async def test_explain_computes_real_score_for_target_outside_top_100(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """Regression test for Critical finding 1 (first-100-only scoring bug).

        A prior version of get_recommendation_explanation scored the
        reviewer's full candidate pool via
        service.get_recommendations(limit=100, exclude_rated=False) and
        looked the requested fragrance_id up in that size-capped result.
        When the target ranked outside the top 100 by match_score, the
        lookup missed and silently fell back to a fabricated
        match_score=0.5/match_percent=50 placeholder.

        This seeds > 100 filler fragrances engineered to score strictly
        higher than the target (so the target would rank below index 100
        under the old top-100-slice behavior), then asserts /explain still
        reports the target's real, directly-computed match percentage (not
        the 50% placeholder) by reading it back out of the LLM-disabled
        fallback explanation text, which always embeds the exact
        `recommendation.match_percent` passed to it.
        """
        monkeypatch.setattr(settings, "api_key", API_KEY)

        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Outside Top 100 Tester"},
        )
        assert reviewer_resp.status_code == 201
        reviewer_id = reviewer_resp.json()["id"]

        # 3 rated fragrances build a profile with a strong "Bergamot" note
        # affinity and a strong "citrus"/"fresh" family/subfamily affinity.
        rated_ids: list[str] = []
        for i in range(3):
            resp = await test_app.post(
                f"{API_PREFIX}/fragrances",
                json={
                    "name": f"Rated Fragrance {i}",
                    "brand": "Rated Brand",
                    "concentration": "EDP",
                    "gender_target": "Unisex",
                    "primary_family": "citrus",
                    "subfamily": "fresh",
                    "notes": [
                        {
                            "note_name": "Bergamot",
                            "note_category": "citrus",
                            "position": "top",
                        }
                    ],
                },
            )
            assert resp.status_code == 201
            rated_ids.append(resp.json()["id"])
        for fid in rated_ids:
            eval_resp = await test_app.post(
                f"{API_PREFIX}/evaluations",
                json={"fragrance_id": fid, "reviewer_id": reviewer_id, "rating": 5},
            )
            assert eval_resp.status_code == 201

        # 105 filler candidates share the Bergamot note AND the citrus/fresh
        # family/subfamily, so each scores strictly higher than the target
        # below (which only shares the family, not the note or subfamily).
        # None of these are rated, so they don't perturb the profile itself.
        #
        # #ASSUME: this test's own request volume (100+ POSTs) would trip
        # the general-purpose DEFAULT_RATE_LIMIT (60/minute, see
        # fragrance_rater.middleware.rate_limit) well before seeding is
        # done; that limit exists to protect against real callers, not this
        # test's own seeding loop, so reset the in-memory counters
        # periodically the same way the autouse `_reset_slowapi_limiter`
        # fixture already does between tests.
        # #VERIFY: keep this reset cadence comfortably under
        # settings.rate_limit_rpm (default 60) if that default is ever
        # lowered further.
        for i in range(105):
            if i % 40 == 0:
                limiter.reset()
            resp = await test_app.post(
                f"{API_PREFIX}/fragrances",
                json={
                    "name": f"Filler Fragrance {i}",
                    "brand": "Filler Brand",
                    "concentration": "EDP",
                    "gender_target": "Unisex",
                    "primary_family": "citrus",
                    "subfamily": "fresh",
                    "notes": [
                        {
                            "note_name": "Bergamot",
                            "note_category": "citrus",
                            "position": "top",
                        }
                    ],
                },
            )
            assert resp.status_code == 201

        limiter.reset()

        # Target: shares only the family (weaker signal, no note/subfamily
        # match), so its real match score is lower than every filler above
        # and it would rank outside the first 100 if a caller ever went
        # back to scoring via a top-100-sliced recommendation list.
        target_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Outside Top 100 Target",
                "brand": "Target Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "citrus",
                "subfamily": "unmatched-subfamily",
            },
        )
        assert target_resp.status_code == 201
        target_id = target_resp.json()["id"]

        response = await test_app.get(
            f"{API_PREFIX}/recommendations/{reviewer_id}/{target_id}/explain",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fragrance_id"] == target_id

        # The target's real raw_score is COMPONENT_WEIGHTS["family"] * 6.0
        # (3 five-star ratings x +2.0 family affinity each) = 1.2, which
        # sigmoid-normalizes to a percent distinctly different from the old
        # 50% fabricated placeholder.
        expected_raw_score = 0.20 * 6.0
        expected_percent = int((1 / (1 + math.exp(-expected_raw_score))) * 100)
        assert expected_percent != 50

        explanation = data["explanation"]
        assert f"{expected_percent}%" in explanation
        assert "50%" not in explanation

    async def test_explain_fragrance_not_found(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """Explaining a nonexistent fragrance returns 404, not a 500."""
        monkeypatch.setattr(settings, "api_key", API_KEY)

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
            f"{API_PREFIX}/recommendations/{reviewer_id}/nonexistent-fragrance/explain",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 404
