"""
API routes for reviewers and evaluations.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    ReviewerCreate, ReviewerResponse,
    EvaluationCreate, EvaluationResponse,
    FragranceListResponse
)
from app.services import ReviewerService, EvaluationService, FragranceService

router = APIRouter(tags=["evaluations"])


# --- Reviewer Routes ---

@router.get("/reviewers", response_model=List[ReviewerResponse])
def list_reviewers(db: Session = Depends(get_db)):
    """
    Get all reviewers (family members).
    """
    return ReviewerService.get_all(db)


@router.get("/reviewers/{reviewer_id}", response_model=ReviewerResponse)
def get_reviewer(reviewer_id: int, db: Session = Depends(get_db)):
    """
    Get a single reviewer by ID.
    """
    reviewer = ReviewerService.get_by_id(db, reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")
    return reviewer


@router.post("/reviewers", response_model=ReviewerResponse, status_code=201)
def create_reviewer(data: ReviewerCreate, db: Session = Depends(get_db)):
    """
    Create a new reviewer (family member).
    """
    existing = ReviewerService.get_by_name(db, data.name)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Reviewer '{data.name}' already exists"
        )

    reviewer = ReviewerService.create(db, data)
    db.commit()
    return reviewer


# --- Evaluation Routes ---

@router.get("/evaluations", response_model=List[EvaluationResponse])
def list_evaluations(
    reviewer_id: int = Query(None, description="Filter by reviewer"),
    fragrance_id: int = Query(None, description="Filter by fragrance"),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db)
):
    """
    List evaluations with optional filters.
    """
    if reviewer_id:
        evaluations = EvaluationService.get_by_reviewer(db, reviewer_id, limit)
    elif fragrance_id:
        evaluations = EvaluationService.get_by_fragrance(db, fragrance_id)
    else:
        evaluations = EvaluationService.get_recent(db, limit)

    # Build response with related data
    results = []
    for eval in evaluations:
        response = EvaluationResponse.model_validate(eval)
        response.fragrance = FragranceListResponse.model_validate(eval.fragrance) if eval.fragrance else None
        response.reviewer = ReviewerResponse.model_validate(eval.reviewer) if eval.reviewer else None
        results.append(response)

    return results


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(evaluation_id: int, db: Session = Depends(get_db)):
    """
    Get a single evaluation by ID.
    """
    evaluation = EvaluationService.get_by_id(db, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    response = EvaluationResponse.model_validate(evaluation)
    response.fragrance = FragranceListResponse.model_validate(evaluation.fragrance) if evaluation.fragrance else None
    response.reviewer = ReviewerResponse.model_validate(evaluation.reviewer) if evaluation.reviewer else None

    return response


@router.post("/evaluations", response_model=EvaluationResponse, status_code=201)
def create_evaluation(data: EvaluationCreate, db: Session = Depends(get_db)):
    """
    Create a new evaluation.

    This is the primary entry point for recording a family member's
    opinion of a fragrance.
    """
    # Validate fragrance exists
    fragrance = FragranceService.get_by_id(db, data.fragrance_id)
    if not fragrance:
        raise HTTPException(status_code=404, detail="Fragrance not found")

    # Validate reviewer exists
    reviewer = ReviewerService.get_by_id(db, data.reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    evaluation = EvaluationService.create(db, data)
    db.commit()

    response = EvaluationResponse.model_validate(evaluation)
    response.fragrance = FragranceListResponse.model_validate(fragrance)
    response.reviewer = ReviewerResponse.model_validate(reviewer)

    return response


# --- Quick Evaluation Entry ---

@router.post("/evaluate", response_model=EvaluationResponse, status_code=201)
def quick_evaluate(
    fragrance_name: str = Query(..., description="Fragrance name"),
    fragrance_brand: str = Query(None, description="Brand name (helps accuracy)"),
    reviewer_name: str = Query(..., description="Reviewer name (will be created if new)"),
    rating: int = Query(..., ge=1, le=5, description="Rating 1-5"),
    notes: str = Query(None, description="Free-form notes"),
    db: Session = Depends(get_db)
):
    """
    Quick evaluation entry with auto-lookup.

    If fragrance doesn't exist locally, attempts to fetch from external sources.
    Creates reviewer if they don't exist.
    """
    # Get or create reviewer
    reviewer = ReviewerService.get_or_create(db, reviewer_name)

    # Try to find fragrance locally first
    fragrance = None
    if fragrance_brand:
        fragrance = FragranceService.get_by_name_brand(db, fragrance_name, fragrance_brand)

    if not fragrance:
        # Search local database
        from app.schemas import FragranceSearchParams
        params = FragranceSearchParams(query=fragrance_name, brand=fragrance_brand, limit=1)
        results = FragranceService.search(db, params)
        if results:
            fragrance = results[0]

    if not fragrance:
        # Try external lookup
        from app.services import FragellaClient
        from app.scrapers import FragranticaScraper

        fragella = FragellaClient(db)
        fragrance_id = None

        if fragella.can_make_request:
            try:
                query = f"{fragrance_name} {fragrance_brand}" if fragrance_brand else fragrance_name
                fragrance_id = fragella.search_and_import(query)
            except Exception:
                pass

        if not fragrance_id:
            scraper = FragranticaScraper(db)
            fragrance_id = scraper.search_and_import(fragrance_name, fragrance_brand)

        if fragrance_id:
            fragrance = FragranceService.get_by_id(db, fragrance_id)

    if not fragrance:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find fragrance '{fragrance_name}'. Try adding it manually first."
        )

    # Create evaluation
    eval_data = EvaluationCreate(
        fragrance_id=fragrance.id,
        reviewer_id=reviewer.id,
        rating=rating,
        notes=notes
    )

    evaluation = EvaluationService.create(db, eval_data)
    db.commit()

    response = EvaluationResponse.model_validate(evaluation)
    response.fragrance = FragranceListResponse.model_validate(fragrance)
    response.reviewer = ReviewerResponse.model_validate(reviewer)

    return response
