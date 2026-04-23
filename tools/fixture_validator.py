#!/usr/bin/env python3
"""
Fixture Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Test Quality

Validates test fixtures for correctness and consistency.

Usage:
    python tools/fixture_validator.py
    python tools/fixture_validator.py --fixtures-dir tests/fixtures
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

@dataclass
class FixtureValidation:
    """Result of validating a fixture file."""
    file: str
    status: str  # valid, warning, error
    fixture_type: str  # yaml, json, python
    issues: List[str]
    warnings: List[str]
    passed: bool

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    total_fixtures: int
    valid: int
    warnings: int
    errors: int
    results: List[FixtureValidation]
    passed: bool

class FixtureValidator:
    """Validates test fixture files."""

    def __init__(self, fixtures_dir: Path = None):
        self.fixtures_dir = fixtures_dir or Path("tests/fixtures")

    def validate_yaml(self, path: Path) -> FixtureValidation:
        """Validate a YAML fixture file."""
        issues = []
        warnings = []

        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)

            if data is None:
                warnings.append("Empty fixture file")
            elif not isinstance(data, (dict, list)):
                warnings.append(f"Unusual fixture type: {type(data).__name__}")

            # Check for common issues
            content = path.read_text()
            if '{{' in content or '}}' in content:
                warnings.append("Contains template syntax - may be unprocessed template")

            if 'TODO' in content or 'FIXME' in content:
                warnings.append("Contains TODO/FIXME markers")

        except yaml.YAMLError as e:
            issues.append(f"Invalid YAML: {e}")
        except Exception as e:
            issues.append(f"Error reading file: {e}")

        status = "error" if issues else ("warning" if warnings else "valid")
        passed = len(issues) == 0

        return FixtureValidation(
            file=str(path),
            status=status,
            fixture_type="yaml",
            issues=issues,
            warnings=warnings,
            passed=passed
        )

    def validate_json(self, path: Path) -> FixtureValidation:
        """Validate a JSON fixture file."""
        issues = []
        warnings = []

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            if data is None:
                warnings.append("Empty fixture file")
            elif not isinstance(data, (dict, list)):
                warnings.append(f"Unusual fixture type: {type(data).__name__}")

        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON: {e}")
        except Exception as e:
            issues.append(f"Error reading file: {e}")

        status = "error" if issues else ("warning" if warnings else "valid")
        passed = len(issues) == 0

        return FixtureValidation(
            file=str(path),
            status=status,
            fixture_type="json",
            issues=issues,
            warnings=warnings,
            passed=passed
        )

    def validate_python(self, path: Path) -> FixtureValidation:
        """Validate a Python fixture file."""
        issues = []
        warnings = []

        try:
            # Check syntax
            with open(path, 'r') as f:
                source = f.read()

            compile(source, path, 'exec')

            # Check for pytest fixtures
            if '@pytest.fixture' not in source and 'fixture' not in source.lower():
                warnings.append("No pytest fixtures found")

            # Check for common issues
            if 'import *' in source:
                warnings.append("Uses wildcard import")

        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
        except Exception as e:
            issues.append(f"Error reading file: {e}")

        status = "error" if issues else ("warning" if warnings else "valid")
        passed = len(issues) == 0

        return FixtureValidation(
            file=str(path),
            status=status,
            fixture_type="python",
            issues=issues,
            warnings=warnings,
            passed=passed
        )

    def validate_file(self, path: Path) -> FixtureValidation:
        """Validate a single fixture file."""
        if path.suffix in ['.yaml', '.yml']:
            return self.validate_yaml(path)
        elif path.suffix == '.json':
            return self.validate_json(path)
        elif path.suffix == '.py':
            return self.validate_python(path)
        else:
            return FixtureValidation(
                file=str(path),
                status="warning",
                fixture_type="unknown",
                issues=[],
                warnings=[f"Unknown fixture type: {path.suffix}"],
                passed=True
            )

    def validate_all(self) -> ValidationReport:
        """Validate all fixture files."""
        results = []

        if not self.fixtures_dir.exists():
            return ValidationReport(
                timestamp=datetime.now().isoformat(),
                total_fixtures=0,
                valid=0,
                warnings=0,
                errors=0,
                results=[],
                passed=True
            )

        # Find all fixture files
        for pattern in ['*.yaml', '*.yml', '*.json', '*.py']:
            for path in self.fixtures_dir.rglob(pattern):
                if '__pycache__' not in str(path):
                    result = self.validate_file(path)
                    results.append(result)

        return self._generate_report(results)

    def _generate_report(self, results: List[FixtureValidation]) -> ValidationReport:
        """Generate validation report."""
        valid_count = sum(1 for r in results if r.status == "valid")
        warning_count = sum(1 for r in results if r.status == "warning")
        error_count = sum(1 for r in results if r.status == "error")

        passed = error_count == 0

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_fixtures=len(results),
            valid=valid_count,
            warnings=warning_count,
            errors=error_count,
            results=results,
            passed=passed
        )

def format_text(report: ValidationReport) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Fixture Validation Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Total Fixtures: {report.total_fixtures}")
    lines.append(f"Valid: {report.valid}")
    lines.append(f"Warnings: {report.warnings}")
    lines.append(f"Errors: {report.errors}")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    icon = "✓" if report.passed else "✗"
    lines.append(f"{icon} Status: {status}")
    lines.append("")

    # Show files with issues
    for result in report.results:
        if result.issues or result.warnings:
            lines.append(f"{result.file} [{result.fixture_type}]:")
            for issue in result.issues:
                lines.append(f"  ERROR: {issue}")
            for warning in result.warnings:
                lines.append(f"  WARN: {warning}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: ValidationReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_fixtures": report.total_fixtures,
        "valid": report.valid,
        "warnings": report.warnings,
        "errors": report.errors,
        "passed": report.passed,
        "results": [asdict(r) for r in report.results]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate test fixtures"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Specific fixture file to validate"
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path("tests/fixtures"),
        help="Fixtures directory"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file"
    )

    args = parser.parse_args()

    validator = FixtureValidator(args.fixtures_dir)

    if args.file:
        result = validator.validate_file(Path(args.file))
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_fixtures=1,
            valid=1 if result.status == "valid" else 0,
            warnings=1 if result.status == "warning" else 0,
            errors=1 if result.status == "error" else 0,
            results=[result],
            passed=result.passed
        )
    else:
        report = validator.validate_all()

    # Format output
    if args.format == "json":
        output = format_json(report)
    else:
        output = format_text(report)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    sys.exit(0 if report.passed else 1)

if __name__ == "__main__":
    main()
