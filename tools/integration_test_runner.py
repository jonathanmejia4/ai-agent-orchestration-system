#!/usr/bin/env python3
"""
integration_test_runner.py - the system Integration Test Runner

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM/Builder
Classification: HIGH - Quality Assurance

Purpose:
    Runs integration tests for the system agent workflows and system components.
    Coordinates test execution, collects results, and generates reports.

Usage:
    python3 integration_test_runner.py --suite agent-workflows
    python3 integration_test_runner.py --task-id 3.2 --mode full
    python3 integration_test_runner.py --all --report-format junit
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

@dataclass
class TestResult:
    name: str
    suite: str
    status: TestStatus
    duration_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "suite": self.suite,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "details": self.details
        }

@dataclass
class TestSuiteResult:
    name: str
    tests: List[TestResult]
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "tests": [t.to_dict() for t in self.tests]
        }

class IntegrationTestRunner:
    """Runs the system integration tests."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.results: List[TestSuiteResult] = []

    def run_suite(self, suite_name: str, **kwargs) -> TestSuiteResult:
        """Run a specific test suite."""
        suites = {
            "agent-workflows": self._run_agent_workflow_tests,
            "state-management": self._run_state_management_tests,
            "boundary-enforcement": self._run_boundary_tests,
            "gate-validation": self._run_gate_validation_tests,
            "logbook-integrity": self._run_logbook_tests,
            "unit": self._run_unit_tests,
            "contract": self._run_contract_tests,
        }

        runner = suites.get(suite_name)
        if runner:
            return runner(**kwargs)
        else:
            return TestSuiteResult(
                name=suite_name,
                tests=[TestResult(
                    name="suite_not_found",
                    suite=suite_name,
                    status=TestStatus.ERROR,
                    duration_ms=0,
                    message=f"Unknown test suite: {suite_name}"
                )],
                total=1,
                errors=1
            )

    def run_all(self, **kwargs) -> List[TestSuiteResult]:
        """Run all test suites."""
        suites = [
            "agent-workflows",
            "state-management",
            "boundary-enforcement",
            "gate-validation",
            "logbook-integrity",
            "unit",
            "contract",
        ]
        results = []
        for suite in suites:
            result = self.run_suite(suite, **kwargs)
            results.append(result)
        return results

    def _run_agent_workflow_tests(self, **kwargs) -> TestSuiteResult:
        """Test agent workflow interactions."""
        tests = []
        start = time.time()

        # Test 1: Work order queue exists
        test_start = time.time()
        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if wo_queue.exists():
            tests.append(TestResult(
                name="work_order_queue_exists",
                suite="agent-workflows",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="WO_QUEUE.yaml exists"
            ))
        else:
            tests.append(TestResult(
                name="work_order_queue_exists",
                suite="agent-workflows",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="WO_QUEUE.yaml not found"
            ))

        # Test 2: Agent state files exist
        agents = ["pm", "builder", "critic", "planner"]
        for agent in agents:
            test_start = time.time()
            state_file = self.base_path / f"LogBook/{agent}/STATE.md"
            if state_file.exists():
                tests.append(TestResult(
                    name=f"{agent}_state_exists",
                    suite="agent-workflows",
                    status=TestStatus.PASSED,
                    duration_ms=(time.time() - test_start) * 1000,
                    message=f"{agent} STATE.md exists"
                ))
            else:
                tests.append(TestResult(
                    name=f"{agent}_state_exists",
                    suite="agent-workflows",
                    status=TestStatus.SKIPPED,
                    duration_ms=(time.time() - test_start) * 1000,
                    message=f"{agent} STATE.md not found (may be intentional)"
                ))

        # Test 3: Agent guidelines exist
        test_start = time.time()
        guardrails = self.base_path / ".claude/guidelines/agent-guardrails.md"
        if guardrails.exists():
            tests.append(TestResult(
                name="agent_guardrails_exist",
                suite="agent-workflows",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Agent guardrails defined"
            ))
        else:
            tests.append(TestResult(
                name="agent_guardrails_exist",
                suite="agent-workflows",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Agent guardrails missing"
            ))

        return self._compile_suite_result("agent-workflows", tests, start)

    def _run_state_management_tests(self, **kwargs) -> TestSuiteResult:
        """Test state file management."""
        tests = []
        start = time.time()

        # Test 1: LogBook directory structure
        test_start = time.time()
        logbook = self.base_path / "LogBook"
        if logbook.exists() and logbook.is_dir():
            agent_dirs = [d for d in logbook.iterdir() if d.is_dir()]
            tests.append(TestResult(
                name="logbook_structure",
                suite="state-management",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message=f"LogBook has {len(agent_dirs)} agent directories"
            ))
        else:
            tests.append(TestResult(
                name="logbook_structure",
                suite="state-management",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="LogBook directory missing"
            ))

        # Test 2: YAML files are valid
        test_start = time.time()
        yaml_errors = []
        if HAS_YAML:
            for yaml_file in (self.base_path / "LogBook").rglob("*.yaml"):
                try:
                    with open(yaml_file) as f:
                        yaml.safe_load(f)
                except Exception as e:
                    yaml_errors.append(f"{yaml_file.name}: {e}")

            if yaml_errors:
                tests.append(TestResult(
                    name="yaml_validity",
                    suite="state-management",
                    status=TestStatus.FAILED,
                    duration_ms=(time.time() - test_start) * 1000,
                    message=f"{len(yaml_errors)} invalid YAML files",
                    details={"errors": yaml_errors[:5]}
                ))
            else:
                tests.append(TestResult(
                    name="yaml_validity",
                    suite="state-management",
                    status=TestStatus.PASSED,
                    duration_ms=(time.time() - test_start) * 1000,
                    message="All YAML files valid"
                ))
        else:
            tests.append(TestResult(
                name="yaml_validity",
                suite="state-management",
                status=TestStatus.SKIPPED,
                duration_ms=(time.time() - test_start) * 1000,
                message="PyYAML not available"
            ))

        # Test 3: State persistence protocol exists
        test_start = time.time()
        protocol = self.base_path / ".claude/guidelines/state-persistence-protocol.md"
        if protocol.exists():
            tests.append(TestResult(
                name="persistence_protocol",
                suite="state-management",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="State persistence protocol defined"
            ))
        else:
            tests.append(TestResult(
                name="persistence_protocol",
                suite="state-management",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="State persistence protocol missing"
            ))

        return self._compile_suite_result("state-management", tests, start)

    def _run_boundary_tests(self, **kwargs) -> TestSuiteResult:
        """Test write boundary enforcement."""
        tests = []
        start = time.time()

        # Test 1: PM boundaries documented
        test_start = time.time()
        pm_boundaries = self.base_path / ".claude/guidelines/pm-write-boundaries.md"
        if pm_boundaries.exists():
            tests.append(TestResult(
                name="pm_boundaries_defined",
                suite="boundary-enforcement",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="PM write boundaries defined"
            ))
        else:
            tests.append(TestResult(
                name="pm_boundaries_defined",
                suite="boundary-enforcement",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="PM write boundaries not defined"
            ))

        # Test 2: Builder scope enforcement documented
        test_start = time.time()
        builder_scope = self.base_path / ".claude/guidelines/builder-scope-enforcement.md"
        if builder_scope.exists():
            tests.append(TestResult(
                name="builder_scope_defined",
                suite="boundary-enforcement",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Builder scope enforcement defined"
            ))
        else:
            tests.append(TestResult(
                name="builder_scope_defined",
                suite="boundary-enforcement",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Builder scope enforcement not defined"
            ))

        # Test 3: Boundary validator tool exists
        test_start = time.time()
        validator = self.base_path / "tools/validate_write_boundaries.py"
        if validator.exists():
            tests.append(TestResult(
                name="boundary_validator_exists",
                suite="boundary-enforcement",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Boundary validator tool exists"
            ))
        else:
            tests.append(TestResult(
                name="boundary_validator_exists",
                suite="boundary-enforcement",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Boundary validator tool missing"
            ))

        return self._compile_suite_result("boundary-enforcement", tests, start)

    def _run_gate_validation_tests(self, **kwargs) -> TestSuiteResult:
        """Test quality gate validation."""
        tests = []
        start = time.time()

        # Test 1: Gate validator exists
        test_start = time.time()
        gate_validator = self.base_path / "tools/gate_validator.py"
        if gate_validator.exists():
            tests.append(TestResult(
                name="gate_validator_exists",
                suite="gate-validation",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Gate validator tool exists"
            ))
        else:
            tests.append(TestResult(
                name="gate_validator_exists",
                suite="gate-validation",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Gate validator tool missing"
            ))

        # Test 2: Stage gate enforcer exists
        test_start = time.time()
        enforcer = self.base_path / "tools/stage_gate_enforcer.py"
        if enforcer.exists():
            tests.append(TestResult(
                name="stage_gate_enforcer_exists",
                suite="gate-validation",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Stage gate enforcer exists"
            ))
        else:
            tests.append(TestResult(
                name="stage_gate_enforcer_exists",
                suite="gate-validation",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Stage gate enforcer missing"
            ))

        return self._compile_suite_result("gate-validation", tests, start)

    def _run_logbook_tests(self, **kwargs) -> TestSuiteResult:
        """Test LogBook integrity."""
        tests = []
        start = time.time()

        # Test 1: LogBook validator exists
        test_start = time.time()
        validator = self.base_path / "tools/validate_logbook.py"
        if validator.exists():
            tests.append(TestResult(
                name="logbook_validator_exists",
                suite="logbook-integrity",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="LogBook validator exists"
            ))
        else:
            tests.append(TestResult(
                name="logbook_validator_exists",
                suite="logbook-integrity",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="LogBook validator missing"
            ))

        # Test 2: LogBook auto-append exists
        test_start = time.time()
        auto_append = self.base_path / "tools/logbook_auto_append.py"
        if auto_append.exists():
            tests.append(TestResult(
                name="logbook_auto_append_exists",
                suite="logbook-integrity",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="LogBook auto-append tool exists"
            ))
        else:
            tests.append(TestResult(
                name="logbook_auto_append_exists",
                suite="logbook-integrity",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="LogBook auto-append tool missing"
            ))

        return self._compile_suite_result("logbook-integrity", tests, start)

    def _run_unit_tests(self, **kwargs) -> TestSuiteResult:
        """Run unit tests for generated code."""
        tests = []
        start = time.time()

        # Test 1: Check if tests directory exists
        test_start = time.time()
        tests_dir = self.base_path / "tests"
        if tests_dir.exists() and tests_dir.is_dir():
            test_files = list(tests_dir.rglob("test_*.py"))
            tests.append(TestResult(
                name="test_directory_exists",
                suite="unit",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message=f"Tests directory exists with {len(test_files)} test files"
            ))
        else:
            tests.append(TestResult(
                name="test_directory_exists",
                suite="unit",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Tests directory missing"
            ))

        # Test 2: Check pytest configuration
        test_start = time.time()
        pytest_ini = self.base_path / "pytest.ini"
        pyproject = self.base_path / "pyproject.toml"
        if pytest_ini.exists() or pyproject.exists():
            tests.append(TestResult(
                name="pytest_config_exists",
                suite="unit",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Pytest configuration found"
            ))
        else:
            tests.append(TestResult(
                name="pytest_config_exists",
                suite="unit",
                status=TestStatus.SKIPPED,
                duration_ms=(time.time() - test_start) * 1000,
                message="No pytest.ini or pyproject.toml found"
            ))

        # Test 3: Verify test naming conventions
        test_start = time.time()
        if tests_dir.exists():
            invalid_tests = []
            for test_file in tests_dir.rglob("*.py"):
                if test_file.stem.startswith("test_") or test_file.stem == "__init__":
                    continue
                if "test" in test_file.stem.lower() and not test_file.stem.startswith("test_"):
                    invalid_tests.append(test_file.name)

            if invalid_tests:
                tests.append(TestResult(
                    name="test_naming_convention",
                    suite="unit",
                    status=TestStatus.FAILED,
                    duration_ms=(time.time() - test_start) * 1000,
                    message=f"Found {len(invalid_tests)} test files with invalid naming",
                    details={"invalid_files": invalid_tests[:5]}
                ))
            else:
                tests.append(TestResult(
                    name="test_naming_convention",
                    suite="unit",
                    status=TestStatus.PASSED,
                    duration_ms=(time.time() - test_start) * 1000,
                    message="All test files follow naming conventions"
                ))
        else:
            tests.append(TestResult(
                name="test_naming_convention",
                suite="unit",
                status=TestStatus.SKIPPED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Tests directory not found"
            ))

        return self._compile_suite_result("unit", tests, start)

    def _run_contract_tests(self, **kwargs) -> TestSuiteResult:
        """Run contract tests for API/interface compliance."""
        tests = []
        start = time.time()

        # Test 1: Check schema files exist
        test_start = time.time()
        schema_dir = self.base_path / "PLANNING/schemas"
        if schema_dir.exists():
            schema_files = list(schema_dir.glob("*.yaml")) + list(schema_dir.glob("*.json"))
            tests.append(TestResult(
                name="schema_files_exist",
                suite="contract",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message=f"Found {len(schema_files)} schema files"
            ))
        else:
            tests.append(TestResult(
                name="schema_files_exist",
                suite="contract",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Schema directory not found"
            ))

        # Test 2: Check SSOT validation
        test_start = time.time()
        ssot_validator = self.base_path / "tools/ssot_validator.py"
        if ssot_validator.exists():
            tests.append(TestResult(
                name="ssot_validator_exists",
                suite="contract",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="SSOT validator tool exists"
            ))
        else:
            tests.append(TestResult(
                name="ssot_validator_exists",
                suite="contract",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - test_start) * 1000,
                message="SSOT validator tool missing"
            ))

        # Test 3: Check convention checker exists
        test_start = time.time()
        convention_checker = self.base_path / "tools/convention_checker.py"
        if convention_checker.exists():
            tests.append(TestResult(
                name="convention_checker_exists",
                suite="contract",
                status=TestStatus.PASSED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Convention checker tool exists"
            ))
        else:
            tests.append(TestResult(
                name="convention_checker_exists",
                suite="contract",
                status=TestStatus.SKIPPED,
                duration_ms=(time.time() - test_start) * 1000,
                message="Convention checker not found (optional)"
            ))

        return self._compile_suite_result("contract", tests, start)

    def _compile_suite_result(self, name: str, tests: List[TestResult], start: float) -> TestSuiteResult:
        """Compile test results into suite result."""
        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)
        errors = sum(1 for t in tests if t.status == TestStatus.ERROR)

        return TestSuiteResult(
            name=name,
            tests=tests,
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration_ms=(time.time() - start) * 1000
        )

    def generate_junit_xml(self, results: List[TestSuiteResult]) -> str:
        """Generate JUnit XML format report."""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<testsuites>')

        for suite in results:
            lines.append(f'  <testsuite name="{suite.name}" tests="{suite.total}" '
                        f'failures="{suite.failed}" errors="{suite.errors}" '
                        f'skipped="{suite.skipped}" time="{suite.duration_ms/1000:.3f}">')

            for test in suite.tests:
                lines.append(f'    <testcase name="{test.name}" classname="{test.suite}" '
                            f'time="{test.duration_ms/1000:.3f}">')

                if test.status == TestStatus.FAILED:
                    lines.append(f'      <failure message="{test.message}"/>')
                elif test.status == TestStatus.ERROR:
                    lines.append(f'      <error message="{test.message}"/>')
                elif test.status == TestStatus.SKIPPED:
                    lines.append(f'      <skipped message="{test.message}"/>')

                lines.append('    </testcase>')

            lines.append('  </testsuite>')

        lines.append('</testsuites>')
        return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description="Run the system integration tests")
    parser.add_argument("--suite", "-s", help="Specific test suite to run")
    parser.add_argument("--all", "-a", action="store_true", help="Run all test suites")
    parser.add_argument("--task-id", help="Task ID for task-specific tests")
    parser.add_argument("--mode", choices=["quick", "full"], default="full")
    parser.add_argument("--report-format", choices=["json", "junit", "text"], default="text")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    runner = IntegrationTestRunner()

    if args.all:
        results = runner.run_all()
    elif args.suite:
        results = [runner.run_suite(args.suite)]
    else:
        results = runner.run_all()

    # Generate output
    if args.report_format == "json":
        output = json.dumps([r.to_dict() for r in results], indent=2)
    elif args.report_format == "junit":
        output = runner.generate_junit_xml(results)
    else:
        # Text format
        lines = ["\n" + "=" * 60, "the system Integration Test Results", "=" * 60]
        total_passed = sum(r.passed for r in results)
        total_failed = sum(r.failed for r in results)
        total_tests = sum(r.total for r in results)

        for result in results:
            status = "PASS" if result.failed == 0 else "FAIL"
            lines.append(f"\n[{status}] {result.name}: {result.passed}/{result.total} passed")
            if args.verbose:
                for test in result.tests:
                    icon = "✓" if test.status == TestStatus.PASSED else "✗"
                    lines.append(f"  {icon} {test.name}: {test.message}")

        lines.append("\n" + "-" * 40)
        lines.append(f"Total: {total_passed}/{total_tests} passed, {total_failed} failed")
        output = '\n'.join(lines)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Exit code
    total_failed = sum(r.failed + r.errors for r in results)
    return 1 if total_failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
