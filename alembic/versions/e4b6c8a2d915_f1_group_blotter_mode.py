"""F1: program blotter mode, shared blind codes, and the group_shared_blotter flag code.

Revision ID: e4b6c8a2d915
Revises: a7f3c2d91e04
Create Date: 2026-11-25 12:00:00.000000

The F1 group session passes ONE physical blotter per sample around the six
evaluators, so every evaluator shares a sample's blind code and the session
order. Three schema changes carry that:

* ``calibration_programs.blotter_mode`` (``INDIVIDUAL`` default, ``SHARED_GROUP``).
  ``INDIVIDUAL`` is what every existing program already does.
* ``calibration_presentations.shared_blind_code`` (default false), and the global
  ``UNIQUE (blind_code)`` is replaced by two narrower guarantees: a partial
  unique index on ``blind_code`` WHERE ``shared_blind_code`` is false (an
  individual code stays unique across the whole table, exactly as before) and
  ``UNIQUE (session_id, blind_code)`` (a shared code is unique within one
  evaluator's session). Existing rows all satisfy both, because every existing
  code was globally unique and none is shared.
* ``calibration_quality_flags``: the code CHECK gains ``group_shared_blotter``,
  an informational flag raised automatically on every session of a
  ``SHARED_GROUP`` program.

The downgrade refuses while any program is ``SHARED_GROUP``, any presentation
holds a shared code (restoring the global UNIQUE would fail or force codes to be
rewritten), or any flag carries the new code (flags are append-only evidence).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4b6c8a2d915"
down_revision: str | Sequence[str] | None = "a7f3c2d91e04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROGRAMS = "calibration_programs"
PRESENTATIONS = "calibration_presentations"
FLAGS = "calibration_quality_flags"

MODE_CHECK = "ck_calibration_programs_blotter_mode_valid"
# Literal copy of models.calibration.BLOTTER_MODES (migrations do not import
# models); tests/unit/test_models/test_group_blotter_migration.py keeps them equal.
BLOTTER_MODES = ("INDIVIDUAL", "SHARED_GROUP")
MODE_CHECK_SQL = "blotter_mode IN ('INDIVIDUAL', 'SHARED_GROUP')"

OLD_UNIQUE = "uq_calibration_presentations_blind_code"
SESSION_UNIQUE = "uq_calibration_presentations_session_id_blind_code"
INDIVIDUAL_INDEX = "uq_calibration_presentations_blind_code_individual"

FLAG_CHECK = "ck_calibration_quality_flags_code_valid"
NEW_CODE = "group_shared_blotter"
# #ASSUME: data-integrity: the lists below equal QUALITY_FLAG_CODES (and
# d7f3a91c5b28's CODES_SQL for PREVIOUS_CODES_SQL).
# #VERIFY: tests/unit/test_models/test_provenance_governance.py compares the
# CHECK this chain leaves with the model's vocabulary.
PREVIOUS_CODES_SQL = (
    "code IN ('out_of_order_presentation', 'outside_planned_window', "
    "'timestamp_inconsistent', 'daily_load_exceeded', "
    "'minimum_spacing_violated', 'clean_air_break_missed', 'interrupted', "
    "'sample_substitution', 'sample_spill', 'mislabel_suspected', "
    "'competing_odor', 'recorder_assistance', 'instrument_fault', "
    "'evaluator_reported_problem', 'non_blind', "
    "'spray_to_smell_ceiling_exceeded', 'other')"
)
CODES_SQL = (
    "code IN ('out_of_order_presentation', 'outside_planned_window', "
    "'timestamp_inconsistent', 'daily_load_exceeded', "
    "'minimum_spacing_violated', 'clean_air_break_missed', 'interrupted', "
    "'sample_substitution', 'sample_spill', 'mislabel_suspected', "
    "'competing_odor', 'recorder_assistance', 'instrument_fault', "
    "'evaluator_reported_problem', 'non_blind', "
    "'spray_to_smell_ceiling_exceeded', 'group_shared_blotter', 'other')"
)


def upgrade() -> None:
    """Add the mode column, the shared-code column, relaxed uniqueness, and the flag code."""
    with op.batch_alter_table(PROGRAMS) as batch_op:
        batch_op.add_column(
            sa.Column(
                "blotter_mode",
                sa.String(length=20),
                nullable=False,
                server_default="INDIVIDUAL",
            )
        )
        batch_op.create_check_constraint(MODE_CHECK, MODE_CHECK_SQL)
    with op.batch_alter_table(PRESENTATIONS) as batch_op:
        batch_op.add_column(
            sa.Column(
                "shared_blind_code",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.drop_constraint(OLD_UNIQUE, type_="unique")
        batch_op.create_unique_constraint(SESSION_UNIQUE, ["session_id", "blind_code"])
        batch_op.create_index(
            INDIVIDUAL_INDEX,
            ["blind_code"],
            unique=True,
            postgresql_where=sa.text("shared_blind_code = false"),
            sqlite_where=sa.text("shared_blind_code = 0"),
        )
    with op.batch_alter_table(FLAGS) as batch_op:
        batch_op.drop_constraint(FLAG_CHECK, type_="check")
        batch_op.create_check_constraint(FLAG_CHECK, CODES_SQL)


def _count(table: sa.TableClause, condition: sa.ColumnElement[bool]) -> int:
    """Return how many rows of ``table`` match ``condition``."""
    return int(
        op.get_bind()
        .execute(sa.select(sa.func.count()).select_from(table).where(condition))
        .scalar_one()
    )


def downgrade() -> None:
    """Restore the global blind-code UNIQUE, refusing while group data exists.

    Raises:
        RuntimeError: When a program is ``SHARED_GROUP``, a presentation holds a
            shared code, or a flag carries ``group_shared_blotter``.
    """
    programs = sa.table(PROGRAMS, sa.column("blotter_mode", sa.String))
    presentations = sa.table(PRESENTATIONS, sa.column("shared_blind_code", sa.Boolean))
    flags = sa.table(FLAGS, sa.column("code", sa.String))
    found = {
        "SHARED_GROUP program(s)": _count(
            programs, programs.c.blotter_mode == "SHARED_GROUP"
        ),
        "shared-blind-code presentation(s)": _count(
            presentations, presentations.c.shared_blind_code.is_(True)
        ),
        "group_shared_blotter quality flag(s)": _count(flags, flags.c.code == NEW_CODE),
    }
    stored = {label: count for label, count in found.items() if count}
    if stored:
        detail = ", ".join(f"{count} {label}" for label, count in stored.items())
        msg = (
            f"Downgrading e4b6c8a2d915 would break group-blotter data ({detail}). "
            "Presentations and flags are append-only evidence; restore a verified "
            "pre-upgrade backup (docs/deployment/p1-release-readiness.md) instead."
        )
        raise RuntimeError(msg)
    with op.batch_alter_table(FLAGS) as batch_op:
        batch_op.drop_constraint(FLAG_CHECK, type_="check")
        batch_op.create_check_constraint(FLAG_CHECK, PREVIOUS_CODES_SQL)
    with op.batch_alter_table(PRESENTATIONS) as batch_op:
        batch_op.drop_index(INDIVIDUAL_INDEX)
        batch_op.drop_constraint(SESSION_UNIQUE, type_="unique")
        batch_op.create_unique_constraint(OLD_UNIQUE, ["blind_code"])
        batch_op.drop_column("shared_blind_code")
    with op.batch_alter_table(PROGRAMS) as batch_op:
        batch_op.drop_constraint(MODE_CHECK, type_="check")
        batch_op.drop_column("blotter_mode")
