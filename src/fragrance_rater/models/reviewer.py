"""Reviewer model for family member profiles.

This module defines the Reviewer model representing family members
who evaluate fragrances.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fragrance_rater.core.database import Base

if TYPE_CHECKING:
    from fragrance_rater.models.evaluation import Evaluation


class Reviewer(Base):
    """Family member profile for fragrance evaluations.

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        name (Mapped[str]): Reviewer's name (unique).
        created_at (Mapped[datetime]): Profile creation timestamp.
        deleted_at (Mapped[datetime | None]): Soft-delete timestamp; NULL
            means active. Set by DELETE routes instead of removing the row.
        evaluations (Mapped[list[Evaluation]]): Evaluations authored by this
            reviewer.
    """

    __tablename__ = "reviewers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    # Critical finding 2: soft-delete, mirroring Fragrance.deleted_at. Every
    # read query against this table must filter WHERE deleted_at IS NULL;
    # see reviewer_service.py.
    # #EDGE: data-integrity: `name` above keeps a bare UNIQUE constraint
    # (not scoped to deleted_at IS NULL), so re-seeding or re-creating a
    # reviewer with the same name as a soft-deleted one still raises the
    # existing UNIQUE violation. Not addressed in this pass; flagged in the
    # remediation report rather than silently decided.
    deleted_at: Mapped[datetime | None] = mapped_column(
        nullable=True, default=None, index=True
    )

    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="reviewer", cascade="all, delete-orphan"
    )
