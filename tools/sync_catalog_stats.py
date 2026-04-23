#!/usr/bin/env python3
"""
Catalog Statistics Synchronization Tool

Automatically scans all issue files and updates ISSUE_CATALOG.md
with accurate statistics from the actual file contents.

Now includes verification data integration - surfaces verification pass rates
alongside resolution rates so users see the full picture.

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
import json
import glob
import argparse
from datetime import datetime
from pathlib import Path

# Import failure analyzer
try:
    from analyze_verification_failures import analyze_all_failures, generate_catalog_section
    FAILURE_ANALYSIS_AVAILABLE = True
except ImportError:
    FAILURE_ANALYSIS_AVAILABLE = False

# Configuration
CATALOG_PATH = "ISSUE_CATALOG.md"
ISSUES_DIR = "issues"
EVIDENCE_DIR = "LogBook/verification/evidence"
COMPREHENSIVE_REPORT = "LogBook/verification/comprehensive_report.json"
LANES = ['A', 'D', 'E', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']

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

# =============================================================================
# VERIFICATION DATA
# =============================================================================

def get_verification_stats(verbose: bool = False) -> dict:
    """
    Get verification statistics from evidence files.

    Returns dict with:
    - per_lane: {lane: {verified: int, failed: int, uncertain: int}}
    - totals: {verified: int, failed: int, uncertain: int, malformed: int}
    """
    stats = {
        'per_lane': {},
        'totals': {
            'verified': 0,
            'failed': 0,
            'uncertain': 0,
            'malformed': 0
        }
    }

    # Initialize lanes
    for lane in LANES:
        stats['per_lane'][lane] = {
            'verified': 0,
            'failed': 0,
            'uncertain': 0
        }

    # Try to read comprehensive report first (faster)
    if os.path.exists(COMPREHENSIVE_REPORT):
        try:
            with open(COMPREHENSIVE_REPORT, 'r') as f:
                report = json.load(f)

            # Extract lane-level stats
            for lane, lane_data in report.get('lanes', {}).items():
                if lane not in stats['per_lane']:
                    continue

                stats['per_lane'][lane] = {
                    'verified': lane_data.get('passed', 0),
                    'failed': lane_data.get('genuine_failures', 0),
                    'uncertain': lane_data.get('false_negatives', 0)
                }

            # Get malformed count from summary
            stats['totals']['malformed'] = report.get('summary', {}).get('false_negatives', 0)

            if verbose:
                print(f"Loaded verification data from {COMPREHENSIVE_REPORT}")

        except Exception as e:
            if verbose:
                print(f"Warning: Could not load comprehensive report: {e}")

    # If no comprehensive report, scan evidence files directly
    if not any(stats['per_lane'][l]['verified'] or stats['per_lane'][l]['failed']
               for l in LANES):
        if verbose:
            print("Scanning evidence directory directly...")

        for lane in LANES:
            lane_dir = os.path.join(EVIDENCE_DIR, lane)
            if not os.path.isdir(lane_dir):
                continue

            # Track unique issues and their latest results
            issue_results = {}

            for evidence_file in glob.glob(os.path.join(lane_dir, '*.json')):
                try:
                    with open(evidence_file, 'r') as f:
                        data = json.load(f)

                    issue_id = data.get('issue_id', '')
                    all_passed = data.get('all_passed', False)

                    if issue_id:
                        # Keep the most recent result
                        issue_results[issue_id] = all_passed

                except Exception:
                    continue

            # Count results
            stats['per_lane'][lane]['verified'] = sum(1 for v in issue_results.values() if v)
            stats['per_lane'][lane]['failed'] = sum(1 for v in issue_results.values() if not v)

    # Calculate totals
    for lane in LANES:
        stats['totals']['verified'] += stats['per_lane'][lane]['verified']
        stats['totals']['failed'] += stats['per_lane'][lane]['failed']
        stats['totals']['uncertain'] += stats['per_lane'][lane]['uncertain']

    return stats

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

def get_all_issue_statuses(verbose: bool = False) -> dict:
    """Get status of all issue files, indexed by issue ID."""
    statuses = {}

    for lane in LANES:
        lane_dir = os.path.join(ISSUES_DIR, lane)
        if not os.path.isdir(lane_dir):
            continue

        files = [f for f in os.listdir(lane_dir) if f.endswith('.md')]

        for f in files:
            filepath = os.path.join(lane_dir, f)
            issue_id = f.replace('.md', '')
            status = get_file_status(filepath)
            statuses[issue_id] = status

            if verbose and status == 'UNKNOWN':
                print(f"  WARNING: {issue_id} has unknown status")

    return statuses

def update_lane_table_statuses(content: str, issue_statuses: dict, verbose: bool = False) -> str:
    """Update Status column in lane issue tables to match issue file statuses."""
    updated_content = content
    changes = []

    # Pattern to match table rows with issue IDs and status
    # Format: | S-11 | Title text... | 7/10 HIGH | Tag1, Tag2 | OPEN |
    row_pattern = re.compile(
        r'\| ([A-Z]-\d+) \|([^|]+)\|([^|]+)\|([^|]+)\| (OPEN|RESOLVED) \|'
    )

    def replace_status(match):
        issue_id = match.group(1)
        title = match.group(2)
        severity = match.group(3)
        tags = match.group(4)
        current_status = match.group(5)

        # Look up actual status from issue file
        actual_status = issue_statuses.get(issue_id)

        if actual_status is None:
            # Issue file not found - log warning but keep existing status
            if verbose:
                print(f"  WARNING: No issue file found for {issue_id}, keeping {current_status}")
            return match.group(0)

        if actual_status == 'UNKNOWN':
            # Can't determine status - keep existing
            if verbose:
                print(f"  WARNING: Unknown status for {issue_id}, keeping {current_status}")
            return match.group(0)

        if current_status != actual_status:
            changes.append((issue_id, current_status, actual_status))
            return f"| {issue_id} |{title}|{severity}|{tags}| {actual_status} |"

        return match.group(0)

    updated_content = row_pattern.sub(replace_status, updated_content)

    if verbose and changes:
        for issue_id, old_status, new_status in changes:
            lane = issue_id.split('-')[0]
            print(f"  Lane {lane}: Updated {issue_id} status {old_status} → {new_status}")

    return updated_content

def update_open_issues_tables(content: str, open_issues: dict, verbose: bool = False) -> str:
    """Regenerate Open Issues tables from actual issue files."""
    updated_content = content

    for lane in LANES:
        # Find the lane marker
        marker = f"<!-- LANE_{lane}_ISSUES -->"
        if marker not in updated_content:
            continue

        # Generate new table rows for this lane
        lane_issues = open_issues.get(lane, [])
        if lane_issues:
            new_rows = generate_open_issues_section(lane_issues)
        else:
            new_rows = ""  # Empty table if no open issues

        # Pattern anchored on the lane section header for specificity
        # Matches: ### Lane X - Description\n| ID | Title ...\n|----|----|...\n(rows)\n<!-- LANE_X_ISSUES -->
        lane_pattern = rf'(### Lane {lane} - [^\n]+\n\| ID \| Title \| Severity \| Type Tags \| Status \|\n\|-+\|-+\|-+\|-+\|-+\|\n).*?({re.escape(marker)})'

        def replace_table(match):
            header_section = match.group(1)
            marker_text = match.group(2)
            if new_rows:
                return f"{header_section}{new_rows}\n{marker_text}"
            else:
                return f"{header_section}{marker_text}"

        new_content = re.sub(lane_pattern, replace_table, updated_content, flags=re.DOTALL)

        if new_content != updated_content:
            if verbose:
                count = len(lane_issues)
                print(f"  Lane {lane}: {count} open issue{'s' if count != 1 else ''}")
            updated_content = new_content

    return updated_content

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

def generate_lane_completion_summary(stats: dict, verification_stats: dict = None) -> str:
    """Generate the Lane Completion Status summary section."""
    complete_lanes = []
    needs_work = []

    for lane in LANES:
        if lane not in stats:
            continue
        s = stats[lane]
        if s['total'] == 0:
            continue
        pct = round(100 * s['resolved'] / s['total'])
        if pct == 100:
            complete_lanes.append(lane)
        else:
            needs_work.append((lane, pct, s['open']))

    # Sort needs_work by percentage (lowest first)
    needs_work.sort(key=lambda x: x[1])

    lines = []
    lines.append("### Lane Completion Status")
    lines.append("")

    if complete_lanes:
        lanes_str = ", ".join(complete_lanes)
        lines.append(f"**Complete (100%):** {lanes_str} ({len(complete_lanes)} lanes)")
    else:
        lines.append("**Complete (100%):** None")

    lines.append("")

    if needs_work:
        lines.append("**Needs Work:**")
        lines.append("| Lane | Progress | Open |")
        lines.append("|------|----------|------|")
        for lane, pct, open_count in needs_work:
            lines.append(f"| {lane} | {pct}% | {open_count} |")
    else:
        lines.append("**Needs Work:** None - all lanes complete!")

    lines.append("")
    return "\n".join(lines)

def generate_verification_summary(stats: dict, verification_stats: dict) -> str:
    """Generate verification status summary section."""
    total_resolved = sum(s['resolved'] for s in stats.values())
    v_totals = verification_stats['totals']

    verified = v_totals['verified']
    failed = v_totals['failed']
    uncertain = v_totals['uncertain']
    malformed = v_totals['malformed']

    # Calculate percentages
    verified_pct = round(100 * verified / total_resolved, 1) if total_resolved else 0
    failed_pct = round(100 * failed / total_resolved, 1) if total_resolved else 0
    uncertain_pct = round(100 * uncertain / total_resolved, 1) if total_resolved else 0

    lines = [
        "### Verification Status",
        "",
        "> ⚠️ **Resolution ≠ Verification**: Issues marked RESOLVED may not have passing verification checks.",
        "> See [LogBook/verification/DASHBOARD.md](LogBook/verification/DASHBOARD.md) for details.",
        "",
        "| Metric | Count | % of Resolved |",
        "|--------|-------|---------------|",
        f"| ✅ Verified (PASS) | {verified} | {verified_pct}% |",
        f"| ❌ Failed | {failed} | {failed_pct}% |",
        f"| ❓ Uncertain | {uncertain} | {uncertain_pct}% |",
        "",
    ]

    if malformed > 0:
        lines.append(f"⚠️ **{malformed} issues** have malformed verification commands (always fail)")
        lines.append("")

    return "\n".join(lines)

def generate_verification_indicator(pct: float) -> str:
    """Generate verification status indicator."""
    if pct >= 80:
        return f"✅ {pct:.0f}%"
    elif pct >= 50:
        return f"🟡 {pct:.0f}%"
    elif pct > 0:
        return f"🔴 {pct:.0f}%"
    else:
        return "- 0%"

def update_catalog(stats: dict, verbose: bool = False) -> bool:
    """Update the catalog file with new statistics."""
    if not os.path.exists(CATALOG_PATH):
        print(f"ERROR: Catalog file not found: {CATALOG_PATH}")
        return False

    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Get verification stats
    if verbose:
        print("Loading verification data...")
    verification_stats = get_verification_stats(verbose=verbose)
    v_totals = verification_stats['totals']

    # Calculate totals
    total_files = sum(s['total'] for s in stats.values())
    total_resolved = sum(s['resolved'] for s in stats.values())
    total_open = sum(s['open'] for s in stats.values())
    total_verified = v_totals['verified']
    progress_pct = round(100 * total_resolved / total_files, 1) if total_files else 0
    verified_pct = round(100 * total_verified / total_resolved, 1) if total_resolved else 0

    if verbose:
        print(f"\nTotals: {total_files} files, {total_resolved} resolved, {total_open} open ({progress_pct}%)")
        print(f"Verification: {total_verified} verified ({verified_pct}% of resolved)")

    # Update timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = re.sub(
        r'>\s*\*\*Last Updated:\*\*\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
        f'> **Last Updated:** {timestamp}',
        content
    )

    # Update header stats table (add Verified column if not present)
    progress_bar = generate_progress_bar(progress_pct)
    verified_bar = generate_progress_bar(verified_pct)

    # Check if Verified column exists in header
    if '| Verified |' in content:
        # Update existing header with verified column
        new_header = f"| {total_files} | {total_resolved} | {total_verified} | {total_open} | {progress_bar} {progress_pct}% |"
        content = re.sub(
            r'\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\[█*░*\]\s*[\d.]+%\s*\|',
            new_header,
            content
        )
    else:
        # Update header without verified column (old format)
        new_header = f"| {total_files} | {total_resolved} | {total_open} | {progress_bar} {progress_pct}% |"
        content = re.sub(
            r'\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\[█*░*\]\s*[\d.]+%\s*\|',
            new_header,
            content
        )

    # Update lane table with verification columns
    lane_table_lines = []
    lane_table_lines.append("| Lane | Total | Resolved | Verified | Open | Resolution | Verification |")
    lane_table_lines.append("|------|-------|----------|----------|------|------------|--------------|")

    for lane in LANES:
        if lane not in stats:
            continue
        s = stats[lane]
        v = verification_stats['per_lane'].get(lane, {'verified': 0})

        res_pct = round(100 * s['resolved'] / s['total']) if s['total'] else 0
        ver_pct = round(100 * v['verified'] / s['resolved']) if s['resolved'] else 0

        res_indicator = generate_lane_indicator(res_pct)
        ver_indicator = generate_verification_indicator(ver_pct)

        lane_table_lines.append(
            f"| {lane} | {s['total']} | {s['resolved']} | {v['verified']} | {s['open']} | {res_indicator} | {ver_indicator} |"
        )

    new_lane_table = "\n".join(lane_table_lines)

    # Replace the lane table (handle both old and new formats)
    old_lane_pattern = r'\| Lane \| Total \| Resolved \| Open \| % \|[\s\S]*?\| Z \| \d+ \| \d+ \| \d+ \| [^\n]+ \|'
    new_lane_pattern = r'\| Lane \| Total \| Resolved \| Verified \| Open \| Resolution \| Verification \|[\s\S]*?\| Z \|[^\n]+\|'

    if re.search(new_lane_pattern, content):
        content = re.sub(new_lane_pattern, new_lane_table, content)
    elif re.search(old_lane_pattern, content):
        content = re.sub(old_lane_pattern, new_lane_table, content)
    else:
        if verbose:
            print("Warning: Could not find lane table to update")

    # Update or insert Verification Status section
    verification_summary = generate_verification_summary(stats, verification_stats)
    verification_pattern = r'### Verification Status\n\n>.*?(?=\n### Lane Completion Status|\n</details>|\n<!-- STATS_END -->)'

    if re.search(verification_pattern, content, re.DOTALL):
        # Update existing section
        content = re.sub(verification_pattern, verification_summary.rstrip(), content, flags=re.DOTALL)
        if verbose:
            print("Updated Verification Status section")
    else:
        # Insert new section before Lane Completion Status
        insert_point = content.find('### Lane Completion Status')
        if insert_point != -1:
            content = content[:insert_point] + verification_summary + '\n' + content[insert_point:]
            if verbose:
                print("Inserted new Verification Status section")
        else:
            # Insert before </details>
            insert_point = content.find('\n</details>')
            if insert_point != -1:
                content = content[:insert_point] + '\n\n' + verification_summary + content[insert_point:]
                if verbose:
                    print("Inserted Verification Status section before </details>")

    # Update or insert Failure Analysis section (if analyzer available)
    if FAILURE_ANALYSIS_AVAILABLE:
        try:
            if verbose:
                print("Analyzing verification failures...")
            failure_results = analyze_all_failures(verbose=False)
            failure_section = generate_catalog_section(failure_results)

            failure_pattern = r'### Failure Analysis\n\n>.*?(?=\n### Lane Completion Status|\n</details>|\n<!-- STATS_END -->)'

            if re.search(failure_pattern, content, re.DOTALL):
                # Update existing section
                content = re.sub(failure_pattern, failure_section.rstrip(), content, flags=re.DOTALL)
                if verbose:
                    print("Updated Failure Analysis section")
            else:
                # Insert new section before Lane Completion Status
                insert_point = content.find('### Lane Completion Status')
                if insert_point != -1:
                    content = content[:insert_point] + failure_section + '\n\n' + content[insert_point:]
                    if verbose:
                        print("Inserted new Failure Analysis section")
                else:
                    # Insert before </details>
                    insert_point = content.find('\n</details>')
                    if insert_point != -1:
                        content = content[:insert_point] + '\n\n' + failure_section + content[insert_point:]
                        if verbose:
                            print("Inserted Failure Analysis section before </details>")
        except Exception as e:
            if verbose:
                print(f"Warning: Could not generate failure analysis: {e}")

    # Update or insert Lane Completion Status section
    lane_summary = generate_lane_completion_summary(stats, verification_stats)
    lane_summary_pattern = r'### Lane Completion Status\n\n\*\*Complete \(100%\):\*\*.*?(?=\n</details>|\n<!-- STATS_END -->)'

    if re.search(lane_summary_pattern, content, re.DOTALL):
        # Update existing section
        content = re.sub(lane_summary_pattern, lane_summary.rstrip(), content, flags=re.DOTALL)
        if verbose:
            print("Updated Lane Completion Status section")
    else:
        # Insert new section before </details>
        insert_point = content.find('\n</details>')
        if insert_point != -1:
            content = content[:insert_point] + '\n\n' + lane_summary + content[insert_point:]
            if verbose:
                print("Inserted new Lane Completion Status section")

    # Update status columns in lane issue tables
    if verbose:
        print("Syncing lane table status columns...")
    issue_statuses = get_all_issue_statuses(verbose=verbose)
    content = update_lane_table_statuses(content, issue_statuses, verbose=verbose)

    # Regenerate Open Issues tables from actual issue files
    if verbose:
        print("Regenerating Open Issues tables...")
    open_issues = scan_open_issues(verbose=verbose)
    content = update_open_issues_tables(content, open_issues, verbose=verbose)

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

    # Check lane stats - handle new format with Verified column
    # New format: | Lane | Total | Resolved | Verified | Open | Resolution | Verification |
    for lane in LANES:
        if lane not in stats:
            continue
        s = stats[lane]

        # Try new format first (with Verified column)
        new_lane_pattern = rf'\| {lane} \| (\d+) \| (\d+) \| \d+ \| (\d+) \|'
        lane_match = re.search(new_lane_pattern, content)

        if not lane_match:
            # Fall back to old format
            old_lane_pattern = rf'\| {lane} \| (\d+) \| (\d+) \| (\d+) \|'
            lane_match = re.search(old_lane_pattern, content)

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
        description="Synchronize ISSUE_CATALOG.md statistics with actual issue files"
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
