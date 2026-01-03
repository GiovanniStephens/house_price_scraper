"""
NZ House Prices - Scrape house price estimates from NZ real estate websites.

Simple Usage (NEW - search by address):
    >>> from nz_house_prices import get_prices
    >>> prices = get_prices("123 Example Street, Ponsonby, Auckland")
    >>> print(prices["homes.co.nz"].midpoint)
    1850000

Class-based Usage:
    >>> from nz_house_prices import HousePriceScraper
    >>> with HousePriceScraper() as scraper:
    ...     prices = scraper.scrape_address("123 Main Street, Auckland")

Legacy Usage (from URLs):
    >>> from nz_house_prices import get_prices_from_urls
    >>> results = get_prices_from_urls(["https://homes.co.nz/address/..."])

Config-based Usage:
    >>> from nz_house_prices import scrape_all_house_prices
    >>> results = scrape_all_house_prices()  # Uses config.yml

Supported Sites:
    - homes.co.nz
    - qv.co.nz
    - propertyvalue.co.nz
    - realestate.co.nz
    - oneroof.co.nz
"""

__version__ = "1.0.0"

# Core functionality
from nz_house_prices.core.driver import (
    UnsupportedPlatformError,
    check_driver_health,
    ensure_driver_health,
    init_driver,
)
from nz_house_prices.core.scraper import (
    scrape_all_house_prices,
    scrape_house_prices,
    scrape_with_retry,
)
from nz_house_prices.core.selectors import (
    SELECTOR_STRATEGIES,
    SelectorStrategy,
    get_supported_sites,
)

# Configuration
from nz_house_prices.config.loader import (
    ConfigurationError,
    load_config,
    validate_config,
)

# Models
from nz_house_prices.models.results import (
    PriceEstimate,
    ScrapingMetrics,
    ScrapingResult,
    ValidationResult,
    calculate_metrics,
)

# Utilities
from nz_house_prices.utils.logging import ScrapingLogger
from nz_house_prices.utils.price_format import (
    PriceValidator,
    find_prices_with_regex,
    format_homes_prices,
    format_oneroof_prices,
    format_price_by_site,
    format_property_value_prices,
    format_qv_prices,
    format_realestate_prices,
)
from nz_house_prices.utils.rate_limit import RateLimiter
from nz_house_prices.utils.retry import retry_with_backoff

# High-level API (NEW)
from nz_house_prices.api import (
    HousePriceScraper,
    get_prices,
    get_prices_from_urls,
)

# Discovery (URL resolution from addresses)
from nz_house_prices.discovery import (
    ParsedAddress,
    PropertyResolver,
    URLCache,
    normalize_address,
    parse_address,
    resolve_property_urls,
)

# Site handlers
from nz_house_prices.sites import (
    SITE_HANDLERS,
    BaseSite,
    SearchResult,
    get_site_handler,
)

__all__ = [
    # Version
    "__version__",
    # High-level API (recommended)
    "get_prices",
    "get_prices_from_urls",
    "HousePriceScraper",
    # Discovery
    "PropertyResolver",
    "resolve_property_urls",
    "parse_address",
    "normalize_address",
    "ParsedAddress",
    "URLCache",
    # Site handlers
    "BaseSite",
    "SearchResult",
    "SITE_HANDLERS",
    "get_site_handler",
    # Core
    "init_driver",
    "check_driver_health",
    "ensure_driver_health",
    "UnsupportedPlatformError",
    "scrape_house_prices",
    "scrape_with_retry",
    "scrape_all_house_prices",
    "SELECTOR_STRATEGIES",
    "SelectorStrategy",
    "get_supported_sites",
    # Config
    "load_config",
    "validate_config",
    "ConfigurationError",
    # Models
    "ScrapingResult",
    "ValidationResult",
    "ScrapingMetrics",
    "PriceEstimate",
    "calculate_metrics",
    # Utils
    "ScrapingLogger",
    "RateLimiter",
    "retry_with_backoff",
    "PriceValidator",
    "format_price_by_site",
    "format_homes_prices",
    "format_qv_prices",
    "format_property_value_prices",
    "format_realestate_prices",
    "format_oneroof_prices",
    "find_prices_with_regex",
]
