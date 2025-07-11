import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import platform
import re


def load_config():
    with open("config.yml", "r") as file:
        return yaml.safe_load(file)


def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    system_architecture = platform.machine()
    if system_architecture == "x86_64":
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
    else:
        print(f"Unsupported architecture: {system_architecture}")
        return None
    return driver


def wait_for_page_load(driver, timeout=15):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
        )
    except Exception as e:
        print("Timeout waiting for page body to load.")


def safe_get(driver, url, retries=3, delay=5):
    for i in range(retries):
        try:
            driver.get(url)
            wait_for_page_load(driver)
            return True
        except Exception as e:
            print(f"Attempt {i+1} failed for URL: {url} with error: {e}")
            time.sleep(delay)
    raise Exception(f"Failed to load {url} after {retries} retries")


def scrape_oneroof_prices(driver):
    driver.implicitly_wait(10)
    midpoint_price = None
    upper_price = None
    lower_price = None
    try:
        # Try using CSS Selectors first
        midpoint_price = find_element_css(
            driver,
            "body > div.min-h-fill-screen.flex.flex-col > main > div.section-wrap.space-y-40.md\\:space-y-64.py-40.md\\:py-64 > section:nth-child(1) > div.mt-16.\\!mt-0 > div > section > aside.border.p-20.rounded-b-sm.md\\:border-0.md\\:p-0 > div > div.pt-110.pb-80.md\\:pt-80.md\\:pb-100 > div > div.text-center.font-medium.absolute.top-0.pt-10.left-1\\/2.-translate-x-1\\/2.hidden.md\\:block > div.text-3xl.font-bold.text-secondary.-mt-60.pb-22",
        )
        upper_price = find_element_css(
            driver,
            "body > div.min-h-fill-screen.flex.flex-col > main > div.section-wrap.space-y-40.md\\:space-y-64.py-40.md\\:py-64 > section:nth-child(1) > div.mt-16.\\!mt-0 > div > section > aside.border.p-20.rounded-b-sm.md\\:border-0.md\\:p-0 > div > div.pt-110.pb-80.md\\:pt-80.md\\:pb-100 > div > div.text-center.font-medium.absolute.top-0.pt-10.right-0 > div.text-base.md\\:text-xl",
        )
        lower_price = find_element_css(
            driver,
            "body > div.min-h-fill-screen.flex.flex-col > main > div.section-wrap.space-y-40.md\\:space-y-64.py-40.md\\:py-64 > section:nth-child(1) > div.mt-16.\\!mt-0 > div > section > aside.border.p-20.rounded-b-sm.md\\:border-0.md\\:p-0 > div > div.pt-110.pb-80.md\\:pt-80.md\\:pb-100 > div > div.text-center.font-medium.absolute.top-0.pt-10.left-0 > div.text-base.md\\:text-xl",
        )
        # If any price is not found via CSS, fall back to regex pattern
        if not midpoint_price or not upper_price or not lower_price:
            page_source = driver.page_source
            prices = find_prices_with_regex(page_source)
            if len(prices) >= 3:
                upper_price, midpoint_price, lower_price = prices[:3]
            else:
                raise Exception("Could not find enough price data using regex fallback")
        # Format the prices if found
        if midpoint_price:
            midpoint_price = format_oneroof_prices(midpoint_price)
        if upper_price:
            upper_price = format_oneroof_prices(upper_price)
        if lower_price:
            lower_price = format_oneroof_prices(lower_price)
    except Exception as e:
        print(f"Error scraping OneRoof: {e}")
    return midpoint_price, upper_price, lower_price


def scrape_realestate_co_nz(driver):
    driver.implicitly_wait(10)
    midpoint_price = None
    upper_price = None
    lower_price = None
    page_source = driver.page_source
    prices = find_prices_with_regex(page_source)[:3]
    formatted_prices = [format_realestate_prices(price) for price in prices]
    lower_price, midpoint_price, upper_price = formatted_prices[:3]
    return midpoint_price, upper_price, lower_price


def find_element_css(driver, selector):
    try:
        return driver.find_element(By.CSS_SELECTOR, selector).text
    except Exception:
        print(f"Failed to find element using CSS Selector: {selector}.")
        return None


def find_prices_with_regex(page_source):
    """Find prices in the format of $X.XM using regex."""
    pattern = re.compile(r"\$\d{1,3}(?:,\d{3})*(?:\.\d+)?M?")
    values = pattern.findall(page_source)
    return values


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
    driver.safe_get(url)
    driver.implicitly_wait(10)  # Adjust this based on page load times
    try:
        midpoint_price = None
        upper_price = None
        lower_price = None
        if "homes.co.nz" in url:
            midpoint_price = driver.find_element(
                By.XPATH,
                '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[1]/homes-price-tag-simple/div/span[2]',
            ).text
            lower_price = driver.find_element(
                By.XPATH,
                '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[2]/div/homes-price-tag-simple[1]/div/span[2]',
            ).text
            upper_price = driver.find_element(
                By.XPATH,
                '//*[@id="mat-tab-content-0-0"]/div/div[2]/div[1]/homes-hestimate-tab/div[2]/div/homes-price-tag-simple[2]/div/span[2]',
            ).text
            midpoint_price = format_homes_prices(midpoint_price)
            upper_price = format_homes_prices(upper_price)
            lower_price = format_homes_prices(lower_price)
        elif "qv.co.nz" in url:
            midpoint_price = driver.find_element(
                By.XPATH,
                '//*[@id="content"]/div/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div',
            ).text
            midpoint_price = format_qv_prices(midpoint_price)
        elif "propertyvalue.co.nz" in url:
            lower_price = driver.find_element(
                By.XPATH,
                '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[1]',
            ).text
            upper_price = driver.find_element(
                By.XPATH,
                '//*[@id="PropertyOverview"]/div/div[2]/div[4]/div[1]/div[2]/div[2]/div[2]',
            ).text
            lower_price = format_property_value_prices(lower_price)
            upper_price = format_property_value_prices(upper_price)
        elif "realestate.co.nz" in url:
            # Logic to find data on realestate.co.nz
            midpoint_price, upper_price, lower_price = scrape_realestate_co_nz(driver)
        elif "oneroof.co.nz" in url:
            # Logic to find data on oneroof.co.nz
            midpoint_price, upper_price, lower_price = scrape_oneroof_prices(driver)
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
