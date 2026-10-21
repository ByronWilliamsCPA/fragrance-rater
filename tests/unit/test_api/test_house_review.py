"""Manager review of house submissions: adopt as evidence, or decline."""

import pytest
from sqlalchemy import select

from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.models.calibration import (
    Membership,
    Perfumer,
    Program,
    SourceSnapshot,
    VersionPerfumer,
)
from fragrance_rater.models.fragrance import FragranceGtin
from fragrance_rater.models.house_intake import HouseSubmission

PREFIX = "/api/v1/house-intake"
HOUSE_A = {"X-Authentik-Username": "maison-a-rep"}
MANAGER = {"X-Authentik-Username": "manager"}
FAMILY = {"X-Authentik-Username": "family-member"}


@pytest.fixture(autouse=True)
def intake_accounts(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])
    monkeypatch.setattr(settings, "house_contributors", {"maison-a-rep": "Maison A"})


def house_payload(**overrides):
    payload = {
        "fragrance_name": "Cèdre Nocturne",
        "concentration": "EDP",
        "launch_year": 2019,
        "availability": "in_production",
        "marketed_for": "Unisex",
        "perfumers": ["Ana Ruiz", "Luc Martin"],
        "product_url": "https://maison-a.example/cedre",
        "notes": [
            {"text": "Bergamote de Calabre", "position": "top"},
            {"text": "Musk", "position": "base"},
        ],
        "accords": ["woody"],
        "permission_scope": "retain_for_qc_only",
        "contact_name": "Ana Ruiz",
        "contact_role": "Founder",
        "attested": True,
    }
    payload.update(overrides)
    return payload


async def submitted(client, **overrides):
    draft = await client.post(
        f"{PREFIX}/submissions", json=house_payload(**overrides), headers=HOUSE_A
    )
    assert draft.status_code == 201, draft.text
    response = await client.post(
        f"{PREFIX}/submissions/{draft.json()['id']}/submit", headers=HOUSE_A
    )
    assert response.status_code == 200, response.text
    return response.json()


async def catalog(client, **overrides):
    data = {
        "name": "Cedre Nocturne",
        "brand": "Maison A",
        "concentration": "Eau de Parfum",
        "launch_year": 2018,
        "gender_target": "Unisex",
        "primary_family": "Woody",
        "subfamily": "Dry Woods",
    }
    data.update(overrides)
    response = await client.post("/api/v1/fragrances", json=data, headers=MANAGER)
    assert response.status_code == 201, response.text
    return response.json()


async def stored(model, row_id):
    from fragrance_rater.main import app

    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        return await session.get(model, row_id)
    finally:
        await sessions.aclose()


async def attributions(fragrance_id):
    from fragrance_rater.main import app

    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        rows = await session.execute(
            select(Perfumer.name, VersionPerfumer.source_url)
            .join(Perfumer, Perfumer.id == VersionPerfumer.perfumer_id)
            .where(VersionPerfumer.fragrance_id == fragrance_id)
            .order_by(Perfumer.name)
        )
        return [tuple(row) for row in rows]
    finally:
        await sessions.aclose()


def adopt_existing(fragrance_id, **overrides):
    decision = {
        "target": {"kind": "existing", "fragrance_id": fragrance_id},
        "confirmed_fields": [
            "name",
            "brand",
            "concentration",
            "launch_year",
            "gender_target",
        ],
        "apply_updates": ["launch_year"],
        "record_perfumers": True,
    }
    decision.update(overrides)
    return decision


@pytest.mark.asyncio
async def test_only_managers_review(test_app):
    record = await submitted(test_app)
    for headers in (HOUSE_A, FAMILY):
        path = f"{PREFIX}/submissions/{record['id']}"
        assert (
            await test_app.get(f"{path}/review", headers=headers)
        ).status_code == 403
        response = await test_app.post(
            f"{path}/decline", json={"reason": "No"}, headers=headers
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_managers_cannot_see_drafts(test_app):
    draft = await test_app.post(
        f"{PREFIX}/submissions", json=house_payload(), headers=HOUSE_A
    )
    path = f"{PREFIX}/submissions/{draft.json()['id']}"
    assert (await test_app.get(path, headers=MANAGER)).status_code == 404
    assert (await test_app.get(f"{path}/review", headers=MANAGER)).status_code == 404


@pytest.mark.asyncio
async def test_review_context_proposes_facts_and_compares_candidates(test_app):
    match = await catalog(test_app)
    await catalog(test_app, name="Iris Poudré", concentration="EDT")
    await catalog(test_app, brand="Another House", name="Unrelated")
    record = await submitted(test_app)

    response = await test_app.get(
        f"{PREFIX}/submissions/{record['id']}/review", headers=MANAGER
    )
    assert response.status_code == 200
    context = response.json()
    assert context["proposed"] == {
        "name": "Cèdre Nocturne",
        "brand": "Maison A",
        "line": None,
        "concentration": "EDP",
        "launch_year": 2019,
        "market_status": "in_production",
        "gender_target": "Unisex",
        "gtins": [],
    }
    names = [candidate["name"] for candidate in context["candidates"]]
    assert "Unrelated" not in names
    first = context["candidates"][0]
    assert first["id"] == match["id"]
    # "Cedre" lacks the accent, so the name differs; "Eau de Parfum" is EDP.
    assert first["comparison"] == {
        "name": "differs",
        "brand": "same",
        "line": "house_silent",
        "concentration": "same",
        "launch_year": "differs",
        "market_status": "differs",
        "gender_target": "same",
    }
    assert first["in_calibration"] is False
    assert first["gtins"] == []

    searched = await test_app.get(
        f"{PREFIX}/submissions/{record['id']}/review",
        params={"q": "Unrelated"},
        headers=MANAGER,
    )
    assert [c["name"] for c in searched.json()["candidates"]] == ["Unrelated"]


@pytest.mark.asyncio
async def test_adopt_writes_snapshot_with_house_permission(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    record = await submitted(test_app)

    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(fragrance["id"], review_note="Matches our bottle."),
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    adopted = response.json()
    assert adopted["review_status"] == "adopted"
    assert adopted["reviewed_by"] == "manager"
    assert adopted["fragrance_id"] == fragrance["id"]
    assert adopted["review_note"] == "Matches our bottle."

    snapshot = await stored(SourceSnapshot, adopted["source_snapshot_id"])
    assert snapshot.fragrance_id == fragrance["id"]
    assert snapshot.source_type == "manufacturer_provided"
    assert snapshot.permission_state == "retain_for_qc_only"
    assert snapshot.fields == [
        "name",
        "brand",
        "concentration",
        "launch_year",
        "gender_target",
    ]
    assert snapshot.source_url == "https://maison-a.example/cedre"
    assert "Ana Ruiz, Founder, Maison A" in snapshot.source_reference
    assert snapshot.verification_status == "verified"
    assert snapshot.payload["house_submission_id"] == record["id"]
    assert snapshot.payload["declared"]["notes"][0] == {
        "text": "Bergamote de Calabre",
        "position": "top",
    }
    assert snapshot.payload["declared_labels"][:2] == [
        {
            "label_kind": "note",
            "raw_text": "Bergamote de Calabre",
            "position": "top",
            "source_order": 0,
        },
        {
            "label_kind": "note",
            "raw_text": "Musk",
            "position": "base",
            "source_order": 0,
        },
    ]

    updated = (
        await test_app.get(f"/api/v1/fragrances/{fragrance['id']}", headers=MANAGER)
    ).json()
    assert updated["launch_year"] == 2019
    # The catalog API does not surface perfumers yet (documented gap in
    # api/fragrances.py), so read the attribution rows directly.
    assert await attributions(fragrance["id"]) == [
        ("Ana Ruiz", "https://maison-a.example/cedre"),
        ("Luc Martin", "https://maison-a.example/cedre"),
    ]


@pytest.mark.asyncio
async def test_house_sees_outcome_without_internal_ids(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    record = await submitted(test_app)
    await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(fragrance["id"]),
        headers=MANAGER,
    )
    seen = (
        await test_app.get(f"{PREFIX}/submissions/{record['id']}", headers=HOUSE_A)
    ).json()
    assert seen["review_status"] == "adopted"
    assert seen["reviewed_at"] is not None
    assert seen["reviewed_by"] is None
    assert seen["fragrance_id"] is None
    assert seen["source_snapshot_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"concentration": "EDT"}, "different version"),
        ({"launch_year": 2018}, None),
    ],
)
async def test_refused_adoption_leaves_record_pending(test_app, overrides, fragment):
    fragrance = await catalog(test_app, name="Cèdre Nocturne", **overrides)
    record = await submitted(test_app)
    decision = adopt_existing(fragrance["id"], apply_updates=[])
    if fragment is None:
        # Launch year matches, so not applying it is fine; break something else.
        decision["confirmed_fields"] = ["name", "concentration"]
        decision["apply_updates"] = ["launch_year"]
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt", json=decision, headers=MANAGER
    )
    assert response.status_code == 422
    if fragment:
        assert fragment in response.json()["detail"]["message"]
    row = await stored(HouseSubmission, record["id"])
    assert row.review_status == "pending"
    assert row.source_snapshot_id is None


@pytest.mark.asyncio
async def test_a_differing_year_must_be_applied_to_be_accepted(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    record = await submitted(test_app)
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(fragrance["id"], apply_updates=[]),
        headers=MANAGER,
    )
    assert response.status_code == 422
    assert "apply it" in response.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_a_fact_the_house_did_not_give_cannot_be_confirmed(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    record = await submitted(test_app, marketed_for="not_specified")
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(fragrance["id"]),
        headers=MANAGER,
    )
    assert response.status_code == 422
    assert "did not give" in response.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_adopting_as_a_new_version_uses_the_house_values(test_app):
    record = await submitted(
        test_app, marketed_for="not_specified", concentration="EXTRAIT"
    )
    new_target = {
        "kind": "new",
        "version_key": "original",
        "primary_family": "Woody",
        "subfamily": "Dry Woods",
    }
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json={"target": new_target},
        headers=MANAGER,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "GENDER_TARGET_REQUIRED"

    new_target["gender_target"] = "Feminine"
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json={"target": new_target},
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    adopted = response.json()
    created = (
        await test_app.get(
            f"/api/v1/fragrances/{adopted['fragrance_id']}", headers=MANAGER
        )
    ).json()
    assert (created["name"], created["brand"], created["concentration"]) == (
        "Cèdre Nocturne",
        "Maison A",
        "Extrait",
    )
    assert created["launch_year"] == 2019
    assert created["gender_target"] == "Feminine"
    snapshot = await stored(SourceSnapshot, adopted["source_snapshot_id"])
    # The manager chose the gender target, so the house is not cited for it.
    assert snapshot.fields == [
        "name",
        "brand",
        "concentration",
        "launch_year",
        "market_status",
    ]
    assert created["market_status"] == "in_production"


@pytest.mark.asyncio
async def test_a_duplicate_new_version_is_refused(test_app):
    await catalog(
        test_app, name="Cèdre Nocturne", concentration="EDP", version_key="original"
    )
    record = await submitted(test_app)
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json={
            "target": {
                "kind": "new",
                "version_key": "original",
                "primary_family": "Woody",
                "subfamily": "Dry Woods",
            }
        },
        headers=MANAGER,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "CATALOG_CONFLICT"
    row = await stored(HouseSubmission, record["id"])
    assert row.review_status == "pending"


@pytest.mark.asyncio
async def test_decline_records_a_reason_the_house_sees(test_app):
    record = await submitted(test_app)
    path = f"{PREFIX}/submissions/{record['id']}"
    blank = await test_app.post(
        f"{path}/decline", json={"reason": "  "}, headers=MANAGER
    )
    assert blank.status_code == 422
    response = await test_app.post(
        f"{path}/decline",
        json={"reason": "We need the barcode to tell this from the 2012 release."},
        headers=MANAGER,
    )
    assert response.status_code == 200
    assert response.json()["reviewed_by"] == "manager"
    seen = (await test_app.get(path, headers=HOUSE_A)).json()
    assert seen["review_status"] == "declined"
    assert seen["review_note"].startswith("We need the barcode")
    assert seen["reviewed_by"] is None


@pytest.mark.asyncio
async def test_record_can_be_reviewed_only_once(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    record = await submitted(test_app)
    path = f"{PREFIX}/submissions/{record['id']}"
    first = await test_app.post(
        f"{path}/adopt", json=adopt_existing(fragrance["id"]), headers=MANAGER
    )
    assert first.status_code == 200
    again = await test_app.post(
        f"{path}/adopt", json=adopt_existing(fragrance["id"]), headers=MANAGER
    )
    assert again.status_code == 409
    declined = await test_app.post(
        f"{path}/decline", json={"reason": "Changed my mind"}, headers=MANAGER
    )
    assert declined.status_code == 409


@pytest.mark.asyncio
async def test_submitted_correction_supersedes_pending_original(test_app):
    original = await submitted(test_app)
    correction = await test_app.post(
        f"{PREFIX}/submissions/{original['id']}/revise", headers=HOUSE_A
    )
    correction_id = correction.json()["id"]
    await test_app.put(
        f"{PREFIX}/submissions/{correction_id}",
        json=house_payload(launch_year=2020),
        headers=HOUSE_A,
    )
    # A correction still in draft does not take the original out of review.
    still = (
        await test_app.get(f"{PREFIX}/submissions/{original['id']}", headers=MANAGER)
    ).json()
    assert still["review_status"] == "pending"

    await test_app.post(f"{PREFIX}/submissions/{correction_id}/submit", headers=HOUSE_A)
    replaced = (
        await test_app.get(f"{PREFIX}/submissions/{original['id']}", headers=MANAGER)
    ).json()
    assert replaced["review_status"] == "superseded"
    response = await test_app.post(
        f"{PREFIX}/submissions/{original['id']}/decline",
        json={"reason": "Stale"},
        headers=MANAGER,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_correction_of_an_adopted_record_keeps_its_outcome(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    original = await submitted(test_app)
    await test_app.post(
        f"{PREFIX}/submissions/{original['id']}/adopt",
        json=adopt_existing(fragrance["id"]),
        headers=MANAGER,
    )
    correction = await test_app.post(
        f"{PREFIX}/submissions/{original['id']}/revise", headers=HOUSE_A
    )
    correction_id = correction.json()["id"]
    await test_app.put(
        f"{PREFIX}/submissions/{correction_id}", json=house_payload(), headers=HOUSE_A
    )
    await test_app.post(f"{PREFIX}/submissions/{correction_id}/submit", headers=HOUSE_A)
    kept = await stored(HouseSubmission, original["id"])
    assert kept.review_status == "adopted"
    fresh = await stored(HouseSubmission, correction_id)
    assert fresh.review_status == "pending"


@pytest.mark.asyncio
async def test_unknown_or_archived_fragrance_is_refused(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    await test_app.delete(f"/api/v1/fragrances/{fragrance['id']}", headers=MANAGER)
    record = await submitted(test_app)
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(fragrance["id"]),
        headers=MANAGER,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "UNKNOWN_FRAGRANCE"


@pytest.mark.asyncio
async def test_adopting_a_correction_does_not_duplicate_attributions(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    original = await submitted(test_app)
    await test_app.post(
        f"{PREFIX}/submissions/{original['id']}/adopt",
        json=adopt_existing(fragrance["id"]),
        headers=MANAGER,
    )
    correction = await test_app.post(
        f"{PREFIX}/submissions/{original['id']}/revise", headers=HOUSE_A
    )
    correction_id = correction.json()["id"]
    await test_app.put(
        f"{PREFIX}/submissions/{correction_id}",
        json=house_payload(perfumers=["Ana Ruiz", "Mei Chen"]),
        headers=HOUSE_A,
    )
    await test_app.post(f"{PREFIX}/submissions/{correction_id}/submit", headers=HOUSE_A)
    response = await test_app.post(
        f"{PREFIX}/submissions/{correction_id}/adopt",
        json=adopt_existing(fragrance["id"], apply_updates=[]),
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    assert [name for name, _ in await attributions(fragrance["id"])] == [
        "Ana Ruiz",
        "Luc Martin",
        "Mei Chen",
    ]


GTIN = "3508440005953"
GTIN_14 = "03508440005953"


async def put_in_calibration(fragrance_id):
    from fragrance_rater.main import app

    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        program = Program(name="Baseline", version="1")
        session.add(program)
        await session.flush()
        session.add(
            Membership(
                program_id=program.id,
                fragrance_id=fragrance_id,
                role="UNIVERSAL_BASELINE",
                group_name="Baseline",
            )
        )
        await session.commit()
    finally:
        await sessions.aclose()


@pytest.mark.asyncio
async def test_line_and_market_status_can_be_applied(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne", launch_year=2019)
    record = await submitted(test_app, line="Les Bois", availability="discontinued")
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(
            fragrance["id"],
            confirmed_fields=["name", "line", "market_status", "launch_year"],
            apply_updates=["line", "market_status"],
        ),
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    updated = (
        await test_app.get(f"/api/v1/fragrances/{fragrance['id']}", headers=MANAGER)
    ).json()
    assert (updated["line"], updated["market_status"]) == ("Les Bois", "discontinued")
    snapshot = await stored(SourceSnapshot, response.json()["source_snapshot_id"])
    assert snapshot.fields == ["name", "line", "launch_year", "market_status"]


@pytest.mark.asyncio
async def test_calibration_locks_identity_updates(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    await put_in_calibration(fragrance["id"])
    record = await submitted(test_app, line="Les Bois")
    context = (
        await test_app.get(
            f"{PREFIX}/submissions/{record['id']}/review", headers=MANAGER
        )
    ).json()
    assert context["candidates"][0]["in_calibration"] is True

    blocked = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(fragrance["id"]),
        headers=MANAGER,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["error"] == "CALIBRATION_LOCKED"
    unchanged = (
        await test_app.get(f"/api/v1/fragrances/{fragrance['id']}", headers=MANAGER)
    ).json()
    assert unchanged["launch_year"] == 2018
    assert (await stored(HouseSubmission, record["id"])).review_status == "pending"

    # Facts outside the lock still apply.
    allowed = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(
            fragrance["id"],
            confirmed_fields=["name", "brand", "line"],
            apply_updates=["line"],
        ),
        headers=MANAGER,
    )
    assert allowed.status_code == 200, allowed.text


@pytest.mark.asyncio
async def test_barcodes_are_recorded_with_evidence_and_rank_matches(test_app):
    fragrance = await catalog(test_app, name="Cèdre Nocturne")
    record = await submitted(test_app, gtins=[GTIN])
    response = await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(fragrance["id"], record_barcodes=True),
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    link = await stored(FragranceGtin, GTIN_14)
    assert link.fragrance_id == fragrance["id"]
    assert link.source_snapshot_id == response.json()["source_snapshot_id"]

    # A later submission carrying the same barcode finds this version first,
    # even under a name the catalog search alone would not match.
    await catalog(test_app, name="Another Maison A scent")
    later = await submitted(test_app, gtins=[GTIN], fragrance_name="Nuit de Cèdre")
    context = (
        await test_app.get(
            f"{PREFIX}/submissions/{later['id']}/review", headers=MANAGER
        )
    ).json()
    assert context["proposed"]["gtins"] == [GTIN_14]
    assert context["candidates"][0]["id"] == fragrance["id"]
    assert context["candidates"][0]["gtin_matches"] == [GTIN_14]


@pytest.mark.asyncio
async def test_a_barcode_on_another_version_is_refused(test_app):
    first = await catalog(test_app, name="Cèdre Nocturne")
    record = await submitted(test_app, gtins=[GTIN])
    await test_app.post(
        f"{PREFIX}/submissions/{record['id']}/adopt",
        json=adopt_existing(first["id"], record_barcodes=True),
        headers=MANAGER,
    )
    other = await catalog(test_app, name="Cèdre Nocturne", version_key="2024")
    again = await submitted(test_app, gtins=[GTIN])
    response = await test_app.post(
        f"{PREFIX}/submissions/{again['id']}/adopt",
        json=adopt_existing(other["id"], record_barcodes=True),
        headers=MANAGER,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "GTIN_CONFLICT"
    assert "version legacy" in response.json()["detail"]["message"]
    assert (await stored(FragranceGtin, GTIN_14)).fragrance_id == first["id"]
    assert (await stored(HouseSubmission, again["id"])).review_status == "pending"
