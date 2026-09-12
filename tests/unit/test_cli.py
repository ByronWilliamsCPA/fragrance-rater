"""Tests for CLI commands."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from fragrance_rater.cli import CLIContext, cli, mask_database_url, run_async


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

    def test_config_output_never_leaks_password(self) -> None:
        """The config command must never print a raw password, regardless of
        how long the host/username portion of the configured URL is.
        """
        runner = CliRunner()
        with patch("fragrance_rater.cli.settings") as mock_settings:
            mock_settings.project_name = "Fragrance Rater"
            mock_settings.version = "0.1.0"
            mock_settings.log_level = "INFO"
            mock_settings.database_url = (
                "postgresql://fragrance_rater:super-secret-password"
                "@a-really-long-hostname.internal.example.com:5432/fragrance_rater"
            )
            result = runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        assert "super-secret-password" not in result.output
        assert "***" in result.output


class TestMaskDatabaseUrl:
    """Direct unit tests for the mask_database_url helper (Major finding 1)."""

    def test_masks_password_short_url(self) -> None:
        """A short URL (where a fixed-offset slice would have hidden the
        password anyway) must still mask it via structural parsing.
        """
        url = "postgresql://user:hunter2@db:5432/app"  # trufflehog:ignore
        masked = mask_database_url(url)
        assert "hunter2" not in masked
        assert "***" in masked
        assert "user" in masked
        assert "db:5432" in masked

    def test_masks_password_long_hostname(self) -> None:
        """A long host/user segment must not push the password past a
        would-be fixed-offset slice and leak it.
        """
        url = (
            "postgresql://fragrance_rater_service_account:hunter2"
            "@a-really-long-hostname.internal.example.com:5432/fragrance_rater"
        )
        masked = mask_database_url(url)
        assert "hunter2" not in masked
        assert "***" in masked

    def test_no_password_left_unchanged(self) -> None:
        """A URL with no embedded credentials is returned unchanged."""
        url = "sqlite+aiosqlite:///./app.db"
        assert mask_database_url(url) == url

    def test_no_userinfo_left_unchanged(self) -> None:
        """A URL with a host but no user info at all is unchanged."""
        url = "postgresql://db:5432/app"
        assert mask_database_url(url) == url

    def test_username_without_password_unchanged(self) -> None:
        """A username with no password segment has nothing to mask."""
        url = "postgresql://user@db:5432/app"
        assert mask_database_url(url) == url

    def test_malformed_url_returned_unchanged(self) -> None:
        """A string that isn't a parseable URL is returned as-is rather than
        raising, since there is nothing structured to mask.
        """
        url = "not a url at all ][{}"
        assert mask_database_url(url) == url


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

    @patch("fragrance_rater.cli.async_session_maker")
    def test_kaggle_import_success(self, mock_session_maker: MagicMock) -> None:
        """Should import CSV successfully."""
        import csv

        # Create temp CSV file
        import tempfile

        from fragrance_rater.services.kaggle_importer import ImportResult

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

            with patch("fragrance_rater.cli.KaggleImporter") as mock_importer_class:
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
            Path(temp_path).unlink()

    @patch("fragrance_rater.cli.async_session_maker")
    def test_kaggle_dry_run(self, mock_session_maker: MagicMock) -> None:
        """Should show dry run in output."""
        import csv
        import tempfile

        from fragrance_rater.services.kaggle_importer import ImportResult

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

            with patch("fragrance_rater.cli.KaggleImporter") as mock_importer_class:
                mock_importer = AsyncMock()
                mock_importer.import_csv.return_value = ImportResult(
                    total_rows=1, imported=1, skipped=0, errors=[]
                )
                mock_importer_class.return_value = mock_importer

                runner = CliRunner()
                result = runner.invoke(
                    cli, ["import-data", "kaggle", "--dry-run", temp_path]
                )

                assert result.exit_code == 0
                assert "[DRY RUN]" in result.output
        finally:
            Path(temp_path).unlink()


class TestSeedReviewersCommand:
    """Tests for seed-reviewers command."""

    @patch("fragrance_rater.cli.async_session_maker")
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

        with patch("fragrance_rater.cli.ReviewerService") as mock_service_class:
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

    @patch("fragrance_rater.cli.async_session_maker")
    def test_profile_not_found(self, mock_session_maker: MagicMock) -> None:
        """Should show error for unknown reviewer."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.cli.ReviewerService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_by_name.return_value = None
            mock_service_class.return_value = mock_service

            runner = CliRunner()
            result = runner.invoke(cli, ["profile", "Unknown"])

            assert result.exit_code == 1
            assert "not found" in result.output

    @patch("fragrance_rater.cli.async_session_maker")
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

        with patch("fragrance_rater.cli.ReviewerService") as mock_service_class:
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

    @patch("fragrance_rater.cli.async_session_maker")
    def test_parfumo_url_success(self, mock_session_maker: MagicMock) -> None:
        """Should import from Parfumo URL."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
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

    @patch("fragrance_rater.cli.async_session_maker")
    def test_parfumo_url_failure(self, mock_session_maker: MagicMock) -> None:
        """Should show error on import failure."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
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

    @patch("fragrance_rater.cli.async_session_maker")
    def test_parfumo_search_no_results(self, mock_session_maker: MagicMock) -> None:
        """Should show message when no results found."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper.search.return_value = []
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(
                cli, ["import-data", "parfumo-search", "nonexistent"]
            )

            assert result.exit_code == 0
            assert "No results found" in result.output

    @patch("fragrance_rater.cli.async_session_maker")
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
        mock_result.concentration = "Eau de Parfum"
        mock_result.year = 2010

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
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

    @patch("fragrance_rater.cli.async_session_maker")
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
        mock_result.concentration = "Eau de Parfum"
        mock_result.year = 2010

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
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
            assert "Importing result 1" in result.output
            assert "Imported with ID: fragrance-456" in result.output

    @patch("fragrance_rater.cli.async_session_maker")
    def test_parfumo_search_select(self, mock_session_maker: MagicMock) -> None:
        """Should import the chosen result with --select N."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # MagicMock's constructor `name=` kwarg sets the mock's own repr,
        # not an attribute, so `.name` is set explicitly afterward instead.
        first = MagicMock()
        first.name = "Aimez-Moi"
        first.brand = "Caron"
        first.url = "https://parfumo.com/aimez-moi-1996"
        first.concentration = "Eau de Toilette"
        first.year = 1996
        second = MagicMock()
        second.name = "Aimez-Moi"
        second.brand = "Caron"
        second.url = "https://parfumo.com/aimez-moi-comme-je-suis"
        second.concentration = None
        second.year = 2020

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper.search.return_value = [first, second]
            mock_scraper.import_from_url = AsyncMock(return_value="fragrance-789")
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["import-data", "parfumo-search", "Aimez-Moi Caron", "--select", "2"],
            )

            assert result.exit_code == 0
            assert "Multiple results share a name" in result.output
            assert "Importing result 2" in result.output
            assert "Imported with ID: fragrance-789" in result.output
            mock_scraper.import_from_url.assert_awaited_once_with(second.url)

    @patch("fragrance_rater.cli.async_session_maker")
    def test_parfumo_search_select_out_of_range(
        self, mock_session_maker: MagicMock
    ) -> None:
        """--select N outside 1..result_count must report the valid
        range and exit non-zero rather than importing the wrong result
        or raising an unhandled IndexError."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        first = MagicMock()
        first.name = "Aimez-Moi"
        first.brand = "Caron"
        first.url = "https://parfumo.com/aimez-moi-1996"
        first.concentration = "Eau de Toilette"
        first.year = 1996

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper.search.return_value = [first]
            mock_scraper.import_from_url = AsyncMock()
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["import-data", "parfumo-search", "Aimez-Moi Caron", "--select", "5"],
            )

            assert result.exit_code == 1
            assert "--select 5 is out of range (1-1)" in result.output
            mock_scraper.import_from_url.assert_not_awaited()

    @patch("fragrance_rater.cli.async_session_maker")
    def test_parfumo_search_import_first_refused_when_ambiguous(
        self, mock_session_maker: MagicMock
    ) -> None:
        """--import-first must refuse rather than silently pick a
        release when multiple results share a name (Critical finding:
        see docs/planning/evidence/
        baseline-v3.1-parfumo-source-resolution.md's Caron Aimez-Moi
        case, where an automated "first result" pick would have chosen
        an unrelated fragrance)."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        first = MagicMock()
        first.name = "Aimez-Moi"
        first.brand = "Caron"
        first.url = "https://parfumo.com/aimez-moi-1996"
        first.concentration = "Eau de Toilette"
        first.year = 1996
        second = MagicMock()
        second.name = "Aimez-Moi"
        second.brand = "Caron"
        second.url = "https://parfumo.com/aimez-moi-comme-je-suis"
        second.concentration = None
        second.year = 2020

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper.search.return_value = [first, second]
            mock_scraper.import_from_url = AsyncMock()
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["import-data", "parfumo-search", "Aimez-Moi Caron", "--import-first"],
            )

            assert result.exit_code == 1
            assert "Refusing --import-first" in result.output
            mock_scraper.import_from_url.assert_not_awaited()

    @patch("fragrance_rater.cli.async_session_maker")
    def test_parfumo_search_offloads_blocking_search_to_thread(
        self, mock_session_maker: MagicMock
    ) -> None:
        """Important finding: search() is a blocking sync call (httpx +
        time.sleep()-based rate limiting/backoff); do_search() must run it
        via asyncio.to_thread rather than calling it directly on the event
        loop. This mocks search() with a real blocking sleep and confirms
        the CLI command still completes end-to-end and produces correct
        output, i.e. the wrap doesn't change behavior or hang.
        """
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        mock_result = MagicMock()
        mock_result.name = "Aventus"
        mock_result.brand = "Creed"
        mock_result.url = "https://parfumo.com/aventus"
        mock_result.concentration = "Eau de Parfum"
        mock_result.year = 2010

        def blocking_search(query: str, limit: int = 10) -> list[MagicMock]:
            # Simulates the real search()'s blocking network call.
            time.sleep(0.05)
            return [mock_result]

        with patch("fragrance_rater.cli.ParfumoScraper") as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper.search = blocking_search
            mock_scraper.close = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            runner = CliRunner()
            result = runner.invoke(cli, ["import-data", "parfumo-search", "Aventus"])

            assert result.exit_code == 0
            assert "Found 1 result" in result.output
            assert "Aventus" in result.output


class TestImportFragellaLookupCommand:
    """Tests for import-data fragella-lookup - a reference-only lookup
    that never creates/updates a Fragrance record."""

    def test_no_results(self) -> None:
        with patch("fragrance_rater.cli.FragellaClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(return_value=[])
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli, ["import-data", "fragella-lookup", "Nonexistent Scent"]
            )

            assert result.exit_code == 0
            assert "No results found" in result.output

    def test_displays_results_without_importing(self) -> None:
        mock_result = MagicMock()
        mock_result.name = "Aimez-Moi"
        mock_result.brand = "Caron"
        mock_result.year = 1996
        mock_result.oil_type = "Eau de Toilette"
        mock_result.confidence = "medium"
        mock_result.general_notes = ["Violet", "Iris"]
        mock_result.top_notes = ["Violet"]
        mock_result.middle_notes = ["Iris"]
        mock_result.base_notes = ["Musk"]

        with patch("fragrance_rater.cli.FragellaClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(return_value=[mock_result])
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli, ["import-data", "fragella-lookup", "Aimez-Moi Caron"]
            )

            assert result.exit_code == 0
            assert "reference only, not imported" in result.output
            assert "Aimez-Moi" in result.output
            assert "Caron" in result.output
            assert "1996" in result.output

    def test_reports_a_fragella_error_and_exits_non_zero(self) -> None:
        from fragrance_rater.services.fragella_client import FragellaError

        with patch("fragrance_rater.cli.FragellaClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                side_effect=FragellaError("FRAGELLA_API_KEY is not configured")
            )
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(
                cli, ["import-data", "fragella-lookup", "Aimez-Moi Caron"]
            )

            assert result.exit_code == 1
            assert "Fragella lookup failed" in result.output


class TestImportFragellaUsageCommand:
    """Tests for import-data fragella-usage."""

    def test_prints_the_usage_body(self) -> None:
        with patch("fragrance_rater.cli.FragellaClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.usage = AsyncMock(
                return_value={"plan": "free", "usage": {"requests_remaining": 17}}
            )
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(cli, ["import-data", "fragella-usage"])

            assert result.exit_code == 0
            assert "requests_remaining" in result.output
            assert "17" in result.output

    def test_reports_failure_when_usage_is_unavailable(self) -> None:
        with patch("fragrance_rater.cli.FragellaClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.usage = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(cli, ["import-data", "fragella-usage"])

            assert result.exit_code == 1
            assert "Could not retrieve Fragella usage" in result.output
