"""Parfumo.com web scraper for fragrance data.

Used as an additional data source alongside Kaggle CSV imports.
Parfumo has excellent note taxonomy and community ratings.

NOTE: Web scraping should be done responsibly with appropriate delays.
Parfumo uses Cloudflare protection - be respectful of their resources.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import quote_plus, urlsplit

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)

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
    top_notes: list[str] = field(default_factory=list)
    heart_notes: list[str] = field(default_factory=list)
    base_notes: list[str] = field(default_factory=list)
    accords: dict[str, float] = field(default_factory=dict)
    rating: float | None = None
    rating_count: int = 0
    gender: str | None = None
    year: int | None = None
    perfumer: str | None = None
    concentration: str | None = None
    image_url: str | None = None


@dataclass
class SearchResult:
    """A search result from Parfumo."""

    name: str
    brand: str
    url: str
    year: int | None = None


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
        SEARCH_URL: Perfume search endpoint.
        ALLOWED_HOSTS (ClassVar[frozenset[str]]): Outbound host allowlist;
            requests to any other host are refused before being sent.
        REQUEST_DELAY: Minimum seconds between requests.
        MAX_RETRIES: Maximum retry attempts on a 429/503 response.
        BACKOFF_BASE_SECONDS: Base delay for exponential backoff between
            retries when the response carries no ``Retry-After`` header.
        HEADERS (ClassVar[dict[str, str]]): Browser-like request headers.
    """

    BASE_URL = "https://www.parfumo.com"
    SEARCH_URL = f"{BASE_URL}/s_perfumes.php"

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
            )
        return self._client

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
        return parsed.scheme == "https" and hostname in self.ALLOWED_HOSTS

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

    def _make_request(self, url: str) -> BeautifulSoup | None:
        """Make HTTP request and return parsed HTML.

        Args:
            url (str): URL to fetch.

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
                response = client.get(url)

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
                    return None

                return BeautifulSoup(response.text, "lxml")
            except httpx.HTTPError:
                # Log error but don't crash
                logger.exception("HTTP request failed for %s", url)
                return None

        return None

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search Parfumo for fragrances.

        Args:
            query (str): Search query (name, brand, or both).
            limit (int): Maximum results to return.

        Returns:
            list[SearchResult]: List of search results.
        """
        search_url = f"{self.SEARCH_URL}?keywords={quote_plus(query)}"
        soup = self._make_request(search_url)

        if not soup:
            return []

        results: list[SearchResult] = []

        # Parfumo search results are in a list/grid of perfume cards
        # Look for links to perfume pages
        for item in soup.select("a[href*='/Perfumes/']")[:limit]:
            try:
                href = item.get("href")
                if not isinstance(href, str) or not href:
                    continue

                # Normalize URL
                if not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                # Skip if it's not a perfume detail page
                # Parfumo URLs: /Perfumes/brand/perfume-name
                path_parts = href.replace(self.BASE_URL, "").split("/")
                if len(path_parts) < 4:
                    continue

                # Try to extract name from link text or nearby elements
                name = item.get_text(strip=True)
                brand = path_parts[2] if len(path_parts) > 2 else ""

                # Clean up brand name (URL encoded)
                brand = brand.replace("-", " ").replace("_", " ").title()

                # Avoid duplicates
                if name and not any(r.url == href for r in results):
                    results.append(
                        SearchResult(
                            name=name,
                            brand=brand,
                            url=href,
                        )
                    )

            except (AttributeError, IndexError):
                continue

        return results[:limit]

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
            data.gender = self._extract_gender(soup)
            data.year = self._extract_year(soup)
            data.perfumer = self._extract_perfumer(soup)
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

        Args:
            soup (BeautifulSoup): Parsed HTML.
            data (ScrapedFragrance): ScrapedFragrance to populate.
        """
        # Parfumo specific, e.g. "Scent8.35 Ratings" in .barfiller_element
        rating_elem = soup.select_one(".barfiller_element.rating-details")
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                data.rating = float(match.group(1))

            count_match = re.search(r"(\d+)\s*Rating", rating_text)
            if count_match:
                data.rating_count = int(count_match.group(1))

        if data.rating:
            return

        # Fallback rating extraction
        rating_elem = soup.select_one(".rating-value, [itemprop='ratingValue'], .score")
        if rating_elem:
            match = re.search(r"(\d+\.?\d*)", rating_elem.get_text(strip=True))
            if match:
                rating = float(match.group(1))
                data.rating = rating / 10 if rating > 10 else rating

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
            data.heart_notes = list(
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

        Args:
            name (str): Fragrance name to search for.
            brand (str | None): Optional brand to filter results.

        Returns:
            str | None: Fragrance ID if imported/found, None otherwise.
        """
        query = f"{name} {brand}" if brand else name
        results = self.search(query, limit=5)

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

        # Scrape full details
        scraped = self.scrape_perfume_page(best_match.url)

        if not scraped or not scraped.name:
            return None

        final_name = scraped.name or best_match.name
        final_brand = scraped.brand or best_match.brand

        if not final_name or not final_brand:
            return None

        # Check if fragrance already exists
        # Critical finding 2: soft-delete filter.
        stmt = select(Fragrance).where(
            Fragrance.name == final_name,
            Fragrance.brand == final_brand,
            Fragrance.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

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
        scraped = self.scrape_perfume_page(url)

        if not scraped or not scraped.name or not scraped.brand:
            return None

        # Check if exists
        # Critical finding 2: soft-delete filter.
        stmt = select(Fragrance).where(
            Fragrance.name == scraped.name,
            Fragrance.brand == scraped.brand,
            Fragrance.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

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
            concentration=scraped.concentration or "EDP",
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
        if not fragrance.launch_year and scraped.year:
            fragrance.launch_year = scraped.year

        if not fragrance.parfumo_url:
            fragrance.parfumo_url = scraped.url

        # Note: We don't overwrite existing notes/accords
        # to preserve user's data integrity

        await self.db.commit()

    async def _add_notes(self, fragrance_id: str, scraped: ScrapedFragrance) -> None:
        """Add notes to fragrance.

        Args:
            fragrance_id (str): Fragrance ID.
            scraped (ScrapedFragrance): Scraped data with notes.
        """
        note_types = [
            ("top", scraped.top_notes),
            ("heart", scraped.heart_notes),
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
        all_notes = scraped.top_notes + scraped.heart_notes + scraped.base_notes
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
