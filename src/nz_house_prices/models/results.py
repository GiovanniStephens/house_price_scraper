"""Result dataclasses for scraping operations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ValidationResult:
    """Result of price validation."""

    is_valid: bool
    value: Optional[float] = None
    error_message: str = ""


@dataclass
class ScrapingResult:
    """Result of scraping a single URL."""

    site: str
    url: str
    success: bool
    prices: Dict[str, Optional[float]]
    errors: List[str]
    extraction_method: str
    execution_time: float


@dataclass
class PriceEstimate:
    """Price estimate from a single source."""

    source: str
    midpoint: Optional[float] = None
    lower: Optional[float] = None
    upper: Optional[float] = None
    confidence: Optional[str] = None
    scraped_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def has_range(self) -> bool:
        """Check if this estimate includes a price range."""
        return self.lower is not None and self.upper is not None

    @classmethod
    def from_scraping_result(cls, result: ScrapingResult) -> "PriceEstimate":
        """Create a PriceEstimate from a ScrapingResult."""
        return cls(
            source=result.site,
            midpoint=result.prices.get("midpoint"),
            lower=result.prices.get("lower"),
            upper=result.prices.get("upper"),
        )


@dataclass
class ScrapingMetrics:
    """Performance metrics from a scraping session."""

    total_sites: int
    successful_sites: int
    failed_sites: int
    total_execution_time: float
    average_time_per_site: float
    extraction_methods_used: Dict[str, int]
    error_summary: Dict[str, int]

    @property
    def success_rate(self) -> float:
        """Calculate the success rate as a percentage."""
        if self.total_sites == 0:
            return 0.0
        return (self.successful_sites / self.total_sites) * 100


def calculate_metrics(results: List[ScrapingResult]) -> ScrapingMetrics:
    """Calculate performance metrics from scraping results."""
    total_sites = len(results)
    successful_sites = sum(1 for r in results if r.success)
    failed_sites = total_sites - successful_sites
    total_time = sum(r.execution_time for r in results)

    methods: Dict[str, int] = {}
    errors: Dict[str, int] = {}

    for result in results:
        for method in result.extraction_method.split(","):
            if method:
                methods[method] = methods.get(method, 0) + 1

        for error in result.errors:
            error_type = error.split(":")[0] if ":" in error else error
            errors[error_type] = errors.get(error_type, 0) + 1

    return ScrapingMetrics(
        total_sites=total_sites,
        successful_sites=successful_sites,
        failed_sites=failed_sites,
        total_execution_time=total_time,
        average_time_per_site=total_time / total_sites if total_sites > 0 else 0,
        extraction_methods_used=methods,
        error_summary=errors,
    )
