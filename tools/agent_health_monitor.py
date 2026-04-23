#!/usr/bin/env python3
"""
Agent Health Monitor
Version: 1.0.0
Last Updated: 2025-12-25
Owner: PM
Classification: HIGH - Monitoring Tool

Monitors agent health and detects stalled or crashed agents.
Integrates with heartbeat daemon for comprehensive health assessment.

Usage:
    python tools/agent_health_monitor.py monitor --interval 60
    python tools/agent_health_monitor.py check --agent pm
    python tools/agent_health_monitor.py report
    python tools/agent_health_monitor.py alerts
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import yaml

@dataclass
class HealthMetric:
    """Individual health metric."""
    name: str
    value: Any
    status: str  # healthy, warning, critical, unknown
    threshold_warning: Optional[Any] = None
    threshold_critical: Optional[Any] = None
    message: Optional[str] = None

@dataclass
class AgentHealth:
    """Agent health assessment."""
    agent_id: str
    timestamp: str
    overall_status: str  # healthy, degraded, unhealthy, unknown
    alive: bool
    metrics: List[HealthMetric] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'timestamp': self.timestamp,
            'overall_status': self.overall_status,
            'alive': self.alive,
            'metrics': [asdict(m) for m in self.metrics],
            'alerts': self.alerts,
            'recommendations': self.recommendations
        }

@dataclass
class Alert:
    """Health alert."""
    alert_id: str
    agent_id: str
    severity: str  # info, warning, critical
    timestamp: str
    message: str
    metric_name: Optional[str] = None
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class AgentHealthMonitor:
    """Monitors agent health across the system."""

    VALID_AGENTS = ['pm', 'planner', 'builder', 'critic_orchestrator',
                    'critic_plan_auditor', 'critic_dependencies', 'critic_effort',
                    'critic_execution_ready', 'critic_spec_fit', 'critic_verification',
                    'critic_security_policy', 'critic_acl']

    # Health thresholds
    THRESHOLDS = {
        'heartbeat_age': {
            'warning': 120,    # 2 minutes
            'critical': 300    # 5 minutes
        },
        'session_age': {
            'warning': 3600,   # 1 hour
            'critical': 7200   # 2 hours
        },
        'error_rate': {
            'warning': 0.1,    # 10%
            'critical': 0.25   # 25%
        },
        'response_time': {
            'warning': 5000,   # 5 seconds
            'critical': 10000  # 10 seconds
        }
    }

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the health monitor."""
        self.project_root = project_root or Path.cwd()
        self.heartbeat_dir = self.project_root / ".heartbeats"
        self.state_dir = self.project_root / ".agent_state" / "current"
        self.health_dir = self.project_root / ".health"
        self.alerts_file = self.health_dir / "alerts.yaml"
        self.history_dir = self.health_dir / "history"
        self.config_file = self.health_dir / "config.yaml"

        # Ensure directories exist
        self.health_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Load config
        self.config = self._load_config()

        # Load alerts
        self.alerts = self._load_alerts()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f) or {}

        default_config = {
            'version': '1.0.0',
            'monitoring_interval': 60,
            'alert_retention_days': 7,
            'thresholds': self.THRESHOLDS,
            'notifications': {
                'enabled': False,
                'channels': []
            }
        }

        self._save_config(default_config)
        return default_config

    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration."""
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    def _load_alerts(self) -> List[Alert]:
        """Load alerts from file."""
        if not self.alerts_file.exists():
            return []

        with open(self.alerts_file, 'r') as f:
            data = yaml.safe_load(f) or []

        return [Alert(**a) for a in data]

    def _save_alerts(self) -> None:
        """Save alerts to file."""
        with open(self.alerts_file, 'w') as f:
            yaml.dump([a.to_dict() for a in self.alerts], f, default_flow_style=False)

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        return f"ALT-{timestamp}"

    def _get_heartbeat(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent's latest heartbeat."""
        heartbeat_file = self.heartbeat_dir / f"{agent_id}.heartbeat"

        if not heartbeat_file.exists():
            return None

        with open(heartbeat_file, 'r') as f:
            return yaml.safe_load(f)

    def _get_session_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent's session state."""
        state_file = self.state_dir / f"{agent_id}.yaml"

        if not state_file.exists():
            return None

        with open(state_file, 'r') as f:
            return yaml.safe_load(f)

    def _get_logbook_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get agent's LogBook statistics."""
        logbook_dir = self.project_root / "LogBook" / agent_id

        if not logbook_dir.exists():
            return {'entries': 0, 'errors': 0, 'last_entry': None}

        entries = list(logbook_dir.glob("*.yaml")) + list(logbook_dir.glob("*.md"))
        errors = len([e for e in entries if 'error' in e.name.lower()])

        last_entry = None
        if entries:
            latest = max(entries, key=lambda p: p.stat().st_mtime)
            last_entry = datetime.fromtimestamp(latest.stat().st_mtime).isoformat() + "Z"

        return {
            'entries': len(entries),
            'errors': errors,
            'last_entry': last_entry
        }

    def check_heartbeat_health(self, agent_id: str) -> HealthMetric:
        """Check heartbeat-based health."""
        heartbeat = self._get_heartbeat(agent_id)
        thresholds = self.config.get('thresholds', self.THRESHOLDS).get('heartbeat_age', {})

        if not heartbeat:
            return HealthMetric(
                name='heartbeat',
                value=None,
                status='unknown',
                message='No heartbeat found'
            )

        timestamp = datetime.fromisoformat(heartbeat['timestamp'].replace('Z', '+00:00'))
        age = (datetime.utcnow().replace(tzinfo=timestamp.tzinfo) - timestamp).total_seconds()

        if age > thresholds.get('critical', 300):
            status = 'critical'
            message = f'Heartbeat stale ({int(age)}s old)'
        elif age > thresholds.get('warning', 120):
            status = 'warning'
            message = f'Heartbeat aging ({int(age)}s old)'
        else:
            status = 'healthy'
            message = 'Heartbeat current'

        return HealthMetric(
            name='heartbeat',
            value=int(age),
            status=status,
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical'),
            message=message
        )

    def check_session_health(self, agent_id: str) -> HealthMetric:
        """Check session state health."""
        session = self._get_session_state(agent_id)
        thresholds = self.config.get('thresholds', self.THRESHOLDS).get('session_age', {})

        if not session:
            return HealthMetric(
                name='session',
                value=None,
                status='unknown',
                message='No active session'
            )

        timestamp = session.get('timestamp')
        if not timestamp:
            return HealthMetric(
                name='session',
                value=None,
                status='warning',
                message='Session has no timestamp'
            )

        ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        age = (datetime.utcnow().replace(tzinfo=ts.tzinfo) - ts).total_seconds()

        if age > thresholds.get('critical', 7200):
            status = 'warning'
            message = f'Session very old ({int(age/60)} min)'
        elif age > thresholds.get('warning', 3600):
            status = 'warning'
            message = f'Session aging ({int(age/60)} min)'
        else:
            status = 'healthy'
            message = 'Session active'

        return HealthMetric(
            name='session',
            value=int(age),
            status=status,
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical'),
            message=message
        )

    def check_logbook_health(self, agent_id: str) -> HealthMetric:
        """Check LogBook health."""
        stats = self._get_logbook_stats(agent_id)
        thresholds = self.config.get('thresholds', self.THRESHOLDS).get('error_rate', {})

        if stats['entries'] == 0:
            return HealthMetric(
                name='logbook',
                value=0,
                status='unknown',
                message='No LogBook entries'
            )

        error_rate = stats['errors'] / stats['entries'] if stats['entries'] > 0 else 0

        if error_rate > thresholds.get('critical', 0.25):
            status = 'critical'
            message = f'High error rate ({error_rate:.1%})'
        elif error_rate > thresholds.get('warning', 0.1):
            status = 'warning'
            message = f'Elevated error rate ({error_rate:.1%})'
        else:
            status = 'healthy'
            message = f'Normal error rate ({error_rate:.1%})'

        return HealthMetric(
            name='logbook',
            value=round(error_rate, 4),
            status=status,
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical'),
            message=message
        )

    def assess_agent_health(self, agent_id: str) -> AgentHealth:
        """
        Perform comprehensive health assessment for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentHealth assessment
        """
        if agent_id not in self.VALID_AGENTS:
            raise ValueError(f"Unknown agent: {agent_id}")

        timestamp = datetime.utcnow().isoformat() + "Z"
        metrics = []
        alerts_list = []
        recommendations = []

        # Check heartbeat
        heartbeat_metric = self.check_heartbeat_health(agent_id)
        metrics.append(heartbeat_metric)

        if heartbeat_metric.status == 'critical':
            alerts_list.append(f"CRITICAL: {heartbeat_metric.message}")
            recommendations.append("Check if agent process is running")
            self._create_alert(agent_id, 'critical', heartbeat_metric.message, 'heartbeat')
        elif heartbeat_metric.status == 'warning':
            alerts_list.append(f"WARNING: {heartbeat_metric.message}")
            recommendations.append("Monitor agent responsiveness")
            self._create_alert(agent_id, 'warning', heartbeat_metric.message, 'heartbeat')

        # Check session
        session_metric = self.check_session_health(agent_id)
        metrics.append(session_metric)

        if session_metric.status in ['critical', 'warning']:
            recommendations.append("Consider refreshing agent session")

        # Check logbook
        logbook_metric = self.check_logbook_health(agent_id)
        metrics.append(logbook_metric)

        if logbook_metric.status == 'critical':
            alerts_list.append(f"CRITICAL: {logbook_metric.message}")
            recommendations.append("Review recent errors in LogBook")
            self._create_alert(agent_id, 'critical', logbook_metric.message, 'logbook')

        # Determine overall status
        statuses = [m.status for m in metrics]

        if 'critical' in statuses:
            overall_status = 'unhealthy'
        elif 'warning' in statuses:
            overall_status = 'degraded'
        elif 'unknown' in statuses and all(s == 'unknown' for s in statuses):
            overall_status = 'unknown'
        else:
            overall_status = 'healthy'

        # Determine if alive
        alive = heartbeat_metric.status not in ['critical', 'unknown']

        health = AgentHealth(
            agent_id=agent_id,
            timestamp=timestamp,
            overall_status=overall_status,
            alive=alive,
            metrics=metrics,
            alerts=alerts_list,
            recommendations=recommendations
        )

        # Save to history
        self._save_health_history(health)

        return health

    def _create_alert(self, agent_id: str, severity: str, message: str,
                      metric_name: Optional[str] = None) -> None:
        """Create a new alert."""
        # Check for duplicate recent alerts
        recent_threshold = datetime.utcnow() - timedelta(minutes=5)

        for alert in self.alerts:
            if (alert.agent_id == agent_id and
                alert.message == message and
                not alert.acknowledged):
                alert_time = datetime.fromisoformat(alert.timestamp.replace('Z', '+00:00'))
                if alert_time.replace(tzinfo=None) > recent_threshold:
                    return  # Duplicate alert, skip

        alert = Alert(
            alert_id=self._generate_alert_id(),
            agent_id=agent_id,
            severity=severity,
            timestamp=datetime.utcnow().isoformat() + "Z",
            message=message,
            metric_name=metric_name
        )

        self.alerts.append(alert)
        self._save_alerts()

    def _save_health_history(self, health: AgentHealth) -> None:
        """Save health assessment to history."""
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        history_file = self.history_dir / f"{health.agent_id}_{date_str}.yaml"

        history = []
        if history_file.exists():
            with open(history_file, 'r') as f:
                history = yaml.safe_load(f) or []

        history.append(health.to_dict())

        # Keep last 1000 entries per day
        history = history[-1000:]

        with open(history_file, 'w') as f:
            yaml.dump(history, f, default_flow_style=False)

    def assess_all_agents(self) -> Dict[str, AgentHealth]:
        """Assess health of all agents."""
        return {agent_id: self.assess_agent_health(agent_id)
                for agent_id in self.VALID_AGENTS}

    def get_active_alerts(self, agent_id: Optional[str] = None,
                          severity: Optional[str] = None) -> List[Alert]:
        """Get active (unacknowledged) alerts."""
        alerts = [a for a in self.alerts if not a.acknowledged]

        if agent_id:
            alerts = [a for a in alerts if a.agent_id == agent_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                self._save_alerts()
                return True
        return False

    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        all_health = self.assess_all_agents()
        active_alerts = self.get_active_alerts()

        healthy_count = sum(1 for h in all_health.values() if h.overall_status == 'healthy')
        degraded_count = sum(1 for h in all_health.values() if h.overall_status == 'degraded')
        unhealthy_count = sum(1 for h in all_health.values() if h.overall_status == 'unhealthy')
        unknown_count = sum(1 for h in all_health.values() if h.overall_status == 'unknown')

        return {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'summary': {
                'total_agents': len(self.VALID_AGENTS),
                'healthy': healthy_count,
                'degraded': degraded_count,
                'unhealthy': unhealthy_count,
                'unknown': unknown_count,
                'active_alerts': len(active_alerts),
                'critical_alerts': len([a for a in active_alerts if a.severity == 'critical'])
            },
            'agents': {aid: h.to_dict() for aid, h in all_health.items()},
            'alerts': [a.to_dict() for a in active_alerts]
        }

    def run_monitor(self, interval: int = 60, callback=None) -> None:
        """
        Run continuous health monitoring.

        Args:
            interval: Check interval in seconds
            callback: Optional callback function for alerts
        """
        print(f"Starting health monitor (interval: {interval}s)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                print(f"\n[{datetime.utcnow().isoformat()}] Running health check...")

                report = self.generate_health_report()
                summary = report['summary']

                print(f"  Healthy: {summary['healthy']}/{summary['total_agents']}")
                print(f"  Degraded: {summary['degraded']}")
                print(f"  Unhealthy: {summary['unhealthy']}")
                print(f"  Active alerts: {summary['active_alerts']}")

                if summary['critical_alerts'] > 0:
                    print(f"  ** CRITICAL ALERTS: {summary['critical_alerts']} **")

                    if callback:
                        for alert in report['alerts']:
                            if alert['severity'] == 'critical':
                                callback(alert)

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nMonitor stopped")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Agent Health Monitor',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Run continuous monitoring')
    monitor_parser.add_argument('--interval', '-i', type=int, default=60, help='Check interval')

    # Check command
    check_parser = subparsers.add_parser('check', help='Check specific agent')
    check_parser.add_argument('--agent', '-a', required=True, help='Agent ID')
    check_parser.add_argument('--format', choices=['text', 'yaml', 'json'], default='text')

    # Check-all command
    check_all_parser = subparsers.add_parser('check-all', help='Check all agents')
    check_all_parser.add_argument('--format', choices=['text', 'yaml', 'json'], default='text')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate health report')
    report_parser.add_argument('--format', choices=['text', 'yaml', 'json'], default='text')
    report_parser.add_argument('--output', '-o', help='Output file')

    # Alerts command
    alerts_parser = subparsers.add_parser('alerts', help='Show active alerts')
    alerts_parser.add_argument('--agent', '-a', help='Filter by agent')
    alerts_parser.add_argument('--severity', '-s', help='Filter by severity')

    # Acknowledge command
    ack_parser = subparsers.add_parser('ack', help='Acknowledge alert')
    ack_parser.add_argument('--alert-id', '-i', required=True, help='Alert ID')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    monitor = AgentHealthMonitor()

    try:
        if args.command == 'monitor':
            monitor.run_monitor(args.interval)

        elif args.command == 'check':
            health = monitor.assess_agent_health(args.agent)

            if args.format == 'text':
                print(f"\nHealth Assessment: {args.agent}")
                print("=" * 40)
                print(f"Status: {health.overall_status.upper()}")
                print(f"Alive: {'Yes' if health.alive else 'No'}")
                print(f"\nMetrics:")
                for m in health.metrics:
                    icon = {'healthy': '+', 'warning': '!', 'critical': 'X', 'unknown': '?'}[m.status]
                    print(f"  [{icon}] {m.name}: {m.message}")
                if health.recommendations:
                    print(f"\nRecommendations:")
                    for r in health.recommendations:
                        print(f"  - {r}")
            elif args.format == 'json':
                print(json.dumps(health.to_dict(), indent=2))
            else:
                print(yaml.dump(health.to_dict(), default_flow_style=False))

        elif args.command == 'check-all':
            all_health = monitor.assess_all_agents()

            if args.format == 'text':
                print(f"\n{'Agent':<25} {'Status':<12} {'Alive':<8} {'Alerts':<10}")
                print("-" * 60)
                for aid, health in all_health.items():
                    alive = 'Yes' if health.alive else 'No'
                    alerts = len(health.alerts)
                    print(f"{aid:<25} {health.overall_status:<12} {alive:<8} {alerts:<10}")
            elif args.format == 'json':
                print(json.dumps({k: v.to_dict() for k, v in all_health.items()}, indent=2))
            else:
                print(yaml.dump({k: v.to_dict() for k, v in all_health.items()}, default_flow_style=False))

        elif args.command == 'report':
            report = monitor.generate_health_report()

            if args.output:
                with open(args.output, 'w') as f:
                    if args.format == 'json':
                        json.dump(report, f, indent=2)
                    else:
                        yaml.dump(report, f, default_flow_style=False)
                print(f"Report saved to {args.output}")
            else:
                if args.format == 'text':
                    s = report['summary']
                    print(f"\nHealth Report ({report['timestamp']})")
                    print("=" * 50)
                    print(f"Total Agents: {s['total_agents']}")
                    print(f"Healthy: {s['healthy']}")
                    print(f"Degraded: {s['degraded']}")
                    print(f"Unhealthy: {s['unhealthy']}")
                    print(f"Unknown: {s['unknown']}")
                    print(f"Active Alerts: {s['active_alerts']}")
                    print(f"Critical Alerts: {s['critical_alerts']}")
                elif args.format == 'json':
                    print(json.dumps(report, indent=2))
                else:
                    print(yaml.dump(report, default_flow_style=False))

        elif args.command == 'alerts':
            alerts = monitor.get_active_alerts(args.agent, args.severity)

            if not alerts:
                print("No active alerts")
            else:
                for alert in alerts:
                    icon = {'info': 'i', 'warning': '!', 'critical': 'X'}[alert.severity]
                    print(f"[{icon}] {alert.alert_id} ({alert.agent_id})")
                    print(f"    {alert.message}")
                    print(f"    Time: {alert.timestamp}")
                    print()

        elif args.command == 'ack':
            if monitor.acknowledge_alert(args.alert_id):
                print(f"Alert {args.alert_id} acknowledged")
            else:
                print(f"Alert {args.alert_id} not found")
                sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
