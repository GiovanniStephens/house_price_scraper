"""Base class for site-specific implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from playwright.sync_api import Page

from nz_house_prices.discovery.geocoder import geocode_address, geocode_batch


@dataclass
class SearchResult:
    """Result from a property search."""

    address: str
    url: str
    confidence: float  # 0.0 to 1.0 - how confident we are this is the right property
    site: str
    extra_info: Optional[dict] = None


class BaseSite(ABC):
    """Abstract base class for real estate site implementations."""

    # Class attributes to be overridden by subclasses
    SITE_NAME: str = ""
    SITE_DOMAIN: str = ""
    SEARCH_URL: str = ""

    def __init__(self, page: Optional[Page] = None):
        """Initialize the site handler.

        Args:
            page: Optional Playwright Page instance
        """
        self._page = page
        self._owns_page = False

    @property
    def page(self) -> Page:
        """Get or create Page instance."""
        if self._page is None:
            from nz_house_prices.core.driver import create_page

            self._page = create_page()
            self._owns_page = True
        return self._page

    def close(self) -> None:
        """Close the page if we own it."""
        if self._owns_page and self._page is not None:
            try:
                context = self._page.context
                self._page.close()
                context.close()
            except Exception:
                pass
            self._page = None
            self._owns_page = False

    def __enter__(self) -> "BaseSite":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    @abstractmethod
    def search_property(self, address: str) -> List[SearchResult]:
        """Search for a property by address.

        Args:
            address: The address to search for

        Returns:
            List of SearchResult objects, ordered by confidence (highest first)
        """
        pass

    @abstractmethod
    def get_property_url(self, address: str) -> Optional[str]:
        """Get the URL for a property page.

        This is a convenience method that returns the best match URL.

        Args:
            address: The address to search for

        Returns:
            URL string or None if not found
        """
        pass

    def normalize_address(self, address: str) -> str:
        """Normalize an address string for searching.

        Args:
            address: Raw address string

        Returns:
            Normalized address string
        """
        # Basic normalization - subclasses can override for site-specific needs
        normalized = address.strip()
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def _calculate_confidence(self, search_address: str, result_address: str) -> float:
        """Calculate confidence score for a search result.

        Args:
            search_address: The address we searched for
            result_address: The address returned in results

        Returns:
            Confidence score from 0.0 to 1.0
        """
        # Simple string similarity - can be improved
        search_lower = search_address.lower()
        result_lower = result_address.lower()

        # Exact match
        if search_lower == result_lower:
            return 1.0

        # Check if search terms are contained
        search_words = set(search_lower.split())
        result_words = set(result_lower.split())

        if not search_words:
            return 0.0

        # Calculate word overlap
        overlap = len(search_words & result_words)
        confidence = overlap / len(search_words)

        return min(confidence, 0.99)  # Cap at 0.99 for non-exact matches

    # NZ region/suburb mappings for city-aware pre-ranking
    _NZ_REGIONS = {
        "auckland": {"papakura", "manukau", "henderson", "mount eden", "ponsonby",
                     "remuera", "epsom", "grey lynn", "newmarket", "parnell",
                     "devonport", "takapuna", "albany", "botany", "howick"},
        "queenstown": {"queenstown", "lake hayes", "arrowtown", "frankton",
                       "kelvin heights", "jacks point", "wakatipu", "dalefield",
                       "lake hayes estate", "jack's point"},
        "wellington": {"wellington", "lower hutt", "upper hutt", "porirua",
                       "petone", "karori", "miramar", "kilbirnie"},
        "christchurch": {"christchurch", "riccarton", "papanui", "fendalton",
                         "merivale", "sumner", "lyttelton", "new brighton"},
        "hamilton": {"hamilton", "te rapa", "dinsdale", "hillcrest"},
        "dunedin": {"dunedin", "mosgiel", "port chalmers"},
    }

    def _pre_rank_candidates(
        self, candidates: List[str], target: str, top_n: int = 5
    ) -> List[str]:
        """Pre-rank candidates by keyword overlap and region matching.

        This reduces the number of expensive geocoding calls by:
        1. Scoring candidates by word overlap with target
        2. Penalizing candidates from different regions (Auckland vs Queenstown)

        Args:
            candidates: List of candidate address strings
            target: The target address to match against
            top_n: Maximum number of candidates to return

        Returns:
            List of top N candidates sorted by score
        """
        target_lower = target.lower()
        target_words = set(target_lower.replace(",", " ").split())

        # Detect target region
        target_region = None
        for region, suburbs in self._NZ_REGIONS.items():
            if region in target_lower or any(s in target_lower for s in suburbs):
                target_region = region
                break

        scored = []
        for candidate in candidates:
            candidate_lower = candidate.lower()
            candidate_words = set(candidate_lower.replace(",", " ").split())

            # Base score: word overlap
            score = len(target_words & candidate_words)

            # Penalty: candidate in different region
            if target_region:
                for other_region, suburbs in self._NZ_REGIONS.items():
                    if other_region != target_region:
                        if other_region in candidate_lower or any(
                            s in candidate_lower for s in suburbs
                        ):
                            score -= 10  # Heavy penalty for wrong region
                            break

            scored.append((candidate, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:top_n]]

    def _calculate_location_score(
        self,
        target_address: str,
        result_address: str,
        max_distance_km: float = 5.0,
    ) -> Tuple[int, bool]:
        """Calculate score based on geographic distance using geocoding.

        Args:
            target_address: The address we're searching for
            result_address: The candidate address to compare
            max_distance_km: Maximum distance to consider a valid match

        Returns:
            Tuple of (score, is_close_match):
            - score: +200 for very close (<0.5km), +100 for close (<2km),
                     +50 for nearby (<5km), -200 for far, 0 if geocoding fails
            - is_close_match: True if within max_distance_km
        """
        # Use pre-geocoded target if available (set by parallel.py)
        target_location = getattr(self, "_target_location", None)
        if not target_location:
            target_location = geocode_address(target_address)
        if not target_location:
            return 0, False

        result_location = geocode_address(result_address)
        if not result_location:
            return 0, False

        distance = target_location.distance_to(result_location)

        # Score based on distance
        if distance < 0.5:
            return 200, True
        elif distance < 2.0:
            return 100, True
        elif distance <= max_distance_km:
            return 50, True
        else:
            return -200, False

    def _geocode_best_match(
        self,
        target_address: str,
        candidates: List[Tuple[str, str, int]],
        max_distance_km: float = 2.0,
    ) -> Optional[Tuple[str, str, int, float]]:
        """Use geocoding to find the best matching candidate by distance.

        This is useful when multiple candidates have similar text-based scores
        but are in different geographic locations (e.g., same street name in
        different suburbs).

        Args:
            target_address: The address we're searching for
            candidates: List of (url, display_address, text_score) tuples
            max_distance_km: Maximum distance to consider a valid match

        Returns:
            Tuple of (url, display_address, text_score, distance_km) for best match,
            or None if geocoding fails or no candidates within max_distance
        """
        if not candidates:
            return None

        # Use pre-geocoded target if available (set by parallel.py)
        target_location = getattr(self, "_target_location", None)
        if not target_location:
            target_location = geocode_address(target_address)
        if not target_location:
            # Fall back to text-based scoring if geocoding fails
            return None

        best_match = None
        best_distance = float("inf")

        for url, display_address, text_score in candidates:
            # Geocode the candidate
            candidate_location = geocode_address(display_address)
            if candidate_location:
                distance = target_location.distance_to(candidate_location)

                # Only consider if within max distance
                if distance <= max_distance_km and distance < best_distance:
                    best_distance = distance
                    best_match = (url, display_address, text_score, distance)

        return best_match

    def _batch_calculate_location_scores(
        self,
        target_address: str,
        candidate_addresses: List[str],
        max_distance_km: float = 5.0,
    ) -> dict[str, Tuple[int, bool]]:
        """Calculate location scores for multiple candidates using batch geocoding.

        This method geocodes all addresses in parallel across multiple geocoding
        services, significantly improving throughput compared to sequential geocoding.

        Args:
            target_address: The address we're searching for
            candidate_addresses: List of candidate addresses to score
            max_distance_km: Maximum distance to consider a valid match

        Returns:
            Dictionary mapping each candidate address to (score, is_close_match)
            - score: +200 for very close (<0.5km), +100 for close (<2km),
                     +50 for nearby (<5km), -200 for far, 0 if geocoding fails
            - is_close_match: True if within max_distance_km
        """
        if not candidate_addresses:
            return {}

        # Use pre-geocoded target if available (set by parallel.py)
        target_location = getattr(self, "_target_location", None)
        if target_location:
            # Only geocode candidates (target already done)
            locations = geocode_batch(list(candidate_addresses))
        else:
            # Batch geocode all addresses (target + candidates)
            all_addresses = [target_address] + list(candidate_addresses)
            locations = geocode_batch(all_addresses)
            target_location = locations.get(target_address)

        if not target_location:
            # Return neutral scores if target can't be geocoded
            return {addr: (0, False) for addr in candidate_addresses}

        results = {}
        for addr in candidate_addresses:
            result_location = locations.get(addr)
            if not result_location:
                results[addr] = (0, False)
                continue

            distance = target_location.distance_to(result_location)

            # Score based on distance
            if distance < 0.5:
                results[addr] = (200, True)
            elif distance < 2.0:
                results[addr] = (100, True)
            elif distance <= max_distance_km:
                results[addr] = (50, True)
            else:
                results[addr] = (-200, False)

        return results
