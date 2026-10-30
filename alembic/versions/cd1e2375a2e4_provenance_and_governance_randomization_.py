"""Provenance and governance: randomization, quality flags, consent, instrument version, season and setting fit.

Revision ID: cd1e2375a2e4
Revises: 3f14014a49cb
Create Date: 2026-10-30 18:17:29.775940

R7a PR 2 (capture assessment 13.2, 13.3, 13.6, 13.7, 13.11, 18.5; ML Decisions
Q9; PROJECT-PLAN R7a row). Schema only, except that program activation now
writes ``instrument_version``. Purely additive: every new column on an existing
table is nullable and existing rows read NULL ("not recorded"). Nothing is
backfilled.

New tables:

- ``calibration_quality_flags``: append-only protocol-deviation and data-quality
  flags on exactly one session, presentation, or observation. Capture
  assessment 13.3/13.6 and PR 1's decision: mistimed or deviant evidence is kept
  and flagged, never rejected, so no CHECK here or elsewhere refuses a row for
  being out of order or mistimed. A flag is ``raised`` once; a later row whose
  ``supersedes_id`` names it ``resolved`` it (with a ``disposition``) or
  ``invalidated`` it. Rows are never updated.
- ``consent_events``: append-only ``granted``/``withdrawn`` events per evaluator
  and scope, with the consent text version and digest and the consent time.
  Scopes cover 13.11's sensitive session-context answers and 18.5's
  contribution state (household research, aggregate reporting, model
  training, research export). This is the consent contract that
  ``calibration_session_contexts`` (3f14014a49cb) waits for.

New columns:

- ``calibration_programs.instrument_version``: the participant instrument in
  force at activation (13.2); only activation writes it.
- ``calibration_enrollments.randomization_algorithm`` and
  ``randomization_seed``: the schedule's randomization record.
- ``calibration_presentations.intended_position``: the slot the randomization
  assigned.
- ``calibration_observations.season_fit`` and ``setting_fit``: Q9's blind
  suitability labels, skin stage only.

Judgment calls:

- Randomization lives on the enrollment, not the session or the presentation.
  ``CalibrationService.enroll`` generates an enrollment's whole schedule in one
  pass (shuffle, place hidden repeats, shuffle holdouts, chunk into sessions),
  so there is one algorithm and one seed per schedule; repeating them on every
  session would only invite disagreement. The per-presentation fact, the
  assigned slot, is ``intended_position`` beside the existing ``position``.
  Actual smelling order is evidenced by ``presented_at``; a mismatch is a
  ``out_of_order_presentation`` flag, so ``intended_position`` deliberately has
  no uniqueness or equality CHECK. ``randomization_seed`` is NULL for an
  unseedable algorithm (today's ``SystemRandom`` shuffle), which is why it is a
  separate column from the algorithm rather than required with it.
- Q9 over the plan row's wording. The R7a row says "scenario/season and
  setting lookup columns"; Q9 (the later, more specific decision) says two
  fields, ``season_fit`` and ``setting_fit``, on skin-stage rows only. They
  are two CHECKed code columns (the R7a convention, not lookup tables) on
  ``calibration_observations``, where the blind phase and stage are recorded;
  a CHECK keeps them off blotter rows. Requiredness on skin rows is the
  instrument's (R7b), not a CHECK, so pre-R7b and skipped rows stay legal.
- Season/setting codes are the instrument v0.5 SK-SEASON/SK-SETTING option
  codes, stored as one best-fit code per field. v0.5 lets an evaluator pick
  several seasons; Q9 asks for two coarse fields counted for completeness per
  skin row, and a single code is CHECKable portably and enters a model as one
  low-cardinality effect (capture assessment section 10). A multi-select
  answer would need a child table, which can be added later without touching
  these columns.
- Quality flags take exactly one target. A presentation-level flag is not
  repeated on its session; the session is reachable by join.
- Consent is one row per scope, not one row with a flag per scope, so a single
  scope can be withdrawn without restating the others.

Constraint names are the literal names the metadata naming convention gives the
models (R2, D-03). Nothing here imports application code.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd1e2375a2e4"
down_revision: str | Sequence[str] | None = "3f14014a49cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = ("calibration_quality_flags", "consent_events")
_NEW_COLUMNS: dict[str, tuple[str, ...]] = {
    "calibration_programs": ("instrument_version",),
    "calibration_enrollments": ("randomization_algorithm", "randomization_seed"),
    "calibration_presentations": ("intended_position",),
    "calibration_observations": ("season_fit", "setting_fit"),
}
_NEW_CHECKS: dict[str, tuple[str, ...]] = {
    "calibration_programs": (
        "ck_calibration_programs_instrument_version_requires_active",
        "ck_calibration_programs_instrument_version_nonblank",
    ),
    "calibration_enrollments": (
        "ck_calibration_enrollments_seed_requires_algorithm",
        "ck_calibration_enrollments_randomization_algorithm_nonblank",
    ),
    "calibration_presentations": (
        "ck_calibration_presentations_intended_position_positive",
    ),
    "calibration_observations": (
        "ck_calibration_observations_season_fit_valid",
        "ck_calibration_observations_setting_fit_valid",
        "ck_calibration_observations_season_fit_requires_skin",
        "ck_calibration_observations_setting_fit_requires_skin",
    ),
}
_FLAG_INDEXES = ("session_id", "presentation_id", "observation_id", "supersedes_id")
_CONSENT_INDEXES = ("reviewer_id", "enrollment_id")


def _create_quality_flags() -> None:
    op.create_table(
        "calibration_quality_flags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("presentation_id", sa.String(length=36), nullable=True),
        sa.Column("observation_id", sa.String(length=36), nullable=True),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("disposition", sa.String(length=10), nullable=False),
        sa.Column("rule_version", sa.String(length=100), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "action IN ('raised', 'resolved', 'invalidated')",
            name="ck_calibration_quality_flags_action_valid",
        ),
        sa.CheckConstraint(
            "code IN ('out_of_order_presentation', 'outside_planned_window', "
            "'timestamp_inconsistent', 'daily_load_exceeded', "
            "'minimum_spacing_violated', 'clean_air_break_missed', 'interrupted', "
            "'sample_substitution', 'sample_spill', 'mislabel_suspected', "
            "'competing_odor', 'recorder_assistance', 'instrument_fault', "
            "'evaluator_reported_problem', 'other')",
            name="ck_calibration_quality_flags_code_valid",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'minor', 'major')",
            name="ck_calibration_quality_flags_severity_valid",
        ),
        sa.CheckConstraint(
            "source IN ('automatic_validation', 'evaluator', 'recorder', 'manager')",
            name="ck_calibration_quality_flags_source_valid",
        ),
        sa.CheckConstraint(
            "disposition IN ('review', 'include', 'exclude')",
            name="ck_calibration_quality_flags_disposition_valid",
        ),
        sa.CheckConstraint(
            "(CASE WHEN session_id IS NULL THEN 0 ELSE 1 END) "
            "+ (CASE WHEN presentation_id IS NULL THEN 0 ELSE 1 END) "
            "+ (CASE WHEN observation_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_calibration_quality_flags_one_target",
        ),
        sa.CheckConstraint(
            "(action = 'raised' AND supersedes_id IS NULL) "
            "OR (action <> 'raised' AND supersedes_id IS NOT NULL)",
            name="ck_calibration_quality_flags_supersedes_matches_action",
        ),
        sa.CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id",
            name="ck_calibration_quality_flags_not_self_superseding",
        ),
        sa.CheckConstraint(
            "source <> 'automatic_validation' "
            "OR (rule_version IS NOT NULL AND TRIM(rule_version) <> '')",
            name="ck_calibration_quality_flags_automatic_requires_rule",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["calibration_sessions.id"],
            name="fk_calibration_quality_flags_session_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["presentation_id"],
            ["calibration_presentations.id"],
            name="fk_calibration_quality_flags_presentation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["calibration_observations.id"],
            name="fk_calibration_quality_flags_observation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["calibration_quality_flags.id"],
            name="fk_calibration_quality_flags_supersedes_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_quality_flags"),
    )
    for column in _FLAG_INDEXES:
        op.create_index(
            f"ix_calibration_quality_flags_{column}",
            "calibration_quality_flags",
            [column],
        )


def _create_consent_events() -> None:
    op.create_table(
        "consent_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("enrollment_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("consent_text_version", sa.String(length=100), nullable=True),
        sa.Column("consent_text_sha256", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('granted', 'withdrawn')",
            name="ck_consent_events_event_type_valid",
        ),
        sa.CheckConstraint(
            "scope IN ('session_context', 'household_research', "
            "'aggregate_reporting', 'model_training', 'research_export')",
            name="ck_consent_events_scope_valid",
        ),
        sa.CheckConstraint(
            "event_type <> 'granted' OR (consent_text_version IS NOT NULL "
            "AND TRIM(consent_text_version) <> '')",
            name="ck_consent_events_grant_requires_text_version",
        ),
        sa.CheckConstraint(
            "consent_text_sha256 IS NULL OR length(consent_text_sha256) = 64",
            name="ck_consent_events_consent_text_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["reviewers.id"],
            name="fk_consent_events_reviewer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["calibration_enrollments.id"],
            name="fk_consent_events_enrollment_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consent_events"),
    )
    for column in _CONSENT_INDEXES:
        op.create_index(f"ix_consent_events_{column}", "consent_events", [column])


def _add_columns() -> None:
    with op.batch_alter_table("calibration_programs") as batch_op:
        batch_op.add_column(
            sa.Column("instrument_version", sa.String(length=100), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_calibration_programs_instrument_version_requires_active",
            "instrument_version IS NULL OR status = 'active'",
        )
        batch_op.create_check_constraint(
            "ck_calibration_programs_instrument_version_nonblank",
            "instrument_version IS NULL OR TRIM(instrument_version) <> ''",
        )

    with op.batch_alter_table("calibration_enrollments") as batch_op:
        batch_op.add_column(
            sa.Column("randomization_algorithm", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("randomization_seed", sa.String(length=128), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_calibration_enrollments_seed_requires_algorithm",
            "randomization_seed IS NULL OR randomization_algorithm IS NOT NULL",
        )
        batch_op.create_check_constraint(
            "ck_calibration_enrollments_randomization_algorithm_nonblank",
            "randomization_algorithm IS NULL OR TRIM(randomization_algorithm) <> ''",
        )

    with op.batch_alter_table("calibration_presentations") as batch_op:
        batch_op.add_column(sa.Column("intended_position", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_calibration_presentations_intended_position_positive",
            "intended_position IS NULL OR intended_position >= 1",
        )

    with op.batch_alter_table("calibration_observations") as batch_op:
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


def upgrade() -> None:
    """Add the R7a provenance and governance shape; existing rows read NULL."""
    _create_quality_flags()
    _create_consent_events()
    _add_columns()


def _captured_data(bind: sa.Connection) -> list[str]:
    """Name every new table or column that holds data a downgrade would drop."""
    found: list[str] = []
    for table in _NEW_TABLES:
        count = bind.execute(
            sa.select(sa.func.count()).select_from(sa.table(table))
        ).scalar_one()
        if count:
            found.append(f"{table}: {count} row(s)")
    for table, columns in _NEW_COLUMNS.items():
        for column in columns:
            count = bind.execute(
                sa.select(sa.func.count())
                .select_from(sa.table(table))
                .where(sa.column(column).is_not(None))
            ).scalar_one()
            if count:
                found.append(f"{table}.{column}: {count} non-NULL row(s)")
    return found


def downgrade() -> None:
    """Drop the R7a provenance and governance shape.

    Refuses when any of it holds data: consent history, deviation flags, the
    randomization record, and the instrument version exist nowhere else.

    Raises:
        RuntimeError: If any new table has rows or any new column is non-NULL.
    """
    bind = op.get_bind()
    found = _captured_data(bind)
    if found:
        msg = (
            "Downgrading cd1e2375a2e4 would discard recorded provenance ("
            + "; ".join(found)
            + "). Restore a verified pre-upgrade backup "
            "(docs/deployment/p1-release-readiness.md) instead."
        )
        raise RuntimeError(msg)

    for table, checks in _NEW_CHECKS.items():
        with op.batch_alter_table(table) as batch_op:
            for check in checks:
                batch_op.drop_constraint(check, type_="check")
            for column in reversed(_NEW_COLUMNS[table]):
                batch_op.drop_column(column)

    for column in reversed(_CONSENT_INDEXES):
        op.drop_index(f"ix_consent_events_{column}", table_name="consent_events")
    op.drop_table("consent_events")
    for column in reversed(_FLAG_INDEXES):
        op.drop_index(
            f"ix_calibration_quality_flags_{column}",
            table_name="calibration_quality_flags",
        )
    op.drop_table("calibration_quality_flags")
