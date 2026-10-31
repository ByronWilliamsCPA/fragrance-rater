"""R8 PR 1: source-snapshot provenance and checkpoint reproduction schema.

Covers issue #130's CHECKs on ``calibration_source_snapshots`` (ADR-012
source-type/permission pairs and the ``fields`` allow-list), the tech-spec D1
provenance columns, the M-07 checkpoint columns, typed checkpoint predictions
(M-08), and ``feature_snapshots`` (X-17). Drift pins tie the allow-list to the
house-review ``ConfirmableField`` literal and the pair table to ADR-012's two
vocabularies.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, get_args

import pytest
from sqlalchemy import CheckConstraint, text
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base
from fragrance_rater.models.calibration import (
    CHECKPOINT_TARGET_SCALES,
    CHECKPOINT_TARGETS,
    PERMISSION_STATES,
    PREDICTION_SCALES,
    SOURCE_EVIDENCE_FIELDS,
    SOURCE_PERMISSION_PAIRS,
    SOURCE_TYPES,
    CheckpointPrediction,
    Enrollment,
    ModelCheckpoint,
    Program,
    SourceSnapshot,
)
from fragrance_rater.models.feature_snapshot import FeatureSnapshot
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.house_intake import HouseSubmission
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.house_review import CONFIRMABLE_FIELDS, ConfirmableField

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DIGEST = hashlib.sha256(b"r8").hexdigest()


def _check_values(table: str, rule: str) -> list[str]:
    name = f"ck_{table}_{rule}"
    (constraint,) = (
        c
        for c in Base.metadata.tables[table].constraints
        if isinstance(c, CheckConstraint) and c.name == name
    )
    return re.findall(r"'([^']*)'", str(constraint.sqltext))


async def _fragrance(session: AsyncSession) -> Fragrance:
    fragrance = Fragrance(
        name="Provenance",
        brand="House",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="unit",
    )
    session.add(fragrance)
    await session.flush()
    return fragrance


async def _rejects(session: AsyncSession, row: object) -> None:
    session.add(row)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


def _snapshot(fragrance_id: str, **overrides: object) -> SourceSnapshot:
    values: dict[str, object] = {
        "fragrance_id": fragrance_id,
        "source_type": "manufacturer_provided",
        "permission_state": "retain_and_train",
        "fields": ["concentration"],
        "source_reference": "Email reply from Brand X contact, 2026-09-20",
        "payload": {},
    }
    values.update(overrides)
    return SourceSnapshot(**values)


# --- vocabulary pins ---------------------------------------------------------


def test_the_allow_list_covers_every_confirmable_house_field() -> None:
    """The house-review writer can never write a name the CHECK rejects."""
    assert get_args(ConfirmableField) == CONFIRMABLE_FIELDS
    assert set(CONFIRMABLE_FIELDS) <= set(SOURCE_EVIDENCE_FIELDS)
    assert set(SOURCE_EVIDENCE_FIELDS) - set(CONFIRMABLE_FIELDS) == {"gtin"}


def test_the_legacy_backfill_fields_are_allowed() -> None:
    """Migration a3f8c1d9e2b7 backfilled these on every Parfumo row."""
    assert {"concentration", "launch_year", "brand"} <= set(SOURCE_EVIDENCE_FIELDS)


def test_every_allowed_field_names_a_fragrance_fact() -> None:
    columns = set(Base.metadata.tables["fragrances"].columns.keys())
    assert set(SOURCE_EVIDENCE_FIELDS) - columns == {"gtin"}
    assert "fragrance_gtins" in Base.metadata.tables


def test_the_pair_table_uses_adr_012s_vocabularies() -> None:
    assert _check_values("calibration_source_snapshots", "source_type") == list(
        SOURCE_TYPES
    )
    assert _check_values("calibration_source_snapshots", "permission_state") == list(
        PERMISSION_STATES
    )
    assert [source for source, _ in SOURCE_PERMISSION_PAIRS] == list(SOURCE_TYPES)
    for _source, states in SOURCE_PERMISSION_PAIRS:
        assert set(states) <= set(PERMISSION_STATES)


def test_the_house_intake_permission_scopes_are_all_allowed_for_manufacturers() -> None:
    """``HouseReviewService.adopt`` copies the house's scope verbatim."""
    allowed = dict(SOURCE_PERMISSION_PAIRS)["manufacturer_provided"]
    scopes = _check_values(HouseSubmission.__tablename__, "permission_state")
    assert set(scopes) <= set(allowed)


def test_checkpoint_targets_match_the_scale_table() -> None:
    assert tuple(t for t, _ in CHECKPOINT_TARGET_SCALES) == CHECKPOINT_TARGETS
    assert {s for _, s in CHECKPOINT_TARGET_SCALES} == set(PREDICTION_SCALES)
    assert dict(CHECKPOINT_TARGET_SCALES)["rating"] == "1-5"
    assert dict(CHECKPOINT_TARGET_SCALES)["liking"] == "0-10"


# --- source snapshots --------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_type", "permission_state"),
    [(source, state) for source, states in SOURCE_PERMISSION_PAIRS for state in states],
)
async def test_every_sanctioned_pair_is_accepted(
    async_session: AsyncSession, source_type: str, permission_state: str
) -> None:
    fragrance = await _fragrance(async_session)
    async_session.add(
        _snapshot(
            fragrance.id, source_type=source_type, permission_state=permission_state
        )
    )
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_type", "permission_state"),
    [
        (source, state)
        for source in SOURCE_TYPES
        for state in PERMISSION_STATES
        if state not in dict(SOURCE_PERMISSION_PAIRS)[source]
    ],
)
async def test_every_unsanctioned_pair_is_rejected(
    async_session: AsyncSession, source_type: str, permission_state: str
) -> None:
    fragrance = await _fragrance(async_session)
    await _rejects(
        async_session,
        _snapshot(
            fragrance.id, source_type=source_type, permission_state=permission_state
        ),
    )


def test_the_unsanctioned_pairs_include_the_ones_issue_130_names() -> None:
    allowed = dict(SOURCE_PERMISSION_PAIRS)
    assert "retain_and_train" not in allowed["excluded_legacy"]
    assert "excluded_no_new_writes" not in allowed["manufacturer_provided"]
    assert "retain_and_train" not in allowed["bounded_lookup"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        [],
        ["gtin"],
        list(SOURCE_EVIDENCE_FIELDS),
        ["concentration", "launch_year", "brand"],
    ],
)
async def test_allowed_fields_are_accepted(
    async_session: AsyncSession, fields: list[str]
) -> None:
    fragrance = await _fragrance(async_session)
    async_session.add(_snapshot(fragrance.id, fields=fields))
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        ["concentraton"],
        ["concentration", "perfumer"],
        ["Brand"],
        [["brand"]],
        [None],
        "brand",
        {"brand": True},
        None,
    ],
)
async def test_unknown_or_misshapen_fields_are_rejected(
    async_session: AsyncSession, fields: object
) -> None:
    fragrance = await _fragrance(async_session)
    await _rejects(async_session, _snapshot(fragrance.id, fields=fields))


@pytest.mark.asyncio
async def test_a_field_name_cannot_hide_inside_a_longer_one(
    async_session: AsyncSession,
) -> None:
    """Stripping quoted names must not leave a partial match behind."""
    fragrance = await _fragrance(async_session)
    await _rejects(async_session, _snapshot(fragrance.id, fields=["brand_line"]))


@pytest.mark.asyncio
async def test_the_provenance_columns_round_trip(async_session: AsyncSession) -> None:
    fragrance = await _fragrance(async_session)
    snapshot = _snapshot(
        fragrance.id,
        source_revision="letter 2026-09-20",
        content_hash=DIGEST,
        parser_version="manual-v1",
        license_evidence="Brand X grants retain-and-train in writing",
        verified_by="manager",
    )
    async_session.add(snapshot)
    await async_session.flush()
    await async_session.refresh(snapshot)

    assert snapshot.content_hash == DIGEST
    assert snapshot.verified_by == "manager"
    assert snapshot.source_revision == "letter 2026-09-20"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "digest",
    [DIGEST.upper(), DIGEST[:63], DIGEST + "0", "g" * 64, "", " " + DIGEST[1:]],
)
async def test_a_malformed_content_hash_is_rejected(
    async_session: AsyncSession, digest: str
) -> None:
    fragrance = await _fragrance(async_session)
    await _rejects(async_session, _snapshot(fragrance.id, content_hash=digest))


# --- checkpoints, typed predictions, feature snapshots -----------------------


async def _checkpoint(session: AsyncSession, **values: object) -> ModelCheckpoint:
    program = Program(name="ckpt", version="1")
    reviewer = Reviewer(name="ckpt")
    session.add_all([program, reviewer])
    await session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    session.add(enrollment)
    await session.flush()
    checkpoint = ModelCheckpoint(
        enrollment_id=enrollment.id,
        algorithm_version="affinity-v2",
        manifest=[],
        predictions=[],
        **values,
    )
    session.add(checkpoint)
    await session.flush()
    return checkpoint


def _feature_snapshot(**overrides: object) -> FeatureSnapshot:
    values: dict[str, object] = {
        "feature_space_version": "fs-v2",
        "content_hash": DIGEST,
        "features": {"fragrance-1": {"notes": []}},
    }
    values.update(overrides)
    return FeatureSnapshot(**values)


@pytest.mark.asyncio
async def test_checkpoint_reproduction_columns_default_to_sql_null(
    async_session: AsyncSession,
) -> None:
    """A pre-R8-shaped checkpoint still writes; ``None`` is SQL NULL, not ``null``."""
    checkpoint = await _checkpoint(async_session)
    raw = (
        await async_session.execute(
            text(
                "SELECT exclusions, filters, model_params FROM "
                "calibration_checkpoints WHERE id = :id"
            ),
            {"id": checkpoint.id},
        )
    ).one()
    assert tuple(raw) == (None, None, None)


@pytest.mark.asyncio
async def test_a_fully_described_checkpoint_round_trips(
    async_session: AsyncSession,
) -> None:
    snapshot = _feature_snapshot()
    async_session.add(snapshot)
    await async_session.flush()
    checkpoint = await _checkpoint(
        async_session,
        exclusions=["holdout-1"],
        filters={"eligibility": "v_training_rows"},
        feature_space_version="fs-v2",
        taxonomy_version="edwards-2026",
        model_params={"shrinkage": 2.0},
        input_digest=DIGEST,
        feature_snapshot_id=snapshot.id,
    )
    await async_session.refresh(checkpoint)
    assert checkpoint.exclusions == ["holdout-1"]
    assert checkpoint.model_params == {"shrinkage": 2.0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values",
    [
        {"exclusions": {"holdout-1": True}},
        {"exclusions": "holdout-1"},
        {"filters": ["eligible"]},
        {"model_params": [1, 2]},
        {"input_digest": DIGEST.upper()},
        {"input_digest": "abc"},
        {"feature_snapshot_id": "no-such-snapshot"},
    ],
)
async def test_a_malformed_checkpoint_column_is_rejected(
    async_session: AsyncSession, values: dict[str, object]
) -> None:
    with pytest.raises(IntegrityError):
        await _checkpoint(async_session, **values)


async def _prediction(
    session: AsyncSession, **overrides: object
) -> CheckpointPrediction:
    checkpoint = await _checkpoint(session)
    fragrance = await _fragrance(session)
    values: dict[str, object] = {
        "checkpoint_id": checkpoint.id,
        "fragrance_id": fragrance.id,
        "target": "liking",
        "scale": "0-10",
        "value": 6.5,
    }
    values.update(overrides)
    row = CheckpointPrediction(**values)
    session.add(row)
    await session.flush()
    return row


@pytest.mark.asyncio
@pytest.mark.parametrize(("target", "scale"), CHECKPOINT_TARGET_SCALES)
async def test_each_target_is_accepted_on_its_own_scale(
    async_session: AsyncSession, target: str, scale: str
) -> None:
    await _prediction(
        async_session, target=target, scale=scale, value=3.0, uncertainty=0.5
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"target": "liking", "scale": "1-5", "value": 3.0},
        {"target": "rating", "scale": "0-10", "value": 3.0},
        {"target": "familiarity"},
        {"value": 10.5},
        {"value": -0.1},
        {"target": "rating", "scale": "1-5", "value": 0.5},
        {"value": float("inf")},
        {"uncertainty": -1.0},
        {"uncertainty": float("inf")},
        {"fragrance_id": "no-such-fragrance"},
    ],
)
async def test_a_mistyped_prediction_is_rejected(
    async_session: AsyncSession, overrides: dict[str, object]
) -> None:
    with pytest.raises(IntegrityError):
        await _prediction(async_session, **overrides)


@pytest.mark.asyncio
async def test_one_prediction_per_checkpoint_fragrance_and_target(
    async_session: AsyncSession,
) -> None:
    first = await _prediction(async_session)
    async_session.add(
        CheckpointPrediction(
            checkpoint_id=first.checkpoint_id,
            fragrance_id=first.fragrance_id,
            target="liking",
            scale="0-10",
            value=2.0,
        )
    )
    with pytest.raises(IntegrityError):
        await async_session.flush()


@pytest.mark.asyncio
async def test_a_checkpoint_with_predictions_cannot_be_hard_deleted(
    async_session: AsyncSession,
) -> None:
    row = await _prediction(async_session)
    checkpoint = await async_session.get(ModelCheckpoint, row.checkpoint_id)
    await async_session.delete(checkpoint)
    with pytest.raises(IntegrityError):
        await async_session.flush()


@pytest.mark.asyncio
async def test_a_feature_snapshot_is_content_addressed(
    async_session: AsyncSession,
) -> None:
    async_session.add(_feature_snapshot())
    await async_session.flush()
    await _rejects(async_session, _feature_snapshot(feature_space_version="fs-v3"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"content_hash": DIGEST.upper()},
        {"content_hash": None},
        {"features": ["fragrance-1"]},
        {"features": None},
        {"feature_space_version": None},
    ],
)
async def test_a_malformed_feature_snapshot_is_rejected(
    async_session: AsyncSession, overrides: dict[str, object]
) -> None:
    await _rejects(async_session, _feature_snapshot(**overrides))


@pytest.mark.asyncio
async def test_a_prediction_snapshot_can_reference_a_feature_snapshot(
    async_session: AsyncSession,
) -> None:
    snapshot = _feature_snapshot()
    reviewer = Reviewer(name="pred")
    fragrance = await _fragrance(async_session)
    async_session.add_all([snapshot, reviewer])
    await async_session.flush()
    prediction = PredictionSnapshot(
        reviewer_id=reviewer.id,
        fragrance_id=fragrance.id,
        model_id="affinity",
        model_version="v2",
        feature_snapshot_id=snapshot.id,
    )
    async_session.add(prediction)
    await async_session.flush()

    await async_session.delete(snapshot)
    with pytest.raises(IntegrityError):
        await async_session.flush()
