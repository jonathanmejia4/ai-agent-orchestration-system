#!/usr/bin/env python3
"""LogBook retention and archival tool (K005).

Archives old LogBook entries to reduce disk usage while maintaining
compliance with retention policies.

Usage:
    # Archive entries older than 1 year
    python3 tools/logbook_archive.py --older-than 365d

    # Dry run to see what would be archived
    python3 tools/logbook_archive.py --older-than 365d --dry-run

    # Archive to specific location
    python3 tools/logbook_archive.py --older-than 365d --archive-dir LogBook/archive/
"""

import argparse
import gzip
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

try:
    import yaml
except ImportError:
    print("❌ Missing dependency: pyyaml")
    print("Install with: pip install pyyaml")
    sys.exit(2)

def parse_age(age_str: str) -> timedelta:
    """Parse age string like '365d', '90d', '1y'."""
    if age_str.endswith('d'):
        days = int(age_str[:-1])
        return timedelta(days=days)
    elif age_str.endswith('y'):
        years = int(age_str[:-1])
        return timedelta(days=years * 365)
    else:
        raise ValueError(f"Invalid age format: {age_str}. Use '365d' or '1y'")

def get_entry_age(entry_path: Path) -> Tuple[datetime, int]:
    """Get entry timestamp and age in days.

    Returns:
        (timestamp, age_in_days)
    """
    try:
        entry = yaml.safe_load(entry_path.read_text())
        timestamp_str = entry.get('timestamp')

        if not timestamp_str:
            # Fall back to file modification time
            mtime = entry_path.stat().st_mtime
            timestamp = datetime.fromtimestamp(mtime, tz=timezone.utc)
        else:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

        age = datetime.now(timezone.utc) - timestamp
        return timestamp, age.days

    except Exception as e:
        print(f"⚠️  Error reading {entry_path.name}: {e}", file=sys.stderr)
        # Fall back to file mtime
        mtime = entry_path.stat().st_mtime
        timestamp = datetime.fromtimestamp(mtime, tz=timezone.utc)
        age = datetime.now(timezone.utc) - timestamp
        return timestamp, age.days

def compress_entry(entry_path: Path, archive_dir: Path) -> bool:
    """Compress and move entry to archive directory.

    File is gzip-compressed to save space.
    """
    try:
        # Preserve directory structure
        relative_path = entry_path.relative_to(Path("LogBook"))
        archive_path = archive_dir / relative_path.parent
        archive_path.mkdir(parents=True, exist_ok=True)

        # Compress
        compressed_path = archive_path / f"{entry_path.name}.gz"

        with open(entry_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove original
        entry_path.unlink()

        return True

    except Exception as e:
        print(f"❌ Failed to archive {entry_path.name}: {e}", file=sys.stderr)
        return False

def archive_old_entries(
    logbook_dir: Path,
    archive_dir: Path,
    older_than_days: int,
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """Archive entries older than specified age.

    Returns:
        (archived_count, skipped_count, bytes_saved)
    """
    entries = list(logbook_dir.rglob("*.yaml"))

    print(f"Found {len(entries)} LogBook entries")
    print(f"Archiving entries older than {older_than_days} days")
    print("")

    archived_count = 0
    skipped_count = 0
    bytes_saved = 0

    for entry_path in entries:
        timestamp, age_days = get_entry_age(entry_path)

        if age_days >= older_than_days:
            # Archive this entry
            original_size = entry_path.stat().st_size

            if dry_run:
                print(f"Would archive: {entry_path.name} (age: {age_days} days, {original_size} bytes)")
                archived_count += 1
                bytes_saved += original_size * 0.7  # Estimate 70% compression
            else:
                print(f"Archiving: {entry_path.name} (age: {age_days} days)")
                if compress_entry(entry_path, archive_dir):
                    archived_count += 1
                    bytes_saved += original_size * 0.7  # Estimate
                else:
                    skipped_count += 1
        else:
            skipped_count += 1

    return archived_count, skipped_count, int(bytes_saved)

def main():
    parser = argparse.ArgumentParser(
        description="Archive old LogBook entries"
    )

    parser.add_argument("--older-than", required=True,
                       help="Archive entries older than this (e.g., '365d', '1y')")
    parser.add_argument("--logbook-dir", default="LogBook",
                       help="LogBook directory")
    parser.add_argument("--archive-dir", default="LogBook/archive",
                       help="Archive directory")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be archived without doing it")

    args = parser.parse_args()

    # Parse age
    try:
        age_delta = parse_age(args.older_than)
        older_than_days = age_delta.days
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    logbook_dir = Path(args.logbook_dir)
    archive_dir = Path(args.archive_dir)

    if not logbook_dir.exists():
        print(f"❌ LogBook directory not found: {logbook_dir}", file=sys.stderr)
        sys.exit(1)

    # Create archive directory
    if not args.dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    # Archive
    archived, skipped, bytes_saved = archive_old_entries(
        logbook_dir, archive_dir, older_than_days, args.dry_run
    )

    # Summary
    print("")
    print("=== Summary ===")
    print(f"Archived: {archived}")
    print(f"Kept: {skipped}")
    print(f"Space saved: {bytes_saved:,} bytes ({bytes_saved / 1024:.1f} KB)")

    if args.dry_run:
        print("\n(DRY RUN - no files were modified)")
        print(f"Run without --dry-run to actually archive {archived} entries")

    sys.exit(0)

if __name__ == "__main__":
    main()
