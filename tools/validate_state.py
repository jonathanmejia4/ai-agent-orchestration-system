#!/usr/bin/env python3
"""
validate_state.py - Agent State Validation Tool

Validates agent STATE.md files and state YAML files for schema compliance,
required sections, and state consistency. Ensures agent state files follow
the defined structure and contain required information.

Exit codes:
  0 - All state files valid
  1 - Validation errors found
  2 - File/parse error

Usage:
  python tools/validate_state.py LogBook/
  python tools/validate_state.py LogBook/pm/STATE.md
  python tools/validate_state.py LogBook/builder/STATE.md --strict
  python tools/validate_state.py LogBook/ --format=json

Reference: integration-test.yml:367, state-persistence-protocol.md
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
    """Result of validating agent state files."""
    path: str
    files_checked: int = 0
    states_validated: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    valid: bool = True

class StateValidator:
    """Validates agent state files for schema compliance and integrity."""

    # Valid agent names (matches agent_state_schema.yaml agent_type enum)
    VALID_AGENTS = [
        "pm", "planner", "builder", "critic",
        "critic-orchestrator", "critic-correctness", "critic-test-coverage",
        "critic-code-quality", "critic-security", "critic-saf-compliance",
        "critic-documentation", "critic-acl"
    ]

    # Required sections for STATE.md files
    REQUIRED_MD_SECTIONS = [
        "current_phase",
        "last_updated",
    ]

    # Optional but expected sections
    EXPECTED_MD_SECTIONS = [
        "working_memory",
        "active_tasks",
        "blocked_items",
        "next_actions",
    ]

    # Required fields for YAML state files
    REQUIRED_YAML_FIELDS = {
        "default": ["last_updated"],
        "session": ["session_id", "start_time", "agent"],
        "progress": ["timestamp", "phase"],
    }

    # Valid phases for agents
    VALID_PHASES = [
        "IDLE", "PLANNING", "EXECUTING", "REVIEWING",
        "BLOCKED", "WAITING", "COMPLETED", "ERROR",
        "INITIALIZING", "READY", "ACTIVE"
    ]

    # Timestamp patterns
    TIMESTAMP_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO 8601
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",   # Space separated
        r"^\d{4}-\d{2}-\d{2}$",                     # Date only
    ]

    def __init__(self, verbose: bool = False, strict: bool = False):
        self.verbose = verbose
        self.strict = strict
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
        """Recursively validate state files in directory."""
        # Find STATE.md files
        state_md_files = list(dir_path.rglob("STATE.md"))

        # Find state YAML files
        state_yaml_files = list(dir_path.rglob("*state*.yaml"))
        state_yaml_files.extend(list(dir_path.rglob("*state*.yml")))

        # Also check for session files
        session_files = list(dir_path.rglob("*session*.yaml"))

        all_files = list(set(state_md_files + state_yaml_files + session_files))

        if not all_files:
            self.log(f"No state files found in {dir_path}")
            self.result.warnings.append(ValidationError(
                file_path=str(dir_path),
                line_number=None,
                error_type="NO_STATE_FILES",
                message="No state files found",
                severity="WARNING"
            ))

        for state_file in all_files:
            self._validate_file(state_file)

    def _validate_file(self, file_path: Path):
        """Validate a single state file."""
        self.result.files_checked += 1
        self.log(f"Validating: {file_path}")

        if file_path.suffix.lower() == ".md":
            self._validate_md_state(file_path)
        elif file_path.suffix.lower() in [".yaml", ".yml"]:
            self._validate_yaml_state(file_path)
        else:
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="UNKNOWN_FORMAT",
                message=f"Unknown state file format: {file_path.suffix}",
                severity="WARNING"
            ))

    def _validate_md_state(self, file_path: Path):
        """Validate a STATE.md file."""
        self.result.states_validated += 1

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.strip():
                self.result.errors.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="EMPTY_FILE",
                    message="STATE.md file is empty"
                ))
                return

            # Check for required sections
            content_lower = content.lower()

            for section in self.REQUIRED_MD_SECTIONS:
                # Look for section header or field
                patterns = [
                    f"## {section}",
                    f"### {section}",
                    f"**{section}**",
                    f"{section}:",
                    f"# {section}",
                ]
                found = any(p.lower() in content_lower for p in patterns)

                if not found:
                    self.result.errors.append(ValidationError(
                        file_path=str(file_path),
                        line_number=None,
                        error_type="MISSING_SECTION",
                        message=f"Missing required section: {section}"
                    ))

            # Check for expected sections (warnings only)
            for section in self.EXPECTED_MD_SECTIONS:
                patterns = [
                    f"## {section}",
                    f"### {section}",
                    f"**{section}**",
                    f"{section}:",
                ]
                found = any(p.lower() in content_lower for p in patterns)

                if not found:
                    self.result.warnings.append(ValidationError(
                        file_path=str(file_path),
                        line_number=None,
                        error_type="MISSING_EXPECTED_SECTION",
                        message=f"Missing expected section: {section}",
                        severity="WARNING"
                    ))

            # Validate last_updated timestamp if present
            timestamp_match = re.search(
                r"last[_\s-]?updated[:\s]+([^\n]+)",
                content,
                re.IGNORECASE
            )
            if timestamp_match:
                ts_value = timestamp_match.group(1).strip()
                self._validate_timestamp(file_path, ts_value)

            # Check for YAML frontmatter
            if content.startswith("---"):
                self._validate_frontmatter(file_path, content)

            # Validate agent name in path
            self._validate_agent_path(file_path)

        except Exception as e:
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="FILE_ERROR",
                message=f"Error reading file: {e}"
            ))

    def _validate_yaml_state(self, file_path: Path):
        """Validate a YAML state file."""
        self.result.states_validated += 1

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

            if not content.strip():
                self.result.warnings.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="EMPTY_FILE",
                    message="State file is empty",
                    severity="WARNING"
                ))
                return

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
                    message="State file parses to null/empty",
                    severity="WARNING"
                ))
                return

            # Determine state type based on file name
            state_type = self._determine_state_type(file_path)

            # Validate based on type
            self._validate_state_data(file_path, data, state_type)

        except Exception as e:
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="FILE_ERROR",
                message=f"Error reading file: {e}"
            ))

    def _determine_state_type(self, file_path: Path) -> str:
        """Determine state file type based on name."""
        name = file_path.stem.lower()

        if "session" in name:
            return "session"
        elif "progress" in name:
            return "progress"
        else:
            return "default"

    def _validate_state_data(self, file_path: Path, data: dict, state_type: str):
        """Validate state data against expected schema."""
        if not isinstance(data, dict):
            self.result.errors.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_STRUCTURE",
                message=f"Expected dict, got {type(data).__name__}"
            ))
            return

        # Check required fields
        required = self.REQUIRED_YAML_FIELDS.get(state_type, self.REQUIRED_YAML_FIELDS["default"])
        for field in required:
            if field not in data:
                self.result.errors.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="MISSING_FIELD",
                    message=f"Missing required field: {field}"
                ))

        # Validate timestamp fields
        for ts_field in ["last_updated", "timestamp", "start_time", "end_time"]:
            if ts_field in data:
                self._validate_timestamp(file_path, data[ts_field])

        # Validate phase if present
        phase = data.get("phase") or data.get("current_phase")
        if phase and isinstance(phase, str):
            if phase.upper() not in self.VALID_PHASES:
                self.result.warnings.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="UNKNOWN_PHASE",
                    message=f"Unknown phase: {phase}",
                    severity="WARNING"
                ))

        # Validate agent if present
        agent = data.get("agent")
        if agent and isinstance(agent, str):
            if agent.lower() not in self.VALID_AGENTS:
                self.result.warnings.append(ValidationError(
                    file_path=str(file_path),
                    line_number=None,
                    error_type="UNKNOWN_AGENT",
                    message=f"Unknown agent: {agent}",
                    severity="WARNING"
                ))

    def _validate_frontmatter(self, file_path: Path, content: str):
        """Validate YAML frontmatter in STATE.md."""
        if not HAS_YAML:
            return

        # Extract frontmatter
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return

        try:
            frontmatter = yaml.safe_load(match.group(1))
            if frontmatter and isinstance(frontmatter, dict):
                # Validate frontmatter fields
                if "last_updated" in frontmatter:
                    self._validate_timestamp(file_path, frontmatter["last_updated"])
        except yaml.YAMLError:
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_FRONTMATTER",
                message="Invalid YAML frontmatter",
                severity="WARNING"
            ))

    def _validate_timestamp(self, file_path: Path, timestamp):
        """Validate timestamp format."""
        if timestamp is None:
            return

        ts_str = str(timestamp)
        valid = any(re.match(pattern, ts_str) for pattern in self.TIMESTAMP_PATTERNS)

        if not valid:
            self.result.warnings.append(ValidationError(
                file_path=str(file_path),
                line_number=None,
                error_type="INVALID_TIMESTAMP",
                message=f"Invalid timestamp format: {ts_str}",
                severity="WARNING"
            ))

    def _validate_agent_path(self, file_path: Path):
        """Validate that state file is in valid agent directory."""
        path_parts = file_path.parts

        # Look for LogBook/<agent>/ pattern
        for i, part in enumerate(path_parts):
            if part.lower() == "logbook" and i + 1 < len(path_parts):
                agent = path_parts[i + 1].lower()
                if agent not in self.VALID_AGENTS and agent not in ["shared", "work-orders", "events", "archive"]:
                    self.result.warnings.append(ValidationError(
                        file_path=str(file_path),
                        line_number=None,
                        error_type="UNUSUAL_PATH",
                        message=f"State file in non-standard location: {agent}",
                        severity="WARNING"
                    ))
                break

    def get_summary(self) -> dict:
        """Get validation summary."""
        return {
            "path": self.result.path,
            "files_checked": self.result.files_checked,
            "states_validated": self.result.states_validated,
            "errors": len(self.result.errors),
            "warnings": len(self.result.warnings),
            "valid": self.result.valid,
            "strict_mode": self.strict
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("AGENT STATE VALIDATION REPORT")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nPath: {summary['path']}")
        lines.append(f"Files checked: {summary['files_checked']}")
        lines.append(f"States validated: {summary['states_validated']}")
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
            lines.append(f"\n\u2713 AGENT STATE VALIDATION PASSED")
        else:
            lines.append(f"\n\u2717 AGENT STATE VALIDATION FAILED")

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
        description="Agent State Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - All state files valid
  1 - Validation errors found
  2 - File/parse error

Examples:
  %(prog)s LogBook/                    # Validate all state files
  %(prog)s LogBook/pm/STATE.md         # Validate single state file
  %(prog)s LogBook/ --strict           # Warnings become errors
  %(prog)s LogBook/ --format=json      # JSON output
        """
    )

    parser.add_argument(
        "path",
        type=Path,
        help="State file or directory to validate"
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
        print("  0 - All state files valid")
        print("  1 - Validation errors found")
        print("  2 - File/parse error")
        sys.exit(0)

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(2)

    validator = StateValidator(
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
