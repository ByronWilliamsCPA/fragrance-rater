"""R8 PR 2 against a PostgreSQL 16 database migrated to head (4edb5c967539).

SQLite has no PL/pgSQL, no ``jsonb``, and no session ``TimeZone``, so the
immutability triggers (D-08/Q14), the ``jsonb`` columns (D-12), the UTC server
defaults and startup assertion (D-16/Q16), and the idempotency constraint
(D-22/Q18) are proved here. Every test runs in one transaction and rolls it
back; an expected failure runs inside a savepoint so the test can continue.

Each trigger test pairs the refused write with the write it must still allow
(the negative control): the trigger is not simply refusing everything.

Skipped unless ``P1_DATABASE_URL`` points at a migrated PostgreSQL database.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from fragrance_rater.core.database import assert_database_timezone_is_utc
from fragrance_rater.core.exceptions import ConfigurationError
from fragrance_rater.models.calibration import (
    CalibrationSession,
    CheckpointPrediction,
    Enrollment,
    Membership,
    ModelCheckpoint,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.feature_snapshot import FeatureSnapshot
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

DATABASE_URL = os.getenv("P1_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="P1_DATABASE_URL is not configured"),
]


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as db:
            yield db
        await transaction.rollback()
    await engine.dispose()


async def _refused(db: AsyncSession, write: Callable[[], Awaitable[Any]]) -> str:
    """Run ``write`` in a savepoint, expect the trigger's refusal, return it."""
    nested = await db.begin_nested()

    async def write_and_flush() -> None:
        await write()
        await db.flush()

    with pytest.raises(IntegrityError) as refused:
        await write_and_flush()
    await nested.rollback()
    return str(refused.value.orig)


async def _allowed(db: AsyncSession, write: Callable[[], Awaitable[Any]]) -> None:
    """Run ``write`` in a savepoint and keep it."""
    nested = await db.begin_nested()
    await write()
    await db.flush()
    await nested.commit()


async def _exec(db: AsyncSession, sql: str, **params: object) -> None:
    await db.execute(text(sql), params)


async def _fragrance(db: AsyncSession) -> Fragrance:
    suffix = uuid4().hex
    fragrance = Fragrance(
        name=f"R8 PR2 {suffix}",
        brand="R8 house",
        concentration="EDP",
        version_key=f"r8p2-{suffix}",
        gender_target="Unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="r8p2",
    )
    db.add(fragrance)
    await db.flush()
    return fragrance


async def _world(db: AsyncSession, *, status: str = "active") -> dict[str, Any]:
    """A program (``status``), one membership, enrollment, sample, answer."""
    reviewer = Reviewer(name=f"R8 PR2 {uuid4().hex}")
    db.add(reviewer)
    fragrance = await _fragrance(db)
    program = Program(name=f"R8 PR2 {uuid4().hex}", version="1")
    db.add(program)
    await db.flush()
    member = Membership(
        program_id=program.id, fragrance_id=fragrance.id, role="UNIVERSAL_BASELINE"
    )
    db.add(member)
    await db.flush()
    # Activation after the membership exists, as the service does it.
    program.status = status
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    db.add(enrollment)
    await db.flush()
    calibration = CalibrationSession(enrollment_id=enrollment.id)
    db.add(calibration)
    await db.flush()
    presentation = Presentation(
        session_id=calibration.id,
        membership_id=member.id,
        blind_code=f"P2{uuid4().hex[:8]}",
        position=1,
    )
    db.add(presentation)
    await db.flush()
    observation = Observation(
        presentation_id=presentation.id,
        stage="BLOTTER",
        phase="PRE_REVEAL",
        detected=True,
        intensity=3,
        liking=6,
        recorded_by="rec",
    )
    db.add(observation)
    await db.flush()
    return {
        "reviewer": reviewer,
        "fragrance": fragrance,
        "program": program,
        "member": member,
        "enrollment": enrollment,
        "presentation": presentation,
        "observation": observation,
    }


# --- D-08: append-only observations --------------------------------------------


@pytest.mark.asyncio
async def test_an_observation_changes_only_its_eligibility(
    session: AsyncSession,
) -> None:
    world = await _world(session)
    row_id = world["observation"].id

    message = await _refused(
        session,
        lambda: _exec(
            session,
            "UPDATE calibration_observations SET liking = 9 WHERE id = :id",
            id=row_id,
        ),
    )
    assert "append-only" in message
    await _refused(
        session,
        lambda: _exec(
            session,
            "UPDATE calibration_observations "
            "SET liking = 9, training_eligibility = 'eligible' WHERE id = :id",
            id=row_id,
        ),
    )
    await _refused(
        session,
        lambda: _exec(
            session, "DELETE FROM calibration_observations WHERE id = :id", id=row_id
        ),
    )
    # Negative control: the one sanctioned in-place write still works.
    await _allowed(
        session,
        lambda: _exec(
            session,
            "UPDATE calibration_observations "
            "SET training_eligibility = 'withheld' WHERE id = :id",
            id=row_id,
        ),
    )
    stored = await session.scalar(
        text(
            "SELECT training_eligibility FROM calibration_observations WHERE id = :id"
        ),
        {"id": row_id},
    )
    assert stored == "withheld"


@pytest.mark.asyncio
async def test_the_service_promotes_through_the_trigger(session: AsyncSession) -> None:
    """Option C's lock-time promotion is exactly the write the trigger allows."""
    world = await _world(session)

    await CalibrationService(session).lock_stage(
        world["presentation"].id, "BLOTTER", "manager", admin=True
    )

    stored = await session.scalar(
        text(
            "SELECT training_eligibility FROM calibration_observations WHERE id = :id"
        ),
        {"id": world["observation"].id},
    )
    assert stored == "eligible"
    assert (
        await session.scalar(
            text("SELECT count(*) FROM v_training_rows WHERE row_id = :id"),
            {"id": world["observation"].id},
        )
        == 1
    )


# --- D-08: frozen checkpoints, typed predictions, feature snapshots -------------


async def _checkpoint(db: AsyncSession, world: dict[str, Any]) -> ModelCheckpoint:
    snapshot = FeatureSnapshot(
        feature_space_version="fs-v2",
        content_hash=uuid4().hex + uuid4().hex,
        features={"x": {"notes": []}},
    )
    db.add(snapshot)
    await db.flush()
    checkpoint = ModelCheckpoint(
        enrollment_id=world["enrollment"].id,
        algorithm_version="frozen-test",
        manifest=[],
        predictions=[],
        feature_snapshot_id=snapshot.id,
    )
    db.add(checkpoint)
    await db.flush()
    db.add(
        CheckpointPrediction(
            checkpoint_id=checkpoint.id,
            fragrance_id=world["fragrance"].id,
            target="liking",
            scale="0-10",
            value=5.0,
        )
    )
    await db.flush()
    return checkpoint


FROZEN_STATEMENTS = {
    "calibration_checkpoints": (
        "UPDATE calibration_checkpoints SET algorithm_version = 'x' WHERE id = :key",
        "DELETE FROM calibration_checkpoints WHERE id = :key",
        "SELECT count(*) FROM calibration_checkpoints WHERE id = :key",
    ),
    "calibration_checkpoint_predictions": (
        (
            "UPDATE calibration_checkpoint_predictions SET value = 9 "
            "WHERE checkpoint_id = :key"
        ),
        "DELETE FROM calibration_checkpoint_predictions WHERE checkpoint_id = :key",
        (
            "SELECT count(*) FROM calibration_checkpoint_predictions "
            "WHERE checkpoint_id = :key"
        ),
    ),
    "feature_snapshots": (
        "UPDATE feature_snapshots SET taxonomy_version = 'x' WHERE id = :key",
        "DELETE FROM feature_snapshots WHERE id = :key",
        "SELECT count(*) FROM feature_snapshots WHERE id = :key",
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("table", sorted(FROZEN_STATEMENTS))
async def test_frozen_rows_refuse_update_and_delete(
    session: AsyncSession, table: str
) -> None:
    world = await _world(session)
    checkpoint = await _checkpoint(session, world)
    key = (
        checkpoint.feature_snapshot_id
        if table == "feature_snapshots"
        else checkpoint.id
    )
    update_sql, delete_sql, count_sql = FROZEN_STATEMENTS[table]

    message = await _refused(session, lambda: _exec(session, update_sql, key=key))
    assert "frozen" in message
    await _refused(session, lambda: _exec(session, delete_sql, key=key))
    # Negative control: the rows are still present and readable.
    assert await session.scalar(text(count_sql), {"key": key}) == 1


# --- D-08: frozen predictions -------------------------------------------------


@pytest.mark.asyncio
async def test_a_prediction_accepts_only_its_one_outcome_link(
    session: AsyncSession,
) -> None:
    world = await _world(session)
    evaluation = Evaluation(
        reviewer_id=world["reviewer"].id,
        fragrance_id=world["fragrance"].id,
        rating=4,
    )
    other = Evaluation(
        reviewer_id=world["reviewer"].id,
        fragrance_id=world["fragrance"].id,
        rating=2,
    )
    snapshot = PredictionSnapshot(
        reviewer_id=world["reviewer"].id,
        fragrance_id=world["fragrance"].id,
        model_id="m",
        model_version="1",
        predicted_scale="1-5",
        predicted_rating=3.0,
        input_manifest=[],
    )
    session.add_all([evaluation, other, snapshot])
    await session.flush()

    await _refused(
        session,
        lambda: session.execute(
            update(PredictionSnapshot)
            .where(PredictionSnapshot.id == snapshot.id)
            .values(predicted_rating=4.0)
        ),
    )
    await _refused(
        session,
        lambda: _exec(
            session, "DELETE FROM prediction_snapshots WHERE id = :id", id=snapshot.id
        ),
    )
    # Negative control: linking the outcome once is the allowed write.
    link = {
        "outcome_evaluation_id": evaluation.id,
        "outcome_linked_at": now_naive_utc(),
        "outcome_recorded_by": "manager",
    }
    await _allowed(
        session,
        lambda: session.execute(
            update(PredictionSnapshot)
            .where(PredictionSnapshot.id == snapshot.id)
            .values(**link)
        ),
    )
    message = await _refused(
        session,
        lambda: session.execute(
            update(PredictionSnapshot)
            .where(PredictionSnapshot.id == snapshot.id)
            .values(outcome_evaluation_id=other.id)
        ),
    )
    assert "exactly once" in message


# --- D-08: activated membership ----------------------------------------------


@pytest.mark.asyncio
async def test_an_active_programs_membership_is_immutable(
    session: AsyncSession,
) -> None:
    world = await _world(session)
    member_id = world["member"].id

    await _refused(
        session,
        lambda: _exec(
            session,
            "UPDATE calibration_memberships SET role = 'HOLDOUT' WHERE id = :id",
            id=member_id,
        ),
    )
    await _refused(
        session,
        lambda: _exec(
            session, "DELETE FROM calibration_memberships WHERE id = :id", id=member_id
        ),
    )
    extra = await _fragrance(session)
    await _refused(
        session,
        lambda: _exec(
            session,
            "INSERT INTO calibration_memberships "
            "(id, program_id, fragrance_id, role, group_name, selection) "
            "VALUES (:id, :p, :f, 'UNIVERSAL_BASELINE', 'Baseline', '{}')",
            id=str(uuid4()),
            p=world["program"].id,
            f=extra.id,
        ),
    )


@pytest.mark.asyncio
async def test_a_draft_programs_membership_stays_editable(
    session: AsyncSession,
) -> None:
    """Negative control: the trigger keys on ``active``, not on the table."""
    world = await _world(session, status="draft")
    member_id = world["member"].id

    await _allowed(
        session,
        lambda: _exec(
            session,
            "UPDATE calibration_memberships SET group_name = 'Renamed' WHERE id = :id",
            id=member_id,
        ),
    )
    assert (
        await session.scalar(
            text("SELECT group_name FROM calibration_memberships WHERE id = :id"),
            {"id": member_id},
        )
        == "Renamed"
    )


# --- D-08: assigned identity ---------------------------------------------------


IDENTITY_UPDATES = (
    "UPDATE fragrances SET name = 'Renamed' WHERE id = :id",
    "UPDATE fragrances SET concentration = 'EDT' WHERE id = :id",
    "UPDATE fragrances SET version_key = 'rekeyed' || id WHERE id = :id",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("statement", IDENTITY_UPDATES)
async def test_an_assigned_versions_identity_is_immutable(
    session: AsyncSession, statement: str
) -> None:
    world = await _world(session, status="draft")
    fragrance_id = world["fragrance"].id

    message = await _refused(
        session, lambda: _exec(session, statement, id=fragrance_id)
    )
    assert "assigned to calibration" in message
    # Negative controls: a non-identity column on the same row, and an identity
    # column on a version no membership references.
    await _allowed(
        session,
        lambda: _exec(
            session,
            "UPDATE fragrances SET external_id = 'ext-1' WHERE id = :id",
            id=fragrance_id,
        ),
    )
    free = await _fragrance(session)
    await _allowed(session, lambda: _exec(session, statement, id=free.id))


# --- D-12: jsonb ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_json_column_is_jsonb(session: AsyncSession) -> None:
    types = dict(
        (
            await session.execute(
                text(
                    "SELECT data_type, count(*) FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND data_type IN ('json', 'jsonb') GROUP BY data_type"
                )
            )
        ).all()
    )
    assert types == {"jsonb": 19}


@pytest.mark.asyncio
async def test_json_shape_checks_still_hold_on_jsonb(session: AsyncSession) -> None:
    world = await _world(session)

    async def bad_notes() -> None:
        session.add(
            Observation(
                presentation_id=world["presentation"].id,
                stage="BLOTTER",
                phase="PRE_REVEAL",
                perceived_notes={"not": "an array"},  # pyright: ignore[reportArgumentType]
                recorded_by="rec",
            )
        )

    await _refused(session, bad_notes)

    async def good_notes() -> None:
        session.add(
            Observation(
                presentation_id=world["presentation"].id,
                stage="BLOTTER",
                phase="PRE_REVEAL",
                perceived_notes=["cedar", "rose"],
                recorded_by="rec",
            )
        )

    await _allowed(session, good_notes)
    # jsonb containment, impossible on plain json, now works.
    assert (
        await session.scalar(
            text(
                "SELECT count(*) FROM calibration_observations "
                "WHERE perceived_notes @> '[\"cedar\"]'::jsonb "
                "AND presentation_id = :p"
            ),
            {"p": world["presentation"].id},
        )
        == 1
    )


# --- D-16: UTC ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_defaults_are_utc_whatever_the_session_zone(
    session: AsyncSession,
) -> None:
    await session.execute(text("SET LOCAL TIME ZONE 'America/Chicago'"))
    name = f"UTC probe {uuid4().hex}"
    await session.execute(
        text("INSERT INTO reviewers (id, name) VALUES (:id, :name)"),
        {"id": str(uuid4()), "name": name},
    )
    row = (
        await session.execute(
            text(
                "SELECT created_at, timezone('utc', now()) AS utc, "
                "now()::timestamp AS local FROM reviewers WHERE name = :name"
            ),
            {"name": name},
        )
    ).one()

    assert row.created_at == row.utc
    # Negative control: a plain now() default would have stored local time,
    # five or six hours away from UTC in Chicago.
    assert abs(row.utc - row.local) >= timedelta(hours=5)


@pytest.mark.asyncio
async def test_every_clock_default_is_utc_in_the_catalog(session: AsyncSession) -> None:
    defaults = dict(
        (
            await session.execute(
                text(
                    "SELECT table_name || '.' || column_name, column_default "
                    "FROM information_schema.columns WHERE table_schema = 'public' "
                    "AND data_type LIKE 'timestamp%' AND column_default IS NOT NULL"
                )
            )
        ).all()
    )
    assert len(defaults) == 8
    assert all("timezone('utc'" in str(value) for value in defaults.values())


@pytest.mark.asyncio
async def test_the_startup_assertion_reads_the_real_session_zone() -> None:
    assert DATABASE_URL is not None
    utc = create_async_engine(DATABASE_URL)
    chicago = create_async_engine(
        DATABASE_URL, connect_args={"server_settings": {"timezone": "America/Chicago"}}
    )
    try:
        assert (await assert_database_timezone_is_utc(utc) or "").lower() in {
            "utc",
            "etc/utc",
        }
        with pytest.raises(ConfigurationError, match="America/Chicago"):
            await assert_database_timezone_is_utc(chicago)
    finally:
        await utc.dispose()
        await chicago.dispose()


# --- D-22: idempotency -------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_key_per_presentation_is_enforced(session: AsyncSession) -> None:
    world = await _world(session)

    def keyed(key: str | None) -> Observation:
        return Observation(
            presentation_id=world["presentation"].id,
            stage="BLOTTER",
            phase="PRE_REVEAL",
            recorded_by="rec",
            idempotency_key=key,
        )

    async def add(key: str | None) -> None:
        session.add(keyed(key))

    await _allowed(session, lambda: add("retry-key-0001"))
    await _refused(session, lambda: add("retry-key-0001"))
    # Negative controls: another key, and two keyless rows, both append.
    await _allowed(session, lambda: add("retry-key-0002"))
    await _allowed(session, lambda: add(None))
    await _allowed(session, lambda: add(None))


# --- X-06: the views -------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_linkage_view_carries_what_the_trainer_view_omits(
    session: AsyncSession,
) -> None:
    trainer = set(
        await session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'v_training_rows'"
            )
        )
    )
    linkage = set(
        await session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'v_manager_linkage'"
            )
        )
    )
    omitted = {"role", "repeat_of_membership_id", "program_id", "session_id"}
    assert omitted <= linkage
    assert not omitted & trainer
    assert "row_id" in trainer & linkage


@pytest.mark.asyncio
async def test_a_later_answer_supersedes_on_postgresql(session: AsyncSession) -> None:
    world = await _world(session)
    world["presentation"].blotter_locked_at = now_naive_utc()
    earlier = world["observation"]
    await session.execute(
        text(
            "UPDATE calibration_observations SET training_eligibility = 'eligible' "
            "WHERE id = :id"
        ),
        {"id": earlier.id},
    )
    later = Observation(
        presentation_id=world["presentation"].id,
        stage="BLOTTER",
        phase="PRE_REVEAL",
        detected=True,
        intensity=3,
        liking=8,
        recorded_by="rec",
        training_eligibility="eligible",
        created_at=earlier.created_at + timedelta(seconds=1),
    )
    session.add(later)
    await session.flush()

    visible = set(
        await session.scalars(
            text("SELECT row_id FROM v_training_rows WHERE reviewer_id = :r"),
            {"r": world["reviewer"].id},
        )
    )
    assert visible == {later.id}
