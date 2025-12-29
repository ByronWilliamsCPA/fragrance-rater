"""Kaggle CSV import service for fragrance data."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ImportResult:
    """Result of a Kaggle import operation."""

    total_rows: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ParsedFragrance:
    """Parsed fragrance data from CSV row."""

    name: str
    brand: str
    concentration: str
    launch_year: int | None
    gender_target: str
    primary_family: str
    subfamily: str
    top_notes: list[str]
    heart_notes: list[str]
    base_notes: list[str]
    accords: dict[str, float]


class KaggleImporter:
    """Service for importing fragrance data from Kaggle CSV files.

    Expected CSV columns (flexible matching):
    - Name/name/perfume: Fragrance name
    - Brand/brand/house: Brand name
    - Concentration/concentration/type: EDT, EDP, etc.
    - Year/year/launch_year: Launch year
    - Gender/gender/for: Masculine/Feminine/Unisex
    - Family/family/main_accords: Primary fragrance family
    - Top/top_notes: Top notes (comma-separated)
    - Heart/heart_notes/middle_notes: Heart notes
    - Base/base_notes: Base notes
    - Accords/accords: Accords with weights
    """

    # Column name mappings (lowercase)
    NAME_COLS = {"name", "perfume", "fragrance", "title"}
    BRAND_COLS = {"brand", "house", "designer", "company"}
    CONCENTRATION_COLS = {"concentration", "type", "strength"}
    YEAR_COLS = {"year", "launch_year", "release_year", "launched"}
    GENDER_COLS = {"gender", "for", "target", "sex"}
    FAMILY_COLS = {"family", "main_accords", "category", "type"}
    TOP_NOTES_COLS = {"top", "top_notes", "top notes", "opening"}
    HEART_NOTES_COLS = {"heart", "heart_notes", "heart notes", "middle", "middle_notes"}
    BASE_NOTES_COLS = {"base", "base_notes", "base notes", "dry_down", "drydown"}
    ACCORDS_COLS = {"accords", "accord", "notes", "scent_profile"}

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the importer with a database session.

        Args:
            session: Async database session.
        """
        self.session = session
        self._note_cache: dict[str, Note] = {}

    async def import_csv(
        self, file_path: Path | str, *, dry_run: bool = False
    ) -> ImportResult:
        """Import fragrances from a Kaggle CSV file.

        Args:
            file_path: Path to the CSV file.
            dry_run: If True, validate without writing to database.

        Returns:
            ImportResult with statistics and any errors.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return ImportResult(errors=[f"File not found: {file_path}"])

        result = ImportResult()

        try:
            with file_path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return ImportResult(errors=["CSV file is empty or has no headers"])

                # Map columns
                col_map = self._map_columns(list(reader.fieldnames))
                if not col_map.get("name") or not col_map.get("brand"):
                    return ImportResult(errors=["CSV must have name and brand columns"])

                for row_num, row in enumerate(reader, start=2):
                    result.total_rows += 1
                    try:
                        parsed = self._parse_row(row, col_map)
                        if parsed:
                            if not dry_run:
                                await self._save_fragrance(parsed)
                            result.imported += 1
                        else:
                            result.skipped += 1
                    except Exception as e:
                        result.errors.append(f"Row {row_num}: {e!s}")
                        result.skipped += 1

                if not dry_run:
                    await self.session.flush()

        except csv.Error as e:
            result.errors.append(f"CSV parsing error: {e!s}")

        return result

    def _map_columns(self, fieldnames: list[str]) -> dict[str, str]:
        """Map CSV columns to our expected fields.

        Args:
            fieldnames: List of column names from CSV.

        Returns:
            Dictionary mapping our field names to CSV column names.
        """
        col_map: dict[str, str] = {}
        lower_fields = {f.lower().strip(): f for f in fieldnames}

        mapping = [
            ("name", self.NAME_COLS),
            ("brand", self.BRAND_COLS),
            ("concentration", self.CONCENTRATION_COLS),
            ("year", self.YEAR_COLS),
            ("gender", self.GENDER_COLS),
            ("family", self.FAMILY_COLS),
            ("top_notes", self.TOP_NOTES_COLS),
            ("heart_notes", self.HEART_NOTES_COLS),
            ("base_notes", self.BASE_NOTES_COLS),
            ("accords", self.ACCORDS_COLS),
        ]

        for field_name, possible_cols in mapping:
            for col in possible_cols:
                if col in lower_fields:
                    col_map[field_name] = lower_fields[col]
                    break

        return col_map

    def _parse_row(
        self, row: dict[str, str], col_map: dict[str, str]
    ) -> ParsedFragrance | None:
        """Parse a CSV row into a ParsedFragrance.

        Args:
            row: CSV row as dictionary.
            col_map: Column name mapping.

        Returns:
            ParsedFragrance if valid, None if should be skipped.
        """
        name = row.get(col_map.get("name", ""), "").strip()
        brand = row.get(col_map.get("brand", ""), "").strip()

        if not name or not brand:
            return None

        # Parse year
        year_str = row.get(col_map.get("year", ""), "").strip()
        launch_year = None
        if year_str:
            try:
                launch_year = int(re.search(r"\d{4}", year_str).group())  # type: ignore[union-attr]
            except (ValueError, AttributeError):
                pass

        # Parse gender
        gender_raw = row.get(col_map.get("gender", ""), "").strip().lower()
        if "male" in gender_raw and "female" not in gender_raw:
            gender_target = "Masculine"
        elif "female" in gender_raw or "women" in gender_raw:
            gender_target = "Feminine"
        else:
            gender_target = "Unisex"

        # Parse concentration
        concentration = row.get(col_map.get("concentration", ""), "").strip()
        if not concentration:
            concentration = "EDP"  # Default

        # Parse family
        family = row.get(col_map.get("family", ""), "").strip()
        if not family:
            family = "Unknown"

        # Parse notes
        top_notes = self._parse_notes(row.get(col_map.get("top_notes", ""), ""))
        heart_notes = self._parse_notes(row.get(col_map.get("heart_notes", ""), ""))
        base_notes = self._parse_notes(row.get(col_map.get("base_notes", ""), ""))

        # Parse accords
        accords = self._parse_accords(row.get(col_map.get("accords", ""), ""))

        return ParsedFragrance(
            name=name,
            brand=brand,
            concentration=concentration,
            launch_year=launch_year,
            gender_target=gender_target,
            primary_family=family,
            subfamily=family,  # Use same as primary for now
            top_notes=top_notes,
            heart_notes=heart_notes,
            base_notes=base_notes,
            accords=accords,
        )

    def _parse_notes(self, notes_str: str) -> list[str]:
        """Parse a comma-separated notes string.

        Args:
            notes_str: Comma-separated notes.

        Returns:
            List of note names.
        """
        if not notes_str:
            return []
        return [n.strip() for n in notes_str.split(",") if n.strip()]

    def _parse_accords(self, accords_str: str) -> dict[str, float]:
        """Parse accords string into dictionary with weights.

        Args:
            accords_str: Accords string (comma-separated or with percentages).

        Returns:
            Dictionary mapping accord names to intensities (0-1).
        """
        if not accords_str:
            return {}

        accords: dict[str, float] = {}
        parts = accords_str.split(",")

        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            # Check for percentage pattern like "Citrus (45%)"
            match = re.match(r"(.+?)\s*\((\d+)%?\)", part)
            if match:
                name = match.group(1).strip()
                intensity = float(match.group(2)) / 100.0
            else:
                name = part
                # Assign decreasing weights based on position
                intensity = max(0.1, 1.0 - (i * 0.15))

            accords[name] = min(1.0, intensity)

        return accords

    async def _save_fragrance(self, parsed: ParsedFragrance) -> Fragrance:
        """Save a parsed fragrance to the database.

        Args:
            parsed: Parsed fragrance data.

        Returns:
            Created Fragrance instance.
        """
        fragrance = Fragrance(
            id=str(uuid4()),
            name=parsed.name,
            brand=parsed.brand,
            concentration=parsed.concentration,
            launch_year=parsed.launch_year,
            gender_target=parsed.gender_target,
            primary_family=parsed.primary_family,
            subfamily=parsed.subfamily,
            data_source="kaggle",
        )
        self.session.add(fragrance)

        # Add notes
        for note_name in parsed.top_notes:
            note = await self._get_or_create_note(note_name, "Top")
            fn = FragranceNote(
                fragrance_id=fragrance.id, note_id=note.id, position="top"
            )
            self.session.add(fn)

        for note_name in parsed.heart_notes:
            note = await self._get_or_create_note(note_name, "Heart")
            fn = FragranceNote(
                fragrance_id=fragrance.id, note_id=note.id, position="heart"
            )
            self.session.add(fn)

        for note_name in parsed.base_notes:
            note = await self._get_or_create_note(note_name, "Base")
            fn = FragranceNote(
                fragrance_id=fragrance.id, note_id=note.id, position="base"
            )
            self.session.add(fn)

        # Add accords
        for accord_type, intensity in parsed.accords.items():
            accord = FragranceAccord(
                fragrance_id=fragrance.id, accord_type=accord_type, intensity=intensity
            )
            self.session.add(accord)

        return fragrance

    async def _get_or_create_note(self, name: str, category: str) -> Note:
        """Get an existing note or create a new one.

        Args:
            name: Note name.
            category: Note category.

        Returns:
            Note instance.
        """
        # Check cache first
        cache_key = name.lower()
        if cache_key in self._note_cache:
            return self._note_cache[cache_key]

        # Query database
        from sqlalchemy import select

        stmt = select(Note).where(Note.name == name)
        result = await self.session.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            note = Note(id=str(uuid4()), name=name, category=category)
            self.session.add(note)
            await self.session.flush()

        self._note_cache[cache_key] = note
        return note

    def iter_csv_preview(
        self, file_path: Path | str, limit: int = 5
    ) -> Iterator[dict[str, str]]:
        """Preview rows from a CSV file.

        Args:
            file_path: Path to the CSV file.
            limit: Maximum rows to return.

        Yields:
            CSV rows as dictionaries.
        """
        file_path = Path(file_path)
        with file_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                yield row
