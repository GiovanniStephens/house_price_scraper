"""Main address-to-URL resolution logic."""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from playwright.sync_api import Page

from nz_house_prices.core.driver import create_page
from nz_house_prices.discovery.address import normalize_address
from nz_house_prices.discovery.cache import URLCache
from nz_house_prices.sites import SITE_HANDLERS, BaseSite, SearchResult


@dataclass
class ResolvedProperty:
    """A property with resolved URLs across sites."""

    address: str
    urls: Dict[str, str]  # site -> URL
    confidence: Dict[str, float]  # site -> confidence score
    resolved_at: float


class PropertyResolver:
    """Resolve property addresses to URLs across multiple sites.

    This is the main entry point for address-to-URL discovery.
    """

    def __init__(
        self,
        page: Optional[Page] = None,
        use_cache: bool = True,
        sites: Optional[List[str]] = None,
    ):
        """Initialize the property resolver.

        Args:
            page: Optional Playwright Page to reuse (creates new if not provided)
            use_cache: Whether to use URL caching
            sites: Optional list of sites to query (default: all supported sites)
        """
        self._page = page
        self._owns_page = False
        self._cache = URLCache() if use_cache else None
        self._sites = sites or list(SITE_HANDLERS.keys())
        self._site_handlers: Dict[str, BaseSite] = {}

    @property
    def page(self) -> Page:
        """Get or create Page instance."""
        if self._page is None:
            self._page = create_page()
            self._owns_page = True
        return self._page

    def close(self) -> None:
        """Close resources."""
        # Close site handlers
        for handler in self._site_handlers.values():
            handler.close()
        self._site_handlers.clear()

        # Close page if we own it
        if self._owns_page and self._page is not None:
            try:
                context = self._page.context
                self._page.close()
                context.close()
            except Exception:
                pass
            self._page = None
            self._owns_page = False

    def __enter__(self) -> "PropertyResolver":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def _get_site_handler(self, site: str) -> BaseSite:
        """Get or create a site handler.

        Args:
            site: Site domain name

        Returns:
            Site handler instance
        """
        if site not in self._site_handlers:
            handler_class = SITE_HANDLERS[site]
            self._site_handlers[site] = handler_class(page=self.page)
        return self._site_handlers[site]

    def resolve(
        self,
        address: str,
        sites: Optional[List[str]] = None,
        skip_cache: bool = False,
    ) -> ResolvedProperty:
        """Resolve an address to URLs across multiple sites.

        Args:
            address: The property address to resolve
            sites: Optional list of sites to query (uses instance default if not provided)
            skip_cache: Skip cache lookup (but still cache results)

        Returns:
            ResolvedProperty with resolved URLs
        """
        normalized = normalize_address(address)
        target_sites = sites or self._sites

        urls: Dict[str, str] = {}
        confidence: Dict[str, float] = {}

        # Check cache first
        if self._cache and not skip_cache:
            for site in target_sites:
                cached_url = self._cache.get(normalized, site)
                if cached_url:
                    urls[site] = cached_url
                    confidence[site] = 1.0  # High confidence for cached

        # Resolve uncached sites
        uncached_sites = [s for s in target_sites if s not in urls]

        for site in uncached_sites:
            try:
                handler = self._get_site_handler(site)

                # Search for the property (this returns results with URLs and confidence)
                search_results = handler.search_property(normalized)

                if search_results and search_results[0].url:
                    best_result = search_results[0]
                    urls[site] = best_result.url
                    confidence[site] = best_result.confidence

                    # Cache the result
                    if self._cache:
                        self._cache.set(normalized, site, best_result.url, confidence[site])

            except Exception as e:
                print(f"Error resolving {site}: {e}")
                continue

        return ResolvedProperty(
            address=normalized,
            urls=urls,
            confidence=confidence,
            resolved_at=time.time(),
        )

    def resolve_single(
        self,
        address: str,
        site: str,
        skip_cache: bool = False,
    ) -> Optional[str]:
        """Resolve an address to a URL for a single site.

        Args:
            address: The property address
            site: The site domain
            skip_cache: Skip cache lookup

        Returns:
            URL string or None if not found
        """
        result = self.resolve(address, sites=[site], skip_cache=skip_cache)
        return result.urls.get(site)

    def search(
        self,
        address: str,
        sites: Optional[List[str]] = None,
    ) -> Dict[str, List[SearchResult]]:
        """Search for a property across multiple sites.

        Unlike resolve(), this returns all search results,
        not just the best match.

        Args:
            address: The property address
            sites: Optional list of sites to search

        Returns:
            Dict mapping site names to lists of SearchResult
        """
        normalized = normalize_address(address)
        target_sites = sites or self._sites

        results: Dict[str, List[SearchResult]] = {}

        for site in target_sites:
            try:
                handler = self._get_site_handler(site)
                search_results = handler.search_property(normalized)
                results[site] = search_results
            except Exception as e:
                print(f"Error searching {site}: {e}")
                results[site] = []

        return results

    def get_cached_urls(self, address: str) -> Dict[str, str]:
        """Get all cached URLs for an address.

        Args:
            address: The property address

        Returns:
            Dict mapping site names to cached URLs
        """
        if not self._cache:
            return {}

        normalized = normalize_address(address)
        return self._cache.get_all(normalized)

    def clear_cache(self, address: Optional[str] = None) -> None:
        """Clear cached URLs.

        Args:
            address: Optional address to clear (None = clear all)
        """
        if not self._cache:
            return

        if address:
            normalized = normalize_address(address)
            self._cache.invalidate(normalized)
        else:
            self._cache.clear()


def resolve_property_urls(
    address: str,
    sites: Optional[List[str]] = None,
    use_cache: bool = True,
) -> Dict[str, str]:
    """Convenience function to resolve property URLs.

    Args:
        address: The property address
        sites: Optional list of sites to query
        use_cache: Whether to use URL caching

    Returns:
        Dict mapping site names to URLs
    """
    with PropertyResolver(use_cache=use_cache, sites=sites) as resolver:
        result = resolver.resolve(address)
        return result.urls
