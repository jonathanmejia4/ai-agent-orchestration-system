# State Persistence Protocol

> **Document Version:** 1.0.0
> **Last Updated:** 2025-01-15
> **Classification:** HIGH - System Integrity
> **Reference:** FAILURE_MODES.md:512, ROLLBACK_PROCEDURES.md:178

## Purpose

This document defines the **state persistence protocol** for the the system, ensuring all critical state is properly saved, validated, and recoverable. Proper state management prevents data loss, enables rollback, and maintains system consistency across sessions.

**Why This Matters:**
- Prevents loss of work order progress and decisions
- Enables system recovery after failures
- Maintains consistency across agent handoffs
- Supports audit trail and compliance requirements
- Enables reliable rollback procedures

---

## 1. State File Definitions

### 1.1 Critical State Files

| State File | Location | Owner | Purpose | Update Frequency |
|------------|----------|-------|---------|------------------|
| PM State | `LogBook/pm/STATE.md` | PM | Current project state, phase, blockers | Per action |
| Work Orders | `LogBook/work-orders/` | PM | Active and pending work orders (individual files per WO) | Per WO change |
| Issue Catalog | `ISSUE_CATALOG.md` | PM | Issue tracking and resolution | Per resolution |
| Builder Progress | `LogBook/builder/progress.yaml` | Builder | Current build status | Per action |
| Task Status | `LogBook/progress/tasks/<task-id>/status.yaml` | Builder | Per-task completion status for PM monitoring | Per task completion |
| Critic Verdicts | `LogBook/critic/verdicts.yaml` | Critic | Review history and verdicts | Per verdict |
| Planner Analysis | `LogBook/planner/planning_log.yaml` | Planner | Planning decisions | Per plan |
| Milestone Tracker | `PLANNING/MILESTONE_TRACKER.md` | PM | Project milestones | Per milestone |
| Master Plan | `PLANNING/MASTER_PLAN.md` | PM | Phase definitions | Per phase change |

### 1.2 State File Categories

```yaml
state_categories:
  critical:
    description: "System cannot operate without these"
    recovery_priority: 1
    backup_frequency: "every_commit"
    files:
      - "LogBook/pm/STATE.md"
      - "LogBook/work-orders/**/*.yaml"
      - "ISSUE_CATALOG.md"

  important:
    description: "Significant data loss if corrupted"
    recovery_priority: 2
    backup_frequency: "daily"
    files:
      - "LogBook/builder/progress.yaml"
      - "LogBook/critic/verdicts.yaml"
      - "LogBook/planner/planning_log.yaml"
      - "PLANNING/MILESTONE_TRACKER.md"

  standard:
    description: "Historical data, can be reconstructed"
    recovery_priority: 3
    backup_frequency: "weekly"
    files:
      - "LogBook/*/actions/*.yaml"
      - "LogBook/pm/escalations/*.yaml"
```

---

## 2. State Persistence Requirements

### 2.1 Mandatory Persistence Rules

```
RULE 1: WRITE-BEFORE-ACTION
  - State MUST be persisted BEFORE any action that modifies it
  - No in-memory-only state for critical data

RULE 2: ATOMIC WRITES
  - State file updates MUST be atomic
  - Use write-to-temp-then-rename pattern

RULE 3: VALIDATION-AFTER-WRITE
  - Every write MUST be followed by validation read
  - Rollback if validation fails

RULE 4: VERSION TRACKING
  - All state files MUST track version/timestamp
  - Enable conflict detection

RULE 5: NO STATE ASSUMPTIONS
  - Agents MUST read current state before modifying
  - Never assume state from previous session
```

### 2.2 State Update Protocol

```python
import os
import shutil
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path


class StateManager:
    """Manages state file persistence with atomic writes and validation."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.backup_path = self.base_path / ".state_backups"
        self.backup_path.mkdir(exist_ok=True)

    def update_state(
        self,
        file_path: str,
        content: str,
        agent: str,
        operation: str = "update"
    ) -> dict:
        """
        Safely update a state file with atomic write and validation.

        Args:
            file_path: Path to state file
            content: New content to write
            agent: Agent performing update
            operation: Type of operation (update, create, append)

        Returns:
            Result dict with success status and details
        """
        target = self.base_path / file_path
        result = {
            "success": False,
            "file_path": str(target),
            "agent": agent,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        try:
            # Step 1: Create backup of existing file
            if target.exists():
                backup_file = self._create_backup(target)
                result["backup_created"] = str(backup_file)
                result["checksum_before"] = self._checksum(target)
            else:
                result["backup_created"] = None
                result["checksum_before"] = None

            # Step 2: Write to temporary file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=target.parent,
                prefix=f".{target.stem}_",
                suffix=".tmp"
            )

            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
            except Exception as e:
                os.unlink(temp_path)
                raise e

            # Step 3: Atomic rename
            shutil.move(temp_path, target)

            # Step 4: Validate write
            result["checksum_after"] = self._checksum(target)

            with open(target, 'r', encoding='utf-8') as f:
                written_content = f.read()

            if written_content != content:
                # Validation failed - rollback
                if result["backup_created"]:
                    shutil.copy(result["backup_created"], target)
                raise ValueError("Write validation failed - content mismatch")

            result["success"] = True
            result["bytes_written"] = len(content.encode('utf-8'))

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)

        # Log the operation
        self._log_state_update(result)

        return result

    def read_state(self, file_path: str, validate: bool = True) -> dict:
        """
        Read a state file with optional validation.

        Returns:
            {
                "success": bool,
                "content": str or None,
                "checksum": str,
                "last_modified": str,
                "validation": dict
            }
        """
        target = self.base_path / file_path
        result = {
            "success": False,
            "file_path": str(target),
            "content": None,
            "checksum": None,
            "last_modified": None,
            "validation": None
        }

        if not target.exists():
            result["error"] = f"State file not found: {file_path}"
            return result

        try:
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()

            result["content"] = content
            result["checksum"] = self._checksum(target)
            result["last_modified"] = datetime.fromtimestamp(
                target.stat().st_mtime
            ).isoformat() + "Z"
            result["success"] = True

            if validate:
                result["validation"] = self._validate_state_file(file_path, content)

        except Exception as e:
            result["error"] = str(e)

        return result

    def _create_backup(self, file_path: Path) -> Path:
        """Create a timestamped backup of the file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"

        # Create date-based subdirectory
        date_dir = self.backup_path / datetime.utcnow().strftime("%Y-%m")
        date_dir.mkdir(exist_ok=True)

        backup_file = date_dir / backup_name
        shutil.copy2(file_path, backup_file)

        return backup_file

    def _checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file (security-grade)."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _validate_state_file(self, file_path: str, content: str) -> dict:
        """Validate state file format and content."""
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Check for empty content
        if not content.strip():
            validation["errors"].append("Empty state file")
            validation["valid"] = False

        # Check for required headers based on file type
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            try:
                import yaml
                yaml.safe_load(content)
            except Exception as e:
                validation["errors"].append(f"Invalid YAML: {e}")
                validation["valid"] = False

        elif file_path.endswith('.md'):
            # Check for version/timestamp header
            if "last_updated:" not in content.lower() and "version:" not in content.lower():
                validation["warnings"].append("No version/timestamp header found")

        return validation

    def _log_state_update(self, result: dict):
        """Log state update to audit trail."""
        log_path = self.base_path / "LogBook" / "audit" / "state_updates.yaml"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": result["timestamp"],
            "file_path": result["file_path"],
            "agent": result["agent"],
            "operation": result["operation"],
            "success": result["success"],
            "checksum_before": result.get("checksum_before"),
            "checksum_after": result.get("checksum_after"),
            "backup": result.get("backup_created"),
            "error": result.get("error")
        }

        # Append to log (simple append for now)
        with open(log_path, 'a', encoding='utf-8') as f:
            import yaml
            f.write("---\n")
            yaml.dump(entry, f, default_flow_style=False)
```

### 2.3 Agent State Update Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   STATE UPDATE FLOW                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. READ CURRENT STATE                                      │
│     └── Validate format and content                         │
│                                                              │
│  2. CREATE BACKUP                                           │
│     └── Timestamped copy in .state_backups/                 │
│                                                              │
│  3. PREPARE NEW STATE                                       │
│     └── Merge changes with current state                    │
│                                                              │
│  4. WRITE TO TEMP FILE                                      │
│     └── Write + fsync to ensure disk write                  │
│                                                              │
│  5. ATOMIC RENAME                                           │
│     └── Move temp file to target path                       │
│                                                              │
│  6. VALIDATE WRITE                                          │
│     └── Read back and compare checksums                     │
│                                                              │
│  7. LOG UPDATE                                              │
│     └── Record in audit trail                               │
│                                                              │
│  8. ROLLBACK IF FAILED                                      │
│     └── Restore from backup                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. State File Formats

### 3.1 PM State File Format

```markdown
# LogBook/pm/STATE.md

## Project State

**Last Updated:** 2025-01-15T10:30:00Z
**Version:** 1.2.3
**State Hash:** abc123def456

### Current Phase
- **Phase:** Implementation
- **Phase Start:** 2025-01-10
- **Expected End:** 2025-01-20

### Active Work
- **Active Work Orders:** 3
- **Pending Reviews:** 2
- **Blocked Items:** 1

### Blockers
| ID | Description | Owner | Since |
|----|-------------|-------|-------|
| B-001 | Waiting for external API | Builder | 2025-01-14 |

### Recent Actions
1. 2025-01-15T10:30:00Z - Approved WO-20250115-042
2. 2025-01-15T09:15:00Z - Created WO-20250115-043
3. 2025-01-15T08:00:00Z - Updated milestone M-003

### Session Context
- **Current Focus:** Resolving issue catalog items
- **Pending Decisions:** Architecture review for Phase 3
- **Notes:** Expedited timeline requested
```

### 3.2 Work Order Format

Work orders are stored as individual files in `LogBook/work-orders/` with status-based subdirectories:
- `pending/` - New work orders awaiting assignment
- `in-progress/` - Work orders currently being executed
- `completed/` - Successfully completed work orders
- `failed/` - Work orders that failed
- `blocked/` - Work orders blocked by dependencies

```yaml
# LogBook/work-orders/pending/WO-20250115-042.yaml
---
work_order_id: "WO-20250115-042"
task_id: "3.2"
agent: "builder"
status: "PENDING"
priority: "HIGH"
created: "2025-01-14T14:00:00Z"
deadline: "2025-01-16T18:00:00Z"
description: "Implement user authentication module"
requirements:
  - "OAuth 2.0 support"
  - "Session management"
  - "Password hashing with bcrypt"
    dependencies:
      - "WO-20250114-040"  # Database schema
    progress:
      percentage: 60
      last_update: "2025-01-15T10:00:00Z"

  - work_order_id: "WO-20250115-043"
    task_id: "3.3"
    agent: "builder"
    status: "PENDING"
    priority: "MEDIUM"
    created: "2025-01-15T08:00:00Z"
    description: "Add logging infrastructure"
    dependencies:
      - "WO-20250115-042"

queue_order:
  - "WO-20250115-042"
  - "WO-20250115-043"
  - "WO-20250115-044"
```

### 3.3 Builder Progress Format

```yaml
# LogBook/builder/progress.yaml
---
metadata:
  agent: "builder"
  last_updated: "2025-01-15T10:30:00Z"
  session_id: "SES-2025-015-001"

current_work:
  work_order_id: "WO-20250115-042"
  task_id: "3.2"
  status: "IN_PROGRESS"
  started: "2025-01-14T14:30:00Z"
  progress_percentage: 60
  files_created:
    - path: "src/auth/oauth.py"
      lines: 245
      status: "complete"
    - path: "src/auth/session.py"
      lines: 180
      status: "in_progress"
  files_modified: []
  tests_written:
    - "tests/auth/test_oauth.py"
    - "tests/auth/test_session.py"
  blockers: []

entries:
  - timestamp: "2025-01-15T10:30:00Z"
    action: "implemented"
    description: "Added session token generation"
    files_affected:
      - "src/auth/session.py"
    work_order_id: "WO-20250115-042"
    progress_delta: 15

  - timestamp: "2025-01-15T09:00:00Z"
    action: "implemented"
    description: "Completed OAuth 2.0 flow"
    files_affected:
      - "src/auth/oauth.py"
    work_order_id: "WO-20250115-042"
    progress_delta: 25
```

---

## 4. Recovery Procedures

### 4.1 State Corruption Detection

```python
class StateCorruptionDetector:
    """Detects corrupted state files."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)

    def check_all_state_files(self) -> dict:
        """
        Check all critical state files for corruption.

        Returns summary of corruption status.
        """
        state_files = [
            "LogBook/pm/STATE.md",
            "LogBook/work-orders/",  # Directory with individual WO files
            "ISSUE_CATALOG.md",
            "LogBook/builder/progress.yaml",
            "LogBook/critic/verdicts.yaml",
        ]

        results = {
            "checked": 0,
            "healthy": 0,
            "corrupted": [],
            "missing": [],
            "warnings": []
        }

        for file_path in state_files:
            full_path = self.base_path / file_path
            results["checked"] += 1

            if not full_path.exists():
                results["missing"].append(file_path)
                continue

            corruption = self._check_file_corruption(full_path)

            if corruption["corrupted"]:
                results["corrupted"].append({
                    "file": file_path,
                    "issues": corruption["issues"]
                })
            else:
                results["healthy"] += 1

            if corruption["warnings"]:
                results["warnings"].extend([
                    {"file": file_path, "warning": w}
                    for w in corruption["warnings"]
                ])

        return results

    def _check_file_corruption(self, file_path: Path) -> dict:
        """Check a single file for corruption."""
        result = {
            "corrupted": False,
            "issues": [],
            "warnings": []
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for empty file
            if not content.strip():
                result["corrupted"] = True
                result["issues"].append("File is empty")
                return result

            # Check for null bytes (binary corruption)
            if '\x00' in content:
                result["corrupted"] = True
                result["issues"].append("Contains null bytes (binary corruption)")
                return result

            # Check for truncation indicators
            if content.endswith('...') or content.endswith('---\n---'):
                result["warnings"].append("Possible truncation detected")

            # YAML-specific checks
            if file_path.suffix in ['.yaml', '.yml']:
                try:
                    import yaml
                    data = yaml.safe_load(content)
                    if data is None:
                        result["warnings"].append("YAML parses to null")
                except yaml.YAMLError as e:
                    result["corrupted"] = True
                    result["issues"].append(f"Invalid YAML: {e}")

            # Markdown-specific checks
            if file_path.suffix == '.md':
                # Check for required sections
                if 'STATE.md' in str(file_path):
                    required = ['## Project State', 'Last Updated:']
                    for req in required:
                        if req not in content:
                            result["warnings"].append(f"Missing expected section: {req}")

        except Exception as e:
            result["corrupted"] = True
            result["issues"].append(f"Cannot read file: {e}")

        return result
```

### 4.2 Recovery from Backup

```python
class StateRecovery:
    """Recovers state files from backups."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.backup_path = self.base_path / ".state_backups"

    def recover_file(self, file_path: str, backup_timestamp: str = None) -> dict:
        """
        Recover a state file from backup.

        Args:
            file_path: Path to corrupted state file
            backup_timestamp: Specific backup to restore (optional)

        Returns:
            Recovery result
        """
        result = {
            "success": False,
            "file_path": file_path,
            "backup_used": None,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # Find available backups
        backups = self._find_backups(file_path)

        if not backups:
            result["error"] = "No backups available"
            return result

        # Select backup to restore
        if backup_timestamp:
            backup_file = self._find_specific_backup(backups, backup_timestamp)
        else:
            backup_file = backups[0]  # Most recent

        if not backup_file:
            result["error"] = f"Backup not found for timestamp: {backup_timestamp}"
            return result

        try:
            # Validate backup before restoring
            validation = self._validate_backup(backup_file)
            if not validation["valid"]:
                result["error"] = f"Backup validation failed: {validation['error']}"
                return result

            # Create backup of current (corrupted) file for forensics
            target = self.base_path / file_path
            if target.exists():
                forensic_backup = self._create_forensic_backup(target)
                result["forensic_backup"] = str(forensic_backup)

            # Restore from backup
            shutil.copy2(backup_file, target)

            # Validate restoration
            with open(target, 'r') as f:
                restored_content = f.read()
            with open(backup_file, 'r') as f:
                backup_content = f.read()

            if restored_content != backup_content:
                result["error"] = "Restoration verification failed"
                return result

            result["success"] = True
            result["backup_used"] = str(backup_file)
            result["backup_date"] = backup_file.stem.split('_')[-2]

        except Exception as e:
            result["error"] = str(e)

        # Log recovery
        self._log_recovery(result)

        return result

    def list_available_backups(self, file_path: str) -> list:
        """List all available backups for a file."""
        backups = self._find_backups(file_path)
        return [
            {
                "file": str(b),
                "timestamp": b.stem.split('_')[-2] + "_" + b.stem.split('_')[-1],
                "size": b.stat().st_size
            }
            for b in backups
        ]

    def _find_backups(self, file_path: str) -> list:
        """Find all backups for a file, sorted by date (newest first)."""
        file_stem = Path(file_path).stem

        backups = []
        for date_dir in self.backup_path.glob("*"):
            if date_dir.is_dir():
                for backup in date_dir.glob(f"{file_stem}_*"):
                    backups.append(backup)

        return sorted(backups, key=lambda x: x.stat().st_mtime, reverse=True)

    def _validate_backup(self, backup_file: Path) -> dict:
        """Validate a backup file before restoration."""
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                return {"valid": False, "error": "Backup is empty"}

            if '\x00' in content:
                return {"valid": False, "error": "Backup contains null bytes"}

            return {"valid": True}

        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _create_forensic_backup(self, file_path: Path) -> Path:
        """Create forensic backup of corrupted file."""
        forensic_dir = self.backup_path / "forensic"
        forensic_dir.mkdir(exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        forensic_file = forensic_dir / f"{file_path.stem}_CORRUPTED_{timestamp}{file_path.suffix}"

        shutil.copy2(file_path, forensic_file)
        return forensic_file

    def _log_recovery(self, result: dict):
        """Log recovery action."""
        log_path = self.base_path / "LogBook" / "audit" / "state_recovery.yaml"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, 'a', encoding='utf-8') as f:
            import yaml
            f.write("---\n")
            yaml.dump(result, f, default_flow_style=False)
```

### 4.3 Recovery Decision Tree

```
STATE FILE ISSUE DETECTED
         │
         ▼
    ┌────────────┐
    │ Is file    │──Yes──▶ Check .state_backups/
    │ missing?   │              │
    └────────────┘              ▼
         │              ┌─────────────┐
         No             │ Backup      │──Yes──▶ RESTORE FROM BACKUP
         │              │ available?  │
         ▼              └─────────────┘
    ┌────────────┐              │
    │ Is file    │              No
    │ corrupted? │              │
    └────────────┘              ▼
         │              ┌─────────────────┐
         │              │ RECONSTRUCT     │
         │              │ from:           │
         │              │ - Git history   │
         │              │ - LogBook       │
         │              │ - Other agents  │
         │              └─────────────────┘
         │
         Yes
         │
         ▼
    ┌────────────────────┐
    │ Create forensic    │
    │ backup of corrupt  │
    │ file               │
    └────────────────────┘
         │
         ▼
    ┌────────────┐
    │ Backup     │──Yes──▶ RESTORE FROM BACKUP
    │ available? │
    └────────────┘
         │
         No
         │
         ▼
    ┌────────────────────┐
    │ MANUAL RECOVERY    │
    │ - Escalate to PM   │
    │ - Check git log    │
    │ - Reconstruct      │
    └────────────────────┘
```

---

## 5. Backup and Versioning

### 5.1 Backup Strategy

```yaml
backup_strategy:
  automatic_backups:
    trigger: "before_every_write"
    location: ".state_backups/{YYYY-MM}/"
    naming: "{filename}_{YYYYMMDD}_{HHMMSS}.{ext}"

  retention:
    daily_backups: 7        # Keep last 7 days of daily backups
    weekly_backups: 4       # Keep last 4 weekly backups
    monthly_backups: 12     # Keep last 12 monthly backups

  critical_files:
    retention_override:
      - file: "LogBook/pm/STATE.md"
        keep_all_for_days: 30
      - file: "LogBook/work-orders/**/*.yaml"
        keep_all_for_days: 14

  cleanup:
    schedule: "daily at 02:00 UTC"
    dry_run_first: true
```

### 5.2 Version Tracking

All state files MUST include version metadata:

```yaml
# For YAML files
metadata:
  version: "2025.01.15.003"  # YYYY.MM.DD.sequence
  last_updated: "2025-01-15T10:30:00Z"
  updated_by: "pm"
  previous_version: "2025.01.15.002"
  change_summary: "Added WO-20250115-043 to queue"
```

```markdown
<!-- For Markdown files -->
---
version: 2025.01.15.003
last_updated: 2025-01-15T10:30:00Z
updated_by: pm
---
```

### 5.3 Backup Cleanup Script

```python
#!/usr/bin/env python3
"""
cleanup_backups.py - State backup cleanup utility.
Implements retention policy for state file backups.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path


def cleanup_backups(
    backup_dir: str = ".state_backups",
    daily_keep: int = 7,
    weekly_keep: int = 4,
    monthly_keep: int = 12,
    dry_run: bool = True
) -> dict:
    """
    Clean up old backups according to retention policy.

    Returns summary of cleanup actions.
    """
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return {"error": "Backup directory not found"}

    now = datetime.utcnow()
    cutoffs = {
        "daily": now - timedelta(days=daily_keep),
        "weekly": now - timedelta(weeks=weekly_keep),
        "monthly": now - timedelta(days=monthly_keep * 30)
    }

    actions = {
        "scanned": 0,
        "kept": 0,
        "deleted": [],
        "errors": []
    }

    # Scan all backup files
    for backup_file in backup_path.rglob("*"):
        if not backup_file.is_file():
            continue

        actions["scanned"] += 1

        # Parse timestamp from filename
        try:
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
        except Exception as e:
            actions["errors"].append(f"Cannot read {backup_file}: {e}")
            continue

        # Determine retention category
        keep = False

        # Keep all from last N days
        if file_time > cutoffs["daily"]:
            keep = True

        # Keep weekly backups (oldest of each week)
        elif file_time > cutoffs["weekly"]:
            # Keep if it's the oldest backup of its week
            week_start = file_time - timedelta(days=file_time.weekday())
            week_backups = [
                f for f in backup_path.rglob(f"{backup_file.stem.split('_')[0]}_*")
                if datetime.fromtimestamp(f.stat().st_mtime).isocalendar()[1] == file_time.isocalendar()[1]
            ]
            if backup_file == min(week_backups, key=lambda x: x.stat().st_mtime):
                keep = True

        # Keep monthly backups (oldest of each month)
        elif file_time > cutoffs["monthly"]:
            month_str = file_time.strftime("%Y-%m")
            month_backups = [
                f for f in backup_path.rglob(f"{backup_file.stem.split('_')[0]}_*")
                if datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m") == month_str
            ]
            if backup_file == min(month_backups, key=lambda x: x.stat().st_mtime):
                keep = True

        if keep:
            actions["kept"] += 1
        else:
            if dry_run:
                actions["deleted"].append({"file": str(backup_file), "dry_run": True})
            else:
                try:
                    backup_file.unlink()
                    actions["deleted"].append({"file": str(backup_file), "deleted": True})
                except Exception as e:
                    actions["errors"].append(f"Failed to delete {backup_file}: {e}")

    return actions
```

---

## 6. State Synchronization

### 6.1 Cross-Agent State Consistency

```python
class StateSynchronizer:
    """Ensures state consistency across agents."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)

    def verify_consistency(self) -> dict:
        """
        Verify state consistency across all agents.

        Checks:
        - Work order references match
        - Task IDs are consistent
        - Timestamps are sequential
        - No orphaned references
        """
        results = {
            "consistent": True,
            "issues": [],
            "checked": []
        }

        # Load all state files
        pm_state = self._load_state("LogBook/pm/STATE.md")
        wo_files = self._load_work_orders("LogBook/work-orders/")  # Individual WO files
        builder_progress = self._load_yaml("LogBook/builder/progress.yaml")
        critic_verdicts = self._load_yaml("LogBook/critic/verdicts.yaml")

        # Check 1: Builder's current WO exists in work-orders directory
        if builder_progress:
            current_wo = builder_progress.get("current_work", {}).get("work_order_id")
            if current_wo:
                wo_ids = [wo.get("work_order_id") for wo in wo_files]
                if current_wo not in wo_ids:
                    results["consistent"] = False
                    results["issues"].append({
                        "type": "ORPHANED_WORK_ORDER",
                        "details": f"Builder working on {current_wo} but not in WO queue"
                    })

        # Check 2: Critic verdicts reference valid tasks
        if critic_verdicts:
            for verdict in critic_verdicts.get("verdicts", []):
                task_id = verdict.get("task_id")
                wo_id = verdict.get("work_order_id")
                # Verify task/WO exists in system
                results["checked"].append(f"Verdict {verdict.get('verdict_id')}")

        # Check 3: Timestamps are reasonable
        self._check_timestamp_consistency(results)

        return results

    def _load_yaml(self, path: str) -> dict:
        """Load YAML state file."""
        try:
            import yaml
            full_path = self.base_path / path
            if full_path.exists():
                with open(full_path) as f:
                    return yaml.safe_load(f) or {}
        except Exception:
            pass
        return {}

    def _load_state(self, path: str) -> str:
        """Load state file content."""
        try:
            full_path = self.base_path / path
            if full_path.exists():
                with open(full_path) as f:
                    return f.read()
        except Exception:
            pass
        return ""

    def _check_timestamp_consistency(self, results: dict):
        """Check timestamp ordering across state files."""
        # Implementation would compare timestamps across files
        # to ensure they're within reasonable bounds
        pass
```

---

## 7. Quick Reference

### 7.1 State File Checklist

```markdown
## Before ANY State Update

[ ] Read current state (never assume)
[ ] Validate current state format
[ ] Create backup before modification
[ ] Prepare new state content
[ ] Write to temp file first
[ ] Atomic rename to target
[ ] Validate write succeeded
[ ] Log update to audit trail
[ ] Clean up temp files

## State File Requirements

[ ] Version/timestamp header present
[ ] Valid format (YAML/Markdown)
[ ] No null bytes or corruption
[ ] All required sections present
[ ] Cross-references valid
```

### 7.2 Emergency Recovery Quick Start

```bash
# 1. Check for corruption
python -c "
from tools.state_manager import StateCorruptionDetector
detector = StateCorruptionDetector()
results = detector.check_all_state_files()
print(results)
"

# 2. List available backups
ls -la .state_backups/

# 3. Recover specific file
python -c "
from tools.state_manager import StateRecovery
recovery = StateRecovery()
result = recovery.recover_file('LogBook/pm/STATE.md')
print(result)
"

# 4. Verify recovery
python tools/validate_logbook.py LogBook/pm/STATE.md
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-15 | PM | Initial document creation |

---

**CRITICAL REMINDER:** State persistence is the foundation of system reliability. Any state update without proper backup and validation is a potential data loss incident. Follow the protocol without exception.
