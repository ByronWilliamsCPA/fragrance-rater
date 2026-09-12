"""Parfumo.com web scraper for fragrance data.

Used as an additional data source alongside Kaggle CSV imports.
Parfumo has excellent note taxonomy and community ratings.

NOTE: Web scraping should be done responsibly with appropriate delays.
Parfumo uses Cloudflare protection - be respectful of their resources.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup, Tag
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.calibration import (
    Membership,
    Perfumer,
    SourceSnapshot,
    VersionPerfumer,
)
from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)
from fragrance_rater.utils.gtin import is_valid_gtin

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.core.vocabulary import GenderTarget


@dataclass
class ScrapedFragrance:
    """Data structure for scraped fragrance information."""

    url: str
    name: str
    brand: str
    display_title: str | None = None
    flat_notes: list[str] = field(default_factory=list)
    perfumers: list[str] = field(default_factory=list)
    top_notes: list[str] = field(default_factory=list)
    heart_notes: list[str] = field(default_factory=list)
    base_notes: list[str] = field(default_factory=list)
    accords: dict[str, float] = field(default_factory=dict)
    rating: float | None = None
    rating_count: int | None = None
    gender: str | None = None
    year: int | None = None
    perfumer: str | None = None
    concentration: str | None = None
    image_url: str | None = None
    # #ASSUME: external-resources: metrics/metric_vote_counts hold the
    # per-dimension community ratings (scent, longevity, sillage, bottle,
    # value_for_money) shown alongside the single overall score
    # _extract_rating already captures. Verified against live pages
    # (Creed Aventus, Chanel Bleu de Chanel, 2026-09-12): each dimension is
    # its own `.barfiller_element.rating-details[data-type]` block: see
    # `_extract_metrics`.
    # #VERIFY: covered by fixtures modeling that block structure and by a
    # missing-block fixture asserting both dicts stay empty rather than
    # guessing a value.
    metrics: dict[str, float] = field(default_factory=dict)
    metric_vote_counts: dict[str, int] = field(default_factory=dict)
    # #ASSUME: data-integrity: production_status is None unless the page's
    # description sentence uses one of the two phrasings Parfumo's own
    # copy uses ("still in production" / "no longer in production" /
    # "discontinued"). Anything else - a redesigned sentence, a language
    # other than English - stays unknown rather than guessed, matching the
    # "unknown concentration stays unknown" invariant applied to status.
    # #VERIFY: covered by in-production, discontinued, and
    # absent-description fixtures.
    production_status: str | None = None
    # #EDGE: external-resources: this is populated only from the sidebar
    # "Also liked" recommendations, which use real `<a href>` anchors.
    # Parfumo's in-page "Smells similar" widget (`#sim_wrapper .sim_item`)
    # is rendered with `data-p_id`/`data-s_id` attributes and no href, so
    # it cannot be resolved to a fragrance URL from static HTML; it is
    # intentionally not scraped here rather than emitting a URL-less
    # entry that looks navigable but is not.
    similar_fragrances: list[dict[str, str]] = field(default_factory=list)
    # #ASSUME: data-integrity: a barcode is manufacturer-assigned per
    # exact SKU and does not depend on Parfumo's page text/markup being
    # unambiguous, unlike every other field above - see
    # `fragrance_rater.utils.gtin` and `_extract_gtin`. Only populated
    # when Parfumo publishes `meta[itemprop='gtin13']`; not every page
    # does (see docs/planning/evidence/
    # baseline-v3.1-parfumo-source-resolution.md's single-release
    # entries), so this stays None rather than guessed. A caller
    # comparing this against a physically-scanned barcode is the
    # strongest available identity confirmation this project has.
    gtin: str | None = None


@dataclass
class SearchResult:
    """A search result from Parfumo.

    # #ASSUME: data-integrity: `concentration` is the one distinguishing
    # field between two results that otherwise share `name`/`brand` (e.g.
    # the same fragrance's Eau de Toilette and Eau de Parfum releases). A
    # caller presenting `search()` results to a human for disambiguation
    # (see `search()`'s docstring) must display it rather than only
    # name/brand/url, or a same-named different-concentration release is
    # indistinguishable from the one actually wanted.
    """

    name: str
    brand: str
    url: str
    year: int | None = None
    concentration: str | None = None


class ParfumoScraper:
    """Web scraper for Parfumo.com.

    Parfumo offers detailed fragrance information including:
    - Note pyramid (top/heart/base)
    - Community ratings with vote counts
    - Perfumer attribution
    - Detailed accords

    Rate limiting is enforced to be respectful of their servers.

    Args:
        session (AsyncSession): Async database session for imports.

    Attributes:
        BASE_URL: Parfumo site root.
        LIVESEARCH_URL: Perfume search endpoint used by `search()`.
        ALLOWED_HOSTS (ClassVar[frozenset[str]]): Outbound host allowlist;
            requests to any other host are refused before being sent.
        METRIC_TYPE_LABELS (ClassVar[dict[str, str]]): Maps a metric
            page's raw ``data-type`` to the key used in
            ScrapedFragrance.metrics/metric_vote_counts.
        REQUEST_DELAY: Minimum seconds between requests.
        MAX_RETRIES: Maximum retry attempts on a 429/503 response.
        BACKOFF_BASE_SECONDS: Base delay for exponential backoff between
            retries when the response carries no ``Retry-After`` header.
        HEADERS (ClassVar[dict[str, str]]): Browser-like request headers.
    """

    BASE_URL = "https://www.parfumo.com"
    # #CRITICAL: data-integrity: the previous implementation of search()
    # issued `GET {BASE_URL}/s_perfumes.php?keywords=...` and was found,
    # verified live on 2026-09-12, to render a generic/"trending" page
    # regardless of query rather than real results - every query returned
    # the same two unrelated links. Reading Parfumo's own bundled JS
    # (assets/js/_js_main322.js) showed the visible search box actually
    # posts to LIVESEARCH_URL with {q, o, iwear} and gets back an HTML
    # fragment of `.ls-perfume-item` cards (name, concentration, brand,
    # release year, url); search() uses that endpoint instead.
    # #VERIFY: covered by fixtures modeling a `.ls-perfume-item` response;
    # a regression here (Parfumo changing this endpoint) would surface as
    # search() returning no/wrong results, not a crash, so periodic live
    # verification (as in docs/planning/evidence/
    # baseline-v3.1-parfumo-source-resolution.md) remains the backstop.
    LIVESEARCH_URL = f"{BASE_URL}/action/livesearch/livesearch.php"

    # #CRITICAL: security: import_from_url() (via the CLI's `parfumo-url`
    # command) accepts an operator-supplied URL and passes it straight to
    # _make_request(). Without a host allowlist this is an SSRF vector: a
    # malicious/mistaken URL could target internal services reachable from
    # wherever the CLI runs. The app already ships SSRFPreventionMiddleware
    # for inbound requests; this list is the outbound equivalent.
    # #VERIFY: _make_request() rejects any URL whose scheme isn't https or
    # whose hostname isn't in ALLOWED_HOSTS before making the request.
    ALLOWED_HOSTS: ClassVar[frozenset[str]] = frozenset(
        {"parfumo.com", "www.parfumo.com"}
    )

    # Maps a rating block's `data-type` attribute to the canonical metric
    # key used in ScrapedFragrance.metrics/metric_vote_counts. Confirmed
    # against live perfume pages on 2026-09-12 (see `_extract_metrics`);
    # an unrecognized data-type is skipped rather than guessed.
    METRIC_TYPE_LABELS: ClassVar[dict[str, str]] = {
        "scent": "scent",
        "durability": "longevity",
        "sillage": "sillage",
        "bottle": "bottle",
        "pricing": "value_for_money",
    }

    # Delay between requests (seconds) - be respectful
    REQUEST_DELAY = 3.0

    # Retry/backoff for rate-limited or unavailable responses.
    MAX_RETRIES = 3
    BACKOFF_BASE_SECONDS = 2.0

    # User agent to identify as a browser
    # Keep headers minimal to avoid Cloudflare issues
    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.db = session
        self._last_request_time: float = 0
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                headers=self.HEADERS,
                follow_redirects=True,
                timeout=30.0,
                event_hooks={"response": [self._validate_response_redirect]},
            )
        return self._client

    # #CRITICAL: security: the client above is configured with
    # follow_redirects=True. Without this hook, a 3xx response from an
    # already-allowlisted host (e.g. www.parfumo.com, or anything reachable
    # via a chain from it - a compromised upstream, an open redirector) could
    # carry a `Location` pointing at an internal address (127.0.0.1, the
    # 169.254.169.254 cloud metadata endpoint, an internal hostname) and
    # httpx would follow it automatically, since _make_request only checks
    # _is_allowed_url() against the *initial* URL, never against redirect
    # targets. httpx calls every registered "response" event hook on each
    # response in the chain - see httpx.Client._send_handling_redirects,
    # which invokes response hooks before building/following the next
    # request - so registering this as a response hook re-validates every
    # hop against the same host allowlist, not just the first one. This
    # mirrors, rather than reimports, the SSRFPreventionMiddleware pattern in
    # middleware/security.py: that middleware is a BaseHTTPMiddleware
    # subclass built to scan *inbound* request parameters against a
    # blocklist, so it is not directly reusable here, and its blocklist is
    # strictly weaker than the allowlist this scraper already enforces via
    # ALLOWED_HOSTS/_is_allowed_url (a scheme+host allowlist blocks every
    # non-parfumo.com destination outright, including hosts a blocklist
    # simply forgot to enumerate).
    # #VERIFY: covered by tests simulating a redirect to a disallowed host
    # (request aborted, not followed) and to an allowlisted host (followed
    # normally), including an end-to-end test through a real httpx.Client
    # with a mock transport.
    def _validate_response_redirect(self, response: httpx.Response) -> None:
        """Reject a redirect response whose target fails the host allowlist.

        Registered as an httpx ``"response"`` event hook (see `_get_client`)
        so it runs on every response in a redirect chain, not just the
        first request's response.

        Args:
            response (httpx.Response): The response httpx is about to
                inspect for a possible redirect.

        Raises:
            httpx.RequestError: If `response` is a redirect and its resolved
                target fails `_is_allowed_url`.
        """
        if not response.has_redirect_location:
            return

        location = str(response.headers.get("Location", ""))
        target = str(response.url.join(location))

        if not self._is_allowed_url(target):
            logger.warning(
                "Refusing to follow redirect outside host allowlist: %s -> %s",
                response.url,
                target,
            )
            error_message = f"Refused redirect to disallowed host: {target}"
            raise httpx.RequestError(error_message, request=response.request)

    def _wait_for_rate_limit(self) -> None:
        """Ensure we don't make requests too quickly.

        # #ASSUME: concurrency: `_last_request_time` is per-instance state,
        # not shared across ParfumoScraper instances/processes. This is
        # acceptable because the only callers (fragrance-rater CLI's
        # `import-data parfumo-url`/`parfumo-search` commands) construct a
        # single ParfumoScraper per process invocation and run it
        # single-threaded to completion before exiting; there is no
        # in-process concurrent scraping path today.
        # #VERIFY: if a future caller runs multiple ParfumoScraper instances
        # concurrently (e.g. a batch/worker process), replace this with a
        # shared/module-level rate limiter so REQUEST_DELAY is enforced
        # across instances, not just within one.
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _is_allowed_url(self, url: str) -> bool:
        """Check a URL against the outbound host allowlist.

        Args:
            url (str): URL to validate.

        Returns:
            bool: True if `url` uses https and its host is in
                `ALLOWED_HOSTS`, False otherwise.
        """
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and hostname in self.ALLOWED_HOSTS
            and parsed.username is None
            and parsed.password is None
        )

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        """Parse a numeric ``Retry-After`` header value into seconds.

        Args:
            value (str | None): Raw ``Retry-After`` header value.

        Returns:
            float | None: Seconds to wait, or None if `value` is missing or
                not a plain integer (HTTP-date forms are not supported; the
                caller falls back to exponential backoff in that case).
        """
        # #EDGE: external-resources: Retry-After may also be an HTTP-date
        # per RFC 9110; we only special-case the far more common delay-
        # seconds form here and fall back to our own backoff otherwise.
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _make_request(
        self, url: str, *, data: dict[str, str] | None = None
    ) -> BeautifulSoup | None:
        """Make an HTTP request and return parsed HTML.

        Args:
            url (str): URL to fetch.
            data (dict[str, str] | None): Form fields to POST. When None
                (the default), issues a GET instead. Only the livesearch
                endpoint (see `search()`) currently passes this.

        Returns:
            BeautifulSoup | None: Parsed BeautifulSoup object or None on
                failure, on a non-200/429/503 status, or when `url` fails
                the outbound host allowlist check.
        """
        if not self._is_allowed_url(url):
            logger.warning("Refusing to fetch URL outside host allowlist: %s", url)
            return None

        for attempt in range(self.MAX_RETRIES + 1):
            self._wait_for_rate_limit()

            try:
                client = self._get_client()
                response = (
                    client.post(url, data=data) if data is not None else client.get(url)
                )

                if response.status_code in (429, 503):
                    if attempt >= self.MAX_RETRIES:
                        logger.warning(
                            "Giving up on %s after repeated %s responses",
                            url,
                            response.status_code,
                        )
                        return None
                    delay = self._parse_retry_after(response.headers.get("Retry-After"))
                    if delay is None:
                        delay = self.BACKOFF_BASE_SECONDS * (2**attempt)
                    logger.info(
                        "Backing off %.1fs after %s response from %s",
                        delay,
                        response.status_code,
                        url,
                    )
                    time.sleep(delay)
                    continue

                if response.status_code != 200:
                    logger.warning(
                        "Parfumo returned HTTP %s for %s", response.status_code, url
                    )
                    return None

                return BeautifulSoup(response.text, "lxml")
            except httpx.HTTPError:
                # Log error but don't crash
                logger.exception("HTTP request failed for %s", url)
                return None

        return None

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search Parfumo for fragrances.

        # #CRITICAL: data-integrity: this is the disambiguation surface for
        # ADR-006's "no guessed fragrance concentration or version"
        # invariant. When a query matches multiple releases of the same
        # name (e.g. different concentrations, or a same-named-but-
        # unrelated reissue), every caller presenting these results to an
        # operator/manager MUST show `concentration` and `year` alongside
        # `name`/`brand` - not just name/brand/url - or two genuinely
        # different fragrances become indistinguishable in the UI. See
        # `cli.py`'s `import-data parfumo-search` for the reference
        # presentation. Do not auto-select a single "best" result when
        # more than one candidate shares the same `name`; that is exactly
        # the class of case (see docs/planning/evidence/
        # baseline-v3.1-parfumo-source-resolution.md's Caron Aimez-Moi
        # finding) where an automated pick can silently choose the wrong
        # release.
        # #VERIFY: covered by fixtures asserting concentration/year are
        # populated when Parfumo's markup provides them, and by the CLI
        # tests asserting both are displayed.

        Args:
            query (str): Search query (name, brand, or both).
            limit (int): Maximum results to return. A non-positive value
                returns an empty list without making a request.

        Returns:
            list[SearchResult]: List of search results, in Parfumo's own
                "popular" ranking order (not a relevance guarantee).
        """
        if limit <= 0:
            return []

        soup = self._make_request(
            self.LIVESEARCH_URL, data={"q": query, "o": "popular", "iwear": "0"}
        )
        if not soup:
            return []

        results: list[SearchResult] = []
        for item in soup.select(".ls-perfume-item"):
            if len(results) >= limit:
                break
            result = self._parse_livesearch_item(item)
            if result is not None and not any(r.url == result.url for r in results):
                results.append(result)

        return results

    def _parse_livesearch_item(self, item: Tag) -> SearchResult | None:
        """Parse one `.ls-perfume-item` card from a livesearch response.

        Args:
            item (Tag): The `.ls-perfume-item` element.

        Returns:
            SearchResult | None: Parsed result, or None if the card is
                missing a link or a name (malformed/unexpected markup).
        """
        link_elem = item.select_one("a.ls-perfume-overlay")
        href = link_elem.get("href") if link_elem else None
        if not isinstance(href, str) or not href:
            return None
        if not href.startswith("http"):
            href = f"{self.BASE_URL}{href}"

        name_elem = item.select_one(".name")
        if name_elem is None:
            return None
        # The concentration, when Parfumo shows one, is nested inside
        # `.name` itself (e.g. "Colonia <span class='label_a'> Eau de
        # Cologne</span>"); the release year is a *direct* child of
        # `.ls-perfume-info`, a sibling of `.name`/`.brand` rather than
        # nested in either. Conflating these two `.label_a` spans (via a
        # single non-scoped `.label_a` selector) previously misread the
        # concentration text as the year for any result that had one -
        # fixed by scoping each lookup to its own container.
        conc_elem = name_elem.select_one(".label_a")
        concentration = conc_elem.get_text(strip=True) if conc_elem else None

        name = name_elem.get_text(strip=True)
        if concentration and name.endswith(concentration):
            name = name[: -len(concentration)].strip()
        if not name:
            return None

        brand_elem = item.select_one(".ls-perfume-info > span.brand")
        brand = brand_elem.get_text(strip=True) if brand_elem else ""

        year_elem = item.select_one(".ls-perfume-info > span.label_a")
        year: int | None = None
        if year_elem:
            year_match = re.search(
                r"\b(1[89]|20)\d{2}\b", year_elem.get_text(strip=True)
            )
            if year_match:
                year = int(year_match.group())

        return SearchResult(
            name=name, brand=brand, url=href, year=year, concentration=concentration
        )

    def scrape_perfume_page(self, url: str) -> ScrapedFragrance | None:
        """Scrape detailed info from a perfume page.

        Args:
            url (str): Full URL to the perfume page.

        Returns:
            ScrapedFragrance | None: ScrapedFragrance with extracted data, or None on failure.
        """
        soup = self._make_request(url)

        if not soup:
            return None

        data = ScrapedFragrance(
            url=url,
            name="",
            brand="",
        )

        try:
            data.name = self._extract_name(soup)
            data.brand = self._extract_brand(soup, url)
            self._extract_notes(soup, data)
            self._extract_accords(soup, data)
            self._extract_rating(soup, data)
            self._extract_metrics(soup, data)
            data.production_status = self._extract_production_status(soup)
            self._extract_similar_fragrances(soup, data)
            data.gtin = self._extract_gtin(soup)
            data.gender = self._extract_gender(soup)
            data.year = self._extract_year(soup)
            data.perfumer = self._extract_perfumer(soup)
            data.perfumers = list(
                dict.fromkeys(
                    el.get_text(strip=True)
                    for el in soup.select("a[href*='/Perfumers/']")
                    if el.get_text(strip=True)
                )
            )
            title = soup.find("h1")
            data.display_title = title.get_text(" ", strip=True) if title else data.name
            title_text = data.display_title.lower()
            for label, value in [
                ("eau de parfum", "EDP"),
                ("eau de toilette", "EDT"),
                ("extrait de parfum", "Extrait"),
                ("eau de cologne", "EDC"),
            ]:
                if label in title_text:
                    data.concentration = value
                    break
            data.image_url = self._extract_image_url(soup)
        except Exception:
            # Page layout changes must degrade to "no data", not crash an import
            logger.exception("Scraping error for %s", url)

        return data if data.name else None

    def _extract_name(self, soup: BeautifulSoup) -> str:
        """Extract the perfume name.

        Args:
            soup (BeautifulSoup): Parsed HTML.

        Returns:
            str: Perfume name, or an empty string if none was found.
        """
        # Parfumo specific: the name is the text before the brand span in
        # h1.p_name_h1. NavigableString has name=None, Tag has name='span' etc.
        name_elem = soup.select_one("h1.p_name_h1")
        if name_elem:
            for child in name_elem.children:
                if getattr(child, "name", None) is not None:
                    break  # Stop at first actual tag
                text = str(child).strip()
                if text:
                    return text

        # Fallback: try generic selectors
        name_elem = soup.select_one("h1, .perfume-title, [itemprop='name']")
        return name_elem.get_text(strip=True) if name_elem else ""

    def _extract_brand(self, soup: BeautifulSoup, url: str) -> str:
        """Extract the brand name.

        Args:
            soup (BeautifulSoup): Parsed HTML.
            url (str): Page URL, used as a last-resort source for the brand.

        Returns:
            str: Brand name, or an empty string if none was found.
        """
        # Parfumo specific: span.p_brand_name, sometimes with a trailing year
        # (e.g., "Polysnifferous2024" -> "Polysnifferous")
        brand_elem = soup.select_one("span.p_brand_name")
        if brand_elem:
            brand = re.sub(r"\d{4}$", "", brand_elem.get_text(strip=True)).strip()
            if brand:
                return brand

        # Fallback brand extraction
        brand_elem = soup.select_one(
            "a[href*='/Brands/'], .brand-name, [itemprop='brand']"
        )
        if brand_elem:
            brand = brand_elem.get_text(strip=True)
            if brand:
                return brand

        # Extract from URL if not found: /Perfumes/brand/perfume-name
        path_parts = url.split("/")
        if len(path_parts) >= 4:
            return path_parts[-2].replace("-", " ").replace("_", " ").title()
        return ""

    def _extract_rating(self, soup: BeautifulSoup, data: ScrapedFragrance) -> None:
        """Extract the community rating and vote count.

        # #CRITICAL: data-integrity: the live block (verified against
        # Creed Aventus and Chanel Bleu de Chanel, 2026-09-12) nests the
        # score and vote count in their own child elements
        # (`.text-lg.bold` / `.text-2xs.upper`) alongside other label
        # text, e.g. "Scent" + "8.4" + "8586 Ratings" as sibling text
        # nodes. Reading `rating_elem.get_text(strip=True)` on the whole
        # block concatenates them with no separator ("Scent8.48586
        # Ratings"), so the plain digit regex below can fuse the score
        # and count into one bogus number ("8.48586"). The scoped
        # `.text-lg.bold`/`.text-2xs.upper` lookup is tried first; the
        # flatter whole-block regex remains only as a fallback for markup
        # that has no such scoped elements (e.g. a single flat text node).
        # #VERIFY: covered by a fixture using the real nested block shape
        # (asserting the correct, non-fused rating) and by the original
        # flat-text fixture (asserting the fallback still parses it).

        Args:
            soup (BeautifulSoup): Parsed HTML.
            data (ScrapedFragrance): ScrapedFragrance to populate.
        """
        # Parfumo specific, e.g. "Scent8.35 Ratings" in .barfiller_element
        rating_elem = soup.select_one(".barfiller_element.rating-details")
        if rating_elem:
            self._extract_scoped_rating(rating_elem, data)
            if data.rating is None:
                self._extract_flat_rating(rating_elem, data)

        if data.rating:
            return

        # Fallback rating extraction
        fallback_elem = soup.select_one(
            ".rating-value, [itemprop='ratingValue'], .score"
        )
        if fallback_elem:
            match = re.search(r"(\d+\.?\d*)", fallback_elem.get_text(strip=True))
            if match:
                rating = float(match.group(1))
                data.rating = rating / 10 if rating > 10 else rating

    @staticmethod
    def _extract_scoped_rating(rating_elem: Tag, data: ScrapedFragrance) -> None:
        """Read the score/count from their own scoped child elements.

        Preferred over `_extract_flat_rating` because it can't fuse the
        score and vote count together (see `_extract_rating`'s docstring).
        """
        score_elem = rating_elem.select_one(".text-lg.bold")
        if score_elem:
            match = re.search(r"(\d+\.?\d*)", score_elem.get_text(strip=True))
            if match:
                data.rating = float(match.group(1))

        count_elem = rating_elem.select_one(".text-2xs.upper")
        if count_elem:
            count_text = count_elem.get_text(strip=True).replace(",", "")
            count_match = re.search(r"(\d+)", count_text)
            if count_match:
                data.rating_count = int(count_match.group(1))

    @staticmethod
    def _extract_flat_rating(rating_elem: Tag, data: ScrapedFragrance) -> None:
        """Fall back to the whole block's concatenated text.

        Only used when `_extract_scoped_rating` found no scoped score
        element, i.e. markup with a single flat text node such as
        "Scent8.55 Ratings" and no nested `.text-lg.bold`/`.text-2xs.upper`
        children.
        """
        rating_text = rating_elem.get_text(strip=True)
        match = re.search(r"(\d+\.?\d*)", rating_text)
        if match:
            data.rating = float(match.group(1))

        count_match = re.search(r"(\d+)\s*Rating", rating_text)
        if count_match:
            data.rating_count = int(count_match.group(1))

    def _extract_metrics(self, soup: BeautifulSoup, data: ScrapedFragrance) -> None:
        """Extract the per-dimension community ratings.

        The overall score `_extract_rating` reads (Scent) is one of
        several sibling `.barfiller_element.rating-details` blocks, each
        tagged with a `data-type` attribute (scent/durability/sillage/
        bottle/pricing per `METRIC_TYPE_LABELS`) and carrying its own
        average score (`.text-lg.bold`) and vote count (`.text-2xs.upper`,
        e.g. "8586 Ratings"). An unrecognized or malformed block is
        skipped rather than guessed.

        Args:
            soup (BeautifulSoup): Parsed HTML.
            data (ScrapedFragrance): ScrapedFragrance to populate.
        """
        for block in soup.select(".barfiller_element.rating-details[data-type]"):
            raw_type = block.get("data-type")
            if not isinstance(raw_type, str):
                continue
            label = self.METRIC_TYPE_LABELS.get(raw_type.lower())
            if not label:
                continue

            score_elem = block.select_one(".text-lg.bold")
            if score_elem:
                match = re.search(r"(\d+\.?\d*)", score_elem.get_text(strip=True))
                if match:
                    data.metrics[label] = float(match.group(1))

            count_elem = block.select_one(".text-2xs.upper")
            if count_elem:
                count_text = count_elem.get_text(strip=True).replace(",", "")
                count_match = re.search(r"(\d+)", count_text)
                if count_match:
                    data.metric_vote_counts[label] = int(count_match.group(1))

    def _extract_production_status(self, soup: BeautifulSoup) -> str | None:
        """Infer production status from the page's descriptive sentence.

        Parfumo does not expose production status as a discrete field; it
        appears as a plain-language sentence inside the perfume
        description (e.g. "It is still in production." or "It is no
        longer in production."). Only those recognized phrasings are
        mapped; anything else - a redesigned sentence, a different
        language - returns None rather than guessing, matching this
        project's "unknown stays unknown" policy for scraped facts.

        Args:
            soup (BeautifulSoup): Parsed HTML.

        Returns:
            str | None: "in_production", "discontinued", or None if the
                description is missing or uses unrecognized phrasing.
        """
        description = soup.select_one("[itemprop='description']")
        if description is None:
            return None

        # #EDGE: external-resources: collapse internal whitespace (line
        # wraps/indentation in the source HTML around the sentence) before
        # matching, so a phrase split across a source line break - "no
        # longer in\n    production" - still matches as one phrase.
        raw_text = description.get_text(" ", strip=True)
        text = " ".join(raw_text.split()).lower()
        if "no longer in production" in text or "discontinued" in text:
            return "discontinued"
        if "still in production" in text:
            return "in_production"
        return None

    def _extract_similar_fragrances(
        self, soup: BeautifulSoup, data: ScrapedFragrance
    ) -> None:
        """Extract the sidebar "Also liked" recommendations.

        The in-page "Smells similar" widget (`#sim_wrapper .sim_item`) is
        driven entirely by `data-p_id`/`data-s_id` attributes with no
        navigable `href`, so it cannot be resolved to a fragrance URL from
        static HTML and is intentionally not read here (see the
        `similar_fragrances` field docstring). The sidebar "Also liked"
        list uses real anchors instead, so it is the source used.

        Args:
            soup (BeautifulSoup): Parsed HTML.
            data (ScrapedFragrance): ScrapedFragrance to populate.
        """
        heading = soup.find(
            lambda tag: (
                tag.name in {"div", "h2", "h3"}
                and len(tag.get_text(strip=True)) < 40
                and tag.get_text(strip=True).lower() == "also liked"
            )
        )
        if heading is None:
            return

        # The links live a couple of siblings past the heading (a
        # "Users who like ... often also like" caption sits between them
        # on the live layout); scan forward rather than assuming an exact
        # sibling offset so a minor layout shift doesn't silently break
        # extraction.
        container = None
        for sibling in heading.find_next_siblings(name=True, limit=4):
            if sibling.select_one("a[href*='/Perfumes/'] img[alt]"):
                container = sibling
                break
        if container is None:
            return

        for link in container.select("a[href*='/Perfumes/']")[:12]:
            href = link.get("href")
            img = link.select_one("img[alt]")
            if not isinstance(href, str) or not href or img is None:
                continue
            alt = img.get("alt")
            if not isinstance(alt, str) or not alt.strip():
                continue

            name, _, brand = alt.partition(" by ")
            name = name.strip()
            if not name:
                continue
            entry = {"name": name, "url": href}
            if brand.strip():
                entry["brand"] = brand.strip()
            data.similar_fragrances.append(entry)

    def _extract_gtin(self, soup: BeautifulSoup) -> str | None:
        """Extract the manufacturer-assigned barcode, if Parfumo publishes one.

        Args:
            soup (BeautifulSoup): Parsed HTML.

        Returns:
            str | None: A validated GTIN, or None if the page carries no
                `gtin13` meta tag or its value fails the GS1 check digit
                (never a value the caller would have to re-validate).
        """
        gtin_elem = soup.select_one("meta[itemprop='gtin13']")
        if gtin_elem is None:
            return None
        value = gtin_elem.get("content")
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value if is_valid_gtin(value) else None

    def _extract_gender(self, soup: BeautifulSoup) -> str | None:
        """Infer the target gender from the page text.

        Args:
            soup (BeautifulSoup): Parsed HTML.

        Returns:
            str | None: "unisex", "feminine" or "masculine", or None if unknown.
        """
        gender_text = soup.get_text().lower()
        if "for women and men" in gender_text or "unisex" in gender_text:
            return "unisex"
        if "for women" in gender_text:
            return "feminine"
        if "for men" in gender_text:
            return "masculine"
        return None

    def _extract_year(self, soup: BeautifulSoup) -> int | None:
        """Extract the launch year.

        Args:
            soup (BeautifulSoup): Parsed HTML.

        Returns:
            int | None: Four-digit year, or None if none was found.
        """
        year_elem = soup.find(string=re.compile(r"\b(19|20)\d{2}\b"))
        if year_elem:
            year_match = re.search(r"\b(19|20)(\d{2})\b", str(year_elem))
            if year_match:
                return int(year_match.group())
        return None

    def _extract_perfumer(self, soup: BeautifulSoup) -> str | None:
        """Extract the perfumer attribution.

        Args:
            soup (BeautifulSoup): Parsed HTML.

        Returns:
            str | None: Perfumer name, or None if none was found.
        """
        perfumer_elem = soup.select_one(
            "a[href*='/Perfumers/'], .perfumer, [itemprop='creator']"
        )
        return perfumer_elem.get_text(strip=True) if perfumer_elem else None

    def _extract_image_url(self, soup: BeautifulSoup) -> str | None:
        """Extract the bottle image URL.

        Args:
            soup (BeautifulSoup): Parsed HTML.

        Returns:
            str | None: Image URL from src or data-src, or None if none was found.
        """
        img_elem = soup.select_one(
            "img[itemprop='image'], .perfume-image img, .bottle-image"
        )
        if img_elem is None:
            return None
        for attr in ("src", "data-src"):
            value = img_elem.get(attr)
            if isinstance(value, str) and value:
                return value
        return None

    def _extract_notes(self, soup: BeautifulSoup, data: ScrapedFragrance) -> None:
        """Extract notes from the fragrance pyramid.

        Args:
            soup (BeautifulSoup): Parsed HTML.
            data (ScrapedFragrance): ScrapedFragrance to populate.
        """
        # Parfumo-specific: Look for pyramid blocks with nb_t, nb_m, nb_b classes
        # .pyramid_block.nb_t = Top Notes
        # .pyramid_block.nb_m = Heart/Middle Notes
        # .pyramid_block.nb_b = Base Notes

        # Method 1: Parfumo-specific pyramid blocks
        top_block = soup.select_one(".pyramid_block.nb_t")
        if top_block:
            note_spans = top_block.select("span.pointer")
            data.top_notes = [
                n.get_text(strip=True) for n in note_spans if n.get_text(strip=True)
            ]

        heart_block = soup.select_one(".pyramid_block.nb_m")
        if heart_block:
            note_spans = heart_block.select("span.pointer")
            data.heart_notes = [
                n.get_text(strip=True) for n in note_spans if n.get_text(strip=True)
            ]

        base_block = soup.select_one(".pyramid_block.nb_b")
        if base_block:
            note_spans = base_block.select("span.pointer")
            data.base_notes = [
                n.get_text(strip=True) for n in note_spans if n.get_text(strip=True)
            ]

        # Method 2: Fallback - look for labeled sections
        if not any([data.top_notes, data.heart_notes, data.base_notes]):
            sections = soup.select("[class*='note'], [class*='pyramid'], .ingredients")

            for section in sections:
                section_text = section.get_text().lower()
                note_links = section.select(
                    "a[href*='/Notes/'], .note-name, .ingredient, span.pointer"
                )
                notes = [
                    n.get_text(strip=True) for n in note_links if n.get_text(strip=True)
                ]

                if (
                    "top" in section_text
                    or "head" in section_text
                    or "kopfnote" in section_text
                ):
                    data.top_notes.extend(notes)
                elif (
                    "heart" in section_text
                    or "middle" in section_text
                    or "herznote" in section_text
                ):
                    data.heart_notes.extend(notes)
                elif (
                    "base" in section_text
                    or "fond" in section_text
                    or "basisnote" in section_text
                ):
                    data.base_notes.extend(notes)

        # Method 3: If still no notes, look for any note links
        if not any([data.top_notes, data.heart_notes, data.base_notes]):
            all_notes = soup.select("a[href*='/Notes/'], span.pointer")
            data.flat_notes = list(
                {n.get_text(strip=True) for n in all_notes if n.get_text(strip=True)}
            )

        # Deduplicate
        data.top_notes = list(dict.fromkeys(data.top_notes))
        data.heart_notes = list(dict.fromkeys(data.heart_notes))
        data.base_notes = list(dict.fromkeys(data.base_notes))

    def _extract_accords(self, soup: BeautifulSoup, data: ScrapedFragrance) -> None:
        """Extract accords/scent profile.

        Args:
            soup (BeautifulSoup): Parsed HTML.
            data (ScrapedFragrance): ScrapedFragrance to populate.
        """
        # Parfumo shows accords with visual bars indicating strength
        accord_elements = soup.select(".accord, .scent-profile .bar, [class*='accord']")

        for elem in accord_elements:
            try:
                # Get accord name
                name_elem = elem.select_one(".name, .label, span")
                if name_elem:
                    accord_name = name_elem.get_text(strip=True).lower()
                else:
                    accord_name = elem.get_text(strip=True).lower()

                if not accord_name or len(accord_name) > 50:
                    continue

                # Try to get strength from width style or data attribute
                style = elem.get("style")
                width_match = (
                    re.search(r"width:\s*(\d+)", style)
                    if isinstance(style, str)
                    else None
                )

                if width_match:
                    weight = float(width_match.group(1)) / 100
                else:
                    # Check for data-value or similar, defaulting to 0.5
                    data_val = elem.get("data-value") or elem.get("data-width")
                    weight = (
                        float(data_val) / 100
                        if isinstance(data_val, str) and data_val
                        else 0.5
                    )

                # Clamp to 0-1
                weight = max(0.0, min(1.0, weight))

                if accord_name and accord_name not in data.accords:
                    data.accords[accord_name] = weight

            except (ValueError, AttributeError):
                continue

    async def search_and_import(
        self,
        name: str,
        brand: str | None = None,
    ) -> str | None:
        """Search Parfumo and import the best match.

        # #CRITICAL: data-integrity: this silently picks one candidate
        # (brand match, else name match, else the first result) with no
        # human confirmation and no visibility into `concentration`/
        # `year` - exactly the class of decision ADR-006's "no guessed
        # fragrance concentration or version" invariant exists to
        # prevent (see the Caron Aimez-Moi finding in docs/planning/
        # evidence/baseline-v3.1-parfumo-source-resolution.md, where the
        # same name matched several distinct releases). This method has
        # no production caller today (CLI's `parfumo-search` command
        # uses `search()` + `import_from_url()` directly so an operator
        # reviews concentration/year before choosing a URL); do not wire
        # it into an API route or background job for calibration-
        # critical catalog entries without adding the same human-
        # confirmation step first.
        # #VERIFY: if this gains a caller, add a test asserting it
        # refuses to auto-pick when multiple results share `name`.

        Args:
            name (str): Fragrance name to search for.
            brand (str | None): Optional brand to filter results.

        Returns:
            str | None: Fragrance ID if imported/found, None otherwise.
        """
        query = f"{name} {brand}" if brand else name
        # #ASSUME: concurrency: search()/scrape_perfume_page() are
        # synchronous (a blocking httpx.Client, plus time.sleep()-based
        # rate limiting and retry backoff up to
        # BACKOFF_BASE_SECONDS * 2**attempt per attempt). Calling them
        # directly from this async method would run all of that blocking
        # I/O on the event loop thread. asyncio.to_thread offloads each
        # call to the default thread pool executor so the loop stays free
        # while the request/backoff runs. This is safe today because the
        # only caller of ParfumoScraper is the one-shot CLI
        # (fragrance-rater import-data parfumo-*), which awaits a single
        # scraper method per process invocation with no other concurrent
        # async work sharing the loop.
        # #VERIFY: if ParfumoScraper is ever called from a live server
        # process (e.g. a FastAPI route) where other requests share the
        # event loop, confirm the thread-pool offload here (and in
        # import_from_url/cli.py) is still sufficient, or migrate to an
        # httpx.AsyncClient-based implementation instead.
        results = await asyncio.to_thread(self.search, query, limit=5)

        if not results:
            return None

        # Find best match
        best_match: SearchResult | None = None
        for result in results:
            if brand and brand.lower() in result.brand.lower():
                best_match = result
                break
            if name.lower() in result.name.lower():
                best_match = result
                break

        if not best_match:
            best_match = results[0]

        # Scrape full details (see #ASSUME above: offloaded to a thread so
        # this blocking call doesn't stall the event loop).
        scraped = await asyncio.to_thread(self.scrape_perfume_page, best_match.url)

        if not scraped or not scraped.name:
            return None

        final_name = scraped.name or best_match.name
        final_brand = scraped.brand or best_match.brand

        if not final_name or not final_brand:
            return None

        # Check if fragrance already exists
        # Critical finding 2: soft-delete filter.
        stmt = (
            select(Fragrance)
            .where(
                Fragrance.parfumo_url == scraped.url,
                Fragrance.deleted_at.is_(None),
            )
            .order_by(Fragrance.created_at, Fragrance.id)
        )
        result = await self.db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            # Update with scraped data
            await self._update_fragrance(existing, scraped)
            return existing.id

        # Create new fragrance
        return await self._create_fragrance(scraped, final_name, final_brand)

    async def import_from_url(self, url: str) -> str | None:
        """Import a fragrance directly from its Parfumo URL.

        Args:
            url (str): Full Parfumo URL (e.g., https://www.parfumo.com/Perfumes/brand/name)

        Returns:
            str | None: Fragrance ID if imported, None on failure.
        """
        # #ASSUME: concurrency: see search_and_import() above for the full
        # rationale - scrape_perfume_page() is a blocking sync call (httpx
        # + time.sleep()-based rate limiting/backoff), offloaded via
        # asyncio.to_thread so this async method doesn't stall the event
        # loop. Safe today because the only caller is the one-shot CLI.
        # #VERIFY: re-examine before calling ParfumoScraper from a live
        # server route sharing an event loop with other requests.
        scraped = await asyncio.to_thread(self.scrape_perfume_page, url)

        if not scraped or not scraped.name or not scraped.brand:
            return None

        # Check if exists
        # Critical finding 2: soft-delete filter.
        stmt = (
            select(Fragrance)
            .where(
                Fragrance.parfumo_url == scraped.url,
                Fragrance.deleted_at.is_(None),
            )
            .order_by(Fragrance.created_at, Fragrance.id)
        )
        result = await self.db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            await self._update_fragrance(existing, scraped)
            return existing.id

        return await self._create_fragrance(scraped, scraped.name, scraped.brand)

    async def _create_fragrance(
        self,
        scraped: ScrapedFragrance,
        name: str,
        brand: str,
    ) -> str:
        """Create a new fragrance from scraped data.

        Args:
            scraped (ScrapedFragrance): Scraped fragrance data.
            name (str): Fragrance name.
            brand (str): Brand name.

        Returns:
            str: New fragrance ID.
        """
        # #CRITICAL: data-integrity: gender_target must use the same
        # capitalized vocabulary (Masculine/Feminine/Unisex) as the Kaggle
        # importer and the API's gender_target filter schema (see
        # core/vocabulary.py, Major finding 5). _extract_gender() returns
        # lowercase values scraped from page text; map them to the
        # canonical form here rather than storing the lowercase form
        # directly, or gender_target filtering silently excludes every
        # fragrance imported through this scraper.
        # #VERIFY: covered by a scraper test asserting the stored value is
        # always a member of GENDER_TARGETS.
        gender_map: dict[str, GenderTarget] = {
            "feminine": "Feminine",
            "masculine": "Masculine",
            "unisex": "Unisex",
        }

        fragrance = Fragrance(
            id=str(uuid.uuid4()),
            name=name,
            brand=brand,
            concentration=scraped.concentration or "Unknown",
            version_key=self._version_key(scraped.url),
            gender_target=gender_map.get(scraped.gender or "", "Unisex"),
            launch_year=scraped.year,
            primary_family=self._infer_family(scraped),
            # Left empty rather than duplicating primary_family: an empty
            # subfamily is treated as "unknown" by
            # RecommendationService.build_preference_profile (Major
            # finding 6), which is the correct semantics here since this
            # scraper does not currently extract a real subfamily.
            subfamily="",
            data_source="parfumo",
            parfumo_url=scraped.url,
        )

        self.db.add(fragrance)
        await self.db.flush()

        await self._save_source(fragrance.id, scraped)
        # Add notes
        await self._add_notes(fragrance.id, scraped)

        # Add accords
        for accord_name, intensity in scraped.accords.items():
            accord = FragranceAccord(
                fragrance_id=fragrance.id,
                accord_type=accord_name,
                intensity=intensity,
            )
            self.db.add(accord)

        await self.db.commit()
        return fragrance.id

    @staticmethod
    def _version_key(url: str) -> str:
        """Build a readable, bounded key with full-URL collision resistance."""
        url_tail = url.rsplit("/", 1)[-1]
        url_digest = hashlib.sha256(url.encode(), usedforsecurity=False).hexdigest()[
            :16
        ]
        return f"parfumo:{url_tail[:174]}:{url_digest}"

    async def _update_fragrance(
        self,
        fragrance: Fragrance,
        scraped: ScrapedFragrance,
    ) -> None:
        """Update existing fragrance with scraped data.

        Args:
            fragrance (Fragrance): Existing fragrance to update.
            scraped (ScrapedFragrance): Scraped data.
        """
        # Update basic fields if not set
        await self.db.execute(
            select(Fragrance.id).where(Fragrance.id == fragrance.id).with_for_update()
        )
        assigned = await self.db.scalar(
            select(Membership.id).where(Membership.fragrance_id == fragrance.id)
        )
        if not assigned and not fragrance.launch_year and scraped.year:
            fragrance.launch_year = scraped.year

        if not fragrance.parfumo_url:
            fragrance.parfumo_url = scraped.url

        await self._save_source(fragrance.id, scraped)
        # Note: We don't overwrite existing notes/accords
        # to preserve user's data integrity

        await self.db.commit()

    async def _save_source(self, fragrance_id: str, scraped: ScrapedFragrance) -> None:
        """Append source evidence and preserve every perfumer attribution."""
        self.db.add(
            SourceSnapshot(
                fragrance_id=fragrance_id,
                source_url=scraped.url,
                payload=asdict(scraped),
            )
        )
        names = scraped.perfumers or ([scraped.perfumer] if scraped.perfumer else [])
        for name in names:
            perfumer = await self.db.scalar(
                select(Perfumer).where(Perfumer.name == name)
            )
            if perfumer is None:
                try:
                    async with self.db.begin_nested():
                        perfumer = Perfumer(name=name)
                        self.db.add(perfumer)
                        await self.db.flush()
                except IntegrityError:
                    perfumer = await self.db.scalar(
                        select(Perfumer).where(Perfumer.name == name)
                    )
            if perfumer is None:
                msg = f"Perfumer {name!r} was not readable after insert conflict"
                raise RuntimeError(msg)
            link = await self.db.get(VersionPerfumer, (fragrance_id, perfumer.id))
            if link is None:
                try:
                    async with self.db.begin_nested():
                        self.db.add(
                            VersionPerfumer(
                                fragrance_id=fragrance_id,
                                perfumer_id=perfumer.id,
                                source_url=scraped.url,
                            )
                        )
                        await self.db.flush()
                except IntegrityError:
                    logger.info(
                        "Perfumer attribution already exists: fragrance_id=%s perfumer=%r",
                        fragrance_id,
                        name,
                    )
        await self.db.flush()

    async def _add_notes(self, fragrance_id: str, scraped: ScrapedFragrance) -> None:
        """Add notes to fragrance.

        Args:
            fragrance_id (str): Fragrance ID.
            scraped (ScrapedFragrance): Scraped data with notes.
        """
        note_types = [
            ("top", scraped.top_notes),
            ("heart", scraped.heart_notes),
            ("flat", scraped.flat_notes),
            ("base", scraped.base_notes),
        ]

        for note_type, note_names in note_types:
            for note_name in note_names:
                # Get or create note
                stmt = select(Note).where(Note.name == note_name)
                result = await self.db.execute(stmt)
                note = result.scalar_one_or_none()

                if not note:
                    note = Note(
                        id=str(uuid.uuid4()),
                        name=note_name,
                        category=self._categorize_note(note_name),
                    )
                    self.db.add(note)
                    await self.db.flush()

                await self._add_fragrance_note(
                    fragrance_id, note.id, note_type, note_name
                )

    # #CRITICAL: concurrency: a duplicate (fragrance_id, note_id, position)
    # triple - e.g. the same note listed twice in the same pyramid section
    # on the scraped page - raises IntegrityError against the
    # UNIQUE(fragrance_id, note_id, position) constraint. Without per-row
    # isolation that error poisons the whole session (PendingRollbackError)
    # and would abort the rest of this fragrance's notes and accords, not
    # just the offending note.
    # #VERIFY: session.begin_nested() opens a SAVEPOINT scoped to just this
    # insert; only that SAVEPOINT rolls back on conflict, so the outer
    # session stays usable for the remaining notes and the accords added
    # right after _add_notes returns. Covered by a regression test
    # importing a note that legitimately appears in two different
    # positions (allowed) and by a same-position duplicate (skipped, not
    # fatal).
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
            async with self.db.begin_nested():
                self.db.add(
                    FragranceNote(
                        fragrance_id=fragrance_id, note_id=note_id, position=position
                    )
                )
                await self.db.flush()
        except IntegrityError:
            logger.warning(
                "Skipping duplicate fragrance note: fragrance_id=%s note=%r position=%s",
                fragrance_id,
                note_name,
                position,
            )

    def _infer_family(self, scraped: ScrapedFragrance) -> str:
        """Infer fragrance family from accords and notes.

        Args:
            scraped (ScrapedFragrance): Scraped fragrance data.

        Returns:
            str: Best guess at fragrance family.
        """
        # Common family keywords
        families = {
            "woody": ["wood", "cedar", "sandalwood", "oud", "vetiver", "patchouli"],
            "floral": ["rose", "jasmine", "lily", "violet", "tuberose", "peony"],
            "oriental": ["vanilla", "amber", "musk", "incense", "spice"],
            "fresh": ["citrus", "bergamot", "lemon", "grapefruit", "aquatic", "marine"],
            "aromatic": ["lavender", "sage", "rosemary", "herbs"],
            "gourmand": ["caramel", "chocolate", "coffee", "honey", "sugar"],
            "leather": ["leather", "suede", "tobacco"],
            "chypre": ["oakmoss", "bergamot", "labdanum"],
            "fougere": ["lavender", "coumarin", "oakmoss", "fern"],
        }

        # Check accords first
        for family, keywords in families.items():
            for keyword in keywords:
                if any(keyword in acc for acc in scraped.accords):
                    return family

        # Check all notes
        all_notes = (
            scraped.top_notes
            + scraped.heart_notes
            + scraped.flat_notes
            + scraped.base_notes
        )
        all_notes_lower = [n.lower() for n in all_notes]

        for family, keywords in families.items():
            for keyword in keywords:
                if any(keyword in note for note in all_notes_lower):
                    return family

        return "unknown"

    def _categorize_note(self, note_name: str) -> str:
        """Categorize a note.

        Args:
            note_name (str): Name of the note.

        Returns:
            str: Category string.
        """
        note_lower = note_name.lower()

        categories = {
            "citrus": ["bergamot", "lemon", "orange", "grapefruit", "lime", "mandarin"],
            "floral": [
                "rose",
                "jasmine",
                "lily",
                "violet",
                "iris",
                "peony",
                "tuberose",
            ],
            "woody": ["cedar", "sandalwood", "oud", "vetiver", "birch", "guaiac"],
            "spicy": ["pepper", "cinnamon", "cardamom", "clove", "ginger", "saffron"],
            "fruity": [
                "apple",
                "peach",
                "pear",
                "berry",
                "plum",
                "cherry",
                "pineapple",
            ],
            "green": ["grass", "leaf", "galbanum", "basil", "mint", "tea"],
            "balsamic": ["vanilla", "benzoin", "tonka", "labdanum", "peru balsam"],
            "animalic": ["musk", "civet", "castoreum", "ambergris", "leather"],
            "aromatic": ["lavender", "sage", "rosemary", "thyme", "artemisia"],
            "aquatic": ["marine", "sea", "ocean", "water", "ozone"],
        }

        for category, keywords in categories.items():
            if any(kw in note_lower for kw in keywords):
                return category

        return "other"

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


def get_parfumo_scraper(session: AsyncSession) -> ParfumoScraper:
    """Factory function to get a ParfumoScraper instance.

    Args:
        session (AsyncSession): Async database session.

    Returns:
        ParfumoScraper: ParfumoScraper instance.
    """
    return ParfumoScraper(session)
