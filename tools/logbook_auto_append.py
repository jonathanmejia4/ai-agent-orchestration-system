#!/usr/bin/env python3
"""
logbook_auto_append.py - LogBook Auto-Append Utility

Safely appends entries to LogBook YAML files with validation,
backup, and atomic write operations.

Features:
- Validates entries before appending
- Creates backups before modification
- Atomic writes to prevent corruption
- Supports all agent LogBook types
- Auto-generates timestamps and IDs

Exit codes:
  0 - Entry appended successfully
  1 - Validation error
  2 - File/write error

Usage:
  python tools/logbook_auto_append.py --agent builder --action implemented --description "Completed feature X"
  python tools/logbook_auto_append.py --agent critic --verdict APPROVED --task-id 3.2
  python tools/logbook_auto_append.py --agent pm --decision "Approved WO-2025-001"
  python tools/logbook_auto_append.py --file LogBook/builder/progress.yaml --entry '{"action": "test"}'

Reference: state-persistence-protocol.md, validate_logbook.py
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class AppendResult:
    """Result of append operation."""
    success: bool
    file_path: str
    entry_id: Optional[str] = None
    backup_path: Optional[str] = None
    error: Optional[str] = None
    warnings: list = field(default_factory=list)

class LogBookAppender:
    """Safely appends entries to LogBook files."""

    # LogBook paths by agent
    AGENT_PATHS = {
        "pm": "LogBook/pm/STATE.md",
        "builder": "LogBook/builder/progress.yaml",
        "critic": "LogBook/critic/verdicts.yaml",
        "planner": "LogBook/planner/plans.yaml",
    }

    # Required fields by entry type
    REQUIRED_FIELDS = {
        "action": ["action", "description"],
        "verdict": ["verdict", "task_id"],
        "decision": ["decision", "rationale"],
        "plan": ["plan_id", "description"],
        "escalation": ["escalation_type", "description"],
    }

    # Valid values for enum fields
    VALID_VERDICTS = ["APPROVED", "REJECTED", "NEEDS_REVISION", "PENDING"]
    VALID_ACTIONS = ["implemented", "revised", "tested", "fixed", "created", "modified", "deleted"]
    VALID_AGENTS = ["pm", "builder", "critic", "planner", "system"]

    def __init__(
        self,
        base_path: str = ".",
        backup_dir: str = ".state_backups",
        verbose: bool = False
    ):
        self.base_path = Path(base_path)
        self.backup_dir = self.base_path / backup_dir
        self.verbose = verbose

    def log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def append_entry(
        self,
        agent: str,
        entry_type: str,
        entry_data: dict,
        file_path: Optional[str] = None
    ) -> AppendResult:
        """
        Append an entry to a LogBook file.

        Args:
            agent: Agent name (pm, builder, critic, planner)
            entry_type: Type of entry (action, verdict, decision, plan)
            entry_data: Entry data to append
            file_path: Optional explicit file path (overrides agent default)

        Returns:
            AppendResult with success status and details
        """
        result = AppendResult(
            success=False,
            file_path=""
        )

        # Determine file path
        if file_path:
            target_path = self.base_path / file_path
        elif agent in self.AGENT_PATHS:
            target_path = self.base_path / self.AGENT_PATHS[agent]
        else:
            result.error = f"Unknown agent: {agent}"
            return result

        result.file_path = str(target_path)

        # Validate entry
        validation = self._validate_entry(agent, entry_type, entry_data)
        if not validation["valid"]:
            result.error = f"Validation failed: {validation['errors']}"
            result.warnings = validation.get("warnings", [])
            return result
        result.warnings = validation.get("warnings", [])

        # Prepare entry with metadata
        entry = self._prepare_entry(agent, entry_type, entry_data)
        result.entry_id = entry.get("entry_id") or entry.get("verdict_id")

        # Handle different file types
        if target_path.suffix == ".md":
            return self._append_to_markdown(target_path, entry, result)
        else:
            return self._append_to_yaml(target_path, entry, result)

    def _validate_entry(self, agent: str, entry_type: str, entry_data: dict) -> dict:
        """Validate entry data."""
        errors = []
        warnings = []

        # Check agent
        if agent.lower() not in self.VALID_AGENTS:
            warnings.append(f"Unknown agent: {agent}")

        # Check required fields
        required = self.REQUIRED_FIELDS.get(entry_type, [])
        for field in required:
            if field not in entry_data:
                errors.append(f"Missing required field: {field}")

        # Validate specific field values
        if "verdict" in entry_data:
            if entry_data["verdict"].upper() not in self.VALID_VERDICTS:
                errors.append(f"Invalid verdict: {entry_data['verdict']}")

        if "action" in entry_data:
            if entry_data["action"].lower() not in self.VALID_ACTIONS:
                warnings.append(f"Uncommon action type: {entry_data['action']}")

        # Check for empty description
        if "description" in entry_data and not entry_data["description"].strip():
            errors.append("Description cannot be empty")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _prepare_entry(self, agent: str, entry_type: str, entry_data: dict) -> dict:
        """Prepare entry with auto-generated fields."""
        entry = dict(entry_data)

        # Add timestamp if not present
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Add agent if not present
        if "agent" not in entry:
            entry["agent"] = agent

        # Generate entry ID based on type
        timestamp_short = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        if entry_type == "verdict":
            if "verdict_id" not in entry:
                entry["verdict_id"] = f"VRD-{timestamp_short}"
        elif entry_type == "action":
            if "entry_id" not in entry:
                entry["entry_id"] = f"ACT-{timestamp_short}"
        elif entry_type == "decision":
            if "decision_id" not in entry:
                entry["decision_id"] = f"DEC-{timestamp_short}"
        elif entry_type == "escalation":
            if "escalation_id" not in entry:
                entry["escalation_id"] = f"ESC-{timestamp_short}"

        return entry

    def _append_to_yaml(self, file_path: Path, entry: dict, result: AppendResult) -> AppendResult:
        """Append entry to YAML file."""
        if not HAS_YAML:
            result.error = "PyYAML not installed (pip install pyyaml)"
            return result

        try:
            # Create parent directory if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing data or create new structure
            if file_path.exists():
                # Create backup
                backup_path = self._create_backup(file_path)
                result.backup_path = str(backup_path)

                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}
                self.log(f"Creating new file: {file_path}")

            # Determine the list key based on file type
            list_key = self._get_list_key(file_path)

            # Initialize list if not present
            if list_key not in data:
                data[list_key] = []

            # Append entry
            data[list_key].append(entry)

            # Update metadata
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"]["last_updated"] = datetime.utcnow().isoformat() + "Z"
            data["metadata"]["entry_count"] = len(data[list_key])

            # Atomic write
            self._atomic_write_yaml(file_path, data)

            result.success = True
            self.log(f"Entry appended to {file_path}")

        except Exception as e:
            result.error = f"Write error: {e}"
            # Attempt to restore from backup
            if result.backup_path and Path(result.backup_path).exists():
                try:
                    shutil.copy(result.backup_path, file_path)
                    self.log(f"Restored from backup: {result.backup_path}")
                except Exception as restore_error:
                    result.error += f" (restore also failed: {restore_error})"

        return result

    def _append_to_markdown(self, file_path: Path, entry: dict, result: AppendResult) -> AppendResult:
        """Append entry to Markdown file (STATE.md format)."""
        try:
            # Create parent directory if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing content or create new
            if file_path.exists():
                # Create backup
                backup_path = self._create_backup(file_path)
                result.backup_path = str(backup_path)

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = self._create_state_template()
                self.log(f"Creating new STATE.md: {file_path}")

            # Format entry for markdown
            md_entry = self._format_entry_as_markdown(entry)

            # Find insertion point (before Document History or at end)
            if "### Recent Actions" in content:
                # Insert after "### Recent Actions" header
                parts = content.split("### Recent Actions")
                if len(parts) == 2:
                    # Find the end of the Recent Actions section
                    lines = parts[1].split('\n')
                    insert_idx = 0
                    for i, line in enumerate(lines):
                        if line.startswith('###') or line.startswith('---'):
                            insert_idx = i
                            break
                        insert_idx = i + 1

                    lines.insert(insert_idx, md_entry)
                    content = parts[0] + "### Recent Actions" + '\n'.join(lines)
            else:
                # Append to end
                content += f"\n\n### Recent Actions\n{md_entry}"

            # Update last_updated timestamp
            content = self._update_timestamp_in_markdown(content)

            # Atomic write
            self._atomic_write_text(file_path, content)

            result.success = True
            self.log(f"Entry appended to {file_path}")

        except Exception as e:
            result.error = f"Write error: {e}"

        return result

    def _get_list_key(self, file_path: Path) -> str:
        """Determine the list key for YAML file based on path."""
        name = file_path.stem.lower()
        if "verdict" in name:
            return "verdicts"
        elif "progress" in name:
            return "entries"
        elif "plan" in name:
            return "plans"
        elif "escalation" in name:
            return "escalations"
        else:
            return "entries"

    def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of the file."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"

        # Create date-based subdirectory
        date_dir = self.backup_dir / datetime.utcnow().strftime("%Y-%m")
        date_dir.mkdir(exist_ok=True)

        backup_path = date_dir / backup_name
        shutil.copy2(file_path, backup_path)

        self.log(f"Backup created: {backup_path}")
        return backup_path

    def _atomic_write_yaml(self, file_path: Path, data: dict):
        """Atomically write YAML data to file."""
        # Write to temp file first
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=f".{file_path.stem}_",
            suffix=".tmp"
        )

        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            shutil.move(temp_path, file_path)

        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _atomic_write_text(self, file_path: Path, content: str):
        """Atomically write text content to file."""
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=f".{file_path.stem}_",
            suffix=".tmp"
        )

        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            shutil.move(temp_path, file_path)

        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _format_entry_as_markdown(self, entry: dict) -> str:
        """Format entry as markdown for STATE.md."""
        timestamp = entry.get("timestamp", datetime.utcnow().isoformat() + "Z")
        action = entry.get("action", entry.get("decision", "update"))
        description = entry.get("description", entry.get("rationale", ""))

        return f"- {timestamp}: {action} - {description}\n"

    def _update_timestamp_in_markdown(self, content: str) -> str:
        """Update the Last Updated timestamp in markdown content."""
        import re
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # Try to find and replace existing timestamp
        pattern = r'\*\*Last Updated:\*\* \d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?'
        replacement = f'**Last Updated:** {timestamp}'

        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
        elif "Last Updated:" in content:
            # Handle other formats
            pattern2 = r'Last Updated:\s*\d{4}-\d{2}-\d{2}'
            content = re.sub(pattern2, f'Last Updated: {timestamp[:10]}', content)

        return content

    def _create_state_template(self) -> str:
        """Create a new STATE.md template."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"""## Project State

**Last Updated:** {timestamp}
**Version:** 1.0.0

### Current Phase
- **Phase:** Active
- **Status:** Operational

### Recent Actions
"""

def main():
    parser = argparse.ArgumentParser(
        description="LogBook Auto-Append Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Append action entry for builder
  %(prog)s --agent builder --type action --action implemented --description "Completed feature"

  # Append verdict entry for critic
  %(prog)s --agent critic --type verdict --verdict APPROVED --task-id 3.2 --work-order WO-2025-001

  # Append decision for PM
  %(prog)s --agent pm --type decision --decision "Approved architecture" --rationale "Meets requirements"

  # Append from JSON
  %(prog)s --agent builder --type action --json '{"action": "fixed", "description": "Bug fix"}'
        """
    )

    parser.add_argument(
        "--agent",
        required=True,
        choices=["pm", "builder", "critic", "planner"],
        help="Agent making the entry"
    )

    parser.add_argument(
        "--type",
        default="action",
        choices=["action", "verdict", "decision", "plan", "escalation"],
        help="Type of entry (default: action)"
    )

    parser.add_argument(
        "--file",
        help="Explicit file path (overrides agent default)"
    )

    # Action entry fields
    parser.add_argument("--action", help="Action type (for action entries)")
    parser.add_argument("--description", help="Entry description")

    # Verdict entry fields
    parser.add_argument("--verdict", help="Verdict value (APPROVED, REJECTED, etc.)")
    parser.add_argument("--task-id", help="Task ID for verdict")
    parser.add_argument("--work-order", help="Work order ID")
    parser.add_argument("--confidence", type=float, help="Confidence score (0-1)")

    # Decision entry fields
    parser.add_argument("--decision", help="Decision made")
    parser.add_argument("--rationale", help="Rationale for decision")

    # JSON input
    parser.add_argument(
        "--json",
        help="Entry data as JSON string"
    )

    # Options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only, don't write"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Build entry data
    if args.json:
        try:
            entry_data = json.loads(args.json)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        entry_data = {}
        if args.action:
            entry_data["action"] = args.action
        if args.description:
            entry_data["description"] = args.description
        if args.verdict:
            entry_data["verdict"] = args.verdict
        if args.task_id:
            entry_data["task_id"] = args.task_id
        if args.work_order:
            entry_data["work_order_id"] = args.work_order
        if args.confidence:
            entry_data["confidence"] = args.confidence
        if args.decision:
            entry_data["decision"] = args.decision
        if args.rationale:
            entry_data["rationale"] = args.rationale

    # Create appender
    appender = LogBookAppender(verbose=args.verbose)

    if args.dry_run:
        # Validate only
        validation = appender._validate_entry(args.agent, args.type, entry_data)
        if args.format == "json":
            print(json.dumps(validation, indent=2))
        else:
            if validation["valid"]:
                print("Validation: PASSED")
            else:
                print("Validation: FAILED")
                for error in validation["errors"]:
                    print(f"  Error: {error}")
            for warning in validation.get("warnings", []):
                print(f"  Warning: {warning}")
        sys.exit(0 if validation["valid"] else 1)

    # Append entry
    result = appender.append_entry(
        agent=args.agent,
        entry_type=args.type,
        entry_data=entry_data,
        file_path=args.file
    )

    # Output result
    if args.format == "json":
        output = {
            "success": result.success,
            "file_path": result.file_path,
            "entry_id": result.entry_id,
            "backup_path": result.backup_path,
            "error": result.error,
            "warnings": result.warnings
        }
        print(json.dumps(output, indent=2))
    else:
        if result.success:
            print(f"Entry appended successfully")
            print(f"  File: {result.file_path}")
            if result.entry_id:
                print(f"  Entry ID: {result.entry_id}")
            if result.backup_path:
                print(f"  Backup: {result.backup_path}")
        else:
            print(f"Failed to append entry: {result.error}", file=sys.stderr)

        for warning in result.warnings:
            print(f"  Warning: {warning}")

    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()
