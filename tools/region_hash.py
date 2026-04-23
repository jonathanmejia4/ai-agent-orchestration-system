#!/usr/bin/env python3
"""
region_hash.py - Protected Region Hash Calculator

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Integrity Verification Tool

Purpose:
    Calculates hashes for protected region content.
    Detects changes to protected regions between versions.
    Supports three-way merge change detection.

Usage:
    python3 region_hash.py --file src/api.ts
    python3 region_hash.py --file src/api.ts --region custom_validation
    python3 region_hash.py compare --base base.json --local local.json --new new.json
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

@dataclass
class RegionHash:
    """Hash information for a protected region."""
    name: str
    hash: str
    line_count: int
    char_count: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hash": self.hash,
            "line_count": self.line_count,
            "char_count": self.char_count
        }

@dataclass
class RegionComparison:
    """Comparison result for a region across versions."""
    name: str
    base_hash: Optional[str]
    local_hash: Optional[str]
    new_hash: Optional[str]
    status: str  # "unchanged", "local_modified", "new_modified", "conflict", "added", "removed"
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "base_hash": self.base_hash,
            "local_hash": self.local_hash,
            "new_hash": self.new_hash,
            "status": self.status,
            "recommendation": self.recommendation
        }

class RegionHashCalculator:
    """Calculates and compares protected region hashes."""

    # Marker patterns
    MARKER_PATTERNS = [
        (r'//\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)', r'//\s*@saf:region\s+end\s+name='),
        (r'#\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)', r'#\s*@saf:region\s+end\s+name='),
        (r'/\*\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)', r'/\*\s*@saf:region\s+end\s+name='),
        (r'<!--\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)', r'<!--\s*@saf:region\s+end\s+name='),
    ]

    def calculate_hash(self, content: str, algorithm: str = "sha256") -> str:
        """Calculate hash of content."""
        # Normalize whitespace for consistent hashing
        normalized = content.strip()

        if algorithm == "sha256":
            return hashlib.sha256(normalized.encode()).hexdigest()[:16]
        elif algorithm == "md5":
            return hashlib.md5(normalized.encode()).hexdigest()[:16]
        else:
            return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def extract_region_content(self, file_content: str, region_name: str) -> Optional[str]:
        """Extract content of a specific region."""
        lines = file_content.split('\n')

        for begin_pattern, end_pattern_base in self.MARKER_PATTERNS:
            begin_regex = re.compile(begin_pattern)
            end_regex = re.compile(end_pattern_base + re.escape(region_name))

            in_region = False
            region_lines = []

            for line in lines:
                if not in_region:
                    match = begin_regex.search(line)
                    if match and match.group(1) == region_name:
                        in_region = True
                        continue
                else:
                    if end_regex.search(line):
                        return '\n'.join(region_lines)
                    region_lines.append(line)

        return None

    def get_all_region_hashes(self, file_path: Path) -> List[RegionHash]:
        """Get hashes for all regions in a file."""
        try:
            content = file_path.read_text()
        except Exception:
            return []

        regions = []
        lines = content.split('\n')

        for begin_pattern, end_pattern_base in self.MARKER_PATTERNS:
            begin_regex = re.compile(begin_pattern)

            current_region = None
            region_lines = []

            for line in lines:
                if current_region is None:
                    match = begin_regex.search(line)
                    if match:
                        current_region = match.group(1)
                        region_lines = []
                else:
                    end_regex = re.compile(end_pattern_base + re.escape(current_region))
                    if end_regex.search(line):
                        region_content = '\n'.join(region_lines)
                        regions.append(RegionHash(
                            name=current_region,
                            hash=self.calculate_hash(region_content),
                            line_count=len(region_lines),
                            char_count=len(region_content)
                        ))
                        current_region = None
                        region_lines = []
                    else:
                        region_lines.append(line)

        return regions

    def compare_versions(
        self,
        base_hashes: Dict[str, str],
        local_hashes: Dict[str, str],
        new_hashes: Dict[str, str]
    ) -> List[RegionComparison]:
        """
        Compare region hashes across three versions for three-way merge.

        Args:
            base_hashes: Original generated version hashes
            local_hashes: Developer-modified version hashes
            new_hashes: Newly regenerated version hashes

        Returns:
            List of comparison results with merge recommendations
        """
        all_names = set(base_hashes.keys()) | set(local_hashes.keys()) | set(new_hashes.keys())
        comparisons = []

        for name in all_names:
            base = base_hashes.get(name)
            local = local_hashes.get(name)
            new = new_hashes.get(name)

            if base is None and local is None:
                # Region only in new version
                status = "added"
                recommendation = "Accept new region from regeneration"
            elif base is None and new is None:
                # Region only in local version
                status = "local_only"
                recommendation = "Preserve local region (not from template)"
            elif local is None and new is None:
                # Region only in base (removed in both)
                status = "removed"
                recommendation = "Region removed, no action needed"
            elif base == local == new:
                # All three identical
                status = "unchanged"
                recommendation = "No changes needed"
            elif base == local and local != new:
                # Only new version changed
                status = "new_modified"
                recommendation = "Accept new version (local unchanged from base)"
            elif base == new and local != new:
                # Only local version changed
                status = "local_modified"
                recommendation = "Preserve local changes"
            elif local == new and base != local:
                # Local and new both changed identically
                status = "converged"
                recommendation = "Both versions match, no conflict"
            else:
                # All three different
                status = "conflict"
                recommendation = "MANUAL MERGE REQUIRED: All versions differ"

            comparisons.append(RegionComparison(
                name=name,
                base_hash=base,
                local_hash=local,
                new_hash=new,
                status=status,
                recommendation=recommendation
            ))

        return comparisons

def load_hashes_from_file(path: str) -> Dict[str, str]:
    """Load region hashes from JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)

    # Handle different formats
    if "regions" in data:
        return {r["name"]: r["hash"] for r in data["regions"]}
    elif isinstance(data, dict) and all(isinstance(v, str) for v in data.values()):
        return data
    else:
        raise ValueError(f"Unknown hash file format: {path}")

def main():
    parser = argparse.ArgumentParser(
        description="Calculate and compare protected region hashes"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Hash command
    hash_parser = subparsers.add_parser("hash", help="Calculate region hashes")
    hash_parser.add_argument("--file", "-f", required=True, help="File to hash")
    hash_parser.add_argument("--region", "-r", help="Specific region name")
    hash_parser.add_argument("--output", "-o", help="Output file")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare versions")
    compare_parser.add_argument("--base", "-b", required=True, help="Base version hashes")
    compare_parser.add_argument("--local", "-l", required=True, help="Local version hashes")
    compare_parser.add_argument("--new", "-n", required=True, help="New version hashes")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    calculator = RegionHashCalculator()

    if args.command == "hash" or not args.command:
        if not hasattr(args, 'file') or not args.file:
            # Default to hash command
            parser.print_help()
            return 1

        file_path = Path(args.file)

        if hasattr(args, 'region') and args.region:
            # Hash single region
            content = file_path.read_text()
            region_content = calculator.extract_region_content(content, args.region)

            if region_content is None:
                print(f"Region '{args.region}' not found in {file_path}", file=sys.stderr)
                return 1

            hash_val = calculator.calculate_hash(region_content)
            result = {
                "name": args.region,
                "hash": hash_val,
                "line_count": len(region_content.split('\n')),
                "char_count": len(region_content)
            }
        else:
            # Hash all regions
            regions = calculator.get_all_region_hashes(file_path)
            result = {
                "file": str(file_path),
                "region_count": len(regions),
                "regions": [r.to_dict() for r in regions]
            }

        if hasattr(args, 'output') and args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Saved hashes to {args.output}")
        elif args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            if "regions" in result:
                print(f"File: {result['file']}")
                print(f"Regions: {result['region_count']}")
                for r in result["regions"]:
                    print(f"  {r['name']}: {r['hash']} ({r['line_count']} lines)")
            else:
                print(f"Region: {result['name']}")
                print(f"Hash: {result['hash']}")
                print(f"Lines: {result['line_count']}")

        return 0

    elif args.command == "compare":
        base_hashes = load_hashes_from_file(args.base)
        local_hashes = load_hashes_from_file(args.local)
        new_hashes = load_hashes_from_file(args.new)

        comparisons = calculator.compare_versions(base_hashes, local_hashes, new_hashes)

        if args.format == "json":
            print(json.dumps([c.to_dict() for c in comparisons], indent=2))
        else:
            print("Region Comparison Results:")
            print("-" * 60)

            conflicts = []
            for c in comparisons:
                status_icon = {
                    "unchanged": "\u2705",
                    "local_modified": "\U0001f4dd",
                    "new_modified": "\U0001f504",
                    "conflict": "\u274c",
                    "added": "\u2795",
                    "removed": "\u2796",
                    "local_only": "\U0001f4be",
                    "converged": "\u2705"
                }.get(c.status, "\u2753")

                print(f"\n{status_icon} {c.name}: {c.status.upper()}")
                print(f"   Recommendation: {c.recommendation}")

                if c.status == "conflict":
                    conflicts.append(c.name)

            print("\n" + "-" * 60)
            if conflicts:
                print(f"\u26a0\ufe0f {len(conflicts)} conflicts require manual resolution:")
                for name in conflicts:
                    print(f"   - {name}")
                return 1
            else:
                print("\u2705 No conflicts detected")
                return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
