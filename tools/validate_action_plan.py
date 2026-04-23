#!/usr/bin/env python3
"""
Action Plan Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Planner
Classification: HIGH - Work Order Validation

Validates action plan files for completeness and correctness.

Usage:
    python tools/validate_action_plan.py <action_plan_file>
    python tools/validate_action_plan.py --check-all
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

@dataclass
class ValidationResult:
    """Result of validating an action plan."""
    file: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    passed: bool

# Required fields for action plans (matches action_plan_schema.yaml)
REQUIRED_FIELDS = [
    'plan_id',
    'version',
    'work_order_id',
    'created_at',
    'created_by',
    'status',
    'actions',
]

# Required fields for each action (matches action_plan_schema.yaml)
ACTION_REQUIRED_FIELDS = [
    'action_id',
    'type',
    'description',
    'status',
]

# Valid plan status values (matches action_plan_schema.yaml status enum)
# Plan lifecycle: draft -> pending_review -> approved -> in_progress -> completed/cancelled/failed
VALID_STATUSES = ['draft', 'pending_review', 'approved', 'in_progress', 'completed', 'cancelled', 'failed']

# Valid action status values (matches action_plan_schema.yaml action status enum)
# Action lifecycle: pending -> in_progress -> completed/skipped/failed/blocked
ACTION_VALID_STATUSES = ['pending', 'in_progress', 'completed', 'skipped', 'failed', 'blocked']

class ActionPlanValidator:
    """Validates action plan files."""

    # Default schema path
    DEFAULT_SCHEMA_PATH = Path("PLANNING/schemas/action_plan_schema.yaml")

    def __init__(self, schema_path: Path = None):
        # Use default schema if none provided
        if schema_path is None:
            schema_path = self.DEFAULT_SCHEMA_PATH
        self.schema_path = schema_path
        self.schema = self._load_schema()

    def _load_schema(self) -> Optional[Dict]:
        """Load validation schema (defaults to action_plan_schema.yaml)."""
        if not self.schema_path or not self.schema_path.exists():
            # Try relative to script location
            script_dir = Path(__file__).parent.parent
            alt_path = script_dir / self.schema_path
            if alt_path.exists():
                self.schema_path = alt_path
            else:
                return None
        with open(self.schema_path, 'r') as f:
            return yaml.safe_load(f)

    def validate_file(self, plan_path: Path) -> ValidationResult:
        """Validate a single action plan file."""
        issues: List[str] = []
        warnings: List[str] = []

        if not plan_path.exists():
            return ValidationResult(
                file=str(plan_path),
                status="error",
                issues=[f"File not found: {plan_path}"],
                warnings=[],
                passed=False
            )

        try:
            with open(plan_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return ValidationResult(
                file=str(plan_path),
                status="error",
                issues=[f"YAML parse error: {e}"],
                warnings=[],
                passed=False
            )

        if not isinstance(data, dict):
            return ValidationResult(
                file=str(plan_path),
                status="error",
                issues=["Action plan must be a YAML mapping"],
                warnings=[],
                passed=False
            )

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate status
        if 'status' in data:
            status = data['status']
            if status not in VALID_STATUSES:
                issues.append(f"Invalid status: {status}. Valid: {VALID_STATUSES}")

        # Validate actions
        if 'actions' in data:
            action_issues, action_warnings = self._validate_actions(data['actions'])
            issues.extend(action_issues)
            warnings.extend(action_warnings)
        else:
            issues.append("No actions defined in action plan")

        # Validate dependencies
        if 'actions' in data and isinstance(data['actions'], list):
            dep_issues = self._validate_dependencies(data['actions'])
            issues.extend(dep_issues)

        # Check for recommended fields
        recommended = ['created_at', 'author', 'task_id', 'priority']
        for field in recommended:
            if field not in data:
                warnings.append(f"Missing recommended field: {field}")

        # Determine status
        if issues:
            status = "error"
            passed = False
        elif warnings:
            status = "warning"
            passed = True
        else:
            status = "valid"
            passed = True

        return ValidationResult(
            file=str(plan_path),
            status=status,
            issues=issues,
            warnings=warnings,
            passed=passed
        )

    def _validate_actions(self, actions: Any) -> tuple[List[str], List[str]]:
        """Validate actions in action plan."""
        issues = []
        warnings = []

        if not isinstance(actions, list):
            issues.append("Actions must be a list")
            return issues, warnings

        if len(actions) == 0:
            warnings.append("Action plan has no actions")
            return issues, warnings

        action_ids = set()
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                issues.append(f"Action {i} must be a mapping")
                continue

            # Check required action fields
            for field in ACTION_REQUIRED_FIELDS:
                if field not in action:
                    issues.append(f"Action {i} missing required field: {field}")

            # Check for duplicate IDs
            action_id = action.get('action_id')
            if action_id:
                if action_id in action_ids:
                    issues.append(f"Duplicate action ID: {action_id}")
                action_ids.add(action_id)

            # Validate action status
            action_status = action.get('status')
            if action_status and action_status not in ACTION_VALID_STATUSES:
                issues.append(f"Action {i} has invalid status: {action_status}. Valid: {ACTION_VALID_STATUSES}")

        return issues, warnings

    def _validate_dependencies(self, actions: List[Dict]) -> List[str]:
        """Validate action dependencies are valid."""
        issues = []
        action_ids = {action.get('action_id') for action in actions if action.get('action_id')}

        for action in actions:
            deps = action.get('dependencies', [])
            if isinstance(deps, str):
                deps = [deps]

            for dep in deps:
                if dep not in action_ids:
                    issues.append(
                        f"Action '{action.get('action_id')}' depends on unknown action: {dep}"
                    )

        return issues

    def validate_all(self, plans_dir: Path = None) -> List[ValidationResult]:
        """Validate all action plan files."""
        plans_dir = plans_dir or Path("PLANNING/action_plans")
        results = []

        if not plans_dir.exists():
            return results

        for plan_file in plans_dir.rglob("*.yaml"):
            if 'schema' not in plan_file.name:
                result = self.validate_file(plan_file)
                results.append(result)

        return results

def format_text(results: List[ValidationResult]) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Action Plan Validation Results")
    lines.append("=" * 60)
    lines.append("")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    for result in results:
        status_icon = "✓" if result.passed else "✗"
        lines.append(f"{status_icon} {result.file}: {result.status}")

        for issue in result.issues:
            lines.append(f"  ERROR: {issue}")
        for warning in result.warnings:
            lines.append(f"  WARN: {warning}")

        if result.issues or result.warnings:
            lines.append("")

    lines.append("=" * 60)
    lines.append(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")
    lines.append("=" * 60)

    return "\n".join(lines)

def format_json(results: List[ValidationResult]) -> str:
    """Format results as JSON."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [asdict(r) for r in results]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate action plan files"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to action plan file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all action plans in PLANNING/action_plans"
    )
    parser.add_argument(
        "--plans-dir",
        type=Path,
        default=Path("PLANNING/action_plans"),
        help="Directory containing action plans"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file"
    )

    args = parser.parse_args()

    validator = ActionPlanValidator()

    if args.check_all:
        results = validator.validate_all(args.plans_dir)
    elif args.file:
        results = [validator.validate_file(Path(args.file))]
    else:
        # Default: validate all
        results = validator.validate_all(args.plans_dir)

    # Format output
    if args.format == "json":
        output = format_json(results)
    else:
        output = format_text(results)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Exit code
    sys.exit(0 if all(r.passed for r in results) else 1)

if __name__ == "__main__":
    main()
