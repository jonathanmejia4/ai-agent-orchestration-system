#!/usr/bin/env python3
"""
Issue Tracker - the system Issue Catalog Consumer

Reads and analyzes ISSUE_CATALOG.md to provide issue tracking and reporting.
Consumes the issue catalog as defined in SSOT wiring policy.

Usage:
    python3 tools/issue_tracker.py --lane G
    python3 tools/issue_tracker.py --status OPEN
    python3 tools/issue_tracker.py --severity HIGH
    python3 tools/issue_tracker.py --stats

Exit Codes:
    0 - Success
    1 - No matching issues found
    2 - Error (file not found, parse error, etc.)

Referenced in:
    - PLANNING/SSOT_WIRING_POLICY.md:114 (issue_catalog consumer)

Author: System
Created: 2026-01-09
"""

import argparse
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class Issue:
    """Issue data structure"""
    issue_id: str
    lane: str
    title: str
    severity: str
    severity_level: str
    type_tags: List[str]
    status: str

    @property
    def severity_number(self) -> int:
        """Extract numeric severity (e.g., '6/10 MEDIUM' -> 6)"""
        match = re.match(r'(\d+)/10', self.severity)
        return int(match.group(1)) if match else 0

@dataclass
class IssueStats:
    """Statistics about issues"""
    total: int = 0
    by_lane: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_status: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_severity: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_tag: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

class IssueTracker:
    """the system Issue Catalog tracker"""

    CATALOG_PATH = Path("ISSUE_CATALOG.md")

    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or self.CATALOG_PATH
        self.issues: List[Issue] = []

    def load_catalog(self) -> bool:
        """Load and parse issue catalog"""
        if not self.catalog_path.exists():
            print(f"Error: Issue catalog not found at {self.catalog_path}", file=sys.stderr)
            return False

        try:
            with open(self.catalog_path, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading catalog: {e}", file=sys.stderr)
            return False

        # Find "Open Issues by Lane" section
        match = re.search(r'## Open Issues by Lane.*?(?=##|\Z)', content, re.DOTALL)
        if not match:
            print("Warning: Could not find 'Open Issues by Lane' section", file=sys.stderr)
            return False

        section = match.group(0)

        # Parse lane sections
        current_lane = None
        for line in section.split('\n'):
            # Lane header: ### Lane X - Description
            lane_match = re.match(r'^### Lane ([A-Z]) -', line)
            if lane_match:
                current_lane = lane_match.group(1)
                continue

            # Issue row: | ID | Title | Severity | Type Tags | Status |
            issue_match = re.match(
                r'^\|\s*([A-Z]-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|',
                line
            )
            if issue_match and current_lane:
                issue_id = issue_match.group(1)
                title = issue_match.group(2).strip()
                severity = issue_match.group(3).strip()
                type_tags_str = issue_match.group(4).strip()
                status = issue_match.group(5).strip()

                # Extract severity level
                sev_level_match = re.search(r'(LOW|MEDIUM|HIGH|CRITICAL)', severity)
                severity_level = sev_level_match.group(1) if sev_level_match else "UNKNOWN"

                # Parse type tags (comma-separated)
                type_tags = [tag.strip() for tag in type_tags_str.split(',')]

                issue = Issue(
                    issue_id=issue_id,
                    lane=current_lane,
                    title=title,
                    severity=severity,
                    severity_level=severity_level,
                    type_tags=type_tags,
                    status=status
                )
                self.issues.append(issue)

        return True

    def filter_issues(
        self,
        lane: Optional[str] = None,
        status: Optional[str] = None,
        severity_min: Optional[int] = None,
        severity_level: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[Issue]:
        """Filter issues by criteria"""
        filtered = self.issues

        if lane:
            filtered = [i for i in filtered if i.lane == lane.upper()]

        if status:
            filtered = [i for i in filtered if i.status.upper() == status.upper()]

        if severity_min is not None:
            filtered = [i for i in filtered if i.severity_number >= severity_min]

        if severity_level:
            filtered = [i for i in filtered if i.severity_level == severity_level.upper()]

        if tag:
            filtered = [i for i in filtered if tag in i.type_tags]

        return filtered

    def get_stats(self) -> IssueStats:
        """Calculate statistics"""
        stats = IssueStats(total=len(self.issues))

        for issue in self.issues:
            stats.by_lane[issue.lane] += 1
            stats.by_status[issue.status] += 1
            stats.by_severity[issue.severity_level] += 1
            for tag in issue.type_tags:
                stats.by_tag[tag] += 1

        return stats

    def print_issues(self, issues: List[Issue], format: str = "table"):
        """Print issues in specified format"""
        if not issues:
            print("No issues found.")
            return

        if format == "table":
            print(f"\n{'ID':<10} {'Lane':<6} {'Severity':<15} {'Status':<8} {'Title'}")
            print("-" * 80)
            for issue in issues:
                print(f"{issue.issue_id:<10} {issue.lane:<6} {issue.severity:<15} "
                      f"{issue.status:<8} {issue.title[:40]}")

        elif format == "ids":
            for issue in issues:
                print(issue.issue_id)

        elif format == "detailed":
            for issue in issues:
                print(f"\n{issue.issue_id}: {issue.title}")
                print(f"  Lane: {issue.lane}")
                print(f"  Severity: {issue.severity}")
                print(f"  Status: {issue.status}")
                print(f"  Tags: {', '.join(issue.type_tags)}")

    def print_stats(self, stats: IssueStats):
        """Print statistics"""
        print(f"\n=== Issue Statistics ===")
        print(f"Total Issues: {stats.total}\n")

        print("By Lane:")
        for lane in sorted(stats.by_lane.keys()):
            print(f"  {lane}: {stats.by_lane[lane]}")

        print("\nBy Status:")
        for status in sorted(stats.by_status.keys()):
            print(f"  {status}: {stats.by_status[status]}")

        print("\nBy Severity:")
        for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            if sev in stats.by_severity:
                print(f"  {sev}: {stats.by_severity[sev]}")

        print("\nTop Tags:")
        sorted_tags = sorted(stats.by_tag.items(), key=lambda x: x[1], reverse=True)
        for tag, count in sorted_tags[:10]:
            print(f"  {tag}: {count}")

def main():
    parser = argparse.ArgumentParser(
        description='Track and analyze the system issues from issue catalog',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --lane G
    %(prog)s --status OPEN --severity-min 7
    %(prog)s --tag GhostRef --format ids
    %(prog)s --stats

Exit Codes:
    0 - Success
    1 - No matching issues
    2 - Error
        """
    )

    parser.add_argument('--catalog', type=Path,
                        help='Path to issue catalog (default: ISSUE_CATALOG.md)')
    parser.add_argument('--lane', '-l',
                        help='Filter by lane (e.g., G, B, H)')
    parser.add_argument('--status', '-s',
                        help='Filter by status (OPEN, RESOLVED)')
    parser.add_argument('--severity-min', type=int, metavar='N',
                        help='Minimum severity (1-10)')
    parser.add_argument('--severity-level',
                        choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
                        help='Filter by severity level')
    parser.add_argument('--tag', '-t',
                        help='Filter by type tag')
    parser.add_argument('--format', '-f',
                        choices=['table', 'ids', 'detailed'],
                        default='table',
                        help='Output format')
    parser.add_argument('--stats', action='store_true',
                        help='Show statistics only')
    parser.add_argument('--count', action='store_true',
                        help='Show count only')

    args = parser.parse_args()

    # Initialize tracker
    tracker = IssueTracker(catalog_path=args.catalog)

    # Load catalog
    if not tracker.load_catalog():
        sys.exit(2)

    # Stats mode
    if args.stats:
        stats = tracker.get_stats()
        tracker.print_stats(stats)
        sys.exit(0)

    # Filter issues
    issues = tracker.filter_issues(
        lane=args.lane,
        status=args.status,
        severity_min=args.severity_min,
        severity_level=args.severity_level,
        tag=args.tag
    )

    # Count mode
    if args.count:
        print(len(issues))
        sys.exit(0 if issues else 1)

    # Print results
    tracker.print_issues(issues, format=args.format)

    sys.exit(0 if issues else 1)

if __name__ == '__main__':
    main()
