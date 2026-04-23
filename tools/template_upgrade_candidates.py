#!/usr/bin/env python3
"""
template_upgrade_candidates.py - Identify tasks needing template upgrades

Scans repository to find tasks using outdated template versions and
prioritizes them for upgrade based on deprecation status and version gap.

Exit codes:
  0 - Scan completed, no critical upgrades needed
  1 - Critical upgrades found (deprecated templates in use)
  2 - File/parse error

Usage:
  python tools/template_upgrade_candidates.py
  python tools/template_upgrade_candidates.py --format=json
  python tools/template_upgrade_candidates.py --critical-only

Reference: PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

@dataclass
class UpgradeCandidate:
    """Represents a task that may need template upgrade."""
    task_id: str
    template: str
    current_version: str
    latest_version: str
    version_gap: int
    priority: str  # critical, high, medium, low
    reason: str
    file_path: str
    deprecated: bool = False
    retired: bool = False

class UpgradeCandidateFinder:
    """Find tasks that are candidates for template upgrades."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.candidates: list[UpgradeCandidate] = []
        self.template_versions: dict[str, list[str]] = defaultdict(list)
        self.deprecated_templates: set[str] = set()
        self.retired_templates: set[str] = set()
        self.errors: list[str] = []

    def load_template_registry(self, root_dir: Path) -> None:
        """Load template registry to get version information."""
        registry_paths = [
            root_dir / ".templates" / "registry.yaml",
            root_dir / "templates" / "registry.yaml",
            root_dir / "PLANNING" / "template_registry.yaml",
        ]

        for registry_path in registry_paths:
            if registry_path.exists():
                try:
                    with open(registry_path) as f:
                        data = yaml.safe_load(f) or {}

                    for template_name, template_info in data.get("templates", {}).items():
                        if isinstance(template_info, dict):
                            versions = template_info.get("versions", [])
                            self.template_versions[template_name] = versions

                            if template_info.get("deprecated", False):
                                self.deprecated_templates.add(template_name)
                            if template_info.get("retired", False):
                                self.retired_templates.add(template_name)

                    if self.verbose:
                        print(f"  Loaded registry: {registry_path}")
                except Exception as e:
                    self.errors.append(f"Error loading registry {registry_path}: {e}")

        # Scan template directories for version information
        template_dirs = [
            root_dir / ".templates",
            root_dir / "templates",
        ]

        for template_dir in template_dirs:
            if template_dir.exists():
                for template_path in template_dir.iterdir():
                    if template_path.is_dir():
                        template_name = template_path.name
                        versions_dir = template_path / "versions"
                        if versions_dir.exists():
                            for ver_dir in versions_dir.iterdir():
                                if ver_dir.is_dir():
                                    self.template_versions[template_name].append(ver_dir.name)

                        # Check metadata for deprecation
                        metadata_path = template_path / "metadata.yaml"
                        if metadata_path.exists():
                            try:
                                with open(metadata_path) as f:
                                    meta = yaml.safe_load(f) or {}
                                if meta.get("deprecated"):
                                    self.deprecated_templates.add(template_name)
                                if meta.get("retired"):
                                    self.retired_templates.add(template_name)
                            except Exception:
                                pass

    def scan_tasks(self, root_dir: Path) -> None:
        """Scan tasks for template usage."""
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
                    self._check_wiring_file(wiring_file)

    def _check_wiring_file(self, wiring_file: Path) -> None:
        """Check a wiring file for upgrade candidates."""
        try:
            with open(wiring_file) as f:
                data = yaml.safe_load(f) or {}

            # Extract task ID
            identity = data.get("identity", {})
            task_id = identity.get("task_id", identity.get("id", wiring_file.parent.name))

            # Extract template info
            template = identity.get("template", data.get("template", ""))
            template_version = identity.get("template_version", "")

            if not template:
                return

            # Parse template@version format
            if "@" in str(template) and not template_version:
                template, template_version = str(template).rsplit("@", 1)

            if not template_version:
                template_version = "unknown"

            # Check if upgrade is needed
            self._evaluate_upgrade_need(
                task_id=task_id,
                template=template,
                current_version=template_version,
                file_path=str(wiring_file)
            )

        except Exception as e:
            self.errors.append(f"Error processing {wiring_file}: {e}")

    def _evaluate_upgrade_need(
        self,
        task_id: str,
        template: str,
        current_version: str,
        file_path: str
    ) -> None:
        """Evaluate if a task needs upgrade and determine priority."""
        # Check for retired template
        if template in self.retired_templates:
            self.candidates.append(UpgradeCandidate(
                task_id=task_id,
                template=template,
                current_version=current_version,
                latest_version="N/A (retired)",
                version_gap=999,
                priority="critical",
                reason="Template is retired - immediate migration required",
                file_path=file_path,
                retired=True
            ))
            return

        # Check for deprecated template
        if template in self.deprecated_templates:
            self.candidates.append(UpgradeCandidate(
                task_id=task_id,
                template=template,
                current_version=current_version,
                latest_version=self._get_latest_version(template),
                version_gap=99,
                priority="high",
                reason="Template is deprecated - upgrade recommended before retirement",
                file_path=file_path,
                deprecated=True
            ))
            return

        # Check version gap
        latest_version = self._get_latest_version(template)

        if current_version == "unknown":
            self.candidates.append(UpgradeCandidate(
                task_id=task_id,
                template=template,
                current_version=current_version,
                latest_version=latest_version,
                version_gap=0,
                priority="medium",
                reason="Template version not specified - should pin version",
                file_path=file_path
            ))
            return

        if latest_version and current_version != latest_version:
            gap = self._calculate_version_gap(current_version, latest_version)

            if gap >= 3:
                priority = "high"
                reason = f"Major version gap ({gap} versions behind)"
            elif gap >= 1:
                priority = "medium"
                reason = f"Minor version gap ({gap} version(s) behind)"
            else:
                priority = "low"
                reason = "Patch version available"

            self.candidates.append(UpgradeCandidate(
                task_id=task_id,
                template=template,
                current_version=current_version,
                latest_version=latest_version,
                version_gap=gap,
                priority=priority,
                reason=reason,
                file_path=file_path
            ))

    def _get_latest_version(self, template: str) -> str:
        """Get latest version for a template."""
        versions = self.template_versions.get(template, [])
        if not versions:
            return "unknown"

        try:
            sorted_versions = sorted(versions, key=self._version_key, reverse=True)
            return sorted_versions[0]
        except Exception:
            return versions[-1] if versions else "unknown"

    def _version_key(self, version: str) -> tuple:
        """Create sortable key from version string."""
        try:
            parts = re.findall(r"\d+", version)
            return tuple(int(p) for p in parts[:3]) if parts else (0, 0, 0)
        except Exception:
            return (0, 0, 0)

    def _calculate_version_gap(self, current: str, latest: str) -> int:
        """Calculate gap between versions."""
        try:
            current_parts = [int(p) for p in re.findall(r"\d+", current)[:3]]
            latest_parts = [int(p) for p in re.findall(r"\d+", latest)[:3]]

            # Pad to 3 parts
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(latest_parts) < 3:
                latest_parts.append(0)

            # Major version difference
            if latest_parts[0] > current_parts[0]:
                return (latest_parts[0] - current_parts[0]) * 10

            # Minor version difference
            if latest_parts[1] > current_parts[1]:
                return latest_parts[1] - current_parts[1]

            # Patch difference
            return max(0, latest_parts[2] - current_parts[2])

        except Exception:
            return 0

    def get_summary(self) -> dict:
        """Get summary of upgrade candidates."""
        by_priority = defaultdict(list)
        for candidate in self.candidates:
            by_priority[candidate.priority].append(candidate)

        return {
            "total_candidates": len(self.candidates),
            "critical": len(by_priority["critical"]),
            "high": len(by_priority["high"]),
            "medium": len(by_priority["medium"]),
            "low": len(by_priority["low"]),
            "deprecated_templates_in_use": len([c for c in self.candidates if c.deprecated]),
            "retired_templates_in_use": len([c for c in self.candidates if c.retired])
        }

    def format_text_output(self, critical_only: bool = False) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("TEMPLATE UPGRADE CANDIDATES")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nTotal candidates: {summary['total_candidates']}")
        lines.append(f"  Critical: {summary['critical']}")
        lines.append(f"  High: {summary['high']}")
        lines.append(f"  Medium: {summary['medium']}")
        lines.append(f"  Low: {summary['low']}")

        if summary["retired_templates_in_use"]:
            lines.append(f"\n  RETIRED TEMPLATES IN USE: {summary['retired_templates_in_use']}")
        if summary["deprecated_templates_in_use"]:
            lines.append(f"  DEPRECATED TEMPLATES IN USE: {summary['deprecated_templates_in_use']}")

        # Group by priority
        priority_order = ["critical", "high", "medium", "low"]
        for priority in priority_order:
            candidates = [c for c in self.candidates if c.priority == priority]

            if critical_only and priority not in ["critical", "high"]:
                continue

            if not candidates:
                continue

            lines.append("\n" + "-" * 40)
            lines.append(f"{priority.upper()} PRIORITY ({len(candidates)}):")
            lines.append("-" * 40)

            for c in sorted(candidates, key=lambda x: -x.version_gap):
                status = ""
                if c.retired:
                    status = " [RETIRED]"
                elif c.deprecated:
                    status = " [DEPRECATED]"

                lines.append(f"\n  {c.task_id}{status}")
                lines.append(f"    Template: {c.template}")
                lines.append(f"    Current: {c.current_version} -> Latest: {c.latest_version}")
                lines.append(f"    Reason: {c.reason}")
                if self.verbose:
                    lines.append(f"    File: {c.file_path}")

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
            "candidates": [
                {
                    "task_id": c.task_id,
                    "template": c.template,
                    "current_version": c.current_version,
                    "latest_version": c.latest_version,
                    "version_gap": c.version_gap,
                    "priority": c.priority,
                    "reason": c.reason,
                    "file_path": c.file_path,
                    "deprecated": c.deprecated,
                    "retired": c.retired
                }
                for c in sorted(self.candidates, key=lambda x: (-x.version_gap, x.priority))
            ],
            "deprecated_templates": list(self.deprecated_templates),
            "retired_templates": list(self.retired_templates),
            "errors": self.errors
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Identify tasks needing template upgrades",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - No critical upgrades needed
  1 - Critical upgrades found (deprecated/retired templates)
  2 - File/parse error

Examples:
  %(prog)s                      # Scan current directory
  %(prog)s --format=json        # JSON output for automation
  %(prog)s --critical-only      # Show only critical/high priority
  %(prog)s --verbose            # Show file paths
        """
    )

    parser.add_argument(
        "--dir", "-d",
        default=".",
        help="Root directory to scan (default: current directory)"
    )

    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="Show only critical and high priority candidates"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information including file paths"
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

    finder = UpgradeCandidateFinder(verbose=args.verbose)

    if args.verbose:
        print("Loading template registry...")
    finder.load_template_registry(root_dir)

    if args.verbose:
        print("Scanning tasks...")
    finder.scan_tasks(root_dir)

    if args.format == "json":
        print(finder.format_json_output())
    else:
        print(finder.format_text_output(critical_only=args.critical_only))

    # Exit code based on critical issues
    summary = finder.get_summary()
    if summary["critical"] > 0 or summary["retired_templates_in_use"] > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
