#!/usr/bin/env python3
"""
Dependency Boundary Checker Tool
Version: 1.0.0
Last Updated: 2025-12-30
Owner: Critic
Classification: HIGH - Security Enforcement

Purpose: Automated SEC-032 enforcement for Anti-Corruption Layer (ACL) compliance.
Checks for vendor SDK isolation violations and dependency boundary breaches.

Issue S-06: Created to resolve ghost reference in Critic-ACL.md

Usage:
    python tools/dependency-boundary-checker.py [options]

Options:
    --path <path>       Path to check (default: src/)
    --config <file>     Config file with allowed boundaries (default: .acl-config.yaml)
    --strict            Fail on any violation (default: warn only)
    --output <format>   Output format: text, json, yaml (default: text)
    --verbose           Show detailed import analysis
    --help              Show this help message

Exit Codes:
    0: All checks passed
    1: Violations found (strict mode)
    2: Configuration error
"""

import argparse
import ast
import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

@dataclass
class BoundaryViolation:
    """Represents a single boundary violation."""
    file_path: str
    line_number: int
    imported_module: str
    violation_type: str
    message: str
    severity: str = "high"

@dataclass
class CheckResult:
    """Results from boundary check."""
    passed: bool
    violations: List[BoundaryViolation] = field(default_factory=list)
    files_checked: int = 0
    imports_analyzed: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract import statements."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.imports: List[Tuple[int, str, str]] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((node.lineno, alias.name, alias.asname or alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            full_name = f"{module}.{alias.name}" if module else alias.name
            self.imports.append((node.lineno, full_name, alias.asname or alias.name))
        self.generic_visit(node)

class DependencyBoundaryChecker:
    """
    Checks dependency boundaries for ACL compliance.

    SEC-032: Vendor SDK Isolation
    - Vendor SDKs must only be imported in adapters/ directory
    - Core business logic must not directly depend on vendor code
    - Adapters must use port interfaces (abstractions)
    """

    DEFAULT_VENDOR_PATTERNS = [
        r"^boto3", r"^botocore", r"^google\.cloud", r"^azure",
        r"^stripe", r"^twilio", r"^sendgrid", r"^slack_sdk",
        r"^openai", r"^anthropic", r"^redis", r"^pymongo",
        r"^psycopg2", r"^mysql", r"^sqlalchemy",
        r"^requests", r"^httpx", r"^aiohttp",
    ]

    DEFAULT_ADAPTER_DIRS = [
        "adapters", "infrastructure", "external", "vendors", "integrations",
    ]

    def __init__(self, config_path: Optional[str] = None):
        self.vendor_patterns = self.DEFAULT_VENDOR_PATTERNS.copy()
        self.adapter_dirs = self.DEFAULT_ADAPTER_DIRS.copy()
        self.allowed_exceptions: Dict[str, List[str]] = {}

        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        if not YAML_AVAILABLE:
            print(f"Warning: PyYAML not available", file=sys.stderr)
            return
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            if config:
                self.vendor_patterns = config.get("vendor_patterns", self.vendor_patterns)
                self.adapter_dirs = config.get("adapter_dirs", self.adapter_dirs)
                self.allowed_exceptions = config.get("allowed_exceptions", {})
        except Exception as e:
            print(f"Warning: Failed to load config: {e}", file=sys.stderr)

    def is_vendor_import(self, module_name: str) -> bool:
        return any(re.match(p, module_name) for p in self.vendor_patterns)

    def is_in_adapter_dir(self, file_path: str) -> bool:
        path_parts = Path(file_path).parts
        return any(d in path_parts for d in self.adapter_dirs)

    def is_exception_allowed(self, file_path: str, module_name: str) -> bool:
        for pattern, allowed in self.allowed_exceptions.items():
            if re.match(pattern, file_path):
                if any(re.match(a, module_name) for a in allowed):
                    return True
        return False

    def check_file(self, file_path: str) -> List[BoundaryViolation]:
        violations = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=file_path)
        except Exception as e:
            print(f"Warning: {file_path}: {e}", file=sys.stderr)
            return violations

        visitor = ImportVisitor(file_path)
        visitor.visit(tree)

        for line_no, module, _ in visitor.imports:
            if self.is_vendor_import(module):
                if not self.is_in_adapter_dir(file_path):
                    if not self.is_exception_allowed(file_path, module):
                        violations.append(BoundaryViolation(
                            file_path=file_path,
                            line_number=line_no,
                            imported_module=module,
                            violation_type="SEC-032",
                            message=f"Vendor SDK '{module}' imported outside adapter directory",
                        ))
        return violations

    def check_directory(self, path: str, verbose: bool = False) -> CheckResult:
        violations = []
        files_checked = 0
        path_obj = Path(path)

        if path_obj.is_file() and path.endswith(".py"):
            violations.extend(self.check_file(path))
            files_checked = 1
        else:
            for py_file in path_obj.rglob("*.py"):
                if verbose:
                    print(f"Checking: {py_file}", file=sys.stderr)
                violations.extend(self.check_file(str(py_file)))
                files_checked += 1

        return CheckResult(passed=len(violations) == 0, violations=violations, files_checked=files_checked)

def format_output(result: CheckResult, fmt: str = "text") -> str:
    if fmt == "json":
        return json.dumps({
            "passed": result.passed,
            "files_checked": result.files_checked,
            "violation_count": len(result.violations),
            "timestamp": result.timestamp,
            "violations": [{"file": v.file_path, "line": v.line_number, "module": v.imported_module,
                           "type": v.violation_type, "severity": v.severity, "message": v.message}
                          for v in result.violations]
        }, indent=2)
    elif fmt == "yaml" and YAML_AVAILABLE:
        return yaml.dump({
            "passed": result.passed, "files_checked": result.files_checked,
            "violation_count": len(result.violations), "timestamp": result.timestamp,
            "violations": [{"file": v.file_path, "line": v.line_number, "module": v.imported_module,
                           "type": v.violation_type, "severity": v.severity, "message": v.message}
                          for v in result.violations]
        }, default_flow_style=False)
    else:
        lines = ["=" * 60, "Dependency Boundary Check Results", "=" * 60,
                 f"Timestamp: {result.timestamp}", f"Files checked: {result.files_checked}",
                 f"Violations found: {len(result.violations)}", ""]
        if result.passed:
            lines.append("PASS: No boundary violations detected")
        else:
            lines.append("FAIL: Boundary violations detected")
            for i, v in enumerate(result.violations, 1):
                lines.extend([f"\n[{i}] {v.violation_type} ({v.severity.upper()})",
                             f"    File: {v.file_path}:{v.line_number}",
                             f"    Module: {v.imported_module}", f"    Issue: {v.message}"])
        lines.extend(["", "=" * 60])
        return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Check dependency boundaries for ACL compliance (SEC-032)")
    parser.add_argument("--path", default="src/", help="Path to check")
    parser.add_argument("--config", default=".acl-config.yaml", help="Config file")
    parser.add_argument("--strict", action="store_true", help="Fail on violation")
    parser.add_argument("--output", choices=["text", "json", "yaml"], default="text")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()
    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist", file=sys.stderr)
        sys.exit(2)

    checker = DependencyBoundaryChecker(config_path=args.config if os.path.exists(args.config) else None)
    result = checker.check_directory(args.path, verbose=args.verbose)
    print(format_output(result, args.output))
    sys.exit(1 if args.strict and not result.passed else 0)

if __name__ == "__main__":
    main()
