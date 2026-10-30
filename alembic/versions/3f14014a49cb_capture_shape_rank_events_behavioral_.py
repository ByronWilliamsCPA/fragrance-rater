"""Capture shape: rank events, behavioral events, session context, timing.

Revision ID: 3f14014a49cb
Revises: 000091664cdd
Create Date: 2026-10-30 17:13:48.210714

R7a PR 1 (ML structure review X-07 in part, X-08, X-09, X-14, X-22, X-23; ML
Decisions Q3, Q8; ADR-005 2026-09-19 amendment). Schema only: no service, API,
or instrument writes any of it yet. Purely additive; every new column on an
existing table is nullable and existing rows read NULL ("not recorded"). Nothing
is backfilled, because no existing value records any of these facts:
``CalibrationSession.created_at`` is schedule-generation time, not when a session
ran, and ``Membership.selection`` holds no per-presentation sample evidence.

New tables:

- ``calibration_session_contexts``: one row per session of self-reported
  conditions (illness, nasal congestion, allergy symptoms, hunger, hours since
  food and caffeine, personal fragrance worn, ambient odor, room temperature and
  humidity, refusable hormonal context). A refusal is ``prefer_not_to_answer``,
  never NULL.
- ``calibration_rank_events`` and ``calibration_rank_entries``: one ranking is one
  event over the session's presentations; an undetected sample is an entry with
  ``eligible_for_rank = false`` and no position. Ties share a position.
- ``behavioral_events``: append-only reviewer behavior for an exact version
  (sampled, wore, bought, finished, declined, ...), independent of
  recommendations.

New columns:

- ``calibration_sessions``: ``occurred_on``, ``started_at``, ``ended_at``,
  ``evaluator_timezone``.
- ``calibration_presentations``: ``presented_at`` (blotter), ``applied_at``,
  ``application_timezone``, ``application_method``, ``application_dose_sprays``
  (skin), and physical-sample provenance (``sample_source_type``,
  ``sample_container``, ``sample_volume_ml``, ``sample_acquired_on``,
  ``sample_decanted_on``, ``sample_opened_on``, ``sample_batch_code``,
  ``physical_sample_confirmed``).
- ``calibration_observations``: ``observed_at``, ``response_status``,
  ``recognition``, ``owned_or_worn``, ``scrubbed_off``, ``time_to_scrub_minutes``,
  ``last_detected_elapsed_min``, ``first_not_detected_elapsed_min``.
- ``evaluations``: ``recognition``, ``owned_or_worn``.

Judgment calls (the ADR-005 amendment governs where sources disagree):

- Familiarity follows the amendment, not the gap analysis's seven-value code:
  recognition (``new``, ``vaguely_familiar``, ``recognized_exact``) and
  owned-or-regularly-worn (``yes``, ``no``, ``unknown``) are separate columns.
  The existing 0-5 ``familiarity`` keeps its meaning as the optional "feels
  familiar" strength the amendment retains.
- No separate pairwise table. The amendment says a ranking is one dependent
  event, never independent pairwise rows; a pairwise judgment is a two-entry
  rank event.
- Response status uses the plan row's six codes. The capture assessment's
  ``not_asked_by_instrument`` and ``technical_failure`` are left out until an
  instrument version exists to give "not asked" evidence (R7a PR 2).
- Timestamps stay naive UTC like the rest of the schema, with an IANA zone
  column beside them, rather than introducing the first ``timestamptz``.
- No CHECK orders timestamps against each other (``ended_at >= started_at``):
  the capture assessment (13.3) says to keep and flag mistimed evidence, not
  reject it. Flags are R7a PR 2's deviation/quality-flag table.
- Season/setting, randomization, deviation flags, consent events, and
  ``instrument_version`` are R7a PR 2 and are not stubbed here.

Constraint names are the literal names the metadata naming convention gives the
models (R2, D-03). Nothing here imports application code.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f14014a49cb"
down_revision: str | Sequence[str] | None = "000091664cdd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTEXT_ANSWERS = "('yes', 'no', 'prefer_not_to_answer')"
_RECOGNITION = "('new', 'vaguely_familiar', 'recognized_exact')"
_OWNED_OR_WORN = "('yes', 'no', 'unknown')"

_NEW_TABLES = (
    "calibration_rank_entries",
    "calibration_rank_events",
    "calibration_session_contexts",
    "behavioral_events",
)
_NEW_COLUMNS: dict[str, tuple[str, ...]] = {
    "calibration_sessions": (
        "occurred_on",
        "started_at",
        "ended_at",
        "evaluator_timezone",
    ),
    "calibration_presentations": (
        "presented_at",
        "applied_at",
        "application_timezone",
        "application_method",
        "application_dose_sprays",
        "sample_source_type",
        "sample_container",
        "sample_volume_ml",
        "sample_acquired_on",
        "sample_decanted_on",
        "sample_opened_on",
        "sample_batch_code",
        "physical_sample_confirmed",
    ),
    "calibration_observations": (
        "observed_at",
        "response_status",
        "recognition",
        "owned_or_worn",
        "scrubbed_off",
        "time_to_scrub_minutes",
        "last_detected_elapsed_min",
        "first_not_detected_elapsed_min",
    ),
    "evaluations": ("recognition", "owned_or_worn"),
}
_NEW_CHECKS: dict[str, tuple[str, ...]] = {
    "calibration_presentations": (
        "ck_calibration_presentations_application_method_valid",
        "ck_calibration_presentations_application_dose_sprays_positive",
        "ck_calibration_presentations_sample_source_type_valid",
        "ck_calibration_presentations_sample_container_valid",
        "ck_calibration_presentations_sample_volume_ml_positive",
    ),
    "calibration_observations": (
        "ck_calibration_observations_response_status_valid",
        "ck_calibration_observations_not_detected_status",
        "ck_calibration_observations_recognition_valid",
        "ck_calibration_observations_owned_or_worn_valid",
        "ck_calibration_observations_scrub_time_nonnegative",
        "ck_calibration_observations_scrub_time_requires_scrub",
        "ck_calibration_observations_scrubbed_off_requires_skin",
        "ck_calibration_observations_last_detected_nonnegative",
        "ck_calibration_observations_first_not_detected_nonnegative",
        "ck_calibration_observations_longevity_interval_ordered",
    ),
    "evaluations": (
        "ck_evaluations_recognition_valid",
        "ck_evaluations_owned_or_worn_valid",
    ),
}


def _create_session_contexts() -> None:
    op.create_table(
        "calibration_session_contexts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("illness", sa.String(length=30), nullable=True),
        sa.Column("nasal_congestion", sa.String(length=30), nullable=True),
        sa.Column("allergy_symptoms", sa.String(length=30), nullable=True),
        sa.Column("hunger", sa.String(length=30), nullable=True),
        sa.Column("hours_since_food", sa.Float(), nullable=True),
        sa.Column("hours_since_caffeine", sa.Float(), nullable=True),
        sa.Column("personal_fragrance_worn", sa.String(length=30), nullable=True),
        sa.Column("ambient_odor", sa.String(length=30), nullable=True),
        sa.Column("ambient_odor_detail", sa.Text(), nullable=True),
        sa.Column("room_temperature_c", sa.Float(), nullable=True),
        sa.Column("room_humidity_pct", sa.Float(), nullable=True),
        sa.Column("hormonal_context", sa.String(length=30), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            f"illness IS NULL OR illness IN {_CONTEXT_ANSWERS}",
            name="ck_calibration_session_contexts_illness_valid",
        ),
        sa.CheckConstraint(
            f"nasal_congestion IS NULL OR nasal_congestion IN {_CONTEXT_ANSWERS}",
            name="ck_calibration_session_contexts_nasal_congestion_valid",
        ),
        sa.CheckConstraint(
            f"allergy_symptoms IS NULL OR allergy_symptoms IN {_CONTEXT_ANSWERS}",
            name="ck_calibration_session_contexts_allergy_symptoms_valid",
        ),
        sa.CheckConstraint(
            "hunger IS NULL OR hunger IN ('not_hungry', 'slightly_hungry', "
            "'hungry', 'very_hungry', 'prefer_not_to_answer')",
            name="ck_calibration_session_contexts_hunger_valid",
        ),
        sa.CheckConstraint(
            "hours_since_food IS NULL OR hours_since_food >= 0",
            name="ck_calibration_session_contexts_food_hours_nonnegative",
        ),
        sa.CheckConstraint(
            "hours_since_caffeine IS NULL OR hours_since_caffeine >= 0",
            name="ck_calibration_session_contexts_caffeine_hours_nonnegative",
        ),
        sa.CheckConstraint(
            "personal_fragrance_worn IS NULL OR personal_fragrance_worn IN "
            f"{_CONTEXT_ANSWERS}",
            name="ck_calibration_session_contexts_personal_fragrance_worn_valid",
        ),
        sa.CheckConstraint(
            f"ambient_odor IS NULL OR ambient_odor IN {_CONTEXT_ANSWERS}",
            name="ck_calibration_session_contexts_ambient_odor_valid",
        ),
        sa.CheckConstraint(
            "room_temperature_c IS NULL OR "
            "(room_temperature_c >= -10 AND room_temperature_c <= 50)",
            name="ck_calibration_session_contexts_room_temperature_c_range",
        ),
        sa.CheckConstraint(
            "room_humidity_pct IS NULL OR "
            "(room_humidity_pct >= 0 AND room_humidity_pct <= 100)",
            name="ck_calibration_session_contexts_room_humidity_pct_range",
        ),
        sa.CheckConstraint(
            "hormonal_context IS NULL OR hormonal_context IN "
            "('yes', 'no', 'prefer_not_to_answer', 'not_applicable')",
            name="ck_calibration_session_contexts_hormonal_context_valid",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["calibration_sessions.id"],
            name="fk_calibration_session_contexts_session_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_session_contexts"),
        sa.UniqueConstraint(
            "session_id", name="uq_calibration_session_contexts_session_id"
        ),
    )


def _create_rank_tables() -> None:
    op.create_table(
        "calibration_rank_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("criterion", sa.String(length=20), nullable=False),
        sa.Column("response_status", sa.String(length=20), nullable=False),
        sa.Column("ranked_at", sa.DateTime(), nullable=True),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "stage IN ('BLOTTER', 'SKIN')",
            name="ck_calibration_rank_events_stage_valid",
        ),
        sa.CheckConstraint(
            "phase IN ('PRE_REVEAL', 'PREVIOUSLY_REVEALED', 'POST_REVEAL')",
            name="ck_calibration_rank_events_phase_valid",
        ),
        sa.CheckConstraint(
            "criterion IN ('liking')",
            name="ck_calibration_rank_events_criterion_valid",
        ),
        sa.CheckConstraint(
            "response_status IN ('completed', 'skipped', 'unable_to_assess', "
            "'interrupted', 'invalidated')",
            name="ck_calibration_rank_events_response_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["calibration_sessions.id"],
            name="fk_calibration_rank_events_session_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_rank_events"),
    )
    op.create_index(
        "ix_calibration_rank_events_session_id",
        "calibration_rank_events",
        ["session_id"],
    )
    op.create_table(
        "calibration_rank_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rank_event_id", sa.String(length=36), nullable=False),
        sa.Column("presentation_id", sa.String(length=36), nullable=False),
        sa.Column("eligible_for_rank", sa.Boolean(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "rank_position IS NULL OR rank_position >= 1",
            name="ck_calibration_rank_entries_rank_position_positive",
        ),
        sa.CheckConstraint(
            "eligible_for_rank OR rank_position IS NULL",
            name="ck_calibration_rank_entries_ineligible_has_no_position",
        ),
        sa.ForeignKeyConstraint(
            ["rank_event_id"],
            ["calibration_rank_events.id"],
            name="fk_calibration_rank_entries_rank_event_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["presentation_id"],
            ["calibration_presentations.id"],
            name="fk_calibration_rank_entries_presentation_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_rank_entries"),
        sa.UniqueConstraint(
            "rank_event_id",
            "presentation_id",
            name="uq_calibration_rank_entries_rank_event_id_presentation_id",
        ),
    )
    op.create_index(
        "ix_calibration_rank_entries_presentation_id",
        "calibration_rank_entries",
        ["presentation_id"],
    )


def _create_behavioral_events() -> None:
    op.create_table(
        "behavioral_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=False),
        sa.Column("fragrance_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("evaluator_timezone", sa.String(length=64), nullable=True),
        sa.Column("size_ml", sa.Float(), nullable=True),
        sa.Column("price_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("decline_reason", sa.String(length=20), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("source_observation_id", sa.String(length=36), nullable=True),
        sa.Column("source_impression_id", sa.String(length=36), nullable=True),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('sampled', 'wore', 'rewore', 'wishlisted', "
            "'removed_from_wishlist', 'bought_sample', 'bought_decant', "
            "'bought_travel', 'bought_bottle', 'finished_sample', "
            "'finished_bottle', 'repurchased', 'returned', 'gifted', 'sold', "
            "'gave_away', 'declined')",
            name="ck_behavioral_events_event_type_valid",
        ),
        sa.CheckConstraint(
            "decline_reason IS NULL OR decline_reason IN ('price', "
            "'availability', 'performance', 'redundancy', 'other')",
            name="ck_behavioral_events_decline_reason_valid",
        ),
        sa.CheckConstraint(
            "decline_reason IS NULL OR event_type = 'declined'",
            name="ck_behavioral_events_decline_reason_requires_declined",
        ),
        sa.CheckConstraint(
            "size_ml IS NULL OR size_ml > 0",
            name="ck_behavioral_events_size_ml_positive",
        ),
        sa.CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0",
            name="ck_behavioral_events_price_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "price_amount IS NULL OR currency IS NOT NULL",
            name="ck_behavioral_events_price_requires_currency",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["reviewers.id"],
            name="fk_behavioral_events_reviewer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name="fk_behavioral_events_fragrance_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_observation_id"],
            ["calibration_observations.id"],
            name="fk_behavioral_events_source_observation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_impression_id"],
            ["recommendation_impressions.id"],
            name="fk_behavioral_events_source_impression_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_behavioral_events"),
    )
    for column in (
        "reviewer_id",
        "fragrance_id",
        "source_observation_id",
        "source_impression_id",
        "created_at",
    ):
        op.create_index(f"ix_behavioral_events_{column}", "behavioral_events", [column])


def _add_session_and_presentation_columns() -> None:
    with op.batch_alter_table("calibration_sessions") as batch_op:
        batch_op.add_column(sa.Column("occurred_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("ended_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("evaluator_timezone", sa.String(length=64), nullable=True)
        )

    with op.batch_alter_table("calibration_presentations") as batch_op:
        batch_op.add_column(sa.Column("presented_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("applied_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("application_timezone", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("application_method", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("application_dose_sprays", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("sample_source_type", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("sample_container", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(sa.Column("sample_volume_ml", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("sample_acquired_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("sample_decanted_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("sample_opened_on", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("sample_batch_code", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("physical_sample_confirmed", sa.Boolean(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_calibration_presentations_application_method_valid",
            "application_method IS NULL OR application_method IN "
            "('spray', 'dab', 'roll')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_presentations_application_dose_sprays_positive",
            "application_dose_sprays IS NULL OR application_dose_sprays > 0",
        )
        batch_op.create_check_constraint(
            "ck_calibration_presentations_sample_source_type_valid",
            "sample_source_type IS NULL OR sample_source_type IN "
            "('manufacturer_sample', 'official_discovery_set', 'retailer_sample', "
            "'decant', 'owned_bottle', 'unknown')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_presentations_sample_container_valid",
            "sample_container IS NULL OR sample_container IN "
            "('spray_atomizer', 'dab_vial', 'rollerball', 'retail_bottle')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_presentations_sample_volume_ml_positive",
            "sample_volume_ml IS NULL OR sample_volume_ml > 0",
        )


def _add_evidence_columns() -> None:
    with op.batch_alter_table("calibration_observations") as batch_op:
        batch_op.add_column(sa.Column("observed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("response_status", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("recognition", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("owned_or_worn", sa.String(length=10), nullable=True)
        )
        batch_op.add_column(sa.Column("scrubbed_off", sa.Boolean(), nullable=True))
        batch_op.add_column(
            sa.Column("time_to_scrub_minutes", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_detected_elapsed_min", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("first_not_detected_elapsed_min", sa.Integer(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_response_status_valid",
            "response_status IS NULL OR response_status IN ('completed', "
            "'not_detected', 'skipped', 'unable_to_assess', 'interrupted', "
            "'invalidated')",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_not_detected_status",
            "response_status IS NULL OR response_status <> 'not_detected' "
            "OR (detected IS NOT NULL AND NOT detected)",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_recognition_valid",
            f"recognition IS NULL OR recognition IN {_RECOGNITION}",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_owned_or_worn_valid",
            f"owned_or_worn IS NULL OR owned_or_worn IN {_OWNED_OR_WORN}",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_scrub_time_nonnegative",
            "time_to_scrub_minutes IS NULL OR time_to_scrub_minutes >= 0",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_scrub_time_requires_scrub",
            "time_to_scrub_minutes IS NULL "
            "OR (scrubbed_off IS NOT NULL AND scrubbed_off)",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_scrubbed_off_requires_skin",
            "scrubbed_off IS NULL OR stage = 'SKIN'",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_last_detected_nonnegative",
            "last_detected_elapsed_min IS NULL OR last_detected_elapsed_min >= 0",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_first_not_detected_nonnegative",
            "first_not_detected_elapsed_min IS NULL OR "
            "first_not_detected_elapsed_min >= 0",
        )
        batch_op.create_check_constraint(
            "ck_calibration_observations_longevity_interval_ordered",
            "last_detected_elapsed_min IS NULL "
            "OR first_not_detected_elapsed_min IS NULL "
            "OR first_not_detected_elapsed_min > last_detected_elapsed_min",
        )

    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.add_column(
            sa.Column("recognition", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("owned_or_worn", sa.String(length=10), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_evaluations_recognition_valid",
            f"recognition IS NULL OR recognition IN {_RECOGNITION}",
        )
        batch_op.create_check_constraint(
            "ck_evaluations_owned_or_worn_valid",
            f"owned_or_worn IS NULL OR owned_or_worn IN {_OWNED_OR_WORN}",
        )


def upgrade() -> None:
    """Add the R7a capture tables and columns; existing rows read NULL."""
    _create_session_contexts()
    _create_rank_tables()
    _create_behavioral_events()
    _add_session_and_presentation_columns()
    _add_evidence_columns()


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
    """Drop the R7a capture shape.

    Refuses when any of it holds data: captured context, rankings, timing, and
    behavior exist nowhere else.
    """
    bind = op.get_bind()
    found = _captured_data(bind)
    if found:
        msg = (
            "Downgrading 3f14014a49cb would discard captured evidence ("
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
    with op.batch_alter_table("calibration_sessions") as batch_op:
        for column in reversed(_NEW_COLUMNS["calibration_sessions"]):
            batch_op.drop_column(column)

    for column in (
        "created_at",
        "source_impression_id",
        "source_observation_id",
        "fragrance_id",
        "reviewer_id",
    ):
        op.drop_index(f"ix_behavioral_events_{column}", table_name="behavioral_events")
    op.drop_table("behavioral_events")
    op.drop_index(
        "ix_calibration_rank_entries_presentation_id",
        table_name="calibration_rank_entries",
    )
    op.drop_table("calibration_rank_entries")
    op.drop_index(
        "ix_calibration_rank_events_session_id", table_name="calibration_rank_events"
    )
    op.drop_table("calibration_rank_events")
    op.drop_table("calibration_session_contexts")
