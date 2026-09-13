"""Outcome measurement API tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

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
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    created = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 1},
    )
    assert created.status_code == 201
    run = created.json()
    assert run["impressions"][0]["fragrance_id"] == candidate_id
    impression_id = run["impressions"][0]["id"]
    assert datetime.fromisoformat(run["impressions"][0]["shown_at"])

    explanation = await test_app.get(
        f"{API}/recommendation-measurement/impressions/{impression_id}/explanation",
        headers=IDENTITY,
    )
    assert explanation.status_code == 200
    assert explanation.headers["cache-control"] == "private, no-store"
    assert "X-Authentik-Username" in explanation.headers["vary"]
    assert explanation.json()["fragrance_id"] == candidate_id
    denied_explanation = await test_app.get(
        f"{API}/recommendation-measurement/impressions/{impression_id}/explanation",
        headers={"X-Authentik-Username": "unassigned"},
    )
    assert denied_explanation.status_code == 403
    assert denied_explanation.headers["cache-control"] == "private, no-store"
    assert "X-Authentik-Username" in denied_explanation.headers["vary"]

    repeated = await test_app.get(
        f"{API}/recommendation-measurement/runs/{run['id']}", headers=IDENTITY
    )
    assert repeated.status_code == 200
    assert repeated.headers["cache-control"] == "private, no-store"
    assert "X-Authentik-Username" in repeated.headers["vary"]
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

    reopened = await test_app.get(
        f"{API}/recommendation-measurement/runs/{run['id']}", headers=IDENTITY
    )
    assert reopened.status_code == 200
    saved = reopened.json()["impressions"][0]["responses"]
    assert [response["revision"] for response in saved] == [1, 2]
    assert saved[1]["sampling_state"] == "PLANNED"
    assert saved[1]["interested"] is False

    report = await test_app.get(
        f"{API}/recommendation-measurement/reviewers/{reviewer_id}/metrics",
        headers=IDENTITY,
    )
    assert report.status_code == 200
    metrics = report.json()
    window_start = datetime.fromisoformat(metrics.pop("window_start"))
    window_end = datetime.fromisoformat(metrics.pop("window_end"))
    assert 89 <= (window_end - window_start).days <= 90
    assert window_end >= datetime.fromisoformat(run["created_at"])
    assert metrics.pop("reviewer_population") == [reviewer_id]
    assert metrics.pop("exclusion_policy") == ["current assigned holdout versions"]
    assert metrics.pop("excluded_impressions") == 0
    assert metrics.pop("algorithm_versions") == ["affinity-v1"]
    assert metrics.pop("candidate_strategies") == ["catalog-affinity"]
    assert metrics.pop("run_filters") == [{"exclude_rated": True, "limit": 1}]
    source_snapshots = metrics.pop("source_snapshots")
    assert source_snapshots[0]["candidate_versions"][0]["fragrance_id"] == candidate_id
    assert metrics == {
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
        "llm_calls_with_known_estimated_cost": 0,
        "known_estimated_cost_usd": None,
        "llm_calls_with_known_provider_cost": 0,
        "known_provider_cost_usd": None,
        "connectivity_failures": 0,
        "manual_recoveries": 0,
    }
    assert report.headers["cache-control"] == "private, no-store"

    invalid_window = await test_app.get(
        f"{API}/recommendation-measurement/reviewers/{reviewer_id}/metrics",
        headers=IDENTITY,
        params={
            "window_start": "2026-09-12T00:00:00Z",
            "window_end": "2026-09-11T00:00:00Z",
        },
    )
    assert invalid_window.status_code == 400

    monkeypatch.setattr(settings, "calibration_admin_usernames", [])
    unauthorized_run = await test_app.get(
        f"{API}/recommendation-measurement/runs/{run['id']}", headers=IDENTITY
    )
    unauthorized_response = await test_app.post(
        f"{API}/recommendation-measurement/impressions/{impression_id}/responses",
        headers=IDENTITY,
        json={"interested": True},
    )
    unauthorized_event = await test_app.post(
        f"{API}/recommendation-measurement/operational-events",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "event_type": "CONNECTIVITY_FAILURE"},
    )
    unauthorized_metrics = await test_app.get(
        f"{API}/recommendation-measurement/reviewers/{reviewer_id}/metrics",
        headers=IDENTITY,
    )
    unauthorized_event_list = await test_app.get(
        f"{API}/recommendation-measurement/operational-events",
        headers=IDENTITY,
    )
    unauthorized_status = await test_app.get(
        f"{API}/recommendation-measurement/operational-status",
        headers=IDENTITY,
    )
    assert unauthorized_run.status_code == 403
    assert unauthorized_response.status_code == 403
    assert unauthorized_event.status_code == 403
    assert unauthorized_metrics.status_code == 403
    assert unauthorized_event_list.status_code == 403
    assert unauthorized_status.status_code == 403
    assert unauthorized_run.headers["cache-control"] == "private, no-store"
    assert unauthorized_event_list.headers["cache-control"] == "private, no-store"
    assert "X-Authentik-Username" in unauthorized_status.headers["vary"]


@pytest.mark.asyncio
async def test_operational_events_drive_manager_pilot_status(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure and recovery events deterministically drive manager status."""
    reviewer_id, _ = await seed_recommendable_catalog(test_app)
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    fixed_time = datetime(
        # datetime.UTC is unavailable on supported Python 3.10.
        2026,
        9,
        12,
        3,
        0,
        tzinfo=timezone.utc,  # noqa: UP017
    ).replace(tzinfo=None)
    monkeypatch.setattr(
        "fragrance_rater.services.recommendation_measurement_service.now_naive_utc",
        lambda: fixed_time,
    )

    initial_status = await test_app.get(
        f"{API}/recommendation-measurement/operational-status", headers=IDENTITY
    )
    assert initial_status.status_code == 200
    assert initial_status.headers["cache-control"] == "private, no-store"
    assert initial_status.json()["status"] == "available"

    failure = await test_app.post(
        f"{API}/recommendation-measurement/operational-events",
        headers=IDENTITY,
        json={
            "reviewer_id": reviewer_id,
            "event_type": "CONNECTIVITY_FAILURE",
            "details": "Recorder used paper fallback",
        },
    )
    assert failure.status_code == 201
    events = await test_app.get(
        f"{API}/recommendation-measurement/operational-events", headers=IDENTITY
    )
    assert events.status_code == 200
    assert events.headers["cache-control"] == "private, no-store"
    assert events.json()[0]["details"] == "Recorder used paper fallback"

    attention = await test_app.get(
        f"{API}/recommendation-measurement/operational-status", headers=IDENTITY
    )
    assert attention.status_code == 200
    assert attention.json()["status"] == "attention"
    assert attention.json()["unresolved_reviewer_ids"] == [reviewer_id]

    recovery = await test_app.post(
        f"{API}/recommendation-measurement/operational-events",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "event_type": "MANUAL_RECOVERY"},
    )
    assert recovery.status_code == 201
    recovered = await test_app.get(
        f"{API}/recommendation-measurement/operational-status", headers=IDENTITY
    )
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "available"
    recovered_events = await test_app.get(
        f"{API}/recommendation-measurement/operational-events", headers=IDENTITY
    )
    assert recovered_events.status_code == 200
    timestamps = [
        datetime.fromisoformat(item["occurred_at"]) for item in recovered_events.json()
    ]
    assert timestamps[0] > timestamps[1]


@pytest.mark.asyncio
async def test_feedback_requires_a_persisted_impression(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Feedback cannot exist independently of an impression."""
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    response = await test_app.post(
        f"{API}/recommendation-measurement/impressions/missing/responses",
        headers=IDENTITY,
        json={"interested": True},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_run_requires_reviewer_assignment(test_app) -> None:
    """An unassigned non-admin recorder cannot create another reviewer's run."""
    reviewer_id, _ = await seed_recommendable_catalog(test_app)
    response = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 1},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_feedback_rejects_unknown_fields(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Misspelled feedback fields cannot create an empty append-only revision."""
    reviewer_id, _ = await seed_recommendable_catalog(test_app)
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    run = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 1},
    )
    impression_id = run.json()["impressions"][0]["id"]
    response = await test_app.post(
        f"{API}/recommendation-measurement/impressions/{impression_id}/responses",
        headers=IDENTITY,
        json={"interest": True},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_assigned_recorder_can_create_run(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recorder explicitly assigned through an enrollment receives access."""
    reviewer_id, candidate_id = await seed_recommendable_catalog(test_app)
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])
    manager_headers = {"X-Authentik-Username": "manager"}
    program = await test_app.post(
        f"{API}/calibration/programs",
        headers=manager_headers,
        json={"name": "Authorization", "version": "v1"},
    )
    program_id = program.json()["id"]
    member = await test_app.post(
        f"{API}/calibration/programs/{program_id}/members",
        headers=manager_headers,
        json={
            "fragrance_id": candidate_id,
            "role": "OTHER",
            "identity_evidence": "verified test version",
        },
    )
    assert member.status_code == 201
    activated = await test_app.post(
        f"{API}/calibration/programs/{program_id}/activate", headers=manager_headers
    )
    assert activated.status_code == 200
    enrolled = await test_app.post(
        f"{API}/calibration/programs/{program_id}/enroll",
        headers=manager_headers,
        json={
            "reviewer_id": reviewer_id,
            "recorder_usernames": ["recorder"],
            "session_size": 1,
        },
    )
    assert enrolled.status_code == 201

    monkeypatch.setattr(settings, "calibration_admin_usernames", [])
    response = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 1},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_feedback_rejects_outcome_recorded_before_impression(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Historical encounters cannot be relabeled as prospective outcomes."""
    reviewer_id, candidate_id = await seed_recommendable_catalog(test_app)
    historical = await test_app.post(
        f"{API}/evaluations",
        headers=IDENTITY,
        json={
            "fragrance_id": candidate_id,
            "reviewer_id": reviewer_id,
            "rating": 4,
        },
    )
    assert historical.status_code == 201
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    created = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 4, "exclude_rated": False},
    )
    assert created.status_code == 201
    impression_id = next(
        item["id"]
        for item in created.json()["impressions"]
        if item["fragrance_id"] == candidate_id
    )
    response = await test_app.post(
        f"{API}/recommendation-measurement/impressions/{impression_id}/responses",
        headers=IDENTITY,
        json={
            "sampling_state": "SAMPLED",
            "outcome_evaluation_id": historical.json()["id"],
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_feedback_rejects_an_on_others_evaluation_as_outcome(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-011: an "on others" evaluation is not this reviewer's own preference."""
    reviewer_id, candidate_id = await seed_recommendable_catalog(test_app)
    subject = await test_app.post(f"{API}/reviewers", json={"name": "Worn By"})
    subject_id = subject.json()["id"]
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    created = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 1},
    )
    assert created.status_code == 201
    impression_id = created.json()["impressions"][0]["id"]

    on_others = await test_app.post(
        f"{API}/evaluations",
        headers=IDENTITY,
        json={
            "fragrance_id": candidate_id,
            "reviewer_id": reviewer_id,
            "rating": 4,
            "worn_by_reviewer_id": subject_id,
        },
    )
    assert on_others.status_code == 201

    response = await test_app.post(
        f"{API}/recommendation-measurement/impressions/{impression_id}/responses",
        headers=IDENTITY,
        json={
            "sampling_state": "SAMPLED",
            "outcome_evaluation_id": on_others.json()["id"],
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_concurrent_sqlite_feedback_never_leaks_database_error(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent append races produce unique revisions or an explicit conflict."""
    reviewer_id, _ = await seed_recommendable_catalog(test_app)
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["recorder"])
    created = await test_app.post(
        f"{API}/recommendation-measurement/runs",
        headers=IDENTITY,
        json={"reviewer_id": reviewer_id, "limit": 1},
    )
    impression_id = created.json()["impressions"][0]["id"]

    responses = await asyncio.gather(
        *[
            test_app.post(
                f"{API}/recommendation-measurement/impressions/{impression_id}/responses",
                headers=IDENTITY,
                json={"interested": bool(index % 2)},
            )
            for index in range(4)
        ]
    )
    assert {response.status_code for response in responses} <= {201, 409}
    revisions = [
        response.json()["revision"]
        for response in responses
        if response.status_code == 201
    ]
    assert revisions
    assert len(revisions) == len(set(revisions))
