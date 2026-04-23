#!/usr/bin/env python3
"""
validate_wo_queue.py - Work Order Queue Validation Tool

Validates work order queue YAML files for schema compliance, ordering,
and work order lifecycle integrity. Checks for proper queue structure,
duplicate work orders, and status transitions.

Exit codes:
  0 - All queues valid
  1 - Validation errors found
  2 - File/parse error

Usage:
  python tools/validate_wo_queue.py LogBook/work-orders/
  python tools/validate_wo_queue.py LogBook/builder/WO_QUEUE.yaml
  python tools/validate_wo_queue.py LogBook/ --strict
  python tools/validate_wo_queue.py LogBook/work-orders/ --format=json

Reference: integration-test.yml:367, FAILURE_MODES.md
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Set

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class ValidationError:
    """Represents a validation error."""
    file_path: str
    line_number: Optional[int]
    error_type: str
    message: str
    severity: str = "ERROR"  # ERROR, WARNING

@dataclass
class ValidationResult:
    """Result of validating work order queues."""
    path: str
    files_checked: int = 0
    work_orders_checked: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    valid: bool = True

class WOQueueValidator:
    """Validates Work Order Queue files for schema compliance and integrity."""

    # Valid work order statuses (matches work_order_queue_schema.yaml)
    VALID_STATUSES = [
        "queued", "assigned", "in_progress", "completed", "blocked", "cancelled"
    ]

    # Valid status transitions (based on work_order_queue_schema.yaml lifecycle)
    VALID_TRANSITIONS = {
        "queued": ["assigned", "in_progress", "cancelled"],
        "assigned": ["in_progress", "queued", "cancelled"],
        "in_progress": ["completed", "blocked", "cancelled"],
        "blocked": ["in_progress", "cancelled"],
        "completed": [],  # Terminal state
        "cancelled": [],  # Terminal state
    }

    # Required fields for work orders (aligned with work_order_queue_schema.yaml:53-56)
    REQUIRED_FIELDS = ["work_order_id", "priority", "status"]
    OPTIONAL_FIELDS = ["agent", "task_id", "created_at", "updated_at", "dependencies"]

    # Valid priority values (aligned with work_order_queue_schema.yaml:63-69)
    VALID_PRIORITIES = ["critical", "high", "normal", "low"]

    # Work order ID pattern (canonical: WO-YYYYMMDD-NNN)
    WO_ID_PATTERN = r"^WO-\d{8}-\d{3}$"

    def __init__(self, verbose: bool = False, strict: bool = False):
        self.verbose = verbose
        self.strict = strict
        self.result = ValidationResult(path="")
        self.seen_work_orders: Set[str] = set()

    def log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def validate_path(self, path: Path) -> ValidationResult:
        """Validate a file or directory."""
        self.result = ValidationResult(path=str(path))
        self.seen_work_orders = set()

        if not path.exists():
            self.result.errors.append(ValidationError(
                file_path=str(path),
                line_number=None,
                error_type="FILE_NOT_FOUND",
                message=f"Path not found: {path}"
            ))
            self.result.valid = False
            return self.result

        if path.is_file():
            self._validate_file(path)
        elif path.is_dir():
            self._validate_directory(path)

        # Apply strict mode
        if self.strict and self.result.warnings:
            self.result.errors.extend(self.result.warnings)
            self.result.warnings = []

        self.result.valid = len(self.result.errors) == 0
        return self.result

    def _validate_directory(self, dir_path: Path):
        """Recursively validate work order queue files."""
        # Look for WO_QUEUE.yaml files and work-orders directory
        queue_files = list(dir_path.rglob("*WO_QUEUE*.yaml"))
        queue_files.extend(list(dir_path.rglob("*work-order*.yaml")))
        queue_files.extend(list(dir_path.rglob("*work_order*.yaml")))

        # Also check standard work-orders directories
        wo_dirs = list(dir_path.rglob("work-orders"))
        for wo_dir in wo_dirs:
            if wo_dir.is_dir():
                queue_files.extend(list(wo_dir.glob("*.yaml")))

        # Deduplicate
        queue_files = list(set(queue_files))

        if not queue_files:
            self.log(f"No work order queue files found in {dir_path}")
            self.result.warnings.append(ValidationError(
                file_path=str(dir_path),
                line_number=None,
                error_type="NO_QUEUE_FILES",
                message="No work order queue files found",
                severity="WARNING"
            ))

        for queue_file in queue_files:
            self._validate_file(queue_file)

    def _validate_file(self, file_path: Path):
        """Validate a single work order queue file."""
        self.result.files_checked += 1
        self.log(f"Validating: {file_path}")

        if not HAS_YAML:
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="MISSING_YAML",
                message="PyYAML not installed (pip install pyyaml)"
            ))
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for empty file
            if not content.strip():
                self.result.warnings.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="EMPTY_FILE",
                    message="Queue file is empty",
                    severity="WARNING"
                ))
                return

            # Parse YAML
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                self.result.errors.append(ValidationError(
                    file_path=str(file_path),
                    line_number=getattr(e, 'problem_mark', None) and e.problem_mark.line,
                    error_type="YAML_PARSE_ERROR",
                    message=f"YAML parse error: {e}"
                ))
                return

            if data is None:
                self.result.warnings.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="EMPTY_CONTENT",
                    message="Queue file parses to null/empty",
                    severity="WARNING"
                ))
                return

            # Validate work orders
            self._validate_work_orders(file_path, data)

        except Exception as e:
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="FILE_ERROR",
                message=f"Error reading file: {e}"
            ))

    def _validate_work_orders(self, file_path: Path, data):
        """Validate work order entries."""
        work_orders = []

        if isinstance(data, list):
            work_orders = data
        elif isinstance(data, dict):
            # Could be a single WO or a queue structure
            if "work_order_id" in data:
                work_orders = [data]
            elif "queue" in data:
                work_orders = data.get("queue", [])
            elif "pending" in data or "active" in data or "completed" in data:
                # Queue with status categories
                for category in ["pending", "active", "in_progress", "completed", "failed", "blocked"]:
                    if category in data and isinstance(data[category], list):
                        work_orders.extend(data[category])
            else:
                # Treat as single work order
                work_orders = [data]

        for i, wo in enumerate(work_orders):
            if isinstance(wo, dict):
                self.result.work_orders_checked += 1
                self._validate_work_order(file_path, wo, index=i)

    def _validate_work_order(self, file_path: Path, wo: dict, index: int = None):
        """Validate a single work order."""
        index_str = f"[{index}]" if index is not None else ""

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in wo:
                self.result.errors.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="MISSING_FIELD",
                    message=f"Work order{index_str}: Missing required field '{field}'"
                ))

        # Validate work_order_id format
        wo_id = wo.get("work_order_id")
        if wo_id:
            if not re.match(self.WO_ID_PATTERN, str(wo_id)):
                self.result.warnings.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="INVALID_WO_ID",
                    message=f"Work order{index_str}: Invalid ID format '{wo_id}'",
                    severity="WARNING"
                ))

            # Check for duplicates
            if wo_id in self.seen_work_orders:
                self.result.errors.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="DUPLICATE_WO",
                    message=f"Work order{index_str}: Duplicate ID '{wo_id}'"
                ))
            self.seen_work_orders.add(wo_id)

        # Validate status (case-insensitive comparison with lowercase schema values)
        status = wo.get("status")
        if status and status.lower() not in self.VALID_STATUSES:
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_STATUS",
                message=f"Work order{index_str}: Invalid status '{status}'. Valid: {self.VALID_STATUSES}"
            ))

        # Validate priority (required field, must match schema enum)
        priority = wo.get("priority")
        if priority is not None:
            if str(priority).lower() not in self.VALID_PRIORITIES:
                self.result.errors.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="INVALID_PRIORITY",
                    message=f"Work order{index_str}: Invalid priority '{priority}'. Valid: {self.VALID_PRIORITIES}"
                ))

        # Validate dependencies
        deps = wo.get("dependencies")
        if deps and isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, str) and not re.match(self.WO_ID_PATTERN, dep):
                    self.result.warnings.append(ValidationError(
                        file_path=str(file_path),
                        line_number=None,
                        error_type="INVALID_DEPENDENCY",
                        message=f"Work order{index_str}: Invalid dependency ID '{dep}'",
                        severity="WARNING"
                    ))

    def get_summary(self) -> dict:
        """Get validation summary."""
        return {
            "path": self.result.path,
            "files_checked": self.result.files_checked,
            "work_orders_checked": self.result.work_orders_checked,
            "errors": len(self.result.errors),
            "warnings": len(self.result.warnings),
            "valid": self.result.valid,
            "strict_mode": self.strict
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("WORK ORDER QUEUE VALIDATION REPORT")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nPath: {summary['path']}")
        lines.append(f"Files checked: {summary['files_checked']}")
        lines.append(f"Work orders checked: {summary['work_orders_checked']}")
        lines.append(f"Mode: {'Strict' if summary['strict_mode'] else 'Normal'}")
        lines.append("")

        # Errors
        if self.result.errors:
            lines.append("-" * 40)
            lines.append(f"ERRORS ({len(self.result.errors)}):")
            lines.append("-" * 40)

            for error in self.result.errors:
                line_info = f":{error.line_number}" if error.line_number else ""
                lines.append(f"\n{error.file_path}{line_info}")
                lines.append(f"  [{error.error_type}] {error.message}")

        # Warnings
        if self.result.warnings:
            lines.append("\n" + "-" * 40)
            lines.append(f"WARNINGS ({len(self.result.warnings)}):")
            lines.append("-" * 40)

            for warning in self.result.warnings:
                line_info = f":{warning.line_number}" if warning.line_number else ""
                lines.append(f"\n{warning.file_path}{line_info}")
                lines.append(f"  [{warning.error_type}] {warning.message}")

        # Summary
        lines.append("\n" + "-" * 40)
        lines.append("SUMMARY:")
        lines.append("-" * 40)
        lines.append(f"Errors: {summary['errors']}")
        lines.append(f"Warnings: {summary['warnings']}")

        if summary['valid']:
            lines.append(f"\n\u2713 WORK ORDER QUEUE VALIDATION PASSED")
        else:
            lines.append(f"\n\u2717 WORK ORDER QUEUE VALIDATION FAILED")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        output = {
            "summary": self.get_summary(),
            "errors": [
                {
                    "file": e.file_path,
                    "line": e.line_number,
                    "type": e.error_type,
                    "message": e.message,
                    "severity": e.severity
                }
                for e in self.result.errors
            ],
            "warnings": [
                {
                    "file": w.file_path,
                    "line": w.line_number,
                    "type": w.error_type,
                    "message": w.message,
                    "severity": w.severity
                }
                for w in self.result.warnings
            ]
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Work Order Queue Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - All queues valid
  1 - Validation errors found
  2 - File/parse error

Examples:
  %(prog)s LogBook/work-orders/          # Validate all WO queue files
  %(prog)s LogBook/builder/WO_QUEUE.yaml # Validate single queue file
  %(prog)s LogBook/ --strict             # Warnings become errors
  %(prog)s LogBook/ --format=json        # JSON output
        """
    )

    parser.add_argument(
        "path",
        type=Path,
        help="Work order queue file or directory to validate"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--help-exit-codes",
        action="store_true",
        help="Show exit code documentation"
    )

    args = parser.parse_args()

    if args.help_exit_codes:
        print("Exit codes:")
        print("  0 - All queues valid")
        print("  1 - Validation errors found")
        print("  2 - File/parse error")
        sys.exit(0)

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(2)

    validator = WOQueueValidator(
        verbose=args.verbose,
        strict=args.strict
    )

    result = validator.validate_path(args.path)

    # Output results
    if args.format == "json":
        print(validator.format_json_output())
    else:
        print(validator.format_text_output())

    # Exit code
    if result.valid:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
