"""Database-level guards on the R7a capture-shape schema (R7a PR 1).

The shared SQLite fixtures enforce foreign keys and CHECKs the same way
PostgreSQL does, so every CHECK, UNIQUE, and closed vocabulary added by
migration ``3f14014a49cb`` is exercised here without a PostgreSQL server. The
migration and the models name the same constraints; the parity test in
``tests/integration`` compares names, so the vocabularies are pinned here.
"""

from __future__ import annotations

import importlib.util
import re
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint, select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base
from fragrance_rater.models.behavioral_event import (
    BEHAVIORAL_EVENT_TYPES,
    DECLINE_REASONS,
    BehavioralEvent,
)
from fragrance_rater.models.calibration import (
    APPLICATION_METHODS,
    CONTEXT_ANSWERS,
    HORMONAL_CONTEXT_ANSWERS,
    HUNGER_LEVELS,
    OWNED_OR_WORN_CODES,
    PHASES,
    RANK_CRITERIA,
    RECOGNITION_CODES,
    RESPONSE_STATUSES,
    SAMPLE_CONTAINERS,
    SAMPLE_SOURCE_TYPES,
    STAGES,
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
    Program,
    RankEntry,
    RankEvent,
    SessionContext,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Table
    from sqlalchemy.ext.asyncio import AsyncSession

MIGRATION = next(
    (Path(__file__).parents[3] / "alembic" / "versions").glob("3f14014a49cb_*.py")
)


def _check(table: Table, rule: str) -> CheckConstraint:
    name = f"ck_{table.name}_{rule}"
    (constraint,) = (
        c
        for c in table.constraints
        if isinstance(c, CheckConstraint) and c.name == name
    )
    return constraint


def _values(table: Table, rule: str) -> set[str]:
    return set(re.findall(r"'([^']*)'", str(_check(table, rule).sqltext)))


VOCABULARIES = [
    ("calibration_observations", "response_status_valid", RESPONSE_STATUSES),
    ("calibration_observations", "recognition_valid", RECOGNITION_CODES),
    ("calibration_observations", "owned_or_worn_valid", OWNED_OR_WORN_CODES),
    ("evaluations", "recognition_valid", RECOGNITION_CODES),
    ("evaluations", "owned_or_worn_valid", OWNED_OR_WORN_CODES),
    ("calibration_presentations", "application_method_valid", APPLICATION_METHODS),
    ("calibration_presentations", "sample_source_type_valid", SAMPLE_SOURCE_TYPES),
    ("calibration_presentations", "sample_container_valid", SAMPLE_CONTAINERS),
    ("calibration_rank_events", "stage_valid", STAGES),
    ("calibration_rank_events", "phase_valid", PHASES),
    ("calibration_rank_events", "criterion_valid", RANK_CRITERIA),
    (
        "calibration_rank_events",
        "response_status_valid",
        tuple(code for code in RESPONSE_STATUSES if code != "not_detected"),
    ),
    ("calibration_session_contexts", "illness_valid", CONTEXT_ANSWERS),
    ("calibration_session_contexts", "nasal_congestion_valid", CONTEXT_ANSWERS),
    ("calibration_session_contexts", "allergy_symptoms_valid", CONTEXT_ANSWERS),
    ("calibration_session_contexts", "personal_fragrance_worn_valid", CONTEXT_ANSWERS),
    ("calibration_session_contexts", "ambient_odor_valid", CONTEXT_ANSWERS),
    ("calibration_session_contexts", "hunger_valid", HUNGER_LEVELS),
    (
        "calibration_session_contexts",
        "hormonal_context_valid",
        HORMONAL_CONTEXT_ANSWERS,
    ),
    ("behavioral_events", "event_type_valid", BEHAVIORAL_EVENT_TYPES),
    ("behavioral_events", "decline_reason_valid", DECLINE_REASONS),
]


@pytest.mark.parametrize(("table", "rule", "codes"), VOCABULARIES)
def test_model_vocabulary_matches_its_check(
    table: str, rule: str, codes: tuple[str, ...]
) -> None:
    """The Python tuple and the CHECK it generates cannot drift apart."""
    assert _values(Base.metadata.tables[table], rule) == set(codes)


class _RecordingOp:
    """Stand-in for ``alembic.op`` that records each CHECK the migration creates."""

    def __init__(self) -> None:
        self.checks: dict[str, str] = {}

    def create_table(self, _name: str, *items: object) -> None:
        for item in items:
            if isinstance(item, CheckConstraint):
                self.checks[str(item.name)] = str(item.sqltext)

    def create_index(self, *_args: object, **_kwargs: object) -> None:
        return None

    @contextmanager
    def batch_alter_table(self, _table: str) -> Iterator[_RecordingOp]:
        yield self

    def add_column(self, *_args: object, **_kwargs: object) -> None:
        return None

    def create_check_constraint(self, name: str, condition: str) -> None:
        self.checks[name] = condition


@pytest.fixture(scope="module")
def migration_checks() -> dict[str, str]:
    """Run the migration's ``upgrade`` against a recorder; return CHECKs by name."""
    migration = _migration_module()
    recorder = _RecordingOp()
    migration.op = recorder
    migration.upgrade()
    return recorder.checks


@pytest.mark.parametrize(("table", "rule", "codes"), VOCABULARIES)
def test_migration_writes_the_same_vocabulary(
    migration_checks: dict[str, str], table: str, rule: str, codes: tuple[str, ...]
) -> None:
    """Each CHECK the migration creates lists exactly the model's codes."""
    name = f"ck_{table}_{rule}"
    assert name in migration_checks, f"{name}: not created by the migration"
    written = set(re.findall(r"'([^']*)'", migration_checks[name]))
    assert written == set(codes), f"{name}: migration and model vocabularies differ"


def test_response_status_has_the_plan_row_codes() -> None:
    """R7a plan row: completed, not_detected, skipped, unable_to_assess, ..."""
    assert set(RESPONSE_STATUSES) == {
        "completed",
        "not_detected",
        "skipped",
        "unable_to_assess",
        "interrupted",
        "invalidated",
    }


def test_recognition_and_prior_ownership_are_separate_columns() -> None:
    """The ADR-005 amendment keeps recognition apart from owned-or-worn."""
    for table in ("calibration_observations", "evaluations"):
        columns = Base.metadata.tables[table].columns
        assert "recognition" in columns
        assert "owned_or_worn" in columns
    # The 0-5 "feels familiar" strength keeps its meaning on observations.
    assert "familiarity" in Base.metadata.tables["calibration_observations"].columns


# --- fixtures -------------------------------------------------------------


async def _fragrance(session: AsyncSession, name: str = "Capture") -> Fragrance:
    fragrance = Fragrance(
        name=name,
        brand="House",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="unit",
    )
    session.add(fragrance)
    await session.flush()
    return fragrance


async def _session_with_presentations(
    session: AsyncSession, count: int = 2
) -> tuple[CalibrationSession, list[Presentation]]:
    program = Program(name="capture", version="1")
    reviewer = Reviewer(name="capture")
    session.add_all([program, reviewer])
    await session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    session.add(enrollment)
    await session.flush()
    calibration = CalibrationSession(enrollment_id=enrollment.id)
    session.add(calibration)
    await session.flush()
    presentations: list[Presentation] = []
    for index in range(count):
        fragrance = await _fragrance(session, f"Capture {index}")
        member = Membership(
            program_id=program.id, fragrance_id=fragrance.id, role="HOLDOUT"
        )
        session.add(member)
        await session.flush()
        presentation = Presentation(
            session_id=calibration.id,
            membership_id=member.id,
            blind_code=f"B{index}",
            position=index,
        )
        session.add(presentation)
        await session.flush()
        presentations.append(presentation)
    return calibration, presentations


def _observation(presentation: Presentation, **fields: object) -> Observation:
    values: dict[str, object] = {
        "presentation_id": presentation.id,
        "stage": "BLOTTER",
        "phase": "PRE_REVEAL",
        "recorded_by": "rec",
    }
    values.update(fields)
    return Observation(**values)


async def _rejects(session: AsyncSession, row: object) -> None:
    """Assert the database refuses ``row`` and leave the session usable."""
    session.add(row)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


# --- observations ---------------------------------------------------------


@pytest.mark.asyncio
async def test_a_plain_observation_leaves_every_r7a_column_null(
    async_session: AsyncSession,
) -> None:
    """Existing flows still write NULL: "not recorded", never a guessed value."""
    _, (presentation, _) = await _session_with_presentations(async_session)
    observation = _observation(presentation)
    async_session.add(observation)
    await async_session.flush()

    for column in (
        "observed_at",
        "response_status",
        "recognition",
        "owned_or_worn",
        "scrubbed_off",
        "time_to_scrub_minutes",
        "last_detected_elapsed_min",
        "first_not_detected_elapsed_min",
    ):
        assert getattr(observation, column) is None, column


@pytest.mark.asyncio
async def test_a_full_skin_observation_is_accepted(
    async_session: AsyncSession,
) -> None:
    _, (presentation, _) = await _session_with_presentations(async_session)
    observation = _observation(
        presentation,
        stage="SKIN",
        phase="PRE_REVEAL",
        response_status="completed",
        recognition="vaguely_familiar",
        owned_or_worn="no",
        scrubbed_off=True,
        time_to_scrub_minutes=45,
        last_detected_elapsed_min=240,
        first_not_detected_elapsed_min=480,
    )
    async_session.add(observation)
    await async_session.flush()


@pytest.mark.parametrize(
    "fields",
    [
        {"response_status": "technical_failure"},
        {"recognition": "familiar"},
        {"owned_or_worn": "maybe"},
        {"response_status": "not_detected", "detected": True},
        {"response_status": "not_detected"},
        {"time_to_scrub_minutes": 10},
        {"time_to_scrub_minutes": 10, "scrubbed_off": False, "stage": "SKIN"},
        {"scrubbed_off": True, "stage": "BLOTTER"},
        {"stage": "SKIN", "scrubbed_off": True, "time_to_scrub_minutes": -1},
        {"last_detected_elapsed_min": -5},
        {"first_not_detected_elapsed_min": -5},
        {"last_detected_elapsed_min": 240, "first_not_detected_elapsed_min": 240},
        {"last_detected_elapsed_min": 240, "first_not_detected_elapsed_min": 120},
    ],
)
@pytest.mark.asyncio
async def test_observation_checks_reject_bad_values(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    _, (presentation, _) = await _session_with_presentations(async_session)

    await _rejects(async_session, _observation(presentation, **fields))


@pytest.mark.asyncio
async def test_not_detected_with_detected_false_is_accepted(
    async_session: AsyncSession,
) -> None:
    _, (presentation, _) = await _session_with_presentations(async_session)
    async_session.add(
        _observation(
            presentation,
            response_status="not_detected",
            detected=False,
            intensity=0,
        )
    )
    await async_session.flush()


# --- evaluations ----------------------------------------------------------


@pytest.mark.parametrize(
    "fields", [{"recognition": "familiar"}, {"owned_or_worn": "maybe"}]
)
@pytest.mark.asyncio
async def test_evaluation_familiarity_codes_are_closed(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    fragrance = await _fragrance(async_session)
    reviewer = Reviewer(name="eval")
    async_session.add(reviewer)
    await async_session.flush()

    await _rejects(
        async_session,
        Evaluation(
            reviewer_id=reviewer.id, fragrance_id=fragrance.id, rating=3, **fields
        ),
    )


# --- presentations --------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"application_method": "pour"},
        {"application_dose_sprays": 0},
        {"sample_source_type": "found"},
        {"sample_container": "bucket"},
        {"sample_volume_ml": 0},
        {"sample_volume_ml": -1.5},
    ],
)
@pytest.mark.asyncio
async def test_presentation_provenance_checks_reject_bad_values(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    calibration, (presentation, _) = await _session_with_presentations(async_session)

    await _rejects(
        async_session,
        Presentation(
            session_id=calibration.id,
            membership_id=presentation.membership_id,
            blind_code="X",
            position=9,
            **fields,
        ),
    )


@pytest.mark.asyncio
async def test_a_presentation_with_full_provenance_is_accepted(
    async_session: AsyncSession,
) -> None:
    calibration, (presentation, _) = await _session_with_presentations(async_session)
    async_session.add(
        Presentation(
            session_id=calibration.id,
            membership_id=presentation.membership_id,
            blind_code="OK",
            position=9,
            application_method="spray",
            application_dose_sprays=2,
            sample_source_type="decant",
            sample_container="spray_atomizer",
            sample_volume_ml=2.0,
            sample_acquired_on=date(2026, 10, 1),
            sample_decanted_on=date(2026, 10, 2),
            sample_opened_on=date(2026, 10, 3),
            sample_batch_code="L123",
            physical_sample_confirmed=True,
            application_timezone="America/Denver",
        )
    )
    await async_session.flush()


# --- session context ------------------------------------------------------


@pytest.mark.asyncio
async def test_a_session_has_at_most_one_context(async_session: AsyncSession) -> None:
    calibration, _ = await _session_with_presentations(async_session)
    async_session.add(SessionContext(session_id=calibration.id, recorded_by="rec"))
    await async_session.flush()

    await _rejects(
        async_session, SessionContext(session_id=calibration.id, recorded_by="rec")
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"illness": "sometimes"},
        {"nasal_congestion": "maybe"},
        {"allergy_symptoms": ""},
        {"personal_fragrance_worn": "unknown"},
        {"ambient_odor": "n/a"},
        {"hunger": "starving"},
        {"hormonal_context": "sometimes"},
        {"hours_since_food": -1.0},
        {"hours_since_caffeine": -0.5},
        {"room_temperature_c": -11.0},
        {"room_temperature_c": 51.0},
        {"room_humidity_pct": -1.0},
        {"room_humidity_pct": 101.0},
    ],
)
@pytest.mark.asyncio
async def test_session_context_checks_reject_bad_values(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    calibration, _ = await _session_with_presentations(async_session)

    await _rejects(
        async_session,
        SessionContext(session_id=calibration.id, recorded_by="rec", **fields),
    )


@pytest.mark.asyncio
async def test_a_refusal_is_stored_not_null(async_session: AsyncSession) -> None:
    """A refusal is ``prefer_not_to_answer``; the context can be wholly refused."""
    calibration, _ = await _session_with_presentations(async_session)
    context = SessionContext(
        session_id=calibration.id,
        recorded_by="rec",
        illness="prefer_not_to_answer",
        hunger="prefer_not_to_answer",
        hormonal_context="not_applicable",
        room_temperature_c=21.5,
        room_humidity_pct=40.0,
        hours_since_food=0.0,
    )
    async_session.add(context)
    await async_session.flush()

    stored = (await async_session.execute(select(SessionContext))).scalar_one()
    assert stored.illness == "prefer_not_to_answer"
    assert stored.nasal_congestion is None


# --- rank events ----------------------------------------------------------


async def _rank_event(
    session: AsyncSession, calibration: CalibrationSession, **fields: object
) -> RankEvent:
    values: dict[str, object] = {
        "session_id": calibration.id,
        "stage": "BLOTTER",
        "phase": "PRE_REVEAL",
        "criterion": "liking",
        "response_status": "completed",
        "recorded_by": "rec",
    }
    values.update(fields)
    event = RankEvent(**values)
    session.add(event)
    await session.flush()
    return event


@pytest.mark.parametrize(
    "fields",
    [
        {"stage": "BOTH"},
        {"phase": "AFTER"},
        {"criterion": "projection"},
        {"response_status": "not_detected"},
        {"response_status": "done"},
    ],
)
@pytest.mark.asyncio
async def test_rank_event_checks_reject_bad_values(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    calibration, _ = await _session_with_presentations(async_session)

    await _rejects(
        async_session,
        RankEvent(
            **{
                "session_id": calibration.id,
                "stage": "BLOTTER",
                "phase": "PRE_REVEAL",
                "criterion": "liking",
                "response_status": "completed",
                "recorded_by": "rec",
                **fields,
            }
        ),
    )


@pytest.mark.asyncio
async def test_ties_share_a_position_and_an_undetected_sample_has_none(
    async_session: AsyncSession,
) -> None:
    """Instrument v0.5 allows 1, 1, 3; an undetected sample is not ranked."""
    calibration, presentations = await _session_with_presentations(
        async_session, count=3
    )
    event = await _rank_event(async_session, calibration)
    async_session.add_all(
        [
            RankEntry(
                rank_event_id=event.id,
                presentation_id=presentations[0].id,
                eligible_for_rank=True,
                rank_position=1,
            ),
            RankEntry(
                rank_event_id=event.id,
                presentation_id=presentations[1].id,
                eligible_for_rank=True,
                rank_position=1,
            ),
            RankEntry(
                rank_event_id=event.id,
                presentation_id=presentations[2].id,
                eligible_for_rank=False,
            ),
        ]
    )
    await async_session.flush()


@pytest.mark.parametrize(
    "fields",
    [
        {"eligible_for_rank": False, "rank_position": 1},
        {"eligible_for_rank": True, "rank_position": 0},
        {"eligible_for_rank": True, "rank_position": -2},
    ],
)
@pytest.mark.asyncio
async def test_rank_entry_checks_reject_bad_values(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    calibration, (presentation, _) = await _session_with_presentations(async_session)
    event = await _rank_event(async_session, calibration)

    await _rejects(
        async_session,
        RankEntry(rank_event_id=event.id, presentation_id=presentation.id, **fields),
    )


@pytest.mark.asyncio
async def test_a_presentation_ranks_once_per_event(
    async_session: AsyncSession,
) -> None:
    calibration, (presentation, _) = await _session_with_presentations(async_session)
    event = await _rank_event(async_session, calibration)
    async_session.add(
        RankEntry(
            rank_event_id=event.id,
            presentation_id=presentation.id,
            eligible_for_rank=True,
            rank_position=1,
        )
    )
    await async_session.flush()

    await _rejects(
        async_session,
        RankEntry(
            rank_event_id=event.id,
            presentation_id=presentation.id,
            eligible_for_rank=True,
            rank_position=2,
        ),
    )


@pytest.mark.asyncio
async def test_a_second_event_may_rank_the_same_presentation(
    async_session: AsyncSession,
) -> None:
    """A correction is an invalidated event plus a new one, not an edit."""
    calibration, (presentation, _) = await _session_with_presentations(async_session)
    first = await _rank_event(async_session, calibration)
    second = await _rank_event(async_session, calibration, phase="POST_REVEAL")
    for event in (first, second):
        async_session.add(
            RankEntry(
                rank_event_id=event.id,
                presentation_id=presentation.id,
                eligible_for_rank=True,
                rank_position=1,
            )
        )
    await async_session.flush()


# --- behavioral events ----------------------------------------------------


def _behavior(
    reviewer: Reviewer, fragrance: Fragrance, **fields: object
) -> BehavioralEvent:
    values: dict[str, object] = {
        "reviewer_id": reviewer.id,
        "fragrance_id": fragrance.id,
        "event_type": "sampled",
        "occurred_on": date(2026, 10, 30),
        "recorded_by": "rec",
    }
    values.update(fields)
    return BehavioralEvent(**values)


async def _reviewer_and_fragrance(
    session: AsyncSession,
) -> tuple[Reviewer, Fragrance]:
    reviewer = Reviewer(name="buyer")
    session.add(reviewer)
    fragrance = await _fragrance(session, "Behaviour")
    await session.flush()
    return reviewer, fragrance


@pytest.mark.asyncio
async def test_behavioral_event_accepts_a_priced_purchase(
    async_session: AsyncSession,
) -> None:
    reviewer, fragrance = await _reviewer_and_fragrance(async_session)
    async_session.add(
        _behavior(
            reviewer,
            fragrance,
            event_type="bought_decant",
            size_ml=5.0,
            price_amount=Decimal("12.50"),
            currency="USD",
            evaluator_timezone="America/Denver",
        )
    )
    await async_session.flush()

    stored = (await async_session.execute(select(BehavioralEvent))).scalar_one()
    assert stored.price_amount == Decimal("12.50")
    assert stored.source_observation_id is None
    assert stored.source_impression_id is None


@pytest.mark.asyncio
async def test_declined_takes_a_reason(async_session: AsyncSession) -> None:
    reviewer, fragrance = await _reviewer_and_fragrance(async_session)
    async_session.add(
        _behavior(reviewer, fragrance, event_type="declined", decline_reason="price")
    )
    await async_session.flush()


@pytest.mark.parametrize(
    "fields",
    [
        {"event_type": "stolen"},
        {"event_type": "declined", "decline_reason": "mood"},
        {"event_type": "sampled", "decline_reason": "price"},
        {"size_ml": 0},
        {"size_ml": -3.0},
        {"price_amount": Decimal("-1.00"), "currency": "USD"},
        {"price_amount": Decimal("10.00")},
    ],
)
@pytest.mark.asyncio
async def test_behavioral_event_checks_reject_bad_values(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    reviewer, fragrance = await _reviewer_and_fragrance(async_session)

    await _rejects(async_session, _behavior(reviewer, fragrance, **fields))


@pytest.mark.asyncio
async def test_a_reviewer_with_events_cannot_be_hard_deleted(
    async_session: AsyncSession,
) -> None:
    """Behavioral history is evidence: its foreign keys do not cascade."""
    reviewer, fragrance = await _reviewer_and_fragrance(async_session)
    async_session.add(_behavior(reviewer, fragrance))
    await async_session.flush()

    await async_session.delete(reviewer)
    with pytest.raises(IntegrityError):
        await async_session.flush()


# --- scope guards ---------------------------------------------------------


def test_behavioral_events_do_not_feed_scoring() -> None:
    """ADR-011: captured, excluded from scoring. No ML module reads the model."""
    ml_root = Path(__file__).parents[3] / "src" / "fragrance_rater" / "ml"
    offenders = [
        str(path)
        for path in ml_root.rglob("*.py")
        if "BehavioralEvent" in path.read_text(encoding="utf-8")
        or "behavioral_event" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


# --- migration downgrade guard --------------------------------------------


def _migration_module():
    spec = importlib.util.spec_from_file_location("capture_shape_migration", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_the_downgrade_guard_sees_nothing_in_an_empty_database(
    async_session: AsyncSession,
) -> None:
    """With no captured evidence, a downgrade is allowed to proceed."""
    migration = _migration_module()
    connection = await async_session.connection()

    found = await connection.run_sync(migration._captured_data)

    assert found == []


@pytest.mark.asyncio
async def test_the_downgrade_guard_names_captured_tables_and_columns(
    async_session: AsyncSession,
) -> None:
    """Captured evidence exists nowhere else, so the guard names what it found."""
    migration = _migration_module()
    calibration, (presentation, _) = await _session_with_presentations(async_session)
    async_session.add(SessionContext(session_id=calibration.id, recorded_by="rec"))
    async_session.add(_observation(presentation, recognition="new"))
    await async_session.flush()
    calibration.evaluator_timezone = "America/Denver"
    await async_session.flush()
    connection = await async_session.connection()

    found = await connection.run_sync(migration._captured_data)

    assert "calibration_session_contexts: 1 row(s)" in found
    assert "calibration_observations.recognition: 1 non-NULL row(s)" in found
    assert "calibration_sessions.evaluator_timezone: 1 non-NULL row(s)" in found
    assert not any(entry.startswith("calibration_rank_events") for entry in found)
