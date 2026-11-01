"""R8 follow-up: drop bounded_lookup from the source snapshot vocabulary.

Revision ID: 736b7db082fb
Revises: 52e22be935d3
Create Date: 2026-11-01 10:00:00.000000

``calibration_source_snapshots.source_type`` allowed ``bounded_lookup`` (a capped
Fragella enrichment), but ADR-012 says those citations must never be written to a
``SourceSnapshot``, and nothing ever wrote one (issue #130). Owner decision
2026-11-01: drop the value. Two CHECKs name it, so both are recreated:
``ck_calibration_source_snapshots_source_type`` and
``ck_calibration_source_snapshots_source_permission_pair``.

The upgrade refuses if any row still carries the value, rather than guessing what
it should become. The downgrade restores the previous CHECKs.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "736b7db082fb"
down_revision: str | Sequence[str] | None = "52e22be935d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "calibration_source_snapshots"
TYPE_CHECK = "ck_calibration_source_snapshots_source_type"
PAIR_CHECK = "ck_calibration_source_snapshots_source_permission_pair"

_ALLOWED = "'retain_and_train', 'retain_for_qc_only'"

TYPE_SQL = (
    "source_type IN ('project_owned', 'manufacturer_provided', "
    "'open_licensed', 'excluded_legacy')"
)
PAIR_SQL = (
    f"(source_type = 'project_owned' AND permission_state IN ({_ALLOWED})) "
    f"OR (source_type = 'manufacturer_provided' AND permission_state IN ({_ALLOWED})) "
    f"OR (source_type = 'open_licensed' AND permission_state IN ({_ALLOWED})) "
    "OR (source_type = 'excluded_legacy' AND permission_state IN "
    "('excluded_no_new_writes'))"
)

# The CHECKs this revision replaces, verbatim, for the downgrade.
PREVIOUS_TYPE_SQL = (
    "source_type IN ('project_owned', 'manufacturer_provided', "
    "'open_licensed', 'bounded_lookup', 'excluded_legacy')"
)
PREVIOUS_PAIR_SQL = (
    f"(source_type = 'project_owned' AND permission_state IN ({_ALLOWED})) "
    f"OR (source_type = 'manufacturer_provided' AND permission_state IN ({_ALLOWED})) "
    f"OR (source_type = 'open_licensed' AND permission_state IN ({_ALLOWED})) "
    "OR (source_type = 'bounded_lookup' AND permission_state IN "
    "('retain_for_qc_only')) "
    "OR (source_type = 'excluded_legacy' AND permission_state IN "
    "('excluded_no_new_writes'))"
)


def _bounded_lookup_rows(bind: sa.Connection) -> int:
    snapshots = sa.table(TABLE, sa.column("source_type", sa.String))
    return bind.execute(
        sa.select(sa.func.count())
        .select_from(snapshots)
        .where(snapshots.c.source_type == "bounded_lookup")
    ).scalar_one()


def upgrade() -> None:
    """Drop the value from both CHECKs, refusing if a row still uses it.

    Raises:
        RuntimeError: When any snapshot still has ``source_type = 'bounded_lookup'``.
    """
    found = _bounded_lookup_rows(op.get_bind())
    if found:
        msg = (
            f"Upgrading to 736b7db082fb would reject {found} source snapshot(s) "
            "with source_type 'bounded_lookup'. ADR-012 says those are never "
            "written; decide what each row is, then change or remove it first."
        )
        raise RuntimeError(msg)
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(TYPE_CHECK, type_="check")
        batch_op.drop_constraint(PAIR_CHECK, type_="check")
        batch_op.create_check_constraint(TYPE_CHECK, TYPE_SQL)
        batch_op.create_check_constraint(PAIR_CHECK, PAIR_SQL)


def downgrade() -> None:
    """Restore the previous CHECKs (which also allow ``bounded_lookup``)."""
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(TYPE_CHECK, type_="check")
        batch_op.drop_constraint(PAIR_CHECK, type_="check")
        batch_op.create_check_constraint(TYPE_CHECK, PREVIOUS_TYPE_SQL)
        batch_op.create_check_constraint(PAIR_CHECK, PREVIOUS_PAIR_SQL)
