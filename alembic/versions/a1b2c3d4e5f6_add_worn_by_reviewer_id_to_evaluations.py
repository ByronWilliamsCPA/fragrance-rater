"""Add worn_by_reviewer_id to evaluations.

Revision ID: a1b2c3d4e5f6
Revises: f5c2d3e4a5b6
Create Date: 2026-09-12

ADR-011: adds an optional "worn by" subject reviewer to `Evaluation`, distinct
from both `reviewer_id` (whose opinion the rating is) and `recorded_by` (who
was logged in when it was submitted). NULL (the default, and every existing
row) means the rating is "on me" -- `reviewer_id` rated the fragrance as worn
by themselves, unchanged behavior. A non-NULL value means `reviewer_id` is
recording an "on others" opinion, e.g. one partner's reaction to how a
fragrance smells on the other.

This migration:
- adds a nullable `worn_by_reviewer_id` column to `evaluations`, with an
  index since recommendation_service.py and preference_history.py now filter
  on it to exclude these rows from affinity/training-manifest scoring
- adds a foreign key to `reviewers.id` with `ondelete="RESTRICT"`: a
  reviewer referenced only as the *subject* of someone else's rating must
  not silently take that rating down with them if ever hard-deleted (unlike
  `reviewer_id`'s own CASCADE, where deleting the rater does remove their
  ratings)

Application-layer validation (schemas/evaluation.py, api/evaluations.py)
rejects `worn_by_reviewer_id == reviewer_id` as a redundant, ambiguous way to
spell the default "on me" rating; this migration does not add a matching
database-level CHECK constraint, consistent with this project's existing
practice of enforcing cross-column business rules in the application layer
rather than in schema constraints.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f5c2d3e4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable worn_by_reviewer_id column, its FK, and its index."""
    op.add_column(
        "evaluations",
        sa.Column("worn_by_reviewer_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluations_worn_by_reviewer_id_reviewers",
        "evaluations",
        "reviewers",
        ["worn_by_reviewer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_evaluations_worn_by_reviewer_id",
        "evaluations",
        ["worn_by_reviewer_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the index, foreign key, and column, in that order."""
    op.drop_index("ix_evaluations_worn_by_reviewer_id", table_name="evaluations")
    op.drop_constraint(
        "fk_evaluations_worn_by_reviewer_id_reviewers",
        "evaluations",
        type_="foreignkey",
    )
    op.drop_column("evaluations", "worn_by_reviewer_id")
