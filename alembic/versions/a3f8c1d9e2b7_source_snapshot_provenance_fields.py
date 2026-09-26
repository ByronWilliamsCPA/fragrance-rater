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
of `source_url` / `source_reference` to be non-blank (an empty or
whitespace-only string does not count as provenance).

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
NOT-NULL columns are added nullable first, backfilled via a typed Core
UPDATE (see `_snapshots_table`), then tightened to NOT NULL in a second batch
block, since the backfill UPDATE must run against real column values, not the
batch-mode shadow table.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f8c1d9e2b7"
down_revision: str | Sequence[str] | None = "7daf681ed339"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "calibration_source_snapshots"
_BACKFILL_FIELDS = ("concentration", "launch_year", "brand")
# Portable across SQLite and PostgreSQL: TRIM and COALESCE behave the same on
# both, so a blank or whitespace-only identifier never counts as provenance.
# Must stay textually identical to the matching CheckConstraint on
# `SourceSnapshot` in `src/fragrance_rater/models/calibration.py`.
_HAS_SOURCE_CHECK = (
    "COALESCE(TRIM(source_url), '') <> '' OR COALESCE(TRIM(source_reference), '') <> ''"
)


def _snapshots_table() -> sa.TableClause:
    """A lightweight Core handle so JSON binds go through the dialect's serializer.

    A raw `sa.text("... CAST(:fields AS JSON) ...")` bypasses SQLAlchemy's
    JSON bind processor; on SQLite (no JSON type) the CAST is a
    numeric-affinity conversion that stores the integer 0. Typing the column
    as `sa.JSON()` here, as 9ded7f54996c does for its own backfill, makes
    the value serialize to JSON text on SQLite and to `json` on PostgreSQL.
    """
    return sa.table(
        _TABLE,
        sa.column("source_type", sa.String()),
        sa.column("permission_state", sa.String()),
        sa.column("fields", sa.JSON()),
        sa.column("source_url", sa.String()),
    )


def upgrade() -> None:
    """Add nullable provenance columns, backfill existing rows, then tighten."""
    with op.batch_alter_table(_TABLE) as batch_op:
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

    # #ASSUME: data-integrity: every calibration_source_snapshots row that
    # exists before this migration was written by
    # `ParfumoScraper._save_source`, the only production constructor of
    # `SourceSnapshot` at this revision (ADR-012's 2026-09-15 inventory), so
    # stamping all of them excluded_legacy / excluded_no_new_writes with
    # Parfumo's field list is correct. A row from any other origin would be
    # mislabeled and must be corrected by hand afterward.
    # #VERIFY: covered by the integration test
    # test_upgrade_backfills_legacy_rows_with_excluded_legacy_provenance
    # (in test_source_snapshot_provenance_migration), which pins the exact
    # backfilled values and that `fields` reads back as a list.
    snapshots = _snapshots_table()
    op.execute(
        snapshots.update()
        .where(snapshots.c.source_type.is_(None))
        .values(
            source_type="excluded_legacy",
            permission_state="excluded_no_new_writes",
            fields=list(_BACKFILL_FIELDS),
        )
    )

    with op.batch_alter_table(_TABLE) as batch_op:
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
            "ck_calibration_source_snapshots_has_source", _HAS_SOURCE_CHECK
        )


def downgrade() -> None:
    """Drop the CHECK constraints and new columns, and restore source_url NOT NULL.

    A row relying only on `source_reference` (no `source_url`) cannot survive
    the restored NOT NULL constraint, and dropping `source_reference` would
    discard its only provenance. There are none as of this migration's own
    upgrade (every backfilled legacy row keeps its original `source_url`), but
    manufacturer-confirmation rows written afterward may be reference-only.
    Rather than let the batch table rebuild fail midway with a raw
    IntegrityError, rows whose `source_url` is NULL or blank are counted
    first and, if any exist, the downgrade refuses before touching the schema.
    A blank `source_url` is counted too: it would pass the restored NOT NULL,
    but the row's real provenance (its `source_reference`) would still be
    silently dropped.

    Raises:
        RuntimeError: If any row has a NULL or blank `source_url`. The
            operator must give each such row a real `source_url` (or export
            and delete it) before retrying the downgrade.
    """
    snapshots = _snapshots_table()
    reference_only = (
        op.get_bind()
        .execute(
            sa.select(sa.func.count())
            .select_from(snapshots)
            .where(sa.func.coalesce(sa.func.trim(snapshots.c.source_url), "") == "")
        )
        .scalar_one()
    )
    if reference_only:
        msg = (
            f"Refusing to downgrade a3f8c1d9e2b7: {reference_only} "
            f"{_TABLE} row(s) have a NULL or blank source_url and rely only on "
            "source_reference. Downgrading would restore source_url NOT NULL "
            "and drop source_reference, losing that reference-only provenance. "
            "Populate source_url for those rows (or export and delete them) "
            "before retrying. No schema change was made."
        )
        raise RuntimeError(msg)

    with op.batch_alter_table(_TABLE) as batch_op:
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
