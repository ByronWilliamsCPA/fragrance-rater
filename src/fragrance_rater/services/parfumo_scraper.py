"""Parfumo.com web scraper for fragrance data.

Used as an additional data source alongside Kaggle CSV imports.
Parfumo has excellent note taxonomy and community ratings.

NOTE: Web scraping should be done responsibly with appropriate delays.
Parfumo uses Cloudflare protection - be respectful of their resources.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from fragrance_rater.models.fragrance import Fragrance, FragranceAccord, FragranceNote, Note

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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
    """

    BASE_URL = "https://www.parfumo.com"
    SEARCH_URL = f"{BASE_URL}/s_perfumes.php"

    # Delay between requests (seconds) - be respectful
    REQUEST_DELAY = 3.0

    # User agent to identify as a browser
    # Keep headers minimal to avoid Cloudflare issues
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the scraper.

        Args:
            session: Async database session for imports.
        """
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
        """Ensure we don't make requests too quickly."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _make_request(self, url: str) -> BeautifulSoup | None:
        """Make HTTP request and return parsed HTML.

        Args:
            url: URL to fetch.

        Returns:
            Parsed BeautifulSoup object or None on failure.
        """
        self._wait_for_rate_limit()

        try:
            client = self._get_client()
            response = client.get(url)

            if response.status_code != 200:
                return None

            return BeautifulSoup(response.text, "lxml")
        except httpx.HTTPError as e:
            # Log error but don't crash
            print(f"HTTP request failed for {url}: {e}")
            return None

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search Parfumo for fragrances.

        Args:
            query: Search query (name, brand, or both).
            limit: Maximum results to return.

        Returns:
            List of search results.
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
                href = item.get("href", "")
                if not href:
                    continue

                # Normalize URL
                if not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                # Skip if it's not a perfume detail page
                # Parfumo URLs: /Perfumes/brand/perfume-name
                path_parts = href.replace(self.BASE_URL, "").split("/")
                if len(path_parts) < 4:  # noqa: PLR2004
                    continue

                # Try to extract name from link text or nearby elements
                name = item.get_text(strip=True)
                brand = path_parts[2] if len(path_parts) > 2 else ""  # noqa: PLR2004

                # Clean up brand name (URL encoded)
                brand = brand.replace("-", " ").replace("_", " ").title()

                if name and href:
                    # Avoid duplicates
                    if not any(r.url == href for r in results):
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
            url: Full URL to the perfume page.

        Returns:
            ScrapedFragrance with extracted data, or None on failure.
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
            # Extract name from h1.p_name_h1 (Parfumo specific)
            name_elem = soup.select_one("h1.p_name_h1")
            if name_elem:
                # Get text before the brand span
                # NavigableString has name=None, Tag has name='span' etc
                for child in name_elem.children:
                    # Check if it's a Tag (not NavigableString) by checking if name is not None
                    if getattr(child, "name", None) is not None:
                        break  # Stop at first actual tag
                    text = str(child).strip()
                    if text:
                        data.name = text
                        break

            # Fallback: try generic selectors
            if not data.name:
                name_elem = soup.select_one("h1, .perfume-title, [itemprop='name']")
                if name_elem:
                    data.name = name_elem.get_text(strip=True)

            # Extract brand from span.p_brand_name (Parfumo specific)
            brand_elem = soup.select_one("span.p_brand_name")
            if brand_elem:
                # Remove year if present (e.g., "Polysnifferous2024" -> "Polysnifferous")
                brand_text = brand_elem.get_text(strip=True)
                # Remove trailing year
                import re as regex
                data.brand = regex.sub(r"\d{4}$", "", brand_text).strip()

            # Fallback brand extraction
            if not data.brand:
                brand_elem = soup.select_one(
                    "a[href*='/Brands/'], .brand-name, [itemprop='brand']"
                )
                if brand_elem:
                    data.brand = brand_elem.get_text(strip=True)

            # Extract from URL if not found
            if not data.brand:
                path_parts = url.split("/")
                if len(path_parts) >= 4:  # noqa: PLR2004
                    data.brand = (
                        path_parts[-2].replace("-", " ").replace("_", " ").title()
                    )

            # Extract notes by pyramid position
            # Parfumo uses a fragrance pyramid visualization
            self._extract_notes(soup, data)

            # Extract accords
            self._extract_accords(soup, data)

            # Extract rating - Parfumo specific
            # Format: "Scent8.35 Ratings" in .barfiller_element.rating-details
            rating_elem = soup.select_one(".barfiller_element.rating-details")
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                # Extract rating value (e.g., "8.3" from "Scent8.35 Ratings")
                match = re.search(r"(\d+\.?\d*)", rating_text)
                if match:
                    data.rating = float(match.group(1))

                # Extract rating count (e.g., "5" from "5 Ratings")
                count_match = re.search(r"(\d+)\s*Rating", rating_text)
                if count_match:
                    data.rating_count = int(count_match.group(1))

            # Fallback rating extraction
            if not data.rating:
                rating_elem = soup.select_one(
                    ".rating-value, [itemprop='ratingValue'], .score"
                )
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    match = re.search(r"(\d+\.?\d*)", rating_text)
                    if match:
                        rating = float(match.group(1))
                        if rating > 10:  # noqa: PLR2004
                            rating = rating / 10
                        data.rating = rating

            # Gender
            gender_text = soup.get_text().lower()
            if "for women and men" in gender_text or "unisex" in gender_text:
                data.gender = "unisex"
            elif "for women" in gender_text:
                data.gender = "feminine"
            elif "for men" in gender_text:
                data.gender = "masculine"

            # Year
            year_elem = soup.find(string=re.compile(r"\b(19|20)\d{2}\b"))
            if year_elem:
                year_match = re.search(r"\b(19|20)(\d{2})\b", str(year_elem))
                if year_match:
                    data.year = int(year_match.group())

            # Perfumer
            perfumer_elem = soup.select_one(
                "a[href*='/Perfumers/'], .perfumer, [itemprop='creator']"
            )
            if perfumer_elem:
                data.perfumer = perfumer_elem.get_text(strip=True)

            # Image
            img_elem = soup.select_one(
                "img[itemprop='image'], .perfume-image img, .bottle-image"
            )
            if img_elem:
                data.image_url = img_elem.get("src") or img_elem.get("data-src")

        except Exception as e:
            print(f"Scraping error for {url}: {e}")

        return data if data.name else None

    def _extract_notes(self, soup: BeautifulSoup, data: ScrapedFragrance) -> None:
        """Extract notes from the fragrance pyramid.

        Args:
            soup: Parsed HTML.
            data: ScrapedFragrance to populate.
        """
        # Parfumo-specific: Look for pyramid blocks with nb_t, nb_m, nb_b classes
        # .pyramid_block.nb_t = Top Notes
        # .pyramid_block.nb_m = Heart/Middle Notes
        # .pyramid_block.nb_b = Base Notes

        # Method 1: Parfumo-specific pyramid blocks
        top_block = soup.select_one(".pyramid_block.nb_t")
        if top_block:
            note_spans = top_block.select("span.pointer")
            data.top_notes = [n.get_text(strip=True) for n in note_spans if n.get_text(strip=True)]

        heart_block = soup.select_one(".pyramid_block.nb_m")
        if heart_block:
            note_spans = heart_block.select("span.pointer")
            data.heart_notes = [n.get_text(strip=True) for n in note_spans if n.get_text(strip=True)]

        base_block = soup.select_one(".pyramid_block.nb_b")
        if base_block:
            note_spans = base_block.select("span.pointer")
            data.base_notes = [n.get_text(strip=True) for n in note_spans if n.get_text(strip=True)]

        # Method 2: Fallback - look for labeled sections
        if not any([data.top_notes, data.heart_notes, data.base_notes]):
            sections = soup.select("[class*='note'], [class*='pyramid'], .ingredients")

            for section in sections:
                section_text = section.get_text().lower()
                note_links = section.select("a[href*='/Notes/'], .note-name, .ingredient, span.pointer")
                notes = [n.get_text(strip=True) for n in note_links if n.get_text(strip=True)]

                if "top" in section_text or "head" in section_text or "kopfnote" in section_text:
                    data.top_notes.extend(notes)
                elif "heart" in section_text or "middle" in section_text or "herznote" in section_text:
                    data.heart_notes.extend(notes)
                elif "base" in section_text or "fond" in section_text or "basisnote" in section_text:
                    data.base_notes.extend(notes)

        # Method 3: If still no notes, look for any note links
        if not any([data.top_notes, data.heart_notes, data.base_notes]):
            all_notes = soup.select("a[href*='/Notes/'], span.pointer")
            data.heart_notes = list({n.get_text(strip=True) for n in all_notes if n.get_text(strip=True)})

        # Deduplicate
        data.top_notes = list(dict.fromkeys(data.top_notes))
        data.heart_notes = list(dict.fromkeys(data.heart_notes))
        data.base_notes = list(dict.fromkeys(data.base_notes))

    def _extract_accords(self, soup: BeautifulSoup, data: ScrapedFragrance) -> None:
        """Extract accords/scent profile.

        Args:
            soup: Parsed HTML.
            data: ScrapedFragrance to populate.
        """
        # Parfumo shows accords with visual bars indicating strength
        accord_elements = soup.select(
            ".accord, .scent-profile .bar, [class*='accord']"
        )

        for elem in accord_elements:
            try:
                # Get accord name
                name_elem = elem.select_one(".name, .label, span")
                if name_elem:
                    accord_name = name_elem.get_text(strip=True).lower()
                else:
                    accord_name = elem.get_text(strip=True).lower()

                if not accord_name or len(accord_name) > 50:  # noqa: PLR2004
                    continue

                # Try to get strength from width style or data attribute
                style = elem.get("style", "")
                width_match = re.search(r"width:\s*(\d+)", style)

                if width_match:
                    weight = float(width_match.group(1)) / 100
                else:
                    # Check for data-value or similar
                    data_val = elem.get("data-value") or elem.get("data-width")
                    if data_val:
                        weight = float(data_val) / 100
                    else:
                        weight = 0.5  # Default weight

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
            name: Fragrance name to search for.
            brand: Optional brand to filter results.

        Returns:
            Fragrance ID if imported/found, None otherwise.
        """
        from sqlalchemy import select

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
        stmt = select(Fragrance).where(
            Fragrance.name == final_name,
            Fragrance.brand == final_brand,
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
            url: Full Parfumo URL (e.g., https://www.parfumo.com/Perfumes/brand/name)

        Returns:
            Fragrance ID if imported, None on failure.
        """
        from sqlalchemy import select

        scraped = self.scrape_perfume_page(url)

        if not scraped or not scraped.name or not scraped.brand:
            return None

        # Check if exists
        stmt = select(Fragrance).where(
            Fragrance.name == scraped.name,
            Fragrance.brand == scraped.brand,
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
            scraped: Scraped fragrance data.
            name: Fragrance name.
            brand: Brand name.

        Returns:
            New fragrance ID.
        """
        import uuid

        # Map gender
        gender_map = {
            "feminine": "feminine",
            "masculine": "masculine",
            "unisex": "unisex",
        }

        fragrance = Fragrance(
            id=str(uuid.uuid4()),
            name=name,
            brand=brand,
            concentration=scraped.concentration or "EDP",
            gender_target=gender_map.get(scraped.gender or "", "unisex"),
            launch_year=scraped.year,
            primary_family=self._infer_family(scraped),
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
            fragrance: Existing fragrance to update.
            scraped: Scraped data.
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
            fragrance_id: Fragrance ID.
            scraped: Scraped data with notes.
        """
        import uuid

        from sqlalchemy import select

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

                # Create fragrance-note relationship
                fn = FragranceNote(
                    fragrance_id=fragrance_id,
                    note_id=note.id,
                    position=note_type,
                )
                self.db.add(fn)

    def _infer_family(self, scraped: ScrapedFragrance) -> str:
        """Infer fragrance family from accords and notes.

        Args:
            scraped: Scraped fragrance data.

        Returns:
            Best guess at fragrance family.
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
            scraped.top_notes + scraped.heart_notes + scraped.base_notes
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
            note_name: Name of the note.

        Returns:
            Category string.
        """
        note_lower = note_name.lower()

        categories = {
            "citrus": ["bergamot", "lemon", "orange", "grapefruit", "lime", "mandarin"],
            "floral": ["rose", "jasmine", "lily", "violet", "iris", "peony", "tuberose"],
            "woody": ["cedar", "sandalwood", "oud", "vetiver", "birch", "guaiac"],
            "spicy": ["pepper", "cinnamon", "cardamom", "clove", "ginger", "saffron"],
            "fruity": ["apple", "peach", "pear", "berry", "plum", "cherry", "pineapple"],
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
        session: Async database session.

    Returns:
        ParfumoScraper instance.
    """
    return ParfumoScraper(session)
