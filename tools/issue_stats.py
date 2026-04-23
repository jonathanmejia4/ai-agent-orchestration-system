#!/usr/bin/env python3
"""
the system Issue Statistics Tool

Counts issues per lane, tracks resolved/unresolved status, and auto-updates
the catalog header with current statistics.

Usage:
    python3 tools/issue_stats.py              # Show stats
    python3 tools/issue_stats.py --update     # Update catalog header
    python3 tools/issue_stats.py --watch      # Watch for changes and auto-update
    python3 tools/issue_stats.py --json       # Output as JSON
"""

import os
import re
import sys
import json
import glob
import time
import argparse
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
CATALOG_PATH = "ISSUE_CATALOG.md"
STATS_FILE = "ISSUE_STATS.md"

# Lane display names
LANE_NAMES = {
    'A': 'Category A (Missing Files/Artifacts)',
    'D': 'Lane D (Marketing Infrastructure)',
    'G': 'Lane G (Ghost References)',
    'H': 'Lane H (Stub Implementations)',
    'I': 'Lane I (Integration Issues)',
    'J': 'Lane J (Enforcement Gaps)',
    'K': 'Lane K (LogBook Issues)',
    'L': 'Lane L (LogBook Path Issues)',
    'M': 'Lane M (Schema Issues)',
    'N': 'Lane N (Template Issues)',
    'O': 'Lane O (Spec Conflicts)',
    'P': 'Lane P (Policy Issues)',
    'Q': 'Lane Q (Planner Issues)',
    'R': 'Lane R (Recovery Issues)',
    'S': 'Lane S (Critic Drift)',
    'T': 'Lane T (Test Issues)',
    'U': 'Lane U (Utility Issues)',
    'V': 'Lane V (Validation Issues)',
    'W': 'Lane W (Workflow Issues)',
    'X': 'Lane X (Documentation Issues)',
    'Y': 'Lane Y (Tooling Issues)',
    'Z': 'Lane Z (Edge Cases)',
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LaneStats:
    """Statistics for a single lane."""
    lane: str
    name: str
    total: int
    resolved: int
    open: int
    high_severity: int
    medium_severity: int
    low_severity: int

    @property
    def resolution_rate(self) -> float:
        return (self.resolved / self.total * 100) if self.total > 0 else 0.0

@dataclass
class CatalogStats:
    """Overall catalog statistics."""
    total_issues: int
    total_resolved: int
    total_open: int
    total_high: int
    total_medium: int
    total_low: int
    lanes: Dict[str, LaneStats]
    last_updated: str

    @property
    def resolution_rate(self) -> float:
        return (self.total_resolved / self.total_issues * 100) if self.total_issues > 0 else 0.0

# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def parse_issue_file(filepath: str) -> Tuple[str, str, str]:
    """
    Parse an issue file and extract status and severity.

    Returns: (status, severity, lane)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
        return ('UNKNOWN', 'UNKNOWN', 'UNKNOWN')

    # Extract status
    status_match = re.search(r'Status:\s*(RESOLVED|OPEN|CLOSED)', content, re.IGNORECASE)
    status = status_match.group(1).upper() if status_match else 'OPEN'

    # Extract severity
    severity = 'MEDIUM'  # Default
    sev_match = re.search(r'Severity:\s*(\d+)/10\s*(HIGH|MEDIUM|LOW|CRITICAL)', content, re.IGNORECASE)
    if sev_match:
        level = sev_match.group(2).upper()
        if level in ('HIGH', 'CRITICAL'):
            severity = 'HIGH'
        elif level == 'LOW':
            severity = 'LOW'
        else:
            severity = 'MEDIUM'

    # Extract lane from path
    parts = filepath.split(os.sep)
    lane = 'A'
    for part in parts:
        if len(part) == 1 and part.isalpha():
            lane = part.upper()
            break

    return (status, severity, lane)

def collect_stats(issues_dir: str) -> CatalogStats:
    """
    Collect statistics from all issue files.
    """
    lanes: Dict[str, LaneStats] = {}

    # Initialize all lanes
    for lane in LANE_NAMES.keys():
        lanes[lane] = LaneStats(
            lane=lane,
            name=LANE_NAMES.get(lane, f'Lane {lane}'),
            total=0,
            resolved=0,
            open=0,
            high_severity=0,
            medium_severity=0,
            low_severity=0
        )

    # Scan all issue files
    for lane_dir in glob.glob(os.path.join(issues_dir, '*')):
        if not os.path.isdir(lane_dir):
            continue

        lane = os.path.basename(lane_dir).upper()
        if lane not in lanes:
            lanes[lane] = LaneStats(
                lane=lane,
                name=f'Lane {lane}',
                total=0,
                resolved=0,
                open=0,
                high_severity=0,
                medium_severity=0,
                low_severity=0
            )

        for filepath in glob.glob(os.path.join(lane_dir, '*.md')):
            if 'TEMPLATE' in filepath.upper():
                continue

            status, severity, _ = parse_issue_file(filepath)

            lanes[lane].total += 1

            if status == 'RESOLVED':
                lanes[lane].resolved += 1
            else:
                lanes[lane].open += 1

            if severity == 'HIGH':
                lanes[lane].high_severity += 1
            elif severity == 'LOW':
                lanes[lane].low_severity += 1
            else:
                lanes[lane].medium_severity += 1

    # Calculate totals
    total_issues = sum(l.total for l in lanes.values())
    total_resolved = sum(l.resolved for l in lanes.values())
    total_open = sum(l.open for l in lanes.values())
    total_high = sum(l.high_severity for l in lanes.values())
    total_medium = sum(l.medium_severity for l in lanes.values())
    total_low = sum(l.low_severity for l in lanes.values())

    return CatalogStats(
        total_issues=total_issues,
        total_resolved=total_resolved,
        total_open=total_open,
        total_high=total_high,
        total_medium=total_medium,
        total_low=total_low,
        lanes={k: v for k, v in lanes.items() if v.total > 0},
        last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

# =============================================================================
# OUTPUT FUNCTIONS
# =============================================================================

def format_stats_table(stats: CatalogStats) -> str:
    """Format statistics as a markdown table."""
    lines = []

    # Header
    lines.append("# the system Issue Catalog Statistics")
    lines.append("")
    lines.append(f"> **Last Updated:** {stats.last_updated}")
    lines.append(">")
    lines.append(f"> **Auto-generated by:** `python3 tools/issue_stats.py --update`")
    lines.append("")

    # Overall summary
    resolution_pct = stats.resolution_rate
    progress_bar = generate_progress_bar(resolution_pct)

    lines.append("## Overall Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| **Total Issues** | {stats.total_issues} |")
    lines.append(f"| Resolved | {stats.total_resolved} ({resolution_pct:.1f}%) |")
    lines.append(f"| Open | {stats.total_open} |")
    lines.append(f"| HIGH Severity | {stats.total_high} |")
    lines.append(f"| MEDIUM Severity | {stats.total_medium} |")
    lines.append(f"| LOW Severity | {stats.total_low} |")
    lines.append("")
    lines.append(f"**Resolution Progress:** {progress_bar} {resolution_pct:.1f}%")
    lines.append("")

    # Per-lane breakdown
    lines.append("## Issues by Lane")
    lines.append("")
    lines.append("| Lane | Total | Resolved | Open | Resolution % | HIGH | MED | LOW |")
    lines.append("|------|-------|----------|------|--------------|------|-----|-----|")

    # Sort lanes: A first, then alphabetically
    sorted_lanes = sorted(stats.lanes.keys(), key=lambda x: ('A' if x == 'A' else x))

    for lane in sorted_lanes:
        lane_stats = stats.lanes[lane]
        pct = lane_stats.resolution_rate
        status_icon = "✅" if pct == 100 else ("🟡" if pct >= 50 else "🔴")

        lines.append(
            f"| **{lane}** | {lane_stats.total} | {lane_stats.resolved} | "
            f"{lane_stats.open} | {status_icon} {pct:.0f}% | "
            f"{lane_stats.high_severity} | {lane_stats.medium_severity} | {lane_stats.low_severity} |"
        )

    lines.append("")

    # Lane descriptions
    lines.append("## Lane Descriptions")
    lines.append("")
    for lane in sorted_lanes:
        lane_stats = stats.lanes[lane]
        lines.append(f"- **{lane}**: {lane_stats.name} ({lane_stats.total} issues)")

    lines.append("")
    lines.append("---")
    lines.append("")

    return '\n'.join(lines)

def generate_progress_bar(percentage: float, width: int = 20) -> str:
    """Generate a text-based progress bar."""
    filled = int(width * percentage / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"

def format_compact_stats(stats: CatalogStats) -> str:
    """Format statistics as compact text for terminal display."""
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("Issue Catalog Statistics")
    lines.append("=" * 70)
    lines.append(f"Last Updated: {stats.last_updated}")
    lines.append("")

    # Overall
    pct = stats.resolution_rate
    bar = generate_progress_bar(pct, 30)
    lines.append(f"TOTAL: {stats.total_issues} issues | "
                 f"✅ {stats.total_resolved} resolved | "
                 f"❌ {stats.total_open} open")
    lines.append(f"Progress: {bar} {pct:.1f}%")
    lines.append("")

    # Severity breakdown
    lines.append(f"Severity: 🔴 HIGH: {stats.total_high} | "
                 f"🟡 MEDIUM: {stats.total_medium} | "
                 f"🟢 LOW: {stats.total_low}")
    lines.append("")

    # Per-lane
    lines.append("-" * 70)
    lines.append(f"{'Lane':<6} {'Total':>6} {'Resolved':>9} {'Open':>6} {'Progress':>12} {'HIGH':>5} {'MED':>5} {'LOW':>5}")
    lines.append("-" * 70)

    sorted_lanes = sorted(stats.lanes.keys(), key=lambda x: ('A' if x == 'A' else x))

    for lane in sorted_lanes:
        s = stats.lanes[lane]
        pct = s.resolution_rate
        icon = "✅" if pct == 100 else ("🟡" if pct >= 50 else "🔴")
        lines.append(
            f"{lane:<6} {s.total:>6} {s.resolved:>9} {s.open:>6} "
            f"{icon} {pct:>5.0f}% {s.high_severity:>6} {s.medium_severity:>5} {s.low_severity:>5}"
        )

    lines.append("-" * 70)
    lines.append("")

    return '\n'.join(lines)

def format_json_stats(stats: CatalogStats) -> str:
    """Format statistics as JSON."""
    data = {
        'total_issues': stats.total_issues,
        'total_resolved': stats.total_resolved,
        'total_open': stats.total_open,
        'resolution_rate': round(stats.resolution_rate, 2),
        'severity': {
            'high': stats.total_high,
            'medium': stats.total_medium,
            'low': stats.total_low
        },
        'last_updated': stats.last_updated,
        'lanes': {}
    }

    for lane, lane_stats in stats.lanes.items():
        data['lanes'][lane] = {
            'name': lane_stats.name,
            'total': lane_stats.total,
            'resolved': lane_stats.resolved,
            'open': lane_stats.open,
            'resolution_rate': round(lane_stats.resolution_rate, 2),
            'high': lane_stats.high_severity,
            'medium': lane_stats.medium_severity,
            'low': lane_stats.low_severity
        }

    return json.dumps(data, indent=2)

# =============================================================================
# UPDATE FUNCTIONS
# =============================================================================

def update_stats_file(stats: CatalogStats, filepath: str = STATS_FILE) -> bool:
    """Write statistics to a dedicated stats file."""
    try:
        content = format_stats_table(stats)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Updated {filepath}")
        return True
    except Exception as e:
        print(f"❌ Failed to update {filepath}: {e}", file=sys.stderr)
        return False

def update_catalog_header(stats: CatalogStats, catalog_path: str = CATALOG_PATH) -> bool:
    """Update the catalog file header with current statistics."""
    if not os.path.exists(catalog_path):
        print(f"❌ Catalog not found: {catalog_path}", file=sys.stderr)
        return False

    try:
        with open(catalog_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Generate stats block
        stats_block = generate_stats_block(stats)

        # Find and replace existing stats block, or insert after title
        stats_pattern = re.compile(
            r'<!-- STATS_START -->.*?<!-- STATS_END -->',
            re.DOTALL
        )

        if stats_pattern.search(content):
            # Replace existing block
            content = stats_pattern.sub(stats_block, content)
        else:
            # Insert after first heading
            first_heading = re.search(r'^#[^#].*$', content, re.MULTILINE)
            if first_heading:
                insert_pos = first_heading.end()
                content = content[:insert_pos] + '\n\n' + stats_block + '\n' + content[insert_pos:]
            else:
                content = stats_block + '\n\n' + content

        with open(catalog_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Updated catalog header in {catalog_path}")
        return True

    except Exception as e:
        print(f"❌ Failed to update catalog: {e}", file=sys.stderr)
        return False

def generate_stats_block(stats: CatalogStats) -> str:
    """Generate a stats block for embedding in the catalog."""
    pct = stats.resolution_rate
    bar = generate_progress_bar(pct, 20)

    lines = [
        "<!-- STATS_START -->",
        "## 📊 Issue Statistics",
        "",
        f"> **Last Updated:** {stats.last_updated}",
        "",
        f"| Total | Resolved | Open | Progress |",
        f"|-------|----------|------|----------|",
        f"| {stats.total_issues} | {stats.total_resolved} | {stats.total_open} | {bar} {pct:.1f}% |",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 HIGH | {stats.total_high} |",
        f"| 🟡 MEDIUM | {stats.total_medium} |",
        f"| 🟢 LOW | {stats.total_low} |",
        "",
        "<details>",
        "<summary>📁 Issues by Lane (click to expand)</summary>",
        "",
        "| Lane | Total | Resolved | Open | % |",
        "|------|-------|----------|------|---|",
    ]

    sorted_lanes = sorted(stats.lanes.keys(), key=lambda x: ('A' if x == 'A' else x))
    for lane in sorted_lanes:
        s = stats.lanes[lane]
        icon = "✅" if s.resolution_rate == 100 else ("🟡" if s.resolution_rate >= 50 else "🔴")
        lines.append(f"| {lane} | {s.total} | {s.resolved} | {s.open} | {icon} {s.resolution_rate:.0f}% |")

    lines.extend([
        "",
        "</details>",
        "",
        "<!-- STATS_END -->"
    ])

    return '\n'.join(lines)

# =============================================================================
# WATCH MODE
# =============================================================================

def watch_for_changes(issues_dir: str, interval: int = 5):
    """Watch for file changes and auto-update statistics."""
    print(f"👁️  Watching {issues_dir} for changes (Ctrl+C to stop)...")
    print(f"   Update interval: {interval} seconds")
    print()

    last_stats = None

    try:
        while True:
            stats = collect_stats(issues_dir)

            # Check if stats changed
            if last_stats is None or stats_changed(last_stats, stats):
                print(f"\n📊 Stats updated at {stats.last_updated}")
                print(format_compact_stats(stats))

                # Update files
                update_stats_file(stats)
                update_catalog_header(stats)

                last_stats = stats

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n👋 Watch mode stopped.")

def stats_changed(old: CatalogStats, new: CatalogStats) -> bool:
    """Check if statistics have changed."""
    if old.total_issues != new.total_issues:
        return True
    if old.total_resolved != new.total_resolved:
        return True
    if old.total_open != new.total_open:
        return True
    return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='the system Issue Catalog Statistics Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 tools/issue_stats.py              # Show stats in terminal
    python3 tools/issue_stats.py --update     # Update ISSUE_STATS.md and catalog
    python3 tools/issue_stats.py --watch      # Auto-update on changes
    python3 tools/issue_stats.py --json       # Output as JSON
        """
    )

    parser.add_argument('--update', '-u', action='store_true',
                        help='Update ISSUE_STATS.md and catalog header')
    parser.add_argument('--watch', '-w', action='store_true',
                        help='Watch for changes and auto-update')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output statistics as JSON')
    parser.add_argument('--interval', '-i', type=int, default=5,
                        help='Watch interval in seconds (default: 5)')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR,
                        help=f'Issues directory (default: {ISSUES_DIR})')

    args = parser.parse_args()

    # Verify issues directory exists
    if not os.path.isdir(args.issues_dir):
        print(f"❌ Issues directory not found: {args.issues_dir}", file=sys.stderr)
        sys.exit(1)

    # Watch mode
    if args.watch:
        watch_for_changes(args.issues_dir, args.interval)
        return

    # Collect stats
    stats = collect_stats(args.issues_dir)

    # Output format
    if args.json:
        print(format_json_stats(stats))
    else:
        print(format_compact_stats(stats))

    # Update files
    if args.update:
        update_stats_file(stats)
        update_catalog_header(stats)

if __name__ == '__main__':
    main()
