"""Calibration manager/recorder authorization and end-to-end lifecycle."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from fragrance_rater.core.config import settings
from fragrance_rater.services.fragella_client import FragellaError, FragellaResult

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
RECORDER = {"X-Authentik-Username": "recorder"}
OUTSIDER = {"X-Authentik-Username": "outsider"}


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


@pytest.mark.asyncio
async def test_anonymous_and_non_manager_cannot_manage_programs(test_app):
    data = {"name": "Test protocol", "version": "1"}
    response = await test_app.post(f"{PREFIX}/programs", json=data)
    assert response.status_code == 401
    response = await test_app.post(f"{PREFIX}/programs", json=data, headers=RECORDER)
    assert response.status_code == 403
    response = await test_app.get(
        f"{PREFIX}/programs/unknown/members", headers=RECORDER
    )
    assert response.status_code == 403
    response = await test_app.get(f"{PREFIX}/access", headers=RECORDER)
    assert response.json() == {"username": "recorder", "manager": False}


@pytest.mark.asyncio
async def test_controlled_lifecycle_authorization_and_reveal(test_app):
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
    holdout = await test_app.post(
        "/api/v1/fragrances",
        json={
            "name": "Future holdout",
            "brand": "Concealed house",
            "concentration": "EDT",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
        headers=MANAGER,
    )
    assert reviewer.status_code == fragrance.status_code == holdout.status_code == 201
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Protocol", "version": "1"}, headers=MANAGER
    )
    assert program.status_code == 201
    program_id = program.json()["id"]
    activation = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activation.status_code == 409
    member = await test_app.post(
        f"{PREFIX}/programs/{program_id}/members",
        json={
            "fragrance_id": fragrance.json()["id"],
            "role": "UNIVERSAL_BASELINE",
            "identity_evidence": "Label verified",
        },
        headers=MANAGER,
    )
    assert member.status_code == 201
    holdout_member = await test_app.post(
        f"{PREFIX}/programs/{program_id}/members",
        json={
            "fragrance_id": holdout.json()["id"],
            "role": "HOLDOUT",
            "identity_evidence": "Label verified",
            "group_name": "Holdout",
        },
        headers=MANAGER,
    )
    assert holdout_member.status_code == 201
    member_list = await test_app.get(
        f"{PREFIX}/programs/{program_id}/members", headers=MANAGER
    )
    assert member_list.status_code == 200
    assert member_list.headers["cache-control"] == "private, no-store"
    baseline_member = next(
        item for item in member_list.json() if item["role"] == "UNIVERSAL_BASELINE"
    )
    assert baseline_member == {
        "id": member.json()["id"],
        "fragrance_id": fragrance.json()["id"],
        "fragrance_name": "Concealed identity",
        "fragrance_brand": "Concealed house",
        "concentration": "EDT",
        "version_key": "legacy",
        "role": "UNIVERSAL_BASELINE",
        "repeat_of_id": None,
        "group_name": "Baseline",
        "identity_evidence": "Label verified",
        "fragella": None,
    }
    activation = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activation.status_code == 200
    enrollment = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer.json()["id"],
            "recorder_usernames": ["recorder"],
        },
        headers=MANAGER,
    )
    assert enrollment.status_code == 201
    enrollment_id = enrollment.json()["id"]
    url = f"{PREFIX}/enrollments/{enrollment_id}"
    forbidden = await test_app.get(url, headers=OUTSIDER)
    assert forbidden.status_code == 403
    assert (await test_app.get(f"{PREFIX}/enrollments", headers=OUTSIDER)).json() == []
    outsider_list = await test_app.get(f"{PREFIX}/enrollments", headers=OUTSIDER)
    assert outsider_list.headers["cache-control"] == "private, no-store"
    assert outsider_list.headers["vary"] == "X-Authentik-Username"
    assert (await test_app.get(f"{PREFIX}/programs", headers=OUTSIDER)).json() == []
    view = await test_app.get(url, headers=RECORDER)
    assert view.status_code == 200
    assert "Concealed" not in view.text
    presentation_id = view.json()["presentations"][0]["id"]
    presentation_url = f"{PREFIX}/presentations/{presentation_id}"
    mapping = await test_app.get(f"{url}/mapping", headers=RECORDER)
    assert mapping.status_code == 403
    mapping = await test_app.get(f"{url}/mapping", headers=MANAGER)
    assert mapping.status_code == 200
    assert mapping.json()[0]["fragrance_id"] == fragrance.json()["id"]
    assert mapping.json()[0]["fragrance_name"] == "Concealed identity"
    assert mapping.json()[0]["version_key"] == "legacy"
    assert mapping.headers["cache-control"] == "private, no-store"
    overview = await test_app.get(f"{PREFIX}/manager/enrollments", headers=MANAGER)
    assert overview.status_code == 200
    assert overview.headers["cache-control"] == "private, no-store"
    assert overview.json() == [
        {
            "id": enrollment_id,
            "program_name": "Protocol",
            "program_version": "1",
            "reviewer_name": "Evaluator",
            "recorder_usernames": ["recorder"],
            "total_presentations": 2,
            "blotter_complete": 0,
            "skin_planned": 0,
            "skin_complete": 0,
            "reveal_eligible": False,
            "reveal_blocker": "SKIN_PLAN",
            "revealed": False,
        }
    ]
    denied_overview = await test_app.get(
        f"{PREFIX}/manager/enrollments", headers=RECORDER
    )
    assert denied_overview.status_code == 403
    assert denied_overview.headers["cache-control"] == "private, no-store"
    assert "X-Authentik-Username" in denied_overview.headers["vary"]

    blocked = await test_app.post(f"{url}/reveal", headers=RECORDER)
    assert blocked.status_code == 409
    blocked = await test_app.post(
        f"{presentation_url}/observations", json={"stage": "BLOTTER"}, headers=OUTSIDER
    )
    assert blocked.status_code == 403
    response = await test_app.post(
        f"{presentation_url}/observations",
        json={
            "stage": "BLOTTER",
            "detected": True,
            "intensity": 3,
            "liking": 8,
        },
        headers=RECORDER,
    )
    assert response.status_code == 201
    history = await test_app.get(
        f"{PREFIX}/history/{reviewer.json()['id']}", headers=RECORDER
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["identity"] is None
    assert "Concealed" not in history.text
    assert fragrance.json()["id"] not in history.text
    forbidden_history = await test_app.get(
        f"{PREFIX}/history/{reviewer.json()['id']}", headers=OUTSIDER
    )
    assert forbidden_history.status_code == 403
    assert (
        await test_app.post(f"{presentation_url}/lock/BLOTTER", headers=RECORDER)
    ).status_code == 200
    assert (
        await test_app.post(f"{url}/lock-skin-plan", headers=RECORDER)
    ).status_code == 200
    ready_overview = await test_app.get(
        f"{PREFIX}/manager/enrollments", headers=MANAGER
    )
    assert ready_overview.status_code == 200
    assert ready_overview.json()[0]["reveal_eligible"] is True
    assert ready_overview.json()[0]["reveal_blocker"] is None
    checkpoint = await test_app.post(
        f"{url}/checkpoints", json={"algorithm_version": "test"}, headers=RECORDER
    )
    assert checkpoint.status_code == 403
    checkpoint = await test_app.post(
        f"{url}/checkpoints", json={"algorithm_version": "test"}, headers=MANAGER
    )
    assert checkpoint.status_code == 201
    assert (await test_app.post(f"{url}/reveal", headers=RECORDER)).status_code == 200
    view = await test_app.get(url, headers=RECORDER)
    assert view.json()["presentations"][0]["identity"]["name"] == "Concealed identity"
    response = await test_app.post(
        f"{presentation_url}/post-reveal",
        json={
            "stage": "BLOTTER",
            "comments": "Now I recognize it",
            "liking": 5,
        },
        headers=RECORDER,
    )
    assert response.status_code == 201
    view = await test_app.get(url, headers=RECORDER)
    assert [
        (row["phase"], row["liking"])
        for row in view.json()["presentations"][0]["observations"]
    ] == [
        ("PRE_REVEAL", 8),
        ("POST_REVEAL", 5),
    ]


@pytest_asyncio.fixture
async def draft_member(test_app):
    """A draft program with one baseline membership; returns (program_id, membership_id)."""
    fragrance = await test_app.post(
        "/api/v1/fragrances",
        json={
            "name": "Aimez-Moi",
            "brand": "Caron",
            "concentration": "EDT",
            "gender_target": "Unisex",
            "primary_family": "floral",
            "subfamily": "powdery",
        },
        headers=MANAGER,
    )
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Gap-fill", "version": "1"}, headers=MANAGER
    )
    program_id = program.json()["id"]
    member = await test_app.post(
        f"{PREFIX}/programs/{program_id}/members",
        json={
            "fragrance_id": fragrance.json()["id"],
            "role": "UNIVERSAL_BASELINE",
            "identity_evidence": "Label verified",
        },
        headers=MANAGER,
    )
    return program_id, member.json()["id"]


@pytest.mark.asyncio
async def test_fragella_lookup_requires_manager(test_app, draft_member):
    program_id, membership_id = draft_member
    response = await test_app.post(
        f"{PREFIX}/programs/{program_id}/members/{membership_id}/fragella-lookup",
        headers=RECORDER,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_fragella_lookup_records_success_and_appears_in_members(
    test_app, draft_member
):
    program_id, membership_id = draft_member
    fake_result = FragellaResult(
        id="aimez-moi-1996",
        name="Aimez-Moi",
        brand="Caron",
        year=1996,
        oil_type="Eau de Toilette",
        confidence="medium",
    )
    with patch(
        "fragrance_rater.services.fragella_lookup_service.FragellaClient.search",
        AsyncMock(return_value=[fake_result]),
    ):
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members/{membership_id}/fragella-lookup",
            headers=MANAGER,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["results"][0]["name"] == "Aimez-Moi"
    assert body["query"] == "Caron Aimez-Moi"

    member_list = await test_app.get(
        f"{PREFIX}/programs/{program_id}/members", headers=MANAGER
    )
    member = next(item for item in member_list.json() if item["id"] == membership_id)
    assert member["fragella"]["status"] == "success"
    assert member["fragella"]["results"][0]["brand"] == "Caron"


@pytest.mark.asyncio
async def test_fragella_lookup_records_failure_without_crashing(test_app, draft_member):
    """A lookup failure (bad key, quota exhausted) must still be recorded
    and reported, not silently dropped or surfaced as a 500."""
    program_id, membership_id = draft_member
    with patch(
        "fragrance_rater.services.fragella_lookup_service.FragellaClient.search",
        AsyncMock(
            side_effect=FragellaError("Fragella monthly quota exhausted (HTTP 429)")
        ),
    ):
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members/{membership_id}/fragella-lookup",
            headers=MANAGER,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "quota exhausted" in body["error_message"]
    assert body["results"] == []


@pytest.mark.asyncio
async def test_fragella_lookup_accepts_an_explicit_query_override(
    test_app, draft_member
):
    program_id, membership_id = draft_member
    with patch(
        "fragrance_rater.services.fragella_lookup_service.FragellaClient.search",
        AsyncMock(return_value=[]),
    ) as mock_search:
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members/{membership_id}/fragella-lookup",
            params={"query": "Aimez-Moi Comme Je Suis"},
            headers=MANAGER,
        )
    assert response.status_code == 200
    mock_search.assert_awaited_once_with("Aimez-Moi Comme Je Suis")


@pytest.mark.asyncio
async def test_fragella_lookup_rejects_an_overlong_query(test_app, draft_member):
    """An over-500-char query must be rejected before spending a Fragella
    quota request or reaching FragellaLookup.query's String(500) column,
    not fail later at flush() as an unhandled 500."""
    program_id, membership_id = draft_member
    with patch(
        "fragrance_rater.services.fragella_lookup_service.FragellaClient.search",
        AsyncMock(return_value=[]),
    ) as mock_search:
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members/{membership_id}/fragella-lookup",
            params={"query": "x" * 501},
            headers=MANAGER,
        )
    assert response.status_code == 422
    mock_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_fragella_lookup_rejects_a_query_containing_a_nul_byte(
    test_app, draft_member
):
    """A NUL byte is valid in a Python str but not in a Postgres text
    column; it must be rejected with a clean 400 rather than spending a
    Fragella quota request and then failing at flush()."""
    program_id, membership_id = draft_member
    with patch(
        "fragrance_rater.services.fragella_lookup_service.FragellaClient.search",
        AsyncMock(return_value=[]),
    ) as mock_search:
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members/{membership_id}/fragella-lookup",
            params={"query": "Aimez\x00Moi"},
            headers=MANAGER,
        )
    assert response.status_code == 400
    mock_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_fragella_lookup_rejects_unknown_membership(test_app, draft_member):
    program_id, _ = draft_member
    response = await test_app.post(
        f"{PREFIX}/programs/{program_id}/members/does-not-exist/fragella-lookup",
        headers=MANAGER,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_history_surfaces_worn_by_reviewer_id_on_ordinary_entries(test_app):
    """ADR-011: the unified history exposes on-others evaluations as such."""
    reviewer = await test_app.post(
        "/api/v1/reviewers", json={"name": "Evaluator"}, headers=MANAGER
    )
    reviewer_id = reviewer.json()["id"]
    subject = await test_app.post(
        "/api/v1/reviewers", json={"name": "Worn By"}, headers=MANAGER
    )
    subject_id = subject.json()["id"]
    fragrance = await test_app.post(
        "/api/v1/fragrances",
        json={
            "name": "History scent",
            "brand": "History house",
            "concentration": "EDP",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
        headers=MANAGER,
    )
    fragrance_id = fragrance.json()["id"]
    on_me = await test_app.post(
        "/api/v1/evaluations",
        headers=MANAGER,
        json={"fragrance_id": fragrance_id, "reviewer_id": reviewer_id, "rating": 4},
    )
    assert on_me.status_code == 201
    on_others = await test_app.post(
        "/api/v1/evaluations",
        headers=MANAGER,
        json={
            "fragrance_id": fragrance_id,
            "reviewer_id": reviewer_id,
            "rating": 3,
            "worn_by_reviewer_id": subject_id,
        },
    )
    assert on_others.status_code == 201

    response = await test_app.get(f"{PREFIX}/history/{reviewer_id}", headers=MANAGER)
    assert response.status_code == 200
    entries = {entry["id"]: entry for entry in response.json()}
    assert entries[on_me.json()["id"]]["worn_by_reviewer_id"] is None
    assert entries[on_others.json()["id"]]["worn_by_reviewer_id"] == subject_id


@pytest.mark.asyncio
async def test_fragella_usage_requires_manager(test_app):
    response = await test_app.get(f"{PREFIX}/fragella/usage", headers=RECORDER)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_fragella_usage_reports_quota(test_app):
    usage_body = {"plan": "free", "usage": {"requests_remaining": 17}}
    with patch(
        "fragrance_rater.api.calibration.FragellaClient.usage",
        AsyncMock(return_value=usage_body),
    ):
        response = await test_app.get(f"{PREFIX}/fragella/usage", headers=MANAGER)
    assert response.status_code == 200
    assert response.json() == usage_body


@pytest.mark.asyncio
async def test_fragella_usage_reports_failure_as_502(test_app):
    with patch(
        "fragrance_rater.api.calibration.FragellaClient.usage",
        AsyncMock(return_value=None),
    ):
        response = await test_app.get(f"{PREFIX}/fragella/usage", headers=MANAGER)
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_fragella_usage_reports_unconfigured_key_as_502(test_app):
    """An unconfigured FRAGELLA_API_KEY raises FragellaError from inside
    usage() before its own try block; the route must still surface the
    documented 502, not an unhandled 500."""
    with patch(
        "fragrance_rater.api.calibration.FragellaClient.usage",
        AsyncMock(side_effect=FragellaError("FRAGELLA_API_KEY is not configured")),
    ):
        response = await test_app.get(f"{PREFIX}/fragella/usage", headers=MANAGER)
    assert response.status_code == 502
