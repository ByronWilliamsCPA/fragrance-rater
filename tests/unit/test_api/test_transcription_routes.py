"""Transcription of a paper column through the real routes (F1).

The facilitator sends the paper's first-smell time as the exposure ``at``, the
column-finished time as ``observed_at`` and the spray time as ``sprayed_at``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio

from fragrance_rater.core.config import settings

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}


def _at(**delta: float) -> str:
    """A time ``delta`` before now (the ``world`` fixture backdates its sessions)."""
    return (datetime.now(UTC) - timedelta(**delta)).isoformat()


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


@pytest_asyncio.fixture
async def world(test_app: Any, backdate_sessions: Any) -> dict[str, str]:
    """One reviewer, one active program with one baseline sample, one enrollment."""
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
    await backdate_sessions()
    return {
        "enrollment_id": enrollment_id,
        "presentation_id": presentation["id"],
        "session_id": presentation["session_id"],
        "blind_code": presentation["blind_code"],
    }


def _exposure_url(world: dict[str, str]) -> str:
    return f"{PREFIX}/presentations/{world['presentation_id']}/exposure"


async def _flags(test_app: Any, world: dict[str, str]) -> list[dict[str, Any]]:
    response = await test_app.get(
        f"{PREFIX}/sessions/{world['session_id']}/quality-flags", headers=RECORDER
    )
    assert response.status_code == 200
    return response.json()


# --- presented_at ----------------------------------------------------------


@pytest.mark.asyncio
async def test_the_paper_first_smell_time_is_stored_as_presented_at(
    test_app: Any, world: dict[str, str]
) -> None:
    smelled = _at(seconds=90)

    response = await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "at": smelled, "sprayed_at": _at(minutes=2)},
        headers=RECORDER,
    )

    assert response.status_code == 200
    stored = datetime.fromisoformat(response.json()["presented_at"])
    assert stored == datetime.fromisoformat(smelled).replace(tzinfo=None) or (
        abs((stored - datetime.fromisoformat(smelled).replace(tzinfo=None)).seconds) < 1
    )
    assert response.json()["ceiling_flag_id"] is None
    view = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}", headers=RECORDER
    )
    assert view.json()["presentations"][0]["presented_at"] is not None


@pytest.mark.asyncio
async def test_an_exposure_without_a_time_keeps_the_old_behavior(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        _exposure_url(world), json={"stage": "BLOTTER"}, headers=RECORDER
    )

    assert response.status_code == 200
    assert response.json()["presented_at"] is not None
    assert response.json()["ceiling_flag_id"] is None


@pytest.mark.asyncio
async def test_a_first_smell_before_the_session_existed_is_refused(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "at": _at(days=5)},
        headers=RECORDER,
    )

    assert response.status_code == 422
    assert "before this session existed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_the_stamp_stays_once_only(test_app: Any, world: dict[str, str]) -> None:
    body = {"stage": "BLOTTER", "at": _at(seconds=5)}
    assert (
        await test_app.post(_exposure_url(world), json=body, headers=RECORDER)
    ).status_code == 200

    again = await test_app.post(_exposure_url(world), json=body, headers=RECORDER)

    assert again.status_code == 409


# --- ceiling deviation -----------------------------------------------------


@pytest.mark.asyncio
async def test_a_first_smell_over_the_ceiling_is_kept_and_flagged(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        _exposure_url(world),
        json={
            "stage": "BLOTTER",
            "sprayed_at": _at(minutes=9),
            "at": _at(minutes=2),
        },
        headers=RECORDER,
    )

    assert response.status_code == 200
    assert response.json()["presented_at"] is not None
    flag_id = response.json()["ceiling_flag_id"]
    assert flag_id is not None
    flags = await _flags(test_app, world)
    raised = [row for row in flags if row["id"] == flag_id]
    assert len(raised) == 1
    assert raised[0]["code"] == "spray_to_smell_ceiling_exceeded"
    assert raised[0]["source"] == "automatic_validation"
    assert raised[0]["action"] == "raised"
    assert "ceiling" in raised[0]["explanation"]


@pytest.mark.asyncio
async def test_a_first_smell_exactly_at_the_ceiling_is_not_flagged(
    test_app: Any, world: dict[str, str]
) -> None:
    now = datetime.now(UTC)
    response = await test_app.post(
        _exposure_url(world),
        json={
            "stage": "BLOTTER",
            "sprayed_at": (now - timedelta(minutes=4)).isoformat(),
            "at": (now - timedelta(minutes=2)).isoformat(),
        },
        headers=RECORDER,
    )

    assert response.status_code == 200
    assert response.json()["ceiling_flag_id"] is None
    assert await _flags(test_app, world) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("gap_seconds", "flagged"),
    [(120, False), (121, True), (180, True)],
)
async def test_the_two_minute_ceiling_boundary_is_judged_on_the_gap(
    test_app: Any, world: dict[str, str], gap_seconds: int, flagged: bool
) -> None:
    """A 3-minute gap breaches; exactly 2 minutes does not (it would pass at 5)."""
    now = datetime.now(UTC)
    response = await test_app.post(
        _exposure_url(world),
        json={
            "stage": "BLOTTER",
            "sprayed_at": (now - timedelta(minutes=10)).isoformat(),
            "at": (
                now - timedelta(minutes=10) + timedelta(seconds=gap_seconds)
            ).isoformat(),
        },
        headers=RECORDER,
    )

    assert response.status_code == 200
    assert (response.json()["ceiling_flag_id"] is not None) is flagged
    codes = [row["code"] for row in await _flags(test_app, world)]
    assert codes == (["spray_to_smell_ceiling_exceeded"] if flagged else [])


@pytest.mark.asyncio
async def test_the_ceiling_flag_names_the_current_rule_version(
    test_app: Any, world: dict[str, str]
) -> None:
    from sqlalchemy import select

    from fragrance_rater.core.database import get_db
    from fragrance_rater.main import app
    from fragrance_rater.models.calibration import QualityFlag
    from fragrance_rater.services.transcription_timing import CEILING_RULE_VERSION

    assert CEILING_RULE_VERSION == "spray-to-smell-ceiling-v2"
    await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "sprayed_at": _at(minutes=9), "at": _at(minutes=5)},
        headers=RECORDER,
    )

    versions: list[str | None] = []
    async for db in app.dependency_overrides[get_db]():
        versions = list(
            await db.scalars(
                select(QualityFlag.rule_version).where(
                    QualityFlag.code == "spray_to_smell_ceiling_exceeded"
                )
            )
        )
    assert versions == ["spray-to-smell-ceiling-v2"]


async def _training_rows() -> set[str]:
    from sqlalchemy import text

    from fragrance_rater.core.database import get_db
    from fragrance_rater.main import app

    rows: set[str] = set()
    async for db in app.dependency_overrides[get_db]():
        rows = set(await db.scalars(text("SELECT row_id FROM v_training_rows")))
    return rows


@pytest.mark.asyncio
async def test_a_ceiling_breach_withholds_training_until_the_flag_is_closed(
    test_app: Any, world: dict[str, str]
) -> None:
    """Unlike group_shared_blotter, the ceiling flag is NOT informational."""
    from fragrance_rater.services.group_blotter import INFORMATIONAL_FLAG_CODES
    from fragrance_rater.services.transcription_timing import CEILING_FLAG_CODE

    assert CEILING_FLAG_CODE == "spray_to_smell_ceiling_exceeded"
    assert CEILING_FLAG_CODE not in INFORMATIONAL_FLAG_CODES
    assert "group_shared_blotter" in INFORMATIONAL_FLAG_CODES

    presentation_id = world["presentation_id"]
    exposure = await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "sprayed_at": _at(minutes=9), "at": _at(minutes=5)},
        headers=RECORDER,
    )
    flag_id = exposure.json()["ceiling_flag_id"]
    assert flag_id is not None
    observed = await test_app.post(
        f"{PREFIX}/presentations/{presentation_id}/observations",
        json={"stage": "BLOTTER", "detected": True, "liking": 6},
        headers=RECORDER,
    )
    assert observed.status_code == 201, observed.text
    row_id = observed.json()["id"]
    locked = await test_app.post(
        f"{PREFIX}/presentations/{presentation_id}/lock/BLOTTER", headers=RECORDER
    )
    assert locked.status_code == 200, locked.text

    linkage = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/linkage", headers=MANAGER
    )
    assert {r["training_eligibility"] for r in linkage.json()} == {"questionable"}
    assert row_id not in await _training_rows()

    closed = await test_app.post(
        f"{PREFIX}/quality-flags",
        json={
            "action": "invalidated",
            "source": "recorder",
            "disposition": "include",
            "supersedes_id": flag_id,
        },
        headers=RECORDER,
    )
    assert closed.status_code == 201, closed.text
    linkage = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/linkage", headers=MANAGER
    )
    assert {r["training_eligibility"] for r in linkage.json()} == {"eligible"}
    assert row_id in await _training_rows()


@pytest.mark.asyncio
async def test_a_first_smell_before_the_spray_is_a_422(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        _exposure_url(world),
        json={
            "stage": "BLOTTER",
            "sprayed_at": _at(minutes=1),
            "at": _at(minutes=2),
        },
        headers=RECORDER,
    )

    assert response.status_code == 422


# --- blind code confirmation ----------------------------------------------


@pytest.mark.asyncio
async def test_a_wrong_blind_code_refuses_the_exposure_and_the_observation(
    test_app: Any, world: dict[str, str]
) -> None:
    wrong = "ZZZZZZZZ"
    exposure = await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "confirmed_blind_code": wrong},
        headers=RECORDER,
    )
    observation = await test_app.post(
        f"{PREFIX}/presentations/{world['presentation_id']}/observations",
        json={"stage": "BLOTTER", "detected": True, "confirmed_blind_code": wrong},
        headers=RECORDER,
    )

    assert exposure.status_code == 409
    assert observation.status_code == 409
    assert "does not match this sample" in observation.json()["detail"]
    view = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}", headers=RECORDER
    )
    sample = view.json()["presentations"][0]
    assert sample["observations"] == []
    assert sample["presented_at"] is None


@pytest.mark.asyncio
async def test_the_right_blind_code_matches_ignoring_case_and_spaces(
    test_app: Any, world: dict[str, str]
) -> None:
    code = f"  {world['blind_code'].lower()} "

    response = await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "confirmed_blind_code": code},
        headers=RECORDER,
    )

    assert response.status_code == 200


# --- observed_at and elapsed_minutes --------------------------------------


@pytest.mark.asyncio
async def test_a_transcribed_column_stores_finish_time_and_whole_minutes(
    test_app: Any, world: dict[str, str]
) -> None:
    sprayed, smelled, finished = (
        _at(minutes=20),
        _at(minutes=19),
        _at(minutes=7, seconds=30),
    )
    await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "sprayed_at": sprayed, "at": smelled},
        headers=RECORDER,
    )

    response = await test_app.post(
        f"{PREFIX}/presentations/{world['presentation_id']}/observations",
        json={
            "stage": "BLOTTER",
            "detected": True,
            "intensity": 3,
            "sprayed_at": sprayed,
            "observed_at": finished,
            "confirmed_blind_code": world["blind_code"],
            "idempotency_key": "transcribe-key-1",
        },
        headers=RECORDER,
    )

    assert response.status_code == 201
    view = await test_app.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}", headers=RECORDER
    )
    stored = view.json()["presentations"][0]["observations"][0]
    assert stored["elapsed_minutes"] == 12
    assert stored["observed_at"].startswith(
        datetime.fromisoformat(finished).strftime("%Y-%m-%dT%H:%M:%S")
    )
    assert "sprayed_at" not in stored
    assert "confirmed_blind_code" not in stored


@pytest.mark.asyncio
async def test_a_retried_transcribed_column_is_a_replay_not_a_second_row(
    test_app: Any, world: dict[str, str]
) -> None:
    body = {
        "stage": "BLOTTER",
        "detected": True,
        "intensity": 3,
        "sprayed_at": _at(minutes=20),
        "observed_at": _at(minutes=7),
        "confirmed_blind_code": world["blind_code"],
        "idempotency_key": "transcribe-key-2",
    }
    url = f"{PREFIX}/presentations/{world['presentation_id']}/observations"
    first = await test_app.post(url, json=body, headers=RECORDER)

    second = await test_app.post(url, json=body, headers=RECORDER)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["replayed"] is True


@pytest.mark.asyncio
async def test_a_column_cannot_finish_before_the_first_smell(
    test_app: Any, world: dict[str, str]
) -> None:
    await test_app.post(
        _exposure_url(world),
        json={"stage": "BLOTTER", "at": _at(minutes=5)},
        headers=RECORDER,
    )

    response = await test_app.post(
        f"{PREFIX}/presentations/{world['presentation_id']}/observations",
        json={"stage": "BLOTTER", "detected": True, "observed_at": _at(minutes=9)},
        headers=RECORDER,
    )

    assert response.status_code == 422
    assert "before the blotter was first smelled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_column_finished_before_the_session_existed_is_refused(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/presentations/{world['presentation_id']}/observations",
        json={"stage": "BLOTTER", "detected": True, "observed_at": _at(days=5)},
        headers=RECORDER,
    )

    assert response.status_code == 422


# --- session times ---------------------------------------------------------


@pytest.mark.asyncio
async def test_session_start_and_end_take_the_paper_times_within_the_window(
    test_app: Any, world: dict[str, str]
) -> None:
    base = f"{PREFIX}/sessions/{world['session_id']}"
    started = await test_app.post(
        f"{base}/start",
        json={"evaluator_timezone": "UTC", "started_at": _at(minutes=40)},
        headers=RECORDER,
    )
    ended = await test_app.post(
        f"{base}/end", json={"ended_at": _at(minutes=2)}, headers=RECORDER
    )

    assert started.status_code == 200
    assert ended.status_code == 200
    assert ended.json()["ended_at"] is not None


@pytest.mark.asyncio
async def test_a_session_start_before_the_session_existed_is_refused(
    test_app: Any, world: dict[str, str]
) -> None:
    response = await test_app.post(
        f"{PREFIX}/sessions/{world['session_id']}/start",
        json={"evaluator_timezone": "UTC", "started_at": _at(days=5)},
        headers=RECORDER,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_ranking_time_outside_the_sitting_is_refused_before_anything_else(
    test_app: Any, world: dict[str, str]
) -> None:
    url = f"{PREFIX}/sessions/{world['session_id']}/rankings"
    body = {"stage": "BLOTTER", "response_status": "skipped"}

    too_early = await test_app.post(
        url, json={**body, "ranked_at": _at(days=5)}, headers=RECORDER
    )
    plausible = await test_app.post(
        url, json={**body, "ranked_at": _at(minutes=3)}, headers=RECORDER
    )

    assert too_early.status_code == 422
    assert "before this session existed" in too_early.json()["detail"]
    # A plausible time passes the timing rule and meets the next rule instead
    # (no sample has been assessed yet), which is a 409, not a 422.
    assert plausible.status_code == 409
