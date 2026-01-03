"""URL caching for faster repeated lookups."""

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class CachedURL:
    """A cached URL entry."""

    url: str
    address: str
    site: str
    confidence: float
    cached_at: float  # Unix timestamp
    expires_at: float  # Unix timestamp


class URLCache:
    """Cache for resolved property URLs.

    Stores URL lookups to avoid repeated searches for the same address.
    Cache is persisted to disk for persistence across sessions.
    """

    DEFAULT_CACHE_DIR = Path.home() / ".cache" / "nz_house_prices"
    DEFAULT_CACHE_FILE = "url_cache.json"
    DEFAULT_TTL = 86400 * 30  # 30 days in seconds

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_file: Optional[str] = None,
        ttl: int = DEFAULT_TTL,
    ):
        """Initialize the URL cache.

        Args:
            cache_dir: Directory for cache files (default: ~/.cache/nz_house_prices)
            cache_file: Cache filename (default: url_cache.json)
            ttl: Time-to-live in seconds for cache entries (default: 30 days)
        """
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self.cache_file = cache_file or self.DEFAULT_CACHE_FILE
        self.ttl = ttl
        self._cache: Dict[str, CachedURL] = {}
        self._load_cache()

    @property
    def cache_path(self) -> Path:
        """Get the full path to the cache file."""
        return self.cache_dir / self.cache_file

    def _make_key(self, address: str, site: str) -> str:
        """Create a cache key from address and site.

        Args:
            address: The property address
            site: The site domain

        Returns:
            Cache key string
        """
        # Normalize the address for consistent keys
        normalized = address.lower().strip()
        normalized = " ".join(normalized.split())
        return f"{normalized}|{site}"

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if not self.cache_path.exists():
            return

        try:
            with open(self.cache_path, "r") as f:
                data = json.load(f)

            now = time.time()
            for key, entry in data.items():
                cached = CachedURL(**entry)
                # Only load non-expired entries
                if cached.expires_at > now:
                    self._cache[key] = cached

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Failed to load URL cache: {e}")
            self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            data = {key: asdict(entry) for key, entry in self._cache.items()}

            with open(self.cache_path, "w") as f:
                json.dump(data, f, indent=2)

        except (OSError, IOError) as e:
            print(f"Warning: Failed to save URL cache: {e}")

    def get(self, address: str, site: str) -> Optional[str]:
        """Get a cached URL for an address and site.

        Args:
            address: The property address
            site: The site domain

        Returns:
            Cached URL or None if not found/expired
        """
        key = self._make_key(address, site)
        entry = self._cache.get(key)

        if entry is None:
            return None

        # Check if expired
        if entry.expires_at < time.time():
            del self._cache[key]
            return None

        return entry.url

    def set(
        self,
        address: str,
        site: str,
        url: str,
        confidence: float = 1.0,
    ) -> None:
        """Cache a URL for an address and site.

        Args:
            address: The property address
            site: The site domain
            url: The resolved URL
            confidence: Confidence score for the match
        """
        key = self._make_key(address, site)
        now = time.time()

        self._cache[key] = CachedURL(
            url=url,
            address=address,
            site=site,
            confidence=confidence,
            cached_at=now,
            expires_at=now + self.ttl,
        )

        self._save_cache()

    def get_all(self, address: str) -> Dict[str, str]:
        """Get all cached URLs for an address across all sites.

        Args:
            address: The property address

        Returns:
            Dict mapping site names to URLs
        """
        results = {}
        for site in ["homes.co.nz", "qv.co.nz", "propertyvalue.co.nz", "realestate.co.nz", "oneroof.co.nz"]:
            url = self.get(address, site)
            if url:
                results[site] = url
        return results

    def invalidate(self, address: str, site: Optional[str] = None) -> None:
        """Invalidate cached entries.

        Args:
            address: The property address
            site: Optional site to invalidate (None = all sites)
        """
        if site:
            key = self._make_key(address, site)
            if key in self._cache:
                del self._cache[key]
        else:
            # Invalidate all sites for this address
            keys_to_remove = [
                k for k in self._cache.keys()
                if k.startswith(address.lower().strip())
            ]
            for key in keys_to_remove:
                del self._cache[key]

        self._save_cache()

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache = {}
        if self.cache_path.exists():
            self.cache_path.unlink()

    def stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        now = time.time()
        valid_entries = sum(1 for e in self._cache.values() if e.expires_at > now)
        expired_entries = len(self._cache) - valid_entries

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
        }
