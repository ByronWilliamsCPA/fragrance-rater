"""First-class recommendation impression and outcome measurement endpoints."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - FastAPI resolves this at runtime
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.api.calibration import actor, manager
from fragrance_rater.api.recommendations import (
    ExplanationResponse,
    build_recommendation_explanation,
)
from fragrance_rater.core.auth import AuthenticatedIdentity, get_current_identity
from fragrance_rater.core.database import get_db
from fragrance_rater.middleware import RATINGS_RATE_LIMIT, limiter
from fragrance_rater.models.calibration import Enrollment
from fragrance_rater.models.recommendation_measurement import (
    PilotOperationalEvent,
    RecommendationImpression,
    RecommendationRun,
)
from fragrance_rater.schemas.recommendation_measurement import (
    ImpressionView,
    MetricsView,
    OperationalEventCreate,
    ResponseCreate,
    ResponseView,
    RunCreate,
    RunView,
)
from fragrance_rater.services.llm_service import LLMService, get_llm_service
from fragrance_rater.services.recommendation_measurement_service import (
    MeasurementConflictError,
    RecommendationMeasurementService,
)
from fragrance_rater.services.recommendation_service import (
    InsufficientDataError,
    RecommendationService,
)

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
    raw_candidates = run.source_snapshot.get("candidate_versions")
    candidates = raw_candidates if isinstance(raw_candidates, list) else []
    snapshots: dict[str, dict[str, object]] = {}
    for raw_item in candidates:
        if not isinstance(raw_item, dict):
            continue
        item = cast("dict[str, object]", raw_item)
        fragrance_id = item.get("fragrance_id")
        if isinstance(fragrance_id, str):
            snapshots[fragrance_id] = item
    histories = await service.response_history(
        {impression.id for impression, _ in rows}
    )
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
                fragrance_name=str(
                    snapshots.get(fragrance.id, {}).get("name", fragrance.name)
                ),
                fragrance_brand=str(
                    snapshots.get(fragrance.id, {}).get("brand", fragrance.brand)
                ),
                rank=impression.rank,
                score_type=impression.score_type,
                score_value=impression.score_value,
                match_percent=int(impression.score_value * 100),
                shown_at=impression.shown_at,
                responses=[
                    response_view(response) for response in histories[impression.id]
                ],
            )
            for impression, fragrance in rows
        ],
    )


async def authorize_reviewer(
    db: AsyncSession, reviewer_id: str, username: str, admin: bool
) -> None:
    """Allow managers or recorders explicitly assigned to the reviewer."""
    if admin:
        return
    enrollments = await db.scalars(
        select(Enrollment).where(Enrollment.reviewer_id == reviewer_id)
    )
    if not any(username in enrollment.recorder_usernames for enrollment in enrollments):
        raise HTTPException(
            status_code=403, detail="Recorder is not assigned to reviewer"
        )


async def run_reviewer_id(db: AsyncSession, run_id: str) -> str:
    """Resolve a run owner without exposing another reviewer's data."""
    reviewer_id = await db.scalar(
        select(RecommendationRun.reviewer_id).where(RecommendationRun.id == run_id)
    )
    if reviewer_id is None:
        raise HTTPException(status_code=404, detail="recommendation run not found")
    return reviewer_id


async def impression_reviewer_id(db: AsyncSession, impression_id: str) -> str:
    """Resolve an impression owner for reviewer-scoped authorization."""
    reviewer_id = await db.scalar(
        select(RecommendationRun.reviewer_id)
        .join(
            RecommendationImpression,
            RecommendationImpression.run_id == RecommendationRun.id,
        )
        .where(RecommendationImpression.id == impression_id)
    )
    if reviewer_id is None:
        raise HTTPException(
            status_code=404, detail="recommendation impression not found"
        )
    return reviewer_id


@router.post("/runs", response_model=RunView, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATINGS_RATE_LIMIT)  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType]
async def create_run(
    request: Request,  # noqa: ARG001 - required by SlowAPI
    data: RunCreate,
    db: DB,
    identity: Identity,
) -> RunView:
    """Generate recommendations and persist their impressions atomically."""
    username, admin = actor(identity)
    await authorize_reviewer(db, data.reviewer_id, username, admin)
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
    username, admin = actor(identity)
    reviewer_id = await run_reviewer_id(db, run_id)
    await authorize_reviewer(db, reviewer_id, username, admin)
    try:
        return await run_view(RecommendationMeasurementService(db), run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/impressions/{impression_id}/explanation",
    response_model=ExplanationResponse,
    responses={429: {"description": "Rate limit exceeded; retry after a short delay."}},
)
@limiter.limit(RATINGS_RATE_LIMIT)  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType]
async def get_impression_explanation(
    request: Request,  # noqa: ARG001 - required by SlowAPI
    impression_id: str,
    db: DB,
    identity: Identity,
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
) -> ExplanationResponse:
    """Explain an existing impression to its assigned recorder."""
    username, admin = actor(identity)
    impression = await db.get(RecommendationImpression, impression_id)
    if impression is None:
        raise HTTPException(
            status_code=404, detail="recommendation impression not found"
        )
    reviewer_id = await impression_reviewer_id(db, impression_id)
    await authorize_reviewer(db, reviewer_id, username, admin)
    return await build_recommendation_explanation(
        reviewer_id=reviewer_id,
        fragrance_id=impression.fragrance_id,
        session=db,
        service=RecommendationService(db),
        llm_service=llm_service,
    )


@router.post(
    "/impressions/{impression_id}/responses",
    response_model=ResponseView,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Impression not found"},
        409: {"description": "Measurement conflict"},
    },
)
async def append_response(
    impression_id: str, data: ResponseCreate, db: DB, identity: Identity
) -> ResponseView:
    """Append feedback, preserving every prior response revision."""
    username, admin = actor(identity)
    reviewer_id = await impression_reviewer_id(db, impression_id)
    await authorize_reviewer(db, reviewer_id, username, admin)
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
async def metrics(
    reviewer_id: str,
    db: DB,
    identity: Identity,
    window_start: Annotated[datetime | None, Query()] = None,
    window_end: Annotated[datetime | None, Query()] = None,
) -> MetricsView:
    """Return the admin metric contract with explicit counts and denominators."""
    manager(identity)
    try:
        return await RecommendationMeasurementService(db).metrics(
            reviewer_id, window_start=window_start, window_end=window_end
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/operational-events")
async def operational_events(
    db: DB,
    identity: Identity,
    reviewer_id: Annotated[str | None, Query()] = None,
) -> list[dict[str, object]]:
    """List recent pilot failures and recoveries for manager follow-up."""
    manager(identity)
    statement = select(PilotOperationalEvent).order_by(
        PilotOperationalEvent.occurred_at.desc()
    )
    if reviewer_id is not None:
        statement = statement.where(PilotOperationalEvent.reviewer_id == reviewer_id)
    return [
        {
            "id": item.id,
            "reviewer_id": item.reviewer_id,
            "event_type": item.event_type,
            "details": item.details,
            "occurred_at": item.occurred_at,
            "recorded_by": item.recorded_by,
        }
        for item in await db.scalars(statement.limit(100))
    ]


@router.get("/operational-status")
async def operational_status(db: DB, identity: Identity) -> dict[str, object]:
    """Report unresolved pilot connectivity incidents without infrastructure detail."""
    manager(identity)
    ranked = select(
        PilotOperationalEvent.reviewer_id,
        PilotOperationalEvent.event_type,
        func.row_number()
        .over(
            partition_by=PilotOperationalEvent.reviewer_id,
            order_by=(
                PilotOperationalEvent.occurred_at.desc(),
                PilotOperationalEvent.id.desc(),
            ),
        )
        .label("position"),
    ).subquery()
    unresolved = sorted(
        await db.scalars(
            select(ranked.c.reviewer_id).where(
                ranked.c.position == 1,
                ranked.c.event_type == "CONNECTIVITY_FAILURE",
            )
        )
    )
    return {
        "status": "attention" if unresolved else "available",
        "unresolved_reviewer_ids": unresolved,
        "guidance": (
            "Use the paper fallback and record a recovery after data entry resumes."
            if unresolved
            else "No unresolved pilot connectivity incidents."
        ),
    }


@router.post("/operational-events", status_code=status.HTTP_201_CREATED)
async def operational_event(
    data: OperationalEventCreate, db: DB, identity: Identity
) -> dict[str, object]:
    """Record a pilot connectivity failure or subsequent manual recovery."""
    username, admin = actor(identity)
    await authorize_reviewer(db, data.reviewer_id, username, admin)
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
