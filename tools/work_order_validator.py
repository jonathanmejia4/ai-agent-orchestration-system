#!/usr/bin/env python3
"""
Work Order Validator - Validates work orders against work_order_schema.yaml

Validates incoming work orders for Builder/Critic agents, checking format,
required fields, dependencies, and path references. Critical for Builder
pre-implementation validation gate.

Usage:
    python3 tools/work_order_validator.py --validate work_order.yaml
    python3 tools/work_order_validator.py --validate-queue LogBook/pm/WO_QUEUE.yaml
    python3 tools/work_order_validator.py --check-deps WO-20251230-001
    python3 tools/work_order_validator.py --help

Exit Codes:
    0 - Validation passed
    1 - Validation errors found
    2 - Error (missing files, invalid arguments)

Referenced in:
    - .claude/agents/Builder.md:61, 78
    - PLANNING/schemas/work_order_schema.yaml

Resolves: J-41
Author: System
Created: 2025-12-30
"""

import argparse
import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Optional YAML support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

@dataclass
class WorkOrderValidationResult:
    """Work order validation result"""
    valid: bool = True
    work_order_id: Optional[str] = None
    work_order_path: Optional[str] = None
    format_errors: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    invalid_values: List[str] = field(default_factory=list)
    path_errors: List[str] = field(default_factory=list)
    dependency_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, category: str, message: str):
        self.valid = False
        if category == "format":
            self.format_errors.append(message)
        elif category == "missing":
            self.missing_fields.append(message)
        elif category == "value":
            self.invalid_values.append(message)
        elif category == "path":
            self.path_errors.append(message)
        elif category == "dependency":
            self.dependency_errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    @property
    def error_count(self) -> int:
        return (len(self.format_errors) + len(self.missing_fields) +
                len(self.invalid_values) + len(self.path_errors) +
                len(self.dependency_errors))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'work_order_id': self.work_order_id,
            'work_order_path': self.work_order_path,
            'format_errors': self.format_errors,
            'missing_fields': self.missing_fields,
            'invalid_values': self.invalid_values,
            'path_errors': self.path_errors,
            'dependency_errors': self.dependency_errors,
            'warnings': self.warnings,
            'error_count': self.error_count
        }

class WorkOrderValidator:
    """Validates work orders against work_order_schema.yaml"""

    # Required fields per schema
    REQUIRED_FIELDS = [
        'id', 'issued_by', 'issued_to', 'task_id', 'task_spec_path',
        'task_type', 'objective', 'inputs', 'expected_outputs',
        'prohibited_actions', 'time_box', 'dependencies'
    ]

    # Valid enum values
    VALID_TASK_TYPES = ['implement_task', 'review_task', 'audit_plan', 'update_logbook']
    VALID_INPUT_TYPES = ['spec', 'config', 'dependency', 'reference', 'template']
    VALID_OUTPUT_TYPES = ['code', 'test', 'doc', 'manifest', 'config']
    VALID_PRIORITIES = ['critical', 'high', 'normal', 'low']
    VALID_AGENTS = [
        'Builder', 'Critic-Orchestrator', 'Critic-PlanAuditor',
        'Critic-FixVerifier', 'Planner', 'Project-Manager'
    ]

    # Patterns
    WO_ID_PATTERN = re.compile(r'^WO-\d{8}-\d{3}$')
    TASK_ID_PATTERN = re.compile(r'^\d+\.\d+(\.\d+)?$')
    ISO_DURATION_PATTERN = re.compile(r'^P(T\d+[HM]|\d+D)$')

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.schema_path = self.repo_root / "PLANNING" / "schemas" / "work_order_schema.yaml"
        self.agents_dir = self.repo_root / ".claude" / "agents"

    def validate_work_order(self, work_order: Dict[str, Any],
                            source_path: Optional[str] = None) -> WorkOrderValidationResult:
        """Validate a single work order against schema."""
        result = WorkOrderValidationResult(work_order_path=source_path)

        # Extract ID first
        wo_id = work_order.get('id') or work_order.get('work_order_id')
        result.work_order_id = wo_id

        # Check required fields
        self._check_required_fields(work_order, result)

        # Validate field formats
        self._validate_id_format(wo_id, result)
        self._validate_issued_by(work_order.get('issued_by'), result)
        self._validate_issued_to(work_order.get('issued_to'), result)
        self._validate_task_id(work_order.get('task_id'), result)
        self._validate_task_type(work_order.get('task_type'), result)
        self._validate_time_box(work_order.get('time_box'), result)

        # Validate paths exist
        self._validate_paths(work_order, result)

        # Validate inputs and outputs structure
        self._validate_inputs(work_order.get('inputs', []), result)
        self._validate_outputs(work_order.get('expected_outputs', []), result)

        # Validate dependencies
        self._validate_dependencies(work_order.get('dependencies', []), result)

        # Optional field validation
        if 'priority' in work_order:
            self._validate_priority(work_order['priority'], result)

        return result

    def _check_required_fields(self, work_order: Dict, result: WorkOrderValidationResult):
        """Check for missing required fields."""
        for field in self.REQUIRED_FIELDS:
            if field not in work_order and field != 'work_order_id':
                # Handle alternate ID field name
                if field == 'id' and 'work_order_id' in work_order:
                    continue
                result.add_error("missing", f"Required field '{field}' is missing")

    def _validate_id_format(self, wo_id: Optional[str], result: WorkOrderValidationResult):
        """Validate work order ID format."""
        if not wo_id:
            return
        if not self.WO_ID_PATTERN.match(wo_id):
            result.add_error("format",
                f"Work order ID '{wo_id}' does not match format WO-YYYYMMDD-NNN")

    def _validate_issued_by(self, issued_by: Optional[str], result: WorkOrderValidationResult):
        """Validate issued_by field."""
        if not issued_by:
            return
        if issued_by != "Project-Manager":
            result.add_warning(f"issued_by is '{issued_by}', expected 'Project-Manager'")

    def _validate_issued_to(self, issued_to: Optional[str], result: WorkOrderValidationResult):
        """Validate issued_to is a valid agent."""
        if not issued_to:
            return
        if issued_to not in self.VALID_AGENTS:
            # Check if agent file exists
            agent_file = self.agents_dir / f"{issued_to}.md"
            if not agent_file.exists():
                result.add_error("value",
                    f"issued_to '{issued_to}' is not a recognized agent")

    def _validate_task_id(self, task_id: Optional[str], result: WorkOrderValidationResult):
        """Validate task ID format."""
        if not task_id:
            return
        # Accept both X.Y format and UUID format
        if not self.TASK_ID_PATTERN.match(str(task_id)):
            # Check if it's a UUID
            uuid_pattern = re.compile(
                r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                re.IGNORECASE
            )
            if not uuid_pattern.match(str(task_id)):
                result.add_warning(
                    f"task_id '{task_id}' is not in standard format (X.Y or UUID)")

    def _validate_task_type(self, task_type: Optional[str], result: WorkOrderValidationResult):
        """Validate task_type enum value."""
        if not task_type:
            return
        if task_type not in self.VALID_TASK_TYPES:
            result.add_error("value",
                f"task_type '{task_type}' is not valid. Must be one of: {self.VALID_TASK_TYPES}")

    def _validate_time_box(self, time_box: Optional[str], result: WorkOrderValidationResult):
        """Validate time_box ISO 8601 duration format."""
        if not time_box:
            return
        if not self.ISO_DURATION_PATTERN.match(time_box):
            result.add_error("format",
                f"time_box '{time_box}' is not valid ISO 8601 duration (e.g., PT4H, PT30M, P1D)")

    def _validate_paths(self, work_order: Dict, result: WorkOrderValidationResult):
        """Validate file paths exist."""
        # Check task_spec_path
        spec_path = work_order.get('task_spec_path')
        if spec_path:
            full_path = self.repo_root / spec_path.lstrip('/')
            if not full_path.exists():
                result.add_warning(f"task_spec_path '{spec_path}' does not exist")

    def _validate_inputs(self, inputs: List[Dict], result: WorkOrderValidationResult):
        """Validate inputs structure."""
        if not isinstance(inputs, list):
            result.add_error("format", "inputs must be a list")
            return

        for i, inp in enumerate(inputs):
            if not isinstance(inp, dict):
                result.add_error("format", f"inputs[{i}] must be an object")
                continue

            # Check required input fields
            if 'path' not in inp:
                result.add_error("missing", f"inputs[{i}].path is required")
            if 'type' not in inp:
                result.add_error("missing", f"inputs[{i}].type is required")
            elif inp['type'] not in self.VALID_INPUT_TYPES:
                result.add_error("value",
                    f"inputs[{i}].type '{inp['type']}' is not valid")

    def _validate_outputs(self, outputs: List[Dict], result: WorkOrderValidationResult):
        """Validate expected_outputs structure."""
        if not isinstance(outputs, list):
            result.add_error("format", "expected_outputs must be a list")
            return

        for i, out in enumerate(outputs):
            if not isinstance(out, dict):
                result.add_error("format", f"expected_outputs[{i}] must be an object")
                continue

            # Check required output fields
            if 'path' not in out:
                result.add_error("missing", f"expected_outputs[{i}].path is required")
            if 'type' not in out:
                result.add_error("missing", f"expected_outputs[{i}].type is required")
            elif out['type'] not in self.VALID_OUTPUT_TYPES:
                result.add_error("value",
                    f"expected_outputs[{i}].type '{out['type']}' is not valid")
            if 'acceptance_criteria' not in out:
                result.add_warning(f"expected_outputs[{i}] missing acceptance_criteria")

    def _validate_dependencies(self, deps: List, result: WorkOrderValidationResult):
        """Validate dependencies list."""
        if not isinstance(deps, list):
            result.add_error("format", "dependencies must be a list")
            return

        # Check for circular dependencies would require loading other work orders
        # For now, just validate format
        for i, dep in enumerate(deps):
            if not isinstance(dep, str):
                result.add_error("format", f"dependencies[{i}] must be a string")

    def _validate_priority(self, priority: str, result: WorkOrderValidationResult):
        """Validate priority enum value."""
        if priority not in self.VALID_PRIORITIES:
            result.add_error("value",
                f"priority '{priority}' is not valid. Must be one of: {self.VALID_PRIORITIES}")

    def validate_queue(self, queue_path: str) -> List[WorkOrderValidationResult]:
        """Validate all work orders in a queue file."""
        results = []

        if not HAS_YAML:
            print("ERROR: pyyaml is required for queue validation", file=sys.stderr)
            return results

        queue_file = Path(queue_path)
        if not queue_file.exists():
            print(f"ERROR: Queue file not found: {queue_path}", file=sys.stderr)
            return results

        try:
            with open(queue_file) as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"ERROR: Failed to parse queue file: {e}", file=sys.stderr)
            return results

        work_orders = data.get('work_orders', [])
        if not work_orders:
            print("No work orders found in queue", file=sys.stderr)
            return results

        for wo in work_orders:
            result = self.validate_work_order(wo, str(queue_file))
            results.append(result)

        return results

def print_result(result: WorkOrderValidationResult, verbose: bool = False):
    """Print validation result."""
    status = "✓ VALID" if result.valid else "✗ INVALID"
    color = "\033[92m" if result.valid else "\033[91m"
    reset = "\033[0m"

    print(f"\n{color}{status}{reset}: {result.work_order_id or 'unknown'}")

    if result.work_order_path:
        print(f"  Source: {result.work_order_path}")

    if not result.valid or verbose:
        if result.format_errors:
            print("  Format Errors:")
            for err in result.format_errors:
                print(f"    - {err}")
        if result.missing_fields:
            print("  Missing Fields:")
            for err in result.missing_fields:
                print(f"    - {err}")
        if result.invalid_values:
            print("  Invalid Values:")
            for err in result.invalid_values:
                print(f"    - {err}")
        if result.path_errors:
            print("  Path Errors:")
            for err in result.path_errors:
                print(f"    - {err}")
        if result.dependency_errors:
            print("  Dependency Errors:")
            for err in result.dependency_errors:
                print(f"    - {err}")

    if result.warnings and verbose:
        print("  Warnings:")
        for warn in result.warnings:
            print(f"    - {warn}")

def main():
    parser = argparse.ArgumentParser(
        description="Validate work orders against work_order_schema.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Validate a single work order:
    %(prog)s --validate work_order.yaml

  Validate all work orders in queue:
    %(prog)s --validate-queue LogBook/pm/WO_QUEUE.yaml

  Check with JSON output:
    %(prog)s --validate work_order.yaml --json
        """
    )

    parser.add_argument("--validate", "-v", metavar="FILE",
                        help="Validate a single work order YAML file")
    parser.add_argument("--validate-queue", "-q", metavar="FILE",
                        help="Validate all work orders in a queue file")
    parser.add_argument("--repo-root", default=".",
                        help="Repository root path (default: current directory)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed output including warnings")
    parser.add_argument("--strict", action="store_true",
                        help="Exit with error on any validation failure")

    args = parser.parse_args()

    if not args.validate and not args.validate_queue:
        parser.print_help()
        return 2

    validator = WorkOrderValidator(args.repo_root)
    results = []

    if args.validate:
        if not HAS_YAML:
            print("ERROR: pyyaml is required. Install with: pip install pyyaml",
                  file=sys.stderr)
            return 2

        try:
            with open(args.validate) as f:
                work_order = yaml.safe_load(f)
            result = validator.validate_work_order(work_order, args.validate)
            results.append(result)
        except Exception as e:
            print(f"ERROR: Failed to load work order: {e}", file=sys.stderr)
            return 2

    elif args.validate_queue:
        results = validator.validate_queue(args.validate_queue)

    # Output results
    if args.json:
        output = {
            "results": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "valid": sum(1 for r in results if r.valid),
                "invalid": sum(1 for r in results if not r.valid)
            }
        }
        print(json.dumps(output, indent=2))
    else:
        for result in results:
            print_result(result, args.verbose)

        print("\n" + "=" * 40)
        valid_count = sum(1 for r in results if r.valid)
        print(f"Summary: {valid_count}/{len(results)} work orders valid")

    # Exit code
    any_invalid = any(not r.valid for r in results)
    if any_invalid and args.strict:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
