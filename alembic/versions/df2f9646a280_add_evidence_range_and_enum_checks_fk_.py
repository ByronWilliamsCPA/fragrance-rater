"""Add evidence range and enum CHECKs, FK indexes, evaluations RESTRICT.

Revision ID: df2f9646a280
Revises: 2c8c3971bfd8
Create Date: 2026-10-02

Milestone R, sprint R2, PR 2 (architecture review D-02, D-09, D-10, D-15;
ML structure review X-25):

* D-02: range CHECKs on `evaluations.rating` (1-5, NOT NULL) and on
  `longevity_rating` / `sillage_rating` (NULL or 1-5). The scales were
  enforced only by Pydantic.
* D-15 / X-25: `IN (...)` CHECKs on `calibration_programs.status`,
  `calibration_memberships.role`, and `calibration_observations.stage` and
  `phase`. `role = 'HOLDOUT'` is the leakage-prevention mechanism; a
  misspelled role made a holdout trainable.
* D-10: indexes on the nine foreign-key columns that had none.
* D-09: `evaluations.fragrance_id` and `evaluations.reviewer_id` change from
  `ON DELETE CASCADE` to `ON DELETE RESTRICT`, so a hard delete of a
  fragrance or reviewer can no longer silently destroy encounter history.
  Soft delete is already the only API path.

Before adding any CHECK, `upgrade()` counts the rows that would violate it
and raises with the offending ids instead of letting PostgreSQL fail on an
anonymous constraint error. Fix or remove those rows, then rerun.

Uses literal names and `op.batch_alter_table` (alembic/README). Fully
reversible.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "df2f9646a280"
down_revision: str | Sequence[str] | None = "2c8c3971bfd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, constraint name, condition). The condition is also the pre-flight
# predicate: a row violates the constraint when it is false (NOT NULL columns)
# or false-but-not-null, which `NOT (condition)` captures in both cases.
CHECKS: tuple[tuple[str, str, str], ...] = (
    ("evaluations", "ck_evaluations_rating_range", "rating >= 1 AND rating <= 5"),
    (
        "evaluations",
        "ck_evaluations_longevity_rating_range",
        "longevity_rating IS NULL OR (longevity_rating >= 1 AND longevity_rating <= 5)",
    ),
    (
        "evaluations",
        "ck_evaluations_sillage_rating_range",
        "sillage_rating IS NULL OR (sillage_rating >= 1 AND sillage_rating <= 5)",
    ),
    (
        "calibration_programs",
        "ck_calibration_programs_status_valid",
        "status IN ('draft', 'active')",
    ),
    (
        "calibration_memberships",
        "ck_calibration_memberships_role_valid",
        (
            "role IN ('UNIVERSAL_BASELINE', 'HIDDEN_REPEAT', 'HOLDOUT', "
            "'ACTIVE_LEARNING', 'RETEST', 'OWNED_VALIDATION', 'OTHER')"
        ),
    ),
    (
        "calibration_observations",
        "ck_calibration_observations_stage_valid",
        "stage IN ('BLOTTER', 'SKIN')",
    ),
    (
        "calibration_observations",
        "ck_calibration_observations_phase_valid",
        "phase IN ('PRE_REVEAL', 'PREVIOUSLY_REVEALED', 'POST_REVEAL')",
    ),
)

# (table, column) for the nine unindexed foreign keys; index names follow
# ix_<table>_<column>.
FK_INDEXES: tuple[tuple[str, str], ...] = (
    ("calibration_checkpoints", "enrollment_id"),
    ("calibration_memberships", "repeat_of_id"),
    ("calibration_presentations", "membership_id"),
    ("calibration_source_snapshots", "fragrance_id"),
    ("calibration_version_perfumers", "perfumer_id"),
    ("prediction_snapshots", "outcome_evaluation_id"),
    ("prediction_snapshots", "outcome_observation_id"),
    ("recommendation_response_revisions", "outcome_evaluation_id"),
    ("recommendation_response_revisions", "outcome_observation_id"),
)

# (constraint name, local column, referred table) on `evaluations`.
EVALUATION_FKS: tuple[tuple[str, str, str], ...] = (
    ("fk_evaluations_fragrance_id", "fragrance_id", "fragrances"),
    ("fk_evaluations_reviewer_id", "reviewer_id", "reviewers"),
)

_MAX_REPORTED_IDS = 20


def _assert_no_violations() -> None:
    """Refuse to add CHECKs that existing rows would violate.

    #CRITICAL: data-integrity: production runs this on container start
    (docker-entrypoint.sh). A bare ADD CONSTRAINT failure would name only the
    constraint; this names every offending row so an operator can repair the
    data instead of guessing.
    #VERIFY: tests/integration/test_schema_parity_postgres.py inserts an
    out-of-range evaluation below this revision and asserts the upgrade fails
    with its id, leaving the schema unchanged.

    Raises:
        RuntimeError: If any existing row violates a new CHECK.
    """
    bind = op.get_bind()
    problems: list[str] = []
    for table, name, condition in CHECKS:
        # False positive (ruff S608, bandit B608): `table` and `condition`
        # come only from the frozen CHECKS literal above, never from input,
        # and identifiers and CHECK bodies cannot be bound as parameters.
        sql = f"SELECT id FROM {table} WHERE NOT ({condition}) ORDER BY id"  # noqa: S608  # nosec B608
        query = sa.text(sql)
        ids = [str(row[0]) for row in bind.execute(query)]
        if ids:
            shown = ", ".join(ids[:_MAX_REPORTED_IDS])
            more = len(ids) - _MAX_REPORTED_IDS
            suffix = f" (and {more} more)" if more > 0 else ""
            problems.append(f"{name}: {len(ids)} row(s) in {table}: {shown}{suffix}")
    if problems:
        msg = (
            f"Migration {revision} cannot add its CHECK constraints until these "
            "rows are corrected or removed:\n  " + "\n  ".join(problems)
        )
        raise RuntimeError(msg)


def upgrade() -> None:
    """Add CHECKs, FK indexes, and RESTRICT on `evaluations`."""
    _assert_no_violations()
    for table, name, condition in CHECKS:
        with op.batch_alter_table(table) as batch:
            batch.create_check_constraint(name, condition)
    for table, column in FK_INDEXES:
        op.create_index(f"ix_{table}_{column}", table, [column])
    with op.batch_alter_table("evaluations") as batch:
        for name, column, referred in EVALUATION_FKS:
            batch.drop_constraint(name, type_="foreignkey")
            batch.create_foreign_key(
                name, referred, [column], ["id"], ondelete="RESTRICT"
            )


def downgrade() -> None:
    """Restore CASCADE on `evaluations` and drop the new indexes and CHECKs."""
    with op.batch_alter_table("evaluations") as batch:
        for name, column, referred in EVALUATION_FKS:
            batch.drop_constraint(name, type_="foreignkey")
            batch.create_foreign_key(
                name, referred, [column], ["id"], ondelete="CASCADE"
            )
    for table, column in reversed(FK_INDEXES):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
    for table, name, _condition in reversed(CHECKS):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(name, type_="check")
