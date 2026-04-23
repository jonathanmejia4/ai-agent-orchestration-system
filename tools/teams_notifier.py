#!/usr/bin/env python3
"""
Microsoft Teams Notifier
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Notifications

Sends notifications to Microsoft Teams channels via webhooks.
Used for build alerts, deployment notifications, and status updates.
"""

import argparse
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

class MessageType(Enum):
    """Types of notification messages."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    BUILD = "build"
    DEPLOY = "deploy"

@dataclass
class NotificationResult:
    """Result of sending a notification."""
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None

class TeamsNotifier:
    """Sends notifications to Microsoft Teams."""

    # Theme colors for different message types
    COLORS = {
        MessageType.INFO: "0078D7",
        MessageType.SUCCESS: "00A651",
        MessageType.WARNING: "FFC107",
        MessageType.ERROR: "DC3545",
        MessageType.BUILD: "6C757D",
        MessageType.DEPLOY: "17A2B8",
    }

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize notifier.

        Args:
            webhook_url: Teams webhook URL (or use TEAMS_WEBHOOK_URL env var)
        """
        self.webhook_url = webhook_url or os.environ.get("TEAMS_WEBHOOK_URL")

    def _create_adaptive_card(
        self,
        title: str,
        message: str,
        message_type: MessageType = MessageType.INFO,
        facts: Optional[Dict[str, str]] = None,
        actions: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Create an Adaptive Card payload."""
        color = self.COLORS.get(message_type, self.COLORS[MessageType.INFO])

        body = [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": title,
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True
            }
        ]

        if facts:
            fact_set = {
                "type": "FactSet",
                "facts": [
                    {"title": k, "value": v}
                    for k, v in facts.items()
                ]
            }
            body.append(fact_set)

        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": body,
                        "msteams": {
                            "width": "Full"
                        }
                    }
                }
            ]
        }

        # Add actions if provided
        if actions:
            card["attachments"][0]["content"]["actions"] = [
                {
                    "type": "Action.OpenUrl",
                    "title": action.get("title", "View"),
                    "url": action.get("url", "#")
                }
                for action in actions
            ]

        return card

    def _create_simple_message(
        self,
        title: str,
        message: str,
        message_type: MessageType = MessageType.INFO,
        facts: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a simple MessageCard payload (legacy format)."""
        color = self.COLORS.get(message_type, self.COLORS[MessageType.INFO])

        sections = [
            {
                "activityTitle": title,
                "text": message
            }
        ]

        if facts:
            sections[0]["facts"] = [
                {"name": k, "value": v}
                for k, v in facts.items()
            ]

        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": title,
            "sections": sections
        }

    def send(
        self,
        title: str,
        message: str,
        message_type: MessageType = MessageType.INFO,
        facts: Optional[Dict[str, str]] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        use_adaptive_card: bool = True
    ) -> NotificationResult:
        """
        Send a notification to Teams.

        Args:
            title: Notification title
            message: Notification message
            message_type: Type of message
            facts: Key-value facts to display
            actions: Action buttons with url and title

        Returns:
            NotificationResult
        """
        if not self.webhook_url:
            return NotificationResult(
                success=False,
                error="No webhook URL configured"
            )

        if use_adaptive_card:
            payload = self._create_adaptive_card(
                title, message, message_type, facts, actions
            )
        else:
            payload = self._create_simple_message(
                title, message, message_type, facts
            )

        try:
            data = json.dumps(payload).encode('utf-8')
            request = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )

            response = urllib.request.urlopen(request, timeout=30)
            return NotificationResult(
                success=True,
                status_code=response.status
            )

        except urllib.error.HTTPError as e:
            return NotificationResult(
                success=False,
                status_code=e.code,
                error=str(e)
            )
        except Exception as e:
            return NotificationResult(
                success=False,
                error=str(e)
            )

    def send_build_notification(
        self,
        build_id: str,
        status: str,
        branch: str = "main",
        commit: Optional[str] = None,
        duration: Optional[str] = None,
        url: Optional[str] = None
    ) -> NotificationResult:
        """Send a build status notification."""
        is_success = status.lower() in ("success", "passed", "completed")
        message_type = MessageType.SUCCESS if is_success else MessageType.ERROR

        emoji = "✅" if is_success else "❌"
        title = f"{emoji} Build {build_id}: {status.upper()}"
        message = f"Build on branch `{branch}` has {status.lower()}."

        facts = {"Branch": branch, "Status": status}
        if commit:
            facts["Commit"] = commit[:8]
        if duration:
            facts["Duration"] = duration

        actions = []
        if url:
            actions.append({"title": "View Build", "url": url})

        return self.send(title, message, message_type, facts, actions)

    def send_deploy_notification(
        self,
        environment: str,
        version: str,
        status: str,
        deployer: Optional[str] = None,
        url: Optional[str] = None
    ) -> NotificationResult:
        """Send a deployment notification."""
        is_success = status.lower() in ("success", "completed", "deployed")
        message_type = MessageType.SUCCESS if is_success else MessageType.ERROR

        emoji = "🚀" if is_success else "💥"
        title = f"{emoji} Deployment to {environment}: {status.upper()}"
        message = f"Version `{version}` deployment to {environment}."

        facts = {
            "Environment": environment,
            "Version": version,
            "Status": status,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if deployer:
            facts["Deployed By"] = deployer

        actions = []
        if url:
            actions.append({"title": "View Deployment", "url": url})

        return self.send(title, message, message_type, facts, actions)

    def send_alert(
        self,
        alert_title: str,
        description: str,
        severity: str = "warning",
        source: Optional[str] = None,
        url: Optional[str] = None
    ) -> NotificationResult:
        """Send an alert notification."""
        severity_map = {
            "critical": MessageType.ERROR,
            "error": MessageType.ERROR,
            "warning": MessageType.WARNING,
            "info": MessageType.INFO
        }
        message_type = severity_map.get(severity.lower(), MessageType.WARNING)

        emoji_map = {
            "critical": "🔴",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        emoji = emoji_map.get(severity.lower(), "⚠️")

        title = f"{emoji} Alert: {alert_title}"

        facts = {"Severity": severity.upper()}
        if source:
            facts["Source"] = source

        actions = []
        if url:
            actions.append({"title": "View Details", "url": url})

        return self.send(title, description, message_type, facts, actions)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Send notifications to Microsoft Teams"
    )
    parser.add_argument("--webhook", help="Teams webhook URL")
    parser.add_argument("-t", "--title", required=True, help="Message title")
    parser.add_argument("-m", "--message", required=True, help="Message body")
    parser.add_argument(
        "--type",
        choices=["info", "success", "warning", "error", "build", "deploy"],
        default="info",
        help="Message type"
    )
    parser.add_argument("--fact", action="append", nargs=2,
                        metavar=("KEY", "VALUE"), help="Add a fact")
    parser.add_argument("--action", action="append", nargs=2,
                        metavar=("TITLE", "URL"), help="Add an action button")
    parser.add_argument("--build", help="Send build notification (pass build ID)")
    parser.add_argument("--deploy", help="Send deploy notification (pass environment)")
    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    notifier = TeamsNotifier(webhook_url=args.webhook)

    # Build facts and actions from args
    facts = dict(args.fact) if args.fact else None
    actions = [{"title": t, "url": u} for t, u in args.action] if args.action else None

    # Send appropriate notification
    if args.build:
        result = notifier.send_build_notification(
            build_id=args.build,
            status=args.message,
            branch=args.title
        )
    elif args.deploy:
        result = notifier.send_deploy_notification(
            environment=args.deploy,
            version=args.title,
            status=args.message
        )
    else:
        message_type = MessageType(args.type)
        result = notifier.send(
            args.title,
            args.message,
            message_type,
            facts,
            actions
        )

    if args.json:
        print(json.dumps({
            "success": result.success,
            "status_code": result.status_code,
            "error": result.error
        }))
    else:
        if result.success:
            print(f"Notification sent successfully (status: {result.status_code})")
        else:
            print(f"Failed to send notification: {result.error}")

    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()
