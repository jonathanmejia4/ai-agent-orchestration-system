#!/usr/bin/env python3
"""
LogBook Access Checker Tool

Validates that only authorized agents write to LogBook directories.
Enforces K002: Single-writer principle per agent directory.

Usage:
    python3 tools/logbook_access_checker.py --agent Builder --path LogBook/builder/status.yaml
    python3 tools/logbook_access_checker.py --agent PM --path LogBook/pm/STATE.md
    python3 tools/logbook_access_checker.py --check-staged  # Pre-commit mode
    python3 tools/logbook_access_checker.py --list-permissions

Exit Codes:
    0 - Write operation allowed
    1 - LogBook access violation
    2 - Configuration error

Referenced by:
    - LogBook/.permissions:10-11

Author: System
Created: 2025-12-29
"""

import argparse
import sys
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

# Default permissions if .permissions file not found
DEFAULT_PERMISSIONS = {
    "LogBook/pm/": "PM",
    "LogBook/planner/": "Planner",
    "LogBook/builder/": "Builder",
    "LogBook/critic/": "Critic",
}

PERMISSIONS_FILE = "LogBook/.permissions"

def load_permissions(permissions_path: str = PERMISSIONS_FILE) -> Dict[str, str]:
    """Load LogBook permissions from .permissions file."""
    permissions = {}

    if not os.path.exists(permissions_path):
        print(f"Warning: {permissions_path} not found, using defaults", file=sys.stderr)
        return DEFAULT_PERMISSIONS.copy()

    with open(permissions_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse "directory: agent" format
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    directory = parts[0].strip()
                    agent = parts[1].strip()
                    permissions[directory] = agent

    return permissions

def get_allowed_agent(path: str, permissions: Dict[str, str]) -> Optional[str]:
    """Get the agent allowed to write to a given path."""
    # Normalize path
    path = path.lstrip('./')

    # Find matching permission
    for directory, agent in permissions.items():
        dir_norm = directory.rstrip('/')
        if path.startswith(dir_norm + '/') or path == dir_norm:
            return agent

    return None

def check_access(agent: str, path: str, permissions: Dict[str, str]) -> Tuple[bool, str]:
    """
    Check if agent can write to path.

    Returns:
        (allowed: bool, reason: str)
    """
    # Only check LogBook paths
    if not path.startswith("LogBook/"):
        return True, "Path is not in LogBook"

    allowed_agent = get_allowed_agent(path, permissions)

    if allowed_agent is None:
        return True, "Path not covered by permissions (allowed by default)"

    if agent.lower() == allowed_agent.lower():
        return True, f"Agent '{agent}' is authorized for {path}"

    return False, f"Agent '{agent}' is NOT authorized for {path} (only '{allowed_agent}' can write)"

def get_staged_files() -> list:
    """Get list of staged files (for pre-commit mode)."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
            capture_output=True, text=True, check=True
        )
        return [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
    except subprocess.CalledProcessError:
        return []

def get_agent_from_env() -> Optional[str]:
    """Get agent identity from environment variable."""
    return os.environ.get('AGENT_NAME')

def main():
    parser = argparse.ArgumentParser(
        description='Check LogBook access permissions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check if Builder can write to its LogBook
    %(prog)s --agent Builder --path LogBook/builder/status.yaml

    # Check if PM can write to STATE.md
    %(prog)s --agent PM --path LogBook/pm/STATE.md

    # Pre-commit mode: check all staged files
    AGENT_NAME=Builder %(prog)s --check-staged

    # List all permissions
    %(prog)s --list-permissions

Environment Variables:
    AGENT_NAME - Agent identity for --check-staged mode
        """
    )

    parser.add_argument('--agent', '-a',
                       help='Agent attempting write (PM, Builder, Planner, Critic)')
    parser.add_argument('--path', '-p',
                       help='Path to validate')
    parser.add_argument('--check-staged', action='store_true',
                       help='Check all staged LogBook files (pre-commit mode)')
    parser.add_argument('--list-permissions', '-l', action='store_true',
                       help='List all LogBook permissions')
    parser.add_argument('--permissions-file', default=PERMISSIONS_FILE,
                       help=f'Path to permissions file (default: {PERMISSIONS_FILE})')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    permissions = load_permissions(args.permissions_file)

    if args.list_permissions:
        print("=== LogBook Access Permissions ===\n")
        for directory, agent in permissions.items():
            print(f"  {directory} -> {agent}")
        print("\nRule: Each agent can only write to their assigned directory")
        sys.exit(0)

    if args.check_staged:
        # Pre-commit mode
        agent = args.agent or get_agent_from_env()
        if not agent:
            print("Error: AGENT_NAME environment variable or --agent required for --check-staged")
            sys.exit(2)

        staged_files = get_staged_files()
        logbook_files = [f for f in staged_files if f.startswith('LogBook/')]

        if not logbook_files:
            if args.verbose:
                print("No LogBook files in staging area")
            sys.exit(0)

        violations = []
        for path in logbook_files:
            allowed, reason = check_access(agent, path, permissions)
            if not allowed:
                violations.append((path, reason))
            elif args.verbose:
                print(f"✅ {path}: {reason}")

        if violations:
            print("\n❌ LogBook Access Violations Detected:\n")
            for path, reason in violations:
                print(f"  • {path}")
                print(f"    {reason}\n")
            print(f"Agent '{agent}' attempted to modify {len(violations)} file(s) outside their LogBook directory.")
            print("This commit has been blocked.")
            sys.exit(1)

        print(f"✅ LogBook access check passed ({len(logbook_files)} file(s) checked)")
        sys.exit(0)

    # Single file check mode
    if not args.agent or not args.path:
        parser.print_help()
        sys.exit(2)

    allowed, reason = check_access(args.agent, args.path, permissions)

    if allowed:
        print(f"\033[92m✅ Access allowed: {args.agent} → {args.path}\033[0m")
        print(f"   Reason: {reason}")
        sys.exit(0)
    else:
        print(f"\033[91m❌ Access BLOCKED: {args.agent} → {args.path}\033[0m")
        print(f"   Reason: {reason}")
        sys.exit(1)

if __name__ == '__main__':
    main()
