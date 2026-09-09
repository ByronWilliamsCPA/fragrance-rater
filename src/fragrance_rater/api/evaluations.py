"""Evaluation API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.evaluation import (
    EvaluationCreate,
    EvaluationResponse,
    EvaluationUpdate,
)
from fragrance_rater.services.evaluation_service import EvaluationService
from fragrance_rater.services.fragrance_service import FragranceService
from fragrance_rater.services.reviewer_service import ReviewerService

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


async def get_evaluation_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EvaluationService:
    """Dependency to get EvaluationService instance."""
    return EvaluationService(session)


async def get_fragrance_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FragranceService:
    """Dependency to get FragranceService instance (for FK validation)."""
    return FragranceService(session)


async def get_reviewer_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewerService:
    """Dependency to get ReviewerService instance (for FK validation)."""
    return ReviewerService(session)


@router.get("", response_model=list[EvaluationResponse])
async def list_evaluations(
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    reviewer_id: Annotated[
        str | None, Query(description="Filter by reviewer ID")
    ] = None,
    fragrance_id: Annotated[
        str | None, Query(description="Filter by fragrance ID")
    ] = None,
) -> list[EvaluationResponse]:
    """List evaluations with optional filters."""
    if reviewer_id:
        evaluations = await service.get_by_reviewer(reviewer_id)
    elif fragrance_id:
        evaluations = await service.get_by_fragrance(fragrance_id)
    else:
        # Return empty list if no filter specified (for safety)
        return []

    return [
        EvaluationResponse(
            id=e.id,
            fragrance_id=e.fragrance_id,
            reviewer_id=e.reviewer_id,
            rating=e.rating,
            notes=e.notes,
            longevity_rating=e.longevity_rating,
            sillage_rating=e.sillage_rating,
            evaluated_at=e.evaluated_at,
            created_at=e.created_at,
        )
        for e in evaluations
    ]


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: str,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationResponse:
    """Get an evaluation by ID."""
    evaluation = await service.get_by_id(evaluation_id)
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "EVALUATION_NOT_FOUND", "message": "Evaluation not found"},
        )
    return EvaluationResponse(
        id=evaluation.id,
        fragrance_id=evaluation.fragrance_id,
        reviewer_id=evaluation.reviewer_id,
        rating=evaluation.rating,
        notes=evaluation.notes,
        longevity_rating=evaluation.longevity_rating,
        sillage_rating=evaluation.sillage_rating,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
    )


@router.post("", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    data: EvaluationCreate,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    fragrance_service: Annotated[FragranceService, Depends(get_fragrance_service)],
    reviewer_service: Annotated[ReviewerService, Depends(get_reviewer_service)],
) -> EvaluationResponse:
    """Create a new evaluation.

    A reviewer can only have one evaluation per fragrance. Both the
    fragrance and the reviewer must already exist.
    """
    # #CRITICAL: data-integrity: on SQLite (used in tests) foreign keys are
    # off by default, so an insert against a nonexistent fragrance_id or
    # reviewer_id would silently succeed there while raising an unhandled
    # IntegrityError (500) on Postgres in production (Major finding 9).
    # #VERIFY: explicit existence checks make this endpoint's 404 behavior
    # identical across both backends instead of depending on FK enforcement.
    fragrance = await fragrance_service.get_by_id(data.fragrance_id)
    if not fragrance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FRAGRANCE_NOT_FOUND",
                "message": f"Fragrance {data.fragrance_id} not found",
            },
        )

    reviewer = await reviewer_service.get_by_id(data.reviewer_id)
    if not reviewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "REVIEWER_NOT_FOUND",
                "message": f"Reviewer {data.reviewer_id} not found",
            },
        )

    # Check if evaluation already exists
    existing = await service.get_by_reviewer_and_fragrance(
        data.reviewer_id, data.fragrance_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "EVALUATION_EXISTS",
                "message": "Evaluation already exists for this reviewer and fragrance",
                "existing_id": existing.id,
            },
        )

    # #CRITICAL: concurrency: the existence check above is a
    # check-then-insert, not atomic; two concurrent requests for the same
    # reviewer/fragrance pair can both pass it and race for the insert
    # (Major finding 8 adds a UNIQUE(reviewer_id, fragrance_id) constraint
    # as the actual data-integrity backstop).
    # #VERIFY: the loser of that race hits IntegrityError here rather than
    # surfacing as an unhandled 500; it is rolled back and translated into
    # the same 409 CONFLICT the pre-check above returns for the common case.
    try:
        evaluation = await service.create(data)
    except IntegrityError:
        await service.session.rollback()
        existing = await service.get_by_reviewer_and_fragrance(
            data.reviewer_id, data.fragrance_id
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "EVALUATION_EXISTS",
                "message": "Evaluation already exists for this reviewer and fragrance",
                "existing_id": existing.id if existing else None,
            },
        ) from None

    return EvaluationResponse(
        id=evaluation.id,
        fragrance_id=evaluation.fragrance_id,
        reviewer_id=evaluation.reviewer_id,
        rating=evaluation.rating,
        notes=evaluation.notes,
        longevity_rating=evaluation.longevity_rating,
        sillage_rating=evaluation.sillage_rating,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
    )


@router.patch("/{evaluation_id}", response_model=EvaluationResponse)
async def update_evaluation(
    evaluation_id: str,
    data: EvaluationUpdate,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationResponse:
    """Update an existing evaluation."""
    evaluation = await service.update(evaluation_id, data)
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "EVALUATION_NOT_FOUND", "message": "Evaluation not found"},
        )
    return EvaluationResponse(
        id=evaluation.id,
        fragrance_id=evaluation.fragrance_id,
        reviewer_id=evaluation.reviewer_id,
        rating=evaluation.rating,
        notes=evaluation.notes,
        longevity_rating=evaluation.longevity_rating,
        sillage_rating=evaluation.sillage_rating,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
    )


@router.delete("/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(
    evaluation_id: str,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> None:
    """Delete an evaluation by ID."""
    deleted = await service.delete(evaluation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "EVALUATION_NOT_FOUND", "message": "Evaluation not found"},
        )
