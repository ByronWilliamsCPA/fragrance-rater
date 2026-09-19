"""predict_and_freeze gives affinity-v1 a prospective record (ADR-009)."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fragrance_rater.ml.feature_space import FEATURE_SPACE_VERSION, vectorize
from fragrance_rater.ml.model import AffinityV1
from fragrance_rater.ml.predict import (
    SKIP_EXISTING,
    SKIP_HOLDOUT_OBSERVED,
    SKIP_MISSING,
    leakage_check,
    predict_and_freeze,
)
from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance, FragranceNote, Note
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.services.preference_history import PreferenceHistoryService
from fragrance_rater.services.recommendation_service import RecommendationService
from fragrance_rater.utils.timestamps import now_naive_utc

RATED = ["rated-a", "rated-b", "rated-c"]


def _fragrance(key, family="woody", **kwargs):
    return Fragrance(
        id=key,
        name=key,
        brand="House",
        concentration="EDP",
        gender_target="unisex",
        primary_family=family,
        subfamily="",
        data_source="manual",
        **kwargs,
    )


@pytest_asyncio.fixture
async def world(async_session):
    """One evaluator with three rated versions and one assigned holdout."""
    async_session.add(Reviewer(id="owner", name="Owner"))
    notes = {
        "vetiver": Note(id="n-vetiver", name="Vetiver", category="Wood"),
        "amber": Note(id="n-amber", name="Amber", category="Resin"),
    }
    async_session.add_all(notes.values())
    for key in [*RATED, "holdout"]:
        async_session.add(_fragrance(key))
    # A version soft-deleted out of the active catalog: it can never be
    # scored again, so a prediction for it must be skipped, not fabricated.
    async_session.add(_fragrance("gone", deleted_at=now_naive_utc()))
    await async_session.flush()
    for key in [*RATED, "holdout", "gone"]:
        async_session.add(
            FragranceNote(fragrance_id=key, note_id="n-vetiver", position="top")
        )
        async_session.add(
            FragranceNote(fragrance_id=key, note_id="n-amber", position="base")
        )
    for rating, key in enumerate(RATED, start=3):
        async_session.add(
            Evaluation(
                reviewer_id="owner",
                fragrance_id=key,
                rating=rating,
                evaluated_at=now_naive_utc(),
            )
        )
    program = Program(name="Prospective", version="1")
    async_session.add(program)
    await async_session.flush()
    membership = Membership(
        program_id=program.id, fragrance_id="holdout", role="HOLDOUT"
    )
    enrollment = Enrollment(
        program_id=program.id, reviewer_id="owner", recorder_usernames=["recorder"]
    )
    async_session.add_all([membership, enrollment])
    await async_session.flush()
    return async_session, membership, enrollment


async def _observe_holdout(session, membership, enrollment, phase="PRE_REVEAL"):
    """Record one response against the holdout, closing prospective status."""
    calibration = CalibrationSession(enrollment_id=enrollment.id)
    session.add(calibration)
    await session.flush()
    presentation = Presentation(
        session_id=calibration.id,
        membership_id=membership.id,
        blind_code="BLIND-1",
        position=0,
        blotter_locked_at=now_naive_utc(),
    )
    session.add(presentation)
    await session.flush()
    session.add(
        Observation(
            presentation_id=presentation.id,
            stage="BLOTTER",
            phase=phase,
            detected=True,
            intensity=3,
            liking=7,
            recorded_by="recorder",
        )
    )
    await session.flush()


async def _run(session, **kwargs):
    kwargs.setdefault("model_key", "affinity-v1")
    kwargs.setdefault("reviewer_id", "owner")
    kwargs.setdefault("recorded_by", "scientist")
    return await predict_and_freeze(session, **kwargs)


@pytest.mark.asyncio
async def test_default_target_is_the_assigned_holdout(world):
    session, _, _ = world
    result = await _run(session)
    assert len(result.created) == 1
    assert result.skipped == []
    snapshot = await session.get(PredictionSnapshot, result.created[0])
    assert snapshot.fragrance_id == "holdout"
    assert result.algorithm_version == "affinity-v1"
    assert result.param_digest == AffinityV1.spec.digest
    assert result.feature_space_version == FEATURE_SPACE_VERSION
    assert result.n_evidence == len(RATED)


@pytest.mark.asyncio
async def test_snapshot_carries_server_built_manifest_and_digests(world):
    session, _, _ = world
    result = await _run(session)
    snapshot = await session.get(PredictionSnapshot, result.created[0])
    assert snapshot.model_id == "affinity"
    assert snapshot.model_version == "v1"
    assert snapshot.feature_snapshot_version == FEATURE_SPACE_VERSION
    assert snapshot.predicted_scale == "0-10"
    assert snapshot.recorded_by == "scientist"
    # Server-built: the three rated versions, never the holdout, and each
    # row carries the feature-space payload the manifest builder produces.
    assert {row["fragrance_id"] for row in snapshot.input_manifest} == set(RATED)
    assert all("source_features" in row for row in snapshot.input_manifest)
    explanation = snapshot.explanation
    assert explanation["param_digest"] == AffinityV1.spec.digest
    assert explanation["input_digest"] == result.input_digest
    assert explanation["score_type"] == "uncalibrated-affinity"
    assert explanation["n_evidence"] == len(RATED)
    assert "ADR-007" in explanation["note"]
    assert snapshot.predicted_rating == round(explanation["score"] * 10, 3)


@pytest.mark.asyncio
async def test_predicted_rating_matches_the_model_scored_directly(world):
    session, _, _ = world
    result = await _run(session)
    snapshot = await session.get(PredictionSnapshot, result.created[0])
    model = AffinityV1()
    profile = await RecommendationService(
        session, model=model
    ).build_preference_profile("owner")
    fragrance = await session.scalar(
        select(Fragrance)
        .where(Fragrance.id == "holdout")
        .options(
            selectinload(Fragrance.notes).selectinload(FragranceNote.note),
            selectinload(Fragrance.accords),
        )
    )
    expected = model.score(profile, vectorize(fragrance))
    assert snapshot.explanation["score"] == pytest.approx(expected.score)
    assert snapshot.explanation["vetoed"] is expected.vetoed
    assert snapshot.uncertainty is None


@pytest.mark.asyncio
async def test_second_run_is_idempotent(world):
    session, _, _ = world
    first = await _run(session)
    second = await _run(session)
    assert second.created == []
    assert second.skipped == [("holdout", SKIP_EXISTING)]
    rows = list(await session.scalars(select(PredictionSnapshot.id)))
    assert rows == first.created


@pytest.mark.asyncio
async def test_holdout_with_a_pre_reveal_observation_is_skipped(world):
    session, membership, enrollment = world
    await _observe_holdout(session, membership, enrollment)
    result = await _run(session)
    assert result.created == []
    assert result.skipped == [("holdout", SKIP_HOLDOUT_OBSERVED)]


@pytest.mark.asyncio
async def test_post_reveal_observation_does_not_close_prediction(world):
    session, membership, enrollment = world
    await _observe_holdout(session, membership, enrollment, phase="POST_REVEAL")
    result = await _run(session)
    assert len(result.created) == 1
    assert result.skipped == []


@pytest.mark.asyncio
async def test_missing_or_deleted_fragrances_are_skipped(world):
    session, _, _ = world
    result = await _run(session, fragrance_ids=["gone", "never-existed", "rated-a"])
    assert result.skipped == [
        ("gone", SKIP_MISSING),
        ("never-existed", SKIP_MISSING),
    ]
    assert len(result.created) == 1


@pytest.mark.asyncio
async def test_explicit_targets_need_not_be_holdouts(world):
    session, _, _ = world
    result = await _run(session, fragrance_ids=["rated-a", "rated-a"])
    # Duplicates collapse; a plain rated version is a legitimate target.
    assert len(result.created) == 1
    snapshot = await session.get(PredictionSnapshot, result.created[0])
    assert snapshot.fragrance_id == "rated-a"


@pytest.mark.asyncio
async def test_one_to_five_scale_rescaling(world):
    session, _, _ = world
    result = await _run(session, predicted_scale="1-5")
    snapshot = await session.get(PredictionSnapshot, result.created[0])
    assert snapshot.predicted_scale == "1-5"
    score = snapshot.explanation["score"]
    assert snapshot.predicted_rating == round(1 + score * 4, 3)
    assert 1 <= snapshot.predicted_rating <= 5


@pytest.mark.asyncio
async def test_unsupported_scale_is_rejected(world):
    session, _, _ = world
    with pytest.raises(ValueError, match="unsupported predicted_scale"):
        await _run(session, predicted_scale="0-100")


@pytest.mark.asyncio
async def test_unknown_model_key_is_rejected(world):
    session, _, _ = world
    with pytest.raises(KeyError, match="affinity-v1"):
        await _run(session, model_key="gbm-v9")


@pytest.mark.asyncio
async def test_leakage_check_flags_a_holdout_row(world):
    session, _, _ = world
    manifest = await PreferenceHistoryService(session).training_manifest("owner")
    assert await leakage_check(session, "owner", manifest) == []
    leaky = [*manifest, {"id": "leaked-row", "fragrance_id": "holdout"}]
    assert await leakage_check(session, "owner", leaky) == ["leaked-row"]


@pytest.mark.asyncio
async def test_leaky_manifest_aborts_the_run(world, monkeypatch):
    session, _, _ = world

    async def leaky_manifest(self, reviewer_id, **kwargs):
        return [{"id": "leaked-row", "fragrance_id": "holdout"}]

    monkeypatch.setattr(PreferenceHistoryService, "training_manifest", leaky_manifest)
    with pytest.raises(ValueError, match="holdout evidence"):
        await _run(session)
    assert list(await session.scalars(select(PredictionSnapshot.id))) == []


@pytest.mark.asyncio
async def test_runner_does_not_commit(world):
    session, _, _ = world
    await _run(session)
    await session.rollback()
    # The runner only flushed, so the caller's rollback discards the run;
    # the unit of work belongs to the caller (the CLI's --dry-run relies
    # on exactly this).
    assert list(await session.scalars(select(PredictionSnapshot.id))) == []
