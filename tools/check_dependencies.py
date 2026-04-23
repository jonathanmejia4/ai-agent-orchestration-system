#!/usr/bin/env python3
"""
Dependency Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Dependency Management

Checks project dependencies for issues, conflicts, and security vulnerabilities.

Usage:
    python tools/check_dependencies.py
    python tools/check_dependencies.py --check-security
    python tools/check_dependencies.py --check-outdated
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

@dataclass
class Dependency:
    """Represents a project dependency."""
    name: str
    version: str
    required_version: str
    source: str  # requirements.txt, pyproject.toml, etc.
    is_dev: bool = False
    has_update: bool = False
    latest_version: Optional[str] = None
    vulnerabilities: List[str] = None

    def __post_init__(self):
        if self.vulnerabilities is None:
            self.vulnerabilities = []

@dataclass
class DependencyReport:
    """Complete dependency check report."""
    timestamp: str
    total_dependencies: int
    outdated: int
    vulnerable: int
    conflicts: int
    dependencies: List[Dependency]
    issues: List[str]
    passed: bool

class DependencyChecker:
    """Checks project dependencies for issues."""

    def __init__(self):
        self.dependencies: List[Dependency] = []
        self.issues: List[str] = []

    def load_requirements(self, path: Path = None) -> List[Dependency]:
        """Load dependencies from requirements.txt."""
        path = path or Path("requirements.txt")
        deps = []

        if not path.exists():
            return deps

        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Parse requirement line
                match = re.match(r'^([a-zA-Z0-9_-]+)([<>=!]+)?(.+)?$', line)
                if match:
                    name = match.group(1)
                    version = match.group(3) or "any"
                    deps.append(Dependency(
                        name=name,
                        version="unknown",
                        required_version=version,
                        source=str(path)
                    ))

        return deps

    def load_pyproject(self, path: Path = None) -> List[Dependency]:
        """Load dependencies from pyproject.toml."""
        path = path or Path("pyproject.toml")
        deps = []

        if not path.exists():
            return deps

        try:
            import tomllib
            with open(path, 'rb') as f:
                data = tomllib.load(f)
        except ImportError:
            # Python < 3.11
            try:
                import toml
                with open(path, 'r') as f:
                    data = toml.load(f)
            except ImportError:
                return deps

        # Get dependencies
        project_deps = data.get('project', {}).get('dependencies', [])
        for dep in project_deps:
            match = re.match(r'^([a-zA-Z0-9_-]+)', dep)
            if match:
                deps.append(Dependency(
                    name=match.group(1),
                    version="unknown",
                    required_version=dep,
                    source=str(path)
                ))

        # Get dev dependencies
        dev_deps = data.get('project', {}).get('optional-dependencies', {}).get('dev', [])
        for dep in dev_deps:
            match = re.match(r'^([a-zA-Z0-9_-]+)', dep)
            if match:
                deps.append(Dependency(
                    name=match.group(1),
                    version="unknown",
                    required_version=dep,
                    source=str(path),
                    is_dev=True
                ))

        return deps

    def check_installed_versions(self):
        """Check installed versions of dependencies."""
        try:
            result = subprocess.run(
                ['pip', 'list', '--format=json'],
                capture_output=True,
                text=True
            )
            installed = {
                pkg['name'].lower(): pkg['version']
                for pkg in json.loads(result.stdout)
            }

            for dep in self.dependencies:
                dep.version = installed.get(dep.name.lower(), "not installed")

        except Exception as e:
            self.issues.append(f"Could not check installed versions: {e}")

    def check_outdated(self):
        """Check for outdated dependencies."""
        try:
            result = subprocess.run(
                ['pip', 'list', '--outdated', '--format=json'],
                capture_output=True,
                text=True
            )
            outdated = {
                pkg['name'].lower(): pkg['latest_version']
                for pkg in json.loads(result.stdout)
            }

            for dep in self.dependencies:
                if dep.name.lower() in outdated:
                    dep.has_update = True
                    dep.latest_version = outdated[dep.name.lower()]

        except Exception as e:
            self.issues.append(f"Could not check for updates: {e}")

    def check_security(self):
        """Check for known vulnerabilities."""
        try:
            # Try pip-audit first
            result = subprocess.run(
                ['pip-audit', '--format=json'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                vulnerabilities = json.loads(result.stdout)
                vuln_map = {}
                for vuln in vulnerabilities.get('dependencies', []):
                    name = vuln.get('name', '').lower()
                    vulns = vuln.get('vulns', [])
                    if vulns:
                        vuln_map[name] = [v.get('id', 'unknown') for v in vulns]

                for dep in self.dependencies:
                    if dep.name.lower() in vuln_map:
                        dep.vulnerabilities = vuln_map[dep.name.lower()]

        except FileNotFoundError:
            # pip-audit not installed
            self.issues.append("pip-audit not installed - security check skipped")
        except Exception as e:
            self.issues.append(f"Security check failed: {e}")

    def check_conflicts(self) -> List[str]:
        """Check for dependency conflicts."""
        conflicts = []

        try:
            result = subprocess.run(
                ['pip', 'check'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                conflicts = result.stdout.strip().split('\n')

        except Exception as e:
            self.issues.append(f"Conflict check failed: {e}")

        return conflicts

    def run_check(
        self,
        check_outdated: bool = True,
        check_security: bool = True
    ) -> DependencyReport:
        """Run full dependency check."""
        # Load dependencies from various sources
        self.dependencies = []
        self.dependencies.extend(self.load_requirements())
        self.dependencies.extend(self.load_requirements(Path("requirements-dev.txt")))
        self.dependencies.extend(self.load_pyproject())

        if not self.dependencies:
            self.issues.append("No dependencies found")

        # Check installed versions
        self.check_installed_versions()

        # Check for outdated
        if check_outdated:
            self.check_outdated()

        # Check for security issues
        if check_security:
            self.check_security()

        # Check for conflicts
        conflicts = self.check_conflicts()
        for conflict in conflicts:
            if conflict:
                self.issues.append(f"Conflict: {conflict}")

        # Count issues
        outdated_count = sum(1 for d in self.dependencies if d.has_update)
        vulnerable_count = sum(1 for d in self.dependencies if d.vulnerabilities)

        # Determine if passed
        passed = vulnerable_count == 0 and len(conflicts) == 0

        return DependencyReport(
            timestamp=datetime.now().isoformat(),
            total_dependencies=len(self.dependencies),
            outdated=outdated_count,
            vulnerable=vulnerable_count,
            conflicts=len(conflicts),
            dependencies=self.dependencies,
            issues=self.issues,
            passed=passed
        )

def format_text(report: DependencyReport) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Dependency Check Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Total Dependencies: {report.total_dependencies}")
    lines.append(f"Outdated: {report.outdated}")
    lines.append(f"Vulnerable: {report.vulnerable}")
    lines.append(f"Conflicts: {report.conflicts}")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"Status: {status}")
    lines.append("")

    # Show vulnerable packages
    vulnerable = [d for d in report.dependencies if d.vulnerabilities]
    if vulnerable:
        lines.append("Vulnerable Packages:")
        for dep in vulnerable:
            lines.append(f"  {dep.name} ({dep.version}): {', '.join(dep.vulnerabilities)}")
        lines.append("")

    # Show outdated packages
    outdated = [d for d in report.dependencies if d.has_update]
    if outdated:
        lines.append("Outdated Packages:")
        for dep in outdated[:10]:
            lines.append(f"  {dep.name}: {dep.version} -> {dep.latest_version}")
        if len(outdated) > 10:
            lines.append(f"  ... and {len(outdated) - 10} more")
        lines.append("")

    # Show issues
    if report.issues:
        lines.append("Issues:")
        for issue in report.issues:
            lines.append(f"  - {issue}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: DependencyReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_dependencies": report.total_dependencies,
        "outdated": report.outdated,
        "vulnerable": report.vulnerable,
        "conflicts": report.conflicts,
        "passed": report.passed,
        "dependencies": [asdict(d) for d in report.dependencies],
        "issues": report.issues
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Check project dependencies"
    )

    parser.add_argument(
        "--check-security",
        action="store_true",
        help="Check for security vulnerabilities"
    )
    parser.add_argument(
        "--check-outdated",
        action="store_true",
        help="Check for outdated packages"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all checks"
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

    checker = DependencyChecker()

    # Determine what to check
    check_outdated = args.check_outdated or args.all or not (args.check_security)
    check_security = args.check_security or args.all

    report = checker.run_check(
        check_outdated=check_outdated,
        check_security=check_security
    )

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
