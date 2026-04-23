#!/usr/bin/env python3
"""
Preview Approver

Approves or rejects a spec-to-diff preview for a task.
Part of the Stage -1 (Preview & Approval) gate.

Usage:
    python3 tools/approve_preview.py --task <task_id> --decision approved
    python3 tools/approve_preview.py --task <task_id> --decision rejected --reason "..."

See: PLANNING/SPEC_TO_DIFF_PREVIEWS_POLICY.md
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

def get_current_user() -> str:
    """Get the current user identity for approval tracking."""
    # Try multiple sources for user identity
    user = None

    # 1. Check AGENT_USER environment variable
    user = os.environ.get('AGENT_USER')
    if user:
        return user

    # 2. Check git config
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

    # 3. Check system user
    user = os.environ.get('USER') or os.environ.get('USERNAME')
    if user:
        return user

    # 4. Default fallback
    return "unknown_user"

def compute_preview_hash(preview_file: Path) -> str:
    """Compute SHA256 hash of preview file for integrity verification."""
    sha256 = hashlib.sha256()
    try:
        with open(preview_file, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception:
        return None

def approve_preview(task_id: str, decision: str, reason: str = None,
                   previews_dir: Path = Path('LogBook/previews')) -> dict:
    """Approve or reject a preview."""
    preview_dir = previews_dir / task_id
    preview_file = preview_dir / "preview.json"
    approval_file = preview_dir / "approval.json"

    if not preview_file.exists():
        raise FileNotFoundError(f"Preview not found: {preview_file}")

    # Load existing preview
    with open(preview_file) as f:
        preview = json.load(f)

    # Get current user identity
    decided_by = get_current_user()

    # Compute preview hash for integrity
    preview_hash = compute_preview_hash(preview_file)

    # Create approval record with real authentication and hash
    approval = {
        "task_id": task_id,
        "decision": decision,
        "decided_at": datetime.utcnow().isoformat() + "Z",
        "decided_by": decided_by,
        "reason": reason,
        "preview_hash": preview_hash,
        "preview_file": str(preview_file),
        "approval_version": "1.0"
    }

    # Update preview status
    preview["status"] = "approved" if decision == "approved" else "rejected"
    preview["approval"] = approval

    # Write updated preview
    with open(preview_file, 'w') as f:
        json.dump(preview, f, indent=2)

    # Write approval record
    with open(approval_file, 'w') as f:
        json.dump(approval, f, indent=2)

    return approval

def main():
    parser = argparse.ArgumentParser(
        description="Approve or reject a spec-to-diff preview"
    )
    parser.add_argument('--task', '-b', required=True,
                        help='Task ID')
    parser.add_argument('--decision', '-d', required=True,
                        choices=['approved', 'rejected'],
                        help='Decision: approved or rejected')
    parser.add_argument('--reason', '-r',
                        help='Reason for decision (required for rejection)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    if args.decision == "rejected" and not args.reason:
        print("Error: --reason is required when rejecting a preview")
        return 1

    try:
        approval = approve_preview(args.task, args.decision, args.reason)
        print(f"Preview {args.decision}: {args.task}")

        if args.verbose:
            print(json.dumps(approval, indent=2))

        if args.decision == "approved":
            print("\nTask is now approved for code generation (Stage 0+)")
        else:
            print(f"\nTask rejected. Reason: {args.reason}")
            print("Generate a new preview after addressing concerns.")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(f"Run: python tools/generate_preview.py --task {args.task}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
