#!/usr/bin/env python3
"""
Auto Resolution Tool - 3-Way Merge Conflict Resolver
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Merge Infrastructure

Git-style 3-way merge with auto-resolution strategies for template regeneration.
Prevents user edits from being overwritten during idempotent generation.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class ConflictType(Enum):
    """Types of merge conflicts."""
    NONE = "none"
    TRIVIAL = "trivial"  # Can be auto-resolved
    COMPLEX = "complex"  # Requires manual intervention
    SEMANTIC = "semantic"  # Structural/semantic conflict

class ResolutionStrategy(Enum):
    """Auto-resolution strategies."""
    KEEP_LOCAL = "keep_local"  # Prefer user changes
    KEEP_NEW = "keep_new"  # Prefer generated changes
    MERGE_BOTH = "merge_both"  # Attempt to merge both
    PROTECTED_REGIONS = "protected_regions"  # Respect protected regions
    SMART_MERGE = "smart_merge"  # Context-aware merging

@dataclass
class ConflictRegion:
    """Represents a conflict region in a file."""
    start_line: int
    end_line: int
    base_content: List[str]
    local_content: List[str]
    new_content: List[str]
    conflict_type: ConflictType
    resolution: Optional[List[str]] = None
    strategy_used: Optional[ResolutionStrategy] = None

@dataclass
class MergeResult:
    """Result of a 3-way merge operation."""
    success: bool
    merged_content: str
    conflicts: List[ConflictRegion] = field(default_factory=list)
    auto_resolved: int = 0
    manual_required: int = 0
    warnings: List[str] = field(default_factory=list)

class ThreeWayMerger:
    """Performs 3-way merge with auto-resolution."""

    # Protected region markers
    PROTECTED_START = re.compile(r'#\s*PROTECTED:START|//\s*PROTECTED:START|<!--\s*PROTECTED:START')
    PROTECTED_END = re.compile(r'#\s*PROTECTED:END|//\s*PROTECTED:END|<!--\s*PROTECTED:END')

    def __init__(self, strategy: ResolutionStrategy = ResolutionStrategy.SMART_MERGE):
        self.strategy = strategy
        self.conflicts: List[ConflictRegion] = []

    def merge(
        self,
        base: str,
        local: str,
        new: str,
        file_path: Optional[str] = None
    ) -> MergeResult:
        """
        Perform 3-way merge.

        Args:
            base: Original/base version
            local: User-modified version (LOCAL)
            new: Newly generated version (NEW)
            file_path: Optional file path for context

        Returns:
            MergeResult with merged content and conflict info
        """
        base_lines = base.splitlines(keepends=True)
        local_lines = local.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        # Find protected regions in local version
        protected_regions = self._find_protected_regions(local_lines)

        # Perform diff3-style merge
        merged_lines, conflicts = self._diff3_merge(
            base_lines, local_lines, new_lines, protected_regions
        )

        # Attempt auto-resolution of conflicts
        auto_resolved = 0
        manual_required = 0

        for conflict in conflicts:
            resolved = self._auto_resolve(conflict, protected_regions)
            if resolved:
                auto_resolved += 1
            else:
                manual_required += 1

        # Build final content
        if manual_required == 0:
            merged_content = self._build_merged_content(merged_lines, conflicts)
            success = True
        else:
            merged_content = self._build_conflict_content(merged_lines, conflicts)
            success = False

        return MergeResult(
            success=success,
            merged_content=merged_content,
            conflicts=conflicts,
            auto_resolved=auto_resolved,
            manual_required=manual_required
        )

    def _find_protected_regions(self, lines: List[str]) -> List[Tuple[int, int]]:
        """Find protected region boundaries."""
        regions = []
        start = None

        for i, line in enumerate(lines):
            if self.PROTECTED_START.search(line):
                start = i
            elif self.PROTECTED_END.search(line) and start is not None:
                regions.append((start, i))
                start = None

        return regions

    def _is_in_protected_region(
        self,
        line_num: int,
        protected_regions: List[Tuple[int, int]]
    ) -> bool:
        """Check if line is within a protected region."""
        for start, end in protected_regions:
            if start <= line_num <= end:
                return True
        return False

    def _diff3_merge(
        self,
        base: List[str],
        local: List[str],
        new: List[str],
        protected_regions: List[Tuple[int, int]]
    ) -> Tuple[List[str], List[ConflictRegion]]:
        """Perform diff3-style merge."""
        conflicts = []
        merged = []

        # Use difflib to find differences
        base_local_diff = list(difflib.unified_diff(base, local, lineterm=''))
        base_new_diff = list(difflib.unified_diff(base, new, lineterm=''))

        # Simple merge: if only one side changed, take that change
        matcher_local = difflib.SequenceMatcher(None, base, local)
        matcher_new = difflib.SequenceMatcher(None, base, new)

        local_changes = self._get_change_regions(matcher_local)
        new_changes = self._get_change_regions(matcher_new)

        # Merge non-overlapping changes
        i = 0
        while i < max(len(base), len(local), len(new)):
            local_changed = self._line_in_changes(i, local_changes)
            new_changed = self._line_in_changes(i, new_changes)

            if not local_changed and not new_changed:
                # No changes, use base
                if i < len(base):
                    merged.append(base[i])
            elif local_changed and not new_changed:
                # Only local changed
                if i < len(local):
                    merged.append(local[i])
            elif not local_changed and new_changed:
                # Only new changed, but check protected regions
                if self._is_in_protected_region(i, protected_regions):
                    if i < len(local):
                        merged.append(local[i])
                else:
                    if i < len(new):
                        merged.append(new[i])
            else:
                # Both changed - conflict
                conflict = ConflictRegion(
                    start_line=i,
                    end_line=i,
                    base_content=[base[i]] if i < len(base) else [],
                    local_content=[local[i]] if i < len(local) else [],
                    new_content=[new[i]] if i < len(new) else [],
                    conflict_type=ConflictType.COMPLEX
                )
                conflicts.append(conflict)
                merged.append(None)  # Placeholder for conflict

            i += 1

        return merged, conflicts

    def _get_change_regions(self, matcher: difflib.SequenceMatcher) -> List[Tuple[int, int]]:
        """Get regions that changed."""
        changes = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                changes.append((i1, i2))
        return changes

    def _line_in_changes(self, line: int, changes: List[Tuple[int, int]]) -> bool:
        """Check if line is in any change region."""
        for start, end in changes:
            if start <= line < end:
                return True
        return False

    def _auto_resolve(
        self,
        conflict: ConflictRegion,
        protected_regions: List[Tuple[int, int]]
    ) -> bool:
        """Attempt to auto-resolve a conflict."""
        # Check if in protected region - always keep local
        if self._is_in_protected_region(conflict.start_line, protected_regions):
            conflict.resolution = conflict.local_content
            conflict.strategy_used = ResolutionStrategy.PROTECTED_REGIONS
            conflict.conflict_type = ConflictType.TRIVIAL
            return True

        # Strategy-based resolution
        if self.strategy == ResolutionStrategy.KEEP_LOCAL:
            conflict.resolution = conflict.local_content
            conflict.strategy_used = ResolutionStrategy.KEEP_LOCAL
            conflict.conflict_type = ConflictType.TRIVIAL
            return True

        elif self.strategy == ResolutionStrategy.KEEP_NEW:
            conflict.resolution = conflict.new_content
            conflict.strategy_used = ResolutionStrategy.KEEP_NEW
            conflict.conflict_type = ConflictType.TRIVIAL
            return True

        elif self.strategy == ResolutionStrategy.SMART_MERGE:
            # Try smart merge - if changes are additive, merge both
            if self._is_additive_change(conflict):
                conflict.resolution = conflict.local_content + conflict.new_content
                conflict.strategy_used = ResolutionStrategy.MERGE_BOTH
                conflict.conflict_type = ConflictType.TRIVIAL
                return True

            # If local only has whitespace changes, use new
            if self._is_whitespace_only_diff(conflict.base_content, conflict.local_content):
                conflict.resolution = conflict.new_content
                conflict.strategy_used = ResolutionStrategy.KEEP_NEW
                conflict.conflict_type = ConflictType.TRIVIAL
                return True

        return False

    def _is_additive_change(self, conflict: ConflictRegion) -> bool:
        """Check if both changes are purely additive (no deletions)."""
        base_set = set(''.join(conflict.base_content).strip())
        local_set = set(''.join(conflict.local_content).strip())
        new_set = set(''.join(conflict.new_content).strip())

        return base_set <= local_set and base_set <= new_set

    def _is_whitespace_only_diff(self, a: List[str], b: List[str]) -> bool:
        """Check if difference is whitespace only."""
        a_stripped = ''.join(line.strip() for line in a)
        b_stripped = ''.join(line.strip() for line in b)
        return a_stripped == b_stripped

    def _build_merged_content(
        self,
        merged: List[str],
        conflicts: List[ConflictRegion]
    ) -> str:
        """Build final merged content with resolved conflicts."""
        result = []
        conflict_idx = 0

        for i, line in enumerate(merged):
            if line is None and conflict_idx < len(conflicts):
                conflict = conflicts[conflict_idx]
                if conflict.resolution:
                    result.extend(conflict.resolution)
                conflict_idx += 1
            elif line is not None:
                result.append(line)

        return ''.join(result)

    def _build_conflict_content(
        self,
        merged: List[str],
        conflicts: List[ConflictRegion]
    ) -> str:
        """Build content with conflict markers for manual resolution."""
        result = []
        conflict_idx = 0

        for i, line in enumerate(merged):
            if line is None and conflict_idx < len(conflicts):
                conflict = conflicts[conflict_idx]
                if conflict.resolution:
                    result.extend(conflict.resolution)
                else:
                    # Add conflict markers
                    result.append("<<<<<<< LOCAL\n")
                    result.extend(conflict.local_content)
                    result.append("=======\n")
                    result.extend(conflict.new_content)
                    result.append(">>>>>>> NEW\n")
                conflict_idx += 1
            elif line is not None:
                result.append(line)

        return ''.join(result)

def merge_file(
    base_path: str,
    local_path: str,
    new_path: str,
    output_path: Optional[str] = None,
    strategy: str = "smart_merge"
) -> MergeResult:
    """
    Merge three versions of a file.

    Args:
        base_path: Path to base version
        local_path: Path to local (user-modified) version
        new_path: Path to new (generated) version
        output_path: Path to write merged result
        strategy: Resolution strategy name

    Returns:
        MergeResult
    """
    # Read files
    with open(base_path, 'r') as f:
        base = f.read()
    with open(local_path, 'r') as f:
        local = f.read()
    with open(new_path, 'r') as f:
        new = f.read()

    # Parse strategy
    try:
        strat = ResolutionStrategy(strategy)
    except ValueError:
        strat = ResolutionStrategy.SMART_MERGE

    # Perform merge
    merger = ThreeWayMerger(strategy=strat)
    result = merger.merge(base, local, new, file_path=local_path)

    # Write output if specified
    if output_path and result.success:
        with open(output_path, 'w') as f:
            f.write(result.merged_content)

    return result

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="3-way merge with auto-resolution for template regeneration"
    )
    parser.add_argument("base", help="Base version file")
    parser.add_argument("local", help="Local (user-modified) version file")
    parser.add_argument("new", help="New (generated) version file")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument(
        "-s", "--strategy",
        choices=["keep_local", "keep_new", "merge_both", "protected_regions", "smart_merge"],
        default="smart_merge",
        help="Resolution strategy"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    # Validate files exist
    for path in [args.base, args.local, args.new]:
        if not os.path.exists(path):
            print(f"Error: File not found: {path}", file=sys.stderr)
            sys.exit(1)

    result = merge_file(
        args.base,
        args.local,
        args.new,
        args.output,
        args.strategy
    )

    if args.json:
        output = {
            "success": result.success,
            "auto_resolved": result.auto_resolved,
            "manual_required": result.manual_required,
            "conflicts": len(result.conflicts),
            "warnings": result.warnings
        }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"Merge successful: {result.auto_resolved} conflicts auto-resolved")
            if args.output:
                print(f"Output written to: {args.output}")
            else:
                print(result.merged_content)
        else:
            print(f"Merge requires manual intervention: {result.manual_required} conflicts")
            print(result.merged_content)

    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()
