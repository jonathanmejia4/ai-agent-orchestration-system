#!/usr/bin/env python3
"""
Integration Test Schema Validator

Validates integration test definition files against the integration_test_schema.yaml.

Usage:
    python3 tools/validate_integration_test.py --test-file path/to/test_def.yaml
    python3 tools/validate_integration_test.py path/to/test1.yaml path/to/test2.yaml

Exit Codes:
    0 - All test definitions are valid
    1 - Validation errors found
    2 - Schema not found or other errors

Author: System
Created: 2025-12-31
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Optional YAML/jsonschema support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import jsonschema
    from jsonschema import validate, ValidationError, Draft7Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

SCHEMA_PATH = Path(__file__).parent.parent / "PLANNING" / "schemas" / "integration_test_schema.yaml"

def load_schema() -> Optional[Dict[str, Any]]:
    """Load the integration test schema."""
    if not HAS_YAML:
        print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
        return None

    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema not found: {SCHEMA_PATH}", file=sys.stderr)
        return None

    with open(SCHEMA_PATH) as f:
        return yaml.safe_load(f)

def validate_test_definition(test_def: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate a test definition against the schema. Returns list of errors."""
    if not HAS_JSONSCHEMA:
        return ["jsonschema library not installed"]

    errors = []
    validator = Draft7Validator(schema)
    for error in validator.iter_errors(test_def):
        path = ".".join(str(p) for p in error.path) if error.path else "(root)"
        errors.append(f"{path}: {error.message}")

    return errors

def validate_file(filepath: Path, schema: Dict[str, Any]) -> tuple:
    """Validate a YAML file. Returns (is_valid, errors)."""
    if not filepath.exists():
        return False, [f"File not found: {filepath}"]

    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return False, [f"YAML parse error: {e}"]

    if data is None:
        return False, ["Empty file"]

    errors = validate_test_definition(data, schema)
    return len(errors) == 0, errors

def main():
    parser = argparse.ArgumentParser(
        description="Validate integration test definitions against schema"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Test definition files to validate"
    )
    parser.add_argument(
        "--test-file", "-f",
        help="Single test definition file to validate"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output errors"
    )

    args = parser.parse_args()

    # Gather files to validate
    files = []
    if args.test_file:
        files.append(Path(args.test_file))
    files.extend(Path(f) for f in args.files)

    if not files:
        print("No files specified. Use --test-file or positional arguments.")
        return 2

    # Load schema
    schema = load_schema()
    if schema is None:
        return 2

    # Validate files
    all_valid = True
    for filepath in files:
        is_valid, errors = validate_file(filepath, schema)

        if is_valid:
            if not args.quiet:
                print(f"PASS: {filepath}")
        else:
            all_valid = False
            print(f"FAIL: {filepath}")
            for error in errors:
                print(f"  - {error}")

    return 0 if all_valid else 1

if __name__ == "__main__":
    sys.exit(main())
