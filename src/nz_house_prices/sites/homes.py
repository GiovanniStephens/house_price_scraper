"""homes.co.nz site implementation."""

from math import atan2, cos, radians, sin, sqrt
from typing import List, Optional, Tuple

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from nz_house_prices.discovery.geocoder import geocode_batch
from nz_house_prices.sites.base import BaseSite, SearchResult


class HomesSite(BaseSite):
    """Handler for homes.co.nz property searches."""

    SITE_NAME = "homes.co.nz"
    SITE_DOMAIN = "homes.co.nz"
    SEARCH_URL = "https://homes.co.nz"

    def _calculate_distance_km(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points using Haversine formula."""
        r = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return r * 2 * atan2(sqrt(a), sqrt(1 - a))

    def _find_best_matching_result(
        self, target_address: str
    ) -> Tuple[Optional[int], str, str]:
        """Find the best matching result using geographic distance.

        Uses a two-step process for efficiency:
        1. Pre-rank candidates by keyword overlap (fast, no API calls)
        2. Batch geocode top candidates and target address (parallel API calls)
        3. Return the geographically closest match

        This handles suburb name variations automatically (e.g., 'Lake Hayes Estate'
        vs 'Dalefield/Wakatipu Basin' for the same location).

        Returns:
            Tuple of (index, street, suburb) for best match, or (None, "", "") if no match.
        """
        # Use JavaScript to get all results at once (much faster than iterating locators)
        results = self.page.evaluate('''() => {
            const items = document.querySelectorAll("[class*='addressResult']:not([class*='addressResults'])");
            return Array.from(items).map((item, index) => {
                const street = item.querySelector("[class*='addressResultStreet']");
                const suburb = item.querySelector("[class*='addressResultSuburb']");
                return {
                    index: index,
                    street: street ? street.textContent.trim() : '',
                    suburb: suburb ? suburb.textContent.trim() : ''
                };
            });
        }''')

        if not results:
            return None, "", ""

        # Build address map: full_address -> (index, street, suburb)
        address_map: dict[str, Tuple[int, str, str]] = {}
        for item in results:
            street_text = item.get("street", "")
            suburb_text = item.get("suburb", "")
            index = item.get("index")
            if street_text:
                full_address = f"{street_text}, {suburb_text}".strip(", ")
                address_map[full_address] = (index, street_text, suburb_text)

        if not address_map:
            return None, "", ""

        # Pre-rank candidates by keyword overlap and region (top 3)
        all_addresses = list(address_map.keys())
        top_addresses = self._pre_rank_candidates(all_addresses, target_address, top_n=3)

        # Use pre-geocoded target if available (set by parallel.py), otherwise geocode
        target_location = getattr(self, "_target_location", None)
        if target_location:
            # Only geocode candidates (target already done)
            locations = geocode_batch(top_addresses)
        else:
            # Fallback: geocode target + candidates together
            addresses_to_geocode = [target_address] + top_addresses
            locations = geocode_batch(addresses_to_geocode)
            target_location = locations.get(target_address)

        if not target_location:
            return None, "", ""

        # Find closest candidate by geographic distance
        candidates = []
        for addr in top_addresses:
            loc = locations.get(addr)
            if loc:
                distance = self._calculate_distance_km(
                    target_location.latitude,
                    target_location.longitude,
                    loc.latitude,
                    loc.longitude,
                )
                index, street, suburb = address_map[addr]
                candidates.append((index, street, suburb, distance))

        if not candidates:
            return None, "", ""

        # Sort by distance (closest first)
        candidates.sort(key=lambda x: x[3])

        # Return closest result if within 5km (generous for address variations)
        if candidates[0][3] < 5.0:
            return candidates[0][0], candidates[0][1], candidates[0][2]

        return None, "", ""

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on homes.co.nz."""
        results = []
        normalized_address = self.normalize_address(address)

        try:
            self.page.goto(self.SEARCH_URL, wait_until="domcontentloaded", timeout=15000)

            # Wait for the main search input to appear
            try:
                self.page.wait_for_selector("#autocomplete-search", state="visible", timeout=10000)
                search_input = self.page.locator("#autocomplete-search").first
            except PlaywrightTimeoutError:
                # Fallback to other selectors
                search_input = None
                for selector in ["input[placeholder*='address' i]", "input[type='search']"]:
                    try:
                        locator = self.page.locator(selector).first
                        locator.wait_for(state="visible", timeout=2000)
                        search_input = locator
                        break
                    except PlaywrightTimeoutError:
                        continue

            if search_input is None:
                print("homes.co.nz: Could not find search input")
                return []

            search_input.fill(normalized_address)

            # Wait for autocomplete dropdown
            try:
                self.page.wait_for_selector(
                    "[class*='addressResults']", state="visible", timeout=5000
                )
            except PlaywrightTimeoutError:
                return []

            # Find best matching result using JS evaluation and geocoding
            best_index, street, suburb = self._find_best_matching_result(normalized_address)

            if best_index is None:
                return []

            full_address = f"{street}, {suburb}".strip(", ")

            # Click the best result by index
            result_items = self.page.locator(
                "[class*='addressResult']:not([class*='addressResults'])"
            ).all()
            if best_index < len(result_items):
                result_items[best_index].click()

                # Wait for property links on map page
                try:
                    self.page.wait_for_selector(
                        "a[href*='/address/']", state="visible", timeout=8000
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
