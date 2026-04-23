#!/usr/bin/env python3
"""
Plugin Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Plugin System

Validates the system plugins for compatibility and correctness.

Usage:
    python tools/plugin_validator.py <plugin_path>
    python tools/plugin_validator.py --check-all
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import yaml

@dataclass
class PluginInfo:
    """Information about a plugin."""
    name: str
    path: str
    version: str
    plugin_type: str  # adapter, hook, extension
    entry_point: Optional[str]
    dependencies: List[str]
    exports: List[str]

@dataclass
class ValidationResult:
    """Result of validating a plugin."""
    plugin: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    info: Optional[PluginInfo]
    passed: bool

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    total_plugins: int
    valid: int
    warnings: int
    errors: int
    results: List[ValidationResult]
    passed: bool

# Required plugin structure
REQUIRED_EXPORTS = ['register', 'unregister']
REQUIRED_METADATA = ['name', 'version', 'plugin_type']

class PluginValidator:
    """Validates the system plugins."""

    def __init__(self, plugins_dir: Path = None):
        self.plugins_dir = plugins_dir or Path("plugins")

    def validate_plugin(self, plugin_path: Path) -> ValidationResult:
        """Validate a single plugin."""
        issues: List[str] = []
        warnings: List[str] = []
        info: Optional[PluginInfo] = None

        if not plugin_path.exists():
            return ValidationResult(
                plugin=str(plugin_path),
                status="error",
                issues=[f"Plugin not found: {plugin_path}"],
                warnings=[],
                info=None,
                passed=False
            )

        # Determine plugin type
        if plugin_path.is_dir():
            result = self._validate_package_plugin(plugin_path, issues, warnings)
        else:
            result = self._validate_single_file_plugin(plugin_path, issues, warnings)

        info = result

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
            plugin=str(plugin_path),
            status=status,
            issues=issues,
            warnings=warnings,
            info=info,
            passed=passed
        )

    def _validate_package_plugin(
        self,
        plugin_path: Path,
        issues: List[str],
        warnings: List[str]
    ) -> Optional[PluginInfo]:
        """Validate a package-style plugin (directory with __init__.py)."""
        init_file = plugin_path / "__init__.py"

        if not init_file.exists():
            issues.append("Package plugin missing __init__.py")
            return None

        # Check for metadata file
        metadata_file = plugin_path / "plugin.yaml"
        if metadata_file.exists():
            metadata = self._load_metadata(metadata_file, issues)
        else:
            metadata = {}
            warnings.append("Missing plugin.yaml metadata file")

        # Parse __init__.py
        exports = self._get_exports(init_file, issues)

        # Check required exports
        for export in REQUIRED_EXPORTS:
            if export not in exports:
                warnings.append(f"Missing recommended export: {export}")

        return PluginInfo(
            name=metadata.get('name', plugin_path.name),
            path=str(plugin_path),
            version=metadata.get('version', 'unknown'),
            plugin_type=metadata.get('plugin_type', 'unknown'),
            entry_point=str(init_file),
            dependencies=metadata.get('dependencies', []),
            exports=list(exports)
        )

    def _validate_single_file_plugin(
        self,
        plugin_path: Path,
        issues: List[str],
        warnings: List[str]
    ) -> Optional[PluginInfo]:
        """Validate a single-file plugin."""
        if plugin_path.suffix != '.py':
            issues.append("Plugin must be a Python file (.py)")
            return None

        # Parse the file
        exports = self._get_exports(plugin_path, issues)

        # Extract metadata from docstring or comments
        metadata = self._extract_metadata(plugin_path)

        # Check required exports
        for export in REQUIRED_EXPORTS:
            if export not in exports:
                warnings.append(f"Missing recommended export: {export}")

        return PluginInfo(
            name=metadata.get('name', plugin_path.stem),
            path=str(plugin_path),
            version=metadata.get('version', 'unknown'),
            plugin_type=metadata.get('plugin_type', 'unknown'),
            entry_point=str(plugin_path),
            dependencies=metadata.get('dependencies', []),
            exports=list(exports)
        )

    def _load_metadata(self, path: Path, issues: List[str]) -> Dict[str, Any]:
        """Load plugin metadata from YAML file."""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            issues.append(f"Invalid metadata YAML: {e}")
            return {}

    def _get_exports(self, path: Path, issues: List[str]) -> Set[str]:
        """Get exported names from a Python file."""
        exports = set()

        try:
            with open(path, 'r') as f:
                source = f.read()

            tree = ast.parse(source)

            # Get top-level definitions
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.startswith('_'):
                        exports.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith('_'):
                        exports.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id == '__all__':
                                # Parse __all__ list
                                if isinstance(node.value, ast.List):
                                    for elt in node.value.elts:
                                        if isinstance(elt, ast.Constant):
                                            exports.add(elt.value)

        except SyntaxError as e:
            issues.append(f"Syntax error in plugin: {e}")
        except Exception as e:
            issues.append(f"Error parsing plugin: {e}")

        return exports

    def _extract_metadata(self, path: Path) -> Dict[str, Any]:
        """Extract metadata from file docstring or comments."""
        metadata = {}

        try:
            with open(path, 'r') as f:
                content = f.read()

            # Look for metadata in comments
            for line in content.split('\n')[:20]:
                line = line.strip()
                if line.startswith('#'):
                    line = line[1:].strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip()
                        if key in ['name', 'version', 'plugin_type']:
                            metadata[key] = value

        except Exception:
            pass

        return metadata

    def validate_all(self) -> ValidationReport:
        """Validate all plugins in plugins directory."""
        results = []

        if not self.plugins_dir.exists():
            return ValidationReport(
                timestamp=datetime.now().isoformat(),
                total_plugins=0,
                valid=0,
                warnings=0,
                errors=0,
                results=[],
                passed=True
            )

        # Find all plugins
        for item in self.plugins_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                result = self.validate_plugin(item)
                results.append(result)
            elif item.suffix == '.py' and not item.name.startswith('_'):
                result = self.validate_plugin(item)
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
            total_plugins=len(results),
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
    lines.append("Plugin Validation Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Total Plugins: {report.total_plugins}")
    lines.append(f"Valid: {report.valid}")
    lines.append(f"Warnings: {report.warnings}")
    lines.append(f"Errors: {report.errors}")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"Status: {status}")
    lines.append("")

    for result in report.results:
        icon = "✓" if result.passed else "✗"
        lines.append(f"{icon} {result.plugin} [{result.status}]")

        if result.info:
            lines.append(f"    Type: {result.info.plugin_type}")
            lines.append(f"    Version: {result.info.version}")
            lines.append(f"    Exports: {', '.join(result.info.exports[:5])}")

        for issue in result.issues:
            lines.append(f"    ERROR: {issue}")
        for warning in result.warnings:
            lines.append(f"    WARN: {warning}")

        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: ValidationReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_plugins": report.total_plugins,
        "valid": report.valid,
        "warnings": report.warnings,
        "errors": report.errors,
        "passed": report.passed,
        "results": [
            {
                "plugin": r.plugin,
                "status": r.status,
                "issues": r.issues,
                "warnings": r.warnings,
                "info": asdict(r.info) if r.info else None,
                "passed": r.passed
            }
            for r in report.results
        ]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate the system plugins"
    )

    parser.add_argument(
        "plugin",
        nargs="?",
        help="Path to plugin to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all plugins in plugins directory"
    )
    parser.add_argument(
        "--plugins-dir",
        type=Path,
        default=Path("plugins"),
        help="Plugins directory"
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

    validator = PluginValidator(args.plugins_dir)

    if args.check_all:
        report = validator.validate_all()
    elif args.plugin:
        result = validator.validate_plugin(Path(args.plugin))
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_plugins=1,
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
