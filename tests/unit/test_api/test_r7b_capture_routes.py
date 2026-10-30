"""Rankings, quality flags, enrollment randomization record, and the export (R7b 1c)."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from fragrance_rater.api import calibration as calibration_api
from fragrance_rater.core.config import settings
from fragrance_rater.models import calibration as models
from fragrance_rater.schemas import capture as capture_schemas
from fragrance_rater.services import consent as consent_module
from fragrance_rater.services.consent import ConsentText

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
OUTSIDER = {"X-Authentik-Username": "outsider"}

APPROVED = ConsentText(
    version="family-consent-v1",
    status="APPROVED",
    sha256="b" * 64,
    body="Version: family-consent-v1\nStatus: APPROVED\n\nApproved test wording.\n",
)


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


@pytest_asyncio.fixture
async def world(test_app: Any) -> dict[str, Any]:
    """One enrollment with three blind samples and an assigned recorder."""
    reviewer = await test_app.post(
        "/api/v1/reviewers", json={"name": "Evaluator"}, headers=MANAGER
    )
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Protocol", "version": "1"}, headers=MANAGER
    )
    program_id = program.json()["id"]
    for index in range(3):
        fragrance = await test_app.post(
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
        await test_app.post(
            f"{PREFIX}/programs/{program_id}/members",
            json={
                "fragrance_id": fragrance.json()["id"],
                "role": "UNIVERSAL_BASELINE",
                "identity_evidence": "Label verified",
            },
            headers=MANAGER,
        )
    await test_app.post(f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER)
    enrollment = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer.json()["id"],
            "recorder_usernames": ["recorder"],
        },
        headers=MANAGER,
    )
    enrollment_id = enrollment.json()["id"]
    view = (
        await test_app.get(f"{PREFIX}/enrollments/{enrollment_id}", headers=RECORDER)
    ).json()
    presentations = view["presentations"]
    return {
        "reviewer_id": reviewer.json()["id"],
        "enrollment_id": enrollment_id,
        "session_id": presentations[0]["session_id"],
        "presentation_ids": [p["id"] for p in presentations],
    }


async def _observe(client: Any, presentation_id: str, **fields: Any) -> dict[str, Any]:
    body = {"stage": "BLOTTER", "detected": True, "liking": 5, **fields}
    response = await client.post(
        f"{PREFIX}/presentations/{presentation_id}/observations",
        json=body,
        headers=RECORDER,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _assess_all(
    client: Any, world: dict[str, Any], *, undetected: int | None = None
) -> None:
    """Assess every sample; optionally mark one (by index) as not detected."""
    for index, presentation_id in enumerate(world["presentation_ids"]):
        if index == undetected:
            await _observe(
                client,
                presentation_id,
                detected=False,
                intensity=0,
                liking=None,
                response_status="not_detected",
            )
        else:
            await _observe(client, presentation_id, response_status="completed")


def _ranking(
    world: dict[str, Any], positions: list[int], **extra: Any
) -> dict[str, Any]:
    ids = world["presentation_ids"]
    return {
        "stage": "BLOTTER",
        "response_status": "completed",
        "entries": [
            {"presentation_id": ids[index], "rank_position": position}
            for index, position in enumerate(positions)
        ],
        **extra,
    }


async def _rank(
    client: Any, world: dict[str, Any], body: dict[str, Any], **kw: Any
) -> Any:
    return await client.post(
        f"{PREFIX}/sessions/{world['session_id']}/rankings",
        json=body,
        headers=kw.get("headers", RECORDER),
    )


# --- rankings --------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_needs_every_sample_assessed(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _observe(test_app, world["presentation_ids"][0])

    response = await _rank(test_app, world, _ranking(world, [1, 2, 3]))

    assert response.status_code == 409
    assert "2 left" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_completed_ranking_is_recorded_pre_reveal(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)

    response = await _rank(test_app, world, _ranking(world, [1, 2, 3]))

    assert response.status_code == 201
    assert response.json()["phase"] == "PRE_REVEAL"
    assert response.json()["eligible"] == 3
    listed = (
        await test_app.get(
            f"{PREFIX}/sessions/{world['session_id']}/rankings", headers=RECORDER
        )
    ).json()
    assert [e["rank_position"] for e in listed[0]["entries"]] == [1, 2, 3]
    assert all(e["eligible_for_rank"] for e in listed[0]["entries"])


@pytest.mark.asyncio
async def test_ties_follow_competition_ranking(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)

    assert (await _rank(test_app, world, _ranking(world, [1, 1, 3]))).status_code == 201


@pytest.mark.asyncio
async def test_positions_that_skip_wrongly_are_refused(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)

    assert (await _rank(test_app, world, _ranking(world, [1, 3, 3]))).status_code == 422


@pytest.mark.asyncio
async def test_an_undetected_sample_is_listed_but_never_ranked(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world, undetected=2)
    ids = world["presentation_ids"]

    response = await _rank(
        test_app,
        world,
        {
            "stage": "BLOTTER",
            "response_status": "completed",
            "entries": [
                {"presentation_id": ids[0], "rank_position": 1},
                {"presentation_id": ids[1], "rank_position": 2},
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["eligible"] == 2
    entries = (
        await test_app.get(
            f"{PREFIX}/sessions/{world['session_id']}/rankings", headers=RECORDER
        )
    ).json()[0]["entries"]
    by_id = {e["presentation_id"]: e for e in entries}
    assert by_id[ids[2]] == {
        "presentation_id": ids[2],
        "eligible_for_rank": False,
        "rank_position": None,
    }


@pytest.mark.asyncio
async def test_a_client_cannot_rank_an_undetected_or_omit_a_detected_sample(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world, undetected=2)

    ranks_the_undetected = await _rank(test_app, world, _ranking(world, [1, 2, 3]))
    omits_a_detected = await _rank(
        test_app,
        world,
        {
            "stage": "BLOTTER",
            "response_status": "completed",
            "entries": [
                {"presentation_id": world["presentation_ids"][0], "rank_position": 1},
                {"presentation_id": "no-such-sample", "rank_position": 2},
            ],
        },
    )

    assert ranks_the_undetected.status_code == 409
    assert omits_a_detected.status_code == 409


@pytest.mark.asyncio
async def test_a_skipped_response_makes_a_sample_ineligible(
    test_app: Any, world: dict[str, Any]
) -> None:
    ids = world["presentation_ids"]
    await _observe(test_app, ids[0], response_status="completed")
    await _observe(test_app, ids[1], response_status="completed")
    await _observe(test_app, ids[2], response_status="skipped")

    response = await _rank(test_app, world, _ranking(world, [1, 2]))

    assert response.status_code == 201
    assert response.json()["eligible"] == 2


@pytest.mark.asyncio
async def test_a_second_ranking_needs_the_first_invalidated(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)
    assert (await _rank(test_app, world, _ranking(world, [1, 2, 3]))).status_code == 201

    again = await _rank(test_app, world, _ranking(world, [3, 2, 1]))
    invalidate = await _rank(
        test_app, world, {"stage": "BLOTTER", "response_status": "invalidated"}
    )
    redo = await _rank(test_app, world, _ranking(world, [3, 2, 1]))

    assert again.status_code == 409
    assert invalidate.status_code == 201
    assert redo.status_code == 201
    events = (
        await test_app.get(
            f"{PREFIX}/sessions/{world['session_id']}/rankings", headers=RECORDER
        )
    ).json()
    assert [e["response_status"] for e in events] == [
        "completed",
        "invalidated",
        "completed",
    ]


@pytest.mark.asyncio
async def test_nothing_to_invalidate_is_refused(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)

    response = await _rank(
        test_app, world, {"stage": "BLOTTER", "response_status": "invalidated"}
    )

    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["skipped", "unable_to_assess", "interrupted"])
async def test_a_non_completed_ranking_is_recorded_without_entries(
    test_app: Any, world: dict[str, Any], status: str
) -> None:
    await _assess_all(test_app, world)

    response = await _rank(
        test_app, world, {"stage": "BLOTTER", "response_status": status}
    )

    assert response.status_code == 201
    event = (
        await test_app.get(
            f"{PREFIX}/sessions/{world['session_id']}/rankings", headers=RECORDER
        )
    ).json()[0]
    assert event["response_status"] == status
    assert event["entries"] == []


@pytest.mark.asyncio
async def test_ranking_input_shape_is_validated(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)
    ids = world["presentation_ids"]
    too_few = {
        "stage": "BLOTTER",
        "response_status": "completed",
        "entries": [{"presentation_id": ids[0], "rank_position": 1}],
    }
    duplicated = _ranking(world, [1, 2, 3])
    duplicated["entries"][1]["presentation_id"] = ids[0]
    skipped_with_entries = _ranking(world, [1, 2, 3], response_status="skipped")

    for body in (too_few, duplicated, skipped_with_entries):
        assert (await _rank(test_app, world, body)).status_code == 422


@pytest.mark.asyncio
async def test_a_ranking_made_after_reveal_is_marked_post_reveal(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)
    for presentation_id in world["presentation_ids"]:
        await test_app.post(
            f"{PREFIX}/presentations/{presentation_id}/lock/BLOTTER", headers=RECORDER
        )
    await test_app.post(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/lock-skin-plan",
        headers=RECORDER,
    )
    revealed = await test_app.post(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/reveal", headers=MANAGER
    )
    assert revealed.status_code == 200, revealed.text
    for presentation_id in world["presentation_ids"]:
        await test_app.post(
            f"{PREFIX}/presentations/{presentation_id}/post-reveal",
            json={"stage": "BLOTTER", "detected": True, "liking": 6},
            headers=MANAGER,
        )

    response = await _rank(test_app, world, _ranking(world, [1, 2, 3]), headers=MANAGER)

    assert response.status_code == 201
    assert response.json()["phase"] == "POST_REVEAL"


@pytest.mark.asyncio
async def test_rankings_are_for_assigned_people_only(
    test_app: Any, world: dict[str, Any]
) -> None:
    await _assess_all(test_app, world)
    body = _ranking(world, [1, 2, 3])
    url = f"{PREFIX}/sessions/{world['session_id']}/rankings"

    assert (await _rank(test_app, world, body, headers=OUTSIDER)).status_code == 403
    assert (await test_app.get(url, headers=OUTSIDER)).status_code == 403
    assert (await _rank(test_app, world, body, headers=MANAGER)).status_code == 201


@pytest.mark.asyncio
async def test_ranking_an_unknown_session_is_404(test_app: Any) -> None:
    response = await test_app.post(
        f"{PREFIX}/sessions/nope/rankings",
        json={"stage": "BLOTTER", "response_status": "skipped"},
        headers=MANAGER,
    )

    assert response.status_code == 404


# --- quality flags ---------------------------------------------------------


def _raise(world: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "action": "raised",
        "source": "evaluator",
        "disposition": "review",
        "target_type": "presentation",
        "target_id": world["presentation_ids"][0],
        "code": "sample_spill",
        "severity": "minor",
        **extra,
    }


async def _flags(client: Any, world: dict[str, Any]) -> list[dict[str, Any]]:
    response = await client.get(
        f"{PREFIX}/sessions/{world['session_id']}/quality-flags", headers=RECORDER
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_a_flag_is_raised_listed_open_and_audited(
    test_app: Any, world: dict[str, Any]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/quality-flags", json=_raise(world), headers=RECORDER
    )

    assert response.status_code == 201
    flags = await _flags(test_app, world)
    assert len(flags) == 1
    assert flags[0]["code"] == "sample_spill"
    assert flags[0]["open"] is True
    assert flags[0]["presentation_id"] == world["presentation_ids"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("closing", ["resolved", "invalidated"])
async def test_a_flag_is_closed_by_a_later_row_that_inherits_target_and_code(
    test_app: Any, world: dict[str, Any], closing: str
) -> None:
    raised = (
        await test_app.post(
            f"{PREFIX}/quality-flags", json=_raise(world), headers=RECORDER
        )
    ).json()["id"]

    response = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": closing,
            "source": "manager",
            "disposition": "include",
            "supersedes_id": raised,
            "explanation": "Checked the sample",
        },
        headers=MANAGER,
    )

    assert response.status_code == 201
    flags = {f["id"]: f for f in await _flags(test_app, world)}
    assert flags[raised]["open"] is False
    closer = flags[response.json()["id"]]
    assert closer["code"] == "sample_spill"
    assert closer["presentation_id"] == world["presentation_ids"][0]
    assert closer["supersedes_id"] == raised
    assert closer["open"] is False


@pytest.mark.asyncio
async def test_a_flag_cannot_be_closed_twice_or_close_a_closer(
    test_app: Any, world: dict[str, Any]
) -> None:
    raised = (
        await test_app.post(
            f"{PREFIX}/quality-flags", json=_raise(world), headers=RECORDER
        )
    ).json()["id"]
    close = {
        "action": "resolved",
        "source": "recorder",
        "disposition": "include",
        "supersedes_id": raised,
    }
    first = await test_app.post(f"{PREFIX}/quality-flags", json=close, headers=RECORDER)

    again = await test_app.post(f"{PREFIX}/quality-flags", json=close, headers=RECORDER)
    close_the_closer = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={**close, "supersedes_id": first.json()["id"]},
        headers=RECORDER,
    )

    assert again.status_code == 409
    assert close_the_closer.status_code == 409


@pytest.mark.asyncio
async def test_closing_an_unknown_flag_is_404(
    test_app: Any, world: dict[str, Any]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "resolved",
            "source": "recorder",
            "disposition": "include",
            "supersedes_id": "nope",
        },
        headers=RECORDER,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_flags_can_target_a_session_or_an_observation(
    test_app: Any, world: dict[str, Any]
) -> None:
    observation = await _observe(test_app, world["presentation_ids"][0])
    on_session = _raise(
        world, target_type="session", target_id=world["session_id"], code="interrupted"
    )
    on_observation = _raise(
        world,
        target_type="observation",
        target_id=observation["id"],
        code="timestamp_inconsistent",
    )

    for body in (on_session, on_observation):
        assert (
            await test_app.post(f"{PREFIX}/quality-flags", json=body, headers=RECORDER)
        ).status_code == 201

    flags = await _flags(test_app, world)
    assert {f["code"] for f in flags} == {"interrupted", "timestamp_inconsistent"}


@pytest.mark.asyncio
async def test_a_flag_on_an_unknown_observation_is_404(
    test_app: Any, world: dict[str, Any]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/quality-flags",
        json=_raise(world, target_type="observation", target_id="nope"),
        headers=RECORDER,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_only_a_manager_can_flag_as_the_manager(
    test_app: Any, world: dict[str, Any]
) -> None:
    body = _raise(world, source="manager")

    assert (
        await test_app.post(f"{PREFIX}/quality-flags", json=body, headers=RECORDER)
    ).status_code == 403
    assert (
        await test_app.post(f"{PREFIX}/quality-flags", json=body, headers=MANAGER)
    ).status_code == 201


@pytest.mark.asyncio
async def test_flag_input_shape_is_validated(
    test_app: Any, world: dict[str, Any]
) -> None:
    bad = [
        _raise(world, source="automatic_validation"),
        _raise(world, code="not_a_code"),
        {**_raise(world), "code": None},
        _raise(world, supersedes_id="x"),
        {
            "action": "resolved",
            "source": "recorder",
            "disposition": "include",
        },
        {
            "action": "resolved",
            "source": "recorder",
            "disposition": "include",
            "supersedes_id": "x",
            "code": "other",
        },
    ]

    for body in bad:
        response = await test_app.post(
            f"{PREFIX}/quality-flags", json=body, headers=RECORDER
        )
        assert response.status_code == 422, body


@pytest.mark.asyncio
async def test_flags_are_for_assigned_people_only(
    test_app: Any, world: dict[str, Any]
) -> None:
    raised = (
        await test_app.post(
            f"{PREFIX}/quality-flags", json=_raise(world), headers=RECORDER
        )
    ).json()["id"]

    outsider_raise = await test_app.post(
        f"{PREFIX}/quality-flags", json=_raise(world), headers=OUTSIDER
    )
    outsider_close = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "resolved",
            "source": "recorder",
            "disposition": "include",
            "supersedes_id": raised,
        },
        headers=OUTSIDER,
    )
    outsider_read = await test_app.get(
        f"{PREFIX}/sessions/{world['session_id']}/quality-flags", headers=OUTSIDER
    )

    assert outsider_raise.status_code == 403
    assert outsider_close.status_code == 403
    assert outsider_read.status_code == 403


def test_flag_and_rank_vocabularies_match_the_model() -> None:
    from typing import get_args

    pairs = [
        (capture_schemas.FlagCode, models.QUALITY_FLAG_CODES),
        (capture_schemas.FlagSeverity, models.QUALITY_FLAG_SEVERITIES),
        (capture_schemas.FlagDisposition, models.QUALITY_FLAG_DISPOSITIONS),
        (capture_schemas.FlagAction, models.QUALITY_FLAG_ACTIONS),
        (capture_schemas.RankStatus, models.RANK_EVENT_STATUSES),
    ]
    for literal, values in pairs:
        assert set(get_args(literal)) == set(values)
    assert set(get_args(capture_schemas.FlagSource)) | {"automatic_validation"} == set(
        models.QUALITY_FLAG_SOURCES
    )


# --- enrollment record -----------------------------------------------------


@pytest.mark.asyncio
async def test_enrollment_records_the_randomization_algorithm(
    test_app: Any, world: dict[str, Any]
) -> None:
    export = (
        await test_app.get(
            f"{PREFIX}/enrollments/{world['enrollment_id']}/evidence-export",
            headers=MANAGER,
        )
    ).json()

    assert export["enrollment"]["randomization_algorithm"] == "system-random-shuffle-v1"
    assert export["enrollment"]["randomization_seed"] is None
    positions = [
        (p["position"], p["intended_position"])
        for p in export["sessions"][0]["presentations"]
    ]
    assert positions == [(n, n) for n in (1, 2, 3)]


# --- evidence export -------------------------------------------------------


@pytest.mark.asyncio
async def test_the_export_is_manager_only(test_app: Any, world: dict[str, Any]) -> None:
    url = f"{PREFIX}/enrollments/{world['enrollment_id']}/evidence-export"

    assert (await test_app.get(url, headers=RECORDER)).status_code == 403
    assert (await test_app.get(url, headers=OUTSIDER)).status_code == 403
    assert (await test_app.get(url, headers=MANAGER)).status_code == 200
    assert (
        await test_app.get(
            f"{PREFIX}/enrollments/nope/evidence-export", headers=MANAGER
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_the_export_carries_observations_rankings_flags_and_conceals_identity(
    test_app: Any, world: dict[str, Any]
) -> None:
    ids = world["presentation_ids"]
    for index, presentation_id in enumerate(ids):
        await _observe(
            test_app,
            presentation_id,
            response_status="completed",
            recognition="new",
            liking=index + 3,
        )
    await _rank(test_app, world, _ranking(world, [1, 2, 3]))
    await test_app.post(f"{PREFIX}/quality-flags", json=_raise(world), headers=RECORDER)

    response = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/evidence-export",
        headers=MANAGER,
    )

    export = response.json()
    assert export["export_version"] == "r7b-evidence-v1"
    session = export["sessions"][0]
    assert len(session["presentations"]) == 3
    first = session["presentations"][0]["observations"][0]
    assert first["response_status"] == "completed"
    assert first["recognition"] == "new"
    assert first["fit_choices"] == {"season": [], "setting": []}
    assert session["rankings"][0]["entries"][0]["rank_position"] == 1
    assert session["quality_flags"][0]["code"] == "sample_spill"
    # Identity stays concealed: only blind codes and positions are exported.
    assert "Concealed" not in response.text
    assert "fragrance_id" not in response.text


@pytest.mark.asyncio
async def test_the_export_withholds_context_unless_consent_stands(
    test_app: Any, world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(consent_module, "load_consent_text", lambda: APPROVED)
    monkeypatch.setattr(calibration_api, "load_consent_text", lambda: APPROVED)
    consent_url = f"{PREFIX}/reviewers/{world['reviewer_id']}/consent"
    context_url = f"{PREFIX}/sessions/{world['session_id']}/context"
    export_url = f"{PREFIX}/enrollments/{world['enrollment_id']}/evidence-export"
    await test_app.post(
        consent_url,
        json={"scope": "session_context", "event_type": "granted"},
        headers=RECORDER,
    )
    saved = await test_app.post(
        context_url, json={"illness": "no", "hunger": "not_hungry"}, headers=RECORDER
    )
    assert saved.status_code == 201, saved.text

    with_consent = (await test_app.get(export_url, headers=MANAGER)).json()
    await test_app.post(
        consent_url,
        json={"scope": "session_context", "event_type": "withdrawn"},
        headers=RECORDER,
    )
    after_withdrawal = (await test_app.get(export_url, headers=MANAGER)).json()

    session = with_consent["sessions"][0]
    assert session["context"]["illness"] == "no"
    assert session["context_withheld"] is False
    assert [e["event_type"] for e in with_consent["consent"]["events"]] == ["granted"]
    withheld = after_withdrawal["sessions"][0]
    assert withheld["context"] is None
    assert withheld["context_withheld"] is True
    assert after_withdrawal["consent"]["state"]["session_context"] == "withdrawn"
