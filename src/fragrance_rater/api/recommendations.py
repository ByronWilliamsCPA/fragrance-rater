"""Recommendation API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.database import get_db
from fragrance_rater.services.recommendation_service import (
    InsufficientDataError,
    RecommendationService,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationResponse(BaseModel):
    """Response model for a single recommendation."""

    fragrance_id: str
    fragrance_name: str
    fragrance_brand: str
    match_score: float = Field(..., description="Match score from 0.0 to 1.0")
    match_percent: int = Field(..., description="Match score as percentage 0-100")
    vetoed: bool = Field(
        False, description="Whether fragrance contains a disliked note"
    )
    veto_reason: str | None = Field(None, description="Reason for veto if applicable")


class RecommendationListResponse(BaseModel):
    """Response model for recommendation list."""

    reviewer_id: str
    recommendations: list[RecommendationResponse]
    count: int


class ProfileSummaryResponse(BaseModel):
    """Response model for reviewer preference profile summary."""

    reviewer_id: str
    evaluation_count: int
    top_liked_notes: list[tuple[str, float]] = Field(
        default_factory=list, description="Top 5 liked notes with scores"
    )
    top_disliked_notes: list[tuple[str, float]] = Field(
        default_factory=list, description="Top 5 disliked notes with scores"
    )
    top_accords: list[tuple[str, float]] = Field(
        default_factory=list, description="Top 5 preferred accords"
    )
    top_families: list[tuple[str, float]] = Field(
        default_factory=list, description="Top 5 preferred fragrance families"
    )


async def get_recommendation_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationService:
    """Dependency to get RecommendationService instance."""
    return RecommendationService(session)


@router.get("/{reviewer_id}", response_model=RecommendationListResponse)
async def get_recommendations(
    reviewer_id: str,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    limit: int = Query(10, ge=1, le=50, description="Maximum recommendations"),
    exclude_rated: bool = Query(True, description="Exclude already-rated fragrances"),
) -> RecommendationListResponse:
    """Get personalized fragrance recommendations for a reviewer.

    Requires at least 3 evaluations to generate meaningful recommendations.
    Returns fragrances sorted by match score, with vetoed items last.
    """
    try:
        recommendations = await service.get_recommendations(
            reviewer_id=reviewer_id,
            limit=limit,
            exclude_rated=exclude_rated,
        )
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INSUFFICIENT_DATA",
                "message": str(e),
            },
        ) from e

    return RecommendationListResponse(
        reviewer_id=reviewer_id,
        recommendations=[
            RecommendationResponse(
                fragrance_id=r.fragrance_id,
                fragrance_name=r.fragrance_name,
                fragrance_brand=r.fragrance_brand,
                match_score=r.match_score,
                match_percent=r.match_percent,
                vetoed=r.vetoed,
                veto_reason=r.veto_reason,
            )
            for r in recommendations
        ],
        count=len(recommendations),
    )


@router.get("/{reviewer_id}/profile", response_model=ProfileSummaryResponse)
async def get_profile_summary(
    reviewer_id: str,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> ProfileSummaryResponse:
    """Get a summary of a reviewer's preference profile.

    Shows top liked/disliked notes, preferred accords, and fragrance families
    based on their evaluation history.
    """
    summary = await service.get_reviewer_profile_summary(reviewer_id)

    return ProfileSummaryResponse(
        reviewer_id=reviewer_id,
        evaluation_count=summary["evaluation_count"],  # type: ignore[arg-type]
        top_liked_notes=summary["top_liked_notes"],  # type: ignore[arg-type]
        top_disliked_notes=summary["top_disliked_notes"],  # type: ignore[arg-type]
        top_accords=summary["top_accords"],  # type: ignore[arg-type]
        top_families=summary["top_families"],  # type: ignore[arg-type]
    )
