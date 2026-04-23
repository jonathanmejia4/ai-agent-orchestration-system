#!/usr/bin/env python3
"""
snapshot_manager.py - the system State Snapshot Manager

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - State Management

Purpose:
    Creates and manages state snapshots for the system:
    - Full system snapshots
    - Task snapshots
    - LogBook snapshots
    - Point-in-time recovery support

Usage:
    python3 snapshot_manager.py create --name "pre-release-v2"
    python3 snapshot_manager.py restore --snapshot-id SNAP-20251224-001
    python3 snapshot_manager.py list --limit 10
    python3 snapshot_manager.py diff --from SNAP-001 --to SNAP-002
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class SnapshotManifest:
    """Snapshot manifest with metadata."""
    snapshot_id: str
    name: str
    description: str
    created_at: str
    created_by: str
    snapshot_type: str  # full, task, logbook, partial
    size_bytes: int
    file_count: int
    checksum: str
    includes: List[str]
    excludes: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "snapshot_type": self.snapshot_type,
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
            "checksum": self.checksum,
            "includes": self.includes,
            "excludes": self.excludes,
            "metadata": self.metadata
        }

@dataclass
class SnapshotDiff:
    """Differences between two snapshots."""
    from_snapshot: str
    to_snapshot: str
    added_files: List[str]
    removed_files: List[str]
    modified_files: List[str]
    unchanged_files: int

    def to_dict(self) -> dict:
        return {
            "from_snapshot": self.from_snapshot,
            "to_snapshot": self.to_snapshot,
            "added_files": self.added_files,
            "removed_files": self.removed_files,
            "modified_files": self.modified_files,
            "unchanged_files": self.unchanged_files,
            "summary": {
                "added": len(self.added_files),
                "removed": len(self.removed_files),
                "modified": len(self.modified_files),
                "unchanged": self.unchanged_files
            }
        }

class SnapshotManager:
    """Manages the system state snapshots."""

    # Default patterns to exclude
    DEFAULT_EXCLUDES = [
        ".git",
        "__pycache__",
        "*.pyc",
        ".venv",
        "venv",
        "node_modules",
        ".DS_Store",
        "*.log",
        ".env",
        "*.tmp"
    ]

    # Default patterns to include for different snapshot types
    SNAPSHOT_TYPES = {
        "full": {
            "includes": ["**/*"],
            "excludes": DEFAULT_EXCLUDES
        },
        "task": {
            "includes": ["task*/**/*"],
            "excludes": DEFAULT_EXCLUDES
        },
        "logbook": {
            "includes": ["LogBook/**/*"],
            "excludes": []
        },
        "planning": {
            "includes": ["PLANNING/**/*", ".claude/**/*"],
            "excludes": []
        },
        "tools": {
            "includes": ["tools/**/*"],
            "excludes": DEFAULT_EXCLUDES
        }
    }

    def __init__(self, base_path: str = ".", snapshots_dir: str = None):
        self.base_path = Path(base_path)
        self.snapshots_dir = Path(snapshots_dir) if snapshots_dir else self.base_path / ".snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._load_registry()

    def _load_registry(self):
        """Load snapshot registry."""
        self.registry: Dict[str, SnapshotManifest] = {}
        registry_file = self.snapshots_dir / "registry.yaml"

        if registry_file.exists() and HAS_YAML:
            try:
                with open(registry_file) as f:
                    data = yaml.safe_load(f) or {}
                for snap_data in data.get("snapshots", []):
                    manifest = SnapshotManifest(
                        snapshot_id=snap_data.get("snapshot_id"),
                        name=snap_data.get("name", ""),
                        description=snap_data.get("description", ""),
                        created_at=snap_data.get("created_at", ""),
                        created_by=snap_data.get("created_by", "system"),
                        snapshot_type=snap_data.get("snapshot_type", "full"),
                        size_bytes=snap_data.get("size_bytes", 0),
                        file_count=snap_data.get("file_count", 0),
                        checksum=snap_data.get("checksum", ""),
                        includes=snap_data.get("includes", []),
                        excludes=snap_data.get("excludes", []),
                        metadata=snap_data.get("metadata", {})
                    )
                    self.registry[manifest.snapshot_id] = manifest
            except Exception:
                pass

    def _save_registry(self):
        """Save snapshot registry."""
        if not HAS_YAML:
            return

        registry_file = self.snapshots_dir / "registry.yaml"
        data = {
            "snapshots": [m.to_dict() for m in self.registry.values()],
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

        with open(registry_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def _generate_snapshot_id(self) -> str:
        """Generate unique snapshot ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        count = len([s for s in self.registry if timestamp[:8] in s]) + 1
        return f"SNAP-{timestamp}-{count:03d}"

    def _should_include(self, path: Path, includes: List[str], excludes: List[str]) -> bool:
        """Check if path should be included in snapshot."""
        import fnmatch

        rel_path = str(path.relative_to(self.base_path))

        # Check excludes first
        for pattern in excludes:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(path.name, pattern):
                return False

        # Check includes
        for pattern in includes:
            if fnmatch.fnmatch(rel_path, pattern):
                return True

        return False

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate file checksum."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()[:16]

    def create_snapshot(
        self,
        name: str,
        description: str = "",
        snapshot_type: str = "full",
        includes: Optional[List[str]] = None,
        excludes: Optional[List[str]] = None,
        created_by: str = "system"
    ) -> SnapshotManifest:
        """Create a new snapshot."""
        snapshot_id = self._generate_snapshot_id()

        # Get include/exclude patterns
        type_config = self.SNAPSHOT_TYPES.get(snapshot_type, self.SNAPSHOT_TYPES["full"])
        inc = includes or type_config["includes"]
        exc = excludes or type_config["excludes"]

        # Create snapshot directory
        snapshot_dir = self.snapshots_dir / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Collect files
        files_to_snapshot: List[Path] = []
        for pattern in inc:
            for file_path in self.base_path.rglob("*"):
                if file_path.is_file() and self._should_include(file_path, inc, exc):
                    files_to_snapshot.append(file_path)

        # Remove duplicates
        files_to_snapshot = list(set(files_to_snapshot))

        # Create tarball
        tar_path = snapshot_dir / "data.tar.gz"
        total_size = 0
        file_hashes = {}

        with tarfile.open(tar_path, "w:gz") as tar:
            for file_path in files_to_snapshot:
                try:
                    rel_path = file_path.relative_to(self.base_path)
                    tar.add(file_path, arcname=str(rel_path))
                    total_size += file_path.stat().st_size
                    file_hashes[str(rel_path)] = self._calculate_checksum(file_path)
                except Exception:
                    pass

        # Calculate overall checksum
        overall_checksum = self._calculate_checksum(tar_path)

        # Create manifest
        manifest = SnapshotManifest(
            snapshot_id=snapshot_id,
            name=name,
            description=description,
            created_at=datetime.utcnow().isoformat() + "Z",
            created_by=created_by,
            snapshot_type=snapshot_type,
            size_bytes=total_size,
            file_count=len(files_to_snapshot),
            checksum=overall_checksum,
            includes=inc,
            excludes=exc,
            metadata={"file_hashes": file_hashes}
        )

        # Save manifest
        manifest_path = snapshot_dir / "manifest.yaml"
        if HAS_YAML:
            with open(manifest_path, 'w') as f:
                yaml.dump(manifest.to_dict(), f, default_flow_style=False)

        # Update registry
        self.registry[snapshot_id] = manifest
        self._save_registry()

        return manifest

    def _validate_tar_member(self, member: tarfile.TarInfo, target: Path) -> bool:
        """Validate tar member path to prevent path traversal attacks.

        Per CLAUDE.md Section 4.1 and 4.2: All code must pass security checks
        and must not contain vulnerabilities like path traversal.

        Args:
            member: The tar archive member to validate
            target: The intended extraction target directory

        Returns:
            True if the member path is safe, False otherwise
        """
        # Get the resolved path of the member within target
        member_path = (target / member.name).resolve()
        target_resolved = target.resolve()

        # Check if the resolved path is within the target directory
        try:
            member_path.relative_to(target_resolved)
            return True
        except ValueError:
            return False

    def restore_snapshot(
        self,
        snapshot_id: str,
        target_path: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Restore a snapshot.

        Security: Validates all tar archive members for path traversal
        before extraction per CLAUDE.md Section 4.1.
        """
        if snapshot_id not in self.registry:
            return {"success": False, "error": f"Snapshot {snapshot_id} not found"}

        manifest = self.registry[snapshot_id]
        snapshot_dir = self.snapshots_dir / snapshot_id
        tar_path = snapshot_dir / "data.tar.gz"

        if not tar_path.exists():
            return {"success": False, "error": "Snapshot data not found"}

        target = Path(target_path) if target_path else self.base_path
        restored_files = []

        if dry_run:
            # Just list files that would be restored
            with tarfile.open(tar_path, "r:gz") as tar:
                restored_files = tar.getnames()

            return {
                "success": True,
                "dry_run": True,
                "files_to_restore": len(restored_files),
                "files": restored_files[:20]
            }

        # Actually restore with path traversal protection
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                # Validate all members for path traversal before extraction
                # Per Python tarfile security advisory and CLAUDE.md Section 4.1
                unsafe_members = []
                for member in tar.getmembers():
                    if not self._validate_tar_member(member, target):
                        unsafe_members.append(member.name)

                if unsafe_members:
                    return {
                        "success": False,
                        "error": f"Path traversal detected in archive. Unsafe paths: {unsafe_members[:5]}"
                    }

                # Safe to extract - all paths validated
                tar.extractall(path=target)
                restored_files = tar.getnames()

            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "restored_to": str(target),
                "files_restored": len(restored_files)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_snapshot(self, snapshot_id: str, force: bool = False, log_to_logbook: bool = True) -> bool:
        """Delete a snapshot with human approval gate and LogBook logging.

        Per CLAUDE.md Section 1.1: Destructive operations require human approval.
        Per CLAUDE.md Section 2.1.3: All agent actions MUST be logged to LogBook.

        Args:
            snapshot_id: ID of the snapshot to delete
            force: If True, skip confirmation prompt (explicit approval)
            log_to_logbook: If True, log deletion to LogBook (default True)

        Returns:
            True if deleted, False if not found or cancelled
        """
        if snapshot_id not in self.registry:
            return False

        manifest = self.registry[snapshot_id]
        snapshot_dir = self.snapshots_dir / snapshot_id

        # Human approval gate per CLAUDE.md Section 1.1
        if not force:
            print(f"\n{chr(9888)} DESTRUCTIVE OPERATION: Delete snapshot {snapshot_id}")
            print(f"   Name: {manifest.name}")
            print(f"   Type: {manifest.snapshot_type}")
            print(f"   Files: {manifest.file_count}")
            print(f"   Size: {manifest.size_bytes / 1024:.1f} KB")
            print(f"   Created: {manifest.created_at}")
            confirm = input("\nType 'yes' to confirm deletion: ")
            if confirm.lower() != 'yes':
                print("Deletion cancelled.")
                return False

        # Perform deletion
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)

        del self.registry[snapshot_id]
        self._save_registry()

        # Log to LogBook per CLAUDE.md Section 2.1.3 and 5.1
        if log_to_logbook:
            self._log_deletion_to_logbook(snapshot_id, manifest)

        return True

    def _log_deletion_to_logbook(self, snapshot_id: str, manifest: SnapshotManifest):
        """Log snapshot deletion to LogBook per CLAUDE.md Section 5.1.

        Logs: Timestamp, Agent identifier, Action taken, Rationale, Outcome
        """
        import os
        from datetime import datetime

        logbook_dir = self.base_path / "LogBook" / "pm" / "actions"
        logbook_dir.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "snapshot_manager",
            "action": "delete_snapshot",
            "snapshot_id": snapshot_id,
            "snapshot_name": manifest.name,
            "snapshot_type": manifest.snapshot_type,
            "files_deleted": manifest.file_count,
            "size_bytes": manifest.size_bytes,
            "rationale": "User-initiated snapshot deletion",
            "outcome": "success"
        }

        # Append to actions log
        log_file = logbook_dir / "snapshot_deletions.yaml"
        try:
            if HAS_YAML:
                existing = []
                if log_file.exists():
                    with open(log_file) as f:
                        data = yaml.safe_load(f) or {}
                        existing = data.get("deletions", [])
                existing.append(log_entry)
                with open(log_file, 'w') as f:
                    yaml.dump({"deletions": existing}, f, default_flow_style=False)
        except Exception:
            # Don't fail deletion if logging fails, but log to console
            print(f"Warning: Could not log to LogBook: {log_file}")

    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotManifest]:
        """Get snapshot details."""
        return self.registry.get(snapshot_id)

    def list_snapshots(
        self,
        snapshot_type: Optional[str] = None,
        limit: int = 20
    ) -> List[SnapshotManifest]:
        """List snapshots with optional filters."""
        snapshots = list(self.registry.values())

        if snapshot_type:
            snapshots = [s for s in snapshots if s.snapshot_type == snapshot_type]

        # Sort by creation time (newest first)
        snapshots.sort(key=lambda s: s.created_at, reverse=True)

        return snapshots[:limit]

    def diff_snapshots(
        self,
        from_snapshot_id: str,
        to_snapshot_id: str
    ) -> Optional[SnapshotDiff]:
        """Calculate diff between two snapshots."""
        from_snap = self.registry.get(from_snapshot_id)
        to_snap = self.registry.get(to_snapshot_id)

        if not from_snap or not to_snap:
            return None

        from_hashes = from_snap.metadata.get("file_hashes", {})
        to_hashes = to_snap.metadata.get("file_hashes", {})

        from_files = set(from_hashes.keys())
        to_files = set(to_hashes.keys())

        added = list(to_files - from_files)
        removed = list(from_files - to_files)
        common = from_files & to_files

        modified = []
        unchanged = 0

        for f in common:
            if from_hashes.get(f) != to_hashes.get(f):
                modified.append(f)
            else:
                unchanged += 1

        return SnapshotDiff(
            from_snapshot=from_snapshot_id,
            to_snapshot=to_snapshot_id,
            added_files=sorted(added),
            removed_files=sorted(removed),
            modified_files=sorted(modified),
            unchanged_files=unchanged
        )

def main():
    parser = argparse.ArgumentParser(description="the system Snapshot Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create snapshot")
    create_parser.add_argument("--name", required=True, help="Snapshot name")
    create_parser.add_argument("--description", "-d", default="", help="Description")
    create_parser.add_argument("--type", default="full", choices=["full", "task", "logbook", "planning", "tools"])
    create_parser.add_argument("--created-by", default="system", help="Creator")

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore snapshot")
    restore_parser.add_argument("--snapshot-id", required=True, help="Snapshot ID")
    restore_parser.add_argument("--target", help="Target path (default: current)")
    restore_parser.add_argument("--dry-run", action="store_true", help="Show what would be restored")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete snapshot")
    delete_parser.add_argument("--snapshot-id", required=True, help="Snapshot ID")
    delete_parser.add_argument("--force", "-f", action="store_true",
                               help="Skip confirmation prompt (explicit approval)")

    # List command
    list_parser = subparsers.add_parser("list", help="List snapshots")
    list_parser.add_argument("--type", help="Filter by type")
    list_parser.add_argument("--limit", type=int, default=20, help="Max results")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get snapshot details")
    get_parser.add_argument("--snapshot-id", required=True, help="Snapshot ID")

    # Diff command
    diff_parser = subparsers.add_parser("diff", help="Compare snapshots")
    diff_parser.add_argument("--from", dest="from_snap", required=True, help="From snapshot")
    diff_parser.add_argument("--to", dest="to_snap", required=True, help="To snapshot")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    manager = SnapshotManager()

    if args.command == "create":
        manifest = manager.create_snapshot(
            name=args.name,
            description=args.description,
            snapshot_type=args.type,
            created_by=args.created_by
        )

        if args.format == "json":
            print(json.dumps(manifest.to_dict(), indent=2))
        else:
            print(f"\n\u2705 Snapshot created: {manifest.snapshot_id}")
            print(f"   Name: {manifest.name}")
            print(f"   Type: {manifest.snapshot_type}")
            print(f"   Files: {manifest.file_count}")
            print(f"   Size: {manifest.size_bytes / 1024:.1f} KB")

    elif args.command == "restore":
        result = manager.restore_snapshot(
            args.snapshot_id,
            args.target,
            args.dry_run
        )

        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                if result.get("dry_run"):
                    print(f"\n[DRY RUN] Would restore {result['files_to_restore']} files")
                else:
                    print(f"\n\u2705 Restored {result['files_restored']} files to {result['restored_to']}")
            else:
                print(f"\n\u274c Error: {result.get('error')}")

    elif args.command == "delete":
        success = manager.delete_snapshot(args.snapshot_id, force=args.force)
        if success:
            print(f"\u2705 Deleted snapshot {args.snapshot_id}")
        else:
            print(f"\u274c Snapshot {args.snapshot_id} not found or deletion cancelled")

    elif args.command == "list":
        snapshots = manager.list_snapshots(args.type, args.limit)

        if args.format == "json":
            print(json.dumps([s.to_dict() for s in snapshots], indent=2))
        else:
            print(f"\nSnapshots ({len(snapshots)}):")
            print("=" * 60)
            for s in snapshots:
                print(f"\n  {s.snapshot_id}")
                print(f"    Name: {s.name}")
                print(f"    Type: {s.snapshot_type}")
                print(f"    Created: {s.created_at}")
                print(f"    Files: {s.file_count}, Size: {s.size_bytes / 1024:.1f} KB")

    elif args.command == "get":
        snapshot = manager.get_snapshot(args.snapshot_id)

        if snapshot:
            if args.format == "json":
                print(json.dumps(snapshot.to_dict(), indent=2))
            else:
                print(f"\nSnapshot: {snapshot.snapshot_id}")
                print("=" * 50)
                print(f"Name: {snapshot.name}")
                print(f"Description: {snapshot.description}")
                print(f"Type: {snapshot.snapshot_type}")
                print(f"Created: {snapshot.created_at}")
                print(f"Created By: {snapshot.created_by}")
                print(f"Files: {snapshot.file_count}")
                print(f"Size: {snapshot.size_bytes / 1024:.1f} KB")
                print(f"Checksum: {snapshot.checksum}")
        else:
            print(f"Snapshot {args.snapshot_id} not found")
            return 1

    elif args.command == "diff":
        diff = manager.diff_snapshots(args.from_snap, args.to_snap)

        if diff:
            if args.format == "json":
                print(json.dumps(diff.to_dict(), indent=2))
            else:
                print(f"\nDiff: {diff.from_snapshot} -> {diff.to_snapshot}")
                print("=" * 50)
                print(f"Added: {len(diff.added_files)}")
                print(f"Removed: {len(diff.removed_files)}")
                print(f"Modified: {len(diff.modified_files)}")
                print(f"Unchanged: {diff.unchanged_files}")

                if diff.added_files:
                    print("\nAdded files:")
                    for f in diff.added_files[:10]:
                        print(f"  + {f}")

                if diff.removed_files:
                    print("\nRemoved files:")
                    for f in diff.removed_files[:10]:
                        print(f"  - {f}")

                if diff.modified_files:
                    print("\nModified files:")
                    for f in diff.modified_files[:10]:
                        print(f"  ~ {f}")
        else:
            print("Could not diff snapshots")
            return 1

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
