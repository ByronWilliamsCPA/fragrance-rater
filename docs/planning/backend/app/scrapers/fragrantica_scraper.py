"""
Fragrantica web scraper.
Used as fallback when data not in Kaggle dataset and Fragella API quota exhausted.

NOTE: Web scraping should be done responsibly with appropriate delays.
"""
import httpx
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
import re
import time
from urllib.parse import quote_plus
from sqlalchemy.orm import Session

from app.models import DataSource, Concentration, GenderTarget
from app.schemas import FragranceCreate, FragranceUpdate
from app.services.fragrance_service import FragranceService


class FragranticaScraper:
    """
    Web scraper for Fragrantica.com

    Use this as a last resort when:
    1. Fragrance not in Kaggle dataset
    2. Fragella API quota exhausted

    Be respectful: use delays between requests.
    """

    BASE_URL = "https://www.fragrantica.com"
    SEARCH_URL = f"{BASE_URL}/search/"

    # Delay between requests (seconds)
    REQUEST_DELAY = 2.0

    # User agent to identify as a browser
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, db: Session):
        self.db = db
        self._last_request_time = 0

    def _wait_for_rate_limit(self):
        """Ensure we don't make requests too quickly."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """Make HTTP request and return parsed HTML."""
        self._wait_for_rate_limit()

        try:
            with httpx.Client(headers=self.HEADERS, follow_redirects=True, timeout=30.0) as client:
                response = client.get(url)

                if response.status_code != 200:
                    return None

                return BeautifulSoup(response.text, 'lxml')
        except Exception as e:
            print(f"Request failed: {e}")
            return None

    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search Fragrantica for fragrances.
        Returns list of {name, brand, url} dicts.
        """
        search_url = f"{self.SEARCH_URL}?query={quote_plus(query)}"
        soup = self._make_request(search_url)

        if not soup:
            return []

        results = []

        # Look for search results - Fragrantica structure may vary
        # This is a simplified parser that may need adjustment
        for item in soup.select('.cell.card')[:limit]:
            try:
                link = item.select_one('a[href*="/perfume/"]')
                if not link:
                    continue

                href = link.get('href', '')
                if not href.startswith('http'):
                    href = f"{self.BASE_URL}{href}"

                # Try to extract name and brand from the card
                name_elem = item.select_one('.card-title, h3, .perfume-name')
                brand_elem = item.select_one('.brand, .designer, .card-subtitle')

                name = name_elem.get_text(strip=True) if name_elem else ""
                brand = brand_elem.get_text(strip=True) if brand_elem else ""

                if name and href:
                    results.append({
                        'name': name,
                        'brand': brand,
                        'url': href
                    })
            except Exception:
                continue

        return results

    def scrape_perfume_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape detailed info from a perfume page.
        Returns dict with fragrance data.
        """
        soup = self._make_request(url)

        if not soup:
            return None

        data = {
            'url': url,
            'name': None,
            'brand': None,
            'top_notes': [],
            'heart_notes': [],
            'base_notes': [],
            'accords': {},
            'rating': None,
            'gender': None,
            'longevity': None,
            'sillage': None,
            'year': None,
            'image_url': None,
        }

        try:
            # Extract name and brand from title
            title_elem = soup.select_one('h1[itemprop="name"], .perfume-name, h1')
            if title_elem:
                full_title = title_elem.get_text(strip=True)
                # Often format is "Name Brand" or "Brand Name"
                data['name'] = full_title

            # Brand
            brand_elem = soup.select_one('span[itemprop="brand"], .brand-name a, a[href*="/designers/"]')
            if brand_elem:
                data['brand'] = brand_elem.get_text(strip=True)

            # Extract notes by position
            # Fragrantica organizes notes in pyramid sections
            for pyramid_section in soup.select('[class*="pyramid"], .notes-box, .accord-box'):
                section_text = pyramid_section.get_text().lower()
                note_links = pyramid_section.select('a[href*="/notes/"]')
                notes = [n.get_text(strip=True) for n in note_links]

                if 'top' in section_text or 'head' in section_text:
                    data['top_notes'].extend(notes)
                elif 'heart' in section_text or 'middle' in section_text:
                    data['heart_notes'].extend(notes)
                elif 'base' in section_text:
                    data['base_notes'].extend(notes)

            # If no pyramid structure found, try general notes
            if not any([data['top_notes'], data['heart_notes'], data['base_notes']]):
                all_notes = soup.select('a[href*="/notes/"]')
                data['heart_notes'] = [n.get_text(strip=True) for n in all_notes]

            # Extract accords
            for accord_elem in soup.select('.accord-box .accord, .cell.accord'):
                try:
                    accord_name = accord_elem.get_text(strip=True).lower()
                    # Try to get width/percentage from style
                    style = accord_elem.get('style', '')
                    width_match = re.search(r'width:\s*(\d+)', style)
                    if width_match:
                        weight = float(width_match.group(1)) / 100
                    else:
                        weight = 0.5

                    if accord_name:
                        data['accords'][accord_name] = weight
                except Exception:
                    continue

            # Rating
            rating_elem = soup.select_one('[itemprop="ratingValue"], .rating-value')
            if rating_elem:
                try:
                    data['rating'] = float(rating_elem.get_text(strip=True).replace(',', '.'))
                except (ValueError, TypeError):
                    pass

            # Gender
            gender_elem = soup.select_one('.gender-icon, [class*="gender"]')
            if gender_elem:
                gender_text = gender_elem.get_text().lower()
                if 'women' in gender_text:
                    data['gender'] = 'feminine'
                elif 'men' in gender_text:
                    data['gender'] = 'masculine'
                else:
                    data['gender'] = 'unisex'

            # Year
            year_match = soup.find(string=re.compile(r'\b(19|20)\d{2}\b'))
            if year_match:
                year_text = re.search(r'\b(19|20)\d{2}\b', year_match)
                if year_text:
                    data['year'] = int(year_text.group())

            # Image
            img_elem = soup.select_one('img[itemprop="image"], .perfume-image img')
            if img_elem:
                data['image_url'] = img_elem.get('src') or img_elem.get('data-src')

        except Exception as e:
            print(f"Scraping error: {e}")

        return data

    def _parse_gender(self, gender: str) -> Optional[GenderTarget]:
        if not gender:
            return None
        gender = gender.lower()
        if 'feminine' in gender or 'women' in gender:
            return GenderTarget.FEMININE
        if 'masculine' in gender or 'men' in gender:
            return GenderTarget.MASCULINE
        return GenderTarget.UNISEX

    def search_and_import(self, name: str, brand: Optional[str] = None) -> Optional[int]:
        """
        Search Fragrantica and import the best match.
        Returns fragrance ID if imported/found.
        """
        query = f"{name} {brand}" if brand else name
        results = self.search(query, limit=3)

        if not results:
            return None

        # Find best match
        best_match = None
        for result in results:
            if brand and brand.lower() in result.get('brand', '').lower():
                best_match = result
                break
            if name.lower() in result.get('name', '').lower():
                best_match = result
                break

        if not best_match:
            best_match = results[0]  # Take first result

        # Scrape full details
        data = self.scrape_perfume_page(best_match['url'])

        if not data:
            return None

        # Check if exists
        final_name = data['name'] or best_match['name']
        final_brand = data['brand'] or best_match['brand']

        if not final_name or not final_brand:
            return None

        existing = FragranceService.get_by_name_brand(self.db, final_name, final_brand)

        if existing:
            # Update with scraped data
            update_data = FragranceUpdate(
                top_notes=data['top_notes'] or None,
                heart_notes=data['heart_notes'] or None,
                base_notes=data['base_notes'] or None,
                accords=data['accords'] or None,
                gender_target=self._parse_gender(data['gender']),
                launch_year=data['year'],
                longevity=data['longevity'],
                sillage=data['sillage'],
                rating=data['rating'],
                image_url=data['image_url'],
                data_source=DataSource.FRAGRANTICA,
            )
            FragranceService.update(self.db, existing.id, update_data)
            self.db.commit()
            return existing.id
        else:
            # Create new
            create_data = FragranceCreate(
                name=final_name,
                brand=final_brand,
                top_notes=data['top_notes'],
                heart_notes=data['heart_notes'],
                base_notes=data['base_notes'],
                accords=data['accords'],
                gender_target=self._parse_gender(data['gender']),
                launch_year=data['year'],
                longevity=data['longevity'],
                sillage=data['sillage'],
                rating=data['rating'],
                image_url=data['image_url'],
                fragrantica_url=data['url'],
                data_source=DataSource.FRAGRANTICA,
            )
            fragrance = FragranceService.create(self.db, create_data)
            self.db.commit()
            return fragrance.id
