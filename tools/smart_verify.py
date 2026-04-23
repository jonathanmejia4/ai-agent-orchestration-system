#!/usr/bin/env python3
"""
Smart verification that understands the difference between:
1. Primary affected paths (files that should be created)
2. Reference paths (documentation/guidelines mentioning the issue)

Strategy:
- For RESOLVED issues, we check the PRIMARY fix target
- Primary target is typically the FIRST affected_path OR the one mentioned in the resolution
"""

import os
import re
import yaml
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent  # project-arrow root
ISSUES_DIR = BASE_DIR / "issues"

def parse_issue_file(filepath):
    """Parse issue file and extract metadata."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Extract YAML frontmatter
    frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
    if frontmatter_match:
        try:
            metadata = yaml.safe_load(frontmatter_match.group(1))
            return metadata, content
        except:
            pass

    return {}, content

def identify_primary_target(metadata, content):
    """
    Identify the primary fix target from affected_paths.

    Strategy:
    1. Look for resolution notes that mention specific files
    2. Prefer paths in PLANNING/, LogBook/, templates/, .github/workflows/
    3. Avoid paths in .claude/ (usually references, not created files)
    4. Take first path if ambiguous
    """
    affected_paths = metadata.get('affected_paths', [])
    if not affected_paths:
        return None

    # Extract resolution notes
    resolution_match = re.search(r'Resolution:(.+?)(?:\n\*\*|$)', content, re.DOTALL | re.IGNORECASE)
    resolution_text = resolution_match.group(1) if resolution_match else ""

    # Check if resolution explicitly mentions a file
    for path in affected_paths:
        path_filename = Path(path).name
        if path_filename and path_filename in resolution_text:
            return path

    # Prefer creation targets over reference targets
    creation_priority = ['PLANNING/', 'LogBook/', 'templates/', '.github/workflows/', 'tools/', 'tasks/']
    reference_paths = ['.claude/', 'docs/', 'README']

    # First pass: Find highest priority creation paths
    for prefix in creation_priority:
        for path in affected_paths:
            if path.startswith(prefix):
                return path

    # Second pass: Avoid reference-only paths
    non_reference_paths = [p for p in affected_paths if not any(p.startswith(ref) for ref in reference_paths)]
    if non_reference_paths:
        return non_reference_paths[0]

    # Default: first path
    return affected_paths[0]

def check_file_exists(filepath):
    """Check if a file exists relative to BASE_DIR."""
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

    # Check if RESOLVED
    status = metadata.get('status', '').upper()
    if status != 'RESOLVED':
        return {
            'issue_id': issue_id,
            'status': 'SKIP',
            'reason': f'Not RESOLVED (status={status})'
        }

    # Identify primary target
    primary_target = identify_primary_target(metadata, content)

    if not primary_target:
        return {
            'issue_id': issue_id,
            'status': 'FAIL',
            'category': 'infrastructure',
            'reason': 'No affected_paths specified'
        }

    # Check if primary target exists
    exists = check_file_exists(primary_target)

    if not exists:
        return {
            'issue_id': issue_id,
            'status': 'FAIL',
            'category': 'genuine',
            'reason': f'Primary target missing: {primary_target}',
            'primary_target': primary_target
        }

    return {
        'issue_id': issue_id,
        'status': 'PASS',
        'reason': f'Primary target exists: {primary_target}',
        'primary_target': primary_target
    }

def verify_all_lanes():
    """Verify all RESOLVED issues."""
    results = defaultdict(list)
    stats = defaultdict(lambda: defaultdict(int))

    lanes = sorted([d.name for d in ISSUES_DIR.iterdir() if d.is_dir()])

    print("SMART VERIFICATION - Checking primary fix targets only")
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
    """Generate report."""
    print(f"\n{'=' * 80}")
    print("SMART VERIFICATION REPORT")
    print("=" * 80)

    total_verified = stats['TOTAL']['PASS'] + stats['TOTAL']['FAIL']
    genuine_failures = stats['TOTAL'].get('genuine_fail', 0)
    infra_failures = stats['TOTAL'].get('infrastructure_fail', 0)

    print(f"\nOverall Statistics:")
    print(f"  Total RESOLVED Issues: {total_verified}")
    print(f"  PASSED: {stats['TOTAL']['PASS']}")
    print(f"  FAILED: {stats['TOTAL']['FAIL']}")
    print(f"    - Genuine failures (files missing): {genuine_failures}")
    print(f"    - Infrastructure issues: {infra_failures}")
    print(f"  SKIPPED (not RESOLVED): {stats['TOTAL']['SKIP']}")

    if total_verified > 0:
        pass_rate = stats['TOTAL']['PASS'] / total_verified * 100
        print(f"  Pass Rate: {pass_rate:.1f}%")

    # Lane breakdown
    print(f"\n{'Lane':<6} {'Total':<7} {'PASS':<7} {'FAIL':<7} {'Genuine':<9} {'Infra':<7} {'Pass %':<8}")
    print("-" * 70)

    for lane in sorted([k for k in stats.keys() if k != 'TOTAL']):
        lane_stats = stats[lane]
        verified = lane_stats['PASS'] + lane_stats['FAIL']
        if verified == 0:
            continue

        pass_rate = (lane_stats['PASS'] / verified * 100) if verified > 0 else 0

        print(f"{lane:<6} {verified:<7} {lane_stats['PASS']:<7} {lane_stats['FAIL']:<7} "
              f"{lane_stats.get('genuine_fail', 0):<9} {lane_stats.get('infrastructure_fail', 0):<7} {pass_rate:>6.1f}%")

    # Detailed failures
    print(f"\n{'=' * 80}")
    print("GENUINE FAILURES (files actually missing)")
    print("=" * 80)

    genuine_failures_list = []
    for lane in sorted(results.keys()):
        for result in results[lane]:
            if result['status'] == 'FAIL' and result.get('category') == 'genuine':
                genuine_failures_list.append(result)
                lane_name = result['issue_id'].split('-')[0]
                print(f"\n{result['issue_id']} ({lane_name})")
                print(f"  Missing: {result.get('primary_target', 'unknown')}")
                print(f"  Reason: {result['reason']}")

    print(f"\nTotal genuine failures: {len(genuine_failures_list)}")

    # Infrastructure issues
    print(f"\n{'=' * 80}")
    print("INFRASTRUCTURE ISSUES (missing affected_paths metadata)")
    print("=" * 80)

    infra_issues_list = []
    for lane in sorted(results.keys()):
        for result in results[lane]:
            if result['status'] == 'FAIL' and result.get('category') == 'infrastructure':
                infra_issues_list.append(result)

    # Group by lane
    by_lane = defaultdict(list)
    for result in infra_issues_list:
        lane_name = result['issue_id'].split('-')[0]
        by_lane[lane_name].append(result['issue_id'])

    for lane in sorted(by_lane.keys()):
        print(f"\n{lane}: {', '.join(sorted(by_lane[lane]))}")

    print(f"\nTotal infrastructure issues: {len(infra_issues_list)}")

    # Actionable summary
    print(f"\n{'=' * 80}")
    print("ACTIONABLE SUMMARY")
    print("=" * 80)
    print(f"\n1. GENUINE FAILURES TO FIX: {len(genuine_failures_list)}")
    print("   These issues are marked RESOLVED but the primary fix target file is missing.")
    print("   Action: Re-open these issues and apply the actual fix.\n")

    if genuine_failures_list:
        print("   Issue IDs:")
        for i, result in enumerate(sorted(genuine_failures_list, key=lambda x: x['issue_id']), 1):
            print(f"   {i:3d}. {result['issue_id']:<10} - {result.get('primary_target', 'unknown')}")

    print(f"\n2. INFRASTRUCTURE ISSUES TO FIX: {len(infra_issues_list)}")
    print("   These issues are missing affected_paths in their YAML frontmatter.")
    print("   Action: Add affected_paths to these issue files.\n")

if __name__ == "__main__":
    results, stats = verify_all_lanes()
    generate_report(results, stats)
