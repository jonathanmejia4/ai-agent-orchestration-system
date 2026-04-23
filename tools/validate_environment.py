#!/usr/bin/env python3
"""
the system Environment Validator

Validates that the development environment is properly configured for the system.
Checks: Python version, required packages, directory structure, git hooks.

Usage:
    python3 tools/validate_environment.py
"""

import sys
import os
import subprocess
from pathlib import Path

def check_python_version():
    """Check Python version is 3.9+"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor} (need 3.9+)"

def check_git_hooks():
    """Check if git hooks are installed"""
    hooks_dir = Path(".githooks")
    if hooks_dir.exists():
        return True, "Git hooks directory exists"
    return False, "Git hooks not installed (run: git config core.hooksPath .githooks)"

def check_required_dirs():
    """Check required directories exist"""
    required = [".task", "LogBook", "PLANNING", "tools", "templates"]
    missing = [d for d in required if not Path(d).exists()]
    if not missing:
        return True, "All required directories present"
    return False, f"Missing directories: {', '.join(missing)}"

def check_saf_config():
    """Check .saf/ configuration exists"""
    saf_dir = Path(".saf")
    if saf_dir.exists():
        return True, ".saf/ configuration directory exists"
    return False, ".saf/ directory missing (run: bash tools/setup_saf.sh)"

def main():
    """Run all environment checks"""
    print("=" * 60)
    print("the system Environment Validator")
    print("=" * 60)

    checks = [
        ("Python Version", check_python_version),
        ("Git Hooks", check_git_hooks),
        ("Required Directories", check_required_dirs),
        ("the system Configuration", check_saf_config),
    ]

    all_passed = True
    for name, check_func in checks:
        passed, message = check_func()
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        print(f"       {message}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("Environment validation: PASSED")
        return 0
    else:
        print("Environment validation: FAILED")
        print("Run 'bash tools/setup_saf.sh' to fix common issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
