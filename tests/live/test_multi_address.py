"""Extended live tests with multiple addresses.

Run with: pytest tests/live/ --live -v

These tests verify that all 5 sites return price estimates for diverse addresses.
"""

import pytest

from tests.fixtures.addresses import ALL_SITES, DIVERSE_ADDRESSES


@pytest.mark.live
class TestMultiAddressLive:
    """Test multiple addresses against all sites."""

    @pytest.mark.parametrize(
        "address_name,address",
        list(DIVERSE_ADDRESSES.items()),
        ids=list(DIVERSE_ADDRESSES.keys()),
    )
    def test_all_sites_return_estimates(self, address_name: str, address: str):
        """Each address should get estimates from all 5 sites.

        This is the key validation that the scraper works for diverse addresses.
        """
        from nz_house_prices.api import get_prices

        results = get_prices(address)

        # Track results
        successful = []
        failed = []

        for site in ALL_SITES:
            if site not in results:
                failed.append((site, "no result returned"))
                continue

            estimate = results[site]
            has_price = (
                estimate.midpoint is not None
                or estimate.lower is not None
                or estimate.upper is not None
            )

            if has_price:
                price = estimate.midpoint or estimate.lower or estimate.upper
                successful.append((site, price))
            else:
                failed.append((site, "no price extracted"))

        # Report results
        print(f"\n{address_name}: {address}")
        print(f"  Successful: {len(successful)}/5")
        for site, price in successful:
            print(f"    ✓ {site}: ${price:,.0f}")
        for site, reason in failed:
            print(f"    ✗ {site}: {reason}")

        # All 5 sites should return prices
        assert len(successful) == 5, (
            f"Only {len(successful)}/5 sites returned prices for {address_name}. "
            f"Failed: {[f[0] for f in failed]}"
        )

    def test_summary_all_addresses(self):
        """Summary test showing results for all addresses."""
        from nz_house_prices.api import get_prices

        print("\n" + "=" * 70)
        print("LIVE TEST SUMMARY: All Addresses x All Sites")
        print("=" * 70)

        total_success = 0
        total_tests = 0

        for name, address in DIVERSE_ADDRESSES.items():
            results = get_prices(address)

            site_results = []
            for site in ALL_SITES:
                total_tests += 1
                if site in results:
                    estimate = results[site]
                    has_price = (
                        estimate.midpoint is not None
                        or estimate.lower is not None
                        or estimate.upper is not None
                    )
                    if has_price:
                        total_success += 1
                        price = estimate.midpoint or estimate.lower or estimate.upper
                        site_results.append(f"${price/1000:.0f}K")
                    else:
                        site_results.append("FAIL")
                else:
                    site_results.append("MISS")

            print(f"\n{name}:")
            print(f"  {address}")
            for site, result in zip(ALL_SITES, site_results):
                status = "✓" if result not in ("FAIL", "MISS") else "✗"
                print(f"    {status} {site}: {result}")

        print("\n" + "=" * 70)
        print(f"TOTAL: {total_success}/{total_tests} successful")
        print("=" * 70)

        # At least 80% success rate
        success_rate = total_success / total_tests
        assert success_rate >= 0.8, (
            f"Only {success_rate:.0%} success rate. "
            f"Expected at least 80%."
        )
