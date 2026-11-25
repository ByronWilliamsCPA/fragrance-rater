"""F1 group-blotter programs over HTTP.

One physical blotter per sample is passed around the evaluators, so they share a
sample's blind code and the session order. The scores are marked
``group_shared_blotter`` and, by the owner's decision, stay eligible for
training. Each evaluator's own spray-to-first-smell pair is checked against the
2-minute ceiling; when it would be exceeded the facilitator sprays a new blotter
of the same sample (same blind code).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text

from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.main import app

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
GROUP = "shared-triples-group-blotter-v1"
SHARED = "shared-triples-latin-rotation-v1"


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


def _at(**delta: float) -> str:
    """A time ``delta`` before now."""
    return (datetime.now(UTC) - timedelta(**delta)).isoformat()


async def _post(client: Any, url: str, body: dict[str, Any] | None = None) -> Any:
    response = await client.post(url, json=body or {}, headers=MANAGER)
    assert response.status_code in {200, 201}, (url, response.text)
    return response.json()


async def _build_program(client: Any, blotter_mode: str) -> tuple[str, list[str]]:
    """An active program of four baseline samples, one repeat and one holdout."""
    fragrance_ids = []
    for index in range(5):
        fragrance = await _post(
            client,
            "/api/v1/fragrances",
            {
                "name": f"Concealed {index}",
                "brand": "Concealed house",
                "concentration": "EDT",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        fragrance_ids.append(fragrance["id"])
    program = await _post(
        client,
        f"{PREFIX}/programs",
        {"name": "Group", "version": "1", "blotter_mode": blotter_mode},
    )
    program_id = program["id"]
    member_ids = []
    for fragrance_id in fragrance_ids[:4]:
        member = await _post(
            client,
            f"{PREFIX}/programs/{program_id}/members",
            {
                "fragrance_id": fragrance_id,
                "role": "UNIVERSAL_BASELINE",
                "identity_evidence": "Verified",
            },
        )
        member_ids.append(member["id"])
    await _post(
        client,
        f"{PREFIX}/programs/{program_id}/members",
        {
            "fragrance_id": fragrance_ids[0],
            "role": "HIDDEN_REPEAT",
            "repeat_of_id": member_ids[0],
            "identity_evidence": "Same decant",
        },
    )
    await _post(
        client,
        f"{PREFIX}/programs/{program_id}/members",
        {
            "fragrance_id": fragrance_ids[4],
            "role": "HOLDOUT",
            "identity_evidence": "Verified",
        },
    )
    reviewers = []
    for name in ("First", "Second"):
        reviewer = await _post(client, "/api/v1/reviewers", {"name": name})
        reviewers.append(reviewer["id"])
    await _post(client, f"{PREFIX}/programs/{program_id}/activate")
    return program_id, reviewers


async def _enroll(
    client: Any, program_id: str, reviewer_id: str, algorithm: str = GROUP
) -> Any:
    return await client.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer_id,
            "recorder_usernames": ["recorder"],
            "session_size": 1,
            "randomization_algorithm": algorithm,
        },
        headers=MANAGER,
    )


@pytest_asyncio.fixture
async def group(test_app: Any, backdate_sessions: Any) -> dict[str, Any]:
    """Two evaluators enrolled on one SHARED_GROUP program."""
    program_id, reviewers = await _build_program(test_app, "SHARED_GROUP")
    views = []
    for reviewer_id in reviewers:
        enrolled = await _enroll(test_app, program_id, reviewer_id)
        assert enrolled.status_code == 201, enrolled.text
        view = await test_app.get(
            f"{PREFIX}/enrollments/{enrolled.json()['id']}", headers=RECORDER
        )
        assert view.status_code == 200, view.text
        views.append({"enrollment_id": enrolled.json()["id"], **view.json()})
    await backdate_sessions()
    return {"program_id": program_id, "views": views}


def _exposure_url(presentation: dict[str, Any]) -> str:
    return f"{PREFIX}/presentations/{presentation['id']}/exposure"


async def _view_codes(client: Any, enrollment_id: str) -> list[str]:
    view = await client.get(f"{PREFIX}/enrollments/{enrollment_id}", headers=RECORDER)
    return [p["blind_code"] for p in view.json()["presentations"]]


# --- program setup ---------------------------------------------------------


@pytest.mark.asyncio
async def test_the_program_list_reports_the_mode(test_app: Any) -> None:
    program_id, _ = await _build_program(test_app, "SHARED_GROUP")
    listing = await test_app.get(f"{PREFIX}/programs", headers=MANAGER)
    mode = {row["id"]: row["blotter_mode"] for row in listing.json()}
    assert mode[program_id] == "SHARED_GROUP"
    plain = await _post(test_app, f"{PREFIX}/programs", {"name": "Old", "version": "1"})
    listing = await test_app.get(f"{PREFIX}/programs", headers=MANAGER)
    assert {r["id"]: r["blotter_mode"] for r in listing.json()}[plain["id"]] == (
        "INDIVIDUAL"
    )


@pytest.mark.asyncio
async def test_the_mode_is_a_manager_choice_that_locks_at_first_enrollment(
    test_app: Any,
) -> None:
    program_id, reviewers = await _build_program(test_app, "INDIVIDUAL")
    url = f"{PREFIX}/programs/{program_id}/blotter-mode"
    denied = await test_app.put(
        url, json={"blotter_mode": "SHARED_GROUP"}, headers=RECORDER
    )
    assert denied.status_code == 403
    bad = await test_app.put(url, json={"blotter_mode": "OTHER"}, headers=MANAGER)
    assert bad.status_code == 422
    changed = await test_app.put(
        url, json={"blotter_mode": "SHARED_GROUP"}, headers=MANAGER
    )
    assert changed.status_code == 200
    assert changed.json() == {"id": program_id, "blotter_mode": "SHARED_GROUP"}
    assert (await _enroll(test_app, program_id, reviewers[0])).status_code == 201
    locked = await test_app.put(
        url, json={"blotter_mode": "INDIVIDUAL"}, headers=MANAGER
    )
    assert locked.status_code == 409
    missing = await test_app.put(
        f"{PREFIX}/programs/nope/blotter-mode",
        json={"blotter_mode": "INDIVIDUAL"},
        headers=MANAGER,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_a_group_program_only_enrolls_with_the_group_algorithm(
    test_app: Any,
) -> None:
    program_id, reviewers = await _build_program(test_app, "SHARED_GROUP")
    for algorithm in ("system-random-shuffle-v1", SHARED):
        refused = await _enroll(test_app, program_id, reviewers[0], algorithm)
        assert refused.status_code == 409
        assert "SHARED_GROUP" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_an_individual_program_refuses_the_group_algorithm(
    test_app: Any,
) -> None:
    program_id, reviewers = await _build_program(test_app, "INDIVIDUAL")
    refused = await _enroll(test_app, program_id, reviewers[0], GROUP)
    assert refused.status_code == 409


@pytest.mark.asyncio
async def test_an_individual_program_enrolls_exactly_as_before(test_app: Any) -> None:
    program_id, reviewers = await _build_program(test_app, "INDIVIDUAL")
    first = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={"reviewer_id": reviewers[0], "recorder_usernames": ["recorder"]},
        headers=MANAGER,
    )
    second = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={"reviewer_id": reviewers[1], "recorder_usernames": ["recorder"]},
        headers=MANAGER,
    )
    assert first.status_code == second.status_code == 201
    one = await _view_codes(test_app, first.json()["id"])
    two = await _view_codes(test_app, second.json()["id"])
    assert set(one).isdisjoint(two)


# --- shared codes and the participant view ---------------------------------


@pytest.mark.asyncio
async def test_evaluators_share_codes_and_order(group: dict[str, Any]) -> None:
    first, second = group["views"]
    assert [p["blind_code"] for p in first["presentations"]] == [
        p["blind_code"] for p in second["presentations"]
    ]
    assert [p["position"] for p in first["presentations"]] == [
        p["position"] for p in second["presentations"]
    ]
    assert first["blotter_mode"] == second["blotter_mode"] == "SHARED_GROUP"


@pytest.mark.asyncio
async def test_the_enrollment_lists_report_the_mode(
    test_app: Any, group: dict[str, Any]
) -> None:
    mine = await test_app.get(f"{PREFIX}/enrollments", headers=RECORDER)
    assert {row["blotter_mode"] for row in mine.json()} == {"SHARED_GROUP"}
    managed = await test_app.get(f"{PREFIX}/manager/enrollments", headers=MANAGER)
    assert {row["blotter_mode"] for row in managed.json()} == {"SHARED_GROUP"}


@pytest.mark.asyncio
async def test_an_individual_enrollment_reports_the_individual_mode(
    test_app: Any,
) -> None:
    program_id, reviewers = await _build_program(test_app, "INDIVIDUAL")
    enrolled = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={"reviewer_id": reviewers[0], "recorder_usernames": ["recorder"]},
        headers=MANAGER,
    )
    view = await test_app.get(
        f"{PREFIX}/enrollments/{enrolled.json()['id']}", headers=RECORDER
    )
    assert view.json()["blotter_mode"] == "INDIVIDUAL"


# --- the informational flag ------------------------------------------------


async def _session_flags(client: Any, session_id: str) -> list[dict[str, Any]]:
    response = await client.get(
        f"{PREFIX}/sessions/{session_id}/quality-flags", headers=RECORDER
    )
    assert response.status_code == 200, response.text
    return list(response.json())


@pytest.mark.asyncio
async def test_every_session_is_flagged_automatically(
    test_app: Any, group: dict[str, Any]
) -> None:
    for view in group["views"]:
        session_ids = {p["session_id"] for p in view["presentations"]}
        assert len(session_ids) == 6
        for session_id in session_ids:
            flags = await _session_flags(test_app, session_id)
            assert [f["code"] for f in flags] == ["group_shared_blotter"]
            assert flags[0]["source"] == "automatic_validation"
            assert flags[0]["severity"] == "info"


@pytest.mark.asyncio
async def test_the_flag_cannot_be_raised_by_hand(
    test_app: Any, group: dict[str, Any]
) -> None:
    session_id = group["views"][0]["presentations"][0]["session_id"]
    response = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "raised",
            "source": "recorder",
            "disposition": "include",
            "target_type": "session",
            "target_id": session_id,
            "code": "group_shared_blotter",
            "severity": "info",
        },
        headers=RECORDER,
    )
    assert response.status_code == 422
    assert "automatically" in response.json()["detail"]


@pytest.mark.asyncio
async def test_only_a_manager_can_withdraw_the_flag(
    test_app: Any, group: dict[str, Any]
) -> None:
    session_id = group["views"][0]["presentations"][0]["session_id"]
    (flag,) = await _session_flags(test_app, session_id)
    body = {
        "action": "invalidated",
        "disposition": "include",
        "supersedes_id": flag["id"],
    }
    denied = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={**body, "source": "recorder"},
        headers=RECORDER,
    )
    assert denied.status_code == 403
    allowed = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={**body, "source": "manager"},
        headers=MANAGER,
    )
    assert allowed.status_code == 201, allowed.text


# --- timing: each evaluator against their own blotter ----------------------


@pytest.mark.asyncio
async def test_two_evaluators_with_different_spray_times_both_record(
    test_app: Any, group: dict[str, Any]
) -> None:
    """One blind code, two blotters sprayed at different times, both recorded."""
    first, second = (view["presentations"][0] for view in group["views"])
    assert first["blind_code"] == second["blind_code"]
    first_spray, second_spray = _at(minutes=30), _at(minutes=20)

    one = await test_app.post(
        _exposure_url(first),
        json={
            "stage": "BLOTTER",
            "sprayed_at": first_spray,
            "at": _at(minutes=29),
            "confirmed_blind_code": first["blind_code"],
        },
        headers=RECORDER,
    )
    two = await test_app.post(
        _exposure_url(second),
        json={
            "stage": "BLOTTER",
            "sprayed_at": second_spray,
            "at": _at(minutes=19),
            "confirmed_blind_code": second["blind_code"],
        },
        headers=RECORDER,
    )

    assert one.status_code == two.status_code == 200, (one.text, two.text)
    assert one.json()["ceiling_flag_id"] is None
    assert two.json()["ceiling_flag_id"] is None
    stored = []
    for view, presentation in zip(group["views"], (first, second), strict=True):
        rows = (
            await test_app.get(
                f"{PREFIX}/enrollments/{view['enrollment_id']}", headers=RECORDER
            )
        ).json()["presentations"]
        stored.append(
            next(r for r in rows if r["id"] == presentation["id"])["presented_at"]
        )
    assert None not in stored
    assert stored[0] != stored[1]
    for presentation, spray in ((first, first_spray), (second, second_spray)):
        observation = await test_app.post(
            f"{PREFIX}/presentations/{presentation['id']}/observations",
            json={
                "stage": "BLOTTER",
                "detected": True,
                "liking": 6,
                "sprayed_at": spray,
                "observed_at": _at(minutes=5),
                "confirmed_blind_code": presentation["blind_code"],
                "idempotency_key": f"group-{presentation['id']}",
            },
            headers=RECORDER,
        )
        assert observation.status_code == 201, observation.text


@pytest.mark.asyncio
async def test_the_ceiling_is_judged_per_evaluator(
    test_app: Any, group: dict[str, Any]
) -> None:
    """A late smell flags that evaluator only; the other stays within 2 minutes."""
    first, second = (view["presentations"][0] for view in group["views"])
    on_time = await test_app.post(
        _exposure_url(first),
        json={"stage": "BLOTTER", "sprayed_at": _at(minutes=10), "at": _at(minutes=9)},
        headers=RECORDER,
    )
    late = await test_app.post(
        _exposure_url(second),
        json={"stage": "BLOTTER", "sprayed_at": _at(minutes=10), "at": _at(minutes=6)},
        headers=RECORDER,
    )
    assert on_time.json()["ceiling_flag_id"] is None
    assert late.json()["ceiling_flag_id"] is not None
    flags = await _session_flags(test_app, second["session_id"])
    codes = {f["code"] for f in flags}
    assert codes == {"group_shared_blotter", "spray_to_smell_ceiling_exceeded"}
    assert {f["code"] for f in await _session_flags(test_app, first["session_id"])} == {
        "group_shared_blotter"
    }


# --- training eligibility is untouched ------------------------------------


async def _training_rows() -> set[str]:
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        return set(await session.scalars(text("SELECT row_id FROM v_training_rows")))
    finally:
        await sessions.aclose()


async def _observe_and_lock(client: Any, presentation: dict[str, Any]) -> str:
    observed = await client.post(
        f"{PREFIX}/presentations/{presentation['id']}/observations",
        json={"stage": "BLOTTER", "detected": True, "liking": 6},
        headers=RECORDER,
    )
    assert observed.status_code == 201, observed.text
    locked = await client.post(
        f"{PREFIX}/presentations/{presentation['id']}/lock/BLOTTER", headers=RECORDER
    )
    assert locked.status_code == 200, locked.text
    return str(observed.json()["id"])


@pytest.mark.asyncio
async def test_group_sessions_stay_trainable_and_in_the_training_view(
    test_app: Any, group: dict[str, Any]
) -> None:
    rows = [
        await _observe_and_lock(test_app, view["presentations"][0])
        for view in group["views"]
    ]

    assert set(rows) <= await _training_rows()
    for view in group["views"]:
        linkage = await test_app.get(
            f"{PREFIX}/enrollments/{view['enrollment_id']}/linkage", headers=MANAGER
        )
        assert {r["training_eligibility"] for r in linkage.json()} == {"eligible"}


@pytest.mark.asyncio
async def test_an_ordinary_flag_still_demotes_a_group_row(
    test_app: Any, group: dict[str, Any]
) -> None:
    """Only the informational code is exempt; other quality flags still demote."""
    presentation = group["views"][0]["presentations"][0]
    row = await _observe_and_lock(test_app, presentation)
    assert row in await _training_rows()

    flagged = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "raised",
            "source": "recorder",
            "disposition": "review",
            "target_type": "presentation",
            "target_id": presentation["id"],
            "code": "competing_odor",
            "severity": "minor",
        },
        headers=RECORDER,
    )

    assert flagged.status_code == 201, flagged.text
    assert flagged.json()["training_eligibility_changes"] == 1
    assert row not in await _training_rows()


@pytest.mark.asyncio
async def test_closing_the_flag_changes_no_row(
    test_app: Any, group: dict[str, Any]
) -> None:
    """Withdrawing or resolving the informational flag neither demotes nor holds."""
    presentation = group["views"][0]["presentations"][0]
    row = await _observe_and_lock(test_app, presentation)
    (flag,) = await _session_flags(test_app, presentation["session_id"])

    resolved = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "resolved",
            "source": "manager",
            "disposition": "include",
            "supersedes_id": flag["id"],
            "explanation": "Reviewed the group session",
        },
        headers=MANAGER,
    )

    assert resolved.status_code == 201, resolved.text
    assert resolved.json().get("training_eligibility_changes", 0) == 0
    assert row in await _training_rows()
    linkage = await test_app.get(
        f"{PREFIX}/enrollments/{group['views'][0]['enrollment_id']}/linkage",
        headers=MANAGER,
    )
    assert {r["training_eligibility"] for r in linkage.json()} == {"eligible"}


@pytest.mark.asyncio
async def test_the_evidence_export_names_the_group_flag(
    test_app: Any, group: dict[str, Any]
) -> None:
    """The export keeps the rows and says the evaluator was in a group session."""
    presentation = group["views"][0]["presentations"][0]
    row = await _observe_and_lock(test_app, presentation)

    response = await test_app.get(
        f"{PREFIX}/enrollments/{group['views'][0]['enrollment_id']}/evidence-export",
        headers=MANAGER,
    )

    assert response.status_code == 200, response.text
    exported = response.json()
    assert exported["enrollment"]["group_shared_blotter"] is True
    assert exported["enrollment"]["non_blind"] is False
    observations = {
        observation["id"]
        for session in exported["sessions"]
        for item in session["presentations"]
        for observation in item["observations"]
    }
    assert observations == {row}
    assert all(
        any(f["code"] == "group_shared_blotter" for f in session["quality_flags"])
        for session in exported["sessions"]
    )


@pytest.mark.asyncio
async def test_an_individual_export_is_not_marked(test_app: Any) -> None:
    program_id, reviewers = await _build_program(test_app, "INDIVIDUAL")
    enrolled = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={"reviewer_id": reviewers[0], "recorder_usernames": ["recorder"]},
        headers=MANAGER,
    )
    response = await test_app.get(
        f"{PREFIX}/enrollments/{enrolled.json()['id']}/evidence-export",
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    assert response.json()["enrollment"]["group_shared_blotter"] is False
