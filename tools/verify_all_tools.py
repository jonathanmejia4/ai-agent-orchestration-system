#!/usr/bin/env python3
"""
the system Tools Verification Suite

Verifies that all catalog tools are working properly.
Runs checks on each tool and reports overall status.

Usage:
    python3 tools/verify_all_tools.py           # Run all checks
    python3 tools/verify_all_tools.py --verbose # Detailed output
"""

import os
import sys
import glob
import json
import subprocess
import argparse
from datetime import datetime
from typing import Dict, List, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
TOOLS_DIR = "tools"
EVIDENCE_DIR = "LogBook/verification/evidence"

REQUIRED_TOOLS = [
    "issue_stats.py",
    "verify_stats.py",
    "add_frontmatter.py",
    "fix_frontmatter.py",
    "collect_evidence.py",
    "verify_issue.py",
    "update_dashboard.py",
    "verification_patterns.yaml",
]

# =============================================================================
# CHECK FUNCTIONS
# =============================================================================

def check_tool_exists(tool: str) -> Tuple[bool, str]:
    """Check if tool file exists."""
    path = os.path.join(TOOLS_DIR, tool)
    if os.path.exists(path):
        return True, f"File exists: {path}"
    return False, f"File missing: {path}"

def check_python_syntax(script: str) -> Tuple[bool, str]:
    """Check Python script has valid syntax."""
    path = os.path.join(TOOLS_DIR, script)
    if not path.endswith('.py'):
        return True, "Not a Python file, skipped"

    try:
        result = subprocess.run(
            ['python3', '-m', 'py_compile', path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "Valid Python syntax"
        return False, f"Syntax error: {result.stderr[:100]}"
    except Exception as e:
        return False, f"Error: {e}"

def check_yaml_valid(filepath: str) -> Tuple[bool, str]:
    """Check YAML file is valid."""
    try:
        import yaml
        with open(filepath, 'r') as f:
            yaml.safe_load(f)
        return True, "Valid YAML"
    except Exception as e:
        return False, f"Invalid YAML: {e}"

def check_issue_stats() -> Tuple[bool, str]:
    """Verify issue_stats.py works correctly."""
    try:
        result = subprocess.run(
            ['python3', 'tools/issue_stats.py'],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0 and 'TOTAL:' in result.stdout:
            # Extract count
            import re
            match = re.search(r'TOTAL:\s*(\d+)\s*issues', result.stdout)
            if match:
                count = int(match.group(1))
                return True, f"Returns {count} total issues"
        return False, "Output format incorrect"
    except Exception as e:
        return False, f"Error: {e}"

def check_verify_stats() -> Tuple[bool, str]:
    """Verify verify_stats.py works correctly."""
    try:
        result = subprocess.run(
            ['python3', 'tools/verify_stats.py'],
            capture_output=True,
            text=True,
            timeout=60
        )
        if 'SCRIPT VERIFIED' in result.stdout:
            return True, "All math checks pass"
        elif 'SCRIPT NOT WORKING' in result.stdout:
            return False, "Math checks failed"
        return False, "Unexpected output"
    except Exception as e:
        return False, f"Error: {e}"

def check_frontmatter_present() -> Tuple[bool, str]:
    """Verify frontmatter was added to issue files."""
    total = 0
    with_frontmatter = 0

    for filepath in glob.glob(os.path.join(ISSUES_DIR, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue
        total += 1
        try:
            with open(filepath, 'r') as f:
                if f.read(3) == '---':
                    with_frontmatter += 1
        except:
            pass

    if total == 0:
        return False, "No issue files found"

    pct = (with_frontmatter / total) * 100
    if pct >= 99:
        return True, f"{with_frontmatter}/{total} files have frontmatter ({pct:.1f}%)"
    return False, f"Only {with_frontmatter}/{total} have frontmatter ({pct:.1f}%)"

def check_frontmatter_valid() -> Tuple[bool, str]:
    """Verify frontmatter is valid YAML in all files."""
    try:
        import yaml
    except ImportError:
        return False, "PyYAML not installed"

    total = 0
    valid = 0
    errors = []

    for filepath in glob.glob(os.path.join(ISSUES_DIR, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        total += 1
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            if not content.startswith('---'):
                continue

            end = content.find('\n---\n', 3)
            if end < 0:
                errors.append(os.path.basename(filepath))
                continue

            yaml.safe_load(content[4:end])
            valid += 1
        except yaml.YAMLError:
            errors.append(os.path.basename(filepath))
        except:
            pass

    if total == 0:
        return False, "No issue files found"

    pct = (valid / total) * 100
    if pct >= 99:
        return True, f"{valid}/{total} have valid YAML frontmatter ({pct:.1f}%)"
    return False, f"Only {valid}/{total} valid ({pct:.1f}%). Errors: {errors[:5]}"

def check_patterns_file() -> Tuple[bool, str]:
    """Verify verification_patterns.yaml is valid and complete."""
    path = os.path.join(TOOLS_DIR, "verification_patterns.yaml")

    try:
        import yaml
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        # Check required sections
        required = ['patterns', 'depth_levels', 'type_tag_patterns']
        missing = [r for r in required if r not in data]

        if missing:
            return False, f"Missing sections: {missing}"

        pattern_count = len(data.get('patterns', {}))
        return True, f"Valid with {pattern_count} patterns defined"
    except Exception as e:
        return False, f"Error: {e}"

def check_dashboard_generation() -> Tuple[bool, str]:
    """Verify dashboard can be generated."""
    try:
        result = subprocess.run(
            ['python3', 'tools/update_dashboard.py'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0 and 'Dashboard saved' in result.stdout:
            # Check file was created
            if os.path.exists('LogBook/verification/DASHBOARD.md'):
                return True, "Dashboard generated successfully"
        return False, f"Generation failed: {result.stderr[:100]}"
    except Exception as e:
        return False, f"Error: {e}"

def check_evidence_directory() -> Tuple[bool, str]:
    """Verify evidence directory structure."""
    if not os.path.isdir(EVIDENCE_DIR):
        return False, f"Directory missing: {EVIDENCE_DIR}"

    # Check for any evidence files
    evidence_files = glob.glob(os.path.join(EVIDENCE_DIR, '*', '*.json'))
    return True, f"Directory exists with {len(evidence_files)} evidence files"

def check_collect_evidence_syntax() -> Tuple[bool, str]:
    """Verify collect_evidence.py can at least parse."""
    try:
        result = subprocess.run(
            ['python3', '-c', 'import tools.collect_evidence'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd='.'
        )
        # Even if import fails due to dependencies, syntax should be OK
        if 'SyntaxError' in result.stderr:
            return False, "Syntax error in script"
        return True, "Script syntax valid"
    except Exception as e:
        return False, f"Error: {e}"

def check_verify_issue_syntax() -> Tuple[bool, str]:
    """Verify verify_issue.py can at least parse."""
    try:
        result = subprocess.run(
            ['python3', '-m', 'py_compile', 'tools/verify_issue.py'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "Script syntax valid"
        return False, f"Syntax error: {result.stderr[:100]}"
    except Exception as e:
        return False, f"Error: {e}"

# =============================================================================
# MAIN VERIFICATION
# =============================================================================

def run_all_checks(verbose: bool = False) -> Dict[str, bool]:
    """Run all verification checks."""
    results = {}

    checks = [
        ("Tool Files Exist", lambda: check_all_tools_exist()),
        ("Python Syntax Valid", lambda: check_all_python_syntax()),
        ("issue_stats.py Working", check_issue_stats),
        ("verify_stats.py Working", check_verify_stats),
        ("Frontmatter Present", check_frontmatter_present),
        ("Frontmatter Valid YAML", check_frontmatter_valid),
        ("Patterns File Valid", check_patterns_file),
        ("Dashboard Generation", check_dashboard_generation),
        ("Evidence Directory", check_evidence_directory),
        ("collect_evidence.py Syntax", check_collect_evidence_syntax),
        ("verify_issue.py Syntax", check_verify_issue_syntax),
    ]

    print("=" * 70)
    print("the system TOOLS VERIFICATION SUITE")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_passed = True

    for name, check_func in checks:
        try:
            passed, message = check_func()
        except Exception as e:
            passed, message = False, f"Exception: {e}"

        results[name] = passed
        icon = "\u2705" if passed else "\u274c"
        status = "PASS" if passed else "FAIL"

        print(f"{icon} {name}: {status}")
        if verbose or not passed:
            print(f"   {message}")

        if not passed:
            all_passed = False

    # Summary
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    print()
    print("=" * 70)

    if all_passed:
        print("\U0001f389 ALL CHECKS PASSED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u2705  ALL TOOLS VERIFIED - Catalog system working properly    \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")
    else:
        print("\u26a0\ufe0f  SOME CHECKS FAILED")
        print()
        print("   \u2554" + "\u2550" * 63 + "\u2557")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u2551   \u274c  TOOLS NOT WORKING PROPERLY - Review errors above       \u2551")
        print("   \u2551" + " " * 63 + "\u2551")
        print("   \u255a" + "\u2550" * 63 + "\u255d")

    print()
    print("=" * 70)
    print(f"Checks Passed: {passed_count}/{total_count}")
    print("=" * 70)

    return results

def check_all_tools_exist() -> Tuple[bool, str]:
    """Check all required tools exist."""
    missing = []
    for tool in REQUIRED_TOOLS:
        path = os.path.join(TOOLS_DIR, tool)
        if not os.path.exists(path):
            missing.append(tool)

    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, f"All {len(REQUIRED_TOOLS)} required tools present"

def check_all_python_syntax() -> Tuple[bool, str]:
    """Check all Python tools have valid syntax."""
    errors = []
    checked = 0

    for tool in REQUIRED_TOOLS:
        if not tool.endswith('.py'):
            continue
        checked += 1
        passed, _ = check_python_syntax(tool)
        if not passed:
            errors.append(tool)

    if errors:
        return False, f"Syntax errors in: {', '.join(errors)}"
    return True, f"All {checked} Python scripts have valid syntax"

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Verify all the system catalog tools are working properly'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed output for all checks')

    args = parser.parse_args()

    results = run_all_checks(args.verbose)

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()
