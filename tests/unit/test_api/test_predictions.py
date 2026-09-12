"""Prediction snapshot endpoint authorization and outcome-link lifecycle."""

import pytest

from fragrance_rater.core.config import settings

PREFIX = "/api/v1/predictions"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


async def _make_reviewer_and_fragrance(test_app):
    reviewer = await test_app.post(
        "/api/v1/reviewers", json={"name": "Predicted Evaluator"}, headers=MANAGER
    )
    fragrance = await test_app.post(
        "/api/v1/fragrances",
        json={
            "name": "Prediction Target",
            "brand": "House",
            "concentration": "EDP",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
        headers=MANAGER,
    )
    assert reviewer.status_code == fragrance.status_code == 201
    return reviewer.json()["id"], fragrance.json()["id"]


@pytest.mark.asyncio
async def test_anonymous_and_non_manager_cannot_use_predictions(test_app):
    reviewer_id, fragrance_id = await _make_reviewer_and_fragrance(test_app)
    payload = {
        "reviewer_id": reviewer_id,
        "fragrance_id": fragrance_id,
        "model_id": "m",
        "model_version": "v1",
    }
    anonymous = await test_app.post(PREFIX, json=payload)
    assert anonymous.status_code == 401
    non_manager = await test_app.post(PREFIX, json=payload, headers=RECORDER)
    assert non_manager.status_code == 403
    listing = await test_app.get(
        PREFIX, params={"reviewer_id": reviewer_id}, headers=RECORDER
    )
    assert listing.status_code == 403


@pytest.mark.asyncio
async def test_anonymous_and_non_manager_cannot_link_an_outcome(test_app):
    reviewer_id, fragrance_id = await _make_reviewer_and_fragrance(test_app)
    created = await test_app.post(
        PREFIX,
        json={
            "reviewer_id": reviewer_id,
            "fragrance_id": fragrance_id,
            "model_id": "m",
            "model_version": "v1",
        },
        headers=MANAGER,
    )
    prediction_id = created.json()["id"]
    evaluation = await test_app.post(
        "/api/v1/evaluations",
        json={"fragrance_id": fragrance_id, "reviewer_id": reviewer_id, "rating": 4},
        headers=MANAGER,
    )
    payload = {"outcome_evaluation_id": evaluation.json()["id"]}
    anonymous = await test_app.post(f"{PREFIX}/{prediction_id}/outcome", json=payload)
    assert anonymous.status_code == 401
    non_manager = await test_app.post(
        f"{PREFIX}/{prediction_id}/outcome", json=payload, headers=RECORDER
    )
    assert non_manager.status_code == 403


@pytest.mark.asyncio
async def test_create_reports_404_for_unknown_reviewer_or_fragrance(test_app):
    _, fragrance_id = await _make_reviewer_and_fragrance(test_app)
    missing_reviewer = await test_app.post(
        PREFIX,
        json={
            "reviewer_id": "ghost",
            "fragrance_id": fragrance_id,
            "model_id": "m",
            "model_version": "v1",
        },
        headers=MANAGER,
    )
    assert missing_reviewer.status_code == 404


@pytest.mark.asyncio
async def test_create_reports_409_for_a_checkpoint_from_another_reviewer(test_app):
    reviewer_id, fragrance_id = await _make_reviewer_and_fragrance(test_app)
    other_reviewer = await test_app.post(
        "/api/v1/reviewers", json={"name": "Someone Else"}, headers=MANAGER
    )
    program = await test_app.post(
        "/api/v1/calibration/programs",
        json={"name": "Checkpoint owner mismatch", "version": "1"},
        headers=MANAGER,
    )
    program_id = program.json()["id"]
    member = await test_app.post(
        f"/api/v1/calibration/programs/{program_id}/members",
        json={
            "fragrance_id": fragrance_id,
            "role": "UNIVERSAL_BASELINE",
            "identity_evidence": "Verified",
        },
        headers=MANAGER,
    )
    assert member.status_code == 201
    activated = await test_app.post(
        f"/api/v1/calibration/programs/{program_id}/activate", headers=MANAGER
    )
    assert activated.status_code == 200
    enrollment = await test_app.post(
        f"/api/v1/calibration/programs/{program_id}/enroll",
        json={
            "reviewer_id": other_reviewer.json()["id"],
            "recorder_usernames": ["manager"],
        },
        headers=MANAGER,
    )
    assert enrollment.status_code == 201
    checkpoint = await test_app.post(
        f"/api/v1/calibration/enrollments/{enrollment.json()['id']}/checkpoints",
        json={"algorithm_version": "v1"},
        headers=MANAGER,
    )
    assert checkpoint.status_code == 201
    conflict = await test_app.post(
        PREFIX,
        json={
            "reviewer_id": reviewer_id,
            "fragrance_id": fragrance_id,
            "checkpoint_id": checkpoint.json()["id"],
            "model_id": "m",
            "model_version": "v1",
        },
        headers=MANAGER,
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_create_predict_link_outcome_and_list(test_app):
    reviewer_id, fragrance_id = await _make_reviewer_and_fragrance(test_app)
    created = await test_app.post(
        PREFIX,
        json={
            "reviewer_id": reviewer_id,
            "fragrance_id": fragrance_id,
            "model_id": "gbm-liking-v0",
            "model_version": "2026-09-12",
            "predicted_rating": 7.5,
            "uncertainty": 1.2,
            "input_manifest": [{"feature": "sweetness", "value": 3}],
        },
        headers=MANAGER,
    )
    assert created.status_code == 201
    prediction = created.json()
    assert prediction["predicted_rating"] == 7.5
    assert prediction["predicted_scale"] == "0-10"
    assert prediction["outcome_linked_at"] is None

    evaluation = await test_app.post(
        "/api/v1/evaluations",
        json={"fragrance_id": fragrance_id, "reviewer_id": reviewer_id, "rating": 4},
        headers=MANAGER,
    )
    assert evaluation.status_code == 201

    linked = await test_app.post(
        f"{PREFIX}/{prediction['id']}/outcome",
        json={"outcome_evaluation_id": evaluation.json()["id"]},
        headers=MANAGER,
    )
    assert linked.status_code == 200
    assert linked.json()["outcome_evaluation_id"] == evaluation.json()["id"]
    assert linked.json()["outcome_linked_at"] is not None
    assert linked.json()["outcome_recorded_by"] == "manager"
    # The frozen prediction itself is unchanged by linking an outcome.
    assert linked.json()["predicted_rating"] == 7.5

    conflict = await test_app.post(
        f"{PREFIX}/{prediction['id']}/outcome",
        json={"outcome_evaluation_id": evaluation.json()["id"]},
        headers=MANAGER,
    )
    assert conflict.status_code == 409

    listing = await test_app.get(
        PREFIX, params={"reviewer_id": reviewer_id}, headers=MANAGER
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [prediction["id"]]


@pytest.mark.asyncio
async def test_outcome_link_rejects_both_ids_and_neither(test_app):
    reviewer_id, fragrance_id = await _make_reviewer_and_fragrance(test_app)
    created = await test_app.post(
        PREFIX,
        json={
            "reviewer_id": reviewer_id,
            "fragrance_id": fragrance_id,
            "model_id": "m",
            "model_version": "v1",
        },
        headers=MANAGER,
    )
    prediction_id = created.json()["id"]
    neither = await test_app.post(
        f"{PREFIX}/{prediction_id}/outcome", json={}, headers=MANAGER
    )
    assert neither.status_code == 422
    evaluation = await test_app.post(
        "/api/v1/evaluations",
        json={"fragrance_id": fragrance_id, "reviewer_id": reviewer_id, "rating": 4},
        headers=MANAGER,
    )
    both = await test_app.post(
        f"{PREFIX}/{prediction_id}/outcome",
        json={
            "outcome_evaluation_id": evaluation.json()["id"],
            "outcome_observation_id": evaluation.json()["id"],
        },
        headers=MANAGER,
    )
    assert both.status_code == 422
