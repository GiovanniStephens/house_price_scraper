"""Address parsing and normalization utilities."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedAddress:
    """Parsed address components."""

    street_number: str
    street_name: str
    street_type: Optional[str] = None
    unit: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postcode: Optional[str] = None
    raw: str = ""

    def to_search_string(self) -> str:
        """Convert to a search-friendly string.

        Returns:
            Formatted address string for searching
        """
        parts = []

        if self.unit:
            parts.append(f"{self.unit}/")

        parts.append(self.street_number)
        parts.append(self.street_name)

        if self.street_type:
            parts.append(self.street_type)

        if self.suburb:
            parts.append(f", {self.suburb}")

        if self.city:
            parts.append(f", {self.city}")

        return " ".join(parts).replace("  ", " ").replace(" ,", ",")

    def to_slug(self) -> str:
        """Convert to a URL-friendly slug.

        Returns:
            URL slug version of the address
        """
        text = f"{self.street_number} {self.street_name}"
        if self.street_type:
            text += f" {self.street_type}"

        # Convert to lowercase, replace spaces with hyphens
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        return slug


# Common NZ street types
STREET_TYPES = {
    "road": ["road", "rd"],
    "street": ["street", "st"],
    "avenue": ["avenue", "ave"],
    "drive": ["drive", "dr"],
    "place": ["place", "pl"],
    "crescent": ["crescent", "cres", "cr"],
    "terrace": ["terrace", "tce", "ter"],
    "lane": ["lane", "ln"],
    "way": ["way"],
    "close": ["close", "cl"],
    "court": ["court", "ct"],
    "parade": ["parade", "pde"],
    "highway": ["highway", "hwy"],
    "esplanade": ["esplanade", "esp"],
    "grove": ["grove", "gr"],
    "rise": ["rise"],
    "view": ["view"],
    "heights": ["heights", "hts"],
    "hill": ["hill"],
}

# Reverse lookup - abbreviation to full form
STREET_TYPE_LOOKUP = {}
for full_form, abbreviations in STREET_TYPES.items():
    for abbr in abbreviations:
        STREET_TYPE_LOOKUP[abbr.lower()] = full_form

# Common NZ regions/cities
NZ_REGIONS = [
    "auckland",
    "wellington",
    "christchurch",
    "hamilton",
    "tauranga",
    "dunedin",
    "auckland",
    "nelson",
    "napier",
    "hastings",
    "palmerston north",
    "rotorua",
    "whangarei",
    "invercargill",
    "whanganui",
    "gisborne",
    "new plymouth",
    "timaru",
    "blenheim",
    "kapiti",
    "porirua",
    "upper hutt",
    "lower hutt",
    "waikato",
    "bay of plenty",
    "hawkes bay",
    "manawatu",
    "taranaki",
    "otago",
    "southland",
    "canterbury",
    "marlborough",
    "west coast",
    "northland",
]


def parse_address(address: str) -> ParsedAddress:
    """Parse a free-form address string into components.

    Args:
        address: Raw address string (e.g., "123 Example Street, Ponsonby, Auckland")

    Returns:
        ParsedAddress with extracted components
    """
    if not address:
        return ParsedAddress(street_number="", street_name="", raw=address)

    raw = address
    address = address.strip()

    # Initialize components
    unit = None
    street_number = ""
    street_name = ""
    street_type = None
    suburb = None
    city = None
    region = None
    postcode = None

    # Split by comma to separate street from suburb/city
    parts = [p.strip() for p in address.split(",")]

    # First part should contain the street address
    street_part = parts[0] if parts else ""

    # Check for unit number (e.g., "1/23" or "Unit 1, 23")
    unit_match = re.match(r"^(\d+[A-Za-z]?)\s*/\s*(.+)$", street_part)
    if unit_match:
        unit = unit_match.group(1)
        street_part = unit_match.group(2)
    else:
        unit_match = re.match(r"^(?:unit|flat|apt|apartment)\s*(\d+[A-Za-z]?)\s*,?\s*(.+)$", street_part, re.I)
        if unit_match:
            unit = unit_match.group(1)
            street_part = unit_match.group(2)

    # Extract street number
    number_match = re.match(r"^(\d+[A-Za-z]?)\s+(.+)$", street_part)
    if number_match:
        street_number = number_match.group(1)
        street_part = number_match.group(2)

    # Extract street type from the end
    words = street_part.split()
    if words:
        last_word = words[-1].lower().rstrip(".")
        if last_word in STREET_TYPE_LOOKUP:
            street_type = STREET_TYPE_LOOKUP[last_word]
            # Keep street name as everything before the street type
            street_name = " ".join(words[:-1])
        else:
            # No street type found, keep the whole thing as street name
            street_name = street_part

    # If street_name is empty but we have a street_part, use it
    if not street_name and street_part:
        street_name = street_part

    # Process remaining parts (suburb, city, region)
    remaining_parts = parts[1:] if len(parts) > 1 else []

    for i, part in enumerate(remaining_parts):
        part_lower = part.lower()

        # Check for postcode
        postcode_match = re.search(r"\b(\d{4})\b", part)
        if postcode_match:
            postcode = postcode_match.group(1)
            part = re.sub(r"\b\d{4}\b", "", part).strip()
            if not part:
                continue

        # Check if it's a known region/city
        if any(r in part_lower for r in NZ_REGIONS):
            if city is None:
                city = part
            else:
                region = part
        elif suburb is None:
            suburb = part
        elif city is None:
            city = part
        else:
            region = part

    return ParsedAddress(
        street_number=street_number,
        street_name=street_name,
        street_type=street_type,
        unit=unit,
        suburb=suburb,
        city=city,
        region=region,
        postcode=postcode,
        raw=raw,
    )


def normalize_address(address: str) -> str:
    """Normalize an address string for consistent searching.

    Args:
        address: Raw address string

    Returns:
        Normalized address string
    """
    if not address:
        return ""

    # Basic cleanup
    normalized = address.strip()
    normalized = " ".join(normalized.split())  # Normalize whitespace

    # Expand common abbreviations while preserving punctuation
    words = normalized.split()
    expanded_words = []

    for word in words:
        # Separate trailing punctuation
        trailing_punct = ""
        clean_word = word
        while clean_word and clean_word[-1] in ".,;:":
            trailing_punct = clean_word[-1] + trailing_punct
            clean_word = clean_word[:-1]

        word_lower = clean_word.lower()
        if word_lower in STREET_TYPE_LOOKUP:
            # Keep original case style and add back punctuation
            full_form = STREET_TYPE_LOOKUP[word_lower]
            if clean_word and clean_word[0].isupper():
                full_form = full_form.capitalize()
            expanded_words.append(full_form + trailing_punct)
        else:
            expanded_words.append(word)

    return " ".join(expanded_words)
