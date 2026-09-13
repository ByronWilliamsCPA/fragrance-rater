"""Add worn_by_reviewer_id to evaluations.

Revision ID: da7c14f4a129
Revises: 2c341c369192
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
- adds a CHECK constraint enforcing `worn_by_reviewer_id != reviewer_id`,
  matching this project's existing practice of also enforcing cross-column
  rules at the schema level (see e.g. e4b1c2d3f4a5's and c731b42e9a01's own
  CHECK constraints), not only in the application layer. The application
  layer (schemas/evaluation.py, api/evaluations.py) rejects this same
  redundant, ambiguous "on others" spelling of the default "on me" rating
  first, with a clear error message; the constraint below is the
  defense-in-depth backstop for any write path that bypasses that layer.

Uses `op.batch_alter_table` rather than bare `op.add_column`/
`op.create_foreign_key`/`op.create_check_constraint`: SQLite (used by this
migration's own integration test) cannot ALTER an already-created table to
add a foreign key or CHECK constraint directly. Batch mode recreates the
table under the hood on SQLite to work around that, and is a transparent
passthrough to plain `ALTER TABLE` statements on PostgreSQL, so production
behavior is unchanged. See 9ded7f54996c_ml_prediction_snapshots.py's
`_add_range_constraints` for the same pattern.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "da7c14f4a129"
down_revision: str | Sequence[str] | None = "2c341c369192"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable worn_by_reviewer_id column, its FK, index, and CHECK."""
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.add_column(
            sa.Column("worn_by_reviewer_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_evaluations_worn_by_reviewer_id_reviewers",
            "reviewers",
            ["worn_by_reviewer_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_evaluations_worn_by_reviewer_id",
            ["worn_by_reviewer_id"],
            unique=False,
        )
        batch_op.create_check_constraint(
            "ck_evaluations_worn_by_reviewer_not_self",
            "worn_by_reviewer_id IS NULL OR worn_by_reviewer_id != reviewer_id",
        )


def downgrade() -> None:
    """Drop the CHECK constraint, index, foreign key, and column, in that order."""
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_constraint(
            "ck_evaluations_worn_by_reviewer_not_self", type_="check"
        )
        batch_op.drop_index("ix_evaluations_worn_by_reviewer_id")
        batch_op.drop_constraint(
            "fk_evaluations_worn_by_reviewer_id_reviewers", type_="foreignkey"
        )
        batch_op.drop_column("worn_by_reviewer_id")
