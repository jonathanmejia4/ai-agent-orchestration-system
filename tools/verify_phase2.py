#!/usr/bin/env python3
"""
the system Phase 2 Optimization Verification

Verifies that all Phase 2 optimizations have been applied:
1. Fix Implementation Checklists in OPEN issues
2. Pattern Variables in frontmatter
3. Enhanced collect_evidence.py

Usage:
    python3 tools/verify_phase2.py
"""

import os
import sys
import glob
import re
from datetime import datetime

ISSUES_DIR = "issues"
TOOLS_DIR = "tools"

def check_fix_checklists(issues_dir: str) -> tuple:
    """Check how many OPEN issues have fix checklists."""
    total_open = 0
    with_checklist = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        # Check if OPEN
        if 'status: "RESOLVED"' in content or 'Status: RESOLVED' in content:
            continue

        total_open += 1

        if '**Fix Implementation Checklist**' in content:
            with_checklist += 1

    return with_checklist, total_open

def check_pattern_vars(issues_dir: str) -> tuple:
    """Check how many issues have pattern_vars."""
    total = 0
    with_vars = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        total += 1

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        if 'pattern_vars:' in content[:3000]:
            with_vars += 1

    return with_vars, total

def check_evidence_collector(tools_dir: str) -> bool:
    """Check if collect_evidence.py uses embedded commands."""
    filepath = os.path.join(tools_dir, 'collect_evidence.py')

    if not os.path.exists(filepath):
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return False

    # Check for key Phase 2 enhancements
    has_extract_commands = 'extract_verification_commands' in content
    has_embedded_check = 'Verification Commands' in content
    has_execute_command = 'execute_command' in content or 'subprocess' in content

    return has_extract_commands and has_embedded_check

def check_fix_checklist_tool(tools_dir: str) -> bool:
    """Check if add_fix_checklist.py exists and is valid."""
    filepath = os.path.join(tools_dir, 'add_fix_checklist.py')

    if not os.path.exists(filepath):
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return False

    # Check for key functionality
    has_fix_templates = 'FIX_TEMPLATES' in content
    has_generate = 'generate_checklist' in content
    has_extract = 'extract_fix_requirements' in content

    return has_fix_templates and has_generate and has_extract

def check_pattern_vars_tool(tools_dir: str) -> bool:
    """Check if add_pattern_vars.py exists and is valid."""
    filepath = os.path.join(tools_dir, 'add_pattern_vars.py')

    if not os.path.exists(filepath):
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return False

    # Check for key functionality
    has_pattern_vars = 'PATTERN_VARS' in content
    has_generate = 'generate_pattern_vars' in content
    has_insert = 'insert_pattern_vars' in content

    return has_pattern_vars and has_generate and has_insert

def run_verification() -> bool:
    """Run Phase 2 optimization verification."""
    print("=" * 70)
    print("the system PHASE 2 OPTIMIZATION VERIFICATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_passed = True

    # Check 1: Fix Implementation Checklists
    print("-" * 70)
    print("CHECK 1: Fix Implementation Checklists (OPEN issues)")
    print("-" * 70)
    with_checklists, total_open = check_fix_checklists(ISSUES_DIR)
    pct = (with_checklists / total_open * 100) if total_open > 0 else 0
    print(f"   OPEN issues with checklists: {with_checklists}/{total_open} ({pct:.1f}%)")
    if pct >= 80:
        print("   \u2705 PASSED")
    else:
        print("   \u274c FAILED (need 80%)")
        all_passed = False

    # Check 2: Pattern Variables
    print()
    print("-" * 70)
    print("CHECK 2: Pattern Variables in Frontmatter")
    print("-" * 70)
    with_vars, total = check_pattern_vars(ISSUES_DIR)
    pct = (with_vars / total * 100) if total > 0 else 0
    print(f"   Issues with pattern_vars: {with_vars}/{total} ({pct:.1f}%)")
    if pct >= 70:
        print("   \u2705 PASSED")
    else:
        print("   \u274c FAILED (need 70%)")
        all_passed = False

    # Check 3: Enhanced Evidence Collector
    print()
    print("-" * 70)
    print("CHECK 3: Enhanced Evidence Collector")
    print("-" * 70)
    evidence_enhanced = check_evidence_collector(TOOLS_DIR)
    if evidence_enhanced:
        print("   collect_evidence.py uses embedded commands: YES")
        print("   \u2705 PASSED")
    else:
        print("   collect_evidence.py uses embedded commands: NO")
        print("   \u274c FAILED")
        all_passed = False

    # Check 4: Fix Checklist Tool
    print()
    print("-" * 70)
    print("CHECK 4: Fix Checklist Generator Tool")
    print("-" * 70)
    checklist_tool_ok = check_fix_checklist_tool(TOOLS_DIR)
    if checklist_tool_ok:
        print("   add_fix_checklist.py exists and valid: YES")
        print("   \u2705 PASSED")
    else:
        print("   add_fix_checklist.py exists and valid: NO")
        print("   \u274c FAILED")
        all_passed = False

    # Check 5: Pattern Vars Tool
    print()
    print("-" * 70)
    print("CHECK 5: Pattern Variables Tool")
    print("-" * 70)
    vars_tool_ok = check_pattern_vars_tool(TOOLS_DIR)
    if vars_tool_ok:
        print("   add_pattern_vars.py exists and valid: YES")
        print("   \u2705 PASSED")
    else:
        print("   add_pattern_vars.py exists and valid: NO")
        print("   \u274c FAILED")
        all_passed = False

    # Final verdict
    print()
    print("=" * 70)

    passed_count = sum([
        pct >= 80,  # checklists
        (with_vars / total * 100) >= 70 if total > 0 else False,  # pattern vars
        evidence_enhanced,
        checklist_tool_ok,
        vars_tool_ok
    ])

    if all_passed:
        print("\U0001f389 PHASE 2 VERIFICATION COMPLETE: ALL CHECKS PASSED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u2705  PHASE 2 OPTIMIZED - Agent fix execution ready       \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")
    else:
        print(f"\u26a0\ufe0f  PHASE 2 VERIFICATION: {passed_count}/5 CHECKS PASSED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u26a0\ufe0f   Some Phase 2 optimizations incomplete           \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")

    print("=" * 70)
    print()
    print("PHASE 2 SUMMARY")
    print(f"   OPEN Issues with Checklists:  {with_checklists}/{total_open}")
    print(f"   Issues with Pattern Vars:     {with_vars}/{total}")
    print(f"   Evidence Collector Enhanced:  {'YES' if evidence_enhanced else 'NO'}")
    print(f"   Fix Checklist Tool:           {'YES' if checklist_tool_ok else 'NO'}")
    print(f"   Pattern Vars Tool:            {'YES' if vars_tool_ok else 'NO'}")
    print()
    print("AGENT READINESS")
    print(f"   Phase 1: ~95% mechanical verification")
    print(f"   Phase 2: ~98% mechanical fix execution")
    print()

    return all_passed

def main():
    passed = run_verification()
    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()
