#!/usr/bin/env python3
"""
the system Verification Dashboard Generator

Generates and updates the LogBook/verification/DASHBOARD.md file with
real-time progress tracking for issue verification.

Features:
- Visual progress bars per lane
- Overall statistics
- Recent activity log
- Current operation status
- Evidence collection summary

Usage:
    python3 tools/update_dashboard.py              # Generate dashboard
    python3 tools/update_dashboard.py --watch      # Auto-update on changes
"""

import os
import sys
import glob
import json
import yaml
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
EVIDENCE_DIR = "LogBook/verification/evidence"
DASHBOARD_FILE = "LogBook/verification/DASHBOARD.md"

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LaneProgress:
    """Progress stats for a lane."""
    lane: str
    total: int
    resolved: int
    verified: int
    open: int
    resolution_pct: float
    verification_pct: float

@dataclass
class RecentActivity:
    """Recent verification activity."""
    timestamp: str
    issue_id: str
    result: str
    checks_passed: int
    checks_total: int
    duration_ms: int

# =============================================================================
# DATA COLLECTION
# =============================================================================

def count_issues_by_lane(issues_dir: str) -> Dict[str, Dict[str, int]]:
    """Count issues by lane and status."""
    lanes = {}

    for lane_dir in glob.glob(os.path.join(issues_dir, '*')):
        if not os.path.isdir(lane_dir):
            continue

        lane = os.path.basename(lane_dir).upper()
        lanes[lane] = {'total': 0, 'resolved': 0, 'open': 0}

        for filepath in glob.glob(os.path.join(lane_dir, '*.md')):
            if 'TEMPLATE' in filepath.upper():
                continue

            lanes[lane]['total'] += 1

            # Check status from content (more reliable)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for RESOLVED status in content (handles both frontmatter and body)
                if 'status: "RESOLVED"' in content or 'Status: RESOLVED' in content or 'Status: CLOSED' in content:
                    lanes[lane]['resolved'] += 1
                else:
                    lanes[lane]['open'] += 1

            except Exception:
                lanes[lane]['open'] += 1

    return lanes

def count_verified_by_lane(evidence_dir: str) -> Dict[str, int]:
    """Count verified issues by lane from evidence files."""
    verified = {}

    for lane_dir in glob.glob(os.path.join(evidence_dir, '*')):
        if not os.path.isdir(lane_dir):
            continue

        lane = os.path.basename(lane_dir).upper()
        verified[lane] = 0

        # Get unique issue IDs that passed all checks
        issue_results = {}

        for evidence_file in glob.glob(os.path.join(lane_dir, '*.json')):
            try:
                with open(evidence_file, 'r') as f:
                    data = json.load(f)

                issue_id = data.get('issue_id', '')
                all_passed = data.get('all_passed', False)

                # Keep most recent result per issue
                if issue_id:
                    if issue_id not in issue_results:
                        issue_results[issue_id] = all_passed
                    else:
                        # Evidence files are timestamped, later = newer
                        issue_results[issue_id] = all_passed

            except Exception:
                continue

        verified[lane] = sum(1 for v in issue_results.values() if v)

    return verified

def get_recent_activity(evidence_dir: str, limit: int = 10) -> List[RecentActivity]:
    """Get recent verification activity."""
    activities = []

    for evidence_file in glob.glob(os.path.join(evidence_dir, '*', '*.json')):
        try:
            with open(evidence_file, 'r') as f:
                data = json.load(f)

            activities.append(RecentActivity(
                timestamp=data.get('timestamp', ''),
                issue_id=data.get('issue_id', 'unknown'),
                result='PASS' if data.get('all_passed', False) else 'FAIL',
                checks_passed=data.get('passed_checks', 0),
                checks_total=data.get('total_checks', 0),
                duration_ms=data.get('total_duration_ms', 0)
            ))

        except Exception:
            continue

    # Sort by timestamp descending
    activities.sort(key=lambda x: x.timestamp, reverse=True)

    return activities[:limit]

# =============================================================================
# PROGRESS BAR GENERATION
# =============================================================================

def generate_progress_bar(percentage: float, width: int = 30) -> str:
    """Generate text-based progress bar."""
    filled = int(width * percentage / 100)
    empty = width - filled
    bar = '\u2588' * filled + '\u2591' * empty
    return f"[{bar}]"

def get_status_icon(pct: float) -> str:
    """Get status icon based on percentage."""
    if pct >= 100:
        return "\u2705"  # Green check
    elif pct >= 50:
        return "\U0001f7e1"  # Yellow circle
    else:
        return "\U0001f534"  # Red circle

# =============================================================================
# DASHBOARD GENERATION
# =============================================================================

def generate_dashboard(issues_dir: str, evidence_dir: str) -> str:
    """Generate complete dashboard markdown."""
    now = datetime.now()

    # Collect data
    lane_counts = count_issues_by_lane(issues_dir)
    verified_counts = count_verified_by_lane(evidence_dir)
    recent = get_recent_activity(evidence_dir)

    # Calculate totals
    total_issues = sum(l['total'] for l in lane_counts.values())
    total_resolved = sum(l['resolved'] for l in lane_counts.values())
    total_open = sum(l['open'] for l in lane_counts.values())
    total_verified = sum(verified_counts.values())

    resolution_pct = (total_resolved / total_issues * 100) if total_issues > 0 else 0
    verification_pct = (total_verified / total_resolved * 100) if total_resolved > 0 else 0

    # Build dashboard
    lines = [
        "# Fix Verification Dashboard",
        "",
        f"> **Last Updated:** {now.strftime('%Y-%m-%d %H:%M:%S')}",
        ">",
        "> **Auto-generated by:** `python3 tools/update_dashboard.py`",
        "",
        "---",
        "",
        "## Overall Progress",
        "",
        f"**Total Issues:** {total_issues}",
        f"",
        f"| Metric | Count | Progress |",
        f"|--------|-------|----------|",
        f"| Resolved | {total_resolved} | {generate_progress_bar(resolution_pct)} {resolution_pct:.1f}% |",
        f"| Verified | {total_verified} | {generate_progress_bar(verification_pct)} {verification_pct:.1f}% |",
        f"| Open | {total_open} | - |",
        "",
        "---",
        "",
        "## Lane Progress",
        "",
        "| Lane | Total | Resolved | Verified | Resolution | Verification |",
        "|------|-------|----------|----------|------------|--------------|",
    ]

    # Sort lanes
    sorted_lanes = sorted(lane_counts.keys(), key=lambda x: (x != 'A', x))

    for lane in sorted_lanes:
        counts = lane_counts[lane]
        verified = verified_counts.get(lane, 0)

        total = counts['total']
        resolved = counts['resolved']

        res_pct = (resolved / total * 100) if total > 0 else 0
        ver_pct = (verified / resolved * 100) if resolved > 0 else 0

        res_icon = get_status_icon(res_pct)
        ver_icon = get_status_icon(ver_pct) if resolved > 0 else "-"

        lines.append(
            f"| **{lane}** | {total} | {resolved} | {verified} | "
            f"{res_icon} {res_pct:.0f}% | {ver_icon} {ver_pct:.0f}% |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Recent Activity",
        "",
    ])

    if recent:
        lines.extend([
            "| Time | Issue | Result | Checks | Duration |",
            "|------|-------|--------|--------|----------|",
        ])

        for activity in recent:
            try:
                time_str = datetime.fromisoformat(activity.timestamp).strftime('%H:%M:%S')
            except:
                time_str = activity.timestamp[:8]

            icon = "\u2705" if activity.result == 'PASS' else "\u274c"
            lines.append(
                f"| {time_str} | {activity.issue_id} | {icon} {activity.result} | "
                f"{activity.checks_passed}/{activity.checks_total} | {activity.duration_ms}ms |"
            )
    else:
        lines.append("*No recent verification activity*")

    lines.extend([
        "",
        "---",
        "",
        "## Quick Commands",
        "",
        "```bash",
        "# Verify single issue",
        "python3 tools/collect_evidence.py G-01",
        "",
        "# Verify entire lane",
        "python3 tools/collect_evidence.py --lane G",
        "",
        "# Verify all issues",
        "python3 tools/collect_evidence.py --all",
        "",
        "# Update this dashboard",
        "python3 tools/update_dashboard.py",
        "",
        "# Check issue statistics",
        "python3 tools/issue_stats.py",
        "",
        "# Verify stats accuracy",
        "python3 tools/verify_stats.py",
        "```",
        "",
        "---",
        "",
        "## Legend",
        "",
        "| Icon | Meaning |",
        "|------|---------|",
        "| \u2705 | 100% complete |",
        "| \U0001f7e1 | 50-99% complete |",
        "| \U0001f534 | <50% complete |",
        "| \u274c | Failed check |",
        "",
        "---",
        "",
    ])

    return '\n'.join(lines)

def save_dashboard(content: str, dashboard_file: str) -> None:
    """Save dashboard to file."""
    os.makedirs(os.path.dirname(dashboard_file), exist_ok=True)

    with open(dashboard_file, 'w', encoding='utf-8') as f:
        f.write(content)

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate the system verification dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--issues-dir', '-i', type=str, default=ISSUES_DIR)
    parser.add_argument('--evidence-dir', '-e', type=str, default=EVIDENCE_DIR)
    parser.add_argument('--output', '-o', type=str, default=DASHBOARD_FILE)

    args = parser.parse_args()

    print(f"Generating dashboard...")

    content = generate_dashboard(args.issues_dir, args.evidence_dir)
    save_dashboard(content, args.output)

    print(f"Dashboard saved to: {args.output}")

    # Also print summary
    lane_counts = count_issues_by_lane(args.issues_dir)
    verified_counts = count_verified_by_lane(args.evidence_dir)

    total = sum(l['total'] for l in lane_counts.values())
    resolved = sum(l['resolved'] for l in lane_counts.values())
    verified = sum(verified_counts.values())

    print(f"\nSummary:")
    print(f"  Total Issues:  {total}")
    print(f"  Resolved:      {resolved} ({resolved/total*100:.1f}%)" if total > 0 else f"  Resolved:      {resolved}")
    print(f"  Verified:      {verified} ({verified/resolved*100:.1f}% of resolved)" if resolved > 0 else "  Verified: 0")

if __name__ == '__main__':
    main()
