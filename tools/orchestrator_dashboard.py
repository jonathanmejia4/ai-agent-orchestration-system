#!/usr/bin/env python3
"""
the system Orchestrator Dashboard (Z-24)
=================================

Visual dashboard for monitoring orchestrator status.

Usage:
    python3 tools/orchestrator_dashboard.py           # Basic view
    python3 tools/orchestrator_dashboard.py --live    # Live updating
    python3 tools/orchestrator_dashboard.py --json    # JSON output
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not installed. Run: pip3 install pyyaml")

STATE_FILE = Path("LogBook/orchestrator/ORCHESTRATOR_STATE.yaml")
HEARTBEAT_FILE = Path("LogBook/orchestrator/HEARTBEAT")
TASKS_DIR = Path("LogBook/orchestrator/tasks")

def load_state():
    """Load orchestrator state from file"""
    if not YAML_AVAILABLE or not STATE_FILE.exists():
        return None
    with open(STATE_FILE) as f:
        return yaml.safe_load(f)

def get_heartbeat():
    """Get last heartbeat time"""
    if HEARTBEAT_FILE.exists():
        try:
            return HEARTBEAT_FILE.read_text().strip()
        except Exception:
            return None
    return None

def count_tasks():
    """Count task execution logs"""
    if TASKS_DIR.exists():
        return len(list(TASKS_DIR.glob("TASK-*.yaml")))
    return 0

def render_box(title, content, width=56):
    """Render a bordered box"""
    lines = []
    lines.append(f"+{'-' * (width - 2)}+")
    lines.append(f"|{title.center(width - 2)}|")
    lines.append(f"+{'-' * (width - 2)}+")
    for line in content:
        lines.append(f"| {line:<{width - 4}} |")
    lines.append(f"+{'-' * (width - 2)}+")
    return "\n".join(lines)

def render_basic(state):
    """Render basic dashboard view"""
    if not state:
        print("\nNo orchestrator session found.")
        print("Start with: python3 tools/orchestrator.py --agent pm --task 'test'")
        return

    budget_used = state.get('total_cost_usd', 0)
    budget_limit = state.get('budget_limit_usd', 10)
    budget_pct = (budget_used / budget_limit * 100) if budget_limit > 0 else 0
    budget_bar = "#" * int(budget_pct / 5) + "-" * (20 - int(budget_pct / 5))

    heartbeat = get_heartbeat()
    task_count = count_tasks()

    content = [
        "",
        f"Session:    {state.get('session_id', 'N/A')}",
        f"Started:    {state.get('started_at', 'N/A')[:19]}",
        f"Checkpoint: {state.get('last_checkpoint', 'N/A')[:19]}",
        "",
        f"Total Runs:   {state.get('total_runs', 0):>10}",
        f"Total Tokens: {state.get('total_tokens', 0):>10,}",
        f"Tasks Run:   {task_count:>10}",
        "",
        f"Budget Used: ${budget_used:>8.4f} / ${budget_limit:.2f}",
        f"[{budget_bar}] {budget_pct:.1f}%",
        f"Remaining:   ${budget_limit - budget_used:>8.4f}",
        "",
        f"Heartbeat: {heartbeat or 'N/A'}",
        "",
    ]

    print("\n" + render_box("the system ORCHESTRATOR DASHBOARD", content))

def render_detailed(state):
    """Render detailed view with recent runs"""
    render_basic(state)

    if not state:
        return

    completed = state.get('completed_runs', [])
    if completed:
        print("\nRecent Runs (last 10):")
        print("-" * 60)
        for run in completed[-10:]:
            status = run.get('status', 'unknown')
            status_icon = "+" if status == 'completed' else "x" if status == 'error' else "?"
            print(f"  [{status_icon}] {run.get('agent', 'N/A'):<15} "
                  f"${run.get('cost_usd', 0):.4f} - {run.get('task', '')[:30]}")

def render_live(refresh_interval=5):
    """Render live updating dashboard"""
    try:
        while True:
            os.system('clear' if os.name == 'posix' else 'cls')
            state = load_state()
            render_basic(state)
            print(f"\n  [Live mode - refreshing every {refresh_interval}s, Ctrl+C to exit]")
            time.sleep(refresh_interval)
    except KeyboardInterrupt:
        print("\nExiting live mode.")

def output_json(state):
    """Output state as JSON"""
    if state:
        print(json.dumps(state, indent=2, default=str))
    else:
        print(json.dumps({"error": "No session found"}))

def main():
    parser = argparse.ArgumentParser(
        description="the system Orchestrator Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tools/orchestrator_dashboard.py            # Basic view
  python3 tools/orchestrator_dashboard.py --detailed # Show recent runs
  python3 tools/orchestrator_dashboard.py --live     # Auto-refresh
  python3 tools/orchestrator_dashboard.py --json     # JSON output
"""
    )

    parser.add_argument("--detailed", "-d", action="store_true",
                        help="Show detailed view with recent runs")
    parser.add_argument("--live", "-l", action="store_true",
                        help="Live updating view (refreshes every 5s)")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--refresh", "-r", type=int, default=5,
                        help="Refresh interval for live mode (default: 5s)")

    args = parser.parse_args()

    if not YAML_AVAILABLE:
        print("Error: PyYAML required. Run: pip3 install pyyaml")
        return 1

    state = load_state()

    if args.json:
        output_json(state)
    elif args.live:
        render_live(args.refresh)
    elif args.detailed:
        render_detailed(state)
    else:
        render_basic(state)

    return 0

if __name__ == "__main__":
    exit(main())
