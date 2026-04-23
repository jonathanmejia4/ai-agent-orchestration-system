#!/usr/bin/env python3
"""
deprecated_template_scanner.py - Proactively scan for deprecated template usage

Scans the repository to identify tasks using deprecated or soon-to-be-deprecated
templates, providing early warning before templates are retired.

Exit codes:
  0 - No deprecated templates in use
  1 - Deprecated templates found
  2 - File/parse error

Usage:
  python tools/deprecated_template_scanner.py
  python tools/deprecated_template_scanner.py --format=json
  python tools/deprecated_template_scanner.py --include-warnings

Reference: PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

@dataclass
class DeprecationInfo:
    """Information about a deprecated template."""
    template: str
    status: str  # deprecated, retiring_soon, retired
    deprecated_since: Optional[str] = None
    retirement_date: Optional[str] = None
    replacement: Optional[str] = None
    migration_guide: Optional[str] = None
    days_until_retirement: Optional[int] = None

@dataclass
class DeprecatedUsage:
    """A task using a deprecated template."""
    task_id: str
    template: str
    version: str
    deprecation_status: str
    urgency: str  # critical, high, medium, low
    message: str
    file_path: str
    replacement: Optional[str] = None
    migration_guide: Optional[str] = None

class DeprecatedTemplateScanner:
    """Scan for deprecated template usage across tasks."""

    def __init__(self, verbose: bool = False, include_warnings: bool = False):
        self.verbose = verbose
        self.include_warnings = include_warnings
        self.deprecations: dict[str, DeprecationInfo] = {}
        self.usages: list[DeprecatedUsage] = []
        self.errors: list[str] = []
        self.scanned_tasks: int = 0

    def load_deprecation_data(self, root_dir: Path) -> None:
        """Load deprecation information from registry and metadata files."""
        # Check registry files
        registry_paths = [
            root_dir / ".templates" / "registry.yaml",
            root_dir / "templates" / "registry.yaml",
            root_dir / "PLANNING" / "template_registry.yaml",
            root_dir / "PLANNING" / "deprecated_templates.yaml",
        ]

        for registry_path in registry_paths:
            if registry_path.exists():
                self._load_registry(registry_path)

        # Check individual template metadata
        template_dirs = [
            root_dir / ".templates",
            root_dir / "templates",
        ]

        for template_dir in template_dirs:
            if template_dir.exists():
                self._scan_template_metadata(template_dir)

        # Check deprecation notices in PLANNING
        deprecation_files = list(root_dir.glob("PLANNING/*deprecat*.yaml"))
        deprecation_files += list(root_dir.glob("PLANNING/*deprecat*.yml"))
        for dep_file in deprecation_files:
            self._load_deprecation_file(dep_file)

    def _load_registry(self, registry_path: Path) -> None:
        """Load deprecation info from registry file."""
        try:
            with open(registry_path) as f:
                data = yaml.safe_load(f) or {}

            for name, info in data.get("templates", {}).items():
                if not isinstance(info, dict):
                    continue

                deprecated = info.get("deprecated", False)
                retired = info.get("retired", False)
                retiring_soon = info.get("retiring_soon", False)

                if deprecated or retired or retiring_soon:
                    status = "retired" if retired else ("retiring_soon" if retiring_soon else "deprecated")

                    retirement_date = info.get("retirement_date", info.get("retire_by"))
                    days_until = None
                    if retirement_date:
                        try:
                            if isinstance(retirement_date, str):
                                ret_date = datetime.strptime(retirement_date, "%Y-%m-%d")
                                days_until = (ret_date - datetime.now()).days
                        except Exception:
                            pass

                    self.deprecations[name] = DeprecationInfo(
                        template=name,
                        status=status,
                        deprecated_since=info.get("deprecated_since"),
                        retirement_date=str(retirement_date) if retirement_date else None,
                        replacement=info.get("replacement", info.get("migrate_to")),
                        migration_guide=info.get("migration_guide", info.get("migration_doc")),
                        days_until_retirement=days_until
                    )

            if self.verbose:
                print(f"  Loaded registry: {registry_path}")

        except Exception as e:
            self.errors.append(f"Error loading registry {registry_path}: {e}")

    def _scan_template_metadata(self, template_dir: Path) -> None:
        """Scan individual template directories for deprecation metadata."""
        for tmpl_path in template_dir.iterdir():
            if not tmpl_path.is_dir():
                continue

            metadata_path = tmpl_path / "metadata.yaml"
            if not metadata_path.exists():
                metadata_path = tmpl_path / "metadata.yml"

            if not metadata_path.exists():
                continue

            try:
                with open(metadata_path) as f:
                    meta = yaml.safe_load(f) or {}

                name = tmpl_path.name
                deprecated = meta.get("deprecated", False)
                retired = meta.get("retired", False)

                if deprecated or retired:
                    if name not in self.deprecations:
                        status = "retired" if retired else "deprecated"

                        retirement_date = meta.get("retirement_date", meta.get("retire_by"))
                        days_until = None
                        if retirement_date:
                            try:
                                if isinstance(retirement_date, str):
                                    ret_date = datetime.strptime(retirement_date, "%Y-%m-%d")
                                    days_until = (ret_date - datetime.now()).days
                            except Exception:
                                pass

                        self.deprecations[name] = DeprecationInfo(
                            template=name,
                            status=status,
                            deprecated_since=meta.get("deprecated_since"),
                            retirement_date=str(retirement_date) if retirement_date else None,
                            replacement=meta.get("replacement", meta.get("migrate_to")),
                            migration_guide=meta.get("migration_guide"),
                            days_until_retirement=days_until
                        )

            except Exception as e:
                if self.verbose:
                    self.errors.append(f"Error reading {metadata_path}: {e}")

    def _load_deprecation_file(self, dep_file: Path) -> None:
        """Load standalone deprecation notice file."""
        try:
            with open(dep_file) as f:
                data = yaml.safe_load(f) or {}

            for entry in data.get("deprecated_templates", []):
                if not isinstance(entry, dict):
                    continue

                name = entry.get("name", entry.get("template"))
                if not name:
                    continue

                if name not in self.deprecations:
                    status = entry.get("status", "deprecated")

                    retirement_date = entry.get("retirement_date", entry.get("retire_by"))
                    days_until = None
                    if retirement_date:
                        try:
                            if isinstance(retirement_date, str):
                                ret_date = datetime.strptime(retirement_date, "%Y-%m-%d")
                                days_until = (ret_date - datetime.now()).days
                        except Exception:
                            pass

                    self.deprecations[name] = DeprecationInfo(
                        template=name,
                        status=status,
                        deprecated_since=entry.get("deprecated_since"),
                        retirement_date=str(retirement_date) if retirement_date else None,
                        replacement=entry.get("replacement", entry.get("migrate_to")),
                        migration_guide=entry.get("migration_guide"),
                        days_until_retirement=days_until
                    )

            if self.verbose:
                print(f"  Loaded deprecation file: {dep_file}")

        except Exception as e:
            self.errors.append(f"Error loading {dep_file}: {e}")

    def scan_tasks(self, root_dir: Path) -> None:
        """Scan all tasks for deprecated template usage."""
        wiring_patterns = [
            "**/wiring.yaml",
            "**/.task/wiring.yaml",
            "tasks/**/wiring.yaml",
        ]

        found_files = set()
        for pattern in wiring_patterns:
            for wiring_file in root_dir.glob(pattern):
                if wiring_file not in found_files:
                    found_files.add(wiring_file)
                    self._check_task(wiring_file)

    def _check_task(self, wiring_file: Path) -> None:
        """Check a task for deprecated template usage."""
        try:
            with open(wiring_file) as f:
                data = yaml.safe_load(f) or {}

            self.scanned_tasks += 1

            # Extract task identity
            identity = data.get("identity", {})
            task_id = identity.get("task_id", identity.get("id", wiring_file.parent.name))

            # Extract template info
            template = identity.get("template", data.get("template", ""))
            template_version = identity.get("template_version", "")

            if not template:
                return

            # Handle template@version format
            if "@" in str(template) and not template_version:
                template, template_version = str(template).rsplit("@", 1)

            if not template_version:
                template_version = "unknown"

            # Check if template is deprecated
            if template in self.deprecations:
                dep_info = self.deprecations[template]
                self._record_usage(
                    task_id=task_id,
                    template=template,
                    version=template_version,
                    dep_info=dep_info,
                    file_path=str(wiring_file)
                )

        except Exception as e:
            self.errors.append(f"Error processing {wiring_file}: {e}")

    def _record_usage(
        self,
        task_id: str,
        template: str,
        version: str,
        dep_info: DeprecationInfo,
        file_path: str
    ) -> None:
        """Record deprecated template usage."""
        # Determine urgency
        if dep_info.status == "retired":
            urgency = "critical"
            message = "Template has been RETIRED - immediate migration required"
        elif dep_info.days_until_retirement is not None:
            if dep_info.days_until_retirement <= 0:
                urgency = "critical"
                message = "Template retirement date has PASSED"
            elif dep_info.days_until_retirement <= 30:
                urgency = "high"
                message = f"Template retiring in {dep_info.days_until_retirement} days"
            elif dep_info.days_until_retirement <= 90:
                urgency = "medium"
                message = f"Template retiring in {dep_info.days_until_retirement} days"
            else:
                urgency = "low"
                message = f"Template deprecated, retiring in {dep_info.days_until_retirement} days"
        elif dep_info.status == "retiring_soon":
            urgency = "high"
            message = "Template marked as retiring soon"
        else:
            urgency = "medium"
            message = "Template is deprecated"

        self.usages.append(DeprecatedUsage(
            task_id=task_id,
            template=template,
            version=version,
            deprecation_status=dep_info.status,
            urgency=urgency,
            message=message,
            file_path=file_path,
            replacement=dep_info.replacement,
            migration_guide=dep_info.migration_guide
        ))

    def get_summary(self) -> dict:
        """Get scan summary statistics."""
        by_urgency = defaultdict(list)
        by_template = defaultdict(list)

        for usage in self.usages:
            by_urgency[usage.urgency].append(usage)
            by_template[usage.template].append(usage)

        return {
            "scanned_tasks": self.scanned_tasks,
            "deprecated_templates_tracked": len(self.deprecations),
            "total_usages": len(self.usages),
            "critical": len(by_urgency["critical"]),
            "high": len(by_urgency["high"]),
            "medium": len(by_urgency["medium"]),
            "low": len(by_urgency["low"]),
            "templates_in_use": {
                template: len(usages)
                for template, usages in by_template.items()
            },
            "has_deprecated_usage": len(self.usages) > 0
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("DEPRECATED TEMPLATE SCAN REPORT")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nTasks scanned: {summary['scanned_tasks']}")
        lines.append(f"Deprecated templates tracked: {summary['deprecated_templates_tracked']}")
        lines.append(f"Deprecated usages found: {summary['total_usages']}")

        if summary["total_usages"] > 0:
            lines.append("\nBy Urgency:")
            lines.append(f"  Critical: {summary['critical']}")
            lines.append(f"  High: {summary['high']}")
            lines.append(f"  Medium: {summary['medium']}")
            lines.append(f"  Low: {summary['low']}")

            lines.append("\nAffected Templates:")
            for template, count in sorted(summary["templates_in_use"].items()):
                dep_info = self.deprecations.get(template)
                status = f" [{dep_info.status}]" if dep_info else ""
                lines.append(f"  {template}{status}: {count} task(s)")

        # Group by urgency
        urgency_order = ["critical", "high", "medium", "low"]
        for urgency in urgency_order:
            usages = [u for u in self.usages if u.urgency == urgency]
            if not usages:
                continue

            if not self.include_warnings and urgency == "low":
                lines.append(f"\n  ({len(usages)} low-urgency items hidden, use --include-warnings)")
                continue

            lines.append("\n" + "-" * 40)
            lines.append(f"{urgency.upper()} URGENCY ({len(usages)}):")
            lines.append("-" * 40)

            for u in usages:
                lines.append(f"\n  Task: {u.task_id}")
                lines.append(f"    Template: {u.template}@{u.version}")
                lines.append(f"    Status: {u.deprecation_status}")
                lines.append(f"    Issue: {u.message}")
                if u.replacement:
                    lines.append(f"    Replacement: {u.replacement}")
                if u.migration_guide and self.verbose:
                    lines.append(f"    Migration guide: {u.migration_guide}")
                if self.verbose:
                    lines.append(f"    File: {u.file_path}")

        if not self.usages:
            lines.append("\n✓ No deprecated templates in use")

        # Show tracked deprecations
        if self.verbose and self.deprecations:
            lines.append("\n" + "-" * 40)
            lines.append("TRACKED DEPRECATIONS:")
            lines.append("-" * 40)
            for name, info in sorted(self.deprecations.items()):
                lines.append(f"\n  {name}")
                lines.append(f"    Status: {info.status}")
                if info.retirement_date:
                    lines.append(f"    Retirement: {info.retirement_date}")
                if info.replacement:
                    lines.append(f"    Replacement: {info.replacement}")

        if self.errors and self.verbose:
            lines.append("\n" + "-" * 40)
            lines.append("ERRORS:")
            for error in self.errors[:5]:
                lines.append(f"  - {error}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        output = {
            "summary": self.get_summary(),
            "usages": [
                {
                    "task_id": u.task_id,
                    "template": u.template,
                    "version": u.version,
                    "deprecation_status": u.deprecation_status,
                    "urgency": u.urgency,
                    "message": u.message,
                    "file_path": u.file_path,
                    "replacement": u.replacement,
                    "migration_guide": u.migration_guide
                }
                for u in sorted(self.usages, key=lambda x: (
                    {"critical": 0, "high": 1, "medium": 2, "low": 3}[x.urgency],
                    x.template
                ))
            ],
            "deprecations": {
                name: {
                    "status": info.status,
                    "deprecated_since": info.deprecated_since,
                    "retirement_date": info.retirement_date,
                    "days_until_retirement": info.days_until_retirement,
                    "replacement": info.replacement,
                    "migration_guide": info.migration_guide
                }
                for name, info in self.deprecations.items()
            },
            "errors": self.errors
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Scan for deprecated template usage across tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - No deprecated templates in use
  1 - Deprecated templates found
  2 - File/parse error

Examples:
  %(prog)s                      # Scan current directory
  %(prog)s --format=json        # JSON output for automation
  %(prog)s --include-warnings   # Include low-urgency items
  %(prog)s --verbose            # Show detailed information
        """
    )

    parser.add_argument(
        "--dir", "-d",
        default=".",
        help="Root directory to scan (default: current directory)"
    )

    parser.add_argument(
        "--include-warnings",
        action="store_true",
        help="Include low-urgency deprecation warnings"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    root_dir = Path(args.dir)
    if not root_dir.exists():
        print(f"Error: Directory not found: {root_dir}", file=sys.stderr)
        sys.exit(2)

    scanner = DeprecatedTemplateScanner(
        verbose=args.verbose,
        include_warnings=args.include_warnings
    )

    if args.verbose:
        print("Loading deprecation data...")
    scanner.load_deprecation_data(root_dir)

    if args.verbose:
        print("Scanning tasks...")
    scanner.scan_tasks(root_dir)

    if args.format == "json":
        print(scanner.format_json_output())
    else:
        print(scanner.format_text_output())

    # Exit code based on findings
    summary = scanner.get_summary()
    if summary["has_deprecated_usage"]:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
