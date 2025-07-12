import unittest
import platform
from scraper import (
    init_driver,
    load_config,
    format_homes_prices,
    format_qv_prices,
    format_property_value_prices,
    find_prices_with_regex,
)


class TestCurrentScraperFunctionality(unittest.TestCase):
    """Test the current scraper functionality to ensure it works as expected"""

    def test_load_config_returns_dict(self):
        """Test that load_config returns a dictionary with urls"""
        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("urls", config)
        self.assertIn("house_price_estimates", config["urls"])
        self.assertIsInstance(config["urls"]["house_price_estimates"], list)

    def test_load_config_has_expected_sites(self):
        """Test that config contains expected property valuation sites"""
        config = load_config()
        urls = config["urls"]["house_price_estimates"]

        expected_sites = [
            "homes.co.nz",
            "qv.co.nz",
            "propertyvalue.co.nz",
            "realestate.co.nz",
            "oneroof.co.nz",
        ]

        for site in expected_sites:
            self.assertTrue(
                any(site in url for url in urls),
                f"Expected site {site} not found in config URLs",
            )

    def test_init_driver_x86_64_success(self):
        """Test that init_driver works on x86_64 architecture"""
        if platform.machine() == "x86_64":
            driver = init_driver()
            self.assertIsNotNone(driver, "Driver should be initialized on x86_64")
            if driver:
                driver.quit()
        else:
            self.skipTest("Test only runs on x86_64 architecture")

    def test_init_driver_non_x86_64_returns_none(self):
        """Test that init_driver returns None on non-x86_64 architecture"""
        if platform.machine() != "x86_64":
            driver = init_driver()
            self.assertIsNone(
                driver, "Driver should return None on non-x86_64 architecture"
            )
        else:
            self.skipTest("Test only runs on non-x86_64 architecture")

    def test_format_homes_prices_valid_input(self):
        """Test format_homes_prices with valid input"""
        test_cases = [
            ("1.2M", 1200000.0),
            ("2.5M", 2500000.0),
            ("0.8M", 800000.0),
            ("10M", 10000000.0),
        ]

        for input_price, expected_output in test_cases:
            result = format_homes_prices(input_price)
            self.assertEqual(result, expected_output, f"Failed for input {input_price}")

    def test_format_qv_prices_valid_input(self):
        """Test format_qv_prices with valid input"""
        test_cases = [
            ("$1,200,000", 1200000.0),
            ("QV: $850,000", 850000.0),
            ("$2,500,000", 2500000.0),
            ("1200000", 1200000.0),
        ]

        for input_price, expected_output in test_cases:
            result = format_qv_prices(input_price)
            self.assertEqual(result, expected_output, f"Failed for input {input_price}")

    def test_format_property_value_prices_valid_input(self):
        """Test format_property_value_prices with valid input"""
        test_cases = [("$1.2M", 1200000.0), ("$2.5M", 2500000.0), ("$0.8M", 800000.0)]

        for input_price, expected_output in test_cases:
            result = format_property_value_prices(input_price)
            self.assertEqual(result, expected_output, f"Failed for input {input_price}")

    def test_find_prices_with_regex_valid_html(self):
        """Test find_prices_with_regex finds prices in HTML content"""
        test_html = """
        <div>Property prices range from $1.2M to $2.5M</div>
        <span>Another property at $3.1M</span>
        <p>Budget option at $0.8M</p>
        """

        prices = find_prices_with_regex(test_html)
        expected_prices = ["$1.2M", "$2.5M", "$3.1M", "$0.8M"]

        self.assertEqual(len(prices), 4)
        for expected_price in expected_prices:
            self.assertIn(expected_price, prices)

    def test_find_prices_with_regex_no_matches(self):
        """Test find_prices_with_regex returns empty list when no prices found"""
        test_html = "<div>No prices here, just some text</div>"

        prices = find_prices_with_regex(test_html)
        self.assertEqual(len(prices), 0)

    def test_selector_strategy_handles_missing_elements(self):
        """Test SelectorStrategy handles missing elements gracefully"""
        from scraper import SelectorStrategy

        class MockDriver:
            def find_element(self, by, selector):
                from selenium.common.exceptions import NoSuchElementException

                raise NoSuchElementException()

        mock_driver = MockDriver()
        strategy = SelectorStrategy()
        test_strategy = {"type": "css", "selector": ".nonexistent-selector"}
        result = strategy.apply_strategy(mock_driver, test_strategy)
        self.assertIsNone(result, "Should return None when element not found")

    def test_scraper_import_all_functions(self):
        """Test that all expected functions can be imported from scraper module"""
        expected_functions = [
            "init_driver",
            "load_config",
            "scrape_house_prices",
            "scrape_all_house_prices",
            "format_homes_prices",
            "format_qv_prices",
            "format_property_value_prices",
            "format_realestate_prices",
            "format_oneroof_prices",
            "find_prices_with_regex",
        ]

        import scraper

        for func_name in expected_functions:
            self.assertTrue(
                hasattr(scraper, func_name),
                f"Function {func_name} not found in scraper module",
            )
            self.assertTrue(
                callable(getattr(scraper, func_name)), f"{func_name} is not callable"
            )


class TestCurrentScraperLimitations(unittest.TestCase):
    """Test the current limitations that need to be addressed"""

    def test_current_scraper_has_hardcoded_selectors(self):
        """Test that current scraper uses hardcoded selectors (limitation to fix)"""
        # This test is no longer valid - the scraper now uses SELECTOR_STRATEGIES
        # instead of hardcoded selectors directly in the function
        from scraper import SELECTOR_STRATEGIES

        # Verify that strategies exist (this is the new approach)
        self.assertIn("homes.co.nz", SELECTOR_STRATEGIES)
        self.assertIn("mat-tab-content", str(SELECTOR_STRATEGIES["homes.co.nz"]))
        self.assertTrue(len(SELECTOR_STRATEGIES) > 0)

    def test_current_scraper_uses_implicit_waits(self):
        """Test that current scraper uses implicit waits (limitation to fix)"""
        # This test is no longer valid - the scraper now uses explicit waits
        # Check that explicit wait functions exist instead
        from scraper import wait_for_element, wait_for_price_elements

        # Verify explicit wait functions exist
        self.assertTrue(callable(wait_for_element))
        self.assertTrue(callable(wait_for_price_elements))

    def test_current_scraper_limited_error_handling(self):
        """Test that current scraper has limited error handling"""
        # This test is no longer valid - the scraper now has comprehensive logging
        # Check that logging functionality exists instead
        from scraper import ScrapingLogger

        # Verify comprehensive logging exists
        logger = ScrapingLogger()
        self.assertTrue(hasattr(logger, "log_extraction_attempt"))
        self.assertTrue(hasattr(logger, "log_price_extraction"))
        self.assertTrue(hasattr(logger, "log_scraping_result"))

    def test_current_scraper_has_price_validation(self):
        """Test that current scraper now has price validation"""
        # PriceValidator should now exist
        try:
            from scraper import PriceValidator

            # Test that it can be instantiated
            validator = PriceValidator()
            self.assertTrue(hasattr(validator, "validate_price"))
        except ImportError:
            self.fail("PriceValidator should now be implemented")

    def test_current_scraper_has_retry_logic(self):
        """Test that current scraper now has retry logic"""
        # retry_with_backoff should now exist
        try:
            from scraper import retry_with_backoff

            # Test that it's callable (decorator)
            self.assertTrue(callable(retry_with_backoff))
        except ImportError:
            self.fail("retry_with_backoff should now be implemented")

    def test_current_scraper_architecture_limitation(self):
        """Test that current scraper only supports x86_64"""
        from scraper import init_driver

        # Current implementation should print unsupported message for non-x86_64
        if platform.machine() != "x86_64":
            driver = init_driver()
            self.assertIsNone(
                driver, "Current implementation should fail on non-x86_64"
            )


class TestConfigurationStructure(unittest.TestCase):
    """Test the configuration file structure"""

    def test_config_file_exists(self):
        """Test that config.yml file exists and is readable"""
        import os

        self.assertTrue(os.path.exists("config.yml"), "config.yml file should exist")

    def test_config_has_valid_urls(self):
        """Test that all URLs in config are valid format"""
        import re

        config = load_config()
        urls = config["urls"]["house_price_estimates"]

        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        for url in urls:
            self.assertIsNotNone(url_pattern.match(url), f"Invalid URL format: {url}")

    def test_config_contains_test_property(self):
        """Test that config contains the specific test property"""
        config = load_config()
        urls = config["urls"]["house_price_estimates"]

        # All URLs should be for the same property (21 Onslow Road)
        # Some URLs might use property IDs instead of addresses
        property_identifiers = [
            "21-onslow-road",
            "21%20onslow",
            "2819859",  # QV property ID for this property
        ]

        for url in urls:
            url_lower = url.lower()
            has_identifier = any(
                identifier in url_lower for identifier in property_identifiers
            )
            self.assertTrue(
                has_identifier,
                f"URL does not appear to be for test property: {url}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
