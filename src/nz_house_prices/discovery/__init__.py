"""URL discovery from addresses."""

from nz_house_prices.discovery.address import (
    ParsedAddress,
    normalize_address,
    parse_address,
)
from nz_house_prices.discovery.cache import CachedURL, URLCache
from nz_house_prices.discovery.resolver import (
    PropertyResolver,
    ResolvedProperty,
    resolve_property_urls,
)

__all__ = [
    # Address parsing
    "ParsedAddress",
    "parse_address",
    "normalize_address",
    # Caching
    "URLCache",
    "CachedURL",
    # Resolution
    "PropertyResolver",
    "ResolvedProperty",
    "resolve_property_urls",
]
