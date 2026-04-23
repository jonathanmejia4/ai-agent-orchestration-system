#!/usr/bin/env python3
"""LogBook compliance reporting tool (K010).

Generates audit reports from LogBook for compliance reviews.

Usage:
    # Generate monthly report
    python3 tools/logbook_compliance_report.py --month 2025-12

    # Generate report for date range
    python3 tools/logbook_compliance_report.py --since 2025-12-01 --until 2025-12-31

    # Export to JSON
    python3 tools/logbook_compliance_report.py --month 2025-12 --format json > report.json

    # Generate summary only
    python3 tools/logbook_compliance_report.py --month 2025-12 --summary-only
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

try:
    import yaml
except ImportError:
    print("❌ Missing dependency: pyyaml")
    print("Install with: pip install pyyaml")
    sys.exit(2)

def load_logbook_entries(logbook_dir: Path) -> List[Dict[str, Any]]:
    """Load all LogBook entries."""
    entries = []

    if not logbook_dir.exists():
        return entries

    for entry_path in logbook_dir.rglob("*.yaml"):
        try:
            entry = yaml.safe_load(entry_path.read_text())
            entry['_file'] = str(entry_path)
            entries.append(entry)
        except Exception as e:
            print(f"⚠️  Failed to load {entry_path.name}: {e}", file=sys.stderr)

    return entries

def filter_by_time_range(entries: List[Dict[str, Any]], since: datetime, until: datetime) -> List[Dict[str, Any]]:
    """Filter entries by time range."""
    filtered = []

    for entry in entries:
        try:
            timestamp_str = entry.get('timestamp')
            if not timestamp_str:
                continue

            entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

            if since <= entry_time <= until:
                filtered.append(entry)

        except Exception:
            continue

    return filtered

def generate_compliance_report(entries: List[Dict[str, Any]], since: datetime, until: datetime) -> Dict[str, Any]:
    """Generate compliance report from LogBook entries."""
    report = {
        'period': {
            'start': since.isoformat(),
            'end': until.isoformat(),
        },
        'summary': {
            'total_entries': len(entries),
            'by_agent': defaultdict(int),
            'by_action': defaultdict(int),
        },
        'stage_promotions': {
            'total': 0,
            'by_stage_transition': defaultdict(int),
            'by_agent': defaultdict(int),
        },
        'tasks_modified': set(),
        'agents_active': set(),
        'compliance_checks': {},
        'anomalies': [],
    }

    # Process entries
    promotion_count = 0

    for entry in entries:
        agent = entry.get('agent', 'UNKNOWN')
        action = entry.get('action', 'UNKNOWN')

        # Summary stats
        report['summary']['by_agent'][agent] += 1
        report['summary']['by_action'][action] += 1

        # Track active agents
        report['agents_active'].add(agent)

        # Track tasks
        task_path = entry.get('context', {}).get('task_path')
        if task_path:
            report['tasks_modified'].add(task_path)

        # Stage promotions
        if action == 'stage_promotion':
            promotion_count += 1

            from_stage = entry.get('context', {}).get('from_stage')
            to_stage = entry.get('context', {}).get('to_stage')

            if from_stage and to_stage:
                transition = f"{from_stage} → {to_stage}"
                report['stage_promotions']['by_stage_transition'][transition] += 1
                report['stage_promotions']['by_agent'][agent] += 1

    # Convert sets to lists for JSON serialization
    report['tasks_modified'] = list(report['tasks_modified'])
    report['agents_active'] = list(report['agents_active'])

    # Convert defaultdict to dict
    report['summary']['by_agent'] = dict(report['summary']['by_agent'])
    report['summary']['by_action'] = dict(report['summary']['by_action'])
    report['stage_promotions']['by_stage_transition'] = dict(report['stage_promotions']['by_stage_transition'])
    report['stage_promotions']['by_agent'] = dict(report['stage_promotions']['by_agent'])
    report['stage_promotions']['total'] = promotion_count

    # Compliance checks
    report['compliance_checks'] = {
        'pm_active': 'PM' in report['agents_active'],
        'has_promotions': promotion_count > 0,
        'has_stage4_golden_promotions': any('Stage4-Golden' in t for t in report['stage_promotions']['by_stage_transition'].keys()),
        'all_agents_active': len(report['agents_active']) == 4,  # PM, Planner, Builder, Critic
    }

    # Detect anomalies
    # 1. No PM activity
    if 'PM' not in report['agents_active']:
        report['anomalies'].append({
            'type': 'NO_PM_ACTIVITY',
            'severity': 'HIGH',
            'message': 'No PM activity detected in this period'
        })

    # 2. No stage promotions
    if promotion_count == 0:
        report['anomalies'].append({
            'type': 'NO_PROMOTIONS',
            'severity': 'MEDIUM',
            'message': 'No stage promotions detected (development may be stalled)'
        })

    # 3. Direct Stage3 → Stage4-Golden without PM
    stage4_promotions = [e for e in entries
                          if e.get('action') == 'stage_promotion'
                          and e.get('context', {}).get('to_stage') == 'Stage4-Golden']

    for prom in stage4_promotions:
        if prom.get('agent') != 'PM':
            report['anomalies'].append({
                'type': 'UNAUTHORIZED_PRODUCTION_PROMOTION',
                'severity': 'CRITICAL',
                'message': f"Stage4-Golden promotion by {prom.get('agent')} (should be PM only)",
                'task': prom.get('context', {}).get('task_path'),
                'timestamp': prom.get('timestamp')
            })

    # 4. High frequency promotions (potential bypass)
    if promotion_count > 100:  # More than 100 promotions in period
        report['anomalies'].append({
            'type': 'HIGH_PROMOTION_FREQUENCY',
            'severity': 'MEDIUM',
            'message': f'{promotion_count} promotions detected (unusually high frequency)'
        })

    return report

def format_report_text(report: Dict[str, Any]):
    """Format report as human-readable text."""
    print("=" * 80)
    print("the system LOGBOOK COMPLIANCE REPORT")
    print("=" * 80)
    print()

    # Period
    print(f"Period: {report['period']['start']} to {report['period']['end']}")
    print()

    # Summary
    summary = report['summary']
    print("SUMMARY")
    print("-" * 80)
    print(f"Total LogBook Entries: {summary['total_entries']}")
    print(f"Unique Tasks Modified: {len(report['tasks_modified'])}")
    print(f"Active Agents: {', '.join(sorted(report['agents_active']))}")
    print()

    # By Agent
    print("Activity by Agent:")
    for agent, count in sorted(summary['by_agent'].items(), key=lambda x: -x[1]):
        print(f"  {agent:10s}: {count:4d} actions")
    print()

    # By Action
    print("Activity by Action Type:")
    for action, count in sorted(summary['by_action'].items(), key=lambda x: -x[1]):
        print(f"  {action:25s}: {count:4d}")
    print()

    # Stage Promotions
    promotions = report['stage_promotions']
    print("STAGE PROMOTIONS")
    print("-" * 80)
    print(f"Total Promotions: {promotions['total']}")
    print()

    if promotions['by_stage_transition']:
        print("By Stage Transition:")
        for transition, count in sorted(promotions['by_stage_transition'].items()):
            print(f"  {transition:30s}: {count:4d}")
        print()

    if promotions['by_agent']:
        print("Promotions by Agent:")
        for agent, count in sorted(promotions['by_agent'].items(), key=lambda x: -x[1]):
            print(f"  {agent:10s}: {count:4d}")
        print()

    # Compliance Checks
    checks = report['compliance_checks']
    print("COMPLIANCE CHECKS")
    print("-" * 80)
    print(f"PM Active: {'✅ YES' if checks['pm_active'] else '❌ NO'}")
    print(f"Has Promotions: {'✅ YES' if checks['has_promotions'] else '❌ NO'}")
    print(f"Has Stage4-Golden Promotions: {'✅ YES' if checks['has_stage4_golden_promotions'] else '⚠️  NO'}")
    print(f"All Agents Active: {'✅ YES' if checks['all_agents_active'] else '⚠️  NO'}")
    print()

    # Anomalies
    anomalies = report['anomalies']
    if anomalies:
        print("ANOMALIES DETECTED")
        print("-" * 80)
        for i, anomaly in enumerate(anomalies, 1):
            severity = anomaly['severity']
            severity_icon = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(severity, '⚪')
            print(f"{i}. [{severity_icon} {severity}] {anomaly['type']}")
            print(f"   {anomaly['message']}")
            if 'task' in anomaly:
                print(f"   Task: {anomaly['task']}")
            if 'timestamp' in anomaly:
                print(f"   Time: {anomaly['timestamp']}")
            print()
    else:
        print("✅ No anomalies detected")
        print()

    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(
        description="Generate compliance reports from LogBook"
    )

    # Time range
    parser.add_argument("--month", help="Month in format YYYY-MM (e.g., 2025-12)")
    parser.add_argument("--since", help="Start date (ISO format)")
    parser.add_argument("--until", help="End date (ISO format)")

    # Output
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--summary-only", action="store_true", help="Show summary only (no details)")
    parser.add_argument("--logbook-dir", default="LogBook", help="LogBook directory")

    args = parser.parse_args()

    # Determine time range
    if args.month:
        # Parse month
        year, month = map(int, args.month.split('-'))
        since = datetime(year, month, 1, tzinfo=timezone.utc)

        # Last day of month
        if month == 12:
            until = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            until = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

    elif args.since and args.until:
        since = datetime.fromisoformat(args.since)
        until = datetime.fromisoformat(args.until)

    else:
        # Default: last 30 days
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=30)

    # Load entries
    logbook_dir = Path(args.logbook_dir)
    all_entries = load_logbook_entries(logbook_dir)

    print(f"Loaded {len(all_entries)} LogBook entries", file=sys.stderr)

    # Filter by time range
    entries = filter_by_time_range(all_entries, since, until)

    print(f"Found {len(entries)} entries in period", file=sys.stderr)
    print("", file=sys.stderr)

    # Generate report
    report = generate_compliance_report(entries, since, until)

    # Output
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        format_report_text(report)

    sys.exit(0)

if __name__ == "__main__":
    main()
