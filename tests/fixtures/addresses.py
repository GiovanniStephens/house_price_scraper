"""Test address constants for nz-house-prices tests.

These addresses are used across integration, live, and performance tests.
The primary address should be a stable property that exists on all sites.
"""

# Primary test address - Christchurch coastal property
PRIMARY_ADDRESS = "66 Pacific Road, North New Brighton, Christchurch"

# Expected price range for primary address (Christchurch suburban)
# Adjust as needed based on actual property values
PRIMARY_ADDRESS_PRICE_RANGE = (300_000, 1_200_000)

# All supported sites
ALL_SITES = [
    "homes.co.nz",
    "qv.co.nz",
    "propertyvalue.co.nz",
    "realestate.co.nz",
    "oneroof.co.nz",
]

# Diverse test addresses for different scenarios
DIVERSE_ADDRESSES = {
    "christchurch_coastal": "66 Pacific Road, North New Brighton, Christchurch",
    "christchurch_central": "227 Worcester Street, City Centre, Christchurch",
    "christchurch_unit": "2/677 Worcester Street, Linwood, Christchurch",
    "auckland_urban": "10 Queen Street, Auckland CBD",
    "wellington_central": "111 The Terrace, Wellington",
}

# Unit/apartment addresses for testing unit number extraction
UNIT_ADDRESSES = {
    "slash_style": "2/677 Worcester Street, Linwood, Christchurch",
    "flat_style": "3/14 Example Street, Grey Lynn, Auckland",
    "unit_prefix": "Unit 5, 100 Main Road, Ponsonby, Auckland",
    "apartment": "Apt 12, 50 Queen Street, Auckland CBD",
}

# Known property URLs for selector validation tests
# These are discovered dynamically during tests
SAMPLE_PROPERTY_URLS = {
    # URLs will be populated as tests run
}
