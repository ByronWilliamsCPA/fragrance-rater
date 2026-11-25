"""Which evidence came from a group-blotter session (F1 ``SHARED_GROUP`` programs).

In a ``SHARED_GROUP`` program the facilitator passes ONE physical blotter per
sample around the evaluators, so they share a sample's blind code and the
session order, and may smell it a few moments apart. The owner accepted that and
chose that the scores stay eligible for blind-baseline training: the marker is
FLAG ONLY. Every session of such a program carries an automatic
``group_shared_blotter`` quality flag so a reader can report results with and
without those sessions (``ml.reliability.pooled_reliability_group_blotter_both_ways``).

This module is the one place that names the code, defines which flag codes are
informational (never demote training eligibility), and answers "is this
enrollment a group-blotter enrollment". It reuses ``calibration_quality_flags``;
the flag follows the usual append-only lifecycle, and a ``raised`` flag counts
until it is closed as ``invalidated`` (raised in error).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import aliased

from fragrance_rater.models.calibration import (
    CalibrationSession,
    QualityFlag,
)

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.ext.asyncio import AsyncSession

GROUP_SHARED_BLOTTER_CODE = "group_shared_blotter"
GROUP_SHARED_BLOTTER_RULE_VERSION = "group-shared-blotter-v1"

# #CRITICAL: data-integrity: the owner decided group-blotter scores stay
# trainable, so these flag codes describe evidence without ever moving it out
# of ``v_training_rows``. Every eligibility rule that reacts to a quality flag
# (raising, open-flag lookup, closing, pending resolutions) must skip them.
# #VERIFY: tests/unit/test_api/test_group_blotter_routes.py fails if an
# informational flag demotes, holds, or releases a row.
INFORMATIONAL_FLAG_CODES: frozenset[str] = frozenset({GROUP_SHARED_BLOTTER_CODE})


def active_group_blotter_flag() -> ColumnElement[bool]:
    """Match a ``group_shared_blotter`` flag that was raised and not invalidated.

    Returns:
        ColumnElement[bool]: A condition over ``QualityFlag``.
    """
    closing = aliased(QualityFlag)
    return and_(
        QualityFlag.code == GROUP_SHARED_BLOTTER_CODE,
        QualityFlag.action == "raised",
        ~exists().where(
            closing.supersedes_id == QualityFlag.id,
            closing.action == "invalidated",
        ),
    )


async def group_blotter_enrollment_ids(db: AsyncSession) -> set[str]:
    """Return every enrollment with an active ``group_shared_blotter`` flag.

    The flag is raised on each session at enrollment, so a session-level flag
    marks the whole enrollment.

    Args:
        db (AsyncSession): Database session.

    Returns:
        set[str]: Enrollment ids.
    """
    statement = (
        select(CalibrationSession.enrollment_id)
        .join(QualityFlag, QualityFlag.session_id == CalibrationSession.id)
        .where(active_group_blotter_flag())
    )
    return set(await db.scalars(statement))
