"""house_submissions: staged fragrance house intake.

Revision ID: b7e3d91a4c2f
Revises: a3f8c1d9e2b7
Create Date: 2026-10-02

A new table. It does not alter the catalog or ``calibration_source_snapshots``;
it only references them: a submission is what a house said, held apart from
adopted evidence until a manager reviews it, and an adopted row points at the
catalog version and the evidence row its review produced (ADR-012, ADR-017).
The CHECK expressions must stay textually identical to ``HouseSubmission``
in ``src/fragrance_rater/models/house_intake.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e3d91a4c2f"
down_revision: str | Sequence[str] | None = "a3f8c1d9e2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "house_submissions"


def upgrade() -> None:
    """Create ``house_submissions``."""
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("house", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_by", sa.String(length=255), nullable=True),
        sa.Column("permission_state", sa.String(length=30), nullable=True),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("fragrance_id", sa.String(length=36), nullable=True),
        sa.Column("source_snapshot_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted')",
            name="ck_house_submissions_status",
        ),
        sa.CheckConstraint(
            "permission_state IS NULL OR permission_state IN ('retain_and_train', 'retain_for_qc_only')",
            name="ck_house_submissions_permission_state",
        ),
        sa.CheckConstraint(
            "status = 'draft' OR (submitted_at IS NOT NULL AND submitted_by IS NOT NULL AND permission_state IS NOT NULL)",
            name="ck_house_submissions_submitted_complete",
        ),
        sa.CheckConstraint(
            "review_status IS NULL OR review_status IN ('pending', 'adopted', 'declined', 'superseded')",
            name="ck_house_submissions_review_status",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND review_status IS NULL) OR (status = 'submitted' AND review_status IS NOT NULL)",
            name="ck_house_submissions_review_matches_status",
        ),
        sa.CheckConstraint(
            "review_status IS NULL OR review_status <> 'adopted' OR (fragrance_id IS NOT NULL AND source_snapshot_id IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_house_submissions_adopted_complete",
        ),
        sa.CheckConstraint(
            "review_status IS NULL OR review_status <> 'declined' OR (COALESCE(TRIM(review_note), '') <> '' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_house_submissions_declined_complete",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], [f"{_TABLE}.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"], ["fragrances.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["calibration_source_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supersedes_id"),
        sa.UniqueConstraint("source_snapshot_id"),
    )
    op.create_index("ix_house_submissions_house_status", _TABLE, ["house", "status"])
    op.create_index("ix_house_submissions_review_status", _TABLE, ["review_status"])
    op.create_index("ix_house_submissions_fragrance_id", _TABLE, ["fragrance_id"])


def downgrade() -> None:
    """Drop ``house_submissions``."""
    op.drop_index("ix_house_submissions_fragrance_id", table_name=_TABLE)
    op.drop_index("ix_house_submissions_review_status", table_name=_TABLE)
    op.drop_index("ix_house_submissions_house_status", table_name=_TABLE)
    op.drop_table(_TABLE)
