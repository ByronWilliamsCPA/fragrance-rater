"""House intake API: house scoping, draft/submit/correct lifecycle, and the fence."""

import pytest

from fragrance_rater.core.config import settings

PREFIX = "/api/v1/house-intake"
HOUSE_A = {"X-Authentik-Username": "maison-a-rep"}
HOUSE_A_COLLEAGUE = {"X-Authentik-Username": "maison-a-intern"}
HOUSE_B = {"X-Authentik-Username": "atelier-b-rep"}
MANAGER = {"X-Authentik-Username": "manager"}
FAMILY = {"X-Authentik-Username": "family-member"}


@pytest.fixture(autouse=True)
def intake_accounts(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])
    monkeypatch.setattr(
        settings,
        "house_contributors",
        {
            "maison-a-rep": "Maison A",
            "maison-a-intern": "Maison A",
            "atelier-b-rep": "Atelier B",
        },
    )


def complete_payload(**overrides):
    payload = {
        "fragrance_name": "Cèdre Nocturne",
        "line": "Les Bois",
        "concentration": "EDP",
        "version_label": "Original formulation",
        "launch_year": 2019,
        "availability": "in_production",
        "marketed_for": "Unisex",
        "perfumers": ["Ana Ruiz"],
        "product_url": "https://maison-a.example/cedre",
        "gtins": ["3508440005953"],
        "note_structure": "pyramid",
        "notes": [
            {"text": "Bergamot", "position": "top"},
            {"text": "Atlas cedar", "position": "heart"},
            {"text": "Musk", "position": "base"},
        ],
        "accords": ["woody", "smoky"],
        "family_as_described": "Woody aromatic",
        "description": "Cedar at dusk.",
        "permission_scope": "retain_for_qc_only",
        "contact_name": "Ana Ruiz",
        "contact_role": "Founder",
        "attested": True,
    }
    payload.update(overrides)
    return payload


async def create(client, headers=HOUSE_A, **overrides):
    response = await client.post(
        f"{PREFIX}/submissions", json=complete_payload(**overrides), headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_access_reports_house_manager_and_family(test_app):
    response = await test_app.get(f"{PREFIX}/access", headers=HOUSE_A)
    assert response.json() == {
        "username": "maison-a-rep",
        "house": "Maison A",
        "manager": False,
        "house_account": True,
    }
    response = await test_app.get(f"{PREFIX}/access", headers=MANAGER)
    assert response.json() == {
        "username": "manager",
        "house": None,
        "manager": True,
        "house_account": False,
    }
    response = await test_app.get(f"{PREFIX}/access", headers=FAMILY)
    assert response.json()["house"] is None
    assert (await test_app.get(f"{PREFIX}/access")).status_code == 401


@pytest.mark.asyncio
async def test_family_member_cannot_read_or_write(test_app):
    assert (
        await test_app.get(f"{PREFIX}/submissions", headers=FAMILY)
    ).status_code == 403
    response = await test_app.post(
        f"{PREFIX}/submissions", json=complete_payload(), headers=FAMILY
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_manager_reads_every_house_but_cannot_write(test_app):
    first = await create(test_app)
    second = await create(test_app, headers=HOUSE_B, fragrance_name="Atelier scent")
    await create(test_app, fragrance_name="Still a draft")
    for record, headers in ((first, HOUSE_A), (second, HOUSE_B)):
        await test_app.post(
            f"{PREFIX}/submissions/{record['id']}/submit", headers=headers
        )
    listed = await test_app.get(f"{PREFIX}/submissions", headers=MANAGER)
    assert {item["house"] for item in listed.json()} == {"Maison A", "Atelier B"}
    assert "Still a draft" not in {
        item["payload"]["fragrance_name"] for item in listed.json()
    }
    assert all(item["review_status"] == "pending" for item in listed.json())
    response = await test_app.post(
        f"{PREFIX}/submissions", json=complete_payload(), headers=MANAGER
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_house_is_taken_from_the_account_not_the_body(test_app):
    response = await test_app.post(
        f"{PREFIX}/submissions",
        json={**complete_payload(), "house": "Atelier B"},
        headers=HOUSE_A,
    )
    assert response.status_code == 422
    created = await create(test_app)
    assert created["house"] == "Maison A"
    assert created["created_by"] == "maison-a-rep"
    assert created["status"] == "draft"


@pytest.mark.asyncio
async def test_houses_cannot_see_or_touch_each_other(test_app):
    draft = await create(test_app)
    other = f"{PREFIX}/submissions/{draft['id']}"
    assert (await test_app.get(other, headers=HOUSE_B)).status_code == 404
    response = await test_app.put(other, json=complete_payload(), headers=HOUSE_B)
    assert response.status_code == 404
    assert (await test_app.delete(other, headers=HOUSE_B)).status_code == 404
    response = await test_app.post(f"{other}/submit", headers=HOUSE_B)
    assert response.status_code == 404
    assert (await test_app.get(f"{PREFIX}/submissions", headers=HOUSE_B)).json() == []


@pytest.mark.asyncio
async def test_colleagues_at_one_house_share_records(test_app):
    draft = await create(test_app)
    response = await test_app.get(
        f"{PREFIX}/submissions/{draft['id']}", headers=HOUSE_A_COLLEAGUE
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_draft_saves_partially_and_submit_lists_problems(test_app):
    response = await test_app.post(
        f"{PREFIX}/submissions",
        json={"fragrance_name": "Working title"},
        headers=HOUSE_A,
    )
    assert response.status_code == 201
    draft_id = response.json()["id"]
    response = await test_app.post(
        f"{PREFIX}/submissions/{draft_id}/submit", headers=HOUSE_A
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "SUBMISSION_INCOMPLETE"
    assert "attested" in {problem["field"] for problem in detail["problems"]}


@pytest.mark.asyncio
async def test_update_replaces_draft_content(test_app):
    draft = await create(test_app, attested=False)
    response = await test_app.put(
        f"{PREFIX}/submissions/{draft['id']}",
        json=complete_payload(fragrance_name="Cèdre Nocturne Intense"),
        headers=HOUSE_A,
    )
    assert response.status_code == 200
    assert response.json()["payload"]["fragrance_name"] == "Cèdre Nocturne Intense"


@pytest.mark.asyncio
async def test_submit_records_permission_and_freezes(test_app):
    draft = await create(test_app)
    path = f"{PREFIX}/submissions/{draft['id']}"
    response = await test_app.post(f"{path}/submit", headers=HOUSE_A_COLLEAGUE)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert body["permission_state"] == "retain_for_qc_only"
    assert body["submitted_by"] == "maison-a-intern"
    assert body["submitted_at"] is not None
    assert body["payload"]["notes"][1] == {"text": "Atlas cedar", "position": "heart"}

    response = await test_app.put(path, json=complete_payload(), headers=HOUSE_A)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "ALREADY_SUBMITTED"
    assert (await test_app.delete(path, headers=HOUSE_A)).status_code == 409
    assert (await test_app.post(f"{path}/submit", headers=HOUSE_A)).status_code == 409


@pytest.mark.asyncio
async def test_correction_supersedes_and_requires_fresh_attestation(test_app):
    draft = await create(test_app)
    original = f"{PREFIX}/submissions/{draft['id']}"
    assert (await test_app.post(f"{original}/revise", headers=HOUSE_A)).status_code == (
        409
    )
    await test_app.post(f"{original}/submit", headers=HOUSE_A)

    response = await test_app.post(f"{original}/revise", headers=HOUSE_A)
    assert response.status_code == 201
    correction = response.json()
    assert correction["status"] == "draft"
    assert correction["supersedes_id"] == draft["id"]
    assert correction["payload"]["attested"] is False
    assert correction["payload"]["notes"] == complete_payload()["notes"]

    second = await test_app.post(f"{original}/revise", headers=HOUSE_A)
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "ALREADY_REVISED"

    refreshed = (await test_app.get(original, headers=HOUSE_A)).json()
    assert refreshed["superseded_by_id"] == correction["id"]
    listed = (await test_app.get(f"{PREFIX}/submissions", headers=HOUSE_A)).json()
    by_id = {item["id"]: item for item in listed}
    assert by_id[draft["id"]]["superseded_by_id"] == correction["id"]


@pytest.mark.asyncio
async def test_draft_can_be_discarded(test_app):
    draft = await create(test_app)
    path = f"{PREFIX}/submissions/{draft['id']}"
    assert (await test_app.delete(path, headers=HOUSE_A)).status_code == 204
    assert (await test_app.get(path, headers=HOUSE_A)).status_code == 404


@pytest.mark.asyncio
async def test_invalid_payload_is_rejected(test_app):
    response = await test_app.post(
        f"{PREFIX}/submissions",
        json=complete_payload(product_url="javascript:alert(1)"),
        headers=HOUSE_A,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/reviewers"),
        ("post", "/api/v1/reviewers"),
        ("get", "/api/v1/fragrances"),
        ("post", "/api/v1/fragrances"),
        ("get", "/api/v1/calibration/access"),
        ("get", "/api/v1/evaluations"),
        ("get", "/api/v1/house-intake-admin"),
        ("get", "/docs"),
        ("get", "/openapi.json"),
        ("get", "/"),
    ],
)
async def test_fence_confines_house_contributors(test_app, method, path):
    response = await getattr(test_app, method)(path, headers=HOUSE_A)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "HOUSE_CONTRIBUTOR_FENCED"


@pytest.mark.asyncio
@pytest.mark.security
async def test_fence_lets_house_contributors_reach_intake_and_health(test_app):
    response = await test_app.get(f"{PREFIX}/submissions", headers=HOUSE_A)
    assert response.status_code == 200
    response = await test_app.get("/health/live", headers=HOUSE_A)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.security
async def test_fence_does_not_affect_family_members(test_app):
    response = await test_app.get("/api/v1/reviewers", headers=FAMILY)
    assert response.status_code == 200


FORMER_HOUSE = {
    "X-Authentik-Username": "former-rep",
    "X-Authentik-Groups": "staff|fragrance-houses",
}


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/reviewers"),
        ("post", "/api/v1/fragrances"),
        ("get", "/api/v1/calibration/access"),
    ],
)
async def test_a_group_member_stays_fenced_after_its_mapping_is_removed(
    test_app, method, path
):
    # "former-rep" is not in house_contributors, as after offboarding.
    response = await getattr(test_app, method)(path, headers=FORMER_HOUSE)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "HOUSE_CONTRIBUTOR_FENCED"


@pytest.mark.asyncio
@pytest.mark.security
async def test_an_unmapped_house_account_has_nothing_left_to_use(test_app):
    access = await test_app.get(f"{PREFIX}/access", headers=FORMER_HOUSE)
    assert access.json() == {
        "username": "former-rep",
        "house": None,
        "manager": False,
        "house_account": True,
    }
    listed = await test_app.get(f"{PREFIX}/submissions", headers=FORMER_HOUSE)
    assert listed.status_code == 403


@pytest.mark.asyncio
@pytest.mark.security
async def test_a_house_group_member_never_acts_as_manager(test_app, monkeypatch):
    monkeypatch.setattr(
        settings, "calibration_admin_usernames", ["manager", "former-rep"]
    )
    access = await test_app.get(f"{PREFIX}/access", headers=FORMER_HOUSE)
    assert access.json()["manager"] is False
    assert (
        await test_app.get(f"{PREFIX}/submissions", headers=FORMER_HOUSE)
    ).status_code == 403


@pytest.mark.asyncio
@pytest.mark.security
async def test_other_groups_do_not_fence_family_members(test_app):
    headers = {**FAMILY, "X-Authentik-Groups": "family|fragrance-houses-archive"}
    assert (await test_app.get("/api/v1/reviewers", headers=headers)).status_code == 200
