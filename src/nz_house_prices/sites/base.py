"""Base class for site-specific implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from selenium.webdriver.remote.webdriver import WebDriver


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
