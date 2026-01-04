"""Geocoding utilities using Nominatim (OpenStreetMap)."""

import functools
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Nominatim requires a user agent identifying the application
USER_AGENT = "nz-house-prices/1.0 (https://github.com/GiovanniStephens/house_price_scraper)"

# Rate limiting: Nominatim allows max 1 request per second
MIN_REQUEST_INTERVAL = 1.1  # seconds

# Cache directory
CACHE_DIR = Path.home() / ".cache" / "nz-house-prices" / "geocode"


@dataclass
class GeocodedLocation:
    """Geocoded location with coordinates and metadata."""

    latitude: float
    longitude: float
    display_name: str
    address_type: str = ""
    importance: float = 0.0

    def distance_to(self, other: "GeocodedLocation") -> float:
        """Calculate distance to another location in kilometers using Haversine formula.

        Args:
            other: Another GeocodedLocation

        Returns:
            Distance in kilometers
        """
        return haversine_distance(
            self.latitude, self.longitude, other.latitude, other.longitude
        )


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1: First point coordinates in degrees
        lat2, lon2: Second point coordinates in degrees

    Returns:
        Distance in kilometers
    """
    # Earth's radius in kilometers
    R = 6371.0

    # Convert to radians
    lat1_r, lon1_r = radians(lat1), radians(lon1)
    lat2_r, lon2_r = radians(lat2), radians(lon2)

    # Differences
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    # Haversine formula
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c


class NominatimGeocoder:
    """Geocoder using OpenStreetMap's Nominatim service."""

    BASE_URL = "https://nominatim.openstreetmap.org/search"

    def __init__(self, use_cache: bool = True):
        """Initialize the geocoder.

        Args:
            use_cache: Whether to cache results to disk
        """
        self.use_cache = use_cache
        self._last_request_time: float = 0

        if use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, query: str) -> Path:
        """Get the cache file path for a query."""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()
        return CACHE_DIR / f"{query_hash}.json"

    def _load_from_cache(self, query: str) -> Optional[dict]:
        """Load cached result for a query."""
        if not self.use_cache:
            return None

        cache_path = self._get_cache_path(query)
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def _save_to_cache(self, query: str, result: dict) -> None:
        """Save result to cache."""
        if not self.use_cache:
            return

        cache_path = self._get_cache_path(query)
        try:
            with open(cache_path, "w") as f:
                json.dump(result, f)
        except IOError:
            pass

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def geocode(
        self, address: str, country: str = "nz"
    ) -> Optional[GeocodedLocation]:
        """Geocode an address to coordinates.

        Args:
            address: Address string to geocode
            country: Country code to limit results (default: "nz" for New Zealand)

        Returns:
            GeocodedLocation if found, None otherwise
        """
        if not address:
            return None

        # Check cache first
        cache_key = f"{address}|{country}"
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            if cached.get("results"):
                result = cached["results"][0]
                return GeocodedLocation(
                    latitude=float(result["lat"]),
                    longitude=float(result["lon"]),
                    display_name=result.get("display_name", ""),
                    address_type=result.get("type", ""),
                    importance=float(result.get("importance", 0)),
                )
            return None

        # Rate limit before making request
        self._rate_limit()

        try:
            params = {
                "q": address,
                "format": "json",
                "countrycodes": country,
                "limit": 1,
                "addressdetails": 1,
            }

            response = requests.get(
                self.BASE_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            response.raise_for_status()

            results = response.json()

            # Cache the results
            self._save_to_cache(cache_key, {"results": results})

            if results:
                result = results[0]
                return GeocodedLocation(
                    latitude=float(result["lat"]),
                    longitude=float(result["lon"]),
                    display_name=result.get("display_name", ""),
                    address_type=result.get("type", ""),
                    importance=float(result.get("importance", 0)),
                )

            return None

        except requests.RequestException as e:
            logger.warning(f"Geocoding failed for '{address}': {e}")
            return None

    def geocode_and_compare(
        self,
        target_address: str,
        candidate_addresses: list[str],
        max_distance_km: float = 5.0,
    ) -> list[Tuple[str, float, Optional[GeocodedLocation]]]:
        """Geocode a target and candidates, returning distances.

        Args:
            target_address: The address we're looking for
            candidate_addresses: List of candidate addresses to compare
            max_distance_km: Maximum distance to consider a valid match

        Returns:
            List of (candidate_address, distance_km, location) tuples,
            sorted by distance. Distance is float('inf') if geocoding failed.
        """
        # Geocode target
        target_location = self.geocode(target_address)
        if not target_location:
            logger.warning(f"Could not geocode target address: {target_address}")
            return [(addr, float("inf"), None) for addr in candidate_addresses]

        # Geocode and compare each candidate
        results = []
        for candidate in candidate_addresses:
            candidate_location = self.geocode(candidate)
            if candidate_location:
                distance = target_location.distance_to(candidate_location)
                results.append((candidate, distance, candidate_location))
            else:
                results.append((candidate, float("inf"), None))

        # Sort by distance
        results.sort(key=lambda x: x[1])

        return results


# Module-level geocoder instance for convenience
_geocoder: Optional[NominatimGeocoder] = None


def get_geocoder() -> NominatimGeocoder:
    """Get or create the module-level geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = NominatimGeocoder()
    return _geocoder


def normalize_for_geocoding(address: str) -> str:
    """Normalize an address for better geocoding results.

    Args:
        address: Raw address string

    Returns:
        Cleaned address suitable for geocoding
    """
    if not address:
        return ""

    # Remove common suffixes that confuse geocoders
    # e.g., "Auckland - City" -> "Auckland"
    address = re.sub(r"\s*-\s*(City|Central|North|South|East|West|Waitakere|Papakura|Manukau)\b", "", address, flags=re.IGNORECASE)

    # Handle suburb combinations with "/"
    # e.g., "Ponsonby Central" -> skip the suburb entirely
    parts = address.split(",")
    cleaned_parts = []
    for i, part in enumerate(parts):
        part = part.strip()
        if "/" in part and i > 0:  # Skip complex suburb names (not street address)
            # This is likely a suburb/area combo - skip it and rely on city
            continue
        cleaned_parts.append(part)

    # Known problematic suburb mappings that Nominatim doesn't recognize
    # Map them to recognizable region names
    SUBURB_MAPPINGS = {
        "wakatipu basin": "Queenstown",
        "dalefield": "Queenstown",
        "arrowtown": "Queenstown",
        "frankton": "Queenstown",
        "kelvin heights": "Queenstown",
        "jack's point": "Queenstown",
        "jacks point": "Queenstown",
        "lake hayes": "Queenstown",
        "lake hayes estate": "Queenstown",
    }

    # Apply suburb mappings
    address_lower = ", ".join(cleaned_parts).lower()
    for suburb, region in SUBURB_MAPPINGS.items():
        if suburb in address_lower:
            # Replace the suburb with the region if the region isn't already there
            if region.lower() not in address_lower:
                cleaned_parts.append(region)
            break

    address = ", ".join(cleaned_parts)

    # Ensure New Zealand is in the address for better results
    if "new zealand" not in address.lower() and "nz" not in address.lower():
        address = address + ", New Zealand"

    return address


@functools.lru_cache(maxsize=1000)
def geocode_address(address: str) -> Optional[GeocodedLocation]:
    """Convenience function to geocode an address.

    Automatically normalizes the address for better results.
    Results are cached in memory (LRU cache) for fast repeated lookups.

    Args:
        address: Address string to geocode

    Returns:
        GeocodedLocation if found, None otherwise
    """
    normalized = normalize_for_geocoding(address)
    return get_geocoder().geocode(normalized)


def distance_between(address1: str, address2: str) -> Optional[float]:
    """Calculate distance between two addresses in kilometers.

    Args:
        address1: First address
        address2: Second address

    Returns:
        Distance in kilometers, or None if either address couldn't be geocoded
    """
    geocoder = get_geocoder()
    loc1 = geocoder.geocode(address1)
    loc2 = geocoder.geocode(address2)

    if loc1 and loc2:
        return loc1.distance_to(loc2)
    return None
