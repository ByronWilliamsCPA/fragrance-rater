"""Catalog alignment with the house intake format: line, market status, GTINs.

Revision ID: c5a9e2d7f1b4
Revises: b7e3d91a4c2f
Create Date: 2026-10-02

Gives three facts a house can confirm a home in the catalog, so a reviewed
submission can record them instead of leaving them only inside evidence
payloads:

- ``fragrances.line``: collection or line (ADR-012 "brand/line attribution").
- ``fragrances.market_status``: whether the house still sells the version.
- ``fragrance_gtins``: barcodes, one row per SKU, each citing the
  ``calibration_source_snapshots`` row that established it (ADR-006).

No existing row is modified: both columns are nullable with no default, so
NULL means "not known", exactly as before. The CHECK and the table's
constraints must stay textually identical to ``models/fragrance.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5a9e2d7f1b4"
down_revision: str | Sequence[str] | None = "b7e3d91a4c2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MARKET_STATUS_CHECK = (
    "market_status IS NULL OR market_status IN ('in_production', "
    "'limited_edition', 'upcoming', 'discontinued')"
)


def upgrade() -> None:
    """Add catalog columns and the GTIN table."""
    with op.batch_alter_table("fragrances") as batch_op:
        batch_op.add_column(sa.Column("line", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("market_status", sa.String(length=20), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_fragrances_market_status", _MARKET_STATUS_CHECK
        )
    op.create_table(
        "fragrance_gtins",
        sa.Column("gtin", sa.String(length=14), nullable=False),
        sa.Column("fragrance_id", sa.String(length=36), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("length(gtin) = 14", name="ck_fragrance_gtins_length"),
        sa.ForeignKeyConstraint(
            ["fragrance_id"], ["fragrances.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["calibration_source_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("gtin"),
    )
    op.create_index(
        "ix_fragrance_gtins_fragrance_id", "fragrance_gtins", ["fragrance_id"]
    )
    op.create_index(
        "ix_fragrance_gtins_source_snapshot_id",
        "fragrance_gtins",
        ["source_snapshot_id"],
    )


def downgrade() -> None:
    """Drop the GTIN table and catalog columns."""
    op.drop_index("ix_fragrance_gtins_source_snapshot_id", table_name="fragrance_gtins")
    op.drop_index("ix_fragrance_gtins_fragrance_id", table_name="fragrance_gtins")
    op.drop_table("fragrance_gtins")
    with op.batch_alter_table("fragrances") as batch_op:
        batch_op.drop_constraint("ck_fragrances_market_status", type_="check")
        batch_op.drop_column("market_status")
        batch_op.drop_column("line")
