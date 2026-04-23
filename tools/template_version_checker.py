#!/usr/bin/env python3
"""
Template Version Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Stage Gate Validator

Validates template versions for compatibility and deprecation status.
Used as a stage gate validator in integration/config/stage-gates.yaml.

Usage:
    python tools/template_version_checker.py <template_path>
    python tools/template_version_checker.py --check-all
    python tools/template_version_checker.py --check-deprecations
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml

@dataclass
class VersionCheckResult:
    """Result of a version check."""
    template: str
    current_version: str
    status: str  # valid, deprecated, expired, invalid
    message: str
    deprecation_date: Optional[str] = None
    replacement: Optional[str] = None
    compatible_versions: List[str] = None

    def __post_init__(self):
        if self.compatible_versions is None:
            self.compatible_versions = []

@dataclass
class VersionCheckReport:
    """Complete version check report."""
    timestamp: str
    total_checked: int
    valid: int
    deprecated: int
    expired: int
    invalid: int
    results: List[VersionCheckResult]
    passed: bool

class TemplateVersionChecker:
    """Checks template versions for compatibility and deprecation."""

    def __init__(self, registry_path: Path = None):
        self.registry_path = registry_path or Path("templates/registry.yaml")
        self.registry = self._load_registry()
        self.results: List[VersionCheckResult] = []

    def _load_registry(self) -> Dict[str, Any]:
        """Load template registry."""
        if not self.registry_path.exists():
            return {"templates": {}, "deprecated": {}}

        with open(self.registry_path, 'r') as f:
            return yaml.safe_load(f) or {"templates": {}, "deprecated": {}}

    def check_template(self, template_path: Path) -> VersionCheckResult:
        """Check a single template's version status."""
        template_name = str(template_path)

        # Check if template exists
        if not template_path.exists():
            return VersionCheckResult(
                template=template_name,
                current_version="unknown",
                status="invalid",
                message=f"Template not found: {template_path}"
            )

        # Try to read template metadata
        metadata = self._get_template_metadata(template_path)

        if not metadata:
            return VersionCheckResult(
                template=template_name,
                current_version="unknown",
                status="invalid",
                message="No metadata found in template"
            )

        version = metadata.get("version", "unknown")

        # Check if deprecated
        deprecated_info = self.registry.get("deprecated", {}).get(template_name)
        if deprecated_info:
            deprecation_date = deprecated_info.get("deprecated_on")
            expiration_date = deprecated_info.get("expires_on")
            replacement = deprecated_info.get("replacement")

            # Check if expired
            if expiration_date:
                exp_date = datetime.fromisoformat(expiration_date)
                if datetime.now() > exp_date:
                    return VersionCheckResult(
                        template=template_name,
                        current_version=version,
                        status="expired",
                        message=f"Template expired on {expiration_date}",
                        deprecation_date=deprecation_date,
                        replacement=replacement
                    )

            return VersionCheckResult(
                template=template_name,
                current_version=version,
                status="deprecated",
                message=f"Template deprecated on {deprecation_date}",
                deprecation_date=deprecation_date,
                replacement=replacement
            )

        # Validate version format
        if not self._is_valid_semver(version):
            return VersionCheckResult(
                template=template_name,
                current_version=version,
                status="invalid",
                message=f"Invalid version format: {version}"
            )

        return VersionCheckResult(
            template=template_name,
            current_version=version,
            status="valid",
            message="Template version is valid"
        )

    def _get_template_metadata(self, template_path: Path) -> Optional[Dict]:
        """Extract metadata from template file."""
        try:
            with open(template_path, 'r') as f:
                content = f.read()

            # Try YAML front matter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    return yaml.safe_load(parts[1])

            # Try to parse as YAML
            if template_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(content)
                if isinstance(data, dict):
                    return data

            # Look for version comment
            for line in content.split('\n')[:10]:
                if 'version' in line.lower():
                    if ':' in line:
                        version = line.split(':')[1].strip().strip('"\'')
                        return {"version": version}

            return None
        except Exception:
            return None

    def _is_valid_semver(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        if not version or version == "unknown":
            return False

        parts = version.split('.')
        if len(parts) < 2 or len(parts) > 3:
            return False

        try:
            for part in parts:
                # Handle pre-release versions like 1.0.0-beta
                base = part.split('-')[0]
                int(base)
            return True
        except ValueError:
            return False

    def check_all_templates(self) -> VersionCheckReport:
        """Check all registered templates."""
        results = []

        # Check templates in registry
        for family_name, family_data in self.registry.get("families", {}).items():
            family_path = Path(family_data.get("path", f"templates/{family_name}"))
            if family_path.exists():
                for template_file in family_path.rglob("*.yaml"):
                    result = self.check_template(template_file)
                    results.append(result)
                for template_file in family_path.rglob("*.jinja2"):
                    result = self.check_template(template_file)
                    results.append(result)

        return self._generate_report(results)

    def check_deprecations(self) -> VersionCheckReport:
        """Check only deprecated templates."""
        results = []

        deprecated = self.registry.get("deprecated", {})
        for template_name in deprecated:
            template_path = Path(template_name)
            result = self.check_template(template_path)
            results.append(result)

        return self._generate_report(results)

    def _generate_report(self, results: List[VersionCheckResult]) -> VersionCheckReport:
        """Generate version check report."""
        valid_count = sum(1 for r in results if r.status == "valid")
        deprecated_count = sum(1 for r in results if r.status == "deprecated")
        expired_count = sum(1 for r in results if r.status == "expired")
        invalid_count = sum(1 for r in results if r.status == "invalid")

        # Pass if no expired or invalid templates
        passed = expired_count == 0 and invalid_count == 0

        return VersionCheckReport(
            timestamp=datetime.now().isoformat(),
            total_checked=len(results),
            valid=valid_count,
            deprecated=deprecated_count,
            expired=expired_count,
            invalid=invalid_count,
            results=results,
            passed=passed
        )

def format_text(report: VersionCheckReport) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Template Version Check Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Total Checked: {report.total_checked}")
    lines.append("")
    lines.append(f"Valid: {report.valid}")
    lines.append(f"Deprecated: {report.deprecated}")
    lines.append(f"Expired: {report.expired}")
    lines.append(f"Invalid: {report.invalid}")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"Status: {status}")
    lines.append("")

    if report.deprecated > 0:
        lines.append("Deprecated Templates:")
        for r in report.results:
            if r.status == "deprecated":
                lines.append(f"  - {r.template} (v{r.current_version})")
                if r.replacement:
                    lines.append(f"    Replacement: {r.replacement}")
        lines.append("")

    if report.expired > 0 or report.invalid > 0:
        lines.append("Issues:")
        for r in report.results:
            if r.status in ["expired", "invalid"]:
                lines.append(f"  - [{r.status.upper()}] {r.template}: {r.message}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: VersionCheckReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_checked": report.total_checked,
        "valid": report.valid,
        "deprecated": report.deprecated,
        "expired": report.expired,
        "invalid": report.invalid,
        "passed": report.passed,
        "results": [asdict(r) for r in report.results]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Check template versions for compatibility and deprecation"
    )

    parser.add_argument(
        "template",
        nargs="?",
        help="Path to template file to check"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Check all registered templates"
    )
    parser.add_argument(
        "--check-deprecations",
        action="store_true",
        help="Check only deprecated templates"
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

    checker = TemplateVersionChecker(args.registry)

    if args.check_all:
        report = checker.check_all_templates()
    elif args.check_deprecations:
        report = checker.check_deprecations()
    elif args.template:
        result = checker.check_template(Path(args.template))
        report = VersionCheckReport(
            timestamp=datetime.now().isoformat(),
            total_checked=1,
            valid=1 if result.status == "valid" else 0,
            deprecated=1 if result.status == "deprecated" else 0,
            expired=1 if result.status == "expired" else 0,
            invalid=1 if result.status == "invalid" else 0,
            results=[result],
            passed=result.status in ["valid", "deprecated"]
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
