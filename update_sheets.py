import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.utils import ValueRenderOption
import scraper
import re
import json
import os


def authenticate_gs_client():
    try:
        credentials_json = open("client_secret.json").read()
    except FileNotFoundError:
        credentials_json = os.environ.get("GSHEETS_CREDENTIALS")
    if not credentials_json:
        raise ValueError("Google Sheets credentials are not set in the environment variables")
    creds_dict = json.loads(credentials_json)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client


def insert_prices(prices, client):
    sheet = client.open('Financial Position')
    sheet_instance = sheet.get_worksheet(1)
    formula = sheet_instance.get("C49", value_render_option=ValueRenderOption.formula)[0][0]
    last_number = re.findall(r'\d+', formula)[-2]
    string = '=('
    for price in prices:
        string += f"{int(price)}+"
    string += str(last_number) + ')/6'
    sheet_instance.update_acell("C49", string)


if __name__ == '__main__':
    client = authenticate_gs_client()
    values = scraper.scrape_all_house_prices()
    midpoints = [value[1] for value in values]
    insert_prices(midpoints, client)
