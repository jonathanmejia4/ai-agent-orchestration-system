#!/usr/bin/env python3
"""
Status File Validator for the system.

Validates LogBook status.yaml files against the state machine definition.
Ensures status transitions are legal and all required fields are present.

See: PLANNING/STATE_TRANSITION_VALIDATION.md

Usage:
    python3 tools/validate_status.py LogBook/progress/tasks/task-2.3/status.yaml
    python3 tools/validate_status.py --all
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# Valid states as defined in task_status_schema.yaml
VALID_STATES = {
    'PLANNED',
    'IN_PROGRESS',
    'BLOCKED',
    'COMPLETE_READY_FOR_REVIEW',
    'IN_REVIEW',
    'REJECTED',
    'APPROVED',
    'PROMOTED',
    'CANCELLED',
}

# Legal state transitions (from -> set of allowed to states)
# Matches task_status_schema.yaml allowed_transitions
STATE_TRANSITIONS = {
    'PLANNED': {'IN_PROGRESS', 'CANCELLED'},
    'IN_PROGRESS': {'COMPLETE_READY_FOR_REVIEW', 'BLOCKED', 'CANCELLED'},
    'BLOCKED': {'IN_PROGRESS', 'CANCELLED'},
    'COMPLETE_READY_FOR_REVIEW': {'IN_REVIEW'},
    'IN_REVIEW': {'APPROVED', 'REJECTED'},
    'REJECTED': {'IN_PROGRESS', 'CANCELLED'},
    'APPROVED': {'PROMOTED', 'CANCELLED'},
    'PROMOTED': set(),  # Terminal state
    'CANCELLED': set(),  # Terminal state
}

# Required fields in status.yaml
REQUIRED_FIELDS = [
    'task_id',
    'status',
]

# Optional but recommended fields
RECOMMENDED_FIELDS = [
    'started_at',
    'completed_at',
    'assigned_to',
    'progress_percentage',
]

class ValidationError:
    """Represents a validation error."""

    def __init__(self, error_type: str, message: str, field: Optional[str] = None):
        self.error_type = error_type
        self.message = message
        self.field = field

    def __str__(self):
        if self.field:
            return f'[{self.error_type}] {self.field}: {self.message}'
        return f'[{self.error_type}] {self.message}'

def load_status_file(path: Path) -> Tuple[Optional[Dict], Optional[str]]:
    """Load and parse a status.yaml file.

    Args:
        path: Path to status.yaml file

    Returns:
        Tuple of (status dict, error message if any)
    """
    if not path.exists():
        return None, f'File not found: {path}'

    try:
        content = path.read_text(encoding='utf-8')
        data = yaml.safe_load(content)
        if data is None:
            return None, f'Empty or invalid YAML: {path}'
        return data, None
    except yaml.YAMLError as e:
        return None, f'YAML parse error: {e}'
    except Exception as e:
        return None, f'Error reading file: {e}'

def validate_required_fields(status: Dict) -> List[ValidationError]:
    """Validate that all required fields are present.

    Args:
        status: Status dictionary

    Returns:
        List of validation errors
    """
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in status:
            errors.append(ValidationError(
                'MISSING_FIELD',
                f'Required field missing',
                field
            ))
        elif status[field] is None or status[field] == '':
            errors.append(ValidationError(
                'EMPTY_FIELD',
                f'Required field is empty',
                field
            ))

    return errors

def validate_status_value(status: Dict) -> List[ValidationError]:
    """Validate the status field value.

    Args:
        status: Status dictionary

    Returns:
        List of validation errors
    """
    errors = []

    status_value = status.get('status')
    if status_value and status_value not in VALID_STATES:
        errors.append(ValidationError(
            'INVALID_STATUS',
            f"Invalid status '{status_value}'. Valid values: {', '.join(sorted(VALID_STATES))}",
            'status'
        ))

    return errors

def validate_timestamps(status: Dict) -> List[ValidationError]:
    """Validate timestamp fields for proper format and ordering.

    Args:
        status: Status dictionary

    Returns:
        List of validation errors
    """
    errors = []
    timestamps = {}

    for field in ['created_at', 'started_at', 'completed_at', 'updated_at']:
        if field in status and status[field]:
            value = status[field]
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    timestamps[field] = dt
                except ValueError:
                    errors.append(ValidationError(
                        'INVALID_TIMESTAMP',
                        f"Invalid timestamp format. Use ISO 8601 format.",
                        field
                    ))
            elif isinstance(value, datetime):
                timestamps[field] = value

    # Validate ordering
    if 'started_at' in timestamps and 'created_at' in timestamps:
        if timestamps['started_at'] < timestamps['created_at']:
            errors.append(ValidationError(
                'TIMESTAMP_ORDER',
                'started_at cannot be before created_at',
                'started_at'
            ))

    if 'completed_at' in timestamps and 'started_at' in timestamps:
        if timestamps['completed_at'] < timestamps['started_at']:
            errors.append(ValidationError(
                'TIMESTAMP_ORDER',
                'completed_at cannot be before started_at',
                'completed_at'
            ))

    return errors

def validate_state_transition(
    current_status: str,
    previous_status: Optional[str]
) -> List[ValidationError]:
    """Validate that a state transition is legal.

    Args:
        current_status: Current status value
        previous_status: Previous status value (if known)

    Returns:
        List of validation errors
    """
    errors = []

    if previous_status and previous_status in STATE_TRANSITIONS:
        allowed = STATE_TRANSITIONS[previous_status]
        if current_status not in allowed and current_status != previous_status:
            errors.append(ValidationError(
                'ILLEGAL_TRANSITION',
                f"Transition from '{previous_status}' to '{current_status}' is not allowed. "
                f"Valid transitions: {', '.join(sorted(allowed)) if allowed else 'none (terminal state)'}"
            ))

    return errors

def validate_progress_percentage(status: Dict) -> List[ValidationError]:
    """Validate progress_percentage field if present.

    Args:
        status: Status dictionary

    Returns:
        List of validation errors
    """
    errors = []

    if 'progress_percentage' in status:
        value = status['progress_percentage']
        if not isinstance(value, (int, float)):
            errors.append(ValidationError(
                'INVALID_TYPE',
                f'Must be a number between 0 and 100',
                'progress_percentage'
            ))
        elif value < 0 or value > 100:
            errors.append(ValidationError(
                'INVALID_RANGE',
                f'Must be between 0 and 100, got {value}',
                'progress_percentage'
            ))

        # Check consistency with status
        status_value = status.get('status')
        if status_value == 'PROMOTED' and value != 100:
            errors.append(ValidationError(
                'INCONSISTENT_VALUE',
                f"Status is 'PROMOTED' but progress is {value}%, should be 100%",
                'progress_percentage'
            ))
        elif status_value == 'PLANNED' and value != 0:
            errors.append(ValidationError(
                'INCONSISTENT_VALUE',
                f"Status is 'PLANNED' but progress is {value}%, should be 0%",
                'progress_percentage'
            ))

    return errors

def validate_status_file(
    path: Path,
    previous_status: Optional[str] = None,
    verbose: bool = False
) -> Tuple[bool, List[str]]:
    """Validate a single status.yaml file.

    Args:
        path: Path to status.yaml
        previous_status: Previous status value for transition validation
        verbose: Whether to print detailed output

    Returns:
        Tuple of (passed, list of messages)
    """
    messages = []
    all_errors: List[ValidationError] = []

    # Load file
    status, error = load_status_file(path)
    if error:
        return False, [f'ERROR: {error}']

    # Run validations
    all_errors.extend(validate_required_fields(status))
    all_errors.extend(validate_status_value(status))
    all_errors.extend(validate_timestamps(status))
    all_errors.extend(validate_progress_percentage(status))

    # Validate state transition if previous status known
    current = status.get('status')
    if current and previous_status:
        all_errors.extend(validate_state_transition(current, previous_status))

    # Compile messages
    if all_errors:
        for err in all_errors:
            messages.append(str(err))
        return False, messages

    messages.append('All validations passed')
    if verbose:
        messages.append(f"  status: {status.get('status')}")
        messages.append(f"  task_id: {status.get('task_id')}")

    return True, messages

def find_status_files(base_path: Path) -> List[Path]:
    """Find all status.yaml files under a base path.

    Args:
        base_path: Base directory to search

    Returns:
        List of paths to status.yaml files
    """
    return list(base_path.rglob('status.yaml'))

def main():
    """CLI entry point for validate_status tool."""
    parser = argparse.ArgumentParser(
        description='Validate LogBook status.yaml files',
        epilog='See PLANNING/STATE_TRANSITION_VALIDATION.md for details'
    )
    parser.add_argument(
        'path',
        nargs='?',
        type=Path,
        help='Path to status.yaml file to validate'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Validate all status.yaml files in LogBook/'
    )
    parser.add_argument(
        '--base-path',
        type=Path,
        default=Path('LogBook/progress/tasks'),
        help='Base path for --all search (default: LogBook/progress/tasks)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Only output on failure'
    )
    parser.add_argument(
        '--list-states',
        action='store_true',
        help='List valid states and transitions'
    )

    args = parser.parse_args()

    if args.list_states:
        print('Valid States:')
        for state in sorted(VALID_STATES):
            transitions = STATE_TRANSITIONS.get(state, set())
            trans_str = ', '.join(sorted(transitions)) if transitions else '(terminal)'
            print(f'  {state:15} -> {trans_str}')
        return 0

    if not args.path and not args.all:
        parser.print_help()
        return 1

    exit_code = 0
    total = 0
    passed = 0

    if args.all:
        files = find_status_files(args.base_path)
        if not files:
            if not args.quiet:
                print(f'No status.yaml files found in {args.base_path}')
            return 0
    else:
        files = [args.path]

    for file_path in files:
        total += 1
        success, messages = validate_status_file(file_path, verbose=args.verbose)

        if success:
            passed += 1
            if not args.quiet:
                print(f'PASS: {file_path}')
                if args.verbose:
                    for msg in messages:
                        print(f'  {msg}')
        else:
            exit_code = 1
            print(f'FAIL: {file_path}')
            for msg in messages:
                print(f'  {msg}')

    if total > 1 and not args.quiet:
        print()
        print(f'Summary: {passed}/{total} status files passed validation')

    return exit_code

if __name__ == '__main__':
    sys.exit(main())
