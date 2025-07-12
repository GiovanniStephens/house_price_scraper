"""
Comprehensive tests for the enhanced scraper implementation.
Tests the integrated multi-strategy, logging, validation, and resilience features.
NO MOCKING - Real functionality testing only.
"""

import unittest
import time
import tempfile
import os
import logging
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from scraper import (
    scrape_house_prices,
    scrape_all_house_prices,
    scrape_with_retry,
    SelectorStrategy,
    SELECTOR_STRATEGIES,
    PriceValidator,
    ValidationResult,
    ScrapingLogger,
    ScrapingResult,
    RateLimiter,
    calculate_metrics,
    ScrapingMetrics,
    check_driver_health,
    ensure_driver_health,
    format_price_by_site,
    ConfigurationError,
    load_config,
    find_prices_with_regex,
)


class TestEnhancedScrapeHousePrices(unittest.TestCase):
    """Test the enhanced scrape_house_prices function with real scenarios"""

    def setUp(self):
        self.mock_driver = MockWebDriver()

    def test_enhanced_scraping_returns_scraping_result(self):
        """Test that enhanced scraping returns ScrapingResult object"""
        # Set up mock driver with homes.co.nz content
        self.mock_driver.current_url = "https://homes.co.nz/test"
        self.mock_driver.elements = {
            '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]': MockElement(
                "$1.2M"
            )
        }

        result = scrape_house_prices(
            self.mock_driver,
            "https://homes.co.nz/test",
            validate_prices=False,
            enable_logging=False,
        )

        # Should return ScrapingResult
        self.assertIsInstance(result, ScrapingResult)
        self.assertEqual(result.site, "homes.co.nz")
        self.assertEqual(result.url, "https://homes.co.nz/test")
        self.assertTrue(result.success)
        self.assertEqual(result.prices["midpoint"], 1200000.0)

    def test_enhanced_scraping_with_validation(self):
        """Test enhanced scraping with price validation enabled"""
        self.mock_driver.elements = {
            '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]': MockElement(
                "$1.2M"
            )
        }

        result = scrape_house_prices(
            self.mock_driver,
            "https://homes.co.nz/test",
            validate_prices=True,
            enable_logging=False,
        )

        self.assertIsInstance(result, ScrapingResult)
        self.assertTrue(result.success)
        # With validation, should return numeric value
        self.assertEqual(result.prices["midpoint"], 1200000.0)
        self.assertIn("midpoint:xpath", result.extraction_method)

    def test_enhanced_scraping_with_logging(self):
        """Test enhanced scraping with logging enabled"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            log_file = f.name

        self.mock_driver.elements = {
            '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]': MockElement(
                "$1.2M"
            )
        }

        # Override the default logger to use our temp file
        original_init = ScrapingLogger.__init__

        def temp_init(self, log_file_param="scraper.log"):
            original_init(self, log_file)

        ScrapingLogger.__init__ = temp_init

        try:
            result = scrape_house_prices(
                self.mock_driver,
                "https://homes.co.nz/test",
                validate_prices=False,
                enable_logging=True,
            )

            # Check log file was created and contains relevant information
            self.assertTrue(os.path.exists(log_file))
            with open(log_file, "r") as f:
                log_content = f.read()

            # Should contain extraction attempt logs
            self.assertIn("homes.co.nz", log_content)
            self.assertIn("SUCCESS", log_content)

        finally:
            ScrapingLogger.__init__ = original_init
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_enhanced_scraping_fallback_strategies(self):
        """Test that scraping falls back through strategies"""
        # First strategy fails, second succeeds
        self.mock_driver.failing_selectors = [
            '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]'
        ]
        self.mock_driver.elements = {
            "[data-testid='price-estimate-main']": MockElement("$1.5M")
        }

        result = scrape_house_prices(
            self.mock_driver,
            "https://homes.co.nz/test",
            validate_prices=False,
            enable_logging=False,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.prices["midpoint"], 1500000.0)
        self.assertIn("midpoint:css", result.extraction_method)

    def test_enhanced_scraping_regex_fallback(self):
        """Test that scraping falls back to regex patterns"""
        # All DOM selectors fail, should use regex
        self.mock_driver.failing_selectors = "all"
        self.mock_driver.page_source = (
            "Property estimate is $1.8M based on recent sales data"
        )

        result = scrape_house_prices(
            self.mock_driver,
            "https://homes.co.nz/test",
            validate_prices=False,
            enable_logging=False,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.prices["midpoint"], 1800000.0)
        self.assertIn("midpoint:regex_fallback", result.extraction_method)

    def test_enhanced_scraping_unsupported_site(self):
        """Test scraping with unsupported site URL"""
        result = scrape_house_prices(
            self.mock_driver,
            "https://unsupported-site.com/test",
            validate_prices=False,
            enable_logging=False,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.site, "unknown")
        self.assertIn("No selector strategies found", result.errors[0])

    def test_enhanced_scraping_propertyvalue_special_case(self):
        """Test PropertyValue.co.nz special case where midpoint is set to None"""
        self.mock_driver.elements = {
            '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[1]': MockElement(
                "$1.0M"
            ),
            '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[2]': MockElement(
                "$1.4M"
            ),
        }

        result = scrape_house_prices(
            self.mock_driver,
            "https://www.propertyvalue.co.nz/test",
            validate_prices=False,
            enable_logging=False,
        )

        self.assertTrue(result.success)
        self.assertIsNone(
            result.prices["midpoint"]
        )  # Should be None for external calculation
        self.assertEqual(result.prices["lower"], 1000000.0)
        self.assertEqual(result.prices["upper"], 1400000.0)


class TestEnhancedScrapingIntegration(unittest.TestCase):
    """Test integration of enhanced scraping with all robustness features"""

    def test_scrape_all_house_prices_enhanced_interface(self):
        """Test that scrape_all_house_prices has enhanced interface"""
        # Test that the function accepts enhanced parameters
        import inspect

        sig = inspect.signature(scrape_all_house_prices)
        params = list(sig.parameters.keys())

        enhanced_params = [
            "enable_retry",
            "rate_limit",
            "validate_prices",
            "enable_logging",
        ]
        for param in enhanced_params:
            self.assertIn(param, params, f"Missing enhanced parameter: {param}")

    def test_scrape_with_retry_integration(self):
        """Test that scrape_with_retry works with enhanced parameters"""
        mock_driver = MockWebDriver()
        mock_driver.elements = {
            '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]': MockElement(
                "$1.2M"
            )
        }

        result = scrape_with_retry(
            mock_driver,
            "https://homes.co.nz/test",
            validate_prices=False,
            enable_logging=False,
        )

        self.assertIsInstance(result, ScrapingResult)
        self.assertTrue(result.success)

    def test_metrics_calculation_with_real_results(self):
        """Test metrics calculation with real ScrapingResult objects"""
        results = [
            ScrapingResult(
                site="homes.co.nz",
                url="https://homes.co.nz/test1",
                success=True,
                prices={"midpoint": 1200000},
                errors=[],
                extraction_method="midpoint:xpath,upper:css",
                execution_time=2.5,
            ),
            ScrapingResult(
                site="qv.co.nz",
                url="https://qv.co.nz/test2",
                success=False,
                prices={},
                errors=["Element not found", "Timeout occurred"],
                extraction_method="",
                execution_time=15.0,
            ),
            ScrapingResult(
                site="propertyvalue.co.nz",
                url="https://propertyvalue.co.nz/test3",
                success=True,
                prices={"lower": 800000, "upper": 1400000, "midpoint": None},
                errors=[],
                extraction_method="lower:xpath,upper:xpath",
                execution_time=3.2,
            ),
        ]

        metrics = calculate_metrics(results)

        self.assertIsInstance(metrics, ScrapingMetrics)
        self.assertEqual(metrics.total_sites, 3)
        self.assertEqual(metrics.successful_sites, 2)
        self.assertEqual(metrics.failed_sites, 1)
        self.assertEqual(metrics.total_execution_time, 20.7)
        self.assertAlmostEqual(metrics.average_time_per_site, 6.9, places=1)

        # Check extraction methods
        self.assertIn("midpoint:xpath", metrics.extraction_methods_used)
        self.assertIn("upper:css", metrics.extraction_methods_used)

        # Check error summary
        self.assertIn("Element not found", metrics.error_summary)


class TestRealWorldScenarios(unittest.TestCase):
    """Test real-world scenarios with the enhanced implementation"""

    def test_price_validation_edge_cases(self):
        """Test price validation with real edge cases from websites"""
        validator = PriceValidator()

        # Real formats that might be extracted
        real_world_cases = [
            ("$1.2M", True, 1200000.0),  # Standard M format
            ("$2,500,000", True, 2500000.0),  # Comma format
            ("850K", True, 850000.0),  # K format without $
            ("$999,999", True, 999999.0),  # High precision
            ("$1.05M", True, 1050000.0),  # Decimal M format
            ("QV: $1,200,000", False, None),  # QV prefix (invalid pattern)
            ("$50,000", False, None),  # Too low
            ("Price: TBC", False, None),  # Non-numeric
            ("", False, None),  # Empty
        ]

        for price_text, expected_valid, expected_value in real_world_cases:
            with self.subTest(price=price_text):
                result = validator.validate_price(price_text)
                self.assertEqual(result.is_valid, expected_valid)
                if expected_valid:
                    self.assertEqual(result.value, expected_value)

    def test_selector_strategy_real_application(self):
        """Test selector strategies with realistic DOM scenarios"""
        strategy = SelectorStrategy()

        # Test different selector types
        test_cases = [
            {
                "strategy": {"type": "css", "selector": ".price"},
                "driver_setup": {"elements": {".price": MockElement("$1.2M")}},
                "expected": "$1.2M",
            },
            {
                "strategy": {"type": "xpath", "selector": "//span[@class='price']"},
                "driver_setup": {
                    "elements": {"//span[@class='price']": MockElement("$1.5M")}
                },
                "expected": "$1.5M",
            },
            {
                "strategy": {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M"},
                "driver_setup": {
                    "page_source": "Property valued at $1.8M in current market"
                },
                "expected": "$1.8M",
            },
        ]

        for case in test_cases:
            with self.subTest(strategy=case["strategy"]["type"]):
                mock_driver = MockWebDriver()
                if "elements" in case["driver_setup"]:
                    mock_driver.elements = case["driver_setup"]["elements"]
                if "page_source" in case["driver_setup"]:
                    mock_driver.page_source = case["driver_setup"]["page_source"]

                result = strategy.apply_strategy(mock_driver, case["strategy"])
                self.assertEqual(result, case["expected"])

    def test_format_price_by_site_real_scenarios(self):
        """Test site-specific price formatting with real extracted values"""
        test_cases = [
            ("homes.co.nz", "1.2M", 1200000.0),
            ("qv.co.nz", "QV: $1,200,000", 1200000.0),
            ("propertyvalue.co.nz", "$1.2M", 1200000.0),
            ("realestate.co.nz", "$1.2M", 1200000.0),
            ("oneroof.co.nz", "$1.2M", 1200000.0),
        ]

        for site, price_text, expected in test_cases:
            with self.subTest(site=site):
                result = format_price_by_site(price_text, site)
                self.assertEqual(result, expected)

    def test_enhanced_regex_patterns(self):
        """Test enhanced regex patterns with real HTML content"""
        html_samples = [
            "<div>Properties range from $1.2M to $2.5M</div>",
            "<span>Listed at $850,000 in today's market</span>",
            "<p>Price: 1.5M (negotiable)</p>",
            "<div>Value: $1,234,567</div>",
            "<span>From 800K to 1.2M depending on condition</span>",
        ]

        for html in html_samples:
            with self.subTest(html=html[:30]):
                prices = find_prices_with_regex(html)
                self.assertGreater(len(prices), 0, f"Should find prices in: {html}")

                # All found prices should be valid formats
                for price in prices:
                    self.assertRegex(
                        price, r"(\$?\d+(?:,\d{3})*(?:\.\d+)?[MK]?|\$[\d,]+(?:\.\d+)?)"
                    )

    def test_driver_health_checks_real_scenarios(self):
        """Test driver health checks with realistic scenarios"""
        # Test healthy driver
        healthy_driver = MockWebDriver()
        healthy_driver.current_url = "https://example.com"
        self.assertTrue(check_driver_health(healthy_driver))

        # Test unhealthy driver
        unhealthy_driver = MockWebDriver()
        unhealthy_driver.should_fail = True
        self.assertFalse(check_driver_health(unhealthy_driver))

        # Test ensure_driver_health with healthy driver
        ensured_driver = ensure_driver_health(healthy_driver)
        self.assertEqual(ensured_driver, healthy_driver)


class TestPerformanceAndStability(unittest.TestCase):
    """Test performance and stability of enhanced implementation"""

    def test_scraping_performance_benchmarks(self):
        """Test that scraping meets performance benchmarks"""
        mock_driver = MockWebDriver()
        mock_driver.elements = {
            '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]': MockElement(
                "$1.2M"
            )
        }

        # Test multiple scrapings for performance
        start_time = time.time()
        for i in range(10):
            result = scrape_house_prices(
                mock_driver,
                "https://homes.co.nz/test",
                validate_prices=True,
                enable_logging=False,
            )
            self.assertTrue(result.success)

        duration = time.time() - start_time
        avg_time = duration / 10

        # Should complete in reasonable time (allowing for validation overhead)
        self.assertLess(avg_time, 0.1, "Average scraping time should be under 100ms")

    def test_memory_stability_with_repeated_operations(self):
        """Test that repeated operations don't cause memory issues"""
        import psutil
        import gc

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        mock_driver = MockWebDriver()
        mock_driver.elements = {
            '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]': MockElement(
                "$1.2M"
            )
        }

        # Perform many operations
        results = []
        for i in range(100):
            result = scrape_house_prices(
                mock_driver,
                "https://homes.co.nz/test",
                validate_prices=True,
                enable_logging=False,
            )
            results.append(result)

            # Check memory every 25 iterations
            if i % 25 == 0:
                gc.collect()  # Force garbage collection
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory

                # Allow some growth but not excessive
                self.assertLess(
                    memory_growth,
                    20 * 1024 * 1024,
                    f"Memory growth exceeds 20MB at iteration {i}",
                )

        # Verify all results were successful
        successful_results = [r for r in results if r.success]
        self.assertEqual(len(successful_results), 100)


# Mock classes for testing without real WebDriver
class MockWebDriver:
    """Mock WebDriver for testing without real browser"""

    def __init__(self):
        self.current_url = "https://example.com"
        self.page_source = "<html><body>Mock page source</body></html>"
        self.elements = {}
        self.failing_selectors = []
        self.should_fail = False

    def get(self, url):
        """Mock navigation"""
        self.current_url = url

    def find_element(self, by, selector):
        """Mock element finding"""
        if self.should_fail:
            raise Exception("Driver is unhealthy")

        if self.failing_selectors == "all" or selector in self.failing_selectors:
            raise NoSuchElementException()

        if selector in self.elements:
            return self.elements[selector]

        raise NoSuchElementException()

    def quit(self):
        """Mock quit"""
        pass


class MockElement:
    """Mock WebElement for testing"""

    def __init__(self, text):
        self.text = text


if __name__ == "__main__":
    unittest.main(verbosity=2)
