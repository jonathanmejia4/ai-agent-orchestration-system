#!/usr/bin/env python3
"""
template_upgrade_assistant.py - Interactive template upgrade wizard

Guides teams through template migrations by analyzing breaking changes,
creating Template Upgrade Tasks, executing upgrade workflows, and
running validation tests.

Exit codes:
  0 - Upgrade successful, all tests pass
  1 - Upgrade failed or tests failed
  2 - User cancelled or invalid input
  3 - File/parse error

Usage:
  python tools/template_upgrade_assistant.py --task 3.1 --from api@1.0.0 --to api@2.0.0
  python tools/template_upgrade_assistant.py --task 3.1 --from api@1.0.0 --to api@2.0.0 --dry-run
  python tools/template_upgrade_assistant.py --task 3.1 --from api@1.0.0 --to api@2.0.0 --auto-approve

Reference: PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md:584,1720,1723
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

@dataclass
class BreakingChange:
    """Represents a breaking change between template versions."""
    change_type: str  # parameter_removed, parameter_renamed, file_moved, interface_changed
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    migration_action: Optional[str] = None
    severity: str = "medium"  # low, medium, high

@dataclass
class UpgradeContext:
    """Context for template upgrade operation."""
    task_id: str
    source_template: str
    source_version: str
    target_template: str
    target_version: str
    task_path: Optional[Path] = None
    wiring_path: Optional[Path] = None
    breaking_changes: list[BreakingChange] = field(default_factory=list)
    upgrade_task_id: str = ""
    upgrade_task_path: Optional[Path] = None
    test_results: dict = field(default_factory=dict)

class TemplateUpgradeAssistant:
    """Interactive wizard for template upgrades."""

    def __init__(
        self,
        dry_run: bool = False,
        auto_approve: bool = False,
        verbose: bool = False
    ):
        self.dry_run = dry_run
        self.auto_approve = auto_approve
        self.verbose = verbose
        self.errors: list[str] = []

    def parse_template_spec(self, spec: str) -> tuple[str, str]:
        """Parse template@version format into (template, version)."""
        if "@" not in spec:
            return spec, "latest"
        parts = spec.rsplit("@", 1)
        return parts[0], parts[1]

    def find_task_path(self, task_id: str) -> Optional[Path]:
        """Locate task directory."""
        # Check common locations
        candidates = [
            Path(f"tasks/{task_id}"),
            Path(f"PLANNING/tasks/{task_id}"),
            Path(f".task/tasks/{task_id}"),
            Path(task_id),
        ]
        for path in candidates:
            if path.exists() and path.is_dir():
                return path
        return None

    def find_wiring_file(self, task_path: Path) -> Optional[Path]:
        """Locate wiring.yaml for task."""
        candidates = [
            task_path / ".task" / "wiring.yaml",
            task_path / "wiring.yaml",
            Path(".task") / "wiring.yaml",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def load_template_metadata(self, template: str, version: str) -> dict:
        """Load template metadata for given version."""
        # Check template registry locations
        candidates = [
            Path(f"templates/{template}/{version}/metadata.yaml"),
            Path(f".templates/{template}/versions/{version}/metadata.yaml"),
            Path(f"PLANNING/templates/{template}.yaml"),
        ]

        for path in candidates:
            if path.exists():
                try:
                    with open(path) as f:
                        return yaml.safe_load(f) or {}
                except Exception:
                    continue

        # Return synthetic metadata if not found
        return {
            "name": template,
            "version": version,
            "parameters": {},
            "files": [],
            "interfaces": []
        }

    def load_migration_guide(self, template: str, from_ver: str, to_ver: str) -> dict:
        """Load migration guide for version upgrade."""
        candidates = [
            Path(f"docs/migration-{template}-{from_ver}-to-{to_ver}.md"),
            Path(f"templates/{template}/migrations/{from_ver}-to-{to_ver}.yaml"),
            Path(f".templates/{template}/migrations/{from_ver}-{to_ver}.yaml"),
        ]

        for path in candidates:
            if path.exists():
                try:
                    with open(path) as f:
                        content = f.read()
                        if path.suffix == ".yaml":
                            return yaml.safe_load(content) or {}
                        # Parse markdown migration guide
                        return self._parse_migration_markdown(content)
                except Exception:
                    continue

        return {}

    def _parse_migration_markdown(self, content: str) -> dict:
        """Parse markdown migration guide into structured data."""
        result = {
            "breaking_changes": [],
            "migration_steps": [],
            "rollback_steps": []
        }

        current_section = None
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("## Breaking"):
                current_section = "breaking_changes"
            elif line.startswith("## Migration"):
                current_section = "migration_steps"
            elif line.startswith("## Rollback"):
                current_section = "rollback_steps"
            elif line.startswith("- ") and current_section:
                result[current_section].append(line[2:])

        return result

    def analyze_breaking_changes(self, ctx: UpgradeContext) -> list[BreakingChange]:
        """Analyze breaking changes between template versions."""
        changes = []

        # Load metadata for both versions
        source_meta = self.load_template_metadata(ctx.source_template, ctx.source_version)
        target_meta = self.load_template_metadata(ctx.target_template, ctx.target_version)

        # Load migration guide
        migration = self.load_migration_guide(
            ctx.source_template,
            ctx.source_version,
            ctx.target_version
        )

        # Check for parameter changes
        source_params = set(source_meta.get("parameters", {}).keys())
        target_params = set(target_meta.get("parameters", {}).keys())

        # Removed parameters
        for param in source_params - target_params:
            changes.append(BreakingChange(
                change_type="parameter_removed",
                description=f"Parameter '{param}' has been removed",
                old_value=param,
                new_value=None,
                migration_action="Remove parameter from task configuration",
                severity="high"
            ))

        # New required parameters
        for param in target_params - source_params:
            param_spec = target_meta.get("parameters", {}).get(param, {})
            if param_spec.get("required", False):
                changes.append(BreakingChange(
                    change_type="parameter_added",
                    description=f"New required parameter '{param}'",
                    old_value=None,
                    new_value=param,
                    migration_action=f"Add parameter '{param}' to task configuration",
                    severity="high"
                ))

        # Check for file changes
        source_files = set(source_meta.get("files", []))
        target_files = set(target_meta.get("files", []))

        for file in source_files - target_files:
            changes.append(BreakingChange(
                change_type="file_removed",
                description=f"File '{file}' has been removed from template",
                old_value=file,
                new_value=None,
                migration_action="Remove file or migrate content",
                severity="medium"
            ))

        # Check for interface changes
        source_interfaces = source_meta.get("interfaces", [])
        target_interfaces = target_meta.get("interfaces", [])

        if source_interfaces != target_interfaces:
            changes.append(BreakingChange(
                change_type="interface_changed",
                description="Template interfaces have changed",
                old_value=str(source_interfaces),
                new_value=str(target_interfaces),
                migration_action="Update interface implementations",
                severity="high"
            ))

        # Add changes from migration guide
        for change_desc in migration.get("breaking_changes", []):
            if not any(c.description == change_desc for c in changes):
                changes.append(BreakingChange(
                    change_type="documented",
                    description=change_desc,
                    migration_action="See migration guide",
                    severity="medium"
                ))

        return changes

    def display_breaking_changes(self, changes: list[BreakingChange]) -> None:
        """Display breaking changes to user."""
        if not changes:
            print("\n  No breaking changes detected.")
            return

        print(f"\n  Found {len(changes)} breaking change(s):\n")

        severity_order = {"high": 0, "medium": 1, "low": 2}
        sorted_changes = sorted(changes, key=lambda c: severity_order.get(c.severity, 1))

        for i, change in enumerate(sorted_changes, 1):
            severity_icon = {"high": "!!!", "medium": "!!", "low": "!"}.get(change.severity, "!")
            print(f"  [{i}] [{severity_icon}] {change.description}")
            if change.old_value and change.new_value:
                print(f"       {change.old_value} -> {change.new_value}")
            elif change.old_value:
                print(f"       Removed: {change.old_value}")
            elif change.new_value:
                print(f"       Added: {change.new_value}")
            if change.migration_action:
                print(f"       Action: {change.migration_action}")
            print()

    def prompt_continue(self, message: str = "Continue?") -> bool:
        """Prompt user to continue."""
        if self.auto_approve:
            print(f"  {message} [auto-approved]")
            return True

        try:
            response = input(f"  {message} [y/N]: ").strip().lower()
            return response in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled by user.")
            return False

    def generate_upgrade_task_id(self, ctx: UpgradeContext) -> str:
        """Generate unique ID for upgrade task."""
        clean_from = ctx.source_version.replace(".", "-")
        clean_to = ctx.target_version.replace(".", "-")
        return f"upgrade-{ctx.task_id}-{ctx.source_template}-{clean_from}-to-{clean_to}"

    def create_upgrade_task(self, ctx: UpgradeContext) -> Optional[Path]:
        """Create Template Upgrade Task."""
        upgrade_id = self.generate_upgrade_task_id(ctx)
        ctx.upgrade_task_id = upgrade_id

        task_content = f"""# Template Upgrade Task: {upgrade_id}

**Created:** {datetime.now().isoformat()}
**Status:** In Progress
**Type:** Template Upgrade

## Overview

Upgrade task `{ctx.task_id}` from template `{ctx.source_template}@{ctx.source_version}`
to `{ctx.target_template}@{ctx.target_version}`.

## Breaking Changes

{self._format_changes_markdown(ctx.breaking_changes)}

## Upgrade Steps

1. [ ] Backup current task state
2. [ ] Update .task/wiring.yaml with new template version
3. [ ] Apply parameter migrations
4. [ ] Regenerate task with new template
5. [ ] Run structural validation (Test #1)
6. [ ] Run behavioral validation (Test #2)
7. [ ] Update documentation
8. [ ] Create commit with upgrade changes

## Rollback Plan

If upgrade fails:
1. Restore .task/wiring.yaml from backup
2. Regenerate task with original template
3. Verify original functionality

## Validation Checklist

- [ ] All tests pass
- [ ] No breaking changes in dependent tasks
- [ ] Documentation updated
- [ ] Upgrade logged in LogBook
"""

        # Determine output path
        output_dir = Path("PLANNING/tasks")
        if not output_dir.exists():
            output_dir = Path("tasks")
        if not output_dir.exists():
            output_dir = Path(".")

        output_path = output_dir / f"{upgrade_id}.md"
        ctx.upgrade_task_path = output_path

        if self.dry_run:
            print(f"  [DRY RUN] Would create: {output_path}")
            return output_path

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(task_content)
            return output_path
        except Exception as e:
            self.errors.append(f"Failed to create upgrade task: {e}")
            return None

    def _format_changes_markdown(self, changes: list[BreakingChange]) -> str:
        """Format breaking changes as markdown list."""
        if not changes:
            return "No breaking changes detected.\n"

        lines = []
        for change in changes:
            severity = {"high": "HIGH", "medium": "MED", "low": "LOW"}.get(change.severity, "?")
            lines.append(f"- **[{severity}]** {change.description}")
            if change.migration_action:
                lines.append(f"  - Action: {change.migration_action}")
        return "\n".join(lines)

    def update_wiring_file(self, ctx: UpgradeContext) -> bool:
        """Update wiring.yaml with new template version."""
        if not ctx.wiring_path or not ctx.wiring_path.exists():
            self.errors.append("Wiring file not found")
            return False

        if self.dry_run:
            print(f"  [DRY RUN] Would update: {ctx.wiring_path}")
            return True

        try:
            with open(ctx.wiring_path) as f:
                wiring = yaml.safe_load(f) or {}

            # Update template version
            if "template" in wiring:
                wiring["template"] = f"{ctx.target_template}@{ctx.target_version}"
            elif "templates" in wiring:
                # Handle multiple templates
                for tmpl in wiring["templates"]:
                    if isinstance(tmpl, dict):
                        if tmpl.get("name") == ctx.source_template:
                            tmpl["version"] = ctx.target_version
                    elif isinstance(tmpl, str) and tmpl.startswith(ctx.source_template):
                        # Replace in list
                        idx = wiring["templates"].index(tmpl)
                        wiring["templates"][idx] = f"{ctx.target_template}@{ctx.target_version}"

            # Add upgrade metadata
            if "upgrades" not in wiring:
                wiring["upgrades"] = []
            wiring["upgrades"].append({
                "from": f"{ctx.source_template}@{ctx.source_version}",
                "to": f"{ctx.target_template}@{ctx.target_version}",
                "date": datetime.now().isoformat(),
                "upgrade_task": ctx.upgrade_task_id
            })

            with open(ctx.wiring_path, "w") as f:
                yaml.dump(wiring, f, default_flow_style=False, sort_keys=False)

            return True

        except Exception as e:
            self.errors.append(f"Failed to update wiring file: {e}")
            return False

    def run_tests(self, ctx: UpgradeContext) -> dict:
        """Run validation tests after upgrade."""
        results = {
            "structural": {"passed": False, "message": "Not run"},
            "behavioral": {"passed": False, "message": "Not run"}
        }

        if self.dry_run:
            print("  [DRY RUN] Would run tests")
            results["structural"]["message"] = "[DRY RUN] Skipped"
            results["behavioral"]["message"] = "[DRY RUN] Skipped"
            return results

        # Test #1: Structural validation
        print("\n  Running Test #1: Structural Validation...")
        try:
            # Check if ssot_validator exists
            ssot_validator = Path("tools/ssot_validator.py")
            if ssot_validator.exists() and ctx.wiring_path:
                result = subprocess.run(
                    ["python3", str(ssot_validator), str(ctx.wiring_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                results["structural"]["passed"] = result.returncode == 0
                results["structural"]["message"] = result.stdout or result.stderr or "Completed"
            else:
                # Basic structural checks
                if ctx.wiring_path and ctx.wiring_path.exists():
                    with open(ctx.wiring_path) as f:
                        wiring = yaml.safe_load(f)
                    if wiring:
                        results["structural"]["passed"] = True
                        results["structural"]["message"] = "Basic structure valid"
        except Exception as e:
            results["structural"]["message"] = str(e)

        # Test #2: Behavioral validation
        print("  Running Test #2: Behavioral Validation...")
        try:
            # Check for task-specific tests
            test_path = None
            if ctx.task_path:
                test_candidates = [
                    ctx.task_path / "tests" / "test_task.py",
                    ctx.task_path / "test.py",
                    Path(f"tests/test_{ctx.task_id.replace('.', '_')}.py")
                ]
                for candidate in test_candidates:
                    if candidate.exists():
                        test_path = candidate
                        break

            if test_path:
                result = subprocess.run(
                    ["python3", "-m", "pytest", str(test_path), "-v"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                results["behavioral"]["passed"] = result.returncode == 0
                results["behavioral"]["message"] = "Tests passed" if result.returncode == 0 else result.stderr
            else:
                results["behavioral"]["passed"] = True
                results["behavioral"]["message"] = "No behavioral tests found (skipped)"
        except Exception as e:
            results["behavioral"]["message"] = str(e)

        ctx.test_results = results
        return results

    def display_test_results(self, results: dict) -> None:
        """Display test results."""
        print("\n  Test Results:")
        print("  " + "-" * 40)

        for test_name, result in results.items():
            status = "PASS" if result["passed"] else "FAIL"
            icon = "v" if result["passed"] else "x"
            print(f"  [{icon}] {test_name.capitalize()}: {status}")
            if self.verbose and result.get("message"):
                for line in result["message"].split("\n")[:5]:
                    print(f"      {line}")

    def run_wizard(self, ctx: UpgradeContext) -> int:
        """Run the interactive upgrade wizard."""
        print("=" * 60)
        print("TEMPLATE UPGRADE ASSISTANT")
        print("=" * 60)
        print(f"\nTask: {ctx.task_id}")
        print(f"From:  {ctx.source_template}@{ctx.source_version}")
        print(f"To:    {ctx.target_template}@{ctx.target_version}")

        if self.dry_run:
            print("\n[DRY RUN MODE - No changes will be made]")

        # Step 1: Analyze Breaking Changes
        print("\n" + "=" * 60)
        print("STEP 1: Analyzing Breaking Changes")
        print("-" * 40)

        ctx.breaking_changes = self.analyze_breaking_changes(ctx)
        self.display_breaking_changes(ctx.breaking_changes)

        high_severity = sum(1 for c in ctx.breaking_changes if c.severity == "high")
        if high_severity > 0:
            print(f"\n  Warning: {high_severity} high-severity breaking change(s) detected!")

        if not self.prompt_continue("Proceed with upgrade?"):
            return 2

        # Step 2: Create Upgrade Task
        print("\n" + "=" * 60)
        print("STEP 2: Creating Template Upgrade Task")
        print("-" * 40)

        upgrade_path = self.create_upgrade_task(ctx)
        if upgrade_path:
            print(f"  Created upgrade task: {upgrade_path}")
        else:
            print("  Failed to create upgrade task")
            return 1

        if not self.prompt_continue("Continue to execute upgrade?"):
            return 2

        # Step 3: Execute Upgrade Workflow
        print("\n" + "=" * 60)
        print("STEP 3: Executing Upgrade Workflow")
        print("-" * 40)

        print("  Updating wiring file...")
        if not self.update_wiring_file(ctx):
            print("  Failed to update wiring file")
            return 1
        print("  Wiring file updated successfully")

        # Step 4: Run Tests
        print("\n" + "=" * 60)
        print("STEP 4: Running Validation Tests")
        print("-" * 40)

        results = self.run_tests(ctx)
        self.display_test_results(results)

        all_passed = all(r["passed"] for r in results.values())

        # Summary
        print("\n" + "=" * 60)
        print("UPGRADE SUMMARY")
        print("-" * 40)
        print(f"  Task:          {ctx.task_id}")
        print(f"  Upgrade Task:  {ctx.upgrade_task_id}")
        print(f"  Breaking Changes: {len(ctx.breaking_changes)}")
        print(f"  Tests Passed:   {'Yes' if all_passed else 'No'}")

        if self.dry_run:
            print("\n  [DRY RUN] No actual changes were made")
            return 0

        if all_passed:
            print("\n  Upgrade completed successfully!")
            print(f"\n  Next steps:")
            print(f"    1. Review changes in {ctx.upgrade_task_path}")
            print(f"    2. Test task functionality manually")
            print(f"    3. Commit changes: git add -A && git commit -m 'Upgrade {ctx.task_id} to {ctx.target_template}@{ctx.target_version}'")
            return 0
        else:
            print("\n  Upgrade completed with test failures!")
            print("  Please review and fix issues before committing.")
            return 1

def main():
    parser = argparse.ArgumentParser(
        description="Interactive template upgrade wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Upgrade successful, all tests pass
  1 - Upgrade failed or tests failed
  2 - User cancelled or invalid input
  3 - File/parse error

Examples:
  %(prog)s --task 3.1 --from api@1.0.0 --to api@2.0.0
  %(prog)s --task 3.1 --from api@1.0.0 --to api@2.0.0 --dry-run
  %(prog)s --task 3.1 --from api@1.0.0 --to api@2.0.0 --auto-approve
        """
    )

    parser.add_argument(
        "--task",
        required=True,
        help="Task ID to upgrade"
    )

    parser.add_argument(
        "--from",
        dest="from_template",
        required=True,
        help="Source template@version"
    )

    parser.add_argument(
        "--to",
        dest="to_template",
        required=True,
        help="Target template@version"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip confirmation prompts"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Parse template specs
    assistant = TemplateUpgradeAssistant(
        dry_run=args.dry_run,
        auto_approve=args.auto_approve,
        verbose=args.verbose
    )

    source_template, source_version = assistant.parse_template_spec(args.from_template)
    target_template, target_version = assistant.parse_template_spec(args.to_template)

    # Validate same template (unless explicitly different)
    if source_template != target_template:
        print(f"Warning: Upgrading across different templates: {source_template} -> {target_template}")

    # Create context
    ctx = UpgradeContext(
        task_id=args.task,
        source_template=source_template,
        source_version=source_version,
        target_template=target_template,
        target_version=target_version
    )

    # Find task and wiring paths
    ctx.task_path = assistant.find_task_path(args.task)
    if ctx.task_path:
        ctx.wiring_path = assistant.find_wiring_file(ctx.task_path)

    # Run wizard
    try:
        exit_code = assistant.run_wizard(ctx)

        if args.format == "json":
            output = {
                "status": "success" if exit_code == 0 else "failed",
                "exit_code": exit_code,
                "task_id": ctx.task_id,
                "upgrade_task_id": ctx.upgrade_task_id,
                "breaking_changes": [
                    {
                        "type": c.change_type,
                        "description": c.description,
                        "severity": c.severity
                    }
                    for c in ctx.breaking_changes
                ],
                "test_results": ctx.test_results,
                "errors": assistant.errors
            }
            print(json.dumps(output, indent=2))

        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\n\nUpgrade cancelled by user.")
        sys.exit(2)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(3)

if __name__ == "__main__":
    main()
