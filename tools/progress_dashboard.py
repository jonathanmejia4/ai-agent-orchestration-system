#!/usr/bin/env python3
"""
the system Progress Dashboard
Version: 1.0.0
Last Updated: 2025-12-25
Owner: PM
Classification: HIGH - Monitoring Tool

Real-time progress dashboard for PM monitoring.
Provides visibility into task progress, agent activity, and system health.

Usage:
    python tools/progress_dashboard.py show
    python tools/progress_dashboard.py tasks
    python tools/progress_dashboard.py agents
    python tools/progress_dashboard.py timeline
    python tools/progress_dashboard.py export --format html
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

class ProgressDashboard:
    """Real-time progress dashboard for the system."""

    TASK_STAGES = ['draft', 'planned', 'in_progress', 'testing', 'review', 'approved', 'deployed']
    AGENTS = ['pm', 'planner', 'builder', 'critic_orchestrator', 'critic_plan_auditor']

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the progress dashboard."""
        self.project_root = project_root or Path.cwd()
        self.tasks_dir = self.project_root / "tasks"
        self.logbook_dir = self.project_root / "LogBook"
        self.planning_dir = self.project_root / "PLANNING"
        self.health_dir = self.project_root / ".health"
        self.heartbeat_dir = self.project_root / ".heartbeats"

    def get_task_progress(self) -> Dict[str, Any]:
        """Get progress statistics for all tasks."""
        if not self.tasks_dir.exists():
            return {'total': 0, 'by_stage': {}, 'tasks': []}

        tasks = []
        by_stage = {stage: 0 for stage in self.TASK_STAGES}

        for task_dir in self.tasks_dir.iterdir():
            if not task_dir.is_dir():
                continue

            manifest_file = task_dir / "task.yaml"
            if not manifest_file.exists():
                continue

            with open(manifest_file, 'r') as f:
                manifest = yaml.safe_load(f) or {}

            task_id = manifest.get('task_id', task_dir.name)
            status = manifest.get('status', 'draft')
            stage = manifest.get('stage', status)

            if stage in by_stage:
                by_stage[stage] += 1

            tasks.append({
                'task_id': task_id,
                'name': manifest.get('name', task_id),
                'stage': stage,
                'status': status,
                'version': manifest.get('version', '0.0.0'),
                'last_modified': self._get_last_modified(task_dir),
                'has_tests': (task_dir / "tests").exists(),
                'has_src': (task_dir / "src").exists()
            })

        # Calculate completion percentage
        total = len(tasks)
        completed = by_stage.get('approved', 0) + by_stage.get('deployed', 0)
        completion_pct = (completed / total * 100) if total > 0 else 0

        return {
            'total': total,
            'completed': completed,
            'completion_percent': round(completion_pct, 1),
            'by_stage': by_stage,
            'tasks': sorted(tasks, key=lambda b: b['task_id'])
        }

    def _get_last_modified(self, directory: Path) -> Optional[str]:
        """Get last modification time for directory."""
        try:
            latest = max(
                (f.stat().st_mtime for f in directory.rglob('*') if f.is_file()),
                default=0
            )
            if latest > 0:
                return datetime.fromtimestamp(latest).isoformat() + "Z"
        except Exception:
            pass
        return None

    def get_agent_activity(self) -> Dict[str, Any]:
        """Get activity statistics for all agents."""
        activities = {}

        for agent in self.AGENTS:
            agent_logbook = self.logbook_dir / agent

            activity = {
                'agent_id': agent,
                'total_entries': 0,
                'today_entries': 0,
                'last_activity': None,
                'heartbeat_status': 'unknown',
                'is_active': False
            }

            # Count LogBook entries
            if agent_logbook.exists():
                entries = list(agent_logbook.glob("*.yaml")) + list(agent_logbook.glob("*.md"))
                activity['total_entries'] = len(entries)

                # Count today's entries
                today = datetime.utcnow().date()
                today_count = 0
                last_activity = None

                for entry in entries:
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                    if mtime.date() == today:
                        today_count += 1
                    if last_activity is None or mtime > last_activity:
                        last_activity = mtime

                activity['today_entries'] = today_count
                if last_activity:
                    activity['last_activity'] = last_activity.isoformat() + "Z"

            # Check heartbeat
            heartbeat_file = self.heartbeat_dir / f"{agent}.heartbeat"
            if heartbeat_file.exists():
                with open(heartbeat_file, 'r') as f:
                    hb = yaml.safe_load(f)
                if hb:
                    ts = datetime.fromisoformat(hb['timestamp'].replace('Z', '+00:00'))
                    age = (datetime.utcnow().replace(tzinfo=ts.tzinfo) - ts).total_seconds()
                    if age < 120:
                        activity['heartbeat_status'] = 'active'
                        activity['is_active'] = True
                    elif age < 300:
                        activity['heartbeat_status'] = 'stale'
                    else:
                        activity['heartbeat_status'] = 'inactive'

            activities[agent] = activity

        return activities

    def get_work_orders_progress(self) -> Dict[str, Any]:
        """Get progress of work orders."""
        wo_dir = self.planning_dir / "work_orders"

        if not wo_dir.exists():
            return {'total': 0, 'by_status': {}, 'work_orders': []}

        work_orders = []
        by_status = {}

        for wo_file in wo_dir.glob("**/*.yaml"):
            with open(wo_file, 'r') as f:
                wo = yaml.safe_load(f) or {}

            status = wo.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1

            work_orders.append({
                'work_order_id': wo.get('work_order_id', wo_file.stem),
                'title': wo.get('title', wo.get('objective', 'Untitled')),
                'status': status,
                'priority': wo.get('priority', 'normal'),
                'created_at': wo.get('created_at'),
                'assigned_to': wo.get('assigned_to')
            })

        return {
            'total': len(work_orders),
            'by_status': by_status,
            'work_orders': work_orders
        }

    def get_action_plans_progress(self) -> Dict[str, Any]:
        """Get progress of action plans."""
        ap_dir = self.planning_dir / "action_plans"

        if not ap_dir.exists():
            return {'total': 0, 'by_status': {}, 'action_plans': []}

        action_plans = []
        by_status = {}

        for status_dir in ['active', 'completed', 'cancelled']:
            status_path = ap_dir / status_dir
            if not status_path.exists():
                continue

            for ap_file in status_path.glob("*.yaml"):
                with open(ap_file, 'r') as f:
                    ap = yaml.safe_load(f) or {}

                plan_status = ap.get('status', status_dir)
                by_status[plan_status] = by_status.get(plan_status, 0) + 1

                # Calculate action progress
                actions = ap.get('actions', [])
                completed_actions = len([a for a in actions if a.get('status') == 'completed'])
                total_actions = len(actions)

                action_plans.append({
                    'plan_id': ap.get('plan_id', ap_file.stem),
                    'status': plan_status,
                    'objective': ap.get('objective', '')[:50],
                    'actions_completed': completed_actions,
                    'actions_total': total_actions,
                    'progress_percent': round(completed_actions / total_actions * 100, 1) if total_actions > 0 else 0
                })

        return {
            'total': len(action_plans),
            'by_status': by_status,
            'action_plans': action_plans
        }

    def get_recent_activity(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent activity across the system."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        activities = []

        # Check LogBook entries
        for agent in self.AGENTS:
            agent_logbook = self.logbook_dir / agent
            if not agent_logbook.exists():
                continue

            for entry_file in agent_logbook.glob("*.yaml"):
                mtime = datetime.fromtimestamp(entry_file.stat().st_mtime)
                if mtime > cutoff:
                    activities.append({
                        'timestamp': mtime.isoformat() + "Z",
                        'type': 'logbook',
                        'agent': agent,
                        'file': str(entry_file.relative_to(self.project_root)),
                        'description': f"LogBook entry by {agent}"
                    })

        # Check task changes
        for task_dir in self.tasks_dir.iterdir():
            if not task_dir.is_dir():
                continue

            for src_file in task_dir.rglob("*"):
                if not src_file.is_file():
                    continue
                mtime = datetime.fromtimestamp(src_file.stat().st_mtime)
                if mtime > cutoff:
                    activities.append({
                        'timestamp': mtime.isoformat() + "Z",
                        'type': 'task_change',
                        'task': task_dir.name,
                        'file': str(src_file.relative_to(self.project_root)),
                        'description': f"Change in {task_dir.name}"
                    })

        # Sort by timestamp descending
        activities.sort(key=lambda a: a['timestamp'], reverse=True)

        return activities[:100]  # Limit to 100 entries

    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get system health summary."""
        health_report_file = self.health_dir / "history"

        # Get latest health data if available
        agents_healthy = 0
        agents_unhealthy = 0
        active_alerts = 0

        alerts_file = self.health_dir / "alerts.yaml"
        if alerts_file.exists():
            with open(alerts_file, 'r') as f:
                alerts = yaml.safe_load(f) or []
            active_alerts = len([a for a in alerts if not a.get('acknowledged', False)])

        # Check heartbeats for quick health
        for agent in self.AGENTS:
            heartbeat_file = self.heartbeat_dir / f"{agent}.heartbeat"
            if heartbeat_file.exists():
                with open(heartbeat_file, 'r') as f:
                    hb = yaml.safe_load(f)
                if hb:
                    ts = datetime.fromisoformat(hb['timestamp'].replace('Z', '+00:00'))
                    age = (datetime.utcnow().replace(tzinfo=ts.tzinfo) - ts).total_seconds()
                    if age < 300:
                        agents_healthy += 1
                    else:
                        agents_unhealthy += 1
                else:
                    agents_unhealthy += 1
            else:
                agents_unhealthy += 1

        return {
            'agents_healthy': agents_healthy,
            'agents_unhealthy': agents_unhealthy,
            'active_alerts': active_alerts,
            'overall_status': 'healthy' if agents_unhealthy == 0 and active_alerts == 0 else 'degraded'
        }

    def generate_dashboard(self) -> Dict[str, Any]:
        """Generate complete dashboard data."""
        return {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'tasks': self.get_task_progress(),
            'agents': self.get_agent_activity(),
            'work_orders': self.get_work_orders_progress(),
            'action_plans': self.get_action_plans_progress(),
            'health': self.get_system_health_summary(),
            'recent_activity': self.get_recent_activity(24)[:20]
        }

    def render_text_dashboard(self, data: Dict[str, Any]) -> str:
        """Render dashboard as text."""
        lines = []
        lines.append("=" * 70)
        lines.append("the system PROGRESS DASHBOARD")
        lines.append(f"Generated: {data['timestamp']}")
        lines.append("=" * 70)

        # Task Progress
        tasks = data['tasks']
        lines.append(f"\nTASK PROGRESS: {tasks['completed']}/{tasks['total']} ({tasks['completion_percent']}%)")
        lines.append("-" * 40)
        for stage in self.TASK_STAGES:
            count = tasks['by_stage'].get(stage, 0)
            bar = '#' * min(count, 20)
            lines.append(f"  {stage:<12} {count:>3} {bar}")

        # Agent Activity
        lines.append(f"\nAGENT ACTIVITY:")
        lines.append("-" * 40)
        for agent_id, activity in data['agents'].items():
            status = activity['heartbeat_status'].upper()[:3]
            today = activity['today_entries']
            lines.append(f"  {agent_id:<20} [{status}] Today: {today}")

        # Work Orders
        wo = data['work_orders']
        lines.append(f"\nWORK ORDERS: {wo['total']} total")
        lines.append("-" * 40)
        for status, count in wo['by_status'].items():
            lines.append(f"  {status:<15} {count:>3}")

        # Action Plans
        ap = data['action_plans']
        lines.append(f"\nACTION PLANS: {ap['total']} total")
        lines.append("-" * 40)
        for status, count in ap['by_status'].items():
            lines.append(f"  {status:<15} {count:>3}")

        # Health
        health = data['health']
        lines.append(f"\nSYSTEM HEALTH: {health['overall_status'].upper()}")
        lines.append("-" * 40)
        lines.append(f"  Agents healthy:   {health['agents_healthy']}")
        lines.append(f"  Agents unhealthy: {health['agents_unhealthy']}")
        lines.append(f"  Active alerts:    {health['active_alerts']}")

        # Recent Activity
        lines.append(f"\nRECENT ACTIVITY (last 24h):")
        lines.append("-" * 40)
        for activity in data['recent_activity'][:10]:
            ts = activity['timestamp'][:16]
            desc = activity['description'][:40]
            lines.append(f"  {ts} {desc}")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)

    def render_html_dashboard(self, data: Dict[str, Any]) -> str:
        """Render dashboard as HTML."""
        tasks = data['tasks']
        health = data['health']

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>the system Progress Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .dashboard {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card h2 {{ margin-top: 0; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        .metric {{ display: inline-block; text-align: center; padding: 15px 25px; margin: 5px; background: #e8f5e9; border-radius: 8px; }}
        .metric .value {{ font-size: 2em; font-weight: bold; color: #2e7d32; }}
        .metric .label {{ color: #666; font-size: 0.9em; }}
        .progress-bar {{ background: #ddd; border-radius: 10px; height: 20px; overflow: hidden; }}
        .progress-fill {{ background: linear-gradient(90deg, #4CAF50, #8BC34A); height: 100%; transition: width 0.3s; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f9f9f9; }}
        .status-healthy {{ color: #4CAF50; }}
        .status-degraded {{ color: #FF9800; }}
        .status-unhealthy {{ color: #f44336; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; }}
        .badge-active {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-stale {{ background: #fff3e0; color: #e65100; }}
        .badge-inactive {{ background: #ffebee; color: #c62828; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <h1>the system Progress Dashboard</h1>
        <p>Generated: {data['timestamp']}</p>

        <div class="card">
            <h2>Task Progress</h2>
            <div class="metric">
                <div class="value">{tasks['completion_percent']}%</div>
                <div class="label">Complete</div>
            </div>
            <div class="metric">
                <div class="value">{tasks['total']}</div>
                <div class="label">Total Tasks</div>
            </div>
            <div class="metric">
                <div class="value">{tasks['completed']}</div>
                <div class="label">Completed</div>
            </div>
            <div class="progress-bar" style="margin-top: 15px;">
                <div class="progress-fill" style="width: {tasks['completion_percent']}%;"></div>
            </div>
        </div>

        <div class="card">
            <h2>Agent Activity</h2>
            <table>
                <tr><th>Agent</th><th>Status</th><th>Today</th><th>Total</th></tr>
"""
        for agent_id, activity in data['agents'].items():
            badge_class = f"badge-{activity['heartbeat_status']}"
            html += f"""                <tr>
                    <td>{agent_id}</td>
                    <td><span class="badge {badge_class}">{activity['heartbeat_status']}</span></td>
                    <td>{activity['today_entries']}</td>
                    <td>{activity['total_entries']}</td>
                </tr>
"""
        html += """            </table>
        </div>

        <div class="card">
            <h2>System Health</h2>
"""
        status_class = f"status-{health['overall_status']}"
        html += f"""            <p class="{status_class}" style="font-size: 1.5em; font-weight: bold;">
                Status: {health['overall_status'].upper()}
            </p>
            <div class="metric">
                <div class="value">{health['agents_healthy']}</div>
                <div class="label">Healthy Agents</div>
            </div>
            <div class="metric">
                <div class="value">{health['active_alerts']}</div>
                <div class="label">Active Alerts</div>
            </div>
        </div>

        <div class="card">
            <h2>Recent Activity</h2>
            <table>
                <tr><th>Time</th><th>Type</th><th>Description</th></tr>
"""
        for activity in data['recent_activity'][:15]:
            html += f"""                <tr>
                    <td>{activity['timestamp'][:19]}</td>
                    <td>{activity['type']}</td>
                    <td>{activity['description'][:50]}</td>
                </tr>
"""
        html += """            </table>
        </div>
    </div>
</body>
</html>
"""
        return html

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Progress Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Show command
    show_parser = subparsers.add_parser('show', help='Show full dashboard')
    show_parser.add_argument('--format', choices=['text', 'json', 'yaml'], default='text')

    # Tasks command
    tasks_parser = subparsers.add_parser('tasks', help='Show task progress')
    tasks_parser.add_argument('--format', choices=['text', 'json', 'yaml'], default='text')

    # Agents command
    agents_parser = subparsers.add_parser('agents', help='Show agent activity')
    agents_parser.add_argument('--format', choices=['text', 'json', 'yaml'], default='text')

    # Timeline command
    timeline_parser = subparsers.add_parser('timeline', help='Show recent activity')
    timeline_parser.add_argument('--hours', type=int, default=24, help='Hours to look back')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export dashboard')
    export_parser.add_argument('--format', choices=['html', 'json', 'yaml'], default='html')
    export_parser.add_argument('--output', '-o', help='Output file')

    args = parser.parse_args()

    if not args.command:
        # Default to show
        args.command = 'show'
        args.format = 'text'

    dashboard = ProgressDashboard()

    try:
        if args.command == 'show':
            data = dashboard.generate_dashboard()
            if args.format == 'text':
                print(dashboard.render_text_dashboard(data))
            elif args.format == 'json':
                print(json.dumps(data, indent=2))
            else:
                print(yaml.dump(data, default_flow_style=False))

        elif args.command == 'tasks':
            data = dashboard.get_task_progress()
            if args.format == 'text':
                print(f"\nTask Progress: {data['completed']}/{data['total']} ({data['completion_percent']}%)")
                print("-" * 40)
                for task in data['tasks']:
                    tests = 'T' if task['has_tests'] else '-'
                    src = 'S' if task['has_src'] else '-'
                    print(f"  {task['task_id']:<20} {task['stage']:<12} [{tests}{src}]")
            elif args.format == 'json':
                print(json.dumps(data, indent=2))
            else:
                print(yaml.dump(data, default_flow_style=False))

        elif args.command == 'agents':
            data = dashboard.get_agent_activity()
            if args.format == 'text':
                print("\nAgent Activity")
                print("-" * 50)
                for agent_id, activity in data.items():
                    status = activity['heartbeat_status']
                    print(f"  {agent_id:<20} [{status:<8}] Today: {activity['today_entries']}")
            elif args.format == 'json':
                print(json.dumps(data, indent=2))
            else:
                print(yaml.dump(data, default_flow_style=False))

        elif args.command == 'timeline':
            activities = dashboard.get_recent_activity(args.hours)
            print(f"\nRecent Activity (last {args.hours} hours)")
            print("-" * 60)
            for activity in activities[:50]:
                ts = activity['timestamp'][:16]
                print(f"  {ts}  {activity['description']}")

        elif args.command == 'export':
            data = dashboard.generate_dashboard()

            if args.format == 'html':
                output = dashboard.render_html_dashboard(data)
            elif args.format == 'json':
                output = json.dumps(data, indent=2)
            else:
                output = yaml.dump(data, default_flow_style=False)

            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
                print(f"Dashboard exported to {args.output}")
            else:
                print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
