"""High-level public API for NZ House Prices."""

from typing import Dict, List, Optional

from playwright.sync_api import Page

from nz_house_prices.core.driver import BrowserManager
from nz_house_prices.core.parallel import get_prices_parallel
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
    parallel: bool = True,
) -> Dict[str, PriceEstimate]:
    """Get house price estimates for an address from NZ real estate sites.

    This is the main entry point for getting house prices by address.

    Args:
        address: Full address string (e.g., "123 Example Street, Ponsonby, Auckland")
        sites: Optional list of sites to query. Defaults to all supported sites.
        use_cache: Whether to cache resolved URLs for faster future lookups.
        rate_limit: Whether to apply rate limiting between requests (sequential mode only).
        min_delay: Minimum delay between requests in seconds (sequential mode only).
        max_delay: Maximum delay between requests in seconds (sequential mode only).
        parallel: Whether to use parallel execution (default: True, ~3-5x faster).

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

    # Use parallel execution for faster results (default)
    if parallel:
        return get_prices_parallel(
            address=address,
            sites=target_sites,
            use_cache=use_cache,
        )

    # Sequential execution (legacy mode)
    return _get_prices_sequential(
        address=address,
        sites=target_sites,
        use_cache=use_cache,
        rate_limit=rate_limit,
        min_delay=min_delay,
        max_delay=max_delay,
    )


def _get_prices_sequential(
    address: str,
    sites: List[str],
    use_cache: bool = True,
    rate_limit: bool = True,
    min_delay: float = 2.0,
    max_delay: float = 5.0,
) -> Dict[str, PriceEstimate]:
    """Get prices using sequential execution (legacy mode).

    Args:
        address: Property address
        sites: List of sites to query
        use_cache: Whether to cache URLs
        rate_limit: Whether to apply rate limiting
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests

    Returns:
        Dictionary mapping site names to PriceEstimate objects
    """
    results: Dict[str, PriceEstimate] = {}
    limiter = RateLimiter(min_delay=min_delay, max_delay=max_delay) if rate_limit else None

    with BrowserManager() as browser_manager:
        page = browser_manager.new_page()

        # Resolve URLs for the address
        with PropertyResolver(page=page, use_cache=use_cache, sites=sites) as resolver:
            resolved = resolver.resolve(address)

        # Scrape each resolved URL
        for site, url in resolved.urls.items():
            try:
                if limiter:
                    limiter.wait_if_needed()

                result = scrape_house_prices(page, url, enable_logging=False)
                results[site] = PriceEstimate.from_scraping_result(result)

            except Exception as e:
                print(f"Error scraping {site}: {e}")
                results[site] = PriceEstimate(
                    source=site,
                    midpoint=None,
                    lower=None,
                    upper=None,
                )

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
        ...     "https://homes.co.nz/address/auckland/ponsonby/123-example-street/xxxxx"
        ... ])
        >>> print(results[0].prices["midpoint"])
    """
    results: List[ScrapingResult] = []
    limiter = RateLimiter(min_delay=min_delay, max_delay=max_delay) if rate_limit else None

    with BrowserManager() as browser_manager:
        page = browser_manager.new_page()

        for url in urls:
            try:
                if limiter:
                    limiter.wait_if_needed()

                result = scrape_house_prices(page, url, enable_logging=False)
                results.append(result)

            except Exception as e:
                print(f"Error scraping {url}: {e}")

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

        self._browser_manager: Optional[BrowserManager] = None
        self._page: Optional[Page] = None
        self._limiter: Optional[RateLimiter] = None
        self._resolver: Optional[PropertyResolver] = None

    def __enter__(self) -> "HousePriceScraper":
        """Context manager entry."""
        self._browser_manager = BrowserManager(headless=self.headless)
        self._browser_manager.start()
        self._page = self._browser_manager.new_page()
        if self.rate_limit:
            self._limiter = RateLimiter(self.min_delay, self.max_delay)
        self._resolver = PropertyResolver(
            page=self._page,
            use_cache=self.use_cache,
            sites=self.sites,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        if self._resolver:
            self._resolver.close()
            self._resolver = None
        if self._browser_manager:
            self._browser_manager.close()
            self._browser_manager = None
        self._page = None

    def scrape_address(self, address: str) -> Dict[str, PriceEstimate]:
        """Scrape prices for an address.

        Args:
            address: Property address string

        Returns:
            Dict mapping site names to PriceEstimate objects
        """
        if self._page is None:
            raise RuntimeError("Scraper not initialized. Use as context manager.")

        results: Dict[str, PriceEstimate] = {}

        # Resolve URLs
        resolved = self._resolver.resolve(address)

        # Scrape each URL
        for site, url in resolved.urls.items():
            try:
                if self._limiter:
                    self._limiter.wait_if_needed()

                result = scrape_house_prices(self._page, url, enable_logging=False)
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
        if self._page is None:
            raise RuntimeError("Scraper not initialized. Use as context manager.")

        results: List[ScrapingResult] = []

        for url in urls:
            try:
                if self._limiter:
                    self._limiter.wait_if_needed()

                result = scrape_house_prices(self._page, url, enable_logging=False)
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
