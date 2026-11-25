"""Shared-session template preview and enrollment over HTTP."""

import json

import pytest

from fragrance_rater.core.config import settings

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
SHARED = "shared-triples-latin-rotation-v1"


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


async def build_program(test_app) -> tuple[str, list[str]]:
    """Active program: four baseline, one hidden repeat, one holdout."""
    fragrance_ids = []
    for index in range(5):
        response = await test_app.post(
            "/api/v1/fragrances",
            json={
                "name": f"Concealed {index}",
                "brand": "Concealed house",
                "concentration": "EDT",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
            headers=MANAGER,
        )
        assert response.status_code == 201
        fragrance_ids.append(response.json()["id"])
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Shared", "version": "1"}, headers=MANAGER
    )
    program_id = program.json()["id"]
    member_ids = []
    for fragrance_id in fragrance_ids[:4]:
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members",
            json={
                "fragrance_id": fragrance_id,
                "role": "UNIVERSAL_BASELINE",
                "identity_evidence": "Verified",
            },
            headers=MANAGER,
        )
        assert response.status_code == 201
        member_ids.append(response.json()["id"])
    for body in (
        {
            "fragrance_id": fragrance_ids[0],
            "role": "HIDDEN_REPEAT",
            "repeat_of_id": member_ids[0],
            "identity_evidence": "Same decant",
        },
        {
            "fragrance_id": fragrance_ids[4],
            "role": "HOLDOUT",
            "identity_evidence": "Verified",
        },
    ):
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members", json=body, headers=MANAGER
        )
        assert response.status_code == 201
    reviewer_ids = []
    for name in ("First", "Second"):
        response = await test_app.post(
            "/api/v1/reviewers", json={"name": name}, headers=MANAGER
        )
        reviewer_ids.append(response.json()["id"])
    activation = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activation.status_code == 200
    return program_id, reviewer_ids


@pytest.mark.asyncio
async def test_preview_is_manager_only_and_round_trips_into_enrollment(test_app):
    program_id, reviewer_ids = await build_program(test_app)
    url = f"{PREFIX}/programs/{program_id}/session-template/preview"
    denied = await test_app.post(url, json={"session_size": 1}, headers=RECORDER)
    assert denied.status_code == 403
    preview = await test_app.post(url, json={"session_size": 1}, headers=MANAGER)
    assert preview.status_code == 200
    assert preview.headers["cache-control"] == "private, no-store"
    body = preview.json()
    assert body["source"] == "generated"
    assert body["next_rotation"] == 0
    assert [s["block"] for s in body["sessions"]][-1] == "holdout"
    assert body["sessions"][0]["members"][0]["fragrance_name"].startswith("Concealed")
    template = body["session_template"]
    enrolled = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer_ids[0],
            "recorder_usernames": ["recorder"],
            "session_size": 1,
            "randomization_algorithm": SHARED,
            "session_template": template,
        },
        headers=MANAGER,
    )
    assert enrolled.status_code == 201
    recorded = await test_app.post(url, json={"session_size": 1}, headers=MANAGER)
    assert recorded.json()["source"] == "recorded"
    assert recorded.json()["session_template"] == template
    assert recorded.json()["next_rotation"] == 1
    # The participant payload carries codes only, never the template.
    participant = await test_app.get(
        f"{PREFIX}/enrollments/{enrolled.json()['id']}", headers=RECORDER
    )
    assert participant.status_code == 200
    serialized = json.dumps(participant.json())
    assert "Concealed" not in serialized
    assert all(mid not in serialized for s in template for mid in s)


@pytest.mark.asyncio
async def test_enroll_rejects_standard_labels_and_invalid_templates(test_app):
    program_id, reviewer_ids = await build_program(test_app)
    base = {
        "reviewer_id": reviewer_ids[0],
        "recorder_usernames": ["recorder"],
        "session_size": 1,
        "randomization_algorithm": SHARED,
    }
    standard = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={**base, "label_scheme": "standard"},
        headers=MANAGER,
    )
    assert standard.status_code == 422
    invalid = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={**base, "session_template": [["unknown"]]},
        headers=MANAGER,
    )
    assert invalid.status_code == 422
    assert "not in this program" in invalid.json()["detail"]
