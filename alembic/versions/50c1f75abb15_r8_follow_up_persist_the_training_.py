"""R8 follow-up: persist the training outcome on a closing quality flag.

Revision ID: 50c1f75abb15
Revises: 4edb5c967539
Create Date: 2026-10-31 13:30:00.000000

``calibration_quality_flags.training_outcome`` records the manager's decision
that a ``resolved`` closing row carried (``eligible``, ``withheld`` or
``invalidated``). It was only ever written to the audit event, so nothing could
tell a resolution that decided an outcome from one that left the covered
rows for a manager. Without that, an ``invalidated`` flag raised later on the
same target sent those held rows back to ``eligible`` (CodeRabbit finding on
PR #181). ``TrainingEligibilityService`` now keeps a row ``questionable``
while a covering ``resolved`` flag has no outcome.

The column is NULL for every other row. Existing ``resolved`` rows also read
NULL, which is the safe reading: their rows wait for a manager, and nothing
becomes trainable without one. The table stays append-only; the column is
written at insert.

The downgrade drops the column and refuses while any outcome is stored, because
that is a manager decision this schema would otherwise discard.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "50c1f75abb15"
down_revision: str | Sequence[str] | None = "4edb5c967539"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "calibration_quality_flags"
CHECK = "ck_calibration_quality_flags_training_outcome_valid"


def upgrade() -> None:
    """Add the nullable outcome column and its vocabulary check."""
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.add_column(
            sa.Column("training_outcome", sa.String(length=20), nullable=True)
        )
        batch_op.create_check_constraint(
            CHECK,
            "training_outcome IS NULL OR training_outcome IN ('eligible', 'withheld', 'invalidated')",
        )


def downgrade() -> None:
    """Drop the column, refusing while a manager decision would be lost.

    Raises:
        RuntimeError: When any closing row carries a training outcome.
    """
    flags = sa.table(TABLE, sa.column("training_outcome", sa.String))
    stored = (
        op.get_bind()
        .execute(
            sa.select(sa.func.count())
            .select_from(flags)
            .where(flags.c.training_outcome.is_not(None))
        )
        .scalar_one()
    )
    if stored:
        msg = (
            f"Downgrading 50c1f75abb15 would discard {stored} stored training "
            "outcome(s) from resolved quality flags. Restore a verified "
            "pre-upgrade backup (docs/deployment/p1-release-readiness.md) "
            "instead."
        )
        raise RuntimeError(msg)
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(CHECK, type_="check")
        batch_op.drop_column("training_outcome")
