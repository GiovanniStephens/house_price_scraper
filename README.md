# NZ House Prices

A Python package to scrape house price estimates from New Zealand real estate websites.

## Installation

```bash
pip install nz-house-prices
```

## Supported Sites

- homes.co.nz
- qv.co.nz
- propertyvalue.co.nz
- realestate.co.nz
- oneroof.co.nz

## Quick Start

### Command Line

```bash
# Search by address
nz-house-prices "123 Example Street, Ponsonby, Auckland"

# Search specific sites only
nz-house-prices "123 Main St, Auckland" --sites homes.co.nz,qv.co.nz

# Output as JSON
nz-house-prices "123 Example Street" --json

# List supported sites
nz-house-prices --list-sites
```

### Python API

```python
from nz_house_prices import get_prices

# Get prices from all sites
prices = get_prices("123 Example Street, Ponsonby, Auckland")

for site, estimate in prices.items():
    if estimate.midpoint:
        print(f"{site}: ${estimate.midpoint:,.0f}")
```

### Context Manager (recommended for multiple lookups)

```python
from nz_house_prices import HousePriceScraper

with HousePriceScraper() as scraper:
    prices1 = scraper.scrape_address("123 Example Street, Ponsonby")
    prices2 = scraper.scrape_address("123 Main St, Auckland")

    for site, estimate in prices1.items():
        print(f"{site}: {estimate.midpoint}")
```

## Features

- Automatic address-to-URL resolution for all supported sites
- URL caching for faster repeated lookups
- Rate limiting to avoid overwhelming sites
- Retry logic with exponential backoff
- Both CLI and Python API interfaces

## Requirements

- Python 3.9+
- Chrome browser (for Selenium WebDriver)

## License

MIT License
