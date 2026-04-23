#!/usr/bin/env python3
"""
template_usage.py - Template usage tracking and reporting tool

Scans repository for template usage across tasks, reports version distribution,
identifies outdated templates, and generates usage statistics for capacity planning.

Exit codes:
  0 - Scan completed successfully
  1 - Errors encountered
  2 - File/parse error

Usage:
  python tools/template_usage.py
  python tools/template_usage.py --format=json
  python tools/template_usage.py --template api-gateway --verbose

Reference: PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

class TemplateUsageTracker:
    """Track and report template usage across tasks."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.usage: dict[str, list[dict]] = defaultdict(list)
        self.versions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.errors: list[str] = []

    def scan_directory(self, root_dir: Path) -> None:
        """Scan directory for wiring.yaml files."""
        # Find all wiring.yaml files
        wiring_patterns = [
            root_dir / "**" / ".task" / "wiring.yaml",
            root_dir / "**" / "wiring.yaml",
            root_dir / "tasks" / "**" / "wiring.yaml",
        ]

        found_files = set()
        for pattern in wiring_patterns:
            for wiring_file in Path(root_dir).glob(str(pattern.relative_to(root_dir))):
                if wiring_file not in found_files:
                    found_files.add(wiring_file)
                    self._process_wiring_file(wiring_file)

        # Also check for task.yaml with template references
        for task_file in root_dir.glob("**/task.yaml"):
            self._process_task_yaml(task_file)

    def _process_wiring_file(self, wiring_file: Path) -> None:
        """Process a wiring.yaml file for template usage."""
        try:
            with open(wiring_file) as f:
                data = yaml.safe_load(f) or {}

            task_id = self._extract_task_id(wiring_file, data)

            # Check for template in identity section
            identity = data.get("identity", {})
            template = identity.get("template", "")
            template_version = identity.get("template_version", "")

            if template:
                self._record_usage(
                    template=template,
                    version=template_version or "unknown",
                    task_id=task_id,
                    file_path=str(wiring_file),
                    source="wiring.yaml"
                )

            # Check for direct template field
            if "template" in data and not template:
                tmpl = data["template"]
                if "@" in str(tmpl):
                    template, template_version = str(tmpl).rsplit("@", 1)
                else:
                    template = str(tmpl)
                    template_version = "unknown"

                self._record_usage(
                    template=template,
                    version=template_version,
                    task_id=task_id,
                    file_path=str(wiring_file),
                    source="wiring.yaml"
                )

        except Exception as e:
            self.errors.append(f"Error processing {wiring_file}: {e}")

    def _process_task_yaml(self, task_file: Path) -> None:
        """Process a task.yaml file for template usage."""
        try:
            with open(task_file) as f:
                data = yaml.safe_load(f) or {}

            task_id = data.get("id", data.get("task_id", task_file.parent.name))

            # Check for template field
            template = data.get("template", "")
            if template:
                if "@" in str(template):
                    tmpl_name, tmpl_version = str(template).rsplit("@", 1)
                else:
                    tmpl_name = str(template)
                    tmpl_version = data.get("template_version", "unknown")

                self._record_usage(
                    template=tmpl_name,
                    version=tmpl_version,
                    task_id=task_id,
                    file_path=str(task_file),
                    source="task.yaml"
                )

        except Exception as e:
            if self.verbose:
                self.errors.append(f"Error processing {task_file}: {e}")

    def _extract_task_id(self, wiring_file: Path, data: dict) -> str:
        """Extract task ID from file path or data."""
        # Try from data
        identity = data.get("identity", {})
        if "task_id" in identity:
            return identity["task_id"]
        if "id" in identity:
            return identity["id"]

        # Try from directory structure
        parts = wiring_file.parts
        for i, part in enumerate(parts):
            if part == ".task" and i > 0:
                return parts[i - 1]
            if part == "tasks" and i + 1 < len(parts):
                return parts[i + 1]

        return wiring_file.parent.name

    def _record_usage(
        self,
        template: str,
        version: str,
        task_id: str,
        file_path: str,
        source: str
    ) -> None:
        """Record template usage."""
        self.usage[template].append({
            "task_id": task_id,
            "version": version,
            "file_path": file_path,
            "source": source
        })
        self.versions[template][version] += 1

    def get_summary(self) -> dict:
        """Get usage summary statistics."""
        summary = {
            "total_templates": len(self.usage),
            "total_usages": sum(len(v) for v in self.usage.values()),
            "templates": {}
        }

        for template, usages in sorted(self.usage.items()):
            version_dist = dict(self.versions[template])
            latest_version = max(version_dist.keys(), key=lambda v: self._version_key(v))

            outdated = sum(
                1 for u in usages
                if u["version"] != latest_version and u["version"] != "unknown"
            )

            summary["templates"][template] = {
                "usage_count": len(usages),
                "versions": version_dist,
                "latest_version": latest_version,
                "outdated_count": outdated,
                "tasks": [u["task_id"] for u in usages]
            }

        return summary

    def _version_key(self, version: str) -> tuple:
        """Create sortable key from version string."""
        if version == "unknown":
            return (0, 0, 0)
        try:
            parts = re.findall(r"\d+", version)
            return tuple(int(p) for p in parts[:3]) if parts else (0, 0, 0)
        except Exception:
            return (0, 0, 0)

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("TEMPLATE USAGE REPORT")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nTotal templates: {summary['total_templates']}")
        lines.append(f"Total usages: {summary['total_usages']}")

        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")

        lines.append("\n" + "-" * 40)
        lines.append("USAGE BY TEMPLATE:")
        lines.append("-" * 40)

        for template, info in sorted(
            summary["templates"].items(),
            key=lambda x: -x[1]["usage_count"]
        ):
            lines.append(f"\n  {template}")
            lines.append(f"    Usages: {info['usage_count']}")
            lines.append(f"    Latest: {info['latest_version']}")
            lines.append(f"    Outdated: {info['outdated_count']}")

            # Version distribution
            lines.append("    Versions:")
            for version, count in sorted(info["versions"].items()):
                marker = " (latest)" if version == info["latest_version"] else ""
                lines.append(f"      {version}: {count} task(s){marker}")

            if self.verbose:
                lines.append("    Tasks:")
                for task_id in info["tasks"][:10]:
                    lines.append(f"      - {task_id}")
                if len(info["tasks"]) > 10:
                    lines.append(f"      ... and {len(info['tasks']) - 10} more")

        if self.errors and self.verbose:
            lines.append("\n" + "-" * 40)
            lines.append("ERRORS:")
            for error in self.errors[:10]:
                lines.append(f"  - {error}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        summary = self.get_summary()
        output = {
            "summary": summary,
            "usage_details": {
                template: usages
                for template, usages in self.usage.items()
            },
            "errors": self.errors
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Track and report template usage across tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Scan completed successfully
  1 - Errors encountered
  2 - File/parse error

Examples:
  %(prog)s                      # Scan current directory
  %(prog)s --format=json        # JSON output
  %(prog)s --template api       # Filter by template name
  %(prog)s --verbose            # Show detailed usage
        """
    )

    parser.add_argument(
        "--dir", "-d",
        default=".",
        help="Root directory to scan (default: current directory)"
    )

    parser.add_argument(
        "--template", "-t",
        help="Filter by template name"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed usage information"
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

    tracker = TemplateUsageTracker(verbose=args.verbose)
    tracker.scan_directory(root_dir)

    # Filter by template if specified
    if args.template:
        filtered_usage = {
            k: v for k, v in tracker.usage.items()
            if args.template.lower() in k.lower()
        }
        filtered_versions = {
            k: v for k, v in tracker.versions.items()
            if args.template.lower() in k.lower()
        }
        tracker.usage = defaultdict(list, filtered_usage)
        tracker.versions = defaultdict(lambda: defaultdict(int), filtered_versions)

    if args.format == "json":
        print(tracker.format_json_output())
    else:
        print(tracker.format_text_output())

    sys.exit(1 if tracker.errors else 0)

if __name__ == "__main__":
    main()
