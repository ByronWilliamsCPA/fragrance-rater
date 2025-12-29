"""Initial schema for Fragrance Rater.

Revision ID: 001
Revises:
Create Date: 2025-12-29

Creates tables:
- fragrances: Core fragrance entity
- notes: Individual scent components
- fragrance_notes: Junction table with note position
- fragrance_accords: Accord types with intensity
- reviewers: Family member profiles
- evaluations: Fragrance ratings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial database schema."""
    # Fragrances table
    op.create_table(
        "fragrances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("brand", sa.String(255), nullable=False, index=True),
        sa.Column("concentration", sa.String(50), nullable=False),
        sa.Column("launch_year", sa.Integer, nullable=True),
        sa.Column("gender_target", sa.String(20), nullable=False),
        sa.Column("primary_family", sa.String(50), nullable=False),
        sa.Column("subfamily", sa.String(50), nullable=False),
        sa.Column("intensity", sa.String(20), nullable=True),
        sa.Column("data_source", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Notes table
    op.create_table(
        "notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("subcategory", sa.String(50), nullable=True),
    )

    # Fragrance-Notes junction table
    op.create_table(
        "fragrance_notes",
        sa.Column(
            "fragrance_id",
            sa.String(36),
            sa.ForeignKey("fragrances.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "note_id",
            sa.String(36),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.String(10), nullable=False),
    )

    # Fragrance accords table
    op.create_table(
        "fragrance_accords",
        sa.Column(
            "fragrance_id",
            sa.String(36),
            sa.ForeignKey("fragrances.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("accord_type", sa.String(50), primary_key=True),
        sa.Column("intensity", sa.Float, nullable=False),
    )

    # Reviewers table
    op.create_table(
        "reviewers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Evaluations table
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "fragrance_id",
            sa.String(36),
            sa.ForeignKey("fragrances.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reviewer_id",
            sa.String(36),
            sa.ForeignKey("reviewers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("longevity_rating", sa.Integer, nullable=True),
        sa.Column("sillage_rating", sa.Integer, nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create additional indexes for recommendation performance
    op.create_index(
        "idx_evaluations_reviewer_fragrance",
        "evaluations",
        ["reviewer_id", "fragrance_id"],
    )
    op.create_index(
        "idx_fragrance_notes_fragrance",
        "fragrance_notes",
        ["fragrance_id"],
    )
    op.create_index(
        "idx_fragrance_notes_note",
        "fragrance_notes",
        ["note_id"],
    )
    op.create_index(
        "idx_fragrance_accords_fragrance",
        "fragrance_accords",
        ["fragrance_id"],
    )
    op.create_index(
        "idx_fragrances_name_brand",
        "fragrances",
        ["name", "brand"],
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index("idx_fragrances_name_brand", table_name="fragrances")
    op.drop_index("idx_fragrance_accords_fragrance", table_name="fragrance_accords")
    op.drop_index("idx_fragrance_notes_note", table_name="fragrance_notes")
    op.drop_index("idx_fragrance_notes_fragrance", table_name="fragrance_notes")
    op.drop_index("idx_evaluations_reviewer_fragrance", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_table("reviewers")
    op.drop_table("fragrance_accords")
    op.drop_table("fragrance_notes")
    op.drop_table("notes")
    op.drop_table("fragrances")
