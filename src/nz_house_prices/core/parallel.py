"""Parallel scraping execution with Playwright."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright

from nz_house_prices.core.scraper import scrape_house_prices
from nz_house_prices.core.selectors import get_supported_sites
from nz_house_prices.discovery.address import normalize_address
from nz_house_prices.discovery.cache import URLCache
from nz_house_prices.models.results import PriceEstimate
from nz_house_prices.sites import SITE_HANDLERS

# Sites that use HTTP APIs for search (no browser needed for URL resolution)
API_SITES = {"realestate.co.nz", "propertyvalue.co.nz"}

# Sites that need browser-based search
BROWSER_SITES = {"homes.co.nz", "qv.co.nz", "oneroof.co.nz"}


def _scrape_site(site: str, url: str, headless: bool = True) -> PriceEstimate:
    """Scrape a single site with its own browser context.

    Args:
        site: Site name
        url: Property URL to scrape
        headless: Whether to run headless

    Returns:
        PriceEstimate with results
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            )
            page = context.new_page()

            result = scrape_house_prices(page, url, enable_logging=True)

            context.close()
            browser.close()

            return PriceEstimate.from_scraping_result(result)
    except Exception as e:
        print(f"Error scraping {site}: {e}")
        return PriceEstimate(source=site)


def _resolve_url_api(site: str, address: str) -> Optional[str]:
    """Resolve property URL using API-based site handlers.

    Args:
        site: Site name
        address: Address to search for

    Returns:
        Property URL or None
    """
    handler_class = SITE_HANDLERS.get(site)
    if not handler_class:
        return None

    try:
        handler = handler_class(page=None)
        results = handler.search_property(address)
        if results and results[0].url:
            return results[0].url
    except Exception:
        pass
    return None


def _resolve_url_browser(site: str, address: str, headless: bool = True) -> Optional[str]:
    """Resolve property URL using browser-based site handlers.

    Args:
        site: Site name
        address: Address to search for
        headless: Whether to run headless

    Returns:
        Property URL or None
    """
    handler_class = SITE_HANDLERS.get(site)
    if not handler_class:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            )
            page = context.new_page()

            handler = handler_class(page=page)
            results = handler.search_property(address)

            context.close()
            browser.close()

            if results and results[0].url:
                return results[0].url
    except Exception as e:
        print(f"Error resolving {site}: {e}")
    return None


def _scrape_site_with_resolution(
    site: str,
    address: str,
    cache: Optional[URLCache],
    headless: bool,
) -> PriceEstimate:
    """Resolve URL and scrape a site.

    Args:
        site: Site name
        address: Address to search
        cache: Optional URL cache
        headless: Whether to run headless

    Returns:
        PriceEstimate with results
    """
    normalized = normalize_address(address)

    # Check cache first
    url = None
    if cache:
        url = cache.get(normalized, site)

    # Resolve URL if not cached
    if not url:
        if site in API_SITES:
            url = _resolve_url_api(site, normalized)
        else:
            url = _resolve_url_browser(site, normalized, headless)

        # Cache the URL
        if url and cache:
            cache.set(normalized, site, url, 0.9)

    if not url:
        print(f"No URL resolved for {site}")
        return PriceEstimate(source=site)

    # Scrape the property page
    return _scrape_site(site, url, headless)


class ParallelScraper:
    """Coordinate parallel scraping across multiple sites."""

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

    def __enter__(self) -> "ParallelScraper":
        """Context manager entry."""
        if self.use_cache:
            self._cache = URLCache()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        pass

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
                future = executor.submit(
                    _scrape_site_with_resolution,
                    site,
                    address,
                    self._cache,
                    self.headless,
                )
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
