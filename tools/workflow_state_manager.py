#!/usr/bin/env python3
"""
workflow_state_manager.py - the system Workflow State Manager

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Workflow Management

Purpose:
    Manages workflow state transitions, validates state changes,
    tracks workflow progress, and ensures consistency.

Usage:
    python3 workflow_state_manager.py status WO-2025-001
    python3 workflow_state_manager.py transition WO-2025-001 --to IN_PROGRESS
    python3 workflow_state_manager.py validate
    python3 workflow_state_manager.py history WO-2025-001
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class WorkflowState(Enum):
    """Valid workflow states."""
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

# Valid state transitions
VALID_TRANSITIONS = {
    WorkflowState.PENDING: {WorkflowState.ASSIGNED, WorkflowState.CANCELLED},
    WorkflowState.ASSIGNED: {WorkflowState.IN_PROGRESS, WorkflowState.BLOCKED, WorkflowState.CANCELLED},
    WorkflowState.IN_PROGRESS: {WorkflowState.REVIEW, WorkflowState.BLOCKED, WorkflowState.FAILED},
    WorkflowState.REVIEW: {WorkflowState.COMPLETED, WorkflowState.IN_PROGRESS, WorkflowState.BLOCKED},
    WorkflowState.BLOCKED: {WorkflowState.PENDING, WorkflowState.IN_PROGRESS, WorkflowState.CANCELLED},
    WorkflowState.COMPLETED: set(),  # Terminal state
    WorkflowState.CANCELLED: set(),  # Terminal state
    WorkflowState.FAILED: {WorkflowState.PENDING, WorkflowState.CANCELLED},  # Can retry
}

@dataclass
class StateTransition:
    """Represents a state transition event."""
    transition_id: str
    work_order_id: str
    from_state: str
    to_state: str
    timestamp: str
    agent: str
    reason: str = ""
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "transition_id": self.transition_id,
            "work_order_id": self.work_order_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "reason": self.reason,
            "metadata": self.metadata
        }

@dataclass
class WorkflowInstance:
    """Represents a workflow instance."""
    work_order_id: str
    current_state: str
    created_at: str
    updated_at: str
    assigned_agent: Optional[str]
    history: List[StateTransition] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "work_order_id": self.work_order_id,
            "current_state": self.current_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "assigned_agent": self.assigned_agent,
            "history": [h.to_dict() for h in self.history],
            "metadata": self.metadata
        }

class WorkflowStateManager:
    """Manages workflow states and transitions."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.workflows: Dict[str, WorkflowInstance] = {}
        self._load_workflows()

    def _load_workflows(self):
        """Load workflow states from work order queue."""
        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if not wo_queue.exists() or not HAS_YAML:
            return

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            for wo in data.get("work_orders", []):
                wo_id = wo.get("work_order_id", "unknown")
                history = []

                # Build history from work order events
                for event in wo.get("history", []):
                    transition = StateTransition(
                        transition_id=f"{wo_id}-{len(history)+1}",
                        work_order_id=wo_id,
                        from_state=event.get("from_state", "UNKNOWN"),
                        to_state=event.get("to_state", event.get("new_status", "UNKNOWN")),
                        timestamp=event.get("timestamp", ""),
                        agent=event.get("agent", "system"),
                        reason=event.get("reason", "")
                    )
                    history.append(transition)

                workflow = WorkflowInstance(
                    work_order_id=wo_id,
                    current_state=wo.get("status", "PENDING"),
                    created_at=wo.get("created_at", ""),
                    updated_at=wo.get("updated_at", ""),
                    assigned_agent=wo.get("agent"),
                    history=history,
                    metadata={
                        "priority": wo.get("priority"),
                        "task_id": wo.get("task_id"),
                        "title": wo.get("title")
                    }
                )
                self.workflows[wo_id] = workflow

        except Exception:
            pass

    def get_workflow(self, work_order_id: str) -> Optional[WorkflowInstance]:
        """Get workflow by work order ID."""
        return self.workflows.get(work_order_id)

    def get_all_workflows(self) -> List[WorkflowInstance]:
        """Get all workflows."""
        return list(self.workflows.values())

    def can_transition(self, work_order_id: str, to_state: str) -> Tuple[bool, str]:
        """Check if transition is valid."""
        workflow = self.get_workflow(work_order_id)
        if not workflow:
            return False, f"Workflow not found: {work_order_id}"

        try:
            current = WorkflowState(workflow.current_state)
            target = WorkflowState(to_state)
        except ValueError as e:
            return False, f"Invalid state: {e}"

        valid_targets = VALID_TRANSITIONS.get(current, set())
        if target not in valid_targets:
            return False, f"Cannot transition from {current.value} to {target.value}"

        return True, "Transition allowed"

    def transition(
        self,
        work_order_id: str,
        to_state: str,
        agent: str,
        reason: str = ""
    ) -> Tuple[bool, str]:
        """Perform state transition."""
        can_do, message = self.can_transition(work_order_id, to_state)
        if not can_do:
            return False, message

        workflow = self.workflows[work_order_id]
        from_state = workflow.current_state

        # Create transition record
        transition = StateTransition(
            transition_id=f"{work_order_id}-{len(workflow.history)+1}",
            work_order_id=work_order_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent=agent,
            reason=reason
        )

        # Update workflow
        workflow.current_state = to_state
        workflow.updated_at = transition.timestamp
        workflow.history.append(transition)

        # Persist change
        self._save_transition(workflow, transition)

        return True, f"Transitioned from {from_state} to {to_state}"

    def _save_transition(self, workflow: WorkflowInstance, transition: StateTransition):
        """Save transition to work order queue."""
        if not HAS_YAML:
            return

        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if not wo_queue.exists():
            return

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            for wo in data.get("work_orders", []):
                if wo.get("work_order_id") == workflow.work_order_id:
                    wo["status"] = workflow.current_state
                    wo["updated_at"] = workflow.updated_at

                    if "history" not in wo:
                        wo["history"] = []

                    wo["history"].append({
                        "timestamp": transition.timestamp,
                        "from_state": transition.from_state,
                        "to_state": transition.to_state,
                        "agent": transition.agent,
                        "reason": transition.reason
                    })
                    break

            with open(wo_queue, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception:
            pass

    def validate_all(self) -> Dict:
        """Validate all workflow states."""
        results = {
            "total_workflows": len(self.workflows),
            "valid": 0,
            "invalid": 0,
            "issues": []
        }

        for wo_id, workflow in self.workflows.items():
            issues = self._validate_workflow(workflow)
            if issues:
                results["invalid"] += 1
                results["issues"].extend(issues)
            else:
                results["valid"] += 1

        return results

    def _validate_workflow(self, workflow: WorkflowInstance) -> List[str]:
        """Validate a single workflow."""
        issues = []

        # Check state is valid
        try:
            WorkflowState(workflow.current_state)
        except ValueError:
            issues.append(f"{workflow.work_order_id}: Invalid state '{workflow.current_state}'")

        # Check history consistency
        if workflow.history:
            expected_state = "PENDING"
            for transition in workflow.history:
                if transition.from_state != expected_state:
                    issues.append(
                        f"{workflow.work_order_id}: History gap at {transition.transition_id}"
                    )
                expected_state = transition.to_state

            if expected_state != workflow.current_state:
                issues.append(
                    f"{workflow.work_order_id}: Current state doesn't match history"
                )

        # Check for stuck workflows
        if workflow.current_state == "IN_PROGRESS":
            if workflow.updated_at:
                try:
                    updated = datetime.fromisoformat(workflow.updated_at.replace("Z", "+00:00"))
                    age_hours = (datetime.utcnow().replace(tzinfo=updated.tzinfo) - updated).total_seconds() / 3600
                    if age_hours > 24:
                        issues.append(
                            f"{workflow.work_order_id}: IN_PROGRESS for {age_hours:.0f} hours"
                        )
                except Exception:
                    pass

        return issues

    def get_by_state(self, state: str) -> List[WorkflowInstance]:
        """Get workflows by state."""
        return [w for w in self.workflows.values() if w.current_state == state]

    def get_summary(self) -> Dict:
        """Get workflow summary statistics."""
        by_state = {}
        by_agent = {}

        for workflow in self.workflows.values():
            state = workflow.current_state
            by_state[state] = by_state.get(state, 0) + 1

            agent = workflow.assigned_agent or "unassigned"
            by_agent[agent] = by_agent.get(agent, 0) + 1

        return {
            "total": len(self.workflows),
            "by_state": by_state,
            "by_agent": by_agent,
            "active": sum(1 for w in self.workflows.values()
                         if w.current_state in ("IN_PROGRESS", "REVIEW", "ASSIGNED")),
            "blocked": sum(1 for w in self.workflows.values()
                          if w.current_state == "BLOCKED"),
            "completed": sum(1 for w in self.workflows.values()
                            if w.current_state == "COMPLETED")
        }

def main():
    parser = argparse.ArgumentParser(description="the system Workflow State Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get workflow status")
    status_parser.add_argument("work_order_id", nargs="?", help="Work order ID")

    # Transition command
    trans_parser = subparsers.add_parser("transition", help="Transition workflow state")
    trans_parser.add_argument("work_order_id")
    trans_parser.add_argument("--to", required=True, help="Target state")
    trans_parser.add_argument("--agent", default="system")
    trans_parser.add_argument("--reason", default="")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate all workflows")

    # History command
    history_parser = subparsers.add_parser("history", help="Get workflow history")
    history_parser.add_argument("work_order_id")

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Get workflow summary")

    # List command
    list_parser = subparsers.add_parser("list", help="List workflows")
    list_parser.add_argument("--state", help="Filter by state")

    # Common arguments
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    manager = WorkflowStateManager()

    if args.command == "status":
        if args.work_order_id:
            workflow = manager.get_workflow(args.work_order_id)
            if workflow:
                if args.format == "json":
                    print(json.dumps(workflow.to_dict(), indent=2))
                else:
                    print(f"\nWorkflow: {workflow.work_order_id}")
                    print("=" * 40)
                    print(f"State: {workflow.current_state}")
                    print(f"Agent: {workflow.assigned_agent or 'unassigned'}")
                    print(f"Created: {workflow.created_at}")
                    print(f"Updated: {workflow.updated_at}")
                    if workflow.metadata.get("title"):
                        print(f"Title: {workflow.metadata['title']}")
            else:
                print(f"Workflow not found: {args.work_order_id}")
                return 1
        else:
            summary = manager.get_summary()
            if args.format == "json":
                print(json.dumps(summary, indent=2))
            else:
                print("\nWorkflow Summary")
                print("=" * 40)
                print(f"Total: {summary['total']}")
                print(f"Active: {summary['active']}")
                print(f"Blocked: {summary['blocked']}")
                print(f"Completed: {summary['completed']}")

    elif args.command == "transition":
        success, message = manager.transition(
            args.work_order_id,
            args.to,
            args.agent,
            args.reason
        )
        if success:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")
            return 1

    elif args.command == "validate":
        results = manager.validate_all()

        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            print("\nWorkflow Validation")
            print("=" * 40)
            print(f"Total: {results['total_workflows']}")
            print(f"Valid: {results['valid']}")
            print(f"Invalid: {results['invalid']}")

            if results['issues']:
                print("\nIssues:")
                for issue in results['issues'][:20]:
                    print(f"  - {issue}")

    elif args.command == "history":
        workflow = manager.get_workflow(args.work_order_id)
        if workflow:
            if args.format == "json":
                print(json.dumps([h.to_dict() for h in workflow.history], indent=2))
            else:
                print(f"\nHistory: {args.work_order_id}")
                print("=" * 50)
                for h in workflow.history:
                    print(f"{h.timestamp}: {h.from_state} -> {h.to_state} ({h.agent})")
                    if h.reason:
                        print(f"  Reason: {h.reason}")
        else:
            print(f"Workflow not found: {args.work_order_id}")
            return 1

    elif args.command == "summary":
        summary = manager.get_summary()
        if args.format == "json":
            print(json.dumps(summary, indent=2))
        else:
            print("\nWorkflow Summary")
            print("=" * 40)
            print(f"Total Workflows: {summary['total']}")
            print(f"\nBy State:")
            for state, count in summary['by_state'].items():
                print(f"  {state}: {count}")
            print(f"\nBy Agent:")
            for agent, count in summary['by_agent'].items():
                print(f"  {agent}: {count}")

    elif args.command == "list":
        if args.state:
            workflows = manager.get_by_state(args.state)
        else:
            workflows = manager.get_all_workflows()

        if args.format == "json":
            print(json.dumps([w.to_dict() for w in workflows], indent=2))
        else:
            print(f"\nWorkflows ({len(workflows)})")
            print("=" * 60)
            for w in workflows:
                agent = w.assigned_agent or "unassigned"
                print(f"{w.work_order_id}: {w.current_state} ({agent})")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
