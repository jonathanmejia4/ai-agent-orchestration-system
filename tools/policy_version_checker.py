#!/usr/bin/env python3
"""
policy_version_checker.py - Policy Version Validator

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Governance Tool

Purpose:
    Validates that all policy documents are current and properly versioned.
    Ensures compliance with the system governance requirements.
    Detects outdated policies that need review.

Usage:
    python3 policy_version_checker.py --policies PLANNING/policies/
    python3 policy_version_checker.py --policies PLANNING/policies/ --max-age-days 90
    python3 policy_version_checker.py --policies PLANNING/policies/ --fail-on-outdated
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

@dataclass
class PolicyInfo:
    """Information about a policy document."""
    file_path: str
    title: str
    version: str
    last_updated: Optional[datetime]
    owner: str
    classification: str
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    days_since_update: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "title": self.title,
            "version": self.version,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "owner": self.owner,
            "classification": self.classification,
            "is_valid": self.is_valid,
            "issues": self.issues,
            "days_since_update": self.days_since_update
        }

@dataclass
class VersionCheckResult:
    """Result of version checking."""
    total_policies: int
    valid_policies: int
    outdated_policies: int
    invalid_policies: int
    policies: List[PolicyInfo]
    summary: Dict[str, int]

    def to_dict(self) -> dict:
        return {
            "total_policies": self.total_policies,
            "valid_policies": self.valid_policies,
            "outdated_policies": self.outdated_policies,
            "invalid_policies": self.invalid_policies,
            "policies": [p.to_dict() for p in self.policies],
            "summary": self.summary
        }

class PolicyVersionChecker:
    """Validates policy document versions and freshness."""

    # Required metadata fields
    REQUIRED_FIELDS = ["version", "last_updated", "owner", "classification"]

    # Version pattern (semantic versioning)
    VERSION_PATTERN = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?$')

    # Date patterns
    DATE_PATTERNS = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{4}/\d{2}/\d{2})',  # YYYY/MM/DD
        r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY
    ]

    # Classification levels
    VALID_CLASSIFICATIONS = [
        "LOW", "MEDIUM", "HIGH", "CRITICAL",
        "PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"
    ]

    def __init__(self, max_age_days: int = 180):
        self.max_age_days = max_age_days

    def _extract_metadata_from_header(self, content: str) -> Dict[str, str]:
        """Extract metadata from document header."""
        metadata = {}
        lines = content.split('\n')[:50]  # Check first 50 lines

        for line in lines:
            # Version
            version_match = re.search(r'[Vv]ersion[:\s]+(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)', line)
            if version_match and "version" not in metadata:
                metadata["version"] = version_match.group(1)

            # Last Updated
            date_match = None
            for pattern in self.DATE_PATTERNS:
                date_match = re.search(pattern, line)
                if date_match and ("updated" in line.lower() or "date" in line.lower()):
                    metadata["last_updated"] = date_match.group(1)
                    break

            # Owner
            owner_match = re.search(r'[Oo]wner[:\s]+([A-Za-z0-9_-]+)', line)
            if owner_match and "owner" not in metadata:
                metadata["owner"] = owner_match.group(1)

            # Classification
            for classification in self.VALID_CLASSIFICATIONS:
                if classification in line.upper():
                    metadata["classification"] = classification
                    break

            # Title (from first # heading)
            if line.startswith('#') and "title" not in metadata:
                metadata["title"] = line.lstrip('#').strip()

        return metadata

    def _extract_metadata_from_yaml(self, content: str) -> Dict[str, str]:
        """Extract metadata from YAML frontmatter or content."""
        metadata = {}

        # Check for YAML frontmatter
        if content.startswith('---'):
            end = content.find('---', 3)
            if end != -1:
                frontmatter = content[3:end]
                for line in frontmatter.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip().lower()] = value.strip()

        # Also check regular content
        header_metadata = self._extract_metadata_from_header(content)
        for key, value in header_metadata.items():
            if key not in metadata:
                metadata[key] = value

        return metadata

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _validate_version(self, version: str) -> Tuple[bool, Optional[str]]:
        """Validate version string."""
        if not version:
            return False, "Missing version"

        if not self.VERSION_PATTERN.match(version):
            return False, f"Invalid version format: {version}"

        return True, None

    def check_policy(self, file_path: Path) -> PolicyInfo:
        """Check a single policy document."""
        try:
            content = file_path.read_text()
        except Exception as e:
            return PolicyInfo(
                file_path=str(file_path),
                title="",
                version="",
                last_updated=None,
                owner="",
                classification="",
                is_valid=False,
                issues=[f"Failed to read file: {e}"]
            )

        # Extract metadata based on file type
        if file_path.suffix in ['.yaml', '.yml']:
            metadata = self._extract_metadata_from_yaml(content)
        else:
            metadata = self._extract_metadata_from_header(content)

        issues = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in metadata or not metadata.get(field):
                issues.append(f"Missing required field: {field}")

        # Validate version
        version = metadata.get("version", "")
        valid, error = self._validate_version(version)
        if not valid:
            issues.append(error)

        # Parse and validate date
        last_updated = None
        days_since_update = None
        if "last_updated" in metadata:
            last_updated = self._parse_date(metadata["last_updated"])
            if last_updated:
                days_since_update = (datetime.now() - last_updated).days
                if days_since_update > self.max_age_days:
                    issues.append(
                        f"Policy outdated: last updated {days_since_update} days ago "
                        f"(max: {self.max_age_days} days)"
                    )
            else:
                issues.append(f"Invalid date format: {metadata['last_updated']}")

        # Validate classification
        classification = metadata.get("classification", "")
        if classification and classification.upper() not in self.VALID_CLASSIFICATIONS:
            issues.append(f"Invalid classification: {classification}")

        return PolicyInfo(
            file_path=str(file_path),
            title=metadata.get("title", file_path.stem),
            version=version,
            last_updated=last_updated,
            owner=metadata.get("owner", ""),
            classification=classification,
            is_valid=len(issues) == 0,
            issues=issues,
            days_since_update=days_since_update
        )

    def check_directory(self, dir_path: Path, recursive: bool = True) -> VersionCheckResult:
        """Check all policy documents in a directory."""
        policies = []
        summary = {
            "by_classification": {},
            "by_owner": {},
            "version_distribution": {}
        }

        # Find policy files
        patterns = ["*.md", "*.yaml", "*.yml"]
        files = []
        for pattern in patterns:
            if recursive:
                files.extend(dir_path.rglob(pattern))
            else:
                files.extend(dir_path.glob(pattern))

        for file_path in sorted(files):
            # Skip non-policy files
            if any(skip in str(file_path) for skip in [".git", "node_modules", "__pycache__"]):
                continue

            policy = self.check_policy(file_path)
            policies.append(policy)

            # Update summary
            if policy.classification:
                summary["by_classification"][policy.classification] = \
                    summary["by_classification"].get(policy.classification, 0) + 1

            if policy.owner:
                summary["by_owner"][policy.owner] = \
                    summary["by_owner"].get(policy.owner, 0) + 1

            if policy.version:
                major = policy.version.split('.')[0]
                summary["version_distribution"][f"v{major}.x"] = \
                    summary["version_distribution"].get(f"v{major}.x", 0) + 1

        # Calculate counts
        valid = sum(1 for p in policies if p.is_valid)
        outdated = sum(
            1 for p in policies
            if p.days_since_update and p.days_since_update > self.max_age_days
        )
        invalid = len(policies) - valid

        return VersionCheckResult(
            total_policies=len(policies),
            valid_policies=valid,
            outdated_policies=outdated,
            invalid_policies=invalid,
            policies=policies,
            summary=summary
        )

def main():
    parser = argparse.ArgumentParser(
        description="Validate policy document versions and freshness"
    )
    parser.add_argument(
        "--policies", "-p",
        required=True,
        help="Directory containing policy documents"
    )
    parser.add_argument(
        "--max-age-days", "-m",
        type=int,
        default=180,
        help="Maximum age in days before policy is considered outdated (default: 180)"
    )
    parser.add_argument(
        "--fail-on-outdated",
        action="store_true",
        help="Exit with error if outdated policies found"
    )
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Exit with error if invalid policies found"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        default=True,
        help="Search recursively (default: true)"
    )

    args = parser.parse_args()

    dir_path = Path(args.policies)
    if not dir_path.exists():
        print(f"Error: Directory not found: {dir_path}", file=sys.stderr)
        return 1

    checker = PolicyVersionChecker(max_age_days=args.max_age_days)
    result = checker.check_directory(dir_path, recursive=args.recursive)

    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print("=" * 60)
        print("POLICY VERSION CHECK REPORT")
        print("=" * 60)
        print(f"\nDirectory: {dir_path}")
        print(f"Max age threshold: {args.max_age_days} days")
        print(f"\nTotal policies: {result.total_policies}")
        print(f"Valid policies: {result.valid_policies}")
        print(f"Outdated policies: {result.outdated_policies}")
        print(f"Invalid policies: {result.invalid_policies}")

        if result.summary["by_classification"]:
            print("\nBy Classification:")
            for cls, count in sorted(result.summary["by_classification"].items()):
                print(f"  {cls}: {count}")

        if result.summary["by_owner"]:
            print("\nBy Owner:")
            for owner, count in sorted(result.summary["by_owner"].items()):
                print(f"  {owner}: {count}")

        # Show issues
        issues_found = [p for p in result.policies if p.issues]
        if issues_found:
            print("\n" + "-" * 60)
            print("ISSUES FOUND:")
            print("-" * 60)
            for policy in issues_found:
                print(f"\n❌ {policy.file_path}")
                for issue in policy.issues:
                    print(f"   - {issue}")

        # Show outdated policies
        outdated = [p for p in result.policies if p.days_since_update and p.days_since_update > args.max_age_days]
        if outdated:
            print("\n" + "-" * 60)
            print("OUTDATED POLICIES:")
            print("-" * 60)
            for policy in sorted(outdated, key=lambda p: p.days_since_update or 0, reverse=True):
                print(f"  ⚠️  {policy.file_path}")
                print(f"      Last updated: {policy.days_since_update} days ago")
                print(f"      Version: {policy.version}")

        print("\n" + "=" * 60)
        if result.invalid_policies == 0 and result.outdated_policies == 0:
            print("✅ All policies are valid and current")
        else:
            print(f"⚠️  {result.invalid_policies} invalid, {result.outdated_policies} outdated")

    # Exit codes
    if args.fail_on_invalid and result.invalid_policies > 0:
        return 1
    if args.fail_on_outdated and result.outdated_policies > 0:
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
