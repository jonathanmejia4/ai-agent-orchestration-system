#!/usr/bin/env python3
"""
Smoke Test Runner
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Testing Infrastructure

Runs quick smoke tests to verify basic functionality after deployment.
Performs lightweight health checks on critical paths.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

@dataclass
class TestResult:
    """Result of a single smoke test."""
    test_name: str
    passed: bool
    duration_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None

@dataclass
class SmokeTestReport:
    """Report of all smoke tests."""
    timestamp: str
    environment: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    total_duration_ms: float
    results: List[TestResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed_tests == 0

class SmokeTestRunner:
    """Runs smoke tests."""

    def __init__(
        self,
        environment: str = "local",
        config_path: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize runner.

        Args:
            environment: Target environment name
            config_path: Path to smoke test configuration
            base_url: Base URL for HTTP tests
            timeout: Default timeout in seconds
        """
        self.environment = environment
        self.base_url = base_url
        self.timeout = timeout
        self.tests: List[Callable[[], TestResult]] = []
        self.config: Dict[str, Any] = {}

        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

        self._register_default_tests()

    def _load_config(self, config_path: str):
        """Load test configuration."""
        try:
            import yaml
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            pass

    def _register_default_tests(self):
        """Register default smoke tests."""
        self.tests.append(self._test_file_system)
        self.tests.append(self._test_python_import)
        self.tests.append(self._test_git_available)
        self.tests.append(self._test_critical_files)

        if self.base_url:
            self.tests.append(self._test_http_health)

    def _run_test(self, test_func: Callable[[], TestResult]) -> TestResult:
        """Run a single test with timing."""
        start = time.time()
        try:
            result = test_func()
            result.duration_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return TestResult(
                test_name=test_func.__name__,
                passed=False,
                duration_ms=(time.time() - start) * 1000,
                message=f"Exception: {str(e)}"
            )

    def _test_file_system(self) -> TestResult:
        """Test file system access."""
        test_file = Path("/tmp/smoke_test_write_check")
        try:
            test_file.write_text("smoke test")
            content = test_file.read_text()
            test_file.unlink()

            if content == "smoke test":
                return TestResult(
                    test_name="file_system",
                    passed=True,
                    duration_ms=0,
                    message="File system read/write OK"
                )
            else:
                return TestResult(
                    test_name="file_system",
                    passed=False,
                    duration_ms=0,
                    message="File content mismatch"
                )
        except Exception as e:
            return TestResult(
                test_name="file_system",
                passed=False,
                duration_ms=0,
                message=f"File system error: {e}"
            )

    def _test_python_import(self) -> TestResult:
        """Test Python imports."""
        required_modules = ["json", "os", "sys", "pathlib"]
        failed = []

        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                failed.append(module)

        if failed:
            return TestResult(
                test_name="python_import",
                passed=False,
                duration_ms=0,
                message=f"Failed to import: {', '.join(failed)}"
            )

        return TestResult(
            test_name="python_import",
            passed=True,
            duration_ms=0,
            message=f"All {len(required_modules)} modules imported"
        )

    def _test_git_available(self) -> TestResult:
        """Test git is available."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return TestResult(
                    test_name="git_available",
                    passed=True,
                    duration_ms=0,
                    message=version
                )
            else:
                return TestResult(
                    test_name="git_available",
                    passed=False,
                    duration_ms=0,
                    message="Git command failed"
                )
        except Exception as e:
            return TestResult(
                test_name="git_available",
                passed=False,
                duration_ms=0,
                message=f"Git not available: {e}"
            )

    def _test_critical_files(self) -> TestResult:
        """Test critical files exist."""
        critical_files = self.config.get("critical_files", [
            "ISSUE_CATALOG.md",
            "PLANNING/",
        ])

        missing = []
        for file_path in critical_files:
            if not Path(file_path).exists():
                missing.append(file_path)

        if missing:
            return TestResult(
                test_name="critical_files",
                passed=False,
                duration_ms=0,
                message=f"Missing: {', '.join(missing)}"
            )

        return TestResult(
            test_name="critical_files",
            passed=True,
            duration_ms=0,
            message=f"All {len(critical_files)} critical files found"
        )

    def _test_http_health(self) -> TestResult:
        """Test HTTP health endpoint."""
        if not self.base_url:
            return TestResult(
                test_name="http_health",
                passed=True,
                duration_ms=0,
                message="Skipped (no base URL)"
            )

        health_endpoints = [
            "/health",
            "/healthz",
            "/api/health",
            "/"
        ]

        for endpoint in health_endpoints:
            try:
                url = f"{self.base_url.rstrip('/')}{endpoint}"
                request = urllib.request.Request(url)
                response = urllib.request.urlopen(request, timeout=self.timeout)

                if response.status < 400:
                    return TestResult(
                        test_name="http_health",
                        passed=True,
                        duration_ms=0,
                        message=f"{endpoint}: HTTP {response.status}"
                    )
            except Exception:
                continue

        return TestResult(
            test_name="http_health",
            passed=False,
            duration_ms=0,
            message="No healthy endpoint found"
        )

    def add_test(self, test_func: Callable[[], TestResult]):
        """Add a custom test."""
        self.tests.append(test_func)

    def run(self) -> SmokeTestReport:
        """Run all smoke tests."""
        start_time = time.time()
        results = []

        for test in self.tests:
            result = self._run_test(test)
            results.append(result)

        total_duration = (time.time() - start_time) * 1000

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        return SmokeTestReport(
            timestamp=datetime.now().isoformat(),
            environment=self.environment,
            total_tests=len(results),
            passed_tests=passed,
            failed_tests=failed,
            total_duration_ms=total_duration,
            results=results
        )

    def format_report(self, report: SmokeTestReport) -> str:
        """Format report for console output."""
        lines = [
            "=" * 60,
            f"Smoke Test Report - {report.environment}",
            "=" * 60,
            f"Timestamp: {report.timestamp}",
            f"Duration: {report.total_duration_ms:.2f}ms",
            f"Tests: {report.passed_tests}/{report.total_tests} passed",
            "",
        ]

        for result in report.results:
            status = "✅" if result.passed else "❌"
            lines.append(f"{status} {result.test_name}: {result.message} ({result.duration_ms:.1f}ms)")

        lines.append("")
        lines.append(f"Result: {'PASS' if report.success else 'FAIL'}")

        return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run smoke tests"
    )
    parser.add_argument("-e", "--environment", default="local",
                        help="Environment name")
    parser.add_argument("-c", "--config", help="Configuration file")
    parser.add_argument("-u", "--url", help="Base URL for HTTP tests")
    parser.add_argument("-t", "--timeout", type=int, default=30,
                        help="Timeout in seconds")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    runner = SmokeTestRunner(
        environment=args.environment,
        config_path=args.config,
        base_url=args.url,
        timeout=args.timeout
    )

    report = runner.run()

    if args.json:
        print(json.dumps({
            "timestamp": report.timestamp,
            "environment": report.environment,
            "success": report.success,
            "total_tests": report.total_tests,
            "passed": report.passed_tests,
            "failed": report.failed_tests,
            "duration_ms": report.total_duration_ms,
            "results": [
                {
                    "name": r.test_name,
                    "passed": r.passed,
                    "duration_ms": r.duration_ms,
                    "message": r.message
                }
                for r in report.results
            ]
        }, indent=2))
    else:
        print(runner.format_report(report))

    sys.exit(0 if report.success else 1)

if __name__ == "__main__":
    main()
