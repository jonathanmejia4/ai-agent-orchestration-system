#!/usr/bin/env python3
"""
Variant Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Stage Gate Validator

Validates template variants for consistency and compatibility.
Variants are alternative versions of templates for different use cases.

Usage:
    python tools/variant_validator.py <template_path>
    python tools/variant_validator.py --check-all
    python tools/variant_validator.py --compare <variant1> <variant2>
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import yaml

@dataclass
class VariantInfo:
    """Information about a template variant."""
    name: str
    path: str
    base_template: Optional[str]
    version: str
    variables: Set[str]
    blocks: Set[str]
    metadata: Dict[str, Any]

@dataclass
class VariantValidationResult:
    """Result of validating a variant."""
    variant: str
    status: str  # valid, warning, error
    base_template: Optional[str]
    issues: List[str]
    compatibility: Dict[str, bool]
    passed: bool

@dataclass
class VariantComparisonResult:
    """Result of comparing two variants."""
    variant1: str
    variant2: str
    compatible: bool
    shared_variables: List[str]
    unique_to_v1: List[str]
    unique_to_v2: List[str]
    shared_blocks: List[str]
    issues: List[str]

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    total_variants: int
    valid: int
    warnings: int
    errors: int
    results: List[VariantValidationResult]
    passed: bool

class VariantValidator:
    """Validates template variants."""

    # Patterns for detecting template elements
    PATTERNS = {
        'variable': re.compile(r'{{\s*(\w+)(?:\.\w+)*\s*}}'),
        'block': re.compile(r'{%\s*block\s+(\w+)\s*%}'),
        'extends': re.compile(r'{%\s*extends\s+[\'"]([^\'"]+)[\'"]\s*%}'),
        'include': re.compile(r'{%\s*include\s+[\'"]([^\'"]+)[\'"]\s*%}'),
        'variant_marker': re.compile(r'#\s*VARIANT:\s*(\w+)'),
    }

    # Required elements for variant compatibility
    REQUIRED_COMPATIBILITY = {
        'same_base': True,
        'subset_variables': False,
        'same_blocks': False,
    }

    def __init__(self, registry_path: Path = None):
        self.registry_path = registry_path or Path("templates/registry.yaml")
        self.registry = self._load_registry()
        self.variants_cache: Dict[str, VariantInfo] = {}

    def _load_registry(self) -> Dict[str, Any]:
        """Load template registry."""
        if not self.registry_path.exists():
            return {"families": {}, "variants": {}}

        with open(self.registry_path, 'r') as f:
            return yaml.safe_load(f) or {"families": {}, "variants": {}}

    def _parse_template(self, template_path: Path) -> VariantInfo:
        """Parse a template to extract variant information."""
        if str(template_path) in self.variants_cache:
            return self.variants_cache[str(template_path)]

        try:
            with open(template_path, 'r') as f:
                content = f.read()
        except Exception:
            return VariantInfo(
                name=template_path.stem,
                path=str(template_path),
                base_template=None,
                version="unknown",
                variables=set(),
                blocks=set(),
                metadata={}
            )

        # Extract variant name
        variant_match = self.PATTERNS['variant_marker'].search(content)
        variant_name = variant_match.group(1) if variant_match else template_path.stem

        # Extract base template
        extends_match = self.PATTERNS['extends'].search(content)
        base_template = extends_match.group(1) if extends_match else None

        # Extract variables
        variables = set(self.PATTERNS['variable'].findall(content))

        # Extract blocks
        blocks = set(self.PATTERNS['block'].findall(content))

        # Extract metadata from YAML front matter or comments
        metadata = self._extract_metadata(content)
        version = metadata.get('version', 'unknown')

        info = VariantInfo(
            name=variant_name,
            path=str(template_path),
            base_template=base_template,
            version=version,
            variables=variables,
            blocks=blocks,
            metadata=metadata
        )

        self.variants_cache[str(template_path)] = info
        return info

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from template content."""
        metadata = {}

        # Try YAML front matter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass

        # Try version comment
        version_match = re.search(r'#\s*Version:\s*([\d.]+)', content, re.IGNORECASE)
        if version_match:
            metadata['version'] = version_match.group(1)

        return metadata

    def validate_variant(self, variant_path: Path) -> VariantValidationResult:
        """Validate a single variant."""
        variant_name = str(variant_path)
        issues: List[str] = []
        compatibility: Dict[str, bool] = {}

        if not variant_path.exists():
            return VariantValidationResult(
                variant=variant_name,
                status="error",
                base_template=None,
                issues=[f"Variant not found: {variant_path}"],
                compatibility={},
                passed=False
            )

        variant_info = self._parse_template(variant_path)

        # Check if base template exists
        if variant_info.base_template:
            base_path = variant_path.parent / variant_info.base_template
            if not base_path.exists():
                # Try relative to templates directory
                base_path = Path("templates") / variant_info.base_template
                if not base_path.exists():
                    issues.append(f"Base template not found: {variant_info.base_template}")
                    compatibility['base_exists'] = False
                else:
                    compatibility['base_exists'] = True
            else:
                compatibility['base_exists'] = True

            # Compare with base template
            if compatibility.get('base_exists', False):
                base_info = self._parse_template(base_path)
                base_issues = self._compare_with_base(variant_info, base_info)
                issues.extend(base_issues)
                compatibility['compatible_with_base'] = len(base_issues) == 0

        # Validate variable naming
        naming_issues = self._validate_variable_naming(variant_info.variables)
        issues.extend(naming_issues)
        compatibility['valid_naming'] = len(naming_issues) == 0

        # Validate blocks
        block_issues = self._validate_blocks(variant_info.blocks)
        issues.extend(block_issues)
        compatibility['valid_blocks'] = len(block_issues) == 0

        # Check version format
        if not self._is_valid_version(variant_info.version):
            issues.append(f"Invalid version format: {variant_info.version}")
            compatibility['valid_version'] = False
        else:
            compatibility['valid_version'] = True

        # Determine status
        if any("not found" in issue or "error" in issue.lower() for issue in issues):
            status = "error"
            passed = False
        elif issues:
            status = "warning"
            passed = True
        else:
            status = "valid"
            passed = True

        return VariantValidationResult(
            variant=variant_name,
            status=status,
            base_template=variant_info.base_template,
            issues=issues,
            compatibility=compatibility,
            passed=passed
        )

    def _compare_with_base(
        self,
        variant: VariantInfo,
        base: VariantInfo
    ) -> List[str]:
        """Compare variant with its base template."""
        issues = []

        # Check for missing base variables
        base_vars = base.variables
        variant_vars = variant.variables
        missing_vars = base_vars - variant_vars

        if missing_vars:
            issues.append(
                f"Variant missing base variables: {', '.join(sorted(missing_vars))}"
            )

        # Check for extra variables (warning only)
        extra_vars = variant_vars - base_vars
        if extra_vars:
            # Not necessarily an issue, just informational
            pass

        # Check block compatibility
        base_blocks = base.blocks
        variant_blocks = variant.blocks

        # Variant should override only existing blocks or add new ones
        # This is usually fine, so we just note differences

        return issues

    def _validate_variable_naming(self, variables: Set[str]) -> List[str]:
        """Validate variable naming conventions."""
        issues = []

        for var in variables:
            # Check for valid Python identifier
            if not var.isidentifier():
                issues.append(f"Invalid variable name: {var}")
            # Check for snake_case
            elif not re.match(r'^[a-z][a-z0-9_]*$', var):
                issues.append(f"Variable should use snake_case: {var}")

        return issues

    def _validate_blocks(self, blocks: Set[str]) -> List[str]:
        """Validate block definitions."""
        issues = []

        reserved_blocks = {'content', 'body', 'super'}
        for block in blocks:
            if block in reserved_blocks:
                issues.append(f"Reserved block name: {block}")
            elif not re.match(r'^[a-z][a-z0-9_]*$', block):
                issues.append(f"Block should use snake_case: {block}")

        return issues

    def _is_valid_version(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        if not version or version == "unknown":
            return False

        parts = version.split('.')
        if len(parts) < 2 or len(parts) > 3:
            return False

        try:
            for part in parts:
                base = part.split('-')[0]
                int(base)
            return True
        except ValueError:
            return False

    def compare_variants(
        self,
        variant1_path: Path,
        variant2_path: Path
    ) -> VariantComparisonResult:
        """Compare two variants for compatibility."""
        v1_info = self._parse_template(variant1_path)
        v2_info = self._parse_template(variant2_path)

        issues = []

        # Compare variables
        shared_vars = v1_info.variables & v2_info.variables
        unique_v1 = v1_info.variables - v2_info.variables
        unique_v2 = v2_info.variables - v1_info.variables

        # Compare blocks
        shared_blocks = v1_info.blocks & v2_info.blocks

        # Check base template compatibility
        if v1_info.base_template != v2_info.base_template:
            issues.append(
                f"Different base templates: {v1_info.base_template} vs {v2_info.base_template}"
            )

        # Determine compatibility
        compatible = len(issues) == 0 and len(shared_vars) > 0

        return VariantComparisonResult(
            variant1=str(variant1_path),
            variant2=str(variant2_path),
            compatible=compatible,
            shared_variables=sorted(shared_vars),
            unique_to_v1=sorted(unique_v1),
            unique_to_v2=sorted(unique_v2),
            shared_blocks=sorted(shared_blocks),
            issues=issues
        )

    def validate_all(self) -> ValidationReport:
        """Validate all variants in registry."""
        results = []

        for family_name, family_data in self.registry.get("families", {}).items():
            family_path = Path(family_data.get("path", f"templates/{family_name}"))
            if family_path.exists():
                # Find variant files (files with variant markers or in variants/ subdirectory)
                for variant_file in family_path.rglob("*.jinja2"):
                    result = self.validate_variant(variant_file)
                    results.append(result)

        return self._generate_report(results)

    def _generate_report(self, results: List[VariantValidationResult]) -> ValidationReport:
        """Generate validation report."""
        valid_count = sum(1 for r in results if r.status == "valid")
        warning_count = sum(1 for r in results if r.status == "warning")
        error_count = sum(1 for r in results if r.status == "error")

        passed = error_count == 0

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_variants=len(results),
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
    lines.append("Variant Validation Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Variants Checked: {report.total_variants}")
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
            lines.append(f"{result.variant} [{result.status.upper()}]:")
            if result.base_template:
                lines.append(f"  Base: {result.base_template}")
            for issue in result.issues:
                lines.append(f"  - {issue}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_comparison(result: VariantComparisonResult) -> str:
    """Format comparison result as text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Variant Comparison")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Variant 1: {result.variant1}")
    lines.append(f"Variant 2: {result.variant2}")
    lines.append("")
    lines.append(f"Compatible: {'Yes' if result.compatible else 'No'}")
    lines.append("")
    lines.append(f"Shared Variables ({len(result.shared_variables)}):")
    for var in result.shared_variables[:10]:
        lines.append(f"  - {var}")
    if len(result.shared_variables) > 10:
        lines.append(f"  ... and {len(result.shared_variables) - 10} more")
    lines.append("")
    lines.append(f"Unique to Variant 1 ({len(result.unique_to_v1)}):")
    for var in result.unique_to_v1[:5]:
        lines.append(f"  - {var}")
    if len(result.unique_to_v1) > 5:
        lines.append(f"  ... and {len(result.unique_to_v1) - 5} more")
    lines.append("")
    lines.append(f"Unique to Variant 2 ({len(result.unique_to_v2)}):")
    for var in result.unique_to_v2[:5]:
        lines.append(f"  - {var}")
    if len(result.unique_to_v2) > 5:
        lines.append(f"  ... and {len(result.unique_to_v2) - 5} more")
    lines.append("")

    if result.issues:
        lines.append("Issues:")
        for issue in result.issues:
            lines.append(f"  - {issue}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: ValidationReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_variants": report.total_variants,
        "valid": report.valid,
        "warnings": report.warnings,
        "errors": report.errors,
        "passed": report.passed,
        "results": [
            {
                "variant": r.variant,
                "status": r.status,
                "base_template": r.base_template,
                "issues": r.issues,
                "compatibility": r.compatibility,
                "passed": r.passed
            }
            for r in report.results
        ]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate template variants"
    )

    parser.add_argument(
        "variant",
        nargs="?",
        help="Path to variant file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all registered variants"
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("VARIANT1", "VARIANT2"),
        help="Compare two variants"
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

    validator = VariantValidator(args.registry)

    if args.compare:
        result = validator.compare_variants(
            Path(args.compare[0]),
            Path(args.compare[1])
        )
        output = format_comparison(result)
        if args.output:
            args.output.write_text(output)
            print(f"Comparison written to {args.output}")
        else:
            print(output)
        sys.exit(0 if result.compatible else 1)

    if args.check_all:
        report = validator.validate_all()
    elif args.variant:
        result = validator.validate_variant(Path(args.variant))
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_variants=1,
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
