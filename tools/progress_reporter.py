#!/usr/bin/env python3
"""
Progress Reporter
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Reporting

Reports progress on the system tasks, tasks, and action plans.
Generates progress dashboards and status updates.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass
class TaskProgress:
    """Progress of a single task."""
    task_id: str
    title: str
    status: str  # "pending", "in_progress", "completed", "blocked"
    progress_percent: float
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    notes: List[str] = field(default_factory=list)

@dataclass
class TaskProgress:
    """Progress of a task."""
    task_id: str
    name: str
    status: str
    phase: str  # "planning", "building", "testing", "review", "completed"
    steps_completed: int
    steps_total: int
    blockers: List[str] = field(default_factory=list)

@dataclass
class ProgressReport:
    """A progress report."""
    report_date: str
    overall_progress: float
    tasks: List[TaskProgress] = field(default_factory=list)
    tasks: List[TaskProgress] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)

class ProgressReporter:
    """Reports progress on the system activities."""

    def __init__(self, base_path: str = "."):
        """
        Initialize reporter.

        Args:
            base_path: Base path for the system files
        """
        self.base_path = Path(base_path)

    def _scan_action_plans(self) -> List[TaskProgress]:
        """Scan action plans for task progress."""
        tasks = []
        plans_dir = self.base_path / "PLANNING" / "action_plans"

        if not plans_dir.exists():
            return tasks

        for plan_file in plans_dir.glob("*.yaml"):
            try:
                import yaml
                with open(plan_file, 'r') as f:
                    plan = yaml.safe_load(f)

                if not plan:
                    continue

                plan_id = plan.get('plan_id', plan_file.stem)
                steps = plan.get('steps', [])

                for step in steps:
                    step_id = step.get('id', '')
                    status = step.get('status', 'pending')

                    tasks.append(TaskProgress(
                        task_id=f"{plan_id}/{step_id}",
                        title=step.get('description', step_id),
                        status=status,
                        progress_percent=100.0 if status == 'completed' else 0.0,
                        assignee=step.get('assignee'),
                        notes=step.get('notes', [])
                    ))

            except Exception:
                continue

        return tasks

    def _scan_tasks(self) -> List[TaskProgress]:
        """Scan task directory for progress."""
        tasks = []
        task_dir = self.base_path / ".task"

        if not task_dir.exists():
            return tasks

        # Check for task.yaml
        task_file = task_dir / "task.yaml"
        if task_file.exists():
            try:
                import yaml
                with open(task_file, 'r') as f:
                    task = yaml.safe_load(f)

                if task:
                    status = task.get('status', 'pending')
                    phase = self._determine_phase(task_dir)

                    tasks.append(TaskProgress(
                        task_id=task.get('id', 'unknown'),
                        name=task.get('name', task.get('id', 'Unknown Task')),
                        status=status,
                        phase=phase,
                        steps_completed=self._count_completed_steps(task),
                        steps_total=self._count_total_steps(task),
                        blockers=task.get('blockers', [])
                    ))

            except Exception:
                pass

        return tasks

    def _determine_phase(self, task_dir: Path) -> str:
        """Determine task phase from files present."""
        if (task_dir / "verdict.yaml").exists():
            return "review"
        if (task_dir / "checkpoint_evaluation.yaml").exists():
            return "testing"
        if (task_dir / "wiring.yaml").exists():
            return "building"
        if (task_dir / "task.yaml").exists():
            return "planning"
        return "pending"

    def _count_completed_steps(self, task: Dict[str, Any]) -> int:
        """Count completed steps in a task."""
        steps = task.get('steps', task.get('tasks', []))
        return sum(1 for s in steps if s.get('status') == 'completed')

    def _count_total_steps(self, task: Dict[str, Any]) -> int:
        """Count total steps in a task."""
        return len(task.get('steps', task.get('tasks', [])))

    def _scan_issues(self) -> Dict[str, int]:
        """Scan issue catalog for counts."""
        catalog_path = self.base_path / "ISSUE_CATALOG.md"
        counts = {"resolved": 0, "unresolved": 0, "total": 0}

        if not catalog_path.exists():
            return counts

        try:
            with open(catalog_path, 'r') as f:
                content = f.read()

            import re
            resolved = len(re.findall(r'✅ RESOLVED', content))
            unresolved = len(re.findall(r'❌ NOT RESOLVED', content))

            counts["resolved"] = resolved
            counts["unresolved"] = unresolved
            counts["total"] = resolved + unresolved

        except Exception:
            pass

        return counts

    def generate_report(self) -> ProgressReport:
        """Generate a progress report."""
        tasks = self._scan_action_plans()
        tasks = self._scan_tasks()
        issue_counts = self._scan_issues()

        # Calculate overall progress
        total_items = len(tasks) + len(tasks)
        completed_items = (
            sum(1 for t in tasks if t.status == 'completed') +
            sum(1 for b in tasks if b.status == 'completed')
        )

        overall_progress = (
            (completed_items / total_items * 100) if total_items > 0 else 0
        )

        # Collect blockers
        blockers = []
        for task in tasks:
            if task.status == 'blocked':
                blockers.append(f"Task {task.task_id}: {task.title}")
        for task in tasks:
            blockers.extend(task.blockers)

        # Summary
        summary = {
            "tasks_total": len(tasks),
            "tasks_completed": sum(1 for t in tasks if t.status == 'completed'),
            "tasks_in_progress": sum(1 for t in tasks if t.status == 'in_progress'),
            "tasks_blocked": sum(1 for t in tasks if t.status == 'blocked'),
            "tasks_total": len(tasks),
            "tasks_completed": sum(1 for b in tasks if b.status == 'completed'),
            "issues_resolved": issue_counts["resolved"],
            "issues_unresolved": issue_counts["unresolved"],
        }

        return ProgressReport(
            report_date=datetime.now().isoformat(),
            overall_progress=overall_progress,
            tasks=tasks,
            summary=summary,
            blockers=blockers
        )

    def format_console(self, report: ProgressReport) -> str:
        """Format report for console output."""
        lines = [
            "=" * 60,
            f"the system Progress Report - {report.report_date[:10]}",
            "=" * 60,
            "",
            f"Overall Progress: {report.overall_progress:.1f}%",
            "",
            "Summary:",
            f"  Tasks: {report.summary.get('tasks_completed', 0)}/{report.summary.get('tasks_total', 0)} completed",
            f"  Tasks: {report.summary.get('tasks_completed', 0)}/{report.summary.get('tasks_total', 0)} completed",
            f"  Issues: {report.summary.get('issues_resolved', 0)} resolved, {report.summary.get('issues_unresolved', 0)} open",
            ""
        ]

        if report.blockers:
            lines.append("Blockers:")
            for blocker in report.blockers[:5]:
                lines.append(f"  ⚠️  {blocker}")
            lines.append("")

        if report.tasks:
            lines.append("Active Tasks:")
            for task in report.tasks:
                progress = (
                    task.steps_completed / task.steps_total * 100
                    if task.steps_total > 0 else 0
                )
                lines.append(f"  [{task.phase}] {task.name}: {progress:.0f}%")
            lines.append("")

        return '\n'.join(lines)

    def format_markdown(self, report: ProgressReport) -> str:
        """Format report as markdown."""
        lines = [
            f"# the system Progress Report",
            f"**Date:** {report.report_date[:10]}",
            "",
            f"## Overall Progress: {report.overall_progress:.1f}%",
            "",
            "```",
            self._generate_progress_bar(report.overall_progress),
            "```",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Tasks Completed | {report.summary.get('tasks_completed', 0)}/{report.summary.get('tasks_total', 0)} |",
            f"| Tasks Completed | {report.summary.get('tasks_completed', 0)}/{report.summary.get('tasks_total', 0)} |",
            f"| Issues Resolved | {report.summary.get('issues_resolved', 0)} |",
            f"| Issues Open | {report.summary.get('issues_unresolved', 0)} |",
            ""
        ]

        if report.blockers:
            lines.append("## Blockers")
            lines.append("")
            for blocker in report.blockers:
                lines.append(f"- ⚠️ {blocker}")
            lines.append("")

        if report.tasks:
            lines.append("## Tasks")
            lines.append("")
            lines.append("| Task | Phase | Progress |")
            lines.append("|-------|-------|----------|")
            for task in report.tasks:
                progress = (
                    task.steps_completed / task.steps_total * 100
                    if task.steps_total > 0 else 0
                )
                lines.append(f"| {task.name} | {task.phase} | {progress:.0f}% |")
            lines.append("")

        return '\n'.join(lines)

    def _generate_progress_bar(self, percent: float, width: int = 40) -> str:
        """Generate a text progress bar."""
        filled = int(width * percent / 100)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return f"[{bar}] {percent:.1f}%"

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate the system progress report"
    )
    parser.add_argument("-p", "--path", default=".",
                        help="the system project path")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("--format", choices=["console", "markdown", "json"],
                        default="console", help="Output format")

    args = parser.parse_args()

    reporter = ProgressReporter(base_path=args.path)
    report = reporter.generate_report()

    if args.format == "json":
        output = json.dumps({
            "report_date": report.report_date,
            "overall_progress": report.overall_progress,
            "summary": report.summary,
            "blockers": report.blockers,
            "tasks": [
                {
                    "id": b.task_id,
                    "name": b.name,
                    "phase": b.phase,
                    "steps_completed": b.steps_completed,
                    "steps_total": b.steps_total
                }
                for b in report.tasks
            ]
        }, indent=2)
    elif args.format == "markdown":
        output = reporter.format_markdown(report)
    else:
        output = reporter.format_console(report)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report written to: {args.output}")
    else:
        print(output)

if __name__ == "__main__":
    main()
