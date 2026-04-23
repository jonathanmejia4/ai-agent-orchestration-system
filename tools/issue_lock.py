#!/usr/bin/env python3
"""
issue_lock.py - Per-issue file locks for fixer safety.

Prevents two fixer agents from racing on the same issue. Locks live at
LogBook/issue-fixing/locks/{ISSUE_ID}.lock and contain the acquiring
agent's identity plus a timestamp.

Stale-lock policy: locks older than STALE_SECS (30 min) are considered
abandoned and may be reclaimed by a new acquirer.

Usage (library):
    from tools.issue_lock import acquire, release, is_locked
    if acquire("G-71", agent_id="IF-Lane-G"):
        try:
            ...fix the issue...
        finally:
            release("G-71")

Usage (CLI):
    python3 tools/issue_lock.py acquire G-71 --agent IF-Lane-G
    python3 tools/issue_lock.py status G-71
    python3 tools/issue_lock.py release G-71
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Lock directory (repo-root relative). Keep consistent with IF-Orchestrator.
LOCK_DIR = Path("LogBook/issue-fixing/locks")

# Stale-lock timeout in seconds (30 minutes).
# A lock older than this is treated as abandoned and may be reclaimed.
STALE_SECS = 1800


def _lock_path(issue_id: str) -> Path:
    return LOCK_DIR / f"{issue_id}.lock"


def acquire(issue_id: str, agent_id: str) -> bool:
    """Attempt to acquire the lock for *issue_id*.

    Returns True on success, False if another agent currently holds an
    unexpired lock. Stale locks (older than STALE_SECS) are reclaimed.
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(issue_id)

    if lock_path.exists():
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            age = float("inf")  # vanished under us, safe to recreate
        if age < STALE_SECS:
            return False
        # Stale — reclaim.
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass

    payload = json.dumps({
        "agent": agent_id,
        "acquired_at": time.time(),
        "issue_id": issue_id,
    })
    # Write atomically so a concurrent reader never sees an empty file.
    tmp = lock_path.with_suffix(lock_path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, lock_path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
        raise
    return True


def release(issue_id: str) -> None:
    """Release the lock for *issue_id*. Idempotent — no error if absent."""
    lock_path = _lock_path(issue_id)
    if lock_path.exists():
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def is_locked(issue_id: str) -> bool:
    """Return True if *issue_id* has an unexpired lock."""
    lock_path = _lock_path(issue_id)
    if not lock_path.exists():
        return False
    try:
        age = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        return False
    return age < STALE_SECS


def lock_info(issue_id: str) -> dict | None:
    """Return parsed lock payload (+ age_secs) or None if no active lock."""
    lock_path = _lock_path(issue_id)
    if not lock_path.exists():
        return None
    try:
        age = time.time() - lock_path.stat().st_mtime
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    data["age_secs"] = age
    data["stale"] = age >= STALE_SECS
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-issue lock management")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_acq = sub.add_parser("acquire", help="Acquire a lock")
    p_acq.add_argument("issue_id")
    p_acq.add_argument("--agent", required=True, help="Agent identifier")

    p_rel = sub.add_parser("release", help="Release a lock")
    p_rel.add_argument("issue_id")

    p_stat = sub.add_parser("status", help="Show lock status")
    p_stat.add_argument("issue_id")

    args = parser.parse_args()

    if args.cmd == "acquire":
        ok = acquire(args.issue_id, args.agent)
        print(json.dumps({"acquired": ok, "issue_id": args.issue_id}))
        return 0 if ok else 1

    if args.cmd == "release":
        release(args.issue_id)
        print(json.dumps({"released": True, "issue_id": args.issue_id}))
        return 0

    if args.cmd == "status":
        info = lock_info(args.issue_id)
        print(json.dumps({"issue_id": args.issue_id, "locked": is_locked(args.issue_id), "info": info}, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
