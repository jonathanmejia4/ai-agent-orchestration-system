#!/usr/bin/env python3
"""
Rollback Event Validator
Version: 1.0.0
Last Updated: 2026-01-05
Owner: PM
Classification: HIGH - Event Validation

Validates rollback event files against rollback_event_schema.yaml.

Usage:
    python tools/validate_rollback.py <rollback_file>
    python tools/validate_rollback.py --check-all
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

@dataclass
class ValidationResult:
    """Result of validating a rollback event."""
    file: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    passed: bool

# Required fields (matches rollback_event_schema.yaml:13-18)
REQUIRED_FIELDS = [
    'rollback_id',
    'timestamp',
    'trigger',
    'target',
    'status',
]

# Valid trigger.type values (matches rollback_event_schema.yaml:42-47)
VALID_TRIGGER_TYPES = ['automatic', 'manual', 'escalation', 'failure']

# Valid target.type values (matches rollback_event_schema.yaml:71-78)
VALID_TARGET_TYPES = ['task', 'work_order', 'commit', 'state', 'configuration']

# Valid status values (matches rollback_event_schema.yaml:91-97)
VALID_STATUSES = ['pending', 'in_progress', 'completed', 'failed', 'cancelled']

# Valid step.status values (matches rollback_event_schema.yaml:128)
VALID_STEP_STATUSES = ['pending', 'in_progress', 'completed', 'failed', 'skipped']

# Valid resource_type values (matches rollback_event_schema.yaml:142)
VALID_RESOURCE_TYPES = ['file', 'directory', 'state', 'configuration', 'database']

# Valid action values (matches rollback_event_schema.yaml:147)
VALID_ACTIONS = ['restored', 'deleted', 'modified', 'created']

# Pattern for rollback_id (matches rollback_event_schema.yaml:22-23)
ROLLBACK_ID_PATTERN = r'^RB-[0-9]{4}-[0-9]{3}$'

# Pattern for work_order_id (matches rollback_event_schema.yaml:57)
WORK_ORDER_ID_PATTERN = r'^WO-[0-9]{8}-[0-9]{3}$'

# Pattern for escalation_id (matches rollback_event_schema.yaml:61)
ESCALATION_ID_PATTERN = r'^ESC-[0-9]{4}-[0-9]{3}$'

class RollbackValidator:
    """Validates rollback event files."""

    DEFAULT_SCHEMA_PATH = Path("PLANNING/schemas/rollback_event_schema.yaml")

    def __init__(self, schema_path: Path = None):
        if schema_path is None:
            schema_path = self.DEFAULT_SCHEMA_PATH
        self.schema_path = schema_path
        self.schema = self._load_schema()

    def _load_schema(self) -> Optional[Dict]:
        """Load validation schema."""
        if not self.schema_path or not self.schema_path.exists():
            script_dir = Path(__file__).parent.parent
            alt_path = script_dir / self.schema_path
            if alt_path.exists():
                self.schema_path = alt_path
            else:
                return None
        with open(self.schema_path, 'r') as f:
            return yaml.safe_load(f)

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single rollback event file."""
        issues: List[str] = []
        warnings: List[str] = []

        if not file_path.exists():
            return ValidationResult(
                file=str(file_path),
                status="error",
                issues=[f"File not found: {file_path}"],
                warnings=[],
                passed=False
            )

        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return ValidationResult(
                file=str(file_path),
                status="error",
                issues=[f"YAML parse error: {e}"],
                warnings=[],
                passed=False
            )

        if not isinstance(data, dict):
            return ValidationResult(
                file=str(file_path),
                status="error",
                issues=["Rollback event must be a YAML mapping"],
                warnings=[],
                passed=False
            )

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate rollback_id pattern
        if 'rollback_id' in data:
            rb_id = data['rollback_id']
            if not isinstance(rb_id, str) or not re.match(ROLLBACK_ID_PATTERN, rb_id):
                issues.append(f"Invalid rollback_id format: {rb_id}. Expected: RB-YYYY-NNN")

        # Validate status
        if 'status' in data:
            if data['status'] not in VALID_STATUSES:
                issues.append(f"Invalid status: {data['status']}. Valid: {VALID_STATUSES}")

        # Validate trigger
        if 'trigger' in data:
            trigger_issues, trigger_warnings = self._validate_trigger(data['trigger'])
            issues.extend(trigger_issues)
            warnings.extend(trigger_warnings)

        # Validate target
        if 'target' in data:
            target_issues, target_warnings = self._validate_target(data['target'])
            issues.extend(target_issues)
            warnings.extend(target_warnings)

        # Validate execution if present
        if 'execution' in data and isinstance(data['execution'], dict):
            exec_issues, exec_warnings = self._validate_execution(data['execution'])
            issues.extend(exec_issues)
            warnings.extend(exec_warnings)

        # Validate affected_resources if present
        if 'affected_resources' in data and isinstance(data['affected_resources'], list):
            res_issues, res_warnings = self._validate_affected_resources(data['affected_resources'])
            issues.extend(res_issues)
            warnings.extend(res_warnings)

        # Check for recommended fields
        recommended = ['execution', 'verification', 'result']
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
            file=str(file_path),
            status=status,
            issues=issues,
            warnings=warnings,
            passed=passed
        )

    def _validate_trigger(self, trigger: Any) -> tuple[List[str], List[str]]:
        """Validate trigger object."""
        issues = []
        warnings = []

        if not isinstance(trigger, dict):
            issues.append("trigger must be an object")
            return issues, warnings

        # Required fields in trigger
        if 'type' not in trigger:
            issues.append("trigger missing required field: type")
        elif trigger['type'] not in VALID_TRIGGER_TYPES:
            issues.append(f"Invalid trigger.type: {trigger['type']}. Valid: {VALID_TRIGGER_TYPES}")

        if 'source' not in trigger:
            issues.append("trigger missing required field: source")

        # Validate related_work_order pattern if present
        if 'related_work_order' in trigger:
            wo_id = trigger['related_work_order']
            if not isinstance(wo_id, str) or not re.match(WORK_ORDER_ID_PATTERN, wo_id):
                issues.append(f"Invalid trigger.related_work_order format: {wo_id}. Expected: WO-YYYYMMDD-NNN")

        # Validate related_escalation pattern if present
        if 'related_escalation' in trigger:
            esc_id = trigger['related_escalation']
            if not isinstance(esc_id, str) or not re.match(ESCALATION_ID_PATTERN, esc_id):
                issues.append(f"Invalid trigger.related_escalation format: {esc_id}. Expected: ESC-YYYY-NNN")

        return issues, warnings

    def _validate_target(self, target: Any) -> tuple[List[str], List[str]]:
        """Validate target object."""
        issues = []
        warnings = []

        if not isinstance(target, dict):
            issues.append("target must be an object")
            return issues, warnings

        # Required fields in target
        if 'type' not in target:
            issues.append("target missing required field: type")
        elif target['type'] not in VALID_TARGET_TYPES:
            issues.append(f"Invalid target.type: {target['type']}. Valid: {VALID_TARGET_TYPES}")

        if 'identifier' not in target:
            issues.append("target missing required field: identifier")

        return issues, warnings

    def _validate_execution(self, execution: Dict) -> tuple[List[str], List[str]]:
        """Validate execution object."""
        issues = []
        warnings = []

        # Validate steps if present
        if 'steps' in execution and isinstance(execution['steps'], list):
            for i, step in enumerate(execution['steps']):
                if not isinstance(step, dict):
                    issues.append(f"execution.steps[{i}] must be an object")
                    continue
                if 'status' in step and step['status'] not in VALID_STEP_STATUSES:
                    issues.append(f"Invalid execution.steps[{i}].status: {step['status']}. Valid: {VALID_STEP_STATUSES}")

        return issues, warnings

    def _validate_affected_resources(self, resources: List) -> tuple[List[str], List[str]]:
        """Validate affected_resources array."""
        issues = []
        warnings = []

        for i, resource in enumerate(resources):
            if not isinstance(resource, dict):
                issues.append(f"affected_resources[{i}] must be an object")
                continue

            if 'resource_type' in resource and resource['resource_type'] not in VALID_RESOURCE_TYPES:
                issues.append(f"Invalid affected_resources[{i}].resource_type: {resource['resource_type']}. Valid: {VALID_RESOURCE_TYPES}")

            if 'action' in resource and resource['action'] not in VALID_ACTIONS:
                issues.append(f"Invalid affected_resources[{i}].action: {resource['action']}. Valid: {VALID_ACTIONS}")

        return issues, warnings

    def validate_all(self, rollbacks_dir: Path = None) -> List[ValidationResult]:
        """Validate all rollback event files."""
        rollbacks_dir = rollbacks_dir or Path("LogBook/rollback")
        results = []

        if not rollbacks_dir.exists():
            return results

        for rb_file in rollbacks_dir.rglob("*.yaml"):
            if 'schema' not in rb_file.name:
                result = self.validate_file(rb_file)
                results.append(result)

        for rb_file in rollbacks_dir.rglob("*.yml"):
            if 'schema' not in rb_file.name:
                result = self.validate_file(rb_file)
                results.append(result)

        return results

def format_text(results: List[ValidationResult]) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Rollback Event Validation Results")
    lines.append("=" * 60)
    lines.append("")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    for result in results:
        status_icon = "+" if result.passed else "X"
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
        description="Validate rollback event files against schema"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to rollback event file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all rollback events in LogBook/rollback"
    )
    parser.add_argument(
        "--rollbacks-dir",
        type=Path,
        default=Path("LogBook/rollback"),
        help="Directory containing rollback event files"
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

    validator = RollbackValidator()

    if args.check_all:
        results = validator.validate_all(args.rollbacks_dir)
    elif args.file:
        results = [validator.validate_file(Path(args.file))]
    else:
        results = validator.validate_all(args.rollbacks_dir)

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
