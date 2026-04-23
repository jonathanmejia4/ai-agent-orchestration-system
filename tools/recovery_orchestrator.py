#!/usr/bin/env python3
"""
recovery_orchestrator.py - the system Recovery Orchestration System

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Resilience Tool

Purpose:
    Orchestrates recovery procedures for the system failures.
    Manages checkpoints, rollbacks, and state restoration.
    Provides automated and manual recovery workflows.

Usage:
    python3 recovery_orchestrator.py checkpoint create --name pre-deployment
    python3 recovery_orchestrator.py checkpoint list
    python3 recovery_orchestrator.py rollback --to CHECKPOINT-001
    python3 recovery_orchestrator.py recover --agent builder-001 --from-checkpoint CHECKPOINT-001
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

class RecoveryStrategy(Enum):
    """Recovery strategy types."""
    ROLLBACK = "rollback"           # Revert to checkpoint
    RESTART = "restart"             # Restart agent/service
    RESTORE = "restore"             # Restore from backup
    FAILOVER = "failover"           # Switch to backup system
    RETRY = "retry"                 # Retry failed operation
    SKIP = "skip"                   # Skip and continue
    MANUAL = "manual"               # Require manual intervention

class CheckpointType(Enum):
    """Checkpoint types."""
    FULL = "full"                   # Complete system state
    INCREMENTAL = "incremental"     # Changes since last checkpoint
    AGENT = "agent"                 # Single agent state
    TASK = "task"                 # Single task state

@dataclass
class Checkpoint:
    """Represents a recovery checkpoint."""
    checkpoint_id: str
    name: str
    checkpoint_type: CheckpointType
    created_at: datetime
    created_by: str
    description: str
    state_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    size_bytes: int = 0
    valid: bool = True
    expires_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "name": self.name,
            "type": self.checkpoint_type.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "description": self.description,
            "state_path": self.state_path,
            "metadata": self.metadata,
            "size_bytes": self.size_bytes,
            "valid": self.valid,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            name=data["name"],
            checkpoint_type=CheckpointType(data["type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            description=data["description"],
            state_path=data["state_path"],
            metadata=data.get("metadata", {}),
            size_bytes=data.get("size_bytes", 0),
            valid=data.get("valid", True),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        )

@dataclass
class RecoveryAction:
    """Represents a recovery action."""
    action_id: str
    strategy: RecoveryStrategy
    target: str
    checkpoint_id: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "strategy": self.strategy.value,
            "target": self.target,
            "checkpoint_id": self.checkpoint_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "steps": self.steps
        }

class RecoveryOrchestrator:
    """Orchestrates system recovery procedures."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(".saf/recovery")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir = self.storage_path / "checkpoints"
        self.checkpoints_dir.mkdir(exist_ok=True)
        self.state_file = self.storage_path / "recovery_state.json"
        self.checkpoints: Dict[str, Checkpoint] = {}
        self.actions: List[RecoveryAction] = []
        self._load_state()

    def _load_state(self):
        """Load recovery state from storage."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    for cp_data in data.get("checkpoints", []):
                        cp = Checkpoint.from_dict(cp_data)
                        self.checkpoints[cp.checkpoint_id] = cp
            except Exception:
                pass

    def _save_state(self):
        """Save recovery state to storage."""
        data = {
            "updated_at": datetime.now().isoformat(),
            "checkpoints": [cp.to_dict() for cp in self.checkpoints.values()],
            "recent_actions": [a.to_dict() for a in self.actions[-50:]]
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = len(self.checkpoints) + 1
        return f"CHECKPOINT-{timestamp}-{count:04d}"

    def _generate_action_id(self) -> str:
        """Generate unique action ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = len(self.actions) + 1
        return f"RECOVERY-{timestamp}-{count:04d}"

    def create_checkpoint(
        self,
        name: str,
        checkpoint_type: CheckpointType = CheckpointType.FULL,
        description: str = "",
        targets: Optional[List[str]] = None,
        created_by: str = "system"
    ) -> Checkpoint:
        """Create a new recovery checkpoint."""
        checkpoint_id = self._generate_checkpoint_id()
        state_dir = self.checkpoints_dir / checkpoint_id
        state_dir.mkdir(parents=True)

        metadata = {
            "targets": targets or ["all"],
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform,
                "cwd": os.getcwd()
            }
        }

        # Capture state based on type
        if checkpoint_type == CheckpointType.FULL:
            self._capture_full_state(state_dir, targets)
        elif checkpoint_type == CheckpointType.AGENT:
            self._capture_agent_state(state_dir, targets)
        elif checkpoint_type == CheckpointType.TASK:
            self._capture_task_state(state_dir, targets)

        # Calculate size
        size = sum(f.stat().st_size for f in state_dir.rglob('*') if f.is_file())

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            name=name,
            checkpoint_type=checkpoint_type,
            created_at=datetime.now(),
            created_by=created_by,
            description=description,
            state_path=str(state_dir),
            metadata=metadata,
            size_bytes=size
        )

        self.checkpoints[checkpoint_id] = checkpoint
        self._save_state()

        return checkpoint

    def _capture_full_state(self, state_dir: Path, targets: Optional[List[str]]):
        """Capture full system state."""
        # Capture key directories
        dirs_to_capture = [
            "tasks",
            "PLANNING",
            "LogBook/pm",
            ".saf"
        ]

        for dir_name in dirs_to_capture:
            src = Path(dir_name)
            if src.exists():
                dst = state_dir / dir_name
                if src.is_dir():
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('*.pyc', '__pycache__', '.git'))
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

        # Capture git state if available
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                (state_dir / "git_head").write_text(result.stdout.strip())

            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                (state_dir / "git_status").write_text(result.stdout)
        except Exception:
            pass

    def _capture_agent_state(self, state_dir: Path, targets: Optional[List[str]]):
        """Capture agent-specific state."""
        agent_state_dir = Path(".saf/agent_state")
        if agent_state_dir.exists():
            for agent_file in agent_state_dir.glob("*.json"):
                if targets is None or any(t in agent_file.name for t in targets):
                    shutil.copy2(agent_file, state_dir / agent_file.name)

    def _capture_task_state(self, state_dir: Path, targets: Optional[List[str]]):
        """Capture task-specific state."""
        tasks_dir = Path("tasks")
        if tasks_dir.exists():
            for task_dir in tasks_dir.iterdir():
                if task_dir.is_dir():
                    if targets is None or task_dir.name in targets:
                        dst = state_dir / task_dir.name
                        shutil.copytree(
                            task_dir,
                            dst,
                            ignore=shutil.ignore_patterns('*.pyc', '__pycache__')
                        )

    def list_checkpoints(
        self,
        checkpoint_type: Optional[CheckpointType] = None,
        limit: int = 20
    ) -> List[Checkpoint]:
        """List available checkpoints."""
        checkpoints = list(self.checkpoints.values())

        if checkpoint_type:
            checkpoints = [cp for cp in checkpoints if cp.checkpoint_type == checkpoint_type]

        # Sort by creation time, newest first
        checkpoints.sort(key=lambda cp: cp.created_at, reverse=True)

        return checkpoints[:limit]

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get a specific checkpoint."""
        return self.checkpoints.get(checkpoint_id)

    def delete_checkpoint(self, checkpoint_id: str, force: bool = False) -> bool:
        """Delete a checkpoint.

        Per CLAUDE.md Section 1.1: Destructive operations require human approval.
        Use --force flag for explicit approval bypass.

        Args:
            checkpoint_id: ID of checkpoint to delete
            force: If True, skip confirmation prompt (explicit approval)

        Returns:
            True if deleted, False if not found or cancelled
        """
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            return False

        # Human approval gate per CLAUDE.md Section 1.1
        if not force:
            state_dir = Path(checkpoint.state_path)
            print(f"\n⚠️  DESTRUCTIVE OPERATION: Delete checkpoint {checkpoint_id}")
            print(f"   Path: {state_dir}")
            print(f"   Name: {checkpoint.name}")
            print(f"   Size: {checkpoint.size_bytes / 1024:.2f} KB")
            confirm = input("\nType 'yes' to confirm deletion: ")
            if confirm.lower() != 'yes':
                print("Deletion cancelled.")
                return False

        # Remove files
        state_dir = Path(checkpoint.state_path)
        if state_dir.exists():
            shutil.rmtree(state_dir)

        del self.checkpoints[checkpoint_id]
        self._save_state()

        return True

    def rollback(
        self,
        checkpoint_id: str,
        targets: Optional[List[str]] = None,
        dry_run: bool = False,
        force: bool = False
    ) -> RecoveryAction:
        """Rollback to a checkpoint.

        Per CLAUDE.md Section 1.1: Destructive operations require human approval.
        The rollback operation deletes existing directories before restoring.

        Args:
            checkpoint_id: ID of checkpoint to rollback to
            targets: Specific targets to rollback (optional)
            dry_run: If True, only simulate rollback
            force: If True, skip confirmation prompt (explicit approval)

        Returns:
            RecoveryAction with rollback results
        """
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        action = RecoveryAction(
            action_id=self._generate_action_id(),
            strategy=RecoveryStrategy.ROLLBACK,
            target=",".join(targets) if targets else "all",
            checkpoint_id=checkpoint_id,
            started_at=datetime.now(),
            status="running"
        )
        self.actions.append(action)

        try:
            state_dir = Path(checkpoint.state_path)

            if dry_run:
                action.steps.append({
                    "step": "dry_run",
                    "message": f"Would restore from {state_dir}"
                })
                action.status = "completed"
                action.result = "dry_run"
            else:
                # Human approval gate per CLAUDE.md Section 1.1
                # Rollback deletes existing directories - destructive operation
                if not force:
                    dirs_to_delete = []
                    for item in state_dir.iterdir():
                        if item.is_dir():
                            target_path = Path(item.name)
                            if targets and item.name not in targets:
                                continue
                            if target_path.exists():
                                dirs_to_delete.append(str(target_path))

                    if dirs_to_delete:
                        print(f"\n⚠️  DESTRUCTIVE OPERATION: Rollback to {checkpoint_id}")
                        print(f"   The following directories will be DELETED and replaced:")
                        for d in dirs_to_delete:
                            print(f"     - {d}")
                        confirm = input("\nType 'yes' to confirm rollback: ")
                        if confirm.lower() != 'yes':
                            action.status = "cancelled"
                            action.result = "user_cancelled"
                            action.completed_at = datetime.now()
                            self._save_state()
                            return action

                # Perform rollback
                for item in state_dir.iterdir():
                    if item.is_dir():
                        target_path = Path(item.name)
                        if targets and item.name not in targets:
                            continue

                        action.steps.append({
                            "step": "restore",
                            "source": str(item),
                            "target": str(target_path)
                        })

                        if target_path.exists():
                            shutil.rmtree(target_path)
                        shutil.copytree(item, target_path)

                action.status = "completed"
                action.result = "success"

        except Exception as e:
            action.status = "failed"
            action.error = str(e)

        action.completed_at = datetime.now()
        self._save_state()

        return action

    def recover_agent(
        self,
        agent_id: str,
        checkpoint_id: Optional[str] = None,
        strategy: RecoveryStrategy = RecoveryStrategy.RESTART
    ) -> RecoveryAction:
        """Recover a specific agent."""
        action = RecoveryAction(
            action_id=self._generate_action_id(),
            strategy=strategy,
            target=agent_id,
            checkpoint_id=checkpoint_id,
            started_at=datetime.now(),
            status="running"
        )
        self.actions.append(action)

        try:
            if strategy == RecoveryStrategy.RESTART:
                action.steps.append({
                    "step": "restart",
                    "agent": agent_id,
                    "message": "Restarting agent"
                })

                # Clear agent state file to force fresh start
                agent_state_file = Path(f".saf/agent_state/{agent_id}.json")
                if agent_state_file.exists():
                    try:
                        # Backup current state before clearing
                        backup_file = agent_state_file.with_suffix('.json.bak')
                        shutil.copy2(agent_state_file, backup_file)
                        action.steps.append({
                            "step": "backup_state",
                            "agent": agent_id,
                            "backup": str(backup_file)
                        })

                        # Reset agent state to trigger restart behavior
                        with open(agent_state_file, 'r') as f:
                            state = json.load(f)
                        state['status'] = 'pending_restart'
                        state['restart_requested_at'] = datetime.now().isoformat()
                        with open(agent_state_file, 'w') as f:
                            json.dump(state, f, indent=2)

                        action.steps.append({
                            "step": "state_reset",
                            "agent": agent_id,
                            "message": "Agent state reset for restart"
                        })
                        action.result = "restart_completed"

                    except Exception as e:
                        action.steps.append({
                            "step": "restart_error",
                            "agent": agent_id,
                            "error": str(e)
                        })
                        action.result = "restart_failed"
                else:
                    # No state file - create initial restart state
                    agent_state_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(agent_state_file, 'w') as f:
                        json.dump({
                            'agent_id': agent_id,
                            'status': 'pending_restart',
                            'restart_requested_at': datetime.now().isoformat()
                        }, f, indent=2)
                    action.result = "restart_initiated"

            elif strategy == RecoveryStrategy.RESTORE and checkpoint_id:
                checkpoint = self.checkpoints.get(checkpoint_id)
                if not checkpoint:
                    raise ValueError(f"Checkpoint not found: {checkpoint_id}")

                state_dir = Path(checkpoint.state_path)
                agent_state_file = state_dir / f"{agent_id}.json"

                if agent_state_file.exists():
                    target = Path(f".saf/agent_state/{agent_id}.json")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(agent_state_file, target)
                    action.result = "state_restored"
                else:
                    action.result = "no_state_found"

            action.status = "completed"

        except Exception as e:
            action.status = "failed"
            action.error = str(e)

        action.completed_at = datetime.now()
        self._save_state()

        return action

    def get_recovery_status(self) -> Dict[str, Any]:
        """Get overall recovery system status."""
        recent_actions = self.actions[-10:]

        return {
            "checkpoints_available": len(self.checkpoints),
            "total_checkpoint_size_mb": sum(
                cp.size_bytes for cp in self.checkpoints.values()
            ) / (1024 * 1024),
            "recent_actions": len(recent_actions),
            "last_checkpoint": max(
                (cp.created_at for cp in self.checkpoints.values()),
                default=None
            ),
            "system_healthy": all(
                a.status == "completed" for a in recent_actions
            ) if recent_actions else True
        }

def main():
    parser = argparse.ArgumentParser(description="the system Recovery Orchestration System")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Checkpoint commands
    checkpoint_parser = subparsers.add_parser("checkpoint", help="Checkpoint management")
    checkpoint_subparsers = checkpoint_parser.add_subparsers(dest="checkpoint_action")

    # checkpoint create
    create_parser = checkpoint_subparsers.add_parser("create", help="Create checkpoint")
    create_parser.add_argument("--name", "-n", required=True, help="Checkpoint name")
    create_parser.add_argument("--type", "-t", choices=["full", "incremental", "agent", "task"],
                               default="full")
    create_parser.add_argument("--description", "-d", default="")
    create_parser.add_argument("--targets", nargs="*", help="Specific targets to capture")

    # checkpoint list
    list_parser = checkpoint_subparsers.add_parser("list", help="List checkpoints")
    list_parser.add_argument("--type", "-t", choices=["full", "incremental", "agent", "task"])
    list_parser.add_argument("--limit", type=int, default=20)

    # checkpoint delete
    delete_parser = checkpoint_subparsers.add_parser("delete", help="Delete checkpoint")
    delete_parser.add_argument("--id", required=True, help="Checkpoint ID")
    delete_parser.add_argument("--force", "-f", action="store_true",
                               help="Skip confirmation prompt (explicit approval)")

    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to checkpoint")
    rollback_parser.add_argument("--to", required=True, help="Checkpoint ID")
    rollback_parser.add_argument("--targets", nargs="*", help="Specific targets to rollback")
    rollback_parser.add_argument("--dry-run", action="store_true")
    rollback_parser.add_argument("--force", "-f", action="store_true",
                                 help="Skip confirmation prompt (explicit approval)")

    # Recover command
    recover_parser = subparsers.add_parser("recover", help="Recover agent")
    recover_parser.add_argument("--agent", "-a", required=True, help="Agent ID")
    recover_parser.add_argument("--from-checkpoint", help="Checkpoint ID")
    recover_parser.add_argument("--strategy", "-s",
                                choices=["rollback", "restart", "restore"],
                                default="restart")

    # Status command
    subparsers.add_parser("status", help="Show recovery status")

    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--storage", help="Recovery storage directory")

    args = parser.parse_args()

    storage_path = Path(args.storage) if args.storage else None
    orchestrator = RecoveryOrchestrator(storage_path=storage_path)

    if args.command == "checkpoint":
        if args.checkpoint_action == "create":
            checkpoint = orchestrator.create_checkpoint(
                name=args.name,
                checkpoint_type=CheckpointType(args.type),
                description=args.description,
                targets=args.targets
            )
            if args.format == "json":
                print(json.dumps(checkpoint.to_dict(), indent=2))
            else:
                print(f"✅ Checkpoint created: {checkpoint.checkpoint_id}")
                print(f"   Name: {checkpoint.name}")
                print(f"   Type: {checkpoint.checkpoint_type.value}")
                print(f"   Size: {checkpoint.size_bytes / 1024:.2f} KB")
                print(f"   Path: {checkpoint.state_path}")

        elif args.checkpoint_action == "list":
            checkpoint_type = CheckpointType(args.type) if args.type else None
            checkpoints = orchestrator.list_checkpoints(
                checkpoint_type=checkpoint_type,
                limit=args.limit
            )
            if args.format == "json":
                print(json.dumps([cp.to_dict() for cp in checkpoints], indent=2))
            else:
                print(f"Checkpoints ({len(checkpoints)}):")
                print("-" * 80)
                for cp in checkpoints:
                    print(f"  {cp.checkpoint_id}")
                    print(f"    Name: {cp.name}")
                    print(f"    Type: {cp.checkpoint_type.value}")
                    print(f"    Created: {cp.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"    Size: {cp.size_bytes / 1024:.2f} KB")
                    print()

        elif args.checkpoint_action == "delete":
            if orchestrator.delete_checkpoint(args.id, force=args.force):
                print(f"✅ Checkpoint {args.id} deleted")
            else:
                print(f"❌ Checkpoint {args.id} not found or deletion cancelled", file=sys.stderr)
                return 1

    elif args.command == "rollback":
        try:
            action = orchestrator.rollback(
                checkpoint_id=args.to,
                targets=args.targets,
                dry_run=args.dry_run,
                force=args.force
            )
            if args.format == "json":
                print(json.dumps(action.to_dict(), indent=2))
            else:
                if action.status == "completed":
                    print(f"✅ Rollback {'simulated' if args.dry_run else 'completed'}: {action.action_id}")
                    for step in action.steps:
                        print(f"   - {step.get('step')}: {step.get('message', step.get('target', ''))}")
                else:
                    print(f"❌ Rollback failed: {action.error}")
                    return 1
        except ValueError as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "recover":
        strategy = RecoveryStrategy(args.strategy)
        action = orchestrator.recover_agent(
            agent_id=args.agent,
            checkpoint_id=args.from_checkpoint,
            strategy=strategy
        )
        if args.format == "json":
            print(json.dumps(action.to_dict(), indent=2))
        else:
            if action.status == "completed":
                print(f"✅ Recovery completed: {action.action_id}")
                print(f"   Agent: {args.agent}")
                print(f"   Strategy: {strategy.value}")
                print(f"   Result: {action.result}")
            else:
                print(f"❌ Recovery failed: {action.error}")
                return 1

    elif args.command == "status":
        status = orchestrator.get_recovery_status()
        if args.format == "json":
            print(json.dumps(status, indent=2, default=str))
        else:
            print("Recovery System Status")
            print("=" * 40)
            print(f"Checkpoints available: {status['checkpoints_available']}")
            print(f"Total checkpoint size: {status['total_checkpoint_size_mb']:.2f} MB")
            print(f"Recent actions: {status['recent_actions']}")
            if status['last_checkpoint']:
                print(f"Last checkpoint: {status['last_checkpoint']}")
            print(f"System healthy: {'✅ Yes' if status['system_healthy'] else '❌ No'}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
