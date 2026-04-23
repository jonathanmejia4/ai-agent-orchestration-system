#!/usr/bin/env python3
"""
validate_logbook.py - LogBook Entry Validation Tool

Validates LogBook YAML files for schema compliance, required fields,
and data integrity. Used for rollback verification and audit trail validation.

Exit codes:
  0 - All entries valid
  1 - Validation errors found
  2 - File/parse error

Usage:
  python tools/validate_logbook.py LogBook/
  python tools/validate_logbook.py LogBook/pm/STATE.md
  python tools/validate_logbook.py LogBook/builder/progress.yaml --strict
  python tools/validate_logbook.py LogBook/ --format=json

Reference: FAILURE_MODES.md:344,761, ROLLBACK_PROCEDURES.md:314
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    """Result of validating a LogBook file or directory."""
    path: str
    files_checked: int = 0
    entries_checked: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    valid: bool = True

class LogBookValidator:
    """Validates LogBook YAML entries for schema compliance and integrity."""

    # Required fields for different entry types (aligned with logbook_entry_schema.yaml)
    REQUIRED_FIELDS = {
        "default": ["entry_id", "entry_type", "timestamp", "author"],
        "action": ["entry_id", "entry_type", "timestamp", "author", "action"],
        "decision": ["entry_id", "entry_type", "timestamp", "author", "decision", "rationale"],
        "verdict": ["entry_id", "entry_type", "timestamp", "author", "task_id", "verdict"],
        "work_order": ["entry_id", "entry_type", "timestamp", "author", "work_order_id", "status"],
        "escalation": ["entry_id", "entry_type", "timestamp", "author", "escalation_type"],
        "state": ["last_updated", "current_phase"],
    }

    # Valid agent names (matches logbook_entry_schema.yaml:48-49)
    VALID_AGENTS = ["PM", "Builder", "Planner", "Critic", "Orchestrator", "Human", "system",
                    "pm", "builder", "critic", "planner"]  # Include lowercase for backwards compat

    # Valid verdict values (matches critic_verdict_schema.yaml:42-60)
    VALID_VERDICTS = ["APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"]

    # Valid LogBook entry statuses (aligned with logbook_entry_schema.yaml:66-70)
    VALID_STATUSES = ["draft", "active", "resolved", "archived"]

    # Timestamp patterns
    TIMESTAMP_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO 8601
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",   # Space separated
        r"^\d{4}-\d{2}-\d{2}$",                     # Date only
    ]

    def __init__(self, verbose: bool = False, strict: bool = False):
        self.verbose = verbose
        self.strict = strict  # Warnings become errors
        self.result = ValidationResult(path="")

    def log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def validate_path(self, path: Path) -> ValidationResult:
        """Validate a file or directory."""
        self.result = ValidationResult(path=str(path))

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
        """Recursively validate all YAML files in directory."""
        yaml_files = list(dir_path.rglob("*.yaml")) + list(dir_path.rglob("*.yml"))

        if not yaml_files:
            self.log(f"No YAML files found in {dir_path}")

        for yaml_file in yaml_files:
            self._validate_file(yaml_file)

    def _validate_file(self, file_path: Path):
        """Validate a single YAML file."""
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
                    message="File is empty",
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
                    message="File parses to null/empty",
                    severity="WARNING"
                ))
                return

            # Validate entries based on structure
            self._validate_entries(file_path, data)

        except Exception as e:
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="FILE_ERROR",
                message=f"Error reading file: {e}"
            ))

    def _validate_entries(self, file_path: Path, data):
        """Validate LogBook entries based on data structure."""
        file_name = file_path.stem.lower()

        # Determine entry type based on file location/name
        entry_type = self._determine_entry_type(file_path)

        if isinstance(data, list):
            # List of entries
            for i, entry in enumerate(data):
                if isinstance(entry, dict):
                    self.result.entries_checked += 1
                    self._validate_entry(file_path, entry, entry_type, index=i)
        elif isinstance(data, dict):
            # Single entry or state file
            self.result.entries_checked += 1
            self._validate_entry(file_path, data, entry_type)
        else:
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="UNEXPECTED_STRUCTURE",
                message=f"Expected dict or list, got {type(data).__name__}",
                severity="WARNING"
            ))

    def _determine_entry_type(self, file_path: Path) -> str:
        """Determine entry type based on file path."""
        path_str = str(file_path).lower()

        if "state" in path_str:
            return "state"
        elif "verdict" in path_str or "critic" in path_str:
            return "verdict"
        elif "decision" in path_str:
            return "decision"
        elif "work-order" in path_str or "work_order" in path_str:
            return "work_order"
        elif "escalation" in path_str:
            return "escalation"
        elif "action" in path_str or "progress" in path_str:
            return "action"
        else:
            return "default"

    def _validate_entry(self, file_path: Path, entry: dict, entry_type: str, index: int = None):
        """Validate a single LogBook entry."""
        index_str = f"[{index}]" if index is not None else ""

        # Check required fields
        required = self.REQUIRED_FIELDS.get(entry_type, self.REQUIRED_FIELDS["default"])
        for field in required:
            if field not in entry:
                self.result.errors.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="MISSING_FIELD",
                    message=f"Entry{index_str}: Missing required field '{field}'"
                ))

        # Validate timestamp format
        timestamp = entry.get("timestamp") or entry.get("last_updated")
        if timestamp:
            self._validate_timestamp(file_path, timestamp, index_str)

        # Validate agent name
        agent = entry.get("agent")
        if agent and agent.lower() not in self.VALID_AGENTS:
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="UNKNOWN_AGENT",
                message=f"Entry{index_str}: Unknown agent '{agent}'",
                severity="WARNING"
            ))

        # Validate verdict values
        verdict = entry.get("verdict")
        if verdict and verdict.upper() not in self.VALID_VERDICTS:
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_VERDICT",
                message=f"Entry{index_str}: Invalid verdict '{verdict}'"
            ))

        # Validate status values (case-insensitive, schema uses lowercase)
        status = entry.get("status")
        if status and status.lower() not in self.VALID_STATUSES:
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="UNKNOWN_STATUS",
                message=f"Entry{index_str}: Unknown status '{status}'. Valid: {self.VALID_STATUSES}",
                severity="WARNING"
            ))

        # Validate work_order_id format
        wo_id = entry.get("work_order_id")
        if wo_id and not re.match(r"^WO-\d{4}-\d{3,}$|^WO-\d+$", str(wo_id)):
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_WORK_ORDER_ID",
                message=f"Entry{index_str}: Invalid work_order_id format '{wo_id}'",
                severity="WARNING"
            ))

        # Validate task_id format (aligned with logbook_entry_schema.yaml:52-55)
        task_id = entry.get("task_id")
        if task_id and not re.match(r"^\d+\.\d+(\.\d+)?$", str(task_id)):
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_TASK_ID",
                message=f"Entry{index_str}: Invalid task_id format '{task_id}'. Expected X.Y or X.Y.Z",
                severity="WARNING"
            ))

    def _validate_timestamp(self, file_path: Path, timestamp, index_str: str):
        """Validate timestamp format."""
        ts_str = str(timestamp)

        valid = any(re.match(pattern, ts_str) for pattern in self.TIMESTAMP_PATTERNS)

        if not valid:
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_TIMESTAMP",
                message=f"Entry{index_str}: Invalid timestamp format '{ts_str}'",
                severity="WARNING"
            ))

    def get_summary(self) -> dict:
        """Get validation summary."""
        return {
            "path": self.result.path,
            "files_checked": self.result.files_checked,
            "entries_checked": self.result.entries_checked,
            "errors": len(self.result.errors),
            "warnings": len(self.result.warnings),
            "valid": self.result.valid,
            "strict_mode": self.strict
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("LOGBOOK VALIDATION REPORT")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nPath: {summary['path']}")
        lines.append(f"Files checked: {summary['files_checked']}")
        lines.append(f"Entries checked: {summary['entries_checked']}")
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
            lines.append(f"\n\u2713 LOGBOOK VALIDATION PASSED")
        else:
            lines.append(f"\n\u2717 LOGBOOK VALIDATION FAILED")

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
        description="LogBook Entry Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - All entries valid
  1 - Validation errors found
  2 - File/parse error

Examples:
  %(prog)s LogBook/                      # Validate all LogBook files
  %(prog)s LogBook/pm/STATE.md           # Validate single file
  %(prog)s LogBook/ --strict             # Warnings become errors
  %(prog)s LogBook/ --format=json        # JSON output
        """
    )

    parser.add_argument(
        "path",
        type=Path,
        help="LogBook file or directory to validate"
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

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(2)

    validator = LogBookValidator(
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
