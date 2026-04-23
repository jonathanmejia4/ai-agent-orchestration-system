#!/usr/bin/env python3
"""
Embedded Test Data Checker
Version: 1.0.0
Last Updated: 2025-12-31
Owner: Builder
Classification: LOW - Test Style Compliance

Enforces CONVENTIONS.md:509 - Test data MUST NOT be embedded in test files
(should be separated to fixtures/).

Usage:
    python tools/embedded_test_data_checker.py tests/
    python tools/embedded_test_data_checker.py --threshold 100
    python tools/embedded_test_data_checker.py --strict

Exit Codes:
    0: No large embedded data found
    1: Large embedded data found
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
class EmbeddedDataViolation:
    """Represents embedded test data that should be in fixtures."""
    file: str
    line: int
    data_type: str  # dict, list, string
    size: int  # characters or elements
    context: str  # variable name or usage

@dataclass
class FileResult:
    """Results for a single file."""
    file_path: str
    violations: List[EmbeddedDataViolation] = field(default_factory=list)

# Size thresholds for detecting "large" embedded data
DEFAULT_DICT_THRESHOLD = 5  # Number of keys
DEFAULT_LIST_THRESHOLD = 10  # Number of elements
DEFAULT_STRING_THRESHOLD = 200  # Characters

class EmbeddedDataVisitor(ast.NodeVisitor):
    """AST visitor that finds large embedded test data."""

    def __init__(
        self,
        file_path: str,
        dict_threshold: int,
        list_threshold: int,
        string_threshold: int
    ):
        self.file_path = file_path
        self.dict_threshold = dict_threshold
        self.list_threshold = list_threshold
        self.string_threshold = string_threshold
        self.result = FileResult(file_path=file_path)
        self._current_name = None

    def visit_Assign(self, node: ast.Assign):
        # Get variable name for context
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._current_name = target.id
                break

        self._check_value(node.value, node.lineno)
        self._current_name = None
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check arguments to function calls
        for arg in node.args:
            self._check_value(arg, node.lineno)
        for keyword in node.keywords:
            self._check_value(keyword.value, node.lineno)
        self.generic_visit(node)

    def _check_value(self, node, line: int):
        """Check if a value is large embedded data."""
        if isinstance(node, ast.Dict):
            self._check_dict(node, line)
        elif isinstance(node, (ast.List, ast.Tuple)):
            self._check_list(node, line)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                self._check_string(node, line)
        # Handle older AST for strings
        elif isinstance(node, ast.Str):
            self._check_string_value(node.s, line)

    def _check_dict(self, node: ast.Dict, line: int):
        """Check if dict is too large to embed."""
        num_keys = len(node.keys)
        if num_keys >= self.dict_threshold:
            self.result.violations.append(EmbeddedDataViolation(
                file=self.file_path,
                line=line,
                data_type="dict",
                size=num_keys,
                context=self._current_name or "inline"
            ))

    def _check_list(self, node, line: int):
        """Check if list is too large to embed."""
        num_elements = len(node.elts)
        if num_elements >= self.list_threshold:
            self.result.violations.append(EmbeddedDataViolation(
                file=self.file_path,
                line=line,
                data_type="list",
                size=num_elements,
                context=self._current_name or "inline"
            ))

    def _check_string(self, node: ast.Constant, line: int):
        """Check if string is too large to embed."""
        if isinstance(node.value, str):
            self._check_string_value(node.value, line)

    def _check_string_value(self, value: str, line: int):
        """Check string length."""
        length = len(value)
        if length >= self.string_threshold:
            self.result.violations.append(EmbeddedDataViolation(
                file=self.file_path,
                line=line,
                data_type="string",
                size=length,
                context=self._current_name or "inline"
            ))

def check_file(
    file_path: Path,
    dict_threshold: int,
    list_threshold: int,
    string_threshold: int
) -> Optional[FileResult]:
    """Check for embedded data in a single file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return None

    visitor = EmbeddedDataVisitor(
        str(file_path),
        dict_threshold,
        list_threshold,
        string_threshold
    )
    visitor.visit(tree)

    return visitor.result

def check_directory(
    directory: Path,
    dict_threshold: int,
    list_threshold: int,
    string_threshold: int,
    exclude_files: Set[str],
    verbose: bool = False
) -> List[FileResult]:
    """Check for embedded data in all test files."""
    results = []

    # Find test files
    patterns = ["test_*.py", "*_test.py"]

    for pattern in patterns:
        for py_file in sorted(directory.rglob(pattern)):
            # Skip excluded files and conftest
            if py_file.name in exclude_files or py_file.name == "conftest.py":
                continue

            # Skip __pycache__
            if "__pycache__" in py_file.parts:
                continue

            result = check_file(
                py_file,
                dict_threshold,
                list_threshold,
                string_threshold
            )
            if result:
                results.append(result)

                if verbose:
                    if result.violations:
                        print(f"[WARN] {py_file}: {len(result.violations)} embedded data instances")
                        for v in result.violations:
                            print(f"  Line {v.line}: {v.data_type} with {v.size} elements ({v.context})")
                    else:
                        print(f"[PASS] {py_file}")

    return results

def main():
    parser = argparse.ArgumentParser(
        description="Check for large embedded test data in test files"
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("tests"),
        help="File or directory to check (default: tests/)"
    )
    parser.add_argument(
        "--dict-threshold",
        type=int,
        default=DEFAULT_DICT_THRESHOLD,
        help=f"Max dict keys before warning (default: {DEFAULT_DICT_THRESHOLD})"
    )
    parser.add_argument(
        "--list-threshold",
        type=int,
        default=DEFAULT_LIST_THRESHOLD,
        help=f"Max list elements before warning (default: {DEFAULT_LIST_THRESHOLD})"
    )
    parser.add_argument(
        "--string-threshold",
        type=int,
        default=DEFAULT_STRING_THRESHOLD,
        help=f"Max string length before warning (default: {DEFAULT_STRING_THRESHOLD})"
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
        results = [check_file(
            args.path,
            args.dict_threshold,
            args.list_threshold,
            args.string_threshold
        )]
        results = [r for r in results if r]
    elif args.path.is_dir():
        results = check_directory(
            args.path,
            args.dict_threshold,
            args.list_threshold,
            args.string_threshold,
            exclude_files,
            args.verbose
        )
    else:
        print(f"Path not found: {args.path}", file=sys.stderr)
        sys.exit(2)

    # Aggregate statistics
    total_files = len(results)
    total_violations = sum(len(r.violations) for r in results)
    files_with_violations = sum(1 for r in results if r.violations)

    all_violations = [v for r in results for v in r.violations]

    if args.json:
        output = {
            "summary": {
                "total_files": total_files,
                "files_with_violations": files_with_violations,
                "total_violations": total_violations,
                "thresholds": {
                    "dict_keys": args.dict_threshold,
                    "list_elements": args.list_threshold,
                    "string_length": args.string_threshold
                },
                "passed": total_violations == 0
            },
            "violations": [
                {
                    "file": v.file,
                    "line": v.line,
                    "type": v.data_type,
                    "size": v.size,
                    "context": v.context
                }
                for v in all_violations
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print("Embedded Test Data Check Summary")
        print(f"{'='*50}")
        print(f"Files checked:        {total_files}")
        print(f"Files with issues:    {files_with_violations}")
        print(f"Total violations:     {total_violations}")
        print(f"\nThresholds:")
        print(f"  Dict keys:     >= {args.dict_threshold}")
        print(f"  List elements: >= {args.list_threshold}")
        print(f"  String length: >= {args.string_threshold}")

        if all_violations and not args.verbose:
            print(f"\n{'='*50}")
            print("Large Embedded Data Found")
            print(f"{'='*50}")
            for v in all_violations[:20]:
                print(f"{v.file}:{v.line}: {v.data_type} with {v.size} elements ({v.context})")
            if len(all_violations) > 20:
                print(f"... and {len(all_violations) - 20} more")

    # Determine exit code
    if args.strict and total_violations > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
