"""Evaluation API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import AuthenticatedIdentity, get_current_identity
from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.evaluation import (
    EvaluationCreate,
    EvaluationResponse,
    EvaluationUpdate,
)
from fragrance_rater.services.evaluation_service import EvaluationService
from fragrance_rater.services.fragrance_service import FragranceService
from fragrance_rater.services.reviewer_service import ReviewerService
from fragrance_rater.utils.logging import get_logger, log_audit_event

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

logger = get_logger(__name__)


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
            worn_by_reviewer_id=e.worn_by_reviewer_id,
            evaluated_at=e.evaluated_at,
            created_at=e.created_at,
            recorded_by=e.recorded_by,
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
        worn_by_reviewer_id=evaluation.worn_by_reviewer_id,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
        recorded_by=evaluation.recorded_by,
    )


@router.post("", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    data: EvaluationCreate,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    fragrance_service: Annotated[FragranceService, Depends(get_fragrance_service)],
    reviewer_service: Annotated[ReviewerService, Depends(get_reviewer_service)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> EvaluationResponse:
    """Create a new evaluation.

    Each submission creates a dated encounter, retaining earlier ratings.
    Both the fragrance and the reviewer must already exist.

    Critical finding 2: `recorded_by` is populated from the Authentik
    forward-auth identity of whoever is logged in when this request is
    made, independent of `reviewer_id` (whose palate the rating reflects).
    One logged-in person can record ratings for several different
    reviewers across separate requests (a group-smelling session); this
    endpoint places no constraint tying the two together.
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

    # ADR-011: same SQLite-FK-off rationale as the fragrance/reviewer
    # checks above, applied to the optional "worn by" subject reviewer.
    # `EvaluationCreate` already rejects worn_by_reviewer_id == reviewer_id
    # at the schema layer; existence still needs a database round trip.
    if data.worn_by_reviewer_id is not None:
        worn_by_reviewer = await reviewer_service.get_by_id(data.worn_by_reviewer_id)
        if not worn_by_reviewer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "WORN_BY_REVIEWER_NOT_FOUND",
                    "message": f"Reviewer {data.worn_by_reviewer_id} not found",
                },
            )

    evaluation = await service.create(data, recorded_by=identity.username)

    log_audit_event(
        logger,
        action="create",
        actor=identity.username,
        target_type="evaluation",
        target_id=evaluation.id,
        reviewer_id=evaluation.reviewer_id,
        fragrance_id=evaluation.fragrance_id,
    )

    return EvaluationResponse(
        id=evaluation.id,
        fragrance_id=evaluation.fragrance_id,
        reviewer_id=evaluation.reviewer_id,
        rating=evaluation.rating,
        notes=evaluation.notes,
        longevity_rating=evaluation.longevity_rating,
        sillage_rating=evaluation.sillage_rating,
        worn_by_reviewer_id=evaluation.worn_by_reviewer_id,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
        recorded_by=evaluation.recorded_by,
    )


@router.patch("/{evaluation_id}", response_model=EvaluationResponse)
async def update_evaluation(
    evaluation_id: str,
    data: EvaluationUpdate,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    reviewer_service: Annotated[ReviewerService, Depends(get_reviewer_service)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> EvaluationResponse:
    """Update an existing evaluation."""
    # ADR-011: `EvaluationUpdate` has no `reviewer_id` field (immutable via
    # PATCH), so the self-reference and existence checks that
    # `EvaluationCreate` handles at the schema layer happen here instead,
    # against the stored evaluation's own reviewer_id. Only runs when the
    # client actually supplied a non-null worn_by_reviewer_id; omitting the
    # field or explicitly clearing it to null needs neither check.
    update_fields = data.model_dump(exclude_unset=True)
    new_worn_by_reviewer_id = update_fields.get("worn_by_reviewer_id")
    if "worn_by_reviewer_id" in update_fields and new_worn_by_reviewer_id is not None:
        existing = await service.get_by_id(evaluation_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "EVALUATION_NOT_FOUND",
                    "message": "Evaluation not found",
                },
            )
        if new_worn_by_reviewer_id == existing.reviewer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "WORN_BY_REVIEWER_SAME_AS_REVIEWER",
                    "message": (
                        "worn_by_reviewer_id must differ from the evaluation's "
                        "reviewer_id; omit it (or set it null) for an on-me rating"
                    ),
                },
            )
        worn_by_reviewer = await reviewer_service.get_by_id(new_worn_by_reviewer_id)
        if not worn_by_reviewer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "WORN_BY_REVIEWER_NOT_FOUND",
                    "message": f"Reviewer {new_worn_by_reviewer_id} not found",
                },
            )

    evaluation = await service.update(evaluation_id, data)
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "EVALUATION_NOT_FOUND", "message": "Evaluation not found"},
        )
    log_audit_event(
        logger,
        action="update",
        actor=identity.username,
        target_type="evaluation",
        target_id=evaluation.id,
    )
    return EvaluationResponse(
        id=evaluation.id,
        fragrance_id=evaluation.fragrance_id,
        reviewer_id=evaluation.reviewer_id,
        rating=evaluation.rating,
        notes=evaluation.notes,
        longevity_rating=evaluation.longevity_rating,
        sillage_rating=evaluation.sillage_rating,
        worn_by_reviewer_id=evaluation.worn_by_reviewer_id,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
        recorded_by=evaluation.recorded_by,
    )


@router.delete("/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(
    evaluation_id: str,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> None:
    """Soft-delete an evaluation by ID."""
    deleted = await service.delete(evaluation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "EVALUATION_NOT_FOUND", "message": "Evaluation not found"},
        )
    log_audit_event(
        logger,
        action="soft_delete",
        actor=identity.username,
        target_type="evaluation",
        target_id=evaluation_id,
    )
