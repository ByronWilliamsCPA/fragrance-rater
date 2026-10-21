"""Rename constraints and indexes to the naming convention.

Revision ID: 2c8c3971bfd8
Revises: a3f8c1d9e2b7
Create Date: 2026-10-02

Milestone R, sprint R2 (architecture review D-03, D-11). `Base.metadata` now
carries a naming convention (`fragrance_rater.core.database.NAMING_CONVENTION`),
so every constraint the ORM declares has a deterministic name. Databases
built by the migration chain instead carry PostgreSQL's invented names
(`<table>_pkey`, `<table>_<col>_fkey`, `<table>_<col>_check`,
`<table>_<cols>_key`) plus a few hand-chosen ones that predate the
convention. This migration renames all of them to the convention, so a
future migration can address any constraint by a name it can derive from
the model, and `tests/integration/test_schema_parity_postgres.py` can assert
names as well as structure.

It also reconciles the legacy `idx_*` indexes from `001_initial_schema`
(D-11): three are renamed to the names the ORM already declares, and
`idx_fragrance_accords_fragrance` is dropped because the
`(fragrance_id, accord_type)` primary key already serves every lookup on its
leading column.

Every operation is a catalog-only rename (no table rewrite, no data change)
except the one index drop. The rename list is frozen literal data, not
derived from the current models, so this migration means the same thing
however the models change later.

PostgreSQL only. The chain already cannot replay on SQLite (see
5d2e7c9f9c92 and `alembic/README`), and SQLite has no `RENAME CONSTRAINT`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c8c3971bfd8"
down_revision: str | Sequence[str] | None = "a3f8c1d9e2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, name produced by the chain through a3f8c1d9e2b7, convention name).
# Generated once from a PostgreSQL 16 database upgraded to a3f8c1d9e2b7 by
# matching each constraint to its ORM counterpart on table, kind, and
# columns (CHECKs on table and expression).
CONSTRAINT_RENAMES: tuple[tuple[str, str, str], ...] = (
    (
        "calibration_checkpoints",
        "calibration_checkpoints_enrollment_id_fkey",
        "fk_calibration_checkpoints_enrollment_id",
    ),
    (
        "calibration_checkpoints",
        "calibration_checkpoints_pkey",
        "pk_calibration_checkpoints",
    ),
    (
        "calibration_enrollments",
        "calibration_enrollments_program_id_fkey",
        "fk_calibration_enrollments_program_id",
    ),
    (
        "calibration_enrollments",
        "calibration_enrollments_reviewer_id_fkey",
        "fk_calibration_enrollments_reviewer_id",
    ),
    (
        "calibration_enrollments",
        "calibration_enrollments_pkey",
        "pk_calibration_enrollments",
    ),
    (
        "calibration_enrollments",
        "calibration_enrollments_program_id_reviewer_id_key",
        "uq_calibration_enrollments_program_id_reviewer_id",
    ),
    (
        "calibration_memberships",
        "calibration_memberships_fragrance_id_fkey",
        "fk_calibration_memberships_fragrance_id",
    ),
    (
        "calibration_memberships",
        "calibration_memberships_program_id_fkey",
        "fk_calibration_memberships_program_id",
    ),
    (
        "calibration_memberships",
        "calibration_memberships_repeat_of_id_fkey",
        "fk_calibration_memberships_repeat_of_id",
    ),
    (
        "calibration_memberships",
        "calibration_memberships_pkey",
        "pk_calibration_memberships",
    ),
    (
        "calibration_observations",
        "calibration_observations_check",
        "ck_calibration_observations_undetected_requires_zero_intensity",
    ),
    (
        "calibration_observations",
        "calibration_observations_elapsed_minutes_check",
        "ck_calibration_observations_elapsed_minutes_nonnegative",
    ),
    (
        "calibration_observations",
        "calibration_observations_intensity_check",
        "ck_calibration_observations_intensity_range",
    ),
    (
        "calibration_observations",
        "calibration_observations_liking_check",
        "ck_calibration_observations_liking_range",
    ),
    (
        "calibration_observations",
        "calibration_observations_presentation_id_fkey",
        "fk_calibration_observations_presentation_id",
    ),
    (
        "calibration_observations",
        "calibration_observations_pkey",
        "pk_calibration_observations",
    ),
    ("calibration_perfumers", "calibration_perfumers_pkey", "pk_calibration_perfumers"),
    (
        "calibration_perfumers",
        "calibration_perfumers_name_key",
        "uq_calibration_perfumers_name",
    ),
    (
        "calibration_presentations",
        "calibration_presentations_membership_id_fkey",
        "fk_calibration_presentations_membership_id",
    ),
    (
        "calibration_presentations",
        "calibration_presentations_session_id_fkey",
        "fk_calibration_presentations_session_id",
    ),
    (
        "calibration_presentations",
        "calibration_presentations_pkey",
        "pk_calibration_presentations",
    ),
    (
        "calibration_presentations",
        "calibration_presentations_blind_code_key",
        "uq_calibration_presentations_blind_code",
    ),
    (
        "calibration_presentations",
        "calibration_presentations_session_id_position_key",
        "uq_calibration_presentations_session_id_position",
    ),
    ("calibration_programs", "calibration_programs_pkey", "pk_calibration_programs"),
    (
        "calibration_programs",
        "calibration_programs_name_version_key",
        "uq_calibration_programs_name_version",
    ),
    (
        "calibration_sessions",
        "calibration_sessions_enrollment_id_fkey",
        "fk_calibration_sessions_enrollment_id",
    ),
    ("calibration_sessions", "calibration_sessions_pkey", "pk_calibration_sessions"),
    (
        "calibration_source_snapshots",
        "calibration_source_snapshots_fragrance_id_fkey",
        "fk_calibration_source_snapshots_fragrance_id",
    ),
    (
        "calibration_source_snapshots",
        "calibration_source_snapshots_pkey",
        "pk_calibration_source_snapshots",
    ),
    (
        "calibration_version_perfumers",
        "calibration_version_perfumers_fragrance_id_fkey",
        "fk_calibration_version_perfumers_fragrance_id",
    ),
    (
        "calibration_version_perfumers",
        "calibration_version_perfumers_perfumer_id_fkey",
        "fk_calibration_version_perfumers_perfumer_id",
    ),
    (
        "calibration_version_perfumers",
        "calibration_version_perfumers_pkey",
        "pk_calibration_version_perfumers",
    ),
    ("evaluations", "evaluations_fragrance_id_fkey", "fk_evaluations_fragrance_id"),
    ("evaluations", "evaluations_reviewer_id_fkey", "fk_evaluations_reviewer_id"),
    (
        "evaluations",
        "fk_evaluations_worn_by_reviewer_id_reviewers",
        "fk_evaluations_worn_by_reviewer_id",
    ),
    ("evaluations", "evaluations_pkey", "pk_evaluations"),
    (
        "fragella_lookups",
        "fragella_lookups_status_check",
        "ck_fragella_lookups_status_valid",
    ),
    (
        "fragella_lookups",
        "fragella_lookups_fragrance_id_fkey",
        "fk_fragella_lookups_fragrance_id",
    ),
    ("fragella_lookups", "fragella_lookups_pkey", "pk_fragella_lookups"),
    (
        "fragrance_accords",
        "fragrance_accords_fragrance_id_fkey",
        "fk_fragrance_accords_fragrance_id",
    ),
    ("fragrance_accords", "fragrance_accords_pkey", "pk_fragrance_accords"),
    (
        "fragrance_notes",
        "fragrance_notes_fragrance_id_fkey",
        "fk_fragrance_notes_fragrance_id",
    ),
    ("fragrance_notes", "fragrance_notes_note_id_fkey", "fk_fragrance_notes_note_id"),
    ("fragrance_notes", "fragrance_notes_pkey", "pk_fragrance_notes"),
    ("fragrances", "fragrances_pkey", "pk_fragrances"),
    (
        "llm_invocations",
        "llm_invocations_estimated_cost_usd_check",
        "ck_llm_invocations_estimated_cost_nonnegative",
    ),
    (
        "llm_invocations",
        "llm_invocations_latency_ms_check",
        "ck_llm_invocations_latency_ms_nonnegative",
    ),
    (
        "llm_invocations",
        "llm_invocations_impression_id_fkey",
        "fk_llm_invocations_impression_id",
    ),
    (
        "llm_invocations",
        "llm_invocations_reviewer_id_fkey",
        "fk_llm_invocations_reviewer_id",
    ),
    ("llm_invocations", "llm_invocations_pkey", "pk_llm_invocations"),
    ("notes", "notes_pkey", "pk_notes"),
    (
        "pilot_operational_events",
        "pilot_operational_events_event_type_check",
        "ck_pilot_operational_events_event_type_valid",
    ),
    (
        "pilot_operational_events",
        "pilot_operational_events_reviewer_id_fkey",
        "fk_pilot_operational_events_reviewer_id",
    ),
    (
        "pilot_operational_events",
        "pilot_operational_events_pkey",
        "pk_pilot_operational_events",
    ),
    (
        "prediction_snapshots",
        "ck_prediction_snapshot_outcome_linked_consistency",
        "ck_prediction_snapshots_outcome_linked_consistency",
    ),
    (
        "prediction_snapshots",
        "ck_prediction_snapshot_predicted_rating_finite",
        "ck_prediction_snapshots_predicted_rating_finite",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_check",
        "ck_prediction_snapshots_single_outcome_target",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_percentile_rank_check",
        "ck_prediction_snapshots_percentile_rank_range",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_uncertainty_check",
        "ck_prediction_snapshots_uncertainty_nonnegative",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_checkpoint_id_fkey",
        "fk_prediction_snapshots_checkpoint_id",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_fragrance_id_fkey",
        "fk_prediction_snapshots_fragrance_id",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_outcome_evaluation_id_fkey",
        "fk_prediction_snapshots_outcome_evaluation_id",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_outcome_observation_id_fkey",
        "fk_prediction_snapshots_outcome_observation_id",
    ),
    (
        "prediction_snapshots",
        "prediction_snapshots_reviewer_id_fkey",
        "fk_prediction_snapshots_reviewer_id",
    ),
    ("prediction_snapshots", "prediction_snapshots_pkey", "pk_prediction_snapshots"),
    (
        "recommendation_impressions",
        "recommendation_impressions_rank_check",
        "ck_recommendation_impressions_rank_positive",
    ),
    (
        "recommendation_impressions",
        "recommendation_impressions_score_value_check",
        "ck_recommendation_impressions_score_value_range",
    ),
    (
        "recommendation_impressions",
        "recommendation_impressions_fragrance_id_fkey",
        "fk_recommendation_impressions_fragrance_id",
    ),
    (
        "recommendation_impressions",
        "recommendation_impressions_run_id_fkey",
        "fk_recommendation_impressions_run_id",
    ),
    (
        "recommendation_impressions",
        "recommendation_impressions_pkey",
        "pk_recommendation_impressions",
    ),
    (
        "recommendation_impressions",
        "recommendation_impressions_run_id_fragrance_id_key",
        "uq_recommendation_impressions_run_id_fragrance_id",
    ),
    (
        "recommendation_impressions",
        "recommendation_impressions_run_id_rank_key",
        "uq_recommendation_impressions_run_id_rank",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_check",
        "ck_recommendation_response_revisions_single_outcome_target",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_revision_check",
        "ck_recommendation_response_revisions_revision_positive",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_sampling_state_check",
        "ck_recommendation_response_revisions_sampling_state_valid",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_impression_id_fkey",
        "fk_recommendation_response_revisions_impression_id",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_outcome_evaluation_id_fkey",
        "fk_recommendation_response_revisions_outcome_evaluation_id",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_outcome_observation_id_fkey",
        "fk_recommendation_response_revisions_outcome_observation_id",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_pkey",
        "pk_recommendation_response_revisions",
    ),
    (
        "recommendation_response_revisions",
        "recommendation_response_revisions_impression_id_revision_key",
        "uq_recommendation_response_revisions_impression_id_revision",
    ),
    (
        "recommendation_runs",
        "recommendation_runs_reviewer_id_fkey",
        "fk_recommendation_runs_reviewer_id",
    ),
    ("recommendation_runs", "recommendation_runs_pkey", "pk_recommendation_runs"),
    ("reviewers", "reviewers_pkey", "pk_reviewers"),
    (
        "training_eligibilities",
        "training_eligibilities_pkey",
        "pk_training_eligibilities",
    ),
)

# (old index, new index) for legacy 001_initial_schema indexes the ORM
# declares under convention names.
INDEX_RENAMES: tuple[tuple[str, str], ...] = (
    ("idx_evaluations_reviewer_fragrance", "ix_evaluations_reviewer_id_fragrance_id"),
    ("idx_fragrance_notes_fragrance", "ix_fragrance_notes_fragrance_id"),
    ("idx_fragrance_notes_note", "ix_fragrance_notes_note_id"),
)


def _require_postgresql() -> None:
    dialect = op.get_bind().dialect.name
    if dialect != "postgresql":
        msg = (
            f"Migration {revision} supports PostgreSQL only (got {dialect!r}); "
            "see alembic/README."
        )
        raise RuntimeError(msg)


def upgrade() -> None:
    """Rename every constraint and legacy index to the naming convention.

    #CRITICAL: data-integrity: assumes the database was built by this
    repository's migration chain, so every old name exists exactly as listed.
    #VERIFY: a missing name fails the RENAME and PostgreSQL's transactional
    DDL rolls the whole migration back, leaving the schema unchanged rather
    than half-renamed; the parity test proves the result matches the models.
    """
    _require_postgresql()
    for table, old, new in CONSTRAINT_RENAMES:
        op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old}" TO "{new}"')
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX "{old}" RENAME TO "{new}"')
    op.drop_index("idx_fragrance_accords_fragrance", table_name="fragrance_accords")


def downgrade() -> None:
    """Restore the names (and the dropped index) the chain produced before."""
    _require_postgresql()
    op.create_index(
        "idx_fragrance_accords_fragrance", "fragrance_accords", ["fragrance_id"]
    )
    for old, new in reversed(INDEX_RENAMES):
        op.execute(f'ALTER INDEX "{new}" RENAME TO "{old}"')
    for table, old, new in reversed(CONSTRAINT_RENAMES):
        op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{new}" TO "{old}"')
