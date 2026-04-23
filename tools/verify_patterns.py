#!/usr/bin/env python3
"""
the system Verification Patterns Verification Tool

Verifies that verification_patterns.yaml is valid and complete.

Checks:
1. File exists and is valid YAML
2. All required sections present
3. All patterns have required fields
4. Type tag mappings are complete

Usage:
    python3 tools/verify_patterns.py
"""

import os
import sys
from datetime import datetime

PATTERNS_FILE = "tools/verification_patterns.yaml"

REQUIRED_SECTIONS = [
    'version',
    'depth_levels',
    'patterns',
    'type_tag_patterns',
    'severity_depth',
]

REQUIRED_PATTERN_FIELDS = [
    'description',
    'checks',
]

REQUIRED_CHECK_FIELDS = [
    'name',
    'command',
    'expected_exit',
]

def run_verification() -> bool:
    """Run patterns verification."""
    print("=" * 70)
    print("the system VERIFICATION PATTERNS VERIFICATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"File: {PATTERNS_FILE}")
    print()

    all_passed = True

    # =========================================================================
    # CHECK 1: File Exists and Valid YAML
    # =========================================================================
    print("-" * 70)
    print("CHECK 1: File Exists and Valid YAML")
    print("-" * 70)

    if not os.path.exists(PATTERNS_FILE):
        print(f"   \u274c FAILED: File not found: {PATTERNS_FILE}")
        return False

    try:
        import yaml
        with open(PATTERNS_FILE, 'r') as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            print(f"   \u274c FAILED: Root is not a dictionary")
            return False

        print(f"   File size: {os.path.getsize(PATTERNS_FILE)} bytes")
        print(f"   \u2705 PASSED: Valid YAML file")
    except ImportError:
        print(f"   \u274c FAILED: PyYAML not installed")
        return False
    except Exception as e:
        print(f"   \u274c FAILED: {e}")
        return False

    # =========================================================================
    # CHECK 2: Required Sections
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 2: Required Sections")
    print("-" * 70)

    missing_sections = []
    for section in REQUIRED_SECTIONS:
        if section in data:
            print(f"   \u2705 Found: {section}")
        else:
            print(f"   \u274c Missing: {section}")
            missing_sections.append(section)

    if missing_sections:
        print(f"   \u274c FAILED: Missing sections: {missing_sections}")
        all_passed = False
    else:
        print(f"   \u2705 PASSED: All required sections present")

    # =========================================================================
    # CHECK 3: Patterns Structure
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 3: Patterns Structure")
    print("-" * 70)

    patterns = data.get('patterns', {})
    pattern_count = len(patterns)
    print(f"   Total patterns: {pattern_count}")

    invalid_patterns = []
    for name, pattern in patterns.items():
        if not isinstance(pattern, dict):
            invalid_patterns.append(f"{name}: not a dict")
            continue

        for field in REQUIRED_PATTERN_FIELDS:
            if field not in pattern:
                invalid_patterns.append(f"{name}: missing {field}")

        # Check that checks is a list
        checks = pattern.get('checks', [])
        if not isinstance(checks, list):
            invalid_patterns.append(f"{name}: checks not a list")
            continue

        # Check each check
        for i, check in enumerate(checks):
            if not isinstance(check, dict):
                invalid_patterns.append(f"{name}.check[{i}]: not a dict")
                continue

            for field in REQUIRED_CHECK_FIELDS:
                if field not in check:
                    invalid_patterns.append(f"{name}.check[{i}]: missing {field}")

    if invalid_patterns:
        print(f"   \u274c FAILED: {len(invalid_patterns)} issues found")
        for issue in invalid_patterns[:5]:
            print(f"      - {issue}")
        all_passed = False
    else:
        print(f"   \u2705 PASSED: All {pattern_count} patterns valid")

    # =========================================================================
    # CHECK 4: Depth Levels
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 4: Depth Levels")
    print("-" * 70)

    depth_levels = data.get('depth_levels', {})
    required_depths = ['QUICK', 'STANDARD', 'DEEP']
    missing_depths = [d for d in required_depths if d not in depth_levels]

    if missing_depths:
        print(f"   \u274c FAILED: Missing depths: {missing_depths}")
        all_passed = False
    else:
        print(f"   \u2705 PASSED: All depth levels defined (QUICK, STANDARD, DEEP)")

    # =========================================================================
    # CHECK 5: Type Tag Mappings
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 5: Type Tag Mappings")
    print("-" * 70)

    type_mappings = data.get('type_tag_patterns', {})
    mapping_count = len(type_mappings)
    print(f"   Type tag mappings: {mapping_count}")

    # Check that mapped patterns exist
    invalid_mappings = []
    for tag, pattern_list in type_mappings.items():
        if not isinstance(pattern_list, list):
            invalid_mappings.append(f"{tag}: not a list")
            continue

        for pattern_name in pattern_list:
            if pattern_name not in patterns:
                invalid_mappings.append(f"{tag}: unknown pattern '{pattern_name}'")

    if invalid_mappings:
        print(f"   \u274c FAILED: {len(invalid_mappings)} invalid mappings")
        for issue in invalid_mappings[:5]:
            print(f"      - {issue}")
        all_passed = False
    else:
        print(f"   \u2705 PASSED: All type tags map to valid patterns")

    # =========================================================================
    # CHECK 6: Severity Mappings
    # =========================================================================
    print()
    print("-" * 70)
    print("CHECK 6: Severity to Depth Mappings")
    print("-" * 70)

    sev_depth = data.get('severity_depth', {})
    required_sev = ['HIGH', 'MEDIUM', 'LOW']
    missing_sev = [s for s in required_sev if s not in sev_depth]

    if missing_sev:
        print(f"   \u274c FAILED: Missing severity mappings: {missing_sev}")
        all_passed = False
    else:
        for sev, depth in sev_depth.items():
            print(f"   {sev} -> {depth}")
        print(f"   \u2705 PASSED: All severity levels mapped")

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
        print("   \u2551   \u2705  PATTERNS VERIFIED - File is valid and complete        \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")
    else:
        print("\u26a0\ufe0f  VERIFICATION COMPLETE: SOME CHECKS FAILED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u274c  PATTERNS NOT WORKING PROPERLY - Review errors above   \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")

    print("=" * 70)
    print()
    print("SUMMARY")
    print(f"   Patterns:     {pattern_count}")
    print(f"   Depth Levels: {len(depth_levels)}")
    print(f"   Type Tags:    {mapping_count}")

    return all_passed

def main():
    passed = run_verification()
    sys.exit(0 if passed else 1)

if __name__ == '__main__':
    main()
