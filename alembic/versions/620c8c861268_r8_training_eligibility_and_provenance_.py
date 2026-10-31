"""R8 PR 1: training eligibility, source provenance, and checkpoint schema.

Revision ID: 620c8c861268
Revises: f74bf7ff9c2d
Create Date: 2026-10-31 03:24:41.497397

Architecture review X-05, X-06, X-16, X-17, D-01, M-07, and M-08, schema only:

* ``training_eligibility`` on ``evaluations`` and ``calibration_observations``
  (X-05), NOT NULL with a closed CHECK vocabulary. Existing and new rows start
  ``unreviewed``, which is not trainable: ADR-014 deliberately leaves the
  per-evidence gate (gap analysis row XL) unbuilt and silent, so the
  conservative default holds every row back until the owner decides.
* ``v_training_rows``, a view exposing only trainable rows (``eligible`` code
  plus the structural rules ``PreferenceHistoryService.training_manifest``
  applies: holdout across all of the reviewer's programs, hidden repeat,
  pre-reveal, stage lock, worn-by, soft delete, and ADR-014's fragrance gate).
  It carries no membership, presentation, session, program, role, or repeat
  column (X-06), so a trainer reading it never joins the blind mapping.
* ``calibration_source_snapshots`` gains the remaining tech-spec D1 provenance
  columns (``source_revision``, ``content_hash``, ``parser_version``,
  ``license_evidence``, ``verified_by``) and issue #130's CHECKs: the
  ADR-012 source-type to permission-state pairs and the ``fields`` allow-list.
* ``calibration_checkpoints`` gains the M-07 reproduction columns and a link to
  a new ``feature_snapshots`` table (X-17), which ``prediction_snapshots`` also
  references; ``calibration_checkpoint_predictions`` holds typed predictions
  (M-08).

The view's SQL and every CHECK are portable to SQLite and PostgreSQL. The view
pins the columns it reads: PostgreSQL refuses to drop or retype them while it
exists, and SQLite batch mode cannot rename a rebuilt table a view names, so a
later migration that alters those columns drops and recreates the view.

The upgrade refuses, naming counts, if an existing source snapshot breaks a new
CHECK. The downgrade refuses while any R8 data exists (a classified evidence
row, a filled provenance or reproduction column, a feature snapshot, or a
typed prediction), since dropping it would lose evidence.

Constraint names are the literal names the metadata naming convention gives the
models (R2, D-03). Nothing here imports application code.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "620c8c861268"
down_revision: str | Sequence[str] | None = "f74bf7ff9c2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_ELIGIBILITY = "unreviewed"
_ELIGIBILITY_CHECK = (
    "training_eligibility IN ('unreviewed', 'eligible', 'withheld', "
    "'invalidated', 'questionable')"
)
_EVIDENCE_TABLES = ("evaluations", "calibration_observations")
_ELIGIBILITY_CHECK_NAMES = {
    "evaluations": "ck_evaluations_training_eligibility_valid",
    "calibration_observations": (
        "ck_calibration_observations_training_eligibility_valid"
    ),
}

_SNAPSHOTS = "calibration_source_snapshots"
_PAIR_CHECK = (
    "(source_type = 'project_owned' AND permission_state IN "
    "('retain_and_train', 'retain_for_qc_only')) "
    "OR (source_type = 'manufacturer_provided' AND permission_state IN "
    "('retain_and_train', 'retain_for_qc_only')) "
    "OR (source_type = 'open_licensed' AND permission_state IN "
    "('retain_and_train', 'retain_for_qc_only')) "
    "OR (source_type = 'bounded_lookup' AND permission_state IN "
    "('retain_for_qc_only')) "
    "OR (source_type = 'excluded_legacy' AND permission_state IN "
    "('excluded_no_new_writes'))"
)
_FIELDS_CHECK = (
    "ltrim(CAST(fields AS TEXT)) LIKE '[%' "
    "AND length(CAST(fields AS TEXT)) - "
    "length(REPLACE(CAST(fields AS TEXT), '[', '')) = 1 "
    "AND length(CAST(fields AS TEXT)) - "
    "length(REPLACE(CAST(fields AS TEXT), ']', '')) = 1 "
    "AND REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
    "REPLACE(REPLACE(REPLACE(CAST(fields AS TEXT), '\"name\"', ''), "
    "'\"brand\"', ''), '\"line\"', ''), '\"concentration\"', ''), "
    "'\"launch_year\"', ''), '\"market_status\"', ''), '\"gender_target\"', ''), "
    "'\"gtin\"', ''), '[', ''), ']', ''), ',', ''), ' ', '') = ''"
)
_CONTENT_HASH_CHECK = (
    "content_hash IS NULL OR (length(content_hash) = 64 "
    "AND TRIM(content_hash, '0123456789abcdef') = '')"
)
_SNAPSHOT_COLUMNS = (
    "source_revision",
    "content_hash",
    "parser_version",
    "license_evidence",
    "verified_by",
)

_CHECKPOINTS = "calibration_checkpoints"
_CHECKPOINT_COLUMNS = (
    "exclusions",
    "filters",
    "feature_space_version",
    "taxonomy_version",
    "model_params",
    "input_digest",
    "feature_snapshot_id",
)

# Every view column is typed in the first branch so both engines agree on the
# UNION's column types. The holdout rule matches
# PreferenceHistoryService.excluded_versions: a version that is a HOLDOUT in any
# program the reviewer is enrolled in never trains, in either workflow. The two
# fragrance codes are ADR-014's TRAINING_INELIGIBLE_CODES.
V_TRAINING_ROWS_SQL = """
CREATE VIEW v_training_rows AS
SELECT
    e.id AS row_id,
    CAST('ORDINARY' AS VARCHAR(20)) AS workflow,
    e.reviewer_id AS reviewer_id,
    e.fragrance_id AS fragrance_id,
    CAST(NULL AS VARCHAR(20)) AS stage,
    CAST('1-5' AS VARCHAR(10)) AS scale,
    e.rating AS rating,
    e.evaluated_at AS observed_at
FROM evaluations AS e
JOIN fragrances AS f ON f.id = e.fragrance_id
WHERE e.training_eligibility = 'eligible'
  AND e.deleted_at IS NULL
  AND e.worn_by_reviewer_id IS NULL
  AND f.deleted_at IS NULL
  AND (
      f.training_eligibility_code IS NULL
      OR f.training_eligibility_code NOT IN
         ('excluded_pending_classification', 'excluded_manual')
  )
  AND NOT EXISTS (
      SELECT 1
      FROM calibration_memberships AS hm
      JOIN calibration_enrollments AS he ON he.program_id = hm.program_id
      WHERE he.reviewer_id = e.reviewer_id
        AND hm.fragrance_id = e.fragrance_id
        AND hm.role = 'HOLDOUT'
  )
UNION ALL
SELECT
    o.id AS row_id,
    CAST('CONTROLLED' AS VARCHAR(20)) AS workflow,
    en.reviewer_id AS reviewer_id,
    m.fragrance_id AS fragrance_id,
    o.stage AS stage,
    CAST('0-10' AS VARCHAR(10)) AS scale,
    o.liking AS rating,
    COALESCE(o.observed_at, o.created_at) AS observed_at
FROM calibration_observations AS o
JOIN calibration_presentations AS p ON p.id = o.presentation_id
JOIN calibration_memberships AS m ON m.id = p.membership_id
JOIN calibration_sessions AS s ON s.id = p.session_id
JOIN calibration_enrollments AS en ON en.id = s.enrollment_id
JOIN fragrances AS f ON f.id = m.fragrance_id
WHERE o.training_eligibility = 'eligible'
  AND o.phase = 'PRE_REVEAL'
  AND o.liking IS NOT NULL
  AND (o.response_status IS NULL OR o.response_status = 'completed')
  AND m.role NOT IN ('HOLDOUT', 'HIDDEN_REPEAT')
  AND (
      (o.stage = 'SKIN' AND p.skin_locked_at IS NOT NULL)
      OR (o.stage = 'BLOTTER' AND p.blotter_locked_at IS NOT NULL)
  )
  AND f.deleted_at IS NULL
  AND (
      f.training_eligibility_code IS NULL
      OR f.training_eligibility_code NOT IN
         ('excluded_pending_classification', 'excluded_manual')
  )
  AND NOT EXISTS (
      SELECT 1
      FROM calibration_memberships AS hm
      JOIN calibration_enrollments AS he ON he.program_id = hm.program_id
      WHERE he.reviewer_id = en.reviewer_id
        AND hm.fragrance_id = m.fragrance_id
        AND hm.role = 'HOLDOUT'
  )
"""
DROP_V_TRAINING_ROWS_SQL = "DROP VIEW IF EXISTS v_training_rows"


def _count(bind: sa.Connection, table: str, condition: str) -> int:
    """Count rows of ``table`` matching a literal SQL ``condition``.

    Args:
        bind (sa.Connection): The migration connection.
        table (str): Table name, one of this module's literals.
        condition (str): A SQL boolean expression, one of this module's
            literals; never built from data.

    Returns:
        int: The number of matching rows.
    """
    return bind.execute(
        sa.select(sa.func.count())
        .select_from(sa.table(table))
        .where(sa.text(condition))
    ).scalar_one()


def _invalid_snapshots(bind: sa.Connection) -> list[str]:
    """Name each new source-snapshot CHECK an existing row would break."""
    found: list[str] = []
    for name, check in (
        ("source_permission_pair", _PAIR_CHECK),
        ("fields_allowed", _FIELDS_CHECK),
    ):
        count = _count(bind, _SNAPSHOTS, "NOT (" + check + ")")
        if count:
            found.append(f"{_SNAPSHOTS} {name}: {count} row(s)")
    return found


def _r8_data(bind: sa.Connection) -> list[str]:
    """Name every place holding data a downgrade would discard."""
    probes: list[tuple[str, str, str]] = [
        (table, "training_eligibility <> 'unreviewed'", "training_eligibility")
        for table in _EVIDENCE_TABLES
    ]
    probes += [
        (_SNAPSHOTS, column + " IS NOT NULL", column) for column in _SNAPSHOT_COLUMNS
    ]
    probes += [
        (_CHECKPOINTS, column + " IS NOT NULL", column)
        for column in _CHECKPOINT_COLUMNS
    ]
    probes += [
        (
            "prediction_snapshots",
            "feature_snapshot_id IS NOT NULL",
            "feature_snapshot_id",
        ),
        ("calibration_checkpoint_predictions", "1 = 1", "rows"),
        ("feature_snapshots", "1 = 1", "rows"),
    ]
    found: list[str] = []
    for table, condition, label in probes:
        count = _count(bind, table, condition)
        if count:
            found.append(f"{table}.{label}: {count} row(s)")
    return found


def upgrade() -> None:
    """Add the R8 columns, tables, CHECKs, and ``v_training_rows``."""
    found = _invalid_snapshots(op.get_bind())
    if found:
        msg = (
            "Upgrading to 620c8c861268 would reject existing source snapshots ("
            + "; ".join(found)
            + "). Correct their source_type/permission_state pair or fields first."
        )
        raise RuntimeError(msg)

    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("feature_space_version", sa.String(length=100), nullable=False),
        sa.Column("taxonomy_version", sa.String(length=100), nullable=True),
        sa.Column("alias_version", sa.String(length=100), nullable=True),
        sa.Column("parser_version", sa.String(length=100), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            _CONTENT_HASH_CHECK, name="ck_feature_snapshots_content_hash_sha256"
        ),
        sa.CheckConstraint(
            "ltrim(CAST(features AS TEXT)) LIKE '{%'",
            name="ck_feature_snapshots_features_is_object",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feature_snapshots"),
        sa.UniqueConstraint("content_hash", name="uq_feature_snapshots_content_hash"),
    )

    for table in _EVIDENCE_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "training_eligibility",
                    sa.String(length=20),
                    server_default=_DEFAULT_ELIGIBILITY,
                    nullable=False,
                )
            )
            batch_op.create_check_constraint(
                _ELIGIBILITY_CHECK_NAMES[table], _ELIGIBILITY_CHECK
            )

    with op.batch_alter_table(_SNAPSHOTS) as batch_op:
        batch_op.add_column(
            sa.Column("source_revision", sa.String(length=200), nullable=True)
        )
        batch_op.add_column(
            sa.Column("content_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("parser_version", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(sa.Column("license_evidence", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("verified_by", sa.String(length=255), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_calibration_source_snapshots_source_permission_pair", _PAIR_CHECK
        )
        batch_op.create_check_constraint(
            "ck_calibration_source_snapshots_fields_allowed", _FIELDS_CHECK
        )
        batch_op.create_check_constraint(
            "ck_calibration_source_snapshots_content_hash_sha256", _CONTENT_HASH_CHECK
        )

    with op.batch_alter_table(_CHECKPOINTS) as batch_op:
        batch_op.add_column(sa.Column("exclusions", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("filters", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("feature_space_version", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("taxonomy_version", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(sa.Column("model_params", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("input_digest", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("feature_snapshot_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_calibration_checkpoints_feature_snapshot_id",
            "feature_snapshots",
            ["feature_snapshot_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_calibration_checkpoints_feature_snapshot_id", ["feature_snapshot_id"]
        )
        batch_op.create_check_constraint(
            "ck_calibration_checkpoints_exclusions_is_array",
            "exclusions IS NULL OR ltrim(CAST(exclusions AS TEXT)) LIKE '[%'",
        )
        batch_op.create_check_constraint(
            "ck_calibration_checkpoints_filters_is_object",
            "filters IS NULL OR ltrim(CAST(filters AS TEXT)) LIKE '{%'",
        )
        batch_op.create_check_constraint(
            "ck_calibration_checkpoints_model_params_is_object",
            "model_params IS NULL OR ltrim(CAST(model_params AS TEXT)) LIKE '{%'",
        )
        batch_op.create_check_constraint(
            "ck_calibration_checkpoints_input_digest_sha256",
            "input_digest IS NULL OR (length(input_digest) = 64 "
            "AND TRIM(input_digest, '0123456789abcdef') = '')",
        )

    op.create_table(
        "calibration_checkpoint_predictions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=36), nullable=False),
        sa.Column("fragrance_id", sa.String(length=36), nullable=False),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("scale", sa.String(length=10), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(target = 'liking' AND scale = '0-10') "
            "OR (target = 'would_wear' AND scale = '0-10') "
            "OR (target = 'would_buy' AND scale = '0-10') "
            "OR (target = 'rating' AND scale = '1-5')",
            name="ck_calibration_checkpoint_predictions_target_scale",
        ),
        sa.CheckConstraint(
            "value = value AND ((scale = '0-10' AND value >= 0 AND value <= 10) "
            "OR (scale = '1-5' AND value >= 1 AND value <= 5))",
            name="ck_calibration_checkpoint_predictions_value_in_scale",
        ),
        sa.CheckConstraint(
            "uncertainty IS NULL OR "
            "(uncertainty = uncertainty AND uncertainty >= 0 AND uncertainty < 1e308)",
            name="ck_calibration_checkpoint_predictions_uncertainty_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["checkpoint_id"],
            ["calibration_checkpoints.id"],
            name="fk_calibration_checkpoint_predictions_checkpoint_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name="fk_calibration_checkpoint_predictions_fragrance_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_checkpoint_predictions"),
        sa.UniqueConstraint(
            "checkpoint_id",
            "fragrance_id",
            "target",
            name="uq_checkpoint_prediction_target",
        ),
    )
    op.create_index(
        "ix_calibration_checkpoint_predictions_checkpoint_id",
        "calibration_checkpoint_predictions",
        ["checkpoint_id"],
    )
    op.create_index(
        "ix_calibration_checkpoint_predictions_fragrance_id",
        "calibration_checkpoint_predictions",
        ["fragrance_id"],
    )

    with op.batch_alter_table("prediction_snapshots") as batch_op:
        batch_op.add_column(
            sa.Column("feature_snapshot_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_prediction_snapshots_feature_snapshot_id",
            "feature_snapshots",
            ["feature_snapshot_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_prediction_snapshots_feature_snapshot_id", ["feature_snapshot_id"]
        )

    op.execute(V_TRAINING_ROWS_SQL)


def downgrade() -> None:
    """Remove the R8 schema; refuse while any R8 data would be lost."""
    found = _r8_data(op.get_bind())
    if found:
        msg = (
            "Downgrading 620c8c861268 would discard R8 evidence ("
            + "; ".join(found)
            + "). Restore a verified pre-upgrade backup "
            "(docs/deployment/p1-release-readiness.md) instead."
        )
        raise RuntimeError(msg)

    # First, so no later batch rebuild trips over a view naming its table.
    op.execute(DROP_V_TRAINING_ROWS_SQL)

    with op.batch_alter_table("prediction_snapshots") as batch_op:
        batch_op.drop_index("ix_prediction_snapshots_feature_snapshot_id")
        batch_op.drop_constraint(
            "fk_prediction_snapshots_feature_snapshot_id", type_="foreignkey"
        )
        batch_op.drop_column("feature_snapshot_id")

    op.drop_index(
        "ix_calibration_checkpoint_predictions_fragrance_id",
        table_name="calibration_checkpoint_predictions",
    )
    op.drop_index(
        "ix_calibration_checkpoint_predictions_checkpoint_id",
        table_name="calibration_checkpoint_predictions",
    )
    op.drop_table("calibration_checkpoint_predictions")

    with op.batch_alter_table(_CHECKPOINTS) as batch_op:
        for check in (
            "ck_calibration_checkpoints_exclusions_is_array",
            "ck_calibration_checkpoints_filters_is_object",
            "ck_calibration_checkpoints_model_params_is_object",
            "ck_calibration_checkpoints_input_digest_sha256",
        ):
            batch_op.drop_constraint(check, type_="check")
        batch_op.drop_index("ix_calibration_checkpoints_feature_snapshot_id")
        batch_op.drop_constraint(
            "fk_calibration_checkpoints_feature_snapshot_id", type_="foreignkey"
        )
        for column in reversed(_CHECKPOINT_COLUMNS):
            batch_op.drop_column(column)

    with op.batch_alter_table(_SNAPSHOTS) as batch_op:
        for check in (
            "ck_calibration_source_snapshots_source_permission_pair",
            "ck_calibration_source_snapshots_fields_allowed",
            "ck_calibration_source_snapshots_content_hash_sha256",
        ):
            batch_op.drop_constraint(check, type_="check")
        for column in reversed(_SNAPSHOT_COLUMNS):
            batch_op.drop_column(column)

    for table in reversed(_EVIDENCE_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(_ELIGIBILITY_CHECK_NAMES[table], type_="check")
            batch_op.drop_column("training_eligibility")

    op.drop_table("feature_snapshots")
