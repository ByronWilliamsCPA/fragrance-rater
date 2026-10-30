"""Consent, session context, session timing, and exposure routes (R7b PR 1b)."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from fragrance_rater.api import calibration as calibration_api
from fragrance_rater.core.config import settings
from fragrance_rater.services import consent as consent_module
from fragrance_rater.services.consent import ConsentText, load_consent_text

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


@pytest.fixture
def approved_consent(monkeypatch: pytest.MonkeyPatch) -> ConsentText:
    """Pretend a person has approved the wording, so consent can be recorded."""
    monkeypatch.setattr(consent_module, "load_consent_text", lambda: APPROVED)
    monkeypatch.setattr(calibration_api, "load_consent_text", lambda: APPROVED)
    return APPROVED


@pytest_asyncio.fixture
async def world(test_app: Any) -> dict[str, str]:
    """One reviewer, one active program, one enrollment with a recorder."""
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
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Protocol", "version": "1"}, headers=MANAGER
    )
    program_id = program.json()["id"]
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
    view = await test_app.get(f"{PREFIX}/enrollments/{enrollment_id}", headers=RECORDER)
    presentation = view.json()["presentations"][0]
    return {
        "reviewer_id": reviewer.json()["id"],
        "enrollment_id": enrollment_id,
        "presentation_id": presentation["id"],
        "session_id": presentation["session_id"],
    }


# --- the consent text ------------------------------------------------------


def test_the_shipped_consent_text_is_a_draft() -> None:
    """Until a person approves the wording, no consent can be recorded."""
    text = load_consent_text()

    assert text.status == "DRAFT"
    assert text.approved is False
    assert text.version == "family-consent-v1"
    assert len(text.sha256) == 64


def test_the_shipped_text_marks_every_open_policy_decision() -> None:
    body = load_consent_text().body

    assert body.count("[OWNER DECISION]") >= 5
    assert "never depends on saying yes" in body


@pytest.mark.asyncio
async def test_the_consent_text_route_reports_the_draft(test_app: Any) -> None:
    response = await test_app.get(f"{PREFIX}/consent/text", headers=RECORDER)

    assert response.status_code == 200
    body = response.json()
    assert body["approved"] is False
    assert body["version"] == "family-consent-v1"
    assert body["sha256"] == load_consent_text().sha256
    assert "DRAFT FOR OWNER APPROVAL" in body["text"]


# --- consent events --------------------------------------------------------


@pytest.mark.asyncio
async def test_consent_cannot_be_recorded_against_draft_wording(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/reviewers/{world['reviewer_id']}/consent",
        json={"scope": "session_context", "event_type": "granted"},
        headers=RECORDER,
    )

    assert response.status_code == 409
    assert "not been approved" in response.json()["detail"]
    state = await test_app.get(
        f"{PREFIX}/reviewers/{world['reviewer_id']}/consent", headers=RECORDER
    )
    assert set(state.json()["state"].values()) == {"none"}
    assert state.json()["events"] == []


async def _consent(
    client: Any, world: dict[str, str], scope: str, event_type: str, **extra: Any
) -> Any:
    return await client.post(
        f"{PREFIX}/reviewers/{world['reviewer_id']}/consent",
        json={"scope": scope, "event_type": event_type, **extra},
        headers=RECORDER,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_grant_withdraw_and_regrant(test_app: Any, world: dict[str, str]) -> None:
    url = f"{PREFIX}/reviewers/{world['reviewer_id']}/consent"

    assert (
        await _consent(test_app, world, "model_training", "granted")
    ).status_code == 201
    state = (await test_app.get(url, headers=RECORDER)).json()["state"]
    assert state["model_training"] == "granted"
    assert state["session_context"] == "none"

    assert (
        await _consent(test_app, world, "model_training", "withdrawn")
    ).status_code == 201
    state = (await test_app.get(url, headers=RECORDER)).json()["state"]
    assert state["model_training"] == "withdrawn"

    assert (
        await _consent(test_app, world, "model_training", "granted")
    ).status_code == 201
    events = (await test_app.get(url, headers=RECORDER)).json()["events"]
    assert [e["event_type"] for e in events] == ["granted", "withdrawn", "granted"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_every_event_is_stamped_with_the_shown_text(
    test_app: Any, world: dict[str, str]
) -> None:
    await _consent(test_app, world, "household_research", "granted", note="verbal yes")

    events = (
        await test_app.get(
            f"{PREFIX}/reviewers/{world['reviewer_id']}/consent", headers=RECORDER
        )
    ).json()["events"]

    (event,) = events
    assert event["consent_text_version"] == "family-consent-v1"
    assert event["recorded_by"] == "recorder"
    assert event["occurred_at"] is not None


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_a_grant_cannot_be_repeated_or_withdrawn_before_it_exists(
    test_app: Any, world: dict[str, str]
) -> None:
    assert (
        await _consent(test_app, world, "research_export", "withdrawn")
    ).status_code == 409

    await _consent(test_app, world, "research_export", "granted")
    assert (
        await _consent(test_app, world, "research_export", "granted")
    ).status_code == 409


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_scopes_are_independent(test_app: Any, world: dict[str, str]) -> None:
    await _consent(test_app, world, "session_context", "granted")
    await _consent(test_app, world, "aggregate_reporting", "granted")
    await _consent(test_app, world, "session_context", "withdrawn")

    state = (
        await test_app.get(
            f"{PREFIX}/reviewers/{world['reviewer_id']}/consent", headers=RECORDER
        )
    ).json()["state"]

    assert state["session_context"] == "withdrawn"
    assert state["aggregate_reporting"] == "granted"


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
@pytest.mark.parametrize(
    "body",
    [
        {"scope": "everything", "event_type": "granted"},
        {"scope": "session_context", "event_type": "revoked"},
        # The caller never supplies the text, its digest, or the timestamp.
        {
            "scope": "session_context",
            "event_type": "granted",
            "consent_text_version": "x",
        },
        {
            "scope": "session_context",
            "event_type": "granted",
            "occurred_at": "2020-01-01",
        },
    ],
)
async def test_malformed_or_forged_consent_is_refused(
    test_app: Any, world: dict[str, str], body: dict[str, str]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/reviewers/{world['reviewer_id']}/consent",
        json=body,
        headers=RECORDER,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_only_a_manager_or_an_assigned_recorder_may_touch_consent(
    test_app: Any, world: dict[str, str]
) -> None:
    url = f"{PREFIX}/reviewers/{world['reviewer_id']}/consent"
    body = {"scope": "session_context", "event_type": "granted"}

    assert (await test_app.post(url, json=body, headers=OUTSIDER)).status_code == 403
    assert (await test_app.get(url, headers=OUTSIDER)).status_code == 403
    assert (await test_app.get(url, headers=MANAGER)).status_code == 200
    assert (await test_app.post(url, json=body, headers=MANAGER)).status_code == 201


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_consent_changes_are_audited_without_the_note(
    test_app: Any, world: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    logged: list[dict[str, Any]] = []
    monkeypatch.setattr(
        calibration_api, "log_audit_event", lambda _logger, **kw: logged.append(kw)
    )

    await _consent(test_app, world, "model_training", "granted", note="private words")

    (event,) = logged
    assert event["action"] == "consent_granted"
    assert event["scope"] == "model_training"
    assert event["actor"] == "recorder"
    assert "private words" not in str(event)


# --- session context -------------------------------------------------------


async def _context(client: Any, world: dict[str, str], body: dict[str, Any]) -> Any:
    return await client.post(
        f"{PREFIX}/sessions/{world['session_id']}/context", json=body, headers=RECORDER
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_context_needs_a_current_grant(
    test_app: Any, world: dict[str, str]
) -> None:
    refused = await _context(test_app, world, {"illness": "no"})
    assert refused.status_code == 403
    assert "session_context" in refused.json()["detail"]

    await _consent(test_app, world, "session_context", "granted")
    assert (await _context(test_app, world, {"illness": "no"})).status_code == 201


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_a_withdrawal_blocks_context_even_after_an_earlier_grant(
    test_app: Any, world: dict[str, str]
) -> None:
    await _consent(test_app, world, "session_context", "granted")
    await _consent(test_app, world, "session_context", "withdrawn")

    assert (await _context(test_app, world, {"illness": "no"})).status_code == 403


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_context_is_recorded_once_and_read_back(
    test_app: Any, world: dict[str, str]
) -> None:
    await _consent(test_app, world, "session_context", "granted")
    url = f"{PREFIX}/sessions/{world['session_id']}/context"
    assert (await test_app.get(url, headers=RECORDER)).json() == {"recorded": False}

    body = {
        "illness": "no",
        "hunger": "slightly_hungry",
        "hours_since_food": 2.5,
        "room_temperature_c": 21.0,
        "hormonal_context": "prefer_not_to_answer",
    }
    assert (await _context(test_app, world, body)).status_code == 201
    assert (await _context(test_app, world, body)).status_code == 409

    stored = (await test_app.get(url, headers=RECORDER)).json()
    assert stored["recorded"] is True
    assert stored["illness"] == "no"
    assert stored["hormonal_context"] == "prefer_not_to_answer"
    assert stored["nasal_congestion"] is None
    assert stored["recorded_by"] == "recorder"


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_an_empty_context_is_accepted_because_every_answer_is_refusable(
    test_app: Any, world: dict[str, str]
) -> None:
    await _consent(test_app, world, "session_context", "granted")

    assert (await _context(test_app, world, {})).status_code == 201


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
@pytest.mark.parametrize(
    "body",
    [
        {"illness": "sometimes"},
        {"hunger": "starving"},
        {"hours_since_food": -1},
        {"room_temperature_c": 99},
        {"room_humidity_pct": 101},
        {"favorite_color": "blue"},
    ],
)
async def test_context_answers_are_validated(
    test_app: Any, world: dict[str, str], body: dict[str, Any]
) -> None:
    await _consent(test_app, world, "session_context", "granted")

    assert (await _context(test_app, world, body)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_context_is_visible_only_to_a_manager_or_assigned_recorder(
    test_app: Any, world: dict[str, str]
) -> None:
    await _consent(test_app, world, "session_context", "granted")
    await _context(test_app, world, {"illness": "yes"})
    url = f"{PREFIX}/sessions/{world['session_id']}/context"

    assert (await test_app.get(url, headers=OUTSIDER)).status_code == 403
    assert (await test_app.post(url, json={}, headers=OUTSIDER)).status_code == 403
    assert (await test_app.get(url, headers=MANAGER)).json()["illness"] == "yes"


@pytest.mark.asyncio
@pytest.mark.usefixtures("approved_consent")
async def test_the_audit_event_names_answered_fields_but_never_the_answers(
    test_app: Any, world: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _consent(test_app, world, "session_context", "granted")
    logged: list[dict[str, Any]] = []
    monkeypatch.setattr(
        calibration_api, "log_audit_event", lambda _logger, **kw: logged.append(kw)
    )

    await _context(
        test_app, world, {"illness": "yes", "ambient_odor_detail": "burnt toast"}
    )

    (event,) = logged
    assert event["action"] == "session_context_record"
    assert event["answered"] == ["ambient_odor_detail", "illness"]
    assert "burnt toast" not in str(event)


@pytest.mark.asyncio
async def test_unknown_session_is_404(test_app: Any) -> None:
    response = await test_app.get(f"{PREFIX}/sessions/nope/context", headers=MANAGER)

    assert response.status_code == 404


# --- session timing --------------------------------------------------------


@pytest.mark.asyncio
async def test_start_records_time_zone_and_the_local_date(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/sessions/{world['session_id']}/start",
        json={
            "evaluator_timezone": "America/Denver",
            "started_at": "2026-10-30T02:30:00Z",
        },
        headers=RECORDER,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["started_at"].startswith("2026-10-30T02:30:00")
    # 02:30 UTC on the 30th is still the evening of the 29th in Denver.
    assert body["occurred_on"] == "2026-10-29"
    assert body["evaluator_timezone"] == "America/Denver"


@pytest.mark.asyncio
async def test_start_defaults_to_receipt_time(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/sessions/{world['session_id']}/start",
        json={"evaluator_timezone": "UTC"},
        headers=RECORDER,
    )

    assert response.status_code == 200
    assert response.json()["started_at"] is not None
    assert response.json()["occurred_on"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"evaluator_timezone": "Mars/Olympus"},
        {"evaluator_timezone": ""},
        {"evaluator_timezone": "UTC", "started_at": "2999-01-01T00:00:00Z"},
        {},
    ],
)
async def test_start_rejects_bad_input(
    test_app: Any, world: dict[str, str], body: dict[str, Any]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/sessions/{world['session_id']}/start", json=body, headers=RECORDER
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_session_starts_once_and_ends_once_after_starting(
    test_app: Any, world: dict[str, str]
) -> None:
    base = f"{PREFIX}/sessions/{world['session_id']}"
    assert (
        await test_app.post(f"{base}/end", json={}, headers=RECORDER)
    ).status_code == 409

    start = {"evaluator_timezone": "UTC"}
    assert (
        await test_app.post(f"{base}/start", json=start, headers=RECORDER)
    ).status_code == 200
    assert (
        await test_app.post(f"{base}/start", json=start, headers=RECORDER)
    ).status_code == 409

    ended = await test_app.post(f"{base}/end", json={}, headers=RECORDER)
    assert ended.status_code == 200
    assert ended.json()["ended_at"] is not None
    assert (
        await test_app.post(f"{base}/end", json={}, headers=RECORDER)
    ).status_code == 409


@pytest.mark.asyncio
async def test_only_assigned_people_can_start_or_end_a_session(
    test_app: Any, world: dict[str, str]
) -> None:
    base = f"{PREFIX}/sessions/{world['session_id']}"

    assert (
        await test_app.post(
            f"{base}/start", json={"evaluator_timezone": "UTC"}, headers=OUTSIDER
        )
    ).status_code == 403
    assert (
        await test_app.post(f"{base}/end", json={}, headers=OUTSIDER)
    ).status_code == 403


# --- exposure --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_blotter_exposure_is_stamped_once(
    test_app: Any, world: dict[str, str]
) -> None:
    url = f"{PREFIX}/presentations/{world['presentation_id']}/exposure"
    body = {"stage": "BLOTTER", "at": "2026-10-30T15:00:00Z"}

    first = await test_app.post(url, json=body, headers=RECORDER)

    assert first.status_code == 200
    assert first.json()["presented_at"].startswith("2026-10-30T15:00:00")
    assert first.json()["applied_at"] is None
    assert (await test_app.post(url, json=body, headers=RECORDER)).status_code == 409


@pytest.mark.asyncio
async def test_a_skin_application_needs_a_plan_then_records_method_and_zone(
    test_app: Any, world: dict[str, str]
) -> None:
    presentation = world["presentation_id"]
    url = f"{PREFIX}/presentations/{presentation}/exposure"
    body = {
        "stage": "SKIN",
        "at": "2026-10-30T15:00:00Z",
        "timezone": "America/Chicago",
        "application_method": "spray",
        "application_dose_sprays": 2,
    }
    assert (await test_app.post(url, json=body, headers=RECORDER)).status_code == 409

    plan = await test_app.post(
        f"{PREFIX}/presentations/{presentation}/skin-plan",
        json={"reason": "Highest rated"},
        headers=RECORDER,
    )
    assert plan.status_code == 200
    response = await test_app.post(url, json=body, headers=RECORDER)

    assert response.status_code == 200
    assert response.json()["applied_at"].startswith("2026-10-30T15:00:00")
    assert response.json()["application_timezone"] == "America/Chicago"
    assert (await test_app.post(url, json=body, headers=RECORDER)).status_code == 409


@pytest.mark.asyncio
async def test_skin_application_defaults_to_the_session_zone(
    test_app: Any, world: dict[str, str]
) -> None:
    presentation = world["presentation_id"]
    await test_app.post(
        f"{PREFIX}/sessions/{world['session_id']}/start",
        json={"evaluator_timezone": "America/Denver"},
        headers=RECORDER,
    )
    await test_app.post(
        f"{PREFIX}/presentations/{presentation}/skin-plan",
        json={"reason": "Highest rated"},
        headers=RECORDER,
    )

    response = await test_app.post(
        f"{PREFIX}/presentations/{presentation}/exposure",
        json={"stage": "SKIN"},
        headers=RECORDER,
    )

    assert response.json()["application_timezone"] == "America/Denver"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"stage": "BLOTTER", "application_method": "spray"},
        {"stage": "BLOTTER", "application_dose_sprays": 2},
        {"stage": "BLOTTER", "timezone": "UTC"},
        {"stage": "SKIN", "application_method": "pour"},
        {"stage": "SKIN", "application_dose_sprays": 0},
        {"stage": "SKIN", "timezone": "Mars/Olympus"},
        {"stage": "BLOTTER", "sample_container": "bucket"},
        {"stage": "BLOTTER", "sample_volume_ml": 0},
        {"stage": "BLOTTER", "at": "2999-01-01T00:00:00Z"},
    ],
)
async def test_exposure_rejects_bad_input(
    test_app: Any, world: dict[str, str], body: dict[str, Any]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/presentations/{world['presentation_id']}/exposure",
        json=body,
        headers=RECORDER,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sample_facts_ride_along_and_cannot_be_silently_changed(
    test_app: Any, world: dict[str, str]
) -> None:
    presentation = world["presentation_id"]
    url = f"{PREFIX}/presentations/{presentation}/exposure"
    facts = {
        "sample_source_type": "decant",
        "sample_container": "spray_atomizer",
        "sample_volume_ml": 2.0,
        "sample_decanted_on": "2026-10-01",
        "sample_batch_code": "L123",
        "physical_sample_confirmed": True,
    }
    assert (
        await test_app.post(url, json={"stage": "BLOTTER", **facts}, headers=RECORDER)
    ).status_code == 200

    await test_app.post(
        f"{PREFIX}/presentations/{presentation}/skin-plan",
        json={"reason": "Highest rated"},
        headers=RECORDER,
    )
    same = await test_app.post(url, json={"stage": "SKIN", **facts}, headers=RECORDER)
    assert same.status_code == 200

    # A second, different batch code for the same physical sample is a conflict.
    conflict = await test_app.post(
        url, json={"stage": "SKIN", "sample_batch_code": "L999"}, headers=RECORDER
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_only_assigned_people_can_stamp_an_exposure(
    test_app: Any, world: dict[str, str]
) -> None:
    url = f"{PREFIX}/presentations/{world['presentation_id']}/exposure"

    assert (
        await test_app.post(url, json={"stage": "BLOTTER"}, headers=OUTSIDER)
    ).status_code == 403
    assert (
        await test_app.post(url, json={"stage": "BLOTTER"}, headers=MANAGER)
    ).status_code == 200


# --- review follow-ups ------------------------------------------------------


@pytest.mark.asyncio
async def test_consent_refuses_an_unknown_reviewer_or_a_foreign_enrollment(
    test_app: Any, world: dict[str, str], approved_consent: ConsentText
) -> None:
    body = {"scope": "session_context", "event_type": "granted"}

    unknown_reviewer = await test_app.post(
        f"{PREFIX}/reviewers/no-such-reviewer/consent", json=body, headers=MANAGER
    )
    foreign = await test_app.post(
        f"{PREFIX}/reviewers/{world['reviewer_id']}/consent",
        json={**body, "enrollment_id": "no-such-enrollment"},
        headers=MANAGER,
    )
    own = await test_app.post(
        f"{PREFIX}/reviewers/{world['reviewer_id']}/consent",
        json={**body, "enrollment_id": world["enrollment_id"]},
        headers=MANAGER,
    )

    assert unknown_reviewer.status_code == 404
    assert foreign.status_code == 404
    assert own.status_code == 201


@pytest.mark.asyncio
async def test_reading_context_is_withheld_after_consent_is_withdrawn(
    test_app: Any, world: dict[str, str], approved_consent: ConsentText
) -> None:
    consent_url = f"{PREFIX}/reviewers/{world['reviewer_id']}/consent"
    url = f"{PREFIX}/sessions/{world['session_id']}/context"
    await test_app.post(
        consent_url,
        json={"scope": "session_context", "event_type": "granted"},
        headers=RECORDER,
    )
    await test_app.post(url, json={"illness": "no"}, headers=RECORDER)
    visible = (await test_app.get(url, headers=RECORDER)).json()
    await test_app.post(
        consent_url,
        json={"scope": "session_context", "event_type": "withdrawn"},
        headers=RECORDER,
    )

    withheld = (await test_app.get(url, headers=RECORDER)).json()

    assert visible["illness"] == "no"
    assert withheld == {"recorded": True, "withheld": True}
