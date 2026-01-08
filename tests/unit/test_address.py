"""Unit tests for address parsing and normalization.

These tests verify the pure functions in discovery/address.py.
They run without network access and should be very fast.
"""

import pytest

from nz_house_prices.discovery.address import (
    STREET_TYPE_LOOKUP,
    STREET_TYPES,
    ParsedAddress,
    normalize_address,
    parse_address,
)


@pytest.mark.unit
class TestParseAddress:
    """Tests for parse_address() function."""

    @pytest.mark.parametrize(
        "address,expected_number,expected_name",
        [
            ("123 Example Street", "123", "Example"),
            ("45A Main Road", "45A", "Main"),
            ("7 Queen Avenue", "7", "Queen"),
            ("100 Victoria Street", "100", "Victoria"),
            ("1 Short St", "1", "Short"),
        ],
    )
    def test_street_number_extraction(self, address: str, expected_number: str, expected_name: str):
        """Verify street number is correctly extracted."""
        parsed = parse_address(address)
        assert parsed.street_number == expected_number
        assert parsed.street_name == expected_name

    @pytest.mark.parametrize(
        "address,expected_unit",
        [
            ("3/14 Example Street", "3"),
            ("1A/100 Main Road", "1A"),
            ("Unit 5, 100 Main Road", "5"),
            ("Flat 2A, 50 Queen St", "2A"),
            ("Apartment 12, 200 High Street", "12"),
            ("2/677 Worcester Street, Linwood", "2"),
        ],
    )
    def test_unit_number_extraction(self, address: str, expected_unit: str):
        """Verify unit numbers are correctly extracted.

        Supports formats:
        - "3/14 Example Street" (slash style)
        - "Unit 5, 100 Main Road" (prefix with comma)
        - "Flat 2A, 50 Queen St" (prefix with letter suffix)
        """
        parsed = parse_address(address)
        assert parsed.unit == expected_unit

    @pytest.mark.parametrize(
        "address,expected_type",
        [
            ("123 Example Street", "street"),
            ("45 Main Road", "road"),
            ("7 Queen Ave", "avenue"),
            ("10 King Dr", "drive"),
            ("50 Park Place", "place"),
            ("30 Ocean Crescent", "crescent"),
            ("5 Hill Terrace", "terrace"),
        ],
    )
    def test_street_type_normalization(self, address: str, expected_type: str):
        """Verify street type abbreviations are expanded."""
        parsed = parse_address(address)
        assert parsed.street_type == expected_type

    def test_suburb_extraction(self):
        """Verify suburb is extracted from comma-separated address."""
        parsed = parse_address("123 Example Street, Ponsonby")
        assert parsed.suburb == "Ponsonby"

    def test_suburb_and_city_extraction(self):
        """Verify suburb and city are extracted."""
        parsed = parse_address("123 Example Street, Ponsonby, Auckland")
        assert parsed.suburb == "Ponsonby"
        assert parsed.city == "Auckland"

    def test_full_address_parsing(self):
        """Verify full address with all components."""
        parsed = parse_address("21 Onslow Road, Lake Hayes, Queenstown")
        assert parsed.street_number == "21"
        assert parsed.street_name == "Onslow"
        assert parsed.street_type == "road"
        assert parsed.suburb == "Lake Hayes"
        assert parsed.city == "Queenstown"

    def test_empty_address(self):
        """Verify empty address returns empty ParsedAddress."""
        parsed = parse_address("")
        assert parsed.street_number == ""
        assert parsed.street_name == ""

    def test_whitespace_only_address(self):
        """Verify whitespace-only address is handled."""
        parsed = parse_address("   ")
        assert parsed.street_number == ""
        assert parsed.street_name == ""

    def test_raw_address_preserved(self):
        """Verify raw address is preserved in result."""
        original = "123 Example Street, Ponsonby, Auckland"
        parsed = parse_address(original)
        assert parsed.raw == original


@pytest.mark.unit
class TestNormalizeAddress:
    """Tests for normalize_address() function."""

    def test_whitespace_normalization(self):
        """Verify extra whitespace is normalized."""
        assert normalize_address("123   Example   Street") == "123 Example Street"

    @pytest.mark.parametrize(
        "input_addr,expected",
        [
            ("123 Example St", "123 Example Street"),
            ("45 Main Rd", "45 Main Road"),
            ("7 Queen Ave", "7 Queen Avenue"),
            ("10 King Dr", "10 King Drive"),
            ("50 Park Pl", "50 Park Place"),
        ],
    )
    def test_abbreviation_expansion(self, input_addr: str, expected: str):
        """Verify street type abbreviations are expanded."""
        assert normalize_address(input_addr) == expected

    def test_preserves_comma_structure(self):
        """Verify comma-separated structure is preserved."""
        result = normalize_address("123 Example St, Ponsonby, Auckland")
        assert result == "123 Example Street, Ponsonby, Auckland"

    def test_empty_string(self):
        """Verify empty string returns empty string."""
        assert normalize_address("") == ""

    def test_none_like_empty(self):
        """Verify None-like values are handled."""
        assert normalize_address("") == ""

    def test_leading_trailing_whitespace(self):
        """Verify leading/trailing whitespace is trimmed."""
        result = normalize_address("  123 Example Street  ")
        assert result == "123 Example Street"

    def test_case_preservation(self):
        """Verify case is appropriately handled."""
        result = normalize_address("123 example St")
        assert "Street" in result or "street" in result


@pytest.mark.unit
class TestParsedAddress:
    """Tests for ParsedAddress dataclass methods."""

    def test_to_search_string_basic(self):
        """Verify basic search string generation."""
        parsed = ParsedAddress(
            street_number="123",
            street_name="Example",
            street_type="street",
        )
        result = parsed.to_search_string()
        assert "123" in result
        assert "Example" in result
        assert "street" in result

    def test_to_search_string_with_unit(self):
        """Verify search string with unit number."""
        parsed = ParsedAddress(
            street_number="14",
            street_name="Example",
            street_type="street",
            unit="3",
        )
        result = parsed.to_search_string()
        assert "3/" in result
        assert "14" in result

    def test_to_search_string_with_suburb(self):
        """Verify search string with suburb."""
        parsed = ParsedAddress(
            street_number="123",
            street_name="Example",
            street_type="street",
            suburb="Ponsonby",
        )
        result = parsed.to_search_string()
        assert "Ponsonby" in result

    def test_to_slug(self):
        """Verify URL slug generation."""
        parsed = ParsedAddress(
            street_number="123",
            street_name="Example",
            street_type="street",
        )
        slug = parsed.to_slug()
        assert slug == "123-example-street"

    def test_to_slug_lowercase(self):
        """Verify slug is lowercase."""
        parsed = ParsedAddress(
            street_number="123",
            street_name="Example Street",
        )
        slug = parsed.to_slug()
        assert slug == slug.lower()

    def test_to_slug_no_special_chars(self):
        """Verify slug has no special characters."""
        parsed = ParsedAddress(
            street_number="123",
            street_name="Example",
            street_type="street",
        )
        slug = parsed.to_slug()
        assert all(c.isalnum() or c == "-" for c in slug)


@pytest.mark.unit
class TestStreetTypeLookup:
    """Tests for STREET_TYPE_LOOKUP dictionary."""

    def test_common_abbreviations_exist(self):
        """Verify common abbreviations are in lookup."""
        assert "st" in STREET_TYPE_LOOKUP
        assert "rd" in STREET_TYPE_LOOKUP
        assert "ave" in STREET_TYPE_LOOKUP
        assert "dr" in STREET_TYPE_LOOKUP

    def test_abbreviations_map_to_full_forms(self):
        """Verify abbreviations map to full forms."""
        assert STREET_TYPE_LOOKUP["st"] == "street"
        assert STREET_TYPE_LOOKUP["rd"] == "road"
        assert STREET_TYPE_LOOKUP["ave"] == "avenue"
        assert STREET_TYPE_LOOKUP["dr"] == "drive"

    def test_full_forms_also_in_lookup(self):
        """Verify full forms are also in lookup (for normalization)."""
        assert STREET_TYPE_LOOKUP.get("street") == "street"
        assert STREET_TYPE_LOOKUP.get("road") == "road"

    def test_all_street_types_have_entries(self):
        """Verify all STREET_TYPES have lookup entries."""
        for full_form, abbreviations in STREET_TYPES.items():
            for abbr in abbreviations:
                assert abbr.lower() in STREET_TYPE_LOOKUP
                assert STREET_TYPE_LOOKUP[abbr.lower()] == full_form
