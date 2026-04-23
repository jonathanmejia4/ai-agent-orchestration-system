#!/usr/bin/env python3
"""LogBook query interface (K006).

Structured query tool for LogBook entries. Replaces grep scripts with
semantic queries.

Usage:
    # Query by agent
    python3 tools/logbook_query.py --agent PM

    # Query by action
    python3 tools/logbook_query.py --action stage_promotion

    # Query promotions from Stage3 to Stage4-Golden
    python3 tools/logbook_query.py --action stage_promotion --from-stage Stage3 --to-stage Stage4-Golden

    # Query last 30 days
    python3 tools/logbook_query.py --since 30d

    # Query specific date range
    python3 tools/logbook_query.py --since 2025-12-01 --until 2025-12-26

    # Query by task path
    python3 tools/logbook_query.py --task components/auth

    # Export to JSON
    python3 tools/logbook_query.py --agent PM --output json > pm_actions.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import yaml
except ImportError:
    print("❌ Missing dependency: pyyaml")
    print("Install with: pip install pyyaml")
    sys.exit(2)

def parse_time_delta(delta_str: str) -> datetime:
    """Parse relative time like '7d', '30d', '1h'.

    Returns datetime in the past.
    """
    units = {
        'd': 'days',
        'h': 'hours',
        'm': 'minutes',
    }

    value = int(delta_str[:-1])
    unit = delta_str[-1]

    if unit not in units:
        raise ValueError(f"Invalid time unit: {unit}. Use d (days), h (hours), m (minutes)")

    kwargs = {units[unit]: value}
    return datetime.now(timezone.utc) - timedelta(**kwargs)

def load_logbook_entry(entry_path: Path) -> Optional[Dict[str, Any]]:
    """Load single LogBook entry from YAML."""
    try:
        entry = yaml.safe_load(entry_path.read_text())
        # Add file path to entry for reference
        entry['_file'] = str(entry_path)
        return entry
    except Exception as e:
        print(f"⚠️  Failed to load {entry_path.name}: {e}", file=sys.stderr)
        return None

def find_all_entries(logbook_dir: Path) -> List[Path]:
    """Find all LogBook entries."""
    if not logbook_dir.exists():
        return []

    return sorted(logbook_dir.rglob("*.yaml"))

def filter_entries(entries: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter entries based on query parameters."""
    filtered = entries

    # Filter by agent
    if filters.get('agent'):
        filtered = [e for e in filtered if e.get('agent') == filters['agent']]

    # Filter by action
    if filters.get('action'):
        filtered = [e for e in filtered if e.get('action') == filters['action']]

    # Filter by task path
    if filters.get('task_path'):
        task_filter = filters['task_path']
        filtered = [e for e in filtered
                   if e.get('context', {}).get('task_path', '').find(task_filter) >= 0]

    # Filter by from_stage
    if filters.get('from_stage'):
        filtered = [e for e in filtered
                   if e.get('context', {}).get('from_stage') == filters['from_stage']]

    # Filter by to_stage
    if filters.get('to_stage'):
        filtered = [e for e in filtered
                   if e.get('context', {}).get('to_stage') == filters['to_stage']]

    # Filter by time range
    if filters.get('since') or filters.get('until'):
        time_filtered = []
        for entry in filtered:
            try:
                timestamp_str = entry.get('timestamp')
                if not timestamp_str:
                    continue

                # Parse ISO-8601 timestamp
                entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                # Check since
                if filters.get('since'):
                    if entry_time < filters['since']:
                        continue

                # Check until
                if filters.get('until'):
                    if entry_time > filters['until']:
                        continue

                time_filtered.append(entry)

            except Exception:
                continue

        filtered = time_filtered

    return filtered

def format_output(entries: List[Dict[str, Any]], output_format: str):
    """Format and print entries."""
    if output_format == 'json':
        # Remove internal _file field
        clean_entries = [{k: v for k, v in e.items() if not k.startswith('_')}
                        for e in entries]
        print(json.dumps(clean_entries, indent=2))

    elif output_format == 'compact':
        # One-line per entry
        for entry in entries:
            timestamp = entry.get('timestamp', 'NO_TIMESTAMP')
            agent = entry.get('agent', 'UNKNOWN')
            action = entry.get('action', 'UNKNOWN')
            task = entry.get('context', {}).get('task_path', 'N/A')
            print(f"{timestamp} | {agent:8s} | {action:20s} | {task}")

    elif output_format == 'table':
        # Formatted table
        print(f"{'Timestamp':<25} {'Agent':<10} {'Action':<20} {'Task Path':<30}")
        print("=" * 90)

        for entry in entries:
            timestamp = entry.get('timestamp', 'NO_TIMESTAMP')[:25]
            agent = entry.get('agent', 'UNKNOWN')[:10]
            action = entry.get('action', 'UNKNOWN')[:20]
            task = entry.get('context', {}).get('task_path', 'N/A')[:30]
            print(f"{timestamp:<25} {agent:<10} {action:<20} {task:<30}")

    elif output_format == 'detailed':
        # Full details
        for i, entry in enumerate(entries, 1):
            print(f"\n{'='*60}")
            print(f"Entry {i}/{len(entries)}")
            print(f"{'='*60}")

            print(f"Timestamp: {entry.get('timestamp', 'NO_TIMESTAMP')}")
            print(f"Agent: {entry.get('agent', 'UNKNOWN')}")
            print(f"Action: {entry.get('action', 'UNKNOWN')}")

            context = entry.get('context', {})
            print(f"\nContext:")
            for key, value in context.items():
                print(f"  {key}: {value}")

            if 'metadata' in entry:
                print(f"\nMetadata:")
                for key, value in entry['metadata'].items():
                    print(f"  {key}: {value}")

            print(f"\nFile: {entry.get('_file', 'UNKNOWN')}")

    else:
        print(f"❌ Unknown output format: {output_format}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Query LogBook entries with structured filters"
    )

    # Filters
    parser.add_argument("--agent", choices=["PM", "Planner", "Builder", "Critic"],
                       help="Filter by agent")
    parser.add_argument("--action", help="Filter by action")
    parser.add_argument("--task", dest="task_path", help="Filter by task path (substring match)")
    parser.add_argument("--from-stage", dest="from_stage", help="Filter by source stage")
    parser.add_argument("--to-stage", dest="to_stage", help="Filter by target stage")

    # Time range
    parser.add_argument("--since", help="Start time (ISO date or relative like '7d', '30d')")
    parser.add_argument("--until", help="End time (ISO date)")

    # Output
    parser.add_argument("--output", choices=["json", "compact", "table", "detailed"],
                       default="table", help="Output format")
    parser.add_argument("--limit", type=int, help="Limit number of results")
    parser.add_argument("--logbook-dir", default="LogBook", help="LogBook directory")

    # Stats
    parser.add_argument("--stats", action="store_true", help="Show statistics instead of entries")

    args = parser.parse_args()

    # Parse time filters
    filters = {}

    if args.agent:
        filters['agent'] = args.agent
    if args.action:
        filters['action'] = args.action
    if args.task_path:
        filters['task_path'] = args.task_path
    if args.from_stage:
        filters['from_stage'] = args.from_stage
    if args.to_stage:
        filters['to_stage'] = args.to_stage

    # Parse time range
    if args.since:
        if args.since.endswith(('d', 'h', 'm')):
            filters['since'] = parse_time_delta(args.since)
        else:
            filters['since'] = datetime.fromisoformat(args.since)

    if args.until:
        filters['until'] = datetime.fromisoformat(args.until)

    # Load all entries
    logbook_dir = Path(args.logbook_dir)
    entry_paths = find_all_entries(logbook_dir)

    if not entry_paths:
        print(f"⚠️  No LogBook entries found in {logbook_dir}/", file=sys.stderr)
        sys.exit(0)

    # Load entries
    entries = []
    for path in entry_paths:
        entry = load_logbook_entry(path)
        if entry:
            entries.append(entry)

    print(f"Loaded {len(entries)} LogBook entries", file=sys.stderr)

    # Apply filters
    filtered = filter_entries(entries, filters)

    print(f"Found {len(filtered)} matching entries", file=sys.stderr)
    print("", file=sys.stderr)

    # Apply limit
    if args.limit:
        filtered = filtered[:args.limit]

    # Show stats or entries
    if args.stats:
        # Calculate statistics
        agents = {}
        actions = {}
        stages = {}

        for entry in filtered:
            agent = entry.get('agent', 'UNKNOWN')
            agents[agent] = agents.get(agent, 0) + 1

            action = entry.get('action', 'UNKNOWN')
            actions[action] = actions.get(action, 0) + 1

            to_stage = entry.get('context', {}).get('to_stage')
            if to_stage:
                stages[to_stage] = stages.get(to_stage, 0) + 1

        print(f"=== Statistics for {len(filtered)} entries ===\n")

        print("By Agent:")
        for agent, count in sorted(agents.items(), key=lambda x: -x[1]):
            print(f"  {agent}: {count}")

        print("\nBy Action:")
        for action, count in sorted(actions.items(), key=lambda x: -x[1]):
            print(f"  {action}: {count}")

        if stages:
            print("\nPromotions to Stage:")
            for stage, count in sorted(stages.items()):
                print(f"  {stage}: {count}")

    else:
        # Output entries
        format_output(filtered, args.output)

    sys.exit(0)

if __name__ == "__main__":
    main()
