"""Unit tests for ParfumoScraper.

Tests the Parfumo.com web scraping functionality with mocked HTTP responses.

Fixture provenance (P1.9): every SAMPLE_* HTML constant in this module is
hand-authored, synthetic markup - none of it is a stored or redistributed
copy of a live Parfumo page, and every brand/fragrance/reviewer name is a
fictitious placeholder ("Test Brand", "Sibling Brand", ...). The CSS
classes, `data-*` attributes, and element nesting they use (e.g.
`.p_name_h1`/`.p_brand_name`, `.pyramid_block.nb_t/.nb_m/.nb_b`,
`.barfiller_element.rating-details[data-type]`, the sidebar "Also liked"
list, and the `.p_con` concentration-popup trigger) were confirmed by
fetching two live, publicly reachable perfume pages once each on
2026-09-12 to inspect their structure (a single ordinary page load per
URL, the same access any visitor's browser performs - not stored,
committed, or redistributed here) and are otherwise written independently
to model that structure with placeholder content. Where the live pages
turned out to load data only via client-side AJAX (concentration variants
behind `getConcentrationsPopup()`; the `#sim_wrapper .sim_item` "Smells
similar" widget, which carries no `href`), the parser intentionally does
not fabricate an extraction for it, and a fixture documents that gap
instead of a fake success path - see
`TestParfumoScraperConcentrationVariantLimitation`.
"""

import dataclasses
import logging
import threading
from datetime import timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from fragrance_rater.core.vocabulary import GENDER_TARGETS
from fragrance_rater.models.calibration import Perfumer, SourceSnapshot, VersionPerfumer
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance, FragranceNote
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.services.parfumo_scraper import (
    ParfumoScraper,
    ScrapedFragrance,
    SearchResult,
)
from fragrance_rater.utils.timestamps import now_naive_utc

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

# search() now POSTs to the real livesearch endpoint (found by reading
# Parfumo's own JS this session) and parses `.ls-perfume-item` fragments.
# Deliberately includes two results sharing a name with different
# concentration/year ("Test Fragrance" EDP 2010 vs. Cologne 2016) to
# exercise the ambiguity/scoped-selector cases (see search()'s docstring
# and the module docstring for fixture provenance).
SAMPLE_LIVESEARCH_RESULTS = """
<div class="live_search_results">
    <div id="ls-perfumes">
        <div class="ls-perfume-item flex pointer">
            <div class="ls-perfume-info">
                <div class="name bold">Test Fragrance <span class="label_a small upper ml-0-5"> Eau de Parfum</span></div>
                <span class="brand lightgrey text-sm">Test Brand</span> <span class="label_a small">2010</span>
            </div>
            <a href="https://www.parfumo.com/Perfumes/Test_Brand/test-fragrance-edp" class="ls-perfume-overlay"></a>
        </div>
        <div class="ls-perfume-item flex pointer">
            <div class="ls-perfume-info">
                <div class="name bold">Test Fragrance <span class="label_a small upper ml-0-5"> Cologne</span></div>
                <span class="brand lightgrey text-sm">Test Brand</span> <span class="label_a small">2016</span>
            </div>
            <a href="https://www.parfumo.com/Perfumes/Test_Brand/test-fragrance-cologne" class="ls-perfume-overlay"></a>
        </div>
        <div class="ls-perfume-item flex pointer">
            <div class="ls-perfume-info">
                <div class="name bold">Unrelated Scent</div>
                <span class="brand lightgrey text-sm">Other Brand</span> <span class="label_a small">1985</span>
            </div>
            <a href="https://www.parfumo.com/Perfumes/Other_Brand/unrelated-scent" class="ls-perfume-overlay"></a>
        </div>
    </div>
</div>
"""

SAMPLE_LIVESEARCH_NO_RESULTS = """
<div class="live_search_results">
    <div id="ls-perfumes"></div>
</div>
"""

# P1.9 fixture: the real per-dimension rating blocks (scent/durability/
# sillage/bottle/pricing), an "in production" status sentence, and the
# sidebar "Also liked" recommendation list. See the module docstring for
# fixture provenance.
SAMPLE_PERFUME_PAGE_METRICS_AND_STATUS = """
<!DOCTYPE html>
<html lang="en">
<head><title>Metrics Fragrance by Metrics Brand » Parfumo</title></head>
<body>
    <h1 class="p_name_h1">
        Metrics Fragrance
        <span class="p_brand_name nobold">Metrics Brand2023</span>
    </h1>

    <span itemprop="description">A popular perfume by Metrics Brand for men,
    released in 2023. The scent is fresh-woody. It is still in production.</span>

    <div class="flex flex-wrap">
        <div class="barfiller_element rating-details pointer" data-type="scent">
            <div class="text-xs upper blue">Scent</div>
            <div class="w-100 nowrap">
                <span class="pr-0-5 text-lg bold blue">8.4</span><span class="lightgrey text-2xs upper">1,200 Ratings</span>
            </div>
        </div>
        <div class="barfiller_element rating-details pointer" data-type="durability">
            <div class="text-xs upper pink">Longevity</div>
            <div class="w-100 nowrap">
                <span class="pr-0-5 text-lg bold pink">7.3</span><span class="lightgrey text-2xs upper">1100 Ratings</span>
            </div>
        </div>
        <div class="barfiller_element rating-details pointer" data-type="sillage">
            <div class="text-xs upper purple">Sillage</div>
            <div class="w-100 nowrap">
                <span class="pr-0-5 text-lg bold purple">6.9</span><span class="lightgrey text-2xs upper">1050 Ratings</span>
            </div>
        </div>
        <div class="barfiller_element rating-details pointer" data-type="bottle">
            <div class="text-xs upper green">Bottle</div>
            <div class="w-100 nowrap">
                <span class="pr-0-5 text-lg bold green">7.7</span><span class="lightgrey text-2xs upper">900 Ratings</span>
            </div>
        </div>
        <div class="barfiller_element rating-details pointer" data-type="pricing">
            <div class="text-xs upper grey">Value for money</div>
            <div class="w-100 nowrap">
                <span class="pr-0-5 text-lg bold grey">5.5</span><span class="lightgrey text-2xs upper">800 Ratings</span>
            </div>
        </div>
    </div>

    <div class="text-lg bold mb-0-5">Also liked</div>
    <div class="text-sm lightgrey mb-1">Users who like <strong>Metrics Fragrance</strong> often also like</div>
    <div class="mb-2">
        <a href="https://www.parfumo.com/Perfumes/Sibling_Brand/sibling-scent"><img alt="Sibling Scent by Sibling Brand" class="p_pic_sidebar"></a>
        <a href="https://www.parfumo.com/Perfumes/Rival_Brand/rival-scent"><img alt="Rival Scent by Rival Brand" class="p_pic_sidebar"></a>
    </div>
</body>
</html>
"""

# P1.9 fixture: a discontinued fragrance, the alternate status phrasing.
SAMPLE_PERFUME_PAGE_DISCONTINUED = """
<!DOCTYPE html>
<html lang="en">
<head><title>Retired Fragrance by Retired Brand » Parfumo</title></head>
<body>
    <h1 class="p_name_h1">
        Retired Fragrance
        <span class="p_brand_name nobold">Retired Brand2005</span>
    </h1>

    <span itemprop="description">A perfume by Retired Brand for women,
    released in 2005. The scent is powdery-floral. It is no longer in
    production.</span>
</body>
</html>
"""

# P1.9 fixture: a page missing every optional section (no rating blocks,
# no description, no "Also liked" sidebar, no perfumer/notes) - every new
# field must default to empty/None rather than raising or guessing.
SAMPLE_PERFUME_PAGE_MISSING_SECTIONS = """
<!DOCTYPE html>
<html lang="en">
<head><title>Sparse Fragrance by Sparse Brand » Parfumo</title></head>
<body>
    <h1 class="p_name_h1">
        Sparse Fragrance
        <span class="p_brand_name nobold">Sparse Brand</span>
    </h1>
</body>
</html>
"""

# P1.9 fixture: the concentration-variant trigger (`.p_con`) that on the
# live site opens an AJAX-populated popup (`getConcentrationsPopup()`)
# rather than rendering related versions into the static page. No related-
# version data exists in this fixture on purpose - see
# TestParfumoScraperConcentrationVariantLimitation.
SAMPLE_PERFUME_PAGE_CONCENTRATION_TRIGGER = """
<!DOCTYPE html>
<html lang="en">
<head><title>Layered Fragrance by Layered Brand » Parfumo</title></head>
<body>
    <h1 class="p_name_h1">
        Layered Fragrance
        <span class="p_brand_name nobold">Layered Brand2010</span>
        <span class="p_con label_a pointer upper">Eau de Parfum
            <i class="fa fa-angle-down grey" aria-hidden="true"></i>
        </span>
    </h1>
    <script>
        $('.p_con').click(function(){getConcentrationsPopup(1234, 0, 'x');});
    </script>
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

    def test_make_request_logs_a_non_200_status(self, caplog):
        """A non-200/429/503 status must be logged, not silently swallowed,
        so a caller cannot mistake a failed fetch for zero genuine matches."""
        scraper = _new_scraper()

        mock_response = MagicMock()
        mock_response.status_code = 404

        with (
            patch.object(scraper, "_get_client") as mock_client,
            caplog.at_level(logging.WARNING),
        ):
            client = MagicMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = scraper._make_request("https://www.parfumo.com/Perfumes/x/y")

        assert result is None
        assert any("404" in record.message for record in caplog.records), (
            "expected a warning logging the non-200 status"
        )


class TestParfumoScraperSearch:
    """Tests for ParfumoScraper search functionality.

    search() posts to the real livesearch endpoint (Critical finding:
    the previous GET /s_perfumes.php implementation returned a generic
    page against the live site, not real results - see search()'s
    docstring and the module docstring for how this was found).
    """

    def test_search_posts_to_the_livesearch_endpoint(self):
        """Regression test for the dead-search-endpoint finding."""
        scraper = _new_scraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_LIVESEARCH_RESULTS

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            scraper.search("Test Fragrance", limit=10)

        client.post.assert_called_once()
        call_args = client.post.call_args
        assert call_args.args[0] == ParfumoScraper.LIVESEARCH_URL
        assert call_args.kwargs["data"]["q"] == "Test Fragrance"
        client.get.assert_not_called()

    def test_search_returns_results_with_concentration_and_year(self):
        """Concentration/year must be scoped to their own elements, not
        conflated (Critical finding: a single non-scoped `.label_a`
        selector previously read the concentration text as the year for
        any result that had one)."""
        scraper = _new_scraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_LIVESEARCH_RESULTS

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            results = scraper.search("Test Fragrance", limit=10)

        assert len(results) == 3
        edp, cologne, unrelated = results

        assert edp.name == "Test Fragrance"
        assert edp.concentration == "Eau de Parfum"
        assert edp.year == 2010
        assert (
            edp.url == "https://www.parfumo.com/Perfumes/Test_Brand/test-fragrance-edp"
        )

        assert cologne.name == "Test Fragrance"
        assert cologne.concentration == "Cologne"
        assert cologne.year == 2016

        assert unrelated.name == "Unrelated Scent"
        assert unrelated.concentration is None
        assert unrelated.year == 1985

    def test_search_respects_limit(self):
        """Test that search respects the limit parameter."""
        scraper = _new_scraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_LIVESEARCH_RESULTS

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            results = scraper.search("test", limit=1)

        assert len(results) == 1

    def test_search_handles_no_results(self):
        """Test search handles empty results."""
        scraper = _new_scraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_LIVESEARCH_NO_RESULTS

        with patch.object(scraper, "_get_client") as mock_client:
            client = MagicMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            results = scraper.search("xyznonexistent123")

        assert len(results) == 0

    def test_search_short_circuits_disallowed_host(self):
        """The host allowlist still applies to the POST-based search."""
        scraper = _new_scraper()

        with (
            patch.object(scraper, "_get_client") as mock_client,
            patch.object(scraper, "LIVESEARCH_URL", "https://evil.example.com/x"),
        ):
            results = scraper.search("anything")

        assert results == []
        mock_client.assert_not_called()


class TestParseLivesearchItem:
    """Tests for `_parse_livesearch_item`'s malformed/absent-markup branches.

    `search()`'s own tests (above) exercise the well-formed-card path;
    these call the parser directly against a single `.ls-perfume-item`
    fragment, since `_parse_livesearch_item`'s entire job is tolerating
    the messy markup real search results sometimes contain."""

    @staticmethod
    def _parse(html: str) -> SearchResult | None:
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        item = BeautifulSoup(html, "html.parser").select_one(".ls-perfume-item")
        assert item is not None
        return scraper._parse_livesearch_item(item)

    def test_returns_none_when_the_overlay_link_is_missing(self):
        """No `a.ls-perfume-overlay` at all - href can't be recovered."""
        result = self._parse("""
            <div class="ls-perfume-item">
                <div class="ls-perfume-info">
                    <div class="name">Test Fragrance</div>
                </div>
            </div>
        """)
        assert result is None

    def test_prefixes_a_relative_href_with_the_base_url(self):
        result = self._parse("""
            <div class="ls-perfume-item">
                <div class="ls-perfume-info">
                    <div class="name">Test Fragrance</div>
                </div>
                <a class="ls-perfume-overlay" href="/Perfumes/Test_Brand/test-fragrance"></a>
            </div>
        """)
        assert result is not None
        assert (
            result.url
            == f"{ParfumoScraper.BASE_URL}/Perfumes/Test_Brand/test-fragrance"
        )

    def test_returns_none_when_the_name_element_is_missing(self):
        result = self._parse("""
            <div class="ls-perfume-item">
                <div class="ls-perfume-info"></div>
                <a class="ls-perfume-overlay" href="https://www.parfumo.com/x"></a>
            </div>
        """)
        assert result is None

    def test_returns_none_when_the_name_is_empty(self):
        """`.name` present but blank (e.g. whitespace-only markup)."""
        result = self._parse("""
            <div class="ls-perfume-item">
                <div class="ls-perfume-info">
                    <div class="name">   </div>
                </div>
                <a class="ls-perfume-overlay" href="https://www.parfumo.com/x"></a>
            </div>
        """)
        assert result is None

    def test_year_stays_none_when_the_year_element_is_missing(self):
        """No `.ls-perfume-info > span.label_a` at all - a missing year
        is not itself a reason to reject the result."""
        result = self._parse("""
            <div class="ls-perfume-item">
                <div class="ls-perfume-info">
                    <div class="name">Test Fragrance</div>
                </div>
                <a class="ls-perfume-overlay" href="https://www.parfumo.com/x"></a>
            </div>
        """)
        assert result is not None
        assert result.year is None

    def test_year_stays_none_when_the_year_text_does_not_match(self):
        """The year element is present but its text isn't a recognizable
        18xx/19xx/20xx year (e.g. Parfumo shows "N/A")."""
        result = self._parse("""
            <div class="ls-perfume-item">
                <div class="ls-perfume-info">
                    <div class="name">Test Fragrance</div>
                    <span class="label_a">N/A</span>
                </div>
                <a class="ls-perfume-overlay" href="https://www.parfumo.com/x"></a>
            </div>
        """)
        assert result is not None
        assert result.year is None


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


def _scrape_fixture(html: str) -> ScrapedFragrance:
    """Scrape a synthetic fixture page through the full mocked HTTP path."""
    scraper = _new_scraper()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    with patch.object(scraper, "_get_client") as mock_client:
        client = MagicMock()
        client.get.return_value = mock_response
        mock_client.return_value = client
        result = scraper.scrape_perfume_page(
            "https://parfumo.com/Perfumes/test/fixture"
        )

    assert result is not None
    return result


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

    def test_rejects_url_credentials(self):
        """Credentials must not be accepted, logged, or persisted in source URLs."""
        scraper = _new_scraper()
        assert not scraper._is_allowed_url(
            "https://user:secret@www.parfumo.com/Perfumes/x/y"
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


class TestParfumoScraperRedirectValidation:
    """Tests for the redirect-hop SSRF revalidation hook (Critical finding:
    the ALLOWED_HOSTS check only ran against the initial URL, so a redirect
    from an allowlisted host to an internal address would previously be
    followed unchecked)."""

    @staticmethod
    def _redirect_response(location: str) -> httpx.Response:
        request = httpx.Request("GET", "https://www.parfumo.com/Perfumes/a/b")
        return httpx.Response(302, headers={"Location": location}, request=request)

    def test_allows_redirect_to_allowlisted_host(self):
        scraper = _new_scraper()
        response = self._redirect_response("https://www.parfumo.com/Perfumes/a/c")

        scraper._validate_response_redirect(response)  # must not raise

    def test_allows_relative_redirect(self):
        """A relative Location resolves against an already-allowlisted host."""
        scraper = _new_scraper()
        response = self._redirect_response("/Perfumes/a/c")

        scraper._validate_response_redirect(response)  # must not raise

    def test_blocks_redirect_to_loopback_address(self):
        scraper = _new_scraper()
        response = self._redirect_response("http://127.0.0.1/admin")

        with pytest.raises(httpx.HTTPError):
            scraper._validate_response_redirect(response)

    def test_blocks_redirect_to_cloud_metadata_endpoint(self):
        scraper = _new_scraper()
        response = self._redirect_response("http://169.254.169.254/latest/meta-data/")

        with pytest.raises(httpx.HTTPError):
            scraper._validate_response_redirect(response)

    def test_blocks_redirect_to_lookalike_host(self):
        scraper = _new_scraper()
        response = self._redirect_response(
            "https://www.parfumo.com.evil.example/Perfumes/a/c"
        )

        with pytest.raises(httpx.HTTPError):
            scraper._validate_response_redirect(response)

    def test_ignores_non_redirect_response(self):
        scraper = _new_scraper()
        request = httpx.Request("GET", "https://www.parfumo.com/Perfumes/a/b")
        response = httpx.Response(200, request=request)

        scraper._validate_response_redirect(response)  # must not raise

    def test_get_client_registers_redirect_validation_hook(self):
        scraper = _new_scraper()

        client = scraper._get_client()
        try:
            assert scraper._validate_response_redirect in client.event_hooks["response"]
        finally:
            client.close()

    def test_make_request_follows_allowlisted_redirect_end_to_end(self):
        """A same-host redirect chain is still followed to completion."""
        scraper = _new_scraper()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/Perfumes/a/old":
                return httpx.Response(
                    302,
                    headers={"Location": "https://www.parfumo.com/Perfumes/a/new"},
                )
            return httpx.Response(200, text=SAMPLE_PERFUME_PAGE)

        client = httpx.Client(
            headers=ParfumoScraper.HEADERS,
            follow_redirects=True,
            timeout=30.0,
            transport=httpx.MockTransport(handler),
            event_hooks={"response": [scraper._validate_response_redirect]},
        )

        original_delay = ParfumoScraper.REQUEST_DELAY
        ParfumoScraper.REQUEST_DELAY = 0.0
        try:
            with patch.object(scraper, "_get_client", return_value=client):
                result = scraper._make_request("https://www.parfumo.com/Perfumes/a/old")
        finally:
            ParfumoScraper.REQUEST_DELAY = original_delay
            client.close()

        assert result is not None

    def test_make_request_aborts_redirect_to_disallowed_host_end_to_end(self):
        """Regression test for the SSRF redirect-bypass finding: an
        allowlisted host that 302s to an internal address must not be
        followed, exercised through real httpx redirect-handling logic
        (not just the isolated hook)."""
        scraper = _new_scraper()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/admin"})

        client = httpx.Client(
            headers=ParfumoScraper.HEADERS,
            follow_redirects=True,
            timeout=30.0,
            transport=httpx.MockTransport(handler),
            event_hooks={"response": [scraper._validate_response_redirect]},
        )

        original_delay = ParfumoScraper.REQUEST_DELAY
        ParfumoScraper.REQUEST_DELAY = 0.0
        try:
            with patch.object(scraper, "_get_client", return_value=client):
                result = scraper._make_request("https://www.parfumo.com/Perfumes/a/old")
        finally:
            ParfumoScraper.REQUEST_DELAY = original_delay
            client.close()

        assert result is None


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


@pytest.mark.asyncio
class TestParfumoScraperNoteSavepointIsolation:
    """Regression tests for Critical finding 3, scraper side.

    Mirrors the Kaggle importer regression tests: a note legitimately
    appearing in two pyramid positions must not crash the scrape, and a
    genuine same-position duplicate must be skipped by the per-row
    SAVEPOINT rather than poisoning the whole session.
    """

    async def test_note_in_two_positions_is_not_a_conflict(self, async_session):
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = async_session

        scraped = ScrapedFragrance(
            url="https://parfumo.com/Perfumes/test/two-position-musk",
            name="Two Position Musk",
            brand="Test Brand",
            heart_notes=["Musk"],
            base_notes=["Musk"],
        )

        fragrance_id = await scraper._create_fragrance(
            scraped, scraped.name, scraped.brand
        )

        result = await async_session.execute(
            select(FragranceNote).where(FragranceNote.fragrance_id == fragrance_id)
        )
        fragrance_notes = result.scalars().all()
        positions = sorted(fn.position for fn in fragrance_notes)
        assert positions == ["base", "heart"]
        assert len({fn.id for fn in fragrance_notes}) == 2

    async def test_true_duplicate_position_is_skipped_not_fatal(self, async_session):
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = async_session

        scraped = ScrapedFragrance(
            url="https://parfumo.com/Perfumes/test/duplicate-top",
            name="Duplicate Top Note Scrape",
            brand="Test Brand",
            top_notes=["Bergamot", "Bergamot"],
        )

        fragrance_id = await scraper._create_fragrance(
            scraped, scraped.name, scraped.brand
        )

        result = await async_session.execute(
            select(FragranceNote).where(FragranceNote.fragrance_id == fragrance_id)
        )
        fragrance_notes = result.scalars().all()
        # The duplicate insert was caught and skipped by the per-row
        # SAVEPOINT; the scrape still completes (fragrance_id is not None)
        # rather than crashing on the second insert.
        assert len(fragrance_notes) == 1
        assert fragrance_notes[0].position == "top"


@pytest.mark.asyncio
class TestParfumoScraperAsyncOffload:
    """Important finding: search()/scrape_perfume_page() are blocking sync
    calls (a sync httpx.Client plus time.sleep()-based rate limiting and
    retry backoff). import_from_url() and search_and_import() are async
    methods that call them directly; without offloading to a thread, that
    blocking I/O runs on the event loop thread and stalls it for the
    duration of the request/backoff. Both methods now wrap the blocking
    calls in asyncio.to_thread(); these tests compare thread identities to
    confirm the offload deterministically, without wall-clock thresholds.
    """

    async def test_import_from_url_does_not_block_event_loop(
        self, async_session, monkeypatch
    ):
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = async_session
        event_loop_thread = threading.get_ident()
        worker_thread: int | None = None

        def fake_scrape_perfume_page(url: str) -> ScrapedFragrance:
            nonlocal worker_thread
            worker_thread = threading.get_ident()
            return ScrapedFragrance(url=url, name="Blocking Test", brand="Test Brand")

        monkeypatch.setattr(scraper, "scrape_perfume_page", fake_scrape_perfume_page)
        fragrance_id = await scraper.import_from_url(
            "https://parfumo.com/Perfumes/test/blocking"
        )

        assert fragrance_id is not None
        assert worker_thread is not None
        assert worker_thread != event_loop_thread

    async def test_search_and_import_does_not_block_event_loop(
        self, async_session, monkeypatch
    ):
        scraper = ParfumoScraper.__new__(ParfumoScraper)
        scraper.db = async_session
        event_loop_thread = threading.get_ident()
        worker_threads: list[int] = []

        def fake_search(query: str, limit: int = 10) -> list[SearchResult]:
            worker_threads.append(threading.get_ident())
            return [
                SearchResult(
                    name="Blocking Result",
                    brand="Test Brand",
                    url="https://parfumo.com/Perfumes/test/blocking-search",
                )
            ]

        def fake_scrape_perfume_page(url: str) -> ScrapedFragrance:
            worker_threads.append(threading.get_ident())
            return ScrapedFragrance(url=url, name="Blocking Result", brand="Test Brand")

        monkeypatch.setattr(scraper, "search", fake_search)
        monkeypatch.setattr(scraper, "scrape_perfume_page", fake_scrape_perfume_page)

        fragrance_id = await scraper.search_and_import("Blocking Result", "Test Brand")

        assert fragrance_id is not None
        assert len(worker_threads) == 2
        assert all(worker != event_loop_thread for worker in worker_threads)


def test_version_key_hashes_the_full_url_after_bounded_readable_prefix():
    """Long URLs with the same truncated tail prefix retain distinct identities."""
    prefix = "x" * 190
    first = ParfumoScraper._version_key(f"https://parfumo.com/Perfumes/a/{prefix}-one")
    second = ParfumoScraper._version_key(f"https://parfumo.com/Perfumes/b/{prefix}-two")
    assert first != second
    assert len(first) <= 200
    assert len(second) <= 200


@pytest.mark.asyncio
async def test_source_snapshots_preserve_collaborators_flat_notes_and_unknown_concentration(
    async_session,
):
    """Refresh appends source evidence without inventing a pyramid or touching ratings."""
    scraper = ParfumoScraper.__new__(ParfumoScraper)
    scraper.db = async_session
    scraped = ScrapedFragrance(
        url="https://parfumo.com/Perfumes/test/source-evidence",
        name="Source evidence",
        brand="Test",
        flat_notes=["Vetiver", "Musk"],
        perfumers=["First Nose", "Second Nose"],
        rating=8.1,
        rating_count=31,
    )
    fragrance_id = await scraper._create_fragrance(scraped, scraped.name, scraped.brand)
    fragrance = await async_session.get(Fragrance, fragrance_id)
    assert fragrance.concentration == "Unknown"
    notes = list(
        await async_session.scalars(
            select(FragranceNote).where(FragranceNote.fragrance_id == fragrance_id)
        )
    )
    assert len(notes) == 2
    assert {note.position for note in notes} == {"flat"}
    names = set(
        await async_session.scalars(
            select(Perfumer.name)
            .join(VersionPerfumer)
            .where(VersionPerfumer.fragrance_id == fragrance_id)
        )
    )
    assert names == {"First Nose", "Second Nose"}
    first_snapshot = await async_session.scalar(
        select(SourceSnapshot).where(SourceSnapshot.fragrance_id == fragrance_id)
    )
    assert first_snapshot is not None
    first_snapshot.retrieved_at = now_naive_utc() - timedelta(minutes=1)
    reviewer = Reviewer(id="source-reviewer", name="Source Reviewer")
    async_session.add(reviewer)
    await async_session.flush()
    rating = Evaluation(
        fragrance_id=fragrance_id,
        reviewer_id=reviewer.id,
        rating=2,
        notes="Pencil shavings",
    )
    async_session.add(rating)
    await async_session.flush()
    scraped.rating = 9.0
    scraped.rating_count = 45
    scraped.flat_notes = ["Rose"]
    await scraper._update_fragrance(fragrance, scraped)
    latest_snapshot = next(
        snapshot
        for snapshot in await async_session.scalars(
            select(SourceSnapshot).where(SourceSnapshot.fragrance_id == fragrance_id)
        )
        if snapshot.payload["rating_count"] == 45
    )
    latest_snapshot.retrieved_at = now_naive_utc()
    snapshots = list(
        await async_session.scalars(
            select(SourceSnapshot)
            .where(SourceSnapshot.fragrance_id == fragrance_id)
            .order_by(SourceSnapshot.retrieved_at)
        )
    )
    assert len(snapshots) == 2
    assert snapshots[0].payload["rating"] == 8.1
    assert snapshots[0].payload["flat_notes"] == ["Vetiver", "Musk"]
    assert snapshots[1].payload["rating_count"] == 45
    assert snapshots[1].payload["flat_notes"] == ["Rose"]
    assert all(snapshot.source_url == scraped.url for snapshot in snapshots)
    links = list(
        await async_session.scalars(
            select(VersionPerfumer).where(VersionPerfumer.fragrance_id == fragrance_id)
        )
    )
    assert len(links) == 2
    await async_session.refresh(rating)
    assert rating.rating == 2
    assert rating.notes == "Pencil shavings"


def test_unstructured_notes_remain_flat_during_extraction():
    """A page without a pyramid must not turn all published notes into heart notes."""
    scraper = ParfumoScraper.__new__(ParfumoScraper)
    scraped = ScrapedFragrance(
        url="https://parfumo.com/Perfumes/test/flat", name="Flat", brand="Test"
    )
    scraper._extract_notes(
        BeautifulSoup(
            '<a href="/Notes/Vetiver">Vetiver</a><a href="/Notes/Musk">Musk</a>',
            "html.parser",
        ),
        scraped,
    )
    assert set(scraped.flat_notes) == {"Vetiver", "Musk"}
    assert scraped.top_notes == []
    assert scraped.heart_notes == []
    assert scraped.base_notes == []


class TestParfumoScraperMetrics:
    """P1.9: per-dimension rating extraction (scent/longevity/sillage/bottle/
    value_for_money), verified against the real `.barfiller_element.rating-
    details[data-type]` block shape (see module docstring for provenance)."""

    def test_extracts_all_five_metrics(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_METRICS_AND_STATUS)
        assert result.metrics == {
            "scent": 8.4,
            "longevity": 7.3,
            "sillage": 6.9,
            "bottle": 7.7,
            "value_for_money": 5.5,
        }

    def test_extracts_metric_vote_counts_and_strips_thousands_separators(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_METRICS_AND_STATUS)
        assert result.metric_vote_counts == {
            "scent": 1200,
            "longevity": 1100,
            "sillage": 1050,
            "bottle": 900,
            "value_for_money": 800,
        }

    def test_overall_rating_is_not_fused_with_the_nested_vote_count(self):
        """Regression test for the nested-markup finding in _extract_rating:
        reading the whole block's concatenated text ("Scent" + "8.4" +
        "1,200 Ratings") without a separator previously fused the score and
        count into a bogus "8.41200"-shaped number. The scoped score/count
        elements must be read instead."""
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_METRICS_AND_STATUS)
        assert result.rating == pytest.approx(8.4)
        assert result.rating_count == 1200

    def test_original_flat_text_fixture_still_falls_back_correctly(self):
        """The pre-existing flat-text fixture (no scoped score/count
        elements) must still resolve through the fallback path."""
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE)
        assert result.rating == pytest.approx(8.55)

    def test_missing_metric_blocks_leave_both_dicts_empty(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_MISSING_SECTIONS)
        assert result.metrics == {}
        assert result.metric_vote_counts == {}


class TestParfumoScraperProductionStatus:
    """P1.9: production status is inferred from Parfumo's own description
    sentence; anything unrecognized stays None rather than guessed."""

    def test_still_in_production(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_METRICS_AND_STATUS)
        assert result.production_status == "in_production"

    def test_no_longer_in_production_reads_as_discontinued(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_DISCONTINUED)
        assert result.production_status == "discontinued"

    def test_missing_description_stays_unknown(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_MISSING_SECTIONS)
        assert result.production_status is None


class TestParfumoScraperSimilarFragrances:
    """P1.9: the sidebar "Also liked" list is the only similar-fragrance
    source with real, navigable hrefs (see module docstring)."""

    def test_extracts_also_liked_sidebar_entries(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_METRICS_AND_STATUS)
        assert result.similar_fragrances == [
            {
                "name": "Sibling Scent",
                "brand": "Sibling Brand",
                "url": "https://www.parfumo.com/Perfumes/Sibling_Brand/sibling-scent",
            },
            {
                "name": "Rival Scent",
                "brand": "Rival Brand",
                "url": "https://www.parfumo.com/Perfumes/Rival_Brand/rival-scent",
            },
        ]

    def test_missing_also_liked_section_stays_empty(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_MISSING_SECTIONS)
        assert result.similar_fragrances == []


class TestParfumoScraperConcentrationVariantLimitation:
    """P1.9: on the live site, other concentrations of the same fragrance
    (related versions) are populated by a client-side AJAX popup
    (`getConcentrationsPopup()`), not rendered into the static page the
    `.p_con` trigger sits on. ScrapedFragrance intentionally carries no
    `related_versions` field until a follow-up implements that endpoint;
    these tests document the gap rather than silently doing nothing, so a
    future change replaces this test deliberately instead of by accident.
    """

    def test_concentration_still_parses_from_the_title(self):
        """What the static page *does* offer (the concentration named in
        the title) is still extracted normally."""
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_CONCENTRATION_TRIGGER)
        assert result.concentration == "EDP"

    def test_no_related_version_field_is_fabricated(self):
        field_names = {f.name for f in dataclasses.fields(ScrapedFragrance)}
        assert "related_versions" not in field_names


class TestParfumoScraperGtin:
    """A scraped GTIN is the strongest identity signal this project has
    (manufacturer-assigned per exact SKU); it must never be trusted
    unvalidated, since a malformed/truncated scrape would otherwise
    silently corrupt the one field meant to *confirm* identity rather
    than infer it."""

    def test_extracts_a_valid_gtin(self):
        html = """
        <html><body>
            <h1 class="p_name_h1">Test Fragrance<span class="p_brand_name nobold">Test Brand</span></h1>
            <meta itemprop="gtin13" content="3508440005953">
        </body></html>
        """
        result = _scrape_fixture(html)
        assert result.gtin == "3508440005953"

    def test_rejects_an_invalid_check_digit_rather_than_propagating_it(self):
        html = """
        <html><body>
            <h1 class="p_name_h1">Test Fragrance<span class="p_brand_name nobold">Test Brand</span></h1>
            <meta itemprop="gtin13" content="3508440005950">
        </body></html>
        """
        result = _scrape_fixture(html)
        assert result.gtin is None

    def test_missing_gtin_meta_stays_none(self):
        result = _scrape_fixture(SAMPLE_PERFUME_PAGE_MISSING_SECTIONS)
        assert result.gtin is None
