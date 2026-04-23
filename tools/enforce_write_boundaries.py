#!/usr/bin/env python3
"""
Write Boundary Enforcement Tool

Validates that agents only write to paths they are authorized to access.
Enforces PM-only write boundaries defined in PM_Operating_Manual.md.

Usage:
    python3 tools/enforce_write_boundaries.py --agent Builder --path PLANNING/spec.md
    python3 tools/enforce_write_boundaries.py --agent PM --path LogBook/pm/STATE.md
    python3 tools/enforce_write_boundaries.py --agent Critic --path LogBook/critic/verdicts/VER-001.yaml
    python3 tools/enforce_write_boundaries.py --list-boundaries
    python3 tools/enforce_write_boundaries.py --help

Exit Codes:
    0 - Write operation allowed
    1 - Write boundary violation
    2 - Invalid agent identity or configuration error

Referenced in:
    - PM_Operating_Manual.md:1066, 1068, 1069, 1073, 1074, 1076, 1078

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import re
import json
import fnmatch
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

# PM-only write paths from PM_Operating_Manual.md:1066-1078
PM_ONLY_PATHS = [
    'LogBook/**',           # PM only (except agents' own entries)
    'PLANNING/**',          # PM only (authoritative specs)
    'archives/golden/**',   # PM only (promotion archive)
    'archives/bad/**',      # PM only (rejection archive)
    '.claude/agents/**',    # PM only (or Human)
    '.claude/guidelines/**',# PM only (or Human)
    'integration/config/**',# PM only (or Human)
    'LogBook/pm/STATE.md',  # PM only (PM working memory)
]

# Agent-specific allowed write paths (exceptions to PM-only)
AGENT_ALLOWED_PATHS = {
    'PM': ['**'],  # PM can write anywhere
    'Human': ['**'],  # Human can write anywhere
    'Builder': [
        'tasks/**',
        'src/**',
        'tests/**',
        '.task/**',
        'LogBook/builder/**',  # Builder's LogBook path (read work-orders, write only to builder/)
    ],
    'Planner': [
        'LogBook/progress/plans/**',  # Planner's assigned LogBook path
    ],
    'Critic': [
        'LogBook/critic/**',  # Critic's assigned LogBook path
    ],
    'Orchestrator': [
        'LogBook/critic/requests/**',  # Orchestrator can create review requests
    ],
}

# Valid agent names
VALID_AGENTS = {'PM', 'Builder', 'Planner', 'Critic', 'Orchestrator', 'Human'}

@dataclass
class BoundaryCheckResult:
    """Result of boundary check"""
    allowed: bool = True
    agent: str = ""
    path: str = ""
    matched_rule: Optional[str] = None
    reason: Optional[str] = None
    is_pm_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class WriteBoundaryEnforcer:
    """Enforces write boundaries for the system agents"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.pm_only_patterns = PM_ONLY_PATHS
        self.agent_allowed = AGENT_ALLOWED_PATHS

    def log(self, message: str):
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def normalize_path(self, path: str) -> str:
        """Normalize path for matching"""
        # Remove leading ./ or /
        path = path.lstrip('./')
        # Normalize separators
        path = path.replace('\\', '/')
        return path

    def path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches a glob pattern"""
        path = self.normalize_path(path)
        pattern = self.normalize_path(pattern)

        # Handle ** patterns
        if '**' in pattern:
            # Convert to regex
            regex = pattern.replace('.', r'\.')
            regex = regex.replace('**', '.*')
            regex = regex.replace('*', '[^/]*')
            regex = f'^{regex}$'
            return bool(re.match(regex, path))
        else:
            return fnmatch.fnmatch(path, pattern)

    def is_pm_only_path(self, path: str) -> Tuple[bool, Optional[str]]:
        """Check if path is PM-only"""
        for pattern in self.pm_only_patterns:
            if self.path_matches_pattern(path, pattern):
                self.log(f"Path '{path}' matches PM-only pattern '{pattern}'")
                return True, pattern
        return False, None

    def is_agent_allowed(self, agent: str, path: str) -> Tuple[bool, Optional[str]]:
        """Check if agent is allowed to write to path"""
        if agent not in self.agent_allowed:
            return False, None

        for pattern in self.agent_allowed[agent]:
            if self.path_matches_pattern(path, pattern):
                self.log(f"Agent '{agent}' allowed by pattern '{pattern}'")
                return True, pattern
        return False, None

    def check_write_boundary(self, agent: str, path: str) -> BoundaryCheckResult:
        """Check if agent can write to path"""
        result = BoundaryCheckResult(agent=agent, path=path)

        # Validate agent
        if agent not in VALID_AGENTS:
            result.allowed = False
            result.reason = f"Invalid agent: {agent}. Valid agents: {', '.join(VALID_AGENTS)}"
            return result

        # PM and Human can write anywhere
        if agent in ('PM', 'Human'):
            result.allowed = True
            result.matched_rule = "PM/Human: full access"
            result.reason = f"{agent} has full write access"
            return result

        # Check if path is PM-only
        is_pm_only, pm_pattern = self.is_pm_only_path(path)
        result.is_pm_only = is_pm_only

        if is_pm_only:
            # Check if agent has explicit exception
            has_exception, exception_pattern = self.is_agent_allowed(agent, path)

            if has_exception:
                result.allowed = True
                result.matched_rule = exception_pattern
                result.reason = f"Agent '{agent}' allowed by exception: {exception_pattern}"
            else:
                result.allowed = False
                result.matched_rule = pm_pattern
                result.reason = f"PM-only path: {pm_pattern}"
        else:
            # Path is not PM-only, check agent-specific rules
            has_permission, pattern = self.is_agent_allowed(agent, path)

            if has_permission:
                result.allowed = True
                result.matched_rule = pattern
                result.reason = f"Agent '{agent}' allowed by: {pattern}"
            else:
                # Default: allow if not PM-only and no explicit restrictions
                result.allowed = True
                result.reason = "Path not restricted"

        return result

    def list_boundaries(self) -> Dict[str, Any]:
        """List all write boundaries"""
        return {
            'pm_only_paths': self.pm_only_patterns,
            'agent_allowed_paths': self.agent_allowed,
            'valid_agents': list(VALID_AGENTS)
        }

def print_result(result: BoundaryCheckResult, format: str = "text"):
    """Print boundary check result"""
    if format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return

    if result.allowed:
        print(f"\033[92m✅ Write allowed: {result.agent} → {result.path}\033[0m")
    else:
        print(f"\033[91m❌ Write BLOCKED: {result.agent} → {result.path}\033[0m")

    if result.reason:
        print(f"   Reason: {result.reason}")

    if result.matched_rule:
        print(f"   Rule: {result.matched_rule}")

def print_boundaries(boundaries: Dict[str, Any], format: str = "text"):
    """Print all boundaries"""
    if format == "json":
        print(json.dumps(boundaries, indent=2))
        return

    print("\n=== PM-Only Write Paths ===")
    for path in boundaries['pm_only_paths']:
        print(f"  • {path}")

    print("\n=== Agent-Specific Allowed Paths ===")
    for agent, paths in boundaries['agent_allowed_paths'].items():
        print(f"\n  {agent}:")
        for path in paths:
            print(f"    • {path}")

    print(f"\n=== Valid Agents ===")
    print(f"  {', '.join(boundaries['valid_agents'])}")

def main():
    parser = argparse.ArgumentParser(
        description='Enforce write boundaries for the system agents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check if Builder can write to PLANNING/
    %(prog)s --agent Builder --path PLANNING/spec.md
    # Returns: Exit 1 (Builder cannot write to PLANNING/**)

    # Check if PM can write anywhere
    %(prog)s --agent PM --path LogBook/pm/STATE.md
    # Returns: Exit 0 (PM can write anywhere)

    # Check if Critic can write to verdicts
    %(prog)s --agent Critic --path LogBook/critic/verdicts/VER-001.yaml
    # Returns: Exit 0 (Critic allowed in LogBook/critic/**)

    # List all write boundaries
    %(prog)s --list-boundaries

Exit Codes:
    0 - Write operation allowed
    1 - Write boundary violation
    2 - Invalid agent identity or configuration error
        """
    )

    parser.add_argument('--agent', '-a',
                       help='Agent attempting write (PM, Builder, Planner, Critic, Orchestrator, Human)')
    parser.add_argument('--path', '-p',
                       help='Path to validate')
    parser.add_argument('--list-boundaries', '-l', action='store_true',
                       help='List all write boundaries')
    parser.add_argument('--format', '-f', choices=['text', 'json'], default='text',
                       help='Output format')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    enforcer = WriteBoundaryEnforcer(verbose=args.verbose)

    if args.list_boundaries:
        boundaries = enforcer.list_boundaries()
        print_boundaries(boundaries, args.format)
        sys.exit(0)

    if not args.agent or not args.path:
        parser.print_help()
        sys.exit(2)

    # Validate agent
    if args.agent not in VALID_AGENTS:
        print(f"\033[91mError: Invalid agent '{args.agent}'\033[0m")
        print(f"Valid agents: {', '.join(VALID_AGENTS)}")
        sys.exit(2)

    # Check boundary
    result = enforcer.check_write_boundary(args.agent, args.path)
    print_result(result, args.format)

    sys.exit(0 if result.allowed else 1)

if __name__ == '__main__':
    main()
