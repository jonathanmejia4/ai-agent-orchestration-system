#!/usr/bin/env python3
"""
Graduation Tracker - Track protected region usage for template graduation.

Per PROTECTED_REGIONS_POLICY.md: When a protected region is used 3+ times
with similar content, it should be graduated to a proper template.

This tool:
1. Scans protected regions across the codebase
2. Identifies reused patterns (similar content hash)
3. Reports regions that should graduate to templates
4. Maintains graduation tracking in LogBook

Usage:
    python3 tools/graduation_tracker.py --scan           # Scan all regions
    python3 tools/graduation_tracker.py --report         # Generate report
    python3 tools/graduation_tracker.py --check          # CI check mode

Exit Codes:
    0 - All checks passed / no graduation needed
    1 - Regions need graduation (for CI blocking)
    2 - Error (missing files, invalid syntax, etc.)

Referenced in:
    - PROTECTED_REGIONS_POLICY.md
    - README.md:818 (graduation tracking)
    - ISSUE_CATALOG.md J-50

Author: System
Created: 2025-12-30
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Graduation threshold - regions used 3+ times should become templates
GRADUATION_THRESHOLD = 3

# Similarity threshold for content matching (percentage)
SIMILARITY_THRESHOLD = 0.85

@dataclass
class RegionUsage:
    """Tracks a protected region usage."""

    file_path: str
    region_name: str
    content_hash: str
    line_count: int
    first_seen: str
    content_preview: str  # First 100 chars

@dataclass
class GraduationCandidate:
    """A region pattern that should graduate to a template."""

    content_hash: str
    region_name: str
    usage_count: int
    files: List[str]
    recommended_template_name: str
    line_count: int
    sample_content: str

def compute_content_hash(content: str) -> str:
    """Compute normalized content hash for similarity detection.

    Normalizes whitespace to detect similar (not just identical) regions.
    """
    # Normalize whitespace
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

def extract_regions_from_file(file_path: Path) -> List[RegionUsage]:
    """Extract protected regions from a file.

    Returns list of RegionUsage objects for each region found.
    """
    regions = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (IOError, UnicodeDecodeError):
        return regions

    # Pattern for protected region markers
    # Supports: # @protected:region_name, // @protected:region_name
    import re

    pattern = r"(?:#|//) @protected:(\w+)(.*?)(?:#|//) @end-protected:\1"
    matches = re.findall(pattern, content, re.DOTALL)

    for region_name, region_content in matches:
        content_hash = compute_content_hash(region_content)
        line_count = region_content.count("\n") + 1
        preview = region_content.strip()[:100]

        regions.append(
            RegionUsage(
                file_path=str(file_path),
                region_name=region_name,
                content_hash=content_hash,
                line_count=line_count,
                first_seen=datetime.now().isoformat(),
                content_preview=preview,
            )
        )

    return regions

def scan_codebase(root: Path, extensions: Optional[List[str]] = None) -> List[RegionUsage]:
    """Scan codebase for all protected regions.

    Args:
        root: Root directory to scan
        extensions: File extensions to check (default: .py, .ts, .js)

    Returns:
        List of all RegionUsage objects found
    """
    if extensions is None:
        extensions = [".py", ".ts", ".js", ".tsx", ".jsx"]

    all_regions = []

    for ext in extensions:
        for file_path in root.rglob(f"*{ext}"):
            # Skip common directories
            if any(
                part in file_path.parts
                for part in ["node_modules", ".venv", "venv", ".git", "__pycache__"]
            ):
                continue

            regions = extract_regions_from_file(file_path)
            all_regions.extend(regions)

    return all_regions

def find_graduation_candidates(regions: List[RegionUsage]) -> List[GraduationCandidate]:
    """Find regions that appear 3+ times and should graduate.

    Groups regions by content hash and identifies candidates.
    """
    # Group by content hash
    by_hash: Dict[str, List[RegionUsage]] = defaultdict(list)
    for region in regions:
        by_hash[region.content_hash].append(region)

    candidates = []

    for content_hash, usages in by_hash.items():
        if len(usages) >= GRADUATION_THRESHOLD:
            # This pattern should graduate
            first = usages[0]
            candidates.append(
                GraduationCandidate(
                    content_hash=content_hash,
                    region_name=first.region_name,
                    usage_count=len(usages),
                    files=[u.file_path for u in usages],
                    recommended_template_name=f"template_{first.region_name}",
                    line_count=first.line_count,
                    sample_content=first.content_preview,
                )
            )

    # Sort by usage count (most used first)
    candidates.sort(key=lambda c: c.usage_count, reverse=True)
    return candidates

def load_tracking_log(log_path: Path) -> Dict[str, Any]:
    """Load graduation tracking log."""
    if not log_path.exists():
        return {"tracked_graduations": [], "last_scan": None, "version": "1.0"}

    try:
        return yaml.safe_load(log_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"tracked_graduations": [], "last_scan": None, "version": "1.0"}

def save_tracking_log(log_path: Path, data: Dict[str, Any]) -> None:
    """Save graduation tracking log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

def print_report(candidates: List[GraduationCandidate], verbose: bool = False) -> None:
    """Print graduation report to stdout."""
    if not candidates:
        print("✅ No regions need graduation (all patterns used < 3 times)")
        return

    print(f"🎓 Found {len(candidates)} region(s) ready for graduation:\n")

    for i, c in enumerate(candidates, 1):
        print(f"{i}. {c.region_name} (used {c.usage_count} times)")
        print(f"   Hash: {c.content_hash}")
        print(f"   Recommended template: {c.recommended_template_name}")
        print(f"   Lines: ~{c.line_count}")

        if verbose:
            print(f"   Files:")
            for f in c.files:
                print(f"     - {f}")
            print(f"   Preview: {c.sample_content}...")
        print()

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Track protected region usage for template graduation",
        epilog="See PROTECTED_REGIONS_POLICY.md for graduation rules",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan codebase for protected regions",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate graduation report",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI check mode - exit 1 if graduation needed",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root directory to scan (default: current)",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("LogBook/graduation/tracking.yaml"),
        help="Path to tracking log",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if not any([args.scan, args.report, args.check]):
        parser.print_help()
        return 0

    # Scan for regions
    print(f"Scanning {args.root} for protected regions..." if not args.json else "", file=sys.stderr)
    regions = scan_codebase(args.root)
    print(f"Found {len(regions)} protected regions" if not args.json else "", file=sys.stderr)

    # Find graduation candidates
    candidates = find_graduation_candidates(regions)

    if args.json:
        output = {
            "scan_time": datetime.now().isoformat(),
            "total_regions": len(regions),
            "graduation_candidates": [asdict(c) for c in candidates],
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(candidates, args.verbose)

    # Update tracking log
    if args.scan or args.report:
        tracking_log = load_tracking_log(args.log_path)
        tracking_log["last_scan"] = datetime.now().isoformat()
        tracking_log["total_regions"] = len(regions)
        tracking_log["graduation_needed"] = len(candidates)
        save_tracking_log(args.log_path, tracking_log)
        print(f"\nTracking log updated: {args.log_path}")

    # CI check mode
    if args.check and candidates:
        print("\n❌ CI CHECK FAILED: Regions need graduation", file=sys.stderr)
        print(f"   {len(candidates)} pattern(s) used {GRADUATION_THRESHOLD}+ times", file=sys.stderr)
        print("   Run with --report for details", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
