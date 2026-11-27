"""Shared label enrollment over HTTP (F1: one blind code per physical sample)."""

import pytest

from fragrance_rater.core.config import settings

PREFIX = "/api/v1/calibration"
MANAGER = {"X-Authentik-Username": "manager"}
SHARED = "shared-triples-latin-rotation-v1"


@pytest.fixture(autouse=True)
def calibration_manager(monkeypatch):
    monkeypatch.setattr(settings, "calibration_admin_usernames", ["manager"])


async def build_program(
    test_app, reveal_policy: str = "HOUSEHOLD"
) -> tuple[str, list[str], list[str]]:
    """Active program: four baseline, one hidden repeat, one holdout."""
    fragrance_ids = []
    for index in range(5):
        response = await test_app.post(
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
        assert response.status_code == 201
        fragrance_ids.append(response.json()["id"])
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Shared", "version": "1"}, headers=MANAGER
    )
    program_id = program.json()["id"]
    policy = await test_app.put(
        f"{PREFIX}/programs/{program_id}/reveal-policy",
        json={"reveal_policy": reveal_policy},
        headers=MANAGER,
    )
    assert policy.status_code == 200
    member_ids = []
    bodies = [
        {
            "fragrance_id": fid,
            "role": "UNIVERSAL_BASELINE",
            "identity_evidence": "Verified",
        }
        for fid in fragrance_ids[:4]
    ]
    for body in bodies:
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members", json=body, headers=MANAGER
        )
        assert response.status_code == 201
        member_ids.append(response.json()["id"])
    for body in (
        {
            "fragrance_id": fragrance_ids[0],
            "role": "HIDDEN_REPEAT",
            "repeat_of_id": member_ids[0],
            "identity_evidence": "Same decant",
        },
        {
            "fragrance_id": fragrance_ids[4],
            "role": "HOLDOUT",
            "identity_evidence": "Verified",
        },
    ):
        response = await test_app.post(
            f"{PREFIX}/programs/{program_id}/members", json=body, headers=MANAGER
        )
        assert response.status_code == 201
        member_ids.append(response.json()["id"])
    reviewer_ids = []
    for name in ("First", "Second"):
        response = await test_app.post(
            "/api/v1/reviewers", json={"name": name}, headers=MANAGER
        )
        reviewer_ids.append(response.json()["id"])
    activation = await test_app.post(
        f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER
    )
    assert activation.status_code == 200
    return program_id, reviewer_ids, member_ids


def body(reviewer_id: str, **extra) -> dict[str, object]:
    return {
        "reviewer_id": reviewer_id,
        "recorder_usernames": ["recorder"],
        "session_size": 1,
        "randomization_algorithm": SHARED,
        "label_scheme": "shared",
        **extra,
    }


async def mapping_of(test_app, enrollment_id: str) -> dict[str, str]:
    """Membership id to blind code, from the manager-only mapping sheet."""
    response = await test_app.get(
        f"{PREFIX}/enrollments/{enrollment_id}/mapping", headers=MANAGER
    )
    assert response.status_code == 200
    return {row["membership_id"]: row["blind_code"] for row in response.json()}


@pytest.mark.asyncio
async def test_first_shared_enrollment_without_codes_is_a_clear_422(test_app):
    program_id, reviewer_ids, _ = await build_program(test_app)
    response = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json=body(reviewer_ids[0]),
        headers=MANAGER,
    )
    assert response.status_code == 422
    assert "membership_codes" in response.json()["detail"]


@pytest.mark.asyncio
async def test_shared_enrollments_carry_one_code_per_membership(test_app):
    program_id, reviewer_ids, member_ids = await build_program(test_app)
    codes = {mid: f"B{index:02d}" for index, mid in enumerate(member_ids, start=1)}
    first = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json=body(reviewer_ids[0], membership_codes=codes),
        headers=MANAGER,
    )
    assert first.status_code == 201
    second = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json=body(reviewer_ids[1]),
        headers=MANAGER,
    )
    assert second.status_code == 201
    # Compare the membership-to-code mapping itself, so codes swapped between
    # memberships (a sorted list would still match) fail this test.
    assert await mapping_of(test_app, first.json()["id"]) == codes
    assert await mapping_of(test_app, second.json()["id"]) == codes
    again = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json=body(reviewer_ids[1]),
        headers=MANAGER,
    )
    assert again.status_code == 409
    assert "already enrolled" in again.json()["detail"]


@pytest.mark.asyncio
async def test_shared_enrollment_is_refused_unless_the_reveal_is_household(test_app):
    program_id, reviewer_ids, member_ids = await build_program(
        test_app, reveal_policy="ENROLLMENT"
    )
    codes = {mid: f"B{index:02d}" for index, mid in enumerate(member_ids, start=1)}
    response = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json=body(reviewer_ids[0], membership_codes=codes),
        headers=MANAGER,
    )
    assert response.status_code == 409
    assert "HOUSEHOLD" in response.json()["detail"]


@pytest.mark.asyncio
async def test_shared_scheme_with_another_algorithm_is_a_422(test_app):
    program_id, reviewer_ids, _ = await build_program(test_app)
    response = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer_ids[0],
            "recorder_usernames": ["recorder"],
            "label_scheme": "shared",
        },
        headers=MANAGER,
    )
    assert response.status_code == 422
