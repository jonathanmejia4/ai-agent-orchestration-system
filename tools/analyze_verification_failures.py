#!/usr/bin/env python3
"""
Verification Failure Analyzer

Scans verification evidence files and categorizes failures by type.
Provides actionable insights into why verifications are failing.

Usage:
    python3 tools/analyze_verification_failures.py           # Summary output
    python3 tools/analyze_verification_failures.py --verbose # Detailed output
    python3 tools/analyze_verification_failures.py --json    # JSON output
    python3 tools/analyze_verification_failures.py --lane G  # Specific lane

Failure Categories:
    MALFORMED_CMD     - Verification command is syntactically broken
    UNSUBSTITUTED_VAR - Placeholder not replaced (e.g., {source_file})
    DIRECTORY_AS_FILE - test -f on a directory (should use test -d)
    FILE_NOT_FOUND    - File genuinely doesn't exist
    CHECK_FAILED      - File exists but content check failed
    IMPORT_ERROR      - Python import/syntax error
    TIMEOUT           - Command timed out
    UNKNOWN           - Unclassified failure
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Optional

# Configuration
EVIDENCE_DIR = "LogBook/verification/evidence"
LANES = ['A', 'D', 'E', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']

# Failure type definitions
FAILURE_TYPES = {
    'MALFORMED_CMD': 'Verification command is syntactically broken',
    'UNSUBSTITUTED_VAR': 'Placeholder not replaced (e.g., {source_file})',
    'DIRECTORY_AS_FILE': 'test -f used on directory (should use test -d)',
    'FILE_NOT_FOUND': 'File genuinely does not exist',
    'CHECK_FAILED': 'File exists but content check failed',
    'IMPORT_ERROR': 'Python import or syntax error',
    'TIMEOUT': 'Command timed out',
    'UNKNOWN': 'Unclassified failure',
}

def classify_failure(check: dict, all_checks: list = None) -> tuple:
    """
    Classify a failed check into a failure type.

    Args:
        check: The failed check to classify
        all_checks: All checks from the evidence file (for context)

    Returns: (failure_type, reason, suggested_fix)
    """
    command = check.get('command', '')
    output = check.get('output', '')
    error = check.get('error', '')

    # Build context from all checks
    all_outputs = ''
    if all_checks:
        all_outputs = ' '.join(c.get('output', '') for c in all_checks)

    # Malformed command patterns
    malformed_patterns = [
        # test -f with shell command as argument (e.g., test -f ls LogBook/)
        (r'test -[fs] (ls|cat|grep|find|echo)\s',
         'Shell command passed to test -f',
         'Remove test -f wrapper or fix command'),

        # Binary operator expected (multiple args to test)
        (r'binary operator expected',
         'Multiple arguments to test command',
         'Use proper test syntax or escape arguments'),

        # Wildcards in test -f (test -f *.md)
        (r'test -[fs] [^\s]*\*',
         'Wildcards in test -f (not expanded)',
         'Use ls or find for wildcard patterns'),

        # Pipe (not || or &&) in wrong place
        (r'test -[fs][^|]*\|(?!\|)',
         'Pipe in test command',
         'Use subshell: test -f "$(command)"'),
    ]

    for pattern, reason, fix in malformed_patterns:
        if re.search(pattern, command) or re.search(pattern, output):
            return ('MALFORMED_CMD', reason, fix)

    # Unsubstituted variable patterns
    var_patterns = [
        (r'\{source_file\}', '{source_file} not substituted', 'Substitute source file path'),
        (r'\{file_path\}', '{file_path} not substituted', 'Substitute file path'),
        (r'\{target\}', '{target} not substituted', 'Substitute target path'),
        (r'<task-id>', '<task-id> not substituted', 'Substitute task ID'),
        (r'<[a-z-]+>', 'Placeholder not substituted', 'Substitute placeholder value'),
    ]

    for pattern, reason, fix in var_patterns:
        if re.search(pattern, command):
            return ('UNSUBSTITUTED_VAR', reason, fix)

    # Directory treated as file
    # Check both the current check output AND all outputs for .gitkeep indication
    if 'test -f' in command:
        if '.gitkeep' in output or '.gitkeep' in all_outputs:
            return ('DIRECTORY_AS_FILE',
                    'Path is a directory (contains .gitkeep)',
                    'Use test -d for directories')
        # Also check for paths that look like directories (no file extension)
        path_match = re.search(r'test -f\s+([^\s&|]+)', command)
        if path_match:
            path = path_match.group(1)
            # If path has no extension and doesn't end with .md/.py/.json etc
            if '.' not in os.path.basename(path) and 'FAIL' in output:
                return ('DIRECTORY_AS_FILE',
                        'Path appears to be a directory (no file extension)',
                        'Use test -d for directories or add file extension')

    if 'is a directory' in output.lower():
        return ('DIRECTORY_AS_FILE',
                'Path is a directory',
                'Use test -d for directories')

    # File not found (genuine missing file)
    not_found_patterns = [
        r'No such file or directory',
        r'pathspec .* did not match',
        r'cannot stat',
        r'FAIL\n$',  # Simple FAIL output with no other context
    ]

    for pattern in not_found_patterns:
        if re.search(pattern, output):
            # Check if this is really a missing file or a command issue
            if 'binary operator expected' not in output:
                return ('FILE_NOT_FOUND',
                        'Target file does not exist',
                        'Check if fix was implemented correctly')

    # Import/syntax errors
    if 'ImportError' in output or 'SyntaxError' in output or 'ModuleNotFoundError' in output:
        return ('IMPORT_ERROR',
                'Python import or syntax error',
                'Fix Python code or install dependencies')

    # Content check failures
    if check.get('name', '') in ['content_check', 'contains_text', 'grep_check']:
        return ('CHECK_FAILED',
                'Content validation failed',
                'Verify expected content exists')

    # Timeout
    if 'timeout' in error.lower() or 'timed out' in output.lower():
        return ('TIMEOUT',
                'Command execution timed out',
                'Optimize command or increase timeout')

    # Generic check failed
    if error == 'Check failed' or 'FAIL' in output:
        # Try to provide more context
        if 'test -f' in command or 'test -e' in command:
            return ('FILE_NOT_FOUND',
                    'File existence check failed',
                    'Verify file path is correct')
        if 'test -s' in command:
            return ('CHECK_FAILED',
                    'File empty or does not exist',
                    'Verify file has content')
        if 'grep' in command:
            return ('CHECK_FAILED',
                    'Grep pattern not found',
                    'Verify content pattern is correct')

    return ('UNKNOWN', 'Unclassified failure', 'Manual review required')

def analyze_evidence_file(filepath: str) -> Optional[dict]:
    """
    Analyze a single evidence file and extract failure information.

    Returns dict with failure analysis or None if passed.
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    # Skip if all passed
    if data.get('all_passed', False):
        return None

    issue_id = data.get('issue_id', Path(filepath).stem.split('_')[0])
    lane = data.get('lane', issue_id[0] if issue_id else 'X')

    all_checks = data.get('checks', [])
    failures = []
    for check in all_checks:
        if not check.get('passed', True):
            failure_type, reason, fix = classify_failure(check, all_checks)
            failures.append({
                'check_name': check.get('name', 'unknown'),
                'command': check.get('command', ''),
                'output': check.get('output', '')[:200],  # Truncate
                'failure_type': failure_type,
                'reason': reason,
                'suggested_fix': fix,
            })

    if not failures:
        return None

    # Determine primary failure type (most severe)
    type_priority = ['MALFORMED_CMD', 'UNSUBSTITUTED_VAR', 'DIRECTORY_AS_FILE',
                     'FILE_NOT_FOUND', 'CHECK_FAILED', 'IMPORT_ERROR', 'TIMEOUT', 'UNKNOWN']

    primary_type = 'UNKNOWN'
    for ftype in type_priority:
        if any(f['failure_type'] == ftype for f in failures):
            primary_type = ftype
            break

    return {
        'issue_id': issue_id,
        'lane': lane,
        'timestamp': data.get('timestamp', ''),
        'primary_failure_type': primary_type,
        'failures': failures,
        'total_checks': data.get('total_checks', 0),
        'failed_checks': data.get('failed_checks', 0),
    }

def get_latest_evidence(lane_dir: str) -> dict:
    """
    Get the latest evidence file for each issue in a lane.
    Returns {issue_id: filepath}
    """
    evidence_files = {}

    for filepath in Path(lane_dir).glob('*.json'):
        # Parse issue ID from filename (e.g., A003_20251228_100459.json -> A003)
        parts = filepath.stem.split('_')
        if parts:
            issue_id = parts[0]
            # Keep the latest file (they're sorted by timestamp in filename)
            if issue_id not in evidence_files:
                evidence_files[issue_id] = str(filepath)
            else:
                # Compare timestamps
                existing_ts = evidence_files[issue_id].split('_')[1:]
                new_ts = str(filepath).split('_')[1:]
                if new_ts > existing_ts:
                    evidence_files[issue_id] = str(filepath)

    return evidence_files

def analyze_all_failures(lane_filter: Optional[str] = None, verbose: bool = False) -> dict:
    """
    Analyze all verification failures across all lanes.

    Returns comprehensive analysis dict.
    """
    results = {
        'summary': {
            'total_analyzed': 0,
            'total_passed': 0,
            'total_failed': 0,
            'by_failure_type': defaultdict(int),
        },
        'lanes': {},
        'failures': [],
        'patterns': defaultdict(list),  # Group by malformed command patterns
    }

    lanes_to_process = [lane_filter] if lane_filter else LANES

    for lane in lanes_to_process:
        lane_dir = os.path.join(EVIDENCE_DIR, lane)
        if not os.path.isdir(lane_dir):
            continue

        if verbose:
            print(f"Analyzing lane {lane}...")

        lane_stats = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'by_failure_type': defaultdict(int),
        }

        # Get latest evidence for each issue
        evidence_files = get_latest_evidence(lane_dir)

        for issue_id, filepath in sorted(evidence_files.items()):
            lane_stats['total'] += 1
            results['summary']['total_analyzed'] += 1

            analysis = analyze_evidence_file(filepath)

            if analysis is None:
                # Passed
                lane_stats['passed'] += 1
                results['summary']['total_passed'] += 1
            else:
                # Failed
                lane_stats['failed'] += 1
                results['summary']['total_failed'] += 1

                ftype = analysis['primary_failure_type']
                lane_stats['by_failure_type'][ftype] += 1
                results['summary']['by_failure_type'][ftype] += 1

                results['failures'].append(analysis)

                # Track malformed command patterns
                for failure in analysis['failures']:
                    if failure['failure_type'] == 'MALFORMED_CMD':
                        cmd = failure['command']
                        # Normalize command for pattern matching
                        if 'test -f ls' in cmd or 'test -s ls' in cmd:
                            pattern = 'test -f/s with ls command'
                        elif re.search(r'test -[fs] [^\s]*\*', cmd):
                            pattern = 'test -f/s with wildcards'
                        elif 'binary operator expected' in failure['output']:
                            pattern = 'Multiple args to test'
                        else:
                            pattern = 'Other malformed'
                        results['patterns'][pattern].append(issue_id)

        results['lanes'][lane] = dict(lane_stats)
        results['lanes'][lane]['by_failure_type'] = dict(lane_stats['by_failure_type'])

    # Convert defaultdicts to regular dicts for JSON serialization
    results['summary']['by_failure_type'] = dict(results['summary']['by_failure_type'])
    results['patterns'] = dict(results['patterns'])

    return results

def format_summary(results: dict) -> str:
    """Format analysis results as human-readable summary."""
    lines = []
    lines.append("=" * 60)
    lines.append("VERIFICATION FAILURE ANALYSIS")
    lines.append("=" * 60)
    lines.append("")

    summary = results['summary']
    lines.append(f"Total Issues Analyzed: {summary['total_analyzed']}")
    lines.append(f"  Passed: {summary['total_passed']}")
    lines.append(f"  Failed: {summary['total_failed']}")
    lines.append("")

    # Failure type breakdown
    lines.append("Failures by Type:")
    lines.append("-" * 40)

    type_counts = summary['by_failure_type']
    for ftype in ['MALFORMED_CMD', 'UNSUBSTITUTED_VAR', 'DIRECTORY_AS_FILE',
                  'FILE_NOT_FOUND', 'CHECK_FAILED', 'IMPORT_ERROR', 'TIMEOUT', 'UNKNOWN']:
        count = type_counts.get(ftype, 0)
        if count > 0:
            desc = FAILURE_TYPES.get(ftype, '')
            pct = round(100 * count / summary['total_failed']) if summary['total_failed'] else 0
            lines.append(f"  {ftype:20} {count:4} ({pct:2}%)  - {desc}")

    lines.append("")

    # Lane breakdown
    lines.append("Failures by Lane:")
    lines.append("-" * 40)
    lines.append(f"{'Lane':<6} {'Total':<7} {'Passed':<8} {'Failed':<8} {'Primary Type'}")
    lines.append("-" * 60)

    for lane in LANES:
        if lane not in results['lanes']:
            continue
        lane_data = results['lanes'][lane]
        if lane_data['failed'] == 0:
            continue

        # Get primary failure type for lane
        by_type = lane_data['by_failure_type']
        primary = max(by_type, key=by_type.get) if by_type else '-'

        lines.append(f"{lane:<6} {lane_data['total']:<7} {lane_data['passed']:<8} {lane_data['failed']:<8} {primary}")

    lines.append("")

    # Malformed command patterns
    if results['patterns']:
        lines.append("Malformed Command Patterns:")
        lines.append("-" * 40)
        for pattern, issues in sorted(results['patterns'].items(), key=lambda x: -len(x[1])):
            lines.append(f"  {pattern}: {len(issues)} issues")
            # Show first 5 examples
            examples = issues[:5]
            lines.append(f"    Examples: {', '.join(examples)}")
        lines.append("")

    # Top 10 failed issues with details
    lines.append("Sample Failed Issues (first 10):")
    lines.append("-" * 40)

    for failure in results['failures'][:10]:
        issue_id = failure['issue_id']
        ftype = failure['primary_failure_type']
        reason = failure['failures'][0]['reason'] if failure['failures'] else 'Unknown'
        lines.append(f"  {issue_id}: {ftype} - {reason}")

    lines.append("")
    lines.append("=" * 60)

    return '\n'.join(lines)

def generate_catalog_section(results: dict) -> str:
    """
    Generate markdown section for ISSUE_CATALOG.md.
    """
    summary = results['summary']
    total_failed = summary['total_failed']

    lines = []
    lines.append("### Failure Analysis")
    lines.append("")
    lines.append("> Breakdown of verification failures by type. See `tools/analyze_verification_failures.py` for details.")
    lines.append("")
    lines.append("| Failure Type | Count | % of Failures | Action Needed |")
    lines.append("|--------------|-------|---------------|---------------|")

    type_actions = {
        'MALFORMED_CMD': 'Fix verification commands',
        'UNSUBSTITUTED_VAR': 'Substitute placeholder values',
        'DIRECTORY_AS_FILE': 'Use test -d for directories',
        'FILE_NOT_FOUND': 'Verify fix was implemented',
        'CHECK_FAILED': 'Review implementation',
        'IMPORT_ERROR': 'Fix Python code/deps',
        'TIMEOUT': 'Optimize command',
        'UNKNOWN': 'Manual review',
    }

    type_counts = summary['by_failure_type']
    for ftype in ['MALFORMED_CMD', 'UNSUBSTITUTED_VAR', 'DIRECTORY_AS_FILE',
                  'FILE_NOT_FOUND', 'CHECK_FAILED', 'IMPORT_ERROR', 'TIMEOUT', 'UNKNOWN']:
        count = type_counts.get(ftype, 0)
        if count > 0:
            pct = round(100 * count / total_failed) if total_failed else 0
            action = type_actions.get(ftype, 'Review')
            lines.append(f"| {ftype} | {count} | {pct}% | {action} |")

    lines.append("")

    # Malformed patterns section
    if results['patterns']:
        lines.append("#### Malformed Command Patterns")
        lines.append("")
        lines.append("| Pattern | Count | Example Issue | Fix |")
        lines.append("|---------|-------|---------------|-----|")

        pattern_fixes = {
            'test -f/s with ls command': 'Remove test wrapper',
            'test -f/s with wildcards': 'Use ls *.md instead',
            'Multiple args to test': 'Quote or escape args',
            'Other malformed': 'Review command syntax',
        }

        for pattern, issues in sorted(results['patterns'].items(), key=lambda x: -len(x[1])):
            fix = pattern_fixes.get(pattern, 'Review')
            example = issues[0] if issues else '-'
            lines.append(f"| {pattern} | {len(issues)} | {example} | {fix} |")

        lines.append("")

    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze verification failures and categorize by type"
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Show detailed output during analysis")
    parser.add_argument('--json', action='store_true',
                        help="Output as JSON")
    parser.add_argument('--lane', type=str,
                        help="Analyze specific lane only")
    parser.add_argument('--catalog', action='store_true',
                        help="Output markdown section for catalog")
    args = parser.parse_args()

    # Run analysis
    results = analyze_all_failures(lane_filter=args.lane, verbose=args.verbose)

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    elif args.catalog:
        print(generate_catalog_section(results))
    else:
        print(format_summary(results))

    return 0

if __name__ == "__main__":
    sys.exit(main())
