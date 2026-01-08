"""oneroof.co.nz site implementation."""

import re
from typing import List, Optional, Tuple

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from nz_house_prices.discovery.geocoder import geocode_address
from nz_house_prices.sites.base import BaseSite, SearchResult


class OneRoofSite(BaseSite):
    """Handler for oneroof.co.nz property searches."""

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
        self, property_links: List[Tuple[str, str]], target_address: str
    ) -> Tuple[Optional[str], str]:
        """Find the best matching property from autocomplete results."""
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()
        target_words = set(target_lower.split())
        first_word = target_lower.split()[0] if target_lower else ""

        candidates = []

        for url, text in property_links:
            if not url or not text:
                continue

            address_text = text.split("\n")[0].strip()
            if not address_text:
                continue

            score = 0
            result_unit = self._extract_unit_number(address_text)

            if target_unit and result_unit:
                if target_unit == result_unit:
                    score += 100
                else:
                    score -= 50
            elif target_unit and not result_unit:
                score -= 10

            address_lower = address_text.lower()
            address_words = set(address_lower.split())
            common_words = target_words & address_words
            score += len(common_words) * 10

            if first_word and address_lower.startswith(first_word):
                score += 50

            candidates.append((url, address_text, score))

        if not candidates:
            return None, ""

        street_matches = [c for c in candidates if c[1].lower().startswith(first_word)]

        if len(street_matches) > 1:
            geocode_result = self._geocode_best_match(
                target_address, street_matches, max_distance_km=5.0
            )
            if geocode_result:
                return geocode_result[0], geocode_result[1]

        best_url = None
        best_text = ""
        best_score = -1000

        for url, address_text, base_score in candidates:
            score = base_score
            location_score, _ = self._calculate_location_score(target_address, address_text)
            score += location_score

            if score > best_score:
                best_score = score
                best_url = url
                best_text = address_text

        return best_url, best_text

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
            self.page.goto(self.SEARCH_URL, wait_until="domcontentloaded", timeout=30000)

            search_input = self.page.locator(
                "input[type='search'], input[placeholder*='address' i]"
            ).first
            search_input.wait_for(state="visible", timeout=10000)
            search_input.click()

            variations = self._generate_search_variations(normalized_address)

            # Collect all unique candidates
            all_links: List[Tuple[str, str]] = []
            seen_urls = set()

            for query in variations:
                links = self._search_with_query(query)
                for url, text in links:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_links.append((url, text))

            if all_links:
                best_url, best_text = self._find_best_match(all_links, normalized_address)

                if best_url:
                    confidence = self._calculate_confidence(normalized_address, best_text)
                    results.append(
                        SearchResult(
                            address=best_text,
                            url=best_url,
                            confidence=confidence,
                            site=self.SITE_NAME,
                        )
                    )

        except Exception as e:
            print(f"Error searching oneroof.co.nz: {e}")

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def get_property_url(self, address: str) -> Optional[str]:
        """Get the best matching property URL."""
        results = self.search_property(address)
        if results and results[0].confidence > 0.5:
            return results[0].url
        return None
