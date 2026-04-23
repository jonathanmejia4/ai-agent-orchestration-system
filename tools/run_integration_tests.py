#!/usr/bin/env python3
"""
Integration Test Runner for the system Tasks

Discovers and executes integration tests for specified tasks with multiple
output formats and test modes.

Usage:
    python3 tools/run_integration_tests.py --task-id 3.1 --mode full
    python3 tools/run_integration_tests.py --task-id 2.3 --mode quick --report-format markdown
    python3 tools/run_integration_tests.py --list-tests --task-id 3.1
    python3 tools/run_integration_tests.py --help

Exit Codes:
    0 - All tests passed
    1 - One or more tests failed
    2 - Error (test discovery failed, configuration error)

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from xml.etree import ElementTree as ET

# Optional YAML support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class TestResult:
    """Individual test result"""
    name: str
    status: str  # passed, failed, skipped, error
    duration: float = 0.0
    message: Optional[str] = None
    traceback: Optional[str] = None

@dataclass
class TestSuiteResult:
    """Test suite result"""
    task_id: str
    mode: str
    timestamp: str = ""
    duration: float = 0.0
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    tests: List[TestResult] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.errors == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'mode': self.mode,
            'timestamp': self.timestamp,
            'duration': self.duration,
            'total': self.total,
            'passed': self.passed,
            'failed': self.failed,
            'skipped': self.skipped,
            'errors': self.errors,
            'success': self.success,
            'tests': [asdict(t) for t in self.tests]
        }

class IntegrationTestRunner:
    """Integration test runner for the system tasks"""

    def __init__(self, repo_root: Optional[Path] = None,
                 mode: str = "full", verbose: bool = False):
        self.repo_root = repo_root or Path.cwd()
        self.mode = mode
        self.verbose = verbose
        self.tests_dir = self.repo_root / 'tests' / 'integration'
        self.common_dir = self.tests_dir / 'common'
        self.fixtures_dir = self.tests_dir / 'fixtures'

    def log(self, message: str):
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def discover_tests(self, task_id: str) -> List[Path]:
        """Discover integration tests for a task"""
        tests = []
        task_test_dir = self.tests_dir / task_id

        if not task_test_dir.exists():
            self.log(f"No test directory for task {task_id}")
            return tests

        # Find all test files
        for test_file in task_test_dir.glob("test_*.py"):
            tests.append(test_file)
        for test_file in task_test_dir.glob("*_test.py"):
            tests.append(test_file)

        # In quick mode, only run smoke tests
        if self.mode == "quick":
            tests = [t for t in tests if "smoke" in t.name or "basic" in t.name]
            if not tests:
                # If no smoke tests, just run first test file
                all_tests = list(task_test_dir.glob("test_*.py"))
                if all_tests:
                    tests = [all_tests[0]]

        return sorted(tests)

    def run_pytest(self, test_files: List[Path], task_id: str) -> TestSuiteResult:
        """Run tests using pytest"""
        result = TestSuiteResult(task_id=task_id, mode=self.mode)

        if not test_files:
            result.errors = 1
            result.tests.append(TestResult(
                name="test_discovery",
                status="error",
                message=f"No tests found for task {task_id}"
            ))
            return result

        # Build pytest command
        cmd = [
            sys.executable, "-m", "pytest",
            "--tb=short",
            "-v",
            "--junit-xml", str(self.repo_root / f"integration_results_{task_id}.xml")
        ]

        # Add test files
        for test_file in test_files:
            cmd.append(str(test_file))

        self.log(f"Running: {' '.join(cmd)}")

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.repo_root,
                timeout=300  # 5 minute timeout
            )
            result.duration = time.time() - start_time

            # Parse JUnit XML results if available
            junit_file = self.repo_root / f"integration_results_{task_id}.xml"
            if junit_file.exists():
                self._parse_junit_results(junit_file, result)
            else:
                # Fallback: parse pytest output
                self._parse_pytest_output(proc.stdout, proc.stderr, result)

        except subprocess.TimeoutExpired:
            result.duration = time.time() - start_time
            result.errors = 1
            result.tests.append(TestResult(
                name="test_execution",
                status="error",
                message="Test execution timed out (5 minutes)"
            ))
        except Exception as e:
            result.duration = time.time() - start_time
            result.errors = 1
            result.tests.append(TestResult(
                name="test_execution",
                status="error",
                message=str(e)
            ))

        return result

    def _parse_junit_results(self, junit_file: Path, result: TestSuiteResult):
        """Parse JUnit XML results"""
        try:
            tree = ET.parse(junit_file)
            root = tree.getroot()

            for testsuite in root.findall('.//testsuite'):
                result.total = int(testsuite.get('tests', 0))
                result.failures = int(testsuite.get('failures', 0))
                result.errors = int(testsuite.get('errors', 0))
                result.skipped = int(testsuite.get('skipped', 0))

            result.passed = result.total - result.failed - result.errors - result.skipped

            for testcase in root.findall('.//testcase'):
                test_result = TestResult(
                    name=testcase.get('name', 'unknown'),
                    status='passed',
                    duration=float(testcase.get('time', 0))
                )

                failure = testcase.find('failure')
                if failure is not None:
                    test_result.status = 'failed'
                    test_result.message = failure.get('message', '')
                    test_result.traceback = failure.text

                error = testcase.find('error')
                if error is not None:
                    test_result.status = 'error'
                    test_result.message = error.get('message', '')
                    test_result.traceback = error.text

                skipped = testcase.find('skipped')
                if skipped is not None:
                    test_result.status = 'skipped'
                    test_result.message = skipped.get('message', '')

                result.tests.append(test_result)

        except Exception as e:
            self.log(f"Error parsing JUnit XML: {e}")

    def _parse_pytest_output(self, stdout: str, stderr: str, result: TestSuiteResult):
        """Parse pytest output when JUnit XML not available"""
        # Simple parsing of pytest output
        for line in stdout.split('\n'):
            if ' passed' in line.lower():
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isdigit() and i + 1 < len(parts):
                            if 'passed' in parts[i + 1]:
                                result.passed = int(part)
                            elif 'failed' in parts[i + 1]:
                                result.failed = int(part)
                            elif 'error' in parts[i + 1]:
                                result.errors = int(part)
                            elif 'skipped' in parts[i + 1]:
                                result.skipped = int(part)
                except:
                    pass

        result.total = result.passed + result.failed + result.errors + result.skipped

    def run_tests(self, task_id: str) -> TestSuiteResult:
        """Run integration tests for a task"""
        self.log(f"Running integration tests for task {task_id}")

        # Discover tests
        test_files = self.discover_tests(task_id)
        self.log(f"Discovered {len(test_files)} test files")

        # Run tests
        result = self.run_pytest(test_files, task_id)

        return result

def format_junit(result: TestSuiteResult) -> str:
    """Format result as JUnit XML"""
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append(f'<testsuites name="integration-tests-{result.task_id}" '
               f'tests="{result.total}" failures="{result.failed}" '
               f'errors="{result.errors}" time="{result.duration:.3f}">')
    xml.append(f'  <testsuite name="{result.task_id}" tests="{result.total}" '
               f'failures="{result.failed}" errors="{result.errors}" '
               f'skipped="{result.skipped}" time="{result.duration:.3f}">')

    for test in result.tests:
        xml.append(f'    <testcase name="{test.name}" time="{test.duration:.3f}">')
        if test.status == 'failed':
            xml.append(f'      <failure message="{test.message or ""}">{test.traceback or ""}</failure>')
        elif test.status == 'error':
            xml.append(f'      <error message="{test.message or ""}">{test.traceback or ""}</error>')
        elif test.status == 'skipped':
            xml.append(f'      <skipped message="{test.message or ""}"/>')
        xml.append('    </testcase>')

    xml.append('  </testsuite>')
    xml.append('</testsuites>')
    return '\n'.join(xml)

def format_markdown(result: TestSuiteResult) -> str:
    """Format result as Markdown"""
    lines = [
        f"# Integration Test Results: Task {result.task_id}",
        "",
        f"**Mode:** {result.mode}",
        f"**Timestamp:** {result.timestamp}",
        f"**Duration:** {result.duration:.2f}s",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total | {result.total} |",
        f"| Passed | {result.passed} |",
        f"| Failed | {result.failed} |",
        f"| Errors | {result.errors} |",
        f"| Skipped | {result.skipped} |",
        "",
        f"**Status:** {'PASSED' if result.success else 'FAILED'}",
        "",
    ]

    if result.tests:
        lines.extend([
            "## Test Details",
            "",
            "| Test | Status | Duration |",
            "|------|--------|----------|"
        ])
        for test in result.tests:
            status_icon = {
                'passed': '',
                'failed': '',
                'error': '',
                'skipped': ''
            }.get(test.status, '')
            lines.append(f"| {test.name} | {status_icon} {test.status} | {test.duration:.2f}s |")

        # Show failures
        failures = [t for t in result.tests if t.status in ('failed', 'error')]
        if failures:
            lines.extend(["", "## Failures", ""])
            for test in failures:
                lines.extend([
                    f"### {test.name}",
                    "",
                    f"**Message:** {test.message or 'N/A'}",
                    ""
                ])
                if test.traceback:
                    lines.extend([
                        "```",
                        test.traceback,
                        "```",
                        ""
                    ])

    return '\n'.join(lines)

def print_result(result: TestSuiteResult, format: str = "text", output: Optional[Path] = None):
    """Print or save test result"""
    if format == "json":
        content = json.dumps(result.to_dict(), indent=2)
    elif format == "junit":
        content = format_junit(result)
    elif format == "markdown":
        content = format_markdown(result)
    else:
        # Text format
        lines = []
        if result.success:
            lines.append(f"\033[92m Integration tests PASSED for task {result.task_id}\033[0m")
        else:
            lines.append(f"\033[91m Integration tests FAILED for task {result.task_id}\033[0m")

        lines.extend([
            f"",
            f"Mode: {result.mode}",
            f"Duration: {result.duration:.2f}s",
            f"Total: {result.total}, Passed: {result.passed}, Failed: {result.failed}, "
            f"Errors: {result.errors}, Skipped: {result.skipped}",
        ])

        if result.tests:
            lines.append(f"\nTests:")
            for test in result.tests:
                status_icon = {
                    'passed': '',
                    'failed': '',
                    'error': '',
                    'skipped': ''
                }.get(test.status, ' ')
                lines.append(f"  {status_icon} {test.name} ({test.duration:.2f}s)")
                if test.message and test.status in ('failed', 'error'):
                    lines.append(f"     {test.message}")

        content = '\n'.join(lines)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        print(f"Results written to: {output}")
    else:
        print(content)

def main():
    parser = argparse.ArgumentParser(
        description='Integration test runner for the system tasks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run full integration tests for task 3.1
    %(prog)s --task-id 3.1 --mode full

    # Run quick smoke tests
    %(prog)s --task-id 3.1 --mode quick

    # Generate JUnit XML report
    %(prog)s --task-id 3.1 --report-format junit --output results.xml

    # Generate Markdown report
    %(prog)s --task-id 3.1 --report-format markdown --output results.md

Exit Codes:
    0 - All tests passed
    1 - One or more tests failed
    2 - Error
        """
    )

    parser.add_argument('--task-id', '-b', required=True,
                       help='Task ID to test')
    parser.add_argument('--mode', '-m', choices=['quick', 'full'], default='full',
                       help='Test mode: quick (smoke tests) or full (all tests)')
    parser.add_argument('--report-format', '-f',
                       choices=['text', 'json', 'junit', 'markdown'], default='text',
                       help='Report format')
    parser.add_argument('--output', '-o', type=Path,
                       help='Output file path')
    parser.add_argument('--list-tests', '-l', action='store_true',
                       help='List discovered tests without running')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd(),
                       help='Repository root')

    args = parser.parse_args()

    runner = IntegrationTestRunner(
        repo_root=args.repo_root,
        mode=args.mode,
        verbose=args.verbose
    )

    if args.list_tests:
        tests = runner.discover_tests(args.task_id)
        if tests:
            print(f"Discovered tests for task {args.task_id}:")
            for test in tests:
                print(f"  - {test.name}")
        else:
            print(f"No tests found for task {args.task_id}")
        sys.exit(0)

    result = runner.run_tests(args.task_id)
    print_result(result, args.report_format, args.output)

    sys.exit(0 if result.success else 1)

if __name__ == '__main__':
    main()
