"""propertyvalue.co.nz site implementation."""

import re
from typing import List, Optional
from urllib.parse import quote

import requests

from nz_house_prices.sites.base import BaseSite, SearchResult


class PropertyValueSite(BaseSite):
    """Handler for propertyvalue.co.nz property searches.

    Uses the public suggestions API for fast and reliable address lookup.
    """

    SITE_NAME = "propertyvalue.co.nz"
    SITE_DOMAIN = "propertyvalue.co.nz"
    SEARCH_URL = "https://www.propertyvalue.co.nz"
    API_URL = "https://propertyvalue.co.nz/api/public/clapi/suggestions"

    def _extract_unit_number(self, address: str) -> Optional[str]:
        """Extract unit number from an address string."""
        match = re.match(r"^(\d+[A-Za-z]?)\s*/", address)
        if match:
            return match.group(1)
        match = re.match(r"^(?:unit|flat|apt|apartment)\s*(\d+[A-Za-z]?)", address, re.I)
        if match:
            return match.group(1)
        return None

    def _find_best_match(
        self, suggestions: list, target_address: str
    ) -> Optional[dict]:
        """Find the best matching suggestion from API results."""
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()

        best_match = None
        best_score = -1

        for suggestion in suggestions:
            if suggestion.get("suggestionType") != "address":
                continue

            suggestion_text = suggestion.get("suggestion", "")
            if not suggestion_text:
                continue

            score = 0
            result_unit = self._extract_unit_number(suggestion_text)

            # Exact unit match is highest priority
            if target_unit and result_unit:
                if target_unit == result_unit:
                    score += 100
                else:
                    score -= 50
            elif target_unit and not result_unit:
                score -= 10

            # Check for word overlap
            suggestion_lower = suggestion_text.lower()
            target_words = target_lower.split()[:3]
            if any(word in suggestion_lower for word in target_words):
                score += 20

            if score > best_score:
                best_score = score
                best_match = suggestion

        return best_match

    def _query_api(self, query: str) -> List[dict]:
        """Query the PropertyValue suggestions API.

        Args:
            query: Search query string

        Returns:
            List of suggestion dictionaries
        """
        try:
            params = {
                "q": query,
                "suggestionTypes": "address,street,locality",
                "limit": "10",
            }
            response = requests.get(self.API_URL, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("suggestions", [])
        except Exception:
            pass
        return []

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on propertyvalue.co.nz.

        Uses the public API for fast lookups. Falls back to shorter
        address queries if the full address returns no results.

        Args:
            address: The address to search for

        Returns:
            List of SearchResult objects
        """
        results = []
        normalized_address = self.normalize_address(address)

        # Try the full address first
        suggestions = self._query_api(normalized_address)

        # If no results, try progressively shorter queries
        # (sometimes full addresses with city/region don't match)
        if not suggestions:
            parts = [p.strip() for p in normalized_address.split(",")]
            for i in range(len(parts) - 1, 0, -1):
                shorter_query = ", ".join(parts[:i])
                suggestions = self._query_api(shorter_query)
                if suggestions:
                    break

        if suggestions:
            best_match = self._find_best_match(suggestions, normalized_address)

            if best_match:
                url_path = best_match.get("url", "")
                suggestion_text = best_match.get("suggestion", "")

                if url_path:
                    full_url = f"{self.SEARCH_URL}{url_path}"
                    confidence = self._calculate_confidence(
                        normalized_address, suggestion_text
                    )
                    results.append(
                        SearchResult(
                            address=suggestion_text,
                            url=full_url,
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
