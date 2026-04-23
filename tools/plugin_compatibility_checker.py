#!/usr/bin/env python3
"""
the system Plugin Compatibility Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: PM
Classification: HIGH - Stage 2 Gate Tool

Validates plugin compatibility for the system Stage 2 gate.
Ensures plugins meet interface contracts and version requirements.

Usage:
    python tools/plugin_compatibility_checker.py check --plugin auth_plugin
    python tools/plugin_compatibility_checker.py check-all
    python tools/plugin_compatibility_checker.py validate --manifest plugin.yaml
    python tools/plugin_compatibility_checker.py report
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

@dataclass
class CompatibilityIssue:
    """Represents a compatibility issue."""
    severity: str  # critical, warning, info
    category: str
    message: str
    location: Optional[str] = None
    fix_suggestion: Optional[str] = None

@dataclass
class PluginManifest:
    """Represents a plugin manifest."""
    plugin_id: str
    version: str
    name: str
    description: str
    author: str
    saf_version_min: str
    saf_version_max: Optional[str]
    dependencies: List[Dict[str, str]]
    interfaces: List[str]
    extension_points: List[str]
    exports: List[str]
    imports: List[str]
    config_schema: Optional[Dict[str, Any]] = None

@dataclass
class CompatibilityReport:
    """Compatibility check report."""
    plugin_id: str
    timestamp: str
    passed: bool
    saf_compatible: bool
    interface_compatible: bool
    dependency_compatible: bool
    issues: List[CompatibilityIssue] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plugin_id': self.plugin_id,
            'timestamp': self.timestamp,
            'passed': self.passed,
            'saf_compatible': self.saf_compatible,
            'interface_compatible': self.interface_compatible,
            'dependency_compatible': self.dependency_compatible,
            'issues': [
                {
                    'severity': i.severity,
                    'category': i.category,
                    'message': i.message,
                    'location': i.location,
                    'fix_suggestion': i.fix_suggestion
                }
                for i in self.issues
            ],
            'warnings': self.warnings,
            'errors': self.errors
        }

class PluginCompatibilityChecker:
    """Checks plugin compatibility with the system."""

    # Current the system version
    SYSTEM_VERSION = "1.0.0"

    # Supported interface versions
    SUPPORTED_INTERFACES = {
        'IAuthProvider': ['1.0', '1.1', '1.2'],
        'IStorageAdapter': ['1.0', '1.1'],
        'INotificationChannel': ['1.0'],
        'IMetricsCollector': ['1.0', '1.1'],
        'ILogAggregator': ['1.0'],
        'IValidator': ['1.0', '1.1', '1.2'],
        'ITransformer': ['1.0'],
        'ICacheProvider': ['1.0', '1.1'],
        'IQueueHandler': ['1.0'],
        'IEventEmitter': ['1.0', '1.1']
    }

    # Required manifest fields
    REQUIRED_MANIFEST_FIELDS = [
        'plugin_id', 'version', 'name', 'description',
        'saf_version_min', 'interfaces'
    ]

    # Extension point registry
    VALID_EXTENSION_POINTS = [
        'pre_build', 'post_build', 'pre_test', 'post_test',
        'pre_deploy', 'post_deploy', 'on_error', 'on_success',
        'pre_review', 'post_review', 'on_escalation',
        'pre_gate', 'post_gate', 'on_state_change'
    ]

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the compatibility checker."""
        self.project_root = project_root or Path.cwd()
        self.plugins_dir = self.project_root / "plugins"
        self.reports_dir = self.project_root / "reports" / "plugin_compatibility"
        self.registry_file = self.project_root / "integration" / "config" / "plugin_registry.yaml"

        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Load plugin registry if exists
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load plugin registry."""
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}

    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse semantic version string."""
        match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (0, 0, 0)

    def _version_compatible(self, required: str, current: str) -> bool:
        """Check if current version satisfies requirement."""
        req_parts = self._parse_version(required)
        cur_parts = self._parse_version(current)

        # Major version must match, minor can be equal or higher
        return (cur_parts[0] == req_parts[0] and
                cur_parts[1] >= req_parts[1])

    def _version_in_range(self, version: str, min_ver: str,
                          max_ver: Optional[str] = None) -> bool:
        """Check if version is within range."""
        ver = self._parse_version(version)
        min_v = self._parse_version(min_ver)

        if ver < min_v:
            return False

        if max_ver:
            max_v = self._parse_version(max_ver)
            if ver > max_v:
                return False

        return True

    def load_manifest(self, manifest_path: Path) -> Optional[PluginManifest]:
        """Load and parse plugin manifest."""
        if not manifest_path.exists():
            return None

        with open(manifest_path, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        return PluginManifest(
            plugin_id=data.get('plugin_id', ''),
            version=data.get('version', '0.0.0'),
            name=data.get('name', ''),
            description=data.get('description', ''),
            author=data.get('author', 'unknown'),
            saf_version_min=data.get('saf_version_min', '1.0.0'),
            saf_version_max=data.get('saf_version_max'),
            dependencies=data.get('dependencies', []),
            interfaces=data.get('interfaces', []),
            extension_points=data.get('extension_points', []),
            exports=data.get('exports', []),
            imports=data.get('imports', []),
            config_schema=data.get('config_schema')
        )

    def check_manifest_validity(self, manifest: PluginManifest) -> List[CompatibilityIssue]:
        """Check if manifest has all required fields."""
        issues = []

        for field in self.REQUIRED_MANIFEST_FIELDS:
            value = getattr(manifest, field, None)
            if not value:
                issues.append(CompatibilityIssue(
                    severity='critical',
                    category='manifest',
                    message=f"Missing required field: {field}",
                    fix_suggestion=f"Add '{field}' to plugin manifest"
                ))

        # Check plugin_id format
        if manifest.plugin_id and not re.match(r'^[a-z][a-z0-9_]*$', manifest.plugin_id):
            issues.append(CompatibilityIssue(
                severity='critical',
                category='manifest',
                message=f"Invalid plugin_id format: {manifest.plugin_id}",
                fix_suggestion="Use lowercase letters, numbers, and underscores. Must start with letter."
            ))

        # Check version format
        if manifest.version and not re.match(r'^\d+\.\d+\.\d+', manifest.version):
            issues.append(CompatibilityIssue(
                severity='critical',
                category='manifest',
                message=f"Invalid version format: {manifest.version}",
                fix_suggestion="Use semantic versioning: X.Y.Z"
            ))

        return issues

    def check_saf_compatibility(self, manifest: PluginManifest) -> List[CompatibilityIssue]:
        """Check the system version compatibility."""
        issues = []

        if not self._version_in_range(
            self.SYSTEM_VERSION,
            manifest.saf_version_min,
            manifest.saf_version_max
        ):
            issues.append(CompatibilityIssue(
                severity='critical',
                category='saf_version',
                message=f"Plugin requires the system {manifest.saf_version_min}"
                        f"{'-' + manifest.saf_version_max if manifest.saf_version_max else '+'}",
                fix_suggestion=f"Current the system version is {self.SYSTEM_VERSION}. Update plugin or the system."
            ))

        return issues

    def check_interface_compatibility(self, manifest: PluginManifest) -> List[CompatibilityIssue]:
        """Check interface compatibility."""
        issues = []

        for interface_spec in manifest.interfaces:
            # Parse interface:version
            parts = interface_spec.split(':')
            interface_name = parts[0]
            interface_version = parts[1] if len(parts) > 1 else '1.0'

            if interface_name not in self.SUPPORTED_INTERFACES:
                issues.append(CompatibilityIssue(
                    severity='critical',
                    category='interface',
                    message=f"Unknown interface: {interface_name}",
                    location=interface_spec,
                    fix_suggestion=f"Valid interfaces: {list(self.SUPPORTED_INTERFACES.keys())}"
                ))
                continue

            supported_versions = self.SUPPORTED_INTERFACES[interface_name]
            if interface_version not in supported_versions:
                issues.append(CompatibilityIssue(
                    severity='critical',
                    category='interface',
                    message=f"Unsupported version {interface_version} for {interface_name}",
                    location=interface_spec,
                    fix_suggestion=f"Supported versions: {supported_versions}"
                ))

        return issues

    def check_extension_points(self, manifest: PluginManifest) -> List[CompatibilityIssue]:
        """Check extension point validity."""
        issues = []

        for ext_point in manifest.extension_points:
            if ext_point not in self.VALID_EXTENSION_POINTS:
                issues.append(CompatibilityIssue(
                    severity='warning',
                    category='extension_point',
                    message=f"Unknown extension point: {ext_point}",
                    fix_suggestion=f"Valid extension points: {self.VALID_EXTENSION_POINTS}"
                ))

        return issues

    def check_dependencies(self, manifest: PluginManifest) -> List[CompatibilityIssue]:
        """Check dependency availability and compatibility."""
        issues = []

        for dep in manifest.dependencies:
            dep_id = dep.get('plugin_id')
            dep_version = dep.get('version', '*')

            if not dep_id:
                issues.append(CompatibilityIssue(
                    severity='critical',
                    category='dependency',
                    message="Dependency missing plugin_id",
                    fix_suggestion="Specify plugin_id for each dependency"
                ))
                continue

            # Check if dependency is in registry
            if dep_id not in self.registry.get('plugins', {}):
                issues.append(CompatibilityIssue(
                    severity='warning',
                    category='dependency',
                    message=f"Dependency not in registry: {dep_id}",
                    location=f"{dep_id}@{dep_version}",
                    fix_suggestion="Ensure dependency is installed and registered"
                ))
                continue

            # Check version compatibility
            registered = self.registry['plugins'][dep_id]
            if dep_version != '*':
                if not self._version_compatible(dep_version, registered.get('version', '0.0.0')):
                    issues.append(CompatibilityIssue(
                        severity='critical',
                        category='dependency',
                        message=f"Incompatible dependency version: {dep_id}",
                        location=f"Required: {dep_version}, Found: {registered.get('version')}",
                        fix_suggestion="Update dependency or adjust version requirement"
                    ))

        return issues

    def check_circular_dependencies(self, manifest: PluginManifest,
                                    visited: Optional[Set[str]] = None) -> List[CompatibilityIssue]:
        """Check for circular dependencies."""
        issues = []
        visited = visited or set()

        if manifest.plugin_id in visited:
            issues.append(CompatibilityIssue(
                severity='critical',
                category='dependency',
                message=f"Circular dependency detected: {manifest.plugin_id}",
                fix_suggestion="Remove circular dependency chain"
            ))
            return issues

        visited.add(manifest.plugin_id)

        for dep in manifest.dependencies:
            dep_id = dep.get('plugin_id')
            if dep_id and dep_id in self.registry.get('plugins', {}):
                dep_manifest_path = self.plugins_dir / dep_id / "plugin.yaml"
                dep_manifest = self.load_manifest(dep_manifest_path)
                if dep_manifest:
                    issues.extend(self.check_circular_dependencies(dep_manifest, visited.copy()))

        return issues

    def check_exports_imports(self, manifest: PluginManifest) -> List[CompatibilityIssue]:
        """Check export/import compatibility."""
        issues = []

        # Check if imports can be satisfied
        for imp in manifest.imports:
            # Parse import: plugin_id.export_name
            parts = imp.split('.')
            if len(parts) < 2:
                issues.append(CompatibilityIssue(
                    severity='warning',
                    category='import',
                    message=f"Invalid import format: {imp}",
                    fix_suggestion="Use format: plugin_id.export_name"
                ))
                continue

            source_plugin = parts[0]
            export_name = '.'.join(parts[1:])

            if source_plugin not in self.registry.get('plugins', {}):
                issues.append(CompatibilityIssue(
                    severity='warning',
                    category='import',
                    message=f"Import source not found: {source_plugin}",
                    location=imp,
                    fix_suggestion=f"Ensure {source_plugin} is installed"
                ))

        return issues

    def check_config_schema(self, manifest: PluginManifest) -> List[CompatibilityIssue]:
        """Validate config schema if present."""
        issues = []

        if not manifest.config_schema:
            return issues

        schema = manifest.config_schema

        # Check for required schema fields
        if 'type' not in schema:
            issues.append(CompatibilityIssue(
                severity='warning',
                category='config_schema',
                message="Config schema missing 'type' field",
                fix_suggestion="Add 'type: object' to config_schema"
            ))

        if schema.get('type') == 'object' and 'properties' not in schema:
            issues.append(CompatibilityIssue(
                severity='info',
                category='config_schema',
                message="Config schema has no properties defined",
                fix_suggestion="Define configuration properties"
            ))

        return issues

    def check_plugin(self, plugin_id: str) -> CompatibilityReport:
        """
        Run all compatibility checks for a plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            CompatibilityReport with all findings
        """
        manifest_path = self.plugins_dir / plugin_id / "plugin.yaml"
        manifest = self.load_manifest(manifest_path)

        timestamp = datetime.utcnow().isoformat() + "Z"

        if not manifest:
            return CompatibilityReport(
                plugin_id=plugin_id,
                timestamp=timestamp,
                passed=False,
                saf_compatible=False,
                interface_compatible=False,
                dependency_compatible=False,
                issues=[CompatibilityIssue(
                    severity='critical',
                    category='manifest',
                    message=f"Plugin manifest not found: {manifest_path}",
                    fix_suggestion="Create plugin.yaml in plugin directory"
                )],
                errors=1
            )

        all_issues = []

        # Run all checks
        all_issues.extend(self.check_manifest_validity(manifest))
        all_issues.extend(self.check_saf_compatibility(manifest))
        all_issues.extend(self.check_interface_compatibility(manifest))
        all_issues.extend(self.check_extension_points(manifest))
        all_issues.extend(self.check_dependencies(manifest))
        all_issues.extend(self.check_circular_dependencies(manifest))
        all_issues.extend(self.check_exports_imports(manifest))
        all_issues.extend(self.check_config_schema(manifest))

        # Count issues by severity
        errors = sum(1 for i in all_issues if i.severity == 'critical')
        warnings = sum(1 for i in all_issues if i.severity == 'warning')

        # Determine compatibility status
        saf_issues = [i for i in all_issues if i.category == 'saf_version' and i.severity == 'critical']
        interface_issues = [i for i in all_issues if i.category == 'interface' and i.severity == 'critical']
        dep_issues = [i for i in all_issues if i.category == 'dependency' and i.severity == 'critical']

        report = CompatibilityReport(
            plugin_id=plugin_id,
            timestamp=timestamp,
            passed=errors == 0,
            saf_compatible=len(saf_issues) == 0,
            interface_compatible=len(interface_issues) == 0,
            dependency_compatible=len(dep_issues) == 0,
            issues=all_issues,
            warnings=warnings,
            errors=errors
        )

        # Save report
        self._save_report(report)

        return report

    def check_all_plugins(self) -> Dict[str, CompatibilityReport]:
        """Check all plugins in the plugins directory."""
        reports = {}

        if not self.plugins_dir.exists():
            return reports

        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and (plugin_dir / "plugin.yaml").exists():
                report = self.check_plugin(plugin_dir.name)
                reports[plugin_dir.name] = report

        return reports

    def _save_report(self, report: CompatibilityReport) -> None:
        """Save compatibility report."""
        report_file = self.reports_dir / f"{report.plugin_id}_compatibility.yaml"

        with open(report_file, 'w') as f:
            yaml.dump(report.to_dict(), f, default_flow_style=False)

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate summary report of all plugin compatibility."""
        reports = self.check_all_plugins()

        summary = {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'saf_version': self.SYSTEM_VERSION,
            'total_plugins': len(reports),
            'compatible': sum(1 for r in reports.values() if r.passed),
            'incompatible': sum(1 for r in reports.values() if not r.passed),
            'total_errors': sum(r.errors for r in reports.values()),
            'total_warnings': sum(r.warnings for r in reports.values()),
            'plugins': {
                pid: {
                    'passed': r.passed,
                    'errors': r.errors,
                    'warnings': r.warnings
                }
                for pid, r in reports.items()
            }
        }

        # Save summary
        summary_file = self.reports_dir / "compatibility_summary.yaml"
        with open(summary_file, 'w') as f:
            yaml.dump(summary, f, default_flow_style=False)

        return summary

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Plugin Compatibility Checker',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Check command
    check_parser = subparsers.add_parser('check', help='Check specific plugin')
    check_parser.add_argument('--plugin', '-p', required=True, help='Plugin ID')
    check_parser.add_argument('--format', choices=['text', 'yaml', 'json'], default='text')

    # Check-all command
    check_all_parser = subparsers.add_parser('check-all', help='Check all plugins')
    check_all_parser.add_argument('--format', choices=['text', 'yaml', 'json'], default='text')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate manifest file')
    validate_parser.add_argument('--manifest', '-m', required=True, help='Manifest file path')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate summary report')
    report_parser.add_argument('--format', choices=['text', 'yaml', 'json'], default='text')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    checker = PluginCompatibilityChecker()

    try:
        if args.command == 'check':
            report = checker.check_plugin(args.plugin)

            if args.format == 'text':
                status = "PASSED" if report.passed else "FAILED"
                print(f"\nPlugin Compatibility Check: {args.plugin}")
                print("=" * 50)
                print(f"Status: {status}")
                print(f"the system Compatible: {'Yes' if report.saf_compatible else 'No'}")
                print(f"Interface Compatible: {'Yes' if report.interface_compatible else 'No'}")
                print(f"Dependency Compatible: {'Yes' if report.dependency_compatible else 'No'}")
                print(f"Errors: {report.errors}, Warnings: {report.warnings}")

                if report.issues:
                    print("\nIssues:")
                    for issue in report.issues:
                        icon = {'critical': 'X', 'warning': '!', 'info': 'i'}[issue.severity]
                        print(f"  [{icon}] [{issue.category}] {issue.message}")
                        if issue.fix_suggestion:
                            print(f"      Fix: {issue.fix_suggestion}")
            elif args.format == 'json':
                print(json.dumps(report.to_dict(), indent=2))
            else:
                print(yaml.dump(report.to_dict(), default_flow_style=False))

            sys.exit(0 if report.passed else 1)

        elif args.command == 'check-all':
            reports = checker.check_all_plugins()

            if args.format == 'text':
                print("\nPlugin Compatibility Summary")
                print("=" * 60)
                print(f"{'Plugin':<30} {'Status':<10} {'Errors':<10} {'Warnings':<10}")
                print("-" * 60)
                for pid, report in reports.items():
                    status = "PASS" if report.passed else "FAIL"
                    print(f"{pid:<30} {status:<10} {report.errors:<10} {report.warnings:<10}")

                total = len(reports)
                passed = sum(1 for r in reports.values() if r.passed)
                print("-" * 60)
                print(f"Total: {total}, Passed: {passed}, Failed: {total - passed}")
            elif args.format == 'json':
                print(json.dumps({k: v.to_dict() for k, v in reports.items()}, indent=2))
            else:
                print(yaml.dump({k: v.to_dict() for k, v in reports.items()}, default_flow_style=False))

        elif args.command == 'validate':
            manifest = checker.load_manifest(Path(args.manifest))
            if not manifest:
                print(f"Error: Cannot load manifest from {args.manifest}")
                sys.exit(1)

            issues = checker.check_manifest_validity(manifest)
            if issues:
                print("Manifest validation failed:")
                for issue in issues:
                    print(f"  [{issue.severity}] {issue.message}")
                sys.exit(1)
            else:
                print("Manifest is valid")

        elif args.command == 'report':
            summary = checker.generate_summary_report()

            if args.format == 'text':
                print("\nPlugin Compatibility Report")
                print("=" * 50)
                print(f"the system Version: {summary['saf_version']}")
                print(f"Total Plugins: {summary['total_plugins']}")
                print(f"Compatible: {summary['compatible']}")
                print(f"Incompatible: {summary['incompatible']}")
                print(f"Total Errors: {summary['total_errors']}")
                print(f"Total Warnings: {summary['total_warnings']}")
            elif args.format == 'json':
                print(json.dumps(summary, indent=2))
            else:
                print(yaml.dump(summary, default_flow_style=False))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
