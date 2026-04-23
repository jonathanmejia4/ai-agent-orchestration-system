#!/usr/bin/env python3
"""Stage promotion tool with automatic LogBook entry creation.

This tool promotes tasks through the system stages and AUTOMATICALLY creates
LogBook entries to ensure 100% traceability. Solves K003 (missing audit trail).

Usage:
    python3 tools/stage_promotion.py promote <task_path> --to Stage2
    python3 tools/stage_promotion.py promote components/auth --from Stage1 --to Stage2
    python3 tools/stage_promotion.py verify <task_path>  # Verify current stage

Stage flow:
    Stage0 (scaffold) → Stage1 (generated) → Stage2 (validated) →
    Stage3 (customized) → Stage4-Golden (production)
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import subprocess

try:
    import yaml
except ImportError:
    print("❌ Missing dependency: pyyaml")
    print("Install with: pip install pyyaml")
    sys.exit(2)

VALID_STAGES = ["Stage0", "Stage1", "Stage2", "Stage3", "Stage4-Golden"]
STAGE_ORDER = {s: i for i, s in enumerate(VALID_STAGES)}

def get_current_stage(task_path: Path) -> Optional[str]:
    """Read current stage from .task/stage file."""
    stage_file = task_path / ".task" / "stage"

    if not stage_file.exists():
        return None

    try:
        stage = stage_file.read_text().strip()
        return stage if stage in VALID_STAGES else None
    except Exception as e:
        print(f"❌ Error reading stage file: {e}")
        return None

def set_stage(task_path: Path, stage: str) -> bool:
    """Write new stage to .task/stage file."""
    stage_file = task_path / ".task" / "stage"

    try:
        stage_file.parent.mkdir(parents=True, exist_ok=True)
        stage_file.write_text(f"{stage}\n")
        return True
    except Exception as e:
        print(f"❌ Error writing stage file: {e}")
        return False

def validate_promotion(task_path: Path, from_stage: str, to_stage: str) -> tuple[bool, str]:
    """Validate that promotion is allowed.

    Returns:
        (is_valid, error_message)
    """
    # Check task exists
    if not task_path.exists():
        return False, f"Task not found: {task_path}"

    # Check .task/ metadata exists
    task_meta = task_path / ".task"
    if not task_meta.exists():
        return False, f"Not a valid task (no .task/ directory): {task_path}"

    # Check stage progression (can only go forward one stage at a time)
    from_idx = STAGE_ORDER.get(from_stage)
    to_idx = STAGE_ORDER.get(to_stage)

    if from_idx is None or to_idx is None:
        return False, f"Invalid stage: {from_stage} → {to_stage}"

    if to_idx != from_idx + 1:
        return False, f"Cannot skip stages: {from_stage} → {to_stage} (must promote one stage at a time)"

    # Stage-specific validation
    if to_stage == "Stage1":
        # Stage 0→1: Must have wiring.yaml
        if not (task_meta / "wiring.yaml").exists():
            return False, "Stage0→Stage1 requires .task/wiring.yaml"

    elif to_stage == "Stage2":
        # Stage 1→2: Must pass validation checks
        # (For now, just check wiring exists; expand with actual validators)
        if not (task_meta / "wiring.yaml").exists():
            return False, "Stage1→Stage2 requires .task/wiring.yaml"

    elif to_stage == "Stage3":
        # Stage 2→3: Validation passed, ready for customization
        pass

    elif to_stage == "Stage4-Golden":
        # Stage 3→Golden: Must have PM approval (check for approval marker)
        approval_file = task_meta / "pm_approval"
        if not approval_file.exists():
            return False, "Stage3→Stage4-Golden requires PM approval (.task/pm_approval marker)"

    return True, ""

def create_logbook_entry(
    agent: str,
    action: str,
    task_path: Path,
    from_stage: Optional[str] = None,
    to_stage: Optional[str] = None,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create LogBook entry for action.

    This is the KEY function that solves K003 (missing LogBook entries).
    Every promotion AUTOMATICALLY creates a LogBook entry.
    """
    # Determine LogBook subdirectory by agent
    agent_dir_map = {
        "PM": "pm",
        "Planner": "planner",
        "Builder": "builder",
        "Critic": "critic"
    }

    agent_dir = agent_dir_map.get(agent, "unknown")
    logbook_dir = Path("LogBook") / agent_dir
    logbook_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename: YYYY-MM-DD-HH-MM-SS-action.yaml
    timestamp = datetime.now(timezone.utc)
    filename = timestamp.strftime(f"%Y-%m-%d-%H-%M-%S-{action}.yaml")
    entry_path = logbook_dir / filename

    # Build entry
    entry = {
        "timestamp": timestamp.isoformat(),
        "agent": agent,
        "action": action,
        "context": {
            "task_path": str(task_path)
        }
    }

    # Add optional context
    if from_stage:
        entry["context"]["from_stage"] = from_stage
    if to_stage:
        entry["context"]["to_stage"] = to_stage
    if reason:
        entry["context"]["reason"] = reason

    # Add metadata
    if metadata:
        entry["metadata"] = metadata
    else:
        entry["metadata"] = {}

    # Try to get git commit SHA
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        entry["metadata"]["commit_sha"] = git_sha
    except:
        pass

    # Write entry
    try:
        with open(entry_path, "w") as f:
            yaml.dump(entry, f, default_flow_style=False, sort_keys=False)

        print(f"✅ LogBook entry created: {entry_path}")
        return True

    except Exception as e:
        print(f"❌ Failed to create LogBook entry: {e}")
        return False

def promote_task(
    task_path: Path,
    to_stage: str,
    from_stage: Optional[str] = None,
    reason: Optional[str] = None,
    agent: str = "Builder",
    dry_run: bool = False
) -> bool:
    """Promote task to next stage with automatic LogBook entry.

    Returns:
        True if promotion successful, False otherwise
    """
    # Get current stage
    current_stage = get_current_stage(task_path)

    if current_stage is None:
        print(f"❌ Cannot determine current stage for: {task_path}")
        print("   Expected .task/stage file with valid stage")
        return False

    # If from_stage not specified, use current_stage
    if from_stage is None:
        from_stage = current_stage
    elif from_stage != current_stage:
        print(f"❌ Stage mismatch: task is at {current_stage}, but --from {from_stage} specified")
        return False

    print(f"=== Promoting {task_path} ===")
    print(f"From: {from_stage}")
    print(f"To: {to_stage}")
    if reason:
        print(f"Reason: {reason}")
    print()

    # Validate promotion
    is_valid, error_msg = validate_promotion(task_path, from_stage, to_stage)

    if not is_valid:
        print(f"❌ Promotion validation failed: {error_msg}")
        return False

    print("✅ Promotion validation passed")

    if dry_run:
        print("\n🔍 DRY RUN: No changes made")
        print(f"   Would promote: {task_path}")
        print(f"   Would update .task/stage: {from_stage} → {to_stage}")
        print(f"   Would create LogBook entry in LogBook/{agent.lower()}/")
        return True

    # Perform promotion
    print(f"\nUpdating .task/stage to {to_stage}...")
    if not set_stage(task_path, to_stage):
        print("❌ Failed to update stage file")
        return False

    print("✅ Stage file updated")

    # Verify promotion happened
    new_stage = get_current_stage(task_path)
    if new_stage != to_stage:
        print(f"❌ VERIFICATION FAILED: Stage is {new_stage}, expected {to_stage}")
        print("   This is a critical error - LogBook would be inaccurate!")
        return False

    print(f"✅ Verified: Stage is now {to_stage}")

    # Create LogBook entry (AUTOMATIC - this is the fix for K003!)
    print("\nCreating LogBook entry...")
    logbook_created = create_logbook_entry(
        agent=agent,
        action="stage_promotion",
        task_path=task_path,
        from_stage=from_stage,
        to_stage=to_stage,
        reason=reason or f"Promoted from {from_stage} to {to_stage}"
    )

    if not logbook_created:
        print("⚠️  WARNING: Promotion succeeded but LogBook entry failed!")
        print("   Audit trail is incomplete - manual entry may be required")
        return False

    print("\n✅ Promotion complete with audit trail")
    print(f"   Task: {task_path}")
    print(f"   Stage: {from_stage} → {to_stage}")
    print(f"   LogBook: Created in LogBook/{agent.lower()}/")

    return True

def verify_task(task_path: Path):
    """Verify task stage and metadata."""
    print(f"=== Verifying {task_path} ===\n")

    if not task_path.exists():
        print(f"❌ Task not found: {task_path}")
        sys.exit(1)

    task_meta = task_path / ".task"
    if not task_meta.exists():
        print(f"❌ Not a valid task (no .task/ directory)")
        sys.exit(1)

    # Check current stage
    current_stage = get_current_stage(task_path)
    if current_stage:
        print(f"Current Stage: {current_stage}")
    else:
        print(f"Current Stage: ❌ Unknown (no .task/stage file)")

    # Check metadata files
    wiring_file = task_meta / "wiring.yaml"
    print(f"wiring.yaml: {'✅ Exists' if wiring_file.exists() else '❌ Missing'}")

    manifest_file = task_meta / "manifest.json"
    print(f"manifest.json: {'✅ Exists' if manifest_file.exists() else '❌ Missing'}")

    pm_approval = task_meta / "pm_approval"
    print(f"pm_approval: {'✅ Exists' if pm_approval.exists() else '❌ Not approved'}")

def main():
    parser = argparse.ArgumentParser(
        description="the system Stage Promotion Tool with automatic LogBook entries"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Promote command
    promote_parser = subparsers.add_parser("promote", help="Promote task to next stage")
    promote_parser.add_argument("task_path", help="Path to task")
    promote_parser.add_argument("--from", dest="from_stage", help="Current stage (auto-detected if omitted)")
    promote_parser.add_argument("--to", dest="to_stage", required=True, help="Target stage")
    promote_parser.add_argument("--reason", help="Reason for promotion")
    promote_parser.add_argument("--agent", default="Builder", choices=["PM", "Planner", "Builder", "Critic"], help="Agent performing promotion")
    promote_parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify task metadata")
    verify_parser.add_argument("task_path", help="Path to task")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "promote":
        task_path = Path(args.task_path)
        success = promote_task(
            task_path=task_path,
            to_stage=args.to_stage,
            from_stage=args.from_stage,
            reason=args.reason,
            agent=args.agent,
            dry_run=args.dry_run
        )
        sys.exit(0 if success else 1)

    elif args.command == "verify":
        verify_task(Path(args.task_path))
        sys.exit(0)

if __name__ == "__main__":
    main()
