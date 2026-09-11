"""Calibration manager/recorder authorization and end-to-end lifecycle."""

import pytest

from fragrance_rater.core.config import settings

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
OUTSIDER = {"X-Authentik-Username": "outsider"}


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


@pytest.mark.asyncio
async def test_anonymous_and_non_manager_cannot_manage_programs(test_app):
    data = {"name": "Test protocol", "version": "1"}
    response = await test_app.post(f"{PREFIX}/programs", json=data)
    assert response.status_code == 401
    response = await test_app.post(f"{PREFIX}/programs", json=data, headers=RECORDER)
    assert response.status_code == 403
    response = await test_app.get(
        f"{PREFIX}/programs/unknown/members", headers=RECORDER
    )
    assert response.status_code == 403
    response = await test_app.get(f"{PREFIX}/access", headers=RECORDER)
    assert response.json() == {"username": "recorder", "manager": False}


@pytest.mark.asyncio
async def test_controlled_lifecycle_authorization_and_reveal(test_app):
    reviewer = await test_app.post(
        "/api/v1/reviewers", json={"name": "Evaluator"}, headers=MANAGER
    )
    fragrance = await test_app.post(
        "/api/v1/fragrances",
        json={
            "name": "Concealed identity",
            "brand": "Concealed house",
            "concentration": "EDT",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
        headers=MANAGER,
    )
    assert reviewer.status_code == fragrance.status_code == 201
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Protocol", "version": "1"}, headers=MANAGER
    )
    assert program.status_code == 201
    program_id = program.json()["id"]
    activation = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activation.status_code == 409
    member = await test_app.post(
        f"{PREFIX}/programs/{program_id}/members",
        json={
            "fragrance_id": fragrance.json()["id"],
            "role": "UNIVERSAL_BASELINE",
            "identity_evidence": "Label verified",
        },
        headers=MANAGER,
    )
    assert member.status_code == 201
    activation = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activation.status_code == 200
    enrollment = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer.json()["id"],
            "recorder_usernames": ["recorder"],
        },
        headers=MANAGER,
    )
    assert enrollment.status_code == 201
    enrollment_id = enrollment.json()["id"]
    url = f"{PREFIX}/enrollments/{enrollment_id}"
    forbidden = await test_app.get(url, headers=OUTSIDER)
    assert forbidden.status_code == 403
    assert (await test_app.get(f"{PREFIX}/enrollments", headers=OUTSIDER)).json() == []
    assert (await test_app.get(f"{PREFIX}/programs", headers=OUTSIDER)).json() == []
    view = await test_app.get(url, headers=RECORDER)
    assert view.status_code == 200
    assert "Concealed" not in view.text
    presentation_id = view.json()["presentations"][0]["id"]
    presentation_url = f"{PREFIX}/presentations/{presentation_id}"
    mapping = await test_app.get(f"{url}/mapping", headers=RECORDER)
    assert mapping.status_code == 403
    mapping = await test_app.get(f"{url}/mapping", headers=MANAGER)
    assert mapping.status_code == 200
    assert mapping.json()[0]["fragrance_id"] == fragrance.json()["id"]

    blocked = await test_app.post(f"{url}/reveal", headers=RECORDER)
    assert blocked.status_code == 409
    blocked = await test_app.post(
        f"{presentation_url}/observations", json={"stage": "BLOTTER"}, headers=OUTSIDER
    )
    assert blocked.status_code == 403
    response = await test_app.post(
        f"{presentation_url}/observations",
        json={
            "stage": "BLOTTER",
            "detected": True,
            "intensity": 3,
            "liking": 8,
        },
        headers=RECORDER,
    )
    assert response.status_code == 201
    history = await test_app.get(
        f"{PREFIX}/history/{reviewer.json()['id']}", headers=RECORDER
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["identity"] is None
    assert "Concealed" not in history.text
    assert fragrance.json()["id"] not in history.text
    forbidden_history = await test_app.get(
        f"{PREFIX}/history/{reviewer.json()['id']}", headers=OUTSIDER
    )
    assert forbidden_history.status_code == 403
    assert (
        await test_app.post(f"{presentation_url}/lock/BLOTTER", headers=RECORDER)
    ).status_code == 200
    assert (
        await test_app.post(f"{url}/lock-skin-plan", headers=RECORDER)
    ).status_code == 200
    checkpoint = await test_app.post(
        f"{url}/checkpoints", json={"algorithm_version": "test"}, headers=RECORDER
    )
    assert checkpoint.status_code == 403
    checkpoint = await test_app.post(
        f"{url}/checkpoints", json={"algorithm_version": "test"}, headers=MANAGER
    )
    assert checkpoint.status_code == 201
    assert (await test_app.post(f"{url}/reveal", headers=RECORDER)).status_code == 200
    view = await test_app.get(url, headers=RECORDER)
    assert view.json()["presentations"][0]["identity"]["name"] == "Concealed identity"
    response = await test_app.post(
        f"{presentation_url}/post-reveal",
        json={
            "stage": "BLOTTER",
            "comments": "Now I recognize it",
            "liking": 5,
        },
        headers=RECORDER,
    )
    assert response.status_code == 201
    view = await test_app.get(url, headers=RECORDER)
    assert [
        (row["phase"], row["liking"])
        for row in view.json()["presentations"][0]["observations"]
    ] == [
        ("PRE_REVEAL", 8),
        ("POST_REVEAL", 5),
    ]
