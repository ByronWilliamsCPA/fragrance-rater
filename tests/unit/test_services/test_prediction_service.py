"""Prediction snapshots are frozen up front and linked to an outcome once."""

from datetime import timedelta, timezone

import pytest
import pytest_asyncio

from fragrance_rater.core.exceptions import ResourceNotFoundError
from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    ModelCheckpoint,
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
    with pytest.raises(ResourceNotFoundError, match="checkpoint"):
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
async def test_create_accepts_a_checkpoint_belonging_to_the_same_reviewer(scenario):
    service = scenario
    program = Program(name="Checkpoint owner match", version="1")
    service.db.add(program)
    await service.db.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id="owner", recorder_usernames=["rec"]
    )
    service.db.add(enrollment)
    await service.db.flush()
    checkpoint = ModelCheckpoint(
        enrollment_id=enrollment.id, algorithm_version="v1", manifest=[], predictions=[]
    )
    service.db.add(checkpoint)
    await service.db.flush()
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            checkpoint_id=checkpoint.id,
            model_id="m",
            model_version="v1",
        ),
        recorded_by=None,
    )
    assert snapshot.checkpoint_id == checkpoint.id


@pytest.mark.asyncio
async def test_create_rejects_a_checkpoint_belonging_to_a_different_reviewer(scenario):
    service = scenario
    service.db.add(Reviewer(id="someone-else", name="Someone Else"))
    program = Program(name="Checkpoint owner mismatch", version="1")
    service.db.add(program)
    await service.db.flush()
    other_enrollment = Enrollment(
        program_id=program.id, reviewer_id="someone-else", recorder_usernames=["rec"]
    )
    service.db.add(other_enrollment)
    await service.db.flush()
    other_checkpoint = ModelCheckpoint(
        enrollment_id=other_enrollment.id,
        algorithm_version="v1",
        manifest=[],
        predictions=[],
    )
    service.db.add(other_checkpoint)
    await service.db.flush()
    with pytest.raises(PredictionConflictError, match="different reviewer"):
        await service.create(
            PredictionCreate(
                reviewer_id="owner",
                fragrance_id="target",
                checkpoint_id=other_checkpoint.id,
                model_id="m",
                model_version="v1",
            ),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_unknown_prediction(scenario):
    service = scenario
    with pytest.raises(ResourceNotFoundError, match="prediction not found"):
        await service.link_outcome(
            "ghost-prediction",
            PredictionOutcomeInput(outcome_evaluation_id="whatever"),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_create_rejects_unknown_reviewer_or_fragrance(scenario):
    service = scenario
    with pytest.raises(ResourceNotFoundError):
        await service.create(
            PredictionCreate(
                reviewer_id="ghost",
                fragrance_id="target",
                model_id="m",
                model_version="v1",
            ),
            recorded_by=None,
        )
    with pytest.raises(ResourceNotFoundError):
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
            predicted_rating=4.0,
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
    assert linked.predicted_rating == 4.0


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_conflicting_second_link(scenario):
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            model_id="m",
            model_version="v1",
            predicted_scale="1-5",
        ),
        recorded_by=None,
    )
    first_evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="owner",
        rating=4,
        evaluated_at=snapshot.created_at + timedelta(minutes=1),
    )
    second_evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="owner",
        rating=5,
        evaluated_at=snapshot.created_at + timedelta(minutes=2),
    )
    service.db.add_all([first_evaluation, second_evaluation])
    await service.db.flush()
    await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_evaluation_id=first_evaluation.id),
        recorded_by=None,
    )
    with pytest.raises(PredictionConflictError, match="already has a linked outcome"):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_evaluation_id=second_evaluation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_retry_with_the_same_outcome_is_idempotent(scenario):
    """A retried `link_outcome` call with the exact same outcome id(s)
    already linked is a no-op success, not a conflict, e.g. a client
    retrying after a dropped response."""
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            model_id="m",
            model_version="v1",
            predicted_scale="1-5",
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
    first = await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
        recorded_by="recorder",
    )
    retried = await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
        recorded_by="a-different-recorder",
    )
    assert retried.id == first.id
    assert retried.outcome_evaluation_id == evaluation.id
    assert retried.outcome_linked_at == first.outcome_linked_at
    # The no-op retry must not overwrite who originally recorded the link.
    assert retried.outcome_recorded_by == "recorder"


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_scale_mismatched_evaluation(scenario):
    """An evaluation outcome (fixed 1-5 scale) cannot be linked to a
    prediction declared on a different scale."""
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            model_id="m",
            model_version="v1",
            predicted_scale="0-10",
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
    with pytest.raises(PredictionConflictError, match="predicted_scale"):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_scale_mismatched_controlled_observation(
    scenario,
):
    """A controlled observation outcome (fixed 0-10 scale) cannot be linked
    to a prediction declared on a different scale."""
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            model_id="m",
            model_version="v1",
            predicted_scale="1-5",
            predicted_rating=4.0,
        ),
        recorded_by=None,
    )
    program = Program(name="Diagnostic scale mismatch", version="1")
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
        session_id=session.id, membership_id=member.id, blind_code="X7", position=1
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
    with pytest.raises(PredictionConflictError, match="predicted_scale"):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_observation_id=observation.id),
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
    """A tz-aware `evaluated_at` in a genuine non-UTC offset still normalizes to the
    correct UTC instant before comparison.

    Uses a real UTC-5 offset (not `.replace(tzinfo=timezone.utc)` on an
    already-wall-clock-UTC value) so a bug that merely strips tzinfo without
    converting would produce a wall-clock value five hours *before* the
    prediction was frozen, causing `link_outcome` to wrongly reject this as
    stale; only a real `astimezone()` conversion makes this pass.
    """
    service = scenario
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner",
            fragrance_id="target",
            model_id="m",
            model_version="v1",
            predicted_scale="1-5",
        ),
        recorded_by=None,
    )
    expected_utc = snapshot.created_at + timedelta(minutes=5)
    non_utc_offset = timezone(timedelta(hours=-5))
    evaluation = Evaluation(
        fragrance_id="target",
        reviewer_id="owner",
        rating=4,
        evaluated_at=expected_utc.replace(
            tzinfo=timezone.utc  # noqa: UP017 - Python 3.10 floor, matches prediction_service.py
        ).astimezone(non_utc_offset),
    )
    service.db.add(evaluation)
    await service.db.flush()
    # Sanity-check the fixture actually built a non-UTC-offset value, not an
    # accidental UTC one that would make this test as weak as before.
    assert evaluation.evaluated_at.utcoffset() == timedelta(hours=-5)
    linked = await service.link_outcome(
        snapshot.id,
        PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
        recorded_by=None,
    )
    assert linked.outcome_evaluation_id == evaluation.id
    assert PredictionService._naive_utc(evaluation.evaluated_at) == expected_utc


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
async def test_link_outcome_rejects_a_controlled_observation_for_a_mismatched_reviewer(
    scenario,
):
    service = scenario
    async_session = service.db
    async_session.add(Reviewer(id="someone-else", name="Someone Else"))
    await async_session.flush()
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    program = Program(name="Diagnostic reviewer mismatch", version="1")
    async_session.add(program)
    await async_session.flush()
    # Membership/enrollment assigned to a *different* reviewer than the prediction.
    member = Membership(program_id=program.id, fragrance_id="target", role="RETEST")
    async_session.add(member)
    enrollment = Enrollment(
        program_id=program.id, reviewer_id="someone-else", recorder_usernames=["rec"]
    )
    async_session.add(enrollment)
    await async_session.flush()
    session = CalibrationSession(enrollment_id=enrollment.id)
    async_session.add(session)
    await async_session.flush()
    presentation = Presentation(
        session_id=session.id, membership_id=member.id, blind_code="X3", position=1
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
async def test_link_outcome_rejects_a_controlled_observation_recorded_before_the_prediction(
    scenario,
):
    service = scenario
    async_session = service.db
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    program = Program(name="Diagnostic stale observation", version="1")
    async_session.add(program)
    await async_session.flush()
    member = Membership(program_id=program.id, fragrance_id="target", role="RETEST")
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
        session_id=session.id, membership_id=member.id, blind_code="X4", position=1
    )
    async_session.add(presentation)
    await async_session.flush()
    stale_observation = Observation(
        presentation_id=presentation.id,
        stage="SKIN",
        phase="PRE_REVEAL",
        detected=True,
        intensity=3,
        liking=8,
        recorded_by="rec",
        created_at=snapshot.created_at - timedelta(days=1),
    )
    async_session.add(stale_observation)
    await async_session.flush()
    with pytest.raises(
        PredictionConflictError, match="after the prediction was frozen"
    ):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_observation_id=stale_observation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_controlled_observation_for_a_soft_deleted_reviewer(
    scenario,
):
    """A reviewer soft-deleted after the prediction was frozen must not be a valid
    party to a later controlled-observation outcome link.

    RAD data-integrity category: soft-deleted rows must remain excluded from
    every read path, including outcome linking that happens well after the
    original prediction/enrollment were created.
    """
    service = scenario
    async_session = service.db
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    program = Program(name="Diagnostic soft-deleted reviewer", version="1")
    async_session.add(program)
    await async_session.flush()
    member = Membership(program_id=program.id, fragrance_id="target", role="RETEST")
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
        session_id=session.id, membership_id=member.id, blind_code="X5", position=1
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
    reviewer = await async_session.get(Reviewer, "owner")
    assert reviewer is not None
    reviewer.deleted_at = now_naive_utc()
    await async_session.flush()
    with pytest.raises(PredictionConflictError):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_observation_id=observation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_controlled_observation_for_a_soft_deleted_fragrance(
    scenario,
):
    """A fragrance soft-deleted after the prediction was frozen must not be a valid
    party to a later controlled-observation outcome link."""
    service = scenario
    async_session = service.db
    snapshot = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    program = Program(name="Diagnostic soft-deleted fragrance", version="1")
    async_session.add(program)
    await async_session.flush()
    member = Membership(program_id=program.id, fragrance_id="target", role="RETEST")
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
        session_id=session.id, membership_id=member.id, blind_code="X6", position=1
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
    fragrance = await async_session.get(Fragrance, "target")
    assert fragrance is not None
    fragrance.deleted_at = now_naive_utc()
    await async_session.flush()
    with pytest.raises(PredictionConflictError):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_observation_id=observation.id),
            recorded_by=None,
        )


@pytest.mark.asyncio
async def test_link_outcome_rejects_a_soft_deleted_evaluation(scenario):
    """A soft-deleted ordinary evaluation must not be usable as an outcome, even
    when its reviewer/fragrance/timing all otherwise match."""
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
        evaluated_at=snapshot.created_at + timedelta(minutes=5),
        deleted_at=now_naive_utc(),
    )
    service.db.add(evaluation)
    await service.db.flush()
    with pytest.raises(PredictionConflictError):
        await service.link_outcome(
            snapshot.id,
            PredictionOutcomeInput(outcome_evaluation_id=evaluation.id),
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


@pytest.mark.asyncio
async def test_list_for_reviewer_tiebreaks_equal_created_at_by_id_desc(scenario):
    """Rows sharing the same `created_at` (e.g. created within the same
    timestamp tick) still sort deterministically via the `id` tiebreaker."""
    service = scenario
    first = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v1"
        ),
        recorded_by=None,
    )
    second = await service.create(
        PredictionCreate(
            reviewer_id="owner", fragrance_id="target", model_id="m", model_version="v2"
        ),
        recorded_by=None,
    )
    same_moment = now_naive_utc()
    first.created_at = same_moment
    second.created_at = same_moment
    await service.db.flush()
    results = await service.list_for_reviewer("owner")
    assert [item.id for item in results] == sorted([first.id, second.id], reverse=True)
