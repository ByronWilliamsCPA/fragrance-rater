"""
API routes for recommendations and preference profiles.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app.services import RecommendationService, openrouter
from app.services.fragrance_service import FragranceService, ReviewerService
from app.schemas import FragranceListResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# Response schemas
class RecommendationItem(BaseModel):
    fragrance: FragranceListResponse
    match_score: float
    reasons: List[str]
    warnings: List[str]


class ProfileSummary(BaseModel):
    reviewer_id: int
    reviewer_name: str
    summary: str
    evaluation_count: int
    preferred_notes: List[str]
    disliked_notes: List[str]
    family_scores: dict


class ExternalSuggestion(BaseModel):
    name: str
    brand: str
    reason: str


class LLMStatus(BaseModel):
    configured: bool
    model: str


@router.get("/status", response_model=LLMStatus)
def get_llm_status():
    """Check if LLM recommendations are available."""
    return LLMStatus(
        configured=openrouter.is_configured,
        model=openrouter.DEFAULT_MODEL if openrouter.is_configured else "none"
    )


@router.get("/{reviewer_id}", response_model=List[RecommendationItem])
def get_recommendations(
    reviewer_id: int,
    limit: int = Query(default=10, le=50),
    include_evaluated: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """
    Get fragrance recommendations for a reviewer based on their preference profile.

    Recommendations are scored based on:
    - Fragrance family preferences
    - Note affinities (what notes appear in fragrances they've rated high/low)
    - Accord affinities

    Set include_evaluated=True to include fragrances they've already tried
    (useful for finding things to revisit).
    """
    reviewer = ReviewerService.get_by_id(db, reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    service = RecommendationService(db)
    recommendations = service.get_recommendations(
        reviewer_id,
        limit=limit,
        exclude_evaluated=not include_evaluated,
    )

    if not recommendations:
        raise HTTPException(
            status_code=400,
            detail="Not enough evaluations to generate recommendations. Need at least 3."
        )

    # Convert to response format
    return [
        RecommendationItem(
            fragrance=FragranceListResponse.model_validate(r['fragrance']),
            match_score=r['match_score'],
            reasons=r['reasons'],
            warnings=r['warnings'],
        )
        for r in recommendations
    ]


@router.get("/{reviewer_id}/profile", response_model=ProfileSummary)
def get_preference_profile(
    reviewer_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a reviewer's computed preference profile with LLM-generated summary.
    """
    reviewer = ReviewerService.get_by_id(db, reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    service = RecommendationService(db)
    profile = service.analyzer.compute_profile(reviewer_id)

    # Generate LLM summary
    summary = service.generate_profile_summary(reviewer_id)

    return ProfileSummary(
        reviewer_id=reviewer_id,
        reviewer_name=reviewer.name,
        summary=summary,
        evaluation_count=profile['summary_stats']['count'],
        preferred_notes=profile['preferred_notes'],
        disliked_notes=profile['disliked_notes'],
        family_scores=profile['family_scores'],
    )


@router.get("/{reviewer_id}/explain/{fragrance_id}")
def explain_recommendation(
    reviewer_id: int,
    fragrance_id: int,
    db: Session = Depends(get_db)
):
    """
    Get an LLM-generated explanation of why a fragrance might work for someone.
    """
    reviewer = ReviewerService.get_by_id(db, reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    fragrance = FragranceService.get_by_id(db, fragrance_id)
    if not fragrance:
        raise HTTPException(status_code=404, detail="Fragrance not found")

    service = RecommendationService(db)

    # Get score and explanation
    profile = service.analyzer.compute_profile(reviewer_id)
    score, reasons, warnings = service.analyzer.score_fragrance(profile, fragrance)
    explanation = service.explain_recommendation(reviewer_id, fragrance_id)

    return {
        "reviewer": reviewer.name,
        "fragrance": f"{fragrance.name} by {fragrance.brand}",
        "match_score": score,
        "explanation": explanation,
        "reasons": reasons,
        "warnings": warnings,
    }


@router.get("/{reviewer_id}/suggest", response_model=List[ExternalSuggestion])
def suggest_new_fragrances(
    reviewer_id: int,
    context: str = Query(default="", description="Optional context like 'for summer' or 'date night'"),
    db: Session = Depends(get_db)
):
    """
    Use LLM to suggest fragrances that might not be in our database.

    This is useful for getting recommendations beyond what's been imported,
    especially for discovering new options to try.

    Requires OpenRouter API key to be configured.
    """
    if not openrouter.is_configured:
        raise HTTPException(
            status_code=503,
            detail="LLM recommendations not available. Configure OPENROUTER_API_KEY."
        )

    reviewer = ReviewerService.get_by_id(db, reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    service = RecommendationService(db)
    suggestions = service.suggest_new_fragrances(reviewer_id, context)

    if not suggestions:
        raise HTTPException(
            status_code=400,
            detail="Could not generate suggestions. Need more evaluations."
        )

    return [ExternalSuggestion(**s) for s in suggestions]


@router.post("/{reviewer_id}/analyze-notes")
def analyze_evaluation_notes(
    reviewer_id: int,
    db: Session = Depends(get_db)
):
    """
    Use LLM to analyze all of a reviewer's written notes to extract insights.

    Looks for patterns in what they mention liking/disliking that might
    not be captured in the structured note data.
    """
    if not openrouter.is_configured:
        raise HTTPException(
            status_code=503,
            detail="LLM analysis not available. Configure OPENROUTER_API_KEY."
        )

    reviewer = ReviewerService.get_by_id(db, reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    # Get all evaluations with notes
    from app.models import Evaluation
    evaluations = db.query(Evaluation).filter(
        Evaluation.reviewer_id == reviewer_id,
        Evaluation.notes.isnot(None),
        Evaluation.notes != ""
    ).all()

    if len(evaluations) < 3:
        raise HTTPException(
            status_code=400,
            detail="Not enough written notes to analyze. Need at least 3 evaluations with notes."
        )

    # Build prompt
    notes_data = []
    for e in evaluations:
        if e.fragrance:
            notes_data.append({
                "fragrance": f"{e.fragrance.name} by {e.fragrance.brand}",
                "rating": e.rating,
                "notes": e.notes,
            })

    import json
    prompt = f"""Analyze these fragrance evaluation notes from {reviewer.name} and extract insights about their preferences.

Evaluations:
{json.dumps(notes_data, indent=2)}

Identify:
1. Specific things they mention liking (scents, feelings, occasions)
2. Specific things they mention disliking
3. Any patterns in how they describe fragrances
4. Any context clues about when/how they prefer to wear fragrance

Respond in JSON:
{{
  "likes": ["list of things they mention positively"],
  "dislikes": ["list of things they mention negatively"],
  "patterns": ["observed patterns in their preferences"],
  "occasions": ["when they seem to prefer wearing fragrance"],
  "summary": "2-3 sentence summary of insights"
}}
"""

    try:
        result = openrouter.chat_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
