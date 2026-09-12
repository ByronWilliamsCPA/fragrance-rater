"""Reviewer model for family member profiles.

This module defines the Reviewer model representing family members
who evaluate fragrances.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Index, String, func, text
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
        worn_by_evaluations (Mapped[list[Evaluation]]): Evaluations authored
            by a *different* reviewer about a fragrance as worn by this
            reviewer (ADR-011's "on others" ratings, e.g. a partner's
            reaction). Distinct from `evaluations`, which is keyed on
            authorship (`reviewer_id`), not subject.
    """

    __tablename__ = "reviewers"
    # `uq_reviewer_name` is a partial unique index scoped to
    # `deleted_at IS NULL` rather than a plain UniqueConstraint (or the
    # `unique=True` column flag this replaced): see the resolved RAD note
    # on `deleted_at` below for why. `sqlite_where` mirrors
    # `postgresql_where` so the SQLite test database (built from this
    # metadata via `Base.metadata.create_all`, not the Alembic migration)
    # enforces the same scoped uniqueness as production.
    __table_args__ = (
        Index(
            "uq_reviewer_name",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    # Critical finding 2: soft-delete, mirroring Fragrance.deleted_at. Every
    # read query against this table must filter WHERE deleted_at IS NULL;
    # see reviewer_service.py.
    # Resolved: `name` above previously kept a bare UNIQUE constraint (via
    # unique=True, index=True), so re-seeding or re-creating a reviewer
    # with the same name as a soft-deleted one still raised a UNIQUE
    # violation against the deleted row forever. It is now a plain
    # (non-unique) index, with uniqueness enforced separately by the
    # partial `uq_reviewer_name` index above scoped to
    # `deleted_at IS NULL` (see migration 22eed1bf0509), so uniqueness is
    # enforced among live rows only.
    deleted_at: Mapped[datetime | None] = mapped_column(
        nullable=True, default=None, index=True
    )

    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="reviewer",
        foreign_keys="[Evaluation.reviewer_id]",
        cascade="all, delete-orphan",
    )
    # ADR-011: the reverse side of Evaluation.worn_by_reviewer. No cascade:
    # this reviewer is only the *subject* of these rows, not their owner,
    # so deleting this reviewer must not delete someone else's evaluation
    # (see the RESTRICT ondelete on Evaluation.worn_by_reviewer_id).
    worn_by_evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="worn_by_reviewer",
        foreign_keys="[Evaluation.worn_by_reviewer_id]",
    )
