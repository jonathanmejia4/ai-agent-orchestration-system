#!/usr/bin/env python3
"""
Validate issue frontmatter pattern_vars before commit.
Prevents grep commands, glob patterns, and undefined variables.

Detects three bug types:
  BUG-VER-001: Grep commands stored in file_path instead of actual paths
  BUG-VER-002: Glob patterns that won't expand in test -f commands
  BUG-VER-003: Missing required pattern_vars for verification patterns
"""
import os
import re
import sys
import yaml

# Pattern variable requirements by verification_pattern
PATTERN_VARS_REQUIREMENTS = {
    'policy_alignment': ['source_file'],
    'missing_file': ['file_path'],
    'ghost_reference': ['file_path', 'ghost_pattern'],
    'schema_violation': ['schema_file', 'data_file'],
    'missing_directory': ['directory_pattern'],
    'workflow_trigger_drift': ['workflow'],
    'duplicate_implementation': ['implementation1', 'implementation2'],
    'missing_hook_entry': ['hook_file', 'missing_script'],
}

def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown file."""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None

def validate_file_path(file_path, issue_file):
    """
    Validate file_path is an actual path, not a command or glob.
    Returns list of errors.
    """
    errors = []

    if not file_path:
        return errors  # Empty is ok, may be optional

    # BUG-VER-001: Detect grep commands in file_path
    if file_path.startswith('grep') or ' grep ' in file_path or file_path.startswith('find'):
        errors.append({
            'bug': 'BUG-VER-001',
            'file': issue_file,
            'field': 'pattern_vars.file_path',
            'value': file_path,
            'message': 'Contains grep/find command instead of file path',
            'fix': 'Extract actual file path from command'
        })

    # BUG-VER-002: Detect glob patterns
    if '*' in file_path or '?' in file_path:
        errors.append({
            'bug': 'BUG-VER-002',
            'file': issue_file,
            'field': 'pattern_vars.file_path',
            'value': file_path,
            'message': 'Contains glob pattern that test -f cannot expand',
            'fix': 'Use specific file path or directory_path + file_pattern'
        })

    # Detect undefined variable substitutions
    if '{' in file_path and '}' in file_path:
        errors.append({
            'bug': 'BUG-VER-003',
            'file': issue_file,
            'field': 'pattern_vars.file_path',
            'value': file_path,
            'message': 'Contains undefined variable substitution',
            'fix': 'Replace {var} with actual value'
        })

    return errors

def validate_pattern_vars(frontmatter, issue_file):
    """
    Validate pattern_vars for an issue.
    Returns list of errors.
    """
    errors = []

    pattern_vars = frontmatter.get('pattern_vars', {})
    if pattern_vars is None:
        pattern_vars = {}

    # Check file_path if present
    if 'file_path' in pattern_vars:
        errors.extend(validate_file_path(pattern_vars['file_path'], issue_file))

    # BUG-VER-003: Check required variables for verification pattern
    verification_pattern = frontmatter.get('verification_pattern')
    if verification_pattern:
        required_vars = PATTERN_VARS_REQUIREMENTS.get(verification_pattern, [])
        for var in required_vars:
            if var not in pattern_vars or not pattern_vars.get(var):
                errors.append({
                    'bug': 'BUG-VER-003',
                    'file': issue_file,
                    'field': f'pattern_vars.{var}',
                    'value': None,
                    'message': f"verification_pattern '{verification_pattern}' requires pattern_vars.{var}",
                    'fix': f"Add '{var}: <actual_value>' to pattern_vars section"
                })

    return errors

def validate_issue_file(issue_file):
    """Validate a single issue file. Returns list of errors."""
    try:
        with open(issue_file, 'r') as f:
            content = f.read()
    except Exception as e:
        return [{'file': issue_file, 'message': f'Cannot read file: {e}'}]

    frontmatter = parse_frontmatter(content)
    if not frontmatter:
        return []  # No frontmatter, skip validation

    return validate_pattern_vars(frontmatter, issue_file)

def validate_all_issues(issues_dir='issues'):
    """Validate all issue files. Returns list of all errors."""
    all_errors = []

    if not os.path.isdir(issues_dir):
        print(f"Issues directory not found: {issues_dir}")
        return all_errors

    for lane in os.listdir(issues_dir):
        lane_dir = os.path.join(issues_dir, lane)
        if not os.path.isdir(lane_dir):
            continue

        for filename in os.listdir(lane_dir):
            if not filename.endswith('.md'):
                continue

            issue_file = os.path.join(lane_dir, filename)
            errors = validate_issue_file(issue_file)
            all_errors.extend(errors)

    return all_errors

def print_errors(errors, verbose=True):
    """Print errors in human-readable format."""
    if not errors:
        print("No validation errors found")
        return

    # Group by bug type
    by_bug = {}
    for error in errors:
        bug = error.get('bug', 'UNKNOWN')
        if bug not in by_bug:
            by_bug[bug] = []
        by_bug[bug].append(error)

    for bug, bug_errors in sorted(by_bug.items()):
        print(f"\n{'='*60}")
        print(f"{bug}: {len(bug_errors)} issues affected")
        print('='*60)

        for error in bug_errors[:10 if not verbose else len(bug_errors)]:
            print(f"\n  File: {error.get('file')}")
            print(f"  Field: {error.get('field')}")
            if error.get('value'):
                value = error.get('value')
                if len(value) > 80:
                    value = value[:77] + '...'
                print(f"  Value: {value}")
            print(f"  Error: {error.get('message')}")
            print(f"  Fix: {error.get('fix')}")

        if len(bug_errors) > 10 and not verbose:
            print(f"\n  ... and {len(bug_errors) - 10} more")

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate issue frontmatter pattern_vars')
    parser.add_argument('--issues-dir', default='issues', help='Issues directory path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all errors')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--fix', action='store_true', help='Attempt to auto-fix issues')
    args = parser.parse_args()

    errors = validate_all_issues(args.issues_dir)

    if args.json:
        import json
        print(json.dumps(errors, indent=2))
    else:
        print_errors(errors, verbose=args.verbose)
        print(f"\n{'='*60}")
        print(f"TOTAL: {len(errors)} validation errors")
        print('='*60)

    # Exit with error code if validation failed
    if errors:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
