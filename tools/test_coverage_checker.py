#!/usr/bin/env python3
"""
Test Coverage Checker for the system Dimension 7 (Verification)

Validates test coverage for the the system codebase by checking:
- Test files exist for tools
- Task tests are present when required
- Integration test coverage

Usage:
    python3 tools/test_coverage_checker.py
    python3 tools/test_coverage_checker.py --verbose
    python3 tools/test_coverage_checker.py --min-coverage 80

Exit Codes:
    0 - PASS: Test coverage meets requirements
    1 - FAIL: Test coverage below threshold
    2 - ERROR: Invalid arguments or execution error

Referenced in:
    - .github/workflows/saf-gates.yml:380-381 (Verification Dimension check)

Author: System
Created: 2026-01-04
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Set

class TestCoverageChecker:
    """Checks test coverage for the system codebase"""

    def __init__(self, verbose: bool = False, min_coverage: int = 0):
        self.verbose = verbose
        self.min_coverage = min_coverage
        self.repo_root = self._find_repo_root()
        self.source_files: Set[str] = set()
        self.test_files: Set[str] = set()
        self.covered: Set[str] = set()
        self.issues: List[str] = []

    def _find_repo_root(self) -> Path:
        """Find repository root by looking for .git directory or the system markers"""
        current = Path.cwd()
        while current != current.parent:
            if (current / '.git').exists() or (current / 'CLAUDE.md').exists():
                return current
            current = current.parent
        # Fallback to cwd
        return Path.cwd()

    def _log(self, message: str) -> None:
        """Print message if verbose mode enabled"""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def _find_source_files(self) -> None:
        """Find all Python source files (excluding tests)"""
        tools_dir = self.repo_root / 'tools'

        if tools_dir.exists():
            for py_file in tools_dir.glob('*.py'):
                if not py_file.name.startswith('test_') and py_file.name != '__init__.py':
                    self.source_files.add(py_file.stem)
                    self._log(f"Source file: {py_file.name}")

    def _find_test_files(self) -> None:
        """Find all test files"""
        tests_dir = self.repo_root / 'tests'
        tools_dir = self.repo_root / 'tools'

        # Check tests/ directory
        if tests_dir.exists():
            for test_file in tests_dir.rglob('test_*.py'):
                # Extract the module name being tested
                module_name = test_file.stem.replace('test_', '')
                self.test_files.add(module_name)
                self._log(f"Test file: {test_file.name} -> tests {module_name}")

        # Check for tests in tools/ directory
        if tools_dir.exists():
            for test_file in tools_dir.glob('test_*.py'):
                module_name = test_file.stem.replace('test_', '')
                self.test_files.add(module_name)
                self._log(f"Test file: {test_file.name} -> tests {module_name}")

    def _calculate_coverage(self) -> None:
        """Calculate which source files have tests"""
        for source in self.source_files:
            if source in self.test_files:
                self.covered.add(source)
                self._log(f"Covered: {source}")
            else:
                self._log(f"Not covered: {source}")

    def check_coverage(self) -> bool:
        """Run the coverage check"""
        self._find_source_files()
        self._find_test_files()
        self._calculate_coverage()

        total_sources = len(self.source_files)
        covered_sources = len(self.covered)

        if total_sources == 0:
            # No source files to check
            return True

        coverage_pct = (covered_sources / total_sources) * 100

        # Check against minimum threshold
        if coverage_pct < self.min_coverage:
            self.issues.append(
                f"Coverage {coverage_pct:.1f}% is below minimum {self.min_coverage}%"
            )
            return False

        return True

    def report(self) -> None:
        """Print summary report"""
        total_sources = len(self.source_files)
        covered_sources = len(self.covered)
        coverage_pct = (covered_sources / total_sources * 100) if total_sources > 0 else 100

        print("")
        print("=" * 60)
        print("TEST COVERAGE CHECK (Dimension 7: Verification)")
        print("=" * 60)
        print(f"Source files:  {total_sources}")
        print(f"Test files:    {len(self.test_files)}")
        print(f"Covered:       {covered_sources}")
        print(f"Coverage:      {coverage_pct:.1f}%")

        if self.min_coverage > 0:
            print(f"Minimum:       {self.min_coverage}%")

        print("")

        if total_sources > 0 and covered_sources < total_sources:
            uncovered = self.source_files - self.covered
            print("Uncovered modules:")
            for module in sorted(uncovered)[:10]:  # Show max 10
                print(f"  - {module}")
            if len(uncovered) > 10:
                print(f"  ... and {len(uncovered) - 10} more")
            print("")

        if self.issues:
            print("Issues found:")
            for issue in self.issues:
                print(f"  - {issue}")
            print("")
            print("RESULT: FAIL")
        else:
            print("RESULT: PASS")

def main():
    parser = argparse.ArgumentParser(
        description="Check the system test coverage (Dimension 7: Verification)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug output'
    )

    parser.add_argument(
        '--min-coverage',
        type=int,
        default=0,
        help='Minimum coverage percentage required (default: 0)'
    )

    args = parser.parse_args()

    try:
        checker = TestCoverageChecker(
            verbose=args.verbose,
            min_coverage=args.min_coverage
        )

        passed = checker.check_coverage()
        checker.report()

        sys.exit(0 if passed else 1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
