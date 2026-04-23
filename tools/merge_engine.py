#!/usr/bin/env python3
"""
Three-Way Merge Engine
Version: 1.0.0
Last Updated: 2025-12-29
Owner: Builder
Classification: HIGH - Merge Operations

Implements three-way merge algorithm for the system regeneration workflow.

Usage:
    python tools/merge_engine.py <base> <local> <remote> [--output <file>]
    python tools/merge_engine.py --help

See: PLANNING/THREE_WAY_MERGE_REGENERATION_POLICY.md
"""

import argparse
import difflib
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

class ConflictResolution(Enum):
    """How a conflict was resolved."""
    AUTO_MERGED = "auto_merged"
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    MANUAL_REQUIRED = "manual_required"

@dataclass
class MergeConflict:
    """Represents a merge conflict."""
    line_start: int
    line_end: int
    base_content: List[str]
    local_content: List[str]
    remote_content: List[str]
    resolution: Optional[ConflictResolution] = None
    resolved_content: Optional[List[str]] = None

@dataclass
class MergeResult:
    """Result of a three-way merge."""
    success: bool
    merged_content: List[str]
    conflicts: List[MergeConflict]
    stats: dict

def read_file(path: Path) -> List[str]:
    """Read file and return lines."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text().splitlines(keepends=True)

def compute_diff(base: List[str], target: List[str]) -> List[Tuple[str, int, int, int, int]]:
    """Compute unified diff between base and target."""
    matcher = difflib.SequenceMatcher(None, base, target)
    opcodes = matcher.get_opcodes()
    return opcodes

def three_way_merge(
    base: List[str],
    local: List[str],
    remote: List[str],
    prefer_local: bool = False
) -> MergeResult:
    """
    Perform three-way merge.

    Args:
        base: Original content (common ancestor)
        local: Local modifications
        remote: Remote/regenerated content
        prefer_local: If true, prefer local changes in conflicts

    Returns:
        MergeResult with merged content and any conflicts
    """
    merged = []
    conflicts = []

    local_diff = compute_diff(base, local)
    remote_diff = compute_diff(base, remote)

    # Build change maps
    local_changes = {}
    remote_changes = {}

    for tag, i1, i2, j1, j2 in local_diff:
        if tag != 'equal':
            for i in range(i1, i2):
                local_changes[i] = (tag, local[j1:j2] if j2 > j1 else [])

    for tag, i1, i2, j1, j2 in remote_diff:
        if tag != 'equal':
            for i in range(i1, i2):
                remote_changes[i] = (tag, remote[j1:j2] if j2 > j1 else [])

    # Merge line by line
    i = 0
    local_offset = 0
    remote_offset = 0

    while i < len(base):
        local_change = local_changes.get(i)
        remote_change = remote_changes.get(i)

        if local_change is None and remote_change is None:
            # No changes, keep base
            merged.append(base[i])
            i += 1
        elif local_change is not None and remote_change is None:
            # Only local changed
            if local_change[0] == 'delete':
                pass  # Skip deleted line
            else:
                merged.extend(local_change[1])
            i += 1
        elif local_change is None and remote_change is not None:
            # Only remote changed
            if remote_change[0] == 'delete':
                pass  # Skip deleted line
            else:
                merged.extend(remote_change[1])
            i += 1
        else:
            # Both changed - conflict
            if local_change[1] == remote_change[1]:
                # Same change, no conflict
                merged.extend(local_change[1])
            else:
                # Real conflict
                conflict = MergeConflict(
                    line_start=len(merged),
                    line_end=len(merged),
                    base_content=[base[i]] if i < len(base) else [],
                    local_content=local_change[1],
                    remote_content=remote_change[1]
                )

                if prefer_local:
                    merged.extend(local_change[1])
                    conflict.resolution = ConflictResolution.LOCAL_WINS
                    conflict.resolved_content = local_change[1]
                else:
                    # Mark conflict in output
                    merged.append(f"<<<<<<< LOCAL\n")
                    merged.extend(local_change[1])
                    merged.append(f"=======\n")
                    merged.extend(remote_change[1])
                    merged.append(f">>>>>>> REMOTE\n")
                    conflict.resolution = ConflictResolution.MANUAL_REQUIRED

                conflicts.append(conflict)
            i += 1

    stats = {
        'base_lines': len(base),
        'local_lines': len(local),
        'remote_lines': len(remote),
        'merged_lines': len(merged),
        'local_changes': len(local_changes),
        'remote_changes': len(remote_changes),
        'conflicts': len(conflicts),
        'auto_resolved': sum(1 for c in conflicts if c.resolution != ConflictResolution.MANUAL_REQUIRED)
    }

    success = all(c.resolution != ConflictResolution.MANUAL_REQUIRED for c in conflicts)

    return MergeResult(
        success=success,
        merged_content=merged,
        conflicts=conflicts,
        stats=stats
    )

def main():
    parser = argparse.ArgumentParser(
        description='Three-way merge engine for the system regeneration'
    )
    parser.add_argument('base', type=Path, help='Base file (common ancestor)')
    parser.add_argument('local', type=Path, help='Local file (your changes)')
    parser.add_argument('remote', type=Path, help='Remote file (regenerated)')
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output file (default: stdout)'
    )
    parser.add_argument(
        '--prefer-local',
        action='store_true',
        help='Prefer local changes in conflicts'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output result as JSON'
    )

    args = parser.parse_args()

    try:
        base = read_file(args.base)
        local = read_file(args.local)
        remote = read_file(args.remote)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = three_way_merge(base, local, remote, args.prefer_local)

    if args.json:
        output = {
            'success': result.success,
            'stats': result.stats,
            'conflicts': [
                {
                    'line_start': c.line_start,
                    'line_end': c.line_end,
                    'resolution': c.resolution.value if c.resolution else None
                }
                for c in result.conflicts
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        merged_text = ''.join(result.merged_content)

        if args.output:
            args.output.write_text(merged_text)
            print(f"Merged output written to: {args.output}")
        else:
            print(merged_text)

        if result.conflicts:
            print(f"\n--- Merge Statistics ---", file=sys.stderr)
            print(f"Conflicts: {result.stats['conflicts']}", file=sys.stderr)
            print(f"Auto-resolved: {result.stats['auto_resolved']}", file=sys.stderr)
            if not result.success:
                print(f"Manual resolution required!", file=sys.stderr)

    sys.exit(0 if result.success else 1)

if __name__ == '__main__':
    main()
