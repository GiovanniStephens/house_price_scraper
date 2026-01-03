"""High-level public API for NZ House Prices."""

import time
from typing import Dict, List, Optional

from selenium.webdriver.remote.webdriver import WebDriver

from nz_house_prices.core.driver import ensure_driver_health, init_driver
from nz_house_prices.core.scraper import scrape_house_prices
from nz_house_prices.core.selectors import get_supported_sites
from nz_house_prices.discovery.resolver import PropertyResolver
from nz_house_prices.models.results import PriceEstimate, ScrapingResult
from nz_house_prices.utils.rate_limit import RateLimiter


def get_prices(
    address: str,
    sites: Optional[List[str]] = None,
    use_cache: bool = True,
    rate_limit: bool = True,
    min_delay: float = 2.0,
    max_delay: float = 5.0,
) -> Dict[str, PriceEstimate]:
    """Get house price estimates for an address from NZ real estate sites.

    This is the main entry point for getting house prices by address.

    Args:
        address: Full address string (e.g., "123 Example Street, Ponsonby, Auckland")
        sites: Optional list of sites to query. Defaults to all supported sites.
        use_cache: Whether to cache resolved URLs for faster future lookups.
        rate_limit: Whether to apply rate limiting between requests.
        min_delay: Minimum delay between requests in seconds.
        max_delay: Maximum delay between requests in seconds.

    Returns:
        Dictionary mapping site names to PriceEstimate objects.

    Example:
        >>> prices = get_prices("123 Example Street, Ponsonby, Auckland")
        >>> print(prices["homes.co.nz"].midpoint)
        1850000
        >>> for site, estimate in prices.items():
        ...     print(f"{site}: ${estimate.midpoint:,.0f}")
    """
    target_sites = sites or get_supported_sites()
    results: Dict[str, PriceEstimate] = {}

    driver = None
    limiter = RateLimiter(min_delay=min_delay, max_delay=max_delay) if rate_limit else None

    try:
        # Initialize driver
        driver = init_driver()

        # Resolve URLs for the address
        with PropertyResolver(driver=driver, use_cache=use_cache, sites=target_sites) as resolver:
            resolved = resolver.resolve(address)

        # Scrape each resolved URL
        for site, url in resolved.urls.items():
            try:
                if limiter:
                    limiter.wait_if_needed()

                driver = ensure_driver_health(driver)
                result = scrape_house_prices(driver, url, enable_logging=False)

                results[site] = PriceEstimate.from_scraping_result(result)

            except Exception as e:
                print(f"Error scraping {site}: {e}")
                results[site] = PriceEstimate(
                    source=site,
                    midpoint=None,
                    lower=None,
                    upper=None,
                )

    finally:
        if driver:
            driver.quit()

    return results


def get_prices_from_urls(
    urls: List[str],
    rate_limit: bool = True,
    min_delay: float = 2.0,
    max_delay: float = 5.0,
) -> List[ScrapingResult]:
    """Get house prices from specific URLs (legacy/direct mode).

    Use this when you already have property page URLs.

    Args:
        urls: List of property page URLs
        rate_limit: Whether to apply rate limiting
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests

    Returns:
        List of ScrapingResult objects

    Example:
        >>> results = get_prices_from_urls([
        ...     "https://homes.co.nz/address/auckland/ponsonby/123 Example Street/xxxxx"
        ... ])
        >>> print(results[0].prices["midpoint"])
    """
    results: List[ScrapingResult] = []
    limiter = RateLimiter(min_delay=min_delay, max_delay=max_delay) if rate_limit else None

    driver = None
    try:
        driver = init_driver()

        for url in urls:
            try:
                if limiter:
                    limiter.wait_if_needed()

                driver = ensure_driver_health(driver)
                result = scrape_house_prices(driver, url, enable_logging=False)
                results.append(result)

            except Exception as e:
                print(f"Error scraping {url}: {e}")

    finally:
        if driver:
            driver.quit()

    return results


class HousePriceScraper:
    """Class-based API for more control over scraping.

    Provides context manager support for proper resource management.

    Example:
        >>> with HousePriceScraper(headless=True) as scraper:
        ...     prices = scraper.scrape_address("123 Example Street, Ponsonby")
        ...     print(prices["homes.co.nz"].midpoint)
    """

    def __init__(
        self,
        headless: bool = True,
        rate_limit: bool = True,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        use_cache: bool = True,
        sites: Optional[List[str]] = None,
    ):
        """Initialize the scraper.

        Args:
            headless: Run browser in headless mode
            rate_limit: Apply rate limiting between requests
            min_delay: Minimum delay between requests
            max_delay: Maximum delay between requests
            use_cache: Cache resolved URLs
            sites: Sites to query (default: all supported)
        """
        self.headless = headless
        self.rate_limit = rate_limit
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.use_cache = use_cache
        self.sites = sites or get_supported_sites()

        self._driver: Optional[WebDriver] = None
        self._limiter: Optional[RateLimiter] = None
        self._resolver: Optional[PropertyResolver] = None

    def __enter__(self) -> "HousePriceScraper":
        """Context manager entry."""
        self._driver = init_driver(headless=self.headless)
        if self.rate_limit:
            self._limiter = RateLimiter(self.min_delay, self.max_delay)
        self._resolver = PropertyResolver(
            driver=self._driver,
            use_cache=self.use_cache,
            sites=self.sites,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        if self._resolver:
            self._resolver.close()
            self._resolver = None
        if self._driver:
            self._driver.quit()
            self._driver = None

    def scrape_address(self, address: str) -> Dict[str, PriceEstimate]:
        """Scrape prices for an address.

        Args:
            address: Property address string

        Returns:
            Dict mapping site names to PriceEstimate objects
        """
        if self._driver is None:
            raise RuntimeError("Scraper not initialized. Use as context manager.")

        results: Dict[str, PriceEstimate] = {}

        # Resolve URLs
        resolved = self._resolver.resolve(address)

        # Scrape each URL
        for site, url in resolved.urls.items():
            try:
                if self._limiter:
                    self._limiter.wait_if_needed()

                self._driver = ensure_driver_health(self._driver)
                result = scrape_house_prices(self._driver, url, enable_logging=False)
                results[site] = PriceEstimate.from_scraping_result(result)

            except Exception as e:
                print(f"Error scraping {site}: {e}")
                results[site] = PriceEstimate(source=site)

        return results

    def scrape_urls(self, urls: List[str]) -> List[ScrapingResult]:
        """Scrape prices from specific URLs.

        Args:
            urls: List of property page URLs

        Returns:
            List of ScrapingResult objects
        """
        if self._driver is None:
            raise RuntimeError("Scraper not initialized. Use as context manager.")

        results: List[ScrapingResult] = []

        for url in urls:
            try:
                if self._limiter:
                    self._limiter.wait_if_needed()

                self._driver = ensure_driver_health(self._driver)
                result = scrape_house_prices(self._driver, url, enable_logging=False)
                results.append(result)

            except Exception as e:
                print(f"Error scraping {url}: {e}")

        return results

    def resolve_urls(self, address: str) -> Dict[str, str]:
        """Resolve URLs for an address without scraping.

        Args:
            address: Property address string

        Returns:
            Dict mapping site names to URLs
        """
        if self._resolver is None:
            raise RuntimeError("Scraper not initialized. Use as context manager.")

        resolved = self._resolver.resolve(address)
        return resolved.urls

    def clear_cache(self, address: Optional[str] = None) -> None:
        """Clear the URL cache.

        Args:
            address: Optional specific address to clear (None = clear all)
        """
        if self._resolver:
            self._resolver.clear_cache(address)
