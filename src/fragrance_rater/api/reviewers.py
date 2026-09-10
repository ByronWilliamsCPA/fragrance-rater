"""Reviewer API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import AuthenticatedIdentity, get_current_identity
from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.reviewer import ReviewerCreate, ReviewerResponse
from fragrance_rater.services.reviewer_service import ReviewerService
from fragrance_rater.utils.logging import get_logger, log_audit_event

router = APIRouter(prefix="/reviewers", tags=["reviewers"])

logger = get_logger(__name__)


async def get_reviewer_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewerService:
    """Dependency to get ReviewerService instance."""
    return ReviewerService(session)


@router.get("", response_model=list[ReviewerResponse])
async def list_reviewers(
    service: Annotated[ReviewerService, Depends(get_reviewer_service)],
) -> list[ReviewerResponse]:
    """List all reviewers with evaluation counts."""
    reviewers = await service.list_all()
    return [
        ReviewerResponse(
            id=reviewer.id,
            name=reviewer.name,
            created_at=reviewer.created_at,
            evaluation_count=count,
        )
        for reviewer, count in reviewers
    ]


@router.get("/{reviewer_id}", response_model=ReviewerResponse)
async def get_reviewer(
    reviewer_id: str,
    service: Annotated[ReviewerService, Depends(get_reviewer_service)],
) -> ReviewerResponse:
    """Get a reviewer by ID."""
    reviewer = await service.get_by_id(reviewer_id)
    if not reviewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REVIEWER_NOT_FOUND", "message": "Reviewer not found"},
        )
    evaluation_count = await service.count_evaluations(reviewer_id)
    return ReviewerResponse(
        id=reviewer.id,
        name=reviewer.name,
        created_at=reviewer.created_at,
        evaluation_count=evaluation_count,
    )


@router.post("", response_model=ReviewerResponse, status_code=status.HTTP_201_CREATED)
async def create_reviewer(
    data: ReviewerCreate,
    service: Annotated[ReviewerService, Depends(get_reviewer_service)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> ReviewerResponse:
    """Create a new reviewer.

    Rejects a duplicate name (the `uq_reviewer_name` partial unique index)
    with a 409 rather than letting the resulting IntegrityError surface as
    an unhandled 500.
    """
    # Check if name already exists
    existing = await service.get_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "REVIEWER_EXISTS",
                "message": f"Reviewer '{data.name}' already exists",
            },
        )

    # #ASSUME: data-integrity: the pre-check above has no pre-check-to-insert
    # locking, only a catch of the IntegrityError `uq_reviewer_name` raises,
    # since two concurrent requests can both pass the pre-check for the same
    # name before either commits (matches the same pattern used for
    # fragrances' `uq_fragrance_name_brand` in api/fragrances.py).
    # #VERIFY: the caught path rolls back before returning, so the session
    # is left usable for the next request on this connection.
    try:
        reviewer = await service.create(data.name)
    except IntegrityError:
        await service.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "REVIEWER_EXISTS",
                "message": f"Reviewer '{data.name}' already exists",
            },
        ) from None
    log_audit_event(
        logger,
        action="create",
        actor=identity.username,
        target_type="reviewer",
        target_id=reviewer.id,
    )
    return ReviewerResponse(
        id=reviewer.id,
        name=reviewer.name,
        created_at=reviewer.created_at,
        evaluation_count=0,
    )


@router.post("/seed", response_model=list[ReviewerResponse])
async def seed_reviewers(
    service: Annotated[ReviewerService, Depends(get_reviewer_service)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> list[ReviewerResponse]:
    """Create default family reviewer profiles.

    Creates: Byron, Veronica, Bayden, Ariannah
    Idempotent - existing reviewers are returned as-is.
    """
    reviewers = await service.seed_default_reviewers()
    log_audit_event(
        logger,
        action="seed",
        actor=identity.username,
        target_type="reviewer",
        target_id=",".join(r.id for r in reviewers),
    )
    return [
        ReviewerResponse(
            id=reviewer.id,
            name=reviewer.name,
            created_at=reviewer.created_at,
            evaluation_count=0,
        )
        for reviewer in reviewers
    ]


@router.delete("/{reviewer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reviewer(
    reviewer_id: str,
    service: Annotated[ReviewerService, Depends(get_reviewer_service)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> None:
    """Soft-delete a reviewer by ID."""
    deleted = await service.delete(reviewer_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REVIEWER_NOT_FOUND", "message": "Reviewer not found"},
        )
    log_audit_event(
        logger,
        action="soft_delete",
        actor=identity.username,
        target_type="reviewer",
        target_id=reviewer_id,
    )
