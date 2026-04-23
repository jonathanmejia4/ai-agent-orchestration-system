#!/usr/bin/env python3
"""
gate_validator.py - Quality Gate Validation Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Quality Assurance

Purpose:
    Validates quality gates for the system agent workflows.
    Ensures pre/during/post implementation gates are met before proceeding.

Usage:
    python3 gate_validator.py --agent <agent> --gate <gate_type>
    python3 gate_validator.py --agent builder --work-order WO-2025-001
    python3 gate_validator.py --check-all --work-order WO-2025-001

Reference: .claude/guidelines/builder-scope-enforcement.md
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

# =============================================================================
# Configuration
# =============================================================================

class GateType(Enum):
    """Types of quality gates (aligned with gate_validation_schema.yaml)."""
    PRE_IMPLEMENTATION = "pre_implementation"
    DURING_IMPLEMENTATION = "during_implementation"
    POST_IMPLEMENTATION = "post_implementation"
    PRE_PROMOTION = "pre_promotion"
    PRE_DEPLOYMENT = "pre_deployment"
    POST_DEPLOYMENT = "post_deployment"
    # Legacy values for backwards compatibility
    PRE_REVIEW = "pre_review"
    POST_REVIEW = "post_review"
    PRE_MERGE = "pre_merge"
    PRE_COMMIT = "pre_commit"

class GateSeverity(Enum):
    """Severity levels for gate failures."""
    BLOCKING = "blocking"      # Cannot proceed
    WARNING = "warning"        # Can proceed with acknowledgment
    INFO = "info"              # Informational only

@dataclass
class GateCheck:
    """A single gate check."""
    name: str
    description: str
    check_fn: Callable[..., Tuple[bool, str]]
    severity: GateSeverity = GateSeverity.BLOCKING
    agent: Optional[str] = None  # If None, applies to all agents

@dataclass
class GateResult:
    """Result of a gate validation (aligned with gate_validation_schema.yaml)."""
    gate_type: str
    check_name: str
    passed: bool
    message: str
    severity: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    validation_id: str = field(default_factory=lambda: f"GATE-{datetime.utcnow().strftime('%Y%m%d')}-{hash(datetime.utcnow().isoformat()) % 1000:03d}")
    target_type: str = "task"
    target_identifier: str = ""

    @property
    def result(self) -> str:
        """Schema-compliant result value."""
        if self.passed:
            return "passed" if self.severity != "warning" else "passed_with_warnings"
        return "failed" if self.severity == "blocking" else "blocked"

    def to_dict(self) -> dict:
        """Return schema-compliant dict structure."""
        return {
            "validation_id": self.validation_id,
            "timestamp": self.timestamp,
            "gate_type": self.gate_type,
            "target": {
                "type": self.target_type,
                "identifier": self.target_identifier,
            },
            "result": self.result,
            "checks": [{
                "check_name": self.check_name,
                "passed": self.passed,
                "message": self.message,
                "severity": self.severity,
            }],
        }

    def to_legacy_dict(self) -> dict:
        """Return legacy format for backwards compatibility."""
        return {
            "gate_type": self.gate_type,
            "check_name": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }

@dataclass
class GateValidationReport:
    """Complete gate validation report."""
    agent: str
    work_order_id: Optional[str]
    gate_type: str
    results: List[GateResult]
    overall_passed: bool
    blocking_failures: int
    warnings: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "work_order_id": self.work_order_id,
            "gate_type": self.gate_type,
            "overall_passed": self.overall_passed,
            "blocking_failures": self.blocking_failures,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
            "results": [r.to_dict() for r in self.results],
        }

# =============================================================================
# Gate Check Functions
# =============================================================================

def check_work_order_exists(work_order_id: str, **kwargs) -> Tuple[bool, str]:
    """Check if work order exists in queue."""
    wo_queue_paths = [
        "LogBook/pm/WO_QUEUE.yaml",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
    ]

    for path in wo_queue_paths:
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                work_orders = data.get("work_orders", [])
                for wo in work_orders:
                    if wo.get("work_order_id") == work_order_id:
                        return True, f"Work order {work_order_id} found in {path}"
            except Exception as e:
                continue

    return False, f"Work order {work_order_id} not found in any queue"

def check_work_order_status(work_order_id: str, expected_status: str = "ASSIGNED", **kwargs) -> Tuple[bool, str]:
    """Check if work order has expected status."""
    wo_queue_paths = [
        "LogBook/pm/WO_QUEUE.yaml",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
    ]

    for path in wo_queue_paths:
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                work_orders = data.get("work_orders", [])
                for wo in work_orders:
                    if wo.get("work_order_id") == work_order_id:
                        status = wo.get("status", "UNKNOWN")
                        if status == expected_status:
                            return True, f"Work order status is {status}"
                        else:
                            return False, f"Work order status is {status}, expected {expected_status}"
            except Exception:
                continue

    return False, f"Could not verify work order status"

def check_task_assigned(work_order_id: str, **kwargs) -> Tuple[bool, str]:
    """Check if task_id is assigned in work order."""
    wo_queue_paths = [
        "LogBook/pm/WO_QUEUE.yaml",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
    ]

    for path in wo_queue_paths:
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                work_orders = data.get("work_orders", [])
                for wo in work_orders:
                    if wo.get("work_order_id") == work_order_id:
                        task_id = wo.get("task_id")
                        if task_id:
                            return True, f"Task {task_id} assigned"
                        else:
                            return False, "No task_id assigned to work order"
            except Exception:
                continue

    return False, "Could not verify task assignment"

def check_requirements_exist(work_order_id: str, **kwargs) -> Tuple[bool, str]:
    """Check if work order has requirements specified."""
    wo_queue_paths = [
        "LogBook/pm/WO_QUEUE.yaml",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
    ]

    for path in wo_queue_paths:
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                work_orders = data.get("work_orders", [])
                for wo in work_orders:
                    if wo.get("work_order_id") == work_order_id:
                        reqs = wo.get("requirements", [])
                        if reqs and len(reqs) > 0:
                            return True, f"Found {len(reqs)} requirements"
                        else:
                            return False, "No requirements specified"
            except Exception:
                continue

    return False, "Could not verify requirements"

def check_dependencies_met(work_order_id: str, **kwargs) -> Tuple[bool, str]:
    """Check if work order dependencies are met."""
    wo_queue_paths = [
        "LogBook/pm/WO_QUEUE.yaml",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
    ]

    for path in wo_queue_paths:
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                work_orders = data.get("work_orders", [])

                # Find our work order
                our_wo = None
                for wo in work_orders:
                    if wo.get("work_order_id") == work_order_id:
                        our_wo = wo
                        break

                if not our_wo:
                    continue

                deps = our_wo.get("dependencies", [])
                if not deps:
                    return True, "No dependencies to check"

                # Check each dependency
                unmet = []
                for dep_id in deps:
                    dep_met = False
                    for wo in work_orders:
                        if wo.get("work_order_id") == dep_id:
                            if wo.get("status") in ("COMPLETED", "CLOSED"):
                                dep_met = True
                                break
                    if not dep_met:
                        unmet.append(dep_id)

                if unmet:
                    return False, f"Unmet dependencies: {', '.join(unmet)}"
                else:
                    return True, f"All {len(deps)} dependencies met"

            except Exception as e:
                continue

    return True, "No dependencies found to check"

def check_tests_exist(task_id: str = None, **kwargs) -> Tuple[bool, str]:
    """Check if tests exist for the implementation."""
    test_paths = ["tests/", "test/"]

    if task_id:
        # Check for task-specific tests
        specific_paths = [
            f"tests/task{task_id}/",
            f"tests/{task_id}/",
            f"tests/integration/{task_id}/",
        ]
        for path in specific_paths:
            if Path(path).exists():
                test_files = list(Path(path).glob("test_*.py"))
                if test_files:
                    return True, f"Found {len(test_files)} test files in {path}"

    # Check for any tests
    for path in test_paths:
        if Path(path).exists():
            test_files = list(Path(path).rglob("test_*.py"))
            if test_files:
                return True, f"Found {len(test_files)} test files in {path}"

    return False, "No test files found"

def check_tests_pass(**kwargs) -> Tuple[bool, str]:
    """Run tests and check if they pass."""
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "-q", "--tb=no"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            # Parse output for test count
            match = re.search(r"(\d+) passed", result.stdout)
            count = match.group(1) if match else "?"
            return True, f"{count} tests passed"
        else:
            # Extract failure info
            match = re.search(r"(\d+) failed", result.stdout)
            failures = match.group(1) if match else "?"
            return False, f"{failures} tests failed"
    except subprocess.TimeoutExpired:
        return False, "Tests timed out after 5 minutes"
    except FileNotFoundError:
        return True, "pytest not available, skipping"
    except Exception as e:
        return False, f"Test execution error: {e}"

def check_no_lint_errors(**kwargs) -> Tuple[bool, str]:
    """Check for linting errors."""
    try:
        # Try ruff first
        result = subprocess.run(
            ["ruff", "check", "."],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return True, "No lint errors (ruff)"
        else:
            error_count = len(result.stdout.strip().split("\n"))
            return False, f"{error_count} lint errors found"
    except FileNotFoundError:
        # Try flake8
        try:
            result = subprocess.run(
                ["flake8", "--count", "--select=E9,F63,F7,F82", "--show-source", "--statistics", "."],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return True, "No critical lint errors (flake8)"
            else:
                return False, "Lint errors found"
        except FileNotFoundError:
            return True, "No linter available, skipping"
    except Exception as e:
        return False, f"Lint check error: {e}"

def check_no_secrets(**kwargs) -> Tuple[bool, str]:
    """Check for hardcoded secrets."""
    secret_patterns = [
        r'password\s*=\s*["\'][^"\']+["\']',
        r'api_key\s*=\s*["\'][^"\']+["\']',
        r'secret\s*=\s*["\'][^"\']+["\']',
        r'token\s*=\s*["\'][A-Za-z0-9]{20,}["\']',
        r'AWS_SECRET_ACCESS_KEY\s*=',
        r'PRIVATE_KEY\s*=',
    ]

    # Get staged files or all Python files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True
        )
        files = result.stdout.strip().split("\n")
        files = [f for f in files if f.endswith((".py", ".js", ".ts", ".yaml", ".yml"))]
    except:
        files = list(Path(".").rglob("*.py"))[:50]  # Limit for performance

    violations = []
    for file_path in files:
        if not file_path or not Path(file_path).exists():
            continue
        try:
            content = Path(file_path).read_text()
            for pattern in secret_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(file_path)
                    break
        except:
            continue

    if violations:
        return False, f"Potential secrets in: {', '.join(violations[:3])}"
    else:
        return True, "No hardcoded secrets detected"

def check_logbook_updated(agent: str, **kwargs) -> Tuple[bool, str]:
    """Check if agent's LogBook has recent entries."""
    logbook_path = Path(f"LogBook/{agent}")

    if not logbook_path.exists():
        return False, f"LogBook/{agent}/ directory not found"

    # Check for recent files
    recent_files = []
    cutoff = datetime.utcnow().timestamp() - 3600  # Within last hour

    for file_path in logbook_path.rglob("*"):
        if file_path.is_file():
            if file_path.stat().st_mtime > cutoff:
                recent_files.append(file_path.name)

    if recent_files:
        return True, f"Recent LogBook updates: {', '.join(recent_files[:3])}"
    else:
        return False, "No recent LogBook updates found"

def check_state_file_valid(agent: str, **kwargs) -> Tuple[bool, str]:
    """Check if agent's STATE.md exists and is valid."""
    state_path = Path(f"LogBook/{agent}/STATE.md")

    if not state_path.exists():
        return False, f"STATE.md not found for {agent}"

    content = state_path.read_text()
    if len(content) < 50:
        return False, "STATE.md is nearly empty"

    # Check for basic structure
    if "Current" in content or "Status" in content or "#" in content:
        return True, "STATE.md exists and has content"
    else:
        return False, "STATE.md may be malformed"

def check_no_pm_paths(agent: str, **kwargs) -> Tuple[bool, str]:
    """Check that non-PM agent is not modifying PM paths."""
    if agent == "pm":
        return True, "PM can modify PM paths"

    pm_paths = [
        "LogBook/pm/",
        "ISSUE_CATALOG.md",
        "PLANNING/MASTER_PLAN.md",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
    ]

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True
        )
        staged = result.stdout.strip().split("\n")

        violations = []
        for file_path in staged:
            for pm_path in pm_paths:
                if file_path.startswith(pm_path):
                    violations.append(file_path)

        if violations:
            return False, f"PM path violations: {', '.join(violations)}"
        else:
            return True, "No PM path violations"

    except Exception:
        return True, "Could not check staged files"

def check_critic_verdict_exists(work_order_id: str, **kwargs) -> Tuple[bool, str]:
    """Check if Critic has issued a verdict for work order."""
    verdict_paths = [
        "LogBook/critic/verdicts.yaml",
        "LogBook/critic/recent_verdict.yaml",
    ]

    for path in verdict_paths:
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                verdicts = data.get("verdicts", [data]) if isinstance(data, dict) else [data]
                for verdict in verdicts:
                    if verdict.get("work_order_id") == work_order_id:
                        status = verdict.get("verdict", "UNKNOWN")
                        return True, f"Verdict found: {status}"
            except:
                continue

    return False, f"No verdict found for {work_order_id}"

def check_critic_approved(work_order_id: str, **kwargs) -> Tuple[bool, str]:
    """Check if Critic has APPROVED the work order."""
    verdict_paths = [
        "LogBook/critic/verdicts.yaml",
        "LogBook/critic/recent_verdict.yaml",
    ]

    for path in verdict_paths:
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                verdicts = data.get("verdicts", [data]) if isinstance(data, dict) else [data]
                for verdict in verdicts:
                    if verdict.get("work_order_id") == work_order_id:
                        status = verdict.get("verdict", "UNKNOWN")
                        if status == "APPROVED":
                            return True, "Critic APPROVED the work"
                        else:
                            return False, f"Critic verdict is {status}, not APPROVED"
            except:
                continue

    return False, f"No APPROVED verdict found for {work_order_id}"

# =============================================================================
# Gate Definitions
# =============================================================================

class GateValidator:
    """Validates quality gates for agent workflows."""

    def __init__(self):
        self.gates: Dict[GateType, List[GateCheck]] = {
            GateType.PRE_IMPLEMENTATION: [
                GateCheck(
                    "work_order_exists",
                    "Work order must exist",
                    check_work_order_exists,
                    GateSeverity.BLOCKING,
                    "builder"
                ),
                GateCheck(
                    "work_order_assigned",
                    "Work order must be in ASSIGNED status",
                    lambda **kw: check_work_order_status(**kw, expected_status="ASSIGNED"),
                    GateSeverity.BLOCKING,
                    "builder"
                ),
                GateCheck(
                    "task_assigned",
                    "Task ID must be assigned",
                    check_task_assigned,
                    GateSeverity.BLOCKING,
                    "builder"
                ),
                GateCheck(
                    "requirements_exist",
                    "Requirements must be specified",
                    check_requirements_exist,
                    GateSeverity.BLOCKING,
                    "builder"
                ),
                GateCheck(
                    "dependencies_met",
                    "All dependencies must be met",
                    check_dependencies_met,
                    GateSeverity.BLOCKING,
                    "builder"
                ),
            ],
            GateType.DURING_IMPLEMENTATION: [
                GateCheck(
                    "no_pm_paths",
                    "Must not modify PM-exclusive paths",
                    check_no_pm_paths,
                    GateSeverity.BLOCKING,
                    "builder"
                ),
                GateCheck(
                    "no_secrets",
                    "Must not have hardcoded secrets",
                    check_no_secrets,
                    GateSeverity.BLOCKING
                ),
            ],
            GateType.POST_IMPLEMENTATION: [
                GateCheck(
                    "tests_exist",
                    "Tests must exist",
                    check_tests_exist,
                    GateSeverity.WARNING,
                    "builder"
                ),
                GateCheck(
                    "tests_pass",
                    "All tests must pass",
                    check_tests_pass,
                    GateSeverity.BLOCKING,
                    "builder"
                ),
                GateCheck(
                    "no_lint_errors",
                    "No lint errors",
                    check_no_lint_errors,
                    GateSeverity.WARNING
                ),
                GateCheck(
                    "logbook_updated",
                    "LogBook must be updated",
                    check_logbook_updated,
                    GateSeverity.WARNING,
                    "builder"
                ),
            ],
            GateType.PRE_REVIEW: [
                GateCheck(
                    "tests_pass",
                    "All tests must pass before review",
                    check_tests_pass,
                    GateSeverity.BLOCKING
                ),
                GateCheck(
                    "state_valid",
                    "Agent STATE.md must be valid",
                    check_state_file_valid,
                    GateSeverity.WARNING
                ),
            ],
            GateType.PRE_MERGE: [
                GateCheck(
                    "critic_verdict",
                    "Critic must have issued verdict",
                    check_critic_verdict_exists,
                    GateSeverity.BLOCKING
                ),
                GateCheck(
                    "critic_approved",
                    "Critic must have APPROVED",
                    check_critic_approved,
                    GateSeverity.BLOCKING
                ),
                GateCheck(
                    "tests_pass",
                    "All tests must pass",
                    check_tests_pass,
                    GateSeverity.BLOCKING
                ),
            ],
            GateType.PRE_COMMIT: [
                GateCheck(
                    "no_secrets",
                    "No hardcoded secrets",
                    check_no_secrets,
                    GateSeverity.BLOCKING
                ),
                GateCheck(
                    "no_pm_paths",
                    "Respect PM path boundaries",
                    check_no_pm_paths,
                    GateSeverity.BLOCKING
                ),
            ],
        }

    def validate_gate(
        self,
        gate_type: GateType,
        agent: str,
        work_order_id: Optional[str] = None,
        **kwargs
    ) -> GateValidationReport:
        """
        Validate all checks for a specific gate.

        Args:
            gate_type: The type of gate to validate
            agent: The agent performing the action
            work_order_id: Optional work order ID for context
            **kwargs: Additional context for checks

        Returns:
            GateValidationReport with all results
        """
        checks = self.gates.get(gate_type, [])
        results = []
        blocking_failures = 0
        warnings = 0

        # Prepare context
        context = {
            "agent": agent,
            "work_order_id": work_order_id,
            **kwargs
        }

        for check in checks:
            # Skip checks not applicable to this agent
            if check.agent and check.agent != agent and agent != "pm":
                continue

            try:
                passed, message = check.check_fn(**context)
            except Exception as e:
                passed = False
                message = f"Check error: {e}"

            result = GateResult(
                gate_type=gate_type.value,
                check_name=check.name,
                passed=passed,
                message=message,
                severity=check.severity.value
            )
            results.append(result)

            if not passed:
                if check.severity == GateSeverity.BLOCKING:
                    blocking_failures += 1
                elif check.severity == GateSeverity.WARNING:
                    warnings += 1

        return GateValidationReport(
            agent=agent,
            work_order_id=work_order_id,
            gate_type=gate_type.value,
            results=results,
            overall_passed=(blocking_failures == 0),
            blocking_failures=blocking_failures,
            warnings=warnings
        )

    def validate_all_gates(
        self,
        agent: str,
        work_order_id: Optional[str] = None,
        **kwargs
    ) -> List[GateValidationReport]:
        """Validate all gates for an agent."""
        reports = []
        for gate_type in GateType:
            report = self.validate_gate(gate_type, agent, work_order_id, **kwargs)
            reports.append(report)
        return reports

# =============================================================================
# CLI Interface
# =============================================================================

def print_report(report: GateValidationReport, verbose: bool = False):
    """Print a gate validation report."""
    # Header
    status_icon = "✓" if report.overall_passed else "✗"
    status_color = "\033[92m" if report.overall_passed else "\033[91m"
    reset = "\033[0m"

    print(f"\n{status_color}{status_icon}{reset} Gate: {report.gate_type}")
    print(f"   Agent: {report.agent}")
    if report.work_order_id:
        print(f"   Work Order: {report.work_order_id}")

    # Results
    for result in report.results:
        if result.passed:
            icon = "\033[92m✓\033[0m"
        elif result.severity == "warning":
            icon = "\033[93m⚠\033[0m"
        else:
            icon = "\033[91m✗\033[0m"

        print(f"   {icon} {result.check_name}: {result.message}")

    # Summary
    print(f"   ---")
    print(f"   Blocking failures: {report.blocking_failures}, Warnings: {report.warnings}")

def main():
    parser = argparse.ArgumentParser(
        description="Validate quality gates for the system agent workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Validate pre-implementation gates:
    %(prog)s --agent builder --gate pre_implementation --work-order WO-2025-001

  Validate all gates:
    %(prog)s --agent builder --check-all --work-order WO-2025-001

  Pre-commit validation:
    %(prog)s --agent builder --gate pre_commit

  Generate JSON report:
    %(prog)s --agent builder --gate post_implementation --json
        """
    )

    parser.add_argument(
        "--agent",
        required=True,
        choices=["pm", "builder", "critic", "planner"],
        help="Agent performing the action"
    )
    parser.add_argument(
        "--gate",
        choices=[g.value for g in GateType],
        help="Specific gate to validate"
    )
    parser.add_argument(
        "--work-order",
        help="Work order ID for context"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Check all gates"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error on any failure"
    )

    args = parser.parse_args()

    validator = GateValidator()

    if args.check_all:
        reports = validator.validate_all_gates(
            agent=args.agent,
            work_order_id=args.work_order
        )

        if args.json:
            output = {
                "agent": args.agent,
                "work_order_id": args.work_order,
                "reports": [r.to_dict() for r in reports]
            }
            print(json.dumps(output, indent=2))
        else:
            all_passed = True
            for report in reports:
                print_report(report, args.verbose)
                if not report.overall_passed:
                    all_passed = False

            print("\n" + "=" * 40)
            if all_passed:
                print("\033[92m✓ All gates passed\033[0m")
            else:
                print("\033[91m✗ Some gates failed\033[0m")

        # Exit code
        any_failed = any(not r.overall_passed for r in reports)
        return 1 if (any_failed and args.strict) else 0

    elif args.gate:
        gate_type = GateType(args.gate)
        report = validator.validate_gate(
            gate_type=gate_type,
            agent=args.agent,
            work_order_id=args.work_order
        )

        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print_report(report, args.verbose)

        return 1 if (not report.overall_passed and args.strict) else 0

    else:
        parser.print_help()
        return 2

if __name__ == "__main__":
    sys.exit(main())
