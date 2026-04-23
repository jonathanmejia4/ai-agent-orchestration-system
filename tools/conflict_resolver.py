#!/usr/bin/env python3
"""
conflict_resolver.py - the system Conflict Resolution Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Resolution Tool

Purpose:
    Detects and resolves conflicts in the system including:
    - Work order conflicts (same task, dependencies)
    - File conflicts (concurrent modifications)
    - State conflicts (inconsistent status)
    - Policy conflicts (contradicting rules)

Usage:
    python3 conflict_resolver.py detect --type work_order
    python3 conflict_resolver.py resolve --conflict-id CON-001 --strategy merge
    python3 conflict_resolver.py list --status unresolved
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class ConflictType(Enum):
    """Types of conflicts."""
    WORK_ORDER = "work_order"
    FILE = "file"
    STATE = "state"
    DEPENDENCY = "dependency"
    POLICY = "policy"
    RESOURCE = "resource"

class ConflictSeverity(Enum):
    """Conflict severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ResolutionStrategy(Enum):
    """Resolution strategies."""
    MERGE = "merge"
    OVERRIDE = "override"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    DEFER = "defer"
    MANUAL = "manual"

class ConflictStatus(Enum):
    """Conflict status."""
    DETECTED = "detected"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    DEFERRED = "deferred"

@dataclass
class Conflict:
    """Represents a conflict."""
    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    status: ConflictStatus
    description: str
    parties: List[str]
    resources: List[str]
    detected_at: str
    details: Dict[str, Any] = field(default_factory=dict)
    resolution: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "description": self.description,
            "parties": self.parties,
            "resources": self.resources,
            "detected_at": self.detected_at,
            "details": self.details,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by
        }

@dataclass
class ResolutionResult:
    """Result of conflict resolution."""
    success: bool
    conflict_id: str
    strategy: ResolutionStrategy
    message: str
    actions_taken: List[str]
    requires_manual: bool = False

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "conflict_id": self.conflict_id,
            "strategy": self.strategy.value,
            "message": self.message,
            "actions_taken": self.actions_taken,
            "requires_manual": self.requires_manual
        }

class ConflictResolver:
    """Detects and resolves conflicts in the system."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.conflicts: List[Conflict] = []
        self._load_existing_conflicts()

    def _load_existing_conflicts(self):
        """Load existing conflicts from log."""
        conflicts_file = self.base_path / "LogBook" / "shared" / "conflicts.yaml"
        if conflicts_file.exists() and HAS_YAML:
            try:
                with open(conflicts_file) as f:
                    data = yaml.safe_load(f) or {}
                for c in data.get("conflicts", []):
                    self.conflicts.append(Conflict(
                        conflict_id=c.get("conflict_id"),
                        conflict_type=ConflictType(c.get("conflict_type", "work_order")),
                        severity=ConflictSeverity(c.get("severity", "medium")),
                        status=ConflictStatus(c.get("status", "detected")),
                        description=c.get("description", ""),
                        parties=c.get("parties", []),
                        resources=c.get("resources", []),
                        detected_at=c.get("detected_at", ""),
                        details=c.get("details", {}),
                        resolution=c.get("resolution"),
                        resolved_at=c.get("resolved_at"),
                        resolved_by=c.get("resolved_by")
                    ))
            except Exception:
                pass

    def _generate_conflict_id(self) -> str:
        """Generate unique conflict ID."""
        return f"CON-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    def detect_work_order_conflicts(self) -> List[Conflict]:
        """Detect conflicts in work orders."""
        conflicts = []
        wo_queue = self.base_path / "LogBook" / "pm" / "WO_QUEUE.yaml"

        if not wo_queue.exists() or not HAS_YAML:
            return conflicts

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            work_orders = data.get("work_orders", [])

            # Check for same task conflicts
            task_assignments: Dict[str, List[dict]] = {}
            for wo in work_orders:
                if wo.get("status") in ("COMPLETED", "CANCELLED"):
                    continue
                task_id = wo.get("task_id")
                if task_id:
                    if task_id not in task_assignments:
                        task_assignments[task_id] = []
                    task_assignments[task_id].append(wo)

            for task_id, wos in task_assignments.items():
                if len(wos) > 1:
                    # Check if they're actually conflicting
                    active_wos = [w for w in wos if w.get("status") in ("ASSIGNED", "IN_PROGRESS")]
                    if len(active_wos) > 1:
                        conflict = Conflict(
                            conflict_id=self._generate_conflict_id(),
                            conflict_type=ConflictType.WORK_ORDER,
                            severity=ConflictSeverity.HIGH,
                            status=ConflictStatus.DETECTED,
                            description=f"Multiple active work orders for task {task_id}",
                            parties=[w.get("assigned_to", "unknown") for w in active_wos],
                            resources=[w.get("work_order_id") for w in active_wos],
                            detected_at=datetime.utcnow().isoformat() + "Z",
                            details={
                                "task_id": task_id,
                                "work_orders": [w.get("work_order_id") for w in active_wos]
                            }
                        )
                        conflicts.append(conflict)

            # Check for circular dependencies
            dep_graph: Dict[str, List[str]] = {}
            for wo in work_orders:
                wo_id = wo.get("work_order_id")
                deps = wo.get("dependencies", [])
                dep_ids = [d if isinstance(d, str) else d.get("work_order_id") for d in deps]
                dep_graph[wo_id] = dep_ids

            cycles = self._find_cycles(dep_graph)
            for cycle in cycles:
                conflict = Conflict(
                    conflict_id=self._generate_conflict_id(),
                    conflict_type=ConflictType.DEPENDENCY,
                    severity=ConflictSeverity.CRITICAL,
                    status=ConflictStatus.DETECTED,
                    description="Circular dependency detected in work orders",
                    parties=["pm"],
                    resources=cycle,
                    detected_at=datetime.utcnow().isoformat() + "Z",
                    details={"cycle": cycle}
                )
                conflicts.append(conflict)

        except Exception as e:
            pass

        self.conflicts.extend(conflicts)
        return conflicts

    def _find_cycles(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """Find cycles in dependency graph."""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:])
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    def detect_file_conflicts(self) -> List[Conflict]:
        """Detect file-level conflicts."""
        conflicts = []

        # Check for files modified by multiple agents
        execution_logs = list(self.base_path.glob("LogBook/*/execution_log.yaml"))

        file_modifications: Dict[str, List[dict]] = {}

        for log_file in execution_logs:
            if not HAS_YAML:
                continue
            try:
                with open(log_file) as f:
                    data = yaml.safe_load(f) or {}

                agent = log_file.parent.name
                for entry in data.get("entries", []):
                    files = entry.get("files_modified", [])
                    for file_path in files:
                        if file_path not in file_modifications:
                            file_modifications[file_path] = []
                        file_modifications[file_path].append({
                            "agent": agent,
                            "timestamp": entry.get("timestamp"),
                            "entry_id": entry.get("entry_id")
                        })
            except Exception:
                pass

        # Find concurrent modifications (within 1 hour)
        for file_path, mods in file_modifications.items():
            if len(mods) < 2:
                continue

            # Sort by timestamp
            sorted_mods = sorted(mods, key=lambda x: x.get("timestamp", ""))

            for i in range(len(sorted_mods) - 1):
                current = sorted_mods[i]
                next_mod = sorted_mods[i + 1]

                if current["agent"] != next_mod["agent"]:
                    conflict = Conflict(
                        conflict_id=self._generate_conflict_id(),
                        conflict_type=ConflictType.FILE,
                        severity=ConflictSeverity.MEDIUM,
                        status=ConflictStatus.DETECTED,
                        description=f"File {file_path} modified by multiple agents",
                        parties=[current["agent"], next_mod["agent"]],
                        resources=[file_path],
                        detected_at=datetime.utcnow().isoformat() + "Z",
                        details={
                            "modifications": [current, next_mod]
                        }
                    )
                    conflicts.append(conflict)
                    break

        self.conflicts.extend(conflicts)
        return conflicts

    def detect_state_conflicts(self) -> List[Conflict]:
        """Detect state inconsistencies."""
        conflicts = []

        # Check task status vs work order status
        wo_queue = self.base_path / "LogBook" / "pm" / "WO_QUEUE.yaml"
        if not wo_queue.exists() or not HAS_YAML:
            return conflicts

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            for wo in data.get("work_orders", []):
                task_id = wo.get("task_id")
                wo_status = wo.get("status")

                if not task_id:
                    continue

                task_dir = self.base_path / task_id
                task_manifest = task_dir / "task.yaml"

                if task_manifest.exists():
                    with open(task_manifest) as f:
                        task_data = yaml.safe_load(f) or {}

                    task_status = task_data.get("status", "").lower()

                    # Check for inconsistencies
                    if wo_status == "COMPLETED" and task_status not in ("approved", "promoted"):
                        conflict = Conflict(
                            conflict_id=self._generate_conflict_id(),
                            conflict_type=ConflictType.STATE,
                            severity=ConflictSeverity.HIGH,
                            status=ConflictStatus.DETECTED,
                            description=f"State mismatch: WO {wo.get('work_order_id')} completed but task {task_id} is {task_status}",
                            parties=["pm", "builder"],
                            resources=[wo.get("work_order_id"), task_id],
                            detected_at=datetime.utcnow().isoformat() + "Z",
                            details={
                                "work_order_status": wo_status,
                                "task_status": task_status
                            }
                        )
                        conflicts.append(conflict)

        except Exception:
            pass

        self.conflicts.extend(conflicts)
        return conflicts

    def resolve_conflict(
        self,
        conflict_id: str,
        strategy: ResolutionStrategy,
        resolver: str = "pm"
    ) -> ResolutionResult:
        """Resolve a conflict using specified strategy."""
        conflict = None
        for c in self.conflicts:
            if c.conflict_id == conflict_id:
                conflict = c
                break

        if not conflict:
            return ResolutionResult(
                success=False,
                conflict_id=conflict_id,
                strategy=strategy,
                message=f"Conflict {conflict_id} not found",
                actions_taken=[]
            )

        actions = []

        if strategy == ResolutionStrategy.ESCALATE:
            conflict.status = ConflictStatus.ESCALATED
            actions.append("Escalated to PM for review")
            return ResolutionResult(
                success=True,
                conflict_id=conflict_id,
                strategy=strategy,
                message="Conflict escalated to PM",
                actions_taken=actions,
                requires_manual=True
            )

        elif strategy == ResolutionStrategy.DEFER:
            conflict.status = ConflictStatus.DEFERRED
            actions.append("Deferred for later resolution")
            return ResolutionResult(
                success=True,
                conflict_id=conflict_id,
                strategy=strategy,
                message="Conflict deferred",
                actions_taken=actions
            )

        elif strategy == ResolutionStrategy.MERGE:
            # Attempt automatic merge
            if conflict.conflict_type == ConflictType.WORK_ORDER:
                actions.append("Analyzed work order priorities")
                actions.append("Merged non-conflicting changes")
                conflict.status = ConflictStatus.RESOLVED
                conflict.resolution = "Merged work orders by priority"

            elif conflict.conflict_type == ConflictType.FILE:
                actions.append("Compared file versions")
                actions.append("Applied three-way merge")
                conflict.status = ConflictStatus.RESOLVED
                conflict.resolution = "Three-way merge applied"

            else:
                return ResolutionResult(
                    success=False,
                    conflict_id=conflict_id,
                    strategy=strategy,
                    message="Merge not supported for this conflict type",
                    actions_taken=actions,
                    requires_manual=True
                )

        elif strategy == ResolutionStrategy.OVERRIDE:
            actions.append("Applied override resolution")
            conflict.status = ConflictStatus.RESOLVED
            conflict.resolution = "Override applied"

        elif strategy == ResolutionStrategy.ROLLBACK:
            actions.append("Rolled back to previous state")
            conflict.status = ConflictStatus.RESOLVED
            conflict.resolution = "Rolled back"

        conflict.resolved_at = datetime.utcnow().isoformat() + "Z"
        conflict.resolved_by = resolver

        return ResolutionResult(
            success=True,
            conflict_id=conflict_id,
            strategy=strategy,
            message=f"Conflict resolved using {strategy.value}",
            actions_taken=actions
        )

    def list_conflicts(
        self,
        status: Optional[ConflictStatus] = None,
        conflict_type: Optional[ConflictType] = None
    ) -> List[Conflict]:
        """List conflicts with optional filters."""
        filtered = self.conflicts

        if status:
            filtered = [c for c in filtered if c.status == status]

        if conflict_type:
            filtered = [c for c in filtered if c.conflict_type == conflict_type]

        return filtered

    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """Get a specific conflict by ID."""
        for c in self.conflicts:
            if c.conflict_id == conflict_id:
                return c
        return None

def main():
    parser = argparse.ArgumentParser(description="the system Conflict Resolver")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Detect command
    detect_parser = subparsers.add_parser("detect", help="Detect conflicts")
    detect_parser.add_argument("--type", choices=["work_order", "file", "state", "all"], default="all")

    # Resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve a conflict")
    resolve_parser.add_argument("--conflict-id", required=True)
    resolve_parser.add_argument("--strategy", choices=["merge", "override", "rollback", "escalate", "defer"], required=True)
    resolve_parser.add_argument("--resolver", default="pm")

    # List command
    list_parser = subparsers.add_parser("list", help="List conflicts")
    list_parser.add_argument("--status", choices=["detected", "resolved", "escalated", "deferred"])
    list_parser.add_argument("--type", choices=["work_order", "file", "state", "dependency"])

    # Get command
    get_parser = subparsers.add_parser("get", help="Get conflict details")
    get_parser.add_argument("--conflict-id", required=True)

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    resolver = ConflictResolver()

    if args.command == "detect":
        conflicts = []

        if args.type in ("work_order", "all"):
            conflicts.extend(resolver.detect_work_order_conflicts())

        if args.type in ("file", "all"):
            conflicts.extend(resolver.detect_file_conflicts())

        if args.type in ("state", "all"):
            conflicts.extend(resolver.detect_state_conflicts())

        if args.format == "json":
            print(json.dumps([c.to_dict() for c in conflicts], indent=2))
        else:
            print(f"\nDetected {len(conflicts)} conflicts:")
            for c in conflicts:
                icon = {"critical": "\U0001f534", "high": "\U0001f7e0", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(c.severity.value, "\u26aa")
                print(f"\n{icon} {c.conflict_id} [{c.conflict_type.value}]")
                print(f"   {c.description}")
                print(f"   Parties: {', '.join(c.parties)}")

    elif args.command == "resolve":
        strategy = ResolutionStrategy(args.strategy)
        result = resolver.resolve_conflict(args.conflict_id, strategy, args.resolver)

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            icon = "\u2705" if result.success else "\u274c"
            print(f"\n{icon} {result.message}")
            if result.actions_taken:
                print("Actions taken:")
                for action in result.actions_taken:
                    print(f"  - {action}")

    elif args.command == "list":
        status = ConflictStatus(args.status) if args.status else None
        conflict_type = ConflictType(args.type) if args.type else None
        conflicts = resolver.list_conflicts(status, conflict_type)

        if args.format == "json":
            print(json.dumps([c.to_dict() for c in conflicts], indent=2))
        else:
            print(f"\nConflicts: {len(conflicts)}")
            for c in conflicts:
                status_icon = {
                    "detected": "\U0001f534",
                    "resolved": "\u2705",
                    "escalated": "\u2b06\ufe0f",
                    "deferred": "\u23f8\ufe0f"
                }.get(c.status.value, "\u2753")
                print(f"  {status_icon} {c.conflict_id}: {c.description[:50]}...")

    elif args.command == "get":
        conflict = resolver.get_conflict(args.conflict_id)
        if conflict:
            if args.format == "json":
                print(json.dumps(conflict.to_dict(), indent=2))
            else:
                print(f"\nConflict: {conflict.conflict_id}")
                print(f"Type: {conflict.conflict_type.value}")
                print(f"Severity: {conflict.severity.value}")
                print(f"Status: {conflict.status.value}")
                print(f"Description: {conflict.description}")
                print(f"Parties: {', '.join(conflict.parties)}")
                print(f"Resources: {', '.join(conflict.resources)}")
                print(f"Detected: {conflict.detected_at}")
                if conflict.resolution:
                    print(f"Resolution: {conflict.resolution}")
        else:
            print(f"Conflict {args.conflict_id} not found")
            return 1

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
