"""Kaggle CSV import service for fragrance data."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.core.vocabulary import GenderTarget

logger = logging.getLogger(__name__)


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
    gender_target: GenderTarget
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

    Args:
        session (AsyncSession): Async database session.

    Attributes:
        NAME_COLS (ClassVar[set[str]]): Column names holding the fragrance name.
        BRAND_COLS (ClassVar[set[str]]): Column names holding the brand.
        CONCENTRATION_COLS (ClassVar[set[str]]): Column names for concentration.
        YEAR_COLS (ClassVar[set[str]]): Column names for the launch year.
        GENDER_COLS (ClassVar[set[str]]): Column names for the gender target.
        FAMILY_COLS (ClassVar[set[str]]): Column names for the fragrance family.
        TOP_NOTES_COLS (ClassVar[set[str]]): Column names for top notes.
        HEART_NOTES_COLS (ClassVar[set[str]]): Column names for heart notes.
        BASE_NOTES_COLS (ClassVar[set[str]]): Column names for base notes.
        ACCORDS_COLS (ClassVar[set[str]]): Column names for accords.
    """

    # Column name mappings (lowercase)
    NAME_COLS: ClassVar[set[str]] = {"name", "perfume", "fragrance", "title"}
    BRAND_COLS: ClassVar[set[str]] = {"brand", "house", "designer", "company"}
    CONCENTRATION_COLS: ClassVar[set[str]] = {"concentration", "type", "strength"}
    YEAR_COLS: ClassVar[set[str]] = {
        "year",
        "launch_year",
        "release_year",
        "launched",
    }
    GENDER_COLS: ClassVar[set[str]] = {"gender", "for", "target", "sex"}
    FAMILY_COLS: ClassVar[set[str]] = {"family", "main_accords", "category", "type"}
    TOP_NOTES_COLS: ClassVar[set[str]] = {"top", "top_notes", "top notes", "opening"}
    HEART_NOTES_COLS: ClassVar[set[str]] = {
        "heart",
        "heart_notes",
        "heart notes",
        "middle",
        "middle_notes",
    }
    BASE_NOTES_COLS: ClassVar[set[str]] = {
        "base",
        "base_notes",
        "base notes",
        "dry_down",
        "drydown",
    }
    ACCORDS_COLS: ClassVar[set[str]] = {"accords", "accord", "notes", "scent_profile"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._note_cache: dict[str, Note] = {}

    async def import_csv(
        self, file_path: Path | str, *, dry_run: bool = False
    ) -> ImportResult:
        """Import fragrances from a Kaggle CSV file.

        Args:
            file_path (Path | str): Path to the CSV file.
            dry_run (bool): If True, validate without writing to database.

        Returns:
            ImportResult: ImportResult with statistics and any errors.
        """
        file_path = Path(file_path)
        try:
            # Read off the event loop; CSV files are small enough to hold in memory
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        except FileNotFoundError:
            return ImportResult(errors=[f"File not found: {file_path}"])

        result = ImportResult()

        try:
            reader = csv.DictReader(io.StringIO(content))
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
                    # One bad row must not abort the whole import; record and go on
                    logger.exception("Failed to import CSV row %d", row_num)
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
            fieldnames (list[str]): List of column names from CSV.

        Returns:
            dict[str, str]: Dictionary mapping our field names to CSV column names.
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
            row (dict[str, str]): CSV row as dictionary.
            col_map (dict[str, str]): Column name mapping.

        Returns:
            ParsedFragrance | None: ParsedFragrance if valid, None if should be skipped.
        """
        name = row.get(col_map.get("name", ""), "").strip()
        brand = row.get(col_map.get("brand", ""), "").strip()

        if not name or not brand:
            return None

        # Parse year
        year_str = row.get(col_map.get("year", ""), "").strip()
        launch_year = None
        year_match = re.search(r"\d{4}", year_str)
        if year_match:
            launch_year = int(year_match.group())

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
            notes_str (str): Comma-separated notes.

        Returns:
            list[str]: List of note names.
        """
        if not notes_str:
            return []
        return [n.strip() for n in notes_str.split(",") if n.strip()]

    def _parse_accords(self, accords_str: str) -> dict[str, float]:
        """Parse accords string into dictionary with weights.

        Args:
            accords_str (str): Accords string (comma-separated or with percentages).

        Returns:
            dict[str, float]: Dictionary mapping accord names to intensities (0-1).
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
            parsed (ParsedFragrance): Parsed fragrance data.

        Returns:
            Fragrance: Created Fragrance instance.
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

        # Add notes. A note legitimately appearing in more than one pyramid
        # position (e.g. musk in both heart and base) is valid data, not a
        # conflict (Critical finding 3); only an exact duplicate
        # (fragrance_id, note_id, position) triple is rejected, and that
        # rejection is isolated per-row below so it cannot abort the rest
        # of this fragrance's notes or the rest of the import.
        for position, category, note_names in (
            ("top", "Top", parsed.top_notes),
            ("heart", "Heart", parsed.heart_notes),
            ("base", "Base", parsed.base_notes),
        ):
            for note_name in note_names:
                note = await self._get_or_create_note(note_name, category)
                await self._add_fragrance_note(
                    fragrance.id, note.id, position, note_name
                )

        # Add accords
        for accord_type, intensity in parsed.accords.items():
            accord = FragranceAccord(
                fragrance_id=fragrance.id, accord_type=accord_type, intensity=intensity
            )
            self.session.add(accord)

        return fragrance

    # #CRITICAL: concurrency: a duplicate (fragrance_id, note_id, position)
    # triple - e.g. malformed source data listing the same note twice in
    # the same position - raises IntegrityError against the
    # UNIQUE(fragrance_id, note_id, position) constraint. Without per-row
    # isolation that error poisons the whole session (PendingRollbackError)
    # and aborts every row still to come in this import, not just the
    # offending one.
    # #VERIFY: session.begin_nested() opens a SAVEPOINT scoped to just this
    # insert; only that SAVEPOINT rolls back on conflict, so the outer
    # session (and the rest of this fragrance's notes) stays usable.
    # Covered by a regression test importing a note that legitimately
    # appears in two different positions (allowed) and by a same-position
    # duplicate (skipped, not fatal).
    async def _add_fragrance_note(
        self, fragrance_id: str, note_id: str, position: str, note_name: str
    ) -> None:
        """Insert one fragrance-note row, isolated in its own SAVEPOINT.

        Args:
            fragrance_id (str): Owning fragrance ID.
            note_id (str): Referenced note ID.
            position (str): Pyramid position (top, heart, base).
            note_name (str): Note name, for the warning log on conflict.
        """
        try:
            async with self.session.begin_nested():
                self.session.add(
                    FragranceNote(
                        fragrance_id=fragrance_id, note_id=note_id, position=position
                    )
                )
                await self.session.flush()
        except IntegrityError:
            logger.warning(
                "Skipping duplicate fragrance note: fragrance_id=%s note=%r position=%s",
                fragrance_id,
                note_name,
                position,
            )

    async def _get_or_create_note(self, name: str, category: str) -> Note:
        """Get an existing note or create a new one.

        Args:
            name (str): Note name.
            category (str): Note category.

        Returns:
            Note: Note instance.
        """
        # Check cache first
        cache_key = name.lower()
        if cache_key in self._note_cache:
            return self._note_cache[cache_key]

        # Query database
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
            file_path (Path | str): Path to the CSV file.
            limit (int): Maximum rows to return.

        Yields:
            dict[str, str]: CSV rows as dictionaries.
        """
        file_path = Path(file_path)
        with file_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                yield row
