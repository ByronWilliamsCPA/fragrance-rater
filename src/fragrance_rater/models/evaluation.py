"""Evaluation model for fragrance ratings.

This module defines the Evaluation model representing a reviewer's
rating of a fragrance.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, func
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
        worn_by_reviewer_id (Mapped[str | None]): The reviewer whose
            experience wearing the fragrance this rating is about, when
            that differs from `reviewer_id`. NULL means the rating is
            "on me" (`reviewer_id` rated it as worn by themselves), the
            existing and default behavior. A non-NULL value means
            `reviewer_id` is recording an "on others" opinion -- e.g. one
            partner's reaction to how a fragrance smells on the other --
            and must reference a different reviewer than `reviewer_id`.
            Captured as evidence only: per ADR-011, affinity/recommendation
            scoring for `reviewer_id` reads only rows where this is NULL.
        fragrance (Mapped[Fragrance]): Evaluated fragrance.
        reviewer (Mapped[Reviewer]): Reviewer who made the evaluation.
        worn_by_reviewer (Mapped[Reviewer | None]): Reviewer the fragrance
            was worn by, when this is an "on others" rating.
    """

    __tablename__ = "evaluations"
    __table_args__ = (
        # ADR-011: mirrors migration da7c14f4a129's DB-level CHECK, same
        # name, so a schema built by Base.metadata.create_all() (tests,
        # fresh dev databases) enforces the identical rule as one built by
        # running migrations against an existing database.
        CheckConstraint(
            "worn_by_reviewer_id IS NULL OR worn_by_reviewer_id != reviewer_id",
            name="ck_evaluations_worn_by_reviewer_not_self",
        ),
    )
    # Every ordinary encounter is retained, including repeated fragrance ratings.

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
    #
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

    # ADR-011: optional "worn by" subject reviewer, distinct from both
    # `reviewer_id` (whose opinion this is) and `recorded_by` (who typed it
    # in). RESTRICT rather than CASCADE: a reviewer referenced only as the
    # *subject* of someone else's rating must not silently take that
    # rating's evaluation row down with them if ever hard-deleted; the
    # rater's own opinion is still meaningful evidence on its own.
    worn_by_reviewer_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("reviewers.id", ondelete="RESTRICT"),
        nullable=True,
        default=None,
        index=True,
    )

    fragrance: Mapped[Fragrance] = relationship(back_populates="evaluations")
    reviewer: Mapped[Reviewer] = relationship(
        back_populates="evaluations", foreign_keys=[reviewer_id]
    )
    worn_by_reviewer: Mapped[Reviewer | None] = relationship(
        back_populates="worn_by_evaluations", foreign_keys=[worn_by_reviewer_id]
    )
