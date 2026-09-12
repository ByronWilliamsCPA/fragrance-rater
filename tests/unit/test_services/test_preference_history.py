"""Model input policy regressions across ordinary and controlled workflows."""

import json
from datetime import timedelta

import pytest
import pytest_asyncio

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
from fragrance_rater.services.preference_history import PreferenceHistoryService
from fragrance_rater.services.recommendation_service import RecommendationService
from fragrance_rater.utils.timestamps import now_naive_utc


@pytest_asyncio.fixture
async def history_data(async_session):
    """Create one baseline, one holdout and an enrolled evaluator."""
    program = Program(name="History policy", version="1")
    async_session.add(program)
    async_session.add(Reviewer(id="owner", name="Owner"))
    async_session.add(Reviewer(id="other", name="Other"))
    for key, family in [("baseline", "woody"), ("holdout", "floral")]:
        async_session.add(
            Fragrance(
                id=key,
                name=key,
                brand="House",
                concentration="EDP",
                gender_target="unisex",
                primary_family=family,
                subfamily="",
                data_source="manual",
            )
        )
    await async_session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id="owner", recorder_usernames=["recorder"]
    )
    async_session.add(enrollment)
    await async_session.flush()
    session = CalibrationSession(enrollment_id=enrollment.id)
    async_session.add(session)
    await async_session.flush()
    presentations = {}
    base = None
    for position, role in enumerate(["UNIVERSAL_BASELINE", "HIDDEN_REPEAT", "HOLDOUT"]):
        member = Membership(
            program_id=program.id,
            fragrance_id="holdout" if role == "HOLDOUT" else "baseline",
            role=role,
            repeat_of_id=base.id if role == "HIDDEN_REPEAT" else None,
        )
        async_session.add(member)
        await async_session.flush()
        if base is None:
            base = member
        presentation = Presentation(
            session_id=session.id,
            membership_id=member.id,
            blind_code=f"BLIND-{position}",
            position=position,
            blotter_locked_at=now_naive_utc(),
        )
        async_session.add(presentation)
        await async_session.flush()
        presentations[role] = presentation
    return PreferenceHistoryService(async_session), enrollment, presentations


def observation(presentation, *, liking=8, phase="PRE_REVEAL", created_at=None):
    """Create a submitted response with distinct null detection semantics."""
    return Observation(
        presentation_id=presentation.id,
        stage="BLOTTER",
        phase=phase,
        detected=liking is not None,
        intensity=3 if liking is not None else 0,
        liking=liking,
        perceived_notes=["pencil"],
        recorded_by="recorder",
        created_at=created_at or now_naive_utc(),
    )


@pytest.mark.asyncio
async def test_controlled_manifest_exposes_typed_features_not_a_responses_blob(
    history_data,
):
    service, _, presentations = history_data
    service.db.add(observation(presentations["UNIVERSAL_BASELINE"], liking=9))
    await service.db.flush()
    manifest = await service.training_manifest("owner")
    assert len(manifest) == 1
    row = manifest[0]
    assert "responses" not in row
    assert row["features"]["perceived_notes"] == ["pencil"]
    assert row["features"]["would_wear"] is None
    assert row["notes_text"] == {
        "likes": None,
        "dislikes": None,
        "reminds_me_of": None,
        "comments": None,
    }


@pytest.mark.asyncio
async def test_holdouts_excluded_across_workflows_and_scoped_to_evaluator(history_data):
    service, _, presentations = history_data
    service.db.add(Evaluation(fragrance_id="holdout", reviewer_id="owner", rating=5))
    service.db.add(observation(presentations["HOLDOUT"]))
    await service.db.flush()
    assert await service.excluded_versions("owner") == {"holdout"}
    assert await service.excluded_versions("other") == set()
    assert await service.training_manifest("owner") == []
    profile = await RecommendationService(service.db).build_preference_profile("owner")
    assert profile.evaluation_count == 0
    assert profile.family_affinities == {}


@pytest.mark.asyncio
async def test_latest_ordinary_encounter_contributes_once(history_data):
    service, *_ = history_data
    now = now_naive_utc()
    service.db.add(
        Evaluation(
            id="old",
            fragrance_id="baseline",
            reviewer_id="owner",
            rating=1,
            evaluated_at=now - timedelta(days=1),
        )
    )
    service.db.add(
        Evaluation(
            id="new",
            fragrance_id="baseline",
            reviewer_id="owner",
            rating=5,
            evaluated_at=now,
        )
    )
    await service.db.flush()
    manifest = await service.training_manifest("owner")
    assert [row["id"] for row in manifest] == ["new"]
    assert manifest[0]["scale"] == "1-5"
    profile = await RecommendationService(service.db).build_preference_profile("owner")
    assert profile.evaluation_count == 1
    assert profile.family_affinities["woody"] == 2


@pytest.mark.asyncio
async def test_latest_non_detection_does_not_resurrect_earlier_liking(history_data):
    service, _, presentations = history_data
    presentation = presentations["UNIVERSAL_BASELINE"]
    service.db.add(
        observation(
            presentation, liking=8, created_at=now_naive_utc() - timedelta(minutes=1)
        )
    )
    service.db.add(observation(presentation, liking=None))
    await service.db.flush()
    assert await service.training_manifest("owner") == []


@pytest.mark.asyncio
async def test_hidden_repeats_and_post_reveal_are_not_training_inputs(history_data):
    service, _, presentations = history_data
    service.db.add(observation(presentations["HIDDEN_REPEAT"]))
    service.db.add(
        observation(presentations["UNIVERSAL_BASELINE"], phase="POST_REVEAL")
    )
    await service.db.flush()
    assert await service.training_manifest("owner") == []


@pytest.mark.asyncio
async def test_unlocked_stage_not_eligible_until_locked(history_data):
    service, _, presentations = history_data
    presentation = presentations["UNIVERSAL_BASELINE"]
    presentation.blotter_locked_at = None
    response = observation(presentation)
    service.db.add(response)
    await service.db.flush()
    assert await service.training_manifest("owner") == []
    presentation.blotter_locked_at = now_naive_utc()
    await service.db.flush()
    manifest = await service.training_manifest("owner")
    assert [row["id"] for row in manifest] == [response.id]
    assert manifest[0]["scale"] == "0-10"


@pytest.mark.asyncio
async def test_persisted_checkpoint_survives_response_and_source_changes(history_data):
    service, enrollment, presentations = history_data
    response = observation(presentations["UNIVERSAL_BASELINE"])
    service.db.add(response)
    await service.db.flush()
    manifest = await service.training_manifest("owner")
    assert manifest[0]["source_features"] == {
        "version_key": "legacy",
        "concentration": "EDP",
        "primary_family": "woody",
        "subfamily": "",
        "notes": [],
        "accords": [],
    }
    frozen_json = json.dumps(manifest, sort_keys=True)
    checkpoint = ModelCheckpoint(
        enrollment_id=enrollment.id,
        algorithm_version="test-model-1",
        manifest=manifest,
        predictions=[{"fragrance_id": "holdout", "score": 6.5}],
    )
    service.db.add(checkpoint)
    await service.db.flush()
    response.perceived_notes = ["changed"]
    response.liking = 2
    fragrance = await service.db.get(Fragrance, "baseline")
    fragrance.primary_family = "citrus"
    await service.db.flush()
    await service.db.refresh(checkpoint)
    assert json.dumps(checkpoint.manifest, sort_keys=True) == frozen_json
    assert checkpoint.predictions == [{"fragrance_id": "holdout", "score": 6.5}]
    assert (await service.training_manifest("owner"))[0]["rating"] == 2


@pytest.mark.asyncio
async def test_controlled_recommendation_contributes_after_reveal_once_per_version(
    history_data,
):
    service, enrollment, presentations = history_data
    base = presentations["UNIVERSAL_BASELINE"]
    service.db.add(observation(base, liking=10))
    service.db.add(observation(presentations["HIDDEN_REPEAT"], liking=0))
    await service.db.flush()
    recommender = RecommendationService(service.db)
    blind = await recommender.build_preference_profile("owner")
    assert blind.evaluation_count == 0
    assert blind.family_affinities == {}
    enrollment.revealed_at = now_naive_utc()
    await service.db.flush()
    revealed = await recommender.build_preference_profile("owner")
    assert revealed.evaluation_count == 1
    assert revealed.family_affinities["woody"] == 2.0
    # A skin score wins over blotter; ordinary evidence is averaged, not added.
    skin = observation(base, liking=0)
    skin.stage = "SKIN"
    base.skin_locked_at = now_naive_utc()
    service.db.add(skin)
    service.db.add(Evaluation(fragrance_id="baseline", reviewer_id="owner", rating=4))
    await service.db.flush()
    combined = await recommender.build_preference_profile("owner")
    assert combined.evaluation_count == 1
    assert combined.family_affinities["woody"] == -0.5


@pytest.mark.asyncio
async def test_newest_skin_rating_wins_across_presentations(history_data):
    service, enrollment, presentations = history_data
    base = presentations["UNIVERSAL_BASELINE"]
    enrollment.revealed_at = now_naive_utc()
    base.skin_locked_at = now_naive_utc()
    old = observation(base, liking=0, created_at=now_naive_utc() - timedelta(days=1))
    old.stage = "SKIN"
    service.db.add(old)
    retest = Presentation(
        session_id=base.session_id,
        membership_id=base.membership_id,
        blind_code="RETEST-SKIN",
        position=10,
        skin_locked_at=now_naive_utc(),
    )
    service.db.add(retest)
    await service.db.flush()
    newest = observation(retest, liking=10)
    newest.stage = "SKIN"
    service.db.add(newest)
    await service.db.flush()
    profile = await RecommendationService(service.db).build_preference_profile("owner")
    assert profile.evaluation_count == 1
    assert profile.family_affinities["woody"] == 2.0


@pytest.mark.asyncio
async def test_revealed_controlled_fragrance_excluded_from_unrated_recommendations(
    history_data,
):
    service, enrollment, presentations = history_data
    enrollment.revealed_at = now_naive_utc()
    service.db.add(observation(presentations["UNIVERSAL_BASELINE"]))
    for key in ["ordinary-one", "ordinary-two"]:
        service.db.add(
            Fragrance(
                id=key,
                name=key,
                brand="House",
                concentration="EDP",
                gender_target="unisex",
                primary_family="woody",
                subfamily="",
                data_source="manual",
            )
        )
        await service.db.flush()
        service.db.add(Evaluation(fragrance_id=key, reviewer_id="owner", rating=4))
    await service.db.flush()
    recommender = RecommendationService(service.db)
    all_candidates = await recommender.get_recommendations("owner", exclude_rated=False)
    assert "baseline" in {row.fragrance_id for row in all_candidates}
    unrated = await recommender.get_recommendations("owner", exclude_rated=True)
    assert "baseline" not in {row.fragrance_id for row in unrated}
    assert {row.fragrance_id for row in unrated}.isdisjoint(
        {"ordinary-one", "ordinary-two"}
    )


@pytest.mark.asyncio
async def test_unrevealed_holdout_in_other_program_is_not_prior_identity_exposure(
    history_data,
):
    from fragrance_rater.schemas.calibration import ResponseInput
    from fragrance_rater.services.calibration_service import CalibrationService

    service, enrollment, presentations = history_data
    enrollment.revealed_at = now_naive_utc()
    # Baseline reveal does not reveal this enrollment's untested holdout.
    presentations["HOLDOUT"].blotter_locked_at = None
    other_program = Program(name="Later program", version="1")
    service.db.add(other_program)
    await service.db.flush()
    other_enrollment = Enrollment(
        program_id=other_program.id,
        reviewer_id="owner",
        recorder_usernames=["recorder"],
    )
    member = Membership(
        program_id=other_program.id, fragrance_id="holdout", role="UNIVERSAL_BASELINE"
    )
    service.db.add_all([other_enrollment, member])
    await service.db.flush()
    session = CalibrationSession(enrollment_id=other_enrollment.id)
    service.db.add(session)
    await service.db.flush()
    target = Presentation(
        session_id=session.id,
        membership_id=member.id,
        blind_code="OTHER-PROGRAM",
        position=1,
    )
    service.db.add(target)
    await service.db.flush()
    calibration = CalibrationService(service.db)
    naive = await calibration.observe(
        target.id,
        ResponseInput(stage="BLOTTER", detected=True, intensity=2, liking=7),
        "recorder",
        admin=False,
    )
    assert naive.phase == "PRE_REVEAL"
    presentations["HOLDOUT"].blotter_locked_at = now_naive_utc()
    await service.db.flush()
    exposed = await calibration.observe(
        target.id,
        ResponseInput(stage="BLOTTER", detected=True, intensity=2, liking=7),
        "recorder",
        admin=False,
    )
    assert exposed.phase == "PREVIOUSLY_REVEALED"
