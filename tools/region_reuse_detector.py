#!/usr/bin/env python3
"""
Region Reuse Detector
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Template Optimization

Detects opportunities for region reuse across templates.
Identifies duplicate or similar protected regions that could be consolidated.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass
class RegionContent:
    """Content of a protected region."""
    name: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    content_hash: str
    normalized_hash: str  # Hash of whitespace-normalized content
    size: int  # Number of lines

@dataclass
class RegionMatch:
    """A match between two similar regions."""
    region_a: RegionContent
    region_b: RegionContent
    similarity: float  # 0.0 to 1.0
    match_type: str  # "exact", "near", "structural"

@dataclass
class ReuseOpportunity:
    """An opportunity to reuse a region."""
    canonical_region: RegionContent
    duplicates: List[RegionContent]
    similarity_threshold: float
    estimated_savings: int  # Lines that could be deduplicated

@dataclass
class DetectionResult:
    """Result of region reuse detection."""
    files_scanned: int
    regions_found: int
    exact_duplicates: int
    near_duplicates: int
    opportunities: List[ReuseOpportunity] = field(default_factory=list)
    matches: List[RegionMatch] = field(default_factory=list)

class RegionReuseDetector:
    """Detects opportunities for region reuse."""

    REGION_PATTERNS = {
        'python': {
            'start': re.compile(r'#\s*REGION:(\w+):START'),
            'end': re.compile(r'#\s*REGION:(\w+):END'),
        },
        'javascript': {
            'start': re.compile(r'//\s*REGION:(\w+):START'),
            'end': re.compile(r'//\s*REGION:(\w+):END'),
        },
        'html': {
            'start': re.compile(r'<!--\s*REGION:(\w+):START\s*-->'),
            'end': re.compile(r'<!--\s*REGION:(\w+):END\s*-->'),
        },
    }

    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'javascript',
        '.jsx': 'javascript',
        '.tsx': 'javascript',
        '.html': 'html',
        '.htm': 'html',
        '.yaml': 'python',
        '.yml': 'python',
        '.sh': 'python',
    }

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        min_region_size: int = 3
    ):
        """
        Initialize detector.

        Args:
            similarity_threshold: Minimum similarity for near-duplicate detection
            min_region_size: Minimum lines for a region to be considered
        """
        self.similarity_threshold = similarity_threshold
        self.min_region_size = min_region_size

    def _normalize_content(self, content: str) -> str:
        """Normalize content for comparison."""
        lines = content.splitlines()
        # Remove empty lines and strip whitespace
        normalized = [line.strip() for line in lines if line.strip()]
        return '\n'.join(normalized)

    def _compute_hash(self, content: str) -> str:
        """Compute hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_similarity(self, a: str, b: str) -> float:
        """Compute similarity ratio between two strings."""
        return difflib.SequenceMatcher(None, a, b).ratio()

    def extract_regions(self, file_path: str) -> List[RegionContent]:
        """
        Extract all protected regions from a file.

        Args:
            file_path: Path to file

        Returns:
            List of RegionContent objects
        """
        regions = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return regions

        ext = Path(file_path).suffix.lower()
        pattern_type = self.EXTENSION_MAP.get(ext, 'python')
        patterns = self.REGION_PATTERNS.get(pattern_type, self.REGION_PATTERNS['python'])

        open_regions: Dict[str, int] = {}

        for line_num, line in enumerate(lines, 1):
            start_match = patterns['start'].search(line)
            if start_match:
                region_name = start_match.group(1)
                open_regions[region_name] = line_num

            end_match = patterns['end'].search(line)
            if end_match:
                region_name = end_match.group(1)
                if region_name in open_regions:
                    start_line = open_regions.pop(region_name)
                    content_lines = lines[start_line:line_num-1]
                    content = ''.join(content_lines)
                    normalized = self._normalize_content(content)

                    if len(content_lines) >= self.min_region_size:
                        regions.append(RegionContent(
                            name=region_name,
                            file_path=file_path,
                            start_line=start_line,
                            end_line=line_num,
                            content=content,
                            content_hash=self._compute_hash(content),
                            normalized_hash=self._compute_hash(normalized),
                            size=len(content_lines)
                        ))

        return regions

    def find_duplicates(
        self,
        regions: List[RegionContent]
    ) -> Tuple[List[RegionMatch], List[RegionMatch]]:
        """
        Find exact and near duplicates among regions.

        Args:
            regions: List of regions to compare

        Returns:
            Tuple of (exact_matches, near_matches)
        """
        exact_matches = []
        near_matches = []

        # Group by normalized hash for exact matches
        by_hash: Dict[str, List[RegionContent]] = defaultdict(list)
        for region in regions:
            by_hash[region.normalized_hash].append(region)

        # Find exact duplicates
        for hash_val, group in by_hash.items():
            if len(group) > 1:
                for i, region_a in enumerate(group):
                    for region_b in group[i+1:]:
                        exact_matches.append(RegionMatch(
                            region_a=region_a,
                            region_b=region_b,
                            similarity=1.0,
                            match_type="exact"
                        ))

        # Find near duplicates (compare all pairs not already exact matches)
        seen_pairs: Set[Tuple[str, str]] = set()
        for match in exact_matches:
            key = tuple(sorted([
                f"{match.region_a.file_path}:{match.region_a.name}",
                f"{match.region_b.file_path}:{match.region_b.name}"
            ]))
            seen_pairs.add(key)

        for i, region_a in enumerate(regions):
            for region_b in regions[i+1:]:
                key = tuple(sorted([
                    f"{region_a.file_path}:{region_a.name}",
                    f"{region_b.file_path}:{region_b.name}"
                ]))

                if key in seen_pairs:
                    continue

                # Skip if from same file and same name (shouldn't happen)
                if (region_a.file_path == region_b.file_path and
                    region_a.name == region_b.name):
                    continue

                # Compare normalized content
                norm_a = self._normalize_content(region_a.content)
                norm_b = self._normalize_content(region_b.content)

                similarity = self._compute_similarity(norm_a, norm_b)

                if similarity >= self.similarity_threshold:
                    near_matches.append(RegionMatch(
                        region_a=region_a,
                        region_b=region_b,
                        similarity=similarity,
                        match_type="near"
                    ))

        return exact_matches, near_matches

    def identify_opportunities(
        self,
        exact_matches: List[RegionMatch],
        near_matches: List[RegionMatch]
    ) -> List[ReuseOpportunity]:
        """
        Identify reuse opportunities from matches.

        Args:
            exact_matches: List of exact duplicate matches
            near_matches: List of near-duplicate matches

        Returns:
            List of reuse opportunities
        """
        opportunities = []

        # Group exact matches by canonical region (first occurrence)
        exact_groups: Dict[str, List[RegionContent]] = defaultdict(list)

        for match in exact_matches:
            # Use the one from alphabetically first file as canonical
            canonical = min(match.region_a, match.region_b,
                          key=lambda r: (r.file_path, r.start_line))
            other = match.region_b if canonical == match.region_a else match.region_a

            key = f"{canonical.file_path}:{canonical.name}"
            if key not in exact_groups:
                exact_groups[key] = [canonical]
            if other not in exact_groups[key]:
                exact_groups[key].append(other)

        for key, group in exact_groups.items():
            if len(group) > 1:
                canonical = group[0]
                duplicates = group[1:]
                savings = sum(r.size for r in duplicates)

                opportunities.append(ReuseOpportunity(
                    canonical_region=canonical,
                    duplicates=duplicates,
                    similarity_threshold=1.0,
                    estimated_savings=savings
                ))

        # Group near matches
        near_groups: Dict[str, List[Tuple[RegionContent, float]]] = defaultdict(list)

        for match in near_matches:
            canonical = min(match.region_a, match.region_b,
                          key=lambda r: (r.file_path, r.start_line))
            other = match.region_b if canonical == match.region_a else match.region_a

            key = f"{canonical.file_path}:{canonical.name}"
            near_groups[key].append((other, match.similarity))

        for key, items in near_groups.items():
            if items:
                parts = key.split(':')
                file_path = ':'.join(parts[:-1])
                name = parts[-1]

                # Find canonical region
                canonical = None
                for opp in opportunities:
                    if (opp.canonical_region.file_path == file_path and
                        opp.canonical_region.name == name):
                        canonical = opp.canonical_region
                        break

                if canonical is None:
                    # Need to find or create canonical
                    continue

                # Add near-duplicates to existing opportunity or create new
                for region, similarity in items:
                    found = False
                    for opp in opportunities:
                        if opp.canonical_region == canonical:
                            if region not in opp.duplicates:
                                opp.duplicates.append(region)
                                opp.estimated_savings += region.size
                                opp.similarity_threshold = min(
                                    opp.similarity_threshold, similarity
                                )
                            found = True
                            break

        return opportunities

    def scan_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
        exclude_dirs: Optional[List[str]] = None,
        recursive: bool = True
    ) -> DetectionResult:
        """
        Scan a directory for region reuse opportunities.

        Args:
            directory: Directory to scan
            extensions: File extensions to check
            exclude_dirs: Directories to exclude
            recursive: Whether to scan recursively

        Returns:
            DetectionResult
        """
        if extensions is None:
            extensions = list(self.EXTENSION_MAP.keys())
        if exclude_dirs is None:
            exclude_dirs = ['node_modules', '.git', '__pycache__', 'venv']

        all_regions = []
        files_scanned = 0

        path = Path(directory)
        pattern = '**/*' if recursive else '*'

        for file_path in path.glob(pattern):
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            if file_path.is_file() and file_path.suffix.lower() in extensions:
                files_scanned += 1
                regions = self.extract_regions(str(file_path))
                all_regions.extend(regions)

        # Find duplicates
        exact_matches, near_matches = self.find_duplicates(all_regions)

        # Identify opportunities
        opportunities = self.identify_opportunities(exact_matches, near_matches)

        return DetectionResult(
            files_scanned=files_scanned,
            regions_found=len(all_regions),
            exact_duplicates=len(exact_matches),
            near_duplicates=len(near_matches),
            opportunities=opportunities,
            matches=exact_matches + near_matches
        )

    def generate_report(self, result: DetectionResult) -> str:
        """Generate a markdown report."""
        lines = [
            "# Region Reuse Detection Report",
            "",
            "## Summary",
            f"- Files scanned: {result.files_scanned}",
            f"- Regions found: {result.regions_found}",
            f"- Exact duplicates: {result.exact_duplicates}",
            f"- Near duplicates: {result.near_duplicates}",
            f"- Reuse opportunities: {len(result.opportunities)}",
            ""
        ]

        if result.opportunities:
            total_savings = sum(o.estimated_savings for o in result.opportunities)
            lines.append(f"**Estimated line savings: {total_savings}**")
            lines.append("")
            lines.append("## Reuse Opportunities")
            lines.append("")

            for i, opp in enumerate(result.opportunities, 1):
                lines.append(f"### Opportunity {i}: {opp.canonical_region.name}")
                lines.append("")
                lines.append(f"**Canonical:** `{opp.canonical_region.file_path}` "
                           f"(lines {opp.canonical_region.start_line}-{opp.canonical_region.end_line})")
                lines.append("")
                lines.append(f"**Duplicates ({len(opp.duplicates)}):**")
                for dup in opp.duplicates:
                    lines.append(f"- `{dup.file_path}` (lines {dup.start_line}-{dup.end_line})")
                lines.append("")
                lines.append(f"**Similarity threshold:** {opp.similarity_threshold:.1%}")
                lines.append(f"**Estimated savings:** {opp.estimated_savings} lines")
                lines.append("")

        return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect region reuse opportunities"
    )
    parser.add_argument("path", help="Directory to scan")
    parser.add_argument("-t", "--threshold", type=float, default=0.8,
                        help="Similarity threshold (0.0-1.0)")
    parser.add_argument("-m", "--min-size", type=int, default=3,
                        help="Minimum region size in lines")
    parser.add_argument("-e", "--extensions", nargs="+",
                        help="File extensions to scan")
    parser.add_argument("--exclude", nargs="+",
                        help="Directories to exclude")
    parser.add_argument("--no-recursive", action="store_true",
                        help="Don't scan recursively")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("--report", help="Write report to file")

    args = parser.parse_args()

    detector = RegionReuseDetector(
        similarity_threshold=args.threshold,
        min_region_size=args.min_size
    )

    result = detector.scan_directory(
        args.path,
        extensions=args.extensions,
        exclude_dirs=args.exclude,
        recursive=not args.no_recursive
    )

    if args.json:
        output = {
            "files_scanned": result.files_scanned,
            "regions_found": result.regions_found,
            "exact_duplicates": result.exact_duplicates,
            "near_duplicates": result.near_duplicates,
            "opportunities": [
                {
                    "canonical": {
                        "name": o.canonical_region.name,
                        "file": o.canonical_region.file_path,
                        "lines": o.canonical_region.size
                    },
                    "duplicates": len(o.duplicates),
                    "similarity": o.similarity_threshold,
                    "savings": o.estimated_savings
                }
                for o in result.opportunities
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Files scanned: {result.files_scanned}")
        print(f"Regions found: {result.regions_found}")
        print(f"Exact duplicates: {result.exact_duplicates}")
        print(f"Near duplicates: {result.near_duplicates}")
        print(f"Reuse opportunities: {len(result.opportunities)}")

        if result.opportunities:
            total_savings = sum(o.estimated_savings for o in result.opportunities)
            print(f"\nEstimated savings: {total_savings} lines")

    if args.report:
        report = detector.generate_report(result)
        with open(args.report, 'w') as f:
            f.write(report)
        print(f"\nReport written to: {args.report}")

    sys.exit(0 if result.exact_duplicates == 0 else 1)

if __name__ == "__main__":
    main()
