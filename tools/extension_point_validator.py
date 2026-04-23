#!/usr/bin/env python3
"""
Extension Point Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Stage Gate Validator

Validates that templates properly define and use extension points.
Extension points allow customization without modifying core templates.

Usage:
    python tools/extension_point_validator.py <template_path>
    python tools/extension_point_validator.py --check-all
    python tools/extension_point_validator.py --validate-hooks
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import yaml

@dataclass
class ExtensionPoint:
    """Represents an extension point definition."""
    name: str
    type: str  # hook, slot, override, plugin
    location: str  # file:line
    required: bool = False
    default: Optional[str] = None
    description: Optional[str] = None

@dataclass
class ExtensionUsage:
    """Represents usage of an extension point."""
    name: str
    location: str
    valid: bool
    message: str

@dataclass
class ValidationResult:
    """Result of extension point validation."""
    template: str
    status: str  # valid, warning, error
    extension_points: List[ExtensionPoint]
    usages: List[ExtensionUsage]
    issues: List[str]
    passed: bool

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    total_templates: int
    total_extension_points: int
    valid: int
    warnings: int
    errors: int
    results: List[ValidationResult]
    passed: bool

class ExtensionPointValidator:
    """Validates extension points in templates."""

    # Patterns for detecting extension points
    PATTERNS = {
        # Jinja2 block extension points
        'jinja_block': re.compile(r'{%\s*block\s+(\w+)\s*%}'),
        # YAML extension hooks
        'yaml_hook': re.compile(r'^\s*(\w+)_hook:\s*(.*)$', re.MULTILINE),
        # Extension point markers
        'marker': re.compile(r'#\s*EXTENSION[_-]POINT:\s*(\w+)'),
        # Plugin slots
        'slot': re.compile(r'{{\s*slot\s*\(\s*[\'"](\w+)[\'"]\s*\)'),
        # Override markers
        'override': re.compile(r'#\s*@override\s*:\s*(\w+)'),
    }

    # Required extension points by template family
    REQUIRED_EXTENSIONS = {
        'code': ['imports', 'class_body', 'function_body'],
        'config': ['custom_settings', 'overrides'],
        'tests': ['setup', 'teardown', 'custom_assertions'],
        'adapters': ['request_transform', 'response_transform'],
    }

    def __init__(self, registry_path: Path = None):
        self.registry_path = registry_path or Path("templates/registry.yaml")
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load template registry."""
        if not self.registry_path.exists():
            return {"families": {}}

        with open(self.registry_path, 'r') as f:
            return yaml.safe_load(f) or {"families": {}}

    def validate_template(self, template_path: Path) -> ValidationResult:
        """Validate extension points in a template."""
        template_name = str(template_path)
        extension_points: List[ExtensionPoint] = []
        usages: List[ExtensionUsage] = []
        issues: List[str] = []

        if not template_path.exists():
            return ValidationResult(
                template=template_name,
                status="error",
                extension_points=[],
                usages=[],
                issues=[f"Template not found: {template_path}"],
                passed=False
            )

        try:
            with open(template_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            return ValidationResult(
                template=template_name,
                status="error",
                extension_points=[],
                usages=[],
                issues=[f"Error reading template: {e}"],
                passed=False
            )

        # Find all extension points
        extension_points = self._find_extension_points(content, lines, template_name)

        # Validate extension point definitions
        for ep in extension_points:
            validation = self._validate_extension_point(ep)
            usages.append(validation)
            if not validation.valid:
                issues.append(validation.message)

        # Check for required extension points based on family
        family = self._get_template_family(template_path)
        if family and family in self.REQUIRED_EXTENSIONS:
            required = set(self.REQUIRED_EXTENSIONS[family])
            defined = {ep.name for ep in extension_points}
            missing = required - defined

            for name in missing:
                issues.append(f"Missing required extension point: {name}")

        # Check for duplicate extension points
        names = [ep.name for ep in extension_points]
        duplicates = [name for name in names if names.count(name) > 1]
        for dup in set(duplicates):
            issues.append(f"Duplicate extension point: {dup}")

        # Determine status
        if any("error" in issue.lower() or "missing" in issue.lower() for issue in issues):
            status = "error"
            passed = False
        elif issues:
            status = "warning"
            passed = True
        else:
            status = "valid"
            passed = True

        return ValidationResult(
            template=template_name,
            status=status,
            extension_points=extension_points,
            usages=usages,
            issues=issues,
            passed=passed
        )

    def _find_extension_points(
        self,
        content: str,
        lines: List[str],
        template_name: str
    ) -> List[ExtensionPoint]:
        """Find all extension points in template content."""
        points = []

        # Find Jinja2 blocks
        for match in self.PATTERNS['jinja_block'].finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            points.append(ExtensionPoint(
                name=match.group(1),
                type="block",
                location=f"{template_name}:{line_num}",
                required=False
            ))

        # Find YAML hooks
        for match in self.PATTERNS['yaml_hook'].finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            points.append(ExtensionPoint(
                name=match.group(1),
                type="hook",
                location=f"{template_name}:{line_num}",
                required=False,
                default=match.group(2).strip() if match.group(2) else None
            ))

        # Find extension point markers
        for match in self.PATTERNS['marker'].finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            points.append(ExtensionPoint(
                name=match.group(1),
                type="marker",
                location=f"{template_name}:{line_num}",
                required=True
            ))

        # Find plugin slots
        for match in self.PATTERNS['slot'].finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            points.append(ExtensionPoint(
                name=match.group(1),
                type="slot",
                location=f"{template_name}:{line_num}",
                required=False
            ))

        # Find override markers
        for match in self.PATTERNS['override'].finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            points.append(ExtensionPoint(
                name=match.group(1),
                type="override",
                location=f"{template_name}:{line_num}",
                required=False
            ))

        return points

    def _validate_extension_point(self, ep: ExtensionPoint) -> ExtensionUsage:
        """Validate a single extension point."""
        # Check naming convention
        if not re.match(r'^[a-z][a-z0-9_]*$', ep.name):
            return ExtensionUsage(
                name=ep.name,
                location=ep.location,
                valid=False,
                message=f"Invalid extension point name: {ep.name} (use snake_case)"
            )

        # Check for reserved names
        reserved = ['init', 'main', 'base', 'parent', 'self', 'super']
        if ep.name in reserved:
            return ExtensionUsage(
                name=ep.name,
                location=ep.location,
                valid=False,
                message=f"Reserved extension point name: {ep.name}"
            )

        return ExtensionUsage(
            name=ep.name,
            location=ep.location,
            valid=True,
            message="Valid extension point"
        )

    def _get_template_family(self, template_path: Path) -> Optional[str]:
        """Determine template family from path."""
        parts = template_path.parts

        for family in ['code', 'config', 'tests', 'adapters', 'docs', 'schemas']:
            if family in parts:
                return family

        return None

    def validate_all(self) -> ValidationReport:
        """Validate all templates in registry."""
        results = []

        for family_name, family_data in self.registry.get("families", {}).items():
            family_path = Path(family_data.get("path", f"templates/{family_name}"))
            if family_path.exists():
                for template_file in family_path.rglob("*.jinja2"):
                    result = self.validate_template(template_file)
                    results.append(result)
                for template_file in family_path.rglob("*.yaml"):
                    if 'metadata' not in template_file.name:
                        result = self.validate_template(template_file)
                        results.append(result)

        return self._generate_report(results)

    def validate_hooks(self) -> ValidationReport:
        """Validate hook-type extension points only."""
        results = []

        for family_name, family_data in self.registry.get("families", {}).items():
            family_path = Path(family_data.get("path", f"templates/{family_name}"))
            if family_path.exists():
                for template_file in family_path.rglob("*.yaml"):
                    result = self.validate_template(template_file)
                    # Filter to only hook-related issues
                    hook_points = [ep for ep in result.extension_points if ep.type == "hook"]
                    if hook_points:
                        results.append(result)

        return self._generate_report(results)

    def _generate_report(self, results: List[ValidationResult]) -> ValidationReport:
        """Generate validation report."""
        total_points = sum(len(r.extension_points) for r in results)
        valid_count = sum(1 for r in results if r.status == "valid")
        warning_count = sum(1 for r in results if r.status == "warning")
        error_count = sum(1 for r in results if r.status == "error")

        passed = error_count == 0

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_templates=len(results),
            total_extension_points=total_points,
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
    lines.append("Extension Point Validation Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Templates Checked: {report.total_templates}")
    lines.append(f"Extension Points Found: {report.total_extension_points}")
    lines.append("")
    lines.append(f"Valid: {report.valid}")
    lines.append(f"Warnings: {report.warnings}")
    lines.append(f"Errors: {report.errors}")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"Status: {status}")
    lines.append("")

    # Show issues
    for result in report.results:
        if result.issues:
            lines.append(f"{result.template}:")
            for issue in result.issues:
                lines.append(f"  - {issue}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: ValidationReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_templates": report.total_templates,
        "total_extension_points": report.total_extension_points,
        "valid": report.valid,
        "warnings": report.warnings,
        "errors": report.errors,
        "passed": report.passed,
        "results": [
            {
                "template": r.template,
                "status": r.status,
                "extension_points": [asdict(ep) for ep in r.extension_points],
                "issues": r.issues,
                "passed": r.passed
            }
            for r in report.results
        ]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate extension points in templates"
    )

    parser.add_argument(
        "template",
        nargs="?",
        help="Path to template file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all registered templates"
    )
    parser.add_argument(
        "--validate-hooks",
        action="store_true",
        help="Validate only hook-type extension points"
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("templates/registry.yaml"),
        help="Path to template registry"
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

    validator = ExtensionPointValidator(args.registry)

    if args.check_all:
        report = validator.validate_all()
    elif args.validate_hooks:
        report = validator.validate_hooks()
    elif args.template:
        result = validator.validate_template(Path(args.template))
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_templates=1,
            total_extension_points=len(result.extension_points),
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

    # Exit code
    sys.exit(0 if report.passed else 1)

if __name__ == "__main__":
    main()
