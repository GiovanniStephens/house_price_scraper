"""oneroof.co.nz site implementation."""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from nz_house_prices.discovery.geocoder import geocode_address
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

        Uses geocoding to accurately distinguish between properties with the
        same street address in different locations. Falls back to text-based
        matching if geocoding fails.

        Args:
            property_links: List of (url, text) tuples from autocomplete
            target_address: The address we're looking for

        Returns:
            Tuple of (best_url, best_address_text)
        """
        target_unit = self._extract_unit_number(target_address)
        target_lower = target_address.lower()
        target_words = set(target_lower.split())

        # Extract street number for filtering candidates
        first_word = target_lower.split()[0] if target_lower else ""

        # Collect all candidates with their scores
        candidates = []

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
            if first_word and address_lower.startswith(first_word):
                score += 50

            candidates.append((url, address_text, score))

        if not candidates:
            return None, ""

        # Filter to candidates that start with the same street number
        street_matches = [c for c in candidates if c[1].lower().startswith(first_word)]

        # If multiple candidates match the street number, use geocoding
        if len(street_matches) > 1:
            geocode_result = self._geocode_best_match(
                target_address,
                street_matches,
                max_distance_km=5.0,
            )
            if geocode_result:
                return geocode_result[0], geocode_result[1]

        # Fall back to text-based scoring with geocoding-based location penalties
        best_url = None
        best_text = ""
        best_score = -1000

        for url, address_text, base_score in candidates:
            score = base_score

            # Add geocoding-based location scoring
            location_score, _ = self._calculate_location_score(
                target_address, address_text
            )
            score += location_score

            if score > best_score:
                best_score = score
                best_url = url
                best_text = address_text

        return best_url, best_text

    def _get_region_from_geocode(self, address: str) -> Optional[str]:
        """Get the major region/city from geocoding an address.

        Args:
            address: Address to geocode

        Returns:
            Region name like "Auckland", "Auckland", etc. or None
        """
        location = geocode_address(address)
        if not location:
            return None

        # Extract region from the display name
        # Format: "123, Example Street, Ponsonby, Auckland, New Zealand"
        display = location.display_name.lower()

        # Check for major NZ cities/regions
        REGIONS = [
            "queenstown", "auckland", "wellington", "christchurch",
            "hamilton", "tauranga", "dunedin", "nelson", "napier",
            "rotorua", "invercargill", "palmerston north", "new plymouth",
        ]

        for region in REGIONS:
            if region in display:
                return region.title()

        return None

    def _generate_search_variations(self, address: str) -> List[str]:
        """Generate multiple search query variations for an address.

        Different variations help when suburb names confuse the autocomplete.

        Args:
            address: The normalized address

        Returns:
            List of search query variations to try
        """
        variations = [address]  # Start with original

        parts = [p.strip() for p in address.split(",")]
        street_part = parts[0] if parts else address

        # Get region from geocoding
        region = self._get_region_from_geocode(address)

        if region:
            # Variation: street + region only (skip confusing suburb names)
            simplified = f"{street_part} {region}"
            if simplified.lower() != address.lower():
                variations.append(simplified)

            # Variation: full address + region appended
            if region.lower() not in address.lower():
                variations.append(f"{address}, {region}")

        # Variation: progressively shorter queries
        for i in range(len(parts) - 1, 0, -1):
            shorter = ", ".join(parts[:i])
            if shorter not in variations:
                variations.append(shorter)

        return variations

    def _search_with_query(
        self, search_input, query: str
    ) -> List[Tuple[str, str]]:
        """Execute a search query and return property links.

        Args:
            search_input: The search input element
            query: Search query string

        Returns:
            List of (url, text) tuples from autocomplete
        """
        search_input.clear()
        search_input.send_keys(query)

        # Wait for property links to appear (max 5s, usually faster)
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "a[href*='/property/']")
                )
            )
        except TimeoutException:
            # No results found for this query
            return []

        link_elements = self.driver.find_elements(
            By.CSS_SELECTOR, "a[href*='/property/']"
        )

        property_links = []
        for link in link_elements:
            try:
                href = link.get_attribute("href")
                text = link.text.strip()
                if href and "/property/" in href and text:
                    property_links.append((href, text))
            except StaleElementReferenceException:
                # Element was updated by the page, skip it
                continue

        return property_links

    def _find_best_across_variations(
        self,
        search_input,
        variations: List[str],
        target_address: str,
    ) -> Tuple[Optional[str], str]:
        """Search multiple variations and find the best match by geocoding.

        Searches are done sequentially (browser constraint), but geocoding
        of all results is done in parallel for speed.

        Args:
            search_input: The search input element
            variations: List of search query variations
            target_address: Original target address for geocoding comparison

        Returns:
            Tuple of (best_url, best_address_text)
        """
        # Geocode the target address once (cached via lru_cache)
        target_location = geocode_address(target_address)

        # Step 1: Collect all unique candidates from all variations
        # Browser searches must be sequential (single driver)
        candidates: List[Tuple[str, str]] = []  # (url, address_text)
        seen_urls: Set[str] = set()

        for query in variations:
            property_links = self._search_with_query(search_input, query)

            for url, text in property_links:
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Extract address text
                address_text = text.split("\n")[0].strip()
                address_text = address_text.split("|")[0].strip()

                if address_text:
                    candidates.append((url, address_text))

        if not candidates:
            return None, ""

        # Step 2: Batch geocode all candidates in parallel
        # This is much faster than sequential geocoding (uses lru_cache + parallel)
        results: Dict[str, Tuple[str, float]] = {}  # url -> (text, distance)

        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all geocoding tasks
            future_to_candidate = {
                executor.submit(geocode_address, addr): (url, addr)
                for url, addr in candidates
            }

            # Collect results as they complete
            for future in as_completed(future_to_candidate):
                url, address_text = future_to_candidate[future]
                try:
                    result_location = future.result()
                    distance = float("inf")
                    if target_location and result_location:
                        distance = target_location.distance_to(result_location)
                    results[url] = (address_text, distance)

                    # Early exit if we found a very close match (<0.5km)
                    if distance < 0.5:
                        # Cancel remaining futures and return immediately
                        for f in future_to_candidate:
                            f.cancel()
                        return url, address_text
                except Exception:
                    # If geocoding fails, use infinite distance
                    results[url] = (address_text, float("inf"))

        # Return the closest match
        if results:
            sorted_results = sorted(results.items(), key=lambda x: x[1][1])
            best_url, (best_text, _) = sorted_results[0]
            return best_url, best_text

        return None, ""

    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address on oneroof.co.nz.

        Uses multiple search query variations to find the best match.
        Searches are ranked by geographic distance to the target address
        using geocoding, ensuring we find the correct property even when
        the same street address exists in multiple cities.

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
            time.sleep(2)  # Reduced from 3s

            wait = WebDriverWait(self.driver, 10)

            # Find the search input
            search_input = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "input[type='search'], input[placeholder*='address' i]")
                )
            )
            search_input.click()

            # Generate search variations and find best match across all
            variations = self._generate_search_variations(normalized_address)
            best_url, best_text = self._find_best_across_variations(
                search_input, variations, normalized_address
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
