"""F1 routes: reveal policy, program readiness, bulk checkpoints, household reveal."""

import pytest

from fragrance_rater.core.config import settings

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
GATE = "This sample is not open yet"


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


async def make_fragrance(client, name):
    response = await client.post(
        "/api/v1/fragrances",
        json={
            "name": name,
            "brand": "Route House",
            "concentration": "EDT",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
        headers=MANAGER,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def draft_program(client, **extra):
    """A draft program with one baseline and one holdout member."""
    program = await client.post(
        f"{PREFIX}/programs",
        json={"name": "Household", "version": "1", **extra},
        headers=MANAGER,
    )
    assert program.status_code == 201
    program_id = program.json()["id"]
    for role, name in (("UNIVERSAL_BASELINE", "Base"), ("HOLDOUT", "Later")):
        member = await client.post(
            f"{PREFIX}/programs/{program_id}/members",
            json={
                "fragrance_id": await make_fragrance(client, name),
                "role": role,
                "identity_evidence": "Label verified",
            },
            headers=MANAGER,
        )
        assert member.status_code == 201
    return program_id


async def enroll(client, program_id, name):
    reviewer = await client.post(
        "/api/v1/reviewers", json={"name": name}, headers=MANAGER
    )
    return await client.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer.json()["id"],
            "recorder_usernames": ["recorder"],
        },
        headers=MANAGER,
    )


async def answer_and_lock(client, presentation_id):
    url = f"{PREFIX}/presentations/{presentation_id}"
    response = await client.post(
        f"{url}/observations",
        json={"stage": "BLOTTER", "detected": True, "intensity": 3, "liking": 6},
        headers=RECORDER,
    )
    assert response.status_code == 201, response.text
    assert (await client.post(f"{url}/lock/BLOTTER", headers=RECORDER)).status_code == (
        200
    )


@pytest.mark.asyncio
async def test_reveal_policy_is_chosen_while_the_program_is_a_draft(test_app):
    program_id = await draft_program(test_app)
    url = f"{PREFIX}/programs/{program_id}/reveal-policy"
    listed = await test_app.get(f"{PREFIX}/programs", headers=MANAGER)
    assert listed.json()[0]["reveal_policy"] == "ENROLLMENT"
    denied = await test_app.put(
        url, json={"reveal_policy": "HOUSEHOLD"}, headers=RECORDER
    )
    assert denied.status_code == 403
    invalid = await test_app.put(
        url, json={"reveal_policy": "EVERYONE"}, headers=MANAGER
    )
    assert invalid.status_code == 422
    changed = await test_app.put(
        url, json={"reveal_policy": "HOUSEHOLD"}, headers=MANAGER
    )
    assert changed.status_code == 200
    assert changed.json() == {"id": program_id, "reveal_policy": "HOUSEHOLD"}
    listed = await test_app.get(f"{PREFIX}/programs", headers=MANAGER)
    assert listed.json()[0]["reveal_policy"] == "HOUSEHOLD"
    activated = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activated.status_code == 200
    locked = await test_app.put(
        url, json={"reveal_policy": "ENROLLMENT"}, headers=MANAGER
    )
    assert locked.status_code == 409
    assert locked.json()["detail"] == "Program definition is locked"


@pytest.mark.asyncio
async def test_household_program_runs_from_checkpoint_to_one_reveal(test_app):
    program_id = await draft_program(test_app, reveal_policy="HOUSEHOLD")
    program_url = f"{PREFIX}/programs/{program_id}"
    assert (
        await test_app.post(f"{program_url}/activate", headers=MANAGER)
    ).status_code == 200
    enrollment = await enroll(test_app, program_id, "Evaluator")
    assert enrollment.status_code == 201
    enrollment_id = enrollment.json()["id"]
    url = f"{PREFIX}/enrollments/{enrollment_id}"

    view = (await test_app.get(url, headers=RECORDER)).json()
    assert view["reveal_policy"] == "HOUSEHOLD"
    assert "holdout" not in str(view).lower()
    base, later = view["presentations"]
    assert base["available"] is True
    assert later["available"] is False
    refused = await test_app.post(
        f"{PREFIX}/presentations/{later['id']}/observations",
        json={"stage": "BLOTTER", "detected": True, "intensity": 3, "liking": 6},
        headers=RECORDER,
    )
    assert refused.status_code == 409
    assert refused.json()["detail"].startswith(GATE)

    readiness = await test_app.get(f"{program_url}/readiness", headers=MANAGER)
    assert readiness.status_code == 200
    assert readiness.json() == {
        "program_id": program_id,
        "reveal_policy": "HOUSEHOLD",
        "household_reveal_ready": False,
        "household_revealed": False,
        "enrollments": [
            {
                "enrollment_id": enrollment_id,
                "reviewer_id": readiness.json()["enrollments"][0]["reviewer_id"],
                "reviewer_name": "Evaluator",
                "checkpoint_count": 0,
                "checkpoint_blocker": "SKIN_PLAN",
                "reveal_blocker": "SKIN_PLAN",
                "revealed": False,
            }
        ],
    }
    assert (
        await test_app.get(f"{program_url}/readiness", headers=RECORDER)
    ).status_code == 403
    single = await test_app.post(
        f"{url}/checkpoints", json={"algorithm_version": "test"}, headers=MANAGER
    )
    assert single.status_code == 409
    assert single.json()["detail"] == "Finalize the skin plan before the checkpoint"

    await answer_and_lock(test_app, base["id"])
    assert (
        await test_app.post(f"{url}/lock-skin-plan", headers=RECORDER)
    ).status_code == 200
    assert (
        await test_app.post(f"{program_url}/checkpoints", json={}, headers=RECORDER)
    ).status_code == 403
    frozen = await test_app.post(f"{program_url}/checkpoints", json={}, headers=MANAGER)
    assert frozen.status_code == 201, frozen.text
    body = frozen.json()
    assert body["algorithm_version"] == "affinity-v2"
    assert [row["enrollment_id"] for row in body["created"]] == [enrollment_id]
    assert body["created"][0]["predictions_frozen"] == 1
    assert body["skipped"] == []
    repeat = await test_app.post(
        f"{program_url}/checkpoints",
        json={"freeze_predictions": False},
        headers=MANAGER,
    )
    assert repeat.json()["skipped"] == [
        {"enrollment_id": enrollment_id, "reason": "HAS_CHECKPOINT"}
    ]

    overview = await test_app.get(f"{PREFIX}/manager/enrollments", headers=MANAGER)
    row = overview.json()[0]
    assert row["reveal_policy"] == "HOUSEHOLD"
    assert row["checkpoint_count"] == 1
    assert row["checkpoint_blocker"] is None
    assert row["reveal_blocker"] == "HOLDOUT"
    early = await test_app.post(f"{program_url}/reveal", headers=MANAGER)
    assert early.status_code == 409
    assert early.json()["detail"].startswith("1 of 1 evaluators")

    await answer_and_lock(test_app, later["id"])
    readiness = (await test_app.get(f"{program_url}/readiness", headers=MANAGER)).json()
    assert readiness["household_reveal_ready"] is True
    assert readiness["enrollments"][0]["reveal_blocker"] is None
    recorder_reveal = await test_app.post(f"{url}/reveal", headers=RECORDER)
    assert recorder_reveal.status_code == 409
    assert "manager reveals it" in recorder_reveal.json()["detail"]
    assert (
        await test_app.post(f"{program_url}/reveal", headers=RECORDER)
    ).status_code == 403

    revealed = await test_app.post(f"{program_url}/reveal", headers=MANAGER)
    assert revealed.status_code == 200
    assert revealed.json()["revealed"] is True
    assert revealed.json()["enrollment_ids"] == [enrollment_id]
    readiness = (await test_app.get(f"{program_url}/readiness", headers=MANAGER)).json()
    assert readiness["household_revealed"] is True
    assert readiness["household_reveal_ready"] is False
    view = (await test_app.get(url, headers=RECORDER)).json()
    assert view["revealed"] is True
    assert view["presentations"][1]["identity"]["name"] == "Later"
    late = await enroll(test_app, program_id, "Late evaluator")
    assert late.status_code == 409
    assert late.json()["detail"] == (
        "This household is already revealed; enroll in a new program"
    )


@pytest.mark.asyncio
async def test_program_routes_refuse_unknown_programs_and_models(test_app):
    assert (
        await test_app.get(f"{PREFIX}/programs/missing/readiness", headers=MANAGER)
    ).status_code == 404
    assert (
        await test_app.post(f"{PREFIX}/programs/missing/reveal", headers=MANAGER)
    ).status_code == 404
    assert (
        await test_app.post(
            f"{PREFIX}/programs/missing/checkpoints", json={}, headers=MANAGER
        )
    ).status_code == 404
    program_id = await draft_program(test_app)
    unknown = await test_app.post(
        f"{PREFIX}/programs/{program_id}/checkpoints",
        json={"algorithm_version": "no-such-model"},
        headers=MANAGER,
    )
    assert unknown.status_code == 422
    readiness = await test_app.get(
        f"{PREFIX}/programs/{program_id}/readiness", headers=MANAGER
    )
    assert readiness.json()["household_reveal_ready"] is False
    assert readiness.json()["enrollments"] == []
