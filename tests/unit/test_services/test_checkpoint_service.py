"""R8 PR 2 (M-07, M-08, X-17): a checkpoint records how to rebuild its inputs."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from fragrance_rater.core.database import get_db
from fragrance_rater.main import app
from fragrance_rater.ml.feature_space import FEATURE_SPACE_VERSION
from fragrance_rater.ml.model import AffinityV2
from fragrance_rater.ml.training_view import FILTERS
from fragrance_rater.models.calibration import CheckpointPrediction
from fragrance_rater.models.feature_snapshot import FeatureSnapshot
from fragrance_rater.services.checkpoint_service import (
    CheckpointService,
    feature_content_hash,
    typed_predictions,
)
from fragrance_rater.services.vocabulary import NOTE_MAPPING_VERSION
from tests.unit.test_api.test_training_eligibility_routes import (
    API,
    MANAGER,
    PREFIX,
    calibration_manager,
    world,
)

if TYPE_CHECKING:
    from httpx import AsyncClient

__all__ = ["calibration_manager", "world"]


# --- pure validation ----------------------------------------------------------


def test_typed_predictions_keep_each_target_on_its_scale() -> None:
    typed = typed_predictions(
        [
            {"fragrance_id": "h", "target": "liking", "value": 7.5, "uncertainty": 1},
            {"fragrance_id": "h", "target": "rating", "value": 4, "scale": "1-5"},
        ],
        {"h"},
    )
    assert [(p.target, p.scale, p.value, p.uncertainty) for p in typed] == [
        ("liking", "0-10", 7.5, 1.0),
        ("rating", "1-5", 4.0, None),
    ]


@pytest.mark.parametrize(
    "prediction",
    [
        {"fragrance_id": "not-a-holdout", "target": "liking", "value": 5},
        {"fragrance_id": "h", "target": "vibes", "value": 5},
        {"fragrance_id": "h", "target": "liking", "value": 11},
        {"fragrance_id": "h", "target": "rating", "value": 0.5},
        {"fragrance_id": "h", "target": "liking", "value": 5, "scale": "1-5"},
        {"fragrance_id": "h", "target": "liking", "value": "high"},
        {"fragrance_id": "h", "target": "liking", "value": float("nan")},
        {"fragrance_id": "h", "target": "liking", "value": 5, "uncertainty": -1},
        {"fragrance_id": "h", "target": "liking"},
        {"target": "liking", "value": 5},
    ],
)
def test_typed_predictions_refuse_what_cannot_be_scored(
    prediction: dict[str, Any],
) -> None:
    with pytest.raises(HTTPException) as refused:
        typed_predictions([prediction], {"h"})
    assert refused.value.status_code == 422


def test_typed_predictions_refuse_a_duplicate_target() -> None:
    row = {"fragrance_id": "h", "target": "liking", "value": 5}
    with pytest.raises(HTTPException):
        typed_predictions([row, row], {"h"})


def test_the_feature_hash_is_sha256_over_canonical_json() -> None:
    features = {"b": {"x": 1}, "a": {"y": [1, 2]}}
    digest = feature_content_hash(
        features,
        feature_space_version="fs-v2",
        taxonomy_version=None,
        alias_version="nm-v1",
        parser_version=None,
    )
    canonical = json.dumps(
        {
            "features": features,
            "feature_space_version": "fs-v2",
            "taxonomy_version": None,
            "alias_version": "nm-v1",
            "parser_version": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert digest == hashlib.sha256(canonical.encode()).hexdigest()
    reordered = feature_content_hash(
        dict(reversed(list(features.items()))),
        feature_space_version="fs-v2",
        taxonomy_version=None,
        alias_version="nm-v1",
        parser_version=None,
    )
    assert reordered == digest


# --- through the route ----------------------------------------------------------


async def _checkpoint(client: AsyncClient, world: dict[str, Any], **body: Any) -> Any:
    return await client.post(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/checkpoints",
        json={"algorithm_version": "external-model", **body},
        headers=MANAGER,
    )


async def _frozen(client: AsyncClient, world: dict[str, Any]) -> list[dict[str, Any]]:
    response = await client.get(
        f"{PREFIX}/enrollments/{world['enrollment_id']}/checkpoints", headers=MANAGER
    )
    assert response.status_code == 200, response.text
    return list(response.json())


async def _rate(
    client: AsyncClient, world: dict[str, Any], index: int, rating: int
) -> None:
    response = await client.post(
        f"{API}/evaluations",
        json={
            "reviewer_id": world["reviewer_id"],
            "fragrance_id": world["fragrance_ids"][index],
            "rating": rating,
        },
        headers=MANAGER,
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_a_checkpoint_fills_every_reproduction_column(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    await _rate(test_app, world, 0, 5)
    holdout = world["fragrance_ids"][3]

    created = await _checkpoint(
        test_app,
        world,
        algorithm_version=AffinityV2.spec.algorithm_version,
        predictions=[
            {"fragrance_id": holdout, "target": "liking", "value": 6.5},
            {"fragrance_id": holdout, "target": "rating", "value": 3.0},
        ],
    )

    assert created.status_code == 201, created.text
    (frozen,) = await _frozen(test_app, world)
    assert frozen["exclusions"] == [holdout]
    assert frozen["filters"] == FILTERS
    assert frozen["feature_space_version"] == FEATURE_SPACE_VERSION
    assert frozen["taxonomy_version"] is None
    assert frozen["model_params"] == dict(AffinityV2.spec.params)
    assert len(frozen["input_digest"]) == 64
    assert [row["fragrance_id"] for row in frozen["manifest"]] == [
        world["fragrance_ids"][0]
    ]
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        snapshot = await session.get(FeatureSnapshot, frozen["feature_snapshot_id"])
        assert snapshot is not None
        assert snapshot.alias_version == NOTE_MAPPING_VERSION
        assert set(snapshot.features) == {world["fragrance_ids"][0]}
        typed = list(
            await session.scalars(
                select(CheckpointPrediction).where(
                    CheckpointPrediction.checkpoint_id == frozen["id"]
                )
            )
        )
    finally:
        await sessions.aclose()
    assert {(p.target, p.scale, p.value) for p in typed} == {
        ("liking", "0-10", 6.5),
        ("rating", "1-5", 3.0),
    }


@pytest.mark.asyncio
async def test_an_unregistered_model_records_no_params(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    assert (await _checkpoint(test_app, world)).status_code == 201
    (frozen,) = await _frozen(test_app, world)
    assert frozen["model_params"] is None
    assert frozen["manifest"] == []


@pytest.mark.asyncio
async def test_the_input_digest_is_deterministic_and_tracks_the_rows(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    await _rate(test_app, world, 0, 5)
    await _checkpoint(test_app, world)
    await _checkpoint(test_app, world)
    await _rate(test_app, world, 1, 2)
    await _checkpoint(test_app, world)

    first, second, third = sorted(
        await _frozen(test_app, world), key=lambda row: row["created_at"]
    )

    assert first["input_digest"] == second["input_digest"]
    assert first["feature_snapshot_id"] == second["feature_snapshot_id"]
    assert third["input_digest"] != first["input_digest"]
    assert third["feature_snapshot_id"] != first["feature_snapshot_id"]


@pytest.mark.asyncio
async def test_a_withheld_row_changes_the_digest_and_leaves_the_manifest(
    test_app: AsyncClient, world: dict[str, Any]
) -> None:
    await _rate(test_app, world, 0, 5)
    await _checkpoint(test_app, world)
    (before,) = await _frozen(test_app, world)
    row_id = before["manifest"][0]["id"]
    withheld = await test_app.put(
        f"{API}/training-eligibility/evaluation/{row_id}",
        json={"training_eligibility": "withheld", "reason": "Wrong bottle"},
        headers=MANAGER,
    )
    assert withheld.status_code == 200, withheld.text

    await _checkpoint(test_app, world)

    after = next(
        row for row in await _frozen(test_app, world) if row["id"] != before["id"]
    )
    assert after["manifest"] == []
    assert after["input_digest"] != before["input_digest"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prediction",
    [
        {"target": "liking", "value": 5, "fragrance_index": 0},
        {"target": "liking", "value": 50, "fragrance_index": 3},
    ],
)
async def test_a_prediction_outside_the_holdouts_or_scale_is_refused(
    test_app: AsyncClient, world: dict[str, Any], prediction: dict[str, Any]
) -> None:
    index = prediction.pop("fragrance_index")
    response = await _checkpoint(
        test_app,
        world,
        predictions=[{**prediction, "fragrance_id": world["fragrance_ids"][index]}],
    )
    assert response.status_code == 422, response.text
    assert await _frozen(test_app, world) == []


@pytest.mark.asyncio
async def test_a_lost_snapshot_insert_race_reuses_the_winner(
    test_app: AsyncClient,
) -> None:
    """Two checkpoints freezing the same content must not 500 the loser."""
    del test_app  # only to install the in-memory database override
    manifest: list[dict[str, object]] = [
        {"fragrance_id": "f1", "source_features": {"notes": ["rose"]}}
    ]
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        service = CheckpointService(session)
        winner = await service.feature_snapshot(manifest, "manager")

        real_scalar = session.scalar
        calls = 0

        async def lookup_misses_once(*args: Any, **kwargs: Any) -> Any:
            """Hide the winner from the first lookup, as a concurrent insert would."""
            nonlocal calls
            calls += 1
            if calls == 1:
                return None
            return await real_scalar(*args, **kwargs)

        session.scalar = lookup_misses_once  # type: ignore[method-assign]
        loser = await service.feature_snapshot(manifest, "manager")
    finally:
        await sessions.aclose()

    assert loser.id == winner.id
    assert calls == 2
