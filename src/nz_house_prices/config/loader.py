"""Configuration loading and validation."""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from nz_house_prices.core.selectors import SELECTOR_STRATEGIES


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""

    pass


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration file structure and content.

    Args:
        config: Configuration dictionary to validate

    Returns:
        True if configuration is valid

    Raises:
        ConfigurationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ConfigurationError("Configuration must be a dictionary")

    if "urls" not in config:
        raise ConfigurationError("Configuration must contain 'urls' section")

    if "house_price_estimates" not in config["urls"]:
        raise ConfigurationError("Configuration must contain 'urls.house_price_estimates' section")

    urls = config["urls"]["house_price_estimates"]
    if not isinstance(urls, list):
        raise ConfigurationError("'house_price_estimates' must be a list")

    if len(urls) == 0:
        raise ConfigurationError("'house_price_estimates' cannot be empty")

    # Validate each URL
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    supported_sites = set(SELECTOR_STRATEGIES.keys())
    found_sites = set()

    for url in urls:
        if not isinstance(url, str):
            raise ConfigurationError(f"All URLs must be strings, found: {type(url)}")

        if not url_pattern.match(url):
            raise ConfigurationError(f"Invalid URL format: {url}")

        # Check if URL is for a supported site
        site_found = False
        for site in supported_sites:
            if site in url:
                found_sites.add(site)
                site_found = True
                break

        if not site_found:
            logging.warning(f"URL {url} does not match any supported sites: {supported_sites}")

    # Validate that we have strategies for all sites in config
    missing_strategies = found_sites - supported_sites
    if missing_strategies:
        raise ConfigurationError(f"No selector strategies defined for sites: {missing_strategies}")

    return True


def find_config_file(config_path: Optional[str] = None) -> Path:
    """Find configuration file with precedence.

    Args:
        config_path: Optional explicit config path

    Returns:
        Path to configuration file

    Raises:
        ConfigurationError: If no config file found
    """
    if config_path:
        path = Path(config_path)
        if path.exists():
            return path
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    # Check current directory
    local_config = Path("config.yml")
    if local_config.exists():
        return local_config

    # Check user config directory
    home_config = Path.home() / ".config" / "nz_house_prices" / "config.yml"
    if home_config.exists():
        return home_config

    # Check XDG config directory
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg_config_home:
        xdg_config = Path(xdg_config_home) / "nz_house_prices" / "config.yml"
        if xdg_config.exists():
            return xdg_config

    raise ConfigurationError(
        "Configuration file 'config.yml' not found. "
        "Expected locations: ./config.yml or ~/.config/nz_house_prices/config.yml"
    )


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and validate configuration file.

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Validated configuration dictionary

    Raises:
        ConfigurationError: If configuration is invalid or not found
    """
    try:
        config_file = find_config_file(config_path)
        with open(config_file, "r") as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        raise ConfigurationError("Configuration file 'config.yml' not found")
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML syntax in config.yml: {e}")

    validate_config(config)
    return config


def get_urls_from_config(config_path: Optional[str] = None) -> List[str]:
    """Get list of URLs from configuration.

    Args:
        config_path: Optional explicit path to config file

    Returns:
        List of property URLs
    """
    config = load_config(config_path)
    return config["urls"]["house_price_estimates"]
