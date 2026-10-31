"""R8 PR 2: option C eligibility promotion, manager decisions, and linkage.

Every transition the owner's option C defines, driven through the real
routes (so the service, the flag write path, and the audit events are all
exercised): ordinary encounters are eligible when saved; controlled
observations are eligible once their stage is locked and no flag covers
them; a raised flag makes covered rows questionable; closing it settles
them; a manager can set eligible, withheld, or invalidated with a reason;
and no automatic rule ever overrides withheld or invalidated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
import structlog
from sqlalchemy import select

from fragrance_rater.api import calibration as calibration_api
from fragrance_rater.api import capture as capture_api
from fragrance_rater.api import training_eligibility as eligibility_api
from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.main import app
from fragrance_rater.models.calibration import Observation
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.services import training_eligibility as eligibility_service

if TYPE_CHECKING:
    from collections.abc import Iterator

    from httpx import AsyncClient

API = "/api/v1"
PREFIX = f"{API}/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
OUTSIDER = {"X-Authentik-Username": "outsider"}


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture structlog audit events from the routers and the service."""
    with structlog.testing.capture_logs() as logs:
        for module in (
            calibration_api,
            capture_api,
            eligibility_api,
            eligibility_service,
        ):
            monkeypatch.setattr(module, "logger", structlog.get_logger(module.__name__))
        yield logs


def _eligibility_events(captured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in captured
        if event.get("event") == "audit_event"
        and event.get("action") == "training_eligibility_set"
    ]


async def _post(client: AsyncClient, url: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=body, headers=MANAGER)
    assert response.status_code in {200, 201}, (url, response.text)
    return dict(response.json())


@pytest_asyncio.fixture
async def world(test_app: AsyncClient) -> dict[str, Any]:
    """One enrollment, three blind baseline samples, one holdout, a recorder."""
    reviewer = await _post(test_app, f"{API}/reviewers", {"name": "Evaluator"})
    program = await _post(
        test_app, f"{PREFIX}/programs", {"name": "Eligibility", "version": "1"}
    )
    fragrance_ids: list[str] = []
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
        fragrance_ids.append(fragrance["id"])
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
    enrollment = await _post(
        test_app,
        f"{PREFIX}/programs/{program['id']}/enroll",
        {
            "reviewer_id": reviewer["id"],
            "recorder_usernames": ["recorder"],
            "session_size": 10,
        },
    )
    view = (
        await test_app.get(f"{PREFIX}/enrollments/{enrollment['id']}", headers=RECORDER)
    ).json()
    return {
        "reviewer_id": reviewer["id"],
        "fragrance_ids": fragrance_ids,
        "enrollment_id": enrollment["id"],
        "session_id": view["presentations"][0]["session_id"],
        "presentation_ids": [p["id"] for p in view["presentations"]],
    }


async def _observe(client: AsyncClient, presentation_id: str, **fields: Any) -> str:
    body = {"stage": "BLOTTER", "detected": True, "liking": 5, **fields}
    response = await client.post(
        f"{PREFIX}/presentations/{presentation_id}/observations",
        json=body,
        headers=RECORDER,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _lock(client: AsyncClient, presentation_id: str) -> None:
    response = await client.post(
        f"{PREFIX}/presentations/{presentation_id}/lock/BLOTTER", headers=RECORDER
    )
    assert response.status_code == 200, response.text


async def _flag(
    client: AsyncClient, target_type: str, target_id: str, **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "raised",
            "source": "recorder",
            "disposition": "review",
            "target_type": target_type,
            "target_id": target_id,
            "code": "competing_odor",
            "severity": "minor",
            **extra,
        },
        headers=RECORDER,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _close(
    client: AsyncClient,
    flag_id: str,
    *,
    action: str = "resolved",
    headers: dict[str, str] = MANAGER,
    **extra: Any,
) -> Any:
    return await client.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": action,
            "source": "manager" if headers is MANAGER else "recorder",
            "disposition": "include",
            "supersedes_id": flag_id,
            **extra,
        },
        headers=headers,
    )


async def _codes(client: AsyncClient, world: dict[str, Any]) -> dict[str, str]:
    """Each observation's code, read through the manager linkage route."""
    response = await client.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/linkage", headers=MANAGER
    )
    assert response.status_code == 200, response.text
    return {row["row_id"]: row["training_eligibility"] for row in response.json()}


async def _decide(
    client: AsyncClient,
    target_type: str,
    target_id: str,
    code: str,
    *,
    headers: dict[str, str] = MANAGER,
    reason: str = "Reviewed the session notes",
) -> Any:
    return await client.put(
        f"{API}/training-eligibility/{target_type}/{target_id}",
        json={"training_eligibility": code, "reason": reason},
        headers=headers,
    )


async def _evaluation_code(evaluation_id: str) -> str:
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        code = await session.scalar(
            select(Evaluation.training_eligibility).where(
                Evaluation.id == evaluation_id
            )
        )
        return str(code)
    finally:
        await sessions.aclose()


# --- ordinary encounters ---------------------------------------------------


@pytest.mark.asyncio
async def test_an_ordinary_encounter_saved_complete_is_eligible(
    test_app: AsyncClient, world: dict[str, Any], captured: list[dict[str, Any]]
) -> None:
    created = await _post(
        test_app,
        f"{API}/evaluations",
        {
            "reviewer_id": world["reviewer_id"],
            "fragrance_id": world["fragrance_ids"][0],
            "rating": 4,
        },
    )
    assert await _evaluation_code(created["id"]) == "eligible"
    (event,) = [
        e for e in _eligibility_events(captured) if e["target_id"] == created["id"]
    ]
    assert (event["previous"], event["training_eligibility"]) == (
        "unreviewed",
        "eligible",
    )
    assert event["cause"] == "evaluation_saved"


@pytest.mark.asyncio
async def test_an_edit_never_releases_a_withheld_encounter(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    created = await _post(
        test_app,
        f"{API}/evaluations",
        {
            "reviewer_id": world["reviewer_id"],
            "fragrance_id": world["fragrance_ids"][0],
            "rating": 4,
        },
    )
    withheld = await _decide(test_app, "evaluation", created["id"], "withheld")
    assert withheld.status_code == 200, withheld.text
    edited = await test_app.patch(
        f"{API}/evaluations/{created['id']}", json={"rating": 5}, headers=MANAGER
    )
    assert edited.status_code == 200, edited.text
    assert await _evaluation_code(created["id"]) == "withheld"


# --- controlled observations ----------------------------------------------


@pytest.mark.asyncio
async def test_an_observation_is_eligible_once_its_stage_is_locked(
    test_app: AsyncClient, world: dict[str, Any], captured: list[dict[str, Any]]
) -> None:
    presentation = world["presentation_ids"][0]
    first = await _observe(test_app, presentation, liking=3)
    second = await _observe(test_app, presentation, liking=7)
    skin_untouched = world["presentation_ids"][1]
    other = await _observe(test_app, skin_untouched)
    assert await _codes(test_app, world) == {
        first: "unreviewed",
        second: "unreviewed",
        other: "unreviewed",
    }

    await _lock(test_app, presentation)

    assert await _codes(test_app, world) == {
        first: "eligible",
        second: "eligible",
        other: "unreviewed",
    }
    causes = {e["target_id"]: e["cause"] for e in _eligibility_events(captured)}
    assert causes == {first: "stage_locked", second: "stage_locked"}


@pytest.mark.asyncio
async def test_a_raised_flag_demotes_unreviewed_and_eligible_rows(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    locked, unlocked = world["presentation_ids"][:2]
    eligible = await _observe(test_app, locked)
    await _lock(test_app, locked)
    unreviewed = await _observe(test_app, unlocked)

    flagged = await _flag(test_app, "session", world["session_id"])

    assert flagged["training_eligibility_changes"] == 2
    assert await _codes(test_app, world) == {
        eligible: "questionable",
        unreviewed: "questionable",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["observation", "presentation", "session"])
async def test_each_flag_target_covers_its_observations(
    test_app: AsyncClient, world: dict[str, Any], target_type: str
) -> None:
    flagged_sample, other_sample = world["presentation_ids"][:2]
    row = await _observe(test_app, flagged_sample)
    sibling = await _observe(test_app, flagged_sample)
    elsewhere = await _observe(test_app, other_sample)
    target_id = {
        "observation": row,
        "presentation": flagged_sample,
        "session": world["session_id"],
    }[target_type]

    await _flag(test_app, target_type, target_id)

    codes = await _codes(test_app, world)
    assert codes[row] == "questionable"
    assert codes[sibling] == (
        "unreviewed" if target_type == "observation" else "questionable"
    )
    assert codes[elsewhere] == (
        "questionable" if target_type == "session" else "unreviewed"
    )


@pytest.mark.asyncio
async def test_locking_under_an_open_flag_gives_questionable(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    await _flag(test_app, "presentation", presentation)
    row = await _observe(test_app, presentation)
    assert (await _codes(test_app, world))[row] == "questionable"

    await _lock(test_app, presentation)

    assert (await _codes(test_app, world))[row] == "questionable"


@pytest.mark.asyncio
async def test_a_flag_never_overrides_withheld_or_invalidated(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    withheld = await _observe(test_app, presentation)
    invalidated = await _observe(test_app, presentation)
    await _lock(test_app, presentation)
    assert (await _decide(test_app, "observation", withheld, "withheld")).is_success
    assert (
        await _decide(test_app, "observation", invalidated, "invalidated")
    ).is_success

    flag = await _flag(test_app, "presentation", presentation)
    assert flag["training_eligibility_changes"] == 0
    resolved = await _close(
        test_app, flag["id"], training_outcome="eligible", explanation="Fine after all"
    )
    assert resolved.status_code == 201, resolved.text
    invalidated_flag = await _flag(test_app, "presentation", presentation)
    await _close(test_app, invalidated_flag["id"], action="invalidated")

    assert await _codes(test_app, world) == {
        withheld: "withheld",
        invalidated: "invalidated",
    }


@pytest.mark.asyncio
async def test_an_invalidated_flag_restores_the_rule(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    locked, unlocked = world["presentation_ids"][:2]
    eligible = await _observe(test_app, locked)
    await _lock(test_app, locked)
    unreviewed = await _observe(test_app, unlocked)
    flag = await _flag(test_app, "session", world["session_id"])

    closed = await _close(test_app, flag["id"], action="invalidated", headers=RECORDER)

    assert closed.status_code == 201, closed.text
    assert await _codes(test_app, world) == {
        eligible: "eligible",
        unreviewed: "unreviewed",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["eligible", "withheld", "invalidated"])
async def test_a_manager_resolution_sets_the_chosen_outcome(
    test_app: AsyncClient,
    world: dict[str, Any],
    captured: list[dict[str, Any]],
    outcome: str,
) -> None:
    presentation = world["presentation_ids"][0]
    row = await _observe(test_app, presentation)
    await _lock(test_app, presentation)
    flag = await _flag(test_app, "presentation", presentation)

    resolved = await _close(
        test_app,
        flag["id"],
        training_outcome=outcome,
        explanation="Checked the sample label",
    )

    assert resolved.status_code == 201, resolved.text
    assert resolved.json()["training_eligibility_changes"] == 1
    assert (await _codes(test_app, world))[row] == outcome
    last = _eligibility_events(captured)[-1]
    assert last["cause"] == "quality_flag_resolved"
    assert last["reason"] == "Checked the sample label"
    assert last["quality_flag_id"] == flag["id"]
    assert last["actor"] == "manager"


@pytest.mark.asyncio
async def test_another_open_flag_keeps_a_row_questionable(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    row = await _observe(test_app, presentation)
    await _lock(test_app, presentation)
    first = await _flag(test_app, "presentation", presentation)
    await _flag(test_app, "session", world["session_id"])

    await _close(
        test_app, first["id"], training_outcome="eligible", explanation="First is fine"
    )

    assert (await _codes(test_app, world))[row] == "questionable"


@pytest.mark.asyncio
async def test_a_resolution_without_an_outcome_leaves_rows_questionable(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    row = await _observe(test_app, presentation)
    await _lock(test_app, presentation)
    flag = await _flag(test_app, "presentation", presentation)

    closed = await _close(test_app, flag["id"], headers=RECORDER)

    assert closed.status_code == 201, closed.text
    assert (await _codes(test_app, world))[row] == "questionable"


@pytest.mark.asyncio
async def test_only_a_manager_chooses_a_training_outcome(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    await _observe(test_app, presentation)
    flag = await _flag(test_app, "presentation", presentation)

    by_recorder = await _close(
        test_app,
        flag["id"],
        headers=RECORDER,
        training_outcome="eligible",
        explanation="Looks fine",
    )
    without_reason = await _close(test_app, flag["id"], training_outcome="withheld")
    on_invalidation = await _close(
        test_app,
        flag["id"],
        action="invalidated",
        training_outcome="withheld",
        explanation="x",
    )
    on_raise = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "raised",
            "source": "manager",
            "disposition": "review",
            "target_type": "presentation",
            "target_id": presentation,
            "code": "other",
            "severity": "minor",
            "training_outcome": "withheld",
        },
        headers=MANAGER,
    )

    assert by_recorder.status_code == 403, by_recorder.text
    assert without_reason.status_code == 422, without_reason.text
    assert on_invalidation.status_code == 422, on_invalidation.text
    assert on_raise.status_code == 422, on_raise.text


# --- manager decisions -----------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["eligible", "withheld", "invalidated"])
async def test_a_manager_sets_a_row_with_a_reason(
    test_app: AsyncClient,
    world: dict[str, Any],
    captured: list[dict[str, Any]],
    code: str,
) -> None:
    row = await _observe(test_app, world["presentation_ids"][0])

    response = await _decide(test_app, "observation", row, code, reason="  Spill  ")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "target_type": "observation",
        "target_id": row,
        "previous": "unreviewed",
        "training_eligibility": code,
    }
    assert (await _codes(test_app, world))[row] == code
    last = _eligibility_events(captured)[-1]
    assert (last["cause"], last["reason"], last["actor"]) == (
        "manager_decision",
        "Spill",
        "manager",
    )


@pytest.mark.asyncio
async def test_a_manager_decision_is_validated(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    row = await _observe(test_app, world["presentation_ids"][0])

    assert (
        await _decide(test_app, "observation", "nope", "withheld")
    ).status_code == 404
    assert (await _decide(test_app, "evaluation", row, "withheld")).status_code == 404
    assert (
        await _decide(test_app, "observation", row, "questionable")
    ).status_code == 422
    assert (
        await _decide(test_app, "observation", row, "unreviewed")
    ).status_code == 422
    assert (
        await _decide(test_app, "observation", row, "withheld", reason="   ")
    ).status_code == 422
    assert (await _decide(test_app, "reviewer", row, "withheld")).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [RECORDER, OUTSIDER])
async def test_only_a_manager_decides_or_reads_linkage(
    test_app: AsyncClient, world: dict[str, Any], headers: dict[str, str]
) -> None:
    row = await _observe(test_app, world["presentation_ids"][0])

    decided = await _decide(test_app, "observation", row, "eligible", headers=headers)
    linkage = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/linkage", headers=headers
    )

    assert decided.status_code == 403, decided.text
    assert linkage.status_code == 403, linkage.text
    assert (await _codes(test_app, world))[row] == "unreviewed"


# --- linkage -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_linkage_names_role_and_repeat_per_observation(
    test_app: AsyncClient, world: dict[str, Any], captured: list[dict[str, Any]]
) -> None:
    rows = [await _observe(test_app, p) for p in world["presentation_ids"]]

    response = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/linkage", headers=MANAGER
    )

    assert response.status_code == 200, response.text
    linkage = response.json()
    assert {row["row_id"] for row in linkage} == set(rows)
    assert {row["role"] for row in linkage} == {"UNIVERSAL_BASELINE", "HOLDOUT"}
    for row in linkage:
        assert row["enrollment_id"] == world["enrollment_id"]
        assert row["reviewer_id"] == world["reviewer_id"]
        assert row["repeat_of_membership_id"] is None
        assert set(row) >= {"program_id", "session_id", "blind_code", "membership_id"}
    retrievals = [
        e
        for e in captured
        if e.get("event") == "audit_event" and e.get("action") == "linkage_retrieve"
    ]
    assert retrievals
    assert retrievals[-1]["target_id"] == world["enrollment_id"]


@pytest.mark.asyncio
async def test_rows_written_outside_the_service_stay_unreviewed(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    """A legacy import or raw insert never trains without a decision."""
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        session.add(
            Evaluation(
                id="imported",
                reviewer_id=world["reviewer_id"],
                fragrance_id=world["fragrance_ids"][0],
                rating=3,
            )
        )
        session.add(
            Observation(
                id="imported-obs",
                presentation_id=world["presentation_ids"][0],
                stage="BLOTTER",
                phase="PRE_REVEAL",
                detected=True,
                liking=5,
                recorded_by="import",
            )
        )
        await session.commit()
    finally:
        await sessions.aclose()
    assert (await _codes(test_app, world))["imported-obs"] == "unreviewed"

    await _lock(test_app, world["presentation_ids"][0])

    assert await _evaluation_code("imported") == "unreviewed"
    # A later service lock does promote it: option C is a rule on the locked
    # stage, applied when the lock is written, not a property of the writer.
    assert (await _codes(test_app, world))["imported-obs"] == "eligible"
