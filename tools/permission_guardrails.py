#!/usr/bin/env python3
"""
Permission Guardrail System

Classifies operations as SAFE, CONDITIONAL, or UNSAFE
based on operation type, target paths, and context.

Usage:
    from tools.permission_guardrails import SafetyGuardrail

    guardrail = SafetyGuardrail(agent="IF-Lane-E", lane="E")
    result = guardrail.check_operation(
        operation_type="delete_file",
        target_path="src/legacy/deprecated_auth.py"
    )

    if result.safety_tier == SafetyTier.SAFE:
        # Auto-approve, proceed
    elif result.safety_tier == SafetyTier.CONDITIONAL:
        # Check conditions, maybe auto-approve
    else:
        # Request permission
"""

import re
import os
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class SafetyTier(Enum):
    SAFE = "SAFE"
    CONDITIONAL = "CONDITIONAL"
    UNSAFE = "UNSAFE"


class Decision(Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    REQUEST_REQUIRED = "REQUEST_REQUIRED"


@dataclass
class GuardrailResult:
    safety_tier: SafetyTier
    decision: Decision
    reason: str
    auto_approve_eligible: bool
    required_validations: List[str]
    escalation_required: bool


class SafetyGuardrail:
    """Determines if operations are safe to auto-approve"""

    # PM-exclusive paths (from pm-write-boundaries.md)
    PM_EXCLUSIVE_PATHS = [
        r"^LogBook/pm/",
        r"^PLANNING/MASTER_PLAN\.md$",
        r"^PLANNING/WORK_ORDER_QUEUE\.yaml$",
        r"^ISSUE_CATALOG\.md$",
        r"^PLANNING/PROJECT_CONTEXT\.md$",
        r"^PLANNING/MILESTONE_TRACKER\.md$",
        r"^LogBook/pm/escalations/",
        r"^LogBook/work-orders/",
        r"^\.claude/guidelines/",
        r"^archives/golden/",
        r"^archives/bad/",
        r"^\.claude/agents/",
        r"^integration/config/",
    ]

    # Universal prohibitions (from agent-guardrails.md)
    UNIVERSALLY_PROHIBITED = [
        "commit_to_main",
        "force_push",
        "delete_remote_branch",
        "rebase_published_commits",
        "modify_ssot_wiring",
        "skip_quality_gates",
        "self_approve",
    ]

    def __init__(self, agent: str, lane: str):
        self.agent = agent
        self.lane = lane
        self.agent_logbook_path = f"LogBook/{agent.lower()}/"

    def check_operation(
        self,
        operation_type: str,
        target_path: Optional[str] = None,
        context: Optional[dict] = None
    ) -> GuardrailResult:
        """
        Main entry point for guardrail checks

        Args:
            operation_type: Type of operation (e.g., "delete_file", "modify_file", "git_commit")
            target_path: Path being operated on (if applicable)
            context: Additional context (issue_id, work_order_id, etc.)

        Returns:
            GuardrailResult with safety classification and decision
        """
        context = context or {}

        # Check 1: Universal prohibitions
        if operation_type in self.UNIVERSALLY_PROHIBITED:
            return GuardrailResult(
                safety_tier=SafetyTier.UNSAFE,
                decision=Decision.REQUEST_REQUIRED,
                reason=f"Universally prohibited: {operation_type}",
                auto_approve_eligible=False,
                required_validations=[],
                escalation_required=True
            )

        # Check 2: PM-exclusive paths
        if target_path and self._is_pm_exclusive(target_path):
            # Exception: Agents can write to their own LogBook
            if not target_path.startswith(self.agent_logbook_path):
                return GuardrailResult(
                    safety_tier=SafetyTier.UNSAFE,
                    decision=Decision.REQUEST_REQUIRED,
                    reason=f"PM-exclusive path: {target_path}",
                    auto_approve_eligible=False,
                    required_validations=[],
                    escalation_required=True
                )

        # Check 3: Destructive operations
        if operation_type in ["delete_file", "delete_directory", "truncate_file"]:
            # Temp files are safe to delete
            if target_path and (target_path.startswith("/tmp/") or
                               target_path.startswith(f"{self.agent_logbook_path}temp/")):
                return GuardrailResult(
                    safety_tier=SafetyTier.SAFE,
                    decision=Decision.AUTO_APPROVE,
                    reason="Temp file deletion is safe",
                    auto_approve_eligible=True,
                    required_validations=[],
                    escalation_required=False
                )

            # All other deletions require permission
            return GuardrailResult(
                safety_tier=SafetyTier.UNSAFE,
                decision=Decision.REQUEST_REQUIRED,
                reason="Deletion requires permission",
                auto_approve_eligible=False,
                required_validations=[],
                escalation_required=False
            )

        # Check 4: Read-only operations
        if operation_type in ["read_file", "list_directory", "grep", "glob",
                             "git_status", "git_diff", "git_log"]:
            return GuardrailResult(
                safety_tier=SafetyTier.SAFE,
                decision=Decision.AUTO_APPROVE,
                reason="Read-only operation",
                auto_approve_eligible=True,
                required_validations=[],
                escalation_required=False
            )

        # Check 5: Agent's own LogBook writes
        if operation_type in ["write_file", "modify_file"] and target_path:
            if target_path.startswith(self.agent_logbook_path):
                return GuardrailResult(
                    safety_tier=SafetyTier.SAFE,
                    decision=Decision.AUTO_APPROVE,
                    reason="Agent can write to own LogBook",
                    auto_approve_eligible=True,
                    required_validations=[],
                    escalation_required=False
                )

        # Check 6: Issue file operations (lane-specific)
        if target_path and target_path.startswith(f"issues/{self.lane}/"):
            if operation_type == "create_file":
                return GuardrailResult(
                    safety_tier=SafetyTier.SAFE,
                    decision=Decision.AUTO_APPROVE,
                    reason="Creating issue in own lane is safe",
                    auto_approve_eligible=True,
                    required_validations=[],
                    escalation_required=False
                )

            if operation_type == "modify_file":
                # Can modify issues in own lane (conditional: must be OPEN status)
                return GuardrailResult(
                    safety_tier=SafetyTier.CONDITIONAL,
                    decision=Decision.AUTO_APPROVE,  # Will auto-approve if conditions met
                    reason="Can modify OPEN issues in own lane",
                    auto_approve_eligible=True,
                    required_validations=["issue_status_is_open"],
                    escalation_required=False
                )

        # Check 7: File creation (conditional)
        if operation_type == "create_file" and target_path:
            # Not in PM-exclusive, not outside scope
            if not self._is_out_of_scope(target_path):
                return GuardrailResult(
                    safety_tier=SafetyTier.CONDITIONAL,
                    decision=Decision.AUTO_APPROVE,
                    reason="File creation in scope (validate spec match)",
                    auto_approve_eligible=True,
                    required_validations=["matches_documented_spec"],
                    escalation_required=False
                )

        # Check 8: Git operations
        if operation_type == "git_commit":
            branch = context.get("branch", "")
            if branch == "main":
                return GuardrailResult(
                    safety_tier=SafetyTier.UNSAFE,
                    decision=Decision.REQUEST_REQUIRED,
                    reason="Cannot commit to main branch",
                    auto_approve_eligible=False,
                    required_validations=[],
                    escalation_required=True
                )

            # Alt-branch commits are safe (agent's own files)
            return GuardrailResult(
                safety_tier=SafetyTier.SAFE,
                decision=Decision.AUTO_APPROVE,
                reason="Commit to alt-branch is safe",
                auto_approve_eligible=True,
                required_validations=[],
                escalation_required=False
            )

        # Default: Unknown operation → require permission
        return GuardrailResult(
            safety_tier=SafetyTier.UNSAFE,
            decision=Decision.REQUEST_REQUIRED,
            reason=f"Unknown operation type: {operation_type}",
            auto_approve_eligible=False,
            required_validations=[],
            escalation_required=False
        )

    def _is_pm_exclusive(self, path: str) -> bool:
        """Check if path is PM-exclusive"""
        return any(re.match(pattern, path) for pattern in self.PM_EXCLUSIVE_PATHS)

    def _is_out_of_scope(self, path: str) -> bool:
        """Check if path is outside agent's scope (basic implementation)"""
        # Issue fixers: can modify issues/{LANE}/ and related source files
        # This is a simplified check - real implementation would check work order scope
        if path.startswith(f"issues/{self.lane}/"):
            return False
        if path.startswith(f"LogBook/{self.agent.lower()}/"):
            return False
        # Default: conservative - treat as potentially out of scope
        return True


def main():
    """Test harness for guardrail system"""
    import sys

    if "--test" not in sys.argv:
        print("Usage: python3 permission_guardrails.py --test")
        return 1

    print("Testing Permission Guardrail System...")
    print("=" * 60)

    guardrail = SafetyGuardrail(agent="IF-Lane-E", lane="E")

    # Test 1: Read operations
    result = guardrail.check_operation("read_file", "src/api/client.py")
    assert result.decision == Decision.AUTO_APPROVE, "Test 1 failed"
    print("✓ PASS: Read operations auto-approved")

    # Test 2: Delete operations
    result = guardrail.check_operation("delete_file", "src/api/client.py")
    assert result.decision == Decision.REQUEST_REQUIRED, "Test 2 failed"
    print("✓ PASS: Delete operations require permission")

    # Test 3: PM-exclusive paths
    result = guardrail.check_operation("modify_file", "LogBook/pm/STATE.md")
    assert result.safety_tier == SafetyTier.UNSAFE, "Test 3 failed"
    print("✓ PASS: PM-exclusive paths blocked")

    # Test 4: Agent LogBook writes
    result = guardrail.check_operation("write_file", "LogBook/if-lane-e/actions.yaml")
    assert result.decision == Decision.AUTO_APPROVE, "Test 4 failed"
    print("✓ PASS: Agent LogBook writes approved")

    # Test 5: Issue creation
    result = guardrail.check_operation("create_file", "issues/E/E-99.md")
    assert result.decision == Decision.AUTO_APPROVE, "Test 5 failed"
    print("✓ PASS: Issue creation in own lane approved")

    # Test 6: Temp file deletion
    result = guardrail.check_operation("delete_file", "/tmp/test.txt")
    assert result.decision == Decision.AUTO_APPROVE, "Test 6 failed"
    print("✓ PASS: Temp file deletion approved")

    # Test 7: Universal prohibitions
    result = guardrail.check_operation("commit_to_main")
    assert result.decision == Decision.REQUEST_REQUIRED, "Test 7 failed"
    print("✓ PASS: Universal prohibitions blocked")

    print("=" * 60)
    print("All tests passed!")
    return 0


if __name__ == "__main__":
    exit(main())
