"""Controlled workflow integrity and blind-response regression tests."""

import json
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from fragrance_rater.models.calibration import Observation, Program
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import (
    EnrollmentInput,
    MembershipInput,
    ResponseInput,
)
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.utils.timestamps import now_naive_utc


@pytest_asyncio.fixture
async def protocol(async_session):
    """Build a tiny version-resolved definition with repeat and held-out stimulus."""
    service = CalibrationService(async_session)
    program = Program(name="Diagnostic baseline", version="test-1")
    async_session.add(program)
    for index in range(3):
        async_session.add(
            Fragrance(
                id=f"secret-version-{index}",
                name=f"Secret Fragrance {index}",
                brand="Secret House",
                concentration="EDT",
                gender_target="unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="manual",
            )
        )
    for index in range(2):
        async_session.add(Reviewer(id=f"reviewer-{index}", name=f"Evaluator {index}"))
    await async_session.flush()
    base = await service.add_member(
        program.id,
        MembershipInput(
            fragrance_id="secret-version-0",
            role="UNIVERSAL_BASELINE",
            identity_evidence="Verified exact EDT label",
        ),
    )
    repeat = await service.add_member(
        program.id,
        MembershipInput(
            fragrance_id="secret-version-0",
            role="HIDDEN_REPEAT",
            repeat_of_id=base.id,
            identity_evidence="Same verified decant as original",
        ),
    )
    holdout = await service.add_member(
        program.id,
        MembershipInput(
            fragrance_id="secret-version-1",
            role="HOLDOUT",
            identity_evidence="Verified exact EDT label",
        ),
    )
    return service, program, base, repeat, holdout


async def enroll(protocol, reviewer="reviewer-0"):
    """Activate and enroll an evaluator using an independently named recorder."""
    service, program, *_ = protocol
    program.status = "active"
    await service.db.flush()
    return await service.enroll(
        program.id,
        EnrollmentInput(
            reviewer_id=reviewer,
            recorder_usernames=["family-recorder"],
            session_size=2,
        ),
    )


async def answer_and_lock(service, presentation, stage="BLOTTER"):
    """Submit a real response before locking its stage."""
    response = await service.observe(
        presentation.id,
        ResponseInput(stage=stage, detected=True, intensity=3, liking=7),
        "family-recorder",
        admin=False,
    )
    await service.lock_stage(presentation.id, stage, "family-recorder", admin=False)
    return response


@pytest.mark.asyncio
async def test_repeat_references_canonical_version_and_evidence(protocol):
    service, program, base, repeat, _ = protocol
    assert (await service.program(program.id)).version == "test-1"
    assert repeat.fragrance_id == base.fragrance_id
    assert repeat.repeat_of_id == base.id
    assert repeat.selection["identity_evidence"] == "Same verified decant as original"
    with pytest.raises(HTTPException, match="Hidden repeat"):
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id="secret-version-2",
                role="HIDDEN_REPEAT",
                repeat_of_id=base.id,
                identity_evidence="Different version",
            ),
        )


@pytest.mark.asyncio
async def test_repeat_cannot_reference_another_program(protocol):
    service, _, base, *_ = protocol
    other = Program(name="Other", version="1")
    service.db.add(other)
    await service.db.flush()
    with pytest.raises(HTTPException, match="Hidden repeat"):
        await service.add_member(
            other.id,
            MembershipInput(
                fragrance_id=base.fragrance_id,
                role="HIDDEN_REPEAT",
                repeat_of_id=base.id,
                identity_evidence="Correct fragrance, wrong program",
            ),
        )


@pytest.mark.asyncio
async def test_holdout_cannot_also_be_training_member(protocol):
    service, program, base, _, holdout = protocol
    for fragrance_id, role in [
        (base.fragrance_id, "HOLDOUT"),
        (holdout.fragrance_id, "UNIVERSAL_BASELINE"),
    ]:
        with pytest.raises(HTTPException, match="Holdout"):
            await service.add_member(
                program.id,
                MembershipInput(
                    fragrance_id=fragrance_id,
                    role=role,
                    identity_evidence="Verified",
                ),
            )


@pytest.mark.asyncio
async def test_active_program_rejects_definition_edits(protocol):
    service, program, *_ = protocol
    await enroll(protocol)
    with pytest.raises(HTTPException, match="locked"):
        await service.add_member(
            program.id,
            MembershipInput(
                fragrance_id="secret-version-2",
                role="UNIVERSAL_BASELINE",
                identity_evidence="Verified",
            ),
        )


@pytest.mark.asyncio
async def test_enrollment_randomizes_blocks_and_uses_distinct_codes(protocol):
    service, *_ = protocol
    with patch(
        "fragrance_rater.services.calibration_service.secrets.SystemRandom.shuffle"
    ) as shuffle:
        first = await enroll(protocol)
        second = await enroll(protocol, "reviewer-1")
        assert shuffle.call_count >= 2
    first_rows = await service.presentations(first.id)
    second_rows = await service.presentations(second.id)
    assert len(first_rows) == len(second_rows) == 3
    assert len({row.blind_code for row in first_rows + second_rows}) == 6
    assert len({row.membership_id for row in first_rows}) == 3
    assert all(row.position >= 1 for row in first_rows + second_rows)
    with pytest.raises(HTTPException, match="already enrolled"):
        await enroll(protocol)


@pytest.mark.asyncio
async def test_participant_payload_has_no_identity_or_experimental_role(protocol):
    service, _, base, repeat, holdout = protocol
    enrollment = await enroll(protocol)
    payload = await service.participant_view(enrollment)
    serialized = json.dumps(payload)
    for hidden in [
        "Secret Fragrance",
        "Secret House",
        "secret-version-",
        base.id,
        repeat.id,
        holdout.id,
        "fragrance_id",
        "membership_id",
        "repeat_of_id",
        "HIDDEN_REPEAT",
        "HOLDOUT",
        "identity_evidence",
    ]:
        assert hidden not in serialized
    assert len(payload["presentations"]) == 3
    assert payload["revealed"] is False
    assert payload["reveal_eligible"] is False
    assert payload["reveal_blocker"] == "SKIN_PLAN"


@pytest.mark.parametrize(
    ("intensity", "liking"), [(None, None), (1, None), (0, 5), (0, 0)]
)
def test_non_detection_rejects_missing_intensity_and_neutral_liking(intensity, liking):
    with pytest.raises(ValidationError, match="Non-detection"):
        ResponseInput(
            stage="BLOTTER", detected=False, intensity=intensity, liking=liking
        )


@pytest.mark.asyncio
async def test_non_detection_and_unanswered_are_preserved_separately(protocol):
    service, *_ = protocol
    enrollment = await enroll(protocol)
    presentation = (await service.presentations(enrollment.id))[0]
    blank = await service.observe(
        presentation.id, ResponseInput(stage="BLOTTER"), "family-recorder", admin=False
    )
    assert blank.detected is None
    assert blank.intensity is None
    assert blank.liking is None
    with pytest.raises(HTTPException, match="detection response"):
        await service.lock_stage(
            presentation.id, "BLOTTER", "family-recorder", admin=False
        )
    response = await service.observe(
        presentation.id,
        ResponseInput(
            stage="BLOTTER",
            detected=False,
            intensity=0,
            perceived_notes=[],
        ),
        "family-recorder",
        admin=False,
    )
    assert response.detected is False
    assert response.intensity == 0
    assert response.liking is None
    assert response.responses["perceived_notes"] == []
    assert blank.responses["perceived_notes"] is None
    await service.lock_stage(presentation.id, "BLOTTER", "family-recorder", admin=False)


@pytest.mark.asyncio
async def test_stage_lock_preserves_original_and_allows_independent_skin_timepoints(
    protocol,
):
    service, *_ = protocol
    enrollment = await enroll(protocol)
    presentation = (await service.presentations(enrollment.id))[0]
    original = await answer_and_lock(service, presentation)
    with pytest.raises(HTTPException, match="locked"):
        await service.observe(
            presentation.id,
            ResponseInput(stage="BLOTTER", liking=2),
            "family-recorder",
            admin=False,
        )
    with pytest.raises(HTTPException, match="planned"):
        await service.observe(
            presentation.id, ResponseInput(stage="SKIN"), "family-recorder", admin=False
        )
    presentation.skin_reason = "Low confidence diagnostic control"
    await service.db.flush()
    for elapsed in [0, 45, 240]:
        await service.observe(
            presentation.id,
            ResponseInput(
                stage="SKIN",
                elapsed_minutes=elapsed,
                detected=True,
                intensity=2,
                freshness=4,
                density=4,
                would_wear=1,
                artistic_appreciation=9,
            ),
            "family-recorder",
            admin=False,
        )
    await service.lock_stage(presentation.id, "SKIN", "family-recorder", admin=False)
    with pytest.raises(HTTPException, match="locked"):
        await service.observe(
            presentation.id, ResponseInput(stage="SKIN"), "family-recorder", admin=False
        )
    await service.db.refresh(original)
    assert original.liking == 7
    assert original.phase == "PRE_REVEAL"
    rows = list(
        await service.db.scalars(
            select(Observation).where(Observation.presentation_id == presentation.id)
        )
    )
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_reveal_waits_for_repeat_and_finalized_locked_skin_plan(protocol):
    service, _, base, repeat, holdout = protocol
    enrollment = await enroll(protocol)
    presentations = {
        row.membership_id: row for row in await service.presentations(enrollment.id)
    }
    await answer_and_lock(service, presentations[base.id])
    pending_plan = await service.participant_view(enrollment)
    assert pending_plan["reveal_blocker"] == "SKIN_PLAN"
    with pytest.raises(HTTPException, match="Finalize"):
        await service.reveal(enrollment.id, "family-recorder", admin=False)
    enrollment.skin_plan_locked_at = now_naive_utc()
    await service.db.flush()
    pending_blotter = await service.participant_view(enrollment)
    assert pending_blotter["reveal_blocker"] == "BLOTTER"
    with pytest.raises(HTTPException, match="baseline and repeat"):
        await service.reveal(enrollment.id, "family-recorder", admin=False)
    await answer_and_lock(service, presentations[repeat.id])
    presentations[base.id].skin_reason = "Ambiguous opening"
    await service.db.flush()
    with pytest.raises(HTTPException, match="skin tests"):
        await service.reveal(enrollment.id, "family-recorder", admin=False)
    pending_skin = await service.participant_view(enrollment)
    assert pending_skin["reveal_blocker"] == "SKIN"
    await answer_and_lock(service, presentations[base.id], "SKIN")
    eligible = await service.participant_view(enrollment)
    assert eligible["reveal_eligible"] is True
    assert eligible["reveal_blocker"] is None
    await service.reveal(enrollment.id, "family-recorder", admin=False)
    assert enrollment.revealed_at is not None
    payload = await service.participant_view(enrollment)
    visible = {row["id"]: row for row in payload["presentations"]}
    assert (
        visible[presentations[base.id].id]["identity"]["fragrance_id"]
        == base.fragrance_id
    )
    assert "identity" not in visible[presentations[holdout.id].id]


@pytest.mark.asyncio
async def test_post_reveal_is_separate_and_cannot_rewrite_blind_response(protocol):
    service, _, _, _, holdout = protocol
    enrollment = await enroll(protocol)
    rows = await service.presentations(enrollment.id)
    presentation = next(row for row in rows if row.membership_id != holdout.id)
    with pytest.raises(HTTPException, match="not been revealed"):
        await service.observe(
            presentation.id,
            ResponseInput(stage="BLOTTER"),
            "family-recorder",
            admin=False,
            post_reveal=True,
        )
    for row in rows:
        if row.membership_id != holdout.id:
            await answer_and_lock(service, row)
    enrollment.skin_plan_locked_at = now_naive_utc()
    await service.db.flush()
    await service.reveal(enrollment.id, "family-recorder", admin=False)
    post = await service.observe(
        presentation.id,
        ResponseInput(
            stage="BLOTTER",
            liking=3,
            comments="Identity changed my impression",
        ),
        "family-recorder",
        admin=False,
        post_reveal=True,
    )
    with pytest.raises(HTTPException):
        await service.observe(
            presentation.id,
            ResponseInput(stage="BLOTTER", liking=2),
            "family-recorder",
            admin=False,
        )
    records = list(
        await service.db.scalars(
            select(Observation).where(Observation.presentation_id == presentation.id)
        )
    )
    assert len(records) == 2
    assert {(row.phase, row.liking) for row in records} == {
        ("PRE_REVEAL", 7),
        ("POST_REVEAL", 3),
    }
    assert post.recorded_by == "family-recorder"


@pytest.mark.asyncio
async def test_recorder_grants_are_independent_of_evaluator_identity(protocol):
    service, *_ = protocol
    enrollment = await enroll(protocol)
    assert (
        await service.enrollment(enrollment.id, "family-recorder", admin=False)
    ).reviewer_id == "reviewer-0"
    assert (
        await service.enrollment(enrollment.id, "experiment-admin", admin=True)
    ).id == enrollment.id
    for username in ["reviewer-0", "other-recorder"]:
        with pytest.raises(HTTPException) as error:
            await service.enrollment(enrollment.id, username, admin=False)
        assert error.value.status_code == 403
    presentation = (await service.presentations(enrollment.id))[0]
    with pytest.raises(HTTPException) as error:
        await service.observe(
            presentation.id,
            ResponseInput(stage="BLOTTER"),
            "other-recorder",
            admin=False,
        )
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_holdout_remains_blind_after_baseline_reveal_until_own_lock(protocol):
    service, _, _, _, holdout = protocol
    enrollment = await enroll(protocol)
    presentations = await service.presentations(enrollment.id)
    for presentation in presentations:
        if presentation.membership_id != holdout.id:
            await answer_and_lock(service, presentation)
    enrollment.skin_plan_locked_at = now_naive_utc()
    await service.db.flush()
    await service.reveal(enrollment.id, "family-recorder", admin=False)
    target = next(row for row in presentations if row.membership_id == holdout.id)
    with pytest.raises(HTTPException, match="not been revealed"):
        await service.observe(
            target.id,
            ResponseInput(stage="BLOTTER"),
            "family-recorder",
            admin=False,
            post_reveal=True,
        )
    blind = await answer_and_lock(service, target)
    assert blind.phase == "PRE_REVEAL"
    view = await service.participant_view(enrollment)
    row = next(row for row in view["presentations"] if row["id"] == target.id)
    assert row["identity"]["fragrance_id"] == holdout.fragrance_id
    with pytest.raises(HTTPException, match="ended at reveal"):
        await service.observe(
            target.id, ResponseInput(stage="BLOTTER"), "family-recorder", admin=False
        )
    informed = await service.observe(
        target.id,
        ResponseInput(stage="BLOTTER", comments="Recognized after reveal"),
        "family-recorder",
        admin=False,
        post_reveal=True,
    )
    assert informed.phase == "POST_REVEAL"
