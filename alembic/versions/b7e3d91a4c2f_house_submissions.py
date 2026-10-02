"""house_submissions: staged fragrance house intake.

Revision ID: b7e3d91a4c2f
Revises: a3f8c1d9e2b7
Create Date: 2026-10-02

A new, self-contained table. It does not touch the catalog or
``calibration_source_snapshots``: a submission is what a house said, held
apart from adopted evidence until a manager reviews it (ADR-012, ADR-017).
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
        sa.ForeignKeyConstraint(
            ["supersedes_id"], [f"{_TABLE}.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supersedes_id"),
    )
    op.create_index("ix_house_submissions_house_status", _TABLE, ["house", "status"])


def downgrade() -> None:
    """Drop ``house_submissions``."""
    op.drop_index("ix_house_submissions_house_status", table_name=_TABLE)
    op.drop_table(_TABLE)
