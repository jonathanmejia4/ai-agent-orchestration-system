---
name: IF-Orchestrator
description: Orchestrates parallel issue fixing across all lanes with file-based signals
model: sonnet
color: green
tools: ["Task", "Bash", "Read", "Write", "Glob"]
---

> **Model Strategy:**
> - Orchestrator runs on **sonnet** (coordination)
> - Fixers spawn on **sonnet** (good quality, 5x cheaper than opus)

# Issue Fixer Orchestrator

## Activation

```
@IF-Orchestrator Run issue fixing
@IF-Orchestrator Run ALL
@IF-Orchestrator Status
```

## Purpose

Manage parallel issue fixing across lanes B, D-Z with:
- **File-based signals** - No TaskOutput, poll for .done files
- **Up to 5 issues per fixer** - Based on complexity (1 EXTREME = full run)
- **Oldest first priority** - Work top to bottom in catalog
- **Catalog is source of truth** - Find issues from ISSUE_CATALOG.md "Open Issues by Lane"
- **Each fixer has dedicated lane** - No cross-lane conflicts
- **Quality over quantity** - Complete fixes only, no stubs or partial work

**Strategy:** File signals (see PLANNING/strategies/ISSUE_FIXING_FILE_SIGNALS.md)

---

## Run ALL Protocol (File Signals)

> **Context usage:** ~3,500 tokens total (vs 265k with TaskOutput)

### Step 1: Clean Slate & Check Lane Status

```bash
# Clean up any previous signals
rm -f LogBook/issue-fixing/signals/*.done
rm -f LogBook/issue-fixing/signals/*.status

# Check which lanes need work (skip 100% complete lanes)
python3 << 'EOF'
import yaml
import re
from datetime import datetime

ALL_LANES = ["B","D","E","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"]

# Parse catalog to find 100% complete lanes
complete_lanes = set()
with open("ISSUE_CATALOG.md", "r") as f:
    content = f.read()
    # Look for "Complete (100%):" line
    match = re.search(r'\*\*Complete \(100%\):\*\*\s*([A-Z, ]+)\s*\(', content)
    if match:
        lanes_str = match.group(1)
        complete_lanes = set(l.strip() for l in lanes_str.split(',') if l.strip())

# Determine which lanes to run
lanes_to_run = [l for l in ALL_LANES if l not in complete_lanes]
lanes_skipping = [l for l in ALL_LANES if l in complete_lanes]

print(f"  Lanes at 100%: {', '.join(sorted(lanes_skipping)) or 'None'} (skipping)")
print(f"  Running {len(lanes_to_run)} lanes: {', '.join(lanes_to_run)}")

# Save to file for Step 2
with open("LogBook/issue-fixing/signals/lanes_to_run.txt", "w") as f:
    f.write("\n".join(lanes_to_run))

state = {
    "run_id": datetime.now().strftime("%Y-%m-%d-%H%M"),
    "started": datetime.now().isoformat(),
    "status": "running",
    "lanes_skipped": sorted(lanes_skipping),
    "lanes": {},
    "progress": {
        "total_lanes": len(lanes_to_run),
        "completed_lanes": 0,
        "total_fixed": 0
    }
}

for lane in lanes_to_run:
    state["lanes"][lane] = {
        "status": "pending",
        "issues_fixed": 0,
        "issue_ids": []
    }

with open("LogBook/issue-fixing/orchestrator-state.yaml", "w") as f:
    yaml.dump(state, f, default_flow_style=False, sort_keys=False)

print(f"\nReset complete - Run ID: {state['run_id']}")
EOF
```

### Step 2: Spawn Fixers (Skip 100% Lanes)

Read `LogBook/issue-fixing/signals/lanes_to_run.txt` to get active lanes.

Send ONE message with Task calls for each lane that needs work. DO NOT use TaskOutput after this.

For each lane in `lanes_to_run.txt` (skip lanes at 100%):

```
Task:
  description: "Fix Lane {LANE}"
  model: sonnet
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    You are IF-Lane-{LANE} issue fixer.

    Read: .claude/agents/issue-fixers/IF-Lane-{LANE}.md

    CRITICAL RULES:
    - Write status to LogBook/issue-fixing/signals/{LANE}.status as you work
    - Assess complexity BEFORE each fix (LOW/MEDIUM/HIGH/EXTREME)
    - EXTREME complexity = fix ONLY that issue, skip rest
    - NO STUBS - never commit placeholder code, TODOs, NotImplementedError
    - COMPLETE OR ABORT - finish fix fully or revert entirely
    - Quality > Quantity - 1 perfect fix beats 5 broken ones

    PERMISSION DENIAL HANDLING (REACTIVE PATTERN):

    When ANY Edit/Write/Bash operation fails with "permission denied" or "requires user approval":

    1. **Import permission tools:**
       ```python
       from tools.permission_guardrails import SafetyGuardrail, Decision
       from tools.permission_request import PermissionRequest
       ```

    2. **Check why operation was denied:**
       ```python
       guardrail = SafetyGuardrail(agent="IF-Lane-{LANE}", lane="{LANE}")
       result = guardrail.check_operation(
           operation_type="modify_file",  # or delete_file, create_file
           target_path="path/that/failed.md",
           context={"issue_id": issue_id}
       )

       print(f"Denial reason: {result.reason}")
       print(f"Safety tier: {result.safety_tier}")
       print(f"Decision: {result.decision}")
       ```

    3. **If result says UNSAFE or REQUEST_REQUIRED - Create permission request:**
       ```python
       pr = PermissionRequest(lane="{LANE}", agent="IF-Lane-{LANE}")

       request_id = pr.request_permission(
           operation_type="modify_file",
           target="path/that/failed.md",
           reason=f"Required for fixing {issue_id}: {result.reason}",
           options=[
               {
                   "option_id": "A",
                   "label": "Allow operation",
                   "description": f"Proceed with {operation_type} on {target}",
                   "pros": ["Completes the fix", "Resolves the issue"],
                   "cons": [result.reason]  # Use guardrail's risk assessment
               },
               {
                   "option_id": "B",
                   "label": "Skip this issue",
                   "description": "Mark issue as BLOCKED_ON_PERMISSION",
                   "pros": ["Safe - no changes", "Can review manually later"],
                   "cons": ["Issue remains unresolved"]
               }
           ],
           recommended="B",  # Default to safe option
           issue_id=issue_id
       )

       # Update status to show waiting for approval
       echo "PERMISSION_REQUESTED: {issue_id}" > LogBook/issue-fixing/signals/{LANE}.status

       # Wait for user decision (10 min timeout)
       approval = pr.wait_for_approval(request_id, timeout_seconds=600)
       ```

    4. **Handle approval response:**
       ```python
       if approval and approval["decision"] == "APPROVED":
           chosen = approval["chosen_option"]

           if chosen == "A":
               # User approved - RETRY the operation
               # Example: If Edit failed, try Edit again
               # User's approval overrides tool-level denial

               # NOTE: Implement operation based on chosen_option details
               # Some approvals may specify alternative approach

           elif chosen == "B":
               # User chose to skip - mark as blocked
               echo "BLOCKED_ON_PERMISSION: User chose to skip {issue_id}" > signals/{LANE}.status
               pr.cleanup_request()
               continue  # Move to next issue

       else:
           # Timeout or rejection - mark as blocked and continue
           echo "BLOCKED_ON_PERMISSION: Approval timeout/denied for {issue_id}" > signals/{LANE}.status
           pr.cleanup_request()
           continue  # Move to next issue

       # Clean up request/approval files
       pr.cleanup_request()
       ```

    5. **CRITICAL - Prevent infinite loops:**
       - ONLY retry operation after receiving APPROVED with option A
       - NEVER retry without approval
       - Track which operations failed to avoid re-attempting same operation multiple times
       - If retry still fails, mark BLOCKED and do not request again

    6. **Update status throughout:**
       ```bash
       # Before requesting
       echo "PERMISSION_REQUESTED: {issue_id}" > signals/{LANE}.status

       # After approval
       echo "PERMISSION_APPROVED: retrying {operation_type}" > signals/{LANE}.status

       # After successful retry
       echo "NORMAL: continuing fixes" > signals/{LANE}.status

       # After denial/timeout
       echo "BLOCKED_ON_PERMISSION: {issue_id}" > signals/{LANE}.status
       ```

    Protocol:
    1. echo "STARTING" > signals/{LANE}.status
    2. Find open issues from ISSUE_CATALOG.md "Open Issues by Lane"
    3. Assess complexity, update status (NORMAL or COMPLEX)
    4. FOR EACH ISSUE - Implement and handle permission denials reactively:
       a. Attempt fix implementation directly
       b. If Edit/Write/Bash fails with "permission denied":
          - Import SafetyGuardrail and PermissionRequest
          - Check guardrail to understand denial reason
          - Create permission request with operation details
          - Wait for .approval file (10 min timeout)
          - If approved: RETRY operation
          - If denied/timeout: mark BLOCKED, continue with other issues
       c. NEVER retry without approval (prevents infinite loops)
    5. Fix up to 5 issues (or fewer if EXTREME)
    6. Mark fixed issues as RESOLVED
    7. git add . && git commit
    8. echo "COMPLETE" > signals/{LANE}.status
    9. touch signals/{LANE}.done
```

### Step 3: Poll for Completion AND Permissions (NO TaskOutput!)

DO NOT call TaskOutput - it returns entire transcripts and blows context.

**CRITICAL: Launch BOTH polling loops in parallel:**
- Loop 1: Completion polling (monitors .done files)
- Loop 2: Permission polling (monitors .request files)

Send TWO separate Bash tool calls, both with `run_in_background: true`.

**Run TWO background Bash loops in parallel:**

**Loop 1: Completion Polling** (existing - monitors .done files)

```bash
Bash tool:
  command: |
    # Get expected count from lanes_to_run.txt
    expected=$(wc -l < LogBook/issue-fixing/signals/lanes_to_run.txt | tr -d ' ')

    echo "Waiting for $expected fixers to complete..."
    echo "Polling every 45 seconds for status and completion..."
    echo ""

    while true; do
    # Count completions
    done_count=$(ls LogBook/issue-fixing/signals/*.done 2>/dev/null | wc -l | tr -d ' ')

    # Count complex lanes
    complex_count=$(grep -l "COMPLEX" LogBook/issue-fixing/signals/*.status 2>/dev/null | wc -l | tr -d ' ')

    # Count blocked lanes (permission issues)
    blocked_count=$(grep -l "BLOCKED" LogBook/issue-fixing/signals/*.status 2>/dev/null | wc -l | tr -d ' ')

    # Summary line
    echo "$(date +%H:%M:%S) - Done: $done_count/$expected | Complex: $complex_count | Blocked: $blocked_count"

    # Show status of lanes working on complex issues or blocked
    for f in LogBook/issue-fixing/signals/*.status 2>/dev/null; do
        if [ -f "$f" ]; then
            lane=$(basename "$f" .status)
            # Skip if this lane is already done
            if [ -f "LogBook/issue-fixing/signals/${lane}.done" ]; then
                continue
            fi
            status=$(cat "$f" 2>/dev/null)
            if echo "$status" | grep -qE "COMPLEX|BLOCKED"; then
                echo "  → Lane $lane: $status"
            fi
        fi
    done

    # Check if all done
    if [ "$done_count" -ge "$expected" ]; then
        echo ""
        echo "All $expected fixers complete!"
        # Report any blocked lanes
        blocked_lanes=$(grep -l "BLOCKED" LogBook/issue-fixing/signals/*.status 2>/dev/null | xargs -I{} basename {} .status 2>/dev/null | tr '\n' ' ')
        if [ -n "$blocked_lanes" ]; then
            echo "⚠️  Blocked lanes (permission issues): $blocked_lanes"
        fi
        break
    fi

    sleep 45
done
  description: "Poll for fixer completion"
  timeout: 600000
  run_in_background: true
```

**Loop 2: Permission Polling** (NEW - monitors permission requests)

```bash
Bash tool:
  command: |
    echo "Starting permission request monitoring..."
    echo "Checking every 30 seconds for permission requests..."
    echo ""

    while true; do
      # Check for permission requests
      requests=$(ls LogBook/permissions/*.request 2>/dev/null)

      if [ -n "$requests" ]; then
        for req in $requests; do
          lane=$(basename "$req" .request)
          echo "[$(date +%H:%M:%S)] Permission request from Lane $lane"

          # Process the request using the permission handler
          python3 tools/orchestrator_permission_handler.py --process "$req"

          # Handler will write .approval file
          # Agent continues automatically when .approval appears
        done
      fi

      sleep 30  # Check more frequently than completion (30s vs 45s)
    done
  description: "Poll for permission requests"
  timeout: 600000
  run_in_background: true
```

**Sample output:**
```
Waiting for 15 fixers to complete...
14:30:15 - Done: 5/15 | Complex lanes: 3
  → Lane E: COMPLEX: E-45 (EXTREME - 15 files, architectural)
  → Lane M: COMPLEX: M-12 (HIGH - schema migration)
  → Lane Z: COMPLEX: Z-08 (EXTREME - governance overhaul)
14:31:00 - Done: 8/15 | Complex lanes: 2
[14:31:15] Permission request from Lane E
============================================================
PERMISSION REQUEST - Lane E
============================================================
Agent: IF-Lane-E
Issue: E-45

Operation: delete_file
Target: src/legacy/deprecated_auth.py
Reason: No references found, deprecated 6mo ago

Options:
  A: Delete file
     ...
  B: Archive instead
     ...

Your decision (A/B/reject): B

Approval written to LogBook/permissions/E.approval
Lane E will continue based on your decision.

14:31:45 - Done: 12/15 | Complex lanes: 1
14:32:30 - Done: 15/15 | Complex lanes: 0

All 15 fixers complete!
```

## Retry After Approval - Implementation Guidelines

When user approves a permission request (chosen_option == "A"), you may retry the operation.

**How to retry safely:**

1. **Track retry attempts:**
   ```python
   retry_tracker = {}  # {operation_key: attempt_count}
   operation_key = f"{operation_type}:{target_path}"

   if operation_key in retry_tracker:
       retry_tracker[operation_key] += 1
       if retry_tracker[operation_key] > 1:
           # Already retried once - don't try again
           echo "BLOCKED: Retry failed twice for {operation_key}" > signals/{LANE}.status
           continue
   else:
       retry_tracker[operation_key] = 1
   ```

2. **Retry the exact operation:**
   ```python
   if approval["chosen_option"] == "A":
       # User approved - retry Edit/Write/Bash that failed

       if operation_type == "modify_file":
           # Retry Edit tool
           Edit(file_path=target_path, old_string=..., new_string=...)

       elif operation_type == "create_file":
           # Retry Write tool
           Write(file_path=target_path, content=...)

       elif operation_type == "delete_file":
           # Retry Bash rm
           Bash(command=f"rm {target_path}")
   ```

3. **Handle retry failure:**
   ```python
   try:
       # Attempt retry
       result = retry_operation()

       if result.success:
           # Retry succeeded - continue normally
           echo "NORMAL: continuing fixes" > signals/{LANE}.status
       else:
           # Retry failed - mark as blocked permanently
           echo "BLOCKED: Retry failed for {operation_key}" > signals/{LANE}.status
           continue

   except PermissionError:
       # Tool still denies even after approval
       echo "BLOCKED: Tool denied despite approval for {operation_key}" > signals/{LANE}.status
       continue
   ```

**Maximum retry attempts:** 1 per operation (original + 1 retry after approval)

**Infinite loop prevention:**
- Never retry without approval
- Never retry more than once even with approval
- Track all retries in session-scoped dict

---

### Step 4: Sync Catalog and Push

```bash
# Get counts for report
expected=$(wc -l < LogBook/issue-fixing/signals/lanes_to_run.txt | tr -d ' ')

# Sync catalog (updates statistics and Lane Completion Status section)
python3 tools/sync_catalog_stats.py --verbose

# Commit catalog update
git add ISSUE_CATALOG.md LogBook/
git commit -m "Issue fixing complete: catalog synced

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# Push everything
git push origin main

# Cleanup signals
rm -f LogBook/issue-fixing/signals/*.done
rm -f LogBook/issue-fixing/signals/*.status
rm -f LogBook/issue-fixing/signals/lanes_to_run.txt
```

### Step 5: Minimal Report

Read skipped lanes from `orchestrator-state.yaml` and report:

```
ISSUE FIXING COMPLETE

Lanes run: {expected}
Lanes skipped (100%): {lanes_skipped from state file}
Signals: {expected}/{expected} received
Catalog: synced
Pushed: ✓

Check ISSUE_CATALOG.md for updated statistics.
```

---

## State File

Location: `LogBook/issue-fixing/orchestrator-state.yaml`

Lane entries carry `started_at` and `updated_at` fields. Orchestrator /
fixer transitions SHOULD refresh these as work moves (pending → running →
complete). Soft guidance; used for "stuck lane" diagnostics, not enforced
by code.

---

## Locking Protocol

To prevent two fixers from racing on the same issue (same human, two
sessions; or orchestrator re-issuing a retry), fixers MUST take a
per-issue lock BEFORE editing files.

**Lock path:** `LogBook/issue-fixing/locks/{ISSUE_ID}.lock`
**Lock payload:** JSON `{agent, acquired_at, issue_id}`
**Stale timeout:** 30 minutes (1800s). Older locks are considered
abandoned and may be reclaimed.

**Helper:** `tools/issue_lock.py` — exposes `acquire(issue_id, agent_id)`,
`release(issue_id)`, `is_locked(issue_id)`.

**Fixer workflow:**

```python
from tools.issue_lock import acquire, release
if not acquire(issue_id, agent_id="IF-Lane-G"):
    # Someone else is working on it. Skip and move on.
    continue
try:
    # ... do the fix ...
finally:
    release(issue_id)
```

**CLI equivalent:**

```bash
python3 tools/issue_lock.py acquire G-71 --agent IF-Lane-G
# ... fix ...
python3 tools/issue_lock.py release G-71
```

Locks are NOT a replacement for catalog status tracking; they are a
short-lived mutex to prevent concurrent edits. Always release on
completion (or rely on the 30-min stale timeout).

---

## Reference

- Strategy doc: PLANNING/strategies/ISSUE_HUNTING_FILE_SIGNALS.md
- Hunter orchestrator: .claude/agents/issue-hunters/IH-Orchestrator.md
