"""Fragrance catalog endpoints.

These endpoints describe the fragrance catalog surface used by
the rating workflow. The current implementation serves an
in-memory sample list; the production catalog is backed by the
data pipeline described in ADR-002 and is not part of this
change. The routes exist primarily to give the OpenAPI document a
realistic, tagged ``fragrances`` resource and to back the Postman
contract suite.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/fragrances", tags=["fragrances"])


class Fragrance(BaseModel):
    """A fragrance catalog entry.

    Attributes:
        id: Stable integer identifier.
        name: Fragrance name.
        brand: Fragrance house / brand.
        notes: Accord / top / heart / base notes.
    """

    id: int = Field(..., ge=1, description="Stable integer identifier.")
    name: str = Field(..., description="Fragrance name.")
    brand: str = Field(..., description="Fragrance house or brand.")
    notes: list[str] = Field(default_factory=list, description="Accord notes.")


class FragranceListResponse(BaseModel):
    """Paginated-style response for ``GET /fragrances``."""

    items: list[Fragrance] = Field(default_factory=list, description="Catalog entries.")
    total: int = Field(..., ge=0, description="Total entries available.")


_SAMPLE_CATALOG: list[Fragrance] = [
    Fragrance(
        id=1,
        name="Aventus",
        brand="Creed",
        notes=["pineapple", "birch", "blackcurrant", "musk"],
    ),
    Fragrance(
        id=2,
        name="Sauvage",
        brand="Dior",
        notes=["bergamot", "pepper", "ambroxan"],
    ),
    Fragrance(
        id=3,
        name="Bleu de Chanel",
        brand="Chanel",
        notes=["grapefruit", "incense", "sandalwood"],
    ),
]


@router.get(
    "",
    response_model=FragranceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List fragrances in the catalog",
    responses={
        200: {"description": "Catalog returned."},
    },
)
def list_fragrances() -> FragranceListResponse:
    """Return the fragrance catalog used by the rating workflow.

    This is a read-only listing of catalog entries. No LLM call is
    made; fragrance metadata comes from the local catalog managed
    by the data pipeline (ADR-002).

    Returns:
        The full catalog with its item count.
    """
    return FragranceListResponse(items=_SAMPLE_CATALOG, total=len(_SAMPLE_CATALOG))


@router.get(
    "/{fragrance_id}",
    response_model=Fragrance,
    status_code=status.HTTP_200_OK,
    summary="Get a fragrance by id",
    responses={
        200: {"description": "Fragrance found."},
        404: {"description": "No fragrance with the given id."},
        422: {"description": "Path parameter failed validation."},
    },
)
def get_fragrance(fragrance_id: int) -> Fragrance:
    """Look up a single fragrance by its integer id.

    No LLM call is made; this endpoint only serves catalog
    metadata. Use ``POST /ratings`` to obtain an LLM-powered score
    for a fragrance.

    Args:
        fragrance_id: Integer primary key of the catalog entry.

    Returns:
        The matching fragrance record.

    Raises:
        HTTPException: 404 when no entry has the requested id.
    """
    for entry in _SAMPLE_CATALOG:
        if entry.id == fragrance_id:
            return entry
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Fragrance {fragrance_id} not found",
    )
