#!/usr/bin/env python3
"""
Reconstruct PM STATE.md - Rebuild STATE.md from LogBook Entries

Reconstructs LogBook/pm/STATE.md from LogBook entries, git branches,
and task directories when the original STATE.md becomes corrupted
or out of sync. Critical for PM amnesia recovery.

Usage:
    python3 tools/reconstruct_pm_state.py
    python3 tools/reconstruct_pm_state.py --output LogBook/pm/STATE.md
    python3 tools/reconstruct_pm_state.py --dry-run
    python3 tools/reconstruct_pm_state.py --json
    python3 tools/reconstruct_pm_state.py --help

Exit Codes:
    0 - Reconstruction successful
    1 - Reconstruction failed

Referenced in:
    - .claude/guidelines/agent-coordination-protocol.md:1471, 1475
    - PLANNING/PM_Operating_Manual.md:311, 477, 491, 700, 704
    - PLANNING/AGENT_FAILURE_HANDLING_PROTOCOL.md:309

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class TaskInfo:
    """Information about a task"""
    task_id: str
    status: str = "unknown"  # active, completed, failed
    branch: Optional[str] = None
    task_spec_path: Optional[str] = None
    work_order_path: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ReconstructionResult:
    """Result of STATE.md reconstruction"""
    reconstruction_successful: bool = False
    sources_used: List[str] = field(default_factory=list)
    tasks_reconstructed: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    orphaned_branches_detected: List[str] = field(default_factory=list)
    conflicts_resolved: int = 0
    validation_passed: bool = False
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class PMStateReconstructor:
    """Reconstructs PM STATE.md from LogBook entries"""

    def __init__(self, repo_root: Optional[Path] = None,
                 output: Optional[Path] = None,
                 dry_run: bool = False,
                 verbose: bool = False):
        self.repo_root = repo_root or Path.cwd()
        self.output = output or (self.repo_root / 'LogBook' / 'pm' / 'STATE.md')
        self.dry_run = dry_run
        self.verbose = verbose

        # Directories
        self.logbook_pm = self.repo_root / 'LogBook' / 'pm'
        self.logbook_tasks = self.repo_root / 'LogBook' / 'progress' / 'tasks'
        self.work_orders = self.repo_root / 'LogBook' / 'work-orders'

        self.result = ReconstructionResult()
        self.tasks: Dict[str, TaskInfo] = {}

    def log(self, message: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def get_git_branches(self) -> List[str]:
        """Get list of git branches"""
        branches = []
        try:
            result = subprocess.run(
                ['git', 'branch', '-a'],
                capture_output=True, text=True, cwd=self.repo_root
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    line = line.strip().lstrip('* ')
                    if line and not line.startswith('remotes/'):
                        branches.append(line)
            self.result.sources_used.append("git branches")
        except Exception as e:
            self.log(f"Could not get git branches: {e}")

        return branches

    def scan_logbook_tasks(self) -> Dict[str, TaskInfo]:
        """Scan LogBook/progress/tasks/ for task directories"""
        tasks = {}

        if not self.logbook_tasks.exists():
            self.log("LogBook/progress/tasks/ not found")
            return tasks

        for task_dir in self.logbook_tasks.iterdir():
            if not task_dir.is_dir():
                continue

            task_id = task_dir.name
            task = TaskInfo(task_id=task_id)

            # Look for task.yaml/task.yml
            for spec_name in ['task.yaml', 'task.yml']:
                spec_path = task_dir / spec_name
                if spec_path.exists():
                    task.task_spec_path = str(spec_path.relative_to(self.repo_root))
                    # Try to parse status from spec
                    try:
                        content = spec_path.read_text()
                        if 'status:' in content:
                            status_match = re.search(r'status:\s*(\w+)', content)
                            if status_match:
                                task.status = status_match.group(1).lower()
                    except:
                        pass
                    break

            tasks[task_id] = task

        self.result.sources_used.append("LogBook task directories")
        return tasks

    def parse_index_md(self) -> Dict[str, TaskInfo]:
        """Parse LogBook/pm/INDEX.md for task list and statuses"""
        tasks = {}
        index_file = self.logbook_pm / 'INDEX.md'

        if not index_file.exists():
            self.log("INDEX.md not found")
            return tasks

        try:
            content = index_file.read_text()

            # Look for task entries in various formats
            # Format 1: | task-id | status | date |
            # Format 2: - task-id: status
            # Format 3: ## task-id

            # Table format
            for match in re.finditer(r'\|\s*([0-9a-f-]+)\s*\|\s*(\w+)\s*\|', content):
                task_id = match.group(1)
                status = match.group(2).lower()
                tasks[task_id] = TaskInfo(task_id=task_id, status=status)

            # List format
            for match in re.finditer(r'-\s+([0-9a-f-]+):\s*(\w+)', content):
                task_id = match.group(1)
                status = match.group(2).lower()
                tasks[task_id] = TaskInfo(task_id=task_id, status=status)

            self.result.sources_used.append("LogBook INDEX.md")

        except Exception as e:
            self.log(f"Error parsing INDEX.md: {e}")

        return tasks

    def correlate_branches_and_tasks(self, branches: List[str],
                                       tasks: Dict[str, TaskInfo]) -> Dict[str, TaskInfo]:
        """Correlate git branches with task entries"""
        # Match branches to tasks
        for branch in branches:
            # Extract potential task ID from branch name
            # Patterns: feature/task-xxx, alt/xxx, task-xxx
            match = re.search(r'(task[-_])?([0-9a-f-]+)', branch)
            if match:
                task_id = match.group(2)

                if task_id in tasks:
                    tasks[task_id].branch = branch
                    if tasks[task_id].status == "unknown":
                        tasks[task_id].status = "active"
                else:
                    # Branch exists but no LogBook entry
                    self.result.orphaned_branches_detected.append(branch)

        return tasks

    def resolve_conflicts(self, tasks: Dict[str, TaskInfo]) -> Dict[str, TaskInfo]:
        """Resolve conflicts between sources"""
        # Mark tasks with LogBook entries but no git branch as failed
        for task_id, task in tasks.items():
            if task.branch is None and task.status == "active":
                # No branch = task may be failed or completed
                if task.status != "completed":
                    task.status = "failed"
                    self.result.conflicts_resolved += 1

        return tasks

    def generate_state_md(self, tasks: Dict[str, TaskInfo]) -> str:
        """Generate STATE.md content"""
        now = datetime.now()
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

        # Categorize tasks
        active = [b for b in tasks.values() if b.status == "active"]
        completed = [b for b in tasks.values() if b.status == "completed"]
        failed = [b for b in tasks.values() if b.status == "failed"]

        # Calculate metrics
        total = len(tasks)
        success_rate = (len(completed) / total * 100) if total > 0 else 0

        lines = [
            "---",
            f"version: 1.0",
            f"last_updated: {timestamp}",
            f"total_tasks_processed: {total}",
            f"active_tasks: {len(active)}",
            f"tasks_completed: {len(completed)}",
            f"tasks_failed: {len(failed)}",
            f"success_rate: {success_rate:.1f}%",
            "---",
            "",
            "# PM State",
            "",
            f"**Last Updated:** {timestamp}",
            f"**Version:** 1.0",
            "",
            "## Current Task",
            "",
        ]

        if active:
            current = active[0]
            lines.extend([
                f"- **Task ID:** {current.task_id}",
                f"- **Branch:** {current.branch or 'N/A'}",
                f"- **Status:** active",
                ""
            ])
        else:
            lines.extend([
                "No active task.",
                ""
            ])

        lines.extend([
            "## Agent States",
            "",
            "| Agent | Status | Last Active |",
            "|-------|--------|-------------|",
            "| Project-Manager | active | now |",
            "| Builder | idle | - |",
            "| Critic-Orchestrator | idle | - |",
            "",
            "## Active Branches",
            ""
        ])

        if active:
            for task in active:
                lines.append(f"- `{task.branch or task.task_id}`: {task.task_id}")
        else:
            lines.append("No active branches.")
        lines.append("")

        lines.extend([
            "## Completed Tasks",
            ""
        ])

        if completed:
            for task in completed[:10]:  # Show last 10
                lines.append(f"- {task.task_id}")
        else:
            lines.append("No completed tasks.")
        lines.append("")

        lines.extend([
            "## Failed Tasks",
            ""
        ])

        if failed:
            for task in failed[:5]:  # Show last 5
                lines.append(f"- {task.task_id}")
        else:
            lines.append("No failed tasks.")
        lines.append("")

        lines.extend([
            "## Pending Work Orders",
            "",
            "No pending work orders.",
            "",
            "## Recent Decisions",
            "",
            f"- {timestamp}: STATE.md reconstructed from LogBook entries",
            "",
            "---",
            f"*Reconstructed on {timestamp} by tools/reconstruct_pm_state.py*"
        ])

        return '\n'.join(lines)

    def validate_reconstructed_state(self, content: str) -> bool:
        """Validate the reconstructed STATE.md"""
        # Basic validation - check required sections exist
        required = ["## Current Task", "## Agent States", "## Pending Work Orders"]
        for section in required:
            if section not in content:
                self.result.errors.append(f"Missing required section: {section}")
                return False
        return True

    def reconstruct(self) -> ReconstructionResult:
        """Run full reconstruction"""
        print("Reconstructing PM STATE.md from LogBook entries...")
        print()

        # Step 1: Get git branches
        print("Step 1: Scanning git branches...")
        branches = self.get_git_branches()
        self.log(f"Found {len(branches)} branches")

        # Step 2: Scan LogBook tasks
        print("Step 2: Scanning LogBook/progress/tasks/...")
        logbook_tasks = self.scan_logbook_tasks()
        self.log(f"Found {len(logbook_tasks)} task directories")

        # Step 3: Parse INDEX.md
        print("Step 3: Parsing LogBook/pm/INDEX.md...")
        index_tasks = self.parse_index_md()
        self.log(f"Found {len(index_tasks)} entries in INDEX.md")

        # Step 4: Merge task sources
        print("Step 4: Merging task sources...")
        self.tasks = {**logbook_tasks}
        for task_id, task in index_tasks.items():
            if task_id in self.tasks:
                # Merge info
                if task.status != "unknown":
                    self.tasks[task_id].status = task.status
            else:
                self.tasks[task_id] = task

        # Step 5: Correlate with git branches
        print("Step 5: Correlating with git branches...")
        self.tasks = self.correlate_branches_and_tasks(branches, self.tasks)

        # Step 6: Resolve conflicts
        print("Step 6: Resolving conflicts...")
        self.tasks = self.resolve_conflicts(self.tasks)

        # Update result metrics
        self.result.tasks_reconstructed = len(self.tasks)
        self.result.active_tasks = len([b for b in self.tasks.values() if b.status == "active"])
        self.result.completed_tasks = len([b for b in self.tasks.values() if b.status == "completed"])
        self.result.failed_tasks = len([b for b in self.tasks.values() if b.status == "failed"])

        # Step 7: Generate STATE.md
        print("Step 7: Generating STATE.md...")
        state_content = self.generate_state_md(self.tasks)

        # Step 8: Validate
        print("Step 8: Validating reconstruction...")
        self.result.validation_passed = self.validate_reconstructed_state(state_content)

        if not self.result.validation_passed:
            self.result.reconstruction_successful = False
            return self.result

        # Step 9: Write output
        print("Step 9: Writing output...")
        if self.dry_run:
            print("\n--- Reconstructed STATE.md (dry run) ---")
            print(state_content)
            print("--- End of STATE.md ---\n")
        else:
            # Ensure directory exists
            self.output.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing if present
            if self.output.exists():
                backup_path = self.output.with_suffix('.md.bak')
                self.output.rename(backup_path)
                print(f"  Backed up existing to: {backup_path}")

            self.output.write_text(state_content)
            print(f"  Written to: {self.output}")

        self.result.reconstruction_successful = True
        return self.result

    def print_result(self):
        """Print reconstruction result"""
        print()
        print("=" * 50)
        if self.result.reconstruction_successful:
            print("\033[92m✅ STATE.md reconstruction successful\033[0m")
        else:
            print("\033[91m❌ STATE.md reconstruction failed\033[0m")
        print("=" * 50)

        print(f"\nSources used: {', '.join(self.result.sources_used)}")
        print(f"Tasks reconstructed: {self.result.tasks_reconstructed}")
        print(f"  - Active: {self.result.active_tasks}")
        print(f"  - Completed: {self.result.completed_tasks}")
        print(f"  - Failed: {self.result.failed_tasks}")

        if self.result.orphaned_branches_detected:
            print(f"\nOrphaned branches detected ({len(self.result.orphaned_branches_detected)}):")
            for branch in self.result.orphaned_branches_detected[:5]:
                print(f"  - {branch}")

        if self.result.conflicts_resolved:
            print(f"\nConflicts resolved: {self.result.conflicts_resolved}")

        if self.result.errors:
            print(f"\nErrors:")
            for err in self.result.errors:
                print(f"  - {err}")

def main():
    parser = argparse.ArgumentParser(
        description='Reconstruct PM STATE.md from LogBook entries',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Reconstruct to default location
    %(prog)s

    # Reconstruct to custom path
    %(prog)s --output LogBook/pm/STATE.md.new

    # Dry run (preview only)
    %(prog)s --dry-run

    # JSON output
    %(prog)s --json

Exit Codes:
    0 - Reconstruction successful
    1 - Reconstruction failed
        """
    )

    parser.add_argument('--output', '-o', type=Path,
                        help='Output path for reconstructed STATE.md')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Preview reconstruction without writing')
    parser.add_argument('--json', action='store_true',
                        help='Output result as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd(),
                        help='Repository root directory')

    args = parser.parse_args()

    # Create reconstructor
    reconstructor = PMStateReconstructor(
        repo_root=args.repo_root,
        output=args.output,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Run reconstruction
    result = reconstructor.reconstruct()

    # Output
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        reconstructor.print_result()

    sys.exit(0 if result.reconstruction_successful else 1)

if __name__ == '__main__':
    main()
