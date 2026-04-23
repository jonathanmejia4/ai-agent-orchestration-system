#!/usr/bin/env python3
"""
Agent Version Compatibility Checker

Validates agent version compatibility using Semantic Versioning (SemVer).
Ensures that agents can communicate using compatible protocol versions.

Usage:
    python3 tools/check_agent_compatibility.py <sender_version> <receiver_version> <required_version>
    python3 tools/check_agent_compatibility.py --work-order <work_order_file.yaml>

Exit Codes:
    0 - Versions are compatible
    1 - Versions are incompatible
    2 - Error (invalid version format, file not found, etc.)

Examples:
    python3 tools/check_agent_compatibility.py 2.0.3 2.1.5 "2.x.x"
    python3 tools/check_agent_compatibility.py --work-order LogBook/work-orders/WO-20251223-001.yaml

References:
    - .claude/guidelines/edge-cases-and-recovery.md - Section 4: Agent Version Compatibility
    - ISSUE_CATALOG.md - Issue A32

Author: System
Created: 2025-12-23
"""

import sys
import re
import yaml
from pathlib import Path
from typing import Tuple

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def parse_version(version: str) -> Tuple[int, int, int]:
    """
    Parse semantic version string into (major, minor, patch) tuple.

    Args:
        version: Version string in format "MAJOR.MINOR.PATCH" or "MAJOR.x.x"

    Returns:
        Tuple of (major, minor, patch) as integers (-1 for 'x' wildcards)

    Raises:
        ValueError: If version format is invalid
    """
    pattern = r'^(\d+|x)\.(\d+|x)\.(\d+|x)$'
    match = re.match(pattern, version.lower())

    if not match:
        raise ValueError(f"Invalid version format: '{version}'. Expected: MAJOR.MINOR.PATCH (e.g., 2.1.0 or 2.x.x)")

    major_str, minor_str, patch_str = match.groups()

    major = -1 if major_str == 'x' else int(major_str)
    minor = -1 if minor_str == 'x' else int(minor_str)
    patch = -1 if patch_str == 'x' else int(patch_str)

    return (major, minor, patch)

def check_compatibility(sender_version: str, receiver_version: str, required_version: str) -> Tuple[bool, str]:
    """
    Check if agent versions are compatible.

    Compatibility Rules (SemVer):
        - MAJOR version must match (breaking changes are incompatible)
        - MINOR version can differ (backward compatible additions)
        - PATCH version can differ (bug fixes are always compatible)

    Args:
        sender_version: Version of sending agent (e.g., "2.0.3")
        receiver_version: Version of receiving agent (e.g., "2.1.5")
        required_version: Required version pattern (e.g., "2.x.x")

    Returns:
        Tuple of (compatible: bool, message: str)

    Examples:
        >>> check_compatibility("2.0.3", "2.1.5", "2.x.x")
        (True, "Compatible")

        >>> check_compatibility("2.0.3", "1.5.0", "2.x.x")
        (False, "INCOMPATIBLE: Receiver v1 cannot handle v2 protocol")
    """
    try:
        sender_major, sender_minor, sender_patch = parse_version(sender_version)
        receiver_major, receiver_minor, receiver_patch = parse_version(receiver_version)
        required_major, required_minor, required_patch = parse_version(required_version)
    except ValueError as e:
        return (False, f"ERROR: {e}")

    # Check MAJOR version compatibility
    if required_major != -1:
        if receiver_major != required_major:
            return (
                False,
                f"INCOMPATIBLE: Receiver v{receiver_major} cannot handle v{required_major} protocol"
            )

    # MINOR and PATCH versions are backward compatible (don't need to match exactly)
    # As long as MAJOR matches, agents can communicate

    return (True, "Compatible")

def check_work_order_compatibility(work_order_path: str) -> Tuple[bool, str]:
    """
    Check agent compatibility from work order file.

    Extracts sender and receiver versions from work order YAML and validates compatibility.

    Args:
        work_order_path: Path to work order YAML file

    Returns:
        Tuple of (compatible: bool, message: str)
    """
    work_order_file = Path(work_order_path)

    if not work_order_file.exists():
        return (False, f"ERROR: Work order file not found: {work_order_path}")

    try:
        with open(work_order_file, 'r') as f:
            work_order = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return (False, f"ERROR: Invalid YAML: {e}")
    except Exception as e:
        return (False, f"ERROR: Failed to read file: {e}")

    # Extract version information
    if 'saf_protocol_version' not in work_order:
        return (False, "ERROR: Missing 'saf_protocol_version' field in work order")

    if 'sender_agent' not in work_order or 'version' not in work_order['sender_agent']:
        return (False, "ERROR: Missing 'sender_agent.version' field in work order")

    if 'receiver_agent' not in work_order or 'version_required' not in work_order['receiver_agent']:
        return (False, "ERROR: Missing 'receiver_agent.version_required' field in work order")

    sender_version = work_order['sender_agent']['version']
    required_version = work_order['receiver_agent']['version_required']

    # For work orders, we assume the receiver is the current system
    # In a real implementation, this would check the actual receiver agent version
    # For now, we validate that the required version pattern is valid

    try:
        required_major, _, _ = parse_version(required_version)
        sender_major, _, _ = parse_version(sender_version)

        if sender_major != required_major:
            return (
                False,
                f"INCOMPATIBLE: Sender v{sender_major} requires receiver v{required_major}.x.x"
            )

        return (True, f"Compatible (protocol v{work_order['saf_protocol_version']})")

    except ValueError as e:
        return (False, f"ERROR: {e}")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(f"Usage:")
        print(f"  {sys.argv[0]} <sender_version> <receiver_version> <required_version>")
        print(f"  {sys.argv[0]} --work-order <work_order_file.yaml>")
        print()
        print(f"Examples:")
        print(f"  {sys.argv[0]} 2.0.3 2.1.5 '2.x.x'")
        print(f"  {sys.argv[0]} --work-order LogBook/work-orders/WO-20251223-001.yaml")
        sys.exit(2)

    # Check if using work order mode
    if sys.argv[1] == '--work-order':
        if len(sys.argv) != 3:
            print(f"{RED}ERROR{NC}: --work-order requires a file path")
            sys.exit(2)

        work_order_path = sys.argv[2]
        compatible, message = check_work_order_compatibility(work_order_path)

    else:
        # Direct version check mode
        if len(sys.argv) != 4:
            print(f"{RED}ERROR{NC}: Requires 3 arguments: sender_version receiver_version required_version")
            sys.exit(2)

        sender_version = sys.argv[1]
        receiver_version = sys.argv[2]
        required_version = sys.argv[3]

        compatible, message = check_compatibility(sender_version, receiver_version, required_version)

    # Print result
    if compatible:
        print(f"{GREEN}✓ {message}{NC}")
        sys.exit(0)
    else:
        print(f"{RED}✗ {message}{NC}")
        sys.exit(1)

if __name__ == '__main__':
    main()
