"""Tests for Kaggle CSV import service."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from fragrance_rater.models.fragrance import Fragrance, FragranceNote
from fragrance_rater.services.kaggle_importer import (
    ImportResult,
    KaggleImporter,
    ParsedFragrance,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _write_csv(tmp_path: Path, rows: list[list[str]]) -> Path:
    """Write rows to a CSV file under tmp_path and return its path."""
    csv_path = tmp_path / "fragrances.csv"
    with csv_path.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    return csv_path


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        result = ImportResult()

        assert result.total_rows == 0
        assert result.imported == 0
        assert result.skipped == 0
        assert result.errors == []

    def test_with_values(self) -> None:
        """Should accept custom values."""
        result = ImportResult(
            total_rows=100,
            imported=90,
            skipped=10,
            errors=["Error 1", "Error 2"],
        )

        assert result.total_rows == 100
        assert result.imported == 90
        assert result.skipped == 10
        assert len(result.errors) == 2


class TestParsedFragrance:
    """Tests for ParsedFragrance dataclass."""

    def test_creation(self) -> None:
        """Should create with all fields."""
        fragrance = ParsedFragrance(
            name="Aventus",
            brand="Creed",
            concentration="EDP",
            launch_year=2010,
            gender_target="Masculine",
            primary_family="Woody",
            subfamily="Woody Aromatic",
            top_notes=["Bergamot", "Apple"],
            heart_notes=["Jasmine", "Rose"],
            base_notes=["Musk", "Oakmoss"],
            accords={"Woody": 0.8, "Fresh": 0.6},
        )

        assert fragrance.name == "Aventus"
        assert fragrance.brand == "Creed"
        assert fragrance.launch_year == 2010
        assert len(fragrance.top_notes) == 2
        assert fragrance.accords["Woody"] == 0.8


class TestKaggleImporterColumnMapping:
    """Tests for column name mapping."""

    @pytest_asyncio.fixture
    async def session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    def test_maps_standard_columns(self, session: AsyncMock) -> None:
        """Should map standard column names."""
        importer = KaggleImporter(session)

        fieldnames = ["name", "brand", "concentration", "year", "gender"]
        col_map = importer._map_columns(fieldnames)

        assert col_map["name"] == "name"
        assert col_map["brand"] == "brand"
        assert col_map["concentration"] == "concentration"
        assert col_map["year"] == "year"
        assert col_map["gender"] == "gender"

    def test_maps_alternative_columns(self, session: AsyncMock) -> None:
        """Should map alternative column names."""
        importer = KaggleImporter(session)

        fieldnames = ["perfume", "house", "type", "launch_year", "for"]
        col_map = importer._map_columns(fieldnames)

        assert col_map["name"] == "perfume"
        assert col_map["brand"] == "house"
        assert col_map["concentration"] == "type"
        assert col_map["year"] == "launch_year"
        assert col_map["gender"] == "for"

    def test_handles_case_insensitive(self, session: AsyncMock) -> None:
        """Should handle case insensitive matching."""
        importer = KaggleImporter(session)

        fieldnames = ["NAME", "Brand", "CONCENTRATION"]
        col_map = importer._map_columns(fieldnames)

        assert col_map["name"] == "NAME"
        assert col_map["brand"] == "Brand"
        assert col_map["concentration"] == "CONCENTRATION"


class TestKaggleImporterParsing:
    """Tests for row parsing."""

    @pytest_asyncio.fixture
    async def session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    def test_parse_complete_row(self, session: AsyncMock) -> None:
        """Should parse a complete row."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand", "year": "year", "gender": "gender"}

        row = {
            "name": "Aventus",
            "brand": "Creed",
            "year": "2010",
            "gender": "male",
        }

        result = importer._parse_row(row, col_map)

        assert result is not None
        assert result.name == "Aventus"
        assert result.brand == "Creed"
        assert result.launch_year == 2010
        assert result.gender_target == "Masculine"

    def test_parse_row_missing_name(self, session: AsyncMock) -> None:
        """Should return None for missing name."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand"}

        row = {"name": "", "brand": "Creed"}

        result = importer._parse_row(row, col_map)

        assert result is None

    def test_parse_row_missing_brand(self, session: AsyncMock) -> None:
        """Should return None for missing brand."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand"}

        row = {"name": "Aventus", "brand": ""}

        result = importer._parse_row(row, col_map)

        assert result is None

    def test_parse_gender_masculine(self, session: AsyncMock) -> None:
        """Should parse masculine gender."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand", "gender": "gender"}

        row = {"name": "Test", "brand": "Brand", "gender": "male"}
        result = importer._parse_row(row, col_map)

        assert result is not None
        assert result.gender_target == "Masculine"

    def test_parse_gender_feminine(self, session: AsyncMock) -> None:
        """Should parse feminine gender."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand", "gender": "gender"}

        row = {"name": "Test", "brand": "Brand", "gender": "women"}
        result = importer._parse_row(row, col_map)

        assert result is not None
        assert result.gender_target == "Feminine"

    def test_parse_gender_unisex(self, session: AsyncMock) -> None:
        """Should default to unisex."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand", "gender": "gender"}

        row = {"name": "Test", "brand": "Brand", "gender": "unisex"}
        result = importer._parse_row(row, col_map)

        assert result is not None
        assert result.gender_target == "Unisex"

    def test_parse_year_from_text(self, session: AsyncMock) -> None:
        """Should extract year from text."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand", "year": "year"}

        row = {"name": "Test", "brand": "Brand", "year": "Launched in 2015"}
        result = importer._parse_row(row, col_map)

        assert result is not None
        assert result.launch_year == 2015

    def test_parse_invalid_year(self, session: AsyncMock) -> None:
        """Should handle invalid year gracefully."""
        importer = KaggleImporter(session)
        col_map = {"name": "name", "brand": "brand", "year": "year"}

        row = {"name": "Test", "brand": "Brand", "year": "unknown"}
        result = importer._parse_row(row, col_map)

        assert result is not None
        assert result.launch_year is None


class TestKaggleImporterNotesParsing:
    """Tests for notes parsing."""

    @pytest_asyncio.fixture
    async def session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    def test_parse_notes_comma_separated(self, session: AsyncMock) -> None:
        """Should parse comma-separated notes."""
        importer = KaggleImporter(session)

        notes = importer._parse_notes("Bergamot, Apple, Pineapple")

        assert len(notes) == 3
        assert "Bergamot" in notes
        assert "Apple" in notes
        assert "Pineapple" in notes

    def test_parse_notes_with_spaces(self, session: AsyncMock) -> None:
        """Should trim whitespace from notes."""
        importer = KaggleImporter(session)

        notes = importer._parse_notes("  Bergamot  ,   Apple  ")

        assert len(notes) == 2
        assert notes[0] == "Bergamot"
        assert notes[1] == "Apple"

    def test_parse_notes_empty(self, session: AsyncMock) -> None:
        """Should return empty list for empty string."""
        importer = KaggleImporter(session)

        notes = importer._parse_notes("")

        assert notes == []

    def test_parse_notes_filters_empty(self, session: AsyncMock) -> None:
        """Should filter out empty entries."""
        importer = KaggleImporter(session)

        notes = importer._parse_notes("Bergamot,,Apple,,,")

        assert len(notes) == 2


class TestKaggleImporterAccordsParsing:
    """Tests for accords parsing."""

    @pytest_asyncio.fixture
    async def session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    def test_parse_accords_with_percentages(self, session: AsyncMock) -> None:
        """Should parse accords with percentages."""
        importer = KaggleImporter(session)

        accords = importer._parse_accords("Citrus (45%), Woody (30%)")

        assert len(accords) == 2
        assert accords["Citrus"] == 0.45
        assert accords["Woody"] == 0.30

    def test_parse_accords_without_percentages(self, session: AsyncMock) -> None:
        """Should assign decreasing weights without percentages."""
        importer = KaggleImporter(session)

        accords = importer._parse_accords("Citrus, Woody, Fresh")

        assert len(accords) == 3
        assert accords["Citrus"] == 1.0  # First
        assert accords["Woody"] == 0.85  # Second
        assert accords["Fresh"] == 0.70  # Third

    def test_parse_accords_empty(self, session: AsyncMock) -> None:
        """Should return empty dict for empty string."""
        importer = KaggleImporter(session)

        accords = importer._parse_accords("")

        assert accords == {}

    def test_parse_accords_caps_at_one(self, session: AsyncMock) -> None:
        """Should cap intensity at 1.0."""
        importer = KaggleImporter(session)

        accords = importer._parse_accords("Citrus (150%)")

        assert accords["Citrus"] == 1.0


class TestKaggleImporterCSVImport:
    """Tests for CSV file import."""

    @pytest_asyncio.fixture
    async def session(self) -> AsyncMock:
        """Create a mock database session."""
        mock = AsyncMock()
        mock.flush = AsyncMock()
        mock.add = MagicMock()
        return mock

    @pytest.mark.asyncio
    async def test_import_file_not_found(self, session: AsyncMock) -> None:
        """Should return error for missing file."""
        importer = KaggleImporter(session)

        result = await importer.import_csv("/nonexistent/file.csv")

        assert len(result.errors) == 1
        assert "not found" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def test_import_empty_file(self, session: AsyncMock, tmp_path: Path) -> None:
        """Should handle empty CSV file."""
        csv_path = _write_csv(tmp_path, [])

        importer = KaggleImporter(session)
        result = await importer.import_csv(csv_path)

        assert len(result.errors) == 1
        assert (
            "empty" in result.errors[0].lower() or "headers" in result.errors[0].lower()
        )

    @pytest.mark.asyncio
    async def test_import_missing_required_columns(
        self, session: AsyncMock, tmp_path: Path
    ) -> None:
        """Should return error when missing name/brand columns."""
        csv_path = _write_csv(tmp_path, [["color", "size"], ["red", "large"]])

        importer = KaggleImporter(session)
        result = await importer.import_csv(csv_path)

        assert len(result.errors) == 1
        assert "name" in result.errors[0].lower() or "brand" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def test_import_valid_csv_dry_run(
        self, session: AsyncMock, tmp_path: Path
    ) -> None:
        """Should process CSV in dry run mode without saving."""
        csv_path = _write_csv(
            tmp_path,
            [
                ["name", "brand", "year", "gender"],
                ["Aventus", "Creed", "2010", "male"],
                ["Sauvage", "Dior", "2015", "male"],
            ],
        )

        importer = KaggleImporter(session)
        result = await importer.import_csv(csv_path, dry_run=True)

        assert result.total_rows == 2
        assert result.imported == 2
        assert result.skipped == 0
        assert result.errors == []
        session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_skips_invalid_rows(
        self, session: AsyncMock, tmp_path: Path
    ) -> None:
        """Should skip rows with missing required fields."""
        csv_path = _write_csv(
            tmp_path,
            [
                ["name", "brand"],
                ["Aventus", "Creed"],  # Valid
                ["", "Dior"],  # Missing name
                ["Sauvage", ""],  # Missing brand
            ],
        )

        importer = KaggleImporter(session)
        result = await importer.import_csv(csv_path, dry_run=True)

        assert result.total_rows == 3
        assert result.imported == 1
        assert result.skipped == 2


class TestKaggleImporterPreview:
    """Tests for CSV preview functionality."""

    @pytest_asyncio.fixture
    async def session(self) -> AsyncMock:
        """Create a mock database session."""
        return AsyncMock()

    def test_preview_returns_limited_rows(self, session: AsyncMock) -> None:
        """Should return only requested number of rows."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["name", "brand"])
            for i in range(10):
                writer.writerow([f"Fragrance{i}", f"Brand{i}"])
            temp_path = f.name

        try:
            importer = KaggleImporter(session)
            rows = list(importer.iter_csv_preview(temp_path, limit=3))

            assert len(rows) == 3
            assert rows[0]["name"] == "Fragrance0"
            assert rows[2]["name"] == "Fragrance2"
        finally:
            Path(temp_path).unlink()

    def test_preview_returns_all_if_less_than_limit(self, session: AsyncMock) -> None:
        """Should return all rows if fewer than limit."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["name", "brand"])
            writer.writerow(["Aventus", "Creed"])
            writer.writerow(["Sauvage", "Dior"])
            temp_path = f.name

        try:
            importer = KaggleImporter(session)
            rows = list(importer.iter_csv_preview(temp_path, limit=10))

            assert len(rows) == 2
        finally:
            Path(temp_path).unlink()


class TestKaggleImporterSavepointIsolation:
    """Regression tests for Critical finding 3.

    Uses a real (in-memory SQLite) session rather than a mock, since the
    behavior under test is the actual UNIQUE(fragrance_id, note_id,
    position) constraint and the SAVEPOINT that isolates a conflicting
    row from the rest of the import.
    """

    @pytest.mark.asyncio
    async def test_note_in_two_positions_is_not_a_conflict(
        self, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        """A note legitimately appearing in two pyramid positions (e.g.
        musk in both heart and base) must not crash the import, and both
        position rows must be saved: this is the exact scenario that
        crashed under the old (fragrance_id, note_id) composite PK.
        """
        csv_path = _write_csv(
            tmp_path,
            [
                ["name", "brand", "heart", "base"],
                ["Two Position Musk", "Test Brand", "Musk", "Musk"],
            ],
        )

        importer = KaggleImporter(async_session)
        result = await importer.import_csv(csv_path)

        assert result.errors == []
        assert result.imported == 1

        frag_stmt = select(Fragrance).where(Fragrance.name == "Two Position Musk")
        fragrance = (await async_session.execute(frag_stmt)).scalar_one()

        fn_stmt = select(FragranceNote).where(
            FragranceNote.fragrance_id == fragrance.id
        )
        fragrance_notes = (await async_session.execute(fn_stmt)).scalars().all()
        positions = sorted(fn.position for fn in fragrance_notes)
        assert positions == ["base", "heart"]
        # Each row has its own surrogate id (Critical finding 3's fix), not
        # a shared composite key.
        assert len({fn.id for fn in fragrance_notes}) == 2

    @pytest.mark.asyncio
    async def test_true_duplicate_position_is_skipped_not_fatal(
        self, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        """A genuine duplicate - the same note listed twice in the same
        position - hits the UNIQUE(fragrance_id, note_id, position)
        constraint. The per-row SAVEPOINT must absorb that IntegrityError
        so the row is skipped rather than poisoning the whole import
        session (PendingRollbackError).
        """
        csv_path = _write_csv(
            tmp_path,
            [
                ["name", "brand", "top"],
                ["Duplicate Top Note", "Test Brand", "Bergamot, Bergamot"],
            ],
        )

        importer = KaggleImporter(async_session)
        result = await importer.import_csv(csv_path)

        assert result.errors == []
        assert result.imported == 1

        frag_stmt = select(Fragrance).where(Fragrance.name == "Duplicate Top Note")
        fragrance = (await async_session.execute(frag_stmt)).scalar_one()

        fn_stmt = select(FragranceNote).where(
            FragranceNote.fragrance_id == fragrance.id
        )
        fragrance_notes = (await async_session.execute(fn_stmt)).scalars().all()
        # Only one row survives; the duplicate insert was caught and
        # skipped by the per-row SAVEPOINT, not left to abort the import.
        assert len(fragrance_notes) == 1
        assert fragrance_notes[0].position == "top"

    @pytest.mark.asyncio
    async def test_conflicting_row_does_not_poison_later_rows(
        self, async_session: AsyncSession, tmp_path: Path
    ) -> None:
        """A conflicting row in one fragrance must not abort a later,
        unrelated fragrance in the same import batch.
        """
        csv_path = _write_csv(
            tmp_path,
            [
                ["name", "brand", "top"],
                ["Duplicate Top Note Two", "Test Brand", "Bergamot, Bergamot"],
                ["Clean Fragrance", "Test Brand", "Lemon"],
            ],
        )

        importer = KaggleImporter(async_session)
        result = await importer.import_csv(csv_path)

        assert result.errors == []
        assert result.imported == 2

        frag_stmt = select(Fragrance).where(Fragrance.name == "Clean Fragrance")
        fragrance = (await async_session.execute(frag_stmt)).scalar_one_or_none()
        assert fragrance is not None
