"""Unit tests for data models.

These tests verify the dataclasses and helper functions in models/results.py.
"""

import pytest

from nz_house_prices.models.results import (
    PriceEstimate,
    ScrapingMetrics,
    ScrapingResult,
    ValidationResult,
    calculate_metrics,
)


@pytest.mark.unit
class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Verify valid result creation."""
        result = ValidationResult(is_valid=True, value=1500000.0, error_message="")
        assert result.is_valid
        assert result.value == 1500000.0
        assert result.error_message == ""

    def test_invalid_result(self):
        """Verify invalid result creation."""
        result = ValidationResult(is_valid=False, value=None, error_message="Invalid price")
        assert not result.is_valid
        assert result.value is None
        assert result.error_message == "Invalid price"


@pytest.mark.unit
class TestScrapingResult:
    """Tests for ScrapingResult dataclass."""

    def test_creation(self, sample_scraping_result):
        """Verify ScrapingResult creation."""
        assert sample_scraping_result.site == "homes.co.nz"
        assert sample_scraping_result.success is True
        assert sample_scraping_result.prices["midpoint"] == 1500000.0

    def test_success_with_prices(self):
        """Verify success=True when prices exist."""
        result = ScrapingResult(
            site="test.co.nz",
            url="https://test.co.nz/property/123",
            success=True,
            prices={"midpoint": 1000000.0, "lower": None, "upper": None},
            errors=[],
            extraction_method="css",
            execution_time=1.5,
        )
        assert result.success

    def test_failure_without_prices(self):
        """Verify creation with no prices."""
        result = ScrapingResult(
            site="test.co.nz",
            url="https://test.co.nz/property/123",
            success=False,
            prices={"midpoint": None, "lower": None, "upper": None},
            errors=["No prices found"],
            extraction_method="",
            execution_time=2.0,
        )
        assert not result.success
        assert len(result.errors) == 1


@pytest.mark.unit
class TestPriceEstimate:
    """Tests for PriceEstimate dataclass."""

    def test_from_scraping_result(self, sample_scraping_result):
        """Verify creation from ScrapingResult."""
        estimate = PriceEstimate.from_scraping_result(sample_scraping_result)
        assert estimate.source == "homes.co.nz"
        assert estimate.midpoint == 1500000.0
        assert estimate.lower == 1400000.0
        assert estimate.upper == 1600000.0

    def test_has_range_true(self):
        """Verify has_range=True when lower and upper exist."""
        estimate = PriceEstimate(
            source="test.co.nz",
            midpoint=1500000.0,
            lower=1400000.0,
            upper=1600000.0,
        )
        assert estimate.has_range is True

    def test_has_range_false_no_lower(self):
        """Verify has_range=False when lower is missing."""
        estimate = PriceEstimate(
            source="test.co.nz",
            midpoint=1500000.0,
            lower=None,
            upper=1600000.0,
        )
        assert estimate.has_range is False

    def test_has_range_false_no_upper(self):
        """Verify has_range=False when upper is missing."""
        estimate = PriceEstimate(
            source="test.co.nz",
            midpoint=1500000.0,
            lower=1400000.0,
            upper=None,
        )
        assert estimate.has_range is False

    def test_has_range_false_only_midpoint(self):
        """Verify has_range=False with only midpoint."""
        estimate = PriceEstimate(
            source="test.co.nz",
            midpoint=1500000.0,
        )
        assert estimate.has_range is False

    def test_scraped_at_default(self):
        """Verify scraped_at defaults to current time."""
        estimate = PriceEstimate(source="test.co.nz")
        assert estimate.scraped_at is not None
        # Should be an ISO format string
        assert "T" in estimate.scraped_at


@pytest.mark.unit
class TestScrapingMetrics:
    """Tests for ScrapingMetrics dataclass."""

    def test_success_rate_all_success(self):
        """Verify success rate with all successful."""
        metrics = ScrapingMetrics(
            total_sites=5,
            successful_sites=5,
            failed_sites=0,
            total_execution_time=10.0,
            average_time_per_site=2.0,
            extraction_methods_used={"css": 5},
            error_summary={},
        )
        assert metrics.success_rate == 100.0

    def test_success_rate_partial(self):
        """Verify success rate with partial success."""
        metrics = ScrapingMetrics(
            total_sites=5,
            successful_sites=3,
            failed_sites=2,
            total_execution_time=10.0,
            average_time_per_site=2.0,
            extraction_methods_used={"css": 3},
            error_summary={"timeout": 2},
        )
        assert metrics.success_rate == 60.0

    def test_success_rate_zero_sites(self):
        """Verify success rate with zero sites."""
        metrics = ScrapingMetrics(
            total_sites=0,
            successful_sites=0,
            failed_sites=0,
            total_execution_time=0.0,
            average_time_per_site=0.0,
            extraction_methods_used={},
            error_summary={},
        )
        assert metrics.success_rate == 0.0


@pytest.mark.unit
class TestCalculateMetrics:
    """Tests for calculate_metrics() function."""

    def test_basic_metrics(self):
        """Verify basic metrics calculation."""
        results = [
            ScrapingResult(
                site="site1.co.nz",
                url="https://site1.co.nz/1",
                success=True,
                prices={"midpoint": 1000000.0},
                errors=[],
                extraction_method="css",
                execution_time=2.0,
            ),
            ScrapingResult(
                site="site2.co.nz",
                url="https://site2.co.nz/2",
                success=True,
                prices={"midpoint": 1500000.0},
                errors=[],
                extraction_method="xpath",
                execution_time=3.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert metrics.total_sites == 2
        assert metrics.successful_sites == 2
        assert metrics.failed_sites == 0
        assert metrics.total_execution_time == 5.0
        assert metrics.average_time_per_site == 2.5

    def test_mixed_success_failure(self):
        """Verify metrics with mixed success/failure."""
        results = [
            ScrapingResult(
                site="site1.co.nz",
                url="https://site1.co.nz/1",
                success=True,
                prices={"midpoint": 1000000.0},
                errors=[],
                extraction_method="css",
                execution_time=2.0,
            ),
            ScrapingResult(
                site="site2.co.nz",
                url="https://site2.co.nz/2",
                success=False,
                prices={"midpoint": None},
                errors=["timeout: Connection failed"],
                extraction_method="",
                execution_time=5.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert metrics.total_sites == 2
        assert metrics.successful_sites == 1
        assert metrics.failed_sites == 1
        assert metrics.error_summary == {"timeout": 1}

    def test_extraction_methods_counted(self):
        """Verify extraction methods are counted."""
        results = [
            ScrapingResult(
                site="site1.co.nz",
                url="https://site1.co.nz/1",
                success=True,
                prices={"midpoint": 1000000.0},
                errors=[],
                extraction_method="css,xpath",
                execution_time=2.0,
            ),
            ScrapingResult(
                site="site2.co.nz",
                url="https://site2.co.nz/2",
                success=True,
                prices={"midpoint": 1500000.0},
                errors=[],
                extraction_method="css",
                execution_time=3.0,
            ),
        ]

        metrics = calculate_metrics(results)

        assert metrics.extraction_methods_used["css"] == 2
        assert metrics.extraction_methods_used["xpath"] == 1

    def test_empty_results(self):
        """Verify handling of empty results list."""
        metrics = calculate_metrics([])

        assert metrics.total_sites == 0
        assert metrics.successful_sites == 0
        assert metrics.average_time_per_site == 0
