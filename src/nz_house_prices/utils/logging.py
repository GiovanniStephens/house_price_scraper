"""Logging utilities for scraping operations."""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from nz_house_prices.models.results import ScrapingResult


class ScrapingLogger:
    """Logger for scraping operations with file and console output."""

    def __init__(self, log_file: str = "scraper.log"):
        """Initialize the scraping logger.

        Args:
            log_file: Path to the log file
        """
        logger_name = f"scraper_{log_file.replace('/', '_').replace('.', '_')}"
        self.logger = logging.getLogger(logger_name)

        # Clear any existing handlers to avoid duplication
        self.logger.handlers.clear()

        # Set level and format
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Prevent propagation to avoid double logging
        self.logger.propagate = False

    def log_extraction_attempt(
        self,
        site: str,
        selector_type: str,
        selector: str,
        success: bool,
        extracted_value: Optional[str] = None,
    ) -> None:
        """Log each selector attempt with detailed information.

        Args:
            site: The website being scraped
            selector_type: Type of selector used (css, xpath, etc.)
            selector: The selector string
            success: Whether extraction was successful
            extracted_value: The extracted value if successful
        """
        status = "SUCCESS" if success else "FAILED"
        emoji = "+" if success else "x"

        if success and extracted_value:
            self.logger.info(
                f"{emoji} {site} - {selector_type} - {status}: "
                f"Found '{extracted_value}' using {selector[:100]}"
            )
        else:
            self.logger.info(f"{emoji} {site} - {selector_type} - {status}: {selector[:100]}")

    def log_price_extraction(
        self,
        site: str,
        price_type: str,
        raw_value: str,
        formatted_value: float,
        method: str,
    ) -> None:
        """Log detailed price extraction information.

        Args:
            site: The website being scraped
            price_type: Type of price (midpoint, upper, lower)
            raw_value: Raw extracted value
            formatted_value: Formatted numeric value
            method: Extraction method used
        """
        self.logger.info(
            f"$ {site} - {price_type}: '{raw_value}' -> ${formatted_value:,.0f} (via {method})"
        )

    def log_scraping_result(self, result: "ScrapingResult") -> None:
        """Log comprehensive scraping result.

        Args:
            result: The scraping result to log
        """
        if result.success:
            price_summary = []
            for price_type in ["lower", "midpoint", "upper"]:
                price = result.prices.get(price_type)
                if price:
                    price_summary.append(f"{price_type}: ${price:,.0f}")
                else:
                    price_summary.append(f"{price_type}: None")

            self.logger.info(
                f"OK {result.site} SUCCESS: {' | '.join(price_summary)} "
                f"(methods: {result.extraction_method}) [{result.execution_time:.2f}s]"
            )
        else:
            self.logger.error(
                f"FAIL {result.site} FAILED: {'; '.join(result.errors[:3])} "
                f"[{result.execution_time:.2f}s]"
            )
