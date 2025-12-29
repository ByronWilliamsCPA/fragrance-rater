"""
API routes for fragrance operations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DataSource, FragranceFamily, FragranceSubfamily, GenderTarget
from app.schemas import (
    FragranceCreate, FragranceUpdate, FragranceResponse, FragranceListResponse,
    FragranceSearchParams, NoteResponse
)
from app.services import FragranceService, NoteService, FragellaClient, FragellaAPIError
from app.scrapers import FragranticaScraper

router = APIRouter(prefix="/fragrances", tags=["fragrances"])


@router.get("/", response_model=List[FragranceListResponse])
def list_fragrances(
    query: Optional[str] = None,
    brand: Optional[str] = None,
    family: Optional[FragranceFamily] = None,
    subfamily: Optional[FragranceSubfamily] = None,
    gender: Optional[GenderTarget] = None,
    min_rating: Optional[float] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Search and list fragrances with optional filters.
    """
    params = FragranceSearchParams(
        query=query,
        brand=brand,
        family=family,
        subfamily=subfamily,
        gender=gender,
        min_rating=min_rating,
        limit=limit,
        offset=offset
    )
    return FragranceService.search(db, params)


@router.get("/{fragrance_id}", response_model=FragranceResponse)
def get_fragrance(fragrance_id: int, db: Session = Depends(get_db)):
    """
    Get a single fragrance by ID with full details.
    """
    fragrance = FragranceService.get_by_id(db, fragrance_id)
    if not fragrance:
        raise HTTPException(status_code=404, detail="Fragrance not found")

    # Get notes organized by position
    notes_by_position = FragranceService.get_notes_by_position(db, fragrance_id)

    # Build response
    response = FragranceResponse.model_validate(fragrance)
    response.top_notes = [NoteResponse.model_validate(n) for n in notes_by_position['top']]
    response.heart_notes = [NoteResponse.model_validate(n) for n in notes_by_position['heart']]
    response.base_notes = [NoteResponse.model_validate(n) for n in notes_by_position['base']]

    return response


@router.post("/", response_model=FragranceResponse, status_code=201)
def create_fragrance(data: FragranceCreate, db: Session = Depends(get_db)):
    """
    Create a new fragrance manually.
    """
    # Check if already exists
    existing = FragranceService.get_by_name_brand(db, data.name, data.brand)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Fragrance '{data.name}' by '{data.brand}' already exists (ID: {existing.id})"
        )

    fragrance = FragranceService.create(db, data)
    db.commit()

    # Get full response with notes
    notes_by_position = FragranceService.get_notes_by_position(db, fragrance.id)
    response = FragranceResponse.model_validate(fragrance)
    response.top_notes = [NoteResponse.model_validate(n) for n in notes_by_position['top']]
    response.heart_notes = [NoteResponse.model_validate(n) for n in notes_by_position['heart']]
    response.base_notes = [NoteResponse.model_validate(n) for n in notes_by_position['base']]

    return response


@router.patch("/{fragrance_id}", response_model=FragranceResponse)
def update_fragrance(fragrance_id: int, data: FragranceUpdate, db: Session = Depends(get_db)):
    """
    Update a fragrance.
    """
    fragrance = FragranceService.update(db, fragrance_id, data)
    if not fragrance:
        raise HTTPException(status_code=404, detail="Fragrance not found")

    db.commit()

    notes_by_position = FragranceService.get_notes_by_position(db, fragrance_id)
    response = FragranceResponse.model_validate(fragrance)
    response.top_notes = [NoteResponse.model_validate(n) for n in notes_by_position['top']]
    response.heart_notes = [NoteResponse.model_validate(n) for n in notes_by_position['heart']]
    response.base_notes = [NoteResponse.model_validate(n) for n in notes_by_position['base']]

    return response


@router.post("/lookup", response_model=FragranceResponse)
def lookup_fragrance(
    name: str = Query(..., description="Fragrance name to search for"),
    brand: Optional[str] = Query(None, description="Brand name (helps accuracy)"),
    db: Session = Depends(get_db)
):
    """
    Look up a fragrance from external sources.

    Data source priority:
    1. Local database
    2. Fragella API (if quota available)
    3. Fragrantica scraper (fallback)

    Returns existing or newly imported fragrance.
    """
    # First check local database
    if brand:
        existing = FragranceService.get_by_name_brand(db, name, brand)
        if existing:
            notes_by_position = FragranceService.get_notes_by_position(db, existing.id)
            response = FragranceResponse.model_validate(existing)
            response.top_notes = [NoteResponse.model_validate(n) for n in notes_by_position['top']]
            response.heart_notes = [NoteResponse.model_validate(n) for n in notes_by_position['heart']]
            response.base_notes = [NoteResponse.model_validate(n) for n in notes_by_position['base']]
            return response

    # Search local database
    params = FragranceSearchParams(query=name, brand=brand, limit=1)
    local_results = FragranceService.search(db, params)
    if local_results:
        fragrance = local_results[0]
        notes_by_position = FragranceService.get_notes_by_position(db, fragrance.id)
        response = FragranceResponse.model_validate(fragrance)
        response.top_notes = [NoteResponse.model_validate(n) for n in notes_by_position['top']]
        response.heart_notes = [NoteResponse.model_validate(n) for n in notes_by_position['heart']]
        response.base_notes = [NoteResponse.model_validate(n) for n in notes_by_position['base']]
        return response

    # Try Fragella API
    fragella = FragellaClient(db)
    if fragella.can_make_request:
        try:
            query = f"{name} {brand}" if brand else name
            fragrance_id = fragella.search_and_import(query)
            if fragrance_id:
                fragrance = FragranceService.get_by_id(db, fragrance_id)
                notes_by_position = FragranceService.get_notes_by_position(db, fragrance_id)
                response = FragranceResponse.model_validate(fragrance)
                response.top_notes = [NoteResponse.model_validate(n) for n in notes_by_position['top']]
                response.heart_notes = [NoteResponse.model_validate(n) for n in notes_by_position['heart']]
                response.base_notes = [NoteResponse.model_validate(n) for n in notes_by_position['base']]
                return response
        except FragellaAPIError:
            pass  # Fall through to scraper

    # Fallback to Fragrantica scraper
    scraper = FragranticaScraper(db)
    fragrance_id = scraper.search_and_import(name, brand)

    if fragrance_id:
        fragrance = FragranceService.get_by_id(db, fragrance_id)
        notes_by_position = FragranceService.get_notes_by_position(db, fragrance_id)
        response = FragranceResponse.model_validate(fragrance)
        response.top_notes = [NoteResponse.model_validate(n) for n in notes_by_position['top']]
        response.heart_notes = [NoteResponse.model_validate(n) for n in notes_by_position['heart']]
        response.base_notes = [NoteResponse.model_validate(n) for n in notes_by_position['base']]
        return response

    raise HTTPException(
        status_code=404,
        detail=f"Could not find fragrance '{name}'" + (f" by '{brand}'" if brand else "")
    )


@router.get("/notes/search", response_model=List[NoteResponse])
def search_notes(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db)
):
    """
    Search notes by name for autocomplete.
    """
    return NoteService.search(db, query, limit)


@router.get("/notes/all", response_model=List[NoteResponse])
def list_all_notes(
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db)
):
    """
    Get all notes ordered by frequency of use.
    """
    return NoteService.get_all(db, limit)
