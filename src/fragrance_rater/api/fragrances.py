"""Fragrance API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.fragrance import (
    FragranceCreate,
    FragranceResponse,
    FragranceSearchParams,
    FragranceUpdate,
)
from fragrance_rater.services.fragrance_service import FragranceService

router = APIRouter(prefix="/fragrances", tags=["fragrances"])


async def get_fragrance_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FragranceService:
    """Dependency to get FragranceService instance."""
    return FragranceService(session)


@router.get("", response_model=list[FragranceResponse])
async def list_fragrances(
    service: Annotated[FragranceService, Depends(get_fragrance_service)],
    q: str | None = Query(None, description="Search query for name or brand"),
    brand: str | None = Query(None, description="Filter by brand"),
    primary_family: str | None = Query(None, description="Filter by fragrance family"),
    gender_target: str | None = Query(None, description="Filter by gender target"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[FragranceResponse]:
    """List and search fragrances.

    Supports filtering by name/brand search, brand, family, and gender.
    """
    params = FragranceSearchParams(
        q=q,
        brand=brand,
        primary_family=primary_family,
        gender_target=gender_target,  # type: ignore[arg-type]
        limit=limit,
        offset=offset,
    )
    fragrances = await service.search(params)

    return [
        FragranceResponse(
            id=f.id,
            name=f.name,
            brand=f.brand,
            concentration=f.concentration,
            launch_year=f.launch_year,
            gender_target=f.gender_target,
            primary_family=f.primary_family,
            subfamily=f.subfamily,
            intensity=f.intensity,
            data_source=f.data_source,
            external_id=f.external_id,
            created_at=f.created_at,
            updated_at=f.updated_at,
            notes=[],  # Simplified for list view
            accords=[],
        )
        for f in fragrances
    ]


@router.get("/{fragrance_id}", response_model=FragranceResponse)
async def get_fragrance(
    fragrance_id: str,
    service: Annotated[FragranceService, Depends(get_fragrance_service)],
) -> FragranceResponse:
    """Get a fragrance by ID with full details."""
    fragrance = await service.get_by_id(fragrance_id)
    if not fragrance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "FRAGRANCE_NOT_FOUND", "message": "Fragrance not found"},
        )

    from fragrance_rater.schemas.fragrance import (
        FragranceAccordResponse,
        FragranceNoteResponse,
        NoteResponse,
    )

    return FragranceResponse(
        id=fragrance.id,
        name=fragrance.name,
        brand=fragrance.brand,
        concentration=fragrance.concentration,
        launch_year=fragrance.launch_year,
        gender_target=fragrance.gender_target,
        primary_family=fragrance.primary_family,
        subfamily=fragrance.subfamily,
        intensity=fragrance.intensity,
        data_source=fragrance.data_source,
        external_id=fragrance.external_id,
        created_at=fragrance.created_at,
        updated_at=fragrance.updated_at,
        notes=[
            FragranceNoteResponse(
                note=NoteResponse(
                    id=fn.note.id,
                    name=fn.note.name,
                    category=fn.note.category,
                    subcategory=fn.note.subcategory,
                ),
                position=fn.position,
            )
            for fn in fragrance.notes
        ],
        accords=[
            FragranceAccordResponse(
                accord_type=acc.accord_type,
                intensity=acc.intensity,
            )
            for acc in fragrance.accords
        ],
    )


@router.post("", response_model=FragranceResponse, status_code=status.HTTP_201_CREATED)
async def create_fragrance(
    data: FragranceCreate,
    service: Annotated[FragranceService, Depends(get_fragrance_service)],
) -> FragranceResponse:
    """Create a new fragrance with notes and accords."""
    fragrance = await service.create(data)
    return await get_fragrance(fragrance.id, service)


@router.patch("/{fragrance_id}", response_model=FragranceResponse)
async def update_fragrance(
    fragrance_id: str,
    data: FragranceUpdate,
    service: Annotated[FragranceService, Depends(get_fragrance_service)],
) -> FragranceResponse:
    """Update an existing fragrance."""
    fragrance = await service.update(fragrance_id, data)
    if not fragrance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "FRAGRANCE_NOT_FOUND", "message": "Fragrance not found"},
        )
    return await get_fragrance(fragrance_id, service)


@router.delete("/{fragrance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fragrance(
    fragrance_id: str,
    service: Annotated[FragranceService, Depends(get_fragrance_service)],
) -> None:
    """Delete a fragrance by ID."""
    deleted = await service.delete(fragrance_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "FRAGRANCE_NOT_FOUND", "message": "Fragrance not found"},
        )
