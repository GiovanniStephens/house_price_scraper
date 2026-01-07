"""WebDriver management for cross-platform browser automation."""

import platform
from typing import Tuple

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class UnsupportedPlatformError(Exception):
    """Raised when platform is not supported."""

    pass


# Cache ChromeDriver path to avoid repeated HTTP checks
_cached_driver_path: str = None


def init_driver(headless: bool = True) -> WebDriver:
    """Initialize WebDriver with cross-platform support.

    Args:
        headless: Whether to run browser in headless mode

    Returns:
        Configured WebDriver instance

    Raises:
        UnsupportedPlatformError: If platform is not supported
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    global _cached_driver_path

    system_arch = platform.machine().lower()
    system_os = platform.system().lower()

    # Cache ChromeDriver path to avoid repeated HTTP checks
    if _cached_driver_path is None and system_os in ["linux", "darwin", "windows"]:
        if system_os == "linux" and system_arch in ["aarch64", "arm64"]:
            pass  # ARM Linux doesn't use ChromeDriverManager
        else:
            _cached_driver_path = ChromeDriverManager().install()

    if system_os == "linux":
        if system_arch in ["x86_64", "amd64"]:
            driver = webdriver.Chrome(
                service=Service(_cached_driver_path), options=options
            )
        elif system_arch in ["aarch64", "arm64"]:
            options.binary_location = "/usr/bin/chromium-browser"
            driver = webdriver.Chrome(options=options)
        else:
            driver = webdriver.Chrome(options=options)
    elif system_os == "darwin":  # macOS
        driver = webdriver.Chrome(
            service=Service(_cached_driver_path), options=options
        )
    elif system_os == "windows":
        driver = webdriver.Chrome(
            service=Service(_cached_driver_path), options=options
        )
    else:
        raise UnsupportedPlatformError(f"Unsupported platform: {system_os}-{system_arch}")

    return driver


def check_driver_health(driver: WebDriver) -> bool:
    """Check if driver is still responsive.

    Args:
        driver: WebDriver instance to check

    Returns:
        True if driver is healthy, False otherwise
    """
    try:
        driver.current_url
        return True
    except Exception:
        return False


def ensure_driver_health(driver: WebDriver) -> WebDriver:
    """Ensure driver is healthy, recreate if needed.

    Args:
        driver: WebDriver instance to check

    Returns:
        Healthy WebDriver instance (original or new)
    """
    if not check_driver_health(driver):
        try:
            driver.quit()
        except Exception:
            pass
        return init_driver()
    return driver


def wait_for_element(
    driver: WebDriver, selector: Tuple[str, str], timeout: int = 15
) -> any:
    """Wait for element with specified timeout.

    Args:
        driver: WebDriver instance
        selector: Tuple of (By, selector_string)
        timeout: Maximum wait time in seconds

    Returns:
        Located element
    """
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.presence_of_element_located(selector))
