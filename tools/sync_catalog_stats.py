#!/usr/bin/env python3
"""
Catalog Statistics Synchronization Tool

Automatically scans all issue files and updates SAF_ISSUE_CATALOG.md
with accurate statistics from the actual file contents.

Usage:
    python3 tools/sync_catalog_stats.py           # Update catalog
    python3 tools/sync_catalog_stats.py --check   # Check only, don't update
    python3 tools/sync_catalog_stats.py --verbose # Show detailed output

Can be integrated into:
- Pre-commit hooks
- CI workflows
- Manual maintenance
"""

import os
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
CATALOG_PATH = "SAF_ISSUE_CATALOG.md"
ISSUES_DIR = "issues"
LANES = ['A', 'E', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']


def parse_issue_file(filepath: str) -> dict:
    """Parse an issue file and extract frontmatter + title."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {
        'issue_id': None,
        'lane': None,
        'title': None,
        'severity': None,
        'severity_level': None,
        'type_tags': [],
        'status': 'UNKNOWN',
    }

    # Parse YAML frontmatter
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            frontmatter = content[3:end]

            # Extract issue_id
            match = re.search(r'^issue_id:\s*["\']?([^"\']+)["\']?', frontmatter, re.MULTILINE)
            if match:
                result['issue_id'] = match.group(1).strip()

            # Extract lane
            match = re.search(r'^lane:\s*["\']?([^"\']+)["\']?', frontmatter, re.MULTILINE)
            if match:
                result['lane'] = match.group(1).strip()

            # Extract severity (numeric)
            match = re.search(r'^severity:\s*(\d+)', frontmatter, re.MULTILINE)
            if match:
                result['severity'] = int(match.group(1))

            # Extract severity_level
            match = re.search(r'^severity_level:\s*["\']?(HIGH|MEDIUM|LOW|CRITICAL|TRIVIAL)["\']?', frontmatter, re.MULTILINE)
            if match:
                result['severity_level'] = match.group(1)

            # Extract type_tags
            match = re.search(r'^type_tags:\s*\[([^\]]+)\]', frontmatter, re.MULTILINE)
            if match:
                tags = match.group(1)
                result['type_tags'] = [t.strip().strip('"\'') for t in tags.split(',')]

            # Extract status
            match = re.search(r'^status:\s*["\']?(OPEN|RESOLVED)["\']?', frontmatter, re.MULTILINE)
            if match:
                result['status'] = match.group(1)

    # Extract title from heading
    match = re.search(r'^#\s*\[LANE [A-Z]\]\s*Issue\s+[A-Z]-\d+:\s*(.+)$', content, re.MULTILINE)
    if match:
        result['title'] = match.group(1).strip()
    else:
        # Fallback to first heading
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            result['title'] = match.group(1).strip()

    return result


def get_file_status(filepath: str) -> str:
    """Extract status from an issue file (YAML frontmatter or markdown)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check YAML frontmatter first (most reliable)
    yaml_resolved = bool(re.search(r'^status:\s*["\']?RESOLVED["\']?', content, re.MULTILINE))
    yaml_open = bool(re.search(r'^status:\s*["\']?OPEN["\']?', content, re.MULTILINE))

    if yaml_resolved:
        return "RESOLVED"
    if yaml_open:
        return "OPEN"

    # Fallback to markdown status
    md_resolved = bool(re.search(r'-\s*Status:\s*RESOLVED', content, re.IGNORECASE))
    md_open = bool(re.search(r'-\s*Status:\s*OPEN', content, re.IGNORECASE))

    if md_resolved:
        return "RESOLVED"
    if md_open:
        return "OPEN"

    # Check for resolution indicators as last resort
    resolution_patterns = [
        r'\*Resolved:',
        r'Resolution applied',
        r'Issue resolved',
        r'\*\*Resolution Status:\*\*\s*RESOLVED',
    ]
    if any(re.search(p, content, re.IGNORECASE) for p in resolution_patterns):
        return "RESOLVED"

    return "UNKNOWN"


def scan_all_issues(verbose: bool = False) -> dict:
    """Scan all issue files and return statistics."""
    stats = {}

    for lane in LANES:
        lane_dir = os.path.join(ISSUES_DIR, lane)
        if not os.path.isdir(lane_dir):
            continue

        files = [f for f in os.listdir(lane_dir) if f.endswith('.md')]

        resolved = 0
        open_count = 0
        unknown = 0

        for f in files:
            filepath = os.path.join(lane_dir, f)
            status = get_file_status(filepath)

            if status == "RESOLVED":
                resolved += 1
            elif status == "OPEN":
                open_count += 1
            else:
                unknown += 1
                if verbose:
                    print(f"  WARNING: {filepath} has unknown status")

        stats[lane] = {
            'total': len(files),
            'resolved': resolved,
            'open': open_count,
            'unknown': unknown
        }

        if verbose:
            pct = round(100 * resolved / len(files)) if files else 0
            print(f"Lane {lane}: {len(files)} total, {resolved} resolved, {open_count} open ({pct}%)")

    return stats


def scan_open_issues(verbose: bool = False) -> dict:
    """Scan all issue files and return open issues grouped by lane."""
    open_issues = {lane: [] for lane in LANES}

    for lane in LANES:
        lane_dir = os.path.join(ISSUES_DIR, lane)
        if not os.path.isdir(lane_dir):
            continue

        files = [f for f in os.listdir(lane_dir) if f.endswith('.md')]

        for f in sorted(files):
            filepath = os.path.join(lane_dir, f)
            issue_data = parse_issue_file(filepath)

            if issue_data['status'] == 'OPEN':
                # Truncate title if too long
                title = issue_data['title'] or 'Untitled'
                if len(title) > 60:
                    title = title[:57] + '...'

                open_issues[lane].append({
                    'id': issue_data['issue_id'] or f.replace('.md', ''),
                    'title': title,
                    'severity': issue_data['severity'],
                    'severity_level': issue_data['severity_level'],
                    'type_tags': issue_data['type_tags'],
                })

        if verbose and open_issues[lane]:
            print(f"Lane {lane}: {len(open_issues[lane])} open issues")

    return open_issues


def generate_open_issues_section(open_issues: dict) -> str:
    """Generate the Open Issues section content for a specific lane."""
    lines = []

    for issue in open_issues:
        # Format severity
        sev = issue['severity']
        sev_level = issue['severity_level'] or 'MEDIUM'
        severity_str = f"{sev}/10 {sev_level}"

        # Format type tags
        tags_str = ', '.join(issue['type_tags'][:4])  # Max 4 tags

        lines.append(f"| {issue['id']} | {issue['title']} | {severity_str} | {tags_str} | OPEN |")

    return '\n'.join(lines)


def generate_progress_bar(percentage: float) -> str:
    """Generate a text-based progress bar."""
    filled = int(percentage / 5)  # 20 chars total
    empty = 20 - filled
    return f"[{'█' * filled}{'░' * empty}]"


def generate_lane_indicator(percentage: int) -> str:
    """Generate lane status indicator."""
    if percentage == 100:
        return "✅ 100%"
    elif percentage >= 80:
        return f"🟡 {percentage}%"
    else:
        return f"🔴 {percentage}%"


def update_catalog(stats: dict, verbose: bool = False) -> bool:
    """Update the catalog file with new statistics."""
    if not os.path.exists(CATALOG_PATH):
        print(f"ERROR: Catalog file not found: {CATALOG_PATH}")
        return False

    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Calculate totals
    total_files = sum(s['total'] for s in stats.values())
    total_resolved = sum(s['resolved'] for s in stats.values())
    total_open = sum(s['open'] for s in stats.values())
    progress_pct = round(100 * total_resolved / total_files, 1) if total_files else 0

    if verbose:
        print(f"\nTotals: {total_files} files, {total_resolved} resolved, {total_open} open ({progress_pct}%)")

    # Update timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = re.sub(
        r'>\s*\*\*Last Updated:\*\*\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
        f'> **Last Updated:** {timestamp}',
        content
    )

    # Update header stats table
    progress_bar = generate_progress_bar(progress_pct)
    new_header = f"| {total_files} | {total_resolved} | {total_open} | {progress_bar} {progress_pct}% |"
    content = re.sub(
        r'\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\[█*░*\]\s*[\d.]+%\s*\|',
        new_header,
        content
    )

    # Update lane table
    lane_table_lines = []
    lane_table_lines.append("| Lane | Total | Resolved | Open | % |")
    lane_table_lines.append("|------|-------|----------|------|---|")

    for lane in LANES:
        if lane not in stats:
            continue
        s = stats[lane]
        pct = round(100 * s['resolved'] / s['total']) if s['total'] else 0
        indicator = generate_lane_indicator(pct)
        lane_table_lines.append(f"| {lane} | {s['total']} | {s['resolved']} | {s['open']} | {indicator} |")

    new_lane_table = "\n".join(lane_table_lines)

    # Replace the lane table
    lane_table_pattern = r'\| Lane \| Total \| Resolved \| Open \| % \|[\s\S]*?\| Z \| \d+ \| \d+ \| \d+ \| [^\n]+ \|'
    content = re.sub(lane_table_pattern, new_lane_table, content)

    # Update Open Issues section
    if verbose:
        print("Scanning open issues for Open Issues section...")
    open_issues = scan_open_issues(verbose=verbose)

    # Update each lane's issues in the Open Issues section
    for lane in LANES:
        # Pattern to match: table header + existing rows + marker
        # <!-- LANE_X_ISSUES --> marks end of lane section
        lane_marker = f'<!-- LANE_{lane}_ISSUES -->'

        if lane_marker not in content:
            if verbose:
                print(f"  Warning: No marker {lane_marker} found in catalog")
            continue

        # Find the lane section header (e.g., "### Lane E - ...")
        lane_header_pattern = rf'(### Lane {lane} - [^\n]+\n\| ID \| Title \| Severity \| Type Tags \| Status \|\n\|[-|]+\|)[\s\S]*?({lane_marker})'

        match = re.search(lane_header_pattern, content)
        if match:
            # Generate new issue rows
            if open_issues.get(lane):
                issue_rows = generate_open_issues_section(open_issues[lane])
                new_section = f"{match.group(1)}\n{issue_rows}\n{match.group(2)}"
            else:
                # No open issues - empty section
                new_section = f"{match.group(1)}\n{match.group(2)}"

            content = re.sub(lane_header_pattern, new_section, content)
            if verbose and open_issues.get(lane):
                print(f"  Lane {lane}: {len(open_issues[lane])} open issues updated")
        else:
            if verbose:
                print(f"  Warning: Could not find lane section for Lane {lane}")

    # Write updated content
    with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    return True


def check_sync(stats: dict) -> tuple:
    """Check if catalog is in sync with actual files. Returns (is_synced, differences)."""
    if not os.path.exists(CATALOG_PATH):
        return False, ["Catalog file not found"]

    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    differences = []

    # Check header totals
    total_files = sum(s['total'] for s in stats.values())
    total_resolved = sum(s['resolved'] for s in stats.values())
    total_open = sum(s['open'] for s in stats.values())

    header_match = re.search(r'\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|', content)
    if header_match:
        cat_total = int(header_match.group(1))
        cat_resolved = int(header_match.group(2))
        cat_open = int(header_match.group(3))

        if cat_total != total_files:
            differences.append(f"Header total: catalog={cat_total}, actual={total_files}")
        if cat_resolved != total_resolved:
            differences.append(f"Header resolved: catalog={cat_resolved}, actual={total_resolved}")
        if cat_open != total_open:
            differences.append(f"Header open: catalog={cat_open}, actual={total_open}")

    # Check lane stats
    for lane in LANES:
        if lane not in stats:
            continue
        s = stats[lane]

        lane_pattern = rf'\| {lane} \| (\d+) \| (\d+) \| (\d+) \|'
        lane_match = re.search(lane_pattern, content)
        if lane_match:
            cat_total = int(lane_match.group(1))
            cat_resolved = int(lane_match.group(2))
            cat_open = int(lane_match.group(3))

            if cat_total != s['total'] or cat_resolved != s['resolved'] or cat_open != s['open']:
                differences.append(
                    f"Lane {lane}: catalog=({cat_total}/{cat_resolved}/{cat_open}), "
                    f"actual=({s['total']}/{s['resolved']}/{s['open']})"
                )

    return len(differences) == 0, differences


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize SAF_ISSUE_CATALOG.md statistics with actual issue files"
    )
    parser.add_argument('--check', action='store_true',
                        help="Check sync status without updating")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Show detailed output")
    args = parser.parse_args()

    print("Scanning issue files...")
    stats = scan_all_issues(verbose=args.verbose)

    total_files = sum(s['total'] for s in stats.values())
    total_resolved = sum(s['resolved'] for s in stats.values())
    total_open = sum(s['open'] for s in stats.values())

    print(f"\nFound: {total_files} issues, {total_resolved} resolved, {total_open} open")

    if args.check:
        is_synced, differences = check_sync(stats)
        if is_synced:
            print("✅ Catalog is in sync with issue files")
            return 0
        else:
            print("❌ Catalog is OUT OF SYNC:")
            for diff in differences:
                print(f"  - {diff}")
            return 1
    else:
        print("Updating catalog...")
        if update_catalog(stats, verbose=args.verbose):
            print("✅ Catalog updated successfully")
            return 0
        else:
            print("❌ Failed to update catalog")
            return 1


if __name__ == "__main__":
    sys.exit(main())
