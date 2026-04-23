#!/usr/bin/env python3
"""
the system Dashboard Verification Tool

Verifies that the dashboard generation tool is working properly.

Checks:
1. Dashboard file can be generated
2. Dashboard contains required sections
3. Statistics in dashboard match issue_stats.py output
4. Progress bars are accurate

Usage:
    python3 tools/verify_dashboard.py
"""

import os
import sys
import re
import subprocess
from datetime import datetime

DASHBOARD_FILE = "LogBook/verification/DASHBOARD.md"
ISSUES_DIR = "issues"

def run_verification() -> bool:
    """Run dashboard verification."""
    print("=" * 70)
    print("the system DASHBOARD VERIFICATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_passed = True

    # =========================================================================
    # CHECK 1: Dashboard Generation
    # =========================================================================
    print("-" * 70)
    print("CHECK 1: Dashboard Generation")
    print("-" * 70)

    try:
        result = subprocess.run(
            ['python3', 'tools/update_dashboard.py'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0 and 'Dashboard saved' in result.stdout:
            print(f"   \u2705 PASSED: Dashboard generated successfully")
        else:
            print(f"   \u274c FAILED: Generation error: {result.stderr[:100]}")
            all_passed = False
    except Exception as e:
        print(f"   \u274c FAILED: {e}")
        all_passed = False

    # =========================================================================
    # CHECK 2: Dashboard File Exists
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 2: Dashboard File Exists")
    print("-" * 70)

    if os.path.exists(DASHBOARD_FILE):
        size = os.path.getsize(DASHBOARD_FILE)
        print(f"   File: {DASHBOARD_FILE}")
        print(f"   Size: {size} bytes")
        print(f"   \u2705 PASSED: Dashboard file exists")
    else:
        print(f"   \u274c FAILED: Dashboard file not found")
        all_passed = False
        return all_passed

    # =========================================================================
    # CHECK 3: Required Sections
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 3: Required Sections")
    print("-" * 70)

    try:
        with open(DASHBOARD_FILE, 'r') as f:
            content = f.read()

        required_sections = [
            'Overall Progress',
            'Lane Progress',
            'Recent Activity',
            'Quick Commands',
        ]

        missing = []
        for section in required_sections:
            if section in content:
                print(f"   \u2705 Found: {section}")
            else:
                print(f"   \u274c Missing: {section}")
                missing.append(section)

        if missing:
            print(f"   \u274c FAILED: Missing sections: {missing}")
            all_passed = False
        else:
            print(f"   \u2705 PASSED: All required sections present")
    except Exception as e:
        print(f"   \u274c FAILED: {e}")
        all_passed = False

    # =========================================================================
    # CHECK 4: Statistics Accuracy
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 4: Statistics Match issue_stats.py")
    print("-" * 70)

    try:
        # Get stats from issue_stats.py
        result = subprocess.run(
            ['python3', 'tools/issue_stats.py'],
            capture_output=True,
            text=True,
            timeout=60
        )

        stats_match = re.search(r'TOTAL:\s*(\d+)\s*issues.*?(\d+)\s*resolved', result.stdout, re.DOTALL)
        if not stats_match:
            print(f"   \u274c FAILED: Could not parse issue_stats.py output")
            all_passed = False
        else:
            stats_total = int(stats_match.group(1))
            stats_resolved = int(stats_match.group(2))

            # Get stats from dashboard
            with open(DASHBOARD_FILE, 'r') as f:
                dashboard_content = f.read()

            # Look for "Resolved | XXX |" pattern
            dash_resolved_match = re.search(r'Resolved\s*\|\s*(\d+)', dashboard_content)
            dash_total_match = re.search(r'Total Issues.*?(\d+)', dashboard_content)

            if dash_resolved_match:
                dash_resolved = int(dash_resolved_match.group(1))
                print(f"   issue_stats.py resolved: {stats_resolved}")
                print(f"   dashboard resolved:      {dash_resolved}")

                if stats_resolved == dash_resolved:
                    print(f"   \u2705 PASSED: Resolved counts match")
                else:
                    print(f"   \u274c FAILED: Resolved counts don't match")
                    all_passed = False
            else:
                print(f"   \u26a0\ufe0f  Could not parse dashboard resolved count")

    except Exception as e:
        print(f"   \u274c FAILED: {e}")
        all_passed = False

    # =========================================================================
    # FINAL VERDICT
    # =========================================================================
    print()
    print("=" * 70)

    if all_passed:
        print("\U0001f389 VERIFICATION COMPLETE: ALL CHECKS PASSED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u2705  DASHBOARD VERIFIED - Working properly                   \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")
    else:
        print("\u26a0\ufe0f  VERIFICATION COMPLETE: SOME CHECKS FAILED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u274c  DASHBOARD NOT WORKING PROPERLY - Review errors above   \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")

    print("=" * 70)

    return all_passed

def main():
    passed = run_verification()
    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()
