"""R8 PR 1: evidence training eligibility and ``v_training_rows`` (X-05, X-06).

Pins the evidence-level vocabulary across ``core/vocabulary.py``, both model
CHECKs, and migration ``620c8c861268``; exercises the CHECK and the default on
both evidence tables; and runs the migration's own view SQL against the
SQLite test schema to prove which rows the view admits and which columns it
exposes.
"""

from __future__ import annotations

import importlib.util
import itertools
import re
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, get_args

import pytest
import sqlalchemy as sa
from sqlalchemy import CheckConstraint, text
from sqlalchemy.exc import IntegrityError

from fragrance_rater.core.vocabulary import (
    DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY,
    EVIDENCE_TRAINING_ELIGIBILITIES,
    TRAINABLE_EVIDENCE_ELIGIBILITY,
    TRAINING_INELIGIBLE_CODES,
    EvidenceTrainingEligibility,
)
from fragrance_rater.models import Base
from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from types import ModuleType

    from sqlalchemy.ext.asyncio import AsyncSession

MIGRATION = next(
    (Path(__file__).parents[3] / "alembic" / "versions").glob("620c8c861268_*.py")
)
EVIDENCE_TABLES = ("evaluations", "calibration_observations")
_POSITIONS = itertools.count(1)
VIEW_COLUMNS = (
    "row_id",
    "workflow",
    "reviewer_id",
    "fragrance_id",
    "stage",
    "scale",
    "rating",
    "observed_at",
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("r8_migration", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check_text(table: str, rule: str) -> str:
    name = f"ck_{table}_{rule}"
    (constraint,) = (
        c
        for c in Base.metadata.tables[table].constraints
        if isinstance(c, CheckConstraint) and c.name == name
    )
    return str(constraint.sqltext)


# --- vocabulary pins ---------------------------------------------------------


def test_the_literal_and_the_tuple_agree() -> None:
    assert get_args(EvidenceTrainingEligibility) == EVIDENCE_TRAINING_ELIGIBILITIES


def test_the_default_is_not_trainable() -> None:
    """ADR-014 is silent on evidence rows, so nothing trains by default."""
    assert DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY == "unreviewed"
    assert DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY != TRAINABLE_EVIDENCE_ELIGIBILITY
    assert TRAINABLE_EVIDENCE_ELIGIBILITY in EVIDENCE_TRAINING_ELIGIBILITIES


@pytest.mark.parametrize("table", EVIDENCE_TABLES)
def test_each_model_check_lists_exactly_the_vocabulary(table: str) -> None:
    text_ = _check_text(table, "training_eligibility_valid")
    assert re.findall(r"'([^']*)'", text_) == list(EVIDENCE_TRAINING_ELIGIBILITIES)


@pytest.mark.parametrize("table", EVIDENCE_TABLES)
def test_each_model_column_is_not_null_with_the_conservative_default(
    table: str,
) -> None:
    column = Base.metadata.tables[table].columns["training_eligibility"]
    assert not column.nullable
    assert column.server_default is not None
    assert column.server_default.arg == DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY  # pyright: ignore[reportAttributeAccessIssue]


def test_the_migration_lists_the_same_vocabulary_and_default() -> None:
    migration = _migration()
    assert re.findall(r"'([^']*)'", migration._ELIGIBILITY_CHECK) == list(
        EVIDENCE_TRAINING_ELIGIBILITIES
    )
    assert migration._DEFAULT_ELIGIBILITY == DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY


def test_the_view_admits_only_the_trainable_code() -> None:
    sql = _migration().V_TRAINING_ROWS_SQL
    assert set(re.findall(r"training_eligibility = '([^']*)'", sql)) == {
        TRAINABLE_EVIDENCE_ELIGIBILITY
    }


def test_the_view_excludes_exactly_adr_014s_fragrance_codes() -> None:
    sql = _migration().V_TRAINING_ROWS_SQL
    blocks = re.findall(r"training_eligibility_code NOT IN\s*\(([^)]*)\)", sql)
    assert len(blocks) == 2
    for block in blocks:
        assert set(re.findall(r"'([^']*)'", block)) == TRAINING_INELIGIBLE_CODES


# --- the CHECK and the default on both tables --------------------------------


async def _fragrance(session: AsyncSession, name: str = "Gate") -> Fragrance:
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


async def _reviewer(session: AsyncSession, name: str = "Rater") -> Reviewer:
    reviewer = Reviewer(name=name)
    session.add(reviewer)
    await session.flush()
    return reviewer


async def _evaluation(
    session: AsyncSession,
    reviewer: Reviewer,
    fragrance: Fragrance,
    eligibility: str | None = TRAINABLE_EVIDENCE_ELIGIBILITY,
    **extra: object,
) -> Evaluation:
    row = Evaluation(
        reviewer_id=reviewer.id, fragrance_id=fragrance.id, rating=4, **extra
    )
    if eligibility is not None:
        row.training_eligibility = eligibility
    session.add(row)
    await session.flush()
    return row


async def _enrollment(
    session: AsyncSession, reviewer: Reviewer, name: str = "P"
) -> tuple[Program, CalibrationSession]:
    program = Program(name=name, version="1")
    session.add(program)
    await session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    session.add(enrollment)
    await session.flush()
    calibration = CalibrationSession(enrollment_id=enrollment.id)
    session.add(calibration)
    await session.flush()
    return program, calibration


async def _observation(
    session: AsyncSession,
    program: Program,
    calibration: CalibrationSession,
    fragrance: Fragrance,
    *,
    role: str = "UNIVERSAL_BASELINE",
    stage: str = "SKIN",
    phase: str = "PRE_REVEAL",
    locked: bool = True,
    liking: int | None = 7,
    eligibility: str = TRAINABLE_EVIDENCE_ELIGIBILITY,
    response_status: str | None = None,
) -> Observation:
    member = Membership(program_id=program.id, fragrance_id=fragrance.id, role=role)
    session.add(member)
    await session.flush()
    stamp = now_naive_utc() if locked else None
    presentation = Presentation(
        session_id=calibration.id,
        membership_id=member.id,
        blind_code=f"B{member.id[:6]}",
        position=next(_POSITIONS),
        skin_locked_at=stamp,
        blotter_locked_at=stamp,
    )
    session.add(presentation)
    await session.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage=stage,
        phase=phase,
        liking=liking,
        detected=True,
        recorded_by="rec",
        training_eligibility=eligibility,
        response_status=response_status,
    )
    session.add(observation)
    await session.flush()
    return observation


@pytest.mark.asyncio
async def test_an_evaluation_starts_unreviewed(async_session: AsyncSession) -> None:
    row = await _evaluation(
        async_session,
        await _reviewer(async_session),
        await _fragrance(async_session),
        eligibility=None,
    )
    assert row.training_eligibility == "unreviewed"


@pytest.mark.asyncio
async def test_an_observation_starts_unreviewed(async_session: AsyncSession) -> None:
    reviewer = await _reviewer(async_session)
    program, calibration = await _enrollment(async_session, reviewer)
    member = Membership(
        program_id=program.id,
        fragrance_id=(await _fragrance(async_session)).id,
        role="UNIVERSAL_BASELINE",
    )
    async_session.add(member)
    await async_session.flush()
    presentation = Presentation(
        session_id=calibration.id, membership_id=member.id, blind_code="X1", position=1
    )
    async_session.add(presentation)
    await async_session.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage="SKIN",
        phase="PRE_REVEAL",
        recorded_by="rec",
    )
    async_session.add(observation)
    await async_session.flush()
    assert observation.training_eligibility == "unreviewed"


@pytest.mark.asyncio
async def test_the_server_default_fills_a_row_written_without_the_column(
    async_session: AsyncSession,
) -> None:
    """A writer that never names the column (raw SQL, a backfill) still lands."""
    reviewer = await _reviewer(async_session)
    fragrance = await _fragrance(async_session)
    await async_session.execute(
        text(
            "INSERT INTO evaluations (id, fragrance_id, reviewer_id, rating) "
            "VALUES ('raw-1', :f, :r, 3)"
        ),
        {"f": fragrance.id, "r": reviewer.id},
    )
    stored = await async_session.scalar(
        text("SELECT training_eligibility FROM evaluations WHERE id = 'raw-1'")
    )
    assert stored == "unreviewed"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", EVIDENCE_TRAINING_ELIGIBILITIES)
async def test_every_code_is_accepted_on_evaluations(
    async_session: AsyncSession, code: str
) -> None:
    row = await _evaluation(
        async_session,
        await _reviewer(async_session),
        await _fragrance(async_session),
        eligibility=code,
    )
    assert row.training_eligibility == code


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["ELIGIBLE", "excluded_manual", "", "trainable"])
async def test_an_unknown_code_is_rejected_on_evaluations(
    async_session: AsyncSession, code: str
) -> None:
    reviewer = await _reviewer(async_session)
    fragrance = await _fragrance(async_session)
    with pytest.raises(IntegrityError):
        await _evaluation(async_session, reviewer, fragrance, eligibility=code)


@pytest.mark.asyncio
async def test_an_unknown_code_is_rejected_on_observations(
    async_session: AsyncSession,
) -> None:
    reviewer = await _reviewer(async_session)
    program, calibration = await _enrollment(async_session, reviewer)
    fragrance = await _fragrance(async_session)
    with pytest.raises(IntegrityError):
        await _observation(
            async_session, program, calibration, fragrance, eligibility="ELIGIBLE"
        )


@pytest.mark.asyncio
async def test_a_null_code_is_rejected(async_session: AsyncSession) -> None:
    """NOT NULL: no third "unknown" state beside the five codes."""
    reviewer = await _reviewer(async_session)
    fragrance = await _fragrance(async_session)
    with pytest.raises(IntegrityError):
        await async_session.execute(
            text(
                "INSERT INTO evaluations "
                "(id, fragrance_id, reviewer_id, rating, training_eligibility) "
                "VALUES ('raw-2', :f, :r, 3, NULL)"
            ),
            {"f": fragrance.id, "r": reviewer.id},
        )


# --- the view ----------------------------------------------------------------


async def _with_view(session: AsyncSession) -> None:
    await session.execute(text(_migration().V_TRAINING_ROWS_SQL))


async def _view_ids(session: AsyncSession) -> set[str]:
    return set(await session.scalars(text("SELECT row_id FROM v_training_rows")))


@pytest.mark.asyncio
async def test_the_view_exposes_no_role_repeat_or_blind_linkage(
    async_session: AsyncSession,
) -> None:
    """X-06: a trainer reading the view never sees the blind mapping."""
    await _with_view(async_session)
    result = await async_session.execute(text("SELECT * FROM v_training_rows"))

    assert tuple(result.keys()) == VIEW_COLUMNS
    leaked = {
        "role",
        "repeat_of_id",
        "membership_id",
        "presentation_id",
        "session_id",
        "enrollment_id",
        "program_id",
        "blind_code",
        "training_eligibility",
        "worn_by_reviewer_id",
        "recorded_by",
    }
    assert not leaked & set(result.keys())


@pytest.mark.asyncio
async def test_the_view_admits_only_eligible_ordinary_rows(
    async_session: AsyncSession,
) -> None:
    reviewer = await _reviewer(async_session)
    other = await _reviewer(async_session, "Partner")
    fragrance = await _fragrance(async_session)
    excluded = await _fragrance(async_session, "Excluded")
    excluded.training_eligibility_code = "excluded_manual"
    deleted = await _fragrance(async_session, "Deleted")
    deleted.deleted_at = now_naive_utc()

    eligible = await _evaluation(async_session, reviewer, fragrance)
    held_back = [
        await _evaluation(async_session, reviewer, fragrance, eligibility=code)
        for code in EVIDENCE_TRAINING_ELIGIBILITIES
        if code != TRAINABLE_EVIDENCE_ELIGIBILITY
    ]
    held_back += [
        await _evaluation(
            async_session, reviewer, fragrance, worn_by_reviewer_id=other.id
        ),
        await _evaluation(
            async_session, reviewer, fragrance, deleted_at=now_naive_utc()
        ),
        await _evaluation(async_session, reviewer, excluded),
        await _evaluation(async_session, reviewer, deleted),
    ]
    await _with_view(async_session)

    ids = await _view_ids(async_session)

    assert ids == {eligible.id}
    assert not ids & {row.id for row in held_back}
    row = (
        await async_session.execute(
            text("SELECT * FROM v_training_rows WHERE row_id = :id"),
            {"id": eligible.id},
        )
    ).one()
    assert row.workflow == "ORDINARY"
    assert row.scale == "1-5"
    assert row.rating == 4
    assert row.stage is None
    assert row.reviewer_id == reviewer.id
    assert row.fragrance_id == fragrance.id


@pytest.mark.asyncio
async def test_a_holdout_version_never_trains_in_either_workflow(
    async_session: AsyncSession,
) -> None:
    """A HOLDOUT in any of the reviewer's programs hides the version everywhere."""
    reviewer = await _reviewer(async_session)
    holdout = await _fragrance(async_session, "Holdout")
    program, calibration = await _enrollment(async_session, reviewer)
    controlled = await _observation(
        async_session, program, calibration, holdout, role="HOLDOUT"
    )
    # The same version as a baseline in a second program, and as an
    # ordinary encounter: both still hidden.
    second, second_session = await _enrollment(async_session, reviewer, "Q")
    baseline = await _observation(async_session, second, second_session, holdout)
    ordinary = await _evaluation(async_session, reviewer, holdout)
    # Another reviewer's rating of the same version is not affected.
    stranger = await _reviewer(async_session, "Stranger")
    unaffected = await _evaluation(async_session, stranger, holdout)
    await _with_view(async_session)

    ids = await _view_ids(async_session)

    assert {controlled.id, baseline.id, ordinary.id}.isdisjoint(ids)
    assert unaffected.id in ids


@pytest.mark.asyncio
async def test_the_view_applies_the_controlled_structural_rules(
    async_session: AsyncSession,
) -> None:
    reviewer = await _reviewer(async_session)
    program, calibration = await _enrollment(async_session, reviewer)

    async def observe(**kwargs: object) -> Observation:
        fragrance = await _fragrance(async_session, f"F{len(kwargs)}{kwargs}")
        return await _observation(
            async_session,
            program,
            calibration,
            fragrance,
            **kwargs,  # pyright: ignore[reportArgumentType]
        )

    skin = await observe()
    blotter = await observe(stage="BLOTTER")
    completed = await observe(response_status="completed")
    excluded = [
        await observe(eligibility="unreviewed"),
        await observe(eligibility="questionable"),
        await observe(role="HIDDEN_REPEAT"),
        await observe(phase="POST_REVEAL"),
        await observe(phase="PREVIOUSLY_REVEALED"),
        await observe(locked=False),
        await observe(stage="BLOTTER", locked=False),
        await observe(liking=None),
        await observe(response_status="interrupted"),
        await observe(response_status="invalidated"),
    ]
    await _with_view(async_session)

    ids = await _view_ids(async_session)

    assert ids == {skin.id, blotter.id, completed.id}
    assert not ids & {row.id for row in excluded}
    row = (
        await async_session.execute(
            text("SELECT * FROM v_training_rows WHERE row_id = :id"),
            {"id": skin.id},
        )
    ).one()
    assert row.workflow == "CONTROLLED"
    assert row.scale == "0-10"
    assert row.rating == 7
    assert row.stage == "SKIN"
    assert row.reviewer_id == reviewer.id


@pytest.mark.asyncio
async def test_a_locked_stage_must_be_the_observed_stage(
    async_session: AsyncSession,
) -> None:
    """A SKIN row needs the skin lock, not the blotter lock."""
    reviewer = await _reviewer(async_session)
    program, calibration = await _enrollment(async_session, reviewer)
    row = await _observation(
        async_session, program, calibration, await _fragrance(async_session)
    )
    presentation = await async_session.get(Presentation, row.presentation_id)
    assert presentation is not None
    presentation.skin_locked_at = None
    presentation.blotter_locked_at = now_naive_utc() - timedelta(minutes=5)
    await async_session.flush()
    await _with_view(async_session)

    assert row.id not in await _view_ids(async_session)


# --- the migration ----------------------------------------------------------


class _Batch:
    """Stand-in for ``op.batch_alter_table`` that records into its parent."""

    def __init__(self, parent: _RecordingOp, table: str) -> None:
        self.parent = parent
        self.table = table

    def __enter__(self) -> _Batch:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def add_column(self, column: sa.Column[object]) -> None:
        self.parent.columns[(self.table, column.name)] = column

    def create_check_constraint(self, name: str, condition: str) -> None:
        self.parent.checks[name] = condition

    def create_foreign_key(self, name: str, *_args: object, **_kw: object) -> None:
        self.parent.others.add(name)

    def create_index(self, name: str, *_args: object, **_kw: object) -> None:
        self.parent.others.add(name)


class _RecordingOp:
    """Stand-in for ``alembic.op`` recording what ``upgrade`` creates."""

    def __init__(self, bind: sa.Connection) -> None:
        self.bind = bind
        self.checks: dict[str, str] = {}
        self.columns: dict[tuple[str, str], sa.Column[object]] = {}
        self.others: set[str] = set()
        self.executed: list[str] = []

    def get_bind(self) -> sa.Connection:
        return self.bind

    def create_table(self, name: str, *items: object) -> None:
        for item in items:
            if isinstance(item, sa.CheckConstraint):
                self.checks[str(item.name)] = str(item.sqltext)
            elif isinstance(item, sa.Column):
                self.columns[(name, item.name)] = item  # pyright: ignore[reportUnknownMemberType]
            elif isinstance(item, sa.Constraint):
                self.others.add(str(item.name))

    def create_index(self, name: str, *_args: object, **_kw: object) -> None:
        self.others.add(name)

    def batch_alter_table(self, table: str) -> _Batch:
        return _Batch(self, table)

    def execute(self, statement: str) -> None:
        self.executed.append(statement)


def _empty_snapshots() -> sa.Connection:
    connection = sa.create_engine("sqlite://").connect()
    connection.execute(
        text(
            "CREATE TABLE calibration_source_snapshots "
            "(source_type TEXT, permission_state TEXT, fields TEXT)"
        )
    )
    return connection


def _recorded_upgrade(monkeypatch: pytest.MonkeyPatch) -> _RecordingOp:
    migration = _migration()
    recorder = _RecordingOp(_empty_snapshots())
    monkeypatch.setattr(migration, "op", recorder)
    migration.upgrade()
    return recorder


def _model_checks() -> dict[str, str]:
    """Every R8 CHECK the models declare, by full name."""
    rules = {
        "evaluations": ["training_eligibility_valid"],
        "calibration_observations": ["training_eligibility_valid"],
        "calibration_source_snapshots": [
            "source_permission_pair",
            "fields_allowed",
            "content_hash_sha256",
        ],
        "calibration_checkpoints": [
            "exclusions_is_array",
            "filters_is_object",
            "model_params_is_object",
            "input_digest_sha256",
        ],
        "calibration_checkpoint_predictions": [
            "target_scale",
            "value_in_scale",
            "uncertainty_nonnegative",
        ],
        "feature_snapshots": ["content_hash_sha256", "features_is_object"],
    }
    return {
        f"ck_{table}_{rule}": _check_text(table, rule)
        for table, table_rules in rules.items()
        for rule in table_rules
    }


def test_the_migration_writes_every_r8_check_exactly_as_the_models_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact text, not just the quoted values: the parity test only compares names."""
    recorder = _recorded_upgrade(monkeypatch)

    assert recorder.checks == _model_checks()


def test_the_migration_adds_the_columns_the_models_declare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _recorded_upgrade(monkeypatch)
    expected = {
        ("evaluations", "training_eligibility"),
        ("calibration_observations", "training_eligibility"),
        *(
            ("calibration_source_snapshots", c)
            for c in (
                "source_revision",
                "content_hash",
                "parser_version",
                "license_evidence",
                "verified_by",
            )
        ),
        *(
            ("calibration_checkpoints", c)
            for c in (
                "exclusions",
                "filters",
                "feature_space_version",
                "taxonomy_version",
                "model_params",
                "input_digest",
                "feature_snapshot_id",
            )
        ),
        ("prediction_snapshots", "feature_snapshot_id"),
    }
    added = {key for key in recorder.columns if key[0] in {t for t, _ in expected}}
    assert added == expected
    for table, name in recorder.columns:
        model = Base.metadata.tables[table].columns[name]
        migrated = recorder.columns[(table, name)]
        assert migrated.nullable == model.nullable, (table, name)
        assert type(migrated.type) is type(model.type), (table, name)
    for table in EVIDENCE_TABLES:
        default = recorder.columns[(table, "training_eligibility")].server_default
        assert default is not None
        assert default.arg == DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY  # pyright: ignore[reportAttributeAccessIssue]


def test_the_migration_creates_the_view_last(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _recorded_upgrade(monkeypatch)
    assert recorder.executed == [_migration().V_TRAINING_ROWS_SQL]


def _snapshot_bind(source_type: str, permission: str, fields: str) -> sa.Connection:
    connection = _empty_snapshots()
    connection.execute(
        text("INSERT INTO calibration_source_snapshots VALUES (:s, :p, :f)"),
        {"s": source_type, "p": permission, "f": fields},
    )
    return connection


def test_the_upgrade_guard_passes_valid_legacy_rows() -> None:
    bind = _snapshot_bind(
        "excluded_legacy",
        "excluded_no_new_writes",
        '["concentration", "launch_year", "brand"]',
    )
    assert _migration()._invalid_snapshots(bind) == []


def test_the_upgrade_guard_names_each_broken_check() -> None:
    bind = _snapshot_bind("excluded_legacy", "retain_and_train", '["perfume"]')
    assert _migration()._invalid_snapshots(bind) == [
        "calibration_source_snapshots source_permission_pair: 1 row(s)",
        "calibration_source_snapshots fields_allowed: 1 row(s)",
    ]


def test_the_upgrade_refuses_before_touching_the_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration()
    recorder = _RecordingOp(
        _snapshot_bind("bounded_lookup", "retain_and_train", '["gtin"]')
    )
    monkeypatch.setattr(migration, "op", recorder)

    with pytest.raises(RuntimeError, match=r"620c8c861268.*source_permission_pair"):
        migration.upgrade()
    assert not recorder.checks
    assert not recorder.executed


@pytest.mark.asyncio
async def test_the_downgrade_guard_sees_nothing_on_an_untouched_schema(
    async_session: AsyncSession,
) -> None:
    migration = _migration()
    await _evaluation(
        async_session,
        await _reviewer(async_session),
        await _fragrance(async_session),
        eligibility=None,
    )
    connection = await async_session.connection()
    assert await connection.run_sync(migration._r8_data) == []


@pytest.mark.asyncio
async def test_the_downgrade_guard_names_classified_evidence(
    async_session: AsyncSession,
) -> None:
    migration = _migration()
    reviewer = await _reviewer(async_session)
    await _evaluation(async_session, reviewer, await _fragrance(async_session))
    await _evaluation(
        async_session, reviewer, await _fragrance(async_session, "W"), "withheld"
    )
    connection = await async_session.connection()
    assert await connection.run_sync(migration._r8_data) == [
        "evaluations.training_eligibility: 2 row(s)"
    ]


def test_the_downgrade_refuses_while_r8_data_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration()
    recorder = _RecordingOp(_empty_snapshots())
    monkeypatch.setattr(migration, "op", recorder)
    monkeypatch.setattr(
        migration, "_r8_data", lambda _bind: ["feature_snapshots.rows: 1 row(s)"]
    )

    with pytest.raises(RuntimeError, match=r"620c8c861268.*feature_snapshots.*backup"):
        migration.downgrade()
    assert recorder.executed == []
