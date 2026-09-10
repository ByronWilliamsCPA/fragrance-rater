"""Root-mounted sample fragrance catalog.

This is the in-memory catalog that the original scaffold served at
``/fragrances``. It is kept, unchanged in behaviour, because the Postman
contract suite (``docs/api/postman-collection.json``, run by the
``postman-api-tests`` workflow) asserts on this exact surface: an
``items``/``total`` listing, integer ids, and a 404 with ``detail`` for
unknown ids.

The real, database-backed catalog lives under ``/api/v1/fragrances`` (see
``fragrance_rater.api.fragrances``). Once the contract suite is pointed at
that surface this module can be deleted.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/fragrances", tags=["catalog-stub"])


class CatalogEntry(BaseModel):
    """A sample catalog entry.

    Attributes:
        id (int): Stable integer identifier.
        name (str): Fragrance name.
        brand (str): Fragrance house / brand.
        notes (list[str]): Accord / top / heart / base notes.
    """

    id: int = Field(..., ge=1, description="Stable integer identifier.")
    name: str = Field(..., description="Fragrance name.")
    brand: str = Field(..., description="Fragrance house or brand.")
    notes: list[str] = Field(default_factory=list, description="Accord notes.")


class CatalogListResponse(BaseModel):
    """Paginated-style response for ``GET /fragrances``.

    Attributes:
        items (list[CatalogEntry]): Catalog entries.
        total (int): Total entries available.
    """

    items: list[CatalogEntry] = Field(
        default_factory=list, description="Catalog entries."
    )
    total: int = Field(..., ge=0, description="Total entries available.")


_SAMPLE_CATALOG: list[CatalogEntry] = [
    CatalogEntry(
        id=1,
        name="Aventus",
        brand="Creed",
        notes=["pineapple", "birch", "blackcurrant", "musk"],
    ),
    CatalogEntry(
        id=2,
        name="Sauvage",
        brand="Dior",
        notes=["bergamot", "pepper", "ambroxan"],
    ),
    CatalogEntry(
        id=3,
        name="Bleu de Chanel",
        brand="Chanel",
        notes=["grapefruit", "incense", "sandalwood"],
    ),
]


@router.get(
    "",
    response_model=CatalogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List the sample fragrance catalog",
    responses={
        200: {"description": "Catalog returned."},
    },
)
def list_catalog_entries() -> CatalogListResponse:
    """Return the sample catalog used by the contract suite.

    Returns:
        CatalogListResponse: The full sample catalog with its item count.
    """
    return CatalogListResponse(items=_SAMPLE_CATALOG, total=len(_SAMPLE_CATALOG))


@router.get(
    "/{fragrance_id}",
    response_model=CatalogEntry,
    status_code=status.HTTP_200_OK,
    summary="Get a sample catalog entry by id",
    responses={
        200: {"description": "Fragrance found."},
        404: {"description": "No fragrance with the given id."},
        422: {"description": "Path parameter failed validation."},
    },
)
def get_catalog_entry(fragrance_id: int) -> CatalogEntry:
    """Look up a single sample entry by its integer id.

    Args:
        fragrance_id (int): Integer identifier of the catalog entry.

    Returns:
        CatalogEntry: The matching catalog entry.

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
