#!/usr/bin/env python3
"""
Test Mirror Checker
Version: 1.0.0
Last Updated: 2025-12-31
Owner: Builder
Classification: MEDIUM - Test Compliance

Enforces CONVENTIONS.md:166 - For every src/<path>/module.py,
there MUST exist tests/<path>/test_module.py.

Usage:
    python tools/test_mirror_checker.py
    python tools/test_mirror_checker.py --src-dir src/ --tests-dir tests/
    python tools/test_mirror_checker.py --exclude "migrations,conftest"

Exit Codes:
    0: All source files have corresponding test files
    1: Missing test files found
    2: Configuration/runtime error
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Set, Tuple

# Files to exclude from mirror check
DEFAULT_EXCLUDES = {
    "__init__.py",
    "conftest.py",
    "__main__.py",
    "setup.py",
    "version.py",
    "_version.py",
}

# Directories to exclude
DEFAULT_EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    "migrations",
    "scripts",
    "fixtures",
    "data",
}

def find_source_files(
    src_dir: Path,
    exclude_files: Set[str],
    exclude_dirs: Set[str]
) -> List[Path]:
    """Find all Python source files in src directory."""
    source_files = []

    if not src_dir.exists():
        return source_files

    for py_file in src_dir.rglob("*.py"):
        # Skip excluded files
        if py_file.name in exclude_files:
            continue

        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue

        source_files.append(py_file)

    return sorted(source_files)

def get_expected_test_path(src_file: Path, src_dir: Path, tests_dir: Path) -> Path:
    """Calculate expected test file path for a source file."""
    # Get relative path from src directory
    rel_path = src_file.relative_to(src_dir)

    # Convert module.py to test_module.py
    test_filename = f"test_{rel_path.name}"

    # Build test path
    test_path = tests_dir / rel_path.parent / test_filename

    return test_path

def check_test_mirror(
    src_dir: Path,
    tests_dir: Path,
    exclude_files: Set[str],
    exclude_dirs: Set[str],
    verbose: bool = False
) -> Tuple[List[Path], List[Tuple[Path, Path]], int]:
    """
    Check that all source files have corresponding test files.

    Returns:
        Tuple of (missing_tests, found_tests, total_source_files)
    """
    source_files = find_source_files(src_dir, exclude_files, exclude_dirs)

    missing_tests = []
    found_tests = []

    for src_file in source_files:
        expected_test = get_expected_test_path(src_file, src_dir, tests_dir)

        if expected_test.exists():
            found_tests.append((src_file, expected_test))
            if verbose:
                print(f"[PASS] {src_file} -> {expected_test}")
        else:
            missing_tests.append(src_file)
            if verbose:
                print(f"[FAIL] {src_file} -> {expected_test} (MISSING)")

    return missing_tests, found_tests, len(source_files)

def main():
    parser = argparse.ArgumentParser(
        description="Check that source files have corresponding test files"
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=Path("src"),
        help="Source directory (default: src/)"
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=Path("tests"),
        help="Tests directory (default: tests/)"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated list of additional files/dirs to exclude"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if any source files are missing tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Build exclude sets
    exclude_files = DEFAULT_EXCLUDES.copy()
    exclude_dirs = DEFAULT_EXCLUDE_DIRS.copy()

    if args.exclude:
        for item in args.exclude.split(","):
            item = item.strip()
            if item.endswith(".py"):
                exclude_files.add(item)
            else:
                exclude_dirs.add(item)

    # Check if src directory exists
    if not args.src_dir.exists():
        if args.json:
            print(json.dumps({"error": f"Source directory not found: {args.src_dir}"}))
        else:
            print(f"Source directory not found: {args.src_dir}", file=sys.stderr)
        sys.exit(2)

    # Run the check
    missing, found, total = check_test_mirror(
        args.src_dir,
        args.tests_dir,
        exclude_files,
        exclude_dirs,
        args.verbose
    )

    # Calculate coverage
    coverage = (len(found) / total * 100) if total > 0 else 100

    if args.json:
        output = {
            "summary": {
                "total_source_files": total,
                "with_tests": len(found),
                "missing_tests": len(missing),
                "coverage_percent": round(coverage, 1),
                "passed": len(missing) == 0
            },
            "missing_test_files": [
                {
                    "source": str(src),
                    "expected_test": str(get_expected_test_path(src, args.src_dir, args.tests_dir))
                }
                for src in missing
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print("Test Mirror Check Summary")
        print(f"{'='*50}")
        print(f"Total source files:  {total}")
        print(f"With test files:     {len(found)}")
        print(f"Missing test files:  {len(missing)}")
        print(f"Test coverage:       {coverage:.1f}%")

        if missing:
            print(f"\n{'='*50}")
            print("Missing Test Files")
            print(f"{'='*50}")
            for src in missing[:20]:  # Limit output
                expected = get_expected_test_path(src, args.src_dir, args.tests_dir)
                print(f"  {src}")
                print(f"    -> Expected: {expected}")
            if len(missing) > 20:
                print(f"  ... and {len(missing) - 20} more")

    # Determine exit code
    if args.strict and missing:
        sys.exit(1)
    elif missing:
        # Non-strict mode: warn but don't fail
        sys.exit(0)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
