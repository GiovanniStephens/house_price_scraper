"""Unit tests for price formatting utilities.

These tests verify the price parsing and validation functions.
They run without network access and should be very fast.
"""

import pytest

from nz_house_prices.utils.price_format import (
    PriceValidator,
    find_prices_with_regex,
    format_homes_prices,
    format_price_by_site,
    format_property_value_prices,
    format_qv_prices,
)


@pytest.mark.unit
class TestPriceValidatorConversion:
    """Tests for PriceValidator.convert_to_numeric()."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PriceValidator()

    @pytest.mark.parametrize(
        "price_text,expected",
        [
            ("$1.5M", 1500000.0),
            ("1.5M", 1500000.0),
            ("$2M", 2000000.0),
            ("2m", 2000000.0),
            ("$850K", 850000.0),
            ("850k", 850000.0),
            ("$1,200,000", 1200000.0),
            ("1200000", 1200000.0),
            ("$1.25M", 1250000.0),
        ],
    )
    def test_convert_to_numeric_valid(self, price_text: str, expected: float):
        """Verify valid price conversion."""
        result = self.validator.convert_to_numeric(price_text)
        assert result == expected

    def test_convert_million_suffix(self):
        """Verify M suffix is multiplied by 1,000,000."""
        result = self.validator.convert_to_numeric("1.5M")
        assert result == 1500000.0

    def test_convert_thousand_suffix(self):
        """Verify K suffix is multiplied by 1,000."""
        result = self.validator.convert_to_numeric("850K")
        assert result == 850000.0

    def test_convert_removes_dollar_sign(self):
        """Verify dollar sign is removed."""
        result = self.validator.convert_to_numeric("$1,000,000")
        assert result == 1000000.0

    def test_convert_removes_commas(self):
        """Verify commas are removed."""
        result = self.validator.convert_to_numeric("1,234,567")
        assert result == 1234567.0

    def test_convert_empty_raises(self):
        """Verify empty string raises ValueError."""
        with pytest.raises(ValueError):
            self.validator.convert_to_numeric("")


@pytest.mark.unit
class TestPriceValidatorValidation:
    """Tests for PriceValidator.validate_price()."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PriceValidator()

    def test_validate_valid_price(self):
        """Verify valid price passes validation."""
        result = self.validator.validate_price("$1,500,000")
        assert result.is_valid
        assert result.value == 1500000.0

    def test_validate_out_of_range_low(self):
        """Verify price below minimum fails."""
        result = self.validator.validate_price("$10,000")
        assert not result.is_valid
        assert "out of range" in result.error_message.lower()

    def test_validate_out_of_range_high(self):
        """Verify price above maximum fails."""
        result = self.validator.validate_price("$100,000,000")
        assert not result.is_valid
        assert "out of range" in result.error_message.lower()

    def test_validate_empty_string(self):
        """Verify empty string fails validation."""
        result = self.validator.validate_price("")
        assert not result.is_valid

    def test_validate_none(self):
        """Verify None fails validation."""
        result = self.validator.validate_price(None)
        assert not result.is_valid

    def test_validate_custom_range(self):
        """Verify custom min/max range works."""
        validator = PriceValidator(min_price=500000, max_price=2000000)

        # Within range
        result = validator.validate_price("$1,000,000")
        assert result.is_valid

        # Below range
        result = validator.validate_price("$400,000")
        assert not result.is_valid


@pytest.mark.unit
class TestPriceValidatorRelationships:
    """Tests for PriceValidator.validate_price_relationships()."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PriceValidator()

    def test_valid_ascending_order(self):
        """Verify valid ascending prices pass."""
        assert self.validator.validate_price_relationships(
            lower=1000000, midpoint=1200000, upper=1400000
        )

    def test_invalid_descending_order(self):
        """Verify descending prices fail."""
        assert not self.validator.validate_price_relationships(
            lower=1400000, midpoint=1200000, upper=1000000
        )

    def test_midpoint_higher_than_upper(self):
        """Verify midpoint > upper fails."""
        assert not self.validator.validate_price_relationships(
            lower=1000000, midpoint=1500000, upper=1400000
        )

    def test_single_price_passes(self):
        """Verify single price passes (can't validate relationships)."""
        assert self.validator.validate_price_relationships(lower=None, midpoint=1200000, upper=None)

    def test_two_prices_valid(self):
        """Verify two valid prices pass."""
        assert self.validator.validate_price_relationships(
            lower=1000000, midpoint=None, upper=1400000
        )


@pytest.mark.unit
class TestSiteSpecificFormatters:
    """Tests for site-specific price formatters."""

    @pytest.mark.parametrize(
        "input_price,expected",
        [
            ("1.2M", 1200000.0),
            ("$2.5M", 2500000.0),
            ("850K", 850000.0),
            ("$850K", 850000.0),
            ("1500000", 1500000.0),
        ],
    )
    def test_format_homes_prices(self, input_price: str, expected: float):
        """Test homes.co.nz price formatting."""
        result = format_homes_prices(input_price)
        assert result == expected

    @pytest.mark.parametrize(
        "input_price,expected",
        [
            ("$1,200,000", 1200000.0),
            ("$850,000", 850000.0),
            ("QV: $1,500,000", 1500000.0),
            ("1200000", 1200000.0),
        ],
    )
    def test_format_qv_prices(self, input_price: str, expected: float):
        """Test qv.co.nz price formatting."""
        result = format_qv_prices(input_price)
        assert result == expected

    @pytest.mark.parametrize(
        "input_price,expected",
        [
            ("$1.8M", 1800000.0),
            ("$950K", 950000.0),
            ("1.5M", 1500000.0),
        ],
    )
    def test_format_property_value_prices(self, input_price: str, expected: float):
        """Test propertyvalue.co.nz price formatting."""
        result = format_property_value_prices(input_price)
        assert result == expected


@pytest.mark.unit
class TestFormatPriceBySite:
    """Tests for format_price_by_site() dispatcher."""

    def test_dispatch_homes(self):
        """Verify homes.co.nz uses correct formatter."""
        result = format_price_by_site("1.5M", "homes.co.nz")
        assert result == 1500000.0

    def test_dispatch_qv(self):
        """Verify qv.co.nz uses correct formatter."""
        result = format_price_by_site("$1,500,000", "qv.co.nz")
        assert result == 1500000.0

    def test_dispatch_propertyvalue(self):
        """Verify propertyvalue.co.nz uses correct formatter."""
        result = format_price_by_site("$1.5M", "propertyvalue.co.nz")
        assert result == 1500000.0

    def test_dispatch_realestate(self):
        """Verify realestate.co.nz uses correct formatter."""
        result = format_price_by_site("$1.5M", "realestate.co.nz")
        assert result == 1500000.0

    def test_dispatch_oneroof(self):
        """Verify oneroof.co.nz uses correct formatter."""
        result = format_price_by_site("$1.5M", "oneroof.co.nz")
        assert result == 1500000.0

    def test_dispatch_unknown_site(self):
        """Verify unknown site uses default formatter."""
        result = format_price_by_site("$1,500,000", "unknown.co.nz")
        assert result == 1500000.0


@pytest.mark.unit
class TestFindPricesWithRegex:
    """Tests for find_prices_with_regex() function."""

    def test_finds_million_format(self):
        """Verify $X.XM format prices are found."""
        html = "The estimate is $1.5M for this property"
        prices = find_prices_with_regex(html)
        assert "$1.5M" in prices

    def test_finds_thousands_format(self):
        """Verify $XXXK format prices are found."""
        html = "Lower estimate: $850K"
        prices = find_prices_with_regex(html)
        assert "$850K" in prices

    def test_finds_full_format(self):
        """Verify $X,XXX,XXX format prices are found."""
        html = "Price: $1,500,000"
        prices = find_prices_with_regex(html)
        assert "$1,500,000" in prices

    def test_no_duplicates(self):
        """Verify no duplicate prices returned."""
        html = "$1.5M and again $1.5M"
        prices = find_prices_with_regex(html)
        assert prices.count("$1.5M") == 1

    def test_multiple_formats(self):
        """Verify multiple price formats are found."""
        html = "Range: $850K to $1.2M or about $1,000,000"
        prices = find_prices_with_regex(html)
        assert len(prices) >= 2

    def test_empty_html(self):
        """Verify empty HTML returns empty list."""
        prices = find_prices_with_regex("")
        assert prices == []

    def test_no_prices(self):
        """Verify no prices found returns empty list."""
        html = "This property has no listed price"
        prices = find_prices_with_regex(html)
        assert prices == []
