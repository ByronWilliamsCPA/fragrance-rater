"""Fragrance API endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.fragrance import (
    FragranceAccordResponse,
    FragranceCreate,
    FragranceNoteResponse,
    FragranceResponse,
    FragranceSearchParams,
    FragranceUpdate,
    NoteResponse,
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
    *,
    q: Annotated[
        str | None, Query(description="Search query for name or brand")
    ] = None,
    brand: Annotated[str | None, Query(description="Filter by brand")] = None,
    primary_family: Annotated[
        str | None, Query(description="Filter by fragrance family")
    ] = None,
    gender_target: Annotated[
        Literal["Masculine", "Feminine", "Unisex"] | None,
        Query(description="Filter by gender target"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[FragranceResponse]:
    """List and search fragrances.

    Supports filtering by name/brand search, brand, family, and gender. An
    unknown ``gender_target`` value is rejected with 422 before the search
    parameters are built.
    """
    params = FragranceSearchParams(
        q=q,
        brand=brand,
        primary_family=primary_family,
        gender_target=gender_target,
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
    """Create a new fragrance with notes and accords.

    Rejects a (name, brand) pair that already exists (Major finding 8's
    `uq_fragrance_name_brand` constraint) with a 409 rather than letting the
    resulting IntegrityError surface as an unhandled 500.
    """
    # #ASSUME: data-integrity: this has no pre-check, only a catch of the
    # IntegrityError the new UNIQUE(name, brand) constraint raises, since a
    # pre-check here would carry the same check-then-insert race the
    # evaluations endpoint has to guard against separately.
    # #VERIFY: the caught path rolls back before returning, so the session
    # is left usable for the next request on this connection.
    try:
        fragrance = await service.create(data)
    except IntegrityError:
        await service.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "FRAGRANCE_EXISTS",
                "message": (
                    f"A fragrance named {data.name!r} by {data.brand!r} already exists"
                ),
            },
        ) from None
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
