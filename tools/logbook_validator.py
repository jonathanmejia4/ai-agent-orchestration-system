#!/usr/bin/env python3
"""Validate LogBook entries against schema.

This tool validates LogBook YAML entries against the LogBook JSON Schema
to ensure data integrity and prevent corrupted audit trails.

Usage:
    python3 tools/logbook_validator.py                    # Validate all entries
    python3 tools/logbook_validator.py LogBook/pm/*.yaml  # Validate specific entries
    python3 tools/logbook_validator.py --entry path.yaml  # Validate single entry

Exit codes:
    0: All entries valid
    1: Validation failures found
    2: Schema not found or invalid
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple
import argparse

try:
    import yaml
    from jsonschema import validate, ValidationError, SchemaError
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install with: pip install pyyaml jsonschema")
    sys.exit(2)

def load_schema(schema_path: Path) -> dict:
    """Load and validate LogBook schema."""
    if not schema_path.exists():
        print(f"❌ Schema not found: {schema_path}")
        print("   Expected: manifests/logbook.schema.json")
        sys.exit(2)

    try:
        schema = json.loads(schema_path.read_text())
        return schema
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in schema: {e}")
        sys.exit(2)

def validate_logbook_entry(entry_path: Path, schema: dict) -> Tuple[bool, str]:
    """Validate single LogBook entry.

    Returns:
        (is_valid, error_message)
    """
    try:
        # Load entry (YAML)
        entry = yaml.safe_load(entry_path.read_text())

        # Validate against schema
        validate(instance=entry, schema=schema)

        return True, ""

    except yaml.YAMLError as e:
        return False, f"Invalid YAML: {e}"
    except ValidationError as e:
        # Extract user-friendly error message
        error_path = " -> ".join(str(p) for p in e.path) if e.path else "root"
        return False, f"Schema validation failed at '{error_path}': {e.message}"
    except FileNotFoundError:
        return False, "File not found"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def find_logbook_entries(base_dir: Path) -> List[Path]:
    """Find all LogBook YAML entries."""
    if not base_dir.exists():
        return []

    return sorted(base_dir.rglob("*.yaml"))

def main():
    parser = argparse.ArgumentParser(
        description="Validate LogBook entries against schema"
    )
    parser.add_argument(
        "entries",
        nargs="*",
        help="Specific entries to validate (default: all in LogBook/)"
    )
    parser.add_argument(
        "--schema",
        default="manifests/logbook.schema.json",
        help="Path to LogBook schema (default: manifests/logbook.schema.json)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show details for valid entries too"
    )

    args = parser.parse_args()

    # Load schema
    schema_path = Path(args.schema)
    schema = load_schema(schema_path)

    # Find entries to validate
    if args.entries:
        # Validate specific entries
        entries = [Path(e) for e in args.entries]
    else:
        # Validate all entries in LogBook/
        logbook_dir = Path("LogBook")
        entries = find_logbook_entries(logbook_dir)

        if not entries:
            print(f"⚠️  No LogBook entries found in {logbook_dir}/")
            print("   (This might be expected if LogBook is empty)")
            sys.exit(0)

    print(f"=== Validating {len(entries)} LogBook entries ===\n")

    # Validate each entry
    valid_count = 0
    invalid_count = 0
    errors = []

    for entry_path in entries:
        is_valid, error_msg = validate_logbook_entry(entry_path, schema)

        if is_valid:
            valid_count += 1
            if args.verbose:
                print(f"✅ Valid: {entry_path.name}")
        else:
            invalid_count += 1
            print(f"❌ Invalid: {entry_path.name}")
            print(f"   Error: {error_msg}")
            errors.append((entry_path, error_msg))

    # Summary
    print(f"\n=== Summary ===")
    print(f"Valid: {valid_count}/{len(entries)}")

    if invalid_count > 0:
        print(f"Invalid: {invalid_count}/{len(entries)}")
        print("\n❌ Validation failed")
        print("\nCommon issues:")
        print("  - Missing required fields (timestamp, agent, action, context)")
        print("  - Invalid timestamp format (use ISO-8601: 2025-12-26T10:30:00Z)")
        print("  - Invalid agent (must be: PM, Planner, Builder, or Critic)")
        print("  - Invalid stage pattern (use: Stage0, Stage1, ..., Stage4-Golden)")
        print("  - Invalid template_id format (use: Family:name:1.0.0)")
        print("\nSee manifests/logbook.schema.json for full specification")
        sys.exit(1)
    else:
        print("✅ All LogBook entries valid")
        sys.exit(0)

if __name__ == "__main__":
    main()
