#!/usr/bin/env python3
"""
version_compatibility_checker.py - the system Version Compatibility Checker

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Validation Tool

Purpose:
    Checks version compatibility across a system components:
    - Task version constraints
    - Template version compatibility
    - Schema version validation
    - Tool version requirements

Usage:
    python3 version_compatibility_checker.py check --task task001
    python3 version_compatibility_checker.py validate --all
    python3 version_compatibility_checker.py matrix --output compatibility.json
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class Version:
    """Semantic version representation."""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse version string."""
        match = re.match(
            r'^(\d+)\.(\d+)\.(\d+)(?:-([a-z]+\.[0-9]+))?$',
            version_str.strip()
        )
        if not match:
            return cls(0, 0, 0)
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4)
        )

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{self.prerelease}"
        return base

    def __lt__(self, other: "Version") -> bool:
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and other.prerelease:
            return False
        return (self.prerelease or "") < (other.prerelease or "")

    def __le__(self, other: "Version") -> bool:
        return self == other or self < other

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch, self.prerelease) == \
               (other.major, other.minor, other.patch, other.prerelease)

    def __ge__(self, other: "Version") -> bool:
        return self == other or self > other

    def __gt__(self, other: "Version") -> bool:
        return not self <= other

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

@dataclass
class VersionConstraint:
    """Version constraint specification."""
    constraint: str
    operator: str  # >=, <=, ==, ^, ~, >, <
    version: Version

    @classmethod
    def parse(cls, constraint_str: str) -> "VersionConstraint":
        """Parse version constraint string."""
        constraint_str = constraint_str.strip()

        operators = [">=", "<=", "==", "^", "~", ">", "<"]
        for op in operators:
            if constraint_str.startswith(op):
                version_str = constraint_str[len(op):].strip()
                return cls(
                    constraint=constraint_str,
                    operator=op,
                    version=Version.parse(version_str)
                )

        # No operator means exact match
        return cls(
            constraint=constraint_str,
            operator="==",
            version=Version.parse(constraint_str)
        )

    def satisfies(self, version: Version) -> bool:
        """Check if version satisfies constraint."""
        if self.operator == ">=":
            return version >= self.version
        elif self.operator == "<=":
            return version <= self.version
        elif self.operator == "==":
            return version == self.version
        elif self.operator == ">":
            return version > self.version
        elif self.operator == "<":
            return version < self.version
        elif self.operator == "^":
            # Caret: compatible with major version
            return (version.major == self.version.major and
                    version >= self.version)
        elif self.operator == "~":
            # Tilde: compatible with minor version
            return (version.major == self.version.major and
                    version.minor == self.version.minor and
                    version >= self.version)
        return False

@dataclass
class CompatibilityIssue:
    """Represents a compatibility issue."""
    issue_id: str
    severity: str  # critical, high, medium, low
    source: str
    target: str
    source_version: str
    target_version: str
    constraint: str
    message: str
    remediation: str

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity,
            "source": self.source,
            "target": self.target,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "constraint": self.constraint,
            "message": self.message,
            "remediation": self.remediation
        }

@dataclass
class CompatibilityReport:
    """Complete compatibility report."""
    report_id: str
    timestamp: str
    components_checked: int
    compatible: bool
    issues: List[CompatibilityIssue]
    matrix: Dict[str, Dict[str, bool]]

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "components_checked": self.components_checked,
            "compatible": self.compatible,
            "issues": [i.to_dict() for i in self.issues],
            "issue_count": len(self.issues),
            "matrix": self.matrix
        }

class VersionCompatibilityChecker:
    """Checks version compatibility across the system."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.components: Dict[str, Dict[str, Any]] = {}
        self.issue_counter = 0
        self._discover_components()

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"VCI-{datetime.utcnow().strftime('%Y%m%d')}-{self.issue_counter:04d}"

    def _discover_components(self):
        """Discover all components and their versions."""
        # Discover tasks
        for task_dir in self.base_path.glob("task*"):
            if not task_dir.is_dir():
                continue

            manifest = task_dir / "task.yaml"
            if manifest.exists() and HAS_YAML:
                try:
                    with open(manifest) as f:
                        data = yaml.safe_load(f) or {}
                    self.components[task_dir.name] = {
                        "type": "task",
                        "version": data.get("version", "0.0.0"),
                        "dependencies": data.get("dependencies", []),
                        "status": data.get("status", "unknown")
                    }
                except Exception:
                    pass

        # Discover templates
        for template_file in self.base_path.glob("templates/**/*.yaml"):
            if HAS_YAML:
                try:
                    with open(template_file) as f:
                        data = yaml.safe_load(f) or {}
                    if "template_id" in data:
                        self.components[data["template_id"]] = {
                            "type": "template",
                            "version": data.get("version", "0.0.0"),
                            "dependencies": data.get("dependencies", {}).get("templates", [])
                        }
                except Exception:
                    pass

        # Discover schemas
        for schema_file in self.base_path.glob("PLANNING/schemas/*.yaml"):
            if HAS_YAML:
                try:
                    with open(schema_file) as f:
                        data = yaml.safe_load(f) or {}
                    schema_id = schema_file.stem
                    self.components[schema_id] = {
                        "type": "schema",
                        "version": "1.0.0",  # Schemas typically version in comments
                        "dependencies": []
                    }
                except Exception:
                    pass

    def check_task_compatibility(self, task_id: str) -> List[CompatibilityIssue]:
        """Check compatibility for a specific task."""
        issues = []

        if task_id not in self.components:
            return [CompatibilityIssue(
                issue_id=self._generate_issue_id(),
                severity="high",
                source=task_id,
                target="",
                source_version="",
                target_version="",
                constraint="",
                message=f"Task {task_id} not found",
                remediation=f"Verify task {task_id} exists"
            )]

        component = self.components[task_id]
        dependencies = component.get("dependencies", [])

        for dep in dependencies:
            if isinstance(dep, str):
                dep_id = dep
                constraint = None
            else:
                dep_id = dep.get("task_id")
                constraint = dep.get("version_constraint")

            if not dep_id:
                continue

            # Check if dependency exists
            if dep_id not in self.components:
                issues.append(CompatibilityIssue(
                    issue_id=self._generate_issue_id(),
                    severity="critical",
                    source=task_id,
                    target=dep_id,
                    source_version=component.get("version", ""),
                    target_version="missing",
                    constraint=constraint or "",
                    message=f"Missing dependency: {dep_id}",
                    remediation=f"Create or install {dep_id}"
                ))
                continue

            # Check version constraint
            if constraint:
                dep_version = Version.parse(self.components[dep_id].get("version", "0.0.0"))
                version_constraint = VersionConstraint.parse(constraint)

                if not version_constraint.satisfies(dep_version):
                    issues.append(CompatibilityIssue(
                        issue_id=self._generate_issue_id(),
                        severity="high",
                        source=task_id,
                        target=dep_id,
                        source_version=component.get("version", ""),
                        target_version=str(dep_version),
                        constraint=constraint,
                        message=f"Version constraint not satisfied: requires {constraint}, found {dep_version}",
                        remediation=f"Update {dep_id} to version matching {constraint}"
                    ))

        return issues

    def check_all_compatibility(self) -> CompatibilityReport:
        """Check compatibility for all components."""
        all_issues: List[CompatibilityIssue] = []

        # Check task dependencies
        for comp_id, comp_data in self.components.items():
            if comp_data.get("type") == "task":
                issues = self.check_task_compatibility(comp_id)
                all_issues.extend(issues)

        # Build compatibility matrix
        matrix: Dict[str, Dict[str, bool]] = {}
        tasks = [k for k, v in self.components.items() if v.get("type") == "task"]

        for task in tasks:
            matrix[task] = {}
            for other_task in tasks:
                if task == other_task:
                    matrix[task][other_task] = True
                else:
                    # Check if compatible (no issues between them)
                    has_issue = any(
                        (i.source == task and i.target == other_task) or
                        (i.source == other_task and i.target == task)
                        for i in all_issues
                    )
                    matrix[task][other_task] = not has_issue

        return CompatibilityReport(
            report_id=f"COMPAT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            components_checked=len(self.components),
            compatible=len(all_issues) == 0,
            issues=all_issues,
            matrix=matrix
        )

    def validate_constraint(
        self,
        version_str: str,
        constraint_str: str
    ) -> Dict[str, Any]:
        """Validate a version against a constraint."""
        version = Version.parse(version_str)
        constraint = VersionConstraint.parse(constraint_str)

        return {
            "version": version_str,
            "constraint": constraint_str,
            "satisfies": constraint.satisfies(version),
            "parsed_version": {
                "major": version.major,
                "minor": version.minor,
                "patch": version.patch,
                "prerelease": version.prerelease
            },
            "parsed_constraint": {
                "operator": constraint.operator,
                "version": str(constraint.version)
            }
        }

    def get_upgrade_path(
        self,
        from_version: str,
        to_version: str
    ) -> List[str]:
        """Suggest upgrade path between versions."""
        from_v = Version.parse(from_version)
        to_v = Version.parse(to_version)

        if from_v >= to_v:
            return []

        path = []

        # Major upgrades
        if from_v.major < to_v.major:
            for major in range(from_v.major + 1, to_v.major + 1):
                path.append(f"{major}.0.0")

        # Minor upgrades
        if from_v.minor < to_v.minor or from_v.major < to_v.major:
            if from_v.major == to_v.major:
                for minor in range(from_v.minor + 1, to_v.minor + 1):
                    path.append(f"{to_v.major}.{minor}.0")

        # Final version
        if str(to_v) not in path:
            path.append(str(to_v))

        return path

def main():
    parser = argparse.ArgumentParser(description="the system Version Compatibility Checker")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check task compatibility")
    check_parser.add_argument("--task", required=True, help="Task ID to check")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate all components")
    validate_parser.add_argument("--all", action="store_true", help="Validate all")

    # Matrix command
    matrix_parser = subparsers.add_parser("matrix", help="Generate compatibility matrix")
    matrix_parser.add_argument("--output", "-o", help="Output file")

    # Constraint command
    constraint_parser = subparsers.add_parser("constraint", help="Test version constraint")
    constraint_parser.add_argument("--version", required=True, help="Version to test")
    constraint_parser.add_argument("--constraint", required=True, help="Constraint to check")

    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Get upgrade path")
    upgrade_parser.add_argument("--from", dest="from_ver", required=True, help="Current version")
    upgrade_parser.add_argument("--to", dest="to_ver", required=True, help="Target version")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    checker = VersionCompatibilityChecker()

    if args.command == "check":
        issues = checker.check_task_compatibility(args.task)

        if args.format == "json":
            print(json.dumps([i.to_dict() for i in issues], indent=2))
        else:
            if not issues:
                print(f"\n\u2705 {args.task} is compatible with all dependencies")
            else:
                print(f"\n\u274c Found {len(issues)} compatibility issues:")
                for i in issues:
                    icon = {"critical": "\U0001f534", "high": "\U0001f7e0", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(i.severity, "\u26aa")
                    print(f"\n  {icon} [{i.severity.upper()}] {i.message}")
                    print(f"     Source: {i.source} ({i.source_version})")
                    print(f"     Target: {i.target} ({i.target_version})")
                    print(f"     Fix: {i.remediation}")

    elif args.command == "validate":
        report = checker.check_all_compatibility()

        if args.format == "json":
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"\nCompatibility Validation Report")
            print("=" * 50)
            print(f"Components Checked: {report.components_checked}")
            print(f"Overall Compatible: {'Yes' if report.compatible else 'No'}")
            print(f"Issues Found: {len(report.issues)}")

            if report.issues:
                print("\nIssues by Severity:")
                for sev in ["critical", "high", "medium", "low"]:
                    count = sum(1 for i in report.issues if i.severity == sev)
                    if count > 0:
                        print(f"  {sev}: {count}")

    elif args.command == "matrix":
        report = checker.check_all_compatibility()

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report.to_dict(), f, indent=2)
            print(f"Matrix saved to {args.output}")
        else:
            if args.format == "json":
                print(json.dumps(report.matrix, indent=2))
            else:
                print("\nCompatibility Matrix:")
                tasks = list(report.matrix.keys())[:10]  # Limit display
                if tasks:
                    # Header
                    header = "".ljust(15) + " ".join(b[:6].ljust(7) for b in tasks)
                    print(header)
                    # Rows
                    for b1 in tasks:
                        row = b1[:14].ljust(15)
                        for b2 in tasks:
                            compat = report.matrix.get(b1, {}).get(b2, False)
                            row += ("\u2705" if compat else "\u274c").ljust(7)
                        print(row)

    elif args.command == "constraint":
        result = checker.validate_constraint(args.version, args.constraint)

        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            icon = "\u2705" if result["satisfies"] else "\u274c"
            print(f"\n{icon} Version {args.version} {'satisfies' if result['satisfies'] else 'does NOT satisfy'} constraint {args.constraint}")

    elif args.command == "upgrade":
        path = checker.get_upgrade_path(args.from_ver, args.to_ver)

        if args.format == "json":
            print(json.dumps({"from": args.from_ver, "to": args.to_ver, "path": path}))
        else:
            if not path:
                print(f"\n{args.from_ver} >= {args.to_ver}: No upgrade needed")
            else:
                print(f"\nUpgrade path from {args.from_ver} to {args.to_ver}:")
                print(f"  {args.from_ver} -> " + " -> ".join(path))

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
