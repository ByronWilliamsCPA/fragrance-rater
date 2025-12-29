"""Evaluation model for fragrance ratings.

This module defines the Evaluation model representing a reviewer's
rating of a fragrance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fragrance_rater.core.database import Base

if TYPE_CHECKING:
    from datetime import datetime

    from fragrance_rater.models.fragrance import Fragrance
    from fragrance_rater.models.reviewer import Reviewer


class Evaluation(Base):
    """A reviewer's rating and notes for a fragrance.

    Attributes:
        id: Unique identifier (UUID).
        fragrance_id: Foreign key to the fragrance.
        reviewer_id: Foreign key to the reviewer.
        rating: Overall rating (1-5 scale).
        notes: Free-form observations about the fragrance.
        longevity_rating: Optional longevity score (1-5).
        sillage_rating: Optional sillage/projection score (1-5).
        evaluated_at: When the evaluation was made.
        created_at: Record creation timestamp.
    """

    __tablename__ = "evaluations"

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

    fragrance: Mapped[Fragrance] = relationship(back_populates="evaluations")
    reviewer: Mapped[Reviewer] = relationship(back_populates="evaluations")
