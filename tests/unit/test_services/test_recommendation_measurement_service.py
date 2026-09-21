"""SQLite-runnable unit tests for the recommendation measurement service.

These call ``RecommendationMeasurementService`` directly against the
``async_session`` fixture rather than through the FastAPI/ASGI layer used by
``tests/unit/test_api/test_recommendation_measurement.py``. That API-level
suite already exercises most of this service's happy path, but branches such
as the "reviewer not found" guards, holdout exclusion during feedback, the
defensive outcome-link checks in ``_validate_outcome``, and the
occurred-at collision handling in ``record_operational_event`` are either
unreachable through the HTTP contract (a valid ``ResponseCreate`` cannot
carry a linked outcome without ``sampling_state="SAMPLED"``; the Pydantic
validator rejects it first) or need direct, tightly-scoped setup to reach at
all. Calling the service directly is also what actually gets credited by
coverage.py for this module; the equivalent branches exercised only through
``httpx.ASGITransport`` + FastAPI ``Depends()`` were repeatedly confirmed
during R1 (docs/ci-gates.md) to run for real (verified with a temporary
``print`` in the service) but not to register as covered lines.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

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
from fragrance_rater.schemas.recommendation_measurement import (
    ResponseCreate,
    RunCreate,
)
from fragrance_rater.services.recommendation_measurement_service import (
    MeasurementConflictError,
    RecommendationMeasurementService,
)
from fragrance_rater.utils.timestamps import now_naive_utc


async def _seed_reviewer_and_candidates(
    session, *, rated: int = 3, extra: int = 1
) -> tuple[Reviewer, list[Fragrance]]:
    reviewer = Reviewer(name="Unit reviewer")
    fragrances = [
        Fragrance(
            name=f"Unit scent {index}",
            brand="Unit house",
            concentration="EDP",
            version_key=f"unit-{index}",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="unit",
        )
        for index in range(rated + extra)
    ]
    session.add_all([reviewer, *fragrances])
    await session.flush()
    session.add_all(
        [
            Evaluation(reviewer_id=reviewer.id, fragrance_id=f.id, rating=5)
            for f in fragrances[:rated]
        ]
    )
    await session.commit()
    return reviewer, fragrances


@pytest.mark.asyncio
async def test_create_run_rejects_unknown_reviewer(async_session) -> None:
    service = RecommendationMeasurementService(async_session)
    with pytest.raises(LookupError, match="reviewer not found"):
        await service.create_run(
            RunCreate(reviewer_id="missing", limit=1), recorded_by="unit"
        )


@pytest.mark.asyncio
async def test_create_run_collects_source_features_and_persists_impressions(
    async_session,
) -> None:
    reviewer, fragrances = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)
    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1, exclude_rated=True),
        recorded_by="unit",
    )
    assert run.id
    manifest_version_keys: set[str] = set()
    for row in run.input_manifest:
        source_features = row.get("source_features")
        if isinstance(source_features, dict):
            version_key = source_features.get("version_key")
            if isinstance(version_key, str):
                manifest_version_keys.add(version_key)
    assert manifest_version_keys == {"unit-0", "unit-1", "unit-2"}
    assert run.source_snapshot["input_version_keys"] == sorted(manifest_version_keys)
    candidate_versions = run.source_snapshot["candidate_versions"]
    assert isinstance(candidate_versions, list)
    first_candidate = candidate_versions[0]
    assert isinstance(first_candidate, dict)
    assert first_candidate["fragrance_id"] == fragrances[3].id


@pytest.mark.asyncio
async def test_run_rows_rejects_unknown_run(async_session) -> None:
    service = RecommendationMeasurementService(async_session)
    with pytest.raises(LookupError, match="recommendation run not found"):
        await service.run_rows("missing")


@pytest.mark.asyncio
async def test_response_history_empty_and_populated(async_session) -> None:
    reviewer, _ = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)

    assert await service.response_history(set()) == {}

    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1), recorded_by="unit"
    )
    _, rows = await service.run_rows(run.id)
    impression_id = rows[0][0].id
    await service.append_response(
        impression_id, ResponseCreate(interested=True), recorded_by="unit"
    )
    await service.append_response(
        impression_id, ResponseCreate(interested=False), recorded_by="unit"
    )
    history = await service.response_history({impression_id})
    assert [item.revision for item in history[impression_id]] == [1, 2]


@pytest.mark.asyncio
async def test_append_response_rejects_unknown_impression(async_session) -> None:
    service = RecommendationMeasurementService(async_session)
    with pytest.raises(LookupError, match="recommendation impression not found"):
        await service.append_response(
            "missing", ResponseCreate(interested=True), recorded_by="unit"
        )


@pytest.mark.asyncio
async def test_append_response_rejects_holdout_version(async_session) -> None:
    reviewer, _fragrances = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)
    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1), recorded_by="unit"
    )
    _, rows = await service.run_rows(run.id)
    impression = rows[0][0]

    program = Program(name="Holdout gate", version="v1", status="active")
    async_session.add(program)
    await async_session.flush()
    async_session.add(
        Membership(
            program_id=program.id,
            fragrance_id=impression.fragrance_id,
            role="HOLDOUT",
            group_name="Gate",
        )
    )
    async_session.add(
        Enrollment(
            program_id=program.id,
            reviewer_id=reviewer.id,
            recorder_usernames=["unit"],
        )
    )
    await async_session.commit()

    with pytest.raises(MeasurementConflictError, match="holdout version"):
        await service.append_response(
            impression.id, ResponseCreate(interested=True), recorded_by="unit"
        )


@pytest.mark.asyncio
async def test_validate_outcome_rejects_link_without_sampled_state(
    async_session,
) -> None:
    """Defense-in-depth: unreachable through the API, whose Pydantic
    validator (schemas.recommendation_measurement.ResponseCreate) already
    rejects a linked outcome without sampling_state=SAMPLED. Bypass it with
    model_construct to exercise the service's own guard directly.
    """
    reviewer, _ = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)
    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1), recorded_by="unit"
    )
    _, rows = await service.run_rows(run.id)
    impression = rows[0][0]

    unvalidated = ResponseCreate.model_construct(
        interested=None,
        sampling_state=None,
        unavailable_reason=None,
        outcome_evaluation_id="some-evaluation",
        outcome_observation_id=None,
        would_wear=None,
        would_buy=None,
    )
    with pytest.raises(
        MeasurementConflictError, match="require sampling_state SAMPLED"
    ):
        await service._validate_outcome(unvalidated, run, impression)


@pytest.mark.asyncio
async def test_validate_outcome_rejects_mismatched_evaluation(async_session) -> None:
    reviewer, fragrances = await _seed_reviewer_and_candidates(async_session)
    other_reviewer = Reviewer(name="Someone else")
    async_session.add(other_reviewer)
    await async_session.flush()
    mismatched = Evaluation(
        reviewer_id=other_reviewer.id, fragrance_id=fragrances[3].id, rating=4
    )
    async_session.add(mismatched)
    await async_session.commit()

    service = RecommendationMeasurementService(async_session)
    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1), recorded_by="unit"
    )
    _, rows = await service.run_rows(run.id)
    impression = rows[0][0]

    data = ResponseCreate(sampling_state="SAMPLED", outcome_evaluation_id=mismatched.id)
    with pytest.raises(MeasurementConflictError, match="live, on-me encounter"):
        await service._validate_outcome(data, run, impression)


@pytest.mark.asyncio
async def test_validate_outcome_rejects_missing_observation(async_session) -> None:
    reviewer, _ = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)
    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1), recorded_by="unit"
    )
    _, rows = await service.run_rows(run.id)
    impression = rows[0][0]

    data = ResponseCreate(sampling_state="SAMPLED", outcome_observation_id="missing")
    with pytest.raises(MeasurementConflictError, match="revealed and match"):
        await service._validate_outcome(data, run, impression)


@pytest.mark.asyncio
async def test_validate_outcome_accepts_revealed_matching_observation(
    async_session,
) -> None:
    reviewer, _fragrances = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)
    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1), recorded_by="unit"
    )
    _, rows = await service.run_rows(run.id)
    impression = rows[0][0]

    program = Program(name="Controlled gate", version="v1", status="active")
    async_session.add(program)
    await async_session.flush()
    membership = Membership(
        program_id=program.id,
        fragrance_id=impression.fragrance_id,
        role="UNIVERSAL_BASELINE",
        group_name="Baseline",
    )
    async_session.add(membership)
    enrollment = Enrollment(
        program_id=program.id,
        reviewer_id=reviewer.id,
        recorder_usernames=["unit"],
        revealed_at=now_naive_utc(),
        revealed_by="unit",
    )
    async_session.add(enrollment)
    await async_session.flush()
    calibration_session = CalibrationSession(enrollment_id=enrollment.id, context={})
    async_session.add(calibration_session)
    await async_session.flush()
    presentation = Presentation(
        session_id=calibration_session.id,
        membership_id=membership.id,
        blind_code="ABCD1234",
        position=1,
    )
    async_session.add(presentation)
    await async_session.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage="BLOTTER",
        phase="FIRST",
        detected=True,
        intensity=3,
        liking=7,
        recorded_by="unit",
        created_at=impression.shown_at + timedelta(minutes=1),
    )
    async_session.add(observation)
    await async_session.commit()

    data = ResponseCreate(
        sampling_state="SAMPLED", outcome_observation_id=observation.id
    )
    await service._validate_outcome(data, run, impression)


@pytest.mark.asyncio
async def test_metrics_aggregates_linked_ordinary_outcome_rating(async_session) -> None:
    reviewer, _fragrances = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)
    run = await service.create_run(
        RunCreate(reviewer_id=reviewer.id, limit=1), recorded_by="unit"
    )
    _, rows = await service.run_rows(run.id)
    impression = rows[0][0]

    outcome = Evaluation(
        reviewer_id=reviewer.id,
        fragrance_id=impression.fragrance_id,
        rating=4,
        evaluated_at=impression.shown_at + timedelta(minutes=5),
    )
    async_session.add(outcome)
    await async_session.commit()

    await service.append_response(
        impression.id,
        ResponseCreate(sampling_state="SAMPLED", outcome_evaluation_id=outcome.id),
        recorded_by="unit",
    )
    # A second revision on the same impression exercises the "keep only the
    # latest revision per impression" setdefault path in metrics().
    await service.append_response(
        impression.id,
        ResponseCreate(
            sampling_state="SAMPLED",
            outcome_evaluation_id=outcome.id,
            would_wear=True,
        ),
        recorded_by="unit",
    )

    metrics = await service.metrics(reviewer.id)
    assert metrics.linked_outcomes == 1
    assert metrics.mean_ordinary_rating == 4.0
    assert metrics.would_wear_positive == 1


@pytest.mark.asyncio
async def test_record_operational_event_rejects_unknown_reviewer(async_session) -> None:
    service = RecommendationMeasurementService(async_session)
    with pytest.raises(LookupError, match="reviewer not found"):
        await service.record_operational_event(
            "missing", "CONNECTIVITY_FAILURE", None, recorded_by="unit"
        )


@pytest.mark.asyncio
async def test_record_operational_event_avoids_timestamp_collision(
    async_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewer, _ = await _seed_reviewer_and_candidates(async_session)
    service = RecommendationMeasurementService(async_session)
    fixed_time = now_naive_utc()
    monkeypatch.setattr(
        "fragrance_rater.services.recommendation_measurement_service.now_naive_utc",
        lambda: fixed_time,
    )

    first = await service.record_operational_event(
        reviewer.id, "CONNECTIVITY_FAILURE", None, recorded_by="unit"
    )
    second = await service.record_operational_event(
        reviewer.id, "MANUAL_RECOVERY", None, recorded_by="unit"
    )
    assert first.occurred_at == fixed_time
    assert second.occurred_at > first.occurred_at
