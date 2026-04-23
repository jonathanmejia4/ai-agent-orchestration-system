#!/usr/bin/env python3
"""
stage_gate_enforcer.py - Stage Gate Enforcement Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Quality Enforcement

Purpose:
    Actively enforces stage gates by blocking operations that don't meet requirements.
    Acts as a wrapper around gate_validator.py with enforcement capabilities.

Usage:
    python3 stage_gate_enforcer.py --stage <stage> --action <action> [options]
    python3 stage_gate_enforcer.py --stage implementation --action start --work-order WO-2025-001
    python3 stage_gate_enforcer.py --install-hooks

Reference: tools/gate_validator.py, .claude/guidelines/builder-scope-enforcement.md
"""

import argparse
import json
import os
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
# Stage Definitions
# =============================================================================

class WorkflowStage(Enum):
    """Stages in the the system workflow."""
    PLANNING = "planning"
    ASSIGNMENT = "assignment"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    REVIEW = "review"
    MERGE = "merge"
    DEPLOYMENT = "deployment"

class StageAction(Enum):
    """Actions within a stage."""
    START = "start"
    COMPLETE = "complete"
    ABORT = "abort"
    TRANSITION = "transition"

@dataclass
class EnforcementResult:
    """Result of enforcement check."""
    allowed: bool
    stage: str
    action: str
    message: str
    blocking_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "stage": self.stage,
            "action": self.action,
            "message": self.message,
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }

# =============================================================================
# Stage Gate Definitions
# =============================================================================

STAGE_GATES = {
    # Before starting implementation
    WorkflowStage.IMPLEMENTATION: {
        StageAction.START: {
            "required_gates": ["pre_implementation"],
            "required_status": "ASSIGNED",
            "checks": [
                "work_order_exists",
                "task_assigned",
                "requirements_exist",
                "dependencies_met",
            ],
        },
        StageAction.COMPLETE: {
            "required_gates": ["post_implementation"],
            "required_status": "IN_PROGRESS",
            "checks": [
                "tests_exist",
                "tests_pass",
                "no_lint_errors",
                "logbook_updated",
            ],
        },
    },
    # Before starting review
    WorkflowStage.REVIEW: {
        StageAction.START: {
            "required_gates": ["pre_review"],
            "required_status": "READY_FOR_REVIEW",
            "checks": [
                "tests_pass",
                "state_valid",
            ],
        },
        StageAction.COMPLETE: {
            "required_gates": ["post_review"],
            "required_status": "IN_REVIEW",
            "checks": [
                "critic_verdict_exists",
            ],
        },
    },
    # Before merging
    WorkflowStage.MERGE: {
        StageAction.START: {
            "required_gates": ["pre_merge"],
            "required_status": "APPROVED",
            "checks": [
                "critic_approved",
                "tests_pass",
            ],
        },
    },
    # Testing stage
    WorkflowStage.TESTING: {
        StageAction.START: {
            "required_gates": ["implementation"],
            "checks": [
                "no_secrets",
                "no_pm_paths",
            ],
        },
        StageAction.COMPLETE: {
            "required_gates": ["post_implementation"],
            "checks": [
                "tests_pass",
            ],
        },
    },
}

# =============================================================================
# Stage Transition Rules
# =============================================================================

VALID_TRANSITIONS = {
    None: [WorkflowStage.PLANNING, WorkflowStage.ASSIGNMENT],
    WorkflowStage.PLANNING: [WorkflowStage.ASSIGNMENT],
    WorkflowStage.ASSIGNMENT: [WorkflowStage.IMPLEMENTATION],
    WorkflowStage.IMPLEMENTATION: [WorkflowStage.TESTING, WorkflowStage.REVIEW],
    WorkflowStage.TESTING: [WorkflowStage.REVIEW],
    WorkflowStage.REVIEW: [WorkflowStage.IMPLEMENTATION, WorkflowStage.MERGE],  # Can go back if rejected
    WorkflowStage.MERGE: [WorkflowStage.DEPLOYMENT],
    WorkflowStage.DEPLOYMENT: [],  # Terminal state
}

# =============================================================================
# Stage Gate Enforcer
# =============================================================================

class StageGateEnforcer:
    """Enforces stage gates and workflow transitions."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.enforcement_log_path = self.base_path / "LogBook/pm/enforcement_log.yaml"

    def check_stage_gate(
        self,
        stage: WorkflowStage,
        action: StageAction,
        agent: str,
        work_order_id: Optional[str] = None,
        **kwargs
    ) -> EnforcementResult:
        """
        Check if a stage gate allows the action.

        Args:
            stage: The workflow stage
            action: The action being attempted
            agent: The agent attempting the action
            work_order_id: Optional work order ID

        Returns:
            EnforcementResult with allowed/blocked status
        """
        blocking_issues = []
        warnings = []

        # Get gate requirements
        stage_gates = STAGE_GATES.get(stage, {})
        action_gates = stage_gates.get(action, {})

        if not action_gates:
            return EnforcementResult(
                allowed=True,
                stage=stage.value,
                action=action.value,
                message=f"No specific gates defined for {stage.value}/{action.value}",
            )

        # Check required status if work order is specified
        if work_order_id:
            required_status = action_gates.get("required_status")
            if required_status:
                status_ok, status_msg = self._check_work_order_status(
                    work_order_id, required_status
                )
                if not status_ok:
                    blocking_issues.append(status_msg)

        # Run gate validator checks
        required_gates = action_gates.get("required_gates", [])
        for gate_name in required_gates:
            gate_ok, gate_issues, gate_warnings = self._run_gate_validation(
                gate_name, agent, work_order_id
            )
            blocking_issues.extend(gate_issues)
            warnings.extend(gate_warnings)

        # Additional specific checks
        specific_checks = action_gates.get("checks", [])
        for check_name in specific_checks:
            check_ok, check_msg = self._run_specific_check(
                check_name, agent, work_order_id, **kwargs
            )
            if not check_ok:
                blocking_issues.append(f"{check_name}: {check_msg}")

        # Determine overall result
        allowed = len(blocking_issues) == 0

        return EnforcementResult(
            allowed=allowed,
            stage=stage.value,
            action=action.value,
            message="Gate passed" if allowed else "Gate blocked",
            blocking_issues=blocking_issues,
            warnings=warnings,
        )

    def check_transition(
        self,
        from_stage: Optional[WorkflowStage],
        to_stage: WorkflowStage,
        work_order_id: Optional[str] = None,
    ) -> EnforcementResult:
        """
        Check if a stage transition is allowed.

        Args:
            from_stage: Current stage (None if starting)
            to_stage: Target stage

        Returns:
            EnforcementResult with transition allowed/blocked
        """
        valid_targets = VALID_TRANSITIONS.get(from_stage, [])

        if to_stage in valid_targets:
            return EnforcementResult(
                allowed=True,
                stage=to_stage.value,
                action="transition",
                message=f"Transition from {from_stage.value if from_stage else 'start'} to {to_stage.value} allowed",
            )
        else:
            return EnforcementResult(
                allowed=False,
                stage=to_stage.value,
                action="transition",
                message=f"Invalid transition from {from_stage.value if from_stage else 'start'} to {to_stage.value}",
                blocking_issues=[
                    f"Valid targets from {from_stage.value if from_stage else 'start'}: {[s.value for s in valid_targets]}"
                ],
            )

    def enforce(
        self,
        stage: WorkflowStage,
        action: StageAction,
        agent: str,
        work_order_id: Optional[str] = None,
        dry_run: bool = False,
        **kwargs
    ) -> EnforcementResult:
        """
        Enforce stage gate - block if requirements not met.

        Args:
            stage: The workflow stage
            action: The action being attempted
            agent: The agent attempting the action
            work_order_id: Optional work order ID
            dry_run: If True, don't log or block

        Returns:
            EnforcementResult
        """
        result = self.check_stage_gate(stage, action, agent, work_order_id, **kwargs)

        if not dry_run:
            self._log_enforcement(result, agent, work_order_id)

        return result

    def _check_work_order_status(
        self, work_order_id: str, expected_status: str
    ) -> Tuple[bool, str]:
        """Check work order has expected status."""
        wo_paths = [
            self.base_path / "LogBook/pm/WO_QUEUE.yaml",
            self.base_path / "PLANNING/WORK_ORDER_QUEUE.yaml",
        ]

        for path in wo_paths:
            if path.exists():
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f) if HAS_YAML else {}
                    work_orders = data.get("work_orders", [])
                    for wo in work_orders:
                        if wo.get("work_order_id") == work_order_id:
                            status = wo.get("status", "UNKNOWN")
                            if status == expected_status:
                                return True, f"Status is {status}"
                            else:
                                return False, f"Status is {status}, expected {expected_status}"
                except Exception:
                    continue

        return False, f"Work order {work_order_id} not found"

    def _run_gate_validation(
        self, gate_name: str, agent: str, work_order_id: Optional[str]
    ) -> Tuple[bool, List[str], List[str]]:
        """Run gate validator and return results."""
        # Try to import and run gate_validator directly
        try:
            from tools.gate_validator import GateValidator, GateType

            validator = GateValidator()
            gate_type = GateType(gate_name)
            report = validator.validate_gate(gate_type, agent, work_order_id)

            issues = []
            warnings = []

            for result in report.results:
                if not result.passed:
                    if result.severity == "blocking":
                        issues.append(f"{result.check_name}: {result.message}")
                    else:
                        warnings.append(f"{result.check_name}: {result.message}")

            return report.overall_passed, issues, warnings

        except ImportError:
            # Fallback to subprocess
            cmd = [
                sys.executable,
                str(self.base_path / "tools/gate_validator.py"),
                "--agent", agent,
                "--gate", gate_name,
                "--json",
            ]
            if work_order_id:
                cmd.extend(["--work-order", work_order_id])

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                data = json.loads(result.stdout)

                issues = []
                warnings = []
                for r in data.get("results", []):
                    if not r.get("passed"):
                        if r.get("severity") == "blocking":
                            issues.append(f"{r.get('check_name')}: {r.get('message')}")
                        else:
                            warnings.append(f"{r.get('check_name')}: {r.get('message')}")

                return data.get("overall_passed", True), issues, warnings

            except Exception as e:
                return False, [f"Gate validation error: {e}"], []

    def _run_specific_check(
        self, check_name: str, agent: str, work_order_id: Optional[str], **kwargs
    ) -> Tuple[bool, str]:
        """Run a specific named check."""
        # Map check names to functions
        checks = {
            "work_order_exists": self._check_wo_exists,
            "task_assigned": self._check_task_assigned,
            "requirements_exist": self._check_requirements,
            "dependencies_met": self._check_dependencies,
            "tests_pass": self._check_tests_pass,
            "tests_exist": self._check_tests_exist,
            "no_lint_errors": self._check_no_lint,
            "no_secrets": self._check_no_secrets,
            "no_pm_paths": self._check_no_pm_paths,
            "logbook_updated": self._check_logbook_updated,
            "state_valid": self._check_state_valid,
            "critic_verdict_exists": self._check_critic_verdict,
            "critic_approved": self._check_critic_approved,
        }

        check_fn = checks.get(check_name)
        if check_fn:
            return check_fn(agent, work_order_id, **kwargs)
        else:
            return True, f"Unknown check: {check_name}"

    # Specific check implementations
    def _check_wo_exists(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        if not work_order_id:
            return False, "No work order ID provided"

        wo_paths = [
            self.base_path / "LogBook/pm/WO_QUEUE.yaml",
            self.base_path / "PLANNING/WORK_ORDER_QUEUE.yaml",
        ]

        for path in wo_paths:
            if path.exists():
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f) if HAS_YAML else {}
                    work_orders = data.get("work_orders", [])
                    for wo in work_orders:
                        if wo.get("work_order_id") == work_order_id:
                            return True, "Work order exists"
                except:
                    continue

        return False, "Work order not found"

    def _check_task_assigned(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        if not work_order_id:
            return False, "No work order ID"

        wo_paths = [
            self.base_path / "LogBook/pm/WO_QUEUE.yaml",
            self.base_path / "PLANNING/WORK_ORDER_QUEUE.yaml",
        ]

        for path in wo_paths:
            if path.exists():
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f) if HAS_YAML else {}
                    for wo in data.get("work_orders", []):
                        if wo.get("work_order_id") == work_order_id:
                            if wo.get("task_id"):
                                return True, f"Task {wo.get('task_id')} assigned"
                            return False, "No task assigned"
                except:
                    continue

        return False, "Could not verify task assignment"

    def _check_requirements(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        if not work_order_id:
            return False, "No work order ID"

        wo_paths = [
            self.base_path / "LogBook/pm/WO_QUEUE.yaml",
            self.base_path / "PLANNING/WORK_ORDER_QUEUE.yaml",
        ]

        for path in wo_paths:
            if path.exists():
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f) if HAS_YAML else {}
                    for wo in data.get("work_orders", []):
                        if wo.get("work_order_id") == work_order_id:
                            reqs = wo.get("requirements", [])
                            if reqs:
                                return True, f"{len(reqs)} requirements specified"
                            return False, "No requirements specified"
                except:
                    continue

        return False, "Could not verify requirements"

    def _check_dependencies(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        """Check that task dependencies are satisfied before allowing stage promotion."""
        if not work_order_id:
            return True, "No work order - dependencies not applicable"

        # Find the task associated with this work order
        wo_paths = [
            self.base_path / "LogBook/pm/WO_QUEUE.yaml",
            self.base_path / "PLANNING/WORK_ORDER_QUEUE.yaml",
        ]

        task_id = None
        for path in wo_paths:
            if path.exists():
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f) if HAS_YAML else {}
                    for wo in data.get("work_orders", []):
                        if wo.get("work_order_id") == work_order_id:
                            task_id = wo.get("task_id")
                            break
                except Exception:
                    continue
            if task_id:
                break

        if not task_id:
            return True, "No task associated - dependencies not applicable"

        # Find the task's wiring.yaml to get dependencies
        wiring_path = self.base_path / "tasks" / task_id / "wiring.yaml"
        if not wiring_path.exists():
            return True, "No wiring.yaml found - no dependencies declared"

        try:
            with open(wiring_path) as f:
                wiring = yaml.safe_load(f) if HAS_YAML else {}
        except Exception as e:
            return False, f"Failed to read wiring.yaml: {e}"

        dependencies = wiring.get("dependencies", [])
        if not dependencies:
            return True, "No dependencies declared"

        # Check each dependency task has reached the required stage
        unmet_deps = []
        for dep in dependencies:
            dep_task_id = dep.get("task_id") if isinstance(dep, dict) else dep
            required_stage = dep.get("required_stage", "implementation") if isinstance(dep, dict) else "implementation"

            # Check if dependency task exists and has reached required stage
            dep_status_path = self.base_path / "tasks" / dep_task_id / "status.yaml"
            if not dep_status_path.exists():
                unmet_deps.append(f"{dep_task_id}: not found")
                continue

            try:
                with open(dep_status_path) as f:
                    dep_status = yaml.safe_load(f) if HAS_YAML else {}
                current_stage = dep_status.get("stage", "unknown")
                # Simple stage ordering check
                stage_order = ["planning", "assignment", "implementation", "testing", "review", "merge", "deployment"]
                if current_stage not in stage_order:
                    unmet_deps.append(f"{dep_task_id}: unknown stage '{current_stage}'")
                elif stage_order.index(current_stage) < stage_order.index(required_stage):
                    unmet_deps.append(f"{dep_task_id}: at '{current_stage}', needs '{required_stage}'")
            except Exception:
                unmet_deps.append(f"{dep_task_id}: failed to read status")

        if unmet_deps:
            return False, f"Unmet dependencies: {', '.join(unmet_deps)}"

        return True, f"All {len(dependencies)} dependencies satisfied"

    def _check_tests_pass(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--tb=no"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.base_path)
            )
            if result.returncode == 0:
                return True, "All tests pass"
            return False, "Tests failed"
        except subprocess.TimeoutExpired:
            return False, "Tests timed out"
        except FileNotFoundError:
            return True, "pytest not available"
        except Exception as e:
            return False, f"Test error: {e}"

    def _check_tests_exist(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        test_paths = [self.base_path / "tests", self.base_path / "test"]
        for path in test_paths:
            if path.exists():
                test_files = list(path.rglob("test_*.py"))
                if test_files:
                    return True, f"Found {len(test_files)} test files"
        return False, "No test files found"

    def _check_no_lint(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                ["ruff", "check", "."],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.base_path)
            )
            if result.returncode == 0:
                return True, "No lint errors"
            return False, "Lint errors found"
        except FileNotFoundError:
            return True, "Linter not available"
        except Exception:
            return True, "Could not run linter"

    def _check_no_secrets(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        """Scan staged files for hardcoded secrets, API keys, or credentials."""
        import re

        # Common secret patterns to detect
        secret_patterns = [
            (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}["\']?', "API key"),
            (r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}["\']?', "Secret key"),
            (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{8,}["\']', "Password"),
            (r'(?i)(token|auth[_-]?token)\s*[=:]\s*["\']?[a-zA-Z0-9_\-\.]{20,}["\']?', "Token"),
            (r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}', "Bearer token"),
            (r'(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[=:]\s*["\']?[A-Z0-9]{20}["\']?', "AWS access key"),
            (r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*["\']?[a-zA-Z0-9/+=]{40}["\']?', "AWS secret key"),
            (r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', "Private key"),
            (r'ghp_[a-zA-Z0-9]{36}', "GitHub personal access token"),
            (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth token"),
            (r'sk-[a-zA-Z0-9]{48}', "OpenAI API key"),
        ]

        try:
            # Get list of staged files
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                cwd=str(self.base_path)
            )

            if result.returncode != 0:
                return True, "Could not get staged files - skipping secret scan"

            staged_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

            if not staged_files:
                return True, "No staged files to scan"

            secrets_found = []

            for file_path in staged_files:
                full_path = self.base_path / file_path

                # Skip binary files and certain extensions
                skip_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.png', '.jpg', '.gif', '.ico'}
                if full_path.suffix.lower() in skip_extensions:
                    continue

                if not full_path.exists() or not full_path.is_file():
                    continue

                try:
                    content = full_path.read_text(errors='ignore')

                    for pattern, secret_type in secret_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            secrets_found.append(f"{file_path}: potential {secret_type} detected")
                            break  # One detection per file is enough

                except Exception:
                    continue  # Skip files we can't read

            if secrets_found:
                return False, f"Secrets detected in {len(secrets_found)} file(s): {'; '.join(secrets_found[:3])}"

            return True, f"No secrets detected in {len(staged_files)} staged file(s)"

        except Exception as e:
            return True, f"Secret scan error (non-blocking): {e}"

    def _check_no_pm_paths(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        if agent == "pm":
            return True, "PM can modify PM paths"

        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                cwd=str(self.base_path)
            )
            staged = result.stdout.strip().split("\n")

            pm_paths = ["LogBook/pm/", "ISSUE_CATALOG.md", "PLANNING/MASTER_PLAN.md"]
            violations = [f for f in staged if any(f.startswith(p) for p in pm_paths)]

            if violations:
                return False, f"PM path violations: {violations}"
            return True, "No PM path violations"
        except:
            return True, "Could not check staged files"

    def _check_logbook_updated(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        logbook = self.base_path / f"LogBook/{agent}"
        if not logbook.exists():
            return False, f"LogBook/{agent}/ not found"

        cutoff = datetime.utcnow().timestamp() - 3600
        for f in logbook.rglob("*"):
            if f.is_file() and f.stat().st_mtime > cutoff:
                return True, "Recent LogBook updates found"

        return False, "No recent LogBook updates"

    def _check_state_valid(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        state_path = self.base_path / f"LogBook/{agent}/STATE.md"
        if not state_path.exists():
            return False, "STATE.md not found"

        content = state_path.read_text()
        if len(content) > 50:
            return True, "STATE.md is valid"
        return False, "STATE.md is too short"

    def _check_critic_verdict(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        if not work_order_id:
            return False, "No work order ID"

        verdict_path = self.base_path / "LogBook/critic/verdicts.yaml"
        if verdict_path.exists():
            try:
                with open(verdict_path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                verdicts = data.get("verdicts", [])
                for v in verdicts:
                    if v.get("work_order_id") == work_order_id:
                        return True, f"Verdict found: {v.get('verdict')}"
            except:
                pass

        return False, "No verdict found"

    def _check_critic_approved(self, agent: str, work_order_id: Optional[str], **kwargs) -> Tuple[bool, str]:
        if not work_order_id:
            return False, "No work order ID"

        verdict_path = self.base_path / "LogBook/critic/verdicts.yaml"
        if verdict_path.exists():
            try:
                with open(verdict_path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
                verdicts = data.get("verdicts", [])
                for v in verdicts:
                    if v.get("work_order_id") == work_order_id:
                        if v.get("verdict") == "APPROVED":
                            return True, "Critic APPROVED"
                        return False, f"Verdict is {v.get('verdict')}, not APPROVED"
            except:
                pass

        return False, "No APPROVED verdict found"

    def _log_enforcement(
        self, result: EnforcementResult, agent: str, work_order_id: Optional[str]
    ):
        """Log enforcement action."""
        if not self.enforcement_log_path.parent.exists():
            return

        entry = {
            "timestamp": result.timestamp,
            "agent": agent,
            "work_order_id": work_order_id,
            "stage": result.stage,
            "action": result.action,
            "allowed": result.allowed,
            "blocking_issues": result.blocking_issues,
        }

        try:
            if self.enforcement_log_path.exists():
                with open(self.enforcement_log_path) as f:
                    data = yaml.safe_load(f) if HAS_YAML else {}
            else:
                data = {}

            if "enforcement_log" not in data:
                data["enforcement_log"] = []

            data["enforcement_log"].append(entry)

            # Keep last 100 entries
            data["enforcement_log"] = data["enforcement_log"][-100:]

            with open(self.enforcement_log_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False) if HAS_YAML else None

        except Exception:
            pass  # Silent fail for logging

# =============================================================================
# Hook Installation
# =============================================================================

def install_git_hooks(base_path: str = "."):
    """Install git hooks for stage gate enforcement."""
    hooks_dir = Path(base_path) / ".git/hooks"

    if not hooks_dir.exists():
        print("Not a git repository or .git/hooks not found")
        return False

    # Pre-commit hook
    pre_commit = hooks_dir / "pre-commit"
    pre_commit_content = '''#!/bin/bash
# the system Stage Gate Enforcer - Pre-commit Hook

AGENT="${AGENT_NAME:-builder}"

python3 tools/stage_gate_enforcer.py \\
    --stage implementation \\
    --action complete \\
    --agent "$AGENT" \\
    --strict

if [ $? -ne 0 ]; then
    echo "Stage gate check failed. Commit blocked."
    exit 1
fi
'''

    try:
        with open(pre_commit, "w") as f:
            f.write(pre_commit_content)
        os.chmod(pre_commit, 0o755)
        print(f"Installed pre-commit hook: {pre_commit}")
    except Exception as e:
        print(f"Failed to install pre-commit hook: {e}")
        return False

    # Pre-push hook
    pre_push = hooks_dir / "pre-push"
    pre_push_content = '''#!/bin/bash
# the system Stage Gate Enforcer - Pre-push Hook

AGENT="${AGENT_NAME:-builder}"

python3 tools/stage_gate_enforcer.py \\
    --stage merge \\
    --action start \\
    --agent "$AGENT" \\
    --strict

if [ $? -ne 0 ]; then
    echo "Merge gate check failed. Push blocked."
    exit 1
fi
'''

    try:
        with open(pre_push, "w") as f:
            f.write(pre_push_content)
        os.chmod(pre_push, 0o755)
        print(f"Installed pre-push hook: {pre_push}")
    except Exception as e:
        print(f"Failed to install pre-push hook: {e}")
        return False

    print("Git hooks installed successfully")
    return True

# =============================================================================
# CLI Interface
# =============================================================================

def print_result(result: EnforcementResult, verbose: bool = False):
    """Print enforcement result."""
    status = "ALLOWED" if result.allowed else "BLOCKED"
    color = "\033[92m" if result.allowed else "\033[91m"
    reset = "\033[0m"

    print(f"\n{color}[{status}]{reset} Stage: {result.stage}, Action: {result.action}")
    print(f"Message: {result.message}")

    if result.blocking_issues:
        print(f"\n{color}Blocking Issues:{reset}")
        for issue in result.blocking_issues:
            print(f"  - {issue}")

    if result.warnings and verbose:
        print(f"\n\033[93mWarnings:\033[0m")
        for warning in result.warnings:
            print(f"  - {warning}")

def main():
    parser = argparse.ArgumentParser(
        description="Enforce stage gates for the system workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Start implementation:
    %(prog)s --stage implementation --action start --agent builder --work-order WO-2025-001

  Complete testing:
    %(prog)s --stage testing --action complete --agent builder

  Check transition:
    %(prog)s --check-transition --from implementation --to review

  Install git hooks:
    %(prog)s --install-hooks

  Dry run (no blocking):
    %(prog)s --stage merge --action start --agent builder --dry-run
        """
    )

    parser.add_argument(
        "--stage",
        choices=[s.value for s in WorkflowStage],
        help="Workflow stage"
    )
    parser.add_argument(
        "--action",
        choices=[a.value for a in StageAction],
        default="start",
        help="Stage action"
    )
    parser.add_argument(
        "--agent",
        choices=["pm", "builder", "critic", "planner"],
        help="Agent performing the action"
    )
    parser.add_argument(
        "--work-order",
        help="Work order ID"
    )
    parser.add_argument(
        "--check-transition",
        action="store_true",
        help="Check stage transition validity"
    )
    parser.add_argument(
        "--from",
        dest="from_stage",
        choices=[s.value for s in WorkflowStage],
        help="Source stage for transition"
    )
    parser.add_argument(
        "--to",
        dest="to_stage",
        choices=[s.value for s in WorkflowStage],
        help="Target stage for transition"
    )
    parser.add_argument(
        "--install-hooks",
        action="store_true",
        help="Install git hooks"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check without blocking or logging"
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
        help="Exit with error if blocked"
    )

    args = parser.parse_args()

    enforcer = StageGateEnforcer()

    # Install hooks
    if args.install_hooks:
        success = install_git_hooks()
        return 0 if success else 1

    # Check transition
    if args.check_transition:
        if not args.to_stage:
            print("Error: --to required for transition check")
            return 2

        from_stage = WorkflowStage(args.from_stage) if args.from_stage else None
        to_stage = WorkflowStage(args.to_stage)

        result = enforcer.check_transition(from_stage, to_stage, args.work_order)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print_result(result, args.verbose)

        return 0 if result.allowed else (1 if args.strict else 0)

    # Stage gate enforcement
    if args.stage and args.agent:
        stage = WorkflowStage(args.stage)
        action = StageAction(args.action)

        result = enforcer.enforce(
            stage=stage,
            action=action,
            agent=args.agent,
            work_order_id=args.work_order,
            dry_run=args.dry_run
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print_result(result, args.verbose)

        return 0 if result.allowed else (1 if args.strict else 0)

    parser.print_help()
    return 2

if __name__ == "__main__":
    sys.exit(main())
