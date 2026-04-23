#!/usr/bin/env python3
"""
Comprehensive verification script for all RESOLVED issues.

This script:
1. Scans all lanes for RESOLVED issues
2. Checks affected_paths files actually exist
3. Categorizes failures as genuine vs false negatives
4. Generates detailed statistics
"""

import os
import re
import yaml
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Base directory
BASE_DIR = Path(__file__).parent.parent  # project-arrow root
ISSUES_DIR = BASE_DIR / "issues"

class VerificationResult:
    def __init__(self, issue_id, status, reason="", details=None):
        self.issue_id = issue_id
        self.status = status  # PASS, FAIL, or UNCERTAIN
        self.reason = reason
        self.details = details or {}

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

    # Fallback: parse markdown headers
    metadata = {}

    # Extract status
    status_match = re.search(r'Status:\s*(\w+)', content, re.IGNORECASE)
    if status_match:
        metadata['status'] = status_match.group(1)

    # Extract issue ID
    id_match = re.search(r'Issue ID:\s*([A-Z]-\d+)', content)
    if id_match:
        metadata['issue_id'] = id_match.group(1)

    # Extract affected paths
    paths_section = re.search(r'Affected Paths:?\s*\n((?:[-*]\s+`[^`]+`\s*\n?)+)', content, re.MULTILINE)
    if paths_section:
        paths = re.findall(r'`([^`]+)`', paths_section.group(1))
        metadata['affected_paths'] = paths

    return metadata, content

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
        return VerificationResult(issue_id, "UNCERTAIN", f"Failed to parse: {e}")

    # Check if RESOLVED
    status = metadata.get('status', '').upper()
    if status != 'RESOLVED':
        return VerificationResult(issue_id, "SKIP", f"Status is {status}, not RESOLVED")

    # Check affected_paths
    affected_paths = metadata.get('affected_paths', [])
    if not affected_paths:
        # Try to extract from content
        paths_match = re.findall(r'(?:Affected Path|File Path|Path)s?:\s*(?:\n[-*]\s*)?`([^`]+)`', content)
        if paths_match:
            affected_paths = paths_match

    if not affected_paths:
        return VerificationResult(
            issue_id,
            "FAIL",
            "No affected_paths specified (infrastructure issue)",
            {"category": "false_negative", "reason": "missing_affected_paths"}
        )

    # Check if files exist
    missing_files = []
    existing_files = []

    for path in affected_paths:
        # Clean path
        path = path.strip().lstrip('./')

        if check_file_exists(path):
            existing_files.append(path)
        else:
            missing_files.append(path)

    if missing_files:
        return VerificationResult(
            issue_id,
            "FAIL",
            f"{len(missing_files)}/{len(affected_paths)} files missing",
            {
                "category": "genuine_failure",
                "missing_files": missing_files,
                "existing_files": existing_files
            }
        )

    # All files exist
    return VerificationResult(
        issue_id,
        "PASS",
        f"All {len(affected_paths)} files exist",
        {"affected_paths": affected_paths}
    )

def verify_all_lanes():
    """Verify all RESOLVED issues across all lanes."""
    results = defaultdict(list)
    stats = defaultdict(lambda: defaultdict(int))

    lanes = sorted([d.name for d in ISSUES_DIR.iterdir() if d.is_dir()])

    print(f"Starting comprehensive verification of {len(lanes)} lanes...")
    print("=" * 80)

    for lane in lanes:
        lane_dir = ISSUES_DIR / lane
        issue_files = sorted(lane_dir.glob("*.md"))

        print(f"\nLane {lane}: {len(issue_files)} issues")

        for issue_file in issue_files:
            result = verify_issue(issue_file)
            results[lane].append(result)

            stats[lane][result.status] += 1
            stats['TOTAL'][result.status] += 1

            if result.status == "FAIL":
                category = result.details.get('category', 'unknown')
                stats[lane][f"FAIL_{category}"] += 1
                stats['TOTAL'][f"FAIL_{category}"] += 1

        # Print lane summary
        lane_total = len(issue_files)
        lane_passed = stats[lane]['PASS']
        lane_failed = stats[lane]['FAIL']
        lane_skipped = stats[lane]['SKIP']

        if lane_total > 0:
            pass_rate = (lane_passed / (lane_passed + lane_failed) * 100) if (lane_passed + lane_failed) > 0 else 0
            print(f"  PASS: {lane_passed}, FAIL: {lane_failed}, SKIP: {lane_skipped} | Pass Rate: {pass_rate:.1f}%")

    return results, stats

def generate_report(results, stats):
    """Generate comprehensive report."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE VERIFICATION REPORT")
    print("=" * 80)

    # Overall statistics
    total_issues = stats['TOTAL']['PASS'] + stats['TOTAL']['FAIL'] + stats['TOTAL']['SKIP']
    total_verified = stats['TOTAL']['PASS'] + stats['TOTAL']['FAIL']

    print(f"\nOverall Statistics:")
    print(f"  Total Issues Scanned: {total_issues}")
    print(f"  RESOLVED Issues Verified: {total_verified}")
    print(f"  PASSED: {stats['TOTAL']['PASS']}")
    print(f"  FAILED: {stats['TOTAL']['FAIL']}")
    print(f"  SKIPPED: {stats['TOTAL']['SKIP']}")

    if total_verified > 0:
        pass_rate = stats['TOTAL']['PASS'] / total_verified * 100
        print(f"  Overall Pass Rate: {pass_rate:.1f}%")

    # Failure breakdown
    genuine_failures = stats['TOTAL'].get('FAIL_genuine_failure', 0)
    false_negatives = stats['TOTAL'].get('FAIL_false_negative', 0)

    print(f"\nFailure Breakdown:")
    print(f"  Genuine Failures (files actually missing): {genuine_failures}")
    print(f"  False Negatives (infrastructure issues): {false_negatives}")

    # Lane-by-lane breakdown
    print(f"\nLane-by-Lane Breakdown:")
    print(f"{'Lane':<6} {'Total':<7} {'PASS':<7} {'FAIL':<7} {'SKIP':<7} {'Pass %':<8}")
    print("-" * 50)

    for lane in sorted([k for k in stats.keys() if k != 'TOTAL']):
        lane_stats = stats[lane]
        total = lane_stats['PASS'] + lane_stats['FAIL'] + lane_stats['SKIP']
        verified = lane_stats['PASS'] + lane_stats['FAIL']
        pass_rate = (lane_stats['PASS'] / verified * 100) if verified > 0 else 0

        print(f"{lane:<6} {total:<7} {lane_stats['PASS']:<7} {lane_stats['FAIL']:<7} {lane_stats['SKIP']:<7} {pass_rate:>6.1f}%")

    # List genuine failures
    print(f"\nGenuine Failures (need actual fixes):")
    print("-" * 80)

    genuine_count = 0
    for lane in sorted(results.keys()):
        lane_failures = [r for r in results[lane] if r.status == "FAIL" and r.details.get('category') == 'genuine_failure']
        if lane_failures:
            print(f"\nLane {lane}:")
            for result in lane_failures:
                genuine_count += 1
                missing = result.details.get('missing_files', [])
                print(f"  {result.issue_id}: {len(missing)} file(s) missing")
                for path in missing[:3]:  # Show first 3
                    print(f"    - {path}")
                if len(missing) > 3:
                    print(f"    ... and {len(missing) - 3} more")

    print(f"\nTotal Genuine Failures: {genuine_count}")

    # List false negatives
    print(f"\nFalse Negatives (infrastructure issues):")
    print("-" * 80)

    false_neg_count = 0
    for lane in sorted(results.keys()):
        lane_false_negs = [r for r in results[lane] if r.status == "FAIL" and r.details.get('category') == 'false_negative']
        if lane_false_negs:
            print(f"\nLane {lane}:")
            for result in lane_false_negs:
                false_neg_count += 1
                print(f"  {result.issue_id}: {result.reason}")

    print(f"\nTotal False Negatives: {false_neg_count}")

    # Write JSON report
    report_path = BASE_DIR / "LogBook/verification/comprehensive_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_issues": total_issues,
            "total_verified": total_verified,
            "passed": stats['TOTAL']['PASS'],
            "failed": stats['TOTAL']['FAIL'],
            "skipped": stats['TOTAL']['SKIP'],
            "pass_rate": pass_rate if total_verified > 0 else 0,
            "genuine_failures": genuine_failures,
            "false_negatives": false_negatives
        },
        "lanes": {
            lane: {
                "total": stats[lane]['PASS'] + stats[lane]['FAIL'] + stats[lane]['SKIP'],
                "passed": stats[lane]['PASS'],
                "failed": stats[lane]['FAIL'],
                "skipped": stats[lane]['SKIP'],
                "genuine_failures": stats[lane].get('FAIL_genuine_failure', 0),
                "false_negatives": stats[lane].get('FAIL_false_negative', 0)
            }
            for lane in stats.keys() if lane != 'TOTAL'
        },
        "failures": {
            lane: [
                {
                    "issue_id": r.issue_id,
                    "category": r.details.get('category'),
                    "reason": r.reason,
                    "missing_files": r.details.get('missing_files', [])
                }
                for r in results[lane] if r.status == "FAIL"
            ]
            for lane in results.keys()
        }
    }

    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2)

    print(f"\n{'=' * 80}")
    print(f"Report saved to: {report_path}")
    print(f"{'=' * 80}\n")

if __name__ == "__main__":
    results, stats = verify_all_lanes()
    generate_report(results, stats)
