"""Parallel execution for concurrent site scraping."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from threading import Lock
from typing import Dict, List, Optional

from selenium.webdriver.remote.webdriver import WebDriver

from nz_house_prices.core.driver import init_driver
from nz_house_prices.core.scraper import scrape_house_prices
from nz_house_prices.core.selectors import get_supported_sites
from nz_house_prices.discovery.address import normalize_address
from nz_house_prices.discovery.cache import URLCache
from nz_house_prices.models.results import PriceEstimate
from nz_house_prices.sites import SITE_HANDLERS


class WebDriverPool:
    """Thread-safe pool of WebDriver instances.

    Manages a pool of Chrome WebDriver instances for parallel scraping.
    Each driver can be acquired by a thread, used, and then released back.
    """

    def __init__(self, size: int = 3, headless: bool = True):
        """Initialize the driver pool.

        Args:
            size: Number of drivers in the pool
            headless: Whether to run browsers in headless mode
        """
        self.size = size
        self.headless = headless
        self._pool: Queue = Queue()
        self._drivers: List[WebDriver] = []
        self._lock = Lock()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all drivers in the pool."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            for _ in range(self.size):
                driver = init_driver(headless=self.headless)
                self._drivers.append(driver)
                self._pool.put(driver)

            self._initialized = True

    def acquire(self, timeout: float = 60.0) -> WebDriver:
        """Acquire a driver from the pool.

        Args:
            timeout: Maximum time to wait for a driver

        Returns:
            WebDriver instance

        Raises:
            TimeoutError: If no driver available within timeout
        """
        if not self._initialized:
            self.initialize()

        try:
            return self._pool.get(timeout=timeout)
        except Exception:
            raise TimeoutError("No WebDriver available in pool")

    def release(self, driver: WebDriver) -> None:
        """Release a driver back to the pool.

        Args:
            driver: WebDriver to release
        """
        self._pool.put(driver)

    def close_all(self) -> None:
        """Close all drivers and cleanup."""
        with self._lock:
            for driver in self._drivers:
                try:
                    driver.quit()
                except Exception:
                    pass
            self._drivers.clear()
            self._initialized = False

            # Clear the queue
            while not self._pool.empty():
                try:
                    self._pool.get_nowait()
                except Exception:
                    break

    def __enter__(self) -> "WebDriverPool":
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close_all()


def _scrape_site_with_driver(
    site: str,
    address: str,
    driver: WebDriver,
    cache: Optional[URLCache] = None,
) -> PriceEstimate:
    """Scrape a single site using provided driver.

    Combines URL resolution and price scraping in one operation.

    Args:
        site: Site domain name
        address: Property address to search
        driver: WebDriver to use
        cache: Optional URL cache

    Returns:
        PriceEstimate with results
    """
    try:
        normalized = normalize_address(address)
        handler_class = SITE_HANDLERS.get(site)

        if not handler_class:
            return PriceEstimate(source=site)

        # Create handler with the provided driver
        handler = handler_class(driver=driver)

        # Check cache first
        cached_url = None
        if cache:
            cached_url = cache.get(normalized, site)

        if cached_url:
            url = cached_url
        else:
            # Search for the property URL
            results = handler.search_property(normalized)
            if results and results[0].url:
                url = results[0].url
                # Cache the result
                if cache:
                    cache.set(normalized, site, url, results[0].confidence)
            else:
                return PriceEstimate(source=site)

        # Scrape prices from the URL
        result = scrape_house_prices(driver, url, enable_logging=False)
        return PriceEstimate.from_scraping_result(result)

    except Exception as e:
        print(f"Error scraping {site}: {e}")
        return PriceEstimate(source=site)


def _scrape_api_site(
    site: str,
    address: str,
    cache: Optional[URLCache] = None,
    driver_pool: Optional[WebDriverPool] = None,
) -> PriceEstimate:
    """Scrape an API-based site (propertyvalue, realestate).

    These sites use HTTP APIs for address lookup but still need
    a driver for price scraping from the property page.

    Args:
        site: Site domain name
        address: Property address to search
        cache: Optional URL cache
        driver_pool: Driver pool for price scraping

    Returns:
        PriceEstimate with results
    """
    try:
        normalized = normalize_address(address)
        handler_class = SITE_HANDLERS.get(site)

        if not handler_class:
            return PriceEstimate(source=site)

        # API-based sites don't need a driver for search
        handler = handler_class(driver=None)

        # Check cache first
        cached_url = None
        if cache:
            cached_url = cache.get(normalized, site)

        if cached_url:
            url = cached_url
        else:
            # Search using the API (no driver needed)
            results = handler.search_property(normalized)
            if results and results[0].url:
                url = results[0].url
                if cache:
                    cache.set(normalized, site, url, results[0].confidence)
            else:
                return PriceEstimate(source=site)

        # Need a driver for price scraping
        if driver_pool:
            driver = driver_pool.acquire()
            try:
                result = scrape_house_prices(driver, url, enable_logging=False)
                return PriceEstimate.from_scraping_result(result)
            finally:
                driver_pool.release(driver)
        else:
            # Fallback: create a temporary driver
            driver = init_driver()
            try:
                result = scrape_house_prices(driver, url, enable_logging=False)
                return PriceEstimate.from_scraping_result(result)
            finally:
                driver.quit()

    except Exception as e:
        print(f"Error scraping {site}: {e}")
        return PriceEstimate(source=site)


# Sites that use HTTP APIs (don't need driver for URL resolution)
API_SITES = {"propertyvalue.co.nz", "realestate.co.nz"}

# Sites that need Selenium for URL resolution
SELENIUM_SITES = {"homes.co.nz", "qv.co.nz", "oneroof.co.nz"}


class ParallelScraper:
    """Coordinate parallel scraping across multiple sites.

    Uses a thread pool to scrape multiple sites simultaneously.
    Selenium-based sites each get their own driver.
    API-based sites share a smaller driver pool for price scraping.
    """

    def __init__(
        self,
        max_workers: int = 5,
        headless: bool = True,
        use_cache: bool = True,
    ):
        """Initialize the parallel scraper.

        Args:
            max_workers: Maximum parallel threads
            headless: Run browsers in headless mode
            use_cache: Whether to cache resolved URLs
        """
        self.max_workers = max_workers
        self.headless = headless
        self.use_cache = use_cache

        self._cache: Optional[URLCache] = None
        self._driver_pool: Optional[WebDriverPool] = None
        self._selenium_drivers: Dict[str, WebDriver] = {}

    def __enter__(self) -> "ParallelScraper":
        """Context manager entry."""
        if self.use_cache:
            self._cache = URLCache()

        # Create a driver pool for API sites' price scraping
        self._driver_pool = WebDriverPool(size=3, headless=self.headless)

        # Pre-create drivers for Selenium sites (they run in parallel)
        for site in SELENIUM_SITES:
            self._selenium_drivers[site] = init_driver(headless=self.headless)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        # Close Selenium site drivers
        for driver in self._selenium_drivers.values():
            try:
                driver.quit()
            except Exception:
                pass
        self._selenium_drivers.clear()

        # Close the driver pool
        if self._driver_pool:
            self._driver_pool.close_all()
            self._driver_pool = None

    def scrape_all_sites(
        self,
        address: str,
        sites: Optional[List[str]] = None,
    ) -> Dict[str, PriceEstimate]:
        """Scrape all sites in parallel.

        Args:
            address: Property address to search
            sites: Optional list of sites (default: all supported)

        Returns:
            Dict mapping site names to PriceEstimate objects
        """
        target_sites = sites or get_supported_sites()
        results: Dict[str, PriceEstimate] = {}

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for site in target_sites:
                if site in API_SITES:
                    # API sites use shared driver pool
                    future = executor.submit(
                        _scrape_api_site,
                        site,
                        address,
                        self._cache,
                        self._driver_pool,
                    )
                elif site in SELENIUM_SITES:
                    # Selenium sites use dedicated drivers
                    driver = self._selenium_drivers.get(site)
                    if driver:
                        future = executor.submit(
                            _scrape_site_with_driver,
                            site,
                            address,
                            driver,
                            self._cache,
                        )
                    else:
                        continue
                else:
                    continue

                futures[future] = site

            # Collect results as they complete
            for future in as_completed(futures):
                site = futures[future]
                try:
                    results[site] = future.result()
                except Exception as e:
                    print(f"Error getting result for {site}: {e}")
                    results[site] = PriceEstimate(source=site)

        elapsed = time.time() - start_time
        print(f"Parallel scraping completed in {elapsed:.1f}s")

        return results


def get_prices_parallel(
    address: str,
    sites: Optional[List[str]] = None,
    use_cache: bool = True,
    headless: bool = True,
) -> Dict[str, PriceEstimate]:
    """Get house prices using parallel execution.

    This is a convenience function that creates a ParallelScraper
    and scrapes all sites in parallel.

    Args:
        address: Property address to search
        sites: Optional list of sites to query
        use_cache: Whether to cache resolved URLs
        headless: Run browsers in headless mode

    Returns:
        Dict mapping site names to PriceEstimate objects
    """
    with ParallelScraper(
        max_workers=5,
        headless=headless,
        use_cache=use_cache,
    ) as scraper:
        return scraper.scrape_all_sites(address, sites)
