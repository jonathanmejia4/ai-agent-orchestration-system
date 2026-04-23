#!/usr/bin/env python3
"""
policy_enforcement_engine.py - the system Policy Enforcement Engine

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: CRITICAL - Enforcement Tool

Purpose:
    Enforces the system policies across all agents and operations.
    Validates actions against policy rules before execution.
    Provides real-time policy compliance checking.

Usage:
    python3 policy_enforcement_engine.py check --policy POLICY-001 --action write --target file.py
    python3 policy_enforcement_engine.py validate --agent builder --operation create_task
    python3 policy_enforcement_engine.py audit --since 2025-12-01
    python3 policy_enforcement_engine.py list --status active
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class PolicyResult(Enum):
    """Policy check result."""
    ALLOWED = "allowed"
    DENIED = "denied"
    CONDITIONAL = "conditional"
    ESCALATE = "escalate"
    UNKNOWN = "unknown"

class PolicySeverity(Enum):
    """Policy severity level."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class PolicyRule:
    """Represents a policy rule."""
    rule_id: str
    policy_id: str
    name: str
    description: str
    severity: PolicySeverity
    condition: str
    action: str  # allow, deny, escalate, conditional
    applies_to: List[str]  # agents this rule applies to
    exceptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "condition": self.condition,
            "action": self.action,
            "applies_to": self.applies_to,
            "exceptions": self.exceptions,
            "metadata": self.metadata
        }

@dataclass
class PolicyViolation:
    """Represents a policy violation."""
    violation_id: str
    rule_id: str
    policy_id: str
    agent: str
    operation: str
    target: str
    severity: PolicySeverity
    timestamp: str
    details: str
    remediation: str

    def to_dict(self) -> dict:
        return {
            "violation_id": self.violation_id,
            "rule_id": self.rule_id,
            "policy_id": self.policy_id,
            "agent": self.agent,
            "operation": self.operation,
            "target": self.target,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "details": self.details,
            "remediation": self.remediation
        }

@dataclass
class EnforcementResult:
    """Result of policy enforcement check."""
    result: PolicyResult
    policy_id: str
    rule_id: Optional[str]
    message: str
    details: Dict[str, Any]
    violations: List[PolicyViolation] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "result": self.result.value,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "message": self.message,
            "details": self.details,
            "violations": [v.to_dict() for v in self.violations],
            "conditions": self.conditions
        }

class PolicyEnforcementEngine:
    """Enforces the system policies across all operations."""

    # Built-in policy rules
    CORE_POLICIES = {
        "POLICY-001": {
            "name": "Agent Write Boundaries",
            "description": "Enforces agent write permissions to designated paths",
            "severity": "critical",
            "rules": [
                {
                    "rule_id": "AWB-001",
                    "name": "PM Exclusive Paths",
                    "condition": "path_matches",
                    "paths": [
                        "LogBook/pm/**",
                        "PLANNING/**",
                        "archives/golden/**",
                        "archives/bad/**",
                        ".claude/agents/**",
                        ".claude/guidelines/**",
                        "integration/config/**"
                    ],
                    "allowed_agents": ["pm"],
                    "action": "deny",
                    "severity": "critical"
                },
                {
                    "rule_id": "AWB-002",
                    "name": "Builder Task Paths",
                    "condition": "path_matches",
                    "paths": ["task*/src/**", "task*/tests/**"],
                    "allowed_agents": ["builder", "pm"],
                    "action": "allow",
                    "severity": "high"
                },
                {
                    "rule_id": "AWB-003",
                    "name": "Critic Verdict Paths",
                    "condition": "path_matches",
                    "paths": ["LogBook/critic/**"],
                    "allowed_agents": ["critic", "pm"],
                    "action": "allow",
                    "severity": "high"
                }
            ]
        },
        "POLICY-002": {
            "name": "Escalation Requirements",
            "description": "Defines when escalation to PM is required",
            "severity": "high",
            "rules": [
                {
                    "rule_id": "ESC-001",
                    "name": "Policy Modification Escalation",
                    "condition": "operation_type",
                    "operations": ["modify_policy", "create_guideline", "update_schema"],
                    "action": "escalate",
                    "severity": "critical"
                },
                {
                    "rule_id": "ESC-002",
                    "name": "Security Issue Escalation",
                    "condition": "contains_pattern",
                    "patterns": ["security", "vulnerability", "credential", "secret"],
                    "action": "escalate",
                    "severity": "critical"
                }
            ]
        },
        "POLICY-003": {
            "name": "Idempotence Requirements",
            "description": "Enforces idempotent operations for Builder",
            "severity": "high",
            "rules": [
                {
                    "rule_id": "IDP-001",
                    "name": "No Timestamps in Generated Code",
                    "condition": "content_pattern",
                    "patterns": [
                        r"datetime\.now\(\)",
                        r"time\.time\(\)",
                        r"Date\.now\(\)",
                        r"new Date\(\)"
                    ],
                    "applies_to": ["builder"],
                    "action": "deny",
                    "severity": "high",
                    "exceptions": ["metadata files", "log entries"]
                },
                {
                    "rule_id": "IDP-002",
                    "name": "No Random Values",
                    "condition": "content_pattern",
                    "patterns": [
                        r"random\.",
                        r"uuid\.uuid4\(\)",
                        r"Math\.random\(\)"
                    ],
                    "applies_to": ["builder"],
                    "action": "deny",
                    "severity": "high"
                }
            ]
        },
        "POLICY-004": {
            "name": "Work Order Compliance",
            "description": "Enforces work order workflow rules",
            "severity": "high",
            "rules": [
                {
                    "rule_id": "WOC-001",
                    "name": "Work Order Required",
                    "condition": "operation_type",
                    "operations": ["create_task", "modify_task", "promote_task"],
                    "requires": "valid_work_order",
                    "action": "conditional",
                    "severity": "high"
                },
                {
                    "rule_id": "WOC-002",
                    "name": "Stage Gate Validation",
                    "condition": "stage_transition",
                    "requires": "gate_validation_passed",
                    "action": "conditional",
                    "severity": "critical"
                }
            ]
        },
        "POLICY-005": {
            "name": "Audit Trail Requirements",
            "description": "Enforces audit logging for all operations",
            "severity": "medium",
            "rules": [
                {
                    "rule_id": "AUD-001",
                    "name": "Log All Write Operations",
                    "condition": "operation_type",
                    "operations": ["write", "create", "delete", "modify"],
                    "requires": "audit_log_entry",
                    "action": "conditional",
                    "severity": "medium"
                }
            ]
        }
    }

    # Agent permissions
    AGENT_PERMISSIONS = {
        "pm": {
            "can_write": ["**"],
            "can_read": ["**"],
            "can_execute": ["**"],
            "can_escalate": False,
            "can_approve": True,
            "can_reject": True
        },
        "builder": {
            "can_write": [
                "task*/src/**",
                "task*/tests/**",
                "task*/.task/**",
                "LogBook/builder/**"
            ],
            "can_read": ["**"],
            "can_execute": ["tools/**"],
            "can_escalate": True,
            "can_approve": False,
            "can_reject": False
        },
        "critic": {
            "can_write": [
                "LogBook/critic/**"
            ],
            "can_read": ["**"],
            "can_execute": ["tools/**"],
            "can_escalate": True,
            "can_approve": True,
            "can_reject": True
        },
        "planner": {
            "can_write": [
                "LogBook/planner/**"
            ],
            "can_read": ["**"],
            "can_execute": ["tools/**"],
            "can_escalate": True,
            "can_approve": False,
            "can_reject": False
        }
    }

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.policies: Dict[str, dict] = dict(self.CORE_POLICIES)
        self.violations: List[PolicyViolation] = []
        self._load_custom_policies()

    def _load_custom_policies(self):
        """Load custom policies from PLANNING directory."""
        policies_dir = self.base_path / "PLANNING" / "policies"
        if not policies_dir.exists() or not HAS_YAML:
            return

        for policy_file in policies_dir.glob("*.yaml"):
            try:
                with open(policy_file) as f:
                    policy = yaml.safe_load(f) or {}
                if "policy_id" in policy:
                    self.policies[policy["policy_id"]] = policy
            except Exception:
                pass

    def _match_path(self, path: str, pattern: str) -> bool:
        """Check if path matches a glob-like pattern."""
        import fnmatch
        # Convert ** to match any path segment
        regex_pattern = pattern.replace("**", ".*").replace("*", "[^/]*")
        return bool(re.match(f"^{regex_pattern}$", path))

    def check_write_permission(
        self,
        agent: str,
        target_path: str
    ) -> EnforcementResult:
        """Check if agent has write permission to target path."""
        if agent not in self.AGENT_PERMISSIONS:
            return EnforcementResult(
                result=PolicyResult.DENIED,
                policy_id="POLICY-001",
                rule_id=None,
                message=f"Unknown agent: {agent}",
                details={"agent": agent, "target": target_path}
            )

        permissions = self.AGENT_PERMISSIONS[agent]
        allowed_paths = permissions.get("can_write", [])

        # Check if path is allowed
        for pattern in allowed_paths:
            if self._match_path(target_path, pattern):
                return EnforcementResult(
                    result=PolicyResult.ALLOWED,
                    policy_id="POLICY-001",
                    rule_id="AWB-ALLOW",
                    message=f"Write allowed for {agent} to {target_path}",
                    details={"agent": agent, "target": target_path, "matched_pattern": pattern}
                )

        # Check PM-exclusive paths
        policy = self.policies.get("POLICY-001", {})
        for rule in policy.get("rules", []):
            if rule.get("rule_id") == "AWB-001":
                for pm_path in rule.get("paths", []):
                    if self._match_path(target_path, pm_path):
                        violation = PolicyViolation(
                            violation_id=f"VIO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                            rule_id="AWB-001",
                            policy_id="POLICY-001",
                            agent=agent,
                            operation="write",
                            target=target_path,
                            severity=PolicySeverity.CRITICAL,
                            timestamp=datetime.utcnow().isoformat() + "Z",
                            details=f"Agent {agent} attempted write to PM-exclusive path",
                            remediation="Only PM agent can write to this path"
                        )
                        self.violations.append(violation)

                        return EnforcementResult(
                            result=PolicyResult.DENIED,
                            policy_id="POLICY-001",
                            rule_id="AWB-001",
                            message=f"DENIED: {target_path} is PM-exclusive",
                            details={"agent": agent, "target": target_path},
                            violations=[violation]
                        )

        # Default deny for unmatched paths
        return EnforcementResult(
            result=PolicyResult.DENIED,
            policy_id="POLICY-001",
            rule_id="AWB-DEFAULT",
            message=f"No write permission for {agent} to {target_path}",
            details={"agent": agent, "target": target_path}
        )

    def check_operation(
        self,
        agent: str,
        operation: str,
        target: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> EnforcementResult:
        """Check if an operation is allowed by policies."""
        context = context or {}
        violations = []
        conditions = []

        # Check each policy
        for policy_id, policy in self.policies.items():
            for rule in policy.get("rules", []):
                applies_to = rule.get("applies_to", ["all"])
                if "all" not in applies_to and agent not in applies_to:
                    continue

                condition = rule.get("condition")
                action = rule.get("action", "allow")

                # Check operation type conditions
                if condition == "operation_type":
                    operations = rule.get("operations", [])
                    if operation in operations:
                        if action == "escalate":
                            return EnforcementResult(
                                result=PolicyResult.ESCALATE,
                                policy_id=policy_id,
                                rule_id=rule.get("rule_id"),
                                message=f"Operation {operation} requires escalation to PM",
                                details={"agent": agent, "operation": operation}
                            )
                        elif action == "deny":
                            return EnforcementResult(
                                result=PolicyResult.DENIED,
                                policy_id=policy_id,
                                rule_id=rule.get("rule_id"),
                                message=f"Operation {operation} denied by policy",
                                details={"agent": agent, "operation": operation}
                            )
                        elif action == "conditional":
                            requires = rule.get("requires")
                            if requires and requires not in context:
                                conditions.append(requires)

                # Check path-based conditions
                if condition == "path_matches" and target:
                    paths = rule.get("paths", [])
                    for pattern in paths:
                        if self._match_path(target, pattern):
                            allowed_agents = rule.get("allowed_agents", [])
                            if agent not in allowed_agents:
                                if action == "deny":
                                    return EnforcementResult(
                                        result=PolicyResult.DENIED,
                                        policy_id=policy_id,
                                        rule_id=rule.get("rule_id"),
                                        message=f"Path {target} not allowed for {agent}",
                                        details={"agent": agent, "target": target}
                                    )

        # Return conditional if conditions need to be met
        if conditions:
            return EnforcementResult(
                result=PolicyResult.CONDITIONAL,
                policy_id="multiple",
                rule_id=None,
                message=f"Operation allowed if conditions are met",
                details={"agent": agent, "operation": operation},
                conditions=conditions
            )

        # Default allow
        return EnforcementResult(
            result=PolicyResult.ALLOWED,
            policy_id="default",
            rule_id=None,
            message="Operation allowed",
            details={"agent": agent, "operation": operation, "target": target}
        )

    def validate_content(
        self,
        agent: str,
        content: str,
        file_path: Optional[str] = None
    ) -> EnforcementResult:
        """Validate content against policy rules."""
        violations = []

        # Check idempotence policy for builder
        if agent == "builder":
            policy = self.policies.get("POLICY-003", {})
            for rule in policy.get("rules", []):
                patterns = rule.get("patterns", [])
                for pattern in patterns:
                    if re.search(pattern, content):
                        violation = PolicyViolation(
                            violation_id=f"VIO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                            rule_id=rule.get("rule_id", "unknown"),
                            policy_id="POLICY-003",
                            agent=agent,
                            operation="generate_content",
                            target=file_path or "unknown",
                            severity=PolicySeverity(rule.get("severity", "high")),
                            timestamp=datetime.utcnow().isoformat() + "Z",
                            details=f"Content contains forbidden pattern: {pattern}",
                            remediation=f"Remove or replace pattern matching: {pattern}"
                        )
                        violations.append(violation)

        if violations:
            self.violations.extend(violations)
            return EnforcementResult(
                result=PolicyResult.DENIED,
                policy_id="POLICY-003",
                rule_id=violations[0].rule_id,
                message=f"Content violates {len(violations)} policy rules",
                details={"agent": agent, "violation_count": len(violations)},
                violations=violations
            )

        return EnforcementResult(
            result=PolicyResult.ALLOWED,
            policy_id="POLICY-003",
            rule_id=None,
            message="Content passes policy validation",
            details={"agent": agent}
        )

    def get_violations(
        self,
        since: Optional[datetime] = None,
        agent: Optional[str] = None,
        severity: Optional[PolicySeverity] = None
    ) -> List[PolicyViolation]:
        """Get policy violations with optional filters."""
        filtered = self.violations

        if since:
            since_str = since.isoformat()
            filtered = [v for v in filtered if v.timestamp >= since_str]

        if agent:
            filtered = [v for v in filtered if v.agent == agent]

        if severity:
            filtered = [v for v in filtered if v.severity == severity]

        return filtered

    def list_policies(
        self,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """List all policies."""
        policies = []
        for policy_id, policy in self.policies.items():
            policies.append({
                "policy_id": policy_id,
                "name": policy.get("name", "Unknown"),
                "description": policy.get("description", ""),
                "severity": policy.get("severity", "medium"),
                "rule_count": len(policy.get("rules", [])),
                "status": status
            })
        return policies

    def get_agent_permissions(self, agent: str) -> Dict[str, Any]:
        """Get permissions for an agent."""
        if agent not in self.AGENT_PERMISSIONS:
            return {"error": f"Unknown agent: {agent}"}
        return {
            "agent": agent,
            "permissions": self.AGENT_PERMISSIONS[agent]
        }

def main():
    parser = argparse.ArgumentParser(description="the system Policy Enforcement Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check policy compliance")
    check_parser.add_argument("--agent", required=True, help="Agent name")
    check_parser.add_argument("--operation", help="Operation type")
    check_parser.add_argument("--target", help="Target path or resource")
    check_parser.add_argument("--policy", help="Specific policy to check")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate an action")
    validate_parser.add_argument("--agent", required=True, help="Agent name")
    validate_parser.add_argument("--operation", required=True, help="Operation")
    validate_parser.add_argument("--target", help="Target resource")
    validate_parser.add_argument("--content", help="Content to validate")
    validate_parser.add_argument("--file", help="File containing content")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Audit policy violations")
    audit_parser.add_argument("--since", help="Start date (ISO format)")
    audit_parser.add_argument("--agent", help="Filter by agent")
    audit_parser.add_argument("--severity", choices=["critical", "high", "medium", "low"])

    # List command
    list_parser = subparsers.add_parser("list", help="List policies")
    list_parser.add_argument("--status", default="active", choices=["active", "deprecated"])

    # Permissions command
    perm_parser = subparsers.add_parser("permissions", help="Show agent permissions")
    perm_parser.add_argument("--agent", required=True, help="Agent name")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    engine = PolicyEnforcementEngine()

    if args.command == "check":
        if args.target and not args.operation:
            result = engine.check_write_permission(args.agent, args.target)
        else:
            result = engine.check_operation(
                args.agent,
                args.operation or "unknown",
                args.target
            )

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            icon = {
                PolicyResult.ALLOWED: "\u2705",
                PolicyResult.DENIED: "\u274c",
                PolicyResult.CONDITIONAL: "\u26a0\ufe0f",
                PolicyResult.ESCALATE: "\u2b06\ufe0f",
                PolicyResult.UNKNOWN: "\u2753"
            }.get(result.result, "?")
            print(f"\n{icon} {result.result.value.upper()}: {result.message}")
            if result.violations:
                print(f"\nViolations: {len(result.violations)}")
                for v in result.violations:
                    print(f"  - [{v.severity.value}] {v.details}")
            if result.conditions:
                print(f"\nConditions required:")
                for c in result.conditions:
                    print(f"  - {c}")

        return 0 if result.result == PolicyResult.ALLOWED else 1

    elif args.command == "validate":
        content = args.content
        if args.file:
            try:
                content = Path(args.file).read_text()
            except Exception as e:
                print(f"Error reading file: {e}")
                return 2

        if content:
            result = engine.validate_content(args.agent, content, args.file)
        else:
            result = engine.check_operation(args.agent, args.operation, args.target)

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\n{result.result.value.upper()}: {result.message}")

        return 0 if result.result == PolicyResult.ALLOWED else 1

    elif args.command == "audit":
        since = None
        if args.since:
            since = datetime.fromisoformat(args.since)

        severity = PolicySeverity(args.severity) if args.severity else None
        violations = engine.get_violations(since, args.agent, severity)

        if args.format == "json":
            print(json.dumps([v.to_dict() for v in violations], indent=2))
        else:
            print(f"\nPolicy Violations: {len(violations)}")
            for v in violations:
                print(f"\n  [{v.severity.value}] {v.violation_id}")
                print(f"    Agent: {v.agent}")
                print(f"    Operation: {v.operation}")
                print(f"    Details: {v.details}")

    elif args.command == "list":
        policies = engine.list_policies(args.status)

        if args.format == "json":
            print(json.dumps(policies, indent=2))
        else:
            print(f"\n{'='*60}")
            print("the system POLICIES")
            print(f"{'='*60}")
            for p in policies:
                print(f"\n{p['policy_id']}: {p['name']}")
                print(f"  Severity: {p['severity']}")
                print(f"  Rules: {p['rule_count']}")
                print(f"  {p['description']}")

    elif args.command == "permissions":
        perms = engine.get_agent_permissions(args.agent)

        if args.format == "json":
            print(json.dumps(perms, indent=2))
        else:
            if "error" in perms:
                print(f"Error: {perms['error']}")
                return 1
            print(f"\nPermissions for {args.agent}:")
            for key, value in perms["permissions"].items():
                if isinstance(value, list):
                    print(f"  {key}:")
                    for v in value:
                        print(f"    - {v}")
                else:
                    print(f"  {key}: {value}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
