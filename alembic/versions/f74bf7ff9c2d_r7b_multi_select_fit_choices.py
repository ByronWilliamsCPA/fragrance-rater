"""R7b: season and setting fit become multi-select child rows.

Revision ID: f74bf7ff9c2d
Revises: cd1e2375a2e4
Create Date: 2026-10-30 19:18:57.231762

R7a PR 2 stored ML Decisions Q9's blind season and setting suitability as one
best-fit code per field on ``calibration_observations``. The accepted
instrument (v0.5) offers multi-select and the owner confirmed multi-select on
2026-10-30, so each ticked option is now one row of ``calibration_fit_choices``
and the two single-select columns (and their four CHECKs) are dropped.

Nothing has ever written ``season_fit`` or ``setting_fit``: no route accepted
them before this sprint. The upgrade still refuses, naming the count, if either
column holds data, because dropping evidence silently is never acceptable;
convert such rows by hand first. The downgrade restores the columns and
refuses while any fit choice exists, since a multi-select answer cannot be
squeezed into one code without losing part of it.

Not portable CHECKs, so enforced by ``CalibrationService.observe`` instead: a
fit choice belongs to a SKIN-stage observation, and ``none`` and
``cannot_judge`` stand alone.

Constraint names are the literal names the metadata naming convention gives the
models (R2, D-03). Nothing here imports application code.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f74bf7ff9c2d"
down_revision: str | Sequence[str] | None = "cd1e2375a2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OBSERVATIONS = "calibration_observations"
_DROPPED_COLUMNS = ("season_fit", "setting_fit")
_DROPPED_CHECKS = (
    "ck_calibration_observations_season_fit_valid",
    "ck_calibration_observations_setting_fit_valid",
    "ck_calibration_observations_season_fit_requires_skin",
    "ck_calibration_observations_setting_fit_requires_skin",
)


def _populated_single_select_columns(bind: sa.Connection) -> list[str]:
    """Name each single-select column that holds data an upgrade would drop."""
    found: list[str] = []
    for column in _DROPPED_COLUMNS:
        count = bind.execute(
            sa.select(sa.func.count())
            .select_from(sa.table(_OBSERVATIONS))
            .where(sa.column(column).is_not(None))
        ).scalar_one()
        if count:
            found.append(f"{_OBSERVATIONS}.{column}: {count} non-NULL row(s)")
    return found


def _fit_choice_count(bind: sa.Connection) -> int:
    """Return how many fit choices a downgrade would drop."""
    return bind.execute(
        sa.select(sa.func.count()).select_from(sa.table("calibration_fit_choices"))
    ).scalar_one()


def upgrade() -> None:
    """Add ``calibration_fit_choices`` and drop the single-select columns."""
    found = _populated_single_select_columns(op.get_bind())
    if found:
        msg = (
            "Upgrading to f74bf7ff9c2d would drop single-select fit answers ("
            + "; ".join(found)
            + "). Convert them to calibration_fit_choices rows first."
        )
        raise RuntimeError(msg)

    op.create_table(
        "calibration_fit_choices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("observation_id", sa.String(length=36), nullable=False),
        sa.Column("dimension", sa.String(length=10), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "dimension IN ('season', 'setting')",
            name="ck_calibration_fit_choices_dimension_valid",
        ),
        sa.CheckConstraint(
            "(dimension = 'season' AND code IN ('spring', 'summer', 'fall', "
            "'winter', 'year_round', 'none', 'cannot_judge')) "
            "OR (dimension = 'setting' AND code IN ('work_school', 'home', "
            "'social_outing', 'formal_event', 'outdoor_activity', 'other', "
            "'none', 'cannot_judge'))",
            name="ck_calibration_fit_choices_code_valid",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["calibration_observations.id"],
            name="fk_calibration_fit_choices_observation_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_fit_choices"),
        sa.UniqueConstraint(
            "observation_id",
            "dimension",
            "code",
            name="uq_calibration_fit_choices_observation_id_dimension_code",
        ),
    )
    op.create_index(
        "ix_calibration_fit_choices_observation_id",
        "calibration_fit_choices",
        ["observation_id"],
    )

    with op.batch_alter_table(_OBSERVATIONS) as batch_op:
        for check in _DROPPED_CHECKS:
            batch_op.drop_constraint(check, type_="check")
        for column in _DROPPED_COLUMNS:
            batch_op.drop_column(column)


def downgrade() -> None:
    """Restore the single-select columns; refuse while fit choices exist."""
    count = _fit_choice_count(op.get_bind())
    if count:
        msg = (
            "Downgrading f74bf7ff9c2d would discard multi-select fit answers "
            f"(calibration_fit_choices: {count} row(s)). Restore a verified "
            "pre-upgrade backup (docs/deployment/p1-release-readiness.md) instead."
        )
        raise RuntimeError(msg)

    with op.batch_alter_table(_OBSERVATIONS) as batch_op:
        batch_op.add_column(
            sa.Column("season_fit", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("setting_fit", sa.String(length=20), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_season_fit_valid",
            "season_fit IS NULL OR season_fit IN ('spring', 'summer', 'fall', "
            "'winter', 'year_round', 'none', 'cannot_judge')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_setting_fit_valid",
            "setting_fit IS NULL OR setting_fit IN ('work_school', 'home', "
            "'social_outing', 'formal_event', 'outdoor_activity', 'other', "
            "'none', 'cannot_judge')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_season_fit_requires_skin",
            "season_fit IS NULL OR stage = 'SKIN'",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_setting_fit_requires_skin",
            "setting_fit IS NULL OR stage = 'SKIN'",
        )

    op.drop_index(
        "ix_calibration_fit_choices_observation_id",
        table_name="calibration_fit_choices",
    )
    op.drop_table("calibration_fit_choices")
