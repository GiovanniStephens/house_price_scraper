import gspread
from gspread.utils import ValueRenderOption
import json
from oauth2client.service_account import ServiceAccountCredentials
import os
import re
import scraper
import numpy as np


def authenticate_gs_client():
    try:
        credentials_json = open("client_secret.json").read()
    except FileNotFoundError:
        credentials_json = os.environ.get("GSHEETS_CREDENTIALS")
    if not credentials_json:
        raise ValueError(
            "Google Sheets credentials are not set in the environment variables"
        )
    creds_dict = json.loads(credentials_json)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client


def get_last_number(sheet_instance):
    formula = sheet_instance.get("C49", value_render_option=ValueRenderOption.formula)[
        0
    ][0]
    last_number = re.findall(r"\d+", formula)[-2]
    return last_number


def simulate_single_website(lower=None, midpoint=None, upper=None, num_simulations=10000):
    """
    Simulate a single website's price estimate based on available data:
    - 3 values (lower, midpoint, upper): Triangle distribution
    - 2 values: Uniform distribution between the two
    - 1 value: Return that value (no simulation needed)
    """
    values = [v for v in [lower, midpoint, upper] if v is not None]
    
    if len(values) == 3:
        # Triangle distribution: lower, midpoint, upper
        sorted_values = sorted(values)
        # Handle case where all values are identical
        if sorted_values[0] == sorted_values[2]:
            return np.full(num_simulations, sorted_values[0])
        samples = np.random.triangular(sorted_values[0], midpoint, sorted_values[2], num_simulations)
        return samples
    elif len(values) == 2:
        # Uniform distribution between min and max
        min_val, max_val = min(values), max(values)
        samples = np.random.uniform(min_val, max_val, num_simulations)
        return samples
    elif len(values) == 1:
        # Single value - return array of that value
        return np.full(num_simulations, values[0])
    else:
        raise ValueError(f"Expected 1-3 price values, got {len(values)}")

def simulate_all_websites(results, num_simulations=10000):
    """
    Simulate each website individually, then aggregate all simulations
    """
    all_samples = []
    
    for result in results:
        if not result.success:
            continue
            
        # Get the price data for this website
        lower = result.prices.get("lower")
        midpoint = result.prices.get("midpoint") 
        upper = result.prices.get("upper")
        
        # Special handling for PropertyValue.co.nz (midpoint calculated externally)
        if result.site == "propertyvalue.co.nz":
            # Calculate midpoint from bounds like the original code does
            if lower is not None and upper is not None:
                # Use the average of other sites to constrain the midpoint
                other_midpoints = []
                for other_result in results:
                    if other_result.success and other_result.site != "propertyvalue.co.nz":
                        other_mid = other_result.prices.get("midpoint")
                        if other_mid is not None:
                            other_midpoints.append(other_mid)
                
                if other_midpoints:
                    average = sum(other_midpoints) / len(other_midpoints) 
                    if lower <= average <= upper:
                        midpoint = average
                    elif average < lower:
                        midpoint = lower
                    else:
                        midpoint = upper
        
        # Run simulation for this website
        try:
            website_samples = simulate_single_website(lower, midpoint, upper, num_simulations)
            all_samples.append(website_samples)
            print(f"Simulated {result.site}: {len([v for v in [lower, midpoint, upper] if v is not None])} values")
        except ValueError as e:
            print(f"Skipping {result.site}: {e}")
            continue
    
    if not all_samples:
        raise ValueError("No valid simulations could be run")
    
    # Aggregate all simulations: for each simulation run, use median across all websites
    aggregated_samples = []
    for i in range(num_simulations):
        # Get the i-th sample from each website and take the median
        sample_values = [samples[i] for samples in all_samples]
        aggregated_samples.append(np.median(sample_values))
    
    # Return the median of all aggregated samples for final robustness
    return np.median(aggregated_samples)

def format_price_for_note(price):
    """Format a price value for display in the note"""
    if price is None:
        return "N/A"
    # Convert to millions for readability
    price_in_millions = price / 1000000
    return f"${price_in_millions:.2f}M"


def build_note_from_results(results):
    """Build a note string showing all domain estimates"""
    note_lines = []

    for result in results:
        if not result.success:
            continue

        prices = result.prices
        lower = format_price_for_note(prices.get("lower"))
        midpoint = format_price_for_note(prices.get("midpoint"))
        upper = format_price_for_note(prices.get("upper"))

        # Format: "domain.com: low, mid, high"
        note_lines.append(f"{result.site}: {lower}, {midpoint}, {upper}")

    return "\n".join(note_lines)


def insert_prices(results, client):
    sheet = client.open("Financial Position")
    sheet_instance = sheet.get_worksheet(1)

    # Run Monte Carlo simulation across all websites
    simulated_price = simulate_all_websites(results)

    # Insert the simulated value directly (not as a formula)
    sheet_instance.update_acell("C49", int(round(simulated_price)))

    # Build and add note with all domain estimates
    note_text = build_note_from_results(results)
    if note_text:
        # Update the note for cell C49
        sheet_instance.update_note("C49", note_text)


if __name__ == "__main__":
    client = authenticate_gs_client()
    results = scraper.scrape_all_house_prices()
    
    # Check if we have any successful results
    successful_results = [r for r in results if r.success]
    if not successful_results:
        print("Error: No successful scraping results found")
        exit(1)
    
    print("Running Monte Carlo simulations for each website...")
    for result in successful_results:
        prices = result.prices
        value_count = len([v for v in [prices.get("lower"), prices.get("midpoint"), prices.get("upper")] if v is not None])
        print(f"{result.site}: {value_count} values - Lower: {prices.get('lower')}, Mid: {prices.get('midpoint')}, Upper: {prices.get('upper')}")
    
    # Run simulations and insert final result
    insert_prices(results, client)
    print("Monte Carlo simulation completed and result inserted into spreadsheet.")
