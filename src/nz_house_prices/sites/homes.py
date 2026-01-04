"""homes.co.nz site implementation."""

import re
import time
from typing import List, Optional, Tuple

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from nz_house_prices.sites.base import BaseSite, SearchResult


class HomesSite(BaseSite):
    """Handler for homes.co.nz property searches."""

    SITE_NAME = "homes.co.nz"
    SITE_DOMAIN = "homes.co.nz"
    SEARCH_URL = "https://homes.co.nz"

    # Selectors for search functionality (Angular Material based)
    SEARCH_INPUT_SELECTOR = "input[placeholder*='address' i], input[placeholder*='Search by' i]"
    SEARCH_RESULT_ITEM_SELECTOR = "[class*='addressResult'], [class*='search-result']"
    RESULT_STREET_SELECTOR = "[class*='addressResultStreet'], .street"
    RESULT_SUBURB_SELECTOR = "[class*='addressResultSuburb'], .suburb"

    def _extract_unit_number(self, address: str) -> Optional[str]:
        """Extract unit number from an address string.

        Args:
            address: Address string (e.g., "3/14 Buffon Street" or "Unit 3, 14 Main St")

        Returns:
            Unit number as string, or None if no unit
        """
        # Match patterns like "3/14" or "3A/14"
        match = re.match(r"^(\d+[A-Za-z]?)\s*/", address)
        if match:
            return match.group(1)

        # Match patterns like "Unit 3" or "Flat 3A"
        match = re.match(r"^(?:unit|flat|apt|apartment)\s*(\d+[A-Za-z]?)", address, re.I)
        if match:
            return match.group(1)

        return None

    def _find_best_matching_result(
        self, result_items: list, target_address: str
    ) -> Tuple[Optional[object], str, str]:
        """Find the best matching result from autocomplete items.

        Uses location-aware scoring to distinguish between properties
        with the same street address in different suburbs/cities.

        Args:
            result_items: List of autocomplete result elements
            target_address: The address we're looking for

        Returns:
            Tuple of (best_element, street_text, suburb_text)
        """
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()

        best_match = None
        best_street = ""
        best_suburb = ""
        best_score = -1000  # Start very low to allow negative scores

        for item in result_items:
            try:
                # Get the street text from this result
                street_elem = item.find_element(
                    By.CSS_SELECTOR, "[class*='addressResultStreet']"
                )
                street_text = street_elem.text.strip()

                # Get suburb if available
                suburb_text = ""
                try:
                    suburb_elem = item.find_element(
                        By.CSS_SELECTOR, "[class*='addressResultSuburb']"
                    )
                    suburb_text = suburb_elem.text.strip()
                except Exception:
                    pass

                # Calculate match score
                score = 0
                result_unit = self._extract_unit_number(street_text)

                # Exact unit match is highest priority
                if target_unit and result_unit:
                    if target_unit == result_unit:
                        score += 100  # Exact unit match
                    else:
                        score -= 50  # Wrong unit, penalize heavily
                elif target_unit and not result_unit:
                    # Looking for a unit but this result has no unit
                    score -= 10

                # Check if street name matches (without unit)
                street_lower = street_text.lower()
                # Remove unit prefix for comparison
                street_core = re.sub(r"^\d+[A-Za-z]?\s*/\s*", "", street_lower)
                target_core = re.sub(r"^\d+[A-Za-z]?\s*/\s*", "", target_lower)

                # Check for street number and name match
                if street_core in target_core or target_core in street_core:
                    score += 20

                # Geocoding-based location scoring
                result_full_address = f"{street_text}, {suburb_text}"
                location_score, _ = self._calculate_location_score(
                    target_address, result_full_address
                )
                score += location_score

                if score > best_score:
                    best_score = score
                    best_match = item
                    best_street = street_text
                    best_suburb = suburb_text

            except Exception:
                continue

        return best_match, best_street, best_suburb

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on homes.co.nz.

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
            time.sleep(3)  # Wait for Angular to load

            wait = WebDriverWait(self.driver, 10)

            # Find the search input (use ID or placeholder)
            search_input = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "#autocomplete-search, input[placeholder*='address' i]")
                )
            )

            # Click and enter the address
            search_input.click()
            search_input.clear()
            search_input.send_keys(normalized_address)

            # Wait for autocomplete dropdown (WebDriverWait is faster than fixed sleep)
            try:
                results_container = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[class*='addressResults']")
                    )
                )
            except TimeoutException:
                return []

            # Find all individual result items within the container
            result_items = results_container.find_elements(
                By.CSS_SELECTOR, "[class*='addressResult']:not([class*='addressResults'])"
            )

            # If no individual items, treat the container as a single result
            if not result_items:
                result_items = [results_container]

            # Find the best matching result based on unit number
            best_item, street, suburb = self._find_best_matching_result(
                result_items, normalized_address
            )

            if best_item is None and result_items:
                # Fallback to first result if no good match
                best_item = result_items[0]
                try:
                    street_elem = best_item.find_element(
                        By.CSS_SELECTOR, "[class*='addressResultStreet']"
                    )
                    street = street_elem.text
                except Exception:
                    pass
                try:
                    suburb_elem = best_item.find_element(
                        By.CSS_SELECTOR, "[class*='addressResultSuburb']"
                    )
                    suburb = suburb_elem.text
                except Exception:
                    pass

            full_address = f"{street}, {suburb}".strip(", ")

            # Click the best matching result to navigate
            if best_item:
                best_item.click()

                # Wait for map page to load with property links
                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "a[href*='/address/']")
                        )
                    )
                except TimeoutException:
                    pass

                # Now on the map page, find the property tile link
                property_links = self.driver.find_elements(
                    By.CSS_SELECTOR, "a[href*='/address/']"
                )

                if property_links:
                    # Get the first property link URL
                    property_url = property_links[0].get_attribute("href")

                    if property_url:
                        confidence = self._calculate_confidence(
                            normalized_address, full_address
                        )
                        results.append(
                            SearchResult(
                                address=full_address,
                                url=property_url,
                                confidence=confidence,
                                site=self.SITE_NAME,
                            )
                        )

        except Exception as e:
            print(f"Error searching homes.co.nz: {e}")

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
