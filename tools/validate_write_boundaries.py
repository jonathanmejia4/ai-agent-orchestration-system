#!/usr/bin/env python3
"""
validate_write_boundaries.py - Agent Write Boundary Validation Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Scope Enforcement

Purpose:
    Validates that agent write operations comply with defined boundaries.
    Prevents unauthorized cross-agent file modifications.

Usage:
    python3 validate_write_boundaries.py --agent <agent> --path <path>
    python3 validate_write_boundaries.py --check-commit
    python3 validate_write_boundaries.py --audit

Reference: .claude/guidelines/pm-write-boundaries.md
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# =============================================================================
# Configuration
# =============================================================================

class Agent(Enum):
    """the agent types."""
    PM = "pm"
    BUILDER = "builder"
    CRITIC = "critic"
    PLANNER = "planner"
    HUMAN = "human"
    SYSTEM = "system"

@dataclass
class BoundaryConfig:
    """Configuration for write boundaries."""

    # PM-Exclusive paths
    pm_exclusive_paths: List[str] = field(default_factory=lambda: [
        "LogBook/pm/",
        "LogBook/escalations/",
        "PLANNING/MASTER_PLAN.md",
        "PLANNING/WORK_ORDER_QUEUE.yaml",
        "ISSUE_CATALOG.md",
        "PLANNING/PROJECT_CONTEXT.md",
        "PLANNING/MILESTONE_TRACKER.md",
    ])

    # Agent LogBook paths (each agent owns their directory)
    agent_logbook_paths: Dict[str, str] = field(default_factory=lambda: {
        "pm": "LogBook/pm/",
        "builder": "LogBook/builder/",
        "critic": "LogBook/critic/",
        "planner": "LogBook/planner/",
    })

    # Shared paths (multiple agents can write)
    shared_paths: List[str] = field(default_factory=lambda: [
        "PLANNING/AGENT_BEST_PRACTICES.md",
        ".claude/guidelines/",
        "tools/",
        "tests/",
    ])

    # Protected paths (require approval for any write)
    protected_paths: List[str] = field(default_factory=lambda: [
        "CLAUDE.md",
        "FAILURE_MODES.md",
        "ROLLBACK_PROCEDURES.md",
        ".claude/guidelines/agent-guardrails.md",
    ])

    # Builder allowed paths
    builder_allowed_paths: List[str] = field(default_factory=lambda: [
        "LogBook/builder/",
        "src/",
        "tools/",
        "tests/",
        "task*/",
    ])

    # Critic allowed paths
    critic_allowed_paths: List[str] = field(default_factory=lambda: [
        "LogBook/critic/",
    ])

    # Planner allowed paths
    planner_allowed_paths: List[str] = field(default_factory=lambda: [
        "LogBook/planner/",
        "PLANNING/",
    ])

# =============================================================================
# Validation Classes
# =============================================================================

@dataclass
class ValidationResult:
    """Result of a boundary validation."""
    valid: bool
    agent: str
    path: str
    reason: str
    boundary_type: str = "unknown"
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "agent": self.agent,
            "path": self.path,
            "reason": self.reason,
            "boundary_type": self.boundary_type,
            "suggestions": self.suggestions,
        }

class WriteBoundaryValidator:
    """Validates write operations against agent boundaries."""

    def __init__(self, config: Optional[BoundaryConfig] = None):
        self.config = config or BoundaryConfig()
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile path patterns for efficient matching."""
        self.pm_exclusive_patterns = [
            self._path_to_pattern(p) for p in self.config.pm_exclusive_paths
        ]
        self.protected_patterns = [
            self._path_to_pattern(p) for p in self.config.protected_paths
        ]

    def _path_to_pattern(self, path: str) -> re.Pattern:
        """Convert a path pattern to a regex pattern."""
        # Escape special chars except * and /
        escaped = re.escape(path).replace(r"\*", ".*")
        # Handle directory patterns (ending with /)
        if path.endswith("/"):
            escaped = escaped.rstrip("/") + "/.*"
        return re.compile(f"^{escaped}$")

    def _matches_any_pattern(self, path: str, patterns: List[re.Pattern]) -> bool:
        """Check if path matches any of the given patterns."""
        normalized = self._normalize_path(path)
        for pattern in patterns:
            if pattern.match(normalized):
                return True
        return False

    def _normalize_path(self, path: str) -> str:
        """Normalize a path for comparison."""
        # Remove leading ./ or /
        path = path.lstrip("./")
        # Normalize separators
        path = path.replace("\\", "/")
        return path

    def validate_write(self, agent: str, path: str) -> ValidationResult:
        """
        Validate if an agent can write to the given path.

        Args:
            agent: The agent attempting the write (pm, builder, critic, planner)
            path: The path being written to

        Returns:
            ValidationResult with validation details
        """
        normalized_path = self._normalize_path(path)
        agent_lower = agent.lower()

        # Check protected paths first
        if self._is_protected_path(normalized_path):
            return ValidationResult(
                valid=False,
                agent=agent,
                path=path,
                reason=f"Protected path requires approval: {normalized_path}",
                boundary_type="protected",
                suggestions=[
                    "Request approval via .claude/hooks/critical-action-validator.sh",
                    "Document change rationale before proceeding",
                    "Follow Tier 1 policy change process"
                ]
            )

        # Agent-specific validation
        if agent_lower == "pm":
            return self._validate_pm_write(normalized_path)
        elif agent_lower == "builder":
            return self._validate_builder_write(normalized_path)
        elif agent_lower == "critic":
            return self._validate_critic_write(normalized_path)
        elif agent_lower == "planner":
            return self._validate_planner_write(normalized_path)
        elif agent_lower in ("human", "system"):
            # Human and system have full access
            return ValidationResult(
                valid=True,
                agent=agent,
                path=path,
                reason=f"{agent} has unrestricted write access",
                boundary_type="unrestricted"
            )
        else:
            return ValidationResult(
                valid=False,
                agent=agent,
                path=path,
                reason=f"Unknown agent type: {agent}",
                boundary_type="unknown_agent"
            )

    def _is_protected_path(self, path: str) -> bool:
        """Check if path is in protected list."""
        for protected in self.config.protected_paths:
            if path == protected or path.startswith(protected.rstrip("/")):
                return True
        return False

    def _validate_pm_write(self, path: str) -> ValidationResult:
        """Validate PM write operation."""
        # PM can write to PM-exclusive paths
        for pm_path in self.config.pm_exclusive_paths:
            if path.startswith(pm_path.rstrip("/")) or path == pm_path.rstrip("/"):
                return ValidationResult(
                    valid=True,
                    agent="pm",
                    path=path,
                    reason="PM-exclusive path",
                    boundary_type="pm_exclusive"
                )

        # PM can write to shared paths
        for shared in self.config.shared_paths:
            if path.startswith(shared.rstrip("/")):
                return ValidationResult(
                    valid=True,
                    agent="pm",
                    path=path,
                    reason="Shared path accessible to PM",
                    boundary_type="shared"
                )

        # Check if PM is trying to write to other agent's LogBook
        for agent_name, logbook_path in self.config.agent_logbook_paths.items():
            if agent_name != "pm" and path.startswith(logbook_path.rstrip("/")):
                return ValidationResult(
                    valid=False,
                    agent="pm",
                    path=path,
                    reason=f"Cannot write to {agent_name}'s LogBook",
                    boundary_type="cross_agent_violation",
                    suggestions=[
                        f"Use LogBook/pm/ for PM-specific logging",
                        f"Request {agent_name} to update their own LogBook",
                        "Use escalation mechanism for cross-agent communication"
                    ]
                )

        # Default: PM has broader access for coordination
        return ValidationResult(
            valid=True,
            agent="pm",
            path=path,
            reason="PM has coordination access",
            boundary_type="pm_coordination"
        )

    def _validate_builder_write(self, path: str) -> ValidationResult:
        """Validate Builder write operation."""
        # Builder can write to their LogBook
        if path.startswith("LogBook/builder/"):
            return ValidationResult(
                valid=True,
                agent="builder",
                path=path,
                reason="Builder's LogBook directory",
                boundary_type="agent_logbook"
            )

        # Builder can write to implementation paths
        for allowed in self.config.builder_allowed_paths:
            if path.startswith(allowed.rstrip("/").replace("*", "")):
                return ValidationResult(
                    valid=True,
                    agent="builder",
                    path=path,
                    reason="Builder implementation path",
                    boundary_type="builder_allowed"
                )

        # Check PM-exclusive violation
        for pm_path in self.config.pm_exclusive_paths:
            if path.startswith(pm_path.rstrip("/")):
                return ValidationResult(
                    valid=False,
                    agent="builder",
                    path=path,
                    reason=f"PM-exclusive path: {pm_path}",
                    boundary_type="pm_exclusive_violation",
                    suggestions=[
                        "Request PM to make this update",
                        "Use LogBook/builder/ for builder logs",
                        "Escalate if urgent"
                    ]
                )

        # Check other agent LogBook violation
        for agent_name, logbook_path in self.config.agent_logbook_paths.items():
            if agent_name != "builder" and path.startswith(logbook_path.rstrip("/")):
                return ValidationResult(
                    valid=False,
                    agent="builder",
                    path=path,
                    reason=f"Cannot write to {agent_name}'s LogBook",
                    boundary_type="cross_agent_violation",
                    suggestions=[
                        "Use LogBook/builder/ for builder logging",
                        f"Request {agent_name} to update their LogBook"
                    ]
                )

        # Shared paths
        for shared in self.config.shared_paths:
            if path.startswith(shared.rstrip("/")):
                return ValidationResult(
                    valid=True,
                    agent="builder",
                    path=path,
                    reason="Shared path",
                    boundary_type="shared"
                )

        return ValidationResult(
            valid=False,
            agent="builder",
            path=path,
            reason="Path not in Builder's allowed boundaries",
            boundary_type="outside_boundary",
            suggestions=[
                "Check if this path should be in Builder's scope",
                "Request PM approval for boundary extension"
            ]
        )

    def _validate_critic_write(self, path: str) -> ValidationResult:
        """Validate Critic write operation."""
        # Critic can write to their LogBook
        if path.startswith("LogBook/critic/"):
            return ValidationResult(
                valid=True,
                agent="critic",
                path=path,
                reason="Critic's LogBook directory",
                boundary_type="agent_logbook"
            )

        # Critic has very limited write scope
        for pm_path in self.config.pm_exclusive_paths:
            if path.startswith(pm_path.rstrip("/")):
                return ValidationResult(
                    valid=False,
                    agent="critic",
                    path=path,
                    reason=f"PM-exclusive path: {pm_path}",
                    boundary_type="pm_exclusive_violation",
                    suggestions=[
                        "Critic should only write verdicts to LogBook/critic/",
                        "Communicate findings via verdict entries"
                    ]
                )

        # Check other agent LogBook violation
        for agent_name, logbook_path in self.config.agent_logbook_paths.items():
            if agent_name != "critic" and path.startswith(logbook_path.rstrip("/")):
                return ValidationResult(
                    valid=False,
                    agent="critic",
                    path=path,
                    reason=f"Cannot write to {agent_name}'s LogBook",
                    boundary_type="cross_agent_violation",
                    suggestions=[
                        "Use LogBook/critic/ for critic logging",
                        "Include findings in verdict entries"
                    ]
                )

        return ValidationResult(
            valid=False,
            agent="critic",
            path=path,
            reason="Critic can only write to LogBook/critic/",
            boundary_type="outside_boundary",
            suggestions=[
                "Critic role is read-only except for verdicts",
                "Use LogBook/critic/verdicts.yaml for review outcomes"
            ]
        )

    def _validate_planner_write(self, path: str) -> ValidationResult:
        """Validate Planner write operation."""
        # Planner can write to their LogBook
        if path.startswith("LogBook/planner/"):
            return ValidationResult(
                valid=True,
                agent="planner",
                path=path,
                reason="Planner's LogBook directory",
                boundary_type="agent_logbook"
            )

        # Planner can write to PLANNING directory (except PM-exclusive files)
        if path.startswith("PLANNING/"):
            # Check PM-exclusive files in PLANNING
            pm_planning_files = [
                "PLANNING/MASTER_PLAN.md",
                "PLANNING/WORK_ORDER_QUEUE.yaml",
                "PLANNING/PROJECT_CONTEXT.md",
                "PLANNING/MILESTONE_TRACKER.md",
            ]
            if path in pm_planning_files:
                return ValidationResult(
                    valid=False,
                    agent="planner",
                    path=path,
                    reason="PM-exclusive planning file",
                    boundary_type="pm_exclusive_violation",
                    suggestions=[
                        "Submit planning updates via LogBook/planner/",
                        "Request PM to incorporate changes"
                    ]
                )
            return ValidationResult(
                valid=True,
                agent="planner",
                path=path,
                reason="Planner planning directory",
                boundary_type="planner_allowed"
            )

        # Check other agent LogBook violation
        for agent_name, logbook_path in self.config.agent_logbook_paths.items():
            if agent_name != "planner" and path.startswith(logbook_path.rstrip("/")):
                return ValidationResult(
                    valid=False,
                    agent="planner",
                    path=path,
                    reason=f"Cannot write to {agent_name}'s LogBook",
                    boundary_type="cross_agent_violation",
                    suggestions=[
                        "Use LogBook/planner/ for planner logging",
                        f"Request {agent_name} to update their LogBook"
                    ]
                )

        return ValidationResult(
            valid=False,
            agent="planner",
            path=path,
            reason="Path not in Planner's allowed boundaries",
            boundary_type="outside_boundary",
            suggestions=[
                "Planner can write to LogBook/planner/ and PLANNING/",
                "Request PM for boundary extension if needed"
            ]
        )

# =============================================================================
# Git Integration
# =============================================================================

class GitBoundaryChecker:
    """Checks git commits against write boundaries."""

    def __init__(self, validator: WriteBoundaryValidator):
        self.validator = validator

    def check_staged_files(self, agent: str) -> Tuple[List[ValidationResult], bool]:
        """
        Check all staged files against boundaries.

        Returns:
            Tuple of (list of results, overall pass/fail)
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                check=True
            )
            staged_files = result.stdout.strip().split("\n")
            staged_files = [f for f in staged_files if f]  # Remove empty strings
        except subprocess.CalledProcessError:
            return [], True  # No git or no staged files

        results = []
        all_valid = True

        for file_path in staged_files:
            validation = self.validator.validate_write(agent, file_path)
            results.append(validation)
            if not validation.valid:
                all_valid = False

        return results, all_valid

    def check_commit_author(self) -> Optional[str]:
        """
        Try to determine agent from commit context.

        Returns agent name if determinable, None otherwise.
        """
        import subprocess

        # Check for agent hints in environment or git config
        import os

        # Check environment variable
        agent = os.environ.get("AGENT_NAME")
        if agent:
            return agent.lower()

        # Try to infer from git user
        try:
            result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True,
                text=True,
                check=True
            )
            user = result.stdout.strip().lower()

            # Check for agent keywords
            for agent_name in ["pm", "builder", "critic", "planner"]:
                if agent_name in user:
                    return agent_name
        except subprocess.CalledProcessError:
            pass

        return None

# =============================================================================
# Audit Functions
# =============================================================================

def audit_boundaries(base_path: str = ".") -> Dict:
    """
    Audit current file structure against boundary definitions.

    Returns audit report dictionary.
    """
    base = Path(base_path)
    validator = WriteBoundaryValidator()

    audit_report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "base_path": str(base.absolute()),
        "pm_exclusive_files": [],
        "shared_files": [],
        "agent_logbook_files": {},
        "protected_files": [],
        "unclassified_files": [],
    }

    # Initialize agent logbook tracking
    for agent in validator.config.agent_logbook_paths:
        audit_report["agent_logbook_files"][agent] = []

    # Scan relevant directories
    scan_dirs = ["LogBook", "PLANNING", ".claude", "tools"]

    for scan_dir in scan_dirs:
        dir_path = base / scan_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(base))

                # Classify file
                classified = False

                # Check PM-exclusive
                for pm_path in validator.config.pm_exclusive_paths:
                    if rel_path.startswith(pm_path.rstrip("/")):
                        audit_report["pm_exclusive_files"].append(rel_path)
                        classified = True
                        break

                if classified:
                    continue

                # Check protected
                if validator._is_protected_path(rel_path):
                    audit_report["protected_files"].append(rel_path)
                    continue

                # Check agent LogBooks
                for agent, logbook_path in validator.config.agent_logbook_paths.items():
                    if rel_path.startswith(logbook_path.rstrip("/")):
                        audit_report["agent_logbook_files"][agent].append(rel_path)
                        classified = True
                        break

                if classified:
                    continue

                # Check shared
                for shared in validator.config.shared_paths:
                    if rel_path.startswith(shared.rstrip("/")):
                        audit_report["shared_files"].append(rel_path)
                        classified = True
                        break

                if not classified:
                    audit_report["unclassified_files"].append(rel_path)

    return audit_report

# =============================================================================
# CLI Interface
# =============================================================================

def print_validation_result(result: ValidationResult, verbose: bool = False):
    """Print a validation result."""
    status = "✓" if result.valid else "✗"
    color_start = "\033[92m" if result.valid else "\033[91m"
    color_end = "\033[0m"

    print(f"{color_start}{status}{color_end} [{result.agent}] {result.path}")
    print(f"    {result.reason}")

    if verbose and result.suggestions:
        print("    Suggestions:")
        for suggestion in result.suggestions:
            print(f"      - {suggestion}")

def main():
    parser = argparse.ArgumentParser(
        description="Validate agent write boundaries in the system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Validate a single path:
    %(prog)s --agent builder --path src/module.py

  Check staged git files:
    %(prog)s --check-commit --agent builder

  Audit current boundaries:
    %(prog)s --audit

  Generate JSON report:
    %(prog)s --agent pm --path LogBook/pm/STATE.md --json
        """
    )

    parser.add_argument(
        "--agent",
        choices=["pm", "builder", "critic", "planner", "human", "system"],
        help="Agent performing the write operation"
    )
    parser.add_argument(
        "--path",
        help="Path being written to"
    )
    parser.add_argument(
        "--check-commit",
        action="store_true",
        help="Check staged files in git commit"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Audit current file structure against boundaries"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output with suggestions"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error on any invalid boundary"
    )

    args = parser.parse_args()

    validator = WriteBoundaryValidator()

    # Audit mode
    if args.audit:
        report = audit_boundaries()

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("=" * 60)
            print("the system Write Boundary Audit Report")
            print("=" * 60)
            print(f"Timestamp: {report['timestamp']}")
            print(f"Base Path: {report['base_path']}")
            print()

            print(f"PM-Exclusive Files: {len(report['pm_exclusive_files'])}")
            for f in report['pm_exclusive_files'][:5]:
                print(f"  - {f}")
            if len(report['pm_exclusive_files']) > 5:
                print(f"  ... and {len(report['pm_exclusive_files']) - 5} more")

            print(f"\nProtected Files: {len(report['protected_files'])}")
            for f in report['protected_files']:
                print(f"  - {f}")

            print(f"\nAgent LogBook Files:")
            for agent, files in report['agent_logbook_files'].items():
                print(f"  {agent}: {len(files)} files")

            print(f"\nShared Files: {len(report['shared_files'])}")
            print(f"Unclassified Files: {len(report['unclassified_files'])}")

            if args.verbose and report['unclassified_files']:
                print("\nUnclassified files:")
                for f in report['unclassified_files']:
                    print(f"  - {f}")

        return 0

    # Check commit mode
    if args.check_commit:
        if not args.agent:
            # Try to infer agent
            checker = GitBoundaryChecker(validator)
            agent = checker.check_commit_author()
            if not agent:
                print("Error: Could not determine agent. Use --agent flag.")
                return 2
        else:
            agent = args.agent
            checker = GitBoundaryChecker(validator)

        results, all_valid = checker.check_staged_files(agent)

        if args.json:
            output = {
                "agent": agent,
                "all_valid": all_valid,
                "results": [r.to_dict() for r in results]
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Checking staged files for agent: {agent}")
            print("-" * 40)

            for result in results:
                print_validation_result(result, args.verbose)

            print("-" * 40)
            if all_valid:
                print("✓ All files within boundaries")
            else:
                print("✗ Boundary violations detected")

        return 0 if all_valid else (1 if args.strict else 0)

    # Single path validation
    if args.agent and args.path:
        result = validator.validate_write(args.agent, args.path)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print_validation_result(result, args.verbose)

        return 0 if result.valid else (1 if args.strict else 0)

    # No valid command
    parser.print_help()
    return 2

if __name__ == "__main__":
    sys.exit(main())
