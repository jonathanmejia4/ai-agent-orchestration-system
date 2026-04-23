#!/usr/bin/env python3
"""
Test Runner
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Quality Assurance

Unified test runner for the system projects with reporting and coverage.

Usage:
    python tools/test_runner.py
    python tools/test_runner.py --unit
    python tools/test_runner.py --integration
    python tools/test_runner.py --coverage
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    status: str  # passed, failed, skipped, error
    duration: float
    message: Optional[str] = None

@dataclass
class TestSuiteResult:
    """Result of a test suite."""
    name: str
    tests_run: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    results: List[TestResult]

@dataclass
class TestReport:
    """Complete test report."""
    timestamp: str
    total_suites: int
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    coverage_percent: Optional[float]
    suites: List[TestSuiteResult]
    passed_all: bool

class TestRunner:
    """Runs tests and generates reports."""

    def __init__(self, tests_dir: Path = None):
        self.tests_dir = tests_dir or Path("tests")
        self.suites: List[TestSuiteResult] = []

    def run_pytest(
        self,
        path: Path = None,
        markers: List[str] = None,
        coverage: bool = False,
        verbose: bool = False
    ) -> TestSuiteResult:
        """Run tests using pytest."""
        path = path or self.tests_dir
        start_time = time.time()

        cmd = ["python", "-m", "pytest", str(path)]

        if markers:
            for marker in markers:
                cmd.extend(["-m", marker])

        if coverage:
            cmd.extend(["--cov=tools", "--cov-report=json"])

        if verbose:
            cmd.append("-v")

        cmd.append("--tb=short")
        cmd.append("-q")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            duration = time.time() - start_time

            # Parse output
            tests_run, passed, failed, skipped, errors = self._parse_pytest_output(result.stdout)

            return TestSuiteResult(
                name=str(path),
                tests_run=tests_run,
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors,
                duration=duration,
                results=[]  # Detailed results would require JSON output
            )

        except subprocess.TimeoutExpired:
            return TestSuiteResult(
                name=str(path),
                tests_run=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                duration=300,
                results=[TestResult(
                    name="timeout",
                    status="error",
                    duration=300,
                    message="Test execution timed out"
                )]
            )
        except FileNotFoundError:
            return TestSuiteResult(
                name=str(path),
                tests_run=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=1,
                duration=0,
                results=[TestResult(
                    name="setup",
                    status="error",
                    duration=0,
                    message="pytest not found"
                )]
            )

    def _parse_pytest_output(self, output: str) -> tuple:
        """Parse pytest output for test counts."""
        import re

        tests_run = 0
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        # Look for summary line like "5 passed, 2 failed, 1 skipped"
        summary_match = re.search(
            r'(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+skipped|(\d+)\s+error',
            output
        )

        if summary_match:
            # Parse all counts from output
            passed_match = re.search(r'(\d+)\s+passed', output)
            failed_match = re.search(r'(\d+)\s+failed', output)
            skipped_match = re.search(r'(\d+)\s+skipped', output)
            error_match = re.search(r'(\d+)\s+error', output)

            if passed_match:
                passed = int(passed_match.group(1))
            if failed_match:
                failed = int(failed_match.group(1))
            if skipped_match:
                skipped = int(skipped_match.group(1))
            if error_match:
                errors = int(error_match.group(1))

            tests_run = passed + failed + skipped + errors

        return tests_run, passed, failed, skipped, errors

    def run_unit_tests(self) -> TestSuiteResult:
        """Run unit tests."""
        unit_dir = self.tests_dir / "unit"
        if unit_dir.exists():
            return self.run_pytest(unit_dir, markers=["unit"])
        return self.run_pytest(self.tests_dir, markers=["unit"])

    def run_integration_tests(self) -> TestSuiteResult:
        """Run integration tests."""
        integration_dir = self.tests_dir / "integration"
        if integration_dir.exists():
            return self.run_pytest(integration_dir, markers=["integration"])
        return self.run_pytest(self.tests_dir, markers=["integration"])

    def run_all_tests(self, coverage: bool = False) -> TestReport:
        """Run all tests."""
        start_time = time.time()
        suites = []

        # Run all tests
        result = self.run_pytest(coverage=coverage)
        suites.append(result)

        duration = time.time() - start_time

        # Get coverage if available
        coverage_percent = None
        if coverage:
            coverage_percent = self._get_coverage()

        return self._generate_report(suites, duration, coverage_percent)

    def _get_coverage(self) -> Optional[float]:
        """Get coverage percentage from coverage.json."""
        coverage_file = Path("coverage.json")
        if coverage_file.exists():
            try:
                with open(coverage_file) as f:
                    data = json.load(f)
                return data.get("totals", {}).get("percent_covered", 0)
            except Exception:
                pass
        return None

    def _generate_report(
        self,
        suites: List[TestSuiteResult],
        duration: float,
        coverage_percent: Optional[float]
    ) -> TestReport:
        """Generate test report."""
        total_tests = sum(s.tests_run for s in suites)
        passed = sum(s.passed for s in suites)
        failed = sum(s.failed for s in suites)
        skipped = sum(s.skipped for s in suites)
        errors = sum(s.errors for s in suites)

        passed_all = failed == 0 and errors == 0

        return TestReport(
            timestamp=datetime.now().isoformat(),
            total_suites=len(suites),
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration=duration,
            coverage_percent=coverage_percent,
            suites=suites,
            passed_all=passed_all
        )

def format_text(report: TestReport) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Test Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Duration: {report.duration:.2f}s")
    lines.append("")
    lines.append(f"Total Tests: {report.total_tests}")
    lines.append(f"Passed: {report.passed}")
    lines.append(f"Failed: {report.failed}")
    lines.append(f"Skipped: {report.skipped}")
    lines.append(f"Errors: {report.errors}")
    lines.append("")

    if report.coverage_percent is not None:
        lines.append(f"Coverage: {report.coverage_percent:.1f}%")
        lines.append("")

    status = "PASSED" if report.passed_all else "FAILED"
    icon = "✓" if report.passed_all else "✗"
    lines.append(f"{icon} Status: {status}")
    lines.append("")

    for suite in report.suites:
        lines.append(f"Suite: {suite.name}")
        lines.append(f"  Tests: {suite.tests_run}, Passed: {suite.passed}, Failed: {suite.failed}")
        lines.append(f"  Duration: {suite.duration:.2f}s")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: TestReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "duration": report.duration,
        "total_tests": report.total_tests,
        "passed": report.passed,
        "failed": report.failed,
        "skipped": report.skipped,
        "errors": report.errors,
        "coverage_percent": report.coverage_percent,
        "passed_all": report.passed_all,
        "suites": [asdict(s) for s in report.suites]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Run tests and generate reports"
    )

    parser.add_argument(
        "--unit",
        action="store_true",
        help="Run only unit tests"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run only integration tests"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=Path("tests"),
        help="Tests directory"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file"
    )

    args = parser.parse_args()

    runner = TestRunner(args.tests_dir)

    if args.unit:
        suite = runner.run_unit_tests()
        report = runner._generate_report([suite], suite.duration, None)
    elif args.integration:
        suite = runner.run_integration_tests()
        report = runner._generate_report([suite], suite.duration, None)
    else:
        report = runner.run_all_tests(coverage=args.coverage)

    # Format output
    if args.format == "json":
        output = format_json(report)
    else:
        output = format_text(report)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    sys.exit(0 if report.passed_all else 1)

if __name__ == "__main__":
    main()
