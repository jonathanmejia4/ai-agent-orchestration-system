#!/usr/bin/env python3
"""
Task Spec Validator - Schema Validation for Task Specifications

Validates task specification files against the task_spec_schema.yaml schema.
Ensures requirement definitions meet quality standards before Builder consumption.

Usage:
    python3 tools/validate_task_spec.py PLANNING/specs/tasks/<file>.yaml
    python3 tools/validate_task_spec.py --all
    python3 tools/validate_task_spec.py --strict <file>.yaml

Exit Codes:
    0 - Valid spec
    1 - Validation errors
    2 - Error (file not found, parse error, etc.)

Referenced in:
    - PLANNING/specs/tasks/README.md:60 (validation step)

Author: System
Created: 2026-01-09
"""

import argparse
import sys
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

@dataclass
class ValidationError:
    """Validation error details"""
    field: str
    message: str
    severity: str = "error"  # error, warning, info
    line: Optional[int] = None

    def __str__(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"[{self.severity.upper()}] {self.field}{loc}: {self.message}"

@dataclass
class ValidationResult:
    """Complete validation result"""
    valid: bool
    spec_path: str
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    info: List[ValidationError] = field(default_factory=list)

    def add_error(self, field: str, message: str, line: Optional[int] = None):
        self.errors.append(ValidationError(field, message, "error", line))
        self.valid = False

    def add_warning(self, field: str, message: str, line: Optional[int] = None):
        self.warnings.append(ValidationError(field, message, "warning", line))

    def add_info(self, field: str, message: str, line: Optional[int] = None):
        self.info.append(ValidationError(field, message, "info", line))

class TaskSpecValidator:
    """Validator for task specification (requirements) files"""

    # Required fields (from task_spec_schema.yaml:25-29)
    REQUIRED_FIELDS = ['spec_id', 'task_id', 'title', 'requirements']

    # Recommended fields
    RECOMMENDED_FIELDS = ['version', 'status', 'author']

    # Valid statuses (from task_spec_schema.yaml:55-61)
    VALID_STATUSES = ['draft', 'review', 'approved', 'implemented', 'deprecated']

    # Spec ID pattern (SPEC-YYYY-NNN)
    SPEC_ID_PATTERN = r'^SPEC-\d{4}-\d{3}$'

    # Task ID pattern (e.g., 1.1, 2.3, 3.1.2)
    TASK_ID_PATTERN = r'^\d+\.\d+(\.\d+)?$'

    # Version pattern (X.Y)
    VERSION_PATTERN = r'^\d+\.\d+$'

    # Requirement ID pattern (REQ-NNN)
    REQ_ID_PATTERN = r'^REQ-\d{3}$'

    # Valid requirement priorities (from task_spec_schema.yaml:90)
    VALID_PRIORITIES = ['must', 'should', 'could', 'wont']

    # Valid constraint types (from task_spec_schema.yaml:117)
    VALID_CONSTRAINT_TYPES = ['performance', 'security', 'compatibility', 'resource']

    def __init__(self, spec_path: Path, strict: bool = False):
        self.spec_path = spec_path
        self.strict = strict
        self.spec_data = None
        self.result = ValidationResult(valid=True, spec_path=str(spec_path))

    def load_spec(self) -> bool:
        """Load and parse specification file"""
        if not self.spec_path.exists():
            self.result.add_error("file", f"Spec file not found: {self.spec_path}")
            return False

        try:
            with open(self.spec_path, 'r') as f:
                self.spec_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.result.add_error("yaml", f"YAML parse error: {e}")
            return False

        if not self.spec_data:
            self.result.add_error("content", "Spec is empty")
            return False

        if not isinstance(self.spec_data, dict):
            self.result.add_error("structure", "Spec must be a YAML mapping")
            return False

        return True

    def validate_required_fields(self):
        """Check all required fields are present"""
        for field in self.REQUIRED_FIELDS:
            if field not in self.spec_data:
                self.result.add_error(field, f"Required field '{field}' is missing")
            elif self.spec_data[field] is None:
                self.result.add_error(field, f"Required field '{field}' cannot be null")
            elif isinstance(self.spec_data[field], str) and not self.spec_data[field].strip():
                self.result.add_error(field, f"Required field '{field}' cannot be empty")

    def validate_recommended_fields(self):
        """Check recommended fields"""
        for field in self.RECOMMENDED_FIELDS:
            if field not in self.spec_data:
                self.result.add_warning(field, f"Recommended field '{field}' is missing")

    def validate_spec_id(self):
        """Validate spec_id format"""
        spec_id = self.spec_data.get('spec_id')
        if not spec_id:
            return

        if not isinstance(spec_id, str):
            self.result.add_error("spec_id", "Spec ID must be a string")
            return

        if not re.match(self.SPEC_ID_PATTERN, spec_id):
            self.result.add_error("spec_id",
                f"Invalid spec ID format: '{spec_id}'. Must be SPEC-YYYY-NNN (e.g., SPEC-2025-001)")

    def validate_task_id(self):
        """Validate task_id format"""
        task_id = self.spec_data.get('task_id')
        if not task_id:
            return

        if not isinstance(task_id, str):
            self.result.add_error("task_id", "Task ID must be a string")
            return

        if not re.match(self.TASK_ID_PATTERN, task_id):
            self.result.add_error("task_id",
                f"Invalid task ID format: '{task_id}'. Must be numeric (e.g., 1.1, 2.3.1)")

    def validate_title(self):
        """Validate title"""
        title = self.spec_data.get('title')
        if not title:
            return

        if not isinstance(title, str):
            self.result.add_error("title", "Title must be a string")
            return

        if len(title) > 200:
            self.result.add_warning("title", "Title exceeds 200 characters")

        if len(title) < 10:
            self.result.add_warning("title", "Title should be at least 10 characters")

    def validate_version(self):
        """Validate version format"""
        version = self.spec_data.get('version')
        if not version:
            return

        if not isinstance(version, str):
            self.result.add_error("version", "Version must be a string")
            return

        if not re.match(self.VERSION_PATTERN, version):
            self.result.add_warning("version",
                f"Version '{version}' doesn't follow X.Y format")

    def validate_status(self):
        """Validate status"""
        status = self.spec_data.get('status')
        if not status:
            return

        if not isinstance(status, str):
            self.result.add_error("status", "Status must be a string")
            return

        if status.lower() not in self.VALID_STATUSES:
            self.result.add_warning("status",
                f"Unknown status: '{status}'. Expected one of: {', '.join(self.VALID_STATUSES)}")

    def validate_requirements(self):
        """Validate requirements array"""
        requirements = self.spec_data.get('requirements')
        if not requirements:
            self.result.add_error("requirements", "Requirements array is required")
            return

        if not isinstance(requirements, list):
            self.result.add_error("requirements", "Requirements must be an array")
            return

        if len(requirements) == 0:
            self.result.add_error("requirements", "Requirements array cannot be empty")
            return

        # Validate each requirement
        req_ids = set()
        for i, req in enumerate(requirements):
            if not isinstance(req, dict):
                self.result.add_error(f"requirements[{i}]",
                    "Each requirement must be a mapping")
                continue

            # Required fields
            if 'id' not in req:
                self.result.add_error(f"requirements[{i}]",
                    "Requirement must have 'id' field")
            else:
                req_id = req['id']
                if not re.match(self.REQ_ID_PATTERN, req_id):
                    self.result.add_error(f"requirements[{i}].id",
                        f"Invalid requirement ID: '{req_id}'. Must be REQ-NNN")

                # Check for duplicate IDs
                if req_id in req_ids:
                    self.result.add_error(f"requirements[{i}].id",
                        f"Duplicate requirement ID: {req_id}")
                req_ids.add(req_id)

            if 'description' not in req:
                self.result.add_error(f"requirements[{i}]",
                    "Requirement must have 'description' field")
            elif not req['description']:
                self.result.add_error(f"requirements[{i}].description",
                    "Requirement description cannot be empty")

            if 'priority' not in req:
                self.result.add_error(f"requirements[{i}]",
                    "Requirement must have 'priority' field")
            elif req['priority'].lower() not in self.VALID_PRIORITIES:
                self.result.add_error(f"requirements[{i}].priority",
                    f"Invalid priority: '{req['priority']}'. "
                    f"Must be one of: {', '.join(self.VALID_PRIORITIES)}")

            # Validate acceptance criteria if present
            if 'acceptance_criteria' in req:
                criteria = req['acceptance_criteria']
                if not isinstance(criteria, list):
                    self.result.add_error(f"requirements[{i}].acceptance_criteria",
                        "Acceptance criteria must be an array")
                else:
                    for j, criterion in enumerate(criteria):
                        if not isinstance(criterion, dict):
                            self.result.add_error(
                                f"requirements[{i}].acceptance_criteria[{j}]",
                                "Each criterion must be a mapping")
                            continue

                        if 'criterion' not in criterion:
                            self.result.add_error(
                                f"requirements[{i}].acceptance_criteria[{j}]",
                                "Criterion must have 'criterion' field")

                        if 'testable' not in criterion:
                            self.result.add_error(
                                f"requirements[{i}].acceptance_criteria[{j}]",
                                "Criterion must have 'testable' field")
                        elif not isinstance(criterion['testable'], bool):
                            self.result.add_error(
                                f"requirements[{i}].acceptance_criteria[{j}].testable",
                                "Testable field must be boolean")

    def validate_constraints(self):
        """Validate constraints array"""
        constraints = self.spec_data.get('constraints')
        if constraints is None:
            return

        if not isinstance(constraints, list):
            self.result.add_error("constraints", "Constraints must be an array")
            return

        for i, constraint in enumerate(constraints):
            if not isinstance(constraint, dict):
                self.result.add_error(f"constraints[{i}]",
                    "Each constraint must be a mapping")
                continue

            constraint_type = constraint.get('type')
            if constraint_type and constraint_type not in self.VALID_CONSTRAINT_TYPES:
                self.result.add_warning(f"constraints[{i}].type",
                    f"Unknown constraint type: '{constraint_type}'. "
                    f"Expected one of: {', '.join(self.VALID_CONSTRAINT_TYPES)}")

            if 'description' not in constraint:
                self.result.add_warning(f"constraints[{i}]",
                    "Constraint should have description")

    def validate_interfaces(self):
        """Validate interfaces section"""
        interfaces = self.spec_data.get('interfaces')
        if interfaces is None:
            return

        if not isinstance(interfaces, dict):
            self.result.add_error("interfaces", "Interfaces must be a mapping")
            return

        for key in ['inputs', 'outputs', 'events']:
            if key in interfaces and not isinstance(interfaces[key], list):
                self.result.add_error(f"interfaces.{key}",
                    f"{key.capitalize()} must be an array")

    def validate_testing(self):
        """Validate testing section"""
        testing = self.spec_data.get('testing')
        if testing is None:
            return

        if not isinstance(testing, dict):
            self.result.add_error("testing", "Testing must be a mapping")
            return

        if 'coverage_threshold' in testing:
            threshold = testing['coverage_threshold']
            if not isinstance(threshold, int) or threshold < 0 or threshold > 100:
                self.result.add_error("testing.coverage_threshold",
                    "Coverage threshold must be integer between 0 and 100")

    def validate_against_schema(self, schema_path: Path):
        """Validate against schema file if provided"""
        if not schema_path.exists():
            self.result.add_warning("schema", f"Schema file not found: {schema_path}")
            return

        try:
            with open(schema_path, 'r') as f:
                schema = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.result.add_warning("schema", f"Failed to load schema: {e}")
            return

        if not schema:
            return

        # Basic schema validation (simplified)
        if 'required' in schema:
            for field in schema['required']:
                if field not in self.spec_data:
                    self.result.add_error(field,
                        f"Required by schema: field '{field}' is missing")

    def validate(self, schema_path: Optional[Path] = None) -> ValidationResult:
        """Run full validation"""
        if not self.load_spec():
            return self.result

        # Core validations
        self.validate_required_fields()
        self.validate_recommended_fields()
        self.validate_spec_id()
        self.validate_task_id()
        self.validate_title()
        self.validate_version()
        self.validate_status()
        self.validate_requirements()
        self.validate_constraints()
        self.validate_interfaces()
        self.validate_testing()

        # Schema validation if provided
        if schema_path:
            self.validate_against_schema(schema_path)

        # In strict mode, warnings become errors
        if self.strict and self.result.warnings:
            for warning in self.result.warnings:
                warning.severity = "error"
            self.result.errors.extend(self.result.warnings)
            self.result.warnings = []
            self.result.valid = len(self.result.errors) == 0

        return self.result

def find_all_specs(base_dir: Path) -> List[Path]:
    """Find all task spec files"""
    specs = []

    # Look in PLANNING/specs/tasks/
    specs_dir = base_dir / 'PLANNING' / 'specs' / 'tasks'
    if specs_dir.exists():
        for spec_file in specs_dir.glob('*.yaml'):
            if spec_file.name != 'README.md':
                specs.append(spec_file)
        for spec_file in specs_dir.glob('*.yml'):
            specs.append(spec_file)

    return specs

def main():
    parser = argparse.ArgumentParser(
        description='Validate task specification files against schema',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s PLANNING/specs/tasks/spec-001.yaml
    %(prog)s --all
    %(prog)s --strict PLANNING/specs/tasks/spec-001.yaml
    %(prog)s --schema PLANNING/schemas/task_spec_schema.yaml spec-001.yaml

Exit Codes:
    0 - Valid (no errors)
    1 - Validation errors found
    2 - File or parsing error
        """
    )

    parser.add_argument('spec', type=Path, nargs='?',
                        help='Path to task spec file')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Validate all specs in PLANNING/specs/tasks/')
    parser.add_argument('--schema', '-s', type=Path,
                        default=Path('PLANNING/schemas/task_spec_schema.yaml'),
                        help='Schema file for validation')
    parser.add_argument('--strict', action='store_true',
                        help='Treat warnings as errors')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Only output errors')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Determine specs to validate
    if args.all:
        base_dir = Path.cwd()
        specs = find_all_specs(base_dir)
        if not specs:
            print("No task specs found in PLANNING/specs/tasks/")
            sys.exit(0)
    elif args.spec:
        specs = [args.spec]
    else:
        parser.print_help()
        sys.exit(2)

    # Validate each spec
    all_valid = True
    results = []

    for spec_path in specs:
        validator = TaskSpecValidator(spec_path, strict=args.strict)
        result = validator.validate(schema_path=args.schema if args.schema.exists() else None)
        results.append(result)

        if not result.valid:
            all_valid = False

    # Output results
    if args.json:
        import json
        output = []
        for result in results:
            output.append({
                'spec': result.spec_path,
                'valid': result.valid,
                'errors': [str(e) for e in result.errors],
                'warnings': [str(w) for w in result.warnings],
                'info': [str(i) for i in result.info],
            })
        print(json.dumps(output, indent=2))
    else:
        for result in results:
            print(f"\n{'='*60}")
            print(f"Spec: {result.spec_path}")
            print(f"{'='*60}")

            if result.valid:
                print("\033[92m✅ VALID\033[0m")
            else:
                print("\033[91m❌ INVALID\033[0m")

            if result.errors:
                print(f"\nErrors ({len(result.errors)}):")
                for error in result.errors:
                    print(f"  \033[91m{error}\033[0m")

            if not args.quiet and result.warnings:
                print(f"\nWarnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    print(f"  \033[93m{warning}\033[0m")

            if args.verbose and result.info:
                print(f"\nInfo ({len(result.info)}):")
                for info in result.info:
                    print(f"  \033[94m{info}\033[0m")

        # Summary
        print(f"\n{'='*60}")
        print(f"Summary: {len([r for r in results if r.valid])}/{len(results)} valid")

    sys.exit(0 if all_valid else 1)

if __name__ == '__main__':
    main()
