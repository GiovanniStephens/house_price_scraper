"""Command-line interface for NZ House Prices."""

import argparse
import json
import sys
from typing import List, Optional

from nz_house_prices import __version__
from nz_house_prices.api import get_prices, get_prices_from_urls
from nz_house_prices.core.scraper import scrape_all_house_prices
from nz_house_prices.core.selectors import get_supported_sites
from nz_house_prices.models.results import calculate_metrics


def main(args: Optional[List[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success)
    """
    parser = argparse.ArgumentParser(
        prog="nz-house-prices",
        description="Scrape house price estimates from NZ real estate websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search by address
  nz-house-prices "123 Example Street, Ponsonby, Auckland"

  # Search specific sites only
  nz-house-prices "123 Main St, Auckland" --sites homes.co.nz,qv.co.nz

  # Use config file (legacy mode)
  nz-house-prices --config config.yml

  # Output as JSON
  nz-house-prices "123 Example Street" --json
""",
    )
    parser.add_argument(
        "address",
        nargs="?",
        type=str,
        help="Property address to search (e.g., '123 Example Street, Ponsonby, Auckland')",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file (uses URLs from config instead of address search)",
    )
    parser.add_argument(
        "--sites",
        "-s",
        type=str,
        help="Comma-separated list of sites to query (e.g., 'homes.co.nz,qv.co.nz')",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable URL caching",
    )
    parser.add_argument(
        "--no-rate-limit",
        action="store_true",
        help="Disable rate limiting between requests",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Disable detailed logging",
    )
    parser.add_argument(
        "--list-sites",
        action="store_true",
        help="List supported sites and exit",
    )

    parsed_args = parser.parse_args(args)

    # List sites and exit
    if parsed_args.list_sites:
        print("Supported sites:")
        for site in get_supported_sites():
            print(f"  - {site}")
        return 0

    # Parse sites if provided
    sites = None
    if parsed_args.sites:
        sites = [s.strip() for s in parsed_args.sites.split(",")]
        # Validate sites
        supported = set(get_supported_sites())
        invalid = [s for s in sites if s not in supported]
        if invalid:
            print(f"Error: Invalid sites: {invalid}")
            print(f"Supported sites: {list(supported)}")
            return 1

    # Determine mode: address search vs config file
    if parsed_args.address:
        # Address search mode (new)
        return _run_address_search(
            address=parsed_args.address,
            sites=sites,
            use_cache=not parsed_args.no_cache,
            rate_limit=not parsed_args.no_rate_limit,
            output_json=parsed_args.json,
        )
    elif parsed_args.config:
        # Config file mode (legacy)
        return _run_config_mode(
            config_path=parsed_args.config,
            rate_limit=not parsed_args.no_rate_limit,
            quiet=parsed_args.quiet,
            output_json=parsed_args.json,
        )
    else:
        # Default: try config file
        try:
            return _run_config_mode(
                config_path=None,
                rate_limit=not parsed_args.no_rate_limit,
                quiet=parsed_args.quiet,
                output_json=parsed_args.json,
            )
        except Exception:
            parser.print_help()
            print("\nError: Please provide an address or config file.")
            return 1


def _run_address_search(
    address: str,
    sites: Optional[List[str]],
    use_cache: bool,
    rate_limit: bool,
    output_json: bool,
) -> int:
    """Run address-based search.

    Args:
        address: Property address to search
        sites: List of sites to query
        use_cache: Whether to use URL caching
        rate_limit: Whether to apply rate limiting
        output_json: Output as JSON

    Returns:
        Exit code
    """
    print(f"Searching for: {address}")
    if sites:
        print(f"Sites: {', '.join(sites)}")
    print()

    try:
        prices = get_prices(
            address=address,
            sites=sites,
            use_cache=use_cache,
            rate_limit=rate_limit,
        )

        if output_json:
            output = {
                "address": address,
                "prices": {
                    site: {
                        "midpoint": estimate.midpoint,
                        "lower": estimate.lower,
                        "upper": estimate.upper,
                        "source": estimate.source,
                    }
                    for site, estimate in prices.items()
                },
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            found_any = False
            for site, estimate in prices.items():
                # Show results if we have any price data
                has_prices = (
                    estimate.midpoint is not None
                    or estimate.lower is not None
                    or estimate.upper is not None
                )
                if has_prices:
                    found_any = True
                    print(f"{site}:")
                    if estimate.lower and estimate.upper:
                        print(f"  Range: ${estimate.lower:,.0f} - ${estimate.upper:,.0f}")
                    if estimate.midpoint:
                        print(f"  Midpoint: ${estimate.midpoint:,.0f}")
                    elif estimate.lower and estimate.upper:
                        # Calculate midpoint if we have range
                        calc_midpoint = (estimate.lower + estimate.upper) / 2
                        print(f"  Midpoint: ${calc_midpoint:,.0f}")
                    print()

            if not found_any:
                print("No prices found. The address may not be recognized by the sites.")
                return 1

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def _run_config_mode(
    config_path: Optional[str],
    rate_limit: bool,
    quiet: bool,
    output_json: bool,
) -> int:
    """Run config-based scraping (legacy mode).

    Args:
        config_path: Path to config file
        rate_limit: Whether to apply rate limiting
        quiet: Disable logging
        output_json: Output as JSON

    Returns:
        Exit code
    """
    results = scrape_all_house_prices(
        enable_retry=True,
        rate_limit=rate_limit,
        enable_logging=not quiet,
    )

    if not results:
        print("No results obtained")
        return 1

    if output_json:
        output = {
            "results": [
                {
                    "site": r.site,
                    "url": r.url,
                    "success": r.success,
                    "prices": r.prices,
                    "execution_time": r.execution_time,
                }
                for r in results
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        # Print summary
        metrics = calculate_metrics(results)
        print(f"\nSummary: {metrics.successful_sites}/{metrics.total_sites} sites successful")
        print(f"Total time: {metrics.total_execution_time:.2f}s")

    return 0 if any(r.success for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
