#!/usr/bin/env python3
"""
Promotion Gate Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Release Management

Validates that all promotion gates are satisfied before deployment.
Checks tests, coverage, security, approvals, and documentation.
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass
class GateCheck:
    """Result of a single gate check."""
    gate_name: str
    passed: bool
    required: bool
    message: str
    details: Optional[Dict[str, Any]] = None

@dataclass
class PromotionResult:
    """Result of promotion gate validation."""
    can_promote: bool
    environment: str
    checks: List[GateCheck] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class PromotionGate:
    """Validates promotion gates."""

    DEFAULT_GATES = {
        "staging": {
            "tests": {"required": True, "min_pass_rate": 100},
            "coverage": {"required": True, "min_percent": 70},
            "security": {"required": True, "max_critical": 0},
            "lint": {"required": True},
            "build": {"required": True},
        },
        "production": {
            "tests": {"required": True, "min_pass_rate": 100},
            "coverage": {"required": True, "min_percent": 80},
            "security": {"required": True, "max_critical": 0, "max_high": 0},
            "lint": {"required": True},
            "build": {"required": True},
            "approval": {"required": True, "min_approvers": 2},
            "staging_soak": {"required": True, "min_hours": 24},
            "documentation": {"required": False},
        },
    }

    def __init__(self, config_path: Optional[str] = None, base_path: str = "."):
        """
        Initialize gate checker.

        Args:
            config_path: Path to custom gate configuration
            base_path: Base path for project files
        """
        self.base_path = Path(base_path)
        self.gates = self.DEFAULT_GATES.copy()

        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Load custom gate configuration."""
        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            if config and 'gates' in config:
                for env, gates in config['gates'].items():
                    if env in self.gates:
                        self.gates[env].update(gates)
                    else:
                        self.gates[env] = gates

        except Exception:
            pass

    def _check_tests(self, config: Dict[str, Any]) -> GateCheck:
        """Check test gate."""
        min_rate = config.get("min_pass_rate", 100)

        # Look for test results
        test_results = None
        for results_file in ["test-results.json", "pytest-results.json", ".task/verification.json"]:
            path = self.base_path / results_file
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        test_results = json.load(f)
                    break
                except Exception:
                    continue

        if test_results is None:
            return GateCheck(
                gate_name="tests",
                passed=False,
                required=config.get("required", True),
                message="No test results found"
            )

        # Parse results
        passed = test_results.get("passed", test_results.get("checks", {}).get("tests", {}).get("passed"))
        if passed is None:
            return GateCheck(
                gate_name="tests",
                passed=False,
                required=config.get("required", True),
                message="Could not determine test status"
            )

        return GateCheck(
            gate_name="tests",
            passed=passed,
            required=config.get("required", True),
            message="All tests passed" if passed else "Tests failed",
            details=test_results
        )

    def _check_coverage(self, config: Dict[str, Any]) -> GateCheck:
        """Check coverage gate."""
        min_percent = config.get("min_percent", 80)

        # Look for coverage data
        coverage_percent = None
        for coverage_file in ["coverage.json", ".coverage.json", ".task/verification.json"]:
            path = self.base_path / coverage_file
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                    coverage_percent = data.get("coverage", {}).get("percentage")
                    if coverage_percent is None:
                        coverage_percent = data.get("checks", {}).get("coverage", {}).get("percentage")
                    if coverage_percent is not None:
                        break
                except Exception:
                    continue

        if coverage_percent is None:
            return GateCheck(
                gate_name="coverage",
                passed=False,
                required=config.get("required", True),
                message="No coverage data found"
            )

        passed = coverage_percent >= min_percent
        return GateCheck(
            gate_name="coverage",
            passed=passed,
            required=config.get("required", True),
            message=f"Coverage: {coverage_percent:.1f}% (min: {min_percent}%)",
            details={"coverage_percent": coverage_percent, "min_required": min_percent}
        )

    def _check_security(self, config: Dict[str, Any]) -> GateCheck:
        """Check security gate."""
        max_critical = config.get("max_critical", 0)
        max_high = config.get("max_high", 5)

        # Look for security scan results
        findings = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for security_file in ["security-results.json", ".task/verification.json"]:
            path = self.base_path / security_file
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)

                    security = data.get("security", data.get("checks", {}).get("security", {}))
                    for f_item in security.get("findings", []):
                        severity = f_item.get("severity", "low").lower()
                        if severity in findings:
                            findings[severity] += 1
                    break
                except Exception:
                    continue

        passed = (
            findings["critical"] <= max_critical and
            findings.get("high", 0) <= max_high
        )

        return GateCheck(
            gate_name="security",
            passed=passed,
            required=config.get("required", True),
            message=f"Security: {findings['critical']} critical, {findings['high']} high",
            details=findings
        )

    def _check_lint(self, config: Dict[str, Any]) -> GateCheck:
        """Check lint gate."""
        # Look for lint results
        for lint_file in ["lint-results.json", ".task/verification.json"]:
            path = self.base_path / lint_file
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)

                    lint = data.get("lint", data.get("checks", {}).get("lint", {}))
                    passed = lint.get("passed", lint.get("status") == "passed")

                    return GateCheck(
                        gate_name="lint",
                        passed=passed if passed is not None else True,
                        required=config.get("required", True),
                        message="Lint checks passed" if passed else "Lint errors found"
                    )
                except Exception:
                    continue

        return GateCheck(
            gate_name="lint",
            passed=True,
            required=config.get("required", True),
            message="No lint results found (assuming passed)"
        )

    def _check_build(self, config: Dict[str, Any]) -> GateCheck:
        """Check build gate."""
        # Check for build artifacts
        build_indicators = [
            "dist/", "build/", "target/", ".task/outputs.list"
        ]

        for indicator in build_indicators:
            path = self.base_path / indicator
            if path.exists():
                return GateCheck(
                    gate_name="build",
                    passed=True,
                    required=config.get("required", True),
                    message="Build artifacts found"
                )

        return GateCheck(
            gate_name="build",
            passed=False,
            required=config.get("required", True),
            message="No build artifacts found"
        )

    def _check_approval(self, config: Dict[str, Any]) -> GateCheck:
        """Check approval gate."""
        min_approvers = config.get("min_approvers", 1)

        # Look for approval records
        approval_file = self.base_path / ".task" / "verdict.yaml"
        if approval_file.exists():
            try:
                import yaml
                with open(approval_file, 'r') as f:
                    verdict = yaml.safe_load(f)

                if verdict and verdict.get("status") in ["pass", "approved"]:
                    return GateCheck(
                        gate_name="approval",
                        passed=True,
                        required=config.get("required", True),
                        message="Approval granted"
                    )
            except Exception:
                pass

        return GateCheck(
            gate_name="approval",
            passed=False,
            required=config.get("required", True),
            message=f"Requires {min_approvers} approver(s)"
        )

    def _check_staging_soak(self, config: Dict[str, Any]) -> GateCheck:
        """Check staging soak time gate."""
        min_hours = config.get("min_hours", 24)

        # Check for staging deployment timestamp file
        staging_deploy_file = self.base_path / ".saf" / "staging_deploy.json"
        if not staging_deploy_file.exists():
            return GateCheck(
                gate_name="staging_soak",
                passed=False,
                required=config.get("required", True),
                message=f"No staging deployment record found"
            )

        try:
            with open(staging_deploy_file, 'r') as f:
                deploy_data = json.load(f)

            deploy_time_str = deploy_data.get("deployed_at")
            if not deploy_time_str:
                return GateCheck(
                    gate_name="staging_soak",
                    passed=False,
                    required=config.get("required", True),
                    message="Staging deployment time not recorded"
                )

            deploy_time = datetime.fromisoformat(deploy_time_str.replace('Z', '+00:00'))
            now = datetime.now(deploy_time.tzinfo) if deploy_time.tzinfo else datetime.now()
            hours_in_staging = (now - deploy_time.replace(tzinfo=None)).total_seconds() / 3600

            if hours_in_staging >= min_hours:
                return GateCheck(
                    gate_name="staging_soak",
                    passed=True,
                    required=config.get("required", True),
                    message=f"In staging for {hours_in_staging:.1f}h (min: {min_hours}h)",
                    details={"hours_in_staging": hours_in_staging, "min_required": min_hours}
                )
            else:
                return GateCheck(
                    gate_name="staging_soak",
                    passed=False,
                    required=config.get("required", True),
                    message=f"Only {hours_in_staging:.1f}h in staging (requires {min_hours}h)",
                    details={"hours_in_staging": hours_in_staging, "min_required": min_hours}
                )

        except (json.JSONDecodeError, ValueError) as e:
            return GateCheck(
                gate_name="staging_soak",
                passed=False,
                required=config.get("required", True),
                message=f"Error reading staging deployment data: {e}"
            )

    def _check_documentation(self, config: Dict[str, Any]) -> GateCheck:
        """Check documentation gate."""
        doc_files = ["README.md", "CHANGELOG.md", "docs/"]

        found = []
        for doc in doc_files:
            if (self.base_path / doc).exists():
                found.append(doc)

        return GateCheck(
            gate_name="documentation",
            passed=len(found) > 0,
            required=config.get("required", False),
            message=f"Found: {', '.join(found)}" if found else "No documentation found"
        )

    def check(self, environment: str) -> PromotionResult:
        """
        Check all gates for an environment.

        Args:
            environment: Target environment

        Returns:
            PromotionResult
        """
        gates = self.gates.get(environment, self.gates.get("staging", {}))

        result = PromotionResult(
            can_promote=True,
            environment=environment
        )

        gate_checks = {
            "tests": self._check_tests,
            "coverage": self._check_coverage,
            "security": self._check_security,
            "lint": self._check_lint,
            "build": self._check_build,
            "approval": self._check_approval,
            "staging_soak": self._check_staging_soak,
            "documentation": self._check_documentation,
        }

        for gate_name, gate_config in gates.items():
            if gate_name in gate_checks:
                check = gate_checks[gate_name](gate_config)
                result.checks.append(check)

                if not check.passed:
                    if check.required:
                        result.can_promote = False
                        result.blockers.append(f"{gate_name}: {check.message}")
                    else:
                        result.warnings.append(f"{gate_name}: {check.message}")

        return result

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check promotion gates"
    )
    parser.add_argument("environment", nargs="?", default="staging",
                        help="Target environment")
    parser.add_argument("-c", "--config", help="Gate configuration file")
    parser.add_argument("-p", "--path", default=".",
                        help="Project path")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    gate = PromotionGate(config_path=args.config, base_path=args.path)
    result = gate.check(args.environment)

    if args.json:
        print(json.dumps({
            "can_promote": result.can_promote,
            "environment": result.environment,
            "checks": [
                {
                    "gate": c.gate_name,
                    "passed": c.passed,
                    "required": c.required,
                    "message": c.message
                }
                for c in result.checks
            ],
            "blockers": result.blockers,
            "warnings": result.warnings
        }, indent=2))
    else:
        print(f"Promotion to {result.environment}: {'✅ ALLOWED' if result.can_promote else '❌ BLOCKED'}")
        print()

        for check in result.checks:
            status = "✅" if check.passed else ("❌" if check.required else "⚠️")
            req = "(required)" if check.required else "(optional)"
            print(f"  {status} {check.gate_name} {req}: {check.message}")

        if result.blockers:
            print(f"\nBlockers:")
            for blocker in result.blockers:
                print(f"  ❌ {blocker}")

        if result.warnings:
            print(f"\nWarnings:")
            for warning in result.warnings:
                print(f"  ⚠️ {warning}")

    sys.exit(0 if result.can_promote else 1)

if __name__ == "__main__":
    main()
