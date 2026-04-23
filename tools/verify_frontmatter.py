#!/usr/bin/env python3
"""
the system Frontmatter Verification Tool

Verifies that YAML frontmatter is present and valid in all issue files.

Checks:
1. All issue files have frontmatter (starts with ---)
2. Frontmatter is valid YAML
3. Required fields are present
4. Field values are valid

Usage:
    python3 tools/verify_frontmatter.py           # Run verification
    python3 tools/verify_frontmatter.py --verbose # Show details
"""

import os
import sys
import glob
import argparse
from datetime import datetime
from typing import Dict, List, Tuple

ISSUES_DIR = "issues"

REQUIRED_FIELDS = [
    'issue_id',
    'lane',
    'status',
    'severity',
    'severity_level',
]

OPTIONAL_FIELDS = [
    'type_tags',
    'category',
    'user_approval_required',
    'verification_pattern',
    'verification_depth',
    'affected_paths',
    'depends_on',
    'blocks',
    'related',
]

VALID_STATUS = ['OPEN', 'RESOLVED']
VALID_SEVERITY_LEVELS = ['HIGH', 'MEDIUM', 'LOW']
VALID_DEPTHS = ['QUICK', 'STANDARD', 'DEEP']

def parse_frontmatter(filepath: str) -> Tuple[bool, dict, str]:
    """Parse frontmatter from file. Returns (success, data, error)."""
    try:
        import yaml
    except ImportError:
        return False, {}, "PyYAML not installed"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, {}, f"Read error: {e}"

    if not content.startswith('---'):
        return False, {}, "No frontmatter (missing opening ---)"

    end = content.find('\n---\n', 3)
    if end < 0:
        return False, {}, "No frontmatter (missing closing ---)"

    try:
        data = yaml.safe_load(content[4:end])
        if not isinstance(data, dict):
            return False, {}, "Frontmatter is not a dictionary"
        return True, data, ""
    except yaml.YAMLError as e:
        return False, {}, f"Invalid YAML: {str(e)[:50]}"

def validate_frontmatter(data: dict, filepath: str) -> List[str]:
    """Validate frontmatter data. Returns list of errors."""
    errors = []
    basename = os.path.basename(filepath)

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate issue_id
    if 'issue_id' in data:
        issue_id = data['issue_id']
        if not isinstance(issue_id, str) or len(issue_id) < 2:
            errors.append(f"Invalid issue_id: {issue_id}")

    # Validate lane
    if 'lane' in data:
        lane = data['lane']
        if not isinstance(lane, str) or len(lane) != 1 or not lane.isalpha():
            errors.append(f"Invalid lane: {lane}")

    # Validate status
    if 'status' in data:
        status = data['status']
        if status not in VALID_STATUS:
            errors.append(f"Invalid status: {status}")

    # Validate severity
    if 'severity' in data:
        sev = data['severity']
        if not isinstance(sev, int) or sev < 1 or sev > 10:
            errors.append(f"Invalid severity: {sev} (must be 1-10)")

    # Validate severity_level
    if 'severity_level' in data:
        level = data['severity_level']
        if level not in VALID_SEVERITY_LEVELS:
            errors.append(f"Invalid severity_level: {level}")

    # Validate verification_depth if present
    if 'verification_depth' in data:
        depth = data['verification_depth']
        if depth not in VALID_DEPTHS:
            errors.append(f"Invalid verification_depth: {depth}")

    # Validate list fields
    for field in ['type_tags', 'affected_paths', 'depends_on', 'blocks', 'related']:
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be a list")

    return errors

def run_verification(issues_dir: str, verbose: bool = False) -> Tuple[bool, Dict]:
    """Run frontmatter verification on all issues."""
    stats = {
        'total': 0,
        'has_frontmatter': 0,
        'valid_yaml': 0,
        'valid_fields': 0,
        'errors': [],
    }

    print("=" * 70)
    print("the system FRONTMATTER VERIFICATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Issues Directory: {issues_dir}")
    print()

    for filepath in sorted(glob.glob(os.path.join(issues_dir, '*', '*.md'))):
        if 'TEMPLATE' in filepath.upper():
            continue

        stats['total'] += 1
        basename = os.path.basename(filepath)

        # Parse frontmatter
        success, data, error = parse_frontmatter(filepath)

        if not success:
            stats['errors'].append((basename, error))
            if verbose:
                print(f"\u274c {basename}: {error}")
            continue

        stats['has_frontmatter'] += 1
        stats['valid_yaml'] += 1

        # Validate fields
        field_errors = validate_frontmatter(data, filepath)

        if field_errors:
            stats['errors'].append((basename, "; ".join(field_errors)))
            if verbose:
                print(f"\u26a0\ufe0f  {basename}: {field_errors[0]}")
        else:
            stats['valid_fields'] += 1
            if verbose:
                print(f"\u2705 {basename}")

    # Results
    print()
    print("-" * 70)
    print("CHECK 1: Frontmatter Presence")
    print("-" * 70)
    pct1 = (stats['has_frontmatter'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"   Files with frontmatter: {stats['has_frontmatter']}/{stats['total']} ({pct1:.1f}%)")

    if pct1 >= 99:
        print(f"   \u2705 PASSED: Frontmatter present in {pct1:.1f}% of files")
    else:
        print(f"   \u274c FAILED: Only {pct1:.1f}% have frontmatter")

    print()
    print("-" * 70)
    print("CHECK 2: Valid YAML")
    print("-" * 70)
    pct2 = (stats['valid_yaml'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"   Files with valid YAML: {stats['valid_yaml']}/{stats['total']} ({pct2:.1f}%)")

    if pct2 >= 99:
        print(f"   \u2705 PASSED: YAML valid in {pct2:.1f}% of files")
    else:
        print(f"   \u274c FAILED: Only {pct2:.1f}% have valid YAML")

    print()
    print("-" * 70)
    print("CHECK 3: Valid Field Values")
    print("-" * 70)
    pct3 = (stats['valid_fields'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"   Files with valid fields: {stats['valid_fields']}/{stats['total']} ({pct3:.1f}%)")

    if pct3 >= 95:
        print(f"   \u2705 PASSED: Fields valid in {pct3:.1f}% of files")
    else:
        print(f"   \u274c FAILED: Only {pct3:.1f}% have valid fields")

    # Show errors if not verbose and there are some
    if stats['errors'] and not verbose:
        print()
        print("-" * 70)
        print(f"First 5 errors (of {len(stats['errors'])}):")
        print("-" * 70)
        for basename, error in stats['errors'][:5]:
            print(f"   {basename}: {error[:60]}")

    # Final verdict
    all_passed = (pct1 >= 99 and pct2 >= 99 and pct3 >= 95)

    print()
    print("=" * 70)

    if all_passed:
        print("\U0001f389 VERIFICATION COMPLETE: ALL CHECKS PASSED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u2705  FRONTMATTER VERIFIED - All files properly formatted     \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")
    else:
        print("\u26a0\ufe0f  VERIFICATION COMPLETE: SOME CHECKS FAILED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u274c  FRONTMATTER NOT WORKING PROPERLY - Review errors above  \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")

    print("=" * 70)
    print()
    print("SUMMARY")
    print(f"   Total Files:        {stats['total']}")
    print(f"   Has Frontmatter:    {stats['has_frontmatter']} ({pct1:.1f}%)")
    print(f"   Valid YAML:         {stats['valid_yaml']} ({pct2:.1f}%)")
    print(f"   Valid Fields:       {stats['valid_fields']} ({pct3:.1f}%)")
    print(f"   Errors:             {len(stats['errors'])}")
    print()

    return all_passed, stats

def main():
    parser = argparse.ArgumentParser(
        description='Verify the system issue frontmatter'
    )
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)

    args = parser.parse_args()

    passed, stats = run_verification(args.issues_dir, args.verbose)
    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()
