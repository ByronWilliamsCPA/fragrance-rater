"""First-class recommendation impression and outcome measurement endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.api.calibration import actor, manager
from fragrance_rater.core.auth import AuthenticatedIdentity, get_current_identity
from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.recommendation_measurement import (
    ImpressionView,
    MetricsView,
    OperationalEventCreate,
    ResponseCreate,
    ResponseView,
    RunCreate,
    RunView,
)
from fragrance_rater.services.recommendation_measurement_service import (
    MeasurementConflictError,
    RecommendationMeasurementService,
)
from fragrance_rater.services.recommendation_service import InsufficientDataError

router = APIRouter(prefix="/recommendation-measurement", tags=["recommendations"])
DB = Annotated[AsyncSession, Depends(get_db)]
Identity = Annotated[AuthenticatedIdentity, Depends(get_current_identity)]

if TYPE_CHECKING:
    from fragrance_rater.models.recommendation_measurement import (
        RecommendationResponseRevision,
    )


def response_view(item: RecommendationResponseRevision) -> ResponseView:
    """Serialize one append-only response revision."""
    return ResponseView.model_validate(item, from_attributes=True)


async def run_view(service: RecommendationMeasurementService, run_id: str) -> RunView:
    """Serialize a run without creating another impression."""
    run, rows = await service.run_rows(run_id)
    return RunView(
        id=run.id,
        reviewer_id=run.reviewer_id,
        algorithm_version=run.algorithm_version,
        candidate_strategy=run.candidate_strategy,
        created_at=run.created_at,
        impressions=[
            ImpressionView(
                id=impression.id,
                fragrance_id=fragrance.id,
                fragrance_name=fragrance.name,
                fragrance_brand=fragrance.brand,
                rank=impression.rank,
                score_type=impression.score_type,
                score_value=impression.score_value,
                match_percent=int(impression.score_value * 100),
            )
            for impression, fragrance in rows
        ],
    )


@router.post("/runs", response_model=RunView, status_code=status.HTTP_201_CREATED)
async def create_run(data: RunCreate, db: DB, identity: Identity) -> RunView:
    """Generate recommendations and persist their impressions atomically."""
    username, _ = actor(identity)
    service = RecommendationMeasurementService(db)
    try:
        run = await service.create_run(data, recorded_by=username)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InsufficientDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await run_view(service, run.id)


@router.get("/runs/{run_id}", response_model=RunView)
async def get_run(run_id: str, db: DB, identity: Identity) -> RunView:
    """Return an existing run; repeated views create no new impressions."""
    actor(identity)
    try:
        return await run_view(RecommendationMeasurementService(db), run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/impressions/{impression_id}/responses",
    response_model=ResponseView,
    status_code=status.HTTP_201_CREATED,
)
async def append_response(
    impression_id: str, data: ResponseCreate, db: DB, identity: Identity
) -> ResponseView:
    """Append feedback, preserving every prior response revision."""
    username, _ = actor(identity)
    try:
        item = await RecommendationMeasurementService(db).append_response(
            impression_id, data, recorded_by=username
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MeasurementConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return response_view(item)


@router.get("/reviewers/{reviewer_id}/metrics", response_model=MetricsView)
async def metrics(reviewer_id: str, db: DB, identity: Identity) -> MetricsView:
    """Return the admin metric contract with explicit counts and denominators."""
    manager(identity)
    return await RecommendationMeasurementService(db).metrics(reviewer_id)


@router.post("/operational-events", status_code=status.HTTP_201_CREATED)
async def operational_event(
    data: OperationalEventCreate, db: DB, identity: Identity
) -> dict[str, object]:
    """Record a pilot connectivity failure or subsequent manual recovery."""
    username, _ = actor(identity)
    try:
        item = await RecommendationMeasurementService(db).record_operational_event(
            data.reviewer_id, data.event_type, data.details, recorded_by=username
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": item.id,
        "event_type": item.event_type,
        "occurred_at": item.occurred_at,
    }
