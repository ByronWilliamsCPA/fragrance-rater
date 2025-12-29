"""
Fragella API client service.
Limited to 20 requests/month on free tier - use sparingly!
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
import json
from pathlib import Path

from app.core.config import settings
from app.models import DataSource, Concentration, GenderTarget
from app.schemas import FragranceCreate, FragranceUpdate
from app.services.fragrance_service import FragranceService


class FragellaAPIError(Exception):
    """Custom exception for Fragella API errors."""
    pass


class FragellaClient:
    """
    Client for the Fragella API.

    IMPORTANT: Free tier is limited to 20 requests/month.
    Use this client only when:
    1. Fragrance not found in Kaggle dataset
    2. Fragrantica scraping fails
    3. Need authoritative/enriched data
    """

    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.FRAGELLA_BASE_URL
        self.api_key = settings.FRAGELLA_API_KEY
        self.monthly_limit = settings.FRAGELLA_MONTHLY_LIMIT

        # Track usage (persist to file)
        self.usage_file = Path(settings.DATA_DIR) / "fragella_usage.json"
        self._load_usage()

    def _load_usage(self):
        """Load usage tracking from file."""
        self.usage = {"month": None, "count": 0, "requests": []}

        if self.usage_file.exists():
            try:
                with open(self.usage_file) as f:
                    self.usage = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Reset if new month
        current_month = date.today().strftime("%Y-%m")
        if self.usage.get("month") != current_month:
            self.usage = {"month": current_month, "count": 0, "requests": []}

    def _save_usage(self):
        """Save usage tracking to file."""
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.usage_file, 'w') as f:
            json.dump(self.usage, f, indent=2)

    def _record_request(self, endpoint: str):
        """Record API request for tracking."""
        self.usage["count"] += 1
        self.usage["requests"].append({
            "endpoint": endpoint,
            "timestamp": datetime.utcnow().isoformat()
        })
        self._save_usage()

    @property
    def requests_remaining(self) -> int:
        """Get number of requests remaining this month."""
        return max(0, self.monthly_limit - self.usage.get("count", 0))

    @property
    def can_make_request(self) -> bool:
        """Check if we can make another request."""
        return self.api_key and self.requests_remaining > 0

    async def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make authenticated request to Fragella API."""
        if not self.api_key:
            raise FragellaAPIError("Fragella API key not configured")

        if not self.can_make_request:
            raise FragellaAPIError(f"Monthly request limit ({self.monthly_limit}) reached")

        headers = {"x-api-key": self.api_key}
        url = f"{self.base_url}/{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)

            if response.status_code == 429:
                raise FragellaAPIError("Rate limited by Fragella API")

            if response.status_code == 401:
                raise FragellaAPIError("Invalid Fragella API key")

            if response.status_code != 200:
                raise FragellaAPIError(f"API error: {response.status_code} - {response.text}")

            self._record_request(endpoint)
            return response.json()

    def _sync_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Synchronous version for non-async contexts."""
        if not self.api_key:
            raise FragellaAPIError("Fragella API key not configured")

        if not self.can_make_request:
            raise FragellaAPIError(f"Monthly request limit ({self.monthly_limit}) reached")

        headers = {"x-api-key": self.api_key}
        url = f"{self.base_url}/{endpoint}"

        with httpx.Client() as client:
            response = client.get(url, headers=headers, params=params, timeout=30.0)

            if response.status_code == 429:
                raise FragellaAPIError("Rate limited by Fragella API")

            if response.status_code == 401:
                raise FragellaAPIError("Invalid Fragella API key")

            if response.status_code != 200:
                raise FragellaAPIError(f"API error: {response.status_code} - {response.text}")

            self._record_request(endpoint)
            return response.json()

    def _parse_concentration(self, oil_type: str) -> Optional[Concentration]:
        """Parse concentration from Fragella OilType field."""
        if not oil_type:
            return None

        oil_type = oil_type.lower()

        if 'parfum' in oil_type and 'eau' not in oil_type:
            return Concentration.PARFUM
        if 'eau de parfum' in oil_type or oil_type == 'edp':
            return Concentration.EDP
        if 'eau de toilette' in oil_type or oil_type == 'edt':
            return Concentration.EDT
        if 'eau de cologne' in oil_type or oil_type == 'edc':
            return Concentration.EDC

        return Concentration.OTHER

    def _parse_gender(self, gender: str) -> Optional[GenderTarget]:
        """Parse gender from Fragella Gender field."""
        if not gender:
            return None

        gender = gender.lower()

        if 'women' in gender or 'female' in gender:
            return GenderTarget.FEMININE
        if 'men' in gender or 'male' in gender:
            return GenderTarget.MASCULINE

        return GenderTarget.UNISEX

    def _parse_notes(self, notes_data: Dict) -> tuple[List[str], List[str], List[str]]:
        """Parse notes from Fragella Notes structure."""
        top = []
        heart = []
        base = []

        if not notes_data:
            return top, heart, base

        for note in notes_data.get('Top', []):
            if isinstance(note, dict):
                top.append(note.get('name', ''))
            else:
                top.append(str(note))

        for note in notes_data.get('Middle', []):
            if isinstance(note, dict):
                heart.append(note.get('name', ''))
            else:
                heart.append(str(note))

        for note in notes_data.get('Base', []):
            if isinstance(note, dict):
                base.append(note.get('name', ''))
            else:
                base.append(str(note))

        return (
            [n for n in top if n],
            [n for n in heart if n],
            [n for n in base if n]
        )

    def _parse_accords(self, accords_list: List[str], percentages: Dict) -> Dict[str, float]:
        """Parse accords with percentages from Fragella data."""
        result = {}

        # Map percentage descriptions to numeric values
        pct_map = {
            'dominant': 1.0,
            'prominent': 0.75,
            'moderate': 0.5,
            'subtle': 0.25,
        }

        for accord in accords_list or []:
            accord_lower = accord.lower()
            pct = percentages.get(accord_lower, percentages.get(accord, 'moderate'))

            if isinstance(pct, str):
                pct = pct_map.get(pct.lower(), 0.5)
            elif isinstance(pct, (int, float)):
                pct = min(1.0, max(0.0, pct / 100 if pct > 1 else pct))
            else:
                pct = 0.5

            result[accord_lower] = pct

        return result

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for fragrances by name.
        Uses 1 API request.
        """
        return self._sync_request("fragrances", {"search": query, "limit": limit})

    def get_by_brand(self, brand: str, limit: int = 10) -> List[Dict]:
        """
        Get fragrances by brand.
        Uses 1 API request.
        """
        return self._sync_request(f"brands/{brand}", {"limit": limit})

    def find_similar(self, name: str, limit: int = 5) -> Dict:
        """
        Find fragrances similar to a given scent.
        Uses 1 API request.
        """
        return self._sync_request("fragrances/similar", {"name": name, "limit": limit})

    def search_and_import(self, query: str) -> Optional[int]:
        """
        Search Fragella and import the best match.
        Returns the fragrance ID if imported/found.
        Uses 1 API request.
        """
        results = self.search(query, limit=1)

        if not results:
            return None

        data = results[0]
        return self._import_fragrance_data(data)

    def _import_fragrance_data(self, data: Dict) -> Optional[int]:
        """Import or update a fragrance from Fragella API data."""
        name = data.get('Name', '').strip()
        brand = data.get('Brand', '').strip()

        if not name or not brand:
            return None

        # Check if exists
        existing = FragranceService.get_by_name_brand(self.db, name, brand)

        # Parse notes
        top_notes, heart_notes, base_notes = self._parse_notes(data.get('Notes', {}))

        # Parse accords
        accords = self._parse_accords(
            data.get('Main Accords', []),
            data.get('Main Accords Percentage', {})
        )

        # Parse year
        year = None
        if data.get('Year'):
            try:
                year = int(data['Year'])
            except (ValueError, TypeError):
                pass

        # Parse rating
        rating = None
        if data.get('rating'):
            try:
                rating = float(data['rating'])
            except (ValueError, TypeError):
                pass

        if existing:
            # Update with Fragella data (higher quality source)
            update_data = FragranceUpdate(
                top_notes=top_notes or None,
                heart_notes=heart_notes or None,
                base_notes=base_notes or None,
                accords=accords or None,
                concentration=self._parse_concentration(data.get('OilType')),
                gender_target=self._parse_gender(data.get('Gender')),
                launch_year=year,
                country=data.get('Country'),
                longevity=data.get('Longevity'),
                sillage=data.get('Sillage'),
                rating=rating,
                image_url=data.get('Image URL'),
                data_source=DataSource.FRAGELLA,
            )
            FragranceService.update(self.db, existing.id, update_data)
            self.db.commit()
            return existing.id
        else:
            # Create new
            create_data = FragranceCreate(
                name=name,
                brand=brand,
                top_notes=top_notes,
                heart_notes=heart_notes,
                base_notes=base_notes,
                accords=accords,
                concentration=self._parse_concentration(data.get('OilType')),
                gender_target=self._parse_gender(data.get('Gender')),
                launch_year=year,
                country=data.get('Country'),
                longevity=data.get('Longevity'),
                sillage=data.get('Sillage'),
                rating=rating,
                image_url=data.get('Image URL'),
                data_source=DataSource.FRAGELLA,
            )
            fragrance = FragranceService.create(self.db, create_data)
            self.db.commit()
            return fragrance.id
