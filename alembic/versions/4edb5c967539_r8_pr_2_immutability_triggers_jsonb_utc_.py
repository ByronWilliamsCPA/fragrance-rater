"""R8 PR 2: immutability triggers, jsonb, UTC defaults, idempotency key, view.

Revision ID: 4edb5c967539
Revises: 620c8c861268
Create Date: 2026-10-31 11:01:57.648194

Architecture review WS-9 items placed in R8 (D-08/Q14, D-12, D-16/Q16, D-22/Q18)
and the trainer-facing half of X-05/X-06:

* ``v_manager_linkage`` (new, X-06) carries the role, hidden-repeat, blind
  code, session, and program linkage per observation that the trainer view
  omits; only a manager endpoint reads it.
* ``v_training_rows`` is dropped first and recreated last (alembic/README,
  VIEWS). The new definition adds one column, ``revealed`` (whether the
  evaluator's enrollment has been revealed, always true for ordinary rows),
  and one rule: a controlled observation trains only while no later
  pre-reveal observation of the same presentation and stage exists, which is
  the selection ``PreferenceHistoryService.training_manifest`` makes. Readers
  (``ml/training_view.py``) can then reproduce the manifest without joining
  presentation, membership, session, or enrollment. Every PR 1 rule stays.
* D-12: the 19 ``json`` columns become ``jsonb`` (PostgreSQL only; SQLite
  stores both the same way). ``USING col::jsonb`` re-parses each value; a
  value ``jsonb`` cannot hold (an escaped NUL character) fails the whole upgrade,
  which is transactional, so nothing is half-converted.
* D-16: the eight ``now()``/``CURRENT_TIMESTAMP`` server defaults become
  ``timezone('utc', now())``, which is UTC whatever the session ``TimeZone``
  says (PostgreSQL only; SQLite's ``CURRENT_TIMESTAMP`` is already UTC).
* D-22: ``calibration_observations.idempotency_key`` with
  ``uq_calibration_observations_presentation_id_idempotency_key``.
* D-08/Q14: ``BEFORE`` triggers on PostgreSQL enforcing the five immutability
  guarantees the service already promises:

  - append-only observations: no DELETE; an UPDATE may change
    ``training_eligibility`` and nothing else (R8's eligibility promotion is
    the one sanctioned in-place write);
  - frozen checkpoints, their typed predictions, and feature snapshots: no
    UPDATE, no DELETE;
  - activated membership: no INSERT, UPDATE, or DELETE of a membership whose
    program is ``active``;
  - frozen predictions: no DELETE; an UPDATE may only fill the four outcome
    link columns while they are NULL;
  - assigned identity: no UPDATE of a fragrance identity column while any
    membership references the fragrance (the columns
    ``FragranceService.update`` already guards).

  SQLite has no PL/pgSQL, so the triggers exist only on PostgreSQL and the
  integration suite exercises them.

The downgrade is a real reversal (drops the triggers and functions, converts
``jsonb`` back to ``json``, restores ``now()`` defaults, restores PR 1's view)
except that it refuses with RuntimeError while any observation carries an
idempotency key: dropping the column would discard client keys recorded with
evidence. Nothing here imports application code; every name is a literal.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4edb5c967539"
down_revision: str | Sequence[str] | None = "620c8c861268"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# D-12: every ``json`` column at 620c8c861268, as (table, column, nullable).
JSON_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("calibration_checkpoints", "exclusions", True),
    ("calibration_checkpoints", "filters", True),
    ("calibration_checkpoints", "manifest", False),
    ("calibration_checkpoints", "model_params", True),
    ("calibration_checkpoints", "predictions", False),
    ("calibration_enrollments", "recorder_usernames", False),
    ("calibration_memberships", "selection", False),
    ("calibration_observations", "perceived_notes", True),
    ("calibration_sessions", "context", False),
    ("calibration_source_snapshots", "fields", False),
    ("calibration_source_snapshots", "payload", False),
    ("feature_snapshots", "features", False),
    ("fragella_lookups", "results", False),
    ("house_submissions", "payload", False),
    ("prediction_snapshots", "explanation", True),
    ("prediction_snapshots", "input_manifest", False),
    ("recommendation_runs", "filters", False),
    ("recommendation_runs", "input_manifest", False),
    ("recommendation_runs", "source_snapshot", False),
)

# D-16: every server-side clock default at 620c8c861268, with the default it
# had (the downgrade restores exactly that text).
TIMESTAMP_DEFAULTS: tuple[tuple[str, str, str], ...] = (
    ("accord_types", "created_at", "CURRENT_TIMESTAMP"),
    ("evaluations", "created_at", "now()"),
    ("evaluations", "evaluated_at", "now()"),
    ("fragrance_gtins", "created_at", "CURRENT_TIMESTAMP"),
    ("fragrances", "created_at", "now()"),
    ("fragrances", "updated_at", "now()"),
    ("note_aliases", "created_at", "CURRENT_TIMESTAMP"),
    ("reviewers", "created_at", "now()"),
)
UTC_NOW = "timezone('utc', now())"

OBSERVATIONS = "calibration_observations"
IDEMPOTENCY_UNIQUE = "uq_calibration_observations_presentation_id_idempotency_key"
IDEMPOTENCY_CHECK = "ck_calibration_observations_idempotency_key_length"

# Columns ``FragranceService.update`` refuses to change on a referenced
# version (assigned identity, D-08).
IDENTITY_COLUMNS = (
    "id",
    "name",
    "brand",
    "concentration",
    "launch_year",
    "version_key",
    "gender_target",
    "primary_family",
    "subfamily",
    "intensity",
)

# --- triggers (PostgreSQL only) ----------------------------------------------
# Each function raises SQLSTATE 23001 (restrict_violation), an integrity
# error class, so a violating write surfaces as an IntegrityError.

OBSERVATION_FUNCTION_SQL = """
CREATE FUNCTION fr_observation_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'calibration_observations is append-only: row % cannot be deleted', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF (to_jsonb(NEW) - 'training_eligibility')
        IS DISTINCT FROM (to_jsonb(OLD) - 'training_eligibility') THEN
        RAISE EXCEPTION 'calibration_observations is append-only: only training_eligibility may change on row %', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$
"""

FROZEN_FUNCTION_SQL = """
CREATE FUNCTION fr_frozen_row() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are frozen: % refused on row %', TG_TABLE_NAME, TG_OP, OLD.id
        USING ERRCODE = 'restrict_violation';
END;
$$
"""

PREDICTION_FUNCTION_SQL = """
CREATE FUNCTION fr_prediction_frozen() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'prediction_snapshots rows are frozen: row % cannot be deleted', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF (to_jsonb(NEW) - ARRAY['outcome_evaluation_id', 'outcome_observation_id',
                              'outcome_linked_at', 'outcome_recorded_by'])
        IS DISTINCT FROM
       (to_jsonb(OLD) - ARRAY['outcome_evaluation_id', 'outcome_observation_id',
                              'outcome_linked_at', 'outcome_recorded_by']) THEN
        RAISE EXCEPTION 'prediction_snapshots rows are frozen: only the outcome link may be set on row %', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF (OLD.outcome_evaluation_id IS NOT NULL
            AND NEW.outcome_evaluation_id IS DISTINCT FROM OLD.outcome_evaluation_id)
        OR (OLD.outcome_observation_id IS NOT NULL
            AND NEW.outcome_observation_id IS DISTINCT FROM OLD.outcome_observation_id)
        OR (OLD.outcome_linked_at IS NOT NULL
            AND NEW.outcome_linked_at IS DISTINCT FROM OLD.outcome_linked_at)
        OR (OLD.outcome_recorded_by IS NOT NULL
            AND NEW.outcome_recorded_by IS DISTINCT FROM OLD.outcome_recorded_by) THEN
        RAISE EXCEPTION 'prediction_snapshots outcome link is set exactly once on row %', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$
"""

MEMBERSHIP_FUNCTION_SQL = """
CREATE FUNCTION fr_membership_activated() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') AND EXISTS (
        SELECT 1 FROM calibration_programs
        WHERE id = OLD.program_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'calibration_memberships of an active program are immutable: % refused on row %', TG_OP, OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') AND EXISTS (
        SELECT 1 FROM calibration_programs
        WHERE id = NEW.program_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'calibration_memberships of an active program are immutable: % refused on row %', TG_OP, NEW.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$
"""

IDENTITY_FUNCTION_SQL = """
CREATE FUNCTION fr_fragrance_assigned_identity() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.id, NEW.name, NEW.brand, NEW.concentration, NEW.launch_year,
        NEW.version_key, NEW.gender_target, NEW.primary_family, NEW.subfamily,
        NEW.intensity)
        IS DISTINCT FROM
       (OLD.id, OLD.name, OLD.brand, OLD.concentration, OLD.launch_year,
        OLD.version_key, OLD.gender_target, OLD.primary_family, OLD.subfamily,
        OLD.intensity)
       AND EXISTS (
        SELECT 1 FROM calibration_memberships WHERE fragrance_id = OLD.id
    ) THEN
        RAISE EXCEPTION 'fragrance % is assigned to calibration; its identity cannot change', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$
"""

# (trigger name, table, timing/events, function)
TRIGGERS: tuple[tuple[str, str, str, str], ...] = (
    (
        "trg_calibration_observations_append_only",
        OBSERVATIONS,
        "BEFORE UPDATE OR DELETE",
        "fr_observation_append_only",
    ),
    (
        "trg_calibration_checkpoints_frozen",
        "calibration_checkpoints",
        "BEFORE UPDATE OR DELETE",
        "fr_frozen_row",
    ),
    (
        "trg_calibration_checkpoint_predictions_frozen",
        "calibration_checkpoint_predictions",
        "BEFORE UPDATE OR DELETE",
        "fr_frozen_row",
    ),
    (
        "trg_feature_snapshots_frozen",
        "feature_snapshots",
        "BEFORE UPDATE OR DELETE",
        "fr_frozen_row",
    ),
    (
        "trg_prediction_snapshots_frozen",
        "prediction_snapshots",
        "BEFORE UPDATE OR DELETE",
        "fr_prediction_frozen",
    ),
    (
        "trg_calibration_memberships_activated",
        "calibration_memberships",
        "BEFORE INSERT OR UPDATE OR DELETE",
        "fr_membership_activated",
    ),
    (
        "trg_fragrances_assigned_identity",
        "fragrances",
        "BEFORE UPDATE",
        "fr_fragrance_assigned_identity",
    ),
)
FUNCTIONS: tuple[tuple[str, str], ...] = (
    ("fr_observation_append_only", OBSERVATION_FUNCTION_SQL),
    ("fr_frozen_row", FROZEN_FUNCTION_SQL),
    ("fr_prediction_frozen", PREDICTION_FUNCTION_SQL),
    ("fr_membership_activated", MEMBERSHIP_FUNCTION_SQL),
    ("fr_fragrance_assigned_identity", IDENTITY_FUNCTION_SQL),
)

# --- the view --------------------------------------------------------------
# Same rules as 620c8c861268's V_TRAINING_ROWS_SQL plus ``revealed`` and the
# controlled supersession rule (module docstring). Kept portable to SQLite:
# the unit suite builds the view from this constant.
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
    e.evaluated_at AS observed_at,
    CAST(1 AS BOOLEAN) AS revealed
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
    COALESCE(o.observed_at, o.created_at) AS observed_at,
    (en.revealed_at IS NOT NULL) AS revealed
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
  AND NOT EXISTS (
      SELECT 1
      FROM calibration_observations AS later
      WHERE later.presentation_id = o.presentation_id
        AND later.stage = o.stage
        AND later.phase = 'PRE_REVEAL'
        AND (
            later.created_at > o.created_at
            OR (later.created_at = o.created_at AND later.id > o.id)
        )
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

# 620c8c861268's definition, verbatim, for the downgrade.
V_TRAINING_ROWS_PR1_SQL = """
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

# X-06: the linkage the trainer view deliberately omits (role, hidden-repeat
# link, blind code, session, program), one row per observation, keyed by the
# same ``row_id`` as ``v_training_rows``. Only the manager endpoint
# ``GET /calibration/enrollments/{id}/linkage`` reads it.
V_MANAGER_LINKAGE_SQL = """
CREATE VIEW v_manager_linkage AS
SELECT
    o.id AS row_id,
    en.reviewer_id AS reviewer_id,
    en.id AS enrollment_id,
    en.program_id AS program_id,
    s.id AS session_id,
    p.id AS presentation_id,
    p.blind_code AS blind_code,
    m.id AS membership_id,
    m.fragrance_id AS fragrance_id,
    m.role AS role,
    m.repeat_of_id AS repeat_of_membership_id,
    o.stage AS stage,
    o.phase AS phase,
    o.training_eligibility AS training_eligibility
FROM calibration_observations AS o
JOIN calibration_presentations AS p ON p.id = o.presentation_id
JOIN calibration_memberships AS m ON m.id = p.membership_id
JOIN calibration_sessions AS s ON s.id = p.session_id
JOIN calibration_enrollments AS en ON en.id = s.enrollment_id
"""
DROP_V_MANAGER_LINKAGE_SQL = "DROP VIEW IF EXISTS v_manager_linkage"


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _keyed_observations(bind: sa.Connection) -> int:
    """Count observations whose idempotency key a downgrade would discard.

    Args:
        bind (sa.Connection): The migration connection.

    Returns:
        int: Rows with a non-NULL ``idempotency_key``.
    """
    return bind.execute(
        sa.select(sa.func.count())
        .select_from(sa.table(OBSERVATIONS))
        .where(sa.text("idempotency_key IS NOT NULL"))
    ).scalar_one()


def upgrade() -> None:
    """Drop the view, harden the schema, then recreate the views last."""
    op.execute(DROP_V_TRAINING_ROWS_SQL)

    if _is_postgresql():
        for table, column, nullable in JSON_COLUMNS:
            op.alter_column(
                table,
                column,
                existing_type=postgresql.JSON(),
                type_=postgresql.JSONB(),
                existing_nullable=nullable,
                postgresql_using=column + "::jsonb",
            )
        for table, column, _ in TIMESTAMP_DEFAULTS:
            op.alter_column(table, column, server_default=sa.text(UTC_NOW))

    with op.batch_alter_table(OBSERVATIONS) as batch_op:
        batch_op.add_column(
            sa.Column("idempotency_key", sa.String(length=64), nullable=True)
        )
        batch_op.create_unique_constraint(
            IDEMPOTENCY_UNIQUE, ["presentation_id", "idempotency_key"]
        )
        batch_op.create_check_constraint(
            IDEMPOTENCY_CHECK,
            "idempotency_key IS NULL OR "
            "(length(idempotency_key) >= 8 AND length(idempotency_key) <= 64)",
        )

    if _is_postgresql():
        for _, function_sql in FUNCTIONS:
            op.execute(function_sql)
        for name, table, events, function in TRIGGERS:
            op.execute(
                "CREATE TRIGGER "
                + name
                + " "
                + events
                + " ON "
                + table
                + " FOR EACH ROW EXECUTE FUNCTION "
                + function
                + "()"
            )

    op.execute(V_TRAINING_ROWS_SQL)
    op.execute(V_MANAGER_LINKAGE_SQL)


def downgrade() -> None:
    """Reverse the upgrade; refuse while idempotency keys would be lost.

    Raises:
        RuntimeError: When any observation carries an idempotency key.
    """
    keyed = _keyed_observations(op.get_bind())
    if keyed:
        msg = (
            f"Downgrading 4edb5c967539 would discard {keyed} observation "
            "idempotency key(s) recorded with evidence. Restore a verified "
            "pre-upgrade backup (docs/deployment/p1-release-readiness.md) "
            "instead."
        )
        raise RuntimeError(msg)

    op.execute(DROP_V_MANAGER_LINKAGE_SQL)
    op.execute(DROP_V_TRAINING_ROWS_SQL)

    if _is_postgresql():
        for name, table, _, _ in reversed(TRIGGERS):
            op.execute("DROP TRIGGER IF EXISTS " + name + " ON " + table)
        for function, _ in reversed(FUNCTIONS):
            op.execute("DROP FUNCTION IF EXISTS " + function + "()")

    with op.batch_alter_table(OBSERVATIONS) as batch_op:
        batch_op.drop_constraint(IDEMPOTENCY_CHECK, type_="check")
        batch_op.drop_constraint(IDEMPOTENCY_UNIQUE, type_="unique")
        batch_op.drop_column("idempotency_key")

    if _is_postgresql():
        for table, column, default in reversed(TIMESTAMP_DEFAULTS):
            op.alter_column(table, column, server_default=sa.text(default))
        for table, column, nullable in reversed(JSON_COLUMNS):
            op.alter_column(
                table,
                column,
                existing_type=postgresql.JSONB(),
                type_=postgresql.JSON(),
                existing_nullable=nullable,
                postgresql_using=column + "::json",
            )

    op.execute(V_TRAINING_ROWS_PR1_SQL)
