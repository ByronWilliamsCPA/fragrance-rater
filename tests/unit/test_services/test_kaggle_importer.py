"""Tests for Kaggle CSV import service."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from fragrance_rater.services.kaggle_importer import (
    ImportResult,
    KaggleImporter,
    ParsedFragrance,
)


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
    async def test_import_empty_file(self, session: AsyncMock) -> None:
        """Should handle empty CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            importer = KaggleImporter(session)
            result = await importer.import_csv(temp_path)

            assert len(result.errors) == 1
            assert "empty" in result.errors[0].lower() or "headers" in result.errors[0].lower()
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_import_missing_required_columns(self, session: AsyncMock) -> None:
        """Should return error when missing name/brand columns."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["color", "size"])
            writer.writerow(["red", "large"])
            temp_path = f.name

        try:
            importer = KaggleImporter(session)
            result = await importer.import_csv(temp_path)

            assert len(result.errors) == 1
            assert "name" in result.errors[0].lower() or "brand" in result.errors[0].lower()
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_import_valid_csv_dry_run(self, session: AsyncMock) -> None:
        """Should process CSV in dry run mode without saving."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["name", "brand", "year", "gender"])
            writer.writerow(["Aventus", "Creed", "2010", "male"])
            writer.writerow(["Sauvage", "Dior", "2015", "male"])
            temp_path = f.name

        try:
            importer = KaggleImporter(session)
            result = await importer.import_csv(temp_path, dry_run=True)

            assert result.total_rows == 2
            assert result.imported == 2
            assert result.skipped == 0
            assert result.errors == []
            session.flush.assert_not_called()
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_import_skips_invalid_rows(self, session: AsyncMock) -> None:
        """Should skip rows with missing required fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["name", "brand"])
            writer.writerow(["Aventus", "Creed"])  # Valid
            writer.writerow(["", "Dior"])  # Missing name
            writer.writerow(["Sauvage", ""])  # Missing brand
            temp_path = f.name

        try:
            importer = KaggleImporter(session)
            result = await importer.import_csv(temp_path, dry_run=True)

            assert result.total_rows == 3
            assert result.imported == 1
            assert result.skipped == 2
        finally:
            Path(temp_path).unlink()


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
