"""
API routes for data import operations.
"""
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import shutil

from app.db import get_db
from app.core.config import settings
from app.schemas import ImportResult
from app.services import KaggleImporter, FragellaClient

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/kaggle", response_model=ImportResult)
async def import_kaggle_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Import fragrances from a Kaggle CSV file.

    Upload a CSV file downloaded from Kaggle datasets.
    Supports various column name formats.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    # Save uploaded file temporarily
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    temp_path = data_dir / f"upload_{file.filename}"

    try:
        with open(temp_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Import the file
        importer = KaggleImporter(db)
        result = importer.import_csv(temp_path)

        return result

    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


@router.post("/kaggle/directory", response_model=List[ImportResult])
def import_kaggle_directory(
    directory: str = "/app/data",
    db: Session = Depends(get_db)
):
    """
    Import all CSV files from a directory.

    Use this to bulk import multiple Kaggle datasets.
    Directory should be mounted in the container.
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")

    importer = KaggleImporter(db)
    return importer.import_directory(dir_path)


@router.get("/fragella/status")
def fragella_api_status(db: Session = Depends(get_db)):
    """
    Check Fragella API status and remaining quota.
    """
    client = FragellaClient(db)

    return {
        "configured": bool(client.api_key),
        "monthly_limit": client.monthly_limit,
        "requests_remaining": client.requests_remaining,
        "requests_used": client.usage.get("count", 0),
        "current_month": client.usage.get("month"),
        "recent_requests": client.usage.get("requests", [])[-5:]  # Last 5
    }


@router.post("/fragella/search")
def search_fragella(
    query: str,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """
    Search Fragella API directly (uses 1 API request).

    Results are returned but NOT automatically imported.
    Use /fragrances/lookup to search and import.
    """
    client = FragellaClient(db)

    if not client.can_make_request:
        raise HTTPException(
            status_code=429,
            detail=f"Fragella API quota exhausted. {client.requests_remaining} requests remaining this month."
        )

    try:
        results = client.search(query, limit)
        return {
            "query": query,
            "results": results,
            "requests_remaining": client.requests_remaining
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed-reviewers")
def seed_default_reviewers(db: Session = Depends(get_db)):
    """
    Create the default family member reviewers.
    """
    from app.services import ReviewerService

    default_names = ["Byron", "Veronica", "Bayden", "Ariannah"]
    created = []

    for name in default_names:
        existing = ReviewerService.get_by_name(db, name)
        if not existing:
            reviewer = ReviewerService.get_or_create(db, name)
            created.append(name)

    db.commit()

    return {
        "message": "Seeded default reviewers",
        "created": created,
        "all_reviewers": [r.name for r in ReviewerService.get_all(db)]
    }
