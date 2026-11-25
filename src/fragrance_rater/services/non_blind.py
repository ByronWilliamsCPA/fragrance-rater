"""Which evidence comes from an evaluator who is not blind (F1 mapping holder).

``docs/planning/gates/f1.md`` and the ADR-009 2026-09-21 amendment: the
evaluator who also holds the blind-to-identity mapping cannot be made blind by
software. Their rows carry a ``non_blind`` quality flag, which keeps them out of
blind-baseline model training but leaves them in evaluation (per-evaluator
metrics, and the pooled repeat benchmark reported both with and without them).

This module is the one place that answers "is this flag, enrollment, or
evaluator non-blind". A ``non_blind`` flag counts while it is ``raised`` and has
not been closed as ``invalidated`` (raised in error). A ``resolved`` closing row
does not lift it: resolving records a disposition for the flagged evidence, it
does not make the evaluator blind.

It reuses ``calibration_quality_flags``; no new table or column exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import aliased

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Observation,
    Presentation,
    QualityFlag,
)

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.ext.asyncio import AsyncSession

NON_BLIND_CODE = "non_blind"


def active_non_blind_flag() -> ColumnElement[bool]:
    """Match a ``non_blind`` flag that was raised and not invalidated.

    Returns:
        ColumnElement[bool]: A condition over ``QualityFlag``.
    """
    closing = aliased(QualityFlag)
    return and_(
        QualityFlag.code == NON_BLIND_CODE,
        QualityFlag.action == "raised",
        ~exists().where(
            closing.supersedes_id == QualityFlag.id,
            closing.action == "invalidated",
        ),
    )


async def non_blind_enrollment_ids(db: AsyncSession) -> set[str]:
    """Return every enrollment with an active ``non_blind`` flag.

    A flag on the enrollment's session, any of its presentations, or any of
    their observations marks the whole enrollment.

    Args:
        db (AsyncSession): Database session.

    Returns:
        set[str]: Enrollment ids.
    """
    by_session = select(CalibrationSession.enrollment_id).join(
        QualityFlag, QualityFlag.session_id == CalibrationSession.id
    )
    by_presentation = (
        select(CalibrationSession.enrollment_id)
        .join(Presentation, Presentation.session_id == CalibrationSession.id)
        .join(QualityFlag, QualityFlag.presentation_id == Presentation.id)
    )
    by_observation = (
        select(CalibrationSession.enrollment_id)
        .join(Presentation, Presentation.session_id == CalibrationSession.id)
        .join(Observation, Observation.presentation_id == Presentation.id)
        .join(QualityFlag, QualityFlag.observation_id == Observation.id)
    )
    found: set[str] = set()
    for statement in (by_session, by_presentation, by_observation):
        found.update(await db.scalars(statement.where(active_non_blind_flag())))
    return found


async def non_blind_reviewer_ids(db: AsyncSession) -> set[str]:
    """Return every evaluator with at least one non-blind enrollment.

    Args:
        db (AsyncSession): Database session.

    Returns:
        set[str]: Reviewer ids.
    """
    enrollment_ids = await non_blind_enrollment_ids(db)
    if not enrollment_ids:
        return set()
    return set(
        await db.scalars(
            select(Enrollment.reviewer_id).where(Enrollment.id.in_(enrollment_ids))
        )
    )
