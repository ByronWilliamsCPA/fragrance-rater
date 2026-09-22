"""Add ADR-012 provenance fields to calibration_source_snapshots.

Revision ID: a3f8c1d9e2b7
Revises: 7daf681ed339
Create Date: 2026-09-22

ADR-012's 2026-09-15 amendment specified this schema change but it was never
implemented: `SourceSnapshot` gains `source_type` and `permission_state`
(CHECK-constrained enum-shaped strings, matching the existing
`PilotOperationalEvent.event_type` / `FragellaLookup.status` precedent),
`fields` (JSON, names which `Fragrance` column(s) this snapshot evidences),
and `source_reference` (free-text citation for evidence with no URL, e.g. an
outreach-letter reply received by email or phone). `source_url` is relaxed
from NOT NULL to nullable, with a new CHECK constraint requiring at least one
of `source_url` / `source_reference` to be populated.

This unblocks `scripts/validate_calibration_manifest.py` recording a
manufacturer confirmation as P1.1 evidence: previously the validator (and
this table) required an absolute HTTPS `source_url` for every entry, which a
private reply cannot supply without inventing a public URL for it (see
`docs/planning/evidence/baseline-v3.1-catalog-coverage.md`, "Implementation
gate").

Every row written before this migration was written only by
`ParfumoScraper._save_source`, per ADR-012's own inventory ("no populated
database" as of 2026-09-15, and the source hierarchy table's classification
of Parfumo as "Excluded"). The backfill below assigns those rows
`source_type="excluded_legacy"`, `permission_state="excluded_no_new_writes"`,
and `fields=["concentration", "launch_year", "brand"]`, matching the exact
values ADR-012's amendment names for this trade-off. Any row that is not, in
fact, Parfumo-derived at migration time should be corrected by hand
afterward; this migration cannot distinguish origin beyond what the ADR's
own inventory already established.

Uses `op.batch_alter_table` for the same SQLite-compatibility reason as
da7c14f4a129 and 9ded7f54996c: SQLite cannot ALTER an already-created table
to add a CHECK constraint or change nullability directly, and batch mode is
a transparent passthrough to plain `ALTER TABLE` on PostgreSQL. The new
NOT-NULL columns are added nullable first, backfilled via `op.execute`, then
tightened to NOT NULL in a second batch block, since the backfill UPDATE
must run against real column values, not the batch-mode shadow table.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f8c1d9e2b7"
down_revision: str | Sequence[str] | None = "7daf681ed339"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_FIELDS = '["concentration", "launch_year", "brand"]'


def upgrade() -> None:
    """Add nullable provenance columns, backfill existing rows, then tighten."""
    with op.batch_alter_table("calibration_source_snapshots") as batch_op:
        batch_op.add_column(
            sa.Column("source_type", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("permission_state", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(sa.Column("fields", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("source_reference", sa.String(length=500), nullable=True)
        )
        batch_op.alter_column(
            "source_url", existing_type=sa.String(length=1000), nullable=True
        )

    op.execute(
        sa.text(
            "UPDATE calibration_source_snapshots "
            "SET source_type = 'excluded_legacy', "
            "permission_state = 'excluded_no_new_writes', "
            "fields = CAST(:fields AS JSON) "
            "WHERE source_type IS NULL"
        ).bindparams(fields=_BACKFILL_FIELDS)
    )

    with op.batch_alter_table("calibration_source_snapshots") as batch_op:
        batch_op.alter_column(
            "source_type", existing_type=sa.String(length=30), nullable=False
        )
        batch_op.alter_column(
            "permission_state", existing_type=sa.String(length=30), nullable=False
        )
        batch_op.alter_column("fields", existing_type=sa.JSON(), nullable=False)
        batch_op.create_check_constraint(
            "ck_calibration_source_snapshots_source_type",
            "source_type IN ('project_owned', 'manufacturer_provided', "
            "'open_licensed', 'bounded_lookup', 'excluded_legacy')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_source_snapshots_permission_state",
            "permission_state IN ('retain_and_train', 'retain_for_qc_only', "
            "'excluded_no_new_writes')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_source_snapshots_has_source",
            "source_url IS NOT NULL OR source_reference IS NOT NULL",
        )


def downgrade() -> None:
    """Drop the CHECK constraints and new columns, and restore source_url NOT NULL.

    Any row relying only on source_reference (no source_url) would violate the
    restored NOT NULL constraint; there are none as of this migration's own
    upgrade (every backfilled legacy row keeps its original source_url), but a
    downgrade after new manufacturer-confirmation rows exist must be preceded
    by re-populating source_url for any row where it is NULL, or it will fail.
    """
    with op.batch_alter_table("calibration_source_snapshots") as batch_op:
        batch_op.drop_constraint(
            "ck_calibration_source_snapshots_has_source", type_="check"
        )
        batch_op.drop_constraint(
            "ck_calibration_source_snapshots_permission_state", type_="check"
        )
        batch_op.drop_constraint(
            "ck_calibration_source_snapshots_source_type", type_="check"
        )
        batch_op.alter_column(
            "source_url", existing_type=sa.String(length=1000), nullable=False
        )
        batch_op.drop_column("source_reference")
        batch_op.drop_column("fields")
        batch_op.drop_column("permission_state")
        batch_op.drop_column("source_type")
