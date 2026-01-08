"""Website health checks - verify sites haven't changed structure.

These are the MOST IMPORTANT tests in the suite. They verify that each
property website still returns valid prices for a known address.

Run these before production use:
    pytest tests/integration/test_site_health.py -v

If any test fails, the site's HTML structure may have changed and
selectors need updating.
"""

import pytest

from tests.fixtures.addresses import (
    ALL_SITES,
    PRIMARY_ADDRESS,
    PRIMARY_ADDRESS_PRICE_RANGE,
)


@pytest.mark.integration
class TestSiteHealth:
    """Verify each site returns expected results for known address."""

    @pytest.mark.parametrize(
        "site",
        ALL_SITES,
        ids=ALL_SITES,
    )
    def test_site_returns_valid_price(self, site: str):
        """Each site returns a price in expected range for known property.

        This test verifies:
        1. The site's search/autocomplete finds the property
        2. The price selectors extract a valid price
        3. The price is in a reasonable range for the property

        If this test fails, the site may have changed its HTML structure.
        """
        from nz_house_prices.api import get_prices

        results = get_prices(PRIMARY_ADDRESS, sites=[site])

        # Site should return a result
        assert site in results, f"{site} returned no results"
        estimate = results[site]

        # Must have at least one price value
        has_price = (
            estimate.midpoint is not None
            or estimate.lower is not None
            or estimate.upper is not None
        )
        assert has_price, (
            f"{site} returned no prices - site structure may have changed. Result: {estimate}"
        )

        # Price should be in reasonable range for this property
        price = estimate.midpoint or estimate.lower or estimate.upper
        min_price, max_price = PRIMARY_ADDRESS_PRICE_RANGE
        assert min_price <= price <= max_price, (
            f"{site} returned ${price:,.0f}, "
            f"expected ${min_price:,.0f}-${max_price:,.0f}. "
            "Price extraction may be broken or property value changed significantly."
        )

    def test_all_sites_return_results(self):
        """At least 4 of 5 sites should return valid prices.

        This test catches cases where multiple sites break simultaneously,
        which might indicate a systemic issue rather than individual site changes.
        """
        from nz_house_prices.api import get_prices

        results = get_prices(PRIMARY_ADDRESS)

        # Count successful results
        successful_sites = []
        failed_sites = []

        for site, estimate in results.items():
            has_price = (
                estimate.midpoint is not None
                or estimate.lower is not None
                or estimate.upper is not None
            )
            if has_price:
                successful_sites.append(site)
            else:
                failed_sites.append(site)

        # At least 4 of 5 sites should work
        min_required = 4
        assert len(successful_sites) >= min_required, (
            f"Only {len(successful_sites)}/{len(ALL_SITES)} sites returned prices. "
            f"Failed sites: {failed_sites}. "
            "Multiple sites may have changed structure."
        )

    def test_prices_are_consistent_across_sites(self):
        """Prices from different sites should be roughly consistent.

        If one site returns a vastly different price, it may be scraping
        the wrong property or extracting prices incorrectly.
        """
        from nz_house_prices.api import get_prices

        results = get_prices(PRIMARY_ADDRESS)

        # Collect all midpoint prices
        prices = []
        for site, estimate in results.items():
            if estimate.midpoint:
                prices.append((site, estimate.midpoint))

        if len(prices) < 2:
            pytest.skip("Not enough prices to compare consistency")

        # Calculate mean and check for outliers
        price_values = [p[1] for p in prices]
        mean_price = sum(price_values) / len(price_values)

        # Each price should be within 50% of the mean
        # (property estimates can vary significantly between sites)
        tolerance = 0.5
        for site, price in prices:
            deviation = abs(price - mean_price) / mean_price
            assert deviation <= tolerance, (
                f"{site} returned ${price:,.0f}, which deviates "
                f"{deviation:.0%} from mean ${mean_price:,.0f}. "
                "This site may be scraping the wrong property."
            )


@pytest.mark.integration
class TestSiteAvailability:
    """Verify sites are accessible and responding."""

    @pytest.mark.parametrize("site", ALL_SITES)
    def test_site_homepage_loads(self, site: str):
        """Each site's homepage should be accessible."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            try:
                url = f"https://www.{site}"
                response = page.goto(url, wait_until="domcontentloaded", timeout=15000)

                assert response is not None, f"{site} returned no response"
                assert response.ok, (
                    f"{site} returned HTTP {response.status}. "
                    "Site may be down or blocking requests."
                )
            finally:
                context.close()
                browser.close()
