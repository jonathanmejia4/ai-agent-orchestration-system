#!/usr/bin/env python3
"""
Missing Manifest Detector
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Build Validation

Detects missing manifest files in projects.
Ensures all required package/module manifests are present.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass
class ManifestRequirement:
    """A required manifest file."""
    name: str
    patterns: List[str]
    required_fields: List[str] = field(default_factory=list)
    description: str = ""

@dataclass
class MissingManifest:
    """A missing or incomplete manifest."""
    manifest_type: str
    expected_path: str
    reason: str
    severity: str = "error"
    suggestion: str = ""

@dataclass
class ManifestIssue:
    """An issue with an existing manifest."""
    manifest_path: str
    manifest_type: str
    issue: str
    severity: str = "warning"

@dataclass
class DetectionResult:
    """Result of manifest detection."""
    valid: bool
    directories_checked: int
    manifests_found: int
    missing: List[MissingManifest] = field(default_factory=list)
    issues: List[ManifestIssue] = field(default_factory=list)
    manifests: Dict[str, str] = field(default_factory=dict)

class ManifestDetector:
    """Detects missing manifest files."""

    # Known manifest types and their patterns
    MANIFEST_TYPES = {
        "python": ManifestRequirement(
            name="Python Package",
            patterns=["setup.py", "pyproject.toml", "setup.cfg"],
            required_fields=["name", "version"],
            description="Python package manifest"
        ),
        "node": ManifestRequirement(
            name="Node.js Package",
            patterns=["package.json"],
            required_fields=["name", "version"],
            description="Node.js package manifest"
        ),
        "rust": ManifestRequirement(
            name="Rust Crate",
            patterns=["Cargo.toml"],
            required_fields=["name", "version"],
            description="Rust crate manifest"
        ),
        "go": ManifestRequirement(
            name="Go Module",
            patterns=["go.mod"],
            required_fields=["module"],
            description="Go module manifest"
        ),
        "ruby": ManifestRequirement(
            name="Ruby Gem",
            patterns=["Gemfile", "*.gemspec"],
            required_fields=[],
            description="Ruby gem manifest"
        ),
        "java": ManifestRequirement(
            name="Java/Maven",
            patterns=["pom.xml", "build.gradle", "build.gradle.kts"],
            required_fields=[],
            description="Java build manifest"
        ),
        "docker": ManifestRequirement(
            name="Docker",
            patterns=["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
            required_fields=[],
            description="Docker configuration"
        ),
        "saf": ManifestRequirement(
            name="the system Task",
            patterns=[".task/task.yaml", "task.yaml"],
            required_fields=["id", "version"],
            description="the system task manifest"
        ),
    }

    # Indicators that a directory is a package/module root
    PACKAGE_INDICATORS = {
        "python": ["__init__.py", "src/", "tests/"],
        "node": ["src/", "lib/", "index.js", "index.ts"],
        "rust": ["src/main.rs", "src/lib.rs"],
        "go": ["main.go", "*.go"],
        "ruby": ["lib/", "spec/"],
        "java": ["src/main/", "src/"],
        "docker": ["Dockerfile", "docker/"],
        "saf": [".task/", "PLANNING/"],
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize detector.

        Args:
            config_path: Path to custom configuration
        """
        self.config: Dict[str, Any] = {}
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Load configuration."""
        try:
            import yaml
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            pass

    def _detect_project_type(self, directory: str) -> List[str]:
        """Detect what type of project is in a directory."""
        detected = []
        path = Path(directory)

        for project_type, indicators in self.PACKAGE_INDICATORS.items():
            for indicator in indicators:
                if '*' in indicator:
                    # Glob pattern
                    if list(path.glob(indicator)):
                        detected.append(project_type)
                        break
                else:
                    # Direct path
                    if (path / indicator).exists():
                        detected.append(project_type)
                        break

        return detected

    def _find_manifest(
        self,
        directory: str,
        manifest_type: str
    ) -> Optional[str]:
        """Find a manifest file in a directory."""
        requirement = self.MANIFEST_TYPES.get(manifest_type)
        if not requirement:
            return None

        path = Path(directory)
        for pattern in requirement.patterns:
            if '*' in pattern:
                matches = list(path.glob(pattern))
                if matches:
                    return str(matches[0])
            else:
                manifest_path = path / pattern
                if manifest_path.exists():
                    return str(manifest_path)

        return None

    def _validate_manifest(
        self,
        manifest_path: str,
        manifest_type: str
    ) -> List[ManifestIssue]:
        """Validate a manifest file."""
        issues = []
        requirement = self.MANIFEST_TYPES.get(manifest_type)
        if not requirement:
            return issues

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            issues.append(ManifestIssue(
                manifest_path=manifest_path,
                manifest_type=manifest_type,
                issue=f"Failed to read: {e}",
                severity="error"
            ))
            return issues

        # Check required fields based on file type
        if manifest_path.endswith('.json'):
            try:
                data = json.loads(content)
                for field in requirement.required_fields:
                    if field not in data:
                        issues.append(ManifestIssue(
                            manifest_path=manifest_path,
                            manifest_type=manifest_type,
                            issue=f"Missing required field: {field}"
                        ))
            except json.JSONDecodeError as e:
                issues.append(ManifestIssue(
                    manifest_path=manifest_path,
                    manifest_type=manifest_type,
                    issue=f"Invalid JSON: {e}",
                    severity="error"
                ))

        elif manifest_path.endswith(('.yaml', '.yml')):
            try:
                import yaml
                data = yaml.safe_load(content)
                if data:
                    for field in requirement.required_fields:
                        if field not in data:
                            issues.append(ManifestIssue(
                                manifest_path=manifest_path,
                                manifest_type=manifest_type,
                                issue=f"Missing required field: {field}"
                            ))
            except Exception as e:
                issues.append(ManifestIssue(
                    manifest_path=manifest_path,
                    manifest_type=manifest_type,
                    issue=f"Invalid YAML: {e}",
                    severity="error"
                ))

        elif manifest_path.endswith('.toml'):
            try:
                import tomllib
                data = tomllib.loads(content)
                # Check in [project] or [package] sections
                project = data.get('project', data.get('package', {}))
                for field in requirement.required_fields:
                    if field not in project and field not in data:
                        issues.append(ManifestIssue(
                            manifest_path=manifest_path,
                            manifest_type=manifest_type,
                            issue=f"Missing required field: {field}"
                        ))
            except Exception:
                # tomllib not available in Python < 3.11
                pass

        return issues

    def check_directory(
        self,
        directory: str,
        project_types: Optional[List[str]] = None,
        recursive: bool = False
    ) -> DetectionResult:
        """
        Check a directory for missing manifests.

        Args:
            directory: Directory to check
            project_types: Specific types to check (default: auto-detect)
            recursive: Check subdirectories

        Returns:
            DetectionResult
        """
        result = DetectionResult(
            valid=True,
            directories_checked=0,
            manifests_found=0
        )

        directories = [directory]
        if recursive:
            for root, dirs, files in os.walk(directory):
                # Skip common non-project directories
                dirs[:] = [d for d in dirs if d not in [
                    'node_modules', '.git', '__pycache__', 'venv',
                    '.venv', 'dist', 'build', 'target'
                ]]
                directories.extend(os.path.join(root, d) for d in dirs)

        for dir_path in directories:
            result.directories_checked += 1

            # Detect or use specified project types
            types_to_check = project_types or self._detect_project_type(dir_path)

            for project_type in types_to_check:
                manifest_path = self._find_manifest(dir_path, project_type)

                if manifest_path:
                    result.manifests_found += 1
                    result.manifests[project_type] = manifest_path

                    # Validate the manifest
                    issues = self._validate_manifest(manifest_path, project_type)
                    result.issues.extend(issues)
                    if any(i.severity == "error" for i in issues):
                        result.valid = False
                else:
                    # Only report missing if we detected indicators
                    if project_type in self._detect_project_type(dir_path):
                        requirement = self.MANIFEST_TYPES[project_type]
                        result.missing.append(MissingManifest(
                            manifest_type=project_type,
                            expected_path=os.path.join(
                                dir_path, requirement.patterns[0]
                            ),
                            reason=f"{requirement.name} indicators found but no manifest",
                            suggestion=f"Create {requirement.patterns[0]}"
                        ))
                        result.valid = False

        return result

    def generate_manifest_template(
        self,
        manifest_type: str,
        name: str = "my-project",
        version: str = "0.1.0"
    ) -> str:
        """Generate a manifest template."""
        templates = {
            "python": f'''[project]
name = "{name}"
version = "{version}"
description = ""
requires-python = ">=3.8"
dependencies = []

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
''',
            "node": json.dumps({
                "name": name,
                "version": version,
                "description": "",
                "main": "index.js",
                "scripts": {
                    "test": "echo 'No tests'"
                },
                "dependencies": {},
                "devDependencies": {}
            }, indent=2),

            "rust": f'''[package]
name = "{name}"
version = "{version}"
edition = "2021"

[dependencies]
''',
            "go": f'''module {name}

go 1.21
''',
            "saf": f'''# the system Task Manifest
id: "{name}"
version: "{version}"
type: feature
description: ""

inputs: []
outputs: []
dependencies: []
'''
        }

        return templates.get(manifest_type, "# No template available")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect missing manifest files"
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="Directory to check")
    parser.add_argument("-t", "--types", nargs="+",
                        choices=list(ManifestDetector.MANIFEST_TYPES.keys()),
                        help="Project types to check")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Check subdirectories")
    parser.add_argument("-c", "--config", help="Configuration file")
    parser.add_argument("--generate", metavar="TYPE",
                        help="Generate manifest template")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    detector = ManifestDetector(config_path=args.config)

    if args.generate:
        template = detector.generate_manifest_template(args.generate)
        print(template)
        sys.exit(0)

    result = detector.check_directory(
        args.path,
        project_types=args.types,
        recursive=args.recursive
    )

    if args.json:
        output = {
            "valid": result.valid,
            "directories_checked": result.directories_checked,
            "manifests_found": result.manifests_found,
            "missing": [
                {
                    "type": m.manifest_type,
                    "expected": m.expected_path,
                    "reason": m.reason,
                    "suggestion": m.suggestion
                }
                for m in result.missing
            ],
            "issues": [
                {
                    "path": i.manifest_path,
                    "type": i.manifest_type,
                    "issue": i.issue,
                    "severity": i.severity
                }
                for i in result.issues
            ],
            "manifests": result.manifests
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Directories checked: {result.directories_checked}")
        print(f"Manifests found: {result.manifests_found}")
        print(f"Valid: {'Yes' if result.valid else 'No'}")

        if result.manifests and args.verbose:
            print(f"\nManifests:")
            for mtype, path in result.manifests.items():
                print(f"  [{mtype}] {path}")

        if result.missing:
            print(f"\nMissing manifests ({len(result.missing)}):")
            for m in result.missing:
                print(f"  [{m.manifest_type}] {m.expected_path}")
                print(f"    Reason: {m.reason}")
                if m.suggestion:
                    print(f"    Suggestion: {m.suggestion}")

        if result.issues:
            print(f"\nManifest issues ({len(result.issues)}):")
            for i in result.issues:
                symbol = "!" if i.severity == "error" else "?"
                print(f"  [{symbol}] {i.manifest_path}: {i.issue}")

    sys.exit(0 if result.valid else 1)

if __name__ == "__main__":
    main()
