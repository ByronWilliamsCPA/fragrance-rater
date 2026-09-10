"""Import API endpoints for Kaggle data."""

import asyncio
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import AuthenticatedIdentity, get_current_identity
from fragrance_rater.core.database import get_db
from fragrance_rater.services.kaggle_importer import KaggleImporter
from fragrance_rater.utils.logging import get_logger, log_audit_event

router = APIRouter(prefix="/import", tags=["import"])
logger = get_logger(__name__)


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
    # #CRITICAL: security: this route writes fragrance rows to the database
    # (a mutating, non-dry-run call can bulk-insert arbitrary caller-supplied
    # data) and previously carried no authentication dependency at all,
    # letting any caller who could reach the service trigger an import.
    # #VERIFY: reuses the same Authentik forward-auth identity dependency
    # already enforced on the other mutating routes (fragrances/evaluations/
    # reviewers, see fragrance_rater.core.auth.get_current_identity); fails
    # closed with 401 whenever settings.authentik_required is true and the
    # request did not transit the Traefik forward-auth middleware.
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    dry_run: bool = False,
) -> ImportResponse:
    """Import fragrances from a Kaggle CSV file.

    Upload a CSV file with fragrance data. Expected columns include:
    name, brand, concentration, year, gender, family, top_notes,
    heart_notes, base_notes, accords (flexible column name matching).

    Set dry_run=true to validate without writing to database.

    Requires a verified Authentik forward-auth identity (see
    ``fragrance_rater.core.auth.get_current_identity``) when
    ``settings.authentik_required`` is true.
    """
    filename = file.filename
    if not filename or not filename.endswith(".csv"):
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
            log_audit_event(
                logger,
                action="kaggle_import",
                actor=identity.username,
                target_type="kaggle_csv",
                target_id=filename,
                imported=result.imported,
                skipped=result.skipped,
            )

        return ImportResponse(
            total_rows=result.total_rows,
            imported=result.imported,
            skipped=result.skipped,
            errors=result.errors[:20],  # Limit errors returned
        )

    finally:
        # Clean up temp file without blocking the event loop
        await asyncio.to_thread(tmp_path.unlink, missing_ok=True)
