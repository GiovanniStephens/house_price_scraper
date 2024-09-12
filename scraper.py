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
            # Logic to find data on propertyvalue.co.nz
            midpoint_price = driver.find_element(By.CLASS_NAME, "property-value-class")  # Example class
            print(f"PropertyValue.co.nz price: {midpoint_price.text}")
        elif "realestate.co.nz" in url:
            # Logic to find data on realestate.co.nz
            midpoint_price = driver.find_element(By.CLASS_NAME, "realestate-price-class")  # Example class
            print(f"RealEstate.co.nz price: {midpoint_price.text}")
        elif "oneroof.co.nz" in url:
            # Logic to find data on oneroof.co.nz
            midpoint_price = driver.find_element(By.CLASS_NAME, "oneroof-price-class")  # Example class
            print(f"OneRoof.co.nz price: {midpoint_price.text}")
        else:
            print("No scraping logic for this URL")
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return midpoint_price, upper_price, lower_price


def main():
    config = load_config()
    urls = config["urls"]["house_price_estimates"]

    driver = init_driver()
    try:
        for url in urls:
            scrape_house_prices(driver, url)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
