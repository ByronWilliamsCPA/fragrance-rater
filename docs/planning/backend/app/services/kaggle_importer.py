"""
Kaggle dataset import service.
Loads fragrance data from pre-downloaded Kaggle CSV files.
"""
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import json
import re

from app.models import DataSource, Concentration, GenderTarget
from app.schemas import FragranceCreate, ImportResult
from app.services.fragrance_service import FragranceService, NoteService


def parse_notes_string(notes_str: str) -> List[str]:
    """
    Parse notes from various string formats.
    Handles: "['note1', 'note2']", "note1, note2", "note1|note2"
    """
    if not notes_str or pd.isna(notes_str):
        return []

    notes_str = str(notes_str).strip()

    # Try JSON-like format
    if notes_str.startswith('['):
        try:
            # Handle Python list syntax
            notes_str = notes_str.replace("'", '"')
            return json.loads(notes_str)
        except json.JSONDecodeError:
            pass

    # Try comma-separated
    if ',' in notes_str:
        return [n.strip().strip("'\"") for n in notes_str.split(',') if n.strip()]

    # Try pipe-separated
    if '|' in notes_str:
        return [n.strip() for n in notes_str.split('|') if n.strip()]

    # Single note
    return [notes_str] if notes_str else []


def parse_accords(accords_str: str) -> Dict[str, float]:
    """
    Parse accords from string format.
    Returns dict with accord names as keys and weights as values (0-1).
    """
    if not accords_str or pd.isna(accords_str):
        return {}

    accords = {}
    accords_str = str(accords_str).strip()

    # Try JSON format
    if accords_str.startswith('{'):
        try:
            return json.loads(accords_str.replace("'", '"'))
        except json.JSONDecodeError:
            pass

    # Try list format - assume equal weights
    if accords_str.startswith('['):
        try:
            accord_list = json.loads(accords_str.replace("'", '"'))
            # Assign descending weights (first is strongest)
            for i, accord in enumerate(accord_list):
                accords[accord.lower()] = max(0.1, 1.0 - (i * 0.15))
            return accords
        except json.JSONDecodeError:
            pass

    # Comma-separated list
    parts = [p.strip().strip("'\"") for p in accords_str.split(',')]
    for i, accord in enumerate(parts):
        if accord:
            accords[accord.lower()] = max(0.1, 1.0 - (i * 0.15))

    return accords


def normalize_concentration(value: str) -> Optional[Concentration]:
    """Map concentration strings to enum values."""
    if not value or pd.isna(value):
        return None

    value = str(value).lower().strip()

    mapping = {
        'parfum': Concentration.PARFUM,
        'extrait': Concentration.PARFUM,
        'extrait de parfum': Concentration.PARFUM,
        'pure parfum': Concentration.PARFUM,
        'edp': Concentration.EDP,
        'eau de parfum': Concentration.EDP,
        'edt': Concentration.EDT,
        'eau de toilette': Concentration.EDT,
        'edc': Concentration.EDC,
        'eau de cologne': Concentration.EDC,
        'cologne': Concentration.EDC,
        'body mist': Concentration.BODY_MIST,
        'body spray': Concentration.BODY_MIST,
    }

    for key, val in mapping.items():
        if key in value:
            return val

    return Concentration.OTHER


def normalize_gender(value: str) -> Optional[GenderTarget]:
    """Map gender strings to enum values."""
    if not value or pd.isna(value):
        return None

    value = str(value).lower().strip()

    if 'unisex' in value or 'shared' in value:
        return GenderTarget.UNISEX
    if 'women' in value or 'female' in value or 'feminine' in value:
        return GenderTarget.FEMININE
    if 'men' in value or 'male' in value or 'masculine' in value:
        return GenderTarget.MASCULINE

    return GenderTarget.UNISEX


class KaggleImporter:
    """
    Import fragrance data from Kaggle CSV datasets.

    Expected CSV columns (flexible mapping):
    - name/perfume/fragrance_name
    - brand/house/designer
    - notes/top_notes/middle_notes/base_notes
    - accords/main_accords
    - rating/score
    - gender
    - longevity/sillage
    - year/launch_year
    - image/image_url
    - url/fragrantica_url
    """

    # Column name mappings (source -> target)
    COLUMN_MAPPINGS = {
        'name': ['name', 'perfume', 'fragrance_name', 'fragrance', 'title'],
        'brand': ['brand', 'house', 'designer', 'brand_name'],
        'top_notes': ['top_notes', 'top', 'top notes'],
        'heart_notes': ['heart_notes', 'middle_notes', 'middle', 'heart', 'heart notes', 'middle notes'],
        'base_notes': ['base_notes', 'base', 'base notes'],
        'notes': ['notes', 'all_notes', 'fragrance_notes', 'scent_notes'],
        'accords': ['accords', 'main_accords', 'accord', 'main accords'],
        'rating': ['rating', 'score', 'avg_rating', 'average_rating'],
        'gender': ['gender', 'for', 'target', 'gender_target'],
        'concentration': ['concentration', 'type', 'oil_type', 'oiltype'],
        'longevity': ['longevity', 'lasting', 'duration'],
        'sillage': ['sillage', 'projection'],
        'year': ['year', 'launch_year', 'release_year', 'launched'],
        'image_url': ['image', 'image_url', 'img', 'picture'],
        'url': ['url', 'fragrantica_url', 'link', 'perfume_url'],
        'country': ['country', 'origin'],
    }

    def __init__(self, db: Session):
        self.db = db

    def _find_column(self, df: pd.DataFrame, target: str) -> Optional[str]:
        """Find the actual column name in the dataframe for a target field."""
        candidates = self.COLUMN_MAPPINGS.get(target, [target])

        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in candidates:
                return col

        return None

    def _get_value(self, row: pd.Series, df: pd.DataFrame, target: str, default=None):
        """Get value from row using flexible column mapping."""
        col = self._find_column(df, target)
        if col and col in row.index:
            val = row[col]
            if pd.isna(val):
                return default
            return val
        return default

    def import_csv(self, filepath: Path) -> ImportResult:
        """Import fragrances from a CSV file."""
        result = ImportResult(
            source=DataSource.KAGGLE,
            total_records=0,
            imported=0,
            updated=0,
            skipped=0,
            errors=0,
            error_messages=[]
        )

        if not filepath.exists():
            result.error_messages.append(f"File not found: {filepath}")
            return result

        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except Exception as e:
            try:
                df = pd.read_csv(filepath, encoding='latin-1')
            except Exception as e2:
                result.error_messages.append(f"Failed to read CSV: {e2}")
                return result

        result.total_records = len(df)

        # Check required columns
        name_col = self._find_column(df, 'name')
        brand_col = self._find_column(df, 'brand')

        if not name_col:
            result.error_messages.append("No name column found in CSV")
            return result

        if not brand_col:
            result.error_messages.append("No brand column found in CSV")
            return result

        for idx, row in df.iterrows():
            try:
                name = str(self._get_value(row, df, 'name', '')).strip()
                brand = str(self._get_value(row, df, 'brand', '')).strip()

                if not name or not brand:
                    result.skipped += 1
                    continue

                # Check if already exists
                existing = FragranceService.get_by_name_brand(self.db, name, brand)

                # Parse notes
                top_notes = parse_notes_string(self._get_value(row, df, 'top_notes', ''))
                heart_notes = parse_notes_string(self._get_value(row, df, 'heart_notes', ''))
                base_notes = parse_notes_string(self._get_value(row, df, 'base_notes', ''))

                # If no pyramid notes, try general notes field
                if not top_notes and not heart_notes and not base_notes:
                    general_notes = parse_notes_string(self._get_value(row, df, 'notes', ''))
                    # Put all in heart by default if no position known
                    heart_notes = general_notes

                # Parse accords
                accords = parse_accords(self._get_value(row, df, 'accords', ''))

                # Parse rating
                rating = self._get_value(row, df, 'rating')
                if rating is not None:
                    try:
                        rating = float(rating)
                        # Normalize to 5-point scale if needed
                        if rating > 5:
                            rating = rating / 2  # Assume 10-point scale
                    except (ValueError, TypeError):
                        rating = None

                # Parse year
                year = self._get_value(row, df, 'year')
                if year is not None:
                    try:
                        year = int(float(year))
                        if year < 1800 or year > 2100:
                            year = None
                    except (ValueError, TypeError):
                        year = None

                fragrance_data = FragranceCreate(
                    name=name,
                    brand=brand,
                    top_notes=top_notes,
                    heart_notes=heart_notes,
                    base_notes=base_notes,
                    accords=accords,
                    rating=rating,
                    launch_year=year,
                    gender_target=normalize_gender(self._get_value(row, df, 'gender')),
                    concentration=normalize_concentration(self._get_value(row, df, 'concentration')),
                    longevity=str(self._get_value(row, df, 'longevity', '')) or None,
                    sillage=str(self._get_value(row, df, 'sillage', '')) or None,
                    image_url=str(self._get_value(row, df, 'image_url', '')) or None,
                    fragrantica_url=str(self._get_value(row, df, 'url', '')) or None,
                    country=str(self._get_value(row, df, 'country', '')) or None,
                    data_source=DataSource.KAGGLE,
                )

                if existing:
                    # Only update if Kaggle data is more complete
                    # For now, skip existing
                    result.skipped += 1
                else:
                    FragranceService.create(self.db, fragrance_data)
                    result.imported += 1

                # Commit in batches
                if (result.imported + result.updated) % 100 == 0:
                    self.db.commit()

            except Exception as e:
                result.errors += 1
                if len(result.error_messages) < 10:
                    result.error_messages.append(f"Row {idx}: {str(e)}")

        self.db.commit()
        return result

    def import_directory(self, directory: Path) -> List[ImportResult]:
        """Import all CSV files from a directory."""
        results = []

        if not directory.exists():
            return results

        for csv_file in directory.glob("*.csv"):
            result = self.import_csv(csv_file)
            results.append(result)

        return results
