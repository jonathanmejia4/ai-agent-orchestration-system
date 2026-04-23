#!/usr/bin/env python3
"""
region_reinserter.py - Protected Region Reinserter

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Regeneration Support Tool

Purpose:
    Reinserts protected regions into regenerated files.
    Preserves developer customizations after template regeneration.

Usage:
    python3 region_reinserter.py --file src/api.ts --regions regions.json
    python3 region_reinserter.py --file src/api.ts --regions regions.json --output src/api.ts.new
    python3 region_reinserter.py --dir src/ --regions all_regions.json
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
class ProtectedRegion:
    """Represents a protected region to reinsert."""
    name: str
    content: str
    hash: str
    comment_style: str

    @classmethod
    def from_dict(cls, data: dict) -> "ProtectedRegion":
        return cls(
            name=data["name"],
            content=data["content"],
            hash=data["hash"],
            comment_style=data.get("comment_style", "//")
        )

@dataclass
class ReinsertionResult:
    """Result of region reinsertion."""
    file: str
    regions_reinserted: int
    regions_not_found: List[str]
    errors: List[str]
    warnings: List[str]
    success: bool

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "success": self.success,
            "regions_reinserted": self.regions_reinserted,
            "regions_not_found": self.regions_not_found,
            "errors": self.errors,
            "warnings": self.warnings
        }

class RegionReinserter:
    """Reinserts protected regions into regenerated files."""

    # Marker patterns for different comment styles
    MARKER_TEMPLATES = {
        "//": {
            "begin": "// @saf:region begin name={name} hash={hash}",
            "end": "// @saf:region end name={name}",
            "pattern_begin": r'^(\s*)//\s*@saf:region\s+begin\s+name={name}\s*(?:hash=[a-f0-9]+)?\s*$',
            "pattern_end": r'^(\s*)//\s*@saf:region\s+end\s+name={name}\s*$'
        },
        "#": {
            "begin": "# @saf:region begin name={name} hash={hash}",
            "end": "# @saf:region end name={name}",
            "pattern_begin": r'^(\s*)#\s*@saf:region\s+begin\s+name={name}\s*(?:hash=[a-f0-9]+)?\s*$',
            "pattern_end": r'^(\s*)#\s*@saf:region\s+end\s+name={name}\s*$'
        },
        "/* */": {
            "begin": "/* @saf:region begin name={name} hash={hash} */",
            "end": "/* @saf:region end name={name} */",
            "pattern_begin": r'^(\s*)/\*\s*@saf:region\s+begin\s+name={name}\s*(?:hash=[a-f0-9]+)?\s*\*/\s*$',
            "pattern_end": r'^(\s*)/\*\s*@saf:region\s+end\s+name={name}\s*\*/\s*$'
        },
        "<!-- -->": {
            "begin": "<!-- @saf:region begin name={name} hash={hash} -->",
            "end": "<!-- @saf:region end name={name} -->",
            "pattern_begin": r'^(\s*)<!--\s*@saf:region\s+begin\s+name={name}\s*(?:hash=[a-f0-9]+)?\s*-->\s*$',
            "pattern_end": r'^(\s*)<!--\s*@saf:region\s+end\s+name={name}\s*-->\s*$'
        }
    }

    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _find_region_markers(
        self,
        lines: List[str],
        region_name: str,
        comment_style: str
    ) -> Optional[Tuple[int, int, str]]:
        """
        Find begin and end markers for a region.

        Returns: (begin_line_idx, end_line_idx, indent) or None
        """
        templates = self.MARKER_TEMPLATES.get(comment_style, self.MARKER_TEMPLATES["//"])

        begin_pattern = re.compile(templates["pattern_begin"].format(name=region_name))
        end_pattern = re.compile(templates["pattern_end"].format(name=region_name))

        begin_idx = None
        begin_indent = ""

        for i, line in enumerate(lines):
            if begin_idx is None:
                match = begin_pattern.match(line)
                if match:
                    begin_idx = i
                    begin_indent = match.group(1) if match.groups() else ""
            else:
                if end_pattern.match(line):
                    return (begin_idx, i, begin_indent)

        return None

    def reinsert_region(
        self,
        lines: List[str],
        region: ProtectedRegion
    ) -> Tuple[List[str], bool, Optional[str]]:
        """
        Reinsert a single region into file lines.

        Returns: (modified_lines, success, error_message)
        """
        markers = self._find_region_markers(lines, region.name, region.comment_style)

        if not markers:
            return lines, False, f"Region markers for '{region.name}' not found in file"

        begin_idx, end_idx, indent = markers

        # Build new lines
        new_lines = lines[:begin_idx + 1]  # Include begin marker

        # Add region content with proper indentation
        content_lines = region.content.split('\n')
        for content_line in content_lines:
            # Preserve relative indentation
            new_lines.append(content_line)

        # Add remaining lines from end marker
        new_lines.extend(lines[end_idx:])

        # Update the begin marker with new hash
        new_hash = self._calculate_hash(region.content)
        templates = self.MARKER_TEMPLATES.get(region.comment_style, self.MARKER_TEMPLATES["//"])
        new_begin_marker = indent + templates["begin"].format(name=region.name, hash=new_hash)
        new_lines[begin_idx] = new_begin_marker

        return new_lines, True, None

    def reinsert_regions(
        self,
        file_path: Path,
        regions: List[ProtectedRegion],
        output_path: Optional[Path] = None
    ) -> ReinsertionResult:
        """Reinsert all regions into a file."""
        result = ReinsertionResult(
            file=str(file_path),
            regions_reinserted=0,
            regions_not_found=[],
            errors=[],
            warnings=[],
            success=True
        )

        try:
            content = file_path.read_text()
            lines = content.split('\n')
        except Exception as e:
            result.errors.append(f"Failed to read file: {e}")
            result.success = False
            return result

        # Reinsert each region
        for region in regions:
            lines, success, error = self.reinsert_region(lines, region)

            if success:
                result.regions_reinserted += 1
            else:
                result.regions_not_found.append(region.name)
                if error:
                    result.warnings.append(error)

        # Write output
        output = output_path or file_path
        try:
            output.write_text('\n'.join(lines))
        except Exception as e:
            result.errors.append(f"Failed to write file: {e}")
            result.success = False

        if result.regions_not_found:
            result.warnings.append(
                f"Some regions not found in regenerated file: {result.regions_not_found}"
            )

        return result

    def reinsert_from_json(
        self,
        file_path: Path,
        regions_data: dict,
        output_path: Optional[Path] = None
    ) -> ReinsertionResult:
        """Reinsert regions from JSON data."""
        # Handle single file format
        if "regions" in regions_data:
            regions = [ProtectedRegion.from_dict(r) for r in regions_data["regions"]]
        # Handle directory format
        elif "files" in regions_data:
            file_key = str(file_path)
            if file_key not in regions_data["files"]:
                return ReinsertionResult(
                    file=str(file_path),
                    regions_reinserted=0,
                    regions_not_found=[],
                    errors=[f"No regions found for {file_path} in JSON"],
                    warnings=[],
                    success=False
                )
            regions = [
                ProtectedRegion.from_dict(r)
                for r in regions_data["files"][file_key]["regions"]
            ]
        else:
            return ReinsertionResult(
                file=str(file_path),
                regions_reinserted=0,
                regions_not_found=[],
                errors=["Invalid regions JSON format"],
                warnings=[],
                success=False
            )

        return self.reinsert_regions(file_path, regions, output_path)

def main():
    parser = argparse.ArgumentParser(
        description="Reinsert protected regions into regenerated files"
    )
    parser.add_argument(
        "--file", "-f",
        help="File to reinsert regions into"
    )
    parser.add_argument(
        "--dir", "-d",
        help="Directory to process (recursive)"
    )
    parser.add_argument(
        "--regions", "-r",
        required=True,
        help="JSON file containing extracted regions"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: modify in place)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    if not args.file and not args.dir:
        print("Error: Must specify --file or --dir", file=sys.stderr)
        return 1

    # Load regions
    try:
        with open(args.regions, 'r') as f:
            regions_data = json.load(f)
    except Exception as e:
        print(f"Error loading regions file: {e}", file=sys.stderr)
        return 1

    reinserter = RegionReinserter()

    if args.file:
        file_path = Path(args.file)
        output_path = Path(args.output) if args.output else None

        if args.dry_run:
            print(f"Would reinsert regions into {file_path}")
            return 0

        result = reinserter.reinsert_from_json(file_path, regions_data, output_path)

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            if result.success:
                print(f"\u2705 Reinserted {result.regions_reinserted} regions into {result.file}")
                if result.warnings:
                    for w in result.warnings:
                        print(f"  \u26a0\ufe0f {w}")
            else:
                print(f"\u274c Failed to reinsert regions into {result.file}")
                for e in result.errors:
                    print(f"  {e}")

        return 0 if result.success else 1

    elif args.dir:
        if "files" not in regions_data:
            print("Error: Regions JSON must contain 'files' for directory mode", file=sys.stderr)
            return 1

        all_results = []
        for file_key in regions_data["files"]:
            file_path = Path(file_key)
            if not file_path.exists():
                print(f"Warning: File not found: {file_key}", file=sys.stderr)
                continue

            if args.dry_run:
                region_count = len(regions_data["files"][file_key]["regions"])
                print(f"Would reinsert {region_count} regions into {file_key}")
                continue

            result = reinserter.reinsert_from_json(file_path, regions_data)
            all_results.append(result)

        if args.dry_run:
            return 0

        if args.format == "json":
            print(json.dumps([r.to_dict() for r in all_results], indent=2))
        else:
            success_count = sum(1 for r in all_results if r.success)
            total_regions = sum(r.regions_reinserted for r in all_results)
            print(f"Processed {len(all_results)} files")
            print(f"Successfully updated: {success_count}")
            print(f"Total regions reinserted: {total_regions}")

        return 0 if all(r.success for r in all_results) else 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
