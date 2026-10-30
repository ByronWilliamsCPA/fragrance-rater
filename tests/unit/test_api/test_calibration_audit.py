"""Audit trail on the calibration and prediction surfaces (R4, B-03).

Activation, enrollment, stage and skin-plan locks, reveal, checkpoint
creation, blind-mapping retrieval, and prediction create and link each write
one ``audit_event``. The mapping record names who retrieved which enrollment
and never what the mapping contains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import structlog

from fragrance_rater.api import calibration as calibration_api
from fragrance_rater.api import predictions as predictions_api
from fragrance_rater.core.config import settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from httpx import AsyncClient

API = "/api/v1"
PREFIX = f"{API}/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture structlog events from the audited routers.

    ``setup_logging`` caches each logger on first use, so a module logger
    used earlier in the session would bypass ``capture_logs``; fresh loggers
    bound inside the capture always reach it.
    """
    with structlog.testing.capture_logs() as logs:
        for module in (calibration_api, predictions_api):
            monkeypatch.setattr(module, "logger", structlog.get_logger(module.__name__))
        yield logs


def _audits(captured: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["action"]: e for e in captured if e.get("event") == "audit_event"}


async def _created(client: AsyncClient, url: str, body: dict[str, Any]) -> str:
    response = await client.post(url, json=body, headers=MANAGER)
    assert response.status_code == 201, (url, response.text)
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_controlled_lifecycle_writes_an_audit_trail(
    test_app: AsyncClient, captured: list[dict[str, Any]]
) -> None:
    fragrance = {
        "brand": "Audit house",
        "concentration": "EDT",
        "gender_target": "Unisex",
        "primary_family": "woody",
        "subfamily": "aromatic",
    }
    reviewer_id = await _created(test_app, f"{API}/reviewers", {"name": "Audited"})
    baseline_id = await _created(
        test_app, f"{API}/fragrances", {**fragrance, "name": "Secret baseline"}
    )
    holdout_id = await _created(
        test_app, f"{API}/fragrances", {**fragrance, "name": "Secret holdout"}
    )
    program_id = await _created(
        test_app, f"{PREFIX}/programs", {"name": "Audit", "version": "1"}
    )
    for fragrance_id, role, group in (
        (baseline_id, "UNIVERSAL_BASELINE", "Baseline"),
        (holdout_id, "HOLDOUT", "Holdout"),
    ):
        await _created(
            test_app,
            f"{PREFIX}/programs/{program_id}/members",
            {
                "fragrance_id": fragrance_id,
                "role": role,
                "identity_evidence": "Label verified",
                "group_name": group,
            },
        )

    activated = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activated.status_code == 200
    enrollment_id = await _created(
        test_app,
        f"{PREFIX}/programs/{program_id}/enroll",
        {"reviewer_id": reviewer_id, "recorder_usernames": ["recorder"]},
    )
    url = f"{PREFIX}/enrollments/{enrollment_id}"
    mapping = await test_app.get(f"{url}/mapping", headers=MANAGER)
    assert mapping.status_code == 200
    view = (await test_app.get(url, headers=RECORDER)).json()
    presentation_id = next(
        p["id"]
        for p in view["presentations"]
        if p["blind_code"]
        == next(
            m["blind_code"] for m in mapping.json() if m["fragrance_id"] == baseline_id
        )
    )
    observed = await test_app.post(
        f"{PREFIX}/presentations/{presentation_id}/observations",
        json={"stage": "BLOTTER", "detected": True, "intensity": 3, "liking": 7},
        headers=RECORDER,
    )
    assert observed.status_code == 201
    for path in (
        f"{PREFIX}/presentations/{presentation_id}/lock/BLOTTER",
        f"{url}/lock-skin-plan",
    ):
        assert (await test_app.post(path, headers=RECORDER)).status_code == 200
    checkpoint_id = await _created(
        test_app, f"{url}/checkpoints", {"algorithm_version": "audit-test"}
    )
    revealed = await test_app.post(f"{url}/reveal", headers=RECORDER)
    assert revealed.status_code == 200

    audits = _audits(captured)
    assert set(audits) >= {
        "program_activate",
        "enroll",
        "mapping_retrieve",
        "lock_stage",
        "lock_skin_plan",
        "checkpoint_create",
        "reveal",
    }
    assert audits["program_activate"]["target_id"] == program_id
    assert audits["enroll"]["target_id"] == enrollment_id
    assert audits["enroll"]["reviewer_id"] == reviewer_id
    assert audits["lock_stage"]["actor"] == "recorder"
    assert audits["checkpoint_create"]["target_id"] == checkpoint_id
    assert audits["reveal"]["actor"] == "recorder"
    for event in audits.values():
        assert event["actor"] in {"manager", "recorder"}
        assert "correlation_id" in event

    # The mapping record says who looked at which enrollment, and nothing of
    # what they saw: no fragrance, blind code, or role (B-03).
    retrieval = audits["mapping_retrieve"]
    assert retrieval["actor"] == "manager"
    assert retrieval["target_type"] == "enrollment"
    assert retrieval["target_id"] == enrollment_id
    rendered = repr(retrieval)
    for secret in (baseline_id, holdout_id, "Secret", "HOLDOUT", "BASELINE"):
        assert secret not in rendered
    for row in mapping.json():
        assert row["blind_code"] not in rendered


@pytest.mark.asyncio
async def test_prediction_create_and_link_are_audited(
    test_app: AsyncClient, captured: list[dict[str, Any]]
) -> None:
    reviewer_id = await _created(test_app, f"{API}/reviewers", {"name": "Predicted"})
    fragrance_id = await _created(
        test_app,
        f"{API}/fragrances",
        {
            "name": "Predicted scent",
            "brand": "Audit house",
            "concentration": "EDT",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
    )

    prediction_id = await _created(
        test_app,
        f"{API}/predictions",
        {
            "reviewer_id": reviewer_id,
            "fragrance_id": fragrance_id,
            "model_id": "audit-model",
            "model_version": "1",
            "predicted_scale": "1-5",
            "predicted_rating": 4.0,
        },
    )
    evaluation_id = await _created(
        test_app,
        f"{API}/evaluations",
        {"reviewer_id": reviewer_id, "fragrance_id": fragrance_id, "rating": 4},
    )
    linked = await test_app.post(
        f"{API}/predictions/{prediction_id}/outcome",
        json={"outcome_evaluation_id": evaluation_id},
        headers=MANAGER,
    )
    assert linked.status_code == 200, linked.text

    audits = _audits(captured)
    created = audits["prediction_create"]
    assert created["target_id"] == prediction_id
    assert created["reviewer_id"] == reviewer_id
    assert created["actor"] == "manager"
    # A prediction may target a holdout, so the fragrance stays out of the log.
    assert fragrance_id not in repr(created)
    link = audits["prediction_link_outcome"]
    assert link["target_id"] == prediction_id
    assert link["outcome_evaluation_id"] == evaluation_id
