#!/usr/bin/env python3
"""
the system Comprehensive Status Report Generator

Generates detailed reports on catalog status, progress, and agent readiness.
Outputs both console summary and JSON/Markdown reports.

Usage:
    python3 tools/generate_report.py                 # Console output
    python3 tools/generate_report.py --json report.json
    python3 tools/generate_report.py --markdown report.md
    python3 tools/generate_report.py --all           # All formats
"""

import os
import re
import sys
import glob
import json
import yaml
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
TOOLS_DIR = "tools"

# =============================================================================
# DATA COLLECTION
# =============================================================================

def parse_frontmatter(filepath: str) -> Optional[Dict]:
    """Parse YAML frontmatter from issue file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    if not content.startswith('---'):
        return None

    end = content.find('\n---\n', 3)
    if end < 0:
        return None

    try:
        fm = yaml.safe_load(content[4:end])
        fm['_content'] = content
        return fm
    except yaml.YAMLError:
        return None

def collect_all_issues(issues_dir: str) -> List[Dict]:
    """Collect data from all issues."""
    issues = []

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        fm = parse_frontmatter(filepath)
        if fm:
            fm['_filepath'] = filepath
            fm['_filename'] = os.path.basename(filepath)
            issues.append(fm)

    return issues

def analyze_issues(issues: List[Dict]) -> Dict:
    """Analyze issues and generate statistics."""
    stats = {
        'total': len(issues),
        'resolved': 0,
        'open': 0,
        'by_lane': defaultdict(lambda: {'total': 0, 'resolved': 0, 'open': 0}),
        'by_severity': defaultdict(lambda: {'total': 0, 'resolved': 0}),
        'by_type': defaultdict(lambda: {'total': 0, 'resolved': 0}),
        'by_pattern': defaultdict(lambda: {'total': 0, 'resolved': 0}),
        'has_commands': 0,
        'has_outputs': 0,
        'has_deps': 0,
        'has_checklist': 0,
        'has_pattern_vars': 0,
        'has_resolution': 0,
        'high_severity_open': [],
        'recently_resolved': [],
        'blocked_issues': [],
    }

    for issue in issues:
        content = issue.get('_content', '')
        status = issue.get('status', 'OPEN')
        lane = issue.get('lane', 'X')
        severity = issue.get('severity', 5)
        issue_id = issue.get('issue_id', issue.get('_filename', '').replace('.md', ''))

        # Basic counts
        if status == 'RESOLVED':
            stats['resolved'] += 1
            stats['by_lane'][lane]['resolved'] += 1
        else:
            stats['open'] += 1
            stats['by_lane'][lane]['open'] += 1

        stats['by_lane'][lane]['total'] += 1

        # Severity
        severity_level = issue.get('severity_level', 'MEDIUM')
        stats['by_severity'][severity_level]['total'] += 1
        if status == 'RESOLVED':
            stats['by_severity'][severity_level]['resolved'] += 1

        # High severity open
        if severity >= 8 and status != 'RESOLVED':
            stats['high_severity_open'].append({
                'id': issue_id,
                'severity': severity,
                'lane': lane
            })

        # Type tags
        for tag in issue.get('type_tags', []):
            stats['by_type'][tag]['total'] += 1
            if status == 'RESOLVED':
                stats['by_type'][tag]['resolved'] += 1

        # Pattern
        pattern = issue.get('verification_pattern', 'unknown')
        stats['by_pattern'][pattern]['total'] += 1
        if status == 'RESOLVED':
            stats['by_pattern'][pattern]['resolved'] += 1

        # Optimization features
        if '**Verification Commands' in content and '```bash' in content:
            stats['has_commands'] += 1
        if '**Expected Output' in content:
            stats['has_outputs'] += 1
        if 'depends_on:' in content and 'blocks:' in content:
            stats['has_deps'] += 1
        if '**Fix Implementation Checklist**' in content:
            stats['has_checklist'] += 1
        if 'pattern_vars:' in content[:3000]:
            stats['has_pattern_vars'] += 1
        if '## Resolution Evidence' in content:
            stats['has_resolution'] += 1

        # Blocked issues
        blocks = issue.get('blocks', [])
        if blocks and status != 'RESOLVED':
            stats['blocked_issues'].append({
                'id': issue_id,
                'blocks': blocks[:5]
            })

    return stats

def check_tools_status(tools_dir: str) -> Dict:
    """Check status of all optimization tools."""
    tools = {
        'phase1': [
            'verification_patterns.yaml',
            'add_frontmatter.py',
            'add_verification_commands.py',
            'generate_expected_outputs.py',
            'compute_dependencies.py',
            'verify_optimization.py',
        ],
        'phase2': [
            'collect_evidence.py',
            'add_fix_checklist.py',
            'add_pattern_vars.py',
            'verify_phase2.py',
        ],
        'phase3': [
            'batch_verify.py',
            'add_resolution_template.py',
            'validate_crossrefs.py',
            'auto_resolve.py',
            'generate_report.py',
        ],
        'core': [
            'issue_stats.py',
            'verify_stats.py',
            'verify_issue.py',
            'update_dashboard.py',
        ]
    }

    status = {}
    for phase, tool_list in tools.items():
        status[phase] = {
            'total': len(tool_list),
            'present': 0,
            'tools': {}
        }
        for tool in tool_list:
            path = os.path.join(tools_dir, tool)
            exists = os.path.exists(path)
            status[phase]['tools'][tool] = exists
            if exists:
                status[phase]['present'] += 1

    return status

# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_console_report(stats: Dict, tools: Dict) -> str:
    """Generate console-formatted report."""
    lines = []

    lines.append("=" * 70)
    lines.append("the system COMPREHENSIVE STATUS REPORT")
    lines.append("=" * 70)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Overall Progress
    lines.append("-" * 70)
    lines.append("OVERALL PROGRESS")
    lines.append("-" * 70)
    total = stats['total']
    resolved = stats['resolved']
    open_count = stats['open']
    pct = (resolved / total * 100) if total > 0 else 0

    # Progress bar
    bar_width = 40
    filled = int(bar_width * pct / 100)
    bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
    lines.append(f"   [{bar}] {pct:.1f}%")
    lines.append("")
    lines.append(f"   Total Issues:    {total}")
    lines.append(f"   Resolved:        {resolved}")
    lines.append(f"   Open:            {open_count}")
    lines.append("")

    # By Lane
    lines.append("-" * 70)
    lines.append("BY LANE")
    lines.append("-" * 70)
    for lane in sorted(stats['by_lane'].keys()):
        data = stats['by_lane'][lane]
        lane_pct = (data['resolved'] / data['total'] * 100) if data['total'] > 0 else 0
        lines.append(f"   Lane {lane}: {data['resolved']}/{data['total']} ({lane_pct:.0f}%)")
    lines.append("")

    # By Severity
    lines.append("-" * 70)
    lines.append("BY SEVERITY")
    lines.append("-" * 70)
    for level in ['HIGH', 'MEDIUM', 'LOW']:
        if level in stats['by_severity']:
            data = stats['by_severity'][level]
            sev_pct = (data['resolved'] / data['total'] * 100) if data['total'] > 0 else 0
            lines.append(f"   {level}: {data['resolved']}/{data['total']} ({sev_pct:.0f}%)")
    lines.append("")

    # Optimization Status
    lines.append("-" * 70)
    lines.append("OPTIMIZATION STATUS")
    lines.append("-" * 70)
    opt_items = [
        ('Verification Commands', stats['has_commands']),
        ('Expected Outputs', stats['has_outputs']),
        ('Dependencies', stats['has_deps']),
        ('Fix Checklists', stats['has_checklist']),
        ('Pattern Variables', stats['has_pattern_vars']),
        ('Resolution Templates', stats['has_resolution']),
    ]
    for name, count in opt_items:
        pct = (count / total * 100) if total > 0 else 0
        lines.append(f"   {name}: {count}/{total} ({pct:.0f}%)")
    lines.append("")

    # Tools Status
    lines.append("-" * 70)
    lines.append("TOOLS STATUS")
    lines.append("-" * 70)
    for phase, data in tools.items():
        phase_pct = (data['present'] / data['total'] * 100) if data['total'] > 0 else 0
        status = "\u2705" if data['present'] == data['total'] else "\u26a0\ufe0f "
        lines.append(f"   {status} {phase.upper()}: {data['present']}/{data['total']} ({phase_pct:.0f}%)")
    lines.append("")

    # High Priority Open Issues
    if stats['high_severity_open']:
        lines.append("-" * 70)
        lines.append("HIGH PRIORITY OPEN ISSUES")
        lines.append("-" * 70)
        for issue in stats['high_severity_open'][:10]:
            lines.append(f"   {issue['id']} (severity: {issue['severity']}, lane: {issue['lane']})")
        if len(stats['high_severity_open']) > 10:
            lines.append(f"   ... and {len(stats['high_severity_open']) - 10} more")
        lines.append("")

    # Agent Readiness
    lines.append("-" * 70)
    lines.append("AGENT READINESS")
    lines.append("-" * 70)

    cmd_pct = (stats['has_commands'] / total * 100) if total > 0 else 0
    checklist_pct = (stats['has_checklist'] / total * 100) if total > 0 else 0

    if cmd_pct >= 95:
        lines.append("   \u2705 Phase 1: Mechanical verification ready (95%+)")
    else:
        lines.append(f"   \u26a0\ufe0f  Phase 1: {cmd_pct:.0f}% ready")

    if checklist_pct >= 80:
        lines.append("   \u2705 Phase 2: Fix execution ready (80%+)")
    else:
        lines.append(f"   \u26a0\ufe0f  Phase 2: {checklist_pct:.0f}% ready")

    all_phase3 = all(tools['phase3']['tools'].values())
    if all_phase3:
        lines.append("   \u2705 Phase 3: Batch operations ready")
    else:
        lines.append("   \u26a0\ufe0f  Phase 3: Tools incomplete")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)

def generate_json_report(stats: Dict, tools: Dict) -> Dict:
    """Generate JSON report."""
    return {
        'generated': datetime.now().isoformat(),
        'summary': {
            'total': stats['total'],
            'resolved': stats['resolved'],
            'open': stats['open'],
            'resolution_rate': round(stats['resolved'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
        },
        'by_lane': dict(stats['by_lane']),
        'by_severity': dict(stats['by_severity']),
        'by_type': dict(stats['by_type']),
        'by_pattern': dict(stats['by_pattern']),
        'optimization': {
            'has_commands': stats['has_commands'],
            'has_outputs': stats['has_outputs'],
            'has_deps': stats['has_deps'],
            'has_checklist': stats['has_checklist'],
            'has_pattern_vars': stats['has_pattern_vars'],
            'has_resolution': stats['has_resolution'],
        },
        'tools': tools,
        'high_priority_open': stats['high_severity_open'],
        'blocked_issues': stats['blocked_issues'][:20]
    }

def generate_markdown_report(stats: Dict, tools: Dict) -> str:
    """Generate Markdown report."""
    lines = []

    lines.append("# the system Status Report")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")

    # Summary
    total = stats['total']
    resolved = stats['resolved']
    pct = (resolved / total * 100) if total > 0 else 0

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Issues | {total} |")
    lines.append(f"| Resolved | {resolved} ({pct:.1f}%) |")
    lines.append(f"| Open | {stats['open']} |")
    lines.append("")

    # By Lane
    lines.append("## Progress by Lane")
    lines.append("")
    lines.append("| Lane | Total | Resolved | Open | Progress |")
    lines.append("|------|-------|----------|------|----------|")
    for lane in sorted(stats['by_lane'].keys()):
        data = stats['by_lane'][lane]
        lane_pct = (data['resolved'] / data['total'] * 100) if data['total'] > 0 else 0
        lines.append(f"| {lane} | {data['total']} | {data['resolved']} | {data['open']} | {lane_pct:.0f}% |")
    lines.append("")

    # Optimization
    lines.append("## Optimization Status")
    lines.append("")
    lines.append("| Feature | Count | Coverage |")
    lines.append("|---------|-------|----------|")
    opt_items = [
        ('Verification Commands', stats['has_commands']),
        ('Expected Outputs', stats['has_outputs']),
        ('Dependencies', stats['has_deps']),
        ('Fix Checklists', stats['has_checklist']),
        ('Pattern Variables', stats['has_pattern_vars']),
    ]
    for name, count in opt_items:
        opt_pct = (count / total * 100) if total > 0 else 0
        lines.append(f"| {name} | {count} | {opt_pct:.0f}% |")
    lines.append("")

    # High Priority
    if stats['high_severity_open']:
        lines.append("## High Priority Open Issues")
        lines.append("")
        for issue in stats['high_severity_open'][:15]:
            lines.append(f"- **{issue['id']}** (Lane {issue['lane']}, Severity {issue['severity']})")
        lines.append("")

    return "\n".join(lines)

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate the system comprehensive status report'
    )
    parser.add_argument('--json', '-j', type=str, help='Output JSON report to file')
    parser.add_argument('--markdown', '-m', type=str, help='Output Markdown report to file')
    parser.add_argument('--all', '-a', action='store_true', help='Generate all report formats')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)
    parser.add_argument('--tools-dir', '-t', type=str, default=TOOLS_DIR)

    args = parser.parse_args()

    # Collect data
    print("Collecting data...")
    issues = collect_all_issues(args.issues_dir)
    stats = analyze_issues(issues)
    tools = check_tools_status(args.tools_dir)

    # Generate console report
    console_report = generate_console_report(stats, tools)
    print(console_report)

    # Generate JSON if requested
    if args.json or args.all:
        json_file = args.json or 'saf_report.json'
        json_report = generate_json_report(stats, tools)
        with open(json_file, 'w') as f:
            json.dump(json_report, f, indent=2)
        print(f"\nJSON report saved to: {json_file}")

    # Generate Markdown if requested
    if args.markdown or args.all:
        md_file = args.markdown or 'saf_report.md'
        md_report = generate_markdown_report(stats, tools)
        with open(md_file, 'w') as f:
            f.write(md_report)
        print(f"Markdown report saved to: {md_file}")

if __name__ == '__main__':
    main()
