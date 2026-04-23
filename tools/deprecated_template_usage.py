#!/usr/bin/env python3
"""
Deprecated Template Usage Detector
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Template Lifecycle

Scans codebase for usage of deprecated templates and provides migration guidance.
Helps track deprecation timelines and ensures smooth template transitions.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

@dataclass
class DeprecatedTemplate:
    """Information about a deprecated template."""
    name: str
    family: str
    version: str
    deprecated_date: datetime
    removal_date: Optional[datetime]
    replacement: Optional[str]
    migration_guide: Optional[str]
    reason: str

@dataclass
class TemplateUsage:
    """A usage of a template in the codebase."""
    template_name: str
    file_path: str
    line_number: int
    context: str
    is_deprecated: bool = False
    deprecation_info: Optional[DeprecatedTemplate] = None

@dataclass
class ScanResult:
    """Result of scanning for deprecated template usage."""
    total_usages: int
    deprecated_usages: int
    files_scanned: int
    usages: List[TemplateUsage] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class DeprecatedTemplateDetector:
    """Detects usage of deprecated templates in codebase."""

    # Patterns to find template references
    TEMPLATE_PATTERNS = [
        # Jinja2 extends/includes
        re.compile(r'{%\s*extends\s+["\']([^"\']+)["\']'),
        re.compile(r'{%\s*include\s+["\']([^"\']+)["\']'),
        # YAML template references
        re.compile(r'template:\s*["\']?([a-zA-Z0-9_\-./]+)["\']?'),
        re.compile(r'uses:\s*["\']?([a-zA-Z0-9_\-./]+\.jinja2)["\']?'),
        # Python template loading
        re.compile(r'get_template\(["\']([^"\']+)["\']'),
        re.compile(r'load_template\(["\']([^"\']+)["\']'),
        # Template registry references
        re.compile(r'template_id:\s*["\']?([a-zA-Z0-9_\-./]+)["\']?'),
    ]

    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialize detector.

        Args:
            registry_path: Path to template registry YAML
        """
        self.deprecated_templates: Dict[str, DeprecatedTemplate] = {}
        self.registry_path = registry_path

        if registry_path:
            self._load_registry(registry_path)

    def _load_registry(self, registry_path: str):
        """Load deprecated templates from registry."""
        try:
            import yaml
            with open(registry_path, 'r') as f:
                registry = yaml.safe_load(f)

            # Look for deprecated entries
            for family_name, family_data in registry.get('families', {}).items():
                for template in family_data.get('templates', []):
                    if template.get('status') == 'deprecated':
                        name = template.get('name', '')
                        deprecated_date = template.get('deprecated_date')
                        if isinstance(deprecated_date, str):
                            deprecated_date = datetime.fromisoformat(deprecated_date)

                        removal_date = template.get('removal_date')
                        if isinstance(removal_date, str):
                            removal_date = datetime.fromisoformat(removal_date)

                        self.deprecated_templates[name] = DeprecatedTemplate(
                            name=name,
                            family=family_name,
                            version=template.get('version', ''),
                            deprecated_date=deprecated_date or datetime.now(),
                            removal_date=removal_date,
                            replacement=template.get('replacement'),
                            migration_guide=template.get('migration_guide'),
                            reason=template.get('deprecation_reason', 'No reason provided')
                        )
        except Exception as e:
            print(f"Warning: Failed to load registry: {e}", file=sys.stderr)

    def add_deprecated_template(
        self,
        name: str,
        family: str = "unknown",
        reason: str = "Deprecated",
        replacement: Optional[str] = None,
        removal_days: int = 30
    ):
        """Manually add a deprecated template."""
        self.deprecated_templates[name] = DeprecatedTemplate(
            name=name,
            family=family,
            version="",
            deprecated_date=datetime.now(),
            removal_date=datetime.now() + timedelta(days=removal_days),
            replacement=replacement,
            migration_guide=None,
            reason=reason
        )

    def scan_file(self, file_path: str) -> List[TemplateUsage]:
        """
        Scan a file for template usages.

        Args:
            file_path: Path to file to scan

        Returns:
            List of template usages found
        """
        usages = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return usages

        for line_num, line in enumerate(lines, 1):
            for pattern in self.TEMPLATE_PATTERNS:
                matches = pattern.findall(line)
                for template_name in matches:
                    # Normalize template name
                    template_name = template_name.strip()

                    # Check if deprecated
                    is_deprecated = template_name in self.deprecated_templates
                    deprecation_info = self.deprecated_templates.get(template_name)

                    # Also check without extension
                    base_name = Path(template_name).stem
                    if not is_deprecated and base_name in self.deprecated_templates:
                        is_deprecated = True
                        deprecation_info = self.deprecated_templates.get(base_name)

                    usages.append(TemplateUsage(
                        template_name=template_name,
                        file_path=file_path,
                        line_number=line_num,
                        context=line.strip()[:100],
                        is_deprecated=is_deprecated,
                        deprecation_info=deprecation_info
                    ))

        return usages

    def scan_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None,
        recursive: bool = True
    ) -> ScanResult:
        """
        Scan a directory for template usages.

        Args:
            directory: Directory to scan
            extensions: File extensions to check
            exclude_dirs: Directories to exclude
            recursive: Whether to scan recursively

        Returns:
            ScanResult with all usages found
        """
        if extensions is None:
            extensions = ['.py', '.yaml', '.yml', '.html', '.jinja2', '.j2', '.md']
        if exclude_dirs is None:
            exclude_dirs = ['node_modules', '.git', '__pycache__', 'venv', '.venv']

        result = ScanResult(
            total_usages=0,
            deprecated_usages=0,
            files_scanned=0
        )

        path = Path(directory)
        if not path.exists():
            result.warnings.append(f"Directory not found: {directory}")
            return result

        pattern = '**/*' if recursive else '*'
        for file_path in path.glob(pattern):
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            if file_path.is_file() and file_path.suffix.lower() in extensions:
                result.files_scanned += 1
                usages = self.scan_file(str(file_path))

                for usage in usages:
                    result.total_usages += 1
                    if usage.is_deprecated:
                        result.deprecated_usages += 1
                    result.usages.append(usage)

        return result

    def generate_migration_report(self, result: ScanResult) -> str:
        """
        Generate a migration report for deprecated usages.

        Args:
            result: Scan result

        Returns:
            Markdown-formatted report
        """
        lines = [
            "# Deprecated Template Usage Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Summary",
            f"- Files scanned: {result.files_scanned}",
            f"- Total template usages: {result.total_usages}",
            f"- Deprecated usages: {result.deprecated_usages}",
            ""
        ]

        if result.deprecated_usages == 0:
            lines.append("No deprecated template usages found.")
            return '\n'.join(lines)

        # Group by template
        by_template: Dict[str, List[TemplateUsage]] = {}
        for usage in result.usages:
            if usage.is_deprecated:
                if usage.template_name not in by_template:
                    by_template[usage.template_name] = []
                by_template[usage.template_name].append(usage)

        lines.append("## Deprecated Templates in Use")
        lines.append("")

        for template_name, usages in sorted(by_template.items()):
            info = usages[0].deprecation_info

            lines.append(f"### {template_name}")
            lines.append("")

            if info:
                lines.append(f"- **Reason:** {info.reason}")
                lines.append(f"- **Deprecated:** {info.deprecated_date.strftime('%Y-%m-%d')}")
                if info.removal_date:
                    days_left = (info.removal_date - datetime.now()).days
                    lines.append(f"- **Removal Date:** {info.removal_date.strftime('%Y-%m-%d')} "
                               f"({days_left} days remaining)")
                if info.replacement:
                    lines.append(f"- **Replacement:** `{info.replacement}`")
                if info.migration_guide:
                    lines.append(f"- **Migration Guide:** {info.migration_guide}")

            lines.append("")
            lines.append(f"**Usages ({len(usages)}):**")
            lines.append("")

            for usage in usages[:10]:  # Limit to 10 examples
                lines.append(f"- `{usage.file_path}:{usage.line_number}`")

            if len(usages) > 10:
                lines.append(f"- ... and {len(usages) - 10} more")

            lines.append("")

        return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect usage of deprecated templates"
    )
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("-r", "--registry", help="Path to template registry")
    parser.add_argument("-e", "--extensions", nargs="+",
                        help="File extensions to scan")
    parser.add_argument("--exclude", nargs="+",
                        help="Directories to exclude")
    parser.add_argument("--no-recursive", action="store_true",
                        help="Don't scan recursively")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("--report", help="Write migration report to file")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    # Initialize detector
    detector = DeprecatedTemplateDetector(registry_path=args.registry)

    # Scan
    if os.path.isdir(args.path):
        result = detector.scan_directory(
            args.path,
            extensions=args.extensions,
            exclude_dirs=args.exclude,
            recursive=not args.no_recursive
        )
    else:
        usages = detector.scan_file(args.path)
        result = ScanResult(
            total_usages=len(usages),
            deprecated_usages=sum(1 for u in usages if u.is_deprecated),
            files_scanned=1,
            usages=usages
        )

    # Output
    if args.json:
        output = {
            "files_scanned": result.files_scanned,
            "total_usages": result.total_usages,
            "deprecated_usages": result.deprecated_usages,
            "usages": [{
                "template": u.template_name,
                "file": u.file_path,
                "line": u.line_number,
                "deprecated": u.is_deprecated,
                "replacement": u.deprecation_info.replacement if u.deprecation_info else None
            } for u in result.usages if u.is_deprecated or args.verbose]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Files scanned: {result.files_scanned}")
        print(f"Total template usages: {result.total_usages}")
        print(f"Deprecated usages: {result.deprecated_usages}")

        if result.deprecated_usages > 0:
            print("\nDeprecated template usages:")
            for usage in result.usages:
                if usage.is_deprecated:
                    replacement = ""
                    if usage.deprecation_info and usage.deprecation_info.replacement:
                        replacement = f" -> {usage.deprecation_info.replacement}"
                    print(f"  {usage.file_path}:{usage.line_number}: "
                          f"{usage.template_name}{replacement}")

    # Write report if requested
    if args.report:
        report = detector.generate_migration_report(result)
        with open(args.report, 'w') as f:
            f.write(report)
        print(f"\nMigration report written to: {args.report}")

    sys.exit(1 if result.deprecated_usages > 0 else 0)

if __name__ == "__main__":
    main()
