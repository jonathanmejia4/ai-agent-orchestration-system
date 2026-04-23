#!/usr/bin/env python3
"""
alert_manager.py - Alert Management System

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Monitoring Tool

Purpose:
    Manages alerts for the system events.
    Supports multiple notification channels.
    Provides alert aggregation and deduplication.

Usage:
    python3 alert_manager.py send --level critical --message "Build failed"
    python3 alert_manager.py send --level warning --message "High memory usage" --channel slack
    python3 alert_manager.py list --status active
    python3 alert_manager.py acknowledge --alert-id ALERT-001
"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

class AlertLevel(Enum):
    """Alert severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def priority(self) -> int:
        priorities = {
            "debug": 0,
            "info": 1,
            "warning": 2,
            "error": 3,
            "critical": 4
        }
        return priorities[self.value]

class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

class NotificationChannel(Enum):
    """Notification channels."""
    CONSOLE = "console"
    FILE = "file"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"

@dataclass
class Alert:
    """Represents a system alert."""
    alert_id: str
    level: AlertLevel
    message: str
    source: str
    timestamp: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    context: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    occurrences: int = 1
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notification_sent: bool = False

    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = self._generate_fingerprint()
        if not self.first_seen:
            self.first_seen = self.timestamp
        if not self.last_seen:
            self.last_seen = self.timestamp

    def _generate_fingerprint(self) -> str:
        """Generate unique fingerprint for deduplication."""
        content = f"{self.level.value}:{self.source}:{self.message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "context": self.context,
            "fingerprint": self.fingerprint,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "notification_sent": self.notification_sent
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        return cls(
            alert_id=data["alert_id"],
            level=AlertLevel(data["level"]),
            message=data["message"],
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=AlertStatus(data.get("status", "active")),
            context=data.get("context", {}),
            fingerprint=data.get("fingerprint", ""),
            occurrences=data.get("occurrences", 1),
            first_seen=datetime.fromisoformat(data["first_seen"]) if data.get("first_seen") else None,
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else None,
            acknowledged_by=data.get("acknowledged_by"),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            notification_sent=data.get("notification_sent", False)
        )

class AlertManager:
    """Manages system alerts with deduplication and notification."""

    def __init__(self, storage_path: Optional[Path] = None, config: Optional[dict] = None):
        self.storage_path = storage_path or Path(".saf/alerts")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.alerts_file = self.storage_path / "alerts.json"
        self.config = config or {}
        self.alerts: Dict[str, Alert] = {}
        self._load_alerts()

        # Deduplication window (seconds)
        self.dedup_window = self.config.get("dedup_window_seconds", 300)

        # Suppression rules
        self.suppression_rules = self.config.get("suppression_rules", [])

    def _load_alerts(self):
        """Load alerts from storage."""
        if self.alerts_file.exists():
            try:
                with open(self.alerts_file, 'r') as f:
                    data = json.load(f)
                    for alert_data in data.get("alerts", []):
                        alert = Alert.from_dict(alert_data)
                        self.alerts[alert.alert_id] = alert
            except Exception:
                self.alerts = {}

    def _save_alerts(self):
        """Save alerts to storage."""
        data = {
            "updated_at": datetime.now().isoformat(),
            "alerts": [a.to_dict() for a in self.alerts.values()]
        }
        with open(self.alerts_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = len(self.alerts) + 1
        return f"ALERT-{timestamp}-{count:04d}"

    def _should_suppress(self, alert: Alert) -> bool:
        """Check if alert should be suppressed."""
        for rule in self.suppression_rules:
            if rule.get("level") and alert.level.value != rule["level"]:
                continue
            if rule.get("source") and alert.source != rule["source"]:
                continue
            if rule.get("message_pattern"):
                import re
                if not re.search(rule["message_pattern"], alert.message):
                    continue
            return True
        return False

    def _find_duplicate(self, alert: Alert) -> Optional[Alert]:
        """Find existing duplicate alert within dedup window."""
        cutoff = datetime.now() - timedelta(seconds=self.dedup_window)

        for existing in self.alerts.values():
            if existing.status in [AlertStatus.RESOLVED, AlertStatus.SUPPRESSED]:
                continue
            if existing.fingerprint == alert.fingerprint:
                if existing.last_seen and existing.last_seen > cutoff:
                    return existing

        return None

    def send_alert(
        self,
        level: AlertLevel,
        message: str,
        source: str = "system",
        context: Optional[Dict[str, Any]] = None,
        channels: Optional[List[NotificationChannel]] = None
    ) -> Alert:
        """Send a new alert with deduplication."""
        alert = Alert(
            alert_id=self._generate_alert_id(),
            level=level,
            message=message,
            source=source,
            timestamp=datetime.now(),
            context=context or {}
        )

        # Check suppression
        if self._should_suppress(alert):
            alert.status = AlertStatus.SUPPRESSED
            self.alerts[alert.alert_id] = alert
            self._save_alerts()
            return alert

        # Check for duplicates
        duplicate = self._find_duplicate(alert)
        if duplicate:
            duplicate.occurrences += 1
            duplicate.last_seen = datetime.now()
            self._save_alerts()
            return duplicate

        # Store new alert
        self.alerts[alert.alert_id] = alert

        # Send notifications
        channels = channels or [NotificationChannel.CONSOLE]
        for channel in channels:
            self._notify(alert, channel)

        alert.notification_sent = True
        self._save_alerts()

        return alert

    def _notify(self, alert: Alert, channel: NotificationChannel):
        """Send notification through specified channel."""
        if channel == NotificationChannel.CONSOLE:
            self._notify_console(alert)
        elif channel == NotificationChannel.FILE:
            self._notify_file(alert)
        elif channel == NotificationChannel.SLACK:
            self._notify_slack(alert)
        elif channel == NotificationChannel.WEBHOOK:
            self._notify_webhook(alert)

    def _notify_console(self, alert: Alert):
        """Print alert to console."""
        level_colors = {
            AlertLevel.DEBUG: "\033[90m",     # Gray
            AlertLevel.INFO: "\033[94m",      # Blue
            AlertLevel.WARNING: "\033[93m",   # Yellow
            AlertLevel.ERROR: "\033[91m",     # Red
            AlertLevel.CRITICAL: "\033[91;1m" # Bold Red
        }
        reset = "\033[0m"
        color = level_colors.get(alert.level, "")

        print(f"{color}[{alert.level.value.upper()}]{reset} [{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {alert.message}")
        if alert.context:
            print(f"  Context: {json.dumps(alert.context)}")

    def _notify_file(self, alert: Alert):
        """Write alert to file."""
        log_file = self.storage_path / "alert.log"
        with open(log_file, 'a') as f:
            f.write(f"[{alert.level.value.upper()}] [{alert.timestamp.isoformat()}] {alert.message}\n")

    def _notify_slack(self, alert: Alert):
        """Send alert to Slack via webhook."""
        webhook_url = self.config.get("slack_webhook_url") or os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("Slack webhook URL not configured, skipping notification")
            return

        # Slack message formatting
        level_emoji = {
            AlertLevel.DEBUG: ":white_circle:",
            AlertLevel.INFO: ":large_blue_circle:",
            AlertLevel.WARNING: ":warning:",
            AlertLevel.ERROR: ":red_circle:",
            AlertLevel.CRITICAL: ":rotating_light:"
        }
        emoji = level_emoji.get(alert.level, ":grey_question:")

        payload = {
            "text": f"{emoji} *[{alert.level.value.upper()}]* {alert.message}",
            "attachments": [{
                "color": self._get_level_color(alert.level),
                "fields": [
                    {"title": "Source", "value": alert.source, "short": True},
                    {"title": "Time", "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"), "short": True},
                    {"title": "Alert ID", "value": alert.alert_id, "short": True},
                ],
                "footer": "Alert System"
            }]
        }

        if alert.context:
            payload["attachments"][0]["fields"].append({
                "title": "Context",
                "value": json.dumps(alert.context, indent=2)[:500],
                "short": False
            })

        self._send_http_post(webhook_url, payload)

    def _notify_webhook(self, alert: Alert):
        """Send alert to generic webhook."""
        webhook_url = self.config.get("webhook_url") or os.environ.get("ALERT_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("Alert webhook URL not configured, skipping notification")
            return

        payload = {
            "event_type": "alert",
            "timestamp": alert.timestamp.isoformat(),
            "alert": {
                "id": alert.alert_id,
                "level": alert.level.value,
                "message": alert.message,
                "source": alert.source,
                "status": alert.status.value,
                "fingerprint": alert.fingerprint,
                "occurrences": alert.occurrences,
                "context": alert.context
            }
        }

        self._send_http_post(webhook_url, payload)

    def _get_level_color(self, level: AlertLevel) -> str:
        """Get color code for alert level."""
        colors = {
            AlertLevel.DEBUG: "#808080",
            AlertLevel.INFO: "#36a64f",
            AlertLevel.WARNING: "#ffcc00",
            AlertLevel.ERROR: "#ff6600",
            AlertLevel.CRITICAL: "#ff0000"
        }
        return colors.get(level, "#808080")

    def _send_http_post(self, url: str, payload: dict) -> bool:
        """Send HTTP POST request with JSON payload."""
        try:
            import urllib.request
            import urllib.error

            data = json.dumps(payload).encode('utf-8')
            request = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    logger.debug(f"Successfully sent notification to {url}")
                    return True
                else:
                    logger.warning(f"Notification failed with status {response.status}")
                    return False
        except urllib.error.URLError as e:
            logger.error(f"Failed to send notification to {url}: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False

    def acknowledge(self, alert_id: str, acknowledged_by: str = "system") -> Optional[Alert]:
        """Acknowledge an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now()
        self._save_alerts()

        return alert

    def resolve(self, alert_id: str) -> Optional[Alert]:
        """Resolve an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        self._save_alerts()

        return alert

    def list_alerts(
        self,
        status: Optional[AlertStatus] = None,
        level: Optional[AlertLevel] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Alert]:
        """List alerts with optional filters."""
        alerts = list(self.alerts.values())

        if status:
            alerts = [a for a in alerts if a.status == status]

        if level:
            alerts = [a for a in alerts if a.level.priority >= level.priority]

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        # Sort by timestamp descending
        alerts.sort(key=lambda a: a.timestamp, reverse=True)

        return alerts[:limit]

    def get_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics."""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)

        active = [a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE]
        recent = [a for a in self.alerts.values() if a.timestamp >= last_24h]

        return {
            "total_alerts": len(self.alerts),
            "active_alerts": len(active),
            "alerts_last_24h": len(recent),
            "by_level": {
                level.value: len([a for a in active if a.level == level])
                for level in AlertLevel
            },
            "by_status": {
                status.value: len([a for a in self.alerts.values() if a.status == status])
                for status in AlertStatus
            }
        }

def main():
    parser = argparse.ArgumentParser(description="Alert Management System")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Send command
    send_parser = subparsers.add_parser("send", help="Send an alert")
    send_parser.add_argument("--level", "-l", required=True,
                            choices=["debug", "info", "warning", "error", "critical"])
    send_parser.add_argument("--message", "-m", required=True)
    send_parser.add_argument("--source", "-s", default="cli")
    send_parser.add_argument("--channel", "-c", action="append",
                            choices=["console", "file", "slack", "webhook"],
                            default=[])
    send_parser.add_argument("--context", type=json.loads, default={})

    # List command
    list_parser = subparsers.add_parser("list", help="List alerts")
    list_parser.add_argument("--status", choices=["active", "acknowledged", "resolved", "suppressed"])
    list_parser.add_argument("--level", choices=["debug", "info", "warning", "error", "critical"])
    list_parser.add_argument("--limit", type=int, default=20)

    # Acknowledge command
    ack_parser = subparsers.add_parser("acknowledge", help="Acknowledge an alert")
    ack_parser.add_argument("--alert-id", "-a", required=True)
    ack_parser.add_argument("--by", default="cli-user")

    # Resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve an alert")
    resolve_parser.add_argument("--alert-id", "-a", required=True)

    # Summary command
    subparsers.add_parser("summary", help="Show alert summary")

    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--storage", help="Alert storage directory")

    args = parser.parse_args()

    storage_path = Path(args.storage) if args.storage else None
    manager = AlertManager(storage_path=storage_path)

    if args.command == "send":
        channels = [NotificationChannel(c) for c in args.channel] if args.channel else [NotificationChannel.CONSOLE]
        alert = manager.send_alert(
            level=AlertLevel(args.level),
            message=args.message,
            source=args.source,
            context=args.context,
            channels=channels
        )
        if args.format == "json":
            print(json.dumps(alert.to_dict(), indent=2))
        else:
            print(f"Alert sent: {alert.alert_id}")

    elif args.command == "list":
        status = AlertStatus(args.status) if args.status else None
        level = AlertLevel(args.level) if args.level else None
        alerts = manager.list_alerts(status=status, level=level, limit=args.limit)

        if args.format == "json":
            print(json.dumps([a.to_dict() for a in alerts], indent=2))
        else:
            print(f"Alerts ({len(alerts)}):")
            print("-" * 80)
            for alert in alerts:
                status_icon = {
                    AlertStatus.ACTIVE: "🔴",
                    AlertStatus.ACKNOWLEDGED: "🟡",
                    AlertStatus.RESOLVED: "🟢",
                    AlertStatus.SUPPRESSED: "⚪"
                }.get(alert.status, "⚪")
                print(f"{status_icon} [{alert.level.value.upper():8}] {alert.alert_id}")
                print(f"   {alert.message}")
                print(f"   Source: {alert.source} | Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                if alert.occurrences > 1:
                    print(f"   Occurrences: {alert.occurrences}")
                print()

    elif args.command == "acknowledge":
        alert = manager.acknowledge(args.alert_id, args.by)
        if alert:
            print(f"Alert {args.alert_id} acknowledged")
        else:
            print(f"Alert {args.alert_id} not found", file=sys.stderr)
            return 1

    elif args.command == "resolve":
        alert = manager.resolve(args.alert_id)
        if alert:
            print(f"Alert {args.alert_id} resolved")
        else:
            print(f"Alert {args.alert_id} not found", file=sys.stderr)
            return 1

    elif args.command == "summary":
        summary = manager.get_summary()
        if args.format == "json":
            print(json.dumps(summary, indent=2))
        else:
            print("Alert Summary")
            print("=" * 40)
            print(f"Total alerts: {summary['total_alerts']}")
            print(f"Active alerts: {summary['active_alerts']}")
            print(f"Last 24 hours: {summary['alerts_last_24h']}")
            print("\nBy Level:")
            for level, count in summary['by_level'].items():
                if count > 0:
                    print(f"  {level}: {count}")
            print("\nBy Status:")
            for status, count in summary['by_status'].items():
                if count > 0:
                    print(f"  {status}: {count}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
