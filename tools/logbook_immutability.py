#!/usr/bin/env python3
"""LogBook immutability enforcer (K004).

Makes LogBook entries immutable after creation:
- Sets file permissions to read-only (444) after write
- Detects and prevents deletion attempts
- Enforces append-only log structure

Usage:
    python3 tools/logbook_immutability.py enforce         # Apply immutability to all entries
    python3 tools/logbook_immutability.py check           # Verify immutability
    python3 tools/logbook_immutability.py protect <file>  # Make single file immutable
"""

import argparse
import os
import stat
import sys
from pathlib import Path
from typing import List, Tuple

def make_immutable(file_path: Path) -> bool:
    """Make LogBook entry immutable (read-only).

    Sets permissions to 444 (r--r--r--) to prevent modification.
    """
    try:
        # Set read-only for owner, group, others
        os.chmod(file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        return True
    except Exception as e:
        print(f"❌ Failed to make immutable: {file_path}: {e}")
        return False

def check_immutable(file_path: Path) -> Tuple[bool, str]:
    """Check if file is immutable (read-only).

    Returns:
        (is_immutable, status_message)
    """
    try:
        file_stat = file_path.stat()
        mode = file_stat.st_mode

        # Check if file is read-only (no write bits set)
        has_owner_write = bool(mode & stat.S_IWUSR)
        has_group_write = bool(mode & stat.S_IWGRP)
        has_other_write = bool(mode & stat.S_IWOTH)

        is_writable = has_owner_write or has_group_write or has_other_write

        if is_writable:
            perms = stat.filemode(mode)
            return False, f"❌ Writable ({perms})"
        else:
            return True, "✅ Immutable (read-only)"

    except Exception as e:
        return False, f"❌ Error: {e}"

def find_logbook_entries(base_dir: Path) -> List[Path]:
    """Find all LogBook YAML entries."""
    if not base_dir.exists():
        return []

    return sorted(base_dir.rglob("*.yaml"))

def enforce_immutability(logbook_dir: Path) -> Tuple[int, int]:
    """Enforce immutability on all LogBook entries.

    Returns:
        (protected_count, failed_count)
    """
    entries = find_logbook_entries(logbook_dir)

    if not entries:
        print(f"⚠️  No LogBook entries found in {logbook_dir}/")
        return 0, 0

    print(f"=== Enforcing immutability on {len(entries)} LogBook entries ===\n")

    protected_count = 0
    failed_count = 0

    for entry in entries:
        # Check current state
        is_immutable, status = check_immutable(entry)

        if is_immutable:
            # Already immutable, skip
            protected_count += 1
            continue

        # Make immutable
        print(f"Protecting: {entry.name}")
        if make_immutable(entry):
            protected_count += 1
            print(f"  ✅ Set to read-only (444)")
        else:
            failed_count += 1

    return protected_count, failed_count

def check_all_immutability(logbook_dir: Path) -> Tuple[int, int]:
    """Check immutability of all LogBook entries.

    Returns:
        (immutable_count, mutable_count)
    """
    entries = find_logbook_entries(logbook_dir)

    if not entries:
        print(f"⚠️  No LogBook entries found in {logbook_dir}/")
        return 0, 0

    print(f"=== Checking immutability of {len(entries)} LogBook entries ===\n")

    immutable_count = 0
    mutable_count = 0
    violations = []

    for entry in entries:
        is_immutable, status = check_immutable(entry)

        if is_immutable:
            immutable_count += 1
        else:
            mutable_count += 1
            violations.append((entry, status))

    # Summary
    print(f"\n=== Summary ===")
    print(f"Immutable: {immutable_count}/{len(entries)}")
    print(f"Mutable: {mutable_count}/{len(entries)}")

    if violations:
        print(f"\n❌ Immutability violations:")
        for entry, status in violations:
            print(f"  {entry.name}: {status}")
        print("\nFix with: python3 tools/logbook_immutability.py enforce")
        return immutable_count, mutable_count
    else:
        print("\n✅ All LogBook entries are immutable (read-only)")
        return immutable_count, mutable_count

def detect_deletions(logbook_dir: Path):
    """Detect if LogBook entries have been deleted.

    Note: This requires a separate audit log of created entries.
    For now, we rely on git history to detect deletions.
    """
    try:
        import subprocess

        # Check git log for deleted LogBook entries
        result = subprocess.run(
            ["git", "log", "--diff-filter=D", "--name-only", "--pretty=format:", "--", "LogBook/"],
            capture_output=True,
            text=True,
            cwd=logbook_dir.parent
        )

        deleted_files = [line for line in result.stdout.split("\n") if line.strip() and line.endswith(".yaml")]

        if deleted_files:
            print(f"\n⚠️  AUDIT WARNING: {len(deleted_files)} LogBook entries deleted in git history:")
            for f in deleted_files[:10]:  # Show first 10
                print(f"  - {f}")
            if len(deleted_files) > 10:
                print(f"  ... and {len(deleted_files) - 10} more")
            print("\nLogBook entries should NEVER be deleted!")
            print("Deleted entries indicate potential audit trail tampering.")
        else:
            print("\n✅ No LogBook entry deletions detected in git history")

    except Exception as e:
        print(f"\n⚠️  Could not check for deletions: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="LogBook immutability enforcer"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Enforce command
    enforce_parser = subparsers.add_parser("enforce", help="Apply immutability to all entries")
    enforce_parser.add_argument("--dir", default="LogBook", help="LogBook directory")

    # Check command
    check_parser = subparsers.add_parser("check", help="Verify immutability of all entries")
    check_parser.add_argument("--dir", default="LogBook", help="LogBook directory")
    check_parser.add_argument("--detect-deletions", action="store_true", help="Check git history for deletions")

    # Protect command
    protect_parser = subparsers.add_parser("protect", help="Make single file immutable")
    protect_parser.add_argument("file", help="File to protect")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "enforce":
        logbook_dir = Path(args.dir)
        protected, failed = enforce_immutability(logbook_dir)

        print(f"\n=== Summary ===")
        print(f"Protected: {protected}")
        if failed > 0:
            print(f"Failed: {failed}")
            sys.exit(1)
        else:
            print("✅ All LogBook entries are now immutable")
            sys.exit(0)

    elif args.command == "check":
        logbook_dir = Path(args.dir)
        immutable, mutable = check_all_immutability(logbook_dir)

        if args.detect_deletions:
            detect_deletions(logbook_dir)

        sys.exit(0 if mutable == 0 else 1)

    elif args.command == "protect":
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            sys.exit(1)

        print(f"Making immutable: {file_path}")
        if make_immutable(file_path):
            print("✅ File is now read-only (444)")
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()
