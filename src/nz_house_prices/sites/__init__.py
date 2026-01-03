"""Site-specific implementations for NZ real estate websites."""

from nz_house_prices.sites.base import BaseSite, SearchResult
from nz_house_prices.sites.homes import HomesSite
from nz_house_prices.sites.oneroof import OneRoofSite
from nz_house_prices.sites.propertyvalue import PropertyValueSite
from nz_house_prices.sites.qv import QVSite
from nz_house_prices.sites.realestate import RealEstateSite

# Mapping of site domains to their handler classes
SITE_HANDLERS = {
    "homes.co.nz": HomesSite,
    "qv.co.nz": QVSite,
    "propertyvalue.co.nz": PropertyValueSite,
    "realestate.co.nz": RealEstateSite,
    "oneroof.co.nz": OneRoofSite,
}


def get_site_handler(site_domain: str) -> type:
    """Get the handler class for a site domain.

    Args:
        site_domain: The domain name (e.g., 'homes.co.nz')

    Returns:
        The site handler class

    Raises:
        ValueError: If site is not supported
    """
    if site_domain not in SITE_HANDLERS:
        raise ValueError(
            f"Unsupported site: {site_domain}. "
            f"Supported sites: {list(SITE_HANDLERS.keys())}"
        )
    return SITE_HANDLERS[site_domain]


__all__ = [
    "BaseSite",
    "SearchResult",
    "HomesSite",
    "QVSite",
    "PropertyValueSite",
    "RealEstateSite",
    "OneRoofSite",
    "SITE_HANDLERS",
    "get_site_handler",
]
