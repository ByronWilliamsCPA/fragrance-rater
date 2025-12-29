"""Reviewer API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.reviewer import ReviewerCreate, ReviewerResponse
from fragrance_rater.services.reviewer_service import ReviewerService

router = APIRouter(prefix="/reviewers", tags=["reviewers"])


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
    return ReviewerResponse(
        id=reviewer.id,
        name=reviewer.name,
        created_at=reviewer.created_at,
        evaluation_count=len(reviewer.evaluations),
    )


@router.post("", response_model=ReviewerResponse, status_code=status.HTTP_201_CREATED)
async def create_reviewer(
    data: ReviewerCreate,
    service: Annotated[ReviewerService, Depends(get_reviewer_service)],
) -> ReviewerResponse:
    """Create a new reviewer."""
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

    reviewer = await service.create(data.name)
    return ReviewerResponse(
        id=reviewer.id,
        name=reviewer.name,
        created_at=reviewer.created_at,
        evaluation_count=0,
    )


@router.post("/seed", response_model=list[ReviewerResponse])
async def seed_reviewers(
    service: Annotated[ReviewerService, Depends(get_reviewer_service)],
) -> list[ReviewerResponse]:
    """Create default family reviewer profiles.

    Creates: Byron, Veronica, Bayden, Ariannah
    Idempotent - existing reviewers are returned as-is.
    """
    reviewers = await service.seed_default_reviewers()
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
) -> None:
    """Delete a reviewer by ID."""
    deleted = await service.delete(reviewer_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REVIEWER_NOT_FOUND", "message": "Reviewer not found"},
        )
