"""Controlled measurement records sharing the existing version catalog."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import SchemaItem

from fragrance_rater.core.database import Base, portable_json
from fragrance_rater.core.vocabulary import (
    DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY,
    EVIDENCE_TRAINING_ELIGIBILITIES,
)
from fragrance_rater.utils.timestamps import now_naive_utc


def identifier() -> str:
    """Return an opaque identifier."""
    return str(uuid4())


def quoted(values: tuple[str, ...]) -> str:
    """Return ``values`` as a SQL list body: ``'a', 'b'``.

    Args:
        values (tuple[str, ...]): The codes, in their stored spelling.

    Returns:
        str: The comma-separated, single-quoted list without parentheses.
    """
    return ", ".join(f"'{value}'" for value in values)


def in_check(column: str, values: tuple[str, ...], *, nullable: bool = True) -> str:
    """Return a CHECK expression limiting ``column`` to a closed vocabulary.

    Args:
        column (str): Column name as written in SQL.
        values (tuple[str, ...]): The legal codes, in their stored spelling.
        nullable (bool): Whether NULL (not recorded) is also legal.

    Returns:
        str: A SQL expression usable in ``CheckConstraint`` and in migrations.
    """
    listed = quoted(values)
    if nullable:
        return f"{column} IS NULL OR {column} IN ({listed})"
    return f"{column} IN ({listed})"


# R7a closed vocabularies. Each tuple is the single source of the stored codes;
# migration 3f14014a49cb writes the same lists literally (R2 rule: migrations do
# not import models).
# #ASSUME: data-integrity: the parity test compares CHECK names, not their
# expressions, so a code added here but not in a migration passes it silently.
# #VERIFY: a unit test asserts each tuple matches the migration's literal list.

# ADR-005 2026-09-19 amendment, "Familiarity" row: recognition is categorical and
# separate from prior ownership/exposure. The existing 0-5 ``familiarity`` column
# keeps its meaning as the optional "feels familiar" strength.
RECOGNITION_CODES: tuple[str, ...] = ("new", "vaguely_familiar", "recognized_exact")
# Same row: "has owned or regularly worn this fragrance: yes / no / unknown".
OWNED_OR_WORN_CODES: tuple[str, ...] = ("yes", "no", "unknown")
# PROJECT-PLAN R7a row; preference-prediction-data-capture-assessment 13.4.
RESPONSE_STATUSES: tuple[str, ...] = (
    "completed",
    "not_detected",
    "skipped",
    "unable_to_assess",
    "interrupted",
    "invalidated",
)
# A rank event is never "not detected": an undetected sample is an ineligible
# entry, and fewer than two eligible samples means no event at all.
RANK_EVENT_STATUSES: tuple[str, ...] = tuple(
    status for status in RESPONSE_STATUSES if status != "not_detected"
)
RANK_CRITERIA: tuple[str, ...] = ("liking",)
STAGES: tuple[str, ...] = ("BLOTTER", "SKIN")
PHASES: tuple[str, ...] = ("PRE_REVEAL", "PREVIOUSLY_REVEALED", "POST_REVEAL")
# data-model-gap-analysis section 5 ("Sample/source types", "Container/delivery
# format"), stored as CHECKed codes rather than lookup tables.
SAMPLE_SOURCE_TYPES: tuple[str, ...] = (
    "manufacturer_sample",
    "official_discovery_set",
    "retailer_sample",
    "decant",
    "owned_bottle",
    "unknown",
)
SAMPLE_CONTAINERS: tuple[str, ...] = (
    "spray_atomizer",
    "dab_vial",
    "rollerball",
    "retail_bottle",
)
APPLICATION_METHODS: tuple[str, ...] = ("spray", "dab", "roll")
# Session-context answers that must stay refusable (ADR-005 amendment,
# "Session-context fields" row; capture assessment 13.11).
CONTEXT_ANSWERS: tuple[str, ...] = ("yes", "no", "prefer_not_to_answer")
HORMONAL_CONTEXT_ANSWERS: tuple[str, ...] = (*CONTEXT_ANSWERS, "not_applicable")
HUNGER_LEVELS: tuple[str, ...] = (
    "not_hungry",
    "slightly_hungry",
    "hungry",
    "very_hungry",
    "prefer_not_to_answer",
)

# R7a PR 2 closed vocabularies; migration cd1e2375a2e4 writes the same lists
# literally (same #ASSUME/#VERIFY as above).

# ML Decisions Q9: a blind, coarse suitability judgment on skin-stage rows. The
# option codes are the instrument v0.5 SK-SEASON/SK-SETTING codes; the instrument
# is multi-select, so each ticked option is one ``FitChoice`` row.
SEASON_FIT_CODES: tuple[str, ...] = (
    "spring",
    "summer",
    "fall",
    "winter",
    "year_round",
    "none",
    "cannot_judge",
)
SETTING_FIT_CODES: tuple[str, ...] = (
    "work_school",
    "home",
    "social_outing",
    "formal_event",
    "outdoor_activity",
    "other",
    "none",
    "cannot_judge",
)
FIT_DIMENSIONS: tuple[str, ...] = ("season", "setting")
FIT_CODE_CHECK = f"(dimension = 'season' AND code IN ({quoted(SEASON_FIT_CODES)})) OR (dimension = 'setting' AND code IN ({quoted(SETTING_FIT_CODES)}))"
# Capture assessment 13.6 (deviations) and 13.3 (mistimed evidence). A flag
# describes what happened; it never removes or rewrites the flagged evidence.
QUALITY_FLAG_CODES: tuple[str, ...] = (
    "out_of_order_presentation",
    "outside_planned_window",
    "timestamp_inconsistent",
    "daily_load_exceeded",
    "minimum_spacing_violated",
    "clean_air_break_missed",
    "interrupted",
    "sample_substitution",
    "sample_spill",
    "mislabel_suspected",
    "competing_odor",
    "recorder_assistance",
    "instrument_fault",
    "evaluator_reported_problem",
    "other",
)
# Append-only lifecycle: a flag is raised once; a later row resolves it (with a
# disposition) or invalidates it (raised in error). Nothing is updated.
QUALITY_FLAG_ACTIONS: tuple[str, ...] = ("raised", "resolved", "invalidated")
QUALITY_FLAG_SEVERITIES: tuple[str, ...] = ("info", "minor", "major")
# Capture assessment 13.7: "automatic validation, evaluator, recorder, or manager".
QUALITY_FLAG_SOURCES: tuple[str, ...] = (
    "automatic_validation",
    "evaluator",
    "recorder",
    "manager",
)
# Capture assessment 13.6: "an explicit include/exclude/review disposition".
QUALITY_FLAG_DISPOSITIONS: tuple[str, ...] = ("review", "include", "exclude")

# R8 closed vocabularies and CHECK bodies; migration 620c8c861268 writes the
# same lists literally (same #ASSUME/#VERIFY as the R7a block above).

# X-05: the per-row evidence gate, shared with ``Evaluation``. The vocabulary
# and its conservative default live in ``core/vocabulary.py``.
TRAINING_ELIGIBILITY_CHECK = in_check(
    "training_eligibility", EVIDENCE_TRAINING_ELIGIBILITIES, nullable=False
)

# ADR-012 2026-09-15 amendment and issue #130. The ``source_type`` and
# ``permission_state`` vocabularies are the amendment's own lists.
SOURCE_TYPES: tuple[str, ...] = (
    "project_owned",
    "manufacturer_provided",
    "open_licensed",
    "bounded_lookup",
    "excluded_legacy",
)
PERMISSION_STATES: tuple[str, ...] = (
    "retain_and_train",
    "retain_for_qc_only",
    "excluded_no_new_writes",
)
# #ASSUME: data-integrity: the amendment maps each source type to the widest
# permission it may carry: project-owned, manufacturer-provided, and
# open-licensed facts may be retained and trained on; a bounded lookup is
# QC-only; a legacy Parfumo row is excluded. A narrower grant is always
# allowed (an unattributed or scope-limited manufacturer reply "should not"
# default to retain_and_train, per ADR-012's Context), a wider one never is.
# #VERIFY: test_r8_provenance.py asserts every pair outside this
# table fails at flush.
SOURCE_PERMISSION_PAIRS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("project_owned", ("retain_and_train", "retain_for_qc_only")),
    ("manufacturer_provided", ("retain_and_train", "retain_for_qc_only")),
    ("open_licensed", ("retain_and_train", "retain_for_qc_only")),
    ("bounded_lookup", ("retain_for_qc_only",)),
    ("excluded_legacy", ("excluded_no_new_writes",)),
)
SOURCE_PERMISSION_PAIR_CHECK = " OR ".join(
    f"(source_type = '{source}' AND permission_state IN ({quoted(states)}))"
    for source, states in SOURCE_PERMISSION_PAIRS
)
# ADR-012: ``fields`` names the ``Fragrance`` facts a snapshot evidences. The
# allow-list is the facts a house can confirm (``schemas/house_review.py``'s
# ``ConfirmableField``, which already covers the legacy backfill's
# ``concentration``, ``launch_year``, and ``brand``) plus ``gtin``, the barcode
# fact ``CalibrationService`` reads from snapshot payloads and
# ``fragrance_gtins`` links back to its snapshot.
SOURCE_EVIDENCE_FIELDS: tuple[str, ...] = (
    "name",
    "brand",
    "line",
    "concentration",
    "launch_year",
    "market_status",
    "gender_target",
    "gtin",
)


def json_string_array_check(column: str, values: tuple[str, ...]) -> str:
    """Return a portable CHECK that a JSON column is an array drawn from ``values``.

    ``jsonb`` containment is PostgreSQL-only and SQLite has no JSON array
    operators in a CHECK, so this requires exactly one ``[`` and one ``]``
    (a flat array), strips every allowed quoted value, then the array
    punctuation and spaces, from the column's text and requires nothing to
    remain. Anything else (an unknown or misspelled name, a nested array, an
    object, an escaped quote, a JSON ``null``) leaves a residue and fails. An
    empty array passes: a snapshot may support barcodes or attributions alone.

    Args:
        column (str): Column name as written in SQL.
        values (tuple[str, ...]): The legal array elements.

    Returns:
        str: A SQL expression usable in ``CheckConstraint`` and in migrations.
    """
    stripped = f"CAST({column} AS TEXT)"
    for value in values:
        stripped = f"REPLACE({stripped}, '\"{value}\"', '')"
    for punctuation in ("[", "]", ",", " "):
        stripped = f"REPLACE({stripped}, '{punctuation}', '')"
    as_text = f"CAST({column} AS TEXT)"
    return (
        f"ltrim({as_text}) LIKE '[%' "
        f"AND length({as_text}) - length(REPLACE({as_text}, '[', '')) = 1 "
        f"AND length({as_text}) - length(REPLACE({as_text}, ']', '')) = 1 "
        f"AND {stripped} = ''"
    )


def sha256_hex_check(column: str) -> str:
    """Return a portable CHECK that ``column`` is NULL or a lowercase SHA-256 hex.

    ``TRIM(x, chars)`` removes every leading and trailing character in
    ``chars`` on both SQLite and PostgreSQL, so a 64-character value that
    trims to the empty string is made only of lowercase hex digits.

    Args:
        column (str): Column name as written in SQL.

    Returns:
        str: A SQL expression usable in ``CheckConstraint`` and in migrations.
    """
    return (
        f"{column} IS NULL OR (length({column}) = 64 "
        f"AND TRIM({column}, '0123456789abcdef') = '')"
    )


def json_shape_check(column: str, opener: str) -> str:
    """Return a portable CHECK that a nullable JSON column starts with ``opener``.

    Same technique as ``perceived_notes_is_array``: ``[`` for an array, ``{``
    for an object.

    Args:
        column (str): Column name as written in SQL.
        opener (str): ``[`` or ``{``.

    Returns:
        str: A SQL expression usable in ``CheckConstraint`` and in migrations.
    """
    return f"{column} IS NULL OR ltrim(CAST({column} AS TEXT)) LIKE '{opener}%'"


# M-08 and ADR-009's declared learning problem: what a checkpoint may predict,
# each on its own original scale. ``rating`` is the ordinary 1-5 outcome and is
# never mapped onto liking.
CHECKPOINT_TARGET_SCALES: tuple[tuple[str, str], ...] = (
    ("liking", "0-10"),
    ("would_wear", "0-10"),
    ("would_buy", "0-10"),
    ("rating", "1-5"),
)
CHECKPOINT_TARGETS: tuple[str, ...] = tuple(t for t, _ in CHECKPOINT_TARGET_SCALES)
PREDICTION_SCALES: tuple[str, ...] = ("0-10", "1-5")


class Program(Base):
    """Immutable protocol definition once activated.

    R7a column:
        instrument_version: The participant instrument (questionnaire wording,
            anchors, requiredness, skip logic) in force when the program was
            activated, written once by activation (capture assessment 13.2).
            NULL on programs activated before R7a and on every draft.
    """

    __tablename__ = "calibration_programs"
    __table_args__ = (
        UniqueConstraint("name", "version"),
        # D-15: activation and enrollment gate on these exact strings.
        CheckConstraint("status IN ('draft', 'active')", name="status_valid"),
        # Only activation writes it, so a draft never carries one.
        CheckConstraint(
            "instrument_version IS NULL OR status = 'active'",
            name="instrument_version_requires_active",
        ),
        CheckConstraint(
            "instrument_version IS NULL OR TRIM(instrument_version) <> ''",
            name="instrument_version_nonblank",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    locked_at: Mapped[datetime | None]
    instrument_version: Mapped[str | None] = mapped_column(String(100), nullable=True)


MEMBERSHIP_ROLES: tuple[str, ...] = (
    "UNIVERSAL_BASELINE",
    "HIDDEN_REPEAT",
    "HOLDOUT",
    "ACTIVE_LEARNING",
    "RETEST",
    "OWNED_VALIDATION",
    "OTHER",
)
_ROLE_CHECK = "role IN (" + ", ".join(f"'{role}'" for role in MEMBERSHIP_ROLES) + ")"


class Membership(Base):
    """Version-resolved stimulus with concealed experimental role."""

    __tablename__ = "calibration_memberships"
    # D-15/X-25: `role = 'HOLDOUT'` is the leakage-prevention mechanism, so a
    # misspelled role would make a holdout trainable. Keep in sync with
    # schemas.calibration.Role (a unit test asserts the two agree).
    __table_args__ = (CheckConstraint(_ROLE_CHECK, name="role_valid"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_programs.id", ondelete="RESTRICT"), index=True
    )
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(30))
    repeat_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_memberships.id", ondelete="RESTRICT"), index=True
    )
    group_name: Mapped[str] = mapped_column(String(200), default="Baseline")
    selection: Mapped[dict[str, object]] = mapped_column(portable_json(), default=dict)


class Enrollment(Base):
    """Per-evaluator reveal gate and explicit recorder grants.

    An enrollment owns its whole session schedule: ``CalibrationService.enroll``
    shuffles, places repeats, and chunks every presentation into sessions in
    one pass. The randomization record therefore lives here, once per
    schedule, and each presentation's assigned slot lives on ``Presentation``.

    R7a columns (NULL on enrollments generated before R7a):
        randomization_algorithm: Versioned name of the ordering algorithm that
            generated the schedule.
        randomization_seed: The seed that reproduces the schedule. NULL when
            the algorithm is not seedable (the current ``SystemRandom``
            shuffle is not), so NULL with an algorithm means "not
            reproducible", not "unknown".
    """

    __tablename__ = "calibration_enrollments"
    __table_args__ = (
        UniqueConstraint("program_id", "reviewer_id"),
        CheckConstraint(
            "randomization_seed IS NULL OR randomization_algorithm IS NOT NULL",
            name="seed_requires_algorithm",
        ),
        CheckConstraint(
            "randomization_algorithm IS NULL OR TRIM(randomization_algorithm) <> ''",
            name="randomization_algorithm_nonblank",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_programs.id", ondelete="RESTRICT")
    )
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    recorder_usernames: Mapped[list[str]] = mapped_column(portable_json())
    skin_plan_locked_at: Mapped[datetime | None]
    revealed_at: Mapped[datetime | None]
    revealed_by: Mapped[str | None] = mapped_column(String(255))
    randomization_algorithm: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    randomization_seed: Mapped[str | None] = mapped_column(String(128), nullable=True)


class CalibrationSession(Base):
    """Ordered session; capacity is protocol data rather than a constant.

    ``created_at`` is schedule-generation time: every session in an enrollment
    shares it (ML structure review X-08). The R7a columns record when the
    session actually ran. All are NULL on rows written before R7a and on any
    session not yet run; nothing derives them from ``created_at``.

    R7a columns:
        occurred_on: Evaluator-local calendar date the session ran (protocol
            day). Stored, not derived, so a session that crosses midnight or a
            missing ``started_at`` still has a day.
        started_at: Actual session start, naive UTC like every other
            timestamp in this schema.
        ended_at: Actual session end, naive UTC.
        evaluator_timezone: IANA zone name (``America/Chicago``) used to read
            ``started_at``/``ended_at`` and the session's blotter
            ``presented_at``/``observed_at`` values as local time. Time of day
            is derived from it, not stored.
    """

    __tablename__ = "calibration_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_enrollments.id", ondelete="RESTRICT"), index=True
    )
    context: Mapped[dict[str, object]] = mapped_column(portable_json(), default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    # #ASSUME: data-integrity: an IANA name cannot be validated by a portable
    # CHECK, and a timestamp ordering CHECK (ended_at >= started_at) would
    # reject real but mistimed evidence that the capture assessment (13.3)
    # says to keep and flag instead.
    # #VERIFY: the R7a service validates the zone with zoneinfo before writing.
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    evaluator_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SessionContext(Base):
    """Self-reported conditions for one session (ADR-005 2026-09-19 amendment).

    Kept in its own table rather than in ``CalibrationSession.context`` (an
    untyped JSON object that no code writes) or as session columns, because
    these answers are health-adjacent: a separate row can be access-controlled,
    exported, and deleted on withdrawal without touching the session's
    evidence. ``CalibrationSession.context`` is left as it is.

    NULL in any answer column means "not asked or not recorded". A refusal is
    the explicit ``prefer_not_to_answer`` code, never NULL, so the two stay
    distinguishable (ADR-005: hormonal context is "optional and refusable").
    Time of day is not stored; it derives from the session's ``started_at`` and
    ``evaluator_timezone``.
    """

    __tablename__ = "calibration_session_contexts"
    # #CRITICAL: security: these columns hold illness, allergy, and hormonal
    # context. Capture assessment 13.11 and the remediation plan section 18 say
    # not to collect them before a consent contract (consent text/version and
    # timestamp) exists. That precondition now exists: the ``consent_events``
    # table (models/consent.py, migration cd1e2375a2e4). No write path exists
    # yet; R7b adds one.
    # #VERIFY: the R7b write path refuses a context row unless the reviewer's
    # latest ``session_context`` consent event is ``granted`` (a withdrawal
    # stops further writes), and no sensitive field is required to finish a
    # session.
    __table_args__: tuple[SchemaItem, ...] = (
        UniqueConstraint("session_id"),
        CheckConstraint(in_check("illness", CONTEXT_ANSWERS), name="illness_valid"),
        CheckConstraint(
            in_check("nasal_congestion", CONTEXT_ANSWERS),
            name="nasal_congestion_valid",
        ),
        CheckConstraint(
            in_check("allergy_symptoms", CONTEXT_ANSWERS),
            name="allergy_symptoms_valid",
        ),
        CheckConstraint(in_check("hunger", HUNGER_LEVELS), name="hunger_valid"),
        CheckConstraint(
            "hours_since_food IS NULL OR hours_since_food >= 0",
            name="food_hours_nonnegative",
        ),
        CheckConstraint(
            "hours_since_caffeine IS NULL OR hours_since_caffeine >= 0",
            name="caffeine_hours_nonnegative",
        ),
        CheckConstraint(
            in_check("personal_fragrance_worn", CONTEXT_ANSWERS),
            name="personal_fragrance_worn_valid",
        ),
        CheckConstraint(
            in_check("ambient_odor", CONTEXT_ANSWERS), name="ambient_odor_valid"
        ),
        CheckConstraint(
            "room_temperature_c IS NULL OR (room_temperature_c >= -10 AND room_temperature_c <= 50)",
            name="room_temperature_c_range",
        ),
        CheckConstraint(
            "room_humidity_pct IS NULL OR (room_humidity_pct >= 0 AND room_humidity_pct <= 100)",
            name="room_humidity_pct_range",
        ),
        CheckConstraint(
            in_check("hormonal_context", HORMONAL_CONTEXT_ANSWERS),
            name="hormonal_context_valid",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="RESTRICT")
    )
    illness: Mapped[str | None] = mapped_column(String(30), nullable=True)
    nasal_congestion: Mapped[str | None] = mapped_column(String(30), nullable=True)
    allergy_symptoms: Mapped[str | None] = mapped_column(String(30), nullable=True)
    hunger: Mapped[str | None] = mapped_column(String(30), nullable=True)
    hours_since_food: Mapped[float | None] = mapped_column(Float, nullable=True)
    hours_since_caffeine: Mapped[float | None] = mapped_column(Float, nullable=True)
    personal_fragrance_worn: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    ambient_odor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ambient_odor_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    room_humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    hormonal_context: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)


class Presentation(Base):
    """A concealed presentation; repeats have independent random codes.

    R7a adds when and how the stimulus actually reached the evaluator, and
    which physical sample it came from (ML structure review X-08, X-09). Every
    such column is nullable: NULL means "not recorded", which is the truth for
    every row written before R7a. ``position`` remains the actual position.

    Blotter and skin are two exposures of one presentation. "Presented" names
    the blotter exposure and "application" names the skin exposure.

    R7a columns:
        presented_at: When the blotter was first smelled, naive UTC; local
            time reads through the session's ``evaluator_timezone``.
        applied_at: When the sample was applied to skin, naive UTC.
        application_timezone: IANA zone for ``applied_at`` and the skin
            observations of this wear, which can fall on a later day and in a
            different place than the blotter session.
        application_method: How it was applied to skin.
        application_dose_sprays: Sprays (or dabs) applied to skin.
        sample_source_type: Where the physical sample came from.
        sample_container: The container the sample was presented from.
        sample_volume_ml: Nominal volume of that container.
        sample_acquired_on: Date the household obtained the sample.
        sample_decanted_on: Date it was decanted, when it is a decant.
        sample_opened_on: Date the container was first opened.
        sample_batch_code: Batch or lot code printed on the source, verbatim.
        physical_sample_confirmed: The operator confirmed that the physical
            sample matches the membership's version (P1.1 validator's
            ``physical_sample_confirmed``, which had no column).
        intended_position: The 1-based position in the session that the
            enrollment's randomization assigned, written once at schedule
            generation and never changed. ``position`` is the order the
            presentation is shown in; the order it was actually smelled is
            evidenced by ``presented_at``. Any mismatch is kept and flagged
            (``out_of_order_presentation``), never corrected in place.
    """

    __tablename__ = "calibration_presentations"
    __table_args__ = (
        UniqueConstraint("session_id", "position"),
        UniqueConstraint("blind_code"),
        # Not unique per session: a deviation must stay recordable, and a CHECK
        # comparing it to ``position`` would reject the evidence it exists for.
        CheckConstraint(
            "intended_position IS NULL OR intended_position >= 1",
            name="intended_position_positive",
        ),
        CheckConstraint(
            in_check("application_method", APPLICATION_METHODS),
            name="application_method_valid",
        ),
        CheckConstraint(
            "application_dose_sprays IS NULL OR application_dose_sprays > 0",
            name="application_dose_sprays_positive",
        ),
        CheckConstraint(
            in_check("sample_source_type", SAMPLE_SOURCE_TYPES),
            name="sample_source_type_valid",
        ),
        CheckConstraint(
            in_check("sample_container", SAMPLE_CONTAINERS),
            name="sample_container_valid",
        ),
        CheckConstraint(
            "sample_volume_ml IS NULL OR sample_volume_ml > 0",
            name="sample_volume_ml_positive",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="RESTRICT"), index=True
    )
    membership_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_memberships.id", ondelete="RESTRICT"), index=True
    )
    blind_code: Mapped[str] = mapped_column(String(24))
    position: Mapped[int] = mapped_column(Integer)
    skin_reason: Mapped[str | None] = mapped_column(Text)
    blotter_locked_at: Mapped[datetime | None]
    skin_locked_at: Mapped[datetime | None]

    # Exposure timing (X-08). Client-clock times, not server receipt.
    presented_at: Mapped[datetime | None] = mapped_column(nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(nullable=True)
    application_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    application_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    application_dose_sprays: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Physical-sample provenance (X-09; gap analysis section 6, step 6).
    sample_source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sample_container: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sample_volume_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sample_decanted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sample_opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sample_batch_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    physical_sample_confirmed: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    # Randomization record (capture assessment 13.6); see ``Enrollment``.
    intended_position: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Observation(Base):
    """Append-only submitted response; post-reveal never replaces blind data.

    Every field below (other than the identity/timing columns and the R7a
    capture columns at the end) mirrors a
    field of ``schemas.calibration.ResponseInput`` one-for-one by name, so
    ``calibration_service.observe()`` can populate them by splatting
    ``data.model_dump()`` rather than maintaining a second, drift-prone list.
    These used to be flattened into one untyped ``responses`` JSON column;
    that buried validated, ML-relevant values (``would_wear``, sensory
    dimensions, ``perceived_notes``, ...) where they could not be indexed,
    constrained, or queried, and where the frozen training manifest in
    ``preference_history.py`` could only forward them onward as an opaque
    blob. They are now first-class, individually bounded columns so this
    data is directly usable as ML features/labels without a parsing step.
    ``perceived_notes`` stays a JSON array of free-text labels rather than a
    join against ``Note`` (full normalization is a separate, larger change);
    ``likes``/``dislikes``/``reminds_me_of``/``comments`` stay raw text,
    preserved unchanged even if a future LLM extraction pipeline derives
    structured values from them elsewhere.
    """

    __tablename__ = "calibration_observations"
    __table_args__ = (
        CheckConstraint(
            "liking IS NULL OR (liking >= 0 AND liking <= 10)",
            name="liking_range",
        ),
        CheckConstraint(
            "intensity IS NULL OR (intensity >= 0 AND intensity <= 5)",
            name="intensity_range",
        ),
        CheckConstraint(
            "detected IS NULL OR detected OR (intensity = 0 AND intensity IS NOT NULL AND liking IS NULL)",
            name="undetected_requires_zero_intensity",
        ),
        CheckConstraint("elapsed_minutes >= 0", name="elapsed_minutes_nonnegative"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 5)",
            name="confidence_range",
        ),
        CheckConstraint(
            "sweetness IS NULL OR (sweetness >= 0 AND sweetness <= 5)",
            name="sweetness_range",
        ),
        CheckConstraint(
            "freshness IS NULL OR (freshness >= 0 AND freshness <= 5)",
            name="freshness_range",
        ),
        CheckConstraint(
            "density IS NULL OR (density >= 0 AND density <= 5)",
            name="density_range",
        ),
        CheckConstraint(
            "familiarity IS NULL OR (familiarity >= 0 AND familiarity <= 5)",
            name="familiarity_range",
        ),
        CheckConstraint(
            "dryness IS NULL OR (dryness >= 0 AND dryness <= 5)",
            name="dryness_range",
        ),
        CheckConstraint(
            "clean_soapy IS NULL OR (clean_soapy >= 0 AND clean_soapy <= 5)",
            name="clean_soapy_range",
        ),
        CheckConstraint(
            "earthy_rooty IS NULL OR (earthy_rooty >= 0 AND earthy_rooty <= 5)",
            name="earthy_rooty_range",
        ),
        CheckConstraint(
            "bodily_animalic IS NULL OR (bodily_animalic >= 0 AND bodily_animalic <= 5)",
            name="bodily_animalic_range",
        ),
        CheckConstraint(
            "discomfort IS NULL OR (discomfort >= 0 AND discomfort <= 5)",
            name="discomfort_range",
        ),
        CheckConstraint(
            "opening_liking IS NULL OR (opening_liking >= 0 AND opening_liking <= 10)",
            name="opening_liking_range",
        ),
        CheckConstraint(
            "drydown_liking IS NULL OR (drydown_liking >= 0 AND drydown_liking <= 10)",
            name="drydown_liking_range",
        ),
        CheckConstraint(
            "would_wear IS NULL OR (would_wear >= 0 AND would_wear <= 10)",
            name="would_wear_range",
        ),
        CheckConstraint(
            "would_buy IS NULL OR (would_buy >= 0 AND would_buy <= 10)",
            name="would_buy_range",
        ),
        CheckConstraint(
            "artistic_appreciation IS NULL OR "
            "(artistic_appreciation >= 0 AND artistic_appreciation <= 10)",
            name="artistic_appreciation_range",
        ),
        CheckConstraint(
            "projection IS NULL OR (projection >= 0 AND projection <= 5)",
            name="projection_range",
        ),
        CheckConstraint(
            "longevity_minutes IS NULL OR longevity_minutes >= 0",
            name="longevity_minutes_nonnegative",
        ),
        # `perceived_notes` is `jsonb` on PostgreSQL since R8 PR 2 (D-12) but
        # plain `JSON` on SQLite, and neither PostgreSQL's `jsonb_typeof` nor
        # SQLite's `json_type` exists on the other engine, so
        # neither name is portable to both engines this repo runs against
        # (PostgreSQL in production per ADR-001, SQLite in this repo's
        # migration and unit tests). Casting to text and checking the
        # (whitespace-trimmed) leading character is portable to both and is
        # exact for any valid JSON array. Keep this in sync with the
        # matching `op.create_check_constraint` in
        # alembic/versions/9ded7f54996c_ml_prediction_snapshots.py.
        CheckConstraint(
            "perceived_notes IS NULL OR ltrim(CAST(perceived_notes AS TEXT)) LIKE '[%'",
            name="perceived_notes_is_array",
        ),
        # D-15: Stage and the phase values CalibrationService writes.
        CheckConstraint("stage IN ('BLOTTER', 'SKIN')", name="stage_valid"),
        CheckConstraint(
            "phase IN ('PRE_REVEAL', 'PREVIOUSLY_REVEALED', 'POST_REVEAL')",
            name="phase_valid",
        ),
        # R7a. Closed vocabularies; NULL means "not recorded" (every pre-R7a row).
        CheckConstraint(
            in_check("response_status", RESPONSE_STATUSES),
            name="response_status_valid",
        ),
        # #ASSUME: data-integrity: `not_detected` is the status form of the
        # existing non-detection rule (detected = false, intensity 0, liking
        # NULL), so it must agree with `detected`. Only this direction is
        # enforced: an `interrupted` or `invalidated` row may carry any
        # detection answer it got before it stopped.
        # #VERIFY: unit test that not_detected with detected true/NULL fails.
        CheckConstraint(
            "response_status IS NULL OR response_status <> 'not_detected' OR (detected IS NOT NULL AND NOT detected)",
            name="not_detected_status",
        ),
        CheckConstraint(
            in_check("recognition", RECOGNITION_CODES), name="recognition_valid"
        ),
        CheckConstraint(
            in_check("owned_or_worn", OWNED_OR_WORN_CODES),
            name="owned_or_worn_valid",
        ),
        CheckConstraint(
            "time_to_scrub_minutes IS NULL OR time_to_scrub_minutes >= 0",
            name="scrub_time_nonnegative",
        ),
        CheckConstraint(
            "time_to_scrub_minutes IS NULL OR (scrubbed_off IS NOT NULL AND scrubbed_off)",
            name="scrub_time_requires_scrub",
        ),
        # A blotter cannot be scrubbed off; X-22 is about skin wear.
        CheckConstraint(
            "scrubbed_off IS NULL OR stage = 'SKIN'",
            name="scrubbed_off_requires_skin",
        ),
        CheckConstraint(
            "last_detected_elapsed_min IS NULL OR last_detected_elapsed_min >= 0",
            name="last_detected_nonnegative",
        ),
        CheckConstraint(
            "first_not_detected_elapsed_min IS NULL OR first_not_detected_elapsed_min >= 0",
            name="first_not_detected_nonnegative",
        ),
        # Interval-censored longevity: the scent was gone at the later bound.
        CheckConstraint(
            "last_detected_elapsed_min IS NULL OR first_not_detected_elapsed_min IS NULL OR first_not_detected_elapsed_min > last_detected_elapsed_min",
            name="longevity_interval_ordered",
        ),
        # R8 (X-05): see ``training_eligibility`` below.
        CheckConstraint(TRAINING_ELIGIBILITY_CHECK, name="training_eligibility_valid"),
        # R8 PR 2 (D-22, Q18): one submission per client key per presentation.
        # NULL keys never collide (NULLs are distinct on both engines), so a
        # pre-R8 row or a keyless client is unaffected and genuine repeats
        # with fresh keys stay recordable.
        UniqueConstraint("presentation_id", "idempotency_key"),
        CheckConstraint(
            "idempotency_key IS NULL OR (length(idempotency_key) >= 8 AND length(idempotency_key) <= 64)",
            name="idempotency_key_length",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    presentation_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_presentations.id", ondelete="RESTRICT"), index=True
    )
    stage: Mapped[str] = mapped_column(String(20))
    phase: Mapped[str] = mapped_column(String(20))
    elapsed_minutes: Mapped[int] = mapped_column(Integer, default=0)
    detected: Mapped[bool | None] = mapped_column(Boolean)
    intensity: Mapped[int | None] = mapped_column(Integer)
    liking: Mapped[int | None] = mapped_column(Integer)

    # Structured evaluator perception (published-vs-perceived stays distinct:
    # these are always what the evaluator reported, never a catalog fact).
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sweetness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    freshness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    density: Mapped[int | None] = mapped_column(Integer, nullable=True)
    familiarity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dryness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clean_soapy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earthy_rooty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bodily_animalic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discomfort: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Temporal liking and performance.
    opening_liking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drydown_liking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    would_wear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    would_buy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artistic_appreciation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    projection: Mapped[int | None] = mapped_column(Integer, nullable=True)
    longevity_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Perceived notes and raw free text (see class docstring).
    # #CRITICAL: data-integrity: SQLAlchemy's JSON type defaults to
    # `none_as_null=False`, which would serialize a Python `None` value as
    # the literal JSON text `"null"` on write rather than a SQL NULL. The
    # `ck_calibration_observations_perceived_notes_is_array` CHECK
    # constraint (see `__table_args__` above) only special-cases actual SQL
    # NULL, so an un-set `perceived_notes` would otherwise violate its own
    # constraint. `none_as_null=True` makes Python `None` map to SQL NULL,
    # matching what the constraint and the rest of this codebase assume.
    # #VERIFY: keep this in sync with the matching `sa.JSON(none_as_null=True)`
    # (jsonb on PostgreSQL since R8 PR 2's `JSONB(none_as_null=True)` variant)
    # in alembic/versions/9ded7f54996c_ml_prediction_snapshots.py.
    perceived_notes: Mapped[list[str] | None] = mapped_column(
        portable_json(none_as_null=True), nullable=True
    )
    likes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dislikes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminds_me_of: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    recorded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)

    # R7a capture shape (ADR-005 2026-09-19 amendment; X-08, X-14, X-22). These
    # are not yet fields of ``ResponseInput``; the R7a service PR adds them.
    # Until then ``observe()`` leaves them NULL, which reads as "not recorded".
    # When the evaluator actually made this observation (client clock, naive
    # UTC); ``created_at`` stays server receipt and ``elapsed_minutes`` stays
    # the submitted value, kept for audit.
    observed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Why a required answer is or is not present. NULL on pre-R7a rows.
    response_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Recognition and prior ownership/exposure are separate constructs; the
    # 0-5 ``familiarity`` above stays as the optional "feels familiar" strength.
    recognition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    owned_or_worn: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Skin-wear summary, reported on the skin observation that closes the wear
    # (same placement as ``longevity_minutes``). Longevity is interval-censored:
    # the scent was last detected at one elapsed minute and first missed at a
    # later one. ``longevity_minutes`` keeps its meaning for existing rows.
    scrubbed_off: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    time_to_scrub_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_detected_elapsed_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    first_not_detected_elapsed_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # R8 (X-05): whether this row may train a model. Every row starts
    # ``unreviewed`` and only ``eligible`` rows reach ``v_training_rows``; the
    # structural rules (holdout, hidden repeat, pre-reveal, stage lock) are
    # applied by the view on top of this code, never instead of it.
    training_eligibility: Mapped[str] = mapped_column(
        String(20),
        default=DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY,
        server_default=DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY,
    )
    # R8 PR 2 (D-22, Q18): the client's key for this submission, stable across
    # retries of the same submission and fresh for a new one. A replay with
    # the same key returns this row instead of appending a second one.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FitChoice(Base):
    """One blind season or setting suitability answer on a skin observation.

    ML Decisions Q9 asks, at skin stage only, which seasons and which settings
    the fragrance suits. The instrument offers multi-select, and the owner
    confirmed multi-select (2026-10-30), so each ticked option is one row here
    instead of a code column on ``Observation``.

    Columns:
        id: Primary key.
        observation_id: The skin observation the answer belongs to.
        dimension: ``season`` or ``setting``.
        code: The ticked option, from ``SEASON_FIT_CODES`` or
            ``SETTING_FIT_CODES`` according to ``dimension``.
        created_at: Row creation time.
    """

    __tablename__ = "calibration_fit_choices"
    __table_args__: tuple[SchemaItem, ...] = (
        UniqueConstraint("observation_id", "dimension", "code"),
        CheckConstraint(
            in_check("dimension", FIT_DIMENSIONS, nullable=False),
            name="dimension_valid",
        ),
        CheckConstraint(FIT_CODE_CHECK, name="code_valid"),
    )
    # #ASSUME: data-integrity: a fit choice belongs to a SKIN-stage observation,
    # and "none"/"cannot_judge" stand alone. Neither can be a portable CHECK
    # (they read another table or other rows), so observe() enforces both.
    # #VERIFY: tests/unit/test_services/test_fit_choices.py.

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_observations.id", ondelete="RESTRICT"), index=True
    )
    dimension: Mapped[str] = mapped_column(String(10))
    code: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)


class RankEvent(Base):
    """One end-of-session ranking over the session's eligible presentations.

    The ADR-005 2026-09-19 amendment ("Ranking" row) and ML Decisions Q8 decide
    that a ranking is one dependent event, analyzed with a rank-ordered
    likelihood, never stored as independent pairwise rows. This table is the
    ``PairwiseComparison``/rank-event of the R7a plan row: a single pairwise
    judgment is a rank event with two entries, so no separate pairwise table
    exists.

    Append-only like ``Observation``: a correction invalidates an event
    (``response_status = 'invalidated'``) and records a new one; nothing is
    updated in place.

    Columns:
        session_id: The session whose presentations were ranked.
        stage: Which exposure was ranked (blotter at end of session today).
        phase: Disclosure state when ranked, same codes as ``Observation``;
            a pre-reveal ranking is never replaced by a post-reveal one.
        criterion: What the order means. Only ``liking`` today.
        response_status: ``completed`` or why the ranking is incomplete.
        ranked_at: When the evaluator ranked (client clock, naive UTC).
        recorded_by: Who was at the keyboard (may differ from the evaluator).
        created_at: Server receipt time.
    """

    __tablename__ = "calibration_rank_events"
    # #ASSUME: data-integrity: the amendment says to omit the event entirely
    # when fewer than two samples in the session were detected, and every
    # entry's presentation must belong to `session_id`. Neither is expressible
    # as a portable CHECK across tables.
    # #VERIFY: the R7a service refuses both; tests listed in the PR notes.
    __table_args__: tuple[SchemaItem, ...] = (
        CheckConstraint(in_check("stage", STAGES, nullable=False), name="stage_valid"),
        CheckConstraint(in_check("phase", PHASES, nullable=False), name="phase_valid"),
        CheckConstraint(
            in_check("criterion", RANK_CRITERIA, nullable=False),
            name="criterion_valid",
        ),
        CheckConstraint(
            in_check("response_status", RANK_EVENT_STATUSES, nullable=False),
            name="response_status_valid",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="RESTRICT"), index=True
    )
    stage: Mapped[str] = mapped_column(String(20))
    phase: Mapped[str] = mapped_column(String(20))
    criterion: Mapped[str] = mapped_column(String(20))
    response_status: Mapped[str] = mapped_column(String(20))
    ranked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)


class RankEntry(Base):
    """One presentation's place in a rank event.

    Every presentation shown in the ranked session gets an entry, eligible or
    not, so an export can tell "not ranked because not detected" from "not
    shown". An ineligible entry (the sample was not detected) never has a
    position: forcing it into the order would invent a preference.

    Ties share a position (1, 1, 3), so ``rank_position`` is deliberately not
    unique within an event.
    """

    __tablename__ = "calibration_rank_entries"
    __table_args__: tuple[SchemaItem, ...] = (
        UniqueConstraint("rank_event_id", "presentation_id"),
        CheckConstraint(
            "rank_position IS NULL OR rank_position >= 1",
            name="rank_position_positive",
        ),
        CheckConstraint(
            "eligible_for_rank OR rank_position IS NULL",
            name="ineligible_has_no_position",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    rank_event_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_rank_events.id", ondelete="RESTRICT")
    )
    presentation_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_presentations.id", ondelete="RESTRICT"), index=True
    )
    eligible_for_rank: Mapped[bool] = mapped_column(Boolean)
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)


# Exactly one of the three target columns is set.
_ONE_FLAG_TARGET = "(CASE WHEN session_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN presentation_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN observation_id IS NULL THEN 0 ELSE 1 END) = 1"


class QualityFlag(Base):
    """A protocol deviation or data-quality flag on calibration evidence.

    Capture assessment 13.3, 13.6, and 13.7: mistimed or deviant evidence is
    kept and flagged, never rejected or overwritten. No CHECK anywhere in the
    calibration schema rejects a row for being out of order or mistimed; this
    table is where that fact is recorded. A flag describes what happened;
    whether a flagged row enters a given analysis is a separate, versioned
    eligibility decision (R8), not this table's.

    Append-only. A flag is ``raised`` once. A later row with ``supersedes_id``
    pointing at it either ``resolved`` it (carrying the final
    ``disposition``) or ``invalidated`` it (it was raised in error). Nothing is
    updated in place. Every row names the same target and code as the flag it
    supersedes, so any row can be read on its own.

    Columns:
        session_id: Flagged session; exactly one target column is set.
        presentation_id: Flagged presentation.
        observation_id: Flagged observation.
        supersedes_id: For ``resolved`` and ``invalidated`` rows, the flag
            row this one closes; NULL exactly when ``action`` is ``raised``.
        action: ``raised``, ``resolved``, or ``invalidated``.
        code: What departed from protocol or looks wrong.
        severity: ``info``, ``minor``, or ``major``.
        source: Who or what raised it.
        disposition: ``review`` (undecided), ``include``, or ``exclude``.
        training_outcome: On a ``resolved`` row, the manager's decision for the
            rows the flag made ``questionable`` (``eligible``, ``withheld`` or
            ``invalidated``); NULL when the resolution left them for a manager
            to decide, and on every row that is not a resolution.
        rule_version: The validation rule and version that raised an
            automatic flag; required when ``source`` is
            ``automatic_validation``.
        explanation: Free text from whoever recorded the row.
        occurred_at: When the deviation happened, when known (client clock,
            naive UTC).
        recorded_by: Who was at the keyboard.
        created_at: Server receipt time.
    """

    __tablename__ = "calibration_quality_flags"
    # #ASSUME: data-integrity: a superseding row names the same target and
    # code as the flag it closes, and supersedes a ``raised`` row, not another
    # resolution. Neither is expressible as a portable CHECK (it compares two
    # rows).
    # #VERIFY: the write path (R7b) copies target and code from the superseded
    # row and refuses to supersede a non-``raised`` row.
    __table_args__: tuple[SchemaItem, ...] = (
        CheckConstraint(
            in_check("action", QUALITY_FLAG_ACTIONS, nullable=False),
            name="action_valid",
        ),
        CheckConstraint(
            in_check("code", QUALITY_FLAG_CODES, nullable=False), name="code_valid"
        ),
        CheckConstraint(
            in_check("severity", QUALITY_FLAG_SEVERITIES, nullable=False),
            name="severity_valid",
        ),
        CheckConstraint(
            in_check("source", QUALITY_FLAG_SOURCES, nullable=False),
            name="source_valid",
        ),
        CheckConstraint(
            in_check("disposition", QUALITY_FLAG_DISPOSITIONS, nullable=False),
            name="disposition_valid",
        ),
        CheckConstraint(
            in_check("training_outcome", ("eligible", "withheld", "invalidated")),
            name="training_outcome_valid",
        ),
        CheckConstraint(_ONE_FLAG_TARGET, name="one_target"),
        CheckConstraint(
            "(action = 'raised' AND supersedes_id IS NULL) OR (action <> 'raised' AND supersedes_id IS NOT NULL)",
            name="supersedes_matches_action",
        ),
        CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id",
            name="not_self_superseding",
        ),
        CheckConstraint(
            "source <> 'automatic_validation' OR (rule_version IS NOT NULL AND TRIM(rule_version) <> '')",
            name="automatic_requires_rule",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    presentation_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_presentations.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_observations.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_quality_flags.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(30))
    disposition: Mapped[str] = mapped_column(String(10))
    rule_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)


class ModelCheckpoint(Base):
    """Frozen data manifest and typed predictions, never recomputed in place.

    R8 (M-07, ADR-009 "freeze ... exclusions ... source-feature snapshot"):
    the reproduction columns below record what a checkpoint was built from, so
    the training set can be rebuilt and compared by digest. They are nullable
    because every checkpoint written before R8 lacks them and none can be
    reconstructed after the fact; the R8 checkpoint service populates them.
    ``predictions`` stays as the caller-supplied JSON it always was; the typed
    form is ``CheckpointPrediction`` (M-08).
    """

    __tablename__ = "calibration_checkpoints"
    __table_args__: tuple[SchemaItem, ...] = (
        CheckConstraint(
            json_shape_check("exclusions", "["), name="exclusions_is_array"
        ),
        CheckConstraint(json_shape_check("filters", "{"), name="filters_is_object"),
        CheckConstraint(
            json_shape_check("model_params", "{"), name="model_params_is_object"
        ),
        CheckConstraint(sha256_hex_check("input_digest"), name="input_digest_sha256"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_enrollments.id", ondelete="RESTRICT"), index=True
    )
    algorithm_version: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    manifest: Mapped[list[dict[str, object]]] = mapped_column(portable_json())
    predictions: Mapped[list[dict[str, object]]] = mapped_column(portable_json())
    # #CRITICAL: data-integrity: ``none_as_null=True`` so a Python ``None``
    # is a SQL NULL rather than the JSON text ``null``, which the shape CHECKs
    # above would reject (same reasoning as ``Observation.perceived_notes``).
    # #VERIFY: test_checkpoint_reproduction_columns_default_to_sql_null.
    # Fragrance version ids withheld from training (holdouts and any other
    # exclusion the run applied).
    exclusions: Mapped[list[str] | None] = mapped_column(
        portable_json(none_as_null=True), nullable=True
    )
    # Named row filters the run applied (eligibility policy, stage, phase).
    filters: Mapped[dict[str, object] | None] = mapped_column(
        portable_json(none_as_null=True), nullable=True
    )
    feature_space_version: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    taxonomy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The model's serialized parameters (``ModelSpec.params``).
    model_params: Mapped[dict[str, object] | None] = mapped_column(
        portable_json(none_as_null=True), nullable=True
    )
    # SHA-256 over the canonical JSON of the frozen manifest.
    input_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feature_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("feature_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )


class CheckpointPrediction(Base):
    """One typed prediction frozen with a checkpoint (M-08).

    Replaces reading ``ModelCheckpoint.predictions``' free-form JSON: each row
    names the fragrance version it predicts (a join key to the manifest), the
    declared target, and the target's own scale, so a 1-5 ordinary rating can
    never be compared against a 0-10 liking. The rule that a row must target
    the enrollment's holdout set is a service rule (it needs the enrollment's
    memberships), enforced where checkpoints are created.
    """

    __tablename__ = "calibration_checkpoint_predictions"
    __table_args__: tuple[SchemaItem, ...] = (
        UniqueConstraint(
            "checkpoint_id",
            "fragrance_id",
            "target",
            name="uq_checkpoint_prediction_target",
        ),
        CheckConstraint(
            " OR ".join(
                f"(target = '{target}' AND scale = '{scale}')"
                for target, scale in CHECKPOINT_TARGET_SCALES
            ),
            name="target_scale",
        ),
        # Excludes NaN and +/-Infinity as ``predicted_rating_finite`` does.
        CheckConstraint(
            "value = value AND ((scale = '0-10' AND value >= 0 AND value <= 10) OR (scale = '1-5' AND value >= 1 AND value <= 5))",
            name="value_in_scale",
        ),
        CheckConstraint(
            "uncertainty IS NULL OR (uncertainty = uncertainty AND uncertainty >= 0 AND uncertainty < 1e308)",
            name="uncertainty_nonnegative",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    checkpoint_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_checkpoints.id", ondelete="RESTRICT"), index=True
    )
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    target: Mapped[str] = mapped_column(String(20))
    scale: Mapped[str] = mapped_column(String(10))
    value: Mapped[float] = mapped_column(Float)
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)


class SourceSnapshot(Base):
    """Refreshable source evidence stored independently of human observations.

    ADR-012's 2026-09-15 amendment: source_type and permission_state record
    not just where a fact came from but what may be done with it (retained
    and trained on, QC-only, or excluded outright). fields names which
    Fragrance column(s) this specific snapshot evidences, so two snapshots
    for the same fragrance can disagree on which source is authoritative for
    which field. source_url is relaxed to nullable and source_reference
    added alongside it because a manufacturer confirmation arriving by
    letter, email, or phone has no URL to cite; the CHECK constraint below
    requires at least one of the two to be non-blank.
    """

    __tablename__ = "calibration_source_snapshots"
    # #ASSUME: data-integrity: `source_type` and `permission_state` have
    # exactly the legal values ADR-012's 2026-09-15 amendment enumerates, and
    # every row carries at least one non-blank provenance identifier
    # (`source_url` or `source_reference`; an empty or whitespace-only string
    # is not provenance). Enforcing these in the schema, rather than only in
    # `ParfumoScraper._save_source` and `scripts/validate_calibration_manifest.py`,
    # keeps a future write path from recording evidence with an unknown
    # retention permission or no citation at all, matching the IN(...)
    # precedent on PilotOperationalEvent.event_type and FragellaLookup.status.
    # These expressions must stay textually identical to migration
    # a3f8c1d9e2b7 (`_HAS_SOURCE_CHECK` there).
    # #VERIFY: covered by the unit test
    # test_source_snapshot_rejects_invalid_provenance in
    # test_calibration_service, which asserts each violation fails at
    # flush(), and by the integration test
    # test_upgrade_rejects_invalid_provenance in
    # test_source_snapshot_provenance_migration, which asserts the migrated
    # schema rejects the same rows.
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('project_owned', 'manufacturer_provided', "
            "'open_licensed', 'bounded_lookup', 'excluded_legacy')",
            name="source_type",
        ),
        CheckConstraint(
            "permission_state IN ('retain_and_train', 'retain_for_qc_only', "
            "'excluded_no_new_writes')",
            name="permission_state",
        ),
        CheckConstraint(
            (
                "COALESCE(TRIM(source_url), '') <> '' "
                "OR COALESCE(TRIM(source_reference), '') <> ''"
            ),
            name="has_source",
        ),
        # R8 (issue #130). See the #ASSUME on ``SOURCE_PERMISSION_PAIRS``.
        CheckConstraint(SOURCE_PERMISSION_PAIR_CHECK, name="source_permission_pair"),
        # #ASSUME: data-integrity: ``fields`` holds only ``Fragrance`` column
        # names a source can evidence; a typo would otherwise yield per-field
        # provenance nothing can trace (issue #130).
        # #VERIFY: test_r8_provenance.py rejects an unknown name,
        # a non-array, and a JSON null.
        CheckConstraint(
            json_string_array_check("fields", SOURCE_EVIDENCE_FIELDS),
            name="fields_allowed",
        ),
        CheckConstraint(sha256_hex_check("content_hash"), name="content_hash_sha256"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(30))
    permission_state: Mapped[str] = mapped_column(String(30))
    fields: Mapped[list[str]] = mapped_column(portable_json())
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    retrieved_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    payload: Mapped[dict[str, object]] = mapped_column(portable_json())
    # R8 (tech-spec D1 contract; X-16, D-01): the remaining provenance items.
    # Nullable: no snapshot written before R8 recorded them.
    # The source's own revision or edition identifier (a page revision id, a
    # dataset release, a letter's date), distinct from ``retrieved_at``.
    source_revision: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # SHA-256 (lowercase hex) of the raw evidence as retrieved.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Version of the parser or mapping that turned the evidence into ``fields``.
    parser_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The license text, grant, or written permission that supports
    # ``permission_state`` (or where it is kept).
    license_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Username of the reviewer who verified the snapshot.
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FragellaLookup(Base):
    """A Fragella reference-lookup attempt for a fragrance.

    # #ASSUME: data-integrity: distinct from SourceSnapshot - this is not
    # adopted source evidence (see ADR-002's 2026-09-13 amendment).
    # `results` is read-only reference data a manager can compare against
    # while verifying identity; nothing here is ever written back into
    # `Fragrance` fields or copied into a membership's
    # `identity_evidence`/`verification_evidence` automatically. Recorded
    # so a manager can see which fragrances still have not been checked
    # ("fill holes") without re-spending one of the account's 20
    # monthly requests just to find out.
    # #VERIFY: no code path other than FragellaLookupService writes a
    # Fragrance column or Membership.selection from a FragellaLookup row.
    """

    __tablename__ = "fragella_lookups"
    # #ASSUME: data-integrity: `status` has exactly two legal values today
    # (FragellaLookupService.run_lookup only ever writes "error" or
    # "success"); a bare String(20) column upheld the invariant that
    # `status` moves in lockstep with `error_message`/`results` only by
    # programmer discipline in that one write path, so a future write path
    # could otherwise leave e.g. status="success" with a stale
    # error_message. A CHECK constraint moves that enforcement to the
    # schema, matching the existing IN(...) precedent on
    # PilotOperationalEvent.event_type.
    # #VERIFY: covered by a test asserting a third value fails at flush().
    __table_args__ = (
        CheckConstraint("status IN ('error', 'success')", name="status_valid"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    queried_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    query: Mapped[str] = mapped_column(String(500))
    requested_by: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)
    results: Mapped[list[dict[str, object]]] = mapped_column(
        portable_json(), default=list
    )


class Perfumer(Base):
    """Named source contributor."""

    __tablename__ = "calibration_perfumers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class VersionPerfumer(Base):
    """Many-to-many version attribution with source provenance."""

    __tablename__ = "calibration_version_perfumers"
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), primary_key=True
    )
    perfumer_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_perfumers.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(String(1000))

    perfumer: Mapped[Perfumer] = relationship(lazy="joined")

    @property
    def name(self) -> str:
        """The attributed perfumer's name.

        Exposed on the association rather than reached through it so the API
        schema can read an attribution as one object: a name and the source
        that supports it. The two belong together (ADR-006) and separating
        them invites a name being rendered without its evidence.
        """
        return self.perfumer.name
