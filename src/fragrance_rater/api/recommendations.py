"""Recommendation API endpoints.

``GET /{reviewer_id}/profile`` and ``GET /{reviewer_id}/{fragrance_id}/explain``
can each trigger a billed OpenRouter call via
``fragrance_rater.services.llm_service`` (see ADR-003): the same cost/abuse
vector documented for ``POST /ratings`` in ``fragrance_rater.api.ratings``.
Both routes therefore require the shared household ``X-API-Key`` header (see
``fragrance_rater.middleware.auth.require_api_key``) and are rate limited
(see ``fragrance_rater.middleware.rate_limit.RATINGS_RATE_LIMIT``), mirroring
``POST /ratings`` exactly rather than inventing a separate scheme.
"""

from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fragrance_rater.core.database import get_db
from fragrance_rater.middleware import RATINGS_RATE_LIMIT, limiter, require_api_key
from fragrance_rater.models.fragrance import Fragrance, FragranceNote
from fragrance_rater.models.recommendation_measurement import LLMInvocation
from fragrance_rater.services.llm_service import (
    FragranceDetails,
    LLMService,
    get_llm_service,
)
from fragrance_rater.services.preference_history import PreferenceHistoryService
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
        default=False, description="Whether fragrance contains a disliked note"
    )
    veto_reason: str | None = Field(
        default=None, description="Reason for veto if applicable"
    )


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
        default=None, description="LLM-generated natural language summary"
    )


class ExplanationResponse(BaseModel):
    """Response model for recommendation explanation."""

    fragrance_id: str
    fragrance_name: str
    explanation: str
    model: str = Field(..., description="Model used to generate explanation")
    cached: bool = Field(default=False, description="Whether response was cached")


async def get_recommendation_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationService:
    """Dependency to get RecommendationService instance."""
    return RecommendationService(session)


@router.get("/{reviewer_id}", response_model=RecommendationListResponse)
async def get_recommendations(
    reviewer_id: str,
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    limit: Annotated[
        int, Query(ge=1, le=50, description="Maximum recommendations")
    ] = 10,
    exclude_rated: Annotated[
        bool, Query(description="Exclude already-rated fragrances")
    ] = True,
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


# #CRITICAL: security: this route can call the billed OpenRouter LLM (via
# llm_service.generate_profile_summary) whenever include_llm=True and the
# LLM is available. Left unauthenticated and unlimited, it is the same
# cost/abuse vector as POST /ratings (fragrance_rater.api.ratings), just
# reachable via GET instead of POST.
# #VERIFY: keep dependencies=[Depends(require_api_key)] and
# @limiter.limit(RATINGS_RATE_LIMIT) below in sync with the identical
# pattern on POST /ratings; do not drop either independently, and do not
# gate them on include_llm since the query param is caller-controlled.
@router.get(
    "/{reviewer_id}/profile",
    response_model=ProfileSummaryResponse,
    dependencies=[Depends(require_api_key)],
    responses={
        401: {
            "description": (
                "Missing or invalid X-API-Key header. Required on this "
                "endpoint because it can trigger a billed LLM call (see "
                "fragrance_rater.middleware.auth)."
            )
        },
        429: {"description": "Rate limit exceeded; retry after a short delay."},
        503: {
            "description": (
                "No household API key is configured for this deployment "
                "(FRAGRANCE_RATER_API_KEY unset)."
            )
        },
    },
)
@limiter.limit(RATINGS_RATE_LIMIT)  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType]
async def get_profile_summary(
    *,
    request: Request,
    reviewer_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
    include_llm: Annotated[
        bool, Query(description="Include LLM-generated summary")
    ] = True,
) -> ProfileSummaryResponse:
    """Get a summary of a reviewer's preference profile.

    Shows top liked/disliked notes, preferred accords, and fragrance families
    based on their evaluation history. Optionally includes an LLM-generated
    natural language summary.

    Requires the shared household ``X-API-Key`` header (see
    ``fragrance_rater.middleware.auth.require_api_key``) and is rate limited
    (see ``fragrance_rater.middleware.rate_limit.RATINGS_RATE_LIMIT``)
    because ``include_llm=True`` can trigger a billed OpenRouter call.

    Args:
        request (Request): Incoming request, required by the
            ``@limiter.limit`` decorator to key rate limiting on the caller.
        reviewer_id (str): Reviewer to summarize.
        session (Annotated[AsyncSession, Depends(get_db)]): Database session, injected.
        service (Annotated[RecommendationService, Depends(get_recommendation_service)]):
            Recommendation service, injected.
        llm_service (Annotated[LLMService, Depends(get_llm_service)]): LLM service, injected.
        include_llm (Annotated[bool, Query(description='Include LLM-generated summary')]):
            Whether to include an LLM-generated summary.

    Returns:
        ProfileSummaryResponse: The reviewer's preference profile summary.
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
                started = perf_counter()
                llm_response = await llm_service.generate_profile_summary(
                    profile=profile,
                    reviewer_name=reviewer.name,
                )
                llm_summary = llm_response.text
                session.add(
                    LLMInvocation(
                        reviewer_id=reviewer_id,
                        operation="PROFILE_SUMMARY",
                        model=llm_response.model,
                        latency_ms=round((perf_counter() - started) * 1000),
                        cache_hit=llm_response.cached,
                        succeeded=llm_response.error is None,
                        estimated_cost_usd=None,
                        prompt_tokens=llm_response.prompt_tokens,
                        completion_tokens=llm_response.completion_tokens,
                        total_tokens=llm_response.total_tokens,
                        provider_cost_credits=llm_response.provider_cost_credits,
                    )
                )
                await session.commit()

    return ProfileSummaryResponse(
        reviewer_id=reviewer_id,
        evaluation_count=summary["evaluation_count"],
        top_liked_notes=summary["top_liked_notes"],
        top_disliked_notes=summary["top_disliked_notes"],
        top_accords=summary["top_accords"],
        top_families=summary["top_families"],
        llm_summary=llm_summary,
    )


# #CRITICAL: security: this route always calls the billed OpenRouter LLM
# (via llm_service.generate_recommendation_explanation), unconditionally on
# every successful request. Left unauthenticated and unlimited, it is the
# same cost/abuse vector as POST /ratings (fragrance_rater.api.ratings),
# just reachable via GET instead of POST.
# #VERIFY: keep dependencies=[Depends(require_api_key)] and
# @limiter.limit(RATINGS_RATE_LIMIT) below in sync with the identical
# pattern on POST /ratings; do not drop either independently.
@router.get(
    "/{reviewer_id}/{fragrance_id}/explain",
    response_model=ExplanationResponse,
    dependencies=[Depends(require_api_key)],
    responses={
        401: {
            "description": (
                "Missing or invalid X-API-Key header. Required on this "
                "endpoint because it triggers a billed LLM call (see "
                "fragrance_rater.middleware.auth)."
            )
        },
        429: {"description": "Rate limit exceeded; retry after a short delay."},
        503: {
            "description": (
                "No household API key is configured for this deployment "
                "(FRAGRANCE_RATER_API_KEY unset)."
            )
        },
    },
)
@limiter.limit(RATINGS_RATE_LIMIT)  # pyright: ignore[reportUntypedFunctionDecorator, reportUnknownMemberType]
async def get_recommendation_explanation(
    *,
    request: Request,
    reviewer_id: str,
    fragrance_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
) -> ExplanationResponse:
    """Get an LLM-generated explanation for why a fragrance matches a reviewer.

    Uses the reviewer's preference profile and the fragrance's notes/accords
    to generate a personalized explanation.

    Requires the shared household ``X-API-Key`` header (see
    ``fragrance_rater.middleware.auth.require_api_key``) and is rate limited
    (see ``fragrance_rater.middleware.rate_limit.RATINGS_RATE_LIMIT``)
    because this endpoint always triggers a billed OpenRouter call.

    Args:
        request (Request): Incoming request, required by the
            ``@limiter.limit`` decorator to key rate limiting on the caller.
        reviewer_id (str): Reviewer whose preference profile is used.
        fragrance_id (str): Fragrance to explain the match for.
        session (Annotated[AsyncSession, Depends(get_db)]): Database session, injected.
        service (Annotated[RecommendationService, Depends(get_recommendation_service)]):
            Recommendation service, injected.
        llm_service (Annotated[LLMService, Depends(get_llm_service)]): LLM service, injected.

    Returns:
        ExplanationResponse: The LLM-authored explanation.

    Raises:
        HTTPException: 400 if the reviewer has fewer than 3 evaluations, or
            404 if `fragrance_id` does not resolve to a live (non-soft-
            deleted) fragrance.
    """
    # A reviewer-specific explanation is itself a recommendation surface.
    # Reject assigned holdouts even when a caller already knows a catalog ID.
    if fragrance_id in await PreferenceHistoryService(session).excluded_versions(
        reviewer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": "Fragrance not found"},
        )

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
    # Critical finding 2: soft-delete filter.
    stmt = (
        select(Fragrance)
        .where(Fragrance.id == fragrance_id, Fragrance.deleted_at.is_(None))
        .options(
            selectinload(Fragrance.notes).selectinload(FragranceNote.note),
            selectinload(Fragrance.accords),
        )
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
    unpositioned_notes: list[str] = []
    for fn in fragrance.notes:
        if fn.position == "top":
            top_notes.append(fn.note.name)
        elif fn.position == "heart":
            heart_notes.append(fn.note.name)
        elif fn.position == "base":
            base_notes.append(fn.note.name)
        elif fn.position == "flat":
            unpositioned_notes.append(fn.note.name)

    fragrance_details = FragranceDetails(
        name=fragrance.name,
        brand=fragrance.brand,
        family=fragrance.primary_family or "Unknown",
        subfamily=fragrance.subfamily or "Unknown",
        top_notes=top_notes,
        heart_notes=heart_notes,
        base_notes=base_notes,
        unpositioned_notes=unpositioned_notes,
        accords=[a.accord_type for a in fragrance.accords],
    )

    # #CRITICAL: data integrity: this endpoint asks for the match score of
    # one specific, caller-requested fragrance, so that score must always be
    # the real computed value. A prior version instead called
    # service.get_recommendations(limit=100, exclude_rated=False) and
    # looked this fragrance up by id in that (size-capped, and previously
    # also rated-exclusion-filtered) result list; when the target fell
    # outside the first 100 candidates by match_score, the lookup silently
    # missed and fell back to a fabricated match_score=0.5/match_percent=50
    # placeholder that was then fed to the LLM as if it were a real score,
    # producing an explanation for a match nobody actually computed. The
    # 100-item cap is a reasonable pagination limit for the general
    # recommendation *list* endpoint (GET /{reviewer_id}), but must never
    # gate whether an explicitly-requested target's own score gets computed.
    # #VERIFY: always call calculate_match_score directly on the fetched
    # target `fragrance` (already loaded above with notes/accords) instead
    # of searching for it inside a size-limited candidate list; do not
    # reintroduce a "look it up in the top-N recommendations" shortcut here.
    match_result = await service.calculate_match_score(profile, fragrance)
    recommendation = Recommendation(
        fragrance_id=fragrance_id,
        fragrance_name=fragrance.name,
        fragrance_brand=fragrance.brand,
        match_score=match_result.score,
        match_percent=match_result.score_percent,
        vetoed=match_result.vetoed,
        veto_reason=(
            f"Contains {match_result.veto_note} which you dislike"
            if match_result.vetoed
            else None
        ),
    )

    # Generate explanation
    started = perf_counter()
    llm_response = await llm_service.generate_recommendation_explanation(
        recommendation=recommendation,
        profile=profile,
        fragrance_details=fragrance_details,
    )
    if llm_service.is_available():
        session.add(
            LLMInvocation(
                reviewer_id=reviewer_id,
                operation="RECOMMENDATION_EXPLANATION",
                model=llm_response.model,
                latency_ms=round((perf_counter() - started) * 1000),
                cache_hit=llm_response.cached,
                succeeded=llm_response.error is None,
                estimated_cost_usd=None,
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens,
                provider_cost_credits=llm_response.provider_cost_credits,
            )
        )
        await session.commit()

    return ExplanationResponse(
        fragrance_id=fragrance_id,
        fragrance_name=fragrance.name,
        explanation=llm_response.text,
        model=llm_response.model,
        cached=llm_response.cached,
    )
