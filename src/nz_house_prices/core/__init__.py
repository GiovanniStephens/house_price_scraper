"""Core scraping functionality."""

from nz_house_prices.core.driver import BrowserManager, create_page
from nz_house_prices.core.scraper import (
    scrape_all_house_prices,
    scrape_house_prices,
    scrape_with_retry,
)
from nz_house_prices.core.selectors import SELECTOR_STRATEGIES, SelectorStrategy

__all__ = [
    "BrowserManager",
    "create_page",
    "scrape_house_prices",
    "scrape_with_retry",
    "scrape_all_house_prices",
    "SELECTOR_STRATEGIES",
    "SelectorStrategy",
]
