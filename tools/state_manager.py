#!/usr/bin/env python3
"""
StateManager - Atomic state file persistence with validation.

Implements the StateManager class defined in state-persistence-protocol.md:108-316.
Provides atomic writes, backups, checksums, and validation for state files.

Usage:
    python tools/state_manager.py update --file <path> --content <content> --agent <agent>
    python tools/state_manager.py read --file <path> [--validate]
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class StateManager:
    """Manages state file persistence with atomic writes and validation."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.backup_path = self.base_path / ".state_backups"
        self.backup_path.mkdir(exist_ok=True)

    def update_state(
        self,
        file_path: str,
        content: str,
        agent: str,
        operation: str = "update"
    ) -> Dict:
        """
        Safely update a state file with atomic write and validation.

        Args:
            file_path: Path to state file
            content: New content to write
            agent: Agent performing update
            operation: Type of operation (update, create, append)

        Returns:
            Result dict with success status and details
        """
        target = self.base_path / file_path
        result = {
            "success": False,
            "file_path": str(target),
            "agent": agent,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        try:
            # Step 1: Create backup of existing file
            if target.exists():
                backup_file = self._create_backup(target)
                result["backup_created"] = str(backup_file)
                result["checksum_before"] = self._checksum(target)
            else:
                result["backup_created"] = None
                result["checksum_before"] = None
                # Ensure parent directory exists for new files
                target.parent.mkdir(parents=True, exist_ok=True)

            # Step 2: Write to temporary file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=target.parent,
                prefix=f".{target.stem}_",
                suffix=".tmp"
            )

            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
            except Exception as e:
                os.unlink(temp_path)
                raise e

            # Step 3: Atomic rename
            shutil.move(temp_path, target)

            # Step 4: Validate write
            result["checksum_after"] = self._checksum(target)

            with open(target, 'r', encoding='utf-8') as f:
                written_content = f.read()

            if written_content != content:
                # Validation failed - rollback
                if result["backup_created"]:
                    shutil.copy(result["backup_created"], target)
                raise ValueError("Write validation failed - content mismatch")

            result["success"] = True
            result["bytes_written"] = len(content.encode('utf-8'))

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)

        # Log the operation
        self._log_state_update(result)

        return result

    def read_state(self, file_path: str, validate: bool = True) -> Dict:
        """
        Read a state file with optional validation.

        Returns:
            {
                "success": bool,
                "content": str or None,
                "checksum": str,
                "last_modified": str,
                "validation": dict
            }
        """
        target = self.base_path / file_path
        result = {
            "success": False,
            "file_path": str(target),
            "content": None,
            "checksum": None,
            "last_modified": None,
            "validation": None
        }

        if not target.exists():
            result["error"] = f"State file not found: {file_path}"
            return result

        try:
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()

            result["content"] = content
            result["checksum"] = self._checksum(target)
            result["last_modified"] = datetime.fromtimestamp(
                target.stat().st_mtime
            ).isoformat() + "Z"
            result["success"] = True

            if validate:
                result["validation"] = self._validate_state_file(file_path, content)

        except Exception as e:
            result["error"] = str(e)

        return result

    def _create_backup(self, file_path: Path) -> Path:
        """Create a timestamped backup of the file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"

        # Create date-based subdirectory
        date_dir = self.backup_path / datetime.utcnow().strftime("%Y-%m")
        date_dir.mkdir(exist_ok=True)

        backup_file = date_dir / backup_name
        shutil.copy2(file_path, backup_file)

        return backup_file

    def _checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file (security-grade)."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _validate_state_file(self, file_path: str, content: str) -> Dict:
        """Validate state file format and content."""
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Check for empty content
        if not content.strip():
            validation["errors"].append("Empty state file")
            validation["valid"] = False

        # Check for required headers based on file type
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            try:
                import yaml
                yaml.safe_load(content)
            except Exception as e:
                validation["errors"].append(f"Invalid YAML: {e}")
                validation["valid"] = False

        elif file_path.endswith('.md'):
            # Check for version/timestamp header
            if "last_updated:" not in content.lower() and "version:" not in content.lower():
                validation["warnings"].append("No version/timestamp header found")

        return validation

    def _log_state_update(self, result: Dict):
        """Log state update to audit trail."""
        log_path = self.base_path / "LogBook" / "audit" / "state_updates.yaml"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": result["timestamp"],
            "file_path": result["file_path"],
            "agent": result["agent"],
            "operation": result["operation"],
            "success": result["success"],
            "checksum_before": result.get("checksum_before"),
            "checksum_after": result.get("checksum_after"),
            "backup": result.get("backup_created"),
            "error": result.get("error")
        }

        # Append to log (simple append for now)
        try:
            import yaml
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write("---\n")
                yaml.dump(entry, f, default_flow_style=False)
        except ImportError:
            # Fallback to JSON if PyYAML not available
            import json
            with open(log_path.with_suffix('.json'), 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="StateManager - Atomic state file operations"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Update command
    update_parser = subparsers.add_parser("update", help="Update a state file")
    update_parser.add_argument("--file", required=True, help="Path to state file")
    update_parser.add_argument("--content", help="New content (use --content-file for large content)")
    update_parser.add_argument("--content-file", help="Path to file containing new content")
    update_parser.add_argument("--agent", required=True, help="Agent performing update")
    update_parser.add_argument("--operation", default="update", choices=["update", "create", "append"])
    update_parser.add_argument("--base-path", default=".", help="Base path for state files")

    # Read command
    read_parser = subparsers.add_parser("read", help="Read a state file")
    read_parser.add_argument("--file", required=True, help="Path to state file")
    read_parser.add_argument("--validate", action="store_true", help="Validate file content")
    read_parser.add_argument("--base-path", default=".", help="Base path for state files")

    args = parser.parse_args()

    manager = StateManager(base_path=args.base_path)

    if args.command == "update":
        # Get content
        if args.content_file:
            content_path = Path(args.content_file)
            if not content_path.exists():
                print(f"ERROR: Content file not found: {content_path}", file=sys.stderr)
                sys.exit(1)
            content = content_path.read_text()
        elif args.content:
            content = args.content
        else:
            print("ERROR: Must provide --content or --content-file", file=sys.stderr)
            sys.exit(1)

        # Update state
        result = manager.update_state(
            file_path=args.file,
            content=content,
            agent=args.agent,
            operation=args.operation
        )

        print(json.dumps(result, indent=2))

        if not result["success"]:
            sys.exit(1)

    elif args.command == "read":
        # Read state
        result = manager.read_state(
            file_path=args.file,
            validate=args.validate
        )

        # Don't print content to stdout if it's large
        display_result = result.copy()
        if display_result.get("content") and len(display_result["content"]) > 1000:
            display_result["content"] = f"<{len(result['content'])} bytes>"

        print(json.dumps(display_result, indent=2))

        if not result["success"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
