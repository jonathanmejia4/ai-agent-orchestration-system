#!/usr/bin/env python3
"""
SAF Convention Checker
Purpose: Validate code against SAF conventions defined in conventions.yaml
Usage: python tools/convention_checker.py [--fix] [--verbose]
Exit codes: 0 = pass, 1 = violations found, 2 = error
"""

import argparse
import ast
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

@dataclass
class Violation:
    """Represents a convention violation."""

    check: str
    severity: str
    file_path: str
    line: Optional[int]
    message: str
    fixable: bool = False

class ConventionChecker:
    """Validates SAF conventions."""

    def __init__(self, config_path: str, repo_root: str):
        """Initialize checker with configuration."""
        self.repo_root = Path(repo_root)
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.violations: List[Violation] = []

    def check_all(self) -> int:
        """Run all convention checks.

        Returns:
            Number of violations found
        """
        print("🔍 Running SAF convention checks...\n")

        # Run all check categories
        self.check_file_structure()
        self.check_naming_conventions()
        self.check_traceability_tags()
        self.check_code_quality()
        self.check_documentation()
        self.check_api_documentation()
        self.check_escape_hatch_tracking()
        self.check_fixable_issues()

        return len(self.violations)

    def check_file_structure(self):
        """Verify file and folder structure conventions."""
        print("📁 Checking file structure...")

        # Check required directories exist
        required_dirs = self.config["structure"]["project_root"]["required_directories"]
        for dir_name in required_dirs:
            dir_path = self.repo_root / dir_name
            if not dir_path.exists():
                self.violations.append(
                    Violation(
                        check="file_structure",
                        severity="error",
                        file_path=str(dir_path),
                        line=None,
                        message=f"Required directory '{dir_name}' does not exist",
                    )
                )

        # Check product code is in src/
        for py_file in self.repo_root.rglob("*.py"):
            # Skip venv, .venv, node_modules, etc.
            if any(
                part in py_file.parts
                for part in ["venv", ".venv", "node_modules", ".git", "__pycache__"]
            ):
                continue

            # Check if it's product code (not test, not tool, not in src/)
            if (
                "test" not in py_file.name
                and "tests" not in py_file.parts
                and "tools" not in py_file.parts
                and "src" not in py_file.parts
                and py_file.name != "setup.py"
                and py_file.name != "convention_checker.py"
            ):
                self.violations.append(
                    Violation(
                        check="file_structure",
                        severity="error",
                        file_path=str(py_file),
                        line=None,
                        message="Product code must be in src/ directory",
                    )
                )

        # Check test structure mirrors source
        src_path = self.repo_root / "src"
        tests_path = self.repo_root / "tests"

        if src_path.exists():
            for src_file in src_path.rglob("*.py"):
                if src_file.name == "__init__.py":
                    continue

                # Calculate corresponding test file path
                rel_path = src_file.relative_to(src_path)
                test_file = tests_path / rel_path.parent / f"test_{rel_path.name}"

                if not test_file.exists():
                    self.violations.append(
                        Violation(
                            check="file_structure",
                            severity="error",
                            file_path=str(src_file),
                            line=None,
                            message=f"Missing test file: {test_file}",
                        )
                    )

    def check_naming_conventions(self):
        """Verify naming conventions for Python code."""
        print("✍️  Checking naming conventions...")

        src_path = self.repo_root / "src"
        if not src_path.exists():
            return

        for py_file in src_path.rglob("*.py"):
            try:
                with open(py_file, "r") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                    self._check_ast_naming(tree, py_file)
            except SyntaxError:
                self.violations.append(
                    Violation(
                        check="naming",
                        severity="error",
                        file_path=str(py_file),
                        line=None,
                        message="Syntax error prevents naming check",
                    )
                )

    def _check_ast_naming(self, tree: ast.AST, file_path: Path):
        """Check naming conventions in AST."""
        naming = self.config["naming"]["python"]

        for node in ast.walk(tree):
            # Check class names (PascalCase)
            if isinstance(node, ast.ClassDef):
                class_regex = naming["classes"]["regex"]
                if not re.match(class_regex, node.name):
                    self.violations.append(
                        Violation(
                            check="naming",
                            severity="error",
                            file_path=str(file_path),
                            line=node.lineno,
                            message=f"Class '{node.name}' must be PascalCase",
                        )
                    )

            # Check function names (snake_case)
            elif isinstance(node, ast.FunctionDef):
                # Skip private methods (intentionally start with _)
                if node.name.startswith("_"):
                    continue

                func_regex = naming["functions"]["regex"]
                if not re.match(func_regex, node.name):
                    self.violations.append(
                        Violation(
                            check="naming",
                            severity="error",
                            file_path=str(file_path),
                            line=node.lineno,
                            message=f"Function '{node.name}' must be snake_case",
                        )
                    )

            # Check constant names (UPPER_SNAKE_CASE)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Only check module-level constants (all caps)
                        if target.id.isupper():
                            const_regex = naming["constants"]["regex"]
                            if not re.match(const_regex, target.id):
                                self.violations.append(
                                    Violation(
                                        check="naming",
                                        severity="error",
                                        file_path=str(file_path),
                                        line=node.lineno,
                                        message=f"Constant '{target.id}' must be UPPER_SNAKE_CASE",
                                    )
                                )

    def check_traceability_tags(self):
        """Verify SAF traceability tags are present in generated files."""
        print("🏷️  Checking traceability tags...")

        # Only check files that appear to be generated
        # (This is a simplified check; real implementation would track generated files)
        src_path = self.repo_root / "src"
        if not src_path.exists():
            return

        for py_file in src_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            try:
                with open(py_file, "r") as f:
                    content = f.read()

                    # Check if file has SAF tags
                    if "@saf:brick-id=" in content:
                        # File claims to be generated, validate tags
                        self._validate_saf_tags(py_file, content)
            except Exception as e:
                self.violations.append(
                    Violation(
                        check="traceability",
                        severity="error",
                        file_path=str(py_file),
                        line=None,
                        message=f"Error reading file: {e}",
                    )
                )

    def _validate_saf_tags(self, file_path: Path, content: str):
        """Validate SAF traceability tags in file."""
        required_tags = self.config["traceability"]["saf_tags"]["required_tags"]
        tag_formats = self.config["traceability"]["saf_tags"]["tag_formats"]

        for tag in required_tags:
            pattern = f"@saf:{tag}="
            if pattern not in content:
                self.violations.append(
                    Violation(
                        check="traceability",
                        severity="error",
                        file_path=str(file_path),
                        line=None,
                        message=f"Missing required SAF tag: @saf:{tag}",
                    )
                )
            else:
                # Extract tag value and validate format
                match = re.search(f"@saf:{tag}=([^\n]+)", content)
                if match:
                    value = match.group(1).strip()
                    self._validate_tag_value(file_path, tag, value, tag_formats.get(tag))

    def _validate_tag_value(
        self, file_path: Path, tag: str, value: str, format_spec: Optional[Dict]
    ):
        """Validate tag value against format specification."""
        if not format_spec:
            return

        if "regex" in format_spec:
            if not re.match(format_spec["regex"], value):
                self.violations.append(
                    Violation(
                        check="traceability",
                        severity="error",
                        file_path=str(file_path),
                        line=None,
                        message=f"Invalid format for @saf:{tag}='{value}'",
                    )
                )

        # Special validation for brick-id (must be valid UUID)
        if tag == "brick-id":
            try:
                uuid.UUID(value)
            except ValueError:
                self.violations.append(
                    Violation(
                        check="traceability",
                        severity="error",
                        file_path=str(file_path),
                        line=None,
                        message=f"Invalid UUID for brick-id: '{value}'",
                    )
                )

    def check_code_quality(self):
        """Verify code quality limits."""
        print("📊 Checking code quality limits...")

        quality_limits = self.config["quality"]["complexity"]
        src_path = self.repo_root / "src"
        if not src_path.exists():
            return

        for py_file in src_path.rglob("*.py"):
            try:
                with open(py_file, "r") as f:
                    lines = f.readlines()
                    total_lines = len(lines)

                    # Check file length
                    if total_lines > quality_limits["max_file_length"]:
                        self.violations.append(
                            Violation(
                                check="code_quality",
                                severity="error",
                                file_path=str(py_file),
                                line=None,
                                message=f"File has {total_lines} lines, max is {quality_limits['max_file_length']}",
                            )
                        )

                    # Parse and check function lengths
                    tree = ast.parse("".join(lines), filename=str(py_file))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            func_lines = node.end_lineno - node.lineno + 1
                            if func_lines > quality_limits["max_function_length"]:
                                self.violations.append(
                                    Violation(
                                        check="code_quality",
                                        severity="error",
                                        file_path=str(py_file),
                                        line=node.lineno,
                                        message=f"Function '{node.name}' has {func_lines} lines, max is {quality_limits['max_function_length']}",
                                    )
                                )

                            # Check parameter count
                            param_count = len(node.args.args)
                            if param_count > quality_limits["max_parameters"]:
                                self.violations.append(
                                    Violation(
                                        check="code_quality",
                                        severity="error",
                                        file_path=str(py_file),
                                        line=node.lineno,
                                        message=f"Function '{node.name}' has {param_count} parameters, max is {quality_limits['max_parameters']}",
                                    )
                                )

            except SyntaxError:
                pass  # Already reported in naming check

    def check_documentation(self):
        """Verify documentation requirements."""
        print("📝 Checking documentation...")

        src_path = self.repo_root / "src"
        if not src_path.exists():
            return

        docstring_required = self.config["quality"]["docstrings"]["required_for"]

        for py_file in src_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            try:
                with open(py_file, "r") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                    self._check_docstrings(tree, py_file, docstring_required)
            except SyntaxError:
                pass  # Already reported

    def _check_docstrings(
        self, tree: ast.AST, file_path: Path, required_for: List[str]
    ):
        """Check for required docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions
                if node.name.startswith("_"):
                    continue

                # Check if public function has docstring
                if "public_functions" in required_for:
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        self.violations.append(
                            Violation(
                                check="documentation",
                                severity="error",
                                file_path=str(file_path),
                                line=node.lineno,
                                message=f"Public function '{node.name}' missing docstring",
                            )
                        )

            elif isinstance(node, ast.ClassDef):
                # Check if public class has docstring
                if "public_classes" in required_for:
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        self.violations.append(
                            Violation(
                                check="documentation",
                                severity="error",
                                file_path=str(file_path),
                                line=node.lineno,
                                message=f"Public class '{node.name}' missing docstring",
                            )
                        )

    def check_api_documentation(self):
        """Verify API endpoints have corresponding documentation.

        Per CONVENTIONS.md:186 - Every public API endpoint MUST have a
        corresponding docs/api/<version>/<resource>.md file.
        """
        print("📚 Checking API documentation...")

        api_path = self.repo_root / "api" / "endpoints"
        docs_api_path = self.repo_root / "docs" / "api" / "v1"

        if not api_path.exists():
            return  # No API endpoints to check

        # Check each API endpoint has corresponding documentation
        for endpoint_file in api_path.glob("*.md"):
            if endpoint_file.name == "README.md":
                continue

            # Expected doc path: docs/api/v1/<endpoint>.md
            expected_doc = docs_api_path / endpoint_file.name

            if not expected_doc.exists():
                self.violations.append(
                    Violation(
                        check="api_documentation",
                        severity="error",
                        file_path=str(endpoint_file),
                        line=None,
                        message=f"API endpoint missing docs: expected {expected_doc}",
                    )
                )

    def check_escape_hatch_tracking(self):
        """Verify escape hatches are tracked in LogBook.

        Per GENERATION_ESCAPE_HATCH_POLICY.md:3 - Escape hatches must be
        LogBook-tracked for audit purposes.
        """
        print("🚪 Checking escape hatch tracking...")

        escape_hatch_log = self.repo_root / "LogBook" / "escape-hatches.yaml"

        # Find files with escape hatch markers
        for py_file in self.repo_root.rglob("*.py"):
            # Skip common directories
            if any(
                part in py_file.parts
                for part in ["venv", ".venv", "node_modules", ".git", "__pycache__"]
            ):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                # Check for escape hatch markers
                if "@escape-hatch" in content or "ESCAPE_HATCH" in content:
                    # Verify it's tracked in LogBook (if log exists)
                    if escape_hatch_log.exists():
                        log_content = escape_hatch_log.read_text(encoding="utf-8")
                        rel_path = str(py_file.relative_to(self.repo_root))
                        if rel_path not in log_content:
                            self.violations.append(
                                Violation(
                                    check="escape_hatch_tracking",
                                    severity="error",
                                    file_path=str(py_file),
                                    line=None,
                                    message="Escape hatch not tracked in LogBook/escape-hatches.yaml",
                                )
                            )
            except (IOError, UnicodeDecodeError):
                pass

    def check_fixable_issues(self):
        """Check for auto-fixable issues like trailing whitespace and missing newlines."""
        print("🔧 Checking for auto-fixable issues...")

        # Check all Python files in src and tools
        check_paths = [self.repo_root / "src", self.repo_root / "tools"]

        for check_path in check_paths:
            if not check_path.exists():
                continue

            for py_file in check_path.rglob("*.py"):
                try:
                    with open(py_file, "r") as f:
                        content = f.read()
                        lines = content.split('\n')

                    # Check for trailing whitespace
                    for i, line in enumerate(lines, 1):
                        if line != line.rstrip():
                            self.violations.append(
                                Violation(
                                    check="code_quality",
                                    severity="warning",
                                    file_path=str(py_file),
                                    line=i,
                                    message="Trailing whitespace detected",
                                    fixable=True,
                                )
                            )
                            break  # Only report once per file

                    # Check for missing newline at end of file
                    if content and not content.endswith('\n'):
                        self.violations.append(
                            Violation(
                                check="code_quality",
                                severity="warning",
                                file_path=str(py_file),
                                line=len(lines),
                                message="Missing newline at end of file",
                                fixable=True,
                            )
                        )

                    # Check for multiple blank lines
                    import re as re_check
                    if re_check.search(r'\n{3,}', content):
                        self.violations.append(
                            Violation(
                                check="code_quality",
                                severity="warning",
                                file_path=str(py_file),
                                line=None,
                                message="Multiple blank lines detected (3+ consecutive)",
                                fixable=True,
                            )
                        )

                except (IOError, UnicodeDecodeError):
                    pass

    def report(self, verbose: bool = False) -> bool:
        """Print violation report.

        Args:
            verbose: Show all details

        Returns:
            True if violations found, False otherwise
        """
        if not self.violations:
            print("\n✅ All convention checks passed!\n")
            return False

        print(f"\n❌ Found {len(self.violations)} convention violations:\n")

        # Group by check type
        by_check: Dict[str, List[Violation]] = {}
        for v in self.violations:
            by_check.setdefault(v.check, []).append(v)

        for check, violations in sorted(by_check.items()):
            print(f"  {check}: {len(violations)} violations")

        if verbose:
            print("\nDetailed violations:\n")
            for v in self.violations:
                location = f"{v.file_path}"
                if v.line:
                    location += f":{v.line}"
                print(f"  [{v.severity.upper()}] {location}")
                print(f"    {v.message}")
                if v.fixable:
                    print("    (auto-fixable)")
                print()

        return True

    def auto_fix(self):
        """Apply automatic fixes for fixable violations.

        Currently supports:
        - Trailing whitespace removal
        - Missing newline at end of file
        - Empty line cleanup (multiple blank lines -> single)

        For import ordering and code formatting, use external tools:
        - isort: pip install isort && isort .
        - black: pip install black && black .
        """
        print("🔧 Auto-fixing violations...\n")

        fixable = [v for v in self.violations if v.fixable]
        print(f"Found {len(fixable)} auto-fixable violations")

        if not fixable:
            print("No auto-fixable violations to process.")
            return

        # Group fixable violations by file
        files_to_fix: Dict[str, List[Violation]] = {}
        for v in fixable:
            files_to_fix.setdefault(v.file_path, []).append(v)

        fixed_count = 0

        for file_path, violations in files_to_fix.items():
            try:
                path = Path(file_path)
                if not path.exists():
                    print(f"  ⚠️  Skipping {file_path}: file not found")
                    continue

                # Read original content
                original = path.read_text()
                content = original

                # Apply fixes
                for v in violations:
                    if "trailing whitespace" in v.message.lower():
                        # Remove trailing whitespace from each line
                        lines = content.split('\n')
                        content = '\n'.join(line.rstrip() for line in lines)

                    if "missing newline" in v.message.lower() or "eof" in v.message.lower():
                        # Ensure file ends with newline
                        if not content.endswith('\n'):
                            content += '\n'

                    if "multiple blank lines" in v.message.lower():
                        # Collapse multiple blank lines to single
                        import re as re_fix
                        content = re_fix.sub(r'\n{3,}', '\n\n', content)

                # Only write if content changed
                if content != original:
                    # Create backup
                    backup_path = path.with_suffix(path.suffix + '.bak')
                    backup_path.write_text(original)

                    # Write fixed content
                    path.write_text(content)
                    fixed_count += 1
                    print(f"  ✅ Fixed {file_path} (backup: {backup_path.name})")

            except Exception as e:
                print(f"  ❌ Error fixing {file_path}: {e}")

        print(f"\n📊 Auto-fix complete: {fixed_count} file(s) modified")

        if fixed_count > 0:
            print("\n💡 For import ordering and code formatting, run:")
            print("   pip install isort black && isort . && black .")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SAF Convention Checker")
    parser.add_argument(
        "--config",
        default="integration/config/conventions.yaml",
        help="Path to conventions.yaml",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix violations where possible",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed violation information",
    )

    args = parser.parse_args()

    # Initialize checker
    try:
        checker = ConventionChecker(args.config, args.repo_root)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 2

    # Run checks
    try:
        violation_count = checker.check_all()
    except Exception as e:
        print(f"❌ Error during checks: {e}", file=sys.stderr)
        return 2

    # Apply fixes if requested
    if args.fix and violation_count > 0:
        checker.auto_fix()

    # Report results
    has_violations = checker.report(verbose=args.verbose)

    # Exit with appropriate code
    return 1 if has_violations else 0

if __name__ == "__main__":
    sys.exit(main())
