#!/usr/bin/env python3
"""
Comprehensive test runner for the house price scraper.
Runs different test suites based on requirements and flags.
"""

import sys
import subprocess
import argparse
import time
from pathlib import Path


def run_test_suite(test_file, description, run_args=None):
    """Run a specific test suite and return results"""
    print(f"\n{'=' * 60}")
    print(f"Running {description}")
    print(f"{'=' * 60}")

    cmd = ["python", "-m", "pytest", test_file, "-v"]
    if run_args:
        cmd.extend(run_args)

    start_time = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start_time

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        success = result.returncode == 0
        return {
            "name": description,
            "file": test_file,
            "success": success,
            "duration": duration,
            "return_code": result.returncode,
        }
    except Exception as e:
        duration = time.time() - start_time
        print(f"Error running {test_file}: {e}")
        return {
            "name": description,
            "file": test_file,
            "success": False,
            "duration": duration,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Run house price scraper tests")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only quick tests (skip live website tests)",
    )
    parser.add_argument(
        "--live", action="store_true", help="Run live website tests (requires internet)"
    )
    parser.add_argument(
        "--performance", action="store_true", help="Run performance tests"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all tests including live website tests"
    )
    parser.add_argument(
        "--requirements-only",
        action="store_true",
        help="Run only requirements validation tests",
    )

    args = parser.parse_args()

    # Determine which tests to run
    test_suites = []

    if args.requirements_only:
        test_suites = [("test_requirements.py", "Requirements Validation Tests")]
    elif args.quick:
        test_suites = [
            ("test_requirements.py", "Requirements Validation Tests"),
            ("test_current_scraper.py", "Current Functionality Tests"),
            (
                "test_real_world.py::TestConfigurationValidation",
                "Config Validation Tests",
            ),
            ("test_real_world.py::TestPriceValidationReal", "Price Validation Tests"),
            ("test_real_world.py::TestSelectorStrategyReal", "Selector Strategy Tests"),
        ]
    elif args.live:
        test_suites = [("test_live_websites.py", "Live Website Tests", ["--run-live"])]
    elif args.performance:
        test_suites = [("test_real_world.py::TestPerformance", "Performance Tests")]
    elif args.all:
        test_suites = [
            ("test_requirements.py", "Requirements Validation Tests"),
            ("test_current_scraper.py", "Current Functionality Tests"),
            ("test_real_world.py", "Real-World Functionality Tests"),
            ("test_live_websites.py", "Live Website Tests", ["--run-live"]),
        ]
    else:
        # Default: comprehensive but no live tests
        test_suites = [
            ("test_requirements.py", "Requirements Validation Tests"),
            ("test_current_scraper.py", "Current Functionality Tests"),
            ("test_real_world.py", "Real-World Functionality Tests"),
        ]

    # Check that test files exist
    missing_files = []
    for suite in test_suites:
        test_file = suite[0].split("::")[0]  # Remove class specification
        if not Path(test_file).exists():
            missing_files.append(test_file)

    if missing_files:
        print(f"Error: Missing test files: {missing_files}")
        return 1

    # Run tests
    results = []
    total_start_time = time.time()

    for suite in test_suites:
        test_file = suite[0]
        description = suite[1]
        run_args = suite[2] if len(suite) > 2 else None

        result = run_test_suite(test_file, description, run_args)
        results.append(result)

    total_duration = time.time() - total_start_time

    # Summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print(f"{'=' * 60}")

    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed

    for result in results:
        status = "PASS" if result["success"] else "FAIL"
        duration = result["duration"]
        print(f"{status:4} | {duration:6.2f}s | {result['name']}")

    print("\nOverall Results:")
    print(f"  Test suites run: {len(results)}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total time: {total_duration:.2f}s")

    if failed > 0:
        print("\nFailed test suites:")
        for result in results:
            if not result["success"]:
                print(
                    f"  - {result['name']} (exit code: {result.get('return_code', 'unknown')})"
                )

    # Exit with appropriate code
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
