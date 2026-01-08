"""Base class for site-specific implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from playwright.sync_api import Page

from nz_house_prices.discovery.geocoder import geocode_address


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

    def __init__(self, page: Optional[Page] = None):
        """Initialize the site handler.

        Args:
            page: Optional Playwright Page instance
        """
        self._page = page
        self._owns_page = False

    @property
    def page(self) -> Page:
        """Get or create Page instance."""
        if self._page is None:
            from nz_house_prices.core.driver import create_page

            self._page = create_page()
            self._owns_page = True
        return self._page

    def close(self) -> None:
        """Close the page if we own it."""
        if self._owns_page and self._page is not None:
            try:
                context = self._page.context
                self._page.close()
                context.close()
            except Exception:
                pass
            self._page = None
            self._owns_page = False

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
        target_address: str,
        result_address: str,
        max_distance_km: float = 5.0,
    ) -> Tuple[int, bool]:
        """Calculate score based on geographic distance using geocoding.

        Args:
            target_address: The address we're searching for
            result_address: The candidate address to compare
            max_distance_km: Maximum distance to consider a valid match

        Returns:
            Tuple of (score, is_close_match):
            - score: +200 for very close (<0.5km), +100 for close (<2km),
                     +50 for nearby (<5km), -200 for far, 0 if geocoding fails
            - is_close_match: True if within max_distance_km
        """
        target_location = geocode_address(target_address)
        if not target_location:
            return 0, False

        result_location = geocode_address(result_address)
        if not result_location:
            return 0, False

        distance = target_location.distance_to(result_location)

        # Score based on distance
        if distance < 0.5:
            return 200, True
        elif distance < 2.0:
            return 100, True
        elif distance <= max_distance_km:
            return 50, True
        else:
            return -200, False

    def _geocode_best_match(
        self,
        target_address: str,
        candidates: List[Tuple[str, str, int]],
        max_distance_km: float = 2.0,
    ) -> Optional[Tuple[str, str, int, float]]:
        """Use geocoding to find the best matching candidate by distance.

        This is useful when multiple candidates have similar text-based scores
        but are in different geographic locations (e.g., same street name in
        different suburbs).

        Args:
            target_address: The address we're searching for
            candidates: List of (url, display_address, text_score) tuples
            max_distance_km: Maximum distance to consider a valid match

        Returns:
            Tuple of (url, display_address, text_score, distance_km) for best match,
            or None if geocoding fails or no candidates within max_distance
        """
        if not candidates:
            return None

        # Geocode the target address
        target_location = geocode_address(target_address)
        if not target_location:
            # Fall back to text-based scoring if geocoding fails
            return None

        best_match = None
        best_distance = float("inf")

        for url, display_address, text_score in candidates:
            # Geocode the candidate
            candidate_location = geocode_address(display_address)
            if candidate_location:
                distance = target_location.distance_to(candidate_location)

                # Only consider if within max distance
                if distance <= max_distance_km and distance < best_distance:
                    best_distance = distance
                    best_match = (url, display_address, text_score, distance)

        return best_match
