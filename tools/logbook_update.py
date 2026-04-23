#!/usr/bin/env python3
"""
logbook_update.py - LogBook update automation tool

Automates LogBook entry creation and updates for task operations,
preview tracking, and agent work logs.

Exit codes:
  0 - Update successful
  1 - Validation error
  2 - File/parse error

Usage:
  python tools/logbook_update.py --task <task_id> --action <action>
  python tools/logbook_update.py --preview <task_id> --status approved
  python tools/logbook_update.py --agent <agent_id> --log "Work completed"

Reference: PM_Operating_Manual.md
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

class LogBookUpdater:
    """Manage LogBook entries for various the system operations."""

    def __init__(self, root_dir: Path, verbose: bool = False, dry_run: bool = False):
        self.root_dir = root_dir
        self.verbose = verbose
        self.dry_run = dry_run
        self.logbook_dir = root_dir / "LogBook"
        self.errors: list[str] = []

    def ensure_directories(self) -> None:
        """Ensure LogBook directory structure exists."""
        dirs = [
            self.logbook_dir,
            self.logbook_dir / "tasks",
            self.logbook_dir / "previews",
            self.logbook_dir / "agents",
            self.logbook_dir / "pm",
        ]

        for dir_path in dirs:
            if not dir_path.exists() and not self.dry_run:
                dir_path.mkdir(parents=True, exist_ok=True)
                if self.verbose:
                    print(f"  Created directory: {dir_path}")

    def update_task_entry(
        self,
        task_id: str,
        action: str,
        status: str = "in_progress",
        message: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> bool:
        """Update or create a task LogBook entry."""
        task_log_dir = self.logbook_dir / "tasks" / task_id
        log_file = task_log_dir / "log.yaml"

        # Load existing log or create new
        if log_file.exists():
            try:
                with open(log_file) as f:
                    log_data = yaml.safe_load(f) or {}
            except Exception as e:
                self.errors.append(f"Error reading {log_file}: {e}")
                log_data = {}
        else:
            log_data = {
                "task_id": task_id,
                "created": datetime.now().isoformat(),
                "entries": []
            }

        # Create new entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "status": status,
        }

        if message:
            entry["message"] = message
        if metadata:
            entry["metadata"] = metadata

        # Append entry
        if "entries" not in log_data:
            log_data["entries"] = []
        log_data["entries"].append(entry)
        log_data["last_updated"] = datetime.now().isoformat()
        log_data["last_action"] = action
        log_data["last_status"] = status

        if self.dry_run:
            print(f"[DRY RUN] Would update task log: {log_file}")
            print(f"  Entry: {entry}")
            return True

        # Write log
        try:
            task_log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_file, "w") as f:
                yaml.dump(log_data, f, default_flow_style=False, sort_keys=False)
            if self.verbose:
                print(f"  Updated task log: {log_file}")
            return True
        except Exception as e:
            self.errors.append(f"Error writing {log_file}: {e}")
            return False

    def update_preview_status(
        self,
        task_id: str,
        status: str,
        decision: Optional[str] = None,
        reviewer: Optional[str] = None,
        comments: Optional[str] = None
    ) -> bool:
        """Update preview approval status."""
        preview_dir = self.logbook_dir / "previews" / task_id

        # Create or update approval.json
        approval_file = preview_dir / "approval.json"

        approval_data = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "status": status,
        }

        if decision:
            approval_data["decision"] = decision
        if reviewer:
            approval_data["reviewer"] = reviewer
        if comments:
            approval_data["comments"] = comments

        if self.dry_run:
            print(f"[DRY RUN] Would update preview approval: {approval_file}")
            print(f"  Data: {json.dumps(approval_data, indent=2)}")
            return True

        try:
            preview_dir.mkdir(parents=True, exist_ok=True)
            with open(approval_file, "w") as f:
                json.dump(approval_data, f, indent=2)
            if self.verbose:
                print(f"  Updated preview approval: {approval_file}")
            return True
        except Exception as e:
            self.errors.append(f"Error writing {approval_file}: {e}")
            return False

    def log_agent_work(
        self,
        agent_id: str,
        message: str,
        work_type: str = "task",
        status: str = "completed",
        artifacts: Optional[list] = None
    ) -> bool:
        """Log agent work entry."""
        agent_log_dir = self.logbook_dir / "agents" / agent_id
        log_file = agent_log_dir / "work_log.yaml"

        # Load existing log or create new
        if log_file.exists():
            try:
                with open(log_file) as f:
                    log_data = yaml.safe_load(f) or {}
            except Exception as e:
                self.errors.append(f"Error reading {log_file}: {e}")
                log_data = {}
        else:
            log_data = {
                "agent_id": agent_id,
                "created": datetime.now().isoformat(),
                "entries": []
            }

        # Create entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "work_type": work_type,
            "status": status,
            "message": message,
        }

        if artifacts:
            entry["artifacts"] = artifacts

        # Append entry
        if "entries" not in log_data:
            log_data["entries"] = []
        log_data["entries"].append(entry)
        log_data["last_updated"] = datetime.now().isoformat()

        if self.dry_run:
            print(f"[DRY RUN] Would update agent log: {log_file}")
            print(f"  Entry: {entry}")
            return True

        try:
            agent_log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_file, "w") as f:
                yaml.dump(log_data, f, default_flow_style=False, sort_keys=False)
            if self.verbose:
                print(f"  Updated agent log: {log_file}")
            return True
        except Exception as e:
            self.errors.append(f"Error writing {log_file}: {e}")
            return False

    def update_pm_state(
        self,
        key: str,
        value: any,
        section: str = "state"
    ) -> bool:
        """Update PM state file."""
        state_file = self.logbook_dir / "pm" / "STATE.md"

        # For PM state, we append to markdown format
        timestamp = datetime.now().isoformat()
        entry = f"\n## {section}: {key}\n\n"
        entry += f"**Updated:** {timestamp}\n\n"
        entry += f"**Value:** {value}\n\n"
        entry += "---\n"

        if self.dry_run:
            print(f"[DRY RUN] Would append to PM state: {state_file}")
            print(f"  Entry:\n{entry}")
            return True

        try:
            (self.logbook_dir / "pm").mkdir(parents=True, exist_ok=True)

            # Append to existing file or create new
            mode = "a" if state_file.exists() else "w"
            with open(state_file, mode) as f:
                if mode == "w":
                    f.write("# PM State Log\n\n")
                    f.write(f"Created: {timestamp}\n\n")
                    f.write("---\n")
                f.write(entry)

            if self.verbose:
                print(f"  Updated PM state: {state_file}")
            return True
        except Exception as e:
            self.errors.append(f"Error writing {state_file}: {e}")
            return False

    def list_entries(self, entry_type: str = "all", limit: int = 10) -> list:
        """List recent LogBook entries."""
        entries = []

        if entry_type in ["all", "tasks"]:
            task_dir = self.logbook_dir / "tasks"
            if task_dir.exists():
                for task_log in task_dir.glob("*/log.yaml"):
                    try:
                        with open(task_log) as f:
                            data = yaml.safe_load(f) or {}
                        entries.append({
                            "type": "task",
                            "id": data.get("task_id", task_log.parent.name),
                            "last_updated": data.get("last_updated"),
                            "last_action": data.get("last_action"),
                            "file": str(task_log)
                        })
                    except Exception:
                        pass

        if entry_type in ["all", "previews"]:
            preview_dir = self.logbook_dir / "previews"
            if preview_dir.exists():
                for approval in preview_dir.glob("*/approval.json"):
                    try:
                        with open(approval) as f:
                            data = json.load(f)
                        entries.append({
                            "type": "preview",
                            "id": data.get("task_id", approval.parent.name),
                            "last_updated": data.get("timestamp"),
                            "status": data.get("status", data.get("decision")),
                            "file": str(approval)
                        })
                    except Exception:
                        pass

        if entry_type in ["all", "agents"]:
            agent_dir = self.logbook_dir / "agents"
            if agent_dir.exists():
                for agent_log in agent_dir.glob("*/work_log.yaml"):
                    try:
                        with open(agent_log) as f:
                            data = yaml.safe_load(f) or {}
                        entries.append({
                            "type": "agent",
                            "id": data.get("agent_id", agent_log.parent.name),
                            "last_updated": data.get("last_updated"),
                            "entry_count": len(data.get("entries", [])),
                            "file": str(agent_log)
                        })
                    except Exception:
                        pass

        # Sort by last_updated
        entries.sort(key=lambda x: x.get("last_updated") or "", reverse=True)
        return entries[:limit]

def main():
    parser = argparse.ArgumentParser(
        description="LogBook update automation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Update successful
  1 - Validation error
  2 - File/parse error

Examples:
  %(prog)s --task auth-service --action regenerate --status completed
  %(prog)s --preview my-task --status approved --reviewer "PM"
  %(prog)s --agent agent-001 --log "Completed code review"
  %(prog)s --list --type tasks --limit 5
        """
    )

    # Operation modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--task", "-b",
        metavar="TASK_ID",
        help="Update task LogBook entry"
    )
    mode_group.add_argument(
        "--preview", "-p",
        metavar="TASK_ID",
        help="Update preview approval status"
    )
    mode_group.add_argument(
        "--agent", "-a",
        metavar="AGENT_ID",
        help="Log agent work entry"
    )
    mode_group.add_argument(
        "--pm-state",
        metavar="KEY",
        help="Update PM state"
    )
    mode_group.add_argument(
        "--list",
        action="store_true",
        help="List recent LogBook entries"
    )

    # Task options
    parser.add_argument(
        "--action",
        help="Action being performed (for task updates)"
    )
    parser.add_argument(
        "--status",
        default="in_progress",
        help="Status of the action (default: in_progress)"
    )
    parser.add_argument(
        "--message", "-m",
        help="Message or description"
    )

    # Preview options
    parser.add_argument(
        "--decision",
        choices=["approved", "rejected", "pending"],
        help="Preview decision"
    )
    parser.add_argument(
        "--reviewer",
        help="Reviewer name/ID"
    )
    parser.add_argument(
        "--comments",
        help="Review comments"
    )

    # Agent options
    parser.add_argument(
        "--log",
        dest="log_message",
        help="Log message for agent work"
    )
    parser.add_argument(
        "--work-type",
        default="task",
        help="Type of work (default: task)"
    )

    # PM state options
    parser.add_argument(
        "--value",
        help="Value for PM state update"
    )
    parser.add_argument(
        "--section",
        default="state",
        help="Section for PM state (default: state)"
    )

    # List options
    parser.add_argument(
        "--type",
        choices=["all", "tasks", "previews", "agents"],
        default="all",
        help="Entry type to list (default: all)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of entries to list (default: 10)"
    )

    # Common options
    parser.add_argument(
        "--dir", "-d",
        default=".",
        help="Root directory (default: current directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    root_dir = Path(args.dir)
    if not root_dir.exists():
        print(f"Error: Directory not found: {root_dir}", file=sys.stderr)
        sys.exit(2)

    updater = LogBookUpdater(
        root_dir=root_dir,
        verbose=args.verbose,
        dry_run=args.dry_run
    )

    # Ensure directories exist
    updater.ensure_directories()

    success = True

    # Handle different modes
    if args.task:
        if not args.action:
            print("Error: --action is required for task updates", file=sys.stderr)
            sys.exit(1)
        success = updater.update_task_entry(
            task_id=args.task,
            action=args.action,
            status=args.status,
            message=args.message
        )
        if success:
            print(f"Updated task entry: {args.task}")

    elif args.preview:
        success = updater.update_preview_status(
            task_id=args.preview,
            status=args.status,
            decision=args.decision,
            reviewer=args.reviewer,
            comments=args.comments
        )
        if success:
            print(f"Updated preview status: {args.preview}")

    elif args.agent:
        if not args.log_message:
            print("Error: --log is required for agent logging", file=sys.stderr)
            sys.exit(1)
        success = updater.log_agent_work(
            agent_id=args.agent,
            message=args.log_message,
            work_type=args.work_type,
            status=args.status
        )
        if success:
            print(f"Logged agent work: {args.agent}")

    elif args.pm_state:
        if not args.value:
            print("Error: --value is required for PM state updates", file=sys.stderr)
            sys.exit(1)
        success = updater.update_pm_state(
            key=args.pm_state,
            value=args.value,
            section=args.section
        )
        if success:
            print(f"Updated PM state: {args.pm_state}")

    elif args.list:
        entries = updater.list_entries(entry_type=args.type, limit=args.limit)

        if args.format == "json":
            print(json.dumps(entries, indent=2))
        else:
            print(f"\nLogBook Entries ({args.type}):")
            print("-" * 50)
            for entry in entries:
                print(f"  [{entry['type']}] {entry['id']}")
                if entry.get('last_updated'):
                    print(f"    Updated: {entry['last_updated']}")
                if entry.get('last_action'):
                    print(f"    Action: {entry['last_action']}")
                if entry.get('status'):
                    print(f"    Status: {entry['status']}")
                print()

    else:
        parser.print_help()
        sys.exit(0)

    # Handle errors
    if updater.errors:
        print("\nErrors:", file=sys.stderr)
        for error in updater.errors:
            print(f"  - {error}", file=sys.stderr)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
