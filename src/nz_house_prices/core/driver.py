"""Browser management for Playwright-based automation."""

from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


class BrowserManager:
    """Manages Playwright browser instances."""

    def __init__(self, headless: bool = True):
        """Initialize the browser manager.

        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None

    def start(self) -> Browser:
        """Start the browser.

        Returns:
            Browser instance
        """
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
        return self._browser

    def new_context(self) -> BrowserContext:
        """Create a new browser context.

        Returns:
            BrowserContext instance
        """
        browser = self.start()
        user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=user_agent,
        )

    def new_page(self) -> Page:
        """Create a new page in a new context.

        Returns:
            Page instance
        """
        context = self.new_context()
        return context.new_page()

    def close(self) -> None:
        """Close the browser and cleanup."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> "BrowserManager":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


def create_page(headless: bool = True) -> Page:
    """Create a new page with a fresh browser context.

    This is a convenience function for simple use cases.
    For multiple pages, use BrowserManager directly.

    Args:
        headless: Whether to run browser in headless mode

    Returns:
        Page instance (caller must close the browser context when done)
    """
    manager = BrowserManager(headless=headless)
    manager.start()
    return manager.new_page()
