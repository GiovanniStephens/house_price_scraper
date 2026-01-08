"""Main scraping functionality."""

import time
from typing import List, Optional

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from nz_house_prices.config.loader import ConfigurationError, load_config
from nz_house_prices.core.driver import BrowserManager
from nz_house_prices.core.selectors import SELECTOR_STRATEGIES, SelectorStrategy
from nz_house_prices.models.results import ScrapingResult
from nz_house_prices.utils.logging import ScrapingLogger
from nz_house_prices.utils.price_format import PriceValidator, format_price_by_site
from nz_house_prices.utils.rate_limit import RateLimiter
from nz_house_prices.utils.retry import retry_with_backoff


def scrape_house_prices(
    page: Page,
    url: str,
    validate_prices: bool = False,
    enable_logging: bool = True,
) -> ScrapingResult:
    """Scrape house prices using multi-strategy approach with fallbacks.

    Args:
        page: Playwright Page instance
        url: URL to scrape
        validate_prices: Whether to validate extracted prices
        enable_logging: Whether to enable detailed logging

    Returns:
        ScrapingResult with extracted prices and metadata
    """
    start_time = time.time()

    logger: Optional[ScrapingLogger] = None
    if enable_logging:
        logger = ScrapingLogger()

    # Navigate to URL
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Wait for page content to load
    try:
        page.wait_for_selector(
            "[class*='price'], [class*='estimate'], [class*='value'], [data-testid*='price']",
            state="visible",
            timeout=5000,
        )
    except PlaywrightTimeoutError:
        # Fallback: wait briefly for page to stabilize
        page.wait_for_timeout(1000)

    # Determine site from URL
    site = None
    for site_key in SELECTOR_STRATEGIES.keys():
        if site_key in url:
            site = site_key
            break

    if not site:
        error_msg = f"No selector strategies found for URL: {url}"
        if logger:
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
                result = strategy.apply_strategy(page, strategy_info)
                if result:
                    if logger:
                        logger.log_extraction_attempt(
                            site,
                            strategy_info["type"],
                            str(strategy_info.get("selector", strategy_info.get("pattern", ""))),
                            True,
                            result,
                        )

                    # Validate extracted price
                    if validate_prices:
                        validator = PriceValidator()
                        validation_result = validator.validate_price(result, price_type)
                        if validation_result.is_valid:
                            prices[price_type] = validation_result.value
                            extraction_methods.append(f"{price_type}:{strategy_info['type']}")
                            if logger:
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
                        extraction_methods.append(f"{price_type}:{strategy_info['type']}")
                        if logger:
                            logger.log_price_extraction(
                                site,
                                price_type,
                                result,
                                formatted_price,
                                strategy_info["type"],
                            )
                        break
                else:
                    if logger:
                        logger.log_extraction_attempt(
                            site,
                            strategy_info["type"],
                            str(strategy_info.get("selector", strategy_info.get("pattern", ""))),
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
        extraction_methods = [m for m in extraction_methods if not m.startswith("midpoint:")]
        if logger:
            logger.logger.info(f"~ {site} - midpoint: Set to None for external calculation")

    # Calculate midpoint from lower/upper if midpoint is None but both bounds exist
    if prices.get("midpoint") is None and prices.get("lower") and prices.get("upper"):
        try:
            lower_val = prices["lower"]
            upper_val = prices["upper"]
            if isinstance(lower_val, (int, float)) and isinstance(upper_val, (int, float)):
                prices["midpoint"] = int((lower_val + upper_val) / 2)
                extraction_methods.append("midpoint:calculated")
                if logger:
                    logger.logger.info(
                        f"~ {site} - midpoint: Calculated as {prices['midpoint']} from lower/upper"
                    )
        except (TypeError, ValueError):
            pass  # Keep midpoint as None if calculation fails

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

    if logger:
        logger.log_scraping_result(result)

    return result


@retry_with_backoff(max_attempts=3)
def scrape_with_retry(
    page: Page,
    url: str,
    validate_prices: bool = False,
    enable_logging: bool = True,
) -> ScrapingResult:
    """Scrape with automatic retry logic.

    Args:
        page: Playwright Page instance
        url: URL to scrape
        validate_prices: Whether to validate extracted prices
        enable_logging: Whether to enable detailed logging

    Returns:
        ScrapingResult with extracted prices and metadata
    """
    return scrape_house_prices(page, url, validate_prices, enable_logging)


def scrape_all_house_prices(
    enable_retry: bool = True,
    rate_limit: bool = True,
    min_delay: float = 2,
    max_delay: float = 5,
    validate_prices: bool = False,
    enable_logging: bool = True,
) -> List[ScrapingResult]:
    """Scrape all house prices with full robustness features.

    Args:
        enable_retry: Whether to enable automatic retries
        rate_limit: Whether to enable rate limiting
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests
        validate_prices: Whether to validate extracted prices
        enable_logging: Whether to enable detailed logging

    Returns:
        List of ScrapingResult objects
    """
    # Load and validate configuration
    try:
        config = load_config()
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        return []

    urls = config["urls"]["house_price_estimates"]

    # Initialize rate limiter
    limiter = None
    if rate_limit:
        limiter = RateLimiter(min_delay=min_delay, max_delay=max_delay)

    results = []

    with BrowserManager() as browser_manager:
        page = browser_manager.new_page()

        for url in urls:
            if limiter:
                limiter.wait_if_needed()

            # Scrape with retry logic if enabled
            if enable_retry:
                result = scrape_with_retry(page, url, validate_prices, enable_logging)
            else:
                result = scrape_house_prices(page, url, validate_prices, enable_logging)

            results.append(result)

            # Print results summary
            if not enable_logging:
                print(f"Scraping data from: {url}")
                print(f"Midpoint Price: {result.prices.get('midpoint')}")
                print(f"Upper Price: {result.prices.get('upper')}")
                print(f"Lower Price: {result.prices.get('lower')}")

                if not result.success:
                    print(f"Errors: {', '.join(result.errors)}")

    return results
