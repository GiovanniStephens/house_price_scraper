"""qv.co.nz site implementation."""

import re
import time
from typing import List, Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from nz_house_prices.sites.base import BaseSite, SearchResult


class QVSite(BaseSite):
    """Handler for qv.co.nz property searches.

    Note: QV's Vue.js search autocomplete has limited support for browser automation.
    Address discovery may not work reliably. Direct URL scraping works fine.
    """

    SITE_NAME = "qv.co.nz"
    SITE_DOMAIN = "qv.co.nz"
    SEARCH_URL = "https://www.qv.co.nz"

    # Selectors for Vue.js based search
    SEARCH_INPUT_SELECTOR = "input.c-address_search__field, [data-cy='address-search']"

    def _extract_unit_number(self, address: str) -> Optional[str]:
        """Extract unit number from an address string."""
        match = re.match(r"^(\d+[A-Za-z]?)\s*/", address)
        if match:
            return match.group(1)
        match = re.match(r"^(?:unit|flat|apt|apartment)\s*(\d+[A-Za-z]?)", address, re.I)
        if match:
            return match.group(1)
        return None

    def _find_best_matching_result(
        self, result_items: list, target_address: str
    ) -> Tuple[Optional[object], str]:
        """Find the best matching result from autocomplete items."""
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()

        best_match = None
        best_text = ""
        best_score = -1

        for item in result_items:
            try:
                item_text = item.text.strip()
                if not item_text:
                    continue

                score = 0
                result_unit = self._extract_unit_number(item_text)

                # Exact unit match is highest priority
                if target_unit and result_unit:
                    if target_unit == result_unit:
                        score += 100
                    else:
                        score -= 50
                elif target_unit and not result_unit:
                    score -= 10

                # Check for address overlap
                item_lower = item_text.lower()
                if any(word in item_lower for word in target_lower.split()[:3]):
                    score += 20

                if score > best_score:
                    best_score = score
                    best_match = item
                    best_text = item_text

            except Exception:
                continue

        return best_match, best_text

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on qv.co.nz.

        Args:
            address: The address to search for

        Returns:
            List of SearchResult objects
        """
        results = []
        normalized_address = self.normalize_address(address)

        try:
            # Navigate to the site
            self.driver.get(self.SEARCH_URL)
            time.sleep(3)  # Wait for Vue.js to mount

            wait = WebDriverWait(self.driver, 10)

            # Find the search input using data-cy attribute
            search_input = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "[data-cy='address-search'], input.c-address_search__field")
                )
            )

            # Click and enter the address
            search_input.click()
            search_input.clear()
            search_input.send_keys(normalized_address)
            time.sleep(2.5)  # Wait for autocomplete dropdown

            # Look for search results container (data-cy="display-search-result")
            try:
                results_container = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[data-cy='display-search-result'], .c-address_search__results")
                    )
                )

                # Find all result items
                result_items = results_container.find_elements(
                    By.CSS_SELECTOR, ".c-address_search__result_item"
                )

                if result_items:
                    # Find best matching result
                    best_item, item_text = self._find_best_matching_result(
                        result_items, normalized_address
                    )

                    if best_item:
                        # Click the best matching result
                        best_item.click()
                        time.sleep(2)

                        # Check the URL to see if we're on a property page
                        current_url = self.driver.current_url
                        if "/property" in current_url:
                            confidence = self._calculate_confidence(
                                normalized_address, item_text
                            )
                            results.append(
                                SearchResult(
                                    address=item_text or normalized_address,
                                    url=current_url,
                                    confidence=confidence,
                                    site=self.SITE_NAME,
                                )
                            )
            except Exception:
                pass

            # If no autocomplete results, try clicking the Go button
            if not results:
                try:
                    go_button = self.driver.find_element(
                        By.CSS_SELECTOR, ".c-address_search__button"
                    )
                    if go_button.is_enabled():
                        go_button.click()
                        time.sleep(2)
                        current_url = self.driver.current_url
                        if "/property" in current_url:
                            results.append(
                                SearchResult(
                                    address=normalized_address,
                                    url=current_url,
                                    confidence=0.7,
                                    site=self.SITE_NAME,
                                )
                            )
                except Exception:
                    pass

        except Exception as e:
            print(f"Error searching qv.co.nz: {e}")

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def get_property_url(self, address: str) -> Optional[str]:
        """Get the best matching property URL.

        Args:
            address: The address to search for

        Returns:
            URL string or None if not found
        """
        results = self.search_property(address)
        if results and results[0].confidence > 0.5:
            return results[0].url
        return None
