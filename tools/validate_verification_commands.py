#!/usr/bin/env python3
"""
Validate Verification Commands in Issue Files

Pre-save validation tool that catches malformed verification commands
before they're committed to the repository.

Features:
- Detects unsubstituted placeholders ({var} and <var>)
- Detects shell commands used as file paths
- Detects wrong test flags (-f vs -d)
- Detects wildcards in test commands
- Detects CLI examples copied as verification commands

Usage:
    python3 tools/validate_verification_commands.py issues/G/G-01.md
    python3 tools/validate_verification_commands.py --lane G
    python3 tools/validate_verification_commands.py --all
    python3 tools/validate_verification_commands.py --all --fix  # Auto-fix where possible
"""

import os
import re
import sys
import glob
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# =============================================================================
# VALIDATION RULES
# =============================================================================

@dataclass
class ValidationError:
    """A single validation error."""
    issue_id: str
    check_name: str
    command: str
    error_type: str
    message: str
    severity: str  # ERROR, WARNING
    fixable: bool = False
    suggested_fix: str = ""


# Patterns that indicate malformed verification commands
VALIDATION_RULES = [
    # Unsubstituted placeholders
    (r'\{[a-z_]+\}', "UNSUBSTITUTED_VAR",
     "Unsubstituted {placeholder} variable", "ERROR"),
    (r'<[a-z_-]+>', "UNSUBSTITUTED_VAR",
     "Unsubstituted <placeholder> variable", "ERROR"),

    # Shell commands used as file paths
    (r'test\s+-[efds]\s+(python3?|bash|sh|ls|cat|grep|find|echo|node)\s',
     "SHELL_CMD_AS_PATH",
     "Shell command used as file path in test", "ERROR"),

    # Wrong test flag for directories
    (r'test\s+-f\s+\S+/$', "WRONG_TEST_FLAG",
     "Using -f on directory path (should be -d)", "WARNING"),

    # Wildcards in test command
    (r'test\s+-[ef]\s+[^\s]*\*[^\s]*\s', "WILDCARD_IN_TEST",
     "Wildcard in test command (use compgen or ls)", "WARNING"),

    # CLI flag with placeholder argument
    (r'--\w+\s+<\w+>', "CLI_PLACEHOLDER",
     "CLI flag with placeholder argument", "ERROR"),

    # Documentation example copied as verification
    (r'python3?\s+tools/\S+\s+--\w+\s+<', "DOC_EXAMPLE",
     "Documentation example copied as verification command", "ERROR"),

    # Multiple paths in single test
    (r'test\s+-[efds]\s+\S+\s+\S+\s*&&', "MULTI_PATH_TEST",
     "Multiple paths in single test command", "WARNING"),
]


# =============================================================================
# PARSING
# =============================================================================

def parse_frontmatter(filepath: str) -> Optional[Dict]:
    """Parse YAML frontmatter from issue file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    if not content.startswith('---'):
        return None

    end = content.find('\n---\n', 3)
    if end < 0:
        return None

    try:
        import yaml
        return yaml.safe_load(content[4:end])
    except Exception:
        return None


def extract_verification_commands(filepath: str) -> List[Dict[str, str]]:
    """Extract Verification Commands section from issue file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []

    commands = []

    # Find Verification Commands section
    match = re.search(r'\*\*Verification Commands.*?\*\*.*?```bash\n(.*?)```', content, re.DOTALL)
    if not match:
        return commands

    cmd_section = match.group(1)

    # Extract individual checks
    check_pattern = r'#\s*(Check\s*\d+):\s*([^\n]+)\n([^\n#]+)'
    for m in re.finditer(check_pattern, cmd_section):
        check_num = m.group(1).strip()
        check_name = m.group(2).strip()
        command = m.group(3).strip()

        if command and not command.startswith('#'):
            commands.append({
                'check': check_num,
                'name': check_name,
                'command': command
            })

    return commands


# =============================================================================
# VALIDATION
# =============================================================================

def validate_command(issue_id: str, check_name: str, command: str) -> List[ValidationError]:
    """Validate a single verification command against all rules."""
    errors = []

    for pattern, error_type, message, severity in VALIDATION_RULES:
        if re.search(pattern, command):
            errors.append(ValidationError(
                issue_id=issue_id,
                check_name=check_name,
                command=command,
                error_type=error_type,
                message=message,
                severity=severity,
                fixable=(error_type in ['WRONG_TEST_FLAG', 'WILDCARD_IN_TEST']),
                suggested_fix=suggest_fix(command, error_type)
            ))

    return errors


def suggest_fix(command: str, error_type: str) -> str:
    """Suggest a fix for a validation error."""
    if error_type == 'WRONG_TEST_FLAG':
        return re.sub(r'test\s+-f\s+', 'test -d ', command)

    if error_type == 'WILDCARD_IN_TEST':
        match = re.search(r'test\s+-[ef]\s+([^\s&|;]+)', command)
        if match:
            pattern = match.group(1)
            return f'ls {pattern} >/dev/null 2>&1 && echo "PASS" || echo "FAIL"'

    if error_type == 'SHELL_CMD_AS_PATH':
        # Remove shell interpreter
        return re.sub(r'(test\s+-[efds]\s+)(python3?|bash|sh)\s+', r'\1', command)

    return ""


def validate_issue(filepath: str) -> Tuple[str, List[ValidationError]]:
    """Validate all verification commands in an issue file."""
    frontmatter = parse_frontmatter(filepath)
    if not frontmatter:
        return "", []

    issue_id = frontmatter.get('issue_id', Path(filepath).stem)
    commands = extract_verification_commands(filepath)

    all_errors = []
    for cmd_spec in commands:
        errors = validate_command(issue_id, cmd_spec['name'], cmd_spec['command'])
        all_errors.extend(errors)

    return issue_id, all_errors


# =============================================================================
# OUTPUT
# =============================================================================

def print_errors(errors: List[ValidationError], verbose: bool = False) -> None:
    """Print validation errors."""
    if not errors:
        return

    # Group by issue
    by_issue = {}
    for err in errors:
        if err.issue_id not in by_issue:
            by_issue[err.issue_id] = []
        by_issue[err.issue_id].append(err)

    for issue_id, issue_errors in by_issue.items():
        print(f"\n{issue_id}:")
        for err in issue_errors:
            icon = "❌" if err.severity == "ERROR" else "⚠️"
            print(f"  {icon} [{err.error_type}] {err.message}")
            if verbose:
                print(f"      Check: {err.check_name}")
                print(f"      Command: {err.command[:60]}...")
                if err.suggested_fix:
                    print(f"      Suggested: {err.suggested_fix[:60]}...")


def print_summary(total_files: int, total_errors: int, errors: List[ValidationError]) -> None:
    """Print validation summary."""
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Files checked: {total_files}")
    print(f"Total errors:  {total_errors}")

    if errors:
        # Count by type
        by_type = {}
        for err in errors:
            by_type[err.error_type] = by_type.get(err.error_type, 0) + 1

        print("\nErrors by type:")
        for error_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count}")

        # Count fixable
        fixable = sum(1 for e in errors if e.fixable)
        if fixable:
            print(f"\nAuto-fixable: {fixable}")
            print("Run with --fix to apply automatic corrections")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Validate verification commands in issue files'
    )
    parser.add_argument('files', nargs='*', help='Issue files to validate')
    parser.add_argument('--lane', '-l', type=str, help='Validate all issues in lane')
    parser.add_argument('--all', '-a', action='store_true', help='Validate all issues')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--fix', action='store_true', help='Auto-fix where possible')
    parser.add_argument('--errors-only', action='store_true', help='Only show ERRORs, not WARNINGs')

    args = parser.parse_args()

    # Collect files to validate
    files = []
    issues_dir = "issues"

    if args.files:
        files = args.files
    elif args.lane:
        files = glob.glob(os.path.join(issues_dir, args.lane.upper(), '*.md'))
    elif args.all:
        files = glob.glob(os.path.join(issues_dir, '*', '*.md'))
    else:
        parser.print_help()
        return 1

    # Filter out templates
    files = [f for f in files if 'TEMPLATE' not in f.upper() and 'README' not in f.upper()]

    if not files:
        print("No issue files found to validate")
        return 1

    # Validate
    all_errors = []
    files_with_errors = 0

    for filepath in sorted(files):
        issue_id, errors = validate_issue(filepath)

        if args.errors_only:
            errors = [e for e in errors if e.severity == "ERROR"]

        if errors:
            files_with_errors += 1
            all_errors.extend(errors)

    # Output
    if all_errors:
        print_errors(all_errors, args.verbose)
    else:
        print("✅ No validation errors found!")

    print_summary(len(files), len(all_errors), all_errors)

    # Return exit code based on errors
    error_count = sum(1 for e in all_errors if e.severity == "ERROR")
    return 1 if error_count > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
