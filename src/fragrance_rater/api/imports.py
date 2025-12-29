"""Import API endpoints for Kaggle data."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.database import get_db
from fragrance_rater.services.kaggle_importer import KaggleImporter

router = APIRouter(prefix="/import", tags=["import"])


class ImportResponse(BaseModel):
    """Response model for import operations."""

    total_rows: int = Field(..., description="Total rows processed")
    imported: int = Field(..., description="Successfully imported count")
    skipped: int = Field(..., description="Skipped rows count")
    errors: list[str] = Field(default_factory=list, description="Error messages")


@router.post("/kaggle", response_model=ImportResponse)
async def import_kaggle_csv(
    file: Annotated[UploadFile, File(description="Kaggle CSV file to import")],
    session: Annotated[AsyncSession, Depends(get_db)],
    dry_run: bool = False,
) -> ImportResponse:
    """Import fragrances from a Kaggle CSV file.

    Upload a CSV file with fragrance data. Expected columns include:
    name, brand, concentration, year, gender, family, top_notes,
    heart_notes, base_notes, accords (flexible column name matching).

    Set dry_run=true to validate without writing to database.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_FILE", "message": "File must be a CSV"},
        )

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        importer = KaggleImporter(session)
        result = await importer.import_csv(tmp_path, dry_run=dry_run)

        if not dry_run and result.imported > 0:
            await session.commit()

        return ImportResponse(
            total_rows=result.total_rows,
            imported=result.imported,
            skipped=result.skipped,
            errors=result.errors[:20],  # Limit errors returned
        )

    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)
