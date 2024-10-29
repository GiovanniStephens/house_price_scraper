# House Price Scraper

This repository provides a web scraping solution for gathering real estate price estimates from various property websites in New Zealand, including `homes.co.nz`, `qv.co.nz`, `realestate.co.nz`, `oneroof.co.nz`, and `propertyvalue.co.nz`. The scraped data includes midpoint, upper, and lower price estimates, which can be formatted and directly integrated into financial management tools like Google Sheets.

## Overview

The scraper uses `Selenium` and `WebDriver Manager` to automate browser interaction for each target website. It is configured to run in a headless Chrome browser environment, making it suitable for running on servers or in the background. The URLs for target sites are loaded from a `config.yml` file, providing flexibility to manage and update the list of sites without code modifications.

Key features:
- Scrapes house price estimates from multiple real estate websites.
- Automatically formats price data for easy integration into Google Sheets or other financial management tools.
- Uses CSS selectors and regex for reliable data extraction across different HTML structures.

## Table of Contents
- [Setup](#setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Functions](#functions)
- [Dependencies](#dependencies)

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd house_price_scraper
   ```

2. **Install dependencies**:
   This project requires Python 3.8+ and `pip`. To install the required packages, run:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a config file**:
   Define your target URLs in a `config.yml` file. Example:
   ```yaml
    urls:
      house_price_estimates:
       - "https://www.homes.co.nz/address"
       - "https://www.qv.co.nz/address"
       - "https://www.realestate.co.nz/address"
       - "https://www.oneroof.co.nz/address"
       - "https://www.propertyvalue.co.nz/address"
   ```

## Usage

1. **Run the scraper**:
   Execute the script to start scraping all URLs listed in the configuration:
   ```bash
   python scraper.py
   ```
   This will print the midpoint, upper, and lower prices for each URL.

2. **View Results**:
   The script will print price data for each URL directly to the console. Modify the code to save results to a file or integrate directly with Google Sheets.

## Functions

- **`load_config()`**: Loads scraping URLs from `config.yml`.
- **`init_driver()`**: Initializes the Selenium WebDriver with Chrome in headless mode.
- **`scrape_house_prices(driver, url)`**: Detects the target website and scrapes prices, returning `(midpoint_price, upper_price, lower_price)`.
- **`format_*_prices()`**: A set of helper functions to standardise price formats for each website, including `homes.co.nz`, `qv.co.nz`, `realestate.co.nz`, `oneroof.co.nz`, and `propertyvalue.co.nz`.
- **`scrape_all_house_prices()`**: Iterates through URLs in `config.yml`, runs scraping, and prints results.

## Dependencies

This project relies on:
- `PyYAML` for configuration file management.
- `Selenium` and `webdriver_manager` for browser automation.
- `re` for regex-based data extraction.

Install these dependencies with `pip install -r requirements.txt`.

## Future Improvements

- Extend price extraction methods to improve resilience against site layout changes.
- Save results to a database to create a timeseries of the average price estimate over time.
