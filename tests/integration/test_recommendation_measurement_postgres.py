"""PostgreSQL 16 gate for recommendation measurement and holdout policy."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fragrance_rater.models.calibration import Enrollment, Membership, Program
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.recommendation_measurement import ResponseCreate, RunCreate
from fragrance_rater.services.recommendation_measurement_service import (
    RecommendationMeasurementService,
)

DATABASE_URL = os.getenv("P1_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.skipif(not DATABASE_URL, reason="P1_DATABASE_URL is not configured")
@pytest.mark.asyncio
async def test_postgres_run_feedback_metrics_and_holdout_exclusion() -> None:
    """Exercise P2's write path and blind invariant on the target engine."""
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex
    async with session_factory() as session:
        reviewer = Reviewer(name=f"P1 gate {suffix}")
        fragrances = [
            Fragrance(
                name=f"P1 scent {index} {suffix}",
                brand="P1 gate house",
                concentration="EDP",
                version_key=f"p1-{index}-{suffix}",
                gender_target="Unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="p1-gate",
            )
            for index in range(5)
        ]
        session.add_all([reviewer, *fragrances])
        await session.flush()
        session.add_all(
            [
                Evaluation(
                    reviewer_id=reviewer.id,
                    fragrance_id=fragrance.id,
                    rating=5,
                )
                for fragrance in fragrances[:3]
            ]
        )
        program = Program(
            name=f"P1 holdout {suffix}",
            version="v1",
            description=None,
            status="active",
        )
        session.add(program)
        await session.flush()
        session.add_all(
            [
                Membership(
                    program_id=program.id,
                    fragrance_id=fragrances[3].id,
                    role="HOLDOUT",
                    repeat_of_id=None,
                    group_name="Gate",
                    selection={},
                ),
                Enrollment(
                    program_id=program.id,
                    reviewer_id=reviewer.id,
                    recorder_usernames=["p1-gate"],
                ),
            ]
        )
        await session.commit()

        service = RecommendationMeasurementService(session)
        run = await service.create_run(
            RunCreate(reviewer_id=reviewer.id, limit=10, exclude_rated=True),
            recorded_by="p1-gate",
        )
        _, rows = await service.run_rows(run.id)
        assert [fragrance.id for _, fragrance in rows] == [fragrances[4].id]
        response = await service.append_response(
            rows[0][0].id,
            ResponseCreate(interested=True, sampling_state="PLANNED"),
            recorded_by="p1-gate",
        )
        assert response.revision == 1
        metrics = await service.metrics(reviewer.id)
        assert metrics.eligible_impressions == 1
        assert metrics.positive_interest_responses == 1
        assert metrics.response_coverage == 1.0
    await engine.dispose()
