#!/usr/bin/env python3
"""
Final comprehensive verification with intelligent path filtering.

Filters out:
- Commands (python ..., ls ..., test ...)
- Wildcards (*.jinja2, <template>)
- Documentation-only references
- Invalid path patterns
"""

import os
import re
import yaml
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent  # project-arrow root
ISSUES_DIR = BASE_DIR / "issues"

def is_command_or_invalid(path):
    """Check if path is actually a command, wildcard, or invalid pattern."""
    # Commands
    if any(path.startswith(cmd) for cmd in ['python', 'pytest', 'ls', 'test', 'find', 'grep', 'wc', 'git', 'bash', 'cat', 'echo', 'mkdir', 'touch', 'cp', 'mv', 'rm', 'yamllint', 'markdown-link-check']):
        return True

    # Wildcards
    if '*' in path or '<' in path or '>' in path:
        return True

    # Invalid patterns
    if path.endswith(',') or path.startswith('/plans/,'):
        return True

    # Contains command output
    if ' - Source ' in path or 'for consistency' in path or path.startswith('(missing'):
        return True

    # Starts with response_schema: etc
    if ':' in path and not path.endswith('.yaml') and not path.endswith('.yml') and not path.endswith('.md'):
        return True

    # Directory patterns without specific files
    if path.endswith('/') and ('*' in path or '<' in path):
        return True

    return False

def parse_issue_file(filepath):
    """Parse issue file."""
    with open(filepath, 'r') as f:
        content = f.read()

    frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
    if frontmatter_match:
        try:
            metadata = yaml.safe_load(frontmatter_match.group(1))
            return metadata, content
        except:
            pass

    return {}, content

def identify_fix_targets(metadata, content):
    """
    Identify all legitimate fix targets from affected_paths.
    Returns list of valid file paths that should exist.
    """
    affected_paths = metadata.get('affected_paths', [])
    if not affected_paths:
        return []

    valid_targets = []

    for path in affected_paths:
        path = path.strip().lstrip('./')

        # Skip commands and invalid patterns
        if is_command_or_invalid(path):
            continue

        # Skip .claude/ references (usually documentation)
        if path.startswith('.claude/'):
            continue

        valid_targets.append(path)

    return valid_targets

def check_file_exists(filepath):
    """Check if file exists."""
    full_path = BASE_DIR / filepath
    return full_path.exists()

def verify_issue(issue_file):
    """Verify a single issue."""
    issue_id = issue_file.stem

    try:
        metadata, content = parse_issue_file(issue_file)
    except Exception as e:
        return {
            'issue_id': issue_id,
            'status': 'ERROR',
            'reason': f'Parse failed: {e}'
        }

    status = metadata.get('status', '').upper()
    if status != 'RESOLVED':
        return {
            'issue_id': issue_id,
            'status': 'SKIP',
            'reason': f'Not RESOLVED (status={status})'
        }

    # Get all valid fix targets
    fix_targets = identify_fix_targets(metadata, content)

    if not fix_targets:
        return {
            'issue_id': issue_id,
            'status': 'UNCERTAIN',
            'category': 'infrastructure',
            'reason': 'No valid affected_paths found (may be documentation-only fix)',
            'all_paths': metadata.get('affected_paths', [])
        }

    # Check which targets are missing
    missing = []
    existing = []

    for target in fix_targets:
        if check_file_exists(target):
            existing.append(target)
        else:
            missing.append(target)

    if missing:
        return {
            'issue_id': issue_id,
            'status': 'FAIL',
            'category': 'genuine',
            'reason': f'{len(missing)}/{len(fix_targets)} target(s) missing',
            'missing': missing,
            'existing': existing
        }

    return {
        'issue_id': issue_id,
        'status': 'PASS',
        'reason': f'All {len(fix_targets)} target(s) exist',
        'targets': existing
    }

def verify_all_lanes():
    """Verify all RESOLVED issues."""
    results = defaultdict(list)
    stats = defaultdict(lambda: defaultdict(int))

    lanes = sorted([d.name for d in ISSUES_DIR.iterdir() if d.is_dir()])

    print("FINAL COMPREHENSIVE VERIFICATION")
    print("Filtering out commands, wildcards, and doc-only references")
    print("=" * 80)

    for lane in lanes:
        lane_dir = ISSUES_DIR / lane
        issue_files = sorted(lane_dir.glob("*.md"))

        for issue_file in issue_files:
            result = verify_issue(issue_file)
            results[lane].append(result)

            stats[lane][result['status']] += 1
            stats['TOTAL'][result['status']] += 1

            if result['status'] == 'FAIL':
                category = result.get('category', 'unknown')
                stats[lane][f'{category}_fail'] += 1
                stats['TOTAL'][f'{category}_fail'] += 1

    return results, stats

def generate_report(results, stats):
    """Generate comprehensive report."""
    print(f"\n{'=' * 80}")
    print("FINAL VERIFICATION REPORT")
    print("=" * 80)

    total_verified = stats['TOTAL']['PASS'] + stats['TOTAL']['FAIL'] + stats['TOTAL']['UNCERTAIN']
    genuine_failures = stats['TOTAL'].get('genuine_fail', 0)

    print(f"\nOverall Statistics:")
    print(f"  Total RESOLVED Issues: {total_verified}")
    print(f"  PASSED: {stats['TOTAL']['PASS']} (all fix targets exist)")
    print(f"  FAILED: {stats['TOTAL']['FAIL']} (genuine failures)")
    print(f"  UNCERTAIN: {stats['TOTAL']['UNCERTAIN']} (doc-only or unclear)")
    print(f"  SKIPPED: {stats['TOTAL']['SKIP']} (not RESOLVED)")

    if stats['TOTAL']['PASS'] + stats['TOTAL']['FAIL'] > 0:
        pass_rate = stats['TOTAL']['PASS'] / (stats['TOTAL']['PASS'] + stats['TOTAL']['FAIL']) * 100
        print(f"  Pass Rate (excluding UNCERTAIN): {pass_rate:.1f}%")

    # Lane breakdown
    print(f"\n{'Lane':<6} {'Resolved':<9} {'PASS':<7} {'FAIL':<7} {'Uncertain':<10} {'Pass %':<8}")
    print("-" * 65)

    for lane in sorted([k for k in stats.keys() if k != 'TOTAL']):
        lane_stats = stats[lane]
        resolved = lane_stats['PASS'] + lane_stats['FAIL'] + lane_stats['UNCERTAIN']
        if resolved == 0:
            continue

        verifiable = lane_stats['PASS'] + lane_stats['FAIL']
        pass_rate = (lane_stats['PASS'] / verifiable * 100) if verifiable > 0 else 0

        print(f"{lane:<6} {resolved:<9} {lane_stats['PASS']:<7} {lane_stats['FAIL']:<7} "
              f"{lane_stats['UNCERTAIN']:<10} {pass_rate:>6.1f}%")

    # Detailed failures
    print(f"\n{'=' * 80}")
    print("GENUINE FAILURES - Issues marked RESOLVED but files still missing")
    print("=" * 80)

    failures_by_lane = defaultdict(list)
    for lane in sorted(results.keys()):
        for result in results[lane]:
            if result['status'] == 'FAIL' and result.get('category') == 'genuine':
                failures_by_lane[lane].append(result)

    total_missing_files = 0
    for lane in sorted(failures_by_lane.keys()):
        print(f"\nLane {lane}:")
        for result in failures_by_lane[lane]:
            missing = result.get('missing', [])
            existing = result.get('existing', [])
            total_missing_files += len(missing)

            print(f"  {result['issue_id']}:")
            print(f"    Missing ({len(missing)}): {', '.join(missing)}")
            if existing:
                print(f"    Existing ({len(existing)}): {', '.join(existing)}")

    print(f"\nTotal issues with genuine failures: {genuine_failures}")
    print(f"Total missing files: {total_missing_files}")

    # UNCERTAIN cases
    print(f"\n{'=' * 80}")
    print("UNCERTAIN CASES - May be doc-only fixes or need affected_paths metadata")
    print("=" * 80)

    uncertain_by_lane = defaultdict(list)
    for lane in sorted(results.keys()):
        for result in results[lane]:
            if result['status'] == 'UNCERTAIN':
                uncertain_by_lane[lane].append(result)

    for lane in sorted(uncertain_by_lane.keys()):
        print(f"\nLane {lane}: {', '.join([r['issue_id'] for r in uncertain_by_lane[lane]])}")

    print(f"\nTotal uncertain cases: {stats['TOTAL']['UNCERTAIN']}")

    # Write summary file
    summary_file = BASE_DIR / "LogBook/verification/VERIFICATION_SUMMARY.md"
    summary_file.parent.mkdir(parents=True, exist_ok=True)

    with open(summary_file, 'w') as f:
        f.write("# the system Issue Verification Summary\n\n")
        f.write(f"**Date:** {Path(__file__).stat().st_mtime}\n\n")
        f.write("## Overall Statistics\n\n")
        f.write(f"- Total RESOLVED Issues: {total_verified}\n")
        f.write(f"- PASSED: {stats['TOTAL']['PASS']}\n")
        f.write(f"- FAILED: {stats['TOTAL']['FAIL']}\n")
        f.write(f"- UNCERTAIN: {stats['TOTAL']['UNCERTAIN']}\n")
        f.write(f"- Pass Rate: {pass_rate:.1f}%\n\n")

        f.write("## Issues Requiring Fixes\n\n")
        for lane in sorted(failures_by_lane.keys()):
            for result in failures_by_lane[lane]:
                f.write(f"- **{result['issue_id']}**: {', '.join(result.get('missing', []))}\n")

    print(f"\n{'=' * 80}")
    print(f"Summary saved to: {summary_file}")
    print(f"{'=' * 80}\n")

if __name__ == "__main__":
    results, stats = verify_all_lanes()
    generate_report(results, stats)
