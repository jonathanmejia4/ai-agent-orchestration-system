#!/usr/bin/env python3
"""
three_way_merge.py - Line-based three-way merge for regeneration

Implements the three-way merge algorithm (BASE + LOCAL + NEW) to safely
regenerate files while preserving manual edits.

Merge Rules:
  1. If LOCAL = BASE and NEW differs: Accept NEW (template change, no user edit)
  2. If LOCAL differs from BASE and NEW = BASE: Accept LOCAL (user edit, no template change)
  3. If LOCAL differs from BASE and NEW differs from BASE: CONFLICT

Exit codes:
  0 - Merge successful (no conflicts)
  1 - Merge completed with conflicts
  2 - File/parse error

Usage:
  python tools/three_way_merge.py --base <file> --local <file> --new <file> --output <file>
  python tools/three_way_merge.py --base-dir <dir> --local-dir <dir> --new-dir <dir> --output-dir <dir>

Reference: THREE_WAY_MERGE_REGENERATION_POLICY.md:1190
"""

import argparse
import difflib
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

@dataclass
class MergeConflict:
    """Represents a merge conflict."""
    file_path: str
    line_start: int
    line_end: int
    base_content: list[str]
    local_content: list[str]
    new_content: list[str]
    conflict_type: str  # edit_edit, delete_edit, edit_delete

@dataclass
class MergeResult:
    """Result of a three-way merge operation."""
    file_path: str
    success: bool
    merged_content: Optional[str] = None
    conflicts: list[MergeConflict] = field(default_factory=list)
    base_hash: str = ""
    local_hash: str = ""
    new_hash: str = ""
    merge_strategy: str = ""  # auto_new, auto_local, manual_merge, conflict

class ThreeWayMerger:
    """Perform three-way merge operations on files."""

    def __init__(self, verbose: bool = False, conflict_style: str = "diff3"):
        self.verbose = verbose
        self.conflict_style = conflict_style  # diff3, merge, unified
        self.results: list[MergeResult] = []
        self.errors: list[str] = []

    def merge_file(
        self,
        base_path: Path,
        local_path: Path,
        new_path: Path,
        output_path: Optional[Path] = None
    ) -> MergeResult:
        """
        Perform three-way merge on a single file.

        Args:
            base_path: Path to BASE version (original generated)
            local_path: Path to LOCAL version (current with user edits)
            new_path: Path to NEW version (newly generated)
            output_path: Path to write merged output (default: overwrite local)

        Returns:
            MergeResult with merged content or conflicts
        """
        result = MergeResult(
            file_path=str(local_path),
            success=False
        )

        # Read files
        try:
            base_content = self._read_file(base_path)
            local_content = self._read_file(local_path)
            new_content = self._read_file(new_path)
        except Exception as e:
            self.errors.append(f"Error reading files: {e}")
            return result

        # Calculate hashes
        result.base_hash = self._hash_content(base_content)
        result.local_hash = self._hash_content(local_content)
        result.new_hash = self._hash_content(new_content)

        # Check for trivial cases
        if result.local_hash == result.new_hash:
            # No changes needed - LOCAL and NEW are identical
            result.success = True
            result.merged_content = local_content
            result.merge_strategy = "identical"
            return result

        if result.local_hash == result.base_hash:
            # No user edits - accept NEW entirely
            result.success = True
            result.merged_content = new_content
            result.merge_strategy = "auto_new"
            if self.verbose:
                print(f"  Auto-merge (NEW): {local_path.name} - no user edits")
            return result

        if result.new_hash == result.base_hash:
            # No template changes - keep LOCAL entirely
            result.success = True
            result.merged_content = local_content
            result.merge_strategy = "auto_local"
            if self.verbose:
                print(f"  Auto-merge (LOCAL): {local_path.name} - no template changes")
            return result

        # Both changed - need line-by-line merge
        merged, conflicts = self._merge_lines(
            base_content.splitlines(keepends=True),
            local_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            str(local_path)
        )

        result.merged_content = "".join(merged)
        result.conflicts = conflicts
        result.success = len(conflicts) == 0
        result.merge_strategy = "clean_merge" if result.success else "conflict"

        if self.verbose:
            if result.success:
                print(f"  Clean merge: {local_path.name}")
            else:
                print(f"  Conflicts: {local_path.name} ({len(conflicts)} conflicts)")

        # Write output if specified
        if output_path and result.merged_content:
            self._write_file(output_path, result.merged_content)

        self.results.append(result)
        return result

    def merge_directories(
        self,
        base_dir: Path,
        local_dir: Path,
        new_dir: Path,
        output_dir: Path
    ) -> list[MergeResult]:
        """
        Perform three-way merge on all files in directories.

        Returns:
            List of MergeResult for each file
        """
        results = []

        # Get all files from NEW (the template output)
        new_files = set()
        for f in new_dir.rglob("*"):
            if f.is_file():
                new_files.add(f.relative_to(new_dir))

        # Get all files from LOCAL (current with edits)
        local_files = set()
        for f in local_dir.rglob("*"):
            if f.is_file():
                local_files.add(f.relative_to(local_dir))

        # Process all files
        all_files = new_files | local_files

        for rel_path in sorted(all_files):
            base_path = base_dir / rel_path
            local_path = local_dir / rel_path
            new_path = new_dir / rel_path
            output_path = output_dir / rel_path

            # Handle different cases
            if new_path.exists() and local_path.exists() and base_path.exists():
                # Normal three-way merge
                result = self.merge_file(base_path, local_path, new_path, output_path)
            elif new_path.exists() and not local_path.exists():
                # New file from template - just copy
                result = MergeResult(
                    file_path=str(rel_path),
                    success=True,
                    merged_content=self._read_file(new_path),
                    merge_strategy="new_file"
                )
                self._write_file(output_path, result.merged_content)
            elif local_path.exists() and not new_path.exists():
                # File deleted in NEW - conflict if LOCAL differs from BASE
                if base_path.exists():
                    base_content = self._read_file(base_path)
                    local_content = self._read_file(local_path)
                    if self._hash_content(base_content) == self._hash_content(local_content):
                        # No user edits - accept deletion
                        result = MergeResult(
                            file_path=str(rel_path),
                            success=True,
                            merge_strategy="deleted"
                        )
                    else:
                        # User edited a deleted file - conflict
                        result = MergeResult(
                            file_path=str(rel_path),
                            success=False,
                            merged_content=local_content,
                            conflicts=[MergeConflict(
                                file_path=str(rel_path),
                                line_start=1,
                                line_end=len(local_content.splitlines()),
                                base_content=base_content.splitlines(),
                                local_content=local_content.splitlines(),
                                new_content=[],
                                conflict_type="delete_edit"
                            )],
                            merge_strategy="conflict"
                        )
                else:
                    # New local file - keep it
                    result = MergeResult(
                        file_path=str(rel_path),
                        success=True,
                        merged_content=self._read_file(local_path),
                        merge_strategy="local_only"
                    )
                    self._write_file(output_path, result.merged_content)
            else:
                # File exists only in BASE - was deleted by both
                result = MergeResult(
                    file_path=str(rel_path),
                    success=True,
                    merge_strategy="both_deleted"
                )

            results.append(result)
            self.results.append(result)

        return results

    def _merge_lines(
        self,
        base_lines: list[str],
        local_lines: list[str],
        new_lines: list[str],
        file_path: str
    ) -> tuple[list[str], list[MergeConflict]]:
        """
        Perform line-by-line three-way merge.

        Returns:
            Tuple of (merged_lines, conflicts)
        """
        merged = []
        conflicts = []

        # Use difflib to find differences
        base_to_local = list(difflib.unified_diff(base_lines, local_lines, lineterm=""))
        base_to_new = list(difflib.unified_diff(base_lines, new_lines, lineterm=""))

        # Get matching blocks for both diffs
        sm_local = difflib.SequenceMatcher(None, base_lines, local_lines)
        sm_new = difflib.SequenceMatcher(None, base_lines, new_lines)

        local_changes = self._get_changes(sm_local, base_lines, local_lines)
        new_changes = self._get_changes(sm_new, base_lines, new_lines)

        # Merge changes
        i = 0
        while i < len(base_lines) or local_changes or new_changes:
            local_change = self._get_change_at(local_changes, i)
            new_change = self._get_change_at(new_changes, i)

            if local_change is None and new_change is None:
                # No changes at this position - use base
                if i < len(base_lines):
                    merged.append(base_lines[i])
                i += 1
            elif local_change is not None and new_change is None:
                # Only local changed - accept local
                merged.extend(local_change["lines"])
                i = local_change["end"]
                local_changes = [c for c in local_changes if c["start"] >= i]
            elif local_change is None and new_change is not None:
                # Only new changed - accept new
                merged.extend(new_change["lines"])
                i = new_change["end"]
                new_changes = [c for c in new_changes if c["start"] >= i]
            else:
                # Both changed at same location - check if same change
                if local_change["lines"] == new_change["lines"]:
                    # Same change - no conflict
                    merged.extend(local_change["lines"])
                else:
                    # Different changes - conflict
                    conflict = MergeConflict(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=max(local_change["end"], new_change["end"]),
                        base_content=[l.rstrip("\n\r") for l in base_lines[i:max(local_change["end"], new_change["end"])]],
                        local_content=[l.rstrip("\n\r") for l in local_change["lines"]],
                        new_content=[l.rstrip("\n\r") for l in new_change["lines"]],
                        conflict_type="edit_edit"
                    )
                    conflicts.append(conflict)

                    # Add conflict markers
                    merged.extend(self._format_conflict(
                        local_change["lines"],
                        new_change["lines"],
                        base_lines[i:max(local_change["end"], new_change["end"])]
                    ))

                i = max(local_change["end"], new_change["end"])
                local_changes = [c for c in local_changes if c["start"] >= i]
                new_changes = [c for c in new_changes if c["start"] >= i]

        return merged, conflicts

    def _get_changes(
        self,
        sm: difflib.SequenceMatcher,
        base: list[str],
        other: list[str]
    ) -> list[dict]:
        """Extract changes from a SequenceMatcher."""
        changes = []

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                changes.append({
                    "start": i1,
                    "end": i2,
                    "lines": other[j1:j2],
                    "type": tag
                })

        return changes

    def _get_change_at(self, changes: list[dict], pos: int) -> Optional[dict]:
        """Get change that covers the given position."""
        for change in changes:
            if change["start"] <= pos < change["end"]:
                return change
            if change["start"] == pos and change["end"] == pos:
                # Insertion at this position
                return change
        return None

    def _format_conflict(
        self,
        local_lines: list[str],
        new_lines: list[str],
        base_lines: list[str]
    ) -> list[str]:
        """Format conflict with markers."""
        result = []

        if self.conflict_style == "diff3":
            result.append("<<<<<<< LOCAL\n")
            result.extend(local_lines)
            result.append("||||||| BASE\n")
            result.extend(base_lines)
            result.append("=======\n")
            result.extend(new_lines)
            result.append(">>>>>>> NEW\n")
        else:  # merge style
            result.append("<<<<<<< LOCAL\n")
            result.extend(local_lines)
            result.append("=======\n")
            result.extend(new_lines)
            result.append(">>>>>>> NEW\n")

        return result

    def _read_file(self, path: Path) -> str:
        """Read file content."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _write_file(self, path: Path, content: str) -> None:
        """Write file content."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _hash_content(self, content: str) -> str:
        """Calculate hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def write_conflicts_file(self, output_path: Path) -> None:
        """Write conflicts to .saf/merge-conflicts.yaml."""
        all_conflicts = []

        for result in self.results:
            if result.conflicts:
                for conflict in result.conflicts:
                    all_conflicts.append({
                        "file": conflict.file_path,
                        "line_start": conflict.line_start,
                        "line_end": conflict.line_end,
                        "type": conflict.conflict_type,
                        "base_lines": len(conflict.base_content),
                        "local_lines": len(conflict.local_content),
                        "new_lines": len(conflict.new_content),
                    })

        if all_conflicts:
            output = {
                "timestamp": datetime.now().isoformat(),
                "total_conflicts": len(all_conflicts),
                "files_with_conflicts": len(set(c["file"] for c in all_conflicts)),
                "conflicts": all_conflicts
            }

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                yaml.dump(output, f, default_flow_style=False)

    def get_summary(self) -> dict:
        """Get merge summary."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        with_conflicts = sum(1 for r in self.results if r.conflicts)
        total_conflicts = sum(len(r.conflicts) for r in self.results)

        return {
            "total_files": total,
            "successful": successful,
            "with_conflicts": with_conflicts,
            "total_conflicts": total_conflicts,
            "strategies": {
                "auto_new": sum(1 for r in self.results if r.merge_strategy == "auto_new"),
                "auto_local": sum(1 for r in self.results if r.merge_strategy == "auto_local"),
                "clean_merge": sum(1 for r in self.results if r.merge_strategy == "clean_merge"),
                "conflict": sum(1 for r in self.results if r.merge_strategy == "conflict"),
                "identical": sum(1 for r in self.results if r.merge_strategy == "identical"),
            }
        }

    def format_output(self, format_type: str = "text") -> str:
        """Format output for display."""
        summary = self.get_summary()

        if format_type == "json":
            return json.dumps(summary, indent=2)

        lines = []
        lines.append("=" * 50)
        lines.append("THREE-WAY MERGE RESULT")
        lines.append("=" * 50)

        lines.append(f"\nTotal files: {summary['total_files']}")
        lines.append(f"Successful: {summary['successful']}")
        lines.append(f"With conflicts: {summary['with_conflicts']}")
        lines.append(f"Total conflicts: {summary['total_conflicts']}")

        lines.append("\nMerge strategies:")
        for strategy, count in summary["strategies"].items():
            if count > 0:
                lines.append(f"  {strategy}: {count}")

        if summary["with_conflicts"] > 0:
            lines.append("\nFiles with conflicts:")
            for result in self.results:
                if result.conflicts:
                    lines.append(f"  - {result.file_path} ({len(result.conflicts)} conflicts)")

        if summary["with_conflicts"] == 0:
            lines.append("\n✓ Merge completed without conflicts")
        else:
            lines.append(f"\n✗ Merge completed with {summary['total_conflicts']} conflicts")
            lines.append("  Review conflict markers and resolve manually")

        lines.append("\n" + "=" * 50)
        return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Three-way merge for regeneration (BASE + LOCAL + NEW)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Merge successful (no conflicts)
  1 - Merge completed with conflicts
  2 - File/parse error

Examples:
  # Single file merge
  %(prog)s --base old.ts --local current.ts --new generated.ts --output merged.ts

  # Directory merge
  %(prog)s --base-dir .saf/base/ --local-dir src/ --new-dir .saf/new/ --output-dir src/

  # With conflict file output
  %(prog)s --base a.ts --local b.ts --new c.ts -o out.ts --conflicts .saf/conflicts.yaml
        """
    )

    # Single file mode
    parser.add_argument("--base", "-b", type=Path, help="BASE version file")
    parser.add_argument("--local", "-l", type=Path, help="LOCAL version file (with edits)")
    parser.add_argument("--new", "-n", type=Path, help="NEW version file (regenerated)")
    parser.add_argument("--output", "-o", type=Path, help="Output file path")

    # Directory mode
    parser.add_argument("--base-dir", type=Path, help="BASE version directory")
    parser.add_argument("--local-dir", type=Path, help="LOCAL version directory")
    parser.add_argument("--new-dir", type=Path, help="NEW version directory")
    parser.add_argument("--output-dir", type=Path, help="Output directory")

    # Options
    parser.add_argument(
        "--conflicts",
        type=Path,
        help="Path to write conflicts YAML file"
    )
    parser.add_argument(
        "--style",
        choices=["diff3", "merge"],
        default="diff3",
        help="Conflict marker style (default: diff3)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    merger = ThreeWayMerger(verbose=args.verbose, conflict_style=args.style)

    # Determine mode
    if args.base and args.local and args.new:
        # Single file mode
        if not args.base.exists():
            print(f"Error: BASE file not found: {args.base}", file=sys.stderr)
            sys.exit(2)
        if not args.local.exists():
            print(f"Error: LOCAL file not found: {args.local}", file=sys.stderr)
            sys.exit(2)
        if not args.new.exists():
            print(f"Error: NEW file not found: {args.new}", file=sys.stderr)
            sys.exit(2)

        result = merger.merge_file(
            args.base,
            args.local,
            args.new,
            args.output or args.local
        )

    elif args.base_dir and args.local_dir and args.new_dir and args.output_dir:
        # Directory mode
        if not args.base_dir.exists():
            print(f"Error: BASE directory not found: {args.base_dir}", file=sys.stderr)
            sys.exit(2)
        if not args.local_dir.exists():
            print(f"Error: LOCAL directory not found: {args.local_dir}", file=sys.stderr)
            sys.exit(2)
        if not args.new_dir.exists():
            print(f"Error: NEW directory not found: {args.new_dir}", file=sys.stderr)
            sys.exit(2)

        merger.merge_directories(
            args.base_dir,
            args.local_dir,
            args.new_dir,
            args.output_dir
        )

    else:
        print("Error: Specify either single file (--base, --local, --new) or directory mode (--base-dir, --local-dir, --new-dir, --output-dir)", file=sys.stderr)
        parser.print_help()
        sys.exit(2)

    # Write conflicts file if specified
    if args.conflicts:
        merger.write_conflicts_file(args.conflicts)

    # Output summary
    print(merger.format_output(args.format))

    # Exit code based on conflicts
    summary = merger.get_summary()
    if summary["with_conflicts"] > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
