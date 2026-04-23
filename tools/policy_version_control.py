#!/usr/bin/env python3
"""
Policy Version Control & Drift Detection

Tracks policy document versions, detects unauthorized changes, and validates
version headers against git history.

Usage:
    python3 tools/policy_version_control.py --check-versions
    python3 tools/policy_version_control.py --detect-drift
    python3 tools/policy_version_control.py --validate PLANNING/SOME_POLICY.md
    python3 tools/policy_version_control.py --json
    python3 tools/policy_version_control.py --help

Exit Codes:
    0 - All policies valid
    1 - Version issues or drift detected
    2 - Error

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class PolicyInfo:
    """Policy document information"""
    path: str
    name: str
    policy_id: Optional[str] = None
    version: Optional[str] = None
    last_updated: Optional[str] = None
    git_last_modified: Optional[str] = None
    has_version_header: bool = False
    drift_detected: bool = False
    issues: List[str] = field(default_factory=list)

@dataclass
class ValidationResult:
    """Policy validation result"""
    valid: bool = True
    policies_checked: int = 0
    policies_with_issues: int = 0
    missing_versions: List[str] = field(default_factory=list)
    version_drift: List[str] = field(default_factory=list)
    policy_details: List[PolicyInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'policies_checked': self.policies_checked,
            'policies_with_issues': self.policies_with_issues,
            'missing_versions': self.missing_versions,
            'version_drift': self.version_drift,
            'policy_details': [asdict(p) for p in self.policy_details],
            'warnings': self.warnings
        }

class PolicyVersionController:
    """Policy version control and drift detection"""

    # Version patterns
    VERSION_PATTERNS = [
        r'Version:\s*(\d+\.\d+(?:\.\d+)?)',
        r'version:\s*(\d+\.\d+(?:\.\d+)?)',
        r'\*\*Version:\*\*\s*(\d+\.\d+(?:\.\d+)?)',
        r'Policy Version:\s*(\d+\.\d+(?:\.\d+)?)',
    ]

    # Policy ID pattern
    POLICY_ID_PATTERN = r'Policy ID:\s*(POLICY-\d+)'

    # Last updated patterns
    DATE_PATTERNS = [
        r'Last Updated:\s*(\d{4}-\d{2}-\d{2})',
        r'last_updated:\s*(\d{4}-\d{2}-\d{2})',
        r'\*\*Last Updated:\*\*\s*(\d{4}-\d{2}-\d{2})',
    ]

    def __init__(self, repo_root: Optional[Path] = None, verbose: bool = False):
        self.repo_root = repo_root or Path.cwd()
        self.verbose = verbose
        self.planning_dir = self.repo_root / 'PLANNING'

    def log(self, message: str):
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def get_git_last_modified(self, file_path: Path) -> Optional[str]:
        """Get last git modification date for a file"""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ci', str(file_path)],
                capture_output=True, text=True, cwd=self.repo_root
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse and format date
                date_str = result.stdout.strip()[:10]
                return date_str
        except Exception as e:
            self.log(f"Error getting git date: {e}")
        return None

    def parse_policy_header(self, file_path: Path) -> PolicyInfo:
        """Parse policy document header for version info"""
        info = PolicyInfo(
            path=str(file_path),
            name=file_path.stem
        )

        try:
            content = file_path.read_text()
            # Only check first 50 lines for header
            header = '\n'.join(content.split('\n')[:50])

            # Extract version
            for pattern in self.VERSION_PATTERNS:
                match = re.search(pattern, header, re.IGNORECASE)
                if match:
                    info.version = match.group(1)
                    info.has_version_header = True
                    break

            # Extract policy ID
            match = re.search(self.POLICY_ID_PATTERN, header)
            if match:
                info.policy_id = match.group(1)

            # Extract last updated date
            for pattern in self.DATE_PATTERNS:
                match = re.search(pattern, header, re.IGNORECASE)
                if match:
                    info.last_updated = match.group(1)
                    break

            # Get git last modified
            info.git_last_modified = self.get_git_last_modified(file_path)

            # Check for drift
            if info.last_updated and info.git_last_modified:
                if info.last_updated != info.git_last_modified:
                    info.drift_detected = True
                    info.issues.append(f"Date drift: header says {info.last_updated}, git says {info.git_last_modified}")

        except Exception as e:
            info.issues.append(f"Error parsing: {e}")

        return info

    def check_all_versions(self) -> ValidationResult:
        """Check version headers for all policy files"""
        result = ValidationResult()

        if not self.planning_dir.exists():
            result.warnings.append("PLANNING directory not found")
            return result

        policy_files = list(self.planning_dir.glob('*_POLICY.md'))
        policy_files.extend(self.planning_dir.glob('*_Policy.md'))
        policy_files.extend(self.planning_dir.glob('*_protocol.md'))
        policy_files.extend(self.planning_dir.glob('*_PROTOCOL.md'))

        for policy_path in policy_files:
            result.policies_checked += 1
            info = self.parse_policy_header(policy_path)
            result.policy_details.append(info)

            if not info.has_version_header:
                result.missing_versions.append(str(policy_path))
                result.policies_with_issues += 1
                result.valid = False

            if info.drift_detected:
                result.version_drift.append(str(policy_path))
                result.policies_with_issues += 1
                result.valid = False

        return result

    def validate_single(self, policy_path: Path) -> PolicyInfo:
        """Validate a single policy file"""
        return self.parse_policy_header(policy_path)

def print_result(result: ValidationResult, format: str = "text"):
    """Print validation result"""
    if format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return

    print()
    if result.valid:
        print(f"\033[92m✅ Policy version control passed\033[0m")
    else:
        print(f"\033[91m❌ Policy version issues found\033[0m")

    print(f"\nPolicies checked: {result.policies_checked}")
    print(f"Policies with issues: {result.policies_with_issues}")

    if result.missing_versions:
        print(f"\n\033[91mMissing Version Headers ({len(result.missing_versions)}):\033[0m")
        for path in result.missing_versions[:10]:
            print(f"  - {path}")

    if result.version_drift:
        print(f"\n\033[93mVersion Drift Detected ({len(result.version_drift)}):\033[0m")
        for path in result.version_drift[:10]:
            print(f"  - {path}")

def main():
    parser = argparse.ArgumentParser(
        description='Policy version control and drift detection',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--check-versions', '-c', action='store_true',
                       help='Check version headers for all policies')
    parser.add_argument('--detect-drift', '-d', action='store_true',
                       help='Detect version/date drift')
    parser.add_argument('--validate', '-v', type=Path,
                       help='Validate specific policy file')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose output')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd(),
                       help='Repository root')

    args = parser.parse_args()

    controller = PolicyVersionController(
        repo_root=args.repo_root,
        verbose=args.verbose
    )

    if args.validate:
        info = controller.validate_single(args.validate)
        if args.json:
            print(json.dumps(asdict(info), indent=2))
        else:
            print(f"Policy: {info.name}")
            print(f"Version: {info.version or 'NOT FOUND'}")
            print(f"Policy ID: {info.policy_id or 'NOT FOUND'}")
            print(f"Last Updated: {info.last_updated or 'NOT FOUND'}")
            print(f"Git Modified: {info.git_last_modified or 'N/A'}")
            if info.drift_detected:
                print("\033[93m⚠ Drift detected\033[0m")
        sys.exit(0 if not info.issues else 1)
    else:
        result = controller.check_all_versions()
        print_result(result, 'json' if args.json else 'text')
        sys.exit(0 if result.valid else 1)

if __name__ == '__main__':
    main()
