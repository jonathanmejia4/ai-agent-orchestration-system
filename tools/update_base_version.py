#!/usr/bin/env python3
"""
update_base_version.py - Store BASE versions for three-way merge regeneration

Copies generated files to BASE storage after successful generation/merge,
enabling future three-way merge operations to preserve manual edits.

Exit codes:
  0 - BASE versions updated successfully
  1 - Validation error
  2 - File/parse error

Usage:
  python tools/update_base_version.py <task_id>
  python tools/update_base_version.py <task_id> --source <generated_dir>
  python tools/update_base_version.py <task_id> --dry-run

Reference: THREE_WAY_MERGE_REGENERATION_POLICY.md:445-470
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

class BaseVersionUpdater:
    """Store BASE versions of generated files for three-way merge."""

    def __init__(
        self,
        root_dir: Path,
        verbose: bool = False,
        dry_run: bool = False
    ):
        self.root_dir = root_dir
        self.verbose = verbose
        self.dry_run = dry_run
        self.saf_dir = root_dir / ".saf"
        self.generated_dir = self.saf_dir / "generated"
        self.errors: list[str] = []
        self.files_updated: list[str] = []

    def update_base_version(
        self,
        task_id: str,
        source_dir: Optional[Path] = None,
        files: Optional[list[str]] = None
    ) -> bool:
        """
        Update BASE versions for a task.

        Args:
            task_id: The task identifier
            source_dir: Directory containing generated files (default: auto-detect)
            files: Specific files to update (default: all generated files)

        Returns:
            True if successful, False otherwise
        """
        # Determine source directory
        if source_dir is None:
            source_dir = self._find_source_dir(task_id)

        if source_dir is None or not source_dir.exists():
            self.errors.append(f"Source directory not found for task: {task_id}")
            return False

        # Set up BASE storage directory
        base_dir = self.generated_dir / task_id / "base"

        if self.dry_run:
            print(f"[DRY RUN] Would create BASE storage: {base_dir}")
        else:
            base_dir.mkdir(parents=True, exist_ok=True)

        # Get list of files to copy
        if files:
            file_list = [source_dir / f for f in files]
        else:
            file_list = self._get_generated_files(source_dir)

        if not file_list:
            self.errors.append(f"No generated files found in: {source_dir}")
            return False

        # Copy files to BASE storage
        file_hashes = {}
        for source_file in file_list:
            if not source_file.exists():
                if self.verbose:
                    print(f"  Skipping missing file: {source_file}")
                continue

            # Calculate relative path for storage
            try:
                rel_path = source_file.relative_to(source_dir)
            except ValueError:
                rel_path = Path(source_file.name)

            dest_file = base_dir / rel_path

            # Calculate file hash
            file_hash = self._calculate_hash(source_file)
            file_hashes[str(rel_path)] = file_hash

            if self.dry_run:
                print(f"[DRY RUN] Would copy: {source_file} -> {dest_file}")
                print(f"          Hash: {file_hash}")
            else:
                # Ensure parent directory exists
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                try:
                    shutil.copy2(source_file, dest_file)
                    self.files_updated.append(str(rel_path))
                    if self.verbose:
                        print(f"  Copied: {rel_path} (hash: {file_hash[:12]}...)")
                except Exception as e:
                    self.errors.append(f"Error copying {source_file}: {e}")

        # Update metadata
        metadata_updated = self._update_metadata(task_id, file_hashes, source_dir)

        if not metadata_updated:
            return False

        return len(self.errors) == 0

    def _find_source_dir(self, task_id: str) -> Optional[Path]:
        """Find the source directory for generated files."""
        # Check multiple possible locations
        candidates = [
            self.root_dir / "tasks" / task_id / "src",
            self.root_dir / "tasks" / task_id / "generated",
            self.root_dir / "src" / task_id,
            self.root_dir / task_id / "src",
            self.saf_dir / "generated" / task_id / "current",
        ]

        for candidate in candidates:
            if candidate.exists() and any(candidate.iterdir()):
                return candidate

        # Fall back to task directory itself
        task_dir = self.root_dir / "tasks" / task_id
        if task_dir.exists():
            return task_dir

        return None

    def _get_generated_files(self, source_dir: Path) -> list[Path]:
        """Get list of generated files to store as BASE."""
        files = []

        # Include common generated file patterns
        patterns = [
            "**/*.ts",
            "**/*.tsx",
            "**/*.js",
            "**/*.jsx",
            "**/*.py",
            "**/*.yaml",
            "**/*.yml",
            "**/*.json",
            "**/*.md",
            "**/*.css",
            "**/*.scss",
            "**/*.html",
        ]

        for pattern in patterns:
            files.extend(source_dir.glob(pattern))

        # Filter out node_modules, __pycache__, etc.
        excluded_dirs = {"node_modules", "__pycache__", ".git", ".saf", "dist", "build"}
        files = [
            f for f in files
            if not any(excluded in f.parts for excluded in excluded_dirs)
        ]

        return sorted(set(files))

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.errors.append(f"Error hashing {file_path}: {e}")
            return ""

    def _update_metadata(
        self,
        task_id: str,
        file_hashes: dict[str, str],
        source_dir: Path
    ) -> bool:
        """Update metadata.yaml with BASE version information."""
        metadata_path = self.generated_dir / task_id / "metadata.yaml"

        # Load existing metadata or create new
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = yaml.safe_load(f) or {}
            except Exception as e:
                self.errors.append(f"Error reading metadata: {e}")
                metadata = {}
        else:
            metadata = {}

        # Update BASE version info
        timestamp = datetime.now().isoformat()

        if "base_versions" not in metadata:
            metadata["base_versions"] = []

        # Add new BASE version entry
        base_entry = {
            "timestamp": timestamp,
            "source_dir": str(source_dir),
            "file_count": len(file_hashes),
            "files": file_hashes,
        }

        # Get template version if available
        wiring_path = self._find_wiring_file(task_id)
        if wiring_path and wiring_path.exists():
            try:
                with open(wiring_path) as f:
                    wiring = yaml.safe_load(f) or {}
                identity = wiring.get("identity", {})
                template = identity.get("template", wiring.get("template", ""))
                template_version = identity.get("template_version", "")

                if "@" in str(template) and not template_version:
                    template, template_version = str(template).rsplit("@", 1)

                base_entry["template"] = template
                base_entry["template_version"] = template_version
            except Exception:
                pass

        # Keep history (last 10 BASE versions)
        metadata["base_versions"].append(base_entry)
        metadata["base_versions"] = metadata["base_versions"][-10:]

        # Update current BASE pointer
        metadata["current_base"] = {
            "timestamp": timestamp,
            "file_count": len(file_hashes),
            "combined_hash": self._calculate_combined_hash(file_hashes),
        }

        metadata["task_id"] = task_id
        metadata["last_updated"] = timestamp

        if self.dry_run:
            print(f"[DRY RUN] Would update metadata: {metadata_path}")
            print(f"          Files: {len(file_hashes)}")
            print(f"          Combined hash: {metadata['current_base']['combined_hash'][:16]}...")
            return True

        try:
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_path, "w") as f:
                yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
            if self.verbose:
                print(f"  Updated metadata: {metadata_path}")
            return True
        except Exception as e:
            self.errors.append(f"Error writing metadata: {e}")
            return False

    def _find_wiring_file(self, task_id: str) -> Optional[Path]:
        """Find wiring.yaml for a task."""
        candidates = [
            self.root_dir / "tasks" / task_id / ".task" / "wiring.yaml",
            self.root_dir / "tasks" / task_id / "wiring.yaml",
            self.root_dir / task_id / ".task" / "wiring.yaml",
            self.root_dir / ".task" / "wiring.yaml",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _calculate_combined_hash(self, file_hashes: dict[str, str]) -> str:
        """Calculate combined hash of all file hashes."""
        hasher = hashlib.sha256()
        for path in sorted(file_hashes.keys()):
            hasher.update(path.encode())
            hasher.update(file_hashes[path].encode())
        return hasher.hexdigest()

    def get_summary(self) -> dict:
        """Get update summary."""
        return {
            "files_updated": len(self.files_updated),
            "files": self.files_updated,
            "errors": self.errors,
            "success": len(self.errors) == 0
        }

    def format_output(self, task_id: str, format_type: str = "text") -> str:
        """Format output for display."""
        summary = self.get_summary()

        if format_type == "json":
            return json.dumps({
                "task_id": task_id,
                **summary
            }, indent=2)

        lines = []
        lines.append("=" * 50)
        lines.append(f"BASE VERSION UPDATE: {task_id}")
        lines.append("=" * 50)

        if summary["success"]:
            lines.append(f"\n✓ Successfully updated {summary['files_updated']} files")
        else:
            lines.append(f"\n✗ Update failed with {len(summary['errors'])} errors")

        if self.verbose and summary["files"]:
            lines.append("\nFiles updated:")
            for f in summary["files"][:20]:
                lines.append(f"  - {f}")
            if len(summary["files"]) > 20:
                lines.append(f"  ... and {len(summary['files']) - 20} more")

        if summary["errors"]:
            lines.append("\nErrors:")
            for error in summary["errors"]:
                lines.append(f"  - {error}")

        lines.append("\n" + "=" * 50)
        return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Store BASE versions for three-way merge regeneration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - BASE versions updated successfully
  1 - Validation error
  2 - File/parse error

Examples:
  %(prog)s auth-service                    # Update BASE for auth-service task
  %(prog)s my-task --source ./generated   # Specify source directory
  %(prog)s my-task --dry-run              # Preview without making changes
  %(prog)s my-task --verbose              # Show detailed progress
        """
    )

    parser.add_argument(
        "task_id",
        help="The task identifier"
    )

    parser.add_argument(
        "--source", "-s",
        type=Path,
        help="Source directory containing generated files"
    )

    parser.add_argument(
        "--files", "-f",
        nargs="+",
        help="Specific files to update (relative to source)"
    )

    parser.add_argument(
        "--dir", "-d",
        type=Path,
        default=".",
        help="Root directory (default: current directory)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them"
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

    root_dir = Path(args.dir).resolve()
    if not root_dir.exists():
        print(f"Error: Directory not found: {root_dir}", file=sys.stderr)
        sys.exit(2)

    updater = BaseVersionUpdater(
        root_dir=root_dir,
        verbose=args.verbose,
        dry_run=args.dry_run
    )

    if args.verbose:
        action = "Previewing" if args.dry_run else "Updating"
        print(f"{action} BASE version for task: {args.task_id}")

    success = updater.update_base_version(
        task_id=args.task_id,
        source_dir=args.source,
        files=args.files
    )

    print(updater.format_output(args.task_id, args.format))

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
