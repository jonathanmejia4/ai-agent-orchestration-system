#!/usr/bin/env python3
"""
region_extractor.py - Protected Region Extractor

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Regeneration Support Tool

Purpose:
    Extracts protected regions from generated files before regeneration.
    Enables preservation of developer customizations during template updates.

Usage:
    python3 region_extractor.py --file src/api.ts --output regions.json
    python3 region_extractor.py --dir src/ --output all_regions.json
    python3 region_extractor.py --file src/api.ts --format text
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

@dataclass
class ProtectedRegion:
    """Represents an extracted protected region."""
    name: str
    content: str
    start_line: int
    end_line: int
    hash: str
    comment_style: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hash": self.hash,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "comment_style": self.comment_style
        }

@dataclass
class ExtractionResult:
    """Result of region extraction."""
    file: str
    regions: List[ProtectedRegion] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "region_count": len(self.regions),
            "regions": [r.to_dict() for r in self.regions],
            "errors": self.errors,
            "warnings": self.warnings
        }

class RegionExtractor:
    """Extracts protected regions from source files."""

    # Marker patterns for different comment styles
    MARKER_PATTERNS = {
        "//": {
            "begin": r'^(\s*)//\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:hash=([a-f0-9]+))?\s*$',
            "end": r'^(\s*)//\s*@saf:region\s+end\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*$'
        },
        "#": {
            "begin": r'^(\s*)#\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:hash=([a-f0-9]+))?\s*$',
            "end": r'^(\s*)#\s*@saf:region\s+end\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*$'
        },
        "/* */": {
            "begin": r'^(\s*)/\*\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:hash=([a-f0-9]+))?\s*\*/\s*$',
            "end": r'^(\s*)/\*\s*@saf:region\s+end\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*\*/\s*$'
        },
        "<!-- -->": {
            "begin": r'^(\s*)<!--\s*@saf:region\s+begin\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:hash=([a-f0-9]+))?\s*-->\s*$',
            "end": r'^(\s*)<!--\s*@saf:region\s+end\s+name=([a-zA-Z_][a-zA-Z0-9_]*)\s*-->\s*$'
        }
    }

    def __init__(self):
        self.compiled_patterns = {}
        for style, patterns in self.MARKER_PATTERNS.items():
            self.compiled_patterns[style] = {
                "begin": re.compile(patterns["begin"]),
                "end": re.compile(patterns["end"])
            }

    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _find_marker(self, line: str, marker_type: str) -> Optional[Tuple[str, str, Optional[str]]]:
        """
        Find a marker in a line.

        Returns: (comment_style, region_name, hash) or None
        """
        for style, patterns in self.compiled_patterns.items():
            match = patterns[marker_type].match(line)
            if match:
                groups = match.groups()
                if marker_type == "begin":
                    return (style, groups[1], groups[2] if len(groups) > 2 else None)
                else:
                    return (style, groups[1], None)
        return None

    def extract_regions(self, file_path: Path) -> ExtractionResult:
        """Extract all protected regions from a file."""
        result = ExtractionResult(file=str(file_path))

        try:
            content = file_path.read_text()
            lines = content.split('\n')
        except Exception as e:
            result.errors.append(f"Failed to read file: {e}")
            return result

        # Track open regions (stack for potential nesting detection)
        open_regions: List[Tuple[str, str, int, Optional[str]]] = []  # (name, style, start_line, old_hash)

        for line_num, line in enumerate(lines, 1):
            # Check for begin marker
            begin_match = self._find_marker(line, "begin")
            if begin_match:
                style, name, old_hash = begin_match

                # Check for nested regions (not allowed)
                if open_regions:
                    result.warnings.append(
                        f"Line {line_num}: Nested region '{name}' inside '{open_regions[-1][0]}' - nesting not allowed"
                    )

                open_regions.append((name, style, line_num, old_hash))
                continue

            # Check for end marker
            end_match = self._find_marker(line, "end")
            if end_match:
                style, name, _ = end_match

                if not open_regions:
                    result.errors.append(
                        f"Line {line_num}: End marker for '{name}' without matching begin"
                    )
                    continue

                # Find matching open region
                matching_idx = None
                for i, (open_name, open_style, _, _) in enumerate(reversed(open_regions)):
                    if open_name == name:
                        matching_idx = len(open_regions) - 1 - i
                        break

                if matching_idx is None:
                    result.errors.append(
                        f"Line {line_num}: End marker for '{name}' doesn't match open region '{open_regions[-1][0]}'"
                    )
                    continue

                # Extract region
                open_name, open_style, start_line, old_hash = open_regions.pop(matching_idx)

                # Get content between markers
                region_lines = lines[start_line:line_num - 1]  # Exclude markers
                region_content = '\n'.join(region_lines)

                # Calculate hash
                content_hash = self._calculate_hash(region_content)

                result.regions.append(ProtectedRegion(
                    name=name,
                    content=region_content,
                    start_line=start_line + 1,  # Line after begin marker
                    end_line=line_num - 1,  # Line before end marker
                    hash=content_hash,
                    comment_style=open_style
                ))

        # Check for unclosed regions
        for name, style, start_line, _ in open_regions:
            result.errors.append(
                f"Line {start_line}: Region '{name}' was never closed"
            )

        return result

    def extract_from_directory(self, dir_path: Path, extensions: Optional[List[str]] = None) -> Dict[str, ExtractionResult]:
        """Extract regions from all files in a directory."""
        if extensions is None:
            extensions = [".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css"]

        results = {}

        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                # Skip common ignored directories
                if any(d in file_path.parts for d in [".git", "node_modules", "__pycache__"]):
                    continue

                result = self.extract_regions(file_path)
                if result.regions or result.errors:
                    results[str(file_path)] = result

        return results

def format_text_output(result: ExtractionResult) -> str:
    """Format extraction result as text."""
    lines = [f"File: {result.file}"]
    lines.append(f"Regions found: {len(result.regions)}")

    if result.errors:
        lines.append("\nErrors:")
        for error in result.errors:
            lines.append(f"  \u274c {error}")

    if result.warnings:
        lines.append("\nWarnings:")
        for warning in result.warnings:
            lines.append(f"  \u26a0\ufe0f {warning}")

    if result.regions:
        lines.append("\nExtracted Regions:")
        for region in result.regions:
            lines.append(f"\n  [{region.name}]")
            lines.append(f"    Lines: {region.start_line}-{region.end_line}")
            lines.append(f"    Hash: {region.hash}")
            lines.append(f"    Style: {region.comment_style}")
            # Show first 3 lines of content
            content_lines = region.content.split('\n')[:3]
            for cl in content_lines:
                lines.append(f"    | {cl[:60]}{'...' if len(cl) > 60 else ''}")
            if len(region.content.split('\n')) > 3:
                lines.append(f"    | ... ({len(region.content.split(chr(10)))} lines total)")

    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Extract protected regions from source files"
    )
    parser.add_argument(
        "--file", "-f",
        help="Single file to extract from"
    )
    parser.add_argument(
        "--dir", "-d",
        help="Directory to extract from (recursive)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for extracted regions (JSON)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format"
    )

    args = parser.parse_args()

    if not args.file and not args.dir:
        print("Error: Must specify --file or --dir", file=sys.stderr)
        return 1

    extractor = RegionExtractor()

    if args.file:
        result = extractor.extract_regions(Path(args.file))

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"Saved regions to {args.output}")
        elif args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_text_output(result))

        return 1 if result.errors else 0

    elif args.dir:
        results = extractor.extract_from_directory(Path(args.dir))

        combined = {
            "directory": args.dir,
            "files_with_regions": len(results),
            "total_regions": sum(len(r.regions) for r in results.values()),
            "files": {path: r.to_dict() for path, r in results.items()}
        }

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(combined, f, indent=2)
            print(f"Saved {combined['total_regions']} regions from {combined['files_with_regions']} files to {args.output}")
        elif args.format == "json":
            print(json.dumps(combined, indent=2))
        else:
            print(f"Directory: {args.dir}")
            print(f"Files with regions: {len(results)}")
            print(f"Total regions: {combined['total_regions']}")
            for path, result in results.items():
                print(f"\n{format_text_output(result)}")

        has_errors = any(r.errors for r in results.values())
        return 1 if has_errors else 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
