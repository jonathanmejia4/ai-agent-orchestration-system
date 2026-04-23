#!/usr/bin/env python3
"""
get_base_version.py - BASE Version Retrieval Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: CRITICAL - Three-Way Merge Support Tool

Purpose:
    Retrieves the original generated file (BASE) for three-way merge.
    Fetches file content as it was after initial template generation.
    Enables BASE vs LOCAL vs NEW comparison for safe regeneration.

Usage:
    python3 get_base_version.py --task task001 --file src/api.ts
    python3 get_base_version.py --task task001 --file src/api.ts --output base.ts
    python3 get_base_version.py --task task001 --file src/api.ts --format json
"""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class BaseVersion:
    """Represents the BASE version of a generated file."""
    task_id: str
    file_path: str
    base_content: str
    generated_at: Optional[str]
    template: Optional[str]
    template_version: Optional[str]
    commit: Optional[str]
    source: str  # "git", "cache", "snapshot"
    content_hash: str

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "file": self.file_path,
            "base_content": self.base_content,
            "generated_at": self.generated_at,
            "template": self.template,
            "template_version": self.template_version,
            "commit": self.commit,
            "source": self.source,
            "content_hash": self.content_hash
        }

class BaseVersionRetriever:
    """Retrieves BASE version of generated files."""

    def __init__(self, task_id: str, verbose: bool = False):
        self.task_id = task_id
        self.verbose = verbose
        self.task_path = self._find_task_path()

    def _find_task_path(self) -> Optional[Path]:
        """Find the task directory."""
        candidates = [
            Path(self.task_id),
            Path("tasks") / self.task_id,
            Path("."),
        ]

        for candidate in candidates:
            if (candidate / ".task").exists():
                return candidate

        return None

    def _log(self, message: str):
        """Log verbose message."""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def _get_from_git(self, file_path: str) -> Optional[BaseVersion]:
        """Try to get BASE from git history."""
        if not self.task_path:
            return None

        full_path = self.task_path / file_path

        try:
            # Find the commit when file was first added (generation commit)
            result = subprocess.run(
                ["git", "log", "--follow", "--format=%H", "--diff-filter=A", "--", str(full_path)],
                capture_output=True,
                text=True,
                cwd=str(self.task_path)
            )

            if result.returncode != 0 or not result.stdout.strip():
                self._log(f"Git log failed or no commits found for {file_path}")
                return None

            # Get the first (oldest) commit that added this file
            commits = result.stdout.strip().split('\n')
            generation_commit = commits[-1] if commits else None

            if not generation_commit:
                return None

            self._log(f"Found generation commit: {generation_commit}")

            # Get file content at that commit
            result = subprocess.run(
                ["git", "show", f"{generation_commit}:{file_path}"],
                capture_output=True,
                text=True,
                cwd=str(self.task_path)
            )

            if result.returncode != 0:
                self._log(f"Failed to get file content at commit {generation_commit}")
                return None

            content = result.stdout

            # Get commit timestamp
            result = subprocess.run(
                ["git", "log", "-1", "--format=%aI", generation_commit],
                capture_output=True,
                text=True,
                cwd=str(self.task_path)
            )

            timestamp = result.stdout.strip() if result.returncode == 0 else None

            return BaseVersion(
                task_id=self.task_id,
                file_path=file_path,
                base_content=content,
                generated_at=timestamp,
                template=None,
                template_version=None,
                commit=generation_commit,
                source="git",
                content_hash=hashlib.sha256(content.encode()).hexdigest()
            )

        except FileNotFoundError:
            self._log("Git not available")
            return None
        except Exception as e:
            self._log(f"Git error: {e}")
            return None

    def _get_from_cache(self, file_path: str) -> Optional[BaseVersion]:
        """Try to get BASE from .saf/generated cache."""
        cache_locations = [
            Path(".saf") / "generated" / self.task_id / file_path,
            Path(".task") / "base_snapshots" / file_path,
            self.task_path / ".task" / "base" / file_path if self.task_path else None,
        ]

        for cache_path in cache_locations:
            if cache_path and cache_path.exists():
                self._log(f"Found cached BASE at {cache_path}")
                try:
                    content = cache_path.read_text()

                    # Try to get metadata
                    metadata_path = cache_path.with_suffix(cache_path.suffix + ".meta")
                    metadata = {}
                    if metadata_path.exists() and HAS_YAML:
                        with open(metadata_path) as f:
                            metadata = yaml.safe_load(f) or {}

                    return BaseVersion(
                        task_id=self.task_id,
                        file_path=file_path,
                        base_content=content,
                        generated_at=metadata.get("generated_at"),
                        template=metadata.get("template"),
                        template_version=metadata.get("template_version"),
                        commit=metadata.get("commit"),
                        source="cache",
                        content_hash=hashlib.sha256(content.encode()).hexdigest()
                    )
                except Exception as e:
                    self._log(f"Failed to read cache: {e}")
                    continue

        return None

    def _get_from_snapshot(self, file_path: str) -> Optional[BaseVersion]:
        """Try to get BASE from task snapshot."""
        if not self.task_path:
            return None

        snapshot_dir = self.task_path / ".task" / "snapshots"
        if not snapshot_dir.exists():
            return None

        # Find oldest snapshot (closest to generation)
        snapshots = sorted(snapshot_dir.glob("*.tar.gz"))
        if not snapshots:
            return None

        oldest_snapshot = snapshots[0]
        self._log(f"Checking snapshot: {oldest_snapshot}")

        try:
            import tarfile
            with tarfile.open(oldest_snapshot, 'r:gz') as tar:
                for member in tar.getmembers():
                    if member.name.endswith(file_path):
                        f = tar.extractfile(member)
                        if f:
                            content = f.read().decode('utf-8')
                            return BaseVersion(
                                task_id=self.task_id,
                                file_path=file_path,
                                base_content=content,
                                generated_at=None,
                                template=None,
                                template_version=None,
                                commit=None,
                                source="snapshot",
                                content_hash=hashlib.sha256(content.encode()).hexdigest()
                            )
        except Exception as e:
            self._log(f"Failed to read snapshot: {e}")

        return None

    def get_base_version(self, file_path: str) -> Optional[BaseVersion]:
        """Get BASE version trying multiple sources."""
        # Try sources in order of preference
        sources = [
            ("git", self._get_from_git),
            ("cache", self._get_from_cache),
            ("snapshot", self._get_from_snapshot),
        ]

        for source_name, getter in sources:
            self._log(f"Trying source: {source_name}")
            result = getter(file_path)
            if result:
                self._log(f"Found BASE from {source_name}")
                return result

        return None

def main():
    parser = argparse.ArgumentParser(
        description="Retrieve BASE version of generated file for three-way merge"
    )
    parser.add_argument(
        "--task", "-b",
        required=True,
        help="Task ID"
    )
    parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to file within task"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (writes BASE content)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "content"],
        default="json",
        help="Output format (json=full metadata, content=file only)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    retriever = BaseVersionRetriever(args.task, verbose=args.verbose)
    result = retriever.get_base_version(args.file)

    if not result:
        print(json.dumps({
            "error": "BASE version not found",
            "task_id": args.task,
            "file": args.file,
            "message": "Could not find original generated version in git, cache, or snapshots"
        }), file=sys.stderr)
        sys.exit(1)

    # Write to output file if specified
    if args.output:
        with open(args.output, 'w') as f:
            f.write(result.base_content)
        if args.verbose:
            print(f"Wrote BASE content to {args.output}", file=sys.stderr)

    # Output result
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.base_content)

    sys.exit(0)

if __name__ == "__main__":
    main()
