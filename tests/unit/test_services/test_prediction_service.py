"""Prediction snapshots are frozen up front and linked to an outcome once."""

from datetime import timedelta, timezone

import pytest
import pytest_asyncio

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.prediction import PredictionCreate, PredictionOutcomeInput
from fragrance_rater.services.prediction_service import (
    PredictionConflictError,
    PredictionService,
)
from fragrance_rater.utils.timestamps import now_naive_utc


@pytest_asyncio.fixture
async def scenario(async_session):
    """One reviewer and one fragrance to predict against."""
    async_session.add(Reviewer(id="owner", name="Owner"))
    async_session.add(
        Fragrance(
            id="target",
            name="Target Scent",
            brand="House",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
    )
    await async_session.flush()
    return PredictionService(async_session)


@pytest.mark.asyncio
async def test_create_freezes_predicted_values(scenario):
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            model_id="gbm-liking-v0",
            model_version="2026-09-12",
            predicted_rating=7.2,
            uncertainty=1.1,
            input_manifest=[{"feature": "sweetness", "value": 3}],
        ),
        recorded_by="scientist",
    )
    assert snapshot.predicted_rating == 7.2
    assert snapshot.uncertainty == 1.1
    assert snapshot.predicted_scale == "0-10"
    assert snapshot.outcome_linked_at is None
    assert snapshot.recorded_by == "scientist"


@pytest.mark.asyncio
async def test_create_rejects_unknown_checkpoint(scenario):
    service = scenario
    with pytest.raises(LookupError, match="checkpoint"):
        await service.create(
            PredictionCreate(
                reviewer_id="owner",
                fragrance_id="target",
                checkpoint_id="ghost-checkpoint",
                model_id="m",
                model_version="v1",
            ),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_unknown_prediction(scenario):
    service = scenario
    with pytest.raises(LookupError, match="prediction not found"):
        await service.link_outcome(
            "ghost-prediction",
            PredictionOutcomeInput(outcome_evaluation_id="whatever"),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_create_rejects_unknown_reviewer_or_fragrance(scenario):
    service = scenario
    with pytest.raises(LookupError):
        await service.create(
            PredictionCreate(
                reviewer_id="ghost",
                fragrance_id="target",
                model_id="m",
                model_version="v1",
            ),
            recorded_by=None,
        )
    with pytest.raises(LookupError):
        await service.create(
            PredictionCreate(
                reviewer_id="owner",
                fragrance_id="ghost",
                model_id="m",
                model_version="v1",
            ),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_to_a_later_evaluation(scenario):
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            model_id="m",
            model_version="v1",
            predicted_rating=7.0,
            predicted_scale="1-5",
        ),
        recorded_by=None,
    )
    evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="owner",
        rating=4,
        evaluated_at=snapshot.created_at + timedelta(minutes=5),
    )
    service.db.add(evaluation)
    await service.db.flush()
    linked = await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
        recorded_by="recorder",
    )
    assert linked.outcome_evaluation_id == evaluation.id
    assert linked.outcome_linked_at is not None
    # The frozen prediction itself never changes when the outcome is linked.
    assert linked.predicted_rating == 7.0


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_second_link(scenario):
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="owner",
        rating=4,
        evaluated_at=snapshot.created_at + timedelta(minutes=1),
    )
    service.db.add(evaluation)
    await service.db.flush()
    await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
        recorded_by=None,
    )
    with pytest.raises(PredictionConflictError, match="already has a linked outcome"):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_mismatched_reviewer(scenario):
    service = scenario
    service.db.add(Reviewer(id="someone-else", name="Someone Else"))
    await service.db.flush()
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="someone-else",
        rating=4,
        evaluated_at=snapshot.created_at + timedelta(minutes=1),
    )
    service.db.add(evaluation)
    await service.db.flush()
    with pytest.raises(PredictionConflictError, match="this reviewer"):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_normalizes_a_tz_aware_evaluation_timestamp(scenario):
    """A tz-aware `evaluated_at` (e.g. set directly in-memory) still compares correctly."""
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="owner",
        rating=4,
        evaluated_at=(snapshot.created_at + timedelta(minutes=5)).replace(
            tzinfo=timezone.utc  # noqa: UP017 - Python 3.10 floor, matches prediction_service.py
        ),
    )
    service.db.add(evaluation)
    await service.db.flush()
    linked = await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
        recorded_by=None,
    )
    assert linked.outcome_evaluation_id == evaluation.id


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_controlled_observation_for_another_fragrance(
    scenario,
):
    service = scenario
    async_session = service.db
    async_session.add(
        Fragrance(
            id="other",
            name="Other Scent",
            brand="House",
            concentration="EDT",
            gender_target="Unisex",
            primary_family="citrus",
            subfamily="",
            data_source="manual",
        )
    )
    await async_session.flush()
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    program = Program(name="Diagnostic 2", version="1")
    async_session.add(program)
    await async_session.flush()
    # Membership assigned to a *different* fragrance than the prediction.
    member = Membership(program_id=program.id, fragrance_id="other", role="RETEST")
    async_session.add(member)
    enrollment = Enrollment(
        program_id=program.id, reviewer_id="owner", recorder_usernames=["rec"]
    )
    async_session.add(enrollment)
    await async_session.flush()
    session = CalibrationSession(enrollment_id=enrollment.id)
    async_session.add(session)
    await async_session.flush()
    presentation = Presentation(
        session_id=session.id, membership_id=member.id, blind_code="X2", position=1
    )
    async_session.add(presentation)
    await async_session.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage="SKIN",
        phase="PRE_REVEAL",
        detected=True,
        intensity=3,
        liking=8,
        recorded_by="rec",
        created_at=snapshot.created_at + timedelta(minutes=10),
    )
    async_session.add(observation)
    await async_session.flush()
    with pytest.raises(PredictionConflictError, match="must belong to this reviewer"):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_observation_id=observation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_an_evaluation_recorded_before_the_prediction(
    scenario,
):
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    stale_evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="owner",
        rating=4,
        evaluated_at=snapshot.created_at - timedelta(days=1),
    )
    service.db.add(stale_evaluation)
    await service.db.flush()
    with pytest.raises(
        PredictionConflictError, match="after the prediction was frozen"
    ):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_evaluation_id=stale_evaluation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_to_a_later_controlled_observation(scenario):
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    program = Program(name="Diagnostic", version="1")
    service.db.add(program)
    await service.db.flush()
    member = Membership(program_id=program.id, fragrance_id="target", role="RETEST")
    service.db.add(member)
    enrollment = Enrollment(
        program_id=program.id, reviewer_id="owner", recorder_usernames=["rec"]
    )
    service.db.add(enrollment)
    await service.db.flush()
    session = CalibrationSession(enrollment_id=enrollment.id)
    service.db.add(session)
    await service.db.flush()
    presentation = Presentation(
        session_id=session.id, membership_id=member.id, blind_code="X1", position=1
    )
    service.db.add(presentation)
    await service.db.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage="SKIN",
        phase="PRE_REVEAL",
        detected=True,
        intensity=3,
        liking=8,
        recorded_by="rec",
        created_at=snapshot.created_at + timedelta(minutes=10),
    )
    service.db.add(observation)
    await service.db.flush()
    linked = await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_observation_id=observation.id),
        recorded_by="rec",
    )
    assert linked.outcome_observation_id == observation.id
    assert linked.outcome_evaluation_id is None


@pytest.mark.asyncio
async def test_list_for_reviewer_returns_newest_first(scenario):
    service = scenario
    first = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    first.created_at = now_naive_utc() - timedelta(hours=1)
    await service.db.flush()
    second = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v2"
        ),
        recorded_by=None,
    )
    results = await service.list_for_reviewer("owner")
    assert [item.id for item in results] == [second.id, first.id]
