#!/usr/bin/env python3
"""
Time Box Monitor - Tracks and enforces work order time limits

Monitors Builder work order execution against time_box constraints and
triggers escalations at threshold checkpoints (75%, 80%, 90%, 100%).

Usage:
    python3 tools/time_box_monitor.py --check-all
    python3 tools/time_box_monitor.py --work-order WO-20251230-001
    python3 tools/time_box_monitor.py --monitor --interval 60
    python3 tools/time_box_monitor.py --help

Exit Codes:
    0 - All time boxes within limits
    1 - Time box threshold exceeded (80%+)
    2 - Error (missing files, invalid arguments)

Referenced in:
    - .claude/agents/Builder.md:434-466
    - PLANNING/ESCALATION_PROTOCOL.md

Resolves: J-42
Author: System
Created: 2025-12-30
"""

import argparse
import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# Optional YAML support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

class TimeBoxStatus(Enum):
    """Time box status levels per Builder.md:455-462"""
    UNKNOWN = "unknown"
    START = "start"          # 0%
    QUARTER = "quarter"      # 25%
    HALF = "half"            # 50%
    WARNING = "warning"      # 80% - MANDATORY ESCALATION
    DEADLINE = "deadline"    # 100% - HARD STOP
    OVERRUN = "overrun"      # >100%

@dataclass
class TimeBoxInfo:
    """Time box tracking information per Builder.md:445-451"""
    work_order_id: str
    time_box: str                    # ISO 8601 duration (e.g., PT4H)
    started_at: Optional[datetime] = None
    elapsed: Optional[timedelta] = None
    remaining: Optional[timedelta] = None
    percent_complete: float = 0.0
    status: TimeBoxStatus = TimeBoxStatus.UNKNOWN
    task_id: Optional[str] = None
    agent: str = "builder"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'work_order_id': self.work_order_id,
            'task_id': self.task_id,
            'time_box': self.time_box,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'elapsed': self._format_duration(self.elapsed) if self.elapsed else None,
            'remaining': self._format_duration(self.remaining) if self.remaining else None,
            'percent_complete': round(self.percent_complete, 1),
            'status': self.status.value,
            'agent': self.agent
        }

    @staticmethod
    def _format_duration(td: timedelta) -> str:
        """Format timedelta as ISO 8601 duration."""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"PT{hours}H{minutes}M" if minutes else f"PT{hours}H"
        return f"PT{minutes}M"

@dataclass
class EscalationRecord:
    """Escalation record per Builder.md:472-479"""
    id: str
    category: str = "timeout"
    severity: str = "medium"
    title: str = ""
    description: str = ""
    work_order_id: str = ""
    percent_elapsed: float = 0.0
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category,
            'severity': self.severity,
            'title': self.title,
            'description': self.description,
            'work_order_id': self.work_order_id,
            'percent_elapsed': self.percent_elapsed,
            'recommended_action': self.recommended_action
        }

class TimeBoxMonitor:
    """Monitors and enforces time box constraints."""

    # Threshold checkpoints per Builder.md:455-462
    THRESHOLDS = {
        'quarter': 25,
        'half': 50,
        'warning': 80,      # MANDATORY ESCALATION
        'deadline': 100,
        'overrun': float('inf')
    }

    # ISO 8601 duration pattern
    DURATION_PATTERN = re.compile(
        r'^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$'
    )

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.wo_queue_paths = [
            self.repo_root / "LogBook" / "pm" / "WO_QUEUE.yaml",
            self.repo_root / "PLANNING" / "WORK_ORDER_QUEUE.yaml"
        ]
        self.builder_state_path = self.repo_root / "LogBook" / "builder" / "STATE.md"
        self.escalation_dir = self.repo_root / "LogBook" / "pm" / "escalations"

    def parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """Parse ISO 8601 duration string to timedelta."""
        if not duration_str:
            return None

        match = self.DURATION_PATTERN.match(duration_str)
        if not match:
            return None

        parts = match.groupdict()
        return timedelta(
            days=int(parts['days'] or 0),
            hours=int(parts['hours'] or 0),
            minutes=int(parts['minutes'] or 0),
            seconds=int(parts['seconds'] or 0)
        )

    def get_status_for_percent(self, percent: float) -> TimeBoxStatus:
        """Determine status based on percentage complete."""
        if percent <= 0:
            return TimeBoxStatus.START
        elif percent < 25:
            return TimeBoxStatus.START
        elif percent < 50:
            return TimeBoxStatus.QUARTER
        elif percent < 80:
            return TimeBoxStatus.HALF
        elif percent < 100:
            return TimeBoxStatus.WARNING
        elif percent == 100:
            return TimeBoxStatus.DEADLINE
        else:
            return TimeBoxStatus.OVERRUN

    def check_work_order(self, work_order: Dict[str, Any]) -> TimeBoxInfo:
        """Check time box status for a single work order."""
        wo_id = work_order.get('id') or work_order.get('work_order_id', 'unknown')
        time_box_str = work_order.get('time_box', 'PT4H')
        task_id = work_order.get('task_id')
        started_at_str = work_order.get('started_at')

        info = TimeBoxInfo(
            work_order_id=wo_id,
            time_box=time_box_str,
            task_id=task_id
        )

        # Parse time box duration
        time_box_td = self.parse_duration(time_box_str)
        if not time_box_td:
            info.status = TimeBoxStatus.UNKNOWN
            return info

        # Get started_at from work order or state file
        if started_at_str:
            try:
                info.started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
            except ValueError:
                pass

        # If no started_at, check if work order is in progress
        if not info.started_at:
            status = work_order.get('status', '')
            if status in ('IN_PROGRESS', 'ACTIVE', 'ASSIGNED'):
                # Try to get from builder state
                info.started_at = self._get_started_from_state(wo_id)

        if not info.started_at:
            # Work order not started yet
            info.status = TimeBoxStatus.START
            return info

        # Calculate elapsed time
        now = datetime.now(info.started_at.tzinfo) if info.started_at.tzinfo else datetime.now()
        info.elapsed = now - info.started_at
        info.remaining = time_box_td - info.elapsed
        if info.remaining < timedelta(0):
            info.remaining = timedelta(0)

        # Calculate percentage
        info.percent_complete = (info.elapsed.total_seconds() / time_box_td.total_seconds()) * 100
        info.status = self.get_status_for_percent(info.percent_complete)

        return info

    def _get_started_from_state(self, work_order_id: str) -> Optional[datetime]:
        """Try to get started_at from builder STATE.md."""
        if not self.builder_state_path.exists():
            return None

        try:
            content = self.builder_state_path.read_text()
            # Look for work order and started timestamp
            if work_order_id in content:
                # Simple pattern matching for started_at
                pattern = rf'{work_order_id}.*?started[_\s]*(?:at)?[:\s]*(\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}:\d{{2}}:\d{{2}})'
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    return datetime.fromisoformat(match.group(1))
        except Exception:
            pass

        return None

    def check_all_active_work_orders(self) -> List[TimeBoxInfo]:
        """Check time boxes for all active work orders."""
        results = []

        if not HAS_YAML:
            print("WARNING: pyyaml not available, using empty queue", file=sys.stderr)
            return results

        for queue_path in self.wo_queue_paths:
            if not queue_path.exists():
                continue

            try:
                with open(queue_path) as f:
                    data = yaml.safe_load(f)
                work_orders = data.get('work_orders', [])

                for wo in work_orders:
                    status = wo.get('status', '')
                    if status in ('IN_PROGRESS', 'ACTIVE', 'ASSIGNED'):
                        info = self.check_work_order(wo)
                        results.append(info)
            except Exception as e:
                print(f"WARNING: Failed to read {queue_path}: {e}", file=sys.stderr)

        return results

    def create_escalation(self, info: TimeBoxInfo) -> EscalationRecord:
        """Create escalation record for time box warning."""
        now = datetime.now()
        esc_id = f"ESC-{now.strftime('%Y-%m-%d')}-{abs(hash(info.work_order_id)) % 10000:04d}"

        severity = "medium"
        if info.percent_complete >= 100:
            severity = "high"
        elif info.percent_complete >= 90:
            severity = "high"

        recommended = "Extend time box" if info.percent_complete < 100 else "Hard stop - PM decision required"

        return EscalationRecord(
            id=esc_id,
            category="timeout",
            severity=severity,
            title=f"Time Box {int(info.percent_complete)}% - {info.work_order_id}",
            description=f"Work order {info.work_order_id} has reached {info.percent_complete:.1f}% of time box ({info.time_box}).",
            work_order_id=info.work_order_id,
            percent_elapsed=info.percent_complete,
            recommended_action=recommended
        )

    def save_escalation(self, escalation: EscalationRecord) -> bool:
        """Save escalation to LogBook/pm/escalations/."""
        self.escalation_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{escalation.id}.yaml"
        filepath = self.escalation_dir / filename

        try:
            if HAS_YAML:
                with open(filepath, 'w') as f:
                    yaml.dump(escalation.to_dict(), f, default_flow_style=False)
            else:
                with open(filepath, 'w') as f:
                    json.dump(escalation.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"ERROR: Failed to save escalation: {e}", file=sys.stderr)
            return False

def print_status(info: TimeBoxInfo, verbose: bool = False):
    """Print time box status."""
    status_colors = {
        TimeBoxStatus.START: "\033[92m",      # Green
        TimeBoxStatus.QUARTER: "\033[92m",    # Green
        TimeBoxStatus.HALF: "\033[93m",       # Yellow
        TimeBoxStatus.WARNING: "\033[91m",    # Red
        TimeBoxStatus.DEADLINE: "\033[91m",   # Red
        TimeBoxStatus.OVERRUN: "\033[91m",    # Red
        TimeBoxStatus.UNKNOWN: "\033[90m"     # Gray
    }
    reset = "\033[0m"
    color = status_colors.get(info.status, reset)

    status_icon = "✓" if info.status in (TimeBoxStatus.START, TimeBoxStatus.QUARTER, TimeBoxStatus.HALF) else "⚠"
    if info.status in (TimeBoxStatus.DEADLINE, TimeBoxStatus.OVERRUN):
        status_icon = "✗"

    print(f"\n{color}{status_icon} {info.work_order_id}{reset}")
    print(f"  Time Box: {info.time_box}")
    print(f"  Status: {color}{info.status.value.upper()}{reset} ({info.percent_complete:.1f}%)")

    if info.elapsed:
        print(f"  Elapsed: {info._format_duration(info.elapsed)}")
    if info.remaining and info.status != TimeBoxStatus.OVERRUN:
        print(f"  Remaining: {info._format_duration(info.remaining)}")
    if info.task_id:
        print(f"  Task: {info.task_id}")

def main():
    parser = argparse.ArgumentParser(
        description="Monitor and enforce work order time box constraints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Time Box Thresholds (per Builder.md):
  0%    - Start: Record started_at
  25%   - Quarter: Internal progress check
  50%   - Half: Assess feasibility
  80%   - Warning: MANDATORY ESCALATION to PM
  100%  - Deadline: HARD STOP
  >100% - Overrun: Only continue with PM approval

Examples:
  Check all active work orders:
    %(prog)s --check-all

  Check specific work order:
    %(prog)s --work-order WO-20251230-001

  Monitor continuously:
    %(prog)s --monitor --interval 300
        """
    )

    parser.add_argument("--check-all", action="store_true",
                        help="Check all active work orders in queue")
    parser.add_argument("--work-order", "-w", metavar="ID",
                        help="Check specific work order by ID")
    parser.add_argument("--monitor", action="store_true",
                        help="Run in continuous monitoring mode")
    parser.add_argument("--interval", type=int, default=300,
                        help="Monitoring interval in seconds (default: 300)")
    parser.add_argument("--repo-root", default=".",
                        help="Repository root path (default: current directory)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed output")
    parser.add_argument("--escalate", action="store_true",
                        help="Create escalation records for warnings")
    parser.add_argument("--check-time-boxes", action="store_true",
                        help="Alias for --check-all (for CI integration)")

    args = parser.parse_args()

    # --check-time-boxes is alias for --check-all
    if args.check_time_boxes:
        args.check_all = True

    if not args.check_all and not args.work_order and not args.monitor:
        parser.print_help()
        return 2

    monitor = TimeBoxMonitor(args.repo_root)

    if args.monitor:
        # Continuous monitoring mode
        import time
        print(f"Starting time box monitor (interval: {args.interval}s)")
        print("Press Ctrl+C to stop")

        while True:
            try:
                results = monitor.check_all_active_work_orders()
                if results:
                    print(f"\n{'='*50}")
                    print(f"Time Box Check - {datetime.now().isoformat()}")
                    print(f"{'='*50}")
                    for info in results:
                        print_status(info, args.verbose)
                        if args.escalate and info.status in (TimeBoxStatus.WARNING,
                                                              TimeBoxStatus.DEADLINE,
                                                              TimeBoxStatus.OVERRUN):
                            escalation = monitor.create_escalation(info)
                            if monitor.save_escalation(escalation):
                                print(f"  → Escalation created: {escalation.id}")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nMonitor stopped")
                break

        return 0

    # Single check mode
    results = []

    if args.check_all:
        results = monitor.check_all_active_work_orders()
    elif args.work_order:
        # Find specific work order
        if HAS_YAML:
            for queue_path in monitor.wo_queue_paths:
                if not queue_path.exists():
                    continue
                try:
                    with open(queue_path) as f:
                        data = yaml.safe_load(f)
                    for wo in data.get('work_orders', []):
                        wo_id = wo.get('id') or wo.get('work_order_id')
                        if wo_id == args.work_order:
                            info = monitor.check_work_order(wo)
                            results.append(info)
                            break
                except Exception:
                    continue

        if not results:
            print(f"Work order {args.work_order} not found in queue", file=sys.stderr)
            return 2

    # Output results
    if args.json:
        output = {
            "results": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "warning": sum(1 for r in results if r.status == TimeBoxStatus.WARNING),
                "deadline": sum(1 for r in results if r.status == TimeBoxStatus.DEADLINE),
                "overrun": sum(1 for r in results if r.status == TimeBoxStatus.OVERRUN)
            }
        }
        print(json.dumps(output, indent=2))
    else:
        if not results:
            print("No active work orders found")
        else:
            for info in results:
                print_status(info, args.verbose)

                # Create escalations if requested
                if args.escalate and info.status in (TimeBoxStatus.WARNING,
                                                      TimeBoxStatus.DEADLINE,
                                                      TimeBoxStatus.OVERRUN):
                    escalation = monitor.create_escalation(info)
                    if monitor.save_escalation(escalation):
                        print(f"  → Escalation created: {escalation.id}")

            print(f"\n{'='*40}")
            warnings = sum(1 for r in results if r.status == TimeBoxStatus.WARNING)
            deadlines = sum(1 for r in results if r.status == TimeBoxStatus.DEADLINE)
            overruns = sum(1 for r in results if r.status == TimeBoxStatus.OVERRUN)

            if warnings + deadlines + overruns > 0:
                print(f"⚠ Alerts: {warnings} warnings, {deadlines} deadlines, {overruns} overruns")
            else:
                print("✓ All time boxes within limits")

    # Exit code
    has_critical = any(r.status in (TimeBoxStatus.WARNING, TimeBoxStatus.DEADLINE,
                                     TimeBoxStatus.OVERRUN) for r in results)
    return 1 if has_critical else 0

if __name__ == "__main__":
    sys.exit(main())
