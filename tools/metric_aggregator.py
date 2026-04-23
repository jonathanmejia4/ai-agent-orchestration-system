#!/usr/bin/env python3
"""
metric_aggregator.py - the system Metric Aggregator

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Monitoring

Purpose:
    Aggregates metrics from across a system components,
    generates reports, and tracks performance over time.

Usage:
    python3 metric_aggregator.py collect
    python3 metric_aggregator.py report --period daily
    python3 metric_aggregator.py export --format json
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class Metric:
    """Represents a single metric."""
    name: str
    value: float
    unit: str
    timestamp: str
    source: str
    tags: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp,
            "source": self.source,
            "tags": self.tags
        }

@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    name: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    sum_value: float
    latest_value: float
    latest_timestamp: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "count": self.count,
            "min": self.min_value,
            "max": self.max_value,
            "avg": round(self.avg_value, 2),
            "sum": self.sum_value,
            "latest": self.latest_value,
            "latest_timestamp": self.latest_timestamp
        }

class MetricAggregator:
    """Aggregates and analyzes the system metrics."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.metrics: List[Metric] = []

    def collect_all(self) -> List[Metric]:
        """Collect metrics from all sources."""
        self.metrics = []

        collectors = [
            self._collect_work_order_metrics,
            self._collect_task_metrics,
            self._collect_agent_metrics,
            self._collect_execution_metrics,
            self._collect_verdict_metrics,
        ]

        for collector in collectors:
            try:
                metrics = collector()
                self.metrics.extend(metrics)
            except Exception:
                pass

        return self.metrics

    def _collect_work_order_metrics(self) -> List[Metric]:
        """Collect metrics from work order queue."""
        metrics = []
        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"

        if not wo_queue.exists() or not HAS_YAML:
            return metrics

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            work_orders = data.get("work_orders", [])
            now = datetime.utcnow().isoformat() + "Z"

            # Count by status
            status_counts = {}
            for wo in work_orders:
                status = wo.get("status", "UNKNOWN")
                status_counts[status] = status_counts.get(status, 0) + 1

            for status, count in status_counts.items():
                metrics.append(Metric(
                    name=f"work_orders.{status.lower()}",
                    value=count,
                    unit="count",
                    timestamp=now,
                    source="WO_QUEUE",
                    tags={"status": status}
                ))

            # Total work orders
            metrics.append(Metric(
                name="work_orders.total",
                value=len(work_orders),
                unit="count",
                timestamp=now,
                source="WO_QUEUE"
            ))

            # Count by priority
            priority_counts = {}
            for wo in work_orders:
                priority = wo.get("priority", "medium")
                priority_counts[priority] = priority_counts.get(priority, 0) + 1

            for priority, count in priority_counts.items():
                metrics.append(Metric(
                    name=f"work_orders.priority.{priority}",
                    value=count,
                    unit="count",
                    timestamp=now,
                    source="WO_QUEUE",
                    tags={"priority": priority}
                ))

        except Exception:
            pass

        return metrics

    def _collect_task_metrics(self) -> List[Metric]:
        """Collect metrics from tasks."""
        metrics = []
        now = datetime.utcnow().isoformat() + "Z"

        task_dirs = list(self.base_path.glob("task*"))
        if not task_dirs:
            return metrics

        total = len(task_dirs)
        by_status = {}

        for task_dir in task_dirs:
            manifest = task_dir / "task.yaml"
            if manifest.exists() and HAS_YAML:
                try:
                    with open(manifest) as f:
                        data = yaml.safe_load(f) or {}
                    status = data.get("status", "unknown")
                    by_status[status] = by_status.get(status, 0) + 1
                except Exception:
                    pass

        metrics.append(Metric(
            name="tasks.total",
            value=total,
            unit="count",
            timestamp=now,
            source="tasks"
        ))

        for status, count in by_status.items():
            metrics.append(Metric(
                name=f"tasks.status.{status}",
                value=count,
                unit="count",
                timestamp=now,
                source="tasks",
                tags={"status": status}
            ))

        return metrics

    def _collect_agent_metrics(self) -> List[Metric]:
        """Collect metrics about agents."""
        metrics = []
        now = datetime.utcnow().isoformat() + "Z"

        agents = ["pm", "builder", "critic", "planner"]

        for agent in agents:
            agent_dir = self.base_path / "LogBook" / agent
            if agent_dir.exists():
                # Count files
                file_count = sum(1 for _ in agent_dir.rglob("*") if _.is_file())
                metrics.append(Metric(
                    name=f"agent.{agent}.files",
                    value=file_count,
                    unit="count",
                    timestamp=now,
                    source=f"LogBook/{agent}",
                    tags={"agent": agent}
                ))

                # Check state file
                state_file = agent_dir / "STATE.md"
                metrics.append(Metric(
                    name=f"agent.{agent}.has_state",
                    value=1 if state_file.exists() else 0,
                    unit="boolean",
                    timestamp=now,
                    source=f"LogBook/{agent}",
                    tags={"agent": agent}
                ))

        return metrics

    def _collect_execution_metrics(self) -> List[Metric]:
        """Collect metrics from execution logs."""
        metrics = []
        exec_log = self.base_path / "LogBook/builder/execution_log.yaml"

        if not exec_log.exists() or not HAS_YAML:
            return metrics

        try:
            with open(exec_log) as f:
                data = yaml.safe_load(f) or {}

            now = datetime.utcnow().isoformat() + "Z"
            summary = data.get("summary", {})

            if summary:
                metrics.append(Metric(
                    name="executions.total",
                    value=summary.get("total_executions", 0),
                    unit="count",
                    timestamp=now,
                    source="execution_log"
                ))

                metrics.append(Metric(
                    name="executions.successful",
                    value=summary.get("successful", 0),
                    unit="count",
                    timestamp=now,
                    source="execution_log"
                ))

                metrics.append(Metric(
                    name="executions.failed",
                    value=summary.get("failed", 0),
                    unit="count",
                    timestamp=now,
                    source="execution_log"
                ))

                avg_duration = summary.get("average_duration_seconds", 0)
                metrics.append(Metric(
                    name="executions.avg_duration",
                    value=avg_duration,
                    unit="seconds",
                    timestamp=now,
                    source="execution_log"
                ))

        except Exception:
            pass

        return metrics

    def _collect_verdict_metrics(self) -> List[Metric]:
        """Collect metrics from verdict logs."""
        metrics = []
        verdict_log = self.base_path / "LogBook/critic/verdict_log.yaml"

        if not verdict_log.exists() or not HAS_YAML:
            return metrics

        try:
            with open(verdict_log) as f:
                data = yaml.safe_load(f) or {}

            now = datetime.utcnow().isoformat() + "Z"
            summary = data.get("summary", {})

            if summary:
                metrics.append(Metric(
                    name="verdicts.total",
                    value=summary.get("total_verdicts", 0),
                    unit="count",
                    timestamp=now,
                    source="verdict_log"
                ))

                by_verdict = summary.get("by_verdict", {})
                for verdict, count in by_verdict.items():
                    metrics.append(Metric(
                        name=f"verdicts.{verdict}",
                        value=count,
                        unit="count",
                        timestamp=now,
                        source="verdict_log",
                        tags={"verdict": verdict}
                    ))

                metrics.append(Metric(
                    name="verdicts.avg_confidence",
                    value=summary.get("average_confidence", 0),
                    unit="ratio",
                    timestamp=now,
                    source="verdict_log"
                ))

        except Exception:
            pass

        return metrics

    def summarize(self) -> Dict[str, MetricSummary]:
        """Generate summary statistics for all metrics."""
        summaries = {}

        # Group by name
        by_name = {}
        for metric in self.metrics:
            if metric.name not in by_name:
                by_name[metric.name] = []
            by_name[metric.name].append(metric)

        for name, metrics in by_name.items():
            values = [m.value for m in metrics]
            timestamps = [m.timestamp for m in metrics]

            summary = MetricSummary(
                name=name,
                count=len(values),
                min_value=min(values),
                max_value=max(values),
                avg_value=sum(values) / len(values),
                sum_value=sum(values),
                latest_value=metrics[-1].value,
                latest_timestamp=max(timestamps)
            )
            summaries[name] = summary

        return summaries

    def generate_report(self, period: str = "daily") -> Dict:
        """Generate metrics report."""
        if not self.metrics:
            self.collect_all()

        summaries = self.summarize()

        report = {
            "report_id": f"METRICS-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "period": period,
            "total_metrics": len(self.metrics),
            "unique_metrics": len(summaries),
            "summaries": {name: s.to_dict() for name, s in summaries.items()},
            "highlights": self._generate_highlights(summaries)
        }

        return report

    def _generate_highlights(self, summaries: Dict[str, MetricSummary]) -> List[str]:
        """Generate report highlights."""
        highlights = []

        # Work order highlights
        if "work_orders.total" in summaries:
            total = summaries["work_orders.total"].latest_value
            highlights.append(f"Total work orders: {int(total)}")

        if "work_orders.completed" in summaries:
            completed = summaries["work_orders.completed"].latest_value
            highlights.append(f"Completed work orders: {int(completed)}")

        if "work_orders.blocked" in summaries:
            blocked = summaries["work_orders.blocked"].latest_value
            if blocked > 0:
                highlights.append(f"ALERT: {int(blocked)} blocked work orders")

        # Task highlights
        if "tasks.total" in summaries:
            total = summaries["tasks.total"].latest_value
            highlights.append(f"Total tasks: {int(total)}")

        # Execution highlights
        if "executions.failed" in summaries:
            failed = summaries["executions.failed"].latest_value
            if failed > 0:
                highlights.append(f"WARNING: {int(failed)} failed executions")

        return highlights

    def export(self, format: str = "json") -> str:
        """Export metrics in specified format."""
        if not self.metrics:
            self.collect_all()

        if format == "json":
            return json.dumps([m.to_dict() for m in self.metrics], indent=2)
        elif format == "csv":
            lines = ["name,value,unit,timestamp,source"]
            for m in self.metrics:
                lines.append(f"{m.name},{m.value},{m.unit},{m.timestamp},{m.source}")
            return "\n".join(lines)
        else:
            return str([m.to_dict() for m in self.metrics])

def main():
    parser = argparse.ArgumentParser(description="the system Metric Aggregator")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Collect command
    collect_parser = subparsers.add_parser("collect", help="Collect all metrics")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--period", default="daily", choices=["hourly", "daily", "weekly"])

    # Export command
    export_parser = subparsers.add_parser("export", help="Export metrics")
    export_parser.add_argument("--format", default="json", choices=["json", "csv"])
    export_parser.add_argument("--output", "-o", help="Output file")

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Show metric summaries")

    # Common arguments
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    aggregator = MetricAggregator()

    if args.command == "collect":
        metrics = aggregator.collect_all()

        if args.format == "json":
            print(json.dumps([m.to_dict() for m in metrics], indent=2))
        else:
            print(f"\nCollected {len(metrics)} metrics")
            print("=" * 40)
            for m in metrics:
                print(f"{m.name}: {m.value} {m.unit}")

    elif args.command == "report":
        report = aggregator.generate_report(args.period)

        if args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            print(f"\nMetrics Report: {report['report_id']}")
            print("=" * 50)
            print(f"Generated: {report['generated_at']}")
            print(f"Period: {report['period']}")
            print(f"Total Metrics: {report['total_metrics']}")
            print(f"Unique Metrics: {report['unique_metrics']}")

            if report['highlights']:
                print("\nHighlights:")
                for h in report['highlights']:
                    print(f"  - {h}")

    elif args.command == "export":
        output = aggregator.export(args.format)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Exported to {args.output}")
        else:
            print(output)

    elif args.command == "summary":
        aggregator.collect_all()
        summaries = aggregator.summarize()

        if args.format == "json":
            print(json.dumps({n: s.to_dict() for n, s in summaries.items()}, indent=2))
        else:
            print("\nMetric Summaries")
            print("=" * 60)
            for name, summary in summaries.items():
                print(f"\n{name}:")
                print(f"  Count: {summary.count}")
                print(f"  Min: {summary.min_value}, Max: {summary.max_value}")
                print(f"  Avg: {summary.avg_value:.2f}")
                print(f"  Latest: {summary.latest_value}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
