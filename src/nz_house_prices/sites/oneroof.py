"""oneroof.co.nz site implementation."""

import re
import time
from typing import List, Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from nz_house_prices.sites.base import BaseSite, SearchResult


class OneRoofSite(BaseSite):
    """Handler for oneroof.co.nz property searches.

    Uses the search autocomplete to find property URLs directly.
    """

    SITE_NAME = "oneroof.co.nz"
    SITE_DOMAIN = "oneroof.co.nz"
    SEARCH_URL = "https://www.oneroof.co.nz"

    def _extract_unit_number(self, address: str) -> Optional[str]:
        """Extract unit number from an address string."""
        match = re.match(r"^(\d+[A-Za-z]?)\s*/", address)
        if match:
            return match.group(1)
        match = re.match(r"^(?:unit|flat|apt|apartment)\s*(\d+[A-Za-z]?)", address, re.I)
        if match:
            return match.group(1)
        return None

    def _find_best_match(
        self, property_links: list, target_address: str
    ) -> Tuple[Optional[str], str]:
        """Find the best matching property from autocomplete results.

        Args:
            property_links: List of (url, text) tuples from autocomplete
            target_address: The address we're looking for

        Returns:
            Tuple of (best_url, best_address_text)
        """
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()
        target_words = set(target_lower.split())

        best_url = None
        best_text = ""
        best_score = -1

        for url, text in property_links:
            if not url or not text:
                continue

            # Extract just the address part (before any newlines/extra info)
            address_text = text.split("\n")[0].strip()
            if not address_text:
                continue

            score = 0
            result_unit = self._extract_unit_number(address_text)

            # Exact unit match is highest priority
            if target_unit and result_unit:
                if target_unit == result_unit:
                    score += 100
                else:
                    score -= 50
            elif target_unit and not result_unit:
                score -= 10

            # Check word overlap
            address_lower = address_text.lower()
            address_words = set(address_lower.split())
            common_words = target_words & address_words
            score += len(common_words) * 10

            # Bonus for matching street number at start
            first_word = target_lower.split()[0] if target_lower else ""
            if first_word and address_lower.startswith(first_word):
                score += 50

            if score > best_score:
                best_score = score
                best_url = url
                best_text = address_text

        return best_url, best_text

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on oneroof.co.nz.

        Uses the search autocomplete to find property URLs directly.

        Args:
            address: The address to search for

        Returns:
            List of SearchResult objects
        """
        results = []
        normalized_address = self.normalize_address(address)

        try:
            # Load the page
            self.driver.get(self.SEARCH_URL)
            time.sleep(3)

            wait = WebDriverWait(self.driver, 10)

            # Find the search input
            search_input = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "input[type='search'], input[placeholder*='address' i]")
                )
            )

            # Type the address
            search_input.click()
            time.sleep(0.3)
            search_input.clear()
            search_input.send_keys(normalized_address)
            time.sleep(2.5)  # Wait for autocomplete

            # Find property links in autocomplete
            property_links = []
            link_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "a[href*='/property/']"
            )

            for link in link_elements:
                href = link.get_attribute("href")
                text = link.text.strip()
                if href and "/property/" in href:
                    property_links.append((href, text))

            if property_links:
                best_url, best_text = self._find_best_match(
                    property_links, normalized_address
                )

                if best_url:
                    confidence = self._calculate_confidence(
                        normalized_address, best_text
                    )
                    results.append(
                        SearchResult(
                            address=best_text,
                            url=best_url,
                            confidence=confidence,
                            site=self.SITE_NAME,
                        )
                    )

            # If no results, try shorter query
            if not results:
                parts = [p.strip() for p in normalized_address.split(",")]
                for i in range(len(parts) - 1, 0, -1):
                    shorter_query = ", ".join(parts[:i])

                    # Clear and retype
                    search_input.clear()
                    search_input.send_keys(shorter_query)
                    time.sleep(2.5)

                    # Check for property links again
                    link_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, "a[href*='/property/']"
                    )

                    property_links = []
                    for link in link_elements:
                        href = link.get_attribute("href")
                        text = link.text.strip()
                        if href and "/property/" in href:
                            property_links.append((href, text))

                    if property_links:
                        best_url, best_text = self._find_best_match(
                            property_links, normalized_address
                        )

                        if best_url:
                            confidence = self._calculate_confidence(
                                normalized_address, best_text
                            )
                            results.append(
                                SearchResult(
                                    address=best_text,
                                    url=best_url,
                                    confidence=confidence,
                                    site=self.SITE_NAME,
                                )
                            )
                            break

        except Exception as e:
            print(f"Error searching oneroof.co.nz: {e}")

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
