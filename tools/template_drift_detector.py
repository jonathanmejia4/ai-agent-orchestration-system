#!/usr/bin/env python3
"""
template_drift_detector.py - Detect template version drift across tasks

Compares task template versions against the template registry to identify
version drift, inconsistencies, and sync issues that may cause regeneration
problems.

Exit codes:
  0 - No drift detected
  1 - Drift detected
  2 - File/parse error

Usage:
  python tools/template_drift_detector.py
  python tools/template_drift_detector.py --format=json
  python tools/template_drift_detector.py --threshold=2 --strict

Reference: PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

@dataclass
class DriftEntry:
    """Represents a drift detection for a single task."""
    task_id: str
    template: str
    task_version: str
    registry_version: str
    drift_type: str  # version_mismatch, unknown_template, missing_version, checksum_mismatch
    severity: str  # critical, high, medium, low
    message: str
    file_path: str
    checksum_match: Optional[bool] = None
    version_gap: int = 0

@dataclass
class TemplateInfo:
    """Template information from registry."""
    name: str
    latest_version: str
    versions: list = field(default_factory=list)
    checksums: dict = field(default_factory=dict)
    deprecated: bool = False
    retired: bool = False

class TemplateDriftDetector:
    """Detect template version drift between tasks and registry."""

    def __init__(self, verbose: bool = False, strict: bool = False, threshold: int = 2):
        self.verbose = verbose
        self.strict = strict
        self.threshold = threshold
        self.drifts: list[DriftEntry] = []
        self.templates: dict[str, TemplateInfo] = {}
        self.errors: list[str] = []
        self.scanned_tasks: int = 0

    def load_registry(self, root_dir: Path) -> None:
        """Load template registry for version comparison."""
        registry_paths = [
            root_dir / ".templates" / "registry.yaml",
            root_dir / "templates" / "registry.yaml",
            root_dir / "PLANNING" / "template_registry.yaml",
        ]

        for registry_path in registry_paths:
            if registry_path.exists():
                try:
                    with open(registry_path) as f:
                        data = yaml.safe_load(f) or {}

                    for name, info in data.get("templates", {}).items():
                        if isinstance(info, dict):
                            versions = info.get("versions", [])
                            latest = info.get("latest", versions[-1] if versions else "unknown")
                            checksums = info.get("checksums", {})

                            self.templates[name] = TemplateInfo(
                                name=name,
                                latest_version=latest,
                                versions=versions,
                                checksums=checksums,
                                deprecated=info.get("deprecated", False),
                                retired=info.get("retired", False)
                            )

                    if self.verbose:
                        print(f"  Loaded registry: {registry_path}")
                except Exception as e:
                    self.errors.append(f"Error loading registry {registry_path}: {e}")

        # Scan template directories for version metadata
        template_dirs = [
            root_dir / ".templates",
            root_dir / "templates",
        ]

        for template_dir in template_dirs:
            if not template_dir.exists():
                continue

            for tmpl_path in template_dir.iterdir():
                if not tmpl_path.is_dir():
                    continue

                name = tmpl_path.name
                if name in self.templates:
                    continue

                # Check versions directory
                versions_dir = tmpl_path / "versions"
                versions = []
                checksums = {}

                if versions_dir.exists():
                    for ver_dir in sorted(versions_dir.iterdir()):
                        if ver_dir.is_dir():
                            versions.append(ver_dir.name)
                            # Calculate checksum for version
                            checksum = self._calculate_template_checksum(ver_dir)
                            if checksum:
                                checksums[ver_dir.name] = checksum

                # Check metadata
                metadata_path = tmpl_path / "metadata.yaml"
                deprecated = False
                retired = False
                latest = versions[-1] if versions else "unknown"

                if metadata_path.exists():
                    try:
                        with open(metadata_path) as f:
                            meta = yaml.safe_load(f) or {}
                        deprecated = meta.get("deprecated", False)
                        retired = meta.get("retired", False)
                        latest = meta.get("latest_version", latest)
                    except Exception:
                        pass

                self.templates[name] = TemplateInfo(
                    name=name,
                    latest_version=latest,
                    versions=versions,
                    checksums=checksums,
                    deprecated=deprecated,
                    retired=retired
                )

    def _calculate_template_checksum(self, template_dir: Path) -> Optional[str]:
        """Calculate checksum for template version directory."""
        try:
            hasher = hashlib.sha256()
            for file_path in sorted(template_dir.rglob("*")):
                if file_path.is_file():
                    hasher.update(file_path.name.encode())
                    hasher.update(file_path.read_bytes())
            return hasher.hexdigest()[:16]
        except Exception:
            return None

    def scan_tasks(self, root_dir: Path) -> None:
        """Scan all tasks for template version drift."""
        wiring_patterns = [
            "**/wiring.yaml",
            "**/.task/wiring.yaml",
            "tasks/**/wiring.yaml",
        ]

        found_files = set()
        for pattern in wiring_patterns:
            for wiring_file in root_dir.glob(pattern):
                if wiring_file not in found_files:
                    found_files.add(wiring_file)
                    self._check_task(wiring_file)

    def _check_task(self, wiring_file: Path) -> None:
        """Check a task's wiring.yaml for template drift."""
        try:
            with open(wiring_file) as f:
                data = yaml.safe_load(f) or {}

            self.scanned_tasks += 1

            # Extract task identity
            identity = data.get("identity", {})
            task_id = identity.get("task_id", identity.get("id", wiring_file.parent.name))

            # Extract template info
            template = identity.get("template", data.get("template", ""))
            template_version = identity.get("template_version", "")

            if not template:
                return  # No template, nothing to check

            # Handle template@version format
            if "@" in str(template) and not template_version:
                template, template_version = str(template).rsplit("@", 1)

            if not template_version:
                template_version = "unknown"

            # Check for drift
            self._evaluate_drift(
                task_id=task_id,
                template=template,
                task_version=template_version,
                file_path=str(wiring_file)
            )

        except Exception as e:
            self.errors.append(f"Error processing {wiring_file}: {e}")

    def _evaluate_drift(
        self,
        task_id: str,
        template: str,
        task_version: str,
        file_path: str
    ) -> None:
        """Evaluate drift between task and registry versions."""
        # Unknown template
        if template not in self.templates:
            self.drifts.append(DriftEntry(
                task_id=task_id,
                template=template,
                task_version=task_version,
                registry_version="NOT_IN_REGISTRY",
                drift_type="unknown_template",
                severity="high" if self.strict else "medium",
                message=f"Template '{template}' not found in registry",
                file_path=file_path
            ))
            return

        tmpl_info = self.templates[template]

        # Missing version in task
        if task_version == "unknown":
            self.drifts.append(DriftEntry(
                task_id=task_id,
                template=template,
                task_version=task_version,
                registry_version=tmpl_info.latest_version,
                drift_type="missing_version",
                severity="medium",
                message="Task does not specify template version",
                file_path=file_path
            ))
            return

        # Retired template
        if tmpl_info.retired:
            self.drifts.append(DriftEntry(
                task_id=task_id,
                template=template,
                task_version=task_version,
                registry_version=tmpl_info.latest_version,
                drift_type="version_mismatch",
                severity="critical",
                message="Using retired template - immediate migration required",
                file_path=file_path,
                version_gap=999
            ))
            return

        # Deprecated template
        if tmpl_info.deprecated:
            self.drifts.append(DriftEntry(
                task_id=task_id,
                template=template,
                task_version=task_version,
                registry_version=tmpl_info.latest_version,
                drift_type="version_mismatch",
                severity="high",
                message="Using deprecated template - upgrade recommended",
                file_path=file_path,
                version_gap=99
            ))
            return

        # Version mismatch
        if task_version != tmpl_info.latest_version:
            gap = self._calculate_version_gap(task_version, tmpl_info.latest_version)

            if gap >= self.threshold:
                severity = "high" if gap >= 5 else "medium"
                self.drifts.append(DriftEntry(
                    task_id=task_id,
                    template=template,
                    task_version=task_version,
                    registry_version=tmpl_info.latest_version,
                    drift_type="version_mismatch",
                    severity=severity,
                    message=f"Version drift: {gap} version(s) behind latest",
                    file_path=file_path,
                    version_gap=gap
                ))

        # Check version not in registry versions list
        if tmpl_info.versions and task_version not in tmpl_info.versions:
            self.drifts.append(DriftEntry(
                task_id=task_id,
                template=template,
                task_version=task_version,
                registry_version=tmpl_info.latest_version,
                drift_type="version_mismatch",
                severity="high",
                message=f"Version '{task_version}' not in registry versions list",
                file_path=file_path
            ))

    def _calculate_version_gap(self, task_ver: str, registry_ver: str) -> int:
        """Calculate version gap between task and registry."""
        try:
            task_parts = [int(p) for p in re.findall(r"\d+", task_ver)[:3]]
            reg_parts = [int(p) for p in re.findall(r"\d+", registry_ver)[:3]]

            while len(task_parts) < 3:
                task_parts.append(0)
            while len(reg_parts) < 3:
                reg_parts.append(0)

            # Major version difference
            if reg_parts[0] > task_parts[0]:
                return (reg_parts[0] - task_parts[0]) * 10

            # Minor version difference
            if reg_parts[1] > task_parts[1]:
                return reg_parts[1] - task_parts[1]

            # Patch difference
            return max(0, reg_parts[2] - task_parts[2])

        except Exception:
            return 0

    def get_summary(self) -> dict:
        """Get drift detection summary."""
        by_severity = defaultdict(list)
        by_type = defaultdict(list)

        for drift in self.drifts:
            by_severity[drift.severity].append(drift)
            by_type[drift.drift_type].append(drift)

        return {
            "scanned_tasks": self.scanned_tasks,
            "total_drifts": len(self.drifts),
            "critical": len(by_severity["critical"]),
            "high": len(by_severity["high"]),
            "medium": len(by_severity["medium"]),
            "low": len(by_severity["low"]),
            "by_type": {
                "version_mismatch": len(by_type["version_mismatch"]),
                "unknown_template": len(by_type["unknown_template"]),
                "missing_version": len(by_type["missing_version"]),
                "checksum_mismatch": len(by_type["checksum_mismatch"]),
            },
            "templates_in_registry": len(self.templates),
            "has_drift": len(self.drifts) > 0
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("TEMPLATE DRIFT DETECTION REPORT")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nTasks scanned: {summary['scanned_tasks']}")
        lines.append(f"Templates in registry: {summary['templates_in_registry']}")
        lines.append(f"Total drifts detected: {summary['total_drifts']}")

        if summary["total_drifts"] > 0:
            lines.append("\nBy Severity:")
            lines.append(f"  Critical: {summary['critical']}")
            lines.append(f"  High: {summary['high']}")
            lines.append(f"  Medium: {summary['medium']}")
            lines.append(f"  Low: {summary['low']}")

            lines.append("\nBy Type:")
            for dtype, count in summary["by_type"].items():
                if count > 0:
                    lines.append(f"  {dtype}: {count}")

        # Group by severity
        severity_order = ["critical", "high", "medium", "low"]
        for severity in severity_order:
            drifts = [d for d in self.drifts if d.severity == severity]
            if not drifts:
                continue

            lines.append("\n" + "-" * 40)
            lines.append(f"{severity.upper()} ({len(drifts)}):")
            lines.append("-" * 40)

            for d in sorted(drifts, key=lambda x: -x.version_gap):
                lines.append(f"\n  Task: {d.task_id}")
                lines.append(f"    Template: {d.template}")
                lines.append(f"    Current: {d.task_version} -> Registry: {d.registry_version}")
                lines.append(f"    Type: {d.drift_type}")
                lines.append(f"    Issue: {d.message}")
                if self.verbose:
                    lines.append(f"    File: {d.file_path}")

        if not self.drifts:
            lines.append("\n✓ No template version drift detected")

        if self.errors and self.verbose:
            lines.append("\n" + "-" * 40)
            lines.append("ERRORS:")
            for error in self.errors[:5]:
                lines.append(f"  - {error}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        output = {
            "summary": self.get_summary(),
            "drifts": [
                {
                    "task_id": d.task_id,
                    "template": d.template,
                    "task_version": d.task_version,
                    "registry_version": d.registry_version,
                    "drift_type": d.drift_type,
                    "severity": d.severity,
                    "message": d.message,
                    "file_path": d.file_path,
                    "version_gap": d.version_gap
                }
                for d in sorted(self.drifts, key=lambda x: (-x.version_gap, x.severity))
            ],
            "templates": {
                name: {
                    "latest_version": info.latest_version,
                    "versions": info.versions,
                    "deprecated": info.deprecated,
                    "retired": info.retired
                }
                for name, info in self.templates.items()
            },
            "errors": self.errors
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Detect template version drift between tasks and registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - No drift detected
  1 - Drift detected
  2 - File/parse error

Examples:
  %(prog)s                      # Scan current directory
  %(prog)s --format=json        # JSON output for automation
  %(prog)s --threshold=3        # Only report drifts >= 3 versions
  %(prog)s --strict             # Treat unknown templates as high severity
        """
    )

    parser.add_argument(
        "--dir", "-d",
        default=".",
        help="Root directory to scan (default: current directory)"
    )

    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=2,
        help="Minimum version gap to report (default: 2)"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode (unknown templates are high severity)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information including file paths"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    root_dir = Path(args.dir)
    if not root_dir.exists():
        print(f"Error: Directory not found: {root_dir}", file=sys.stderr)
        sys.exit(2)

    detector = TemplateDriftDetector(
        verbose=args.verbose,
        strict=args.strict,
        threshold=args.threshold
    )

    if args.verbose:
        print("Loading template registry...")
    detector.load_registry(root_dir)

    if args.verbose:
        print("Scanning tasks for drift...")
    detector.scan_tasks(root_dir)

    if args.format == "json":
        print(detector.format_json_output())
    else:
        print(detector.format_text_output())

    # Exit code based on drift detection
    summary = detector.get_summary()
    if summary["has_drift"]:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
