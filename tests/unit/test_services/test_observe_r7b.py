"""``CalibrationService.observe`` persists the R7b capture fields (R7b PR 1a)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    FitChoice,
    Membership,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import ResponseInput
from fragrance_rater.services.calibration_service import CalibrationService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _presentation(
    session: AsyncSession, *, skin_planned: bool = True
) -> Presentation:
    program = Program(name="observe", version="1", status="active")
    reviewer = Reviewer(name="observer")
    fragrance = Fragrance(
        name="Observed",
        brand="House",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="unit",
    )
    session.add_all([program, reviewer, fragrance])
    await session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    session.add(enrollment)
    await session.flush()
    calibration = CalibrationSession(enrollment_id=enrollment.id)
    member = Membership(
        program_id=program.id, fragrance_id=fragrance.id, role="UNIVERSAL_BASELINE"
    )
    session.add_all([calibration, member])
    await session.flush()
    presentation = Presentation(
        session_id=calibration.id,
        membership_id=member.id,
        blind_code="OBS-1",
        position=1,
        skin_reason="planned" if skin_planned else None,
    )
    session.add(presentation)
    await session.flush()
    return presentation


async def _observe(
    session: AsyncSession, presentation: Presentation, **fields: object
) -> Observation:
    stage = fields.pop("stage", "BLOTTER")
    return await CalibrationService(session).observe(
        presentation.id,
        ResponseInput(stage=stage, **fields),  # type: ignore[arg-type]
        "rec",
        admin=False,
    )


async def test_the_capture_fields_are_stored(async_session: AsyncSession) -> None:
    presentation = await _presentation(async_session)
    observed = datetime(2026, 10, 30, 14, 5, 0)  # noqa: DTZ001

    observation = await _observe(
        async_session,
        presentation,
        stage="SKIN",
        detected=True,
        intensity=3,
        liking=8,
        would_buy=6,
        observed_at=observed,
        response_status="completed",
        recognition="vaguely_familiar",
        owned_or_worn="no",
        scrubbed_off=True,
        time_to_scrub_minutes=45,
        last_detected_elapsed_min=240,
        first_not_detected_elapsed_min=480,
    )

    assert observation.observed_at == observed
    assert observation.response_status == "completed"
    assert observation.recognition == "vaguely_familiar"
    assert observation.owned_or_worn == "no"
    assert observation.scrubbed_off is True
    assert observation.time_to_scrub_minutes == 45
    assert observation.last_detected_elapsed_min == 240
    assert observation.first_not_detected_elapsed_min == 480
    assert observation.would_buy == 6


async def test_observed_at_defaults_to_receipt_time(
    async_session: AsyncSession,
) -> None:
    presentation = await _presentation(async_session)
    before = datetime.now(UTC).replace(tzinfo=None)  # server stamps are naive UTC

    observation = await _observe(
        async_session, presentation, detected=True, intensity=2
    )

    assert observation.observed_at is not None
    assert abs(observation.observed_at - before) < timedelta(minutes=5)


async def test_a_response_without_r7b_fields_still_stores_nulls(
    async_session: AsyncSession,
) -> None:
    presentation = await _presentation(async_session)

    observation = await _observe(
        async_session, presentation, detected=True, intensity=2
    )

    for column in (
        "response_status",
        "recognition",
        "owned_or_worn",
        "scrubbed_off",
        "time_to_scrub_minutes",
        "last_detected_elapsed_min",
        "first_not_detected_elapsed_min",
    ):
        assert getattr(observation, column) is None, column


async def test_each_ticked_option_becomes_one_fit_choice_row(
    async_session: AsyncSession,
) -> None:
    presentation = await _presentation(async_session)

    observation = await _observe(
        async_session,
        presentation,
        stage="SKIN",
        detected=True,
        intensity=3,
        season_fit=["spring", "fall"],
        setting_fit=["home", "social_outing", "formal_event"],
    )

    rows = (
        (
            await async_session.execute(
                select(FitChoice).where(FitChoice.observation_id == observation.id)
            )
        )
        .scalars()
        .all()
    )
    assert sorted((r.dimension, r.code) for r in rows) == [
        ("season", "fall"),
        ("season", "spring"),
        ("setting", "formal_event"),
        ("setting", "home"),
        ("setting", "social_outing"),
    ]


async def test_an_observation_without_fit_answers_has_no_fit_rows(
    async_session: AsyncSession,
) -> None:
    presentation = await _presentation(async_session)
    await _observe(
        async_session, presentation, stage="SKIN", detected=True, intensity=1
    )

    rows = (await async_session.execute(select(FitChoice))).scalars().all()

    assert rows == []


async def test_a_none_answer_is_stored_as_a_row_not_as_silence(
    async_session: AsyncSession,
) -> None:
    """ "None of these" is an answer; no row at all means the question was not asked."""
    presentation = await _presentation(async_session)

    await _observe(
        async_session,
        presentation,
        stage="SKIN",
        detected=True,
        intensity=1,
        season_fit=["none"],
        setting_fit=["cannot_judge"],
    )

    rows = (await async_session.execute(select(FitChoice))).scalars().all()
    assert sorted((r.dimension, r.code) for r in rows) == [
        ("season", "none"),
        ("setting", "cannot_judge"),
    ]


async def test_two_observations_keep_their_own_fit_choices(
    async_session: AsyncSession,
) -> None:
    """Observations are append-only; each timepoint's answers stay with it."""
    presentation = await _presentation(async_session)
    first = await _observe(
        async_session,
        presentation,
        stage="SKIN",
        detected=True,
        intensity=3,
        season_fit=["summer"],
    )
    second = await _observe(
        async_session,
        presentation,
        stage="SKIN",
        elapsed_minutes=240,
        detected=True,
        intensity=2,
        season_fit=["winter"],
    )

    rows = (await async_session.execute(select(FitChoice))).scalars().all()

    by_observation = {(r.observation_id, r.code) for r in rows}
    assert by_observation == {(first.id, "summer"), (second.id, "winter")}


async def test_skin_must_still_be_planned_before_any_skin_response(
    async_session: AsyncSession,
) -> None:
    """The R7b fields do not weaken the existing disclosure and planning rules."""
    presentation = await _presentation(async_session, skin_planned=False)

    with pytest.raises(HTTPException) as caught:
        await _observe(
            async_session,
            presentation,
            stage="SKIN",
            detected=True,
            intensity=1,
            season_fit=["spring"],
        )

    assert caught.value.status_code == 409
    assert (await async_session.execute(select(FitChoice))).scalars().all() == []
