#!/usr/bin/env python3
"""
Work Order Validation Tool

Validates work orders against the schema defined in:
PLANNING/schemas/work_order_schema.yaml

Usage:
    python3 tools/validate_work_order.py <work_order_file.yaml>

Exit Codes:
    0 - Validation passed
    1 - Validation failed (schema violations found)
    2 - Error (file not found, invalid YAML, etc.)

References:
    - PLANNING/schemas/work_order_schema.yaml - Schema definition
    - PLANNING/WORK_ORDER_DELIVERY_PROTOCOL.md - Delivery protocol
    - PLANNING/BUILDER_WO_VALIDATION_PROTOCOL.md - Builder validation steps
    - ISSUE_CATALOG.md - Issue A36

Author: System
Created: 2025-12-23
"""

import sys
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

# Valid enum values from schema
VALID_TASK_TYPES = ['implement_task', 'review_task', 'audit_plan', 'update_logbook']
VALID_INPUT_TYPES = ['spec', 'config', 'dependency', 'reference', 'template']
VALID_OUTPUT_TYPES = ['code', 'test', 'doc', 'manifest', 'config']
VALID_PRIORITIES = ['critical', 'high', 'normal', 'low']

# Valid agent names (from .claude/agents/)
VALID_AGENTS = [
    'Builder',
    'Critic-ACL',
    'Critic-Dependencies',
    'Critic-Effort',
    'Critic-ExecutionReady',
    'Critic-FixVerifier',
    'Critic-Orchestrator',
    'Critic-PlanAuditor',
    'Critic-SecurityPolicy',
    'Critic-SpecFit',
    'Critic-Verification',
    'Planner',
    'Project-Manager-final',
    'fix-verifier'
]

class ValidationError:
    """Represents a validation error"""
    def __init__(self, field: str, message: str, severity: str = 'ERROR'):
        self.field = field
        self.message = message
        self.severity = severity

    def __str__(self):
        color = RED if self.severity == 'ERROR' else YELLOW
        return f"{color}{self.severity}{NC}: [{self.field}] {self.message}"

class WorkOrderValidator:
    """Validates work orders against schema"""

    def __init__(self, work_order_path: str):
        self.path = Path(work_order_path)
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.work_order: Dict[str, Any] = {}

    def validate(self) -> bool:
        """
        Run full validation suite

        Returns:
            True if validation passed, False otherwise
        """
        print(f"{BLUE}Validating work order: {self.path}{NC}\n")

        # Step 1: Load and parse YAML
        if not self._load_yaml():
            return False

        # Step 2: Check required fields
        self._validate_required_fields()

        # Step 3: Validate field formats
        self._validate_id_format()
        self._validate_issued_by()
        self._validate_issued_to()
        self._validate_task_id()
        self._validate_task_spec_path()
        self._validate_task_type()
        self._validate_objective()

        # Step 4: Validate inputs/outputs
        self._validate_inputs()
        self._validate_expected_outputs()

        # Step 5: Validate constraints
        self._validate_time_box()
        self._validate_dependencies()
        self._validate_priority()

        # Step 6: Print results
        return self._print_results()

    def _load_yaml(self) -> bool:
        """Load and parse YAML file"""
        if not self.path.exists():
            print(f"{RED}ERROR{NC}: File not found: {self.path}")
            return False

        try:
            with open(self.path, 'r') as f:
                self.work_order = yaml.safe_load(f)

            if not isinstance(self.work_order, dict):
                print(f"{RED}ERROR{NC}: Work order must be a YAML dictionary")
                return False

            return True

        except yaml.YAMLError as e:
            print(f"{RED}ERROR{NC}: Invalid YAML syntax: {e}")
            return False
        except Exception as e:
            print(f"{RED}ERROR{NC}: Failed to read file: {e}")
            return False

    def _validate_required_fields(self):
        """Check all required fields are present"""
        required_fields = [
            'id', 'issued_by', 'issued_to', 'task_id', 'task_spec_path',
            'task_type', 'objective', 'inputs', 'expected_outputs',
            'prohibited_actions', 'time_box', 'dependencies'
        ]

        for field in required_fields:
            if field not in self.work_order:
                self.errors.append(ValidationError(field, "Required field missing"))

    def _validate_id_format(self):
        """Validate work order ID format: WO-YYYYMMDD-NNN"""
        if 'id' not in self.work_order:
            return

        wo_id = self.work_order['id']
        pattern = r'^WO-\d{8}-\d{3}$'

        if not re.match(pattern, wo_id):
            self.errors.append(ValidationError(
                'id',
                f"Invalid format '{wo_id}'. Expected: WO-YYYYMMDD-NNN (e.g., WO-20251223-001)"
            ))
        else:
            # Validate date part
            try:
                date_part = wo_id.split('-')[1]
                datetime.strptime(date_part, '%Y%m%d')
            except ValueError:
                self.errors.append(ValidationError(
                    'id',
                    f"Invalid date in ID: {date_part}. Must be valid YYYYMMDD"
                ))

    def _validate_issued_by(self):
        """Validate issued_by field"""
        if 'issued_by' not in self.work_order:
            return

        # Accept both agent names per schema (line 17-19 says "Project-Manager")
        valid_issuers = ['Project-Manager', 'Project-Manager-final']
        if self.work_order['issued_by'] not in valid_issuers:
            self.errors.append(ValidationError(
                'issued_by',
                f"Must be one of {valid_issuers}, got '{self.work_order['issued_by']}'"
            ))

    def _validate_issued_to(self):
        """Validate issued_to is a valid agent"""
        if 'issued_to' not in self.work_order:
            return

        issued_to = self.work_order['issued_to']
        if issued_to not in VALID_AGENTS:
            self.errors.append(ValidationError(
                'issued_to',
                f"Invalid agent '{issued_to}'. Must be one of: {', '.join(VALID_AGENTS)}"
            ))

    def _validate_task_id(self):
        """Validate task_id is a valid task ID format (X.Y or X.Y.Z)"""
        if 'task_id' not in self.work_order:
            return

        task_id = self.work_order['task_id']
        # Schema requires format X.Y or X.Y.Z (e.g., "1.1", "2.3", "3.1.2")
        task_id_pattern = r'^\d+\.\d+(\.\d+)?$'

        if not re.match(task_id_pattern, str(task_id)):
            self.errors.append(ValidationError(
                'task_id',
                f"Invalid task_id format: '{task_id}'. Expected X.Y or X.Y.Z (e.g., '1.1', '2.3.1')"
            ))

    def _validate_task_spec_path(self):
        """Validate task_spec_path exists"""
        if 'task_spec_path' not in self.work_order:
            return

        spec_path = self.work_order['task_spec_path']

        # Remove leading slash for path resolution
        relative_path = spec_path.lstrip('/')
        full_path = Path.cwd() / relative_path

        if not full_path.exists():
            self.errors.append(ValidationError(
                'task_spec_path',
                f"File not found: {spec_path}"
            ))

    def _validate_task_type(self):
        """Validate task_type is valid enum value"""
        if 'task_type' not in self.work_order:
            return

        task_type = self.work_order['task_type']
        if task_type not in VALID_TASK_TYPES:
            self.errors.append(ValidationError(
                'task_type',
                f"Invalid value '{task_type}'. Must be one of: {', '.join(VALID_TASK_TYPES)}"
            ))

    def _validate_objective(self):
        """Validate objective is non-empty"""
        if 'objective' not in self.work_order:
            return

        objective = self.work_order['objective']
        if not objective or not objective.strip():
            self.errors.append(ValidationError(
                'objective',
                "Objective cannot be empty"
            ))

    def _validate_inputs(self):
        """Validate inputs array"""
        if 'inputs' not in self.work_order:
            return

        inputs = self.work_order['inputs']

        if not isinstance(inputs, list):
            self.errors.append(ValidationError('inputs', "Must be a list"))
            return

        if len(inputs) == 0:
            self.warnings.append(ValidationError(
                'inputs',
                "No inputs specified (unusual but allowed)",
                severity='WARNING'
            ))

        for i, inp in enumerate(inputs):
            if not isinstance(inp, dict):
                self.errors.append(ValidationError(f'inputs[{i}]', "Must be a dictionary"))
                continue

            # Check required fields
            if 'path' not in inp:
                self.errors.append(ValidationError(f'inputs[{i}]', "Missing 'path' field"))
            if 'type' not in inp:
                self.errors.append(ValidationError(f'inputs[{i}]', "Missing 'type' field"))
            if 'description' not in inp:
                self.errors.append(ValidationError(f'inputs[{i}]', "Missing 'description' field"))

            # Validate type enum
            if 'type' in inp and inp['type'] not in VALID_INPUT_TYPES:
                self.errors.append(ValidationError(
                    f'inputs[{i}].type',
                    f"Invalid type '{inp['type']}'. Must be one of: {', '.join(VALID_INPUT_TYPES)}"
                ))

    def _validate_expected_outputs(self):
        """Validate expected_outputs array"""
        if 'expected_outputs' not in self.work_order:
            return

        outputs = self.work_order['expected_outputs']

        if not isinstance(outputs, list):
            self.errors.append(ValidationError('expected_outputs', "Must be a list"))
            return

        if len(outputs) == 0:
            self.errors.append(ValidationError('expected_outputs', "At least one output required"))

        for i, out in enumerate(outputs):
            if not isinstance(out, dict):
                self.errors.append(ValidationError(f'expected_outputs[{i}]', "Must be a dictionary"))
                continue

            # Check required fields
            if 'path' not in out:
                self.errors.append(ValidationError(f'expected_outputs[{i}]', "Missing 'path' field"))
            if 'type' not in out:
                self.errors.append(ValidationError(f'expected_outputs[{i}]', "Missing 'type' field"))
            if 'acceptance_criteria' not in out:
                self.errors.append(ValidationError(f'expected_outputs[{i}]', "Missing 'acceptance_criteria' field"))

            # Validate type enum
            if 'type' in out and out['type'] not in VALID_OUTPUT_TYPES:
                self.errors.append(ValidationError(
                    f'expected_outputs[{i}].type',
                    f"Invalid type '{out['type']}'. Must be one of: {', '.join(VALID_OUTPUT_TYPES)}"
                ))

            # Validate acceptance_criteria is non-empty
            if 'acceptance_criteria' in out:
                if not out['acceptance_criteria'] or not out['acceptance_criteria'].strip():
                    self.errors.append(ValidationError(
                        f'expected_outputs[{i}].acceptance_criteria',
                        "Acceptance criteria cannot be empty"
                    ))

    def _validate_time_box(self):
        """Validate time_box is valid ISO 8601 duration"""
        if 'time_box' not in self.work_order:
            return

        time_box = self.work_order['time_box']
        pattern = r'^P(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?$'

        if not re.match(pattern, time_box):
            self.errors.append(ValidationError(
                'time_box',
                f"Invalid ISO 8601 duration '{time_box}'. Examples: PT4H, PT30M, P1D"
            ))

    def _validate_dependencies(self):
        """Validate dependencies are valid task IDs (X.Y or X.Y.Z format)"""
        if 'dependencies' not in self.work_order:
            return

        deps = self.work_order['dependencies']

        if not isinstance(deps, list):
            self.errors.append(ValidationError('dependencies', "Must be a list"))
            return

        # Schema requires format X.Y or X.Y.Z (e.g., "1.1", "2.3", "3.1.2")
        task_id_pattern = r'^\d+\.\d+(\.\d+)?$'

        for i, dep in enumerate(deps):
            if not isinstance(dep, str):
                self.errors.append(ValidationError(f'dependencies[{i}]', "Must be a string"))
                continue

            if not re.match(task_id_pattern, dep):
                self.errors.append(ValidationError(
                    f'dependencies[{i}]',
                    f"Invalid task_id format: '{dep}'. Expected X.Y or X.Y.Z (e.g., '1.1', '2.3.1')"
                ))

    def _validate_priority(self):
        """Validate priority (optional field)"""
        if 'priority' not in self.work_order:
            return  # Optional field

        priority = self.work_order['priority']
        if priority not in VALID_PRIORITIES:
            self.errors.append(ValidationError(
                'priority',
                f"Invalid value '{priority}'. Must be one of: {', '.join(VALID_PRIORITIES)}"
            ))

    def _print_results(self) -> bool:
        """Print validation results"""
        print("\n" + "=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80 + "\n")

        if self.warnings:
            print(f"{YELLOW}WARNINGS ({len(self.warnings)}){NC}:")
            for warning in self.warnings:
                print(f"  {warning}")
            print()

        if self.errors:
            print(f"{RED}ERRORS ({len(self.errors)}){NC}:")
            for error in self.errors:
                print(f"  {error}")
            print()
            print(f"{RED}✗ VALIDATION FAILED{NC}")
            print(f"{RED}Work order does not conform to schema{NC}")
            return False
        else:
            print(f"{GREEN}✓ VALIDATION PASSED{NC}")
            print(f"{GREEN}Work order conforms to schema{NC}")
            if self.warnings:
                print(f"\n{YELLOW}Note: {len(self.warnings)} warning(s) found (non-blocking){NC}")
            return True

def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <work_order_file.yaml>")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} LogBook/work-orders/WO-20251223-001.yaml")
        print(f"  {sys.argv[0]} /path/to/work-order.yaml")
        sys.exit(2)

    work_order_path = sys.argv[1]

    validator = WorkOrderValidator(work_order_path)

    if validator.validate():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
