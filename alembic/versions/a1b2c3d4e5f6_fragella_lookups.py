"""Add fragella_lookups: a reference-only lookup log, not adopted source evidence.

Revision ID: a1b2c3d4e5f6
Revises: f5c2d3e4a5b6
"""

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f5c2d3e4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the fragella_lookups table; no existing table is touched."""
    op.create_table(
        "fragella_lookups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("fragrance_id", sa.String(length=36), nullable=False),
        sa.Column("queried_at", sa.DateTime(), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fragrance_id"], ["fragrances.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fragella_lookups_fragrance_id",
        "fragella_lookups",
        ["fragrance_id"],
    )


def downgrade() -> None:
    """Drop fragella_lookups; it holds no data other tables depend on."""
    op.drop_index("ix_fragella_lookups_fragrance_id", table_name="fragella_lookups")
    op.drop_table("fragella_lookups")
