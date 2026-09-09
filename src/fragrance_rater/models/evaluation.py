"""Evaluation model for fragrance ratings.

This module defines the Evaluation model representing a reviewer's
rating of a fragrance.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fragrance_rater.core.database import Base

if TYPE_CHECKING:
    from fragrance_rater.models.fragrance import Fragrance
    from fragrance_rater.models.reviewer import Reviewer


class Evaluation(Base):
    """A reviewer's rating and notes for a fragrance.

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        fragrance_id (Mapped[str]): Foreign key to the fragrance.
        reviewer_id (Mapped[str]): Foreign key to the reviewer.
        rating (Mapped[int]): Overall rating (1-5 scale).
        notes (Mapped[str | None]): Free-form observations about the fragrance.
        longevity_rating (Mapped[int | None]): Optional longevity score (1-5).
        sillage_rating (Mapped[int | None]): Optional sillage/projection score
            (1-5).
        evaluated_at (Mapped[datetime]): When the evaluation was made.
        created_at (Mapped[datetime]): Record creation timestamp.
        deleted_at (Mapped[datetime | None]): Soft-delete timestamp; NULL
            means active. Set by DELETE routes instead of removing the row.
        recorded_by (Mapped[str | None]): Authentik username of whoever was
            logged in when this evaluation was submitted. Independent of
            and NOT a replacement for `reviewer_id`: `reviewer_id` is whose
            palate the rating reflects, `recorded_by` is who was at the
            keyboard. One logged-in person often records ratings for
            several reviewers in a single group-smelling session, so these
            two fields are never constrained against each other.
        fragrance (Mapped[Fragrance]): Evaluated fragrance.
        reviewer (Mapped[Reviewer]): Reviewer who made the evaluation.
    """

    __tablename__ = "evaluations"
    # Major finding 8, product decision (not silently assumed, see report):
    # the legacy scaffold this branch replaced allowed repeat evaluations of
    # the same fragrance by the same reviewer over time; that was never an
    # explicit product decision for this app. Defaulting to a hard UNIQUE
    # here matches what the existing (racy) application-level check in
    # api/evaluations.py already assumes: one evaluation per reviewer per
    # fragrance, ever. Revisit if "re-rate over time" turns out to be wanted.
    __table_args__ = (
        UniqueConstraint(
            "reviewer_id", "fragrance_id", name="uq_evaluation_reviewer_fragrance"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    fragrance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fragrances.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviewers.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional structured feedback
    longevity_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sillage_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    evaluated_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )

    # Critical finding 2: soft-delete, mirroring Fragrance.deleted_at. Every
    # read query against this table must filter WHERE deleted_at IS NULL;
    # see evaluation_service.py and recommendation_service.py.
    deleted_at: Mapped[datetime | None] = mapped_column(
        nullable=True, default=None, index=True
    )
    # Critical finding 2: audit trail for who was logged in at write time,
    # populated from the Authentik forward-auth identity dependency
    # (core/auth.py). Nullable because Authentik isn't wired in local
    # dev/tests/seeded data. Deliberately NOT a foreign key to any identity
    # table and deliberately NOT used to constrain reviewer_id selection;
    # the user explicitly corrected an earlier design idea that would have
    # mapped Authentik identity 1:1 onto reviewer_id.
    recorded_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )

    fragrance: Mapped[Fragrance] = relationship(back_populates="evaluations")
    reviewer: Mapped[Reviewer] = relationship(back_populates="evaluations")
