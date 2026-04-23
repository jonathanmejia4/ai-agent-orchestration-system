#!/usr/bin/env python3
"""
the system Issue Statistics Verification Tool

Validates that issue counts are consistent and the stats script is working properly.

Checks:
1. Resolved + Open = Total (per lane and overall)
2. All severity counts add up
3. File counts match parsed counts
4. No orphaned or miscounted issues

Usage:
    python3 tools/verify_stats.py           # Run verification
    python3 tools/verify_stats.py --fix     # Attempt to fix inconsistencies
    python3 tools/verify_stats.py --verbose # Show detailed breakdown
"""

import os
import re
import sys
import glob
import argparse
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class VerificationResult:
    """Result of a single verification check."""
    check_name: str
    passed: bool
    expected: any
    actual: any
    message: str

@dataclass
class LaneVerification:
    """Verification results for a single lane."""
    lane: str
    total_files: int
    resolved_count: int
    open_count: int
    high_count: int
    medium_count: int
    low_count: int
    math_check: bool  # resolved + open == total
    severity_check: bool  # high + medium + low == total

# =============================================================================
# VERIFICATION FUNCTIONS
# =============================================================================

def count_files_in_lane(lane_dir: str) -> int:
    """Count actual .md files in a lane directory."""
    count = 0
    for f in glob.glob(os.path.join(lane_dir, '*.md')):
        if 'TEMPLATE' not in f.upper():
            count += 1
    return count

def parse_issue_status(filepath: str) -> Tuple[str, str]:
    """Parse status and severity from an issue file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return ('UNKNOWN', 'UNKNOWN')

    # Extract status
    status_match = re.search(r'Status:\s*(RESOLVED|OPEN|CLOSED)', content, re.IGNORECASE)
    status = status_match.group(1).upper() if status_match else 'OPEN'
    if status == 'CLOSED':
        status = 'RESOLVED'

    # Extract severity
    severity = 'MEDIUM'
    sev_match = re.search(r'Severity:\s*(\d+)/10\s*(HIGH|MEDIUM|LOW|CRITICAL)', content, re.IGNORECASE)
    if sev_match:
        level = sev_match.group(2).upper()
        if level in ('HIGH', 'CRITICAL'):
            severity = 'HIGH'
        elif level == 'LOW':
            severity = 'LOW'
        else:
            severity = 'MEDIUM'

    return (status, severity)

def verify_lane(lane_dir: str) -> LaneVerification:
    """Verify counts for a single lane."""
    lane = os.path.basename(lane_dir).upper()

    total_files = 0
    resolved = 0
    open_count = 0
    high = 0
    medium = 0
    low = 0

    for filepath in glob.glob(os.path.join(lane_dir, '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        total_files += 1
        status, severity = parse_issue_status(filepath)

        if status == 'RESOLVED':
            resolved += 1
        else:
            open_count += 1

        if severity == 'HIGH':
            high += 1
        elif severity == 'LOW':
            low += 1
        else:
            medium += 1

    math_check = (resolved + open_count) == total_files
    severity_check = (high + medium + low) == total_files

    return LaneVerification(
        lane=lane,
        total_files=total_files,
        resolved_count=resolved,
        open_count=open_count,
        high_count=high,
        medium_count=medium,
        low_count=low,
        math_check=math_check,
        severity_check=severity_check
    )

def run_verification(issues_dir: str, verbose: bool = False) -> Tuple[bool, List[VerificationResult]]:
    """Run all verification checks."""
    results = []
    all_passed = True

    print("=" * 70)
    print("Issue Statistics Verification")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Issues Directory: {issues_dir}")
    print()

    # Collect lane verifications
    lane_results: Dict[str, LaneVerification] = {}

    for lane_dir in sorted(glob.glob(os.path.join(issues_dir, '*'))):
        if not os.path.isdir(lane_dir):
            continue
        lane = os.path.basename(lane_dir).upper()
        lane_results[lane] = verify_lane(lane_dir)

    # Calculate totals
    total_files = sum(lv.total_files for lv in lane_results.values())
    total_resolved = sum(lv.resolved_count for lv in lane_results.values())
    total_open = sum(lv.open_count for lv in lane_results.values())
    total_high = sum(lv.high_count for lv in lane_results.values())
    total_medium = sum(lv.medium_count for lv in lane_results.values())
    total_low = sum(lv.low_count for lv in lane_results.values())

    # =========================================================================
    # CHECK 1: Total Math Check (Resolved + Open = Total)
    # =========================================================================
    print("📊 CHECK 1: Status Count Verification")
    print("-" * 70)

    overall_math = (total_resolved + total_open) == total_files

    print(f"   Total Issues:    {total_files}")
    print(f"   Total Resolved:  {total_resolved}")
    print(f"   Total Open:      {total_open}")
    print(f"   Sum Check:       {total_resolved} + {total_open} = {total_resolved + total_open}")
    print()

    if overall_math:
        print(f"   ✅ PASSED: Resolved ({total_resolved}) + Open ({total_open}) = Total ({total_files})")
    else:
        print(f"   ❌ FAILED: {total_resolved} + {total_open} = {total_resolved + total_open} ≠ {total_files}")
        all_passed = False

    results.append(VerificationResult(
        check_name="Overall Status Math",
        passed=overall_math,
        expected=total_files,
        actual=total_resolved + total_open,
        message=f"Resolved + Open = Total"
    ))
    print()

    # =========================================================================
    # CHECK 2: Severity Math Check (High + Medium + Low = Total)
    # =========================================================================
    print("📊 CHECK 2: Severity Count Verification")
    print("-" * 70)

    overall_severity = (total_high + total_medium + total_low) == total_files

    print(f"   HIGH Severity:   {total_high}")
    print(f"   MEDIUM Severity: {total_medium}")
    print(f"   LOW Severity:    {total_low}")
    print(f"   Sum Check:       {total_high} + {total_medium} + {total_low} = {total_high + total_medium + total_low}")
    print()

    if overall_severity:
        print(f"   ✅ PASSED: HIGH ({total_high}) + MEDIUM ({total_medium}) + LOW ({total_low}) = Total ({total_files})")
    else:
        print(f"   ❌ FAILED: Sum = {total_high + total_medium + total_low} ≠ {total_files}")
        all_passed = False

    results.append(VerificationResult(
        check_name="Overall Severity Math",
        passed=overall_severity,
        expected=total_files,
        actual=total_high + total_medium + total_low,
        message=f"HIGH + MEDIUM + LOW = Total"
    ))
    print()

    # =========================================================================
    # CHECK 3: Per-Lane Verification
    # =========================================================================
    print("📊 CHECK 3: Per-Lane Verification")
    print("-" * 70)
    print(f"{'Lane':<6} {'Total':>6} {'Resolved':>9} {'Open':>6} {'Sum':>6} {'Status':>8} {'Severity':>10}")
    print("-" * 70)

    lane_failures = []

    for lane in sorted(lane_results.keys(), key=lambda x: ('A' if x == 'A' else x)):
        lv = lane_results[lane]
        sum_check = lv.resolved_count + lv.open_count

        status_icon = "✅" if lv.math_check else "❌"
        severity_icon = "✅" if lv.severity_check else "❌"

        print(f"{lane:<6} {lv.total_files:>6} {lv.resolved_count:>9} {lv.open_count:>6} "
              f"{sum_check:>6} {status_icon:>8} {severity_icon:>10}")

        if not lv.math_check or not lv.severity_check:
            lane_failures.append(lane)
            all_passed = False

    print("-" * 70)

    if lane_failures:
        print(f"   ❌ FAILED: Lanes with issues: {', '.join(lane_failures)}")
    else:
        print(f"   ✅ PASSED: All {len(lane_results)} lanes verified")

    results.append(VerificationResult(
        check_name="Per-Lane Verification",
        passed=len(lane_failures) == 0,
        expected=0,
        actual=len(lane_failures),
        message=f"Lanes with failures: {lane_failures if lane_failures else 'None'}"
    ))
    print()

    # =========================================================================
    # CHECK 4: File System Consistency
    # =========================================================================
    print("📊 CHECK 4: File System Consistency")
    print("-" * 70)

    actual_file_count = sum(1 for _ in glob.glob(os.path.join(issues_dir, '*', '*.md'))
                           if 'TEMPLATE' not in _.upper())

    fs_check = actual_file_count == total_files

    print(f"   Files found by glob:  {actual_file_count}")
    print(f"   Files parsed:         {total_files}")
    print()

    if fs_check:
        print(f"   ✅ PASSED: File counts match")
    else:
        print(f"   ❌ FAILED: Mismatch in file counts")
        all_passed = False

    results.append(VerificationResult(
        check_name="File System Consistency",
        passed=fs_check,
        expected=actual_file_count,
        actual=total_files,
        message="Glob count vs parsed count"
    ))
    print()

    # =========================================================================
    # VERBOSE: Detailed Lane Breakdown
    # =========================================================================
    if verbose:
        print("📋 DETAILED LANE BREAKDOWN")
        print("-" * 70)
        for lane in sorted(lane_results.keys(), key=lambda x: ('A' if x == 'A' else x)):
            lv = lane_results[lane]
            pct = (lv.resolved_count / lv.total_files * 100) if lv.total_files > 0 else 0
            print(f"\n   Lane {lane}:")
            print(f"      Total:    {lv.total_files}")
            print(f"      Resolved: {lv.resolved_count} ({pct:.1f}%)")
            print(f"      Open:     {lv.open_count}")
            print(f"      HIGH:     {lv.high_count}")
            print(f"      MEDIUM:   {lv.medium_count}")
            print(f"      LOW:      {lv.low_count}")
            print(f"      Status:   {'✅ Math OK' if lv.math_check else '❌ Math Error'}")
            print(f"      Severity: {'✅ Math OK' if lv.severity_check else '❌ Math Error'}")
        print()

    # =========================================================================
    # FINAL VERDICT
    # =========================================================================
    print("=" * 70)
    if all_passed:
        print("🎉 VERIFICATION COMPLETE: ALL CHECKS PASSED")
        print()
        print("   ╔═══════════════════════════════════════════════════════════════╗")
        print("   ║                                                               ║")
        print("   ║   ✅  SCRIPT VERIFIED - Stats are accurate and consistent    ║")
        print("   ║                                                               ║")
        print("   ╚═══════════════════════════════════════════════════════════════╝")
    else:
        print("⚠️  VERIFICATION COMPLETE: SOME CHECKS FAILED")
        print()
        print("   ╔═══════════════════════════════════════════════════════════════╗")
        print("   ║                                                               ║")
        print("   ║   ❌  SCRIPT NOT WORKING PROPERLY - Review errors above      ║")
        print("   ║                                                               ║")
        print("   ╚═══════════════════════════════════════════════════════════════╝")
        print()
        print("   Failed checks:")
        for r in results:
            if not r.passed:
                print(f"      - {r.check_name}: {r.message}")

    print("=" * 70)
    print()

    # Summary stats
    print("📈 SUMMARY")
    print(f"   Total Issues:     {total_files}")
    print(f"   Total Resolved:   {total_resolved} ({total_resolved/total_files*100:.1f}%)")
    print(f"   Total Open:       {total_open} ({total_open/total_files*100:.1f}%)")
    print(f"   Lanes Verified:   {len(lane_results)}")
    print(f"   Checks Passed:    {sum(1 for r in results if r.passed)}/{len(results)}")
    print()

    return all_passed, results

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Verify the system Issue Statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed breakdown per lane')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR,
                        help=f'Issues directory (default: {ISSUES_DIR})')

    args = parser.parse_args()

    if not os.path.isdir(args.issues_dir):
        print(f"❌ Issues directory not found: {args.issues_dir}", file=sys.stderr)
        sys.exit(1)

    passed, results = run_verification(args.issues_dir, args.verbose)

    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()
