"""Pytest configuration and shared fixtures for nz-house-prices tests."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run extended live tests with multiple addresses",
    )
    parser.addoption(
        "--performance",
        action="store_true",
        default=False,
        help="Run performance benchmark tests",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live and performance tests unless explicitly enabled."""
    if not config.getoption("--live"):
        skip_live = pytest.mark.skip(reason="Need --live option to run")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)

    if not config.getoption("--performance"):
        skip_perf = pytest.mark.skip(reason="Need --performance option to run")
        for item in items:
            if "performance" in item.keywords:
                item.add_marker(skip_perf)


# =============================================================================
# Test Address Fixtures
# =============================================================================


@pytest.fixture
def test_address() -> str:
    """Primary test address: 66 Pacific Road, North New Brighton."""
    return "66 Pacific Road, North New Brighton, Christchurch"


@pytest.fixture
def test_addresses() -> dict:
    """Collection of diverse NZ test addresses."""
    return {
        "christchurch_coastal": "66 Pacific Road, North New Brighton, Christchurch",
        "christchurch_central": "227 Worcester Street, City Centre, Christchurch",
        "christchurch_unit": "2/677 Worcester Street, Linwood, Christchurch",
        "auckland": "10 Queen Street, Auckland CBD",
        "wellington": "111 The Terrace, Wellington",
    }


# =============================================================================
# Mock Playwright Fixtures (for unit tests)
# =============================================================================


@pytest.fixture
def mock_page():
    """Create a mock Playwright Page object."""
    page = MagicMock()
    page.is_closed.return_value = False
    page.url = "https://example.com"
    page.content.return_value = "<html><body>Mock content</body></html>"

    # Mock locator that returns empty by default
    mock_locator = MagicMock()
    mock_locator.count.return_value = 0
    mock_locator.all.return_value = []
    mock_locator.first = MagicMock()
    mock_locator.first.text_content.return_value = None
    page.locator.return_value = mock_locator

    return page


@pytest.fixture
def mock_browser():
    """Create a mock Playwright Browser object."""
    browser = MagicMock()
    context = MagicMock()
    page = MagicMock()

    browser.new_context.return_value = context
    context.new_page.return_value = page
    page.is_closed.return_value = False

    return browser


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory that's cleaned up after test."""
    temp_dir = Path(tempfile.mkdtemp(prefix="nz_house_prices_test_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file."""
    import yaml

    config_data = {
        "urls": {
            "house_price_estimates": [
                "https://homes.co.nz/address/test/123",
                "https://www.qv.co.nz/property/test/456",
            ]
        }
    }
    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


# =============================================================================
# HTML Fixture Loading
# =============================================================================


@pytest.fixture
def html_fixtures_path() -> Path:
    """Path to HTML fixtures directory."""
    return Path(__file__).parent / "fixtures" / "html"


@pytest.fixture
def load_html_fixture(html_fixtures_path):
    """Factory fixture to load HTML fixtures by name."""

    def _load(filename: str) -> str:
        filepath = html_fixtures_path / filename
        if filepath.exists():
            return filepath.read_text()
        raise FileNotFoundError(f"HTML fixture not found: {filepath}")

    return _load


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_scraping_result():
    """Create a sample ScrapingResult for testing."""
    from nz_house_prices.models.results import ScrapingResult

    return ScrapingResult(
        site="homes.co.nz",
        url="https://homes.co.nz/address/test/123",
        success=True,
        prices={"midpoint": 1500000.0, "lower": 1400000.0, "upper": 1600000.0},
        errors=[],
        extraction_method="xpath,css",
        execution_time=2.5,
    )


@pytest.fixture
def sample_price_estimate():
    """Create a sample PriceEstimate for testing."""
    from nz_house_prices.models.results import PriceEstimate

    return PriceEstimate(
        source="homes.co.nz",
        midpoint=1500000.0,
        lower=1400000.0,
        upper=1600000.0,
    )
