#!/usr/bin/env python3
"""
Template Compatibility Checker
Version: 1.0.0
Last Updated: 2026-01-09
Owner: Builder
Classification: HIGH - Stage Gate Validator

Checks template compatibility constraints before regeneration.
Validates that template version combinations satisfy compatibility requirements.
Used in three-way merge regeneration workflow.

Usage:
    python tools/template_compatibility_checker.py --template api-crud@2.3.0
    python tools/template_compatibility_checker.py --task-dir .task/
    python tools/template_compatibility_checker.py --check-all --strict

Referenced in:
    - .claude/guidelines/README.md (Section: Three-Way Merge Regeneration)
    - templates/README.md
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class CompatibilityConstraint:
    """A compatibility constraint between templates."""
    source_template: str
    source_version: str
    target_template: str
    version_constraint: str  # e.g., ">=2.0.0", "==2.3.*", "~=1.0"
    constraint_type: str  # requires, conflicts, recommends

    def to_dict(self) -> dict:
        return {
            "source_template": self.source_template,
            "source_version": self.source_version,
            "target_template": self.target_template,
            "version_constraint": self.version_constraint,
            "constraint_type": self.constraint_type
        }


@dataclass
class CompatibilityResult:
    """Result of a compatibility check."""
    template: str
    version: str
    is_compatible: bool
    constraints_checked: int
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "template": self.template,
            "version": self.version,
            "is_compatible": self.is_compatible,
            "constraints_checked": self.constraints_checked,
            "violations": self.violations,
            "warnings": self.warnings
        }


@dataclass
class CompatibilityReport:
    """Complete compatibility check report."""
    timestamp: str
    total_templates: int
    compatible: int
    incompatible: int
    warnings: int
    results: List[CompatibilityResult]
    blocked: bool

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_templates": self.total_templates,
            "compatible": self.compatible,
            "incompatible": self.incompatible,
            "warnings": self.warnings,
            "results": [r.to_dict() for r in self.results],
            "blocked": self.blocked
        }


class TemplateCompatibilityChecker:
    """Checks template compatibility for regeneration."""

    # Built-in compatibility constraints
    DEFAULT_CONSTRAINTS = [
        # API CRUD constraints
        CompatibilityConstraint("api-crud", "2.3.*", "api-crud-tests", "==2.3.*", "requires"),
        CompatibilityConstraint("api-crud", "2.*", "schema-validator", ">=1.0.0", "requires"),
        CompatibilityConstraint("api-crud", "*", "api-crud-legacy", "*", "conflicts"),

        # Schema constraints
        CompatibilityConstraint("schema-validator", "2.*", "schema-generator", ">=2.0.0", "requires"),
        CompatibilityConstraint("schema-validator", "1.*", "schema-generator", "~=1.0", "recommends"),

        # Test constraints
        CompatibilityConstraint("unit-tests", "*", "integration-tests", ">=1.0.0", "recommends"),
        CompatibilityConstraint("e2e-tests", "2.*", "test-fixtures", ">=2.0.0", "requires"),

        # Compliance constraints
        CompatibilityConstraint("compliance-report", "*", "audit-logger", ">=1.0.0", "requires"),
        CompatibilityConstraint("compliance-contract", "2.*", "compliance-checker", ">=2.0.0", "requires"),
    ]

    def __init__(self, constraints_file: Optional[Path] = None):
        self.constraints = self.DEFAULT_CONSTRAINTS.copy()
        if constraints_file and constraints_file.exists():
            self._load_constraints(constraints_file)

    def _load_constraints(self, path: Path) -> None:
        """Load additional constraints from a YAML file."""
        if not HAS_YAML:
            return

        try:
            content = yaml.safe_load(path.read_text())
            if not isinstance(content, dict):
                return

            for item in content.get("constraints", []):
                self.constraints.append(CompatibilityConstraint(
                    source_template=item.get("source_template", ""),
                    source_version=item.get("source_version", "*"),
                    target_template=item.get("target_template", ""),
                    version_constraint=item.get("version_constraint", "*"),
                    constraint_type=item.get("constraint_type", "requires")
                ))
        except Exception:
            pass

    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse a semver version string into tuple."""
        # Remove leading 'v' if present
        version = version.lstrip('v')

        # Handle wildcards
        if version == "*":
            return (999, 999, 999)

        # Handle partial versions
        parts = version.rstrip('*').rstrip('.').split('.')
        major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        return (major, minor, patch)

    def _version_matches(self, version: str, constraint: str) -> bool:
        """Check if a version satisfies a constraint."""
        if constraint == "*":
            return True

        version_tuple = self._parse_version(version)

        # Handle different constraint operators
        if constraint.startswith("=="):
            pattern = constraint[2:].replace("*", r"\d+").replace(".", r"\.")
            return bool(re.match(f"^{pattern}$", version))

        elif constraint.startswith(">="):
            constraint_tuple = self._parse_version(constraint[2:])
            return version_tuple >= constraint_tuple

        elif constraint.startswith("<="):
            constraint_tuple = self._parse_version(constraint[2:])
            return version_tuple <= constraint_tuple

        elif constraint.startswith(">"):
            constraint_tuple = self._parse_version(constraint[1:])
            return version_tuple > constraint_tuple

        elif constraint.startswith("<"):
            constraint_tuple = self._parse_version(constraint[1:])
            return version_tuple < constraint_tuple

        elif constraint.startswith("~="):
            # Compatible release: ~=2.1 means >=2.1.0,<3.0.0
            base = constraint[2:]
            parts = base.split('.')
            min_version = self._parse_version(base)

            if len(parts) >= 2:
                max_version = (min_version[0] + 1, 0, 0)
            else:
                max_version = (min_version[0], min_version[1] + 1, 0)

            return min_version <= version_tuple < max_version

        elif "*" in constraint:
            # Wildcard matching: 2.* matches 2.0.0, 2.1.0, etc.
            pattern = constraint.replace(".", r"\.").replace("*", r"\d+")
            return bool(re.match(f"^{pattern}$", version))

        else:
            # Exact match
            return version == constraint

    def _source_matches(self, template: str, version: str, constraint: CompatibilityConstraint) -> bool:
        """Check if a template matches a constraint's source."""
        if constraint.source_template != template:
            return False

        return self._version_matches(version, constraint.source_version)

    def check_compatibility(
        self,
        templates: Dict[str, str]  # template_name -> version
    ) -> CompatibilityReport:
        """Check compatibility of a set of templates."""
        from datetime import datetime

        results = []
        total_compatible = 0
        total_incompatible = 0
        total_warnings = 0
        blocked = False

        for template, version in templates.items():
            violations = []
            warnings = []
            constraints_checked = 0

            # Find applicable constraints
            for constraint in self.constraints:
                if not self._source_matches(template, version, constraint):
                    continue

                constraints_checked += 1

                # Check if target template is in our set
                if constraint.target_template in templates:
                    target_version = templates[constraint.target_template]
                    matches = self._version_matches(target_version, constraint.version_constraint)

                    if constraint.constraint_type == "requires" and not matches:
                        violations.append(
                            f"{template}@{version} requires {constraint.target_template} "
                            f"{constraint.version_constraint}, found {target_version}"
                        )
                    elif constraint.constraint_type == "conflicts" and matches:
                        violations.append(
                            f"{template}@{version} conflicts with {constraint.target_template}@{target_version}"
                        )
                    elif constraint.constraint_type == "recommends" and not matches:
                        warnings.append(
                            f"{template}@{version} recommends {constraint.target_template} "
                            f"{constraint.version_constraint}, found {target_version}"
                        )

                elif constraint.constraint_type == "requires":
                    violations.append(
                        f"{template}@{version} requires {constraint.target_template} "
                        f"{constraint.version_constraint} (not found)"
                    )

            is_compatible = len(violations) == 0
            if is_compatible:
                total_compatible += 1
            else:
                total_incompatible += 1
                blocked = True

            if warnings:
                total_warnings += len(warnings)

            results.append(CompatibilityResult(
                template=template,
                version=version,
                is_compatible=is_compatible,
                constraints_checked=constraints_checked,
                violations=violations,
                warnings=warnings
            ))

        return CompatibilityReport(
            timestamp=datetime.now().isoformat(),
            total_templates=len(templates),
            compatible=total_compatible,
            incompatible=total_incompatible,
            warnings=total_warnings,
            results=results,
            blocked=blocked
        )

    def check_task(self, task_dir: Path) -> CompatibilityReport:
        """Check compatibility for a task's templates."""
        templates = {}

        # Look for wiring.yaml
        wiring_path = task_dir / "wiring.yaml"
        if wiring_path.exists() and HAS_YAML:
            try:
                wiring = yaml.safe_load(wiring_path.read_text())
                if isinstance(wiring, dict):
                    for item in wiring.get("templates", []):
                        if isinstance(item, dict):
                            name = item.get("name", item.get("template", ""))
                            version = item.get("version", "1.0.0")
                            if name:
                                templates[name] = version
                        elif isinstance(item, str) and "@" in item:
                            name, version = item.rsplit("@", 1)
                            templates[name] = version
            except Exception:
                pass

        # Look for plan_metadata.yaml
        metadata_path = task_dir / "plan_metadata.yaml"
        if metadata_path.exists() and HAS_YAML:
            try:
                metadata = yaml.safe_load(metadata_path.read_text())
                if isinstance(metadata, dict):
                    for template_ref in metadata.get("templates", []):
                        if isinstance(template_ref, str) and "@" in template_ref:
                            name, version = template_ref.rsplit("@", 1)
                            templates[name] = version
            except Exception:
                pass

        return self.check_compatibility(templates)


def main():
    parser = argparse.ArgumentParser(
        description="Check template compatibility for regeneration"
    )
    parser.add_argument(
        "--template", "-t",
        action="append",
        help="Template with version (name@version), can be repeated"
    )
    parser.add_argument(
        "--task-dir", "-b",
        help="Task directory to check"
    )
    parser.add_argument(
        "--constraints-file", "-c",
        help="Additional constraints YAML file"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Check all tasks in current directory"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file"
    )

    args = parser.parse_args()

    constraints_file = Path(args.constraints_file) if args.constraints_file else None
    checker = TemplateCompatibilityChecker(constraints_file)

    if args.task_dir:
        report = checker.check_task(Path(args.task_dir))
    elif args.template:
        templates = {}
        for t in args.template:
            if "@" in t:
                name, version = t.rsplit("@", 1)
                templates[name] = version
            else:
                templates[t] = "1.0.0"
        report = checker.check_compatibility(templates)
    elif args.check_all:
        # Check all .task directories
        all_results = []
        task_dirs = list(Path(".").rglob(".task"))
        if not task_dirs:
            task_dirs = [Path(".task")] if Path(".task").exists() else []

        for task_dir in task_dirs:
            r = checker.check_task(task_dir)
            all_results.extend(r.results)

        # Aggregate
        from datetime import datetime
        report = CompatibilityReport(
            timestamp=datetime.now().isoformat(),
            total_templates=len(all_results),
            compatible=sum(1 for r in all_results if r.is_compatible),
            incompatible=sum(1 for r in all_results if not r.is_compatible),
            warnings=sum(len(r.warnings) for r in all_results),
            results=all_results,
            blocked=any(not r.is_compatible for r in all_results)
        )
    else:
        print("Error: Must specify --template, --task-dir, or --check-all", file=sys.stderr)
        return 1

    # Handle strict mode
    if args.strict and report.warnings > 0:
        report.blocked = True

    # Output
    if args.format == "json":
        output = json.dumps(report.to_dict(), indent=2)
    else:
        lines = []
        lines.append("=" * 60)
        lines.append("TEMPLATE COMPATIBILITY CHECK")
        lines.append("=" * 60)
        lines.append(f"\nTimestamp: {report.timestamp}")
        lines.append(f"Templates checked: {report.total_templates}")
        lines.append(f"Compatible: {report.compatible}")
        lines.append(f"Incompatible: {report.incompatible}")
        lines.append(f"Warnings: {report.warnings}")

        if report.results:
            lines.append("\n" + "-" * 60)
            for r in report.results:
                status = "✅" if r.is_compatible else "❌"
                lines.append(f"\n{status} {r.template}@{r.version}")
                lines.append(f"   Constraints checked: {r.constraints_checked}")

                for v in r.violations:
                    lines.append(f"   ❌ {v}")

                for w in r.warnings:
                    lines.append(f"   ⚠️ {w}")

        lines.append("\n" + "=" * 60)
        if report.blocked:
            lines.append("❌ BLOCKED: Compatibility check failed")
        else:
            lines.append("✅ All templates are compatible")

        output = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)

    return 1 if report.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
