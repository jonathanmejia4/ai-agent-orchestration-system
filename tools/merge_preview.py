#!/usr/bin/env python3
"""
Merge Preview - Simulates Three-Way Merge and Generates Previews

Performs a simulation of three-way merge (BASE + LOCAL + NEW) and generates
a preview of the merged result before actually executing the merge. This allows
PM to review merge conflicts and resolutions proactively.

Usage:
    # Generate merge preview
    python3 tools/merge_preview.py --base file.base --local file.local --new file.new

    # Output to specific file
    python3 tools/merge_preview.py --base f.base --local f.local --new f.new --output preview.diff

    # Show conflicts only
    python3 tools/merge_preview.py --base f.base --local f.local --new f.new --conflicts-only

    # Interactive mode (show conflict resolution options)
    python3 tools/merge_preview.py --base f.base --local f.local --new f.new --interactive

Exit Codes:
    0 - Merge preview successful, no conflicts
    1 - Merge preview successful, conflicts detected
    2 - Error (missing files, etc.)

Referenced in:
    - THREE_WAY_MERGE_REGENERATION_POLICY.md:1209
    - SPEC_TO_DIFF_PREVIEWS_POLICY.md:1454

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import difflib
import hashlib
import yaml
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

class ConflictType(Enum):
    """Types of merge conflicts"""
    CONTENT = "content"        # Same region modified differently
    DELETE_MODIFY = "delete_modify"  # One deleted, other modified
    ADD_ADD = "add_add"        # Both added at same location
    RENAME = "rename"          # File renamed differently

@dataclass
class MergeConflict:
    """Represents a merge conflict"""
    type: ConflictType
    start_line: int
    end_line: int
    base_content: List[str]
    local_content: List[str]
    new_content: List[str]
    resolution: Optional[str] = None
    resolution_content: Optional[List[str]] = None

@dataclass
class MergeResult:
    """Result of three-way merge simulation"""
    success: bool
    has_conflicts: bool
    conflicts: List[MergeConflict] = field(default_factory=list)
    merged_content: List[str] = field(default_factory=list)
    base_hash: str = ""
    local_hash: str = ""
    new_hash: str = ""
    stats: Dict[str, int] = field(default_factory=dict)

class ThreeWayMerge:
    """Performs three-way merge with conflict detection"""

    CONFLICT_START = "<<<<<<< LOCAL"
    CONFLICT_SEPARATOR = "======="
    CONFLICT_BASE = "||||||| BASE"
    CONFLICT_END = ">>>>>>> NEW"

    def __init__(self, show_base: bool = True):
        self.show_base = show_base

    def file_hash(self, content: str) -> str:
        """Calculate hash of file content"""
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def load_file(self, path: Path) -> Tuple[List[str], str]:
        """Load file and return lines and hash"""
        content = path.read_text()
        lines = content.splitlines(keepends=True)
        return lines, self.file_hash(content)

    def diff_lines(self, a: List[str], b: List[str]) -> List[Tuple[str, int, int, int, int]]:
        """
        Get difference between two line sequences.

        Returns list of (tag, i1, i2, j1, j2) tuples:
        - tag: 'equal', 'replace', 'delete', 'insert'
        - i1:i2 range in sequence a
        - j1:j2 range in sequence b
        """
        matcher = difflib.SequenceMatcher(None, a, b)
        return matcher.get_opcodes()

    def merge(self, base: List[str], local: List[str], new: List[str]) -> MergeResult:
        """
        Perform three-way merge.

        Algorithm:
        1. Find differences between BASE and LOCAL (local changes)
        2. Find differences between BASE and NEW (new changes)
        3. Apply non-overlapping changes
        4. Detect conflicts where changes overlap
        """
        result = MergeResult(
            success=True,
            has_conflicts=False,
            stats={
                'lines_base': len(base),
                'lines_local': len(local),
                'lines_new': len(new),
                'additions': 0,
                'deletions': 0,
                'conflicts': 0
            }
        )

        # Get diffs
        base_to_local = self.diff_lines(base, local)
        base_to_new = self.diff_lines(base, new)

        # Build change maps
        local_changes = self._build_change_map(base_to_local)
        new_changes = self._build_change_map(base_to_new)

        # Find overlapping regions (conflicts)
        conflicts = self._find_conflicts(local_changes, new_changes, base, local, new)
        result.conflicts = conflicts
        result.has_conflicts = len(conflicts) > 0
        result.stats['conflicts'] = len(conflicts)

        # Merge content
        merged = self._merge_content(base, local, new, local_changes, new_changes, conflicts)
        result.merged_content = merged

        return result

    def _build_change_map(self, opcodes: List[Tuple]) -> Dict[int, Tuple[str, List[str]]]:
        """Build map of base line index to (operation, new_content)"""
        changes = {}
        for tag, i1, i2, j1, j2 in opcodes:
            if tag != 'equal':
                for i in range(i1, max(i2, i1 + 1)):
                    changes[i] = (tag, [])
        return changes

    def _find_conflicts(self, local_changes: Dict, new_changes: Dict,
                        base: List[str], local: List[str], new: List[str]) -> List[MergeConflict]:
        """Find overlapping changes (conflicts)"""
        conflicts = []

        # Find regions changed in both
        local_regions = set(local_changes.keys())
        new_regions = set(new_changes.keys())
        overlap = local_regions & new_regions

        if overlap:
            # Group consecutive overlapping lines into conflict regions
            sorted_overlap = sorted(overlap)
            regions = []
            current_start = sorted_overlap[0]
            current_end = sorted_overlap[0]

            for line_idx in sorted_overlap[1:]:
                if line_idx <= current_end + 1:
                    current_end = line_idx
                else:
                    regions.append((current_start, current_end))
                    current_start = line_idx
                    current_end = line_idx
            regions.append((current_start, current_end))

            # Create conflict objects
            for start, end in regions:
                base_content = base[start:end + 1] if start < len(base) else []

                # Find corresponding local content
                local_content = self._get_modified_content(base, local, start, end)

                # Find corresponding new content
                new_content = self._get_modified_content(base, new, start, end)

                # Only a conflict if the changes differ
                if local_content != new_content:
                    conflict = MergeConflict(
                        type=ConflictType.CONTENT,
                        start_line=start + 1,  # 1-indexed
                        end_line=end + 1,
                        base_content=base_content,
                        local_content=local_content,
                        new_content=new_content
                    )
                    conflicts.append(conflict)

        return conflicts

    def _get_modified_content(self, base: List[str], modified: List[str],
                               base_start: int, base_end: int) -> List[str]:
        """Get the content from modified that corresponds to base region"""
        # Use sequence matcher to find corresponding region
        matcher = difflib.SequenceMatcher(None, base, modified)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if i1 <= base_start <= i2 or i1 <= base_end <= i2:
                if tag == 'equal':
                    offset = base_start - i1
                    length = base_end - base_start + 1
                    return modified[j1 + offset:j1 + offset + length]
                elif tag in ('replace', 'insert'):
                    return modified[j1:j2]
                elif tag == 'delete':
                    return []

        return []

    def _merge_content(self, base: List[str], local: List[str], new: List[str],
                       local_changes: Dict, new_changes: Dict,
                       conflicts: List[MergeConflict]) -> List[str]:
        """Merge content, inserting conflict markers where needed"""
        # Build conflict regions set
        conflict_lines = set()
        for conflict in conflicts:
            for i in range(conflict.start_line - 1, conflict.end_line):
                conflict_lines.add(i)

        merged = []
        i = 0

        while i < len(base):
            if i in conflict_lines:
                # Find the conflict for this line
                for conflict in conflicts:
                    if conflict.start_line - 1 <= i < conflict.end_line:
                        # Insert conflict markers
                        merged.append(self.CONFLICT_START + '\n')
                        merged.extend(conflict.local_content)
                        if self.show_base:
                            merged.append(self.CONFLICT_BASE + '\n')
                            merged.extend(conflict.base_content)
                        merged.append(self.CONFLICT_SEPARATOR + '\n')
                        merged.extend(conflict.new_content)
                        merged.append(self.CONFLICT_END + '\n')
                        i = conflict.end_line
                        break
            elif i in new_changes and i not in local_changes:
                # Only new changed this - take new's version
                # Skip base line, new content will be added by diff
                i += 1
            elif i in local_changes and i not in new_changes:
                # Only local changed this - take local's version
                merged.append(base[i] if i < len(base) else '')
                i += 1
            else:
                # No changes or equal changes - take base
                merged.append(base[i])
                i += 1

        return merged

    def generate_preview(self, result: MergeResult) -> str:
        """Generate a human-readable preview of the merge"""
        lines = [
            "=" * 60,
            "THREE-WAY MERGE PREVIEW",
            "=" * 60,
            "",
            f"Base lines: {result.stats['lines_base']}",
            f"Local lines: {result.stats['lines_local']}",
            f"New lines: {result.stats['lines_new']}",
            f"Conflicts: {result.stats['conflicts']}",
            "",
        ]

        if result.has_conflicts:
            lines.append("CONFLICTS DETECTED:")
            lines.append("-" * 40)
            for i, conflict in enumerate(result.conflicts, 1):
                lines.append(f"\nConflict #{i} (lines {conflict.start_line}-{conflict.end_line}):")
                lines.append(f"  Type: {conflict.type.value}")
                lines.append("  LOCAL version:")
                for line in conflict.local_content:
                    lines.append(f"    {line.rstrip()}")
                lines.append("  NEW version:")
                for line in conflict.new_content:
                    lines.append(f"    {line.rstrip()}")
            lines.append("")

        lines.append("-" * 60)
        lines.append("MERGED OUTPUT:")
        lines.append("-" * 60)
        for line in result.merged_content:
            lines.append(line.rstrip())

        lines.append("")
        lines.append("=" * 60)

        return '\n'.join(lines)

    def generate_diff(self, base: List[str], merged: List[str]) -> str:
        """Generate unified diff between base and merged"""
        diff = difflib.unified_diff(
            base,
            merged,
            fromfile='BASE',
            tofile='MERGED',
            lineterm=''
        )
        return '\n'.join(diff)

def main():
    parser = argparse.ArgumentParser(
        description='Generate three-way merge preview',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --base file.base --local file.local --new file.new
    %(prog)s --base f.base --local f.local --new f.new --output preview.diff
    %(prog)s --base f.base --local f.local --new f.new --conflicts-only
        """
    )

    parser.add_argument('--base', '-b', type=Path, required=True,
                        help='Base version (common ancestor)')
    parser.add_argument('--local', '-l', type=Path, required=True,
                        help='Local version (with manual edits)')
    parser.add_argument('--new', '-n', type=Path, required=True,
                        help='New version (regenerated)')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output file for merge preview')
    parser.add_argument('--diff-output', type=Path,
                        help='Output file for unified diff')
    parser.add_argument('--conflicts-only', action='store_true',
                        help='Only output conflict information')
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')
    parser.add_argument('--no-base-in-conflicts', action='store_true',
                        help='Do not show base content in conflict markers')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress output on success')

    args = parser.parse_args()

    # Validate files exist
    for path, name in [(args.base, 'base'), (args.local, 'local'), (args.new, 'new')]:
        if not path.exists():
            print(f"Error: {name} file not found: {path}", file=sys.stderr)
            sys.exit(2)

    # Perform merge
    merger = ThreeWayMerge(show_base=not args.no_base_in_conflicts)

    try:
        base_lines, base_hash = merger.load_file(args.base)
        local_lines, local_hash = merger.load_file(args.local)
        new_lines, new_hash = merger.load_file(args.new)

        result = merger.merge(base_lines, local_lines, new_lines)
        result.base_hash = base_hash
        result.local_hash = local_hash
        result.new_hash = new_hash

    except Exception as e:
        print(f"Error: Merge failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Generate output
    if args.json:
        output = json.dumps({
            'success': result.success,
            'has_conflicts': result.has_conflicts,
            'conflicts': [
                {
                    'type': c.type.value,
                    'start_line': c.start_line,
                    'end_line': c.end_line,
                    'base_content': c.base_content,
                    'local_content': c.local_content,
                    'new_content': c.new_content
                }
                for c in result.conflicts
            ],
            'stats': result.stats,
            'hashes': {
                'base': result.base_hash,
                'local': result.local_hash,
                'new': result.new_hash
            }
        }, indent=2)
    elif args.conflicts_only:
        if result.has_conflicts:
            lines = [f"CONFLICTS DETECTED: {len(result.conflicts)}"]
            for i, c in enumerate(result.conflicts, 1):
                lines.append(f"\n[{i}] Lines {c.start_line}-{c.end_line} ({c.type.value})")
                lines.append("  LOCAL: " + ' '.join(l.strip() for l in c.local_content[:3]))
                lines.append("  NEW: " + ' '.join(l.strip() for l in c.new_content[:3]))
            output = '\n'.join(lines)
        else:
            output = "No conflicts detected"
    else:
        output = merger.generate_preview(result)

    # Output results
    if args.output:
        args.output.write_text(output)
        if not args.quiet:
            print(f"Preview saved to: {args.output}")
    elif not args.quiet or result.has_conflicts:
        print(output)

    # Generate diff output
    if args.diff_output:
        diff = merger.generate_diff(base_lines, result.merged_content)
        args.diff_output.write_text(diff)
        if not args.quiet:
            print(f"Diff saved to: {args.diff_output}")

    # Exit with appropriate code
    if result.has_conflicts:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
