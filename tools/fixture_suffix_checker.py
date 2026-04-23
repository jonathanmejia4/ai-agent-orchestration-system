#!/usr/bin/env python3
"""
Fixture Suffix Checker
Version: 1.0.0
Last Updated: 2025-12-31
Owner: Builder
Classification: LOW - Test Style Compliance

Enforces CONVENTIONS.md:496 - Fixtures MUST use `_fixture` suffix for clarity.

Usage:
    python tools/fixture_suffix_checker.py tests/
    python tools/fixture_suffix_checker.py --strict
    python tools/fixture_suffix_checker.py --exclude conftest.py

Exit Codes:
    0: All fixtures have correct suffix
    1: Fixtures missing suffix found
    2: Configuration/runtime error
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

@dataclass
class FixtureViolation:
    """Represents a fixture without proper suffix."""
    file: str
    line: int
    name: str
    suggested_name: str

@dataclass
class FileResult:
    """Results for a single file."""
    file_path: str
    fixtures_checked: int = 0
    violations: List[FixtureViolation] = field(default_factory=list)

# Standard pytest fixtures that don't need _fixture suffix
EXEMPT_FIXTURES = {
    'request', 'tmp_path', 'tmp_path_factory', 'tmpdir', 'tmpdir_factory',
    'capsys', 'capfd', 'caplog', 'monkeypatch', 'pytestconfig', 'cache',
    'record_property', 'record_testsuite_property', 'record_xml_attribute',
    'recwarn', 'doctest_namespace', 'client', 'db', 'app', 'settings',
}

class FixtureVisitor(ast.NodeVisitor):
    """AST visitor that finds pytest fixtures."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.result = FileResult(file_path=file_path)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_fixture(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_fixture(node)
        self.generic_visit(node)

    def _check_fixture(self, node):
        """Check if function is a fixture and has proper suffix."""
        is_fixture = False

        for decorator in node.decorator_list:
            # Check for @pytest.fixture or @fixture
            if isinstance(decorator, ast.Attribute):
                if decorator.attr == 'fixture':
                    is_fixture = True
                    break
            elif isinstance(decorator, ast.Name):
                if decorator.id == 'fixture':
                    is_fixture = True
                    break
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr == 'fixture':
                        is_fixture = True
                        break
                elif isinstance(decorator.func, ast.Name):
                    if decorator.func.id == 'fixture':
                        is_fixture = True
                        break

        if not is_fixture:
            return

        self.result.fixtures_checked += 1

        # Check if name has _fixture suffix
        name = node.name

        # Skip exempt fixtures
        if name in EXEMPT_FIXTURES:
            return

        # Skip private fixtures
        if name.startswith('_'):
            return

        # Check for _fixture suffix
        if not name.endswith('_fixture'):
            suggested = f"{name}_fixture"
            self.result.violations.append(FixtureViolation(
                file=self.file_path,
                line=node.lineno,
                name=name,
                suggested_name=suggested
            ))

def check_file(file_path: Path) -> Optional[FileResult]:
    """Check fixtures in a single file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return None

    visitor = FixtureVisitor(str(file_path))
    visitor.visit(tree)

    return visitor.result

def check_directory(
    directory: Path,
    exclude_files: Set[str],
    verbose: bool = False
) -> List[FileResult]:
    """Check fixtures in all test files in directory."""
    results = []

    # Find test files
    patterns = ["test_*.py", "*_test.py", "conftest.py"]

    for pattern in patterns:
        for py_file in sorted(directory.rglob(pattern)):
            # Skip excluded files
            if py_file.name in exclude_files:
                continue

            # Skip __pycache__
            if "__pycache__" in py_file.parts:
                continue

            result = check_file(py_file)
            if result:
                results.append(result)

                if verbose:
                    if result.violations:
                        print(f"[FAIL] {py_file}: {len(result.violations)} fixtures without _fixture suffix")
                        for v in result.violations:
                            print(f"  Line {v.line}: '{v.name}' -> '{v.suggested_name}'")
                    elif result.fixtures_checked > 0:
                        print(f"[PASS] {py_file}: {result.fixtures_checked} fixtures OK")

    return results

def main():
    parser = argparse.ArgumentParser(
        description="Check pytest fixtures have _fixture suffix"
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("tests"),
        help="File or directory to check (default: tests/)"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated list of files to exclude"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if any violations found"
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

    # Parse exclusions
    exclude_files = set()
    if args.exclude:
        exclude_files.update(f.strip() for f in args.exclude.split(","))

    # Run checks
    if args.path.is_file():
        results = [check_file(args.path)]
        results = [r for r in results if r]
    elif args.path.is_dir():
        results = check_directory(args.path, exclude_files, args.verbose)
    else:
        print(f"Path not found: {args.path}", file=sys.stderr)
        sys.exit(2)

    # Aggregate statistics
    total_files = len(results)
    total_fixtures = sum(r.fixtures_checked for r in results)
    total_violations = sum(len(r.violations) for r in results)
    files_with_violations = sum(1 for r in results if r.violations)

    all_violations = [v for r in results for v in r.violations]

    if args.json:
        output = {
            "summary": {
                "total_files": total_files,
                "total_fixtures": total_fixtures,
                "total_violations": total_violations,
                "files_with_violations": files_with_violations,
                "passed": total_violations == 0
            },
            "violations": [
                {
                    "file": v.file,
                    "line": v.line,
                    "name": v.name,
                    "suggested_name": v.suggested_name
                }
                for v in all_violations
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print("Fixture Suffix Check Summary")
        print(f"{'='*50}")
        print(f"Files checked:        {total_files}")
        print(f"Fixtures found:       {total_fixtures}")
        print(f"Missing suffix:       {total_violations}")

        if all_violations and not args.verbose:
            print(f"\n{'='*50}")
            print("Fixtures Missing _fixture Suffix")
            print(f"{'='*50}")
            for v in all_violations[:20]:
                print(f"{v.file}:{v.line}: '{v.name}' -> '{v.suggested_name}'")
            if len(all_violations) > 20:
                print(f"... and {len(all_violations) - 20} more")

    # Determine exit code
    if args.strict and total_violations > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
