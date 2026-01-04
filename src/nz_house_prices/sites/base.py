"""Base class for site-specific implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from rapidfuzz import fuzz
from selenium.webdriver.remote.webdriver import WebDriver

from nz_house_prices.discovery.address import NZ_REGIONS, parse_address


@dataclass
class SearchResult:
    """Result from a property search."""

    address: str
    url: str
    confidence: float  # 0.0 to 1.0 - how confident we are this is the right property
    site: str
    extra_info: Optional[dict] = None


class BaseSite(ABC):
    """Abstract base class for real estate site implementations."""

    # Class attributes to be overridden by subclasses
    SITE_NAME: str = ""
    SITE_DOMAIN: str = ""
    SEARCH_URL: str = ""

    def __init__(self, driver: Optional[WebDriver] = None):
        """Initialize the site handler.

        Args:
            driver: Optional WebDriver instance (will be created if not provided)
        """
        self._driver = driver
        self._owns_driver = False

    @property
    def driver(self) -> WebDriver:
        """Get or create WebDriver instance."""
        if self._driver is None:
            from nz_house_prices.core.driver import init_driver

            self._driver = init_driver()
            self._owns_driver = True
        return self._driver

    def close(self) -> None:
        """Close the WebDriver if we own it."""
        if self._owns_driver and self._driver is not None:
            self._driver.quit()
            self._driver = None
            self._owns_driver = False

    def __enter__(self) -> "BaseSite":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    @abstractmethod
    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address.

        Args:
            address: The address to search for

        Returns:
            List of SearchResult objects, ordered by confidence (highest first)
        """
        pass

    @abstractmethod
    def get_property_url(self, address: str) -> Optional[str]:
        """Get the URL for a property page.

        This is a convenience method that returns the best match URL.

        Args:
            address: The address to search for

        Returns:
            URL string or None if not found
        """
        pass

    def normalize_address(self, address: str) -> str:
        """Normalize an address string for searching.

        Args:
            address: Raw address string

        Returns:
            Normalized address string
        """
        # Basic normalization - subclasses can override for site-specific needs
        normalized = address.strip()
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def _calculate_confidence(self, search_address: str, result_address: str) -> float:
        """Calculate confidence score for a search result.

        Args:
            search_address: The address we searched for
            result_address: The address returned in results

        Returns:
            Confidence score from 0.0 to 1.0
        """
        # Simple string similarity - can be improved
        search_lower = search_address.lower()
        result_lower = result_address.lower()

        # Exact match
        if search_lower == result_lower:
            return 1.0

        # Check if search terms are contained
        search_words = set(search_lower.split())
        result_words = set(result_lower.split())

        if not search_words:
            return 0.0

        # Calculate word overlap
        overlap = len(search_words & result_words)
        confidence = overlap / len(search_words)

        return min(confidence, 0.99)  # Cap at 0.99 for non-exact matches

    def _calculate_location_score(
        self,
        target_suburb: Optional[str],
        target_city: Optional[str],
        result_address: str,
        threshold: int = 70,
    ) -> Tuple[int, bool]:
        """Calculate score based on location match using fuzzy matching.

        Args:
            target_suburb: Expected suburb from the search address
            target_city: Expected city from the search address
            result_address: The full address returned from search results
            threshold: Minimum fuzzy match score (0-100) to consider a match

        Returns:
            Tuple of (score, has_location_match):
            - score: +100 for strong suburb match, +50 for city match,
                     -200 for location mismatch, 0 for no location info
            - has_location_match: True if we found a matching location
        """
        if not result_address:
            return 0, False

        result_lower = result_address.lower()

        # Check for suburb match
        suburb_matched = False
        if target_suburb:
            suburb_lower = target_suburb.lower()
            # Try fuzzy matching against the result address
            suburb_ratio = fuzz.partial_ratio(suburb_lower, result_lower)
            if suburb_ratio >= threshold:
                suburb_matched = True

        # Check for city match
        city_matched = False
        if target_city:
            city_lower = target_city.lower()
            city_ratio = fuzz.partial_ratio(city_lower, result_lower)
            if city_ratio >= threshold:
                city_matched = True

        # Check for location mismatch - if result contains a different major city
        # than what's in our target address
        has_different_city = False
        regions_in_result = []

        # Find all major cities/regions in the result
        for region in NZ_REGIONS:
            if region in result_lower:
                regions_in_result.append(region)

        # Check if any region in the result conflicts with our target
        if regions_in_result and (target_city or target_suburb):
            # Build a combined target location string
            target_parts = []
            if target_suburb:
                target_parts.append(target_suburb.lower())
            if target_city:
                target_parts.append(target_city.lower())
            target_combined = " ".join(target_parts)

            # Check if ANY of the regions in the result match our target
            any_region_matches = False

            for region in regions_in_result:
                # Check if this region is in our target location info
                if region in target_combined:
                    any_region_matches = True
                    break
                # Also use fuzzy matching for the city
                if target_city:
                    city_region_ratio = fuzz.ratio(region, target_city.lower())
                    if city_region_ratio >= 80:
                        any_region_matches = True
                        break

            # If none of the regions match AND the result has a major city, it's a conflict
            if not any_region_matches and not suburb_matched and not city_matched:
                has_different_city = True

        # Calculate final score
        if has_different_city:
            # Result is in a different city than what we're looking for
            return -200, False

        score = 0
        if suburb_matched:
            score += 100
        if city_matched:
            score += 50

        return score, suburb_matched or city_matched

    def _parse_target_location(self, address: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse suburb and city from target address.

        Args:
            address: The address to parse

        Returns:
            Tuple of (suburb, city)
        """
        parsed = parse_address(address)
        return parsed.suburb, parsed.city
