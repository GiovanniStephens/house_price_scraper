"""homes.co.nz site implementation."""

import re
from typing import List, Optional, Tuple

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from nz_house_prices.sites.base import BaseSite, SearchResult


class HomesSite(BaseSite):
    """Handler for homes.co.nz property searches."""

    SITE_NAME = "homes.co.nz"
    SITE_DOMAIN = "homes.co.nz"
    SEARCH_URL = "https://homes.co.nz"

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
    ) -> Tuple[Optional[object], str, str]:
        """Find the best matching result from autocomplete items."""
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()

        best_match = None
        best_street = ""
        best_suburb = ""
        best_score = -1000

        for item in result_items:
            try:
                street_elem = item.locator("[class*='addressResultStreet']").first
                street_text = street_elem.text_content() or ""
                street_text = street_text.strip()

                suburb_text = ""
                suburb_elem = item.locator("[class*='addressResultSuburb']").first
                if suburb_elem.count() > 0:
                    suburb_text = suburb_elem.text_content() or ""
                    suburb_text = suburb_text.strip()

                score = 0
                result_unit = self._extract_unit_number(street_text)

                if target_unit and result_unit:
                    if target_unit == result_unit:
                        score += 100
                    else:
                        score -= 50
                elif target_unit and not result_unit:
                    score -= 10

                street_lower = street_text.lower()
                street_core = re.sub(r"^\d+[A-Za-z]?\s*/\s*", "", street_lower)
                target_core = re.sub(r"^\d+[A-Za-z]?\s*/\s*", "", target_lower)

                if street_core in target_core or target_core in street_core:
                    score += 20

                if score > best_score:
                    best_score = score
                    best_match = item
                    best_street = street_text
                    best_suburb = suburb_text

            except Exception:
                continue

        # Validate best match with geocoding (single call, not per-candidate)
        if best_match and best_street:
            result_full_address = f"{best_street}, {best_suburb}"
            location_score, is_close = self._calculate_location_score(
                target_address, result_full_address, max_distance_km=5.0
            )
            # Reject if the match is geographically too far or geocoding failed
            if not is_close:
                return None, "", ""

        return best_match, best_street, best_suburb

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on homes.co.nz."""
        results = []
        normalized_address = self.normalize_address(address)

        try:
            self.page.goto(self.SEARCH_URL, wait_until="domcontentloaded", timeout=30000)

            # Handle potential cookie consent or modals
            try:
                close_btn = self.page.locator(
                    "button:has-text('Accept'), button:has-text('Close'), "
                    "[aria-label='Close'], .modal-close"
                ).first
                if close_btn.count() > 0:
                    close_btn.click(timeout=2000)
            except Exception:
                pass

            # Find and interact with search input - try multiple selectors
            search_selectors = [
                "#autocomplete-search",
                "input[placeholder*='address' i]",
                "input[placeholder*='search' i]",
                "input[type='search']",
                "input[name='search']",
                "[data-testid='search-input']",
                ".search-input input",
            ]

            search_input = None
            for selector in search_selectors:
                try:
                    locator = self.page.locator(selector).first
                    if locator.count() > 0:
                        locator.wait_for(state="visible", timeout=3000)
                        search_input = locator
                        break
                except PlaywrightTimeoutError:
                    continue

            if search_input is None:
                print("homes.co.nz: Could not find search input")
                return []

            search_input.click()
            search_input.fill(normalized_address)

            # Wait for autocomplete dropdown
            try:
                self.page.wait_for_selector(
                    "[class*='addressResults']", state="visible", timeout=5000
                )
            except PlaywrightTimeoutError:
                return []

            # Find all result items
            results_container = self.page.locator("[class*='addressResults']").first
            result_items = results_container.locator(
                "[class*='addressResult']:not([class*='addressResults'])"
            ).all()

            if not result_items:
                result_items = [results_container]

            best_item, street, suburb = self._find_best_matching_result(
                result_items, normalized_address
            )

            if best_item is None and result_items:
                best_item = result_items[0]
                try:
                    street = (
                        best_item.locator("[class*='addressResultStreet']").first.text_content()
                        or ""
                    )
                except Exception:
                    pass
                try:
                    suburb = (
                        best_item.locator("[class*='addressResultSuburb']").first.text_content()
                        or ""
                    )
                except Exception:
                    pass

            full_address = f"{street}, {suburb}".strip(", ")

            if best_item:
                best_item.click()

                # Wait for property links on map page
                try:
                    self.page.wait_for_selector(
                        "a[href*='/address/']", state="visible", timeout=10000
                    )
                except PlaywrightTimeoutError:
                    pass

                property_links = self.page.locator("a[href*='/address/']").all()

                if property_links:
                    property_url = property_links[0].get_attribute("href")
                    # Convert relative URL to absolute
                    if property_url and property_url.startswith("/"):
                        property_url = f"https://homes.co.nz{property_url}"

                    if property_url:
                        confidence = self._calculate_confidence(normalized_address, full_address)
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
        """Get the best matching property URL."""
        results = self.search_property(address)
        if results and results[0].confidence > 0.5:
            return results[0].url
        return None
