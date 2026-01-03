"""
Backward-compatible shim for nz_house_prices package.

This module re-exports all symbols from the nz_house_prices package
to maintain compatibility with existing code that imports from scraper.py.

For new code, import directly from nz_house_prices:
    from nz_house_prices import scrape_all_house_prices
"""

# Re-export everything from the package
from nz_house_prices import (
    SELECTOR_STRATEGIES,
    ConfigurationError,
    PriceValidator,
    RateLimiter,
    ScrapingLogger,
    ScrapingMetrics,
    ScrapingResult,
    SelectorStrategy,
    UnsupportedPlatformError,
    ValidationResult,
    calculate_metrics,
    check_driver_health,
    ensure_driver_health,
    find_prices_with_regex,
    format_homes_prices,
    format_oneroof_prices,
    format_price_by_site,
    format_property_value_prices,
    format_qv_prices,
    format_realestate_prices,
    init_driver,
    load_config,
    retry_with_backoff,
    scrape_all_house_prices,
    scrape_house_prices,
    scrape_with_retry,
    validate_config,
)

# Also import these for compatibility with existing code
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


# These functions are included for compatibility with existing tests
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


if __name__ == "__main__":
    scrape_all_house_prices()
