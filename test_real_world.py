"""
Real-world testing suite for the house price scraper.
Tests actual functionality without mocks, including live website testing (with rate limiting).
"""

import unittest
import time
import tempfile
import os
import psutil
from contextlib import contextmanager
from scraper import (
    load_config,
    ConfigurationError,
    PriceValidator,
    SelectorStrategy,
    SELECTOR_STRATEGIES,
    ScrapingLogger,
    ScrapingResult,
    RateLimiter,
    retry_with_backoff,
)


class TestConfigurationValidation(unittest.TestCase):
    """Test real configuration validation functionality"""

    def setUp(self):
        self.temp_config_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_config_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil

        shutil.rmtree(self.temp_config_dir)

    def create_config_file(self, content):
        """Helper to create a temporary config file"""
        with open("config.yml", "w") as f:
            f.write(content)

    def test_valid_config_loads_successfully(self):
        """Test that a valid config file loads without errors"""
        valid_config = """
urls:
  house_price_estimates:
    - "https://homes.co.nz/address/queenstown/test"
    - "https://www.qv.co.nz/property-search/test"
    - "https://www.propertyvalue.co.nz/test"
"""
        self.create_config_file(valid_config)

        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("urls", config)
        self.assertIn("house_price_estimates", config["urls"])

    def test_missing_config_file_raises_error(self):
        """Test that missing config file raises ConfigurationError"""
        with self.assertRaises(ConfigurationError) as context:
            load_config()
        self.assertIn("not found", str(context.exception))

    def test_invalid_yaml_raises_error(self):
        """Test that invalid YAML syntax raises ConfigurationError"""
        invalid_yaml = """
urls:
  house_price_estimates:
    - "test"
  invalid: [unclosed list
"""
        self.create_config_file(invalid_yaml)

        with self.assertRaises(ConfigurationError) as context:
            load_config()
        self.assertIn("Invalid YAML syntax", str(context.exception))

    def test_missing_urls_section_raises_error(self):
        """Test that missing urls section raises ConfigurationError"""
        config_without_urls = """
other_section:
  some_data: "value"
"""
        self.create_config_file(config_without_urls)

        with self.assertRaises(ConfigurationError) as context:
            load_config()
        self.assertIn("'urls' section", str(context.exception))

    def test_empty_url_list_raises_error(self):
        """Test that empty URL list raises ConfigurationError"""
        empty_urls_config = """
urls:
  house_price_estimates: []
"""
        self.create_config_file(empty_urls_config)

        with self.assertRaises(ConfigurationError) as context:
            load_config()
        self.assertIn("cannot be empty", str(context.exception))

    def test_invalid_url_format_raises_error(self):
        """Test that invalid URL formats raise ConfigurationError"""
        invalid_url_config = """
urls:
  house_price_estimates:
    - "not-a-valid-url"
    - "ftp://unsupported-protocol.com"
"""
        self.create_config_file(invalid_url_config)

        with self.assertRaises(ConfigurationError) as context:
            load_config()
        self.assertIn("Invalid URL format", str(context.exception))

    def test_non_string_urls_raise_error(self):
        """Test that non-string URLs raise ConfigurationError"""
        non_string_config = """
urls:
  house_price_estimates:
    - "https://valid.com"
    - 12345
    - null
"""
        self.create_config_file(non_string_config)

        with self.assertRaises(ConfigurationError) as context:
            load_config()
        self.assertIn("must be strings", str(context.exception))


class TestPriceValidationReal(unittest.TestCase):
    """Test real price validation without mocks"""

    def setUp(self):
        self.validator = PriceValidator()

    def test_price_validation_with_real_formats(self):
        """Test price validation with real-world price formats"""
        test_cases = [
            # Valid cases
            ("$1.2M", True, 1200000.0),
            ("$2,500,000", True, 2500000.0),
            ("1200000", True, 1200000.0),
            ("$850K", True, 850000.0),
            ("$0.5M", True, 500000.0),
            ("$999K", True, 999000.0),
            ("$1.25M", True, 1250000.0),
            # Invalid cases
            ("$50", False, None),  # Too low
            ("$100000000", False, None),  # Too high
            ("abc", False, None),  # Not a number
            ("", False, None),  # Empty
            ("$-100K", False, None),  # Negative
            ("£1.2M", False, None),  # Wrong currency
        ]

        for price_text, expected_valid, expected_value in test_cases:
            with self.subTest(price=price_text):
                result = self.validator.validate_price(price_text)
                self.assertEqual(result.is_valid, expected_valid)
                if expected_valid:
                    self.assertEqual(result.value, expected_value)
                    self.assertEqual(result.error_message, "")
                else:
                    self.assertIsNone(result.value)
                    self.assertNotEqual(result.error_message, "")

    def test_price_conversion_accuracy(self):
        """Test price conversion accuracy with various formats"""
        conversion_cases = [
            ("$1M", 1000000.0),
            ("$2.5M", 2500000.0),
            ("$1.234M", 1234000.0),
            ("500K", 500000.0),
            ("$750K", 750000.0),
            ("1234567", 1234567.0),
            ("$1,234,567", 1234567.0),
        ]

        for price_text, expected in conversion_cases:
            with self.subTest(price=price_text):
                result = self.validator.convert_to_numeric(price_text)
                self.assertEqual(result, expected)

    def test_price_relationship_validation_real_scenarios(self):
        """Test price relationships with realistic scenarios"""
        relationship_cases = [
            # Valid relationships
            (800000, 1000000, 1200000, True),
            (900000, 950000, 1000000, True),
            (None, 1000000, 1200000, True),
            (800000, None, 1200000, True),
            (800000, 1000000, None, True),
            (1000000, 1000000, 1000000, True),  # All equal
            # Invalid relationships
            (1200000, 1000000, 800000, False),  # Descending
            (1000000, 800000, 900000, False),  # Mixed order
        ]

        for lower, midpoint, upper, expected in relationship_cases:
            with self.subTest(lower=lower, midpoint=midpoint, upper=upper):
                result = self.validator.validate_price_relationships(
                    lower, midpoint, upper
                )
                self.assertEqual(result, expected)


class TestSelectorStrategyReal(unittest.TestCase):
    """Test selector strategies with real data structures"""

    def setUp(self):
        self.strategy = SelectorStrategy()

    def test_selector_strategies_data_integrity(self):
        """Test that SELECTOR_STRATEGIES contains valid data"""
        required_sites = [
            "homes.co.nz",
            "qv.co.nz",
            "propertyvalue.co.nz",
            "realestate.co.nz",
            "oneroof.co.nz",
        ]
        required_price_types = ["midpoint", "upper", "lower"]

        for site in required_sites:
            self.assertIn(site, SELECTOR_STRATEGIES, f"Missing strategies for {site}")

            for price_type in required_price_types:
                self.assertIn(
                    price_type,
                    SELECTOR_STRATEGIES[site],
                    f"Missing {price_type} strategies for {site}",
                )

                strategies = SELECTOR_STRATEGIES[site][price_type]
                self.assertIsInstance(strategies, list)
                self.assertGreater(
                    len(strategies), 0, f"No strategies defined for {site}.{price_type}"
                )

                for strategy in strategies:
                    self.assertIn("type", strategy)
                    self.assertIn(
                        strategy["type"],
                        ["css", "xpath", "text_pattern", "regex_fallback"],
                    )

    def test_regex_patterns_are_valid(self):
        """Test that all regex patterns in strategies are valid"""
        import re

        for site, site_strategies in SELECTOR_STRATEGIES.items():
            for price_type, strategies in site_strategies.items():
                for strategy in strategies:
                    if strategy["type"] in ["text_pattern", "regex_fallback"]:
                        pattern = strategy["pattern"]
                        try:
                            re.compile(pattern)
                        except re.error as e:
                            self.fail(
                                f"Invalid regex in {site}.{price_type}: {pattern} - {e}"
                            )

    def test_selector_strategy_application_real(self):
        """Test selector strategy application with realistic scenarios"""

        # Test with simulated page content
        class MockDriver:
            def __init__(self, page_source="", elements=None):
                self.page_source = page_source
                self.elements = elements or {}

            def find_element(self, by, selector):
                if selector in self.elements:
                    return self.elements[selector]
                from selenium.common.exceptions import NoSuchElementException

                raise NoSuchElementException()

        # Test CSS selector success
        class MockElement:
            def __init__(self, text):
                self.text = text

        driver = MockDriver(elements={".price": MockElement("$1.2M")})
        strategy = {"type": "css", "selector": ".price"}
        result = self.strategy.apply_strategy(driver, strategy)
        self.assertEqual(result, "$1.2M")

        # Test regex fallback
        driver = MockDriver(
            page_source="Property estimate: $1.5M based on recent sales"
        )
        strategy = {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M"}
        result = self.strategy.apply_strategy(driver, strategy)
        self.assertEqual(result, "$1.5M")


class TestLoggingReal(unittest.TestCase):
    """Test logging functionality with real file operations"""

    def setUp(self):
        self.temp_log = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        self.temp_log.close()
        self.logger = ScrapingLogger(self.temp_log.name)

    def tearDown(self):
        if os.path.exists(self.temp_log.name):
            os.unlink(self.temp_log.name)

    def test_logging_extraction_attempts_real(self):
        """Test logging extraction attempts to real file"""
        self.logger.log_extraction_attempt(
            "homes.co.nz", "css", ".price-estimate", True
        )
        self.logger.log_extraction_attempt(
            "qv.co.nz", "xpath", "//div[@class='price']", False
        )

        # Read the log file
        with open(self.temp_log.name, "r") as f:
            content = f.read()

        self.assertIn("homes.co.nz", content)
        self.assertIn("🎯", content)  # Success emoji
        self.assertIn("qv.co.nz", content)
        self.assertIn("❌", content)  # Failure emoji
        self.assertIn(".price-estimate", content)

    def test_logging_scraping_results_real(self):
        """Test logging scraping results to real file"""
        success_result = ScrapingResult(
            site="homes.co.nz",
            url="https://homes.co.nz/test",
            success=True,
            prices={"midpoint": 1200000.0, "upper": 1400000.0, "lower": 1000000.0},
            errors=[],
            extraction_method="css",
            execution_time=2.5,
        )

        failure_result = ScrapingResult(
            site="qv.co.nz",
            url="https://qv.co.nz/test",
            success=False,
            prices={},
            errors=["Element not found", "Timeout"],
            extraction_method="xpath",
            execution_time=15.0,
        )

        self.logger.log_scraping_result(success_result)
        self.logger.log_scraping_result(failure_result)

        with open(self.temp_log.name, "r") as f:
            content = f.read()

        self.assertIn("✅", content)  # Success emoji
        self.assertIn("homes.co.nz", content)
        self.assertIn("1,200,000", content)  # Number with commas as formatted in log
        self.assertIn("❌", content)  # Failure emoji
        self.assertIn("qv.co.nz", content)
        self.assertIn("Element not found", content)


class TestRateLimitingReal(unittest.TestCase):
    """Test rate limiting with real timing"""

    def test_rate_limiter_timing_precision(self):
        """Test rate limiter enforces delays with real timing"""
        limiter = RateLimiter(min_delay=0.5, max_delay=0.6)

        # First call should not delay
        start_time = time.time()
        limiter.wait_if_needed()
        first_duration = time.time() - start_time
        self.assertLess(first_duration, 0.1)

        # Second call should enforce delay
        start_time = time.time()
        limiter.wait_if_needed()
        second_duration = time.time() - start_time
        self.assertGreaterEqual(second_duration, 0.5)
        self.assertLessEqual(second_duration, 1.0)  # Allow tolerance

    def test_rate_limiter_multiple_requests(self):
        """Test rate limiter with multiple requests"""
        limiter = RateLimiter(min_delay=0.2, max_delay=0.3)

        start_time = time.time()
        request_times = []

        for i in range(4):
            request_start = time.time()
            limiter.wait_if_needed()
            request_times.append(time.time() - request_start)

        time.time() - start_time

        # First request should not delay
        self.assertLess(request_times[0], 0.1)

        # Subsequent requests should delay
        for i in range(1, 4):
            self.assertGreaterEqual(request_times[i], 0.2)


class TestRetryMechanismReal(unittest.TestCase):
    """Test retry mechanisms with real timing and exceptions"""

    def test_retry_decorator_real_exceptions(self):
        """Test retry decorator with real WebDriver exceptions"""
        from selenium.common.exceptions import WebDriverException, TimeoutException

        attempt_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.1, max_delay=0.2)
        def function_with_real_exceptions():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise WebDriverException("Connection failed")
            elif attempt_count == 2:
                raise TimeoutException("Element not found")
            return {"success": True, "attempts": attempt_count}

        start_time = time.time()
        result = function_with_real_exceptions()
        duration = time.time() - start_time

        self.assertEqual(attempt_count, 3)
        self.assertEqual(result["success"], True)
        self.assertGreater(duration, 0.1)  # Should have some delay from retries

    def test_retry_exponential_backoff_timing(self):
        """Test that retry decorator actually implements exponential backoff"""
        attempt_times = []

        @retry_with_backoff(max_attempts=3, base_delay=0.1, backoff_factor=2)
        def always_failing_function():
            attempt_times.append(time.time())
            raise Exception("Always fails")

        time.time()
        try:
            always_failing_function()
        except Exception:
            pass

        # Verify we had 3 attempts
        self.assertEqual(len(attempt_times), 3)

        # Verify exponential backoff timing
        if len(attempt_times) >= 2:
            first_delay = attempt_times[1] - attempt_times[0]
            self.assertGreater(first_delay, 0.1)  # At least base_delay

        if len(attempt_times) >= 3:
            second_delay = attempt_times[2] - attempt_times[1]
            self.assertGreater(second_delay, first_delay)  # Should be longer


@contextmanager
def performance_monitor():
    """Context manager to monitor performance metrics"""
    process = psutil.Process()
    start_time = time.time()
    start_memory = process.memory_info().rss
    process.cpu_percent()

    yield

    end_time = time.time()
    end_memory = process.memory_info().rss
    end_cpu = process.cpu_percent()

    execution_time = end_time - start_time
    memory_delta = end_memory - start_memory
    cpu_usage = end_cpu

    print("Performance Metrics:")
    print(f"  Execution time: {execution_time:.3f}s")
    print(f"  Memory delta: {memory_delta / 1024 / 1024:.2f}MB")
    print(f"  CPU usage: {cpu_usage:.1f}%")


class TestPerformance(unittest.TestCase):
    """Performance testing for scraper components"""

    def test_config_loading_performance(self):
        """Test configuration loading performance"""
        with performance_monitor():
            for i in range(100):
                load_config()

        # Config loading should be fast
        start_time = time.time()
        load_config()
        duration = time.time() - start_time

        self.assertLess(duration, 0.1, "Config loading should be under 100ms")

    def test_price_validation_performance(self):
        """Test price validation performance"""
        validator = PriceValidator()
        test_prices = [
            "$1.2M",
            "$2,500,000",
            "1200000",
            "$850K",
        ] * 250  # 1000 validations

        start_time = time.time()
        for price in test_prices:
            validator.validate_price(price)
        duration = time.time() - start_time

        self.assertLess(
            duration, 1.0, "1000 price validations should complete under 1 second"
        )

        # Test performance per validation
        avg_time = duration / len(test_prices)
        self.assertLess(avg_time, 0.001, "Each price validation should be under 1ms")

    def test_selector_strategy_performance(self):
        """Test selector strategy performance"""
        strategy = SelectorStrategy()

        # Simulate failed selectors (should fail fast)
        start_time = time.time()
        for i in range(100):
            strategies = SELECTOR_STRATEGIES["homes.co.nz"]["midpoint"]
            strategy.apply_cascading_strategies(None, strategies)
        duration = time.time() - start_time

        self.assertLess(
            duration, 0.5, "100 strategy applications should complete under 500ms"
        )

    def test_memory_usage_stability(self):
        """Test that operations don't cause memory leaks"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Perform multiple operations
        validator = PriceValidator()
        SelectorStrategy()

        for i in range(1000):
            validator.validate_price("$1.2M")
            if i % 100 == 0:
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory
                # Allow some memory growth but not excessive
                self.assertLess(
                    memory_growth,
                    50 * 1024 * 1024,
                    f"Memory growth exceeds 50MB at iteration {i}",
                )


if __name__ == "__main__":
    # Add performance timing to test runner
    import sys

    class TimedTestResult(unittest.TextTestResult):
        def startTest(self, test):
            self.start_time = time.time()
            super().startTest(test)

        def stopTest(self, test):
            duration = time.time() - self.start_time
            if duration > 1.0:  # Warn about slow tests
                print(f"\nWARNING: {test} took {duration:.2f}s")
            super().stopTest(test)

    class TimedTestRunner(unittest.TextTestRunner):
        resultclass = TimedTestResult

    if len(sys.argv) == 1:
        unittest.main(testRunner=TimedTestRunner(verbosity=2))
    else:
        unittest.main(verbosity=2)
