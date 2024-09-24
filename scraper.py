import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import platform


def load_config():
    with open("config.yml", "r") as file:
        return yaml.safe_load(file)


def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    system_architecture = platform.machine()
    if system_architecture == 'x86_64':
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    else:
        print(f"Unsupported architecture: {system_architecture}")
        return None
    return driver


def format_homes_prices(price):
    price = price.replace("M", "")
    price = float(price) * 1000000
    return price


def format_qv_prices(price):
    price = price.replace("$", "")
    price = price.replace(",", "")
    price = price.replace("QV: ", "")
    price = float(price)
    return price


def format_property_value_prices(price):
    price = price.replace("$", "")
    price = format_homes_prices(price)
    return price


def format_realestate_prices(price):
    price = format_property_value_prices(price)
    return price


def format_oneroof_prices(price):
    price = format_property_value_prices(price)
    return price


def scrape_house_prices(driver, url):
    print(f"Scraping data from: {url}")
    driver.get(url)
    driver.implicitly_wait(10)  # Adjust this based on page load times
    try:
        midpoint_price = None
        upper_price = None
        lower_price = None
        if "homes.co.nz" in url:
            midpoint_price = driver.find_element(By.XPATH, '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]').text
            upper_price = driver.find_element(By.XPATH, '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[2]/div/homes-price-tag-simple[1]/div/span[2]').text
            lower_price = driver.find_element(By.XPATH, '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[2]/div/homes-price-tag-simple[2]/div/span[2]').text
            midpoint_price = format_homes_prices(midpoint_price)
            upper_price = format_homes_prices(upper_price)
            lower_price = format_homes_prices(lower_price)
        elif "qv.co.nz" in url:
            midpoint_price = driver.find_element(By.XPATH, '//*[@id="content"]/div/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div').text
            midpoint_price = format_qv_prices(midpoint_price)
        elif "propertyvalue.co.nz" in url:
            lower_price = driver.find_element(By.XPATH, '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[1]').text
            upper_price = driver.find_element(By.XPATH, '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[2]').text
            lower_price = format_property_value_prices(lower_price)
            upper_price = format_property_value_prices(upper_price)
            midpoint_price = (lower_price + upper_price) / 2
        elif "realestate.co.nz" in url:
            lower_price = driver.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[1]/section[1]/div[2]/div[1]/div[1]/div/div[1]/h4').text
            midpoint_price = driver.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[1]/section[1]/div[2]/div[1]/div[1]/div/div[2]/h4').text
            upper_price = driver.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[1]/section[1]/div[2]/div[1]/div[1]/div/div[3]/h4').text
            lower_price = format_realestate_prices(lower_price)
            midpoint_price = format_realestate_prices(midpoint_price)
            upper_price = format_realestate_prices(upper_price)
        elif "oneroof.co.nz" in url:
            # Logic to find data on oneroof.co.nz
            lower_price = driver.find_element(By.XPATH, '/html/body/div[2]/main/div[5]/section[1]/div[2]/div/section/aside[1]/div/div[1]/div/div[2]/div[1]').text
            midpoint_price = driver.find_element(By.XPATH, '/html/body/div[2]/main/div[5]/section[1]/div[2]/div/section/aside[1]/div/div[1]/div/div[4]/div[1]').text
            upper_price = driver.find_element(By.XPATH, '/html/body/div[2]/main/div[5]/section[1]/div[2]/div/section/aside[1]/div/div[1]/div/div[3]/div[1]').text
            lower_price = format_oneroof_prices(lower_price)
            midpoint_price = format_oneroof_prices(midpoint_price)
            upper_price = format_oneroof_prices(upper_price)
        else:
            print("No scraping logic for this URL")
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return midpoint_price, upper_price, lower_price


def scrape_all_house_prices():
    config = load_config()
    urls = config["urls"]["house_price_estimates"]

    driver = init_driver()
    lower_price = None
    upper_price = None
    midpoint_price = None
    values = []
    try:
        for url in urls:
            midpoint_price, upper_price, lower_price = scrape_house_prices(driver, url)
            # Print the results
            print(f"Midpoint Price: {midpoint_price}")
            print(f"Upper Price: {upper_price}")
            print(f"Lower Price: {lower_price}")
            values.append([lower_price, midpoint_price, upper_price])
    finally:
        driver.quit()
    return values


if __name__ == "__main__":
    scrape_all_house_prices()
