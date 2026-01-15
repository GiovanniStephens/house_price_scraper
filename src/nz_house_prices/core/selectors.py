"""Selector strategies for extracting prices from real estate websites."""

import re
from typing import Dict, List, Optional

from playwright.sync_api import Page

# Selector strategies for each supported site
SELECTOR_STRATEGIES: Dict[str, Dict[str, List[Dict[str, str]]]] = {
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
                "selector": (
                    '//*[@id="content"]/div/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div'
                ),
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
            {"type": "css", "selector": "[testid='pv-midpoint']"},
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'property-value-mid')]",
            },
            {"type": "regex_fallback", "pattern": r"\$\d\.\d{1,2}M"},
        ],
        "upper": [
            {"type": "css", "selector": "[testid='highEstimate']"},
            {
                "type": "xpath",
                "selector": (
                    '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[2]'
                ),
            },
            {"type": "css", "selector": "[testid='pv-upper']"},
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'property-value-upper')]",
            },
            {"type": "regex_fallback", "pattern": r"\$\d\.\d{1,2}M"},
        ],
        "lower": [
            {"type": "css", "selector": "[testid='lowEstimate']"},
            {
                "type": "xpath",
                "selector": (
                    '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[1]'
                ),
            },
            {"type": "css", "selector": "[testid='pv-lower']"},
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'property-value-lower')]",
            },
            {"type": "regex_fallback", "pattern": r"\$\d\.\d{1,2}M"},
        ],
    },
    "realestate.co.nz": {
        "midpoint": [
            {
                "type": "css",
                "selector": "[data-test='reinz-valuation__price-range'] div:nth-child(2) h4",
            },
            {
                "type": "css",
                "selector": "div.col-span-3 > div > div:nth-child(2) > h4",
            },
            {
                "type": "xpath",
                "selector": "//div[@data-test='reinz-valuation__price-range']/div[2]//h4",
            },
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
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*[KkMm]"},
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
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*[KkMm]"},
        ],
    },
    "oneroof.co.nz": {
        "midpoint": [
            {
                "type": "css",
                "selector": "div.text-3xl.font-bold.text-secondary.-mt-60.pb-22",
            },
            {
                "type": "css",
                "selector": "div.text-3xl.font-bold.text-secondary",
            },
            {
                "type": "xpath",
                "selector": (
                    "//div[contains(@class, 'text-3xl') and "
                    "contains(@class, 'font-bold') and contains(@class, 'text-secondary')]"
                ),
            },
            {"type": "css", "selector": "[data-testid='oneroof-midpoint']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*[MKmk]"},
        ],
        "upper": [
            {
                "type": "css",
                "selector": (
                    "div.text-center.font-medium.absolute.top-0.pt-10.right-0 "
                    "> div.text-base.md\\:text-xl"
                ),
            },
            {
                "type": "xpath",
                "selector": (
                    "//div[contains(@class, 'right-0')]//div[contains(@class, 'text-base')]"
                ),
            },
            {"type": "css", "selector": "[data-testid='oneroof-upper']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*[MKmk]"},
        ],
        "lower": [
            {
                "type": "css",
                "selector": (
                    "div.text-center.font-medium.absolute.top-0.pt-10.left-0 "
                    "> div.text-base.md\\:text-xl"
                ),
            },
            {
                "type": "xpath",
                "selector": "//div[contains(@class, 'left-0')]//div[contains(@class, 'text-base')]",
            },
            {"type": "css", "selector": "[data-testid='oneroof-lower']"},
            {"type": "regex_fallback", "pattern": r"\$\d+\.?\d*[MKmk]"},
        ],
    },
}


class SelectorStrategy:
    """Multi-strategy selector system for robust element finding."""

    def apply_strategy(self, page: Page, strategy: Dict[str, str]) -> Optional[str]:
        """Apply a single selector strategy.

        Args:
            page: Playwright Page instance
            strategy: Strategy configuration dict

        Returns:
            Extracted text or None if strategy failed
        """
        try:
            if strategy["type"] == "css":
                locator = page.locator(strategy["selector"]).first
                if locator.count() > 0:
                    return locator.text_content()
            elif strategy["type"] == "xpath":
                locator = page.locator(f"xpath={strategy['selector']}").first
                if locator.count() > 0:
                    return locator.text_content()
            elif strategy["type"] == "text_pattern":
                page_content = page.content()
                matches = re.findall(strategy["pattern"], page_content)
                return matches[0] if matches else None
            elif strategy["type"] == "regex_fallback":
                page_content = page.content()
                matches = re.findall(strategy["pattern"], page_content)
                return matches[0] if matches else None
        except Exception:
            return None
        return None

    def apply_cascading_strategies(
        self, page: Page, strategies: List[Dict[str, str]]
    ) -> Optional[str]:
        """Apply strategies in order until one succeeds.

        Args:
            page: Playwright Page instance
            strategies: List of strategy configurations

        Returns:
            First successful extraction result or None
        """
        for strategy in strategies:
            result = self.apply_strategy(page, strategy)
            if result:
                return result
        return None


def get_supported_sites() -> List[str]:
    """Get list of supported real estate sites.

    Returns:
        List of supported site domain names
    """
    return list(SELECTOR_STRATEGIES.keys())
