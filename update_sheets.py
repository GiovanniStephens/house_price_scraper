import gspread
from gspread.utils import ValueRenderOption
import json
from oauth2client.service_account import ServiceAccountCredentials
import os
import re
import scraper


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


def insert_prices(prices, client):
    sheet = client.open("Financial Position")
    sheet_instance = sheet.get_worksheet(1)
    # last_number = get_last_number(sheet_instance)
    string = "=("
    for price in prices:
        string += f"{int(price)}+"
    # string += str(last_number) + ')/' + str(len(prices) + 1)
    string = string[:-1] + ")/" + str(len(prices))
    sheet_instance.update_acell("C49", string)


if __name__ == "__main__":
    client = authenticate_gs_client()
    results = scraper.scrape_all_house_prices()
    property_value_data = None
    regular_midpoints = []

    for result in results:
        # Check if this is a successful scraping result
        if not result.success:
            print(
                f"Warning: Failed to scrape {result.site}: {'; '.join(result.errors)}"
            )
            continue

        # Get the midpoint price
        midpoint = result.prices.get("midpoint")

        # Check if this is PropertyValue.co.nz (which has midpoint as None for external calculation)
        if result.site == "propertyvalue.co.nz":
            property_value_data = result
        elif midpoint is not None:
            regular_midpoints.append(midpoint)

    # Calculate average from regular midpoints
    if regular_midpoints:
        average = sum(regular_midpoints) / len(regular_midpoints)

        # Handle PropertyValue.co.nz special case
        if property_value_data:
            lower_bound = property_value_data.prices.get("lower")
            upper_bound = property_value_data.prices.get("upper")

            if lower_bound is not None and upper_bound is not None:
                # Use average if it's within bounds, otherwise use the closest bound
                if lower_bound <= average <= upper_bound:
                    property_value_midpoint = average
                else:
                    if average < lower_bound:
                        property_value_midpoint = lower_bound
                    else:
                        property_value_midpoint = upper_bound
                regular_midpoints.append(property_value_midpoint)
                print(
                    f"PropertyValue.co.nz midpoint calculated as: ${property_value_midpoint:,.0f}"
                )
            else:
                print("Warning: PropertyValue.co.nz missing lower or upper bound")

        print(f"Final midpoints: {[f'${price:,.0f}' for price in regular_midpoints]}")
        insert_prices(regular_midpoints, client)
    else:
        print("Error: No valid midpoint prices found")
