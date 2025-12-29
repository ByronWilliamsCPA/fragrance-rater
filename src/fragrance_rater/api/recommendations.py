"""Recommendation API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fragrance_rater.core.database import get_db
from fragrance_rater.models.fragrance import Fragrance, FragranceNote
from fragrance_rater.services.llm_service import (
    FragranceDetails,
    LLMService,
    get_llm_service,
)
from fragrance_rater.services.recommendation_service import (
    InsufficientDataError,
    Recommendation,
    RecommendationService,
)
from fragrance_rater.services.reviewer_service import ReviewerService

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
    llm_summary: str | None = Field(
        None, description="LLM-generated natural language summary"
    )


class ExplanationResponse(BaseModel):
    """Response model for recommendation explanation."""

    fragrance_id: str
    fragrance_name: str
    explanation: str
    model: str = Field(..., description="Model used to generate explanation")
    cached: bool = Field(False, description="Whether response was cached")


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
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
    include_llm: bool = Query(True, description="Include LLM-generated summary"),
) -> ProfileSummaryResponse:
    """Get a summary of a reviewer's preference profile.

    Shows top liked/disliked notes, preferred accords, and fragrance families
    based on their evaluation history. Optionally includes an LLM-generated
    natural language summary.
    """
    summary = await service.get_reviewer_profile_summary(reviewer_id)

    llm_summary: str | None = None
    if include_llm and llm_service.is_available():
        # Get reviewer name for the summary
        reviewer_svc = ReviewerService(session)
        reviewer = await reviewer_svc.get_by_id(reviewer_id)
        if reviewer:
            profile = await service.build_preference_profile(reviewer_id)
            if profile.evaluation_count > 0:
                llm_response = await llm_service.generate_profile_summary(
                    profile=profile,
                    reviewer_name=reviewer.name,
                )
                llm_summary = llm_response.text

    return ProfileSummaryResponse(
        reviewer_id=reviewer_id,
        evaluation_count=summary["evaluation_count"],  # type: ignore[arg-type]
        top_liked_notes=summary["top_liked_notes"],  # type: ignore[arg-type]
        top_disliked_notes=summary["top_disliked_notes"],  # type: ignore[arg-type]
        top_accords=summary["top_accords"],  # type: ignore[arg-type]
        top_families=summary["top_families"],  # type: ignore[arg-type]
        llm_summary=llm_summary,
    )


@router.get(
    "/{reviewer_id}/{fragrance_id}/explain", response_model=ExplanationResponse
)
async def get_recommendation_explanation(
    reviewer_id: str,
    fragrance_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
) -> ExplanationResponse:
    """Get an LLM-generated explanation for why a fragrance matches a reviewer.

    Uses the reviewer's preference profile and the fragrance's notes/accords
    to generate a personalized explanation.
    """
    # Build user profile
    profile = await service.build_preference_profile(reviewer_id)
    if profile.evaluation_count < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INSUFFICIENT_DATA",
                "message": "Need at least 3 evaluations to generate explanations",
            },
        )

    # Get fragrance with notes
    stmt = (
        select(Fragrance)
        .where(Fragrance.id == fragrance_id)
        .options(selectinload(Fragrance.notes).selectinload(FragranceNote.note))
    )
    result = await session.execute(stmt)
    fragrance = result.scalar_one_or_none()

    if fragrance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Fragrance not found"},
        )

    # Build fragrance details
    top_notes: list[str] = []
    heart_notes: list[str] = []
    base_notes: list[str] = []
    for fn in fragrance.notes:
        if fn.note_type == "top":
            top_notes.append(fn.note.name)
        elif fn.note_type == "heart":
            heart_notes.append(fn.note.name)
        elif fn.note_type == "base":
            base_notes.append(fn.note.name)

    fragrance_details = FragranceDetails(
        name=fragrance.name,
        brand=fragrance.brand,
        family=fragrance.family or "Unknown",
        subfamily=fragrance.subfamily or "Unknown",
        top_notes=top_notes,
        heart_notes=heart_notes,
        base_notes=base_notes,
        accords=[a.accord for a in fragrance.accords],
    )

    # Calculate recommendation for this fragrance
    recommendations = await service.get_recommendations(
        reviewer_id=reviewer_id, limit=100, exclude_rated=False
    )

    # Find this fragrance in recommendations
    recommendation = next(
        (r for r in recommendations if r.fragrance_id == fragrance_id), None
    )

    if recommendation is None:
        # Create a basic recommendation object for the explanation
        recommendation = Recommendation(
            fragrance_id=fragrance_id,
            fragrance_name=fragrance.name,
            fragrance_brand=fragrance.brand,
            match_score=0.5,
            match_percent=50,
            vetoed=False,
            veto_reason=None,
        )

    # Generate explanation
    llm_response = await llm_service.generate_recommendation_explanation(
        recommendation=recommendation,
        profile=profile,
        fragrance_details=fragrance_details,
    )

    return ExplanationResponse(
        fragrance_id=fragrance_id,
        fragrance_name=fragrance.name,
        explanation=llm_response.text,
        model=llm_response.model,
        cached=llm_response.cached,
    )
