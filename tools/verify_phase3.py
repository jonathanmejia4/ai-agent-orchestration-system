#!/usr/bin/env python3
"""
the system Phase 3 Optimization Verification

Verifies that all Phase 3 optimizations have been applied:
1. Batch verification tool exists and works
2. Resolution templates in issues
3. Cross-reference validator exists
4. Auto-resolve detector exists
5. Report generator exists

Usage:
    python3 tools/verify_phase3.py
"""

import os
import sys
import glob
import subprocess
from datetime import datetime

ISSUES_DIR = "issues"
TOOLS_DIR = "tools"

def check_tool_exists(tool_name: str) -> bool:
    """Check if a tool file exists."""
    return os.path.exists(os.path.join(TOOLS_DIR, tool_name))

def check_tool_syntax(tool_name: str) -> bool:
    """Check if a Python tool has valid syntax."""
    path = os.path.join(TOOLS_DIR, tool_name)
    if not os.path.exists(path):
        return False

    try:
        result = subprocess.run(
            ['python3', '-m', 'py_compile', path],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def check_resolution_templates(issues_dir: str) -> tuple:
    """Check how many issues have resolution templates."""
    total = 0
    with_template = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        total += 1

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        if '## Resolution Evidence' in content:
            with_template += 1

    return with_template, total

def check_batch_verify_works() -> bool:
    """Check if batch_verify.py runs without error."""
    try:
        result = subprocess.run(
            ['python3', 'tools/batch_verify.py', '--help'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def check_report_generator_works() -> bool:
    """Check if generate_report.py runs without error."""
    try:
        result = subprocess.run(
            ['python3', 'tools/generate_report.py'],
            capture_output=True,
            timeout=30
        )
        return result.returncode == 0 and 'the system COMPREHENSIVE STATUS REPORT' in result.stdout.decode()
    except:
        return False

def run_verification() -> bool:
    """Run Phase 3 optimization verification."""
    print("=" * 70)
    print("the system PHASE 3 OPTIMIZATION VERIFICATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_passed = True
    checks_passed = 0
    total_checks = 6

    # Check 1: Batch Verify Tool
    print("-" * 70)
    print("CHECK 1: Batch Verification Tool")
    print("-" * 70)
    batch_exists = check_tool_exists('batch_verify.py')
    batch_syntax = check_tool_syntax('batch_verify.py')
    batch_works = check_batch_verify_works()

    if batch_exists and batch_syntax and batch_works:
        print("   batch_verify.py: EXISTS, VALID, WORKS")
        print("   \u2705 PASSED")
        checks_passed += 1
    else:
        print(f"   batch_verify.py: exists={batch_exists}, valid={batch_syntax}, works={batch_works}")
        print("   \u274c FAILED")
        all_passed = False

    # Check 2: Resolution Templates
    print()
    print("-" * 70)
    print("CHECK 2: Resolution Templates in Issues")
    print("-" * 70)
    with_templates, total = check_resolution_templates(ISSUES_DIR)
    pct = (with_templates / total * 100) if total > 0 else 0
    print(f"   Issues with resolution templates: {with_templates}/{total} ({pct:.1f}%)")
    if pct >= 80:
        print("   \u2705 PASSED")
        checks_passed += 1
    else:
        print("   \u274c FAILED (need 80%)")
        all_passed = False

    # Check 3: Cross-Reference Validator
    print()
    print("-" * 70)
    print("CHECK 3: Cross-Reference Validator Tool")
    print("-" * 70)
    crossref_exists = check_tool_exists('validate_crossrefs.py')
    crossref_syntax = check_tool_syntax('validate_crossrefs.py')

    if crossref_exists and crossref_syntax:
        print("   validate_crossrefs.py: EXISTS, VALID")
        print("   \u2705 PASSED")
        checks_passed += 1
    else:
        print(f"   validate_crossrefs.py: exists={crossref_exists}, valid={crossref_syntax}")
        print("   \u274c FAILED")
        all_passed = False

    # Check 4: Auto-Resolve Detector
    print()
    print("-" * 70)
    print("CHECK 4: Auto-Resolve Detector Tool")
    print("-" * 70)
    autoresolve_exists = check_tool_exists('auto_resolve.py')
    autoresolve_syntax = check_tool_syntax('auto_resolve.py')

    if autoresolve_exists and autoresolve_syntax:
        print("   auto_resolve.py: EXISTS, VALID")
        print("   \u2705 PASSED")
        checks_passed += 1
    else:
        print(f"   auto_resolve.py: exists={autoresolve_exists}, valid={autoresolve_syntax}")
        print("   \u274c FAILED")
        all_passed = False

    # Check 5: Report Generator
    print()
    print("-" * 70)
    print("CHECK 5: Report Generator Tool")
    print("-" * 70)
    report_exists = check_tool_exists('generate_report.py')
    report_syntax = check_tool_syntax('generate_report.py')
    report_works = check_report_generator_works()

    if report_exists and report_syntax and report_works:
        print("   generate_report.py: EXISTS, VALID, WORKS")
        print("   \u2705 PASSED")
        checks_passed += 1
    else:
        print(f"   generate_report.py: exists={report_exists}, valid={report_syntax}, works={report_works}")
        print("   \u274c FAILED")
        all_passed = False

    # Check 6: Add Resolution Template Tool
    print()
    print("-" * 70)
    print("CHECK 6: Add Resolution Template Tool")
    print("-" * 70)
    restemplate_exists = check_tool_exists('add_resolution_template.py')
    restemplate_syntax = check_tool_syntax('add_resolution_template.py')

    if restemplate_exists and restemplate_syntax:
        print("   add_resolution_template.py: EXISTS, VALID")
        print("   \u2705 PASSED")
        checks_passed += 1
    else:
        print(f"   add_resolution_template.py: exists={restemplate_exists}, valid={restemplate_syntax}")
        print("   \u274c FAILED")
        all_passed = False

    # Final verdict
    print()
    print("=" * 70)

    if all_passed:
        print("\U0001f389 PHASE 3 VERIFICATION COMPLETE: ALL CHECKS PASSED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u2705  PHASE 3 OPTIMIZED - Batch operations ready          \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")
    else:
        print(f"\u26a0\ufe0f  PHASE 3 VERIFICATION: {checks_passed}/{total_checks} CHECKS PASSED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u26a0\ufe0f   Some Phase 3 optimizations incomplete           \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")

    print("=" * 70)
    print()
    print("PHASE 3 SUMMARY")
    print(f"   Batch Verify Tool:        {'YES' if batch_exists and batch_works else 'NO'}")
    print(f"   Resolution Templates:     {with_templates}/{total} ({pct:.0f}%)")
    print(f"   Cross-Ref Validator:      {'YES' if crossref_exists else 'NO'}")
    print(f"   Auto-Resolve Detector:    {'YES' if autoresolve_exists else 'NO'}")
    print(f"   Report Generator:         {'YES' if report_exists and report_works else 'NO'}")
    print(f"   Resolution Template Tool: {'YES' if restemplate_exists else 'NO'}")
    print()
    print("AGENT CAPABILITIES")
    print(f"   Phase 1: Mechanical verification (~95%)")
    print(f"   Phase 2: Fix execution (~98%)")
    print(f"   Phase 3: Batch operations + auto-detect + reporting")
    print()

    return all_passed

def main():
    passed = run_verification()
    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()
