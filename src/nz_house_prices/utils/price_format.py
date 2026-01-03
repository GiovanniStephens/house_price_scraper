"""Site-specific price formatting utilities."""

import re
from typing import Optional


class PriceValidator:
    """Validator for house price values."""

    def __init__(
        self,
        min_price: float = 100000,
        max_price: float = 50000000,
    ):
        """Initialize the price validator.

        Args:
            min_price: Minimum valid house price ($100k default)
            max_price: Maximum valid house price ($50M default)
        """
        self.min_house_price = min_price
        self.max_house_price = max_price
        self.price_patterns = [
            r"^\$?[\d,]+\.?\d*[MKmk]?$",  # Standard price formats
            r"^\d+\.?\d*$",  # Numeric only
        ]

    def validate_price(
        self, price_text: Optional[str], price_type: str = "unknown"
    ) -> "ValidationResult":
        """Validate extracted price text.

        Args:
            price_text: The price text to validate
            price_type: Type of price being validated

        Returns:
            ValidationResult with validation status and value
        """
        from nz_house_prices.models.results import ValidationResult

        if not price_text or not isinstance(price_text, str):
            return ValidationResult(False, None, "Empty or invalid price text")

        # Pattern validation
        if not any(re.match(pattern, price_text.strip()) for pattern in self.price_patterns):
            return ValidationResult(False, None, f"Price format invalid: {price_text}")

        # Convert and range check
        try:
            numeric_price = self.convert_to_numeric(price_text)
            if not (self.min_house_price <= numeric_price <= self.max_house_price):
                return ValidationResult(False, None, f"Price out of range: ${numeric_price:,.0f}")

            return ValidationResult(True, numeric_price, "")
        except ValueError as e:
            return ValidationResult(False, None, f"Conversion error: {e}")

    def convert_to_numeric(self, price_text: str) -> float:
        """Convert price text to numeric value.

        Args:
            price_text: The price text to convert

        Returns:
            Numeric price value

        Raises:
            ValueError: If price text cannot be converted
        """
        if not price_text:
            raise ValueError("Empty price text")

        # Remove $ and whitespace
        cleaned = price_text.replace("$", "").replace(",", "").strip()

        # Handle M (millions) and K (thousands) suffixes
        if cleaned.upper().endswith("M"):
            number = float(cleaned[:-1])
            return number * 1000000
        elif cleaned.upper().endswith("K"):
            number = float(cleaned[:-1])
            return number * 1000
        else:
            return float(cleaned)

    def validate_price_relationships(
        self,
        lower: Optional[float],
        midpoint: Optional[float],
        upper: Optional[float],
    ) -> bool:
        """Ensure price relationships are logical.

        Args:
            lower: Lower price estimate
            midpoint: Midpoint price estimate
            upper: Upper price estimate

        Returns:
            True if relationships are valid
        """
        prices = [p for p in [lower, midpoint, upper] if p is not None]
        if len(prices) < 2:
            return True  # Can't validate relationships

        sorted_prices = sorted(prices)
        return prices == sorted_prices  # Prices should be in ascending order


def format_homes_prices(price: str) -> float:
    """Format price from homes.co.nz.

    Args:
        price: Price string (e.g., "1.8M" or "850K")

    Returns:
        Numeric price value
    """
    price = price.replace("$", "").replace(",", "").strip()
    if price.upper().endswith("M"):
        return float(price[:-1]) * 1000000
    elif price.upper().endswith("K"):
        return float(price[:-1]) * 1000
    else:
        return float(price)


def format_qv_prices(price: str) -> float:
    """Format price from qv.co.nz.

    Args:
        price: Price string (e.g., "$1,800,000")

    Returns:
        Numeric price value
    """
    price = price.replace("$", "")
    price = price.replace(",", "")
    price = price.replace("QV: ", "")
    return float(price)


def format_property_value_prices(price: str) -> float:
    """Format price from propertyvalue.co.nz.

    Args:
        price: Price string (e.g., "$1.8M")

    Returns:
        Numeric price value
    """
    price = price.replace("$", "")
    return format_homes_prices(price)


def format_realestate_prices(price: str) -> float:
    """Format price from realestate.co.nz.

    Args:
        price: Price string

    Returns:
        Numeric price value
    """
    return format_property_value_prices(price)


def format_oneroof_prices(price: str) -> float:
    """Format price from oneroof.co.nz.

    Args:
        price: Price string

    Returns:
        Numeric price value
    """
    return format_property_value_prices(price)


def format_price_by_site(price_text: str, site: str) -> float:
    """Format price based on site-specific requirements.

    Args:
        price_text: The price text to format
        site: The website the price came from

    Returns:
        Numeric price value
    """
    if "homes.co.nz" in site:
        return format_homes_prices(price_text)
    elif "qv.co.nz" in site:
        return format_qv_prices(price_text)
    elif "propertyvalue.co.nz" in site:
        return format_property_value_prices(price_text)
    elif "realestate.co.nz" in site:
        return format_realestate_prices(price_text)
    elif "oneroof.co.nz" in site:
        return format_oneroof_prices(price_text)
    else:
        # Default: try to parse as generic price
        validator = PriceValidator()
        return validator.convert_to_numeric(price_text)


def find_prices_with_regex(page_source: str) -> list[str]:
    """Find prices in various formats using comprehensive regex patterns.

    Args:
        page_source: HTML page source to search

    Returns:
        List of unique price strings found
    """
    patterns = [
        r"\$\d+\.\d+M(?!\d)",  # $1.2M format
        r"\$\d+M(?!\d)",  # $2M format
        r"\$\d+\.\d+K(?!\d)",  # $850.5K format
        r"\$\d+K(?!\d)",  # $850K format
        r"\$[\d,]+\.\d+(?![MK\d])",  # $1,200,000.50 format
        r"\$[\d,]+(?![MK\d\.])",  # $1,200,000 format
    ]
    all_matches = []
    for pattern in patterns:
        matches = re.findall(pattern, page_source)
        all_matches.extend(matches)
    return list(set(all_matches))
