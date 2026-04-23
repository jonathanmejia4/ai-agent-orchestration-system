#!/usr/bin/env python3
"""
Action Approver

Approves critical actions during validation hooks.
Used by .claude/hooks/critical-action-validator.sh to programmatically
approve actions that require explicit authorization.

Usage:
    python3 tools/approve_action.py --action <action_type> --target <target>
    python3 tools/approve_action.py --action delete --target "src/important.py"
    python3 tools/approve_action.py --action modify_tier1 --target "CLAUDE.md"

Action Types:
    - delete: File or directory deletion
    - modify_tier1: Modification to Tier 1 governance documents
    - security_change: Security-sensitive changes
    - rollback: Rollback operations
    - force_push: Force push to protected branches

See: .claude/hooks/critical-action-validator.sh
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

def get_current_user() -> str:
    """Get the current user identity for approval tracking."""
    user = os.environ.get('AGENT_USER')
    if user:
        return user

    try:
        import subprocess
        result = subprocess.run(
            ['git', 'config', 'user.email'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    user = os.environ.get('USER') or os.environ.get('USERNAME')
    if user:
        return user

    return "unknown_user"

def get_approval_log_path() -> Path:
    """Get path to approval log file."""
    logbook = Path("LogBook/pm/approvals")
    logbook.mkdir(parents=True, exist_ok=True)
    return logbook / "action_approvals.yaml"

def log_approval(action_type: str, target: str, approved_by: str, reason: str = None) -> dict:
    """Log an action approval."""
    approval_record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action_type": action_type,
        "target": target,
        "approved_by": approved_by,
        "reason": reason or "Programmatic approval via approve_action.py",
        "status": "approved"
    }

    # Append to log file
    log_path = get_approval_log_path()
    try:
        import yaml
        existing = []
        if log_path.exists():
            with open(log_path, 'r') as f:
                content = yaml.safe_load(f)
                if content and isinstance(content, list):
                    existing = content

        existing.append(approval_record)

        with open(log_path, 'w') as f:
            yaml.dump(existing, f, default_flow_style=False, sort_keys=False)
    except ImportError:
        # Fallback to JSON if yaml not available
        log_path = log_path.with_suffix('.json')
        existing = []
        if log_path.exists():
            with open(log_path, 'r') as f:
                existing = json.load(f)

        existing.append(approval_record)

        with open(log_path, 'w') as f:
            json.dump(existing, f, indent=2)

    return approval_record

def validate_action_type(action_type: str) -> bool:
    """Validate the action type is known."""
    known_actions = {
        'delete',
        'modify_tier1',
        'security_change',
        'rollback',
        'force_push',
        'critical',
        'destructive'
    }
    return action_type.lower() in known_actions

def main():
    parser = argparse.ArgumentParser(
        description="Approve critical actions for the system hooks"
    )
    parser.add_argument(
        '--action', '-a',
        required=True,
        help='Action type to approve (delete, modify_tier1, security_change, etc.)'
    )
    parser.add_argument(
        '--target', '-t',
        default='',
        help='Target of the action (file path, resource name, etc.)'
    )
    parser.add_argument(
        '--reason', '-r',
        default=None,
        help='Reason for approval'
    )
    parser.add_argument(
        '--user', '-u',
        default=None,
        help='Override approving user identity'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output approval record as JSON'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate and show what would be approved without logging'
    )

    args = parser.parse_args()

    # Validate action type
    if not validate_action_type(args.action):
        print(f"Warning: Unknown action type '{args.action}' (proceeding anyway)",
              file=sys.stderr)

    # Get approving user
    approving_user = args.user or get_current_user()

    if args.dry_run:
        print(f"Would approve:")
        print(f"  Action: {args.action}")
        print(f"  Target: {args.target or '(none)'}")
        print(f"  User: {approving_user}")
        print(f"  Reason: {args.reason or '(default)'}")
        sys.exit(0)

    # Log the approval
    record = log_approval(
        action_type=args.action,
        target=args.target,
        approved_by=approving_user,
        reason=args.reason
    )

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"✓ Action approved")
        print(f"  Type: {args.action}")
        print(f"  Target: {args.target or '(none)'}")
        print(f"  By: {approving_user}")
        print(f"  At: {record['timestamp']}")

    sys.exit(0)

if __name__ == '__main__':
    main()
