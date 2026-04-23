#!/usr/bin/env python3
"""
retired_template_checker.py - CI blocking tool for retired template detection

Scans task SSOT wiring files to detect retired template usage and fails CI builds
if any retired templates are found, forcing migration to supported versions.

Exit codes:
  0 - No retired templates found (CI passes)
  1 - One or more retired templates found (CI fails)
  2 - Invalid wiring files or metadata

Usage:
  python tools/retired_template_checker.py [OPTIONS]
  python tools/retired_template_checker.py --verbose
  python tools/retired_template_checker.py --format=json
  python tools/retired_template_checker.py --suggest-fixes

Reference: PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml

class RetiredTemplateChecker:
    """Checks tasks for usage of retired templates."""

    def __init__(self, repo_root: str = ".", verbose: bool = False):
        self.repo_root = Path(repo_root)
        self.verbose = verbose
        self.retired_usages: list[dict[str, Any]] = []
        self.scanned_tasks: list[str] = []
        self.errors: list[dict[str, Any]] = []
        self.template_cache: dict[str, dict] = {}

    def find_wiring_files(self) -> list[Path]:
        """Find all .task/wiring.yaml files in the repository."""
        wiring_files = []

        # Search in tasks/ directory
        tasks_dir = self.repo_root / "tasks"
        if tasks_dir.exists():
            for wiring_file in tasks_dir.rglob(".task/wiring.yaml"):
                wiring_files.append(wiring_file)

        # Also search for standalone .task directories
        for wiring_file in self.repo_root.rglob(".task/wiring.yaml"):
            if wiring_file not in wiring_files:
                wiring_files.append(wiring_file)

        return wiring_files

    def load_wiring_file(self, wiring_path: Path) -> Optional[dict]:
        """Load and parse a wiring.yaml file."""
        try:
            with open(wiring_path, 'r') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.errors.append({
                "type": "parse_error",
                "file": str(wiring_path),
                "message": f"YAML parse error: {e}"
            })
            return None
        except Exception as e:
            self.errors.append({
                "type": "read_error",
                "file": str(wiring_path),
                "message": str(e)
            })
            return None

    def get_task_id(self, wiring_path: Path) -> str:
        """Extract task ID from wiring file path."""
        # Try to get task ID from parent directory structure
        # e.g., tasks/3.1/.task/wiring.yaml -> "3.1"
        parts = wiring_path.parts
        for i, part in enumerate(parts):
            if part == ".task" and i > 0:
                return parts[i - 1]
        return str(wiring_path.parent.parent.name)

    def load_template_metadata(self, template_name: str, template_version: str) -> Optional[dict]:
        """Load template metadata to check retirement status."""
        cache_key = f"{template_name}@{template_version}"

        if cache_key in self.template_cache:
            return self.template_cache[cache_key]

        # Search for template metadata in common locations
        search_paths = [
            self.repo_root / "templates" / template_name / template_version / "template_metadata.yaml",
            self.repo_root / "templates" / template_name / "template_metadata.yaml",
            self.repo_root / ".templates" / template_name / template_version / "template_metadata.yaml",
            self.repo_root / "PLANNING" / "templates" / template_name / "template_metadata.yaml",
        ]

        for meta_path in search_paths:
            if meta_path.exists():
                try:
                    with open(meta_path, 'r') as f:
                        metadata = yaml.safe_load(f)
                        self.template_cache[cache_key] = metadata
                        return metadata
                except Exception:
                    continue

        # Template metadata not found - create synthetic entry
        self.template_cache[cache_key] = None
        return None

    def is_template_retired(self, metadata: Optional[dict]) -> Tuple[bool, dict]:
        """Check if a template is retired based on metadata."""
        if metadata is None:
            return False, {}

        retirement_info = {}

        # Check status field
        status = metadata.get("status", "").lower()
        if status == "retired":
            retirement_info["status"] = "retired"
            retirement_info["reason"] = metadata.get("retirement_reason", "No reason specified")

        # Check lifecycle.retirement_date
        lifecycle = metadata.get("lifecycle", {})
        if isinstance(lifecycle, dict):
            retirement_date_str = lifecycle.get("retirement_date")
            if retirement_date_str:
                try:
                    if isinstance(retirement_date_str, str):
                        retirement_date = datetime.fromisoformat(retirement_date_str.replace("Z", "+00:00"))
                    else:
                        retirement_date = retirement_date_str

                    if retirement_date <= datetime.now(retirement_date.tzinfo if hasattr(retirement_date, 'tzinfo') and retirement_date.tzinfo else None):
                        retirement_info["retirement_date"] = str(retirement_date_str)
                        retirement_info["status"] = "retired"
                except Exception:
                    pass

            # Get upgrade path if available
            if "upgrade_path" in lifecycle:
                retirement_info["upgrade_path"] = lifecycle["upgrade_path"]
            if "next_version" in lifecycle:
                retirement_info["next_version"] = lifecycle["next_version"]
            if "migration_guide" in lifecycle:
                retirement_info["migration_guide"] = lifecycle["migration_guide"]

        # Check deprecated_by field
        if "deprecated_by" in metadata:
            retirement_info["deprecated_by"] = metadata["deprecated_by"]

        return "status" in retirement_info and retirement_info["status"] == "retired", retirement_info

    def extract_templates_from_wiring(self, wiring: dict) -> list[dict]:
        """Extract template references from wiring configuration."""
        templates = []

        if not wiring:
            return templates

        # Check 'template' field
        if "template" in wiring:
            template_ref = wiring["template"]
            if isinstance(template_ref, str):
                # Parse "name@version" format
                if "@" in template_ref:
                    name, version = template_ref.rsplit("@", 1)
                else:
                    name, version = template_ref, "latest"
                templates.append({"name": name, "version": version})
            elif isinstance(template_ref, dict):
                templates.append({
                    "name": template_ref.get("name", "unknown"),
                    "version": template_ref.get("version", "latest")
                })

        # Check 'templates' array
        if "templates" in wiring and isinstance(wiring["templates"], list):
            for tmpl in wiring["templates"]:
                if isinstance(tmpl, str):
                    if "@" in tmpl:
                        name, version = tmpl.rsplit("@", 1)
                    else:
                        name, version = tmpl, "latest"
                    templates.append({"name": name, "version": version})
                elif isinstance(tmpl, dict):
                    templates.append({
                        "name": tmpl.get("name", "unknown"),
                        "version": tmpl.get("version", "latest")
                    })

        # Check 'source.template' field
        source = wiring.get("source", {})
        if isinstance(source, dict) and "template" in source:
            template_ref = source["template"]
            if isinstance(template_ref, str):
                if "@" in template_ref:
                    name, version = template_ref.rsplit("@", 1)
                else:
                    name, version = template_ref, "latest"
                templates.append({"name": name, "version": version})

        return templates

    def check_task(self, wiring_path: Path) -> list[dict]:
        """Check a single task for retired template usage."""
        task_id = self.get_task_id(wiring_path)
        self.scanned_tasks.append(task_id)

        if self.verbose:
            print(f"  Scanning task: {task_id} ({wiring_path})")

        wiring = self.load_wiring_file(wiring_path)
        if wiring is None:
            return []

        retired_found = []
        templates = self.extract_templates_from_wiring(wiring)

        for template in templates:
            template_name = template["name"]
            template_version = template["version"]

            if self.verbose:
                print(f"    Checking template: {template_name}@{template_version}")

            metadata = self.load_template_metadata(template_name, template_version)
            is_retired, retirement_info = self.is_template_retired(metadata)

            if is_retired:
                retired_entry = {
                    "task_id": task_id,
                    "wiring_file": str(wiring_path),
                    "template_name": template_name,
                    "template_version": template_version,
                    "retirement_info": retirement_info
                }
                retired_found.append(retired_entry)
                self.retired_usages.append(retired_entry)

        return retired_found

    def check_all_tasks(self) -> int:
        """Check all tasks in the repository for retired templates."""
        wiring_files = self.find_wiring_files()

        if self.verbose:
            print(f"Found {len(wiring_files)} task wiring files to scan\n")

        for wiring_path in wiring_files:
            self.check_task(wiring_path)

        return len(self.retired_usages)

    def generate_fix_suggestions(self) -> list[dict]:
        """Generate suggested fixes for retired template usages."""
        suggestions = []

        for usage in self.retired_usages:
            suggestion = {
                "task_id": usage["task_id"],
                "current_template": f"{usage['template_name']}@{usage['template_version']}",
                "wiring_file": usage["wiring_file"],
                "commands": []
            }

            retirement_info = usage.get("retirement_info", {})

            if "next_version" in retirement_info:
                next_ver = retirement_info["next_version"]
                suggestion["recommended_template"] = f"{usage['template_name']}@{next_ver}"
                suggestion["commands"].append(
                    f"# Update {usage['wiring_file']}: change template version to {next_ver}"
                )
            elif "deprecated_by" in retirement_info:
                suggestion["recommended_template"] = retirement_info["deprecated_by"]
                suggestion["commands"].append(
                    f"# Migrate to: {retirement_info['deprecated_by']}"
                )
            elif "upgrade_path" in retirement_info:
                suggestion["upgrade_path"] = retirement_info["upgrade_path"]
                suggestion["commands"].append(
                    f"# Follow upgrade path: {retirement_info['upgrade_path']}"
                )

            if "migration_guide" in retirement_info:
                suggestion["migration_guide"] = retirement_info["migration_guide"]
                suggestion["commands"].append(
                    f"# See migration guide: {retirement_info['migration_guide']}"
                )

            suggestions.append(suggestion)

        return suggestions

    def format_text_output(self, include_suggestions: bool = False) -> str:
        """Format results as human-readable text."""
        lines = []

        lines.append("=" * 60)
        lines.append("RETIRED TEMPLATE CHECK REPORT")
        lines.append("=" * 60)
        lines.append(f"Scanned: {len(self.scanned_tasks)} tasks")
        lines.append(f"Retired template usages found: {len(self.retired_usages)}")
        lines.append("")

        if self.errors:
            lines.append("⚠️  ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error['file']}: {error['message']}")
            lines.append("")

        if not self.retired_usages:
            lines.append("✅ No retired templates found")
            lines.append("")
            lines.append("All tasks are using supported template versions.")
        else:
            lines.append("❌ RETIRED TEMPLATES DETECTED:")
            lines.append("-" * 40)

            # Group by template
            by_template: dict[str, list] = {}
            for usage in self.retired_usages:
                key = f"{usage['template_name']}@{usage['template_version']}"
                if key not in by_template:
                    by_template[key] = []
                by_template[key].append(usage)

            for template_key, usages in by_template.items():
                lines.append(f"\n🚫 Template: {template_key}")

                # Show retirement info from first usage
                retirement_info = usages[0].get("retirement_info", {})
                if "retirement_date" in retirement_info:
                    lines.append(f"   Retired on: {retirement_info['retirement_date']}")
                if "reason" in retirement_info:
                    lines.append(f"   Reason: {retirement_info['reason']}")
                if "next_version" in retirement_info:
                    lines.append(f"   ➡️  Migrate to: {usages[0]['template_name']}@{retirement_info['next_version']}")

                lines.append(f"\n   Used by {len(usages)} task(s):")
                for usage in usages:
                    lines.append(f"   - Task [{usage['task_id']}]: {usage['wiring_file']}")

            if include_suggestions:
                lines.append("\n" + "=" * 60)
                lines.append("SUGGESTED FIXES")
                lines.append("=" * 60)

                suggestions = self.generate_fix_suggestions()
                for i, suggestion in enumerate(suggestions, 1):
                    lines.append(f"\n{i}. Task: {suggestion['task_id']}")
                    lines.append(f"   Current: {suggestion['current_template']}")
                    if "recommended_template" in suggestion:
                        lines.append(f"   Upgrade to: {suggestion['recommended_template']}")
                    for cmd in suggestion.get("commands", []):
                        lines.append(f"   {cmd}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    def format_json_output(self, include_suggestions: bool = False) -> str:
        """Format results as JSON."""
        result = {
            "summary": {
                "tasks_scanned": len(self.scanned_tasks),
                "retired_usages_found": len(self.retired_usages),
                "errors": len(self.errors),
                "status": "FAIL" if self.retired_usages else "PASS"
            },
            "scanned_tasks": self.scanned_tasks,
            "retired_usages": self.retired_usages,
            "errors": self.errors
        }

        if include_suggestions and self.retired_usages:
            result["suggestions"] = self.generate_fix_suggestions()

        return json.dumps(result, indent=2, default=str)

def main():
    parser = argparse.ArgumentParser(
        description="Check tasks for retired template usage (CI blocking tool)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - No retired templates found (CI passes)
  1 - One or more retired templates found (CI fails)
  2 - Invalid wiring files or metadata errors

Examples:
  %(prog)s                      # Basic check
  %(prog)s --verbose            # Detailed scan output
  %(prog)s --format=json        # JSON output for CI/CD
  %(prog)s --suggest-fixes      # Include migration suggestions
        """
    )

    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory (default: current directory)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with scan details"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--suggest-fixes",
        action="store_true",
        help="Include suggested fixes for retired template usages"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat parsing errors as failures (exit 2)"
    )

    args = parser.parse_args()

    # Run the checker
    checker = RetiredTemplateChecker(
        repo_root=args.repo_root,
        verbose=args.verbose
    )

    retired_count = checker.check_all_tasks()

    # Format and print output
    if args.format == "json":
        print(checker.format_json_output(include_suggestions=args.suggest_fixes))
    else:
        print(checker.format_text_output(include_suggestions=args.suggest_fixes))

    # Determine exit code
    if args.strict and checker.errors:
        sys.exit(2)
    elif retired_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
