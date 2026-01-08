"""Test the search -> property page -> URL extraction flow.

These tests verify that each site's search autocomplete correctly
finds properties and returns valid URLs. This is a critical step
in the scraping pipeline.

Run with:
    pytest tests/integration/test_search_flow.py -v
"""

import pytest
from playwright.sync_api import sync_playwright

from nz_house_prices.sites import SITE_HANDLERS
from tests.fixtures.addresses import ALL_SITES, PRIMARY_ADDRESS


@pytest.mark.integration
class TestSearchFlow:
    """Verify each site's search autocomplete works."""

    @pytest.fixture(scope="class")
    def browser(self):
        """Shared browser instance for search flow tests."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()

    @pytest.mark.parametrize("site", ALL_SITES)
    def test_search_finds_property(self, browser, site: str):
        """Search returns a valid URL for known address.

        This test verifies:
        1. The site's search input accepts the address
        2. Autocomplete returns results
        3. The best match has a valid URL
        4. The confidence score is reasonable
        """
        context = browser.new_context()
        page = context.new_page()

        try:
            handler_class = SITE_HANDLERS.get(site)
            if handler_class is None:
                pytest.skip(f"No handler for {site}")

            handler = handler_class(page=page)
            results = handler.search_property(PRIMARY_ADDRESS)

            # Should find at least one result
            assert results, (
                f"{site} search returned no results. Search autocomplete may have changed."
            )

            # Best result should have a URL
            best_result = results[0]
            assert best_result.url, f"{site} returned result without URL. Result: {best_result}"

            # URL should look valid
            assert best_result.url.startswith(("/", "http")), (
                f"{site} returned invalid URL format: {best_result.url}"
            )

            # Confidence should be reasonable
            assert best_result.confidence > 0.3, (
                f"{site} returned low confidence ({best_result.confidence:.2f}). "
                "Address matching may have changed."
            )

        finally:
            context.close()

    @pytest.mark.parametrize("site", ALL_SITES)
    def test_search_returns_matching_address(self, browser, site: str):
        """Search result address should match the query.

        This helps detect when we're getting wrong properties due to
        autocomplete changes or address disambiguation issues.
        """
        context = browser.new_context()
        page = context.new_page()

        try:
            handler_class = SITE_HANDLERS.get(site)
            if handler_class is None:
                pytest.skip(f"No handler for {site}")

            handler = handler_class(page=page)
            results = handler.search_property(PRIMARY_ADDRESS)

            if not results:
                pytest.skip(f"{site} returned no results")

            best_result = results[0]

            # Result address should contain key parts of the query
            result_address = best_result.address.lower()
            query_parts = PRIMARY_ADDRESS.lower().split(",")[0].split()  # Street part

            # At least the street number should be in the result
            street_number = query_parts[0] if query_parts else ""
            if street_number.isdigit() or (
                street_number[:-1].isdigit() and street_number[-1].isalpha()
            ):
                assert street_number in result_address, (
                    f"{site} returned address without street number {street_number}. "
                    f"Got: {best_result.address}"
                )

        finally:
            context.close()


@pytest.mark.integration
class TestPropertyURLValidity:
    """Verify that discovered property URLs are valid."""

    @pytest.fixture(scope="class")
    def browser(self):
        """Shared browser instance for URL validation tests."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()

    @pytest.mark.parametrize("site", ALL_SITES)
    def test_property_url_loads(self, browser, site: str):
        """Discovered property URLs should load successfully.

        This catches issues where we get URLs that return 404 or redirect
        to error pages.
        """
        context = browser.new_context()
        page = context.new_page()

        try:
            handler_class = SITE_HANDLERS.get(site)
            if handler_class is None:
                pytest.skip(f"No handler for {site}")

            handler = handler_class(page=page)
            results = handler.search_property(PRIMARY_ADDRESS)

            if not results or not results[0].url:
                pytest.skip(f"{site} returned no URL")

            url = results[0].url

            # Convert relative URLs to absolute
            if url.startswith("/"):
                url = f"https://www.{site}{url}"

            # Load the property page
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)

            assert response is not None, f"No response from {url}"
            assert response.ok, (
                f"Property URL returned HTTP {response.status}: {url}. "
                "URL format or routing may have changed."
            )

        finally:
            context.close()
