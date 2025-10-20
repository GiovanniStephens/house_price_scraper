import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
)
import platform
import re
import time
import random
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict
from functools import wraps


SELECTOR_STRATEGIES = {
    "homes.co.nz": {
        "midpoint": [
            {
                "type": "xpath",
                "selector": (
                    '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/'
                    "homes-price-tag-simple/div/span[2]"
                ),
            },
            {"type": "css", "selector": "[data-testid='price-estimate-main']"},
            {"type": "xpath", "selector": "//span[contains(@class, 'price-main')]"},
            {"type": "text_pattern", "pattern": r"Estimate.*?\$(\d+\.?\d*M?)"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M?"},
        ],
        "upper": [
            {
                "type": "xpath",
                "selector": (
                    '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[2]/'
                    "div/homes-price-tag-simple[2]/div/span[2]"
                ),
            },
            {"type": "css", "selector": "[data-testid='price-estimate-upper']"},
            {"type": "xpath", "selector": "//span[contains(@class, 'price-upper')]"},
            {"type": "text_pattern", "pattern": r"Upper.*?\$(\d+\.?\d*M?)"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M?"},
        ],
        "lower": [
            {
                "type": "xpath",
                "selector": (
                    '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/'
                    "div[2]/div/homes-price-tag-simple[1]/div/span[2]"
                ),
            },
            {"type": "css", "selector": "[data-testid='price-estimate-lower']"},
            {"type": "xpath", "selector": "//span[contains(@class, 'price-lower')]"},
            {"type": "text_pattern", "pattern": r"Lower.*?\$(\d+\.?\d*M?)"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M?"},
        ],
    },
    "qv.co.nz": {
        "midpoint": [
            {
                "type": "xpath",
                "selector": '//*[@id="content"]/div/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div',
            },
            {"type": "css", "selector": "[data-testid='qv-price']"},
            {"type": "xpath", "selector": "//div[contains(@class, 'qv-valuation')]"},
            {"type": "text_pattern", "pattern": r"QV.*?\$(\d+,?\d*)"},
            {"type": "regex_fallback", "pattern": r"\$[\d,]+"},
        ],
        "upper": [
            {"type": "css", "selector": "[data-testid='qv-price-upper']"},
            {"type": "xpath", "selector": "//div[contains(@class, 'qv-upper')]"},
            {"type": "regex_fallback", "pattern": r"\$[\d,]+"},
        ],
        "lower": [
            {"type": "css", "selector": "[data-testid='qv-price-lower']"},
            {"type": "xpath", "selector": "//div[contains(@class, 'qv-lower')]"},
            {"type": "regex_fallback", "pattern": r"\$[\d,]+"},
        ],
    },
    "propertyvalue.co.nz": {
        "midpoint": [
            {"type": "css", "selector": "[data-testid='pv-midpoint']"},
            {"type": "css", "selector": "[testid='pv-midpoint']"},
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'property-value-mid')]",
            },
            {"type": "regex_fallback", "pattern": r"\$\s*\d+\.?\d*\s*[Mm]"},
        ],
        "upper": [
            {"type": "css", "selector": "[data-testid='highEstimate']"},
            {"type": "css", "selector": "[testid='highEstimate']"},
            {
                "type": "xpath",
                "selector": '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[2]',
            },
            {"type": "css", "selector": "[data-testid='pv-upper']"},
            {"type": "css", "selector": "[testid='pv-upper']"},
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'property-value-upper')]",
            },
            {"type": "regex_fallback", "pattern": r"\$\s*\d+\.?\d*\s*[Mm]"},
        ],
        "lower": [
            {"type": "css", "selector": "[data-testid='lowEstimate']"},
            {"type": "css", "selector": "[testid='lowEstimate']"},
            {
                "type": "xpath",
                "selector": '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[1]',
            },
            {"type": "css", "selector": "[data-testid='pv-lower']"},
            {"type": "css", "selector": "[testid='pv-lower']"},
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'property-value-lower')]",
            },
            {"type": "regex_fallback", "pattern": r"\$\s*\d+\.?\d*\s*[Mm]"},
        ],
    },
    "realestate.co.nz": {
        "midpoint": [
            {
                "type": "css",
                "selector": "[data-test='reinz-valuation__price-range'] div:nth-child(2) h4",
            },
            {
                "type": "xpath",
                "selector": "//div[@data-test='reinz-valuation__price-range']/div[2]//h4",
            },
            {"type": "css", "selector": "[data-testid='reinz-price-mid']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.\d+M"},
        ],
        "upper": [
            {
                "type": "css",
                "selector": "[data-test='reinz-valuation__price-range'] div:nth-child(3) h4",
            },
            {
                "type": "xpath",
                "selector": "//div[@data-test='reinz-valuation__price-range']/div[3]//h4",
            },
            {"type": "css", "selector": "[data-testid='reinz-price-upper']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.\d+M"},
        ],
        "lower": [
            {
                "type": "css",
                "selector": "[data-test='reinz-valuation__price-range'] div:nth-child(1) h4",
            },
            {
                "type": "xpath",
                "selector": "//div[@data-test='reinz-valuation__price-range']/div[1]//h4",
            },
            {"type": "css", "selector": "[data-testid='reinz-price-lower']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.\d+M"},
        ],
    },
    "oneroof.co.nz": {
        "midpoint": [
            {
                "type": "css",
                "selector": "div.text-3xl.font-bold.text-secondary.-mt-60.pb-22",
            },
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'text-3xl') and contains(@class, 'font-bold')]",
            },
            {"type": "css", "selector": "[data-testid='oneroof-midpoint']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M?"},
        ],
        "upper": [
            {
                "type": "css",
                "selector": "div.text-center.font-medium.absolute.top-0.pt-10.right-0 > div.text-base.md\\:text-xl",
            },
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'right-0')]//div[contains(@class, 'text-base')]",
            },
            {"type": "css", "selector": "[data-testid='oneroof-upper']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M?"},
        ],
        "lower": [
            {
                "type": "css",
                "selector": "div.text-center.font-medium.absolute.top-0.pt-10.left-0 > div.text-base.md\\:text-xl",
            },
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'left-0')]//div[contains(@class, 'text-base')]",
            },
            {"type": "css", "selector": "[data-testid='oneroof-lower']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*M?"},
        ],
    },
}


class SelectorStrategy:
    """Multi-strategy selector system for robust element finding"""

    def apply_strategy(self, driver, strategy):
        """Apply a single selector strategy"""
        try:
            if strategy["type"] == "css":
                element = driver.find_element(By.CSS_SELECTOR, strategy["selector"])
                return element.text
            elif strategy["type"] == "xpath":
                element = driver.find_element(By.XPATH, strategy["selector"])
                return element.text
            elif strategy["type"] == "text_pattern":
                page_source = driver.page_source
                matches = re.findall(strategy["pattern"], page_source)
                return matches[0] if matches else None
            elif strategy["type"] == "regex_fallback":
                page_source = driver.page_source
                matches = re.findall(strategy["pattern"], page_source)
                return matches[0] if matches else None
        except Exception:
            return None
        return None

    def apply_cascading_strategies(self, driver, strategies):
        """Apply strategies in order until one succeeds"""
        for strategy in strategies:
            result = self.apply_strategy(driver, strategy)
            if result:
                return result
        return None


# Configuration Validation
class ConfigurationError(Exception):
    """Raised when configuration is invalid"""

    pass


def validate_config(config):
    """Validate configuration file structure and content"""
    if not isinstance(config, dict):
        raise ConfigurationError("Configuration must be a dictionary")

    if "urls" not in config:
        raise ConfigurationError("Configuration must contain 'urls' section")

    if "house_price_estimates" not in config["urls"]:
        raise ConfigurationError(
            "Configuration must contain 'urls.house_price_estimates' section"
        )

    urls = config["urls"]["house_price_estimates"]
    if not isinstance(urls, list):
        raise ConfigurationError("'house_price_estimates' must be a list")

    if len(urls) == 0:
        raise ConfigurationError("'house_price_estimates' cannot be empty")

    # Validate each URL
    import re

    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    supported_sites = set(SELECTOR_STRATEGIES.keys())
    found_sites = set()

    for url in urls:
        if not isinstance(url, str):
            raise ConfigurationError(f"All URLs must be strings, found: {type(url)}")

        if not url_pattern.match(url):
            raise ConfigurationError(f"Invalid URL format: {url}")

        # Check if URL is for a supported site
        site_found = False
        for site in supported_sites:
            if site in url:
                found_sites.add(site)
                site_found = True
                break

        if not site_found:
            logging.warning(
                f"URL {url} does not match any supported sites: {supported_sites}"
            )

    # Validate that we have strategies for all sites in config
    missing_strategies = found_sites - supported_sites
    if missing_strategies:
        raise ConfigurationError(
            f"No selector strategies defined for sites: {missing_strategies}"
        )

    return True


def load_config():
    """Load and validate configuration file"""
    try:
        with open("config.yml", "r") as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        raise ConfigurationError("Configuration file 'config.yml' not found")
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML syntax in config.yml: {e}")

    validate_config(config)
    return config


def wait_for_element(driver, selector, timeout=15):
    """Wait for element with exponential backoff"""
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.presence_of_element_located(selector))


def wait_for_price_elements(driver, selectors, timeout=20):
    """Wait for any price element to be available"""
    for selector in selectors:
        try:
            return wait_for_element(driver, selector, timeout)
        except TimeoutException:
            continue
    raise TimeoutException("No price elements found")


class UnsupportedPlatformError(Exception):
    """Raised when platform is not supported"""

    pass


def init_driver():
    """Initialize WebDriver with cross-platform support"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    system_arch = platform.machine().lower()
    system_os = platform.system().lower()

    if system_os == "linux":
        if system_arch in ["x86_64", "amd64"]:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=options
            )
        elif system_arch in ["aarch64", "arm64"]:
            options.binary_location = "/usr/bin/chromium-browser"
            driver = webdriver.Chrome(options=options)
        else:
            driver = webdriver.Chrome(options=options)
    elif system_os == "darwin":  # macOS
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
    elif system_os == "windows":
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
    else:
        raise UnsupportedPlatformError(
            f"Unsupported platform: {system_os}-{system_arch}"
        )

    return driver


@dataclass
class ValidationResult:
    """Result of price validation"""

    is_valid: bool
    value: Optional[float] = None
    error_message: str = ""


class PriceValidator:
    def __init__(self):
        self.min_house_price = 100000  # $100k minimum
        self.max_house_price = 50000000  # $50M maximum
        self.price_patterns = [
            r"^\$?[\d,]+\.?\d*[MKmk]?$",  # Standard price formats
            r"^\d+\.?\d*$",  # Numeric only
        ]

    def validate_price(self, price_text, price_type="unknown"):
        """Validate extracted price text"""
        if not price_text or not isinstance(price_text, str):
            return ValidationResult(False, None, "Empty or invalid price text")

        # Pattern validation
        if not any(
            re.match(pattern, price_text.strip()) for pattern in self.price_patterns
        ):
            return ValidationResult(False, None, f"Price format invalid: {price_text}")

        # Convert and range check
        try:
            numeric_price = self.convert_to_numeric(price_text)
            if not (self.min_house_price <= numeric_price <= self.max_house_price):
                return ValidationResult(
                    False, None, f"Price out of range: ${numeric_price:,.0f}"
                )

            return ValidationResult(True, numeric_price, "")
        except ValueError as e:
            return ValidationResult(False, None, f"Conversion error: {e}")

    def convert_to_numeric(self, price_text):
        """Convert price text to numeric value"""
        if not price_text:
            raise ValueError("Empty price text")

        # Remove $ and whitespace
        cleaned = price_text.replace("$", "").replace(",", "").strip()

        # Handle M (millions) and K (thousands) suffixes
        if cleaned.upper().endswith("M"):
            number = float(cleaned[:-1])
            return number * 1000000
        elif cleaned.upper().endswith("K"):
            number = float(cleaned[:-1])
            return number * 1000
        else:
            return float(cleaned)

    def validate_price_relationships(self, lower, midpoint, upper):
        """Ensure price relationships are logical"""
        prices = [p for p in [lower, midpoint, upper] if p is not None]
        if len(prices) < 2:
            return True  # Can't validate relationships

        sorted_prices = sorted(prices)
        return prices == sorted_prices  # Prices should be in ascending order


@dataclass
class ScrapingResult:
    site: str
    url: str
    success: bool
    prices: Dict[str, Optional[float]]
    errors: List[str]
    extraction_method: str
    execution_time: float


class ScrapingLogger:
    def __init__(self, log_file="scraper.log"):
        # Create a unique logger name based on the log file
        logger_name = f"scraper_{log_file.replace('/', '_').replace('.', '_')}"
        self.logger = logging.getLogger(logger_name)

        # Clear any existing handlers to avoid duplication
        self.logger.handlers.clear()

        # Set level and format
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Prevent propagation to avoid double logging
        self.logger.propagate = False

    def log_extraction_attempt(
        self, site, selector_type, selector, success, extracted_value=None
    ):
        """Log each selector attempt with detailed information"""
        status = "SUCCESS" if success else "FAILED"
        emoji = "🎯" if success else "❌"

        if success and extracted_value:
            self.logger.info(
                f"{emoji} {site} - {selector_type} - {status}: Found '{extracted_value}' using {selector[:100]}"
            )
        else:
            self.logger.info(
                f"{emoji} {site} - {selector_type} - {status}: {selector[:100]}"
            )

    def log_price_extraction(
        self, site, price_type, raw_value, formatted_value, method
    ):
        """Log detailed price extraction information"""
        self.logger.info(
            f"💰 {site} - {price_type}: '{raw_value}' → ${formatted_value:,.0f} (via {method})"
        )

    def log_scraping_result(self, result: ScrapingResult):
        """Log comprehensive scraping result"""
        if result.success:
            price_summary = []
            for price_type in ["lower", "midpoint", "upper"]:
                price = result.prices.get(price_type)
                if price:
                    price_summary.append(f"{price_type}: ${price:,.0f}")
                else:
                    price_summary.append(f"{price_type}: None")

            self.logger.info(
                f"✅ {result.site} SUCCESS: {' | '.join(price_summary)} "
                f"(methods: {result.extraction_method}) [{result.execution_time:.2f}s]"
            )
        else:
            self.logger.error(
                f"❌ {result.site} FAILED: {'; '.join(result.errors[:3])} [{result.execution_time:.2f}s]"
            )


def retry_with_backoff(max_attempts=3, base_delay=1, max_delay=60, backoff_factor=2):
    """Decorator for retry logic with exponential backoff"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError, WebDriverException) as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise e

                    delay = min(base_delay * (backoff_factor**attempt), max_delay)
                    jitter = random.uniform(0.1, 0.5) * delay  # Add jitter
                    total_delay = delay + jitter

                    print(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {total_delay:.1f}s"
                    )
                    time.sleep(total_delay)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise e

                    delay = min(base_delay * (backoff_factor**attempt), max_delay)
                    jitter = random.uniform(0.1, 0.5) * delay  # Add jitter
                    total_delay = delay + jitter

                    print(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {total_delay:.1f}s"
                    )
                    time.sleep(total_delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            return None

        return wrapper

    return decorator


class RateLimiter:
    def __init__(self, min_delay=2, max_delay=5):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0

    def wait_if_needed(self):
        """Ensure minimum delay between requests"""
        now = time.time()
        time_since_last = now - self.last_request_time

        if self.last_request_time > 0 and time_since_last < self.min_delay:
            delay = random.uniform(self.min_delay, self.max_delay)
            time.sleep(delay)

        self.last_request_time = time.time()


# Performance Monitoring (Step 7)
@dataclass
class ScrapingMetrics:
    total_sites: int
    successful_sites: int
    failed_sites: int
    total_execution_time: float
    average_time_per_site: float
    extraction_methods_used: Dict[str, int]
    error_summary: Dict[str, int]


def calculate_metrics(results: List[ScrapingResult]) -> ScrapingMetrics:
    """Calculate performance metrics from scraping results"""
    total_sites = len(results)
    successful_sites = sum(1 for r in results if r.success)
    failed_sites = total_sites - successful_sites
    total_time = sum(r.execution_time for r in results)

    methods = {}
    errors = {}

    for result in results:
        for method in result.extraction_method.split(","):
            if method:
                methods[method] = methods.get(method, 0) + 1

        for error in result.errors:
            error_type = error.split(":")[0] if ":" in error else error
            errors[error_type] = errors.get(error_type, 0) + 1

    return ScrapingMetrics(
        total_sites=total_sites,
        successful_sites=successful_sites,
        failed_sites=failed_sites,
        total_execution_time=total_time,
        average_time_per_site=total_time / total_sites if total_sites > 0 else 0,
        extraction_methods_used=methods,
        error_summary=errors,
    )


# Driver Health Checks (Step 6)
def check_driver_health(driver):
    """Check if driver is still responsive"""
    try:
        driver.current_url
        return True
    except Exception:
        return False


def ensure_driver_health(driver):
    """Ensure driver is healthy, recreate if needed"""
    if not check_driver_health(driver):
        driver.quit()
        return init_driver()
    return driver


# Site-Specific Price Formatting (Step 3)
def format_price_by_site(price_text, site):
    """Format price based on site-specific requirements"""
    if "homes.co.nz" in site:
        return format_homes_prices(price_text)
    elif "qv.co.nz" in site:
        return format_qv_prices(price_text)
    elif "propertyvalue.co.nz" in site:
        return format_property_value_prices(price_text)
    elif "realestate.co.nz" in site:
        return format_realestate_prices(price_text)
    elif "oneroof.co.nz" in site:
        return format_oneroof_prices(price_text)
    else:
        # Default: try to parse as generic price
        validator = PriceValidator()
        return validator.convert_to_numeric(price_text)


def scrape_house_prices(driver, url, validate_prices=False, enable_logging=True):
    """Scrape house prices using multi-strategy approach with fallbacks"""
    start_time = time.time()

    if enable_logging:
        logger = ScrapingLogger()

    # Navigate to URL
    driver.get(url)

    # Determine site from URL
    site = None
    for site_key in SELECTOR_STRATEGIES.keys():
        if site_key in url:
            site = site_key
            break

    if not site:
        error_msg = f"No selector strategies found for URL: {url}"
        if enable_logging:
            logger.logger.error(error_msg)
        return ScrapingResult(
            site="unknown",
            url=url,
            success=False,
            prices={"midpoint": None, "upper": None, "lower": None},
            errors=[error_msg],
            extraction_method="none",
            execution_time=time.time() - start_time,
        )

    # Use strategy-based extraction
    strategy = SelectorStrategy()
    prices = {}
    errors = []
    extraction_methods = []

    for price_type in ["midpoint", "upper", "lower"]:
        strategies = SELECTOR_STRATEGIES[site][price_type]

        for strategy_info in strategies:
            try:
                result = strategy.apply_strategy(driver, strategy_info)
                if result:
                    if enable_logging:
                        logger.log_extraction_attempt(
                            site,
                            strategy_info["type"],
                            str(
                                strategy_info.get(
                                    "selector", strategy_info.get("pattern", "")
                                )
                            ),
                            True,
                            result,
                        )

                    # Validate extracted price
                    if validate_prices:
                        validator = PriceValidator()
                        validation_result = validator.validate_price(result, price_type)
                        if validation_result.is_valid:
                            prices[price_type] = validation_result.value
                            extraction_methods.append(
                                f"{price_type}:{strategy_info['type']}"
                            )
                            if enable_logging:
                                logger.log_price_extraction(
                                    site,
                                    price_type,
                                    result,
                                    validation_result.value,
                                    strategy_info["type"],
                                )
                            break
                        else:
                            errors.append(
                                f"{price_type} validation failed: {validation_result.error_message}"
                            )
                    else:
                        # Use existing formatting functions
                        formatted_price = format_price_by_site(result, site)
                        prices[price_type] = formatted_price
                        extraction_methods.append(
                            f"{price_type}:{strategy_info['type']}"
                        )
                        if enable_logging:
                            logger.log_price_extraction(
                                site,
                                price_type,
                                result,
                                formatted_price,
                                strategy_info["type"],
                            )
                        break
                else:
                    if enable_logging:
                        logger.log_extraction_attempt(
                            site,
                            strategy_info["type"],
                            str(
                                strategy_info.get(
                                    "selector", strategy_info.get("pattern", "")
                                )
                            ),
                            False,
                        )
            except Exception as e:
                errors.append(f"{price_type} extraction error: {str(e)}")
                continue

        # If no strategy worked for this price type
        if price_type not in prices:
            prices[price_type] = None
            errors.append(f"All strategies failed for {price_type}")

    # Handle PropertyValue.co.nz special case - leave midpoint as None for external calculation
    if site == "propertyvalue.co.nz":
        prices["midpoint"] = None
        # Remove any midpoint extraction methods
        extraction_methods = [
            m for m in extraction_methods if not m.startswith("midpoint:")
        ]
        if enable_logging:
            logger.logger.info(
                f"🔄 {site} - midpoint: Set to None for external calculation in update_sheets.py"
            )

    # Validate price relationships
    if validate_prices and len([p for p in prices.values() if p is not None]) >= 2:
        validator = PriceValidator()
        if not validator.validate_price_relationships(
            prices.get("lower"), prices.get("midpoint"), prices.get("upper")
        ):
            errors.append("Price relationships are invalid (lower > midpoint > upper)")

    success = any(prices.values())
    execution_time = time.time() - start_time

    result = ScrapingResult(
        site=site,
        url=url,
        success=success,
        prices=prices,
        errors=errors,
        extraction_method=",".join(extraction_methods),
        execution_time=execution_time,
    )

    if enable_logging:
        logger.log_scraping_result(result)

    return result


def find_prices_with_regex(page_source):
    """Find prices in various formats using comprehensive regex patterns"""
    patterns = [
        r"\$\d+\.\d+M(?!\d)",  # $1.2M format (not followed by digit)
        r"\$\d+M(?!\d)",  # $2M format (not followed by digit)
        r"\$\d+\.\d+K(?!\d)",  # $850.5K format (not followed by digit)
        r"\$\d+K(?!\d)",  # $850K format (not followed by digit)
        r"\$[\d,]+\.\d+(?![MK\d])",  # $1,200,000.50 format (not followed by M, K, or digit)
        r"\$[\d,]+(?![MK\d\.])",  # $1,200,000 format (not followed by M, K, digit, or decimal)
    ]
    all_matches = []
    for pattern in patterns:
        matches = re.findall(pattern, page_source)
        all_matches.extend(matches)
    return list(set(all_matches))  # Remove duplicates


def format_homes_prices(price):
    price = price.replace("M", "")
    price = float(price) * 1000000
    return price


def format_qv_prices(price):
    price = price.replace("$", "")
    price = price.replace(",", "")
    price = price.replace("QV: ", "")
    price = float(price)
    return price


def format_property_value_prices(price):
    price = price.replace("$", "")
    price = format_homes_prices(price)
    return price


def format_realestate_prices(price):
    price = format_property_value_prices(price)
    return price


def format_oneroof_prices(price):
    price = format_property_value_prices(price)
    return price


@retry_with_backoff(max_attempts=3)
def scrape_with_retry(driver, url, validate_prices=False, enable_logging=True):
    """Scrape with automatic retry logic"""
    return scrape_house_prices(driver, url, validate_prices, enable_logging)


def scrape_all_house_prices(
    enable_retry=True,
    rate_limit=True,
    min_delay=2,
    max_delay=5,
    validate_prices=False,
    enable_logging=True,
):
    """Scrape all house prices with full robustness features"""

    # Load and validate configuration
    try:
        config = load_config()
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        return []

    urls = config["urls"]["house_price_estimates"]

    # Initialize driver with cross-platform support and retry logic
    driver = None
    for attempt in range(3):
        try:
            driver = init_driver()
            break
        except Exception as e:
            print(f"Driver initialization attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise Exception("Failed to initialize driver after 3 attempts")
            time.sleep(2**attempt)  # Exponential backoff

    # Initialize rate limiter
    if rate_limit:
        limiter = RateLimiter(min_delay=min_delay, max_delay=max_delay)

    results = []

    try:
        for url in urls:
            if rate_limit:
                limiter.wait_if_needed()

            # Ensure driver is healthy
            driver = ensure_driver_health(driver)

            # Scrape with retry logic if enabled
            if enable_retry:
                result = scrape_with_retry(driver, url, validate_prices, enable_logging)
            else:
                result = scrape_house_prices(
                    driver, url, validate_prices, enable_logging
                )

            results.append(result)

            # Print results summary
            if not enable_logging:  # Only print if detailed logging is disabled
                print(f"Scraping data from: {url}")
                print(f"Midpoint Price: {result.prices.get('midpoint')}")
                print(f"Upper Price: {result.prices.get('upper')}")
                print(f"Lower Price: {result.prices.get('lower')}")

                if not result.success:
                    print(f"Errors: {', '.join(result.errors)}")

    finally:
        if driver:
            driver.quit()

    return results


if __name__ == "__main__":
    scrape_all_house_prices()
