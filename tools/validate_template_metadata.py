#!/usr/bin/env python3
"""
Template Metadata Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Template Validation

Validates template metadata files for completeness and correctness.

Usage:
    python tools/validate_template_metadata.py <metadata_file>
    python tools/validate_template_metadata.py --check-all
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
class ValidationResult:
    """Result of validating a metadata file."""
    file: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    passed: bool

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    total_files: int
    valid: int
    warnings: int
    errors: int
    results: List[ValidationResult]
    passed: bool

# Required fields for template metadata (aligned with template_metadata_schema.yaml)
REQUIRED_FIELDS = {
    'template_id': str,
    'name': str,
    'version': str,
    'type': str,
    'created_at': str,
}

# Optional but recommended fields
RECOMMENDED_FIELDS = {
    'author': str,
    'created': str,
    'updated': str,
    'variables': list,
    'dependencies': list,
    'tags': list,
}

# Valid type values (aligned with template_metadata_schema.yaml type enum)
VALID_TYPES = {
    'task', 'service', 'library', 'plugin', 'integration',
    'component', 'utility', 'scaffold'
}

class TemplateMetadataValidator:
    """Validates template metadata files."""

    def __init__(self, schema_path: Path = None):
        self.schema_path = schema_path
        self.schema = self._load_schema() if schema_path else None

    def _load_schema(self) -> Optional[Dict]:
        """Load validation schema if provided."""
        if not self.schema_path or not self.schema_path.exists():
            return None
        with open(self.schema_path, 'r') as f:
            return yaml.safe_load(f)

    def validate_file(self, metadata_path: Path) -> ValidationResult:
        """Validate a single metadata file."""
        file_name = str(metadata_path)
        issues: List[str] = []
        warnings: List[str] = []

        if not metadata_path.exists():
            return ValidationResult(
                file=file_name,
                status="error",
                issues=[f"File not found: {metadata_path}"],
                warnings=[],
                passed=False
            )

        try:
            with open(metadata_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return ValidationResult(
                file=file_name,
                status="error",
                issues=[f"YAML parse error: {e}"],
                warnings=[],
                passed=False
            )

        if not isinstance(data, dict):
            return ValidationResult(
                file=file_name,
                status="error",
                issues=["Metadata must be a YAML mapping"],
                warnings=[],
                passed=False
            )

        # Check required fields
        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in data:
                issues.append(f"Missing required field: {field}")
            elif not isinstance(data[field], expected_type):
                issues.append(
                    f"Field '{field}' must be {expected_type.__name__}, "
                    f"got {type(data[field]).__name__}"
                )

        # Check recommended fields
        for field, expected_type in RECOMMENDED_FIELDS.items():
            if field not in data:
                warnings.append(f"Missing recommended field: {field}")
            elif not isinstance(data.get(field), expected_type):
                warnings.append(
                    f"Field '{field}' should be {expected_type.__name__}"
                )

        # Validate type value (schema-defined enum)
        if 'type' in data:
            type_val = data['type']
            if type_val not in VALID_TYPES:
                issues.append(
                    f"Invalid type '{type_val}'. Valid: {', '.join(sorted(VALID_TYPES))}"
                )

        # Validate template_id pattern (TPL-XX-NNN)
        if 'template_id' in data:
            import re
            template_id = data['template_id']
            if not re.match(r'^TPL-[A-Z]{2,4}-[0-9]{3}$', template_id):
                issues.append(
                    f"Invalid template_id format '{template_id}'. Expected: TPL-XX-NNN (e.g., TPL-BRK-001)"
                )

        # Validate version format
        if 'version' in data:
            version = data['version']
            if not self._is_valid_version(version):
                issues.append(f"Invalid version format: {version}")

        # Validate variables structure
        if 'variables' in data:
            var_issues = self._validate_variables(data['variables'])
            issues.extend(var_issues)

        # Determine status
        if issues:
            status = "error"
            passed = False
        elif warnings:
            status = "warning"
            passed = True
        else:
            status = "valid"
            passed = True

        return ValidationResult(
            file=file_name,
            status=status,
            issues=issues,
            warnings=warnings,
            passed=passed
        )

    def _is_valid_version(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        if not version:
            return False
        parts = str(version).split('.')
        if len(parts) < 2 or len(parts) > 3:
            return False
        try:
            for part in parts:
                int(part.split('-')[0])
            return True
        except ValueError:
            return False

    def _validate_variables(self, variables: Any) -> List[str]:
        """Validate variables structure."""
        issues = []

        if not isinstance(variables, list):
            issues.append("'variables' must be a list")
            return issues

        for i, var in enumerate(variables):
            if isinstance(var, str):
                # Simple variable name
                continue
            elif isinstance(var, dict):
                # Detailed variable definition
                if 'name' not in var:
                    issues.append(f"Variable {i} missing 'name' field")
            else:
                issues.append(f"Variable {i} must be string or mapping")

        return issues

    def validate_all(self, templates_dir: Path = None) -> ValidationReport:
        """Validate all metadata files in templates directory."""
        templates_dir = templates_dir or Path("templates")
        results = []

        for metadata_file in templates_dir.rglob("metadata.yaml"):
            result = self.validate_file(metadata_file)
            results.append(result)

        return self._generate_report(results)

    def _generate_report(self, results: List[ValidationResult]) -> ValidationReport:
        """Generate validation report."""
        valid_count = sum(1 for r in results if r.status == "valid")
        warning_count = sum(1 for r in results if r.status == "warning")
        error_count = sum(1 for r in results if r.status == "error")

        passed = error_count == 0

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_files=len(results),
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
    lines.append("Template Metadata Validation Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Files Checked: {report.total_files}")
    lines.append("")
    lines.append(f"Valid: {report.valid}")
    lines.append(f"Warnings: {report.warnings}")
    lines.append(f"Errors: {report.errors}")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"Status: {status}")
    lines.append("")

    for result in report.results:
        if result.issues or result.warnings:
            lines.append(f"{result.file} [{result.status.upper()}]:")
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
        "total_files": report.total_files,
        "valid": report.valid,
        "warnings": report.warnings,
        "errors": report.errors,
        "passed": report.passed,
        "results": [asdict(r) for r in report.results]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate template metadata files"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to metadata file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all metadata files in templates directory"
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path("templates"),
        help="Templates directory to search"
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

    validator = TemplateMetadataValidator()

    if args.check_all:
        report = validator.validate_all(args.templates_dir)
    elif args.file:
        result = validator.validate_file(Path(args.file))
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_files=1,
            valid=1 if result.status == "valid" else 0,
            warnings=1 if result.status == "warning" else 0,
            errors=1 if result.status == "error" else 0,
            results=[result],
            passed=result.passed
        )
    else:
        parser.print_help()
        sys.exit(1)

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
