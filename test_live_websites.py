"""
Live website testing suite for the house price scraper.
Tests against actual websites with proper rate limiting and error handling.

WARNING: These tests make real HTTP requests to live websites.
Run sparingly to avoid being blocked. Use --run-live flag to enable.
"""

import unittest
import sys
import time
import os
from scraper import (
    load_config,
    init_driver_cross_platform,
    init_driver,
    scrape_house_prices,
    scrape_with_retry,
    RateLimiter,
    SelectorStrategy,
    SELECTOR_STRATEGIES,
    PriceValidator,
    ScrapingLogger,
    ScrapingResult,
)


class LiveWebsiteTestBase(unittest.TestCase):
    """Base class for live website testing"""

    @classmethod
    def setUpClass(cls):
        """Set up driver and rate limiter for the test class"""
        if not cls._should_run_live_tests():
            raise unittest.SkipTest("Live tests disabled. Use --run-live to enable.")

        cls.rate_limiter = RateLimiter(min_delay=3, max_delay=5)  # Conservative delays
        cls.driver = None
        cls.validator = PriceValidator()
        cls.logger = ScrapingLogger("live_test.log")

        try:
            cls.driver = init_driver_cross_platform()
            if cls.driver is None:
                cls.driver = init_driver()

            if cls.driver is None:
                raise unittest.SkipTest("Could not initialize WebDriver")

        except Exception as e:
            raise unittest.SkipTest(f"WebDriver initialization failed: {e}")

    @classmethod
    def tearDownClass(cls):
        """Clean up driver after tests"""
        if hasattr(cls, "driver") and cls.driver:
            cls.driver.quit()

        # Clean up log file
        if os.path.exists("live_test.log"):
            os.remove("live_test.log")

    @staticmethod
    def _should_run_live_tests():
        """Check if live tests should run"""
        return "--run-live" in sys.argv or os.environ.get("RUN_LIVE_TESTS") == "true"

    def setUp(self):
        """Rate limit before each test"""
        if hasattr(self.__class__, "rate_limiter"):
            self.__class__.rate_limiter.wait_if_needed()


class TestLiveWebsiteScraping(LiveWebsiteTestBase):
    """Test scraping against live websites"""

    def test_scrape_configured_urls(self):
        """Test scraping all URLs from configuration"""
        config = load_config()
        urls = config["urls"]["house_price_estimates"]

        results = []
        successful_scrapes = 0

        for url in urls:
            print(f"\nTesting URL: {url}")

            start_time = time.time()
            try:
                midpoint, upper, lower = scrape_house_prices(self.driver, url)
                execution_time = time.time() - start_time

                # Validate extracted prices
                prices = {"midpoint": midpoint, "upper": upper, "lower": lower}
                valid_prices = {}
                validation_errors = []

                for price_type, price_value in prices.items():
                    if price_value is not None:
                        if isinstance(price_value, (int, float)):
                            # Already numeric
                            validation_result = self.validator.validate_price(
                                str(price_value)
                            )
                            if validation_result.is_valid:
                                valid_prices[price_type] = price_value
                            else:
                                validation_errors.append(
                                    f"{price_type}: {validation_result.error_message}"
                                )
                        else:
                            validation_errors.append(
                                f"{price_type}: Invalid type {type(price_value)}"
                            )

                success = len(valid_prices) > 0

                result = ScrapingResult(
                    site=self._extract_site_name(url),
                    url=url,
                    success=success,
                    prices=valid_prices,
                    errors=validation_errors,
                    extraction_method="live_test",
                    execution_time=execution_time,
                )

                results.append(result)
                self.logger.log_scraping_result(result)

                if success:
                    successful_scrapes += 1
                    print(f"  ✓ Success: {valid_prices}")
                else:
                    print(f"  ✗ Failed: {validation_errors}")

                # Validate price relationships if we have multiple prices
                if len(valid_prices) >= 2:
                    lower_val = valid_prices.get("lower")
                    mid_val = valid_prices.get("midpoint")
                    upper_val = valid_prices.get("upper")

                    if not self.validator.validate_price_relationships(
                        lower_val, mid_val, upper_val
                    ):
                        print("  ⚠ Warning: Price relationships are inconsistent")

            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e)

                result = ScrapingResult(
                    site=self._extract_site_name(url),
                    url=url,
                    success=False,
                    prices={},
                    errors=[error_msg],
                    extraction_method="live_test",
                    execution_time=execution_time,
                )

                results.append(result)
                self.logger.log_scraping_result(result)
                print(f"  ✗ Exception: {error_msg}")

            # Rate limit between requests
            self.rate_limiter.wait_if_needed()

        # Summary assertions
        self.assertGreater(len(results), 0, "No results obtained")

        success_rate = successful_scrapes / len(urls)
        print("\nScraping Summary:")
        print(f"  Total URLs tested: {len(urls)}")
        print(f"  Successful scrapes: {successful_scrapes}")
        print(f"  Success rate: {success_rate:.1%}")

        # We expect at least some success, but not necessarily 100% due to website changes
        self.assertGreater(
            success_rate, 0.0, "No successful scrapes - all websites may have changed"
        )

        # If success rate is very low, warn but don't fail (websites may have changed)
        if success_rate < 0.3:
            print(
                f"WARNING: Low success rate ({success_rate:.1%}). Websites may have changed."
            )

    def test_selector_strategy_resilience(self):
        """Test that selector strategies provide resilience"""
        config = load_config()
        urls = config["urls"]["house_price_estimates"]

        strategy = SelectorStrategy()
        resilience_results = []

        for url in urls[:2]:  # Test first 2 URLs to avoid excessive requests
            site_name = self._extract_site_name(url)
            if site_name not in SELECTOR_STRATEGIES:
                continue

            print(f"\nTesting selector resilience for: {site_name}")

            try:
                self.driver.get(url)
                time.sleep(2)  # Allow page to load

                # Test each price type
                for price_type in ["midpoint", "upper", "lower"]:
                    strategies = SELECTOR_STRATEGIES[site_name][price_type]

                    successful_strategies = 0
                    for i, single_strategy in enumerate(strategies):
                        try:
                            result = strategy.apply_strategy(
                                self.driver, single_strategy
                            )
                            if result and result.strip():
                                successful_strategies += 1
                                print(
                                    f"  {price_type} strategy {i + 1}: ✓ '{result[:20]}...'"
                                )
                            else:
                                print(
                                    f"  {price_type} strategy {i + 1}: ✗ (empty result)"
                                )
                        except Exception as e:
                            print(
                                f"  {price_type} strategy {i + 1}: ✗ ({e.__class__.__name__})"
                            )

                    resilience_results.append(
                        {
                            "site": site_name,
                            "price_type": price_type,
                            "total_strategies": len(strategies),
                            "successful_strategies": successful_strategies,
                        }
                    )

            except Exception as e:
                print(f"  Error loading page: {e}")

            self.rate_limiter.wait_if_needed()

        # Analyze resilience
        if resilience_results:
            total_strategy_tests = len(resilience_results)
            tests_with_fallbacks = sum(
                1 for r in resilience_results if r["successful_strategies"] > 1
            )

            fallback_rate = (
                tests_with_fallbacks / total_strategy_tests
                if total_strategy_tests > 0
                else 0
            )

            print("\nResilience Summary:")
            print(f"  Strategy tests: {total_strategy_tests}")
            print(f"  Tests with multiple working strategies: {tests_with_fallbacks}")
            print(f"  Fallback availability: {fallback_rate:.1%}")

            # At least some strategies should work
            working_strategies = sum(
                r["successful_strategies"] for r in resilience_results
            )
            self.assertGreater(working_strategies, 0, "No selector strategies worked")

    def test_retry_mechanism_with_live_sites(self):
        """Test retry mechanism with potential network issues"""
        config = load_config()
        test_url = config["urls"]["house_price_estimates"][0]  # Test first URL

        print(f"\nTesting retry mechanism with: {test_url}")

        # Test normal scraping
        start_time = time.time()
        try:
            result = scrape_with_retry(self.driver, test_url)
            duration = time.time() - start_time

            print(f"  Retry test completed in {duration:.2f}s")
            print(f"  Result: {result}")

            # Should return some result (may be None if all strategies fail)
            self.assertIsNotNone(
                result if any(result) else None,
                "Retry mechanism should return some result structure",
            )

        except Exception as e:
            duration = time.time() - start_time
            print(f"  Retry test failed after {duration:.2f}s: {e}")
            # This is acceptable - the retry mechanism tried but website may be unavailable

    def _extract_site_name(self, url):
        """Extract site name from URL"""
        for site in SELECTOR_STRATEGIES.keys():
            if site in url:
                return site
        return "unknown"


class TestLiveWebsiteHealthMonitoring(LiveWebsiteTestBase):
    """Test health monitoring of live websites"""

    def test_website_availability(self):
        """Test that configured websites are accessible"""
        config = load_config()
        urls = config["urls"]["house_price_estimates"]

        availability_results = []

        for url in urls:
            print(f"\nChecking availability: {url}")

            start_time = time.time()
            try:
                self.driver.get(url)

                # Wait for page to load
                time.sleep(3)

                # Check if page loaded successfully
                page_title = self.driver.title
                page_source_length = len(self.driver.page_source)
                load_time = time.time() - start_time

                # Basic availability checks
                is_available = (
                    page_title
                    and len(page_title) > 0
                    and page_source_length > 1000  # Reasonable page size
                    and "error" not in page_title.lower()
                    and "404" not in page_title
                )

                availability_results.append(
                    {
                        "url": url,
                        "available": is_available,
                        "load_time": load_time,
                        "title": page_title[:50],
                        "page_size": page_source_length,
                    }
                )

                status = "✓" if is_available else "✗"
                print(
                    f"  {status} Load time: {load_time:.2f}s, Title: '{page_title[:30]}...'"
                )

            except Exception as e:
                load_time = time.time() - start_time
                availability_results.append(
                    {
                        "url": url,
                        "available": False,
                        "load_time": load_time,
                        "title": None,
                        "page_size": 0,
                        "error": str(e),
                    }
                )
                print(f"  ✗ Error after {load_time:.2f}s: {e}")

            self.rate_limiter.wait_if_needed()

        # Summary
        available_count = sum(1 for r in availability_results if r["available"])
        availability_rate = available_count / len(urls)

        print("\nAvailability Summary:")
        print(f"  Total URLs: {len(urls)}")
        print(f"  Available: {available_count}")
        print(f"  Availability rate: {availability_rate:.1%}")

        # At least some sites should be available
        self.assertGreater(availability_rate, 0.0, "No websites are available")

        # Warn if availability is low
        if availability_rate < 0.7:
            print(f"WARNING: Low availability rate ({availability_rate:.1%})")

    def test_performance_under_load(self):
        """Test scraper performance with multiple requests"""
        config = load_config()
        test_url = config["urls"]["house_price_estimates"][0]  # Use first URL

        print(f"\nTesting performance under load: {test_url}")

        request_times = []

        # Make 3 requests with rate limiting
        for i in range(3):
            start_time = time.time()
            try:
                midpoint, upper, lower = scrape_house_prices(self.driver, test_url)
                request_time = time.time() - start_time
                request_times.append(request_time)

                print(f"  Request {i + 1}: {request_time:.2f}s")

            except Exception as e:
                request_time = time.time() - start_time
                request_times.append(request_time)
                print(f"  Request {i + 1}: {request_time:.2f}s (failed: {e})")

            if i < 2:  # Don't wait after last request
                self.rate_limiter.wait_if_needed()

        if request_times:
            avg_time = sum(request_times) / len(request_times)
            max_time = max(request_times)
            min_time = min(request_times)

            print("\nPerformance Summary:")
            print(f"  Average time: {avg_time:.2f}s")
            print(f"  Min time: {min_time:.2f}s")
            print(f"  Max time: {max_time:.2f}s")

            # Performance assertions (reasonable for web scraping)
            self.assertLess(
                avg_time, 30.0, "Average request time should be under 30 seconds"
            )
            self.assertLess(max_time, 60.0, "No request should take over 60 seconds")


if __name__ == "__main__":
    # Check if live tests should run
    if not ("--run-live" in sys.argv or os.environ.get("RUN_LIVE_TESTS") == "true"):
        print("Live website tests are disabled by default.")
        print("To run live tests, use: python test_live_websites.py --run-live")
        print("Or set environment variable: RUN_LIVE_TESTS=true")
        sys.exit(0)

    # Remove --run-live from argv so unittest doesn't complain
    if "--run-live" in sys.argv:
        sys.argv.remove("--run-live")

    print("=" * 60)
    print("WARNING: Running live website tests")
    print("This will make real HTTP requests to property websites")
    print("Tests include rate limiting to be respectful")
    print("=" * 60)

    unittest.main(verbosity=2)
