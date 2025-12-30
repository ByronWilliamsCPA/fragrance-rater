"""Tests for CLI commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from fragrance_rater.cli import cli, CLIContext, run_async


class TestCLIContext:
    """Tests for CLIContext dataclass."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        ctx = CLIContext()
        assert ctx.debug is False

    def test_with_debug(self) -> None:
        """Should accept debug flag."""
        ctx = CLIContext(debug=True)
        assert ctx.debug is True


class TestRunAsync:
    """Tests for run_async helper."""

    def test_runs_coroutine(self) -> None:
        """Should run and return coroutine result."""
        async def my_coro() -> str:
            return "result"

        result = run_async(my_coro())
        assert result == "result"


class TestCLIMain:
    """Tests for main CLI group."""

    def test_version_option(self) -> None:
        """Should display version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_option(self) -> None:
        """Should display help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Fragrance Rater" in result.output

    def test_debug_flag(self) -> None:
        """Should enable debug mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--debug", "hello"])

        assert result.exit_code == 0


class TestHelloCommand:
    """Tests for hello command."""

    def test_hello_default(self) -> None:
        """Should greet World by default."""
        runner = CliRunner()
        result = runner.invoke(cli, ["hello"])

        assert result.exit_code == 0
        assert "Hello, World!" in result.output

    def test_hello_with_name(self) -> None:
        """Should greet specified name."""
        runner = CliRunner()
        result = runner.invoke(cli, ["hello", "--name", "Alice"])

        assert result.exit_code == 0
        assert "Hello, Alice!" in result.output

    def test_hello_with_short_option(self) -> None:
        """Should accept -n short option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["hello", "-n", "Bob"])

        assert result.exit_code == 0
        assert "Hello, Bob!" in result.output


class TestConfigCommand:
    """Tests for config command."""

    def test_displays_config(self) -> None:
        """Should display configuration."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        assert "Current Configuration:" in result.output
        assert "Project:" in result.output
        assert "Version:" in result.output


class TestImportDataGroup:
    """Tests for import-data command group."""

    def test_import_data_help(self) -> None:
        """Should display import-data help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["import-data", "--help"])

        assert result.exit_code == 0
        assert "Import fragrance data" in result.output


class TestImportKaggleCommand:
    """Tests for import-data kaggle command."""

    def test_kaggle_file_not_found(self) -> None:
        """Should fail for nonexistent file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["import-data", "kaggle", "/nonexistent/file.csv"])

        assert result.exit_code != 0

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_kaggle_import_success(self, mock_session_maker: MagicMock) -> None:
        """Should import CSV successfully."""
        from fragrance_rater.services.kaggle_importer import ImportResult

        # Create temp CSV file
        import tempfile
        import csv

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["name", "brand"])
            writer.writerow(["Test Fragrance", "Test Brand"])
            temp_path = f.name

        try:
            # Mock the session and importer
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_maker.return_value = mock_session

            with patch("fragrance_rater.services.kaggle_importer.KaggleImporter") as mock_importer_class:
                mock_importer = AsyncMock()
                mock_importer.import_csv.return_value = ImportResult(
                    total_rows=1,
                    imported=1,
                    skipped=0,
                    errors=[],
                )
                mock_importer_class.return_value = mock_importer

                runner = CliRunner()
                result = runner.invoke(cli, ["import-data", "kaggle", temp_path])

                assert result.exit_code == 0
                assert "Imported:   1" in result.output
        finally:
            import os
            os.unlink(temp_path)

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_kaggle_dry_run(self, mock_session_maker: MagicMock) -> None:
        """Should show dry run in output."""
        from fragrance_rater.services.kaggle_importer import ImportResult

        import tempfile
        import csv

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["name", "brand"])
            writer.writerow(["Test", "Brand"])
            temp_path = f.name

        try:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_maker.return_value = mock_session

            with patch("fragrance_rater.services.kaggle_importer.KaggleImporter") as mock_importer_class:
                mock_importer = AsyncMock()
                mock_importer.import_csv.return_value = ImportResult(
                    total_rows=1, imported=1, skipped=0, errors=[]
                )
                mock_importer_class.return_value = mock_importer

                runner = CliRunner()
                result = runner.invoke(cli, ["import-data", "kaggle", "--dry-run", temp_path])

                assert result.exit_code == 0
                assert "[DRY RUN]" in result.output
        finally:
            import os
            os.unlink(temp_path)


class TestSeedReviewersCommand:
    """Tests for seed-reviewers command."""

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_seed_reviewers_success(self, mock_session_maker: MagicMock) -> None:
        """Should seed reviewers successfully."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # Create mock reviewers
        mock_reviewer = MagicMock()
        mock_reviewer.name = "Byron"
        mock_reviewer.id = "123"

        with patch("fragrance_rater.services.reviewer_service.ReviewerService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.seed_default_reviewers.return_value = [mock_reviewer]
            mock_service_class.return_value = mock_service

            runner = CliRunner()
            result = runner.invoke(cli, ["seed-reviewers"])

            assert result.exit_code == 0
            assert "Created/verified reviewers:" in result.output
            assert "Byron" in result.output


class TestProfileCommand:
    """Tests for profile command."""

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_profile_not_found(self, mock_session_maker: MagicMock) -> None:
        """Should show error for unknown reviewer."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.services.reviewer_service.ReviewerService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_by_name.return_value = None
            mock_service_class.return_value = mock_service

            runner = CliRunner()
            result = runner.invoke(cli, ["profile", "Unknown"])

            assert result.exit_code == 1
            assert "not found" in result.output

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_profile_success(self, mock_session_maker: MagicMock) -> None:
        """Should display reviewer profile."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # Create mock reviewer with evaluations
        mock_evaluation = MagicMock()
        mock_evaluation.rating = 4

        mock_reviewer = MagicMock()
        mock_reviewer.name = "Byron"
        mock_reviewer.id = "123"
        mock_reviewer.created_at = "2024-01-01"
        mock_reviewer.evaluations = [mock_evaluation]

        with patch("fragrance_rater.services.reviewer_service.ReviewerService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_by_name.return_value = mock_reviewer
            mock_service_class.return_value = mock_service

            runner = CliRunner()
            result = runner.invoke(cli, ["profile", "Byron"])

            assert result.exit_code == 0
            assert "Profile: Byron" in result.output
            assert "Evaluations: 1" in result.output
            assert "Average Rating:" in result.output


class TestImportParfumoUrlCommand:
    """Tests for import-data parfumo-url command."""

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_parfumo_url_success(self, mock_session_maker: MagicMock) -> None:
        """Should import from Parfumo URL."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.services.parfumo_scraper.ParfumoScraper") as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.import_from_url.return_value = "fragrance-123"
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["import-data", "parfumo-url", "https://parfumo.com/test"],
            )

            assert result.exit_code == 0
            assert "Imported fragrance with ID: fragrance-123" in result.output

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_parfumo_url_failure(self, mock_session_maker: MagicMock) -> None:
        """Should show error on import failure."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.services.parfumo_scraper.ParfumoScraper") as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.import_from_url.return_value = None
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["import-data", "parfumo-url", "https://parfumo.com/invalid"],
            )

            assert result.exit_code == 1
            assert "Failed to import" in result.output


class TestImportParfumoSearchCommand:
    """Tests for import-data parfumo-search command."""

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_parfumo_search_no_results(self, mock_session_maker: MagicMock) -> None:
        """Should show message when no results found."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.services.parfumo_scraper.ParfumoScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper.search.return_value = []
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(cli, ["import-data", "parfumo-search", "nonexistent"])

            assert result.exit_code == 0
            assert "No results found" in result.output

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_parfumo_search_with_results(self, mock_session_maker: MagicMock) -> None:
        """Should display search results."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # Create mock search results
        mock_result = MagicMock()
        mock_result.name = "Aventus"
        mock_result.brand = "Creed"
        mock_result.url = "https://parfumo.com/aventus"

        with patch("fragrance_rater.services.parfumo_scraper.ParfumoScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper.search.return_value = [mock_result]
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(cli, ["import-data", "parfumo-search", "Aventus"])

            assert result.exit_code == 0
            assert "Found 1 result" in result.output
            assert "Aventus" in result.output
            assert "Creed" in result.output

    @patch("fragrance_rater.core.database.async_session_maker")
    def test_parfumo_search_import_first(self, mock_session_maker: MagicMock) -> None:
        """Should import first result with --import-first."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_result = MagicMock()
        mock_result.name = "Aventus"
        mock_result.brand = "Creed"
        mock_result.url = "https://parfumo.com/aventus"

        with patch("fragrance_rater.services.parfumo_scraper.ParfumoScraper") as mock_scraper_class:
            # Use MagicMock for sync methods, AsyncMock for async
            mock_scraper = MagicMock()
            mock_scraper.search.return_value = [mock_result]
            mock_scraper.import_from_url = AsyncMock(return_value="fragrance-456")
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["import-data", "parfumo-search", "Aventus", "--import-first"],
            )

            assert result.exit_code == 0
            assert "Importing first result" in result.output
            assert "Imported with ID: fragrance-456" in result.output
