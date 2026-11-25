"""Timing rules for facilitator transcription of paper sheets (F1).

In the facilitated format an evaluator writes on paper and the facilitator
enters the sheet afterward, so every time the application stores is a time the
paper says, typed some minutes or hours later. This module holds the rules that
keep such a transcription faithful: the instants must fit the sitting's own
window, the first smell cannot precede the spray, and a first smell later than
the spray-to-first-smell ceiling is recorded as a deviation rather than refused
or dropped. The exact times stay on the paper; the application stores the first
smell (``presented_at``), the column-finished time (``observed_at``) and whole
elapsed minutes.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException

from fragrance_rater.models.calibration import QualityFlag
from fragrance_rater.services.training_eligibility import TrainingEligibilityService
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.models.calibration import CalibrationSession, Presentation

# #ASSUME: timing-dependency: 2 minutes is the PROVISIONAL spray-to-first-smell
# ceiling of the F1 facilitated format (ADR-005 amendment, gates/f1.md). It was
# 5 minutes until the owner chose group sessions, where one blotter per sample
# is passed around the evaluators one at a time: the window runs from the
# blotter's spray to EACH evaluator's first smell, and when it would be
# exceeded the facilitator sprays a NEW blotter of the same sample (same blind
# code). Each evaluator's own sprayed_at/presented_at pair is checked against
# this ceiling, never the first evaluator's.
# #VERIFY: P6.3 tests whether six evaluators can each smell within 2 minutes
# and records the confirmed value in the F1 pre-exposure declaration; change
# this one constant (and the matching frontend constant) with it.
SPRAY_TO_SMELL_CEILING = timedelta(minutes=2)

# The flag raised when a first smell breaches the ceiling, and the rule that
# raises it, so an automatic flag names the version of the rule it applied.
CEILING_FLAG_CODE = "spray_to_smell_ceiling_exceeded"
CEILING_RULE_VERSION = "spray-to-smell-ceiling-v1"

# #ASSUME: timing-dependency: a paper sheet is transcribed within days, never
# weeks (all six sheets of a sitting are entered before the next sitting). An
# instant further back than this is a mistyped date, not a late transcription.
# #VERIFY: a recorder who genuinely transcribes later than this window enters
# the evidence without explicit times (the server's receipt time stands in) and
# raises a recorder_assistance flag explaining the delay.
TRANSCRIPTION_WINDOW = timedelta(days=7)


def check_instant(instant: datetime, session: CalibrationSession, label: str) -> None:
    """Refuse an explicit evidence time that cannot belong to this sitting.

    The future is refused by the schema validators (``to_naive_utc``). Here an
    instant must also not precede the moment the session existed (a session is
    created with its enrollment, so evidence from before that is a wrong date
    or a wrong enrollment) and must fall within ``TRANSCRIPTION_WINDOW`` of now.

    Args:
        instant (datetime): The naive-UTC time the caller supplied.
        session (CalibrationSession): The session the evidence belongs to.
        label (str): What the time is, for the error message.

    Raises:
        HTTPException: 422 when the time is outside the allowed window.
    """
    if instant < session.created_at:
        message = f"{label} is before this session existed"
        raise HTTPException(status_code=422, detail=message)
    if instant < now_naive_utc() - TRANSCRIPTION_WINDOW:
        days = TRANSCRIPTION_WINDOW.days
        message = f"{label} is more than {days} days ago; check the date"
        raise HTTPException(status_code=422, detail=message)


def seconds_over_ceiling(sprayed_at: datetime, smelled_at: datetime) -> int:
    """Return whole seconds by which a first smell exceeded the ceiling.

    Args:
        sprayed_at (datetime): When the blotter was sprayed.
        smelled_at (datetime): When it was first smelled.

    Returns:
        int: Seconds past the ceiling; ``0`` when within it.
    """
    gap = smelled_at - sprayed_at
    return max(0, math.ceil((gap - SPRAY_TO_SMELL_CEILING).total_seconds()))


def whole_minutes_between(start: datetime, end: datetime) -> int:
    """Return completed whole minutes from ``start`` to ``end`` (floor).

    Args:
        start (datetime): Spray time.
        end (datetime): Column-finished time; not before ``start``.

    Returns:
        int: Whole minutes elapsed.
    """
    return int((end - start).total_seconds() // 60)


async def raise_ceiling_flag(
    db: AsyncSession,
    presentation: Presentation,
    *,
    sprayed_at: datetime,
    smelled_at: datetime,
    actor: str,
) -> QualityFlag:
    """Record a first smell past the ceiling as an automatic deviation flag.

    The exposure itself is kept; the flag describes what happened and never
    removes or rewrites the evidence (capture assessment 13.3). It is raised in
    the same transaction as the exposure, so a breach cannot be dropped by a
    later step failing.

    Args:
        db (AsyncSession): The open session; the caller commits.
        presentation (Presentation): The sample that was first smelled late.
        sprayed_at (datetime): Spray time from the paper.
        smelled_at (datetime): First-smell time from the paper.
        actor (str): Who was at the keyboard.

    Returns:
        QualityFlag: The flushed, raised flag.
    """
    gap_seconds = int((smelled_at - sprayed_at).total_seconds())
    ceiling_seconds = int(SPRAY_TO_SMELL_CEILING.total_seconds())
    flag = QualityFlag(
        presentation_id=presentation.id,
        action="raised",
        code=CEILING_FLAG_CODE,
        severity="minor",
        source="automatic_validation",
        disposition="review",
        rule_version=CEILING_RULE_VERSION,
        explanation=(
            f"First smelled {gap_seconds} s after the spray, over the "
            f"provisional {ceiling_seconds} s ceiling "
            f"(by {seconds_over_ceiling(sprayed_at, smelled_at)} s)."
        ),
        occurred_at=smelled_at,
        recorded_by=actor,
    )
    db.add(flag)
    await db.flush()
    await TrainingEligibilityService(db).flag_raised(flag, actor=actor)
    await db.flush()
    return flag
