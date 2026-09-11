"""Outcome measurement API tests."""

from __future__ import annotations

import pytest

from fragrance_rater.core.config import settings

API = "/api/v1"
IDENTITY = {"X-Authentik-Username": "recorder"}


async def seed_recommendable_catalog(test_app) -> tuple[str, str]:
    """Create one reviewer, three training versions, and one candidate."""
    reviewer = await test_app.post(f"{API}/reviewers", json={"name": "Measured"})
    reviewer_id = reviewer.json()["id"]
    fragrance_ids: list[str] = []
    for index in range(4):
        response = await test_app.post(
            f"{API}/fragrances",
            json={
                "name": f"Measured scent {index}",
                "brand": "Measured house",
                "concentration": "EDP",
                "version_key": f"measured-{index}",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        assert response.status_code == 201
        fragrance_ids.append(response.json()["id"])
    for fragrance_id in fragrance_ids[:3]:
        response = await test_app.post(
            f"{API}/evaluations",
            headers=IDENTITY,
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": reviewer_id,
                "rating": 5,
            },
        )
        assert response.status_code == 201
    return reviewer_id, fragrance_ids[3]


@pytest.mark.asyncio
async def test_impression_precedes_append_only_feedback_and_metrics(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run persists once, views are idempotent, and feedback revisions append."""
    reviewer_id, candidate_id = await seed_recommendable_catalog(test_app)
    created = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 1},
    )
    assert created.status_code == 201
    run = created.json()
    assert run["impressions"][0]["fragrance_id"] == candidate_id
    impression_id = run["impressions"][0]["id"]

    repeated = await test_app.get(
        f"{API}/recommendation-measurement/runs/{run['id']}", headers=IDENTITY
    )
    assert repeated.status_code == 200
    assert repeated.json()["impressions"][0]["id"] == impression_id

    first = await test_app.post(
        f"{API}/recommendation-measurement/impressions/{impression_id}/responses",
        headers=IDENTITY,
        json={"interested": True},
    )
    second = await test_app.post(
        f"{API}/recommendation-measurement/impressions/{impression_id}/responses",
        headers=IDENTITY,
        json={"interested": False, "sampling_state": "PLANNED"},
    )
    assert first.status_code == 201
    assert first.json()["revision"] == 1
    assert second.status_code == 201
    assert second.json()["revision"] == 2

    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    report = await test_app.get(
        f"{API}/recommendation-measurement/reviewers/{reviewer_id}/metrics",
        headers=IDENTITY,
    )
    assert report.status_code == 200
    assert report.json() == {
        "reviewer_id": reviewer_id,
        "eligible_impressions": 1,
        "explicit_interest_responses": 1,
        "positive_interest_responses": 0,
        "response_coverage": 1.0,
        "interest_rate": 0.0,
        "sampled_recommendations": 0,
        "sampling_conversion": 0.0,
        "linked_outcomes": 0,
        "mean_ordinary_rating": None,
        "would_wear_positive": 0,
        "would_wear_responses": 0,
        "would_buy_positive": 0,
        "would_buy_responses": 0,
        "unique_brands": 1,
        "unavailable_candidates": 0,
        "llm_call_count": 0,
        "llm_cache_hits": 0,
        "llm_failures": 0,
        "mean_llm_latency_ms": None,
        "known_estimated_cost_usd": 0.0,
        "connectivity_failures": 0,
        "manual_recoveries": 0,
    }


@pytest.mark.asyncio
async def test_feedback_requires_a_persisted_impression(test_app) -> None:
    """Feedback cannot exist independently of an impression."""
    response = await test_app.post(
        f"{API}/recommendation-measurement/impressions/missing/responses",
        headers=IDENTITY,
        json={"interested": True},
    )
    assert response.status_code == 404
