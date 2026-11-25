"""F1: the non-blind quality flag for the evaluator who holds the mapping.

``docs/planning/gates/f1.md`` and the ADR-009 2026-09-21 amendment: that
evaluator's rows carry a ``non_blind`` flag, are excluded from blind-baseline
training, and stay in evaluation. Driven through the real routes, with a second
(blind) evaluator in the same program to prove the flag stays on its enrollment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.main import app
from fragrance_rater.ml.training_view import training_manifest

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"
PREFIX = f"{API}/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
OUTSIDER = {"X-Authentik-Username": "outsider"}
REASON = "Declared mapping holder: sprays, times, transcribes and controls the reveal"


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


async def _post(client: AsyncClient, url: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=body, headers=MANAGER)
    assert response.status_code in {200, 201}, (url, response.text)
    return dict(response.json())


async def _enroll(client: AsyncClient, program_id: str, name: str) -> dict[str, Any]:
    reviewer = await _post(client, f"{API}/reviewers", {"name": name})
    enrollment = await _post(
        client,
        f"{PREFIX}/programs/{program_id}/enroll",
        {
            "reviewer_id": reviewer["id"],
            "recorder_usernames": ["recorder"],
            # Sessions of two: 3 baseline + 1 holdout is three sessions.
            "session_size": 2,
        },
    )
    # The holdout opens only after this evaluator's checkpoint (the F1 holdout
    # gate); an ENROLLMENT-policy program may freeze it at any time.
    await _post(
        client,
        f"{PREFIX}/enrollments/{enrollment['id']}/checkpoints",
        {"algorithm_version": "test"},
    )
    view = (
        await client.get(f"{PREFIX}/enrollments/{enrollment['id']}", headers=RECORDER)
    ).json()
    sessions: dict[str, list[str]] = {}
    for presentation in view["presentations"]:
        sessions.setdefault(presentation["session_id"], []).append(presentation["id"])
    return {
        "reviewer_id": reviewer["id"],
        "enrollment_id": enrollment["id"],
        "sessions": sessions,
        "presentation_ids": [p["id"] for p in view["presentations"]],
    }


@pytest_asyncio.fixture
async def world(test_app: AsyncClient) -> dict[str, Any]:
    """One program, a holder enrollment and a blind enrollment, three sessions each."""
    program = await _post(
        test_app, f"{PREFIX}/programs", {"name": "Non-blind", "version": "1"}
    )
    for index, role in enumerate(
        ("UNIVERSAL_BASELINE", "UNIVERSAL_BASELINE", "UNIVERSAL_BASELINE", "HOLDOUT")
    ):
        fragrance = await _post(
            test_app,
            f"{API}/fragrances",
            {
                "name": f"Concealed {index}",
                "brand": "House",
                "concentration": "EDT",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        await _post(
            test_app,
            f"{PREFIX}/programs/{program['id']}/members",
            {
                "fragrance_id": fragrance["id"],
                "role": role,
                "identity_evidence": "Label verified",
                "group_name": "Holdout" if role == "HOLDOUT" else "Baseline",
            },
        )
    activated = await test_app.post(
        f"{PREFIX}/programs/{program['id']}/activate", headers=MANAGER
    )
    assert activated.status_code == 200, activated.text
    holder = await _enroll(test_app, program["id"], "Holder")
    blind = await _enroll(test_app, program["id"], "Blind")
    assert len(holder["sessions"]) == 3
    return {"holder": holder, "blind": blind}


async def _observe(client: AsyncClient, presentation_id: str) -> str:
    response = await client.post(
        f"{PREFIX}/presentations/{presentation_id}/observations",
        json={"stage": "BLOTTER", "detected": True, "liking": 5},
        headers=RECORDER,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _lock(client: AsyncClient, presentation_id: str) -> None:
    response = await client.post(
        f"{PREFIX}/presentations/{presentation_id}/lock/BLOTTER", headers=RECORDER
    )
    assert response.status_code == 200, response.text


async def _mark(
    client: AsyncClient,
    enrollment_id: str,
    *,
    headers: dict[str, str] = RECORDER,
    explanation: str = REASON,
) -> Any:
    return await client.post(
        f"{PREFIX}/enrollments/{enrollment_id}/non-blind",
        json={"explanation": explanation},
        headers=headers,
    )


async def _codes(client: AsyncClient, enrollment_id: str) -> dict[str, str]:
    response = await client.get(
        f"{PREFIX}/enrollments/{enrollment_id}/linkage", headers=MANAGER
    )
    assert response.status_code == 200, response.text
    return {row["row_id"]: row["training_eligibility"] for row in response.json()}


async def _session_flags(client: AsyncClient, session_id: str) -> list[dict[str, Any]]:
    response = await client.get(
        f"{PREFIX}/sessions/{session_id}/quality-flags", headers=MANAGER
    )
    assert response.status_code == 200, response.text
    return list(response.json())


async def _training_row_ids(reviewer_id: str) -> set[str]:
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        return {str(row["id"]) for row in await training_manifest(session, reviewer_id)}
    finally:
        await sessions.aclose()


async def _capture_locked_baseline(
    client: AsyncClient, enrollment: dict[str, Any]
) -> list[str]:
    ids = [await _observe(client, p) for p in enrollment["presentation_ids"]]
    for presentation_id in enrollment["presentation_ids"]:
        await _lock(client, presentation_id)
    return ids


@pytest.mark.asyncio
async def test_marking_flags_every_session_and_withholds_only_that_enrollment(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    holder, blind = world["holder"], world["blind"]
    await _capture_locked_baseline(test_app, holder)
    await _capture_locked_baseline(test_app, blind)
    assert set((await _codes(test_app, holder["enrollment_id"])).values()) == {
        "eligible"
    }

    response = await _mark(test_app, holder["enrollment_id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["flagged"]) == len(holder["sessions"]) == 3
    assert body["already_flagged"] == []
    assert set((await _codes(test_app, holder["enrollment_id"])).values()) == {
        "questionable"
    }
    assert set((await _codes(test_app, blind["enrollment_id"])).values()) == {
        "eligible"
    }
    # The training reader no longer sees the holder, and still sees the blind
    # evaluator.
    assert await _training_row_ids(holder["reviewer_id"]) == set()
    assert await _training_row_ids(blind["reviewer_id"]) != set()
    for session_id in holder["sessions"]:
        (flag,) = await _session_flags(test_app, session_id)
        assert flag["code"] == "non_blind"
        assert flag["source"] == "recorder"
        assert flag["open"] is True
        assert flag["explanation"] == REASON
    for session_id in blind["sessions"]:
        assert await _session_flags(test_app, session_id) == []


@pytest.mark.asyncio
async def test_marking_twice_flags_nothing_new(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    enrollment_id = world["holder"]["enrollment_id"]
    first = (await _mark(test_app, enrollment_id)).json()

    second = (await _mark(test_app, enrollment_id, headers=MANAGER)).json()

    assert second["flagged"] == []
    assert len(second["already_flagged"]) == len(first["flagged"]) == 3
    for session_id in world["holder"]["sessions"]:
        assert len(await _session_flags(test_app, session_id)) == 1


@pytest.mark.asyncio
async def test_a_manager_marking_records_the_manager_source(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    await _mark(test_app, world["holder"]["enrollment_id"], headers=MANAGER)

    (session_id, *_) = world["holder"]["sessions"]
    (flag,) = await _session_flags(test_app, session_id)
    assert flag["source"] == "manager"


@pytest.mark.asyncio
async def test_rows_written_and_locked_after_marking_never_become_eligible(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    holder = world["holder"]
    await _mark(test_app, holder["enrollment_id"])

    rows = await _capture_locked_baseline(test_app, holder)

    codes = await _codes(test_app, holder["enrollment_id"])
    assert {codes[row] for row in rows} == {"questionable"}
    assert await _training_row_ids(holder["reviewer_id"]) == set()


@pytest.mark.asyncio
async def test_resolving_cannot_release_the_rows_to_training(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    holder = world["holder"]
    rows = await _capture_locked_baseline(test_app, holder)
    await _mark(test_app, holder["enrollment_id"])
    (session_id, *_) = holder["sessions"]
    (flag,) = await _session_flags(test_app, session_id)

    release = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "resolved",
            "source": "manager",
            "disposition": "include",
            "supersedes_id": flag["id"],
            "training_outcome": "eligible",
            "explanation": "Looks fine",
        },
        headers=MANAGER,
    )

    assert release.status_code == 409, release.text
    assert "non-blind" in release.json()["detail"].lower()
    codes = await _codes(test_app, holder["enrollment_id"])
    assert {codes[row] for row in rows} == {"questionable"}

    # A resolution that leaves the decision to a manager keeps the evaluator
    # flagged: the resolved row does not make them blind.
    undecided = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "resolved",
            "source": "manager",
            "disposition": "include",
            "supersedes_id": flag["id"],
        },
        headers=MANAGER,
    )
    assert undecided.status_code == 201, undecided.text
    codes = await _codes(test_app, holder["enrollment_id"])
    assert {codes[row] for row in rows} == {"questionable"}
    assert await _training_row_ids(holder["reviewer_id"]) == set()


@pytest.mark.asyncio
async def test_only_a_manager_can_close_the_flag(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    holder = world["holder"]
    await _mark(test_app, holder["enrollment_id"])
    (session_id, *_) = holder["sessions"]
    (flag,) = await _session_flags(test_app, session_id)

    attempt = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "invalidated",
            "source": "recorder",
            "disposition": "include",
            "supersedes_id": flag["id"],
        },
        headers=RECORDER,
    )

    assert attempt.status_code == 403, attempt.text
    (still,) = await _session_flags(test_app, session_id)
    assert still["open"] is True


@pytest.mark.asyncio
async def test_invalidating_a_mistaken_flag_restores_the_rule(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    holder = world["holder"]
    rows = await _capture_locked_baseline(test_app, holder)
    await _mark(test_app, holder["enrollment_id"])
    for session_id in holder["sessions"]:
        (flag,) = await _session_flags(test_app, session_id)
        closed = await test_app.post(
            f"{PREFIX}/quality-flags",
            json={
                "action": "invalidated",
                "source": "manager",
                "disposition": "include",
                "supersedes_id": flag["id"],
                "explanation": "Marked the wrong enrollment",
            },
            headers=MANAGER,
        )
        assert closed.status_code == 201, closed.text

    codes = await _codes(test_app, holder["enrollment_id"])
    assert {codes[row] for row in rows} == {"eligible"}
    assert await _training_row_ids(holder["reviewer_id"]) != set()


@pytest.mark.asyncio
async def test_a_manager_cannot_set_non_blind_evidence_eligible(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    holder = world["holder"]
    (row, *_) = await _capture_locked_baseline(test_app, holder)
    await _mark(test_app, holder["enrollment_id"])
    url = f"{API}/training-eligibility/observation/{row}"

    refused = await test_app.put(
        url,
        json={"training_eligibility": "eligible", "reason": "Reviewed it"},
        headers=MANAGER,
    )
    withheld = await test_app.put(
        url,
        json={"training_eligibility": "withheld", "reason": "Reviewed it"},
        headers=MANAGER,
    )

    assert refused.status_code == 409, refused.text
    assert withheld.status_code == 200, withheld.text
    assert (await _codes(test_app, holder["enrollment_id"]))[row] == "withheld"


@pytest.mark.asyncio
async def test_the_evidence_export_keeps_the_rows_and_names_the_flag(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    """Retained in evaluation: the export still carries every observation."""
    holder, blind = world["holder"], world["blind"]
    rows = await _capture_locked_baseline(test_app, holder)
    await _mark(test_app, holder["enrollment_id"])

    async def export(enrollment_id: str) -> dict[str, Any]:
        response = await test_app.get(
            f"{PREFIX}/enrollments/{enrollment_id}/evidence-export",
            headers=MANAGER,
        )
        assert response.status_code == 200, response.text
        return dict(response.json())

    held = await export(holder["enrollment_id"])
    assert held["enrollment"]["non_blind"] is True
    exported = {
        observation["id"]
        for session in held["sessions"]
        for presentation in session["presentations"]
        for observation in presentation["observations"]
    }
    assert exported == set(rows)
    assert all(
        any(f["code"] == "non_blind" for f in session["quality_flags"])
        for session in held["sessions"]
    )
    assert (await export(blind["enrollment_id"]))["enrollment"]["non_blind"] is False


@pytest.mark.asyncio
async def test_marking_needs_an_assigned_recorder_or_manager_and_a_reason(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    enrollment_id = world["holder"]["enrollment_id"]

    outsider = await _mark(test_app, enrollment_id, headers=OUTSIDER)
    blank = await _mark(test_app, enrollment_id, explanation="   ")
    unknown = await _mark(test_app, "no-such-enrollment")

    assert outsider.status_code == 403
    assert blank.status_code == 422
    assert unknown.status_code == 404
    for session_id in world["holder"]["sessions"]:
        assert await _session_flags(test_app, session_id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["non_blind", "spray_to_smell_ceiling_exceeded"])
async def test_the_new_codes_are_accepted_by_the_flag_route(
    test_app: AsyncClient, world: dict[str, Any], code: str
) -> None:
    (session_id, *_) = world["holder"]["sessions"]

    response = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "raised",
            "source": "recorder",
            "disposition": "review",
            "target_type": "session",
            "target_id": session_id,
            "code": code,
            "severity": "minor",
            "explanation": "Sheet shows first smell at 7 minutes",
        },
        headers=RECORDER,
    )

    assert response.status_code == 201, response.text
