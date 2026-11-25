"""F1: add the non_blind and spray_to_smell_ceiling_exceeded quality flag codes.

Revision ID: d7f3a91c5b28
Revises: 736b7db082fb
Create Date: 2026-11-25 08:00:00.000000

``docs/planning/gates/f1.md`` requires the evaluator who also holds the
blind-to-identity mapping to carry a quality flag marking their rows non-blind
(excluded from blind-baseline training, retained in evaluation, ADR-009
2026-09-21 amendment), and the F1 facilitated format flags a sample first
smelled past the spray-to-first-smell ceiling as a deviation rather than
dropping it. Neither code existed, so ``ck_calibration_quality_flags_code_valid``
is recreated with two more values. ``competing_odor`` and
``clean_air_break_missed`` (the room-contamination codes) already exist.

Only the CHECK changes: no column is added, and the table stays append-only.
The downgrade restores cd1e2375a2e4's list and refuses while any flag row still
carries one of the two new codes, because restoring the CHECK would then fail
or force the rows to be rewritten (a flag is never edited).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7f3a91c5b28"
down_revision: str | Sequence[str] | None = "736b7db082fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "calibration_quality_flags"
CHECK = "ck_calibration_quality_flags_code_valid"
NEW_CODES = ("non_blind", "spray_to_smell_ceiling_exceeded")

# #ASSUME: data-integrity: the lists below equal QUALITY_FLAG_CODES (and
# cd1e2375a2e4's list for PREVIOUS_CODES_SQL).
# #VERIFY: tests/unit/test_models/test_provenance_governance.py compares the
# CHECK this migration leaves with the model's vocabulary.
PREVIOUS_CODES_SQL = (
    "code IN ('out_of_order_presentation', 'outside_planned_window', "
    "'timestamp_inconsistent', 'daily_load_exceeded', "
    "'minimum_spacing_violated', 'clean_air_break_missed', 'interrupted', "
    "'sample_substitution', 'sample_spill', 'mislabel_suspected', "
    "'competing_odor', 'recorder_assistance', 'instrument_fault', "
    "'evaluator_reported_problem', 'other')"
)
CODES_SQL = (
    "code IN ('out_of_order_presentation', 'outside_planned_window', "
    "'timestamp_inconsistent', 'daily_load_exceeded', "
    "'minimum_spacing_violated', 'clean_air_break_missed', 'interrupted', "
    "'sample_substitution', 'sample_spill', 'mislabel_suspected', "
    "'competing_odor', 'recorder_assistance', 'instrument_fault', "
    "'evaluator_reported_problem', 'non_blind', "
    "'spray_to_smell_ceiling_exceeded', 'other')"
)


def upgrade() -> None:
    """Recreate the code CHECK with the two new values."""
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(CHECK, type_="check")
        batch_op.create_check_constraint(CHECK, CODES_SQL)


def downgrade() -> None:
    """Restore the previous CHECK, refusing while a row uses a new code.

    Raises:
        RuntimeError: When any flag row carries ``non_blind`` or
            ``spray_to_smell_ceiling_exceeded``.
    """
    flags = sa.table(TABLE, sa.column("code", sa.String))
    stored = (
        op.get_bind()
        .execute(
            sa.select(sa.func.count())
            .select_from(flags)
            .where(flags.c.code.in_(NEW_CODES))
        )
        .scalar_one()
    )
    if stored:
        msg = (
            f"Downgrading d7f3a91c5b28 would reject {stored} quality flag(s) "
            "coded non_blind or spray_to_smell_ceiling_exceeded. Flags are "
            "append-only evidence; restore a verified pre-upgrade backup "
            "(docs/deployment/p1-release-readiness.md) instead."
        )
        raise RuntimeError(msg)
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(CHECK, type_="check")
        batch_op.create_check_constraint(CHECK, PREVIOUS_CODES_SQL)
