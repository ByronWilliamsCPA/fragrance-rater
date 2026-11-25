"""F1: program-level reveal policy (per-evaluator or household).

Revision ID: a7f3c2d91e04
Revises: d7f3a91c5b28
Create Date: 2026-11-25 01:00:00.000000

Adds ``calibration_programs.reveal_policy``. ``ENROLLMENT`` is what every
existing program already does (each evaluator's identity is revealed on its own
once that evaluator's blind baseline is locked), so it is the server default and
every existing row takes it. ``HOUSEHOLD`` releases identity for all of a
program's enrollments together, after every one of them has finished its blind
work including the checkpoint and holdouts (F1 decision 1).

The downgrade refuses while any program holds ``HOUSEHOLD``: dropping the column
would silently turn that program back into per-evaluator reveal, which is the
cross-evaluator leak the policy exists to prevent.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7f3c2d91e04"
down_revision: str | Sequence[str] | None = "d7f3a91c5b28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "calibration_programs"
CHECK = "ck_calibration_programs_reveal_policy_valid"
# Literal copy of models.calibration.REVEAL_POLICIES (migrations do not import
# models); tests/unit/test_models/test_reveal_policy_migration.py keeps them equal.
REVEAL_POLICIES = ("ENROLLMENT", "HOUSEHOLD")
CHECK_SQL = "reveal_policy IN ('ENROLLMENT', 'HOUSEHOLD')"


def upgrade() -> None:
    """Add the policy column, defaulting every program to per-evaluator reveal."""
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.add_column(
            sa.Column(
                "reveal_policy",
                sa.String(length=20),
                nullable=False,
                server_default="ENROLLMENT",
            )
        )
        batch_op.create_check_constraint(CHECK, CHECK_SQL)


def downgrade() -> None:
    """Drop the policy column, refusing while any program uses ``HOUSEHOLD``.

    Raises:
        RuntimeError: When a program's reveal policy is ``HOUSEHOLD``.
    """
    programs = sa.table(TABLE, sa.column("reveal_policy", sa.String))
    found = (
        op.get_bind()
        .execute(
            sa.select(sa.func.count())
            .select_from(programs)
            .where(programs.c.reveal_policy == "HOUSEHOLD")
        )
        .scalar_one()
    )
    if found:
        msg = (
            f"Downgrading a7f3c2d91e04 would turn {found} household-reveal "
            "program(s) into per-evaluator reveal. Restore a verified "
            "pre-upgrade backup (docs/deployment/p1-release-readiness.md) instead."
        )
        raise RuntimeError(msg)
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(CHECK, type_="check")
        batch_op.drop_column("reveal_policy")
