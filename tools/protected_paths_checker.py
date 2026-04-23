#!/usr/bin/env python3
"""
Protected Paths Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Access Control

Validates that protected paths are not modified by unauthorized agents.
Enforces PM-exclusive path restrictions and agent boundaries.
"""

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

@dataclass
class PathViolation:
    """A violation of protected path rules."""
    path: str
    violation_type: str  # "modified", "created", "deleted"
    protected_by: str  # "pm", "critic", "system"
    actor: Optional[str] = None
    commit: Optional[str] = None
    message: str = ""

@dataclass
class CheckResult:
    """Result of protected paths check."""
    valid: bool
    paths_checked: int
    violations: List[PathViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class ProtectedPathsChecker:
    """Checks for violations of protected paths."""

    DEFAULT_PROTECTED = {
        "pm": [
            "PLANNING/**",
            ".claude/guidelines/**",
            "ISSUE_CATALOG.md",
            ".github/protected-paths.*",
            "scripts/pm_*.sh",
        ],
        "critic": [
            ".task/verdict.yaml",
            "LogBook/critic/**",
        ],
        "system": [
            ".git/**",
            ".github/workflows/**",
            "node_modules/**",
        ]
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        base_path: str = "."
    ):
        """
        Initialize checker.

        Args:
            config_path: Path to protected paths configuration
            base_path: Base path for checking
        """
        self.base_path = Path(base_path)
        self.protected: Dict[str, List[str]] = self.DEFAULT_PROTECTED.copy()

        if config_path:
            self._load_config(config_path)
        else:
            # Try to load from standard locations
            for loc in [".github/protected-paths.json", ".github/protected-paths.yaml"]:
                if (self.base_path / loc).exists():
                    self._load_config(str(self.base_path / loc))
                    break

    def _load_config(self, config_path: str):
        """Load protected paths configuration."""
        try:
            if config_path.endswith('.json'):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                import yaml
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)

            if config:
                for owner, paths in config.get("protected_paths", config).items():
                    if owner in self.protected:
                        self.protected[owner].extend(paths)
                    else:
                        self.protected[owner] = paths

        except Exception as e:
            print(f"Warning: Failed to load config: {e}", file=sys.stderr)

    def _matches_pattern(self, path: str, patterns: List[str]) -> bool:
        """Check if path matches any pattern."""
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
            # Also check with ** expansion
            if '**' in pattern:
                base_pattern = pattern.replace('**', '*')
                if fnmatch.fnmatch(path, base_pattern):
                    return True
        return False

    def _get_protection(self, path: str) -> Optional[str]:
        """Get protection owner for a path."""
        for owner, patterns in self.protected.items():
            if self._matches_pattern(path, patterns):
                return owner
        return None

    def _get_changed_files(
        self,
        since_ref: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Get list of changed files from git."""
        try:
            if since_ref:
                cmd = ["git", "diff", "--name-status", since_ref]
            else:
                # Get uncommitted changes
                cmd = ["git", "status", "--porcelain"]

            result = subprocess.run(
                cmd,
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return []

            changes = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue

                if since_ref:
                    # git diff format: M\tpath
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        status = parts[0]
                        path = parts[1]
                        changes.append({"status": status, "path": path})
                else:
                    # git status format: XY path
                    status = line[:2].strip()
                    path = line[3:]
                    change_type = "modified"
                    if 'A' in status:
                        change_type = "created"
                    elif 'D' in status:
                        change_type = "deleted"
                    changes.append({"status": change_type, "path": path})

            return changes

        except Exception:
            return []

    def check_changes(
        self,
        actor: str = "builder",
        since_ref: Optional[str] = None
    ) -> CheckResult:
        """
        Check if changes violate protected paths.

        Args:
            actor: The actor making changes
            since_ref: Git reference to compare against

        Returns:
            CheckResult
        """
        result = CheckResult(valid=True, paths_checked=0)

        changes = self._get_changed_files(since_ref)

        for change in changes:
            path = change["path"]
            result.paths_checked += 1

            protection = self._get_protection(path)
            if protection:
                # Check if actor is allowed
                if actor != protection and actor != "system":
                    result.violations.append(PathViolation(
                        path=path,
                        violation_type=change.get("status", "modified"),
                        protected_by=protection,
                        actor=actor,
                        message=f"Path protected by {protection}, modified by {actor}"
                    ))
                    result.valid = False

        return result

    def check_file(self, path: str, actor: str = "builder") -> Optional[PathViolation]:
        """
        Check if a single file path is protected.

        Args:
            path: Path to check
            actor: Actor attempting to modify

        Returns:
            PathViolation if protected, None otherwise
        """
        protection = self._get_protection(path)
        if protection and actor != protection and actor != "system":
            return PathViolation(
                path=path,
                violation_type="access",
                protected_by=protection,
                actor=actor,
                message=f"Path protected by {protection}"
            )
        return None

    def check_paths(
        self,
        paths: List[str],
        actor: str = "builder"
    ) -> CheckResult:
        """
        Check multiple paths for protection.

        Args:
            paths: List of paths to check
            actor: Actor attempting to modify

        Returns:
            CheckResult
        """
        result = CheckResult(valid=True, paths_checked=len(paths))

        for path in paths:
            violation = self.check_file(path, actor)
            if violation:
                result.violations.append(violation)
                result.valid = False

        return result

    def list_protected(self) -> Dict[str, List[str]]:
        """List all protected paths by owner."""
        return self.protected.copy()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check protected paths for violations"
    )
    parser.add_argument("paths", nargs="*", help="Paths to check")
    parser.add_argument("-a", "--actor", default="builder",
                        help="Actor making changes")
    parser.add_argument("-c", "--config", help="Configuration file")
    parser.add_argument("-p", "--path", default=".",
                        help="Base path")
    parser.add_argument("--since", help="Git reference to compare against")
    parser.add_argument("--list", action="store_true",
                        help="List protected paths")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")

    args = parser.parse_args()

    checker = ProtectedPathsChecker(
        config_path=args.config,
        base_path=args.path
    )

    if args.list:
        protected = checker.list_protected()
        if args.json:
            print(json.dumps(protected, indent=2))
        else:
            for owner, paths in protected.items():
                print(f"\n{owner.upper()}:")
                for p in paths:
                    print(f"  - {p}")
        sys.exit(0)

    if args.paths:
        result = checker.check_paths(args.paths, actor=args.actor)
    else:
        result = checker.check_changes(actor=args.actor, since_ref=args.since)

    if args.json:
        print(json.dumps({
            "valid": result.valid,
            "paths_checked": result.paths_checked,
            "violations": [
                {
                    "path": v.path,
                    "type": v.violation_type,
                    "protected_by": v.protected_by,
                    "actor": v.actor,
                    "message": v.message
                }
                for v in result.violations
            ],
            "warnings": result.warnings
        }, indent=2))
    else:
        print(f"Paths checked: {result.paths_checked}")
        print(f"Valid: {'Yes' if result.valid else 'No'}")

        if result.violations:
            print(f"\nViolations ({len(result.violations)}):")
            for v in result.violations:
                print(f"  ❌ {v.path}")
                print(f"     Protected by: {v.protected_by}")
                print(f"     Actor: {v.actor}")

    sys.exit(0 if result.valid else 1)

if __name__ == "__main__":
    main()
