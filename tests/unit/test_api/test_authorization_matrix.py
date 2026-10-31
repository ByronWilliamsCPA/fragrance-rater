"""Authorization matrix with Authentik required (R3, architecture review S-23).

Two guarantees, checked against the live route table rather than a
hand-maintained list, so a route added later without an identity check fails
here:

1. Every route outside the explicit public allowlist answers 401 to a caller
   with no verified identity when ``AUTHENTIK_REQUIRED`` is true.
2. Reviewer-keyed reads follow the owner's read policy (architecture review
   Q5, decided 2026-10-21): a manager reads every reviewer, a recorder reads
   only reviewers whose enrollment lists them, anyone else gets 403.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.routing import APIRoute

from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.main import app
from fragrance_rater.models.recommendation_measurement import (
    RecommendationImpression,
    RecommendationRun,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from httpx import AsyncClient

API = "/api/v1"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
OUTSIDER = {"X-Authentik-Username": "outsider"}
ANONYMOUS = {"X-Authentik-Username": ""}
API_KEY = "household-secret"

PUBLIC_ROUTES = {
    ("GET", "/"),
    ("GET", "/health/"),
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/health/startup"),
}
"""Routes that intentionally answer without an identity."""

PUBLIC_MODULES = {"fragrance_rater.api.catalog_stub"}
"""Root-mounted sample catalog kept for the Postman suite; scheduled for
deletion in R9 (architecture review Q1). It holds no household data."""


def _walk(router: object, prefix: str = "") -> Iterator[tuple[str, APIRoute]]:
    """Yield (full path, route) for every API route, through included routers.

    FastAPI wraps ``include_router`` targets in an internal object that keeps
    the include-time prefix on ``include_context`` instead of flattening the
    routes into ``app.routes``.
    """
    for route in getattr(router, "routes", []) or []:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
            continue
        inner = getattr(route, "original_router", None)
        if inner is not None:
            context = getattr(route, "include_context", None)
            include_prefix = str(getattr(context, "prefix", "") or "")
            yield from _walk(inner, prefix + include_prefix)


def _protected_routes() -> list[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for path, route in _walk(app):
        if route.endpoint.__module__ in PUBLIC_MODULES:
            continue
        for method in route.methods:
            if method in {"HEAD", "OPTIONS"} or (method, path) in PUBLIC_ROUTES:
                continue
            routes.add((method, path))
    return sorted(routes)


PROTECTED = _protected_routes()


@pytest.fixture
def authentik_required(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Serve as production does: identity required, a manager configured.

    Indirectly parametrized tests can pass ``False``: the identity rule must
    hold either way, so a route that slips back to the setting-dependent
    ``get_current_identity`` fails here too.
    """
    monkeypatch.setattr(settings, "authentik_required", getattr(request, "param", True))
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])
    monkeypatch.setattr(settings, "api_key", API_KEY)


def test_route_inventory_is_not_empty() -> None:
    """Guards the walk itself: an empty inventory would pass vacuously."""
    assert len(PROTECTED) > 40
    assert ("GET", f"{API}/evaluations") in PROTECTED
    assert ("POST", "/ratings") in PROTECTED


@pytest.mark.asyncio
@pytest.mark.parametrize("authentik_required", [True, False], indirect=True)
@pytest.mark.parametrize(("method", "path"), PROTECTED)
@pytest.mark.usefixtures("authentik_required")
async def test_every_protected_route_rejects_an_anonymous_caller(
    test_app: AsyncClient, method: str, path: str
) -> None:
    """No identity means 401 on every non-public route (S-05, S-06, S-23),
    whether or not ``AUTHENTIK_REQUIRED`` is set."""
    url = re.sub(r"\{[^}]+\}", "unknown-id", path)
    headers = {**ANONYMOUS, "X-API-Key": API_KEY}
    kwargs: dict[str, Any] = {"headers": headers}
    if method in {"POST", "PATCH", "PUT"}:
        kwargs["json"] = {}

    response = await test_app.request(method, url, **kwargs)

    assert response.status_code == 401, (method, path, response.text)


async def _impression(reviewer_id: str, fragrance_id: str) -> str:
    """Persist a one-item run; explanations exist only per impression (B-02)."""
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        run = RecommendationRun(
            reviewer_id=reviewer_id,
            algorithm_version="test",
            candidate_strategy="test",
            input_manifest=[],
        )
        session.add(run)
        await session.flush()
        impression = RecommendationImpression(
            run_id=run.id,
            fragrance_id=fragrance_id,
            rank=1,
            score_type="affinity",
            score_value=0.5,
        )
        session.add(impression)
        await session.commit()
        return impression.id
    finally:
        await sessions.aclose()


async def _reviewer_with_recorder(client: AsyncClient) -> dict[str, str]:
    """Create two reviewers, one enrolled with ``recorder``, plus evidence."""

    async def post(url: str, body: dict[str, Any]) -> dict[str, Any]:
        response = await client.post(url, json=body, headers=MANAGER)
        assert response.status_code == 201, (url, response.text)
        return dict(response.json())

    fragrance_body = {
        "brand": "Matrix house",
        "concentration": "EDT",
        "gender_target": "Unisex",
        "primary_family": "woody",
        "subfamily": "aromatic",
    }
    assigned = await post(f"{API}/reviewers", {"name": "Assigned evaluator"})
    other = await post(f"{API}/reviewers", {"name": "Other evaluator"})
    baseline = await post(f"{API}/fragrances", {**fragrance_body, "name": "Baseline"})
    holdout = await post(f"{API}/fragrances", {**fragrance_body, "name": "Holdout"})
    program = await post(
        f"{API}/calibration/programs", {"name": "Matrix", "version": "1"}
    )
    for fragrance, role, group in (
        (baseline, "UNIVERSAL_BASELINE", "Baseline"),
        (holdout, "HOLDOUT", "Holdout"),
    ):
        await post(
            f"{API}/calibration/programs/{program['id']}/members",
            {
                "fragrance_id": fragrance["id"],
                "role": role,
                "identity_evidence": "Label verified",
                "group_name": group,
            },
        )
    activated = await client.post(
        f"{API}/calibration/programs/{program['id']}/activate", headers=MANAGER
    )
    assert activated.status_code == 200, activated.text
    enrollment = await post(
        f"{API}/calibration/programs/{program['id']}/enroll",
        {"reviewer_id": assigned["id"], "recorder_usernames": ["recorder"]},
    )
    assigned_eval = await post(
        f"{API}/evaluations",
        {"reviewer_id": assigned["id"], "fragrance_id": baseline["id"], "rating": 4},
    )
    other_eval = await post(
        f"{API}/evaluations",
        {"reviewer_id": other["id"], "fragrance_id": baseline["id"], "rating": 2},
    )
    return {
        "enrollment": enrollment["id"],
        "assigned": assigned["id"],
        "other": other["id"],
        "fragrance": baseline["id"],
        "assigned_eval": assigned_eval["id"],
        "other_eval": other_eval["id"],
        "assigned_impression": await _impression(assigned["id"], baseline["id"]),
        "other_impression": await _impression(other["id"], baseline["id"]),
        "holdout_impression": await _impression(assigned["id"], holdout["id"]),
    }


def _reads(ids: dict[str, str], reviewer: str) -> list[str]:
    reviewer_id = ids[reviewer]
    impression_id = ids[f"{reviewer}_impression"]
    return [
        f"{API}/evaluations?reviewer_id={reviewer_id}",
        f"{API}/evaluations/{ids[f'{reviewer}_eval']}",
        f"{API}/recommendations/{reviewer_id}",
        f"{API}/recommendations/{reviewer_id}/profile?include_llm=false",
        f"{API}/recommendation-measurement/impressions/{impression_id}/explanation",
        f"{API}/recommendation-measurement/impressions/{impression_id}/linkable-outcomes",
        f"{API}/calibration/history/{reviewer_id}",
    ]


@pytest.mark.asyncio
@pytest.mark.usefixtures("authentik_required")
async def test_reviewer_reads_follow_the_read_policy(test_app: AsyncClient) -> None:
    """Manager: everyone. Assigned recorder: that reviewer only. Others: 403."""
    ids = await _reviewer_with_recorder(test_app)
    keyed = {"X-API-Key": API_KEY}

    for url in _reads(ids, "assigned"):
        manager = await test_app.get(url, headers={**MANAGER, **keyed})
        recorder = await test_app.get(url, headers={**RECORDER, **keyed})
        outsider = await test_app.get(url, headers={**OUTSIDER, **keyed})
        assert manager.status_code not in {401, 403}, (url, manager.text)
        assert recorder.status_code not in {401, 403}, (url, recorder.text)
        assert outsider.status_code == 403, (url, outsider.text)

    for url in _reads(ids, "other"):
        manager = await test_app.get(url, headers={**MANAGER, **keyed})
        recorder = await test_app.get(url, headers={**RECORDER, **keyed})
        assert manager.status_code not in {401, 403}, (url, manager.text)
        assert recorder.status_code == 403, (url, recorder.text)


@pytest.mark.asyncio
@pytest.mark.usefixtures("authentik_required")
async def test_fragrance_filtered_history_keeps_only_readable_reviewers(
    test_app: AsyncClient,
) -> None:
    """Listing by fragrance spans reviewers, so it is filtered, not refused."""
    ids = await _reviewer_with_recorder(test_app)
    url = f"{API}/evaluations?fragrance_id={ids['fragrance']}"

    def reviewers(response: Any) -> set[str]:
        assert response.status_code == 200, response.text
        return {item["reviewer_id"] for item in response.json()}

    assert reviewers(await test_app.get(url, headers=MANAGER)) == {
        ids["assigned"],
        ids["other"],
    }
    assert reviewers(await test_app.get(url, headers=RECORDER)) == {ids["assigned"]}
    assert reviewers(await test_app.get(url, headers=OUTSIDER)) == set()


@pytest.mark.asyncio
@pytest.mark.usefixtures("authentik_required")
async def test_catalog_and_reviewer_names_need_only_an_identity(
    test_app: AsyncClient,
) -> None:
    """Names and the catalog are household-wide; they need a named caller."""
    for url in (f"{API}/reviewers", f"{API}/fragrances"):
        assert (await test_app.get(url, headers=OUTSIDER)).status_code == 200
        assert (await test_app.get(url, headers=ANONYMOUS)).status_code == 401


@pytest.mark.asyncio
@pytest.mark.usefixtures("authentik_required")
async def test_outcome_metrics_stay_manager_only(test_app: AsyncClient) -> None:
    """P2 outcome metrics are manager reporting, stricter than the read policy."""
    ids = await _reviewer_with_recorder(test_app)
    url = f"{API}/recommendation-measurement/reviewers/{ids['assigned']}/metrics"

    assert (await test_app.get(url, headers=MANAGER)).status_code == 200
    assert (await test_app.get(url, headers=RECORDER)).status_code == 403


@pytest.mark.asyncio
@pytest.mark.usefixtures("authentik_required")
async def test_training_eligibility_and_linkage_stay_manager_only(
    test_app: AsyncClient,
) -> None:
    """R8 PR 2: eligibility decisions and the role/repeat linkage (X-06).

    Even the recorder assigned to the reviewer gets 403: the linkage is the
    blind mapping, and an eligibility decision is a manager's call.
    """
    ids = await _reviewer_with_recorder(test_app)
    decide = f"{API}/training-eligibility/evaluation/{ids['assigned_eval']}"
    body = {"training_eligibility": "withheld", "reason": "Matrix check"}
    linkage = f"{API}/calibration/enrollments/{ids['enrollment']}/linkage"

    for headers in (RECORDER, OUTSIDER):
        refused = await test_app.put(decide, json=body, headers=headers)
        assert refused.status_code == 403, refused.text
        assert (await test_app.get(linkage, headers=headers)).status_code == 403
    refused = await test_app.put(decide, json=body, headers=ANONYMOUS)
    assert refused.status_code == 401, refused.text
    assert (await test_app.get(linkage, headers=ANONYMOUS)).status_code == 401

    decided = await test_app.put(decide, json=body, headers=MANAGER)
    assert decided.status_code == 200, decided.text
    assert decided.json()["previous"] == "eligible"
    assert (await test_app.get(linkage, headers=MANAGER)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("authentik_required")
async def test_holdout_answers_are_role_neutral(test_app: AsyncClient) -> None:
    """A holdout is never named or distinguishable to the recorder (B-01, B-02).

    An impression whose fragrance became the reviewer's holdout explains
    exactly like an ordinary impression while the reviewer has too little
    data, and like a missing impression once they have enough; feedback on it
    is refused without naming the membership role (ADR-005).
    """
    ids = await _reviewer_with_recorder(test_app)
    base = f"{API}/recommendation-measurement/impressions"

    async def explain(impression_id: str) -> tuple[int, object]:
        response = await test_app.get(
            f"{base}/{impression_id}/explanation", headers=RECORDER
        )
        return response.status_code, response.json()

    # Too little data: the holdout answers exactly like an ordinary impression,
    # because the fragrance-independent check runs first.
    assert await explain(ids["holdout_impression"]) == await explain(
        ids["assigned_impression"]
    )
    assert (await explain(ids["holdout_impression"]))[0] == 400

    # Enough data: the holdout answers exactly like a missing impression.
    for name in ("Second", "Third"):
        fragrance = await test_app.post(
            f"{API}/fragrances",
            json={
                "brand": "Matrix house",
                "name": name,
                "concentration": "EDT",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
            headers=MANAGER,
        )
        assert fragrance.status_code == 201, fragrance.text
        evaluation = await test_app.post(
            f"{API}/evaluations",
            json={
                "reviewer_id": ids["assigned"],
                "fragrance_id": fragrance.json()["id"],
                "rating": 3,
            },
            headers=MANAGER,
        )
        assert evaluation.status_code == 201, evaluation.text
    holdout = await explain(ids["holdout_impression"])
    assert holdout == await explain("no-such-impression")
    assert holdout[0] == 404

    feedback = await test_app.post(
        f"{base}/{ids['holdout_impression']}/responses",
        json={"interested": True},
        headers=RECORDER,
    )
    assert feedback.status_code == 409
    assert "holdout" not in feedback.text.lower()
    assert "role" not in feedback.text.lower()
