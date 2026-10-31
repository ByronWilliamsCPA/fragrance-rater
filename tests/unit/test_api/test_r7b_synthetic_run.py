"""A synthetic session through the API: every R7a/R7b field reaches the export.

``PROJECT-PLAN.md`` R7b acceptance: a synthetic run (one enrollment, one session,
one skin wear, one ranking, one flagged deviation) produces an export where each
field the instrument captures is non-null for at least one row. This test is the
repository-level guard for that criterion; the deployed run through the released
UI (P6.3) attaches its own export.

If a captured field is added without being written by the instrument, or is
written but dropped from the export, this fails and names it.
"""

from __future__ import annotations

from typing import Any

import pytest

from fragrance_rater.api import calibration as calibration_api
from fragrance_rater.core.config import settings
from fragrance_rater.services import consent as consent_module
from fragrance_rater.services.consent import ConsentText

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}

APPROVED = ConsentText(
    version="family-consent-v1",
    status="APPROVED",
    sha256="c" * 64,
    body="Version: family-consent-v1\nStatus: APPROVED\n\nApproved test wording.\n",
)

# Every field the instrument captures, by where it appears in the export.
PROGRAM_FIELDS = ("instrument_version",)
ENROLLMENT_FIELDS = ("randomization_algorithm",)
SESSION_FIELDS = ("occurred_on", "started_at", "ended_at", "evaluator_timezone")
CONTEXT_FIELDS = (
    "illness",
    "nasal_congestion",
    "allergy_symptoms",
    "hunger",
    "hours_since_food",
    "hours_since_caffeine",
    "personal_fragrance_worn",
    "ambient_odor",
    "ambient_odor_detail",
    "room_temperature_c",
    "room_humidity_pct",
    "hormonal_context",
    "note",
)
PRESENTATION_FIELDS = (
    "intended_position",
    "presented_at",
    "applied_at",
    "application_timezone",
    "application_method",
    "application_dose_sprays",
    "sample_source_type",
    "sample_container",
    "sample_volume_ml",
    "sample_acquired_on",
    "sample_decanted_on",
    "sample_opened_on",
    "sample_batch_code",
    "physical_sample_confirmed",
)
OBSERVATION_FIELDS = (
    "observed_at",
    "response_status",
    "recognition",
    "owned_or_worn",
    "scrubbed_off",
    "time_to_scrub_minutes",
    "last_detected_elapsed_min",
    "first_not_detected_elapsed_min",
)
RANK_ENTRY_FIELDS = ("eligible_for_rank", "rank_position")
FLAG_FIELDS = ("code", "severity", "source", "disposition", "explanation")


def _non_null_somewhere(
    rows: list[dict[str, Any]], fields: tuple[str, ...]
) -> list[str]:
    """Return the fields that are null in every row."""
    return [f for f in fields if all(row.get(f) is None for row in rows)]


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])
    monkeypatch.setattr(consent_module, "load_consent_text", lambda: APPROVED)
    monkeypatch.setattr(calibration_api, "load_consent_text", lambda: APPROVED)


async def _ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


@pytest.mark.asyncio
async def test_a_full_session_exports_every_captured_field(test_app: Any) -> None:
    reviewer = await _ok(
        await test_app.post(
            "/api/v1/reviewers", json={"name": "Evaluator"}, headers=MANAGER
        ),
        201,
    )
    program = await _ok(
        await test_app.post(
            f"{PREFIX}/programs",
            json={"name": "Protocol", "version": "1"},
            headers=MANAGER,
        ),
        201,
    )
    for index in range(3):
        fragrance = await _ok(
            await test_app.post(
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
            ),
            201,
        )
        await _ok(
            await test_app.post(
                f"{PREFIX}/programs/{program['id']}/members",
                json={
                    "fragrance_id": fragrance["id"],
                    "role": "UNIVERSAL_BASELINE",
                    "identity_evidence": "Label verified",
                },
                headers=MANAGER,
            ),
            201,
        )
    await _ok(
        await test_app.post(
            f"{PREFIX}/programs/{program['id']}/activate", headers=MANAGER
        )
    )
    enrollment = await _ok(
        await test_app.post(
            f"{PREFIX}/programs/{program['id']}/enroll",
            json={"reviewer_id": reviewer["id"], "recorder_usernames": ["recorder"]},
            headers=MANAGER,
        ),
        201,
    )
    view = await _ok(
        await test_app.get(f"{PREFIX}/enrollments/{enrollment['id']}", headers=RECORDER)
    )
    first, second, third = (p["id"] for p in view["presentations"])
    session_id = view["presentations"][0]["session_id"]

    # Consent, then the session opens and its conditions are recorded.
    await _ok(
        await test_app.post(
            f"{PREFIX}/reviewers/{reviewer['id']}/consent",
            json={"scope": "session_context", "event_type": "granted"},
            headers=RECORDER,
        ),
        201,
    )
    await _ok(
        await test_app.post(
            f"{PREFIX}/sessions/{session_id}/start",
            json={"evaluator_timezone": "America/New_York"},
            headers=RECORDER,
        )
    )
    await _ok(
        await test_app.post(
            f"{PREFIX}/sessions/{session_id}/context",
            json={
                "illness": "no",
                "nasal_congestion": "no",
                "allergy_symptoms": "no",
                "hunger": "not_hungry",
                "hours_since_food": 2.5,
                "hours_since_caffeine": 4,
                "personal_fragrance_worn": "no",
                "ambient_odor": "yes",
                "ambient_odor_detail": "Coffee brewing",
                "room_temperature_c": 21.5,
                "room_humidity_pct": 45,
                "hormonal_context": "not_applicable",
                "note": "Quiet room",
            },
            headers=RECORDER,
        ),
        201,
    )

    # Blotter: every sample is smelled; one is not detected.
    for presentation_id in (first, second, third):
        await _ok(
            await test_app.post(
                f"{PREFIX}/presentations/{presentation_id}/exposure",
                json={"stage": "BLOTTER"},
                headers=RECORDER,
            )
        )
    for presentation_id, detected in ((first, True), (second, True), (third, False)):
        await _ok(
            await test_app.post(
                f"{PREFIX}/presentations/{presentation_id}/observations",
                json={
                    "stage": "BLOTTER",
                    "detected": detected,
                    "intensity": 3 if detected else 0,
                    "liking": 6 if detected else None,
                    "response_status": "completed" if detected else "not_detected",
                    "recognition": "vaguely_familiar",
                    "owned_or_worn": "no",
                    "observed_at": "2026-10-30T14:00:00Z",
                },
                headers=RECORDER,
            ),
            201,
        )

    # One skin wear, with sample facts, scrub-off, an interval, and fit choices.
    await _ok(
        await test_app.post(
            f"{PREFIX}/presentations/{first}/skin-plan",
            json={"reason": "Low confidence"},
            headers=RECORDER,
        )
    )
    await _ok(
        await test_app.post(
            f"{PREFIX}/enrollments/{enrollment['id']}/lock-skin-plan", headers=RECORDER
        )
    )
    await _ok(
        await test_app.post(
            f"{PREFIX}/presentations/{first}/exposure",
            json={
                "stage": "SKIN",
                "timezone": "America/New_York",
                "application_method": "spray",
                "application_dose_sprays": 2,
                "sample_source_type": "decant",
                "sample_container": "spray_atomizer",
                "sample_volume_ml": 5,
                "sample_acquired_on": "2026-09-01",
                "sample_decanted_on": "2026-09-02",
                "sample_opened_on": "2026-09-03",
                "sample_batch_code": "B-42",
                "physical_sample_confirmed": True,
            },
            headers=RECORDER,
        )
    )
    await _ok(
        await test_app.post(
            f"{PREFIX}/presentations/{first}/observations",
            json={
                "stage": "SKIN",
                "elapsed_minutes": 480,
                "detected": True,
                "intensity": 1,
                "response_status": "completed",
                "scrubbed_off": True,
                "time_to_scrub_minutes": 500,
                "last_detected_elapsed_min": 240,
                "first_not_detected_elapsed_min": 480,
                "season_fit": ["spring", "fall"],
                "setting_fit": ["home"],
                "observed_at": "2026-10-30T22:00:00Z",
            },
            headers=RECORDER,
        ),
        201,
    )

    # Ranking of the two detected samples, one flagged deviation, then the end.
    await _ok(
        await test_app.post(
            f"{PREFIX}/sessions/{session_id}/rankings",
            json={
                "stage": "BLOTTER",
                "response_status": "completed",
                "entries": [
                    {"presentation_id": first, "rank_position": 1},
                    {"presentation_id": second, "rank_position": 2},
                ],
            },
            headers=RECORDER,
        ),
        201,
    )
    await _ok(
        await test_app.post(
            f"{PREFIX}/quality-flags",
            json={
                "action": "raised",
                "source": "evaluator",
                "disposition": "review",
                "target_type": "presentation",
                "target_id": second,
                "code": "competing_odor",
                "severity": "minor",
                "explanation": "Cooking smell",
            },
            headers=RECORDER,
        ),
        201,
    )
    await _ok(
        await test_app.post(
            f"{PREFIX}/sessions/{session_id}/end", json={}, headers=RECORDER
        )
    )

    export = await _ok(
        await test_app.get(
            f"{PREFIX}/enrollments/{enrollment['id']}/evidence-export", headers=MANAGER
        )
    )

    sessions = export["sessions"]
    presentations = [p for s in sessions for p in s["presentations"]]
    observations = [o for p in presentations for o in p["observations"]]
    rank_entries = [e for s in sessions for r in s["rankings"] for e in r["entries"]]
    flags = [f for s in sessions for f in s["quality_flags"]]
    missing = {
        "program": _non_null_somewhere([export["program"]], PROGRAM_FIELDS),
        "enrollment": _non_null_somewhere([export["enrollment"]], ENROLLMENT_FIELDS),
        "session": _non_null_somewhere(sessions, SESSION_FIELDS),
        "context": _non_null_somewhere(
            [s["context"] or {} for s in sessions], CONTEXT_FIELDS
        ),
        "presentation": _non_null_somewhere(presentations, PRESENTATION_FIELDS),
        "observation": _non_null_somewhere(observations, OBSERVATION_FIELDS),
        "rank_entry": _non_null_somewhere(rank_entries, RANK_ENTRY_FIELDS),
        "flag": _non_null_somewhere(flags, FLAG_FIELDS),
    }
    assert {name: fields for name, fields in missing.items() if fields} == {}

    # Season and setting fit are multi-select child rows, not columns.
    season = {c for o in observations for c in o["fit_choices"]["season"]}
    setting = {c for o in observations for c in o["fit_choices"]["setting"]}
    assert season == {"spring", "fall"}
    assert setting == {"home"}
    # Consent is stamped with the wording it was recorded against.
    assert export["consent"]["events"][0]["consent_text_version"] == "family-consent-v1"
    assert export["consent"]["state"]["session_context"] == "granted"
    # Identity stays concealed in the export.
    assert "Concealed" not in str(export)
