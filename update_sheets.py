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
    values = scraper.scrape_all_house_prices()
    property_value_data = None
    regular_midpoints = []
    for value in values:
        if value[1] is None:
            property_value_data = value
        else:
            regular_midpoints.append(value[1])
    average = sum(regular_midpoints) / len(regular_midpoints)
    if property_value_data:
        lower_bound, upper_bound = property_value_data[0], property_value_data[2]
        if lower_bound <= average <= upper_bound:
            property_value_midpoint = average
        else:
            if average < lower_bound:
                property_value_midpoint = lower_bound
            else:
                property_value_midpoint = upper_bound
        regular_midpoints.append(property_value_midpoint)
    insert_prices(regular_midpoints, client)
