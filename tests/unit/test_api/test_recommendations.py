"""Tests for recommendation API endpoints."""

import pytest
from sqlalchemy import select

from fragrance_rater.core.database import get_db
from fragrance_rater.main import app
from fragrance_rater.middleware import limiter
from fragrance_rater.models.recommendation_measurement import (
    LLMInvocation,
    RecommendationImpression,
    RecommendationRun,
)
from fragrance_rater.services.llm_service import (
    RECOMMENDATION_PROMPT_VERSION,
    LLMResponse,
    get_llm_service,
)

API_PREFIX = "/api/v1"


async def _impression(reviewer_id: str, fragrance_id: str) -> str:
    """Persist a one-item run so the explanation has an impression to read.

    Explanations are only served for persisted impressions (architecture
    review B-02); the catalog-ID route that took any fragrance id was a
    holdout oracle and is gone.
    """
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        run = RecommendationRun(
            reviewer_id=reviewer_id,
            algorithm_version="test",
            candidate_strategy="test",
            input_manifest=[],
        )
        session.add(run)
        await session.flush()
        impression = RecommendationImpression(
            run_id=run.id,
            fragrance_id=fragrance_id,
            rank=1,
            score_type="affinity",
            score_value=0.5,
        )
        session.add(impression)
        await session.commit()
        return impression.id
    finally:
        await sessions.aclose()


def _explanation_url(impression_id: str) -> str:
    return (
        f"{API_PREFIX}/recommendation-measurement/impressions/"
        f"{impression_id}/explanation"
    )


@pytest.mark.asyncio
class TestRecommendationExplainAPI:
    """Tests for explanations served through a persisted impression."""

    async def test_explain_returns_200_with_explanation(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
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
        impression_id = await _impression(reviewer_id, target_fragrance_id)
        response = await test_app.get(_explanation_url(impression_id))

        assert response.status_code == 200
        data = response.json()
        assert data["fragrance_id"] == target_fragrance_id
        assert data["fragrance_name"] == "Explain Fragrance 0"
        assert data["explanation"]
        assert data["model"]

    async def test_explain_persists_attempted_provider_telemetry(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A failed provider call retains attempted model, prompt, usage, and cost."""
        reviewer = await test_app.post(
            f"{API_PREFIX}/reviewers", json={"name": "Telemetry Tester"}
        )
        reviewer_id = reviewer.json()["id"]
        fragrance_ids: list[str] = []
        for index in range(3):
            fragrance = await test_app.post(
                f"{API_PREFIX}/fragrances",
                json={
                    "name": f"Telemetry Fragrance {index}",
                    "brand": "Telemetry Brand",
                    "concentration": "EDP",
                    "gender_target": "Unisex",
                    "primary_family": "woody",
                    "subfamily": "aromatic",
                },
            )
            fragrance_ids.append(fragrance.json()["id"])
        for fragrance_id in fragrance_ids:
            evaluation = await test_app.post(
                f"{API_PREFIX}/evaluations",
                json={
                    "fragrance_id": fragrance_id,
                    "reviewer_id": reviewer_id,
                    "rating": 5,
                },
            )
            assert evaluation.status_code == 201

        class FailedProvider:
            model = "provider/attempted-model"

            @staticmethod
            def is_available() -> bool:
                return True

            @staticmethod
            async def generate_recommendation_explanation(**_kwargs) -> LLMResponse:
                return LLMResponse(
                    text="Deterministic fallback",
                    model="fallback",
                    error="provider failed",
                    prompt_tokens=10,
                    completion_tokens=2,
                    total_tokens=12,
                    provider_cost_usd=0.002,
                )

        impression_id = await _impression(reviewer_id, fragrance_ids[0])
        app.dependency_overrides[get_llm_service] = FailedProvider
        response = await test_app.get(_explanation_url(impression_id))
        assert response.status_code == 200
        assert response.json()["model"] == "fallback"

        session_dependency = app.dependency_overrides[get_db]
        sessions = session_dependency()
        session = await anext(sessions)
        try:
            invocation = await session.scalar(select(LLMInvocation))
            assert invocation is not None
            assert invocation.model == "provider/attempted-model"
            assert invocation.prompt_version == RECOMMENDATION_PROMPT_VERSION
            assert invocation.succeeded is False
            assert invocation.prompt_tokens == 10
            assert invocation.completion_tokens == 2
            assert invocation.total_tokens == 12
            assert invocation.provider_cost_usd == 0.002
        finally:
            await sessions.aclose()

    async def test_catalog_id_explain_route_is_gone(self, test_app):
        """B-02: the catalog-ID route answered 404 for exactly the caller's
        holdouts among listable catalog fragrances, so it no longer exists."""
        response = await test_app.get(
            f"{API_PREFIX}/recommendations/some-reviewer/some-fragrance/explain"
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

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

        impression_id = await _impression(reviewer_id, target_id)
        response = await test_app.get(_explanation_url(impression_id))

        assert response.status_code == 200
        data = response.json()
        assert data["fragrance_id"] == target_id

        # The target's real score under the default scorer: three five-star
        # ratings (+2.0 each) on the same family and nothing else, scored
        # against a candidate in that family with no notes or accords. Compute
        # it through the model object so this test follows the default
        # scorer rather than hardcoding one version's arithmetic; it must be
        # distinctly different from the old 50% fabricated placeholder.
        from fragrance_rater.ml.feature_space import FeatureVector
        from fragrance_rater.ml.model import DEFAULT_SCORER_FACTORY

        scorer = DEFAULT_SCORER_FACTORY()
        family_vector = FeatureVector(
            fragrance_id=None,
            version_key=None,
            concentration=None,
            primary_family="woody",
            subfamily="",
        )
        expected_profile = scorer.build_profile(
            reviewer_id, [(family_vector, [2.0])] * 3
        )
        expected_percent = scorer.score(expected_profile, family_vector).score_percent
        assert expected_percent != 50

        explanation = data["explanation"]
        assert f"{expected_percent}%" in explanation
        assert "50%" not in explanation

    async def test_explain_fragrance_not_found(self, test_app):
        """Explaining an impression whose fragrance is gone returns 404."""
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

        target = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "404 Target",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        target_id = target.json()["id"]
        impression_id = await _impression(reviewer_id, target_id)
        deleted = await test_app.delete(f"{API_PREFIX}/fragrances/{target_id}")
        assert deleted.status_code == 204

        response = await test_app.get(_explanation_url(impression_id))
        missing = await test_app.get(_explanation_url("no-such-impression"))

        # A deleted (or since-assigned holdout) fragrance answers exactly
        # like a missing impression, so the 404 discloses nothing (B-02).
        assert response.status_code == 404
        assert response.json() == missing.json()
