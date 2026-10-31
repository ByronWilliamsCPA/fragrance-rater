"""R8 PR 2 (D-22, Q18): a retried observation POST never appends twice.

The released form sends one ``idempotency_key`` per submission, the same on
every retry of it. A retry returns the original row with 200; the same key
with different answers is a 409, never a silent answer with a row that does
not match the request; a new key, or no key, appends as before.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import func, select

from fragrance_rater.core.database import get_db
from fragrance_rater.main import app
from fragrance_rater.models.calibration import Observation
from tests.unit.test_api.test_training_eligibility_routes import (
    PREFIX,
    RECORDER,
    _lock,
    calibration_manager,
    world,
)

if TYPE_CHECKING:
    from httpx import AsyncClient

__all__ = ["calibration_manager", "world"]

KEY = "a1b2c3d4-key-0001"


def _body(**fields: Any) -> dict[str, Any]:
    return {
        "stage": "SKIN" if fields.get("stage") == "SKIN" else "BLOTTER",
        "detected": True,
        "liking": 6,
        "observed_at": "2026-10-30T14:00:00Z",
        "idempotency_key": KEY,
        **fields,
    }


async def _post(
    client: AsyncClient,
    presentation_id: str,
    body: dict[str, Any],
    kind: str = "observations",
) -> Any:
    return await client.post(
        f"{PREFIX}/presentations/{presentation_id}/{kind}", json=body, headers=RECORDER
    )


async def _count(presentation_id: str) -> int:
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(Observation)
                .where(Observation.presentation_id == presentation_id)
            )
            or 0
        )
    finally:
        await sessions.aclose()


@pytest.mark.asyncio
async def test_a_retry_returns_the_original_row(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]

    first = await _post(test_app, presentation, _body())
    retry = await _post(test_app, presentation, _body())

    assert first.status_code == 201, first.text
    assert retry.status_code == 200, retry.text
    assert retry.json() == {"id": first.json()["id"], "replayed": True}
    assert first.json()["replayed"] is False
    assert await _count(presentation) == 1


@pytest.mark.asyncio
async def test_a_retry_after_the_stage_locked_still_answers_the_original(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    """The first POST succeeded but its response was lost; then it was locked."""
    presentation = world["presentation_ids"][0]
    first = await _post(test_app, presentation, _body())
    await _lock(test_app, presentation)

    retry = await _post(test_app, presentation, _body())

    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_a_retry_without_observed_at_matches_the_server_stamp(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    body = _body()
    del body["observed_at"]

    first = await _post(test_app, presentation, body)
    retry = await _post(test_app, presentation, body)

    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"liking": 7},
        {"observed_at": "2026-10-30T15:00:00Z"},
        {"comments": "different"},
        {"stage": "SKIN"},
    ],
)
async def test_the_same_key_with_different_answers_is_refused(
    test_app: AsyncClient, world: dict[str, Any], change: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    plan = await test_app.post(
        f"{PREFIX}/presentations/{presentation}/skin-plan",
        json={"reason": "check skin"},
        headers=RECORDER,
    )
    assert plan.status_code == 200, plan.text
    first = await _post(test_app, presentation, _body())

    conflict = await _post(test_app, presentation, _body(**change))

    assert first.status_code == 201, first.text
    assert conflict.status_code == 409, conflict.text
    assert "idempotency key" in conflict.json()["detail"]
    assert await _count(presentation) == 1


@pytest.mark.asyncio
async def test_a_fresh_key_or_no_key_appends_a_genuine_repeat(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    presentation = world["presentation_ids"][0]
    keyless = _body()
    del keyless["idempotency_key"]

    first = await _post(test_app, presentation, _body())
    fresh = await _post(
        test_app, presentation, _body(idempotency_key="a1b2c3d4-key-0002")
    )
    bare_one = await _post(test_app, presentation, keyless)
    bare_two = await _post(test_app, presentation, keyless)

    statuses = [r.status_code for r in (first, fresh, bare_one, bare_two)]
    assert statuses == [201, 201, 201, 201]
    assert len({r.json()["id"] for r in (first, fresh, bare_one, bare_two)}) == 4
    assert await _count(presentation) == 4


@pytest.mark.asyncio
async def test_a_key_is_scoped_to_its_presentation(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    one, two = world["presentation_ids"][:2]

    first = await _post(test_app, one, _body())
    second = await _post(test_app, two, _body())

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["short", "x" * 65, "has space!", ""])
async def test_a_malformed_key_is_rejected(
    test_app: AsyncClient, world: dict[str, Any], key: str
) -> None:
    response = await _post(
        test_app, world["presentation_ids"][0], _body(idempotency_key=key)
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_the_key_is_not_shared_between_blind_and_post_reveal_entries(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    """A blind key replayed on the post-reveal route is a different submission."""
    presentation = world["presentation_ids"][0]
    first = await _post(test_app, presentation, _body())
    assert first.status_code == 201, first.text

    response = await _post(test_app, presentation, _body(), kind="post-reveal")

    # The enrollment is not revealed, so the replay check runs first and
    # refuses the mismatched route rather than leaking the reveal state.
    assert response.status_code == 409, response.text
