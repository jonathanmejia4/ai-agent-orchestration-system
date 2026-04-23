#!/usr/bin/env python3
"""
Escape Hatch Validator
Version: 1.0.0
Last Updated: 2025-12-31
Owner: PM
Classification: MEDIUM - Audit Compliance

Enforces GENERATION_ESCAPE_HATCH_POLICY.md - Escape hatches must be
logged to LogBook/exceptions/generation/.

Validates that:
1. All manual/patched tasks have escape hatch entries
2. Escape hatch entries have required fields
3. Escape hatches are properly documented

Usage:
    python tools/escape_hatch_validator.py
    python tools/escape_hatch_validator.py --check-entries
    python tools/escape_hatch_validator.py --strict

Exit Codes:
    0: All escape hatches properly logged
    1: Missing or invalid escape hatch entries
    2: Configuration/runtime error
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml

@dataclass
class EscapeHatchEntry:
    """Represents an escape hatch log entry."""
    task_id: str
    reason: str
    approved_by: Optional[str]
    timestamp: Optional[str]
    justification: Optional[str]
    file_path: str
    valid: bool
    issues: List[str] = field(default_factory=list)

@dataclass
class ValidationResult:
    """Overall validation result."""
    entries: List[EscapeHatchEntry]
    missing_logs: List[str]  # Tasks with manual flag but no log
    valid_entries: int
    invalid_entries: int

# Required fields in escape hatch entry
REQUIRED_FIELDS = [
    "task_id",
    "reason",
    "timestamp",
]

# Optional but recommended fields
RECOMMENDED_FIELDS = [
    "approved_by",
    "justification",
    "scope",
    "expiry",
]

# Valid escape hatch reasons per GENERATION_ESCAPE_HATCH_POLICY.md
VALID_REASONS = [
    "manual_edit",
    "template_override",
    "patch_applied",
    "custom_implementation",
    "legacy_compatibility",
    "performance_optimization",
    "security_fix",
]

def find_manual_tasks(tasks_dir: Path) -> Set[str]:
    """Find tasks marked as manual or patched."""
    manual_tasks = set()

    if not tasks_dir.exists():
        return manual_tasks

    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir():
            continue

        # Check manifest.yaml for manual flag
        manifest_path = task_dir / "manifest.yaml"
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest = yaml.safe_load(f)
                    if manifest and manifest.get("manual", False):
                        manual_tasks.add(task_dir.name)
                    if manifest and manifest.get("patched", False):
                        manual_tasks.add(task_dir.name)
            except Exception:
                pass

        # Check for .manual or .patched marker files
        if (task_dir / ".manual").exists():
            manual_tasks.add(task_dir.name)
        if (task_dir / ".patched").exists():
            manual_tasks.add(task_dir.name)

    return manual_tasks

def load_escape_hatch_entries(exceptions_dir: Path) -> List[EscapeHatchEntry]:
    """Load all escape hatch entries from LogBook."""
    entries = []

    if not exceptions_dir.exists():
        return entries

    # Check for YAML files in exceptions/generation/
    for yaml_file in exceptions_dir.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            # Handle single entry or list of entries
            if isinstance(data, list):
                for item in data:
                    entry = parse_entry(item, str(yaml_file))
                    if entry:
                        entries.append(entry)
            elif isinstance(data, dict):
                entry = parse_entry(data, str(yaml_file))
                if entry:
                    entries.append(entry)

        except Exception as e:
            print(f"Warning: Could not parse {yaml_file}: {e}", file=sys.stderr)

    # Also check for JSON files
    for json_file in exceptions_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    entry = parse_entry(item, str(json_file))
                    if entry:
                        entries.append(entry)
            elif isinstance(data, dict):
                entry = parse_entry(data, str(json_file))
                if entry:
                    entries.append(entry)

        except Exception as e:
            print(f"Warning: Could not parse {json_file}: {e}", file=sys.stderr)

    return entries

def parse_entry(data: Dict, file_path: str) -> Optional[EscapeHatchEntry]:
    """Parse a single escape hatch entry."""
    issues = []

    # Check required fields
    task_id = data.get("task_id", "")
    if not task_id:
        issues.append("Missing required field: task_id")

    reason = data.get("reason", "")
    if not reason:
        issues.append("Missing required field: reason")
    elif reason not in VALID_REASONS:
        issues.append(f"Invalid reason: '{reason}'. Valid: {VALID_REASONS}")

    timestamp = data.get("timestamp", "")
    if not timestamp:
        issues.append("Missing required field: timestamp")

    # Check recommended fields
    for field_name in RECOMMENDED_FIELDS:
        if field_name not in data:
            issues.append(f"Missing recommended field: {field_name}")

    return EscapeHatchEntry(
        task_id=task_id,
        reason=reason,
        approved_by=data.get("approved_by"),
        timestamp=timestamp,
        justification=data.get("justification"),
        file_path=file_path,
        valid=len([i for i in issues if "Missing required" in i]) == 0,
        issues=issues
    )

def validate_escape_hatches(
    tasks_dir: Path,
    exceptions_dir: Path,
    verbose: bool = False
) -> ValidationResult:
    """Validate all escape hatches are properly logged."""

    # Find tasks marked as manual
    manual_tasks = find_manual_tasks(tasks_dir)

    # Load escape hatch entries
    entries = load_escape_hatch_entries(exceptions_dir)

    # Create set of logged task IDs
    logged_tasks = {e.task_id for e in entries}

    # Find missing logs
    missing_logs = list(manual_tasks - logged_tasks)

    # Count valid/invalid
    valid_count = sum(1 for e in entries if e.valid)
    invalid_count = len(entries) - valid_count

    if verbose:
        print(f"\nManual/Patched tasks found: {len(manual_tasks)}")
        for task in sorted(manual_tasks):
            status = "LOGGED" if task in logged_tasks else "MISSING"
            print(f"  [{status}] {task}")

        print(f"\nEscape hatch entries: {len(entries)}")
        for entry in entries:
            status = "VALID" if entry.valid else "INVALID"
            print(f"  [{status}] {entry.task_id}: {entry.reason}")
            for issue in entry.issues:
                print(f"    - {issue}")

    return ValidationResult(
        entries=entries,
        missing_logs=missing_logs,
        valid_entries=valid_count,
        invalid_entries=invalid_count
    )

def main():
    parser = argparse.ArgumentParser(
        description="Validate escape hatch logging"
    )
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=Path("tasks"),
        help="Tasks directory (default: tasks/)"
    )
    parser.add_argument(
        "--exceptions-dir",
        type=Path,
        default=Path("LogBook/exceptions/generation"),
        help="Exceptions log directory (default: LogBook/exceptions/generation/)"
    )
    parser.add_argument(
        "--check-entries",
        action="store_true",
        help="Also validate entry contents"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if any issues found"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Run validation
    result = validate_escape_hatches(
        args.tasks_dir,
        args.exceptions_dir,
        args.verbose
    )

    has_issues = len(result.missing_logs) > 0 or result.invalid_entries > 0

    if args.json:
        output = {
            "summary": {
                "total_entries": len(result.entries),
                "valid_entries": result.valid_entries,
                "invalid_entries": result.invalid_entries,
                "missing_logs": len(result.missing_logs),
                "passed": not has_issues
            },
            "missing_logs": result.missing_logs,
            "entries": [
                {
                    "task_id": e.task_id,
                    "reason": e.reason,
                    "approved_by": e.approved_by,
                    "timestamp": e.timestamp,
                    "file": e.file_path,
                    "valid": e.valid,
                    "issues": e.issues
                }
                for e in result.entries
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print("Escape Hatch Validation Summary")
        print(f"{'='*50}")
        print(f"Total entries:    {len(result.entries)}")
        print(f"Valid entries:    {result.valid_entries}")
        print(f"Invalid entries:  {result.invalid_entries}")
        print(f"Missing logs:     {len(result.missing_logs)}")

        if result.missing_logs:
            print(f"\n{'='*50}")
            print("Tasks Missing Escape Hatch Logs")
            print(f"{'='*50}")
            for task in result.missing_logs:
                print(f"  - {task}")
                print(f"    Create: LogBook/exceptions/generation/{task}.yaml")

        if result.invalid_entries > 0 and not args.verbose:
            print(f"\n{'='*50}")
            print("Invalid Entries")
            print(f"{'='*50}")
            for entry in result.entries:
                if not entry.valid:
                    print(f"  {entry.task_id} ({entry.file_path})")
                    for issue in entry.issues:
                        print(f"    - {issue}")

    # Determine exit code
    if args.strict and has_issues:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
