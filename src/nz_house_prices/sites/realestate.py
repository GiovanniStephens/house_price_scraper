"""realestate.co.nz site implementation."""

import re
from typing import List, Optional

import requests

from nz_house_prices.sites.base import BaseSite, SearchResult


class RealEstateSite(BaseSite):
    """Handler for realestate.co.nz property searches.

    Uses the public properties API for address lookup to property estimates pages.
    """

    SITE_NAME = "realestate.co.nz"
    SITE_DOMAIN = "realestate.co.nz"
    SEARCH_URL = "https://www.realestate.co.nz"
    API_URL = "https://platform.realestate.co.nz/search/v1/properties/smart"

    # Headers required for API access
    API_HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.realestate.co.nz/",
    }

    def _extract_unit_number(self, address: str) -> Optional[str]:
        """Extract unit number from an address string."""
        match = re.match(r"^(\d+[A-Za-z]?)\s*/", address)
        if match:
            return match.group(1)
        match = re.match(r"^(?:unit|flat|apt|apartment)\s*(\d+[A-Za-z]?)", address, re.I)
        if match:
            return match.group(1)
        return None

    def _find_best_match(self, properties: list, target_address: str) -> Optional[dict]:
        """Find the best matching property from API results."""
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()

        best_match = None
        best_score = -1

        for prop in properties:
            if prop.get("filter") != "property":
                continue

            title = prop.get("title", "")
            street_address = prop.get("street-address", "")

            if not title:
                continue

            score = 0
            result_unit = self._extract_unit_number(street_address)

            # Exact unit match is highest priority
            if target_unit and result_unit:
                if target_unit == result_unit:
                    score += 100
                else:
                    score -= 50
            elif target_unit and not result_unit:
                score -= 10

            # Check for word overlap
            title_lower = title.lower()
            target_words = target_lower.split()[:3]
            if any(word in title_lower for word in target_words):
                score += 20

            # Bonus for matching street number
            if street_address and target_lower.split()[0] in street_address.lower():
                score += 30

            if score > best_score:
                best_score = score
                best_match = prop

        return best_match

    def _query_api(self, query: str) -> List[dict]:
        """Query the RealEstate properties API.

        Args:
            query: Search query string

        Returns:
            List of property dictionaries
        """
        try:
            params = {"q": query}
            response = requests.get(
                self.API_URL,
                params=params,
                headers=self.API_HEADERS,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
        except Exception:
            pass
        return []

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on realestate.co.nz.

        Uses the public properties API for fast lookups.

        Args:
            address: The address to search for

        Returns:
            List of SearchResult objects
        """
        results = []
        normalized_address = self.normalize_address(address)

        # Try the full address first
        properties = self._query_api(normalized_address)

        # If no results, try progressively shorter queries
        if not properties:
            parts = [p.strip() for p in normalized_address.split(",")]
            for i in range(len(parts) - 1, 0, -1):
                shorter_query = ", ".join(parts[:i])
                properties = self._query_api(shorter_query)
                if properties:
                    break

        if properties:
            best_match = self._find_best_match(properties, normalized_address)

            if best_match:
                address_slug = best_match.get("address-slug", "")
                short_id = best_match.get("short-id", "")
                title = best_match.get("title", "")

                if address_slug and short_id:
                    # Construct property estimates page URL
                    property_url = f"{self.SEARCH_URL}/property/{address_slug}/{short_id}"
                    confidence = self._calculate_confidence(normalized_address, title)
                    results.append(
                        SearchResult(
                            address=title,
                            url=property_url,
                            confidence=confidence,
                            site=self.SITE_NAME,
                        )
                    )

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def get_property_url(self, address: str) -> Optional[str]:
        """Get the best matching property URL.

        Args:
            address: The address to search for

        Returns:
            URL string or None if not found
        """
        results = self.search_property(address)
        if results and results[0].confidence > 0.5:
            return results[0].url
        return None
