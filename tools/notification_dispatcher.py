#!/usr/bin/env python3
"""
the system Notification Dispatcher
Version: 1.0.0
Last Updated: 2025-12-25
Owner: PM
Classification: HIGH - Communication Tool

Dispatches notifications across multiple channels for the system events.
Supports email, Slack, Teams, webhooks, and file-based notifications.

Usage:
    python tools/notification_dispatcher.py send --channel slack --message "Build complete"
    python tools/notification_dispatcher.py broadcast --event task_promoted --data '{"task": "auth"}'
    python tools/notification_dispatcher.py config --list
    python tools/notification_dispatcher.py test --channel email
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
import yaml

@dataclass
class Notification:
    """Represents a notification message."""
    notification_id: str
    timestamp: str
    channel: str
    event_type: str
    title: str
    message: str
    priority: str = "normal"  # low, normal, high, critical
    data: Dict[str, Any] = field(default_factory=dict)
    recipients: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, sent, failed
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name."""
        pass

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """Send notification through this channel."""
        pass

    @abstractmethod
    def test(self) -> bool:
        """Test channel connectivity."""
        pass

class FileChannel(NotificationChannel):
    """File-based notification channel (always available)."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "file"

    def send(self, notification: Notification) -> bool:
        """Write notification to file."""
        try:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            filename = f"notifications_{date_str}.yaml"
            filepath = self.output_dir / filename

            notifications = []
            if filepath.exists():
                with open(filepath, 'r') as f:
                    notifications = yaml.safe_load(f) or []

            notifications.append(notification.to_dict())

            with open(filepath, 'w') as f:
                yaml.dump(notifications, f, default_flow_style=False)

            return True
        except Exception as e:
            notification.error = str(e)
            return False

    def test(self) -> bool:
        """Test file write access."""
        try:
            test_file = self.output_dir / ".test"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception:
            return False

class WebhookChannel(NotificationChannel):
    """Generic webhook notification channel."""

    def __init__(self, webhook_url: str, headers: Optional[Dict[str, str]] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {'Content-Type': 'application/json'}

    @property
    def name(self) -> str:
        return "webhook"

    def send(self, notification: Notification) -> bool:
        """Send notification via webhook."""
        try:
            payload = {
                'event': notification.event_type,
                'title': notification.title,
                'message': notification.message,
                'priority': notification.priority,
                'timestamp': notification.timestamp,
                'data': notification.data
            }

            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(self.webhook_url, data=data, headers=self.headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200

        except Exception as e:
            notification.error = str(e)
            return False

    def test(self) -> bool:
        """Test webhook connectivity."""
        try:
            req = urllib.request.Request(self.webhook_url, method='HEAD')
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False

class SlackChannel(NotificationChannel):
    """Slack notification channel."""

    PRIORITY_COLORS = {
        'low': '#36a64f',
        'normal': '#2196F3',
        'high': '#FF9800',
        'critical': '#f44336'
    }

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "slack"

    def send(self, notification: Notification) -> bool:
        """Send notification to Slack."""
        try:
            color = self.PRIORITY_COLORS.get(notification.priority, '#2196F3')

            payload = {
                'attachments': [{
                    'color': color,
                    'title': notification.title,
                    'text': notification.message,
                    'fields': [
                        {'title': 'Event', 'value': notification.event_type, 'short': True},
                        {'title': 'Priority', 'value': notification.priority.upper(), 'short': True}
                    ],
                    'footer': 'the system Notification System',
                    'ts': int(datetime.utcnow().timestamp())
                }]
            }

            # Add extra data fields
            for key, value in notification.data.items():
                payload['attachments'][0]['fields'].append({
                    'title': key.replace('_', ' ').title(),
                    'value': str(value),
                    'short': True
                })

            data = json.dumps(payload).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            req = urllib.request.Request(self.webhook_url, data=data, headers=headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200

        except Exception as e:
            notification.error = str(e)
            return False

    def test(self) -> bool:
        """Test Slack webhook."""
        try:
            payload = {'text': 'the system Notification System test message'}
            data = json.dumps(payload).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            req = urllib.request.Request(self.webhook_url, data=data, headers=headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception:
            return False

class TeamsChannel(NotificationChannel):
    """Microsoft Teams notification channel."""

    PRIORITY_COLORS = {
        'low': '36a64f',
        'normal': '2196F3',
        'high': 'FF9800',
        'critical': 'f44336'
    }

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "teams"

    def send(self, notification: Notification) -> bool:
        """Send notification to Microsoft Teams."""
        try:
            color = self.PRIORITY_COLORS.get(notification.priority, '2196F3')

            # Teams Adaptive Card format
            payload = {
                '@type': 'MessageCard',
                '@context': 'http://schema.org/extensions',
                'themeColor': color,
                'summary': notification.title,
                'sections': [{
                    'activityTitle': notification.title,
                    'activitySubtitle': f"Event: {notification.event_type}",
                    'text': notification.message,
                    'facts': [
                        {'name': 'Priority', 'value': notification.priority.upper()},
                        {'name': 'Timestamp', 'value': notification.timestamp}
                    ]
                }]
            }

            # Add extra data
            for key, value in notification.data.items():
                payload['sections'][0]['facts'].append({
                    'name': key.replace('_', ' ').title(),
                    'value': str(value)
                })

            data = json.dumps(payload).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            req = urllib.request.Request(self.webhook_url, data=data, headers=headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200

        except Exception as e:
            notification.error = str(e)
            return False

    def test(self) -> bool:
        """Test Teams webhook."""
        try:
            payload = {
                '@type': 'MessageCard',
                '@context': 'http://schema.org/extensions',
                'summary': 'Test',
                'sections': [{'text': 'the system Notification System test message'}]
            }
            data = json.dumps(payload).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            req = urllib.request.Request(self.webhook_url, data=data, headers=headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception:
            return False

class ConsoleChannel(NotificationChannel):
    """Console output channel (for debugging)."""

    @property
    def name(self) -> str:
        return "console"

    def send(self, notification: Notification) -> bool:
        """Print notification to console."""
        priority_icons = {
            'low': 'i',
            'normal': '*',
            'high': '!',
            'critical': 'X'
        }
        icon = priority_icons.get(notification.priority, '*')

        print(f"\n[{icon}] {notification.title}")
        print(f"    Event: {notification.event_type}")
        print(f"    Message: {notification.message}")
        if notification.data:
            print(f"    Data: {json.dumps(notification.data)}")
        print()

        return True

    def test(self) -> bool:
        """Console is always available."""
        return True

class NotificationDispatcher:
    """Dispatches notifications to configured channels."""

    # Event types and their default priorities
    EVENT_PRIORITIES = {
        'task_created': 'low',
        'task_promoted': 'normal',
        'task_approved': 'normal',
        'task_rejected': 'high',
        'task_failed': 'high',
        'test_passed': 'low',
        'test_failed': 'high',
        'review_requested': 'normal',
        'review_completed': 'normal',
        'escalation': 'high',
        'critical_error': 'critical',
        'deployment_started': 'normal',
        'deployment_completed': 'normal',
        'deployment_failed': 'critical',
        'security_alert': 'critical',
        'health_warning': 'high',
        'health_critical': 'critical'
    }

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the notification dispatcher."""
        self.project_root = project_root or Path.cwd()
        self.config_file = self.project_root / "integration" / "config" / "notifications.yaml"
        self.notifications_dir = self.project_root / ".notifications"
        self.history_dir = self.notifications_dir / "history"

        self.notifications_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Load config
        self.config = self._load_config()

        # Initialize channels
        self.channels: Dict[str, NotificationChannel] = {}
        self._init_channels()

        # Notification counter
        self._counter = self._load_counter()

    def _load_config(self) -> Dict[str, Any]:
        """Load notification configuration."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f) or {}

        # Default config
        default_config = {
            'version': '1.0.0',
            'enabled': True,
            'default_channel': 'file',
            'channels': {
                'file': {
                    'enabled': True,
                    'output_dir': str(self.notifications_dir / "outbox")
                },
                'console': {
                    'enabled': True
                },
                'slack': {
                    'enabled': False,
                    'webhook_url': ''
                },
                'teams': {
                    'enabled': False,
                    'webhook_url': ''
                },
                'webhook': {
                    'enabled': False,
                    'url': ''
                }
            },
            'event_routing': {
                'critical_error': ['slack', 'teams', 'file'],
                'security_alert': ['slack', 'teams', 'file'],
                'default': ['file']
            },
            'quiet_hours': {
                'enabled': False,
                'start': '22:00',
                'end': '07:00',
                'timezone': 'UTC'
            }
        }

        # Save default config
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)

        return default_config

    def _init_channels(self) -> None:
        """Initialize notification channels."""
        channels_config = self.config.get('channels', {})

        # Always add file and console channels
        file_config = channels_config.get('file', {})
        output_dir = Path(file_config.get('output_dir', self.notifications_dir / "outbox"))
        self.channels['file'] = FileChannel(output_dir)
        self.channels['console'] = ConsoleChannel()

        # Add Slack if configured
        slack_config = channels_config.get('slack', {})
        if slack_config.get('enabled') and slack_config.get('webhook_url'):
            self.channels['slack'] = SlackChannel(slack_config['webhook_url'])

        # Add Teams if configured
        teams_config = channels_config.get('teams', {})
        if teams_config.get('enabled') and teams_config.get('webhook_url'):
            self.channels['teams'] = TeamsChannel(teams_config['webhook_url'])

        # Add generic webhook if configured
        webhook_config = channels_config.get('webhook', {})
        if webhook_config.get('enabled') and webhook_config.get('url'):
            self.channels['webhook'] = WebhookChannel(webhook_config['url'])

    def _load_counter(self) -> int:
        """Load notification counter."""
        counter_file = self.notifications_dir / "counter"
        if counter_file.exists():
            return int(counter_file.read_text().strip())
        return 0

    def _save_counter(self) -> None:
        """Save notification counter."""
        counter_file = self.notifications_dir / "counter"
        counter_file.write_text(str(self._counter))

    def _generate_notification_id(self) -> str:
        """Generate unique notification ID."""
        self._counter += 1
        self._save_counter()
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f"NOT-{timestamp}-{self._counter:05d}"

    def get_channels_for_event(self, event_type: str) -> List[str]:
        """Get list of channels for an event type."""
        routing = self.config.get('event_routing', {})

        # Check specific event routing
        if event_type in routing:
            return routing[event_type]

        # Use default routing
        return routing.get('default', ['file'])

    def send(self, channel_name: str, title: str, message: str,
             event_type: str = "notification", priority: Optional[str] = None,
             data: Optional[Dict[str, Any]] = None) -> Notification:
        """
        Send notification to specific channel.

        Args:
            channel_name: Target channel
            title: Notification title
            message: Notification message
            event_type: Type of event
            priority: Priority level
            data: Additional data

        Returns:
            Notification object with status
        """
        # Determine priority
        if priority is None:
            priority = self.EVENT_PRIORITIES.get(event_type, 'normal')

        notification = Notification(
            notification_id=self._generate_notification_id(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            channel=channel_name,
            event_type=event_type,
            title=title,
            message=message,
            priority=priority,
            data=data or {}
        )

        # Get channel
        channel = self.channels.get(channel_name)
        if not channel:
            notification.status = "failed"
            notification.error = f"Channel not found: {channel_name}"
            self._save_notification(notification)
            return notification

        # Send notification
        success = channel.send(notification)
        notification.status = "sent" if success else "failed"

        # Save to history
        self._save_notification(notification)

        return notification

    def broadcast(self, title: str, message: str, event_type: str,
                  priority: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> List[Notification]:
        """
        Broadcast notification to all channels for event type.

        Args:
            title: Notification title
            message: Notification message
            event_type: Type of event
            priority: Priority level
            data: Additional data

        Returns:
            List of Notification objects
        """
        channels = self.get_channels_for_event(event_type)
        notifications = []

        for channel_name in channels:
            if channel_name in self.channels:
                notification = self.send(
                    channel_name=channel_name,
                    title=title,
                    message=message,
                    event_type=event_type,
                    priority=priority,
                    data=data
                )
                notifications.append(notification)

        return notifications

    def _save_notification(self, notification: Notification) -> None:
        """Save notification to history."""
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        history_file = self.history_dir / f"{date_str}.yaml"

        history = []
        if history_file.exists():
            with open(history_file, 'r') as f:
                history = yaml.safe_load(f) or []

        history.append(notification.to_dict())

        with open(history_file, 'w') as f:
            yaml.dump(history, f, default_flow_style=False)

    def test_channel(self, channel_name: str) -> bool:
        """Test a notification channel."""
        channel = self.channels.get(channel_name)
        if not channel:
            print(f"Channel not found: {channel_name}")
            return False

        print(f"Testing channel: {channel_name}")
        success = channel.test()
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")

        return success

    def list_channels(self) -> Dict[str, Dict[str, Any]]:
        """List all configured channels."""
        result = {}
        for name, channel in self.channels.items():
            result[name] = {
                'name': channel.name,
                'available': channel.test()
            }
        return result

    def get_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get notification history."""
        history = []

        for history_file in sorted(self.history_dir.glob("*.yaml"), reverse=True)[:days]:
            with open(history_file, 'r') as f:
                day_history = yaml.safe_load(f) or []
            history.extend(day_history)

        return history

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Notification Dispatcher',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Send command
    send_parser = subparsers.add_parser('send', help='Send notification')
    send_parser.add_argument('--channel', '-c', required=True, help='Channel name')
    send_parser.add_argument('--title', '-t', default='Notification', help='Title')
    send_parser.add_argument('--message', '-m', required=True, help='Message')
    send_parser.add_argument('--event', '-e', default='notification', help='Event type')
    send_parser.add_argument('--priority', '-p', choices=['low', 'normal', 'high', 'critical'])
    send_parser.add_argument('--data', '-d', help='JSON data')

    # Broadcast command
    broadcast_parser = subparsers.add_parser('broadcast', help='Broadcast notification')
    broadcast_parser.add_argument('--event', '-e', required=True, help='Event type')
    broadcast_parser.add_argument('--title', '-t', default='Notification', help='Title')
    broadcast_parser.add_argument('--message', '-m', required=True, help='Message')
    broadcast_parser.add_argument('--priority', '-p', choices=['low', 'normal', 'high', 'critical'])
    broadcast_parser.add_argument('--data', '-d', help='JSON data')

    # Config command
    config_parser = subparsers.add_parser('config', help='Configuration')
    config_parser.add_argument('--list', '-l', action='store_true', help='List channels')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test channel')
    test_parser.add_argument('--channel', '-c', required=True, help='Channel to test')

    # History command
    history_parser = subparsers.add_parser('history', help='Show history')
    history_parser.add_argument('--days', '-d', type=int, default=7, help='Days to show')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatcher = NotificationDispatcher()

    try:
        if args.command == 'send':
            data = json.loads(args.data) if args.data else None
            notification = dispatcher.send(
                channel_name=args.channel,
                title=args.title,
                message=args.message,
                event_type=args.event,
                priority=args.priority,
                data=data
            )
            print(f"Notification {notification.notification_id}: {notification.status}")
            if notification.error:
                print(f"Error: {notification.error}")

        elif args.command == 'broadcast':
            data = json.loads(args.data) if args.data else None
            notifications = dispatcher.broadcast(
                title=args.title,
                message=args.message,
                event_type=args.event,
                priority=args.priority,
                data=data
            )
            print(f"Broadcast to {len(notifications)} channels:")
            for n in notifications:
                print(f"  {n.channel}: {n.status}")

        elif args.command == 'config':
            if args.list:
                channels = dispatcher.list_channels()
                print("\nConfigured Channels:")
                for name, info in channels.items():
                    status = "Available" if info['available'] else "Unavailable"
                    print(f"  {name}: {status}")

        elif args.command == 'test':
            success = dispatcher.test_channel(args.channel)
            sys.exit(0 if success else 1)

        elif args.command == 'history':
            history = dispatcher.get_history(args.days)
            print(f"\nNotification History (last {args.days} days):")
            print("-" * 60)
            for n in history[:50]:
                print(f"{n['timestamp'][:19]} [{n['channel']}] {n['title']}: {n['status']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
