"""Database-level guards on the R7a provenance and governance schema (R7a PR 2).

Covers migration ``cd1e2375a2e4``: randomization record, quality flags, consent
events, ``Program.instrument_version``, and the season/setting fit columns. The
shared SQLite fixtures enforce foreign keys and CHECKs the same way PostgreSQL
does, so every CHECK and closed vocabulary is exercised without a server.
"""

from __future__ import annotations

import importlib.util
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint, select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models import Base
from fragrance_rater.models.calibration import (
    QUALITY_FLAG_ACTIONS,
    QUALITY_FLAG_CODES,
    QUALITY_FLAG_DISPOSITIONS,
    QUALITY_FLAG_SEVERITIES,
    QUALITY_FLAG_SOURCES,
    SEASON_FIT_CODES,
    SETTING_FIT_CODES,
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
    Program,
    QualityFlag,
)
from fragrance_rater.models.consent import (
    CONSENT_EVENT_TYPES,
    CONSENT_SCOPES,
    ConsentEvent,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Table
    from sqlalchemy.ext.asyncio import AsyncSession

MIGRATION = next(
    (Path(__file__).parents[3] / "alembic" / "versions").glob("cd1e2375a2e4_*.py")
)
NOW = datetime(2026, 10, 30, 12, 0, 0)  # noqa: DTZ001 - schema stores naive UTC
DIGEST = "a" * 64


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
    ("calibration_observations", "season_fit_valid", SEASON_FIT_CODES),
    ("calibration_observations", "setting_fit_valid", SETTING_FIT_CODES),
    ("calibration_quality_flags", "action_valid", QUALITY_FLAG_ACTIONS),
    ("calibration_quality_flags", "code_valid", QUALITY_FLAG_CODES),
    ("calibration_quality_flags", "severity_valid", QUALITY_FLAG_SEVERITIES),
    ("calibration_quality_flags", "source_valid", QUALITY_FLAG_SOURCES),
    ("calibration_quality_flags", "disposition_valid", QUALITY_FLAG_DISPOSITIONS),
    ("consent_events", "event_type_valid", CONSENT_EVENT_TYPES),
    ("consent_events", "scope_valid", CONSENT_SCOPES),
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


def _migration_module():
    spec = importlib.util.spec_from_file_location("provenance_migration", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_every_model_check_is_created_by_the_migration(
    migration_checks: dict[str, str],
) -> None:
    """No CHECK on a new table or column exists only in the models."""
    new_tables = {"calibration_quality_flags", "consent_events"}
    new_columns = {
        "calibration_programs": {"instrument_version"},
        "calibration_enrollments": {"randomization_algorithm", "randomization_seed"},
        "calibration_presentations": {"intended_position"},
        "calibration_observations": {"season_fit", "setting_fit"},
    }
    missing: list[str] = []
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if not isinstance(constraint, CheckConstraint):
                continue
            text = str(constraint.sqltext)
            touches_new = table.name in new_tables or any(
                re.search(rf"\b{column}\b", text)
                for column in new_columns.get(table.name, ())
            )
            if touches_new and str(constraint.name) not in migration_checks:
                missing.append(str(constraint.name))
    assert missing == []


# --- fixtures -------------------------------------------------------------


async def _rejects(session: AsyncSession, row: object) -> None:
    """Assert the database refuses ``row`` and leave the session usable."""
    session.add(row)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def _world(
    session: AsyncSession,
) -> tuple[Program, Enrollment, CalibrationSession, Presentation, Observation]:
    program = Program(name="provenance", version="1")
    reviewer = Reviewer(name="provenance")
    fragrance = Fragrance(
        name="Provenance",
        brand="House",
        concentration="EDP",
        gender_target="unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="unit",
    )
    session.add_all([program, reviewer, fragrance])
    await session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    session.add(enrollment)
    await session.flush()
    calibration = CalibrationSession(enrollment_id=enrollment.id)
    member = Membership(
        program_id=program.id, fragrance_id=fragrance.id, role="HOLDOUT"
    )
    session.add_all([calibration, member])
    await session.flush()
    presentation = Presentation(
        session_id=calibration.id,
        membership_id=member.id,
        blind_code="P1",
        position=0,
    )
    session.add(presentation)
    await session.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage="BLOTTER",
        phase="PRE_REVEAL",
        recorded_by="rec",
    )
    session.add(observation)
    await session.flush()
    return program, enrollment, calibration, presentation, observation


def _obs(presentation: Presentation, **fields: object) -> Observation:
    values: dict[str, object] = {
        "presentation_id": presentation.id,
        "stage": "SKIN",
        "phase": "PRE_REVEAL",
        "recorded_by": "rec",
    }
    values.update(fields)
    return Observation(**values)


# --- programs: instrument version ----------------------------------------


@pytest.mark.asyncio
async def test_a_new_program_has_no_instrument_version(
    async_session: AsyncSession,
) -> None:
    program, *_ = await _world(async_session)

    assert program.instrument_version is None


@pytest.mark.asyncio
async def test_an_active_program_may_carry_an_instrument_version(
    async_session: AsyncSession,
) -> None:
    program, *_ = await _world(async_session)
    program.status = "active"
    program.instrument_version = "build-abc123"
    await async_session.flush()


@pytest.mark.asyncio
async def test_a_draft_program_cannot_carry_an_instrument_version(
    async_session: AsyncSession,
) -> None:
    """The version is written at activation, so a draft cannot have one."""
    program, *_ = await _world(async_session)
    program.instrument_version = "build-abc123"

    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", ["", "   "])
async def test_a_blank_instrument_version_is_refused(
    async_session: AsyncSession, blank: str
) -> None:
    program, *_ = await _world(async_session)
    program.status = "active"
    program.instrument_version = blank

    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


# --- enrollments: randomization record ------------------------------------


@pytest.mark.asyncio
async def test_an_algorithm_without_a_seed_is_accepted(
    async_session: AsyncSession,
) -> None:
    """An unseedable algorithm (today's SystemRandom shuffle) has no seed."""
    _, enrollment, *_ = await _world(async_session)
    enrollment.randomization_algorithm = "system-random-shuffle"
    await async_session.flush()


@pytest.mark.asyncio
async def test_an_algorithm_with_a_seed_is_accepted(
    async_session: AsyncSession,
) -> None:
    _, enrollment, *_ = await _world(async_session)
    enrollment.randomization_algorithm = "seeded-shuffle-v1"
    enrollment.randomization_seed = "42"
    await async_session.flush()


@pytest.mark.asyncio
async def test_a_seed_without_an_algorithm_is_refused(
    async_session: AsyncSession,
) -> None:
    _, enrollment, *_ = await _world(async_session)
    enrollment.randomization_seed = "42"

    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", ["", "  "])
async def test_a_blank_algorithm_is_refused(
    async_session: AsyncSession, blank: str
) -> None:
    _, enrollment, *_ = await _world(async_session)
    enrollment.randomization_algorithm = blank

    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


# --- presentations: intended position -------------------------------------


@pytest.mark.asyncio
async def test_intended_position_may_differ_from_position(
    async_session: AsyncSession,
) -> None:
    """A deviation stays recordable: the check never compares the two."""
    _, _, _, presentation, _ = await _world(async_session)
    presentation.position = 3
    presentation.intended_position = 1
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, -1])
async def test_a_non_positive_intended_position_is_refused(
    async_session: AsyncSession, value: int
) -> None:
    _, _, _, presentation, _ = await _world(async_session)
    presentation.intended_position = value

    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


@pytest.mark.asyncio
async def test_intended_position_is_not_unique_within_a_session(
    async_session: AsyncSession,
) -> None:
    """Nothing in the schema forces one presentation per intended slot."""
    _, _, calibration, presentation, _ = await _world(async_session)
    presentation.intended_position = 1
    second = Presentation(
        session_id=calibration.id,
        membership_id=presentation.membership_id,
        blind_code="P2",
        position=1,
        intended_position=1,
    )
    async_session.add(second)
    await async_session.flush()


# --- observations: season and setting fit ---------------------------------


@pytest.mark.asyncio
async def test_a_plain_observation_leaves_season_and_setting_null(
    async_session: AsyncSession,
) -> None:
    *_, observation = await _world(async_session)

    assert observation.season_fit is None
    assert observation.setting_fit is None


@pytest.mark.asyncio
@pytest.mark.parametrize("code", SEASON_FIT_CODES)
async def test_every_season_code_is_accepted_on_a_skin_row(
    async_session: AsyncSession, code: str
) -> None:
    _, _, _, presentation, _ = await _world(async_session)
    async_session.add(_obs(presentation, season_fit=code))
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", SETTING_FIT_CODES)
async def test_every_setting_code_is_accepted_on_a_skin_row(
    async_session: AsyncSession, code: str
) -> None:
    _, _, _, presentation, _ = await _world(async_session)
    async_session.add(_obs(presentation, setting_fit=code))
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"season_fit": "monsoon"},
        {"setting_fit": "beach"},
        {"season_fit": "spring", "stage": "BLOTTER"},
        {"setting_fit": "home", "stage": "BLOTTER"},
        {"season_fit": "year_round", "setting_fit": "home", "stage": "BLOTTER"},
    ],
)
async def test_season_and_setting_are_skin_stage_only_and_closed(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    """Q9: the labels are asked at skin stage only; blotter rows never carry them."""
    _, _, _, presentation, _ = await _world(async_session)

    await _rejects(async_session, _obs(presentation, **fields))


# --- quality flags --------------------------------------------------------


def _flag(**fields: object) -> QualityFlag:
    values: dict[str, object] = {
        "action": "raised",
        "code": "out_of_order_presentation",
        "severity": "minor",
        "source": "recorder",
        "disposition": "review",
        "recorded_by": "rec",
    }
    values.update(fields)
    return QualityFlag(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["session_id", "presentation_id", "observation_id"])
async def test_a_flag_may_target_exactly_one_thing(
    async_session: AsyncSession, target: str
) -> None:
    _, _, calibration, presentation, observation = await _world(async_session)
    ids = {
        "session_id": calibration.id,
        "presentation_id": presentation.id,
        "observation_id": observation.id,
    }
    async_session.add(_flag(**{target: ids[target]}))
    await async_session.flush()


@pytest.mark.asyncio
async def test_a_flag_with_no_target_is_refused(async_session: AsyncSession) -> None:
    await _world(async_session)

    await _rejects(async_session, _flag())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "targets",
    [
        ("session_id", "presentation_id"),
        ("session_id", "observation_id"),
        ("presentation_id", "observation_id"),
        ("session_id", "presentation_id", "observation_id"),
    ],
)
async def test_a_flag_with_several_targets_is_refused(
    async_session: AsyncSession, targets: tuple[str, ...]
) -> None:
    _, _, calibration, presentation, observation = await _world(async_session)
    ids = {
        "session_id": calibration.id,
        "presentation_id": presentation.id,
        "observation_id": observation.id,
    }

    await _rejects(async_session, _flag(**{t: ids[t] for t in targets}))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"action": "closed"},
        {"code": "weather"},
        {"severity": "fatal"},
        {"source": "robot"},
        {"disposition": "ignore"},
    ],
)
async def test_flag_vocabularies_are_closed(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    _, _, calibration, *_ = await _world(async_session)

    await _rejects(async_session, _flag(session_id=calibration.id, **fields))


@pytest.mark.asyncio
async def test_a_flag_may_record_mistimed_evidence_without_rejecting_it(
    async_session: AsyncSession,
) -> None:
    """Capture assessment 13.3: deviant evidence is kept and flagged, not refused."""
    _, _, _, presentation, observation = await _world(async_session)
    presentation.position = 5
    presentation.intended_position = 2
    async_session.add_all(
        [
            _flag(
                presentation_id=presentation.id,
                code="out_of_order_presentation",
                disposition="include",
            ),
            _flag(
                observation_id=observation.id,
                code="timestamp_inconsistent",
                severity="major",
                disposition="review",
                occurred_at=NOW,
            ),
        ]
    )
    await async_session.flush()


@pytest.mark.asyncio
async def test_a_raised_flag_has_nothing_to_supersede(
    async_session: AsyncSession,
) -> None:
    _, _, calibration, *_ = await _world(async_session)
    raised = _flag(session_id=calibration.id)
    async_session.add(raised)
    await async_session.flush()

    await _rejects(
        async_session,
        _flag(session_id=calibration.id, action="raised", supersedes_id=raised.id),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["resolved", "invalidated"])
async def test_a_closing_flag_must_name_the_flag_it_closes(
    async_session: AsyncSession, action: str
) -> None:
    _, _, calibration, *_ = await _world(async_session)

    await _rejects(async_session, _flag(session_id=calibration.id, action=action))


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["resolved", "invalidated"])
async def test_a_flag_is_closed_by_a_later_row_not_an_edit(
    async_session: AsyncSession, action: str
) -> None:
    _, _, calibration, *_ = await _world(async_session)
    raised = _flag(session_id=calibration.id)
    async_session.add(raised)
    await async_session.flush()
    closing = _flag(
        session_id=calibration.id,
        action=action,
        supersedes_id=raised.id,
        explanation="recorder confirmed the sample order",
    )
    async_session.add(closing)
    await async_session.flush()

    rows = (await async_session.execute(select(QualityFlag))).scalars().all()
    assert {row.action for row in rows} == {"raised", action}
    assert raised.action == "raised"


@pytest.mark.asyncio
async def test_a_flag_cannot_supersede_itself(async_session: AsyncSession) -> None:
    _, _, calibration, *_ = await _world(async_session)
    flag = _flag(session_id=calibration.id)
    async_session.add(flag)
    await async_session.flush()
    flag.action = "resolved"
    flag.supersedes_id = flag.id

    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


@pytest.mark.asyncio
async def test_an_automatic_flag_names_the_rule_that_raised_it(
    async_session: AsyncSession,
) -> None:
    _, _, calibration, *_ = await _world(async_session)
    async_session.add(
        _flag(
            session_id=calibration.id,
            source="automatic_validation",
            rule_version="spacing-v1",
        )
    )
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_version", [None, "", "   "])
async def test_an_automatic_flag_without_a_rule_is_refused(
    async_session: AsyncSession, rule_version: str | None
) -> None:
    _, _, calibration, *_ = await _world(async_session)

    await _rejects(
        async_session,
        _flag(
            session_id=calibration.id,
            source="automatic_validation",
            rule_version=rule_version,
        ),
    )


@pytest.mark.asyncio
async def test_a_human_flag_needs_no_rule_version(async_session: AsyncSession) -> None:
    _, _, calibration, *_ = await _world(async_session)
    async_session.add(_flag(session_id=calibration.id, source="evaluator"))
    await async_session.flush()


@pytest.mark.asyncio
async def test_a_flag_must_point_at_something_that_exists(
    async_session: AsyncSession,
) -> None:
    await _world(async_session)

    await _rejects(async_session, _flag(session_id="no-such-session"))


@pytest.mark.asyncio
async def test_a_flagged_observation_cannot_be_hard_deleted(
    async_session: AsyncSession,
) -> None:
    """Flags are evidence about evidence: their foreign keys do not cascade."""
    *_, observation = await _world(async_session)
    async_session.add(_flag(observation_id=observation.id))
    await async_session.flush()

    await async_session.delete(observation)
    with pytest.raises(IntegrityError):
        await async_session.flush()


# --- consent events -------------------------------------------------------


def _consent(reviewer: Reviewer | str, **fields: object) -> ConsentEvent:
    values: dict[str, object] = {
        "reviewer_id": reviewer if isinstance(reviewer, str) else reviewer.id,
        "event_type": "granted",
        "scope": "session_context",
        "consent_text_version": "consent-v1",
        "occurred_at": NOW,
        "recorded_by": "rec",
    }
    values.update(fields)
    return ConsentEvent(**values)


async def _reviewer(session: AsyncSession) -> Reviewer:
    reviewer = Reviewer(name="consenter")
    session.add(reviewer)
    await session.flush()
    return reviewer


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", CONSENT_SCOPES)
async def test_every_scope_can_be_granted(
    async_session: AsyncSession, scope: str
) -> None:
    reviewer = await _reviewer(async_session)
    async_session.add(_consent(reviewer, scope=scope, consent_text_sha256=DIGEST))
    await async_session.flush()


@pytest.mark.asyncio
async def test_a_grant_and_a_later_withdrawal_coexist(
    async_session: AsyncSession,
) -> None:
    """Consent is append-only: withdrawing adds a row and leaves the grant."""
    reviewer = await _reviewer(async_session)
    async_session.add_all(
        [
            _consent(reviewer),
            _consent(
                reviewer,
                event_type="withdrawn",
                consent_text_version=None,
                occurred_at=datetime(2026, 11, 1, 9, 0, 0),  # noqa: DTZ001
            ),
        ]
    )
    await async_session.flush()

    rows = (await async_session.execute(select(ConsentEvent))).scalars().all()
    assert sorted(row.event_type for row in rows) == ["granted", "withdrawn"]


@pytest.mark.asyncio
async def test_one_scope_can_be_withdrawn_without_restating_the_others(
    async_session: AsyncSession,
) -> None:
    reviewer = await _reviewer(async_session)
    async_session.add_all(
        [
            _consent(reviewer, scope="session_context"),
            _consent(reviewer, scope="model_training"),
            _consent(
                reviewer,
                scope="model_training",
                event_type="withdrawn",
                consent_text_version=None,
            ),
        ]
    )
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [None, "", "   "])
async def test_a_grant_must_name_the_consent_text(
    async_session: AsyncSession, version: str | None
) -> None:
    reviewer = await _reviewer(async_session)

    await _rejects(async_session, _consent(reviewer, consent_text_version=version))


@pytest.mark.asyncio
async def test_a_withdrawal_needs_no_consent_text(
    async_session: AsyncSession,
) -> None:
    reviewer = await _reviewer(async_session)
    async_session.add(
        _consent(reviewer, event_type="withdrawn", consent_text_version=None)
    )
    await async_session.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize("digest", ["a" * 63, "a" * 65, ""])
async def test_a_consent_text_digest_must_be_a_sha256_hex_length(
    async_session: AsyncSession, digest: str
) -> None:
    reviewer = await _reviewer(async_session)

    await _rejects(async_session, _consent(reviewer, consent_text_sha256=digest))


@pytest.mark.asyncio
@pytest.mark.parametrize("fields", [{"event_type": "revoked"}, {"scope": "everything"}])
async def test_consent_vocabularies_are_closed(
    async_session: AsyncSession, fields: dict[str, object]
) -> None:
    reviewer = await _reviewer(async_session)

    await _rejects(async_session, _consent(reviewer, **fields))


@pytest.mark.asyncio
async def test_consent_is_not_tied_to_an_enrollment_unless_it_says_so(
    async_session: AsyncSession,
) -> None:
    reviewer = await _reviewer(async_session)
    _, enrollment, *_ = await _world(async_session)
    async_session.add_all(
        [_consent(reviewer), _consent(reviewer, enrollment_id=enrollment.id)]
    )
    await async_session.flush()


@pytest.mark.asyncio
async def test_consent_must_belong_to_a_real_reviewer(
    async_session: AsyncSession,
) -> None:
    await _rejects(async_session, _consent("no-such-reviewer"))


@pytest.mark.asyncio
async def test_a_reviewer_with_consent_events_cannot_be_hard_deleted(
    async_session: AsyncSession,
) -> None:
    """A consent record outlives any attempt to erase the person it concerns."""
    reviewer = await _reviewer(async_session)
    async_session.add(_consent(reviewer))
    await async_session.flush()

    await async_session.delete(reviewer)
    with pytest.raises(IntegrityError):
        await async_session.flush()


# --- migration downgrade guard --------------------------------------------


@pytest.mark.asyncio
async def test_the_downgrade_guard_sees_nothing_in_an_empty_database(
    async_session: AsyncSession,
) -> None:
    migration = _migration_module()
    connection = await async_session.connection()

    found = await connection.run_sync(migration._captured_data)

    assert found == []


@pytest.mark.asyncio
async def test_the_downgrade_guard_names_recorded_provenance(
    async_session: AsyncSession,
) -> None:
    """Consent and flags exist nowhere else, so the guard says what it found."""
    migration = _migration_module()
    program, enrollment, calibration, presentation, _ = await _world(async_session)
    reviewer = await _reviewer(async_session)
    program.status = "active"
    program.instrument_version = "build-abc123"
    enrollment.randomization_algorithm = "system-random-shuffle"
    presentation.intended_position = 1
    async_session.add_all([_consent(reviewer), _flag(session_id=calibration.id)])
    await async_session.flush()
    connection = await async_session.connection()

    found = await connection.run_sync(migration._captured_data)

    assert "consent_events: 1 row(s)" in found
    assert "calibration_quality_flags: 1 row(s)" in found
    assert "calibration_programs.instrument_version: 1 non-NULL row(s)" in found
    assert "calibration_enrollments.randomization_algorithm: 1 non-NULL row(s)" in found
    assert "calibration_presentations.intended_position: 1 non-NULL row(s)" in found
    assert not any(entry.startswith("calibration_observations") for entry in found)


@pytest.mark.asyncio
async def test_a_downgrade_with_recorded_provenance_refuses_and_names_the_revision() -> (
    None
):
    """The RuntimeError names the revision so an operator knows what to restore."""
    migration = _migration_module()

    class _Bind:
        def execute(self, statement: object) -> object:
            class _Result:
                @staticmethod
                def scalar_one() -> int:
                    return 1

            return _Result()

    class _Op:
        @staticmethod
        def get_bind() -> _Bind:
            return _Bind()

    migration.op = _Op()
    migration._captured_data = lambda _bind: ["consent_events: 1 row(s)"]

    with pytest.raises(RuntimeError, match=r"cd1e2375a2e4.*consent_events: 1 row"):
        migration.downgrade()
