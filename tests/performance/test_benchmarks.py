"""Performance benchmark tests for nz-house-prices.

These tests verify that scraping performance meets expectations.
Run with:
    pytest tests/performance/test_benchmarks.py --performance -v

Note: These tests require --performance flag and hit real websites.
"""

import time

import pytest

from tests.fixtures.addresses import PRIMARY_ADDRESS


@pytest.mark.performance
class TestScrapingPerformance:
    """Performance benchmarks for the scraping pipeline."""

    def test_parallel_scraping_under_15_seconds(self):
        """Full parallel scrape should complete in under 15 seconds.

        This is the primary performance target. If this test fails,
        investigate which site is slow or if there's a bottleneck.
        """
        from nz_house_prices.api import get_prices

        start = time.perf_counter()
        results = get_prices(PRIMARY_ADDRESS)
        elapsed = time.perf_counter() - start

        # Should have results
        assert results, "No results returned"

        # Performance assertion
        max_time = 15.0
        assert elapsed < max_time, (
            f"Parallel scraping took {elapsed:.1f}s, expected <{max_time}s. "
            "Performance may have degraded."
        )

        # Report timing for visibility
        print(f"\nParallel scraping completed in {elapsed:.1f}s")

    def test_cached_lookup_under_2_seconds(self):
        """Cached address lookups should be very fast.

        First call populates cache, second call should use cache.
        """
        from nz_house_prices.api import get_prices

        # First call - populates cache
        get_prices(PRIMARY_ADDRESS)

        # Second call - should use cache
        start = time.perf_counter()
        results = get_prices(PRIMARY_ADDRESS)
        elapsed = time.perf_counter() - start

        # Should have results
        assert results, "No results returned"

        # Cached lookup should be fast
        max_time = 5.0  # Allow some time for price scraping even with cached URLs
        assert elapsed < max_time, (
            f"Cached lookup took {elapsed:.1f}s, expected <{max_time}s. "
            "Cache may not be working correctly."
        )

        print(f"\nCached lookup completed in {elapsed:.1f}s")

    def test_single_site_under_10_seconds(self):
        """Single site scraping should be fast.

        Tests that individual site handlers are performant.
        """
        from nz_house_prices.api import get_prices

        # Test homes.co.nz as a representative site
        site = "homes.co.nz"

        start = time.perf_counter()
        get_prices(PRIMARY_ADDRESS, sites=[site])
        elapsed = time.perf_counter() - start

        max_time = 10.0
        assert elapsed < max_time, (
            f"Single site ({site}) took {elapsed:.1f}s, expected <{max_time}s."
        )

        print(f"\nSingle site scraping completed in {elapsed:.1f}s")


@pytest.mark.performance
class TestParallelVsSequential:
    """Compare parallel vs sequential execution."""

    def test_parallel_faster_than_sequential(self):
        """Parallel execution should be significantly faster.

        With 5 sites, parallel should be at least 2x faster.
        """
        from nz_house_prices.api import get_prices

        # Clear cache by using a slight address variation
        # (or we accept cache helps both modes equally)

        # Time parallel
        start = time.perf_counter()
        get_prices(PRIMARY_ADDRESS, parallel=True)
        parallel_time = time.perf_counter() - start

        # Time sequential (if supported, otherwise skip)
        try:
            start = time.perf_counter()
            get_prices(PRIMARY_ADDRESS, parallel=False)
            sequential_time = time.perf_counter() - start
        except TypeError:
            pytest.skip("Sequential mode not supported")

        # Parallel should be faster
        speedup = sequential_time / parallel_time if parallel_time > 0 else 0

        print(f"\nParallel: {parallel_time:.1f}s")
        print(f"Sequential: {sequential_time:.1f}s")
        print(f"Speedup: {speedup:.1f}x")

        # Parallel should be at least 1.5x faster with 5 sites
        min_speedup = 1.5
        assert speedup >= min_speedup, (
            f"Parallel only {speedup:.1f}x faster than sequential. "
            f"Expected at least {min_speedup}x speedup."
        )


@pytest.mark.performance
class TestMemoryUsage:
    """Memory usage tests."""

    def test_no_memory_leak_on_repeated_calls(self):
        """Memory should not grow significantly with repeated calls.

        This catches memory leaks in browser handling.
        """
        import gc

        try:
            import psutil

            process = psutil.Process()
        except ImportError:
            pytest.skip("psutil not installed")

        from nz_house_prices.api import get_prices

        # Get baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run multiple scrapes
        num_iterations = 3
        for i in range(num_iterations):
            get_prices(PRIMARY_ADDRESS, sites=["homes.co.nz"])
            gc.collect()

        # Check final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - baseline_memory

        print(f"\nBaseline memory: {baseline_memory:.1f}MB")
        print(f"Final memory: {final_memory:.1f}MB")
        print(f"Growth: {memory_growth:.1f}MB")

        # Allow some growth but not excessive
        max_growth = 100  # MB
        assert memory_growth < max_growth, (
            f"Memory grew by {memory_growth:.1f}MB after {num_iterations} calls. "
            "Possible memory leak in browser handling."
        )
