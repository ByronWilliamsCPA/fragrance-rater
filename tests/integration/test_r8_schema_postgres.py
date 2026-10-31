"""R8 PR 1 against a PostgreSQL 16 database migrated to head.

The unit suite runs the migration's view SQL and the model CHECKs on SQLite;
this proves the same view and the portable CHECK bodies (``TRIM(x, chars)``,
``CAST(json AS TEXT)``, NaN handling) behave identically on the production
engine. Every test runs in one transaction and rolls it back.

Skipped unless ``P1_DATABASE_URL`` points at a migrated PostgreSQL database.
"""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from fragrance_rater.models.calibration import (
    CalibrationSession,
    CheckpointPrediction,
    Enrollment,
    Membership,
    ModelCheckpoint,
    Observation,
    Presentation,
    Program,
    SourceSnapshot,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

DATABASE_URL = os.getenv("P1_DATABASE_URL")
DIGEST = hashlib.sha256(b"r8-postgres").hexdigest()

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


async def _fragrance(db: AsyncSession) -> Fragrance:
    suffix = uuid4().hex
    fragrance = Fragrance(
        name=f"R8 {suffix}",
        brand="R8 house",
        concentration="EDP",
        version_key=f"r8-{suffix}",
        gender_target="Unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="r8",
    )
    db.add(fragrance)
    await db.flush()
    return fragrance


async def _rejects(db: AsyncSession, row: object) -> None:
    """Flush inside a savepoint so the outer test transaction survives."""
    nested = await db.begin_nested()
    db.add(row)
    with pytest.raises(IntegrityError):
        await db.flush()
    await nested.rollback()


@pytest.mark.asyncio
async def test_the_view_has_only_the_declared_columns(session: AsyncSession) -> None:
    columns = list(
        await session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'v_training_rows' ORDER BY ordinal_position"
            )
        )
    )
    assert columns == [
        "row_id",
        "workflow",
        "reviewer_id",
        "fragrance_id",
        "stage",
        "scale",
        "rating",
        "observed_at",
    ]


@pytest.mark.asyncio
async def test_existing_rows_default_to_unreviewed(session: AsyncSession) -> None:
    default = await session.scalar(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'evaluations' "
            "AND column_name = 'training_eligibility'"
        )
    )
    assert default is not None
    assert "'unreviewed'" in default


@pytest.mark.asyncio
async def test_the_view_filters_rows_on_postgresql(session: AsyncSession) -> None:
    reviewer = Reviewer(name=f"R8 rater {uuid4().hex}")
    session.add(reviewer)
    baseline = await _fragrance(session)
    holdout = await _fragrance(session)
    program = Program(name=f"R8 {uuid4().hex}", version="1")
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

    rows: dict[str, str] = {}
    for position, (fragrance, role) in enumerate(
        [(baseline, "UNIVERSAL_BASELINE"), (holdout, "HOLDOUT")], start=1
    ):
        member = Membership(program_id=program.id, fragrance_id=fragrance.id, role=role)
        session.add(member)
        await session.flush()
        presentation = Presentation(
            session_id=calibration.id,
            membership_id=member.id,
            blind_code=f"R8{position}",
            position=position,
            skin_locked_at=now_naive_utc(),
        )
        session.add(presentation)
        await session.flush()
        observation = Observation(
            presentation_id=presentation.id,
            stage="SKIN",
            phase="PRE_REVEAL",
            liking=8,
            detected=True,
            recorded_by="rec",
            training_eligibility="eligible",
        )
        session.add(observation)
        await session.flush()
        rows[role] = observation.id

    eligible = Evaluation(
        reviewer_id=reviewer.id,
        fragrance_id=baseline.id,
        rating=5,
        training_eligibility="eligible",
    )
    unreviewed = Evaluation(reviewer_id=reviewer.id, fragrance_id=baseline.id, rating=2)
    holdout_ordinary = Evaluation(
        reviewer_id=reviewer.id,
        fragrance_id=holdout.id,
        rating=3,
        training_eligibility="eligible",
    )
    session.add_all([eligible, unreviewed, holdout_ordinary])
    await session.flush()

    visible = set(
        await session.scalars(
            text("SELECT row_id FROM v_training_rows WHERE reviewer_id = :r"),
            {"r": reviewer.id},
        )
    )

    assert visible == {eligible.id, rows["UNIVERSAL_BASELINE"]}


@pytest.mark.asyncio
async def test_the_portable_checks_hold_on_postgresql(session: AsyncSession) -> None:
    fragrance = await _fragrance(session)

    def snapshot(**overrides: object) -> SourceSnapshot:
        values: dict[str, object] = {
            "fragrance_id": fragrance.id,
            "source_type": "manufacturer_provided",
            "permission_state": "retain_and_train",
            "fields": ["concentration", "gtin"],
            "source_reference": "Email reply from R8 house, 2026-10-31",
            "payload": {},
            "content_hash": DIGEST,
        }
        values.update(overrides)
        return SourceSnapshot(**values)

    session.add(snapshot())
    await session.flush()
    await _rejects(session, snapshot(fields=["perfumer"]))
    await _rejects(session, snapshot(fields=[["brand"]]))
    await _rejects(session, snapshot(content_hash=DIGEST.upper()))
    await _rejects(
        session,
        snapshot(source_type="excluded_legacy", permission_state="retain_and_train"),
    )
    reviewer = Reviewer(name=f"R8 checks {uuid4().hex}")
    session.add(reviewer)
    await session.flush()
    await _rejects(
        session,
        Evaluation(
            reviewer_id=reviewer.id,
            fragrance_id=fragrance.id,
            rating=3,
            training_eligibility="ELIGIBLE",
        ),
    )


@pytest.mark.asyncio
async def test_a_nan_prediction_is_rejected_on_postgresql(
    session: AsyncSession,
) -> None:
    """PostgreSQL treats NaN = NaN as true, so the range bound must catch it."""
    reviewer = Reviewer(name=f"R8 ckpt {uuid4().hex}")
    program = Program(name=f"R8 ckpt {uuid4().hex}", version="1")
    fragrance = await _fragrance(session)
    session.add_all([reviewer, program])
    await session.flush()
    enrollment = Enrollment(
        program_id=program.id, reviewer_id=reviewer.id, recorder_usernames=["rec"]
    )
    session.add(enrollment)
    await session.flush()
    checkpoint = ModelCheckpoint(
        enrollment_id=enrollment.id,
        algorithm_version="affinity-v2",
        manifest=[],
        predictions=[],
        input_digest=DIGEST,
        exclusions=[],
        filters={},
        model_params={},
    )
    session.add(checkpoint)
    await session.flush()

    def prediction(**overrides: object) -> CheckpointPrediction:
        values: dict[str, object] = {
            "checkpoint_id": checkpoint.id,
            "fragrance_id": fragrance.id,
            "target": "liking",
            "scale": "0-10",
            "value": 5.0,
        }
        values.update(overrides)
        return CheckpointPrediction(**values)

    await _rejects(session, prediction(value=float("nan")))
    await _rejects(session, prediction(uncertainty=float("nan")))
    session.add(prediction(uncertainty=1.0))
    await session.flush()
