#!/usr/bin/env python3
"""
escalation_handler.py - the system Escalation Handler

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Workflow

Purpose:
    Handles agent escalations, routes to appropriate handlers,
    tracks resolution, and maintains escalation logs.

Usage:
    python3 escalation_handler.py create --from builder --to pm --severity urgent
    python3 escalation_handler.py status ESC-2025-001
    python3 escalation_handler.py resolve ESC-2025-001 --resolution "Approved"
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class EscalationSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class EscalationStatus(Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

@dataclass
class Escalation:
    escalation_id: str
    timestamp: str
    source_agent: str
    target_agent: str
    severity: str
    category: str
    summary: str
    status: str
    details: str = ""
    work_order_id: Optional[str] = None
    resolution: Optional[Dict] = None

    def to_dict(self) -> dict:
        return {
            "escalation_id": self.escalation_id,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "severity": self.severity,
            "category": self.category,
            "summary": self.summary,
            "status": self.status,
            "details": self.details,
            "work_order_id": self.work_order_id,
            "resolution": self.resolution
        }

class EscalationHandler:
    """Handles the system agent escalations."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.escalations_file = self.base_path / "LogBook/pm/escalations.yaml"
        self.escalations: List[Escalation] = []
        self._load_escalations()

    def _load_escalations(self):
        """Load existing escalations from file."""
        if self.escalations_file.exists() and HAS_YAML:
            try:
                with open(self.escalations_file) as f:
                    data = yaml.safe_load(f) or {}
                for esc_data in data.get("escalations", []):
                    self.escalations.append(Escalation(**esc_data))
            except Exception:
                pass

    def _save_escalations(self):
        """Save escalations to file."""
        if not HAS_YAML:
            return

        self.escalations_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "escalations": [e.to_dict() for e in self.escalations],
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        with open(self.escalations_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def _generate_id(self) -> str:
        """Generate unique escalation ID."""
        year = datetime.utcnow().year
        existing = [e for e in self.escalations if e.escalation_id.startswith(f"ESC-{year}")]
        num = len(existing) + 1
        return f"ESC-{year}-{num:03d}"

    def create(
        self,
        source_agent: str,
        target_agent: str,
        severity: str,
        category: str,
        summary: str,
        details: str = "",
        work_order_id: Optional[str] = None
    ) -> Escalation:
        """Create a new escalation."""
        escalation = Escalation(
            escalation_id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            source_agent=source_agent,
            target_agent=target_agent,
            severity=severity,
            category=category,
            summary=summary,
            status="open",
            details=details,
            work_order_id=work_order_id
        )
        self.escalations.append(escalation)
        self._save_escalations()
        return escalation

    def get(self, escalation_id: str) -> Optional[Escalation]:
        """Get escalation by ID."""
        for esc in self.escalations:
            if esc.escalation_id == escalation_id:
                return esc
        return None

    def update_status(self, escalation_id: str, status: str) -> Optional[Escalation]:
        """Update escalation status."""
        esc = self.get(escalation_id)
        if esc:
            esc.status = status
            self._save_escalations()
        return esc

    def resolve(
        self,
        escalation_id: str,
        resolution_type: str,
        resolution_details: str,
        resolved_by: str
    ) -> Optional[Escalation]:
        """Resolve an escalation."""
        esc = self.get(escalation_id)
        if esc:
            esc.status = "resolved"
            esc.resolution = {
                "resolved_by": resolved_by,
                "resolved_at": datetime.utcnow().isoformat() + "Z",
                "resolution_type": resolution_type,
                "resolution_details": resolution_details
            }
            self._save_escalations()
        return esc

    def list_open(self, target_agent: Optional[str] = None) -> List[Escalation]:
        """List open escalations."""
        result = [e for e in self.escalations if e.status in ("open", "acknowledged", "in_progress")]
        if target_agent:
            result = [e for e in result if e.target_agent == target_agent]
        return result

    def list_by_severity(self, severity: str) -> List[Escalation]:
        """List escalations by severity."""
        return [e for e in self.escalations if e.severity == severity]

def main():
    parser = argparse.ArgumentParser(description="the system Escalation Handler")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create escalation")
    create_parser.add_argument("--from", dest="source", required=True)
    create_parser.add_argument("--to", dest="target", required=True)
    create_parser.add_argument("--severity", required=True)
    create_parser.add_argument("--category", default="blocker")
    create_parser.add_argument("--summary", required=True)
    create_parser.add_argument("--details", default="")
    create_parser.add_argument("--work-order")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get escalation status")
    status_parser.add_argument("escalation_id")

    # Resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve escalation")
    resolve_parser.add_argument("escalation_id")
    resolve_parser.add_argument("--resolution", required=True)
    resolve_parser.add_argument("--type", default="approved")
    resolve_parser.add_argument("--by", default="pm")

    # List command
    list_parser = subparsers.add_parser("list", help="List escalations")
    list_parser.add_argument("--target")
    list_parser.add_argument("--severity")
    list_parser.add_argument("--open", action="store_true")

    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    handler = EscalationHandler()

    if args.command == "create":
        esc = handler.create(
            source_agent=args.source,
            target_agent=args.target,
            severity=args.severity,
            category=args.category,
            summary=args.summary,
            details=args.details,
            work_order_id=args.work_order
        )
        if args.json:
            print(json.dumps(esc.to_dict(), indent=2))
        else:
            print(f"Created: {esc.escalation_id}")

    elif args.command == "status":
        esc = handler.get(args.escalation_id)
        if esc:
            if args.json:
                print(json.dumps(esc.to_dict(), indent=2))
            else:
                print(f"ID: {esc.escalation_id}")
                print(f"Status: {esc.status}")
                print(f"Severity: {esc.severity}")
                print(f"From: {esc.source_agent} -> To: {esc.target_agent}")
                print(f"Summary: {esc.summary}")
        else:
            print(f"Escalation not found: {args.escalation_id}")
            return 1

    elif args.command == "resolve":
        esc = handler.resolve(
            args.escalation_id,
            resolution_type=args.type,
            resolution_details=args.resolution,
            resolved_by=args.by
        )
        if esc:
            print(f"Resolved: {esc.escalation_id}")
        else:
            print(f"Escalation not found: {args.escalation_id}")
            return 1

    elif args.command == "list":
        if args.open:
            escalations = handler.list_open(args.target)
        elif args.severity:
            escalations = handler.list_by_severity(args.severity)
        else:
            escalations = handler.escalations

        if args.json:
            print(json.dumps([e.to_dict() for e in escalations], indent=2))
        else:
            for esc in escalations:
                print(f"[{esc.status}] {esc.escalation_id}: {esc.summary}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
