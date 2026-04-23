#!/usr/bin/env python3
"""
access_control_validator.py - Access Control Validator

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: CRITICAL - Security

Purpose:
    Validates access control policies across the system.
    Enforces agent write boundaries, path restrictions,
    and permission hierarchies.

Usage:
    python3 access_control_validator.py validate
    python3 access_control_validator.py check-agent builder
    python3 access_control_validator.py audit --output report.json
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class AccessRule:
    """Represents an access control rule."""
    rule_id: str
    agent: str
    path_pattern: str
    permission: str  # read, write, execute, none
    condition: Optional[str] = None
    priority: int = 0

@dataclass
class AccessViolation:
    """Represents an access control violation."""
    violation_id: str
    agent: str
    path: str
    action: str
    rule_violated: str
    severity: str
    timestamp: str
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "violation_id": self.violation_id,
            "agent": self.agent,
            "path": self.path,
            "action": self.action,
            "rule_violated": self.rule_violated,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "details": self.details
        }

class AccessControlValidator:
    """Validates the system access control policies."""

    # Default access control rules
    DEFAULT_RULES = [
        # PM exclusive paths
        AccessRule("ACL-001", "pm", "LogBook/pm/**", "write", priority=100),
        AccessRule("ACL-002", "*", "LogBook/pm/**", "read", priority=50),
        AccessRule("ACL-003", "builder", "LogBook/pm/**", "none", priority=90),
        AccessRule("ACL-004", "critic", "LogBook/pm/**", "none", priority=90),

        # Builder paths
        AccessRule("ACL-010", "builder", "LogBook/builder/**", "write", priority=100),
        AccessRule("ACL-011", "builder", "task*/**", "write", priority=100),
        AccessRule("ACL-012", "*", "LogBook/builder/**", "read", priority=50),

        # Critic paths
        AccessRule("ACL-020", "critic", "LogBook/critic/**", "write", priority=100),
        AccessRule("ACL-021", "*", "LogBook/critic/**", "read", priority=50),

        # Planner paths
        AccessRule("ACL-030", "planner", "LogBook/planner/**", "write", priority=100),
        AccessRule("ACL-031", "*", "LogBook/planner/**", "read", priority=50),

        # Shared paths
        AccessRule("ACL-040", "*", "LogBook/shared/**", "write", priority=50),
        AccessRule("ACL-041", "*", "PLANNING/**", "read", priority=50),
        AccessRule("ACL-042", "pm", "PLANNING/**", "write", priority=100),

        # Protected paths
        AccessRule("ACL-050", "*", ".git/**", "none", priority=200),
        AccessRule("ACL-051", "*", "**/.env", "none", priority=200),
        AccessRule("ACL-052", "*", "**/credentials*", "none", priority=200),
        AccessRule("ACL-053", "*", "**/secrets*", "none", priority=200),

        # Tool paths
        AccessRule("ACL-060", "*", "tools/**", "read", priority=50),
        AccessRule("ACL-061", "pm", "tools/**", "write", priority=80),
        AccessRule("ACL-062", "builder", "tools/**", "execute", priority=70),
    ]

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.rules: List[AccessRule] = self.DEFAULT_RULES.copy()
        self.violations: List[AccessViolation] = []
        self._load_custom_rules()

    def _load_custom_rules(self):
        """Load custom access control rules from config."""
        acl_config = self.base_path / ".claude/access_control.yaml"
        if acl_config.exists() and HAS_YAML:
            try:
                with open(acl_config) as f:
                    data = yaml.safe_load(f) or {}
                for rule_data in data.get("rules", []):
                    rule = AccessRule(
                        rule_id=rule_data.get("rule_id", f"CUSTOM-{len(self.rules)}"),
                        agent=rule_data.get("agent", "*"),
                        path_pattern=rule_data.get("path_pattern", "**"),
                        permission=rule_data.get("permission", "read"),
                        condition=rule_data.get("condition"),
                        priority=rule_data.get("priority", 0)
                    )
                    self.rules.append(rule)
            except Exception:
                pass

    def _match_path(self, pattern: str, path: str) -> bool:
        """Check if path matches pattern (glob-style)."""
        # Convert glob pattern to regex
        regex = pattern.replace(".", r"\.")
        regex = regex.replace("**", "{{DOUBLESTAR}}")
        regex = regex.replace("*", "[^/]*")
        regex = regex.replace("{{DOUBLESTAR}}", ".*")
        regex = f"^{regex}$"
        return bool(re.match(regex, path))

    def _get_applicable_rules(self, agent: str, path: str) -> List[AccessRule]:
        """Get all rules applicable to agent and path."""
        applicable = []
        for rule in self.rules:
            if rule.agent == "*" or rule.agent == agent:
                if self._match_path(rule.path_pattern, path):
                    applicable.append(rule)
        # Sort by priority (higher first)
        return sorted(applicable, key=lambda r: r.priority, reverse=True)

    def check_access(self, agent: str, path: str, action: str) -> Tuple[bool, Optional[AccessRule]]:
        """Check if agent can perform action on path."""
        applicable = self._get_applicable_rules(agent, path)

        if not applicable:
            # Default deny for unknown paths
            return False, None

        # Use highest priority rule
        rule = applicable[0]

        permission_map = {
            "read": ["read"],
            "write": ["read", "write"],
            "execute": ["read", "execute"],
            "none": []
        }

        allowed_actions = permission_map.get(rule.permission, [])

        if action in allowed_actions:
            return True, rule

        # Check if there's a specific deny rule for this agent
        for r in applicable:
            if r.agent == agent and r.permission == "none":
                return False, r

        return action in allowed_actions, rule

    def validate_agent_boundaries(self, agent: str) -> List[AccessViolation]:
        """Validate that agent respects its boundaries."""
        violations = []

        # Define expected boundaries
        boundaries = {
            "pm": {
                "allowed_write": ["LogBook/pm/", "PLANNING/"],
                "forbidden_write": ["LogBook/builder/", "LogBook/critic/", "task"]
            },
            "builder": {
                "allowed_write": ["LogBook/builder/", "task"],
                "forbidden_write": ["LogBook/pm/", "LogBook/critic/", "PLANNING/"]
            },
            "critic": {
                "allowed_write": ["LogBook/critic/"],
                "forbidden_write": ["LogBook/pm/", "LogBook/builder/", "task", "PLANNING/"]
            },
            "planner": {
                "allowed_write": ["LogBook/planner/"],
                "forbidden_write": ["LogBook/pm/", "LogBook/builder/", "LogBook/critic/", "task"]
            }
        }

        agent_bounds = boundaries.get(agent, {})
        forbidden = agent_bounds.get("forbidden_write", [])

        # Check for files that might violate boundaries
        for pattern in forbidden:
            for path in self.base_path.glob(f"{pattern}**/*"):
                if path.is_file():
                    allowed, rule = self.check_access(agent, str(path.relative_to(self.base_path)), "write")
                    if allowed:
                        # This would be a policy violation
                        violation = AccessViolation(
                            violation_id=f"VIO-{len(violations)+1:03d}",
                            agent=agent,
                            path=str(path.relative_to(self.base_path)),
                            action="write",
                            rule_violated=rule.rule_id if rule else "BOUNDARY",
                            severity="high",
                            timestamp=datetime.utcnow().isoformat() + "Z",
                            details=f"{agent} has write access to forbidden path"
                        )
                        violations.append(violation)

        return violations

    def validate_all(self) -> Dict:
        """Run all access control validations."""
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_rules": len(self.rules),
            "agents_checked": [],
            "violations": [],
            "summary": {}
        }

        agents = ["pm", "builder", "critic", "planner"]

        for agent in agents:
            agent_violations = self.validate_agent_boundaries(agent)
            results["agents_checked"].append({
                "agent": agent,
                "violations": len(agent_violations),
                "status": "pass" if len(agent_violations) == 0 else "fail"
            })
            results["violations"].extend([v.to_dict() for v in agent_violations])

        # Check protected paths
        protected_violations = self._check_protected_paths()
        results["violations"].extend([v.to_dict() for v in protected_violations])

        # Summary
        total_violations = len(results["violations"])
        results["summary"] = {
            "total_violations": total_violations,
            "by_severity": self._count_by_severity(results["violations"]),
            "by_agent": self._count_by_agent(results["violations"]),
            "status": "pass" if total_violations == 0 else "fail"
        }

        return results

    def _check_protected_paths(self) -> List[AccessViolation]:
        """Check that protected paths are properly restricted."""
        violations = []

        protected_patterns = [".env", "credentials", "secrets", ".git"]

        for pattern in protected_patterns:
            for path in self.base_path.glob(f"**/*{pattern}*"):
                if path.is_file():
                    # Check if any agent has write access
                    for agent in ["pm", "builder", "critic", "planner"]:
                        allowed, rule = self.check_access(agent, str(path.relative_to(self.base_path)), "write")
                        if allowed:
                            violation = AccessViolation(
                                violation_id=f"VIO-P-{len(violations)+1:03d}",
                                agent=agent,
                                path=str(path.relative_to(self.base_path)),
                                action="write",
                                rule_violated="PROTECTED",
                                severity="critical",
                                timestamp=datetime.utcnow().isoformat() + "Z",
                                details=f"Protected path accessible to {agent}"
                            )
                            violations.append(violation)

        return violations

    def _count_by_severity(self, violations: List[dict]) -> Dict[str, int]:
        """Count violations by severity."""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for v in violations:
            severity = v.get("severity", "low")
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    def _count_by_agent(self, violations: List[dict]) -> Dict[str, int]:
        """Count violations by agent."""
        counts = {}
        for v in violations:
            agent = v.get("agent", "unknown")
            counts[agent] = counts.get(agent, 0) + 1
        return counts

    def audit_access(self, output_file: Optional[str] = None) -> Dict:
        """Generate comprehensive access control audit."""
        audit = {
            "audit_id": f"ACL-AUDIT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "agent": r.agent,
                    "path_pattern": r.path_pattern,
                    "permission": r.permission,
                    "priority": r.priority
                }
                for r in sorted(self.rules, key=lambda x: x.priority, reverse=True)
            ],
            "validation_results": self.validate_all(),
            "recommendations": []
        }

        # Generate recommendations
        if audit["validation_results"]["summary"]["total_violations"] > 0:
            audit["recommendations"].append("Review and fix access control violations")

            by_severity = audit["validation_results"]["summary"]["by_severity"]
            if by_severity.get("critical", 0) > 0:
                audit["recommendations"].append("URGENT: Address critical violations immediately")

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(audit, f, indent=2)

        return audit

    def check_single_access(self, agent: str, path: str, action: str) -> Dict:
        """Check a single access request."""
        allowed, rule = self.check_access(agent, path, action)

        return {
            "agent": agent,
            "path": path,
            "action": action,
            "allowed": allowed,
            "rule_applied": rule.rule_id if rule else None,
            "rule_permission": rule.permission if rule else None
        }

def main():
    parser = argparse.ArgumentParser(description="Access Control Validator")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate all access controls")
    validate_parser.add_argument("--strict", action="store_true", help="Exit 1 on violations")

    # Check agent command
    check_parser = subparsers.add_parser("check-agent", help="Check agent boundaries")
    check_parser.add_argument("agent", help="Agent to check")

    # Check access command
    access_parser = subparsers.add_parser("check-access", help="Check specific access")
    access_parser.add_argument("--agent", required=True)
    access_parser.add_argument("--path", required=True)
    access_parser.add_argument("--action", required=True, choices=["read", "write", "execute"])

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Generate audit report")
    audit_parser.add_argument("--output", "-o", help="Output file")

    # List rules command
    list_parser = subparsers.add_parser("list-rules", help="List access control rules")

    # Common arguments
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    validator = AccessControlValidator()

    if args.command == "validate":
        results = validator.validate_all()

        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            print("\nAccess Control Validation Results")
            print("=" * 50)
            print(f"Total Rules: {results['total_rules']}")
            print(f"Agents Checked: {len(results['agents_checked'])}")
            print(f"Total Violations: {results['summary']['total_violations']}")

            if results['violations']:
                print("\nViolations:")
                for v in results['violations']:
                    print(f"  [{v['severity'].upper()}] {v['agent']}: {v['path']} ({v['action']})")
            else:
                print("\n✓ No violations found")

            print(f"\nStatus: {results['summary']['status'].upper()}")

        if args.strict and results['summary']['status'] == 'fail':
            return 1

    elif args.command == "check-agent":
        violations = validator.validate_agent_boundaries(args.agent)

        if args.format == "json":
            print(json.dumps([v.to_dict() for v in violations], indent=2))
        else:
            print(f"\nBoundary Check: {args.agent}")
            print("=" * 40)
            if violations:
                print(f"Found {len(violations)} violations:")
                for v in violations:
                    print(f"  - {v.path}: {v.details}")
            else:
                print("✓ No boundary violations")

    elif args.command == "check-access":
        result = validator.check_single_access(args.agent, args.path, args.action)

        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            status = "✓ ALLOWED" if result['allowed'] else "✗ DENIED"
            print(f"\n{status}")
            print(f"Agent: {result['agent']}")
            print(f"Path: {result['path']}")
            print(f"Action: {result['action']}")
            if result['rule_applied']:
                print(f"Rule: {result['rule_applied']} ({result['rule_permission']})")

    elif args.command == "audit":
        audit = validator.audit_access(args.output)

        if args.format == "json" and not args.output:
            print(json.dumps(audit, indent=2))
        else:
            print(f"\nAccess Control Audit: {audit['audit_id']}")
            print("=" * 50)
            print(f"Rules: {len(audit['rules'])}")
            print(f"Violations: {audit['validation_results']['summary']['total_violations']}")

            if audit['recommendations']:
                print("\nRecommendations:")
                for rec in audit['recommendations']:
                    print(f"  - {rec}")

            if args.output:
                print(f"\nReport saved to: {args.output}")

    elif args.command == "list-rules":
        if args.format == "json":
            rules = [{"rule_id": r.rule_id, "agent": r.agent, "path": r.path_pattern,
                      "permission": r.permission, "priority": r.priority} for r in validator.rules]
            print(json.dumps(rules, indent=2))
        else:
            print("\nAccess Control Rules")
            print("=" * 70)
            print(f"{'ID':<12} {'Agent':<10} {'Permission':<10} {'Priority':<8} Path")
            print("-" * 70)
            for r in sorted(validator.rules, key=lambda x: x.priority, reverse=True):
                print(f"{r.rule_id:<12} {r.agent:<10} {r.permission:<10} {r.priority:<8} {r.path_pattern}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
