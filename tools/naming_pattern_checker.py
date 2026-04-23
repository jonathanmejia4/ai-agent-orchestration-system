#!/usr/bin/env python3
"""
Naming Pattern Checker
Version: 1.0.0
Last Updated: 2025-12-31
Owner: Builder
Classification: MEDIUM - Code Style Compliance

Enforces CONVENTIONS.md:191-203 naming patterns:
- Classes: PascalCase
- Functions/Methods: snake_case
- Constants: UPPER_SNAKE_CASE

Usage:
    python tools/naming_pattern_checker.py src/
    python tools/naming_pattern_checker.py src/ tools/
    python tools/naming_pattern_checker.py --check classes,functions
    python tools/naming_pattern_checker.py --strict

Exit Codes:
    0: All naming conventions followed
    1: Naming violations found
    2: Configuration/runtime error
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

@dataclass
class NamingViolation:
    """Represents a naming convention violation."""
    file: str
    line: int
    name: str
    expected_pattern: str
    actual_pattern: str
    element_type: str  # class, function, constant

@dataclass
class FileResult:
    """Results for a single file."""
    file_path: str
    violations: List[NamingViolation] = field(default_factory=list)
    checked_classes: int = 0
    checked_functions: int = 0
    checked_constants: int = 0

# Naming patterns
PASCAL_CASE_PATTERN = re.compile(r'^[A-Z][a-zA-Z0-9]*$')
SNAKE_CASE_PATTERN = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$')
UPPER_SNAKE_CASE_PATTERN = re.compile(r'^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$')

# Allowed exceptions (built-in naming conventions)
ALLOWED_FUNCTION_NAMES = {
    '__init__', '__str__', '__repr__', '__eq__', '__ne__', '__lt__', '__le__',
    '__gt__', '__ge__', '__hash__', '__bool__', '__len__', '__iter__',
    '__next__', '__getitem__', '__setitem__', '__delitem__', '__contains__',
    '__call__', '__enter__', '__exit__', '__add__', '__sub__', '__mul__',
    '__truediv__', '__floordiv__', '__mod__', '__pow__', '__and__', '__or__',
    '__xor__', '__neg__', '__pos__', '__abs__', '__invert__', '__getattr__',
    '__setattr__', '__delattr__', '__new__', '__del__', '__copy__',
    '__deepcopy__', '__reduce__', '__reduce_ex__', '__getnewargs__',
    '__getstate__', '__setstate__', '__format__', '__sizeof__', '__class__',
    'setUp', 'tearDown', 'setUpClass', 'tearDownClass',  # unittest
}

# Skip private names starting with single underscore for constants
SKIP_PRIVATE = True

def is_pascal_case(name: str) -> bool:
    """Check if name follows PascalCase convention."""
    return bool(PASCAL_CASE_PATTERN.match(name))

def is_snake_case(name: str) -> bool:
    """Check if name follows snake_case convention."""
    # Allow dunder methods
    if name.startswith('__') and name.endswith('__'):
        return True
    # Allow private methods with underscore prefix
    check_name = name.lstrip('_')
    return bool(SNAKE_CASE_PATTERN.match(check_name))

def is_upper_snake_case(name: str) -> bool:
    """Check if name follows UPPER_SNAKE_CASE convention."""
    return bool(UPPER_SNAKE_CASE_PATTERN.match(name))

def looks_like_constant(name: str, value_node: Optional[ast.AST]) -> bool:
    """Heuristic to determine if an assignment is a constant."""
    # Must be ALL_CAPS or mostly uppercase
    if not name.isupper() and '_' not in name:
        return False

    # Skip private names
    if SKIP_PRIVATE and name.startswith('_') and not name.startswith('__'):
        return False

    # Check if value looks like a constant
    if value_node is None:
        return name.isupper()

    if isinstance(value_node, (ast.Constant, ast.Num, ast.Str)):
        return True
    if isinstance(value_node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
        return True

    return name.isupper()

class NamingVisitor(ast.NodeVisitor):
    """AST visitor that checks naming conventions."""

    def __init__(self, file_path: str, check_types: Set[str]):
        self.file_path = file_path
        self.check_types = check_types
        self.result = FileResult(file_path=file_path)
        self._in_class = False

    def visit_ClassDef(self, node: ast.ClassDef):
        if 'classes' in self.check_types:
            self.result.checked_classes += 1

            if not is_pascal_case(node.name):
                self.result.violations.append(NamingViolation(
                    file=self.file_path,
                    line=node.lineno,
                    name=node.name,
                    expected_pattern="PascalCase",
                    actual_pattern=self._describe_pattern(node.name),
                    element_type="class"
                ))

        # Visit nested nodes
        old_in_class = self._in_class
        self._in_class = True
        self.generic_visit(node)
        self._in_class = old_in_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function(node)

    def _check_function(self, node):
        if 'functions' in self.check_types:
            self.result.checked_functions += 1

            # Skip allowed names
            if node.name in ALLOWED_FUNCTION_NAMES:
                self.generic_visit(node)
                return

            if not is_snake_case(node.name):
                self.result.violations.append(NamingViolation(
                    file=self.file_path,
                    line=node.lineno,
                    name=node.name,
                    expected_pattern="snake_case",
                    actual_pattern=self._describe_pattern(node.name),
                    element_type="function"
                ))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        if 'constants' in self.check_types and not self._in_class:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id

                    # Check if it looks like a constant
                    if looks_like_constant(name, node.value):
                        self.result.checked_constants += 1

                        if not is_upper_snake_case(name):
                            self.result.violations.append(NamingViolation(
                                file=self.file_path,
                                line=node.lineno,
                                name=name,
                                expected_pattern="UPPER_SNAKE_CASE",
                                actual_pattern=self._describe_pattern(name),
                                element_type="constant"
                            ))

        self.generic_visit(node)

    def _describe_pattern(self, name: str) -> str:
        """Describe the naming pattern of a name."""
        if is_pascal_case(name):
            return "PascalCase"
        if is_snake_case(name):
            return "snake_case"
        if is_upper_snake_case(name):
            return "UPPER_SNAKE_CASE"
        if name.startswith('_'):
            return "private_name"
        return "mixed_case"

def check_file(file_path: Path, check_types: Set[str]) -> Optional[FileResult]:
    """Check naming conventions in a single file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return None

    visitor = NamingVisitor(str(file_path), check_types)
    visitor.visit(tree)

    return visitor.result

def check_directory(
    directory: Path,
    check_types: Set[str],
    exclude_dirs: Set[str],
    verbose: bool = False
) -> List[FileResult]:
    """Check naming conventions in all Python files in directory."""
    results = []

    for py_file in sorted(directory.rglob("*.py")):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue

        result = check_file(py_file, check_types)
        if result:
            results.append(result)

            if verbose:
                if result.violations:
                    print(f"[FAIL] {py_file}: {len(result.violations)} violations")
                    for v in result.violations[:5]:
                        print(f"  Line {v.line}: {v.element_type} '{v.name}' "
                              f"should be {v.expected_pattern}")
                else:
                    print(f"[PASS] {py_file}")

    return results

def main():
    parser = argparse.ArgumentParser(
        description="Check Python naming conventions"
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="*",
        default=[Path(".")],
        help="File(s) or directory(ies) to check (default: current directory)"
    )
    parser.add_argument(
        "--check",
        type=str,
        default="classes,functions,constants",
        help="Comma-separated list of what to check (default: classes,functions,constants)"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated list of directories to exclude"
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

    # Parse check types
    check_types = set(t.strip() for t in args.check.split(","))
    valid_types = {"classes", "functions", "constants"}
    invalid_types = check_types - valid_types
    if invalid_types:
        print(f"Invalid check types: {invalid_types}", file=sys.stderr)
        sys.exit(2)

    # Parse exclusions
    exclude_dirs = {"__pycache__", ".git", ".venv", "venv", "node_modules"}
    if args.exclude:
        exclude_dirs.update(d.strip() for d in args.exclude.split(","))

    # Run checks - handle multiple paths
    results = []
    paths_to_check = args.path if args.path else [Path(".")]
    for path in paths_to_check:
        if path.is_file():
            result = check_file(path, check_types)
            if result:
                results.append(result)
        elif path.is_dir():
            results.extend(check_directory(path, check_types, exclude_dirs, args.verbose))
        else:
            print(f"Path not found: {path}", file=sys.stderr)
            sys.exit(2)

    # Aggregate statistics
    total_files = len(results)
    total_violations = sum(len(r.violations) for r in results)
    files_with_violations = sum(1 for r in results if r.violations)

    total_classes = sum(r.checked_classes for r in results)
    total_functions = sum(r.checked_functions for r in results)
    total_constants = sum(r.checked_constants for r in results)

    all_violations = [v for r in results for v in r.violations]

    if args.json:
        output = {
            "summary": {
                "total_files": total_files,
                "files_with_violations": files_with_violations,
                "total_violations": total_violations,
                "checked": {
                    "classes": total_classes,
                    "functions": total_functions,
                    "constants": total_constants
                },
                "passed": total_violations == 0
            },
            "violations": [
                {
                    "file": v.file,
                    "line": v.line,
                    "name": v.name,
                    "type": v.element_type,
                    "expected": v.expected_pattern,
                    "actual": v.actual_pattern
                }
                for v in all_violations
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print("Naming Convention Check Summary")
        print(f"{'='*50}")
        print(f"Files checked:        {total_files}")
        print(f"Files with violations: {files_with_violations}")
        print(f"Total violations:     {total_violations}")
        print(f"\nChecked:")
        print(f"  Classes:   {total_classes}")
        print(f"  Functions: {total_functions}")
        print(f"  Constants: {total_constants}")

        if all_violations and not args.verbose:
            print(f"\n{'='*50}")
            print("Violations (first 20)")
            print(f"{'='*50}")
            for v in all_violations[:20]:
                print(f"{v.file}:{v.line}: {v.element_type} '{v.name}' "
                      f"should be {v.expected_pattern} (is {v.actual_pattern})")
            if len(all_violations) > 20:
                print(f"... and {len(all_violations) - 20} more")

    # Determine exit code
    if args.strict and total_violations > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
