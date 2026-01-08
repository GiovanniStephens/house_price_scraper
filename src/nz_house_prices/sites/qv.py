"""qv.co.nz site implementation."""

import re
from typing import List, Optional, Tuple

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from nz_house_prices.sites.base import BaseSite, SearchResult


class QVSite(BaseSite):
    """Handler for qv.co.nz property searches."""

    SITE_NAME = "qv.co.nz"
    SITE_DOMAIN = "qv.co.nz"
    SEARCH_URL = "https://www.qv.co.nz"

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
                item_text = item.text_content() or ""
                item_text = item_text.strip()
                if not item_text:
                    continue

                score = 0
                result_unit = self._extract_unit_number(item_text)

                if target_unit and result_unit:
                    if target_unit == result_unit:
                        score += 100
                    else:
                        score -= 50
                elif target_unit and not result_unit:
                    score -= 10

                item_lower = item_text.lower()
                if any(word in item_lower for word in target_lower.split()[:3]):
                    score += 20

                if score > best_score:
                    best_score = score
                    best_match = item
                    best_text = item_text

            except Exception:
                continue

        # Validate best match with geocoding (single call, not per-candidate)
        if best_match and best_text:
            location_score, is_close = self._calculate_location_score(
                target_address, best_text, max_distance_km=5.0
            )
            # Reject if the match is geographically too far or geocoding failed
            if not is_close:
                return None, ""

        return best_match, best_text

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on qv.co.nz."""
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

            # Find the search input - try multiple selectors
            search_selectors = [
                "[data-cy='address-search']",
                "input.c-address_search__field",
                "input[placeholder*='address' i]",
                "input[placeholder*='search' i]",
                "input[type='search']",
                "#address-search",
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
                print("qv.co.nz: Could not find search input")
                return []

            search_input.click()
            search_input.fill(normalized_address)

            # Trigger autocomplete by pressing a key
            search_input.press("Space")
            search_input.press("Backspace")

            # Small delay to let autocomplete populate
            self.page.wait_for_timeout(2000)

            # Wait for autocomplete dropdown - try multiple selectors
            autocomplete_selectors = [
                "[data-cy='display-search-result']",
                ".c-address_search__results",
                "[role='listbox']",
                ".autocomplete-results",
                "ul[class*='search']",
            ]

            autocomplete_found = False
            for selector in autocomplete_selectors:
                try:
                    self.page.wait_for_selector(selector, state="visible", timeout=3000)
                    autocomplete_found = True
                    break
                except PlaywrightTimeoutError:
                    continue

            if not autocomplete_found:
                print("qv.co.nz: No autocomplete dropdown found")

            # Try multiple result item selectors
            result_selectors = [
                ".c-address_search__result_item",
                "[data-cy='display-search-result'] > *",
                "[role='option']",
                ".search-result-item",
            ]

            result_items = []
            for selector in result_selectors:
                items = self.page.locator(selector).all()
                if items:
                    result_items = items
                    break

            if result_items:
                best_item, item_text = self._find_best_matching_result(
                    result_items, normalized_address
                )

                if best_item:
                    current_url_before = self.page.url
                    best_item.click()

                    # Wait for navigation
                    try:
                        self.page.wait_for_url(
                            lambda url: url != current_url_before, timeout=5000
                        )
                    except PlaywrightTimeoutError:
                        pass

                    current_url = self.page.url
                    if "/property" in current_url:
                        confidence = self._calculate_confidence(normalized_address, item_text)
                        results.append(
                            SearchResult(
                                address=item_text or normalized_address,
                                url=current_url,
                                confidence=confidence,
                                site=self.SITE_NAME,
                            )
                        )

            # If no autocomplete results, try the Go button
            if not results:
                try:
                    go_button = self.page.locator(".c-address_search__button").first
                    if go_button.is_visible() and go_button.is_enabled():
                        current_url_before = self.page.url
                        go_button.click()

                        try:
                            self.page.wait_for_url(
                                lambda url: url != current_url_before, timeout=5000
                            )
                        except PlaywrightTimeoutError:
                            pass

                        current_url = self.page.url
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
        """Get the best matching property URL."""
        results = self.search_property(address)
        if results and results[0].confidence > 0.5:
            return results[0].url
        return None
