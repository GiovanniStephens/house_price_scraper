# NZ House Prices Scraper

## Known Edge Cases

### Suburb Name Variations
Different property sites use different suburb names for the same location:
- "Lake Hayes Estate" vs "Dalefield/Wakatipu Basin" (same area near Queenstown)
- "North New Brighton" vs "New Brighton" (Christchurch)

### Solution: Geographic Matching

Instead of brittle text-based matching (comparing street names, suburb names, etc.),
we use **geographic distance** to find the correct property:

1. Geocode the target address (e.g., "21 Onslow Road, Lake Hayes Estate")
2. Geocode all autocomplete results from the site
3. Return the result geographically closest to the target (within 5km)

This handles suburb name variations automatically because the same physical
location will geocode to the same coordinates regardless of how the suburb is named.

### Implementation

The `_find_best_match` methods in site handlers:
- `src/nz_house_prices/sites/oneroof.py`
- `src/nz_house_prices/sites/homes.py`

use the Haversine formula to calculate distances and return the closest match.

### Why Not Text Matching?

Text-based scoring is fragile because:
- Suburb names vary between databases
- Autocomplete results include unrelated addresses (e.g., "21 Hayes Road, Auckland"
  when searching for "21 Onslow Road, Lake Hayes Estate")
- Street name parsing can fail on edge cases (unit numbers, abbreviations, etc.)

Geographic matching is robust because coordinates don't lie - the same property
will always geocode to the same location regardless of how it's named.
