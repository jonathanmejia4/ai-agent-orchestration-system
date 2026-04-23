#!/usr/bin/env python3
"""
the system Metrics Collector Tool

Collects and aggregates metrics from the system operations, providing
insights into system health, performance, and usage patterns.

Version: 1.0.0
Created: 2025-12-25
Author: Builder Agent
"""

import os
import re
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict

@dataclass
class Metric:
    """A single metric measurement."""
    name: str
    value: float
    unit: str
    timestamp: str
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    name: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    sum_value: float
    unit: str
    first_seen: str
    last_seen: str

@dataclass
class MetricsReport:
    """Complete metrics report."""
    timestamp: str
    period_start: str
    period_end: str
    total_metrics: int
    metrics_by_category: Dict[str, int]
    summaries: List[MetricSummary]
    alerts: List[Dict[str, Any]]
    trends: Dict[str, str]

class MetricsCollector:
    """Collects and stores metrics."""

    # Metric categories
    CATEGORIES = {
        'performance': ['latency', 'duration', 'response_time', 'throughput'],
        'usage': ['count', 'requests', 'invocations', 'calls'],
        'resources': ['memory', 'cpu', 'disk', 'connections'],
        'errors': ['error', 'failure', 'exception', 'timeout'],
        'quality': ['coverage', 'score', 'rating', 'compliance'],
    }

    def __init__(self, storage_path: str):
        """Initialize collector with storage path."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.metrics: List[Metric] = []
        self.thresholds: Dict[str, Dict[str, float]] = {}

    def record(
        self,
        name: str,
        value: float,
        unit: str = 'count',
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Metric:
        """Record a single metric."""
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now().isoformat(),
            tags=tags or {},
            metadata=metadata or {},
        )

        self.metrics.append(metric)

        # Check thresholds
        self._check_threshold(metric)

        return metric

    def timer(self, name: str, tags: Optional[Dict[str, str]] = None) -> 'TimerContext':
        """Create a timer context for measuring duration."""
        return TimerContext(self, name, tags)

    def counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> 'Counter':
        """Create a counter for incrementing metrics."""
        return Counter(self, name, tags)

    def gauge(self, name: str, value: float, unit: str = 'value', tags: Optional[Dict[str, str]] = None) -> Metric:
        """Record a gauge (point-in-time) metric."""
        return self.record(name, value, unit, tags, {'type': 'gauge'})

    def histogram(
        self,
        name: str,
        values: List[float],
        unit: str = 'value',
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """Record histogram statistics."""
        if not values:
            return {}

        sorted_values = sorted(values)
        n = len(sorted_values)

        stats = {
            'min': sorted_values[0],
            'max': sorted_values[-1],
            'avg': sum(values) / n,
            'p50': sorted_values[n // 2],
            'p90': sorted_values[int(n * 0.9)],
            'p99': sorted_values[int(n * 0.99)] if n >= 100 else sorted_values[-1],
        }

        for stat_name, stat_value in stats.items():
            self.record(f"{name}.{stat_name}", stat_value, unit, tags)

        return stats

    def set_threshold(
        self,
        metric_name: str,
        warning: Optional[float] = None,
        critical: Optional[float] = None,
    ) -> None:
        """Set threshold for a metric."""
        self.thresholds[metric_name] = {
            'warning': warning,
            'critical': critical,
        }

    def _check_threshold(self, metric: Metric) -> None:
        """Check if metric exceeds threshold."""
        if metric.name not in self.thresholds:
            return

        thresholds = self.thresholds[metric.name]

        if thresholds.get('critical') and metric.value >= thresholds['critical']:
            self._trigger_alert(metric, 'critical', thresholds['critical'])
        elif thresholds.get('warning') and metric.value >= thresholds['warning']:
            self._trigger_alert(metric, 'warning', thresholds['warning'])

    def _trigger_alert(self, metric: Metric, level: str, threshold: float) -> None:
        """Trigger an alert for threshold violation."""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'metric': metric.name,
            'value': metric.value,
            'threshold': threshold,
            'tags': metric.tags,
        }

        # Store alert
        alerts_file = self.storage_path / 'alerts.jsonl'
        with open(alerts_file, 'a') as f:
            f.write(json.dumps(alert) + '\n')

    def save(self) -> str:
        """Save metrics to storage."""
        if not self.metrics:
            return ""

        # Group by date
        metrics_by_date: Dict[str, List[Metric]] = defaultdict(list)
        for metric in self.metrics:
            date = metric.timestamp[:10]  # YYYY-MM-DD
            metrics_by_date[date].append(metric)

        # Save each date
        for date, metrics in metrics_by_date.items():
            date_file = self.storage_path / f"metrics-{date}.jsonl"
            with open(date_file, 'a') as f:
                for metric in metrics:
                    f.write(json.dumps(asdict(metric)) + '\n')

        # Clear in-memory metrics
        saved_count = len(self.metrics)
        self.metrics = []

        return f"Saved {saved_count} metrics"

    def load(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Metric]:
        """Load metrics from storage."""
        metrics = []

        for metrics_file in sorted(self.storage_path.glob('metrics-*.jsonl')):
            # Check date range
            file_date = metrics_file.stem.replace('metrics-', '')
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue

            with open(metrics_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        metrics.append(Metric(**data))

        return metrics

    def summarize(self, metrics: Optional[List[Metric]] = None) -> List[MetricSummary]:
        """Generate summaries for metrics."""
        if metrics is None:
            metrics = self.metrics

        if not metrics:
            return []

        # Group by name
        by_name: Dict[str, List[Metric]] = defaultdict(list)
        for metric in metrics:
            by_name[metric.name].append(metric)

        summaries = []
        for name, name_metrics in by_name.items():
            values = [m.value for m in name_metrics]
            timestamps = [m.timestamp for m in name_metrics]

            summaries.append(MetricSummary(
                name=name,
                count=len(values),
                min_value=min(values),
                max_value=max(values),
                avg_value=sum(values) / len(values),
                sum_value=sum(values),
                unit=name_metrics[0].unit,
                first_seen=min(timestamps),
                last_seen=max(timestamps),
            ))

        return sorted(summaries, key=lambda s: s.name)

    def generate_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> MetricsReport:
        """Generate a complete metrics report."""
        # Load metrics for period
        metrics = self.load(start_date, end_date)

        if not metrics:
            now = datetime.now().isoformat()
            return MetricsReport(
                timestamp=now,
                period_start=start_date or now,
                period_end=end_date or now,
                total_metrics=0,
                metrics_by_category={},
                summaries=[],
                alerts=[],
                trends={},
            )

        # Categorize metrics
        by_category: Dict[str, int] = defaultdict(int)
        for metric in metrics:
            category = self._categorize_metric(metric.name)
            by_category[category] += 1

        # Generate summaries
        summaries = self.summarize(metrics)

        # Load alerts
        alerts = self._load_alerts(start_date, end_date)

        # Calculate trends
        trends = self._calculate_trends(metrics)

        timestamps = [m.timestamp for m in metrics]

        return MetricsReport(
            timestamp=datetime.now().isoformat(),
            period_start=min(timestamps),
            period_end=max(timestamps),
            total_metrics=len(metrics),
            metrics_by_category=dict(by_category),
            summaries=summaries,
            alerts=alerts,
            trends=trends,
        )

    def _categorize_metric(self, name: str) -> str:
        """Categorize a metric by name."""
        name_lower = name.lower()

        for category, keywords in self.CATEGORIES.items():
            if any(keyword in name_lower for keyword in keywords):
                return category

        return 'other'

    def _load_alerts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Load alerts from storage."""
        alerts_file = self.storage_path / 'alerts.jsonl'
        if not alerts_file.exists():
            return []

        alerts = []
        with open(alerts_file) as f:
            for line in f:
                if line.strip():
                    alert = json.loads(line)
                    alert_date = alert['timestamp'][:10]

                    if start_date and alert_date < start_date:
                        continue
                    if end_date and alert_date > end_date:
                        continue

                    alerts.append(alert)

        return alerts

    def _calculate_trends(self, metrics: List[Metric]) -> Dict[str, str]:
        """Calculate trends for metrics."""
        trends = {}

        # Group by name and sort by time
        by_name: Dict[str, List[Metric]] = defaultdict(list)
        for metric in metrics:
            by_name[metric.name].append(metric)

        for name, name_metrics in by_name.items():
            if len(name_metrics) < 2:
                trends[name] = 'stable'
                continue

            sorted_metrics = sorted(name_metrics, key=lambda m: m.timestamp)

            # Compare first half to second half
            mid = len(sorted_metrics) // 2
            first_half_avg = sum(m.value for m in sorted_metrics[:mid]) / mid
            second_half_avg = sum(m.value for m in sorted_metrics[mid:]) / (len(sorted_metrics) - mid)

            if first_half_avg == 0:
                trends[name] = 'stable'
            elif second_half_avg > first_half_avg * 1.1:
                trends[name] = 'increasing'
            elif second_half_avg < first_half_avg * 0.9:
                trends[name] = 'decreasing'
            else:
                trends[name] = 'stable'

        return trends

class TimerContext:
    """Context manager for timing operations."""

    def __init__(self, collector: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.tags = tags or {}
        self.start_time: Optional[float] = None

    def __enter__(self) -> 'TimerContext':
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            duration = (time.perf_counter() - self.start_time) * 1000  # ms
            self.collector.record(
                f"{self.name}.duration",
                duration,
                'ms',
                self.tags,
                {'success': exc_type is None},
            )

class Counter:
    """Counter for incrementing metrics."""

    def __init__(self, collector: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.tags = tags or {}
        self.value = 0

    def increment(self, amount: int = 1) -> None:
        """Increment the counter."""
        self.value += amount

    def decrement(self, amount: int = 1) -> None:
        """Decrement the counter."""
        self.value -= amount

    def record(self) -> Metric:
        """Record the current counter value."""
        return self.collector.record(
            f"{self.name}.count",
            self.value,
            'count',
            self.tags,
        )

class SystemMetricsCollector:
    """System-specific metrics collector."""

    def __init__(self, storage_path: str = '.task/metrics'):
        """Initialize the system metrics collector."""
        self.collector = MetricsCollector(storage_path)
        self._setup_thresholds()

    def _setup_thresholds(self) -> None:
        """Set up default thresholds for the system metrics."""
        self.collector.set_threshold('build.duration', warning=30000, critical=60000)
        self.collector.set_threshold('validation.errors', warning=5, critical=10)
        self.collector.set_threshold('test.failures', warning=1, critical=5)
        self.collector.set_threshold('memory.usage_mb', warning=500, critical=1000)

    def record_build(self, duration_ms: float, success: bool, files_processed: int) -> None:
        """Record build metrics."""
        self.collector.record('build.duration', duration_ms, 'ms', {'success': str(success)})
        self.collector.record('build.files', files_processed, 'count')
        if success:
            self.collector.record('build.success', 1, 'count')
        else:
            self.collector.record('build.failure', 1, 'count')

    def record_validation(self, duration_ms: float, errors: int, warnings: int) -> None:
        """Record validation metrics."""
        self.collector.record('validation.duration', duration_ms, 'ms')
        self.collector.record('validation.errors', errors, 'count')
        self.collector.record('validation.warnings', warnings, 'count')

    def record_test(self, duration_ms: float, passed: int, failed: int, skipped: int) -> None:
        """Record test metrics."""
        self.collector.record('test.duration', duration_ms, 'ms')
        self.collector.record('test.passed', passed, 'count')
        self.collector.record('test.failures', failed, 'count')
        self.collector.record('test.skipped', skipped, 'count')

        total = passed + failed
        if total > 0:
            coverage = passed / total * 100
            self.collector.record('test.pass_rate', coverage, 'percent')

    def record_scan(self, scan_type: str, duration_ms: float, items_found: int) -> None:
        """Record scan metrics."""
        tags = {'type': scan_type}
        self.collector.record(f'scan.{scan_type}.duration', duration_ms, 'ms', tags)
        self.collector.record(f'scan.{scan_type}.items', items_found, 'count', tags)

    def record_deployment(self, environment: str, duration_ms: float, success: bool) -> None:
        """Record deployment metrics."""
        tags = {'environment': environment, 'success': str(success)}
        self.collector.record('deployment.duration', duration_ms, 'ms', tags)
        if success:
            self.collector.record('deployment.success', 1, 'count', tags)
        else:
            self.collector.record('deployment.failure', 1, 'count', tags)

    def save(self) -> str:
        """Save metrics."""
        return self.collector.save()

    def report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> MetricsReport:
        """Generate report."""
        return self.collector.generate_report(start_date, end_date)

def format_report(report: MetricsReport, format: str) -> str:
    """Format report for output."""
    if format == 'json':
        return json.dumps(asdict(report), indent=2, default=str)

    lines = [
        "=" * 60,
        "the system Metrics Report",
        "=" * 60,
        f"Generated: {report.timestamp}",
        f"Period: {report.period_start} to {report.period_end}",
        f"Total Metrics: {report.total_metrics}",
        "",
        "By Category:",
    ]

    for cat, count in sorted(report.metrics_by_category.items()):
        lines.append(f"  {cat:<15} {count:>8}")

    if report.summaries:
        lines.extend(["", "Top Metrics:"])
        for summary in report.summaries[:10]:
            lines.append(f"  {summary.name}:")
            lines.append(f"    Count: {summary.count}, Avg: {summary.avg_value:.2f} {summary.unit}")

    if report.alerts:
        lines.extend(["", f"Alerts ({len(report.alerts)}):"])
        for alert in report.alerts[:5]:
            lines.append(f"  [{alert['level'].upper()}] {alert['metric']}: {alert['value']} > {alert['threshold']}")

    if report.trends:
        lines.extend(["", "Trends:"])
        for name, trend in list(report.trends.items())[:10]:
            arrow = "↑" if trend == "increasing" else "↓" if trend == "decreasing" else "→"
            lines.append(f"  {arrow} {name}: {trend}")

    return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Metrics Collector - Collect and analyze metrics'
    )
    parser.add_argument(
        'command',
        choices=['report', 'record', 'alerts'],
        help='Command to execute'
    )
    parser.add_argument(
        '--storage', '-s',
        default='.task/metrics',
        help='Metrics storage path'
    )
    parser.add_argument(
        '--start-date',
        help='Start date for report (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        help='End date for report (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'summary'],
        default='summary',
        help='Output format'
    )
    parser.add_argument(
        '--name', '-n',
        help='Metric name (for record command)'
    )
    parser.add_argument(
        '--value', '-v',
        type=float,
        help='Metric value (for record command)'
    )
    parser.add_argument(
        '--unit', '-u',
        default='count',
        help='Metric unit (for record command)'
    )

    args = parser.parse_args()

    collector = SystemMetricsCollector(args.storage)

    if args.command == 'report':
        report = collector.report(args.start_date, args.end_date)
        print(format_report(report, args.format))

    elif args.command == 'record':
        if not args.name or args.value is None:
            print("Error: --name and --value required for record command")
            exit(1)

        collector.collector.record(args.name, args.value, args.unit)
        collector.save()
        print(f"Recorded: {args.name} = {args.value} {args.unit}")

    elif args.command == 'alerts':
        alerts = collector.collector._load_alerts(args.start_date, args.end_date)
        if not alerts:
            print("No alerts found")
        else:
            print(f"Alerts ({len(alerts)}):")
            for alert in alerts:
                print(f"  [{alert['level'].upper()}] {alert['timestamp']}: {alert['metric']} = {alert['value']}")

if __name__ == '__main__':
    main()
