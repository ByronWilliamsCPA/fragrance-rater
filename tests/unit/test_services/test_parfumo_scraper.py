"""Unit tests for ParfumoScraper.

Tests the Parfumo.com web scraping functionality with mocked HTTP responses.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from fragrance_rater.core.vocabulary import GENDER_TARGETS
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.services.parfumo_scraper import (
    ParfumoScraper,
    ScrapedFragrance,
    SearchResult,
)

# Sample HTML for testing
SAMPLE_PERFUME_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head><title>Test Fragrance by Test Brand » Parfumo</title></head>
<body>
    <h1 class="p_name_h1">
        Test Fragrance
        <span class="p_brand_name nobold">Test Brand2024</span>
    </h1>

    <div class="pyramid_block nb_t w-100 mt-2">
        <span class="pointer">Bergamot</span>
        <span class="pointer">Lemon</span>
    </div>

    <div class="pyramid_block nb_m w-100 mt-2">
        <span class="pointer">Jasmine</span>
        <span class="pointer">Rose</span>
    </div>

    <div class="pyramid_block nb_b w-100 mt-2">
        <span class="pointer">Musk</span>
        <span class="pointer">Sandalwood</span>
    </div>

    <div class="barfiller_element rating-details pointer">
        Scent8.55 Ratings
    </div>

    <p>A fragrance for women and men released in 2024.</p>
</body>
</html>
"""

SAMPLE_SEARCH_RESULTS = """
<!DOCTYPE html>
<html lang="en">
<head><title>Search Results - Parfumo</title></head>
<body>
    <div class="search-results">
        <a href="/Perfumes/creed/aventus">Aventus by Creed</a>
        <a href="/Perfumes/creed/green-irish-tweed">Green Irish Tweed by Creed</a>
        <a href="/Perfumes/montale/intense-cafe">Intense Cafe by Montale</a>
    </div>
</body>
</html>
"""


class TestScrapedFragrance:
    """Tests for ScrapedFragrance dataclass."""

    def test_creation(self):
        """Test ScrapedFragrance creation."""
        scraped = ScrapedFragrance(
            url="https://parfumo.com/Perfumes/test/test",
            name="Test Fragrance",
            brand="Test Brand",
        )
        assert scraped.name == "Test Fragrance"
        assert scraped.top_notes == []
        assert scraped.accords == {}

    def test_with_notes(self):
        """Test ScrapedFragrance with notes."""
        scraped = ScrapedFragrance(
            url="https://parfumo.com/Perfumes/test/test",
            name="Test",
            brand="Brand",
            top_notes=["Bergamot", "Lemon"],
            heart_notes=["Rose"],
            base_notes=["Musk"],
        )
        assert len(scraped.top_notes) == 2
        assert "Rose" in scraped.heart_notes


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_creation(self):
        """Test SearchResult creation."""
        result = SearchResult(
            name="Aventus",
            brand="Creed",
            url="https://parfumo.com/Perfumes/creed/aventus",
        )
        assert result.name == "Aventus"
        assert result.year is None


class TestParfumoScraperParsing:
    """Tests for ParfumoScraper parsing logic."""

    def test_parse_name_from_html(self):
        """Test parsing fragrance name from HTML."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        # Mock the request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_PERFUME_PAGE

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = scraper.scrape_perfume_page(
                "https://parfumo.com/Perfumes/test/test"
            )

        assert result is not None
        assert result.name == "Test Fragrance"

    def test_parse_brand_from_html(self):
        """Test parsing brand from HTML (removes year suffix)."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_PERFUME_PAGE

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = scraper.scrape_perfume_page(
                "https://parfumo.com/Perfumes/test/test"
            )

        assert result is not None
        # Brand should have year removed
        assert result.brand == "Test Brand"
        assert "2024" not in result.brand

    def test_parse_notes_from_html(self):
        """Test parsing notes from pyramid blocks."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_PERFUME_PAGE

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = scraper.scrape_perfume_page(
                "https://parfumo.com/Perfumes/test/test"
            )

        assert result is not None
        assert "Bergamot" in result.top_notes
        assert "Lemon" in result.top_notes
        assert "Jasmine" in result.heart_notes
        assert "Rose" in result.heart_notes
        assert "Musk" in result.base_notes
        assert "Sandalwood" in result.base_notes

    def test_parse_rating_from_html(self):
        """Test parsing rating from HTML."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_PERFUME_PAGE

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = scraper.scrape_perfume_page(
                "https://parfumo.com/Perfumes/test/test"
            )

        assert result is not None
        assert result.rating == pytest.approx(8.55)

    def test_parse_gender_unisex(self):
        """Test parsing unisex gender."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_PERFUME_PAGE

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = scraper.scrape_perfume_page(
                "https://parfumo.com/Perfumes/test/test"
            )

        assert result is not None
        assert result.gender == "unisex"

    def test_handle_http_error(self):
        """Test handling HTTP errors gracefully."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = scraper.scrape_perfume_page(
                "https://parfumo.com/Perfumes/test/nonexistent"
            )

        assert result is None


class TestParfumoScraperSearch:
    """Tests for ParfumoScraper search functionality."""

    def test_search_returns_results(self):
        """Test that search returns parsed results."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_SEARCH_RESULTS

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            results = scraper.search("Aventus", limit=10)

        assert len(results) > 0
        urls = [r.url for r in results]
        assert any("aventus" in url for url in urls)

    def test_search_respects_limit(self):
        """Test that search respects the limit parameter."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_SEARCH_RESULTS

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            results = scraper.search("test", limit=1)

        assert len(results) <= 1

    def test_search_handles_no_results(self):
        """Test search handles empty results."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0
        scraper._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No results</body></html>"

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            results = scraper.search("xyznonexistent123")

        assert len(results) == 0


class TestParfumoScraperHelpers:
    """Tests for helper methods."""

    def test_infer_family_woody(self):
        """Test inferring woody family."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)

        scraped = ScrapedFragrance(
            url="test",
            name="Test",
            brand="Brand",
            base_notes=["Cedar", "Sandalwood"],
        )

        family = scraper._infer_family(scraped)
        assert family == "woody"

    def test_infer_family_floral(self):
        """Test inferring floral family."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)

        scraped = ScrapedFragrance(
            url="test",
            name="Test",
            brand="Brand",
            heart_notes=["Rose", "Jasmine"],
        )

        family = scraper._infer_family(scraped)
        assert family == "floral"

    def test_infer_family_fresh(self):
        """Test inferring fresh family from citrus."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)

        scraped = ScrapedFragrance(
            url="test",
            name="Test",
            brand="Brand",
            top_notes=["Bergamot", "Lemon", "Grapefruit"],
        )

        family = scraper._infer_family(scraped)
        assert family == "fresh"

    def test_categorize_note_citrus(self):
        """Test categorizing citrus notes."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)

        assert scraper._categorize_note("Bergamot") == "citrus"
        assert scraper._categorize_note("Lemon") == "citrus"
        assert scraper._categorize_note("Orange") == "citrus"

    def test_categorize_note_floral(self):
        """Test categorizing floral notes."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)

        assert scraper._categorize_note("Rose") == "floral"
        assert scraper._categorize_note("Jasmine") == "floral"

    def test_categorize_note_woody(self):
        """Test categorizing woody notes."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)

        assert scraper._categorize_note("Cedar") == "woody"
        assert scraper._categorize_note("Sandalwood") == "woody"

    def test_categorize_note_unknown(self):
        """Test categorizing unknown notes."""
        scraper = ParfumoScraper.__new__(ParfumoScraper)

        assert scraper._categorize_note("Something Random") == "other"


class TestParfumoScraperRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_delay(self):
        """Test that rate limiting applies delay."""
        import time

        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = time.time()
        scraper._client = None

        # Override delay for testing
        original_delay = ParfumoScraper.REQUEST_DELAY
        ParfumoScraper.REQUEST_DELAY = 0.1  # 100ms for testing

        try:
            start = time.time()
            scraper._wait_for_rate_limit()
            elapsed = time.time() - start

            # Should have waited approximately 0.1 seconds
            assert elapsed >= 0.05  # Allow some tolerance
        finally:
            ParfumoScraper.REQUEST_DELAY = original_delay

    def test_no_delay_on_first_request(self):
        """Test no delay on first request."""
        import time

        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = None
        scraper._last_request_time = 0  # No previous request
        scraper._client = None

        start = time.time()
        scraper._wait_for_rate_limit()
        elapsed = time.time() - start

        # Should be nearly instant
        assert elapsed < 0.1


def _new_scraper() -> ParfumoScraper:
    """Build a bare ParfumoScraper with no DB/HTTP client wired up."""
    scraper = ParfumoScraper.__new__(ParfumoScraper)
    scraper.db = None
    scraper._last_request_time = 0
    scraper._client = None
    return scraper


class TestParfumoScraperHostAllowlist:
    """Tests for the outbound SSRF host allowlist (Major finding 3)."""

    def test_allows_configured_parfumo_hosts(self):
        scraper = _new_scraper()
        assert scraper._is_allowed_url("https://www.parfumo.com/Perfumes/x/y")
        assert scraper._is_allowed_url("https://parfumo.com/Perfumes/x/y")

    def test_rejects_non_allowlisted_host(self):
        scraper = _new_scraper()
        assert not scraper._is_allowed_url("https://evil.example.com/Perfumes/x/y")

    def test_rejects_non_https_scheme(self):
        scraper = _new_scraper()
        assert not scraper._is_allowed_url("http://www.parfumo.com/Perfumes/x/y")

    def test_rejects_lookalike_subdomain(self):
        """A host merely containing 'parfumo.com' must not be trusted."""
        scraper = _new_scraper()
        assert not scraper._is_allowed_url(
            "https://www.parfumo.com.evil.example/Perfumes/x/y"
        )

    def test_make_request_short_circuits_disallowed_host(self):
        """_make_request never touches the network for a disallowed host."""
        scraper = _new_scraper()

        with patch.object(scraper, "_get_client") as mock_client:
            result = scraper._make_request("https://evil.example.com/steal")

        assert result is None
        mock_client.assert_not_called()

    def test_scrape_perfume_page_refuses_disallowed_host(self):
        """import_from_url()'s operator-supplied URL is also allowlisted."""
        scraper = _new_scraper()

        with patch.object(scraper, "_get_client") as mock_client:
            result = scraper.scrape_perfume_page("https://internal.local/admin")

        assert result is None
        mock_client.assert_not_called()


class TestParfumoScraperRetryAfterParsing:
    """Tests for the Retry-After header parsing helper."""

    def test_parses_numeric_seconds(self):
        assert ParfumoScraper._parse_retry_after("5") == 5.0

    def test_returns_none_for_missing_header(self):
        assert ParfumoScraper._parse_retry_after(None) is None

    def test_returns_none_for_http_date_form(self):
        assert (
            ParfumoScraper._parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None
        )


class TestParfumoScraperBackoff:
    """Tests for 429/503 backoff-and-retry behavior."""

    def test_retries_after_429_then_succeeds(self):
        scraper = _new_scraper()

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "0"}

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.text = SAMPLE_PERFUME_PAGE

        client = MagicMock()
        client.get.side_effect = [rate_limited, ok_response]

        original_delay = ParfumoScraper.REQUEST_DELAY
        ParfumoScraper.REQUEST_DELAY = 0.0
        try:
            with patch.object(scraper, "_get_client", return_value=client):
                result = scraper.scrape_perfume_page(
                    "https://parfumo.com/Perfumes/test/test"
                )
        finally:
            ParfumoScraper.REQUEST_DELAY = original_delay

        assert result is not None
        assert result.name == "Test Fragrance"
        assert client.get.call_count == 2

    def test_gives_up_after_max_retries_on_503(self):
        scraper = _new_scraper()

        unavailable = MagicMock()
        unavailable.status_code = 503
        unavailable.headers = {}

        client = MagicMock()
        client.get.return_value = unavailable

        original_delay = ParfumoScraper.REQUEST_DELAY
        original_backoff = ParfumoScraper.BACKOFF_BASE_SECONDS
        ParfumoScraper.REQUEST_DELAY = 0.0
        ParfumoScraper.BACKOFF_BASE_SECONDS = 0.0
        try:
            with patch.object(scraper, "_get_client", return_value=client):
                result = scraper.scrape_perfume_page(
                    "https://parfumo.com/Perfumes/test/test"
                )
        finally:
            ParfumoScraper.REQUEST_DELAY = original_delay
            ParfumoScraper.BACKOFF_BASE_SECONDS = original_backoff

        assert result is None
        assert client.get.call_count == ParfumoScraper.MAX_RETRIES + 1


@pytest.mark.asyncio
class TestParfumoScraperGenderVocabulary:
    """Major finding 5: scraper output must match the API's gender enum.

    The Kaggle importer and the API's gender_target schemas both use the
    capitalized "Masculine"/"Feminine"/"Unisex" vocabulary
    (core.vocabulary.GENDER_TARGETS). _extract_gender() scrapes lowercase
    values from page text; _create_fragrance() must map them to the
    canonical form rather than storing the lowercase scrape output
    directly, or gender_target filtering silently excludes every
    fragrance imported through this scraper.
    """

    @pytest.mark.parametrize(
        ("scraped_gender", "expected"),
        [
            ("masculine", "Masculine"),
            ("feminine", "Feminine"),
            ("unisex", "Unisex"),
            (None, "Unisex"),  # unknown/unscraped gender defaults to Unisex
            ("nonsense-value", "Unisex"),  # unrecognized value also defaults
        ],
    )
    async def test_stored_gender_target_matches_api_vocabulary(
        self, async_session, scraped_gender, expected
    ):
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = async_session

        scraped = ScrapedFragrance(
            url="https://parfumo.com/Perfumes/test/test",
            name="Vocabulary Test",
            brand="Vocabulary Brand",
            gender=scraped_gender,
        )

        fragrance_id = await scraper._create_fragrance(
            scraped, scraped.name, scraped.brand
        )

        assert fragrance_id is not None
        # Fetch what was actually persisted rather than trusting the
        # in-memory object, so the assertion covers the DB round trip too.
        result = await async_session.execute(
            select(Fragrance).where(Fragrance.id == fragrance_id)
        )
        fragrance = result.scalar_one()

        assert fragrance.gender_target == expected
        assert fragrance.gender_target in GENDER_TARGETS
