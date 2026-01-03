"""Core scraping functionality."""

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
from nz_house_prices.core.selectors import SELECTOR_STRATEGIES, SelectorStrategy

__all__ = [
    "init_driver",
    "check_driver_health",
    "ensure_driver_health",
    "UnsupportedPlatformError",
    "scrape_house_prices",
    "scrape_with_retry",
    "scrape_all_house_prices",
    "SELECTOR_STRATEGIES",
    "SelectorStrategy",
]
