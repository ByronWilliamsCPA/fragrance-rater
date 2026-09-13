"""Add fragella_lookups: a reference-only lookup log, not adopted source evidence.

Revision ID: 2c341c369192
Revises: 72fe56efd128

Chains after 72fe56efd128 rather than directly after f5c2d3e4a5b6, purely
to keep migration history a single linear head: this table addition has
no actual dependency on either of the two migrations ahead of it. This
revision originally shared the literal id `a1b2c3d4e5f6` with 9ded7f54996c
(ml_prediction_snapshots) - an unrelated collision between two PRs merged
independently, since neither branch could see the other's new file at
review time. Renamed here to resolve it; no deployed environment had
migrated to the original id.
"""

import sqlalchemy as sa

from alembic import op

revision = "2c341c369192"
down_revision = "72fe56efd128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the fragella_lookups table.

    No existing column or row is modified, but the new `fragrance_id`
    foreign key's `ondelete="RESTRICT"` does change `fragrances`' delete
    behavior: deleting a fragrance that any fragella_lookups row still
    references will now fail with a foreign key violation instead of
    succeeding.
    """
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
        sa.CheckConstraint("status IN ('error', 'success')"),
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
