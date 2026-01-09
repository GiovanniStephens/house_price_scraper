"""oneroof.co.nz site implementation."""

import re
from math import atan2, cos, radians, sin, sqrt
from typing import List, Optional, Tuple

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from nz_house_prices.discovery.geocoder import geocode_address, geocode_batch
from nz_house_prices.sites.base import BaseSite, SearchResult


class OneRoofSite(BaseSite):
    """Handler for oneroof.co.nz property searches."""

    SITE_NAME = "oneroof.co.nz"
    SITE_DOMAIN = "oneroof.co.nz"
    SEARCH_URL = "https://www.oneroof.co.nz"

    def _calculate_distance_km(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points using Haversine formula."""
        r = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return r * 2 * atan2(sqrt(a), sqrt(1 - a))

    def _find_best_match(
        self, property_links: List[Tuple[str, str]], target_address: str
    ) -> Tuple[Optional[str], str]:
        """Find the best matching property using geographic distance.

        Uses a two-step process for efficiency:
        1. Pre-rank candidates by keyword overlap (fast, no API calls)
        2. Batch geocode top candidates and target address (parallel API calls)
        3. Return the geographically closest match

        This handles suburb name variations automatically (e.g., 'Lake Hayes Estate'
        vs 'Dalefield/Wakatipu Basin' for the same location).
        """
        # Extract and clean addresses from property links
        address_map: dict[str, Tuple[str, str]] = {}  # address -> (url, original_text)
        for url, text in property_links:
            if not url or not text:
                continue
            address_text = text.split("\n")[0].strip()
            # Remove trailing "Estimate" suffix that oneroof adds
            address_text = re.sub(r"Estimate$", "", address_text).strip()
            if address_text:
                address_map[address_text] = (url, text)

        if not address_map:
            return None, ""

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
            return None, ""

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
                url, _ = address_map[addr]
                candidates.append((url, addr, distance))

        if not candidates:
            return None, ""

        # Sort by distance (closest first)
        candidates.sort(key=lambda x: x[2])

        # Return closest result if within 5km (generous for address variations)
        if candidates[0][2] < 5.0:
            return candidates[0][0], candidates[0][1]

        return None, ""

    def _get_region_from_geocode(self, address: str) -> Optional[str]:
        """Get the major region/city from geocoding an address."""
        location = geocode_address(address)
        if not location:
            return None

        display = location.display_name.lower()
        regions = [
            "queenstown",
            "auckland",
            "wellington",
            "christchurch",
            "hamilton",
            "tauranga",
            "dunedin",
            "nelson",
            "napier",
            "rotorua",
            "invercargill",
            "palmerston north",
            "new plymouth",
        ]

        for region in regions:
            if region in display:
                return region.title()
        return None

    def _generate_search_variations(self, address: str) -> List[str]:
        """Generate multiple search query variations for an address."""
        variations = [address]
        parts = [p.strip() for p in address.split(",")]
        street_part = parts[0] if parts else address

        region = self._get_region_from_geocode(address)

        if region:
            simplified = f"{street_part} {region}"
            if simplified.lower() != address.lower():
                variations.append(simplified)
            if region.lower() not in address.lower():
                variations.append(f"{address}, {region}")

        for i in range(len(parts) - 1, 0, -1):
            shorter = ", ".join(parts[:i])
            if shorter not in variations:
                variations.append(shorter)

        return variations

    def _search_with_query(self, query: str) -> List[Tuple[str, str]]:
        """Execute a search query and return property links."""
        search_input = self.page.locator(
            "input[type='search'], input[placeholder*='address' i]"
        ).first
        search_input.fill("")
        search_input.fill(query)

        try:
            self.page.wait_for_selector("a[href*='/property/']", state="visible", timeout=5000)
        except PlaywrightTimeoutError:
            return []

        link_elements = self.page.locator("a[href*='/property/']").all()

        property_links = []
        for link in link_elements:
            try:
                href = link.get_attribute("href")
                # Convert relative URL to absolute
                if href and href.startswith("/"):
                    href = f"https://www.oneroof.co.nz{href}"
                text = link.text_content() or ""
                text = text.strip()
                if href and "/property/" in href and text:
                    property_links.append((href, text))
            except Exception:
                continue

        return property_links

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on oneroof.co.nz."""
        results = []
        normalized_address = self.normalize_address(address)

        try:
            self.page.goto(self.SEARCH_URL, wait_until="domcontentloaded", timeout=15000)

            search_input = self.page.locator(
                "input[type='search'], input[placeholder*='address' i]"
            ).first
            search_input.wait_for(state="visible", timeout=10000)
            search_input.click()

            # Try original address first
            links = self._search_with_query(normalized_address)
            if links:
                best_url, best_text = self._find_best_match(links, normalized_address)
                if best_url:
                    # Geographic match found (within 5km) - trust it and return immediately
                    # Don't fall back to variations - geographic matching is more reliable
                    # than text confidence for suburb name variations
                    confidence = self._calculate_confidence(normalized_address, best_text)
                    return [
                        SearchResult(
                            address=best_text,
                            url=best_url,
                            confidence=max(confidence, 0.8),  # Boost since geo-matched
                            site=self.SITE_NAME,
                        )
                    ]

            # Only try variations if first search returned NO results
            variations = self._generate_search_variations(normalized_address)

            for query in variations[1:]:  # Skip first (already tried)
                new_links = self._search_with_query(query)
                if new_links:
                    best_url, best_text = self._find_best_match(new_links, normalized_address)
                    if best_url:
                        confidence = self._calculate_confidence(normalized_address, best_text)
                        return [
                            SearchResult(
                                address=best_text,
                                url=best_url,
                                confidence=max(confidence, 0.8),
                                site=self.SITE_NAME,
                            )
                        ]

        except Exception as e:
            print(f"Error searching oneroof.co.nz: {e}")

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def get_property_url(self, address: str) -> Optional[str]:
        """Get the best matching property URL."""
        results = self.search_property(address)
        if results and results[0].confidence > 0.5:
            return results[0].url
        return None
