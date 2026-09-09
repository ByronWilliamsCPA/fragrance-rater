"""Add soft-delete deleted_at and evaluation recorded_by columns.

Revision ID: d3c65c9cf212
Revises: 5d2e7c9f9c92
Create Date: 2026-09-09

Critical finding 2: DELETE routes on fragrances, evaluations, and reviewers
performed a real DELETE with no audit trail. A hard delete of a Fragrance
also risked triggering the cascade="all, delete-orphan" relationship to its
FragranceNote/FragranceAccord/Evaluation rows. Soft-delete sidesteps both
problems: DELETE routes now set `deleted_at` instead of removing the row, so
no cascade ever fires and every mutation is logged (see
core/auth.py, utils/logging.py's log_audit_event).

This migration:
- adds a nullable `deleted_at` timestamp column (NULL = active) to
  `fragrances`, `evaluations`, and `reviewers`, each with an index since
  every read query against these tables now filters on it
- adds a nullable `recorded_by` column to `evaluations`, populated from the
  Authentik forward-auth identity at write time (core/auth.py). This is
  independent of and NOT a replacement for `reviewer_id`: `recorded_by` is
  who was logged in when the rating was submitted, `reviewer_id` is whose
  palate the rating reflects. One logged-in person often records ratings
  for several reviewers in one group-smelling session.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3c65c9cf212"
down_revision: str | Sequence[str] | None = "5d2e7c9f9c92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add deleted_at to fragrances/evaluations/reviewers, recorded_by to evaluations."""
    op.add_column("fragrances", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("evaluations", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("reviewers", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column(
        "evaluations", sa.Column("recorded_by", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "ix_fragrances_deleted_at", "fragrances", ["deleted_at"], unique=False
    )
    op.create_index(
        "ix_evaluations_deleted_at", "evaluations", ["deleted_at"], unique=False
    )
    op.create_index(
        "ix_reviewers_deleted_at", "reviewers", ["deleted_at"], unique=False
    )


def downgrade() -> None:
    """Drop recorded_by, deleted_at, and their indexes."""
    op.drop_index("ix_reviewers_deleted_at", table_name="reviewers")
    op.drop_index("ix_evaluations_deleted_at", table_name="evaluations")
    op.drop_index("ix_fragrances_deleted_at", table_name="fragrances")
    op.drop_column("evaluations", "recorded_by")
    op.drop_column("reviewers", "deleted_at")
    op.drop_column("evaluations", "deleted_at")
    op.drop_column("fragrances", "deleted_at")
