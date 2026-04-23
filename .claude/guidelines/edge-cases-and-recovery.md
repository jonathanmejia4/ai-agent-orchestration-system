# Edge Cases & Recovery Procedures
**Version:** 1.0.1
**Last Updated:** 2026-01-05
**Owner:** PM
**Classification:** MEDIUM - Operational Guidelines

**Purpose:** Address production edge cases not covered in primary guidelines
**Audience:** All agents
**Authority:** Augments agent-coordination-protocol.md and quality-standards.md

---

## 1. Git Merge Conflict Resolution Protocol

**Problem:** When two Builders modify the same file in parallel tasks, Git merge conflicts occur.

**Designated Owner:** **First Builder who committed** (chronological priority)

### Resolution Process

1. **PM detects conflict during promotion:**
   ```bash
   git merge origin/feat-api-v2
   # CONFLICT (content): Merge conflict in src/api.py
   # Automatic merge failed
   ```

2. **PM identifies first committer:**
   ```bash
   # Find who committed first
   git log --all --format="%H %an %ai %s" -- src/api.py | head -2
   # Output:
   # abc123 Builder-A 2025-12-21 10:00:00 "Task 1.1: Add endpoint"
   # def456 Builder-B 2025-12-21 10:30:00 "Task 1.2: Add validation"
   # Builder-A committed first → Builder-A is designated owner
   ```

3. **PM assigns conflict resolution to first Builder:**
   ```markdown
   ## Work Order: Resolve Merge Conflict (Task 1.1 + 1.2)
   **Assigned to:** Builder-A
   **Conflict file:** src/api.py
   **Conflicting branch:** feat-api-v2 (Builder-B's work)

   ### Task
   1. Merge feat-api-v2 into your branch (feat-api-v1)
   2. Resolve conflicts in src/api.py
   3. Ensure both task 1.1 AND task 1.2 functionality works
   4. Re-run tests for BOTH tasks
   5. Request Critic re-review merged result
   ```

4. **Builder-A resolves conflict:**
   ```bash
   git checkout feat-api-v1
   git merge feat-api-v2
   # Fix conflicts in src/api.py
   git add src/api.py
   git commit -m "Resolve conflict: merge task 1.2 into task 1.1"
   # Run tests for both tasks
   pytest tests/test_api_v1.py tests/test_api_v2.py
   ```

5. **Critic re-reviews merged task**

**If Builder-A unavailable:**
- PM attempts resolution OR
- Assigns to Builder-B OR
- Escalates to human (Level 2)

### Prevention

**PM MUST verify no file overlap before assigning parallel tasks:**

```bash
# Before assigning task 1.2, check if it modifies files from task 1.1
TASK_1_1_FILES=$(git diff --name-only feat-api-v1)
TASK_1_2_PLANNED_FILES=$(cat PLANNING/tasks/1.2/files.txt)

# Check for overlap
OVERLAP=$(comm -12 <(echo "$TASK_1_1_FILES") <(echo "$TASK_1_2_PLANNED_FILES"))

if [ -n "$OVERLAP" ]; then
  echo "❌ CONFLICT RISK: Tasks 1.1 and 1.2 both modify: $OVERLAP"
  echo "Making tasks sequential instead of parallel"
fi
```

---

## 2. Partial Task Completion Recovery

**Problem:** Builder completes 80% of task, then crashes/times out. Don't waste 3+ hours of work.

### Checkpoint System

**Builder SHOULD commit checkpoints every hour (recommended best practice):**

```bash
# Checkpoint 1: Tests written
git add tests/
git commit -m "WIP: Task 3.2.1 checkpoint 1/4 (tests written, 0 passing)"

# Checkpoint 2: Implementation 50%
git add src/api.py
git commit -m "WIP: Task 3.2.1 checkpoint 2/4 (implementation 50%, 5/10 tests passing)"

# Checkpoint 3: Implementation 90%
git add src/api.py src/validation.py
git commit -m "WIP: Task 3.2.1 checkpoint 3/4 (implementation 90%, 9/10 tests passing)"

# Checkpoint 4: Complete
git add .
git commit -m "Task 3.2.1 complete (10/10 tests passing)"
```

### Recovery Process

1. **PM detects task failure/interruption:**
   - Builder timeout (> 4 hours)
   - Builder crash (no heartbeat)
   - Builder explicitly abandons task

2. **PM checks for WIP commits:**
   ```bash
   git log feat-task-3.2.1 --grep="WIP" --oneline
   # Output:
   # def456 WIP: Task 3.2.1 checkpoint 2/4 (implementation 50%, 5/10 tests passing)
   # abc123 WIP: Task 3.2.1 checkpoint 1/4 (tests written, 0 passing)
   ```

3. **PM assesses salvageability:**
   - **≥50% complete:** Create resume task
   - **<50% complete:** Restart from scratch

4. **PM creates recovery work order:**
   ```markdown
   ## Work Order: Resume Task 3.2.1 (from checkpoint 2/4)
   **Assigned to:** Builder-C (new builder)
   **Base branch:** feat-task-3.2.1 @ commit def456
   **Starting state:** Implementation 50%, 5/10 tests passing
   **Remaining work:**
   - Complete implementation (50% remaining)
   - Fix 5 failing tests
   - Add documentation
   **Estimated time:** 2 hours (50% of original 4 hours)
   ```

---

## 3. Notification Failure Handling

**Problem:** Teams webhook down, network timeout, rate limit exceeded → notifications silently fail.

### Retry Strategy

**3 attempts with exponential backoff:**

```bash
#!/bin/bash
# tools/send_notification.sh

MESSAGE="$1"
WEBHOOK_URL=$(yq '.teams.webhook_url' integration/config/saf.integration.yaml)

for attempt in 1 2 3; do
  echo "Notification attempt $attempt/3"

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$MESSAGE\"}" \
    "$WEBHOOK_URL")

  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Notification sent successfully"
    exit 0
  fi

  echo "❌ HTTP $HTTP_CODE, retrying..."
  sleep $((5 * 2 ** (attempt - 1)))  # 5s, 10s, 20s
done

echo "🔴 FAILED after 3 attempts, using fallback"
exit 1
```

### Fallback Chain

```
1. Teams notification (primary)
   ↓ (if fails after 3 retries)
2. Email notification (if configured)
   ↓ (if fails)
3. LogBook entry (guaranteed fallback)
   ↓ (always happens)
4. STATE.md update (always happens)
```

**Implementation:**
```bash
#!/bin/bash
# PM notification workflow

MESSAGE="$1"

# Attempt 1: Teams
if tools/send_notification.sh "$MESSAGE"; then
  echo "Sent via Teams"
else
  # Attempt 2: Email (if configured)
  if [ -n "$EMAIL_RECIPIENT" ]; then
    echo "$MESSAGE" | mail -s "[Framework] Notification" "$EMAIL_RECIPIENT"
  fi

  # Attempt 3: LogBook (guaranteed)
  echo "$(date): $MESSAGE" >> LogBook/pm/notifications_fallback.log

  # Log failure
  echo "{\"timestamp\":\"$(date -Iseconds)\",\"message\":\"$MESSAGE\",\"status\":\"fallback\"}" \
    >> LogBook/pm/notification_failures.json
fi

# Always update STATE.md
echo "Last notification: $(date) - $MESSAGE" >> LogBook/pm/STATE.md
```

### Silent Failure Detection

**PM checks daily:**
```bash
# Count notification failures in last 24 hours
FAILURE_RATE=$(jq '[.[] | select(.timestamp > (now - 86400))] | length' \
  LogBook/pm/notification_failures.json)

if [ "$FAILURE_RATE" -gt 10 ]; then
  echo "🚨 ALERT: ${FAILURE_RATE}% notification failure rate (>10% threshold)"
  # Escalate to human
fi
```

---

## 4. Agent Version Compatibility (PLANNED - NOT YET IMPLEMENTED)

> **STATUS: PLANNED FEATURE**
> This section documents a planned version handshake protocol that is NOT currently active.
> All code examples below are design references for future implementation.
> **Current state:** All agents are assumed to be at the same version. No version checking occurs.

**Problem to solve:** PM v2.0 expects different LogBook format than Builder v1.0 produces.

### Current State (As of 2026-01-05)

- Work orders do NOT contain version fields
- `tools/check_agent_compatibility.py` exists but is NOT wired into any workflow
- No version compatibility checking occurs during work order processing
- All agents are assumed to be the same version (homogeneous deployment)

### Future Implementation Reference

The following specifications are planned for future implementation. They are preserved here as design documentation, NOT as active protocol descriptions.

**Prerequisites before implementation:**
1. Add version fields to `PLANNING/schemas/work_order_schema.yaml`
2. Wire `tools/check_agent_compatibility.py` into work order processing
3. Update PM and Builder agents to include/validate version fields
4. Update this status from "PLANNED" to "ACTIVE"

#### Planned Version Format

**MAJOR.MINOR.PATCH** (SemVer)

- **MAJOR:** Breaking changes (incompatible)
- **MINOR:** Backward compatible additions
- **PATCH:** Bug fixes (fully compatible)

#### Planned Version Handshake Design

**Work order version fields (NOT YET IN SCHEMA):**

```yaml
# PLANNED - These fields do not exist in current work orders
# LogBook/work-orders/task-3.2.md
saf_protocol_version: "2.1.0"
sender_agent:
  name: "PM"
  version: "2.0.3"
receiver_agent:
  name: "Builder"
  version_required: "2.x.x"  # Any 2.x version compatible
```

**Planned validation logic (NOT YET CALLED):**

```python
# tools/check_agent_compatibility.py exists but is not wired into workflows

def check_compatibility(sender_version, receiver_version, required_version):
    """Check if agent versions are compatible."""
    sender_major = int(sender_version.split('.')[0])
    receiver_major = int(receiver_version.split('.')[0])
    required_major = int(required_version.split('.')[0])

    if receiver_major != required_major:
        return False, f"INCOMPATIBLE: Receiver v{receiver_major} cannot handle v{required_major} protocol"

    return True, "Compatible"

# Example
compatible, msg = check_compatibility("2.0.3", "2.1.5", "2.x.x")
# Returns: (True, "Compatible")

compatible, msg = check_compatibility("2.0.3", "1.5.0", "2.x.x")
# Returns: (False, "INCOMPATIBLE: Receiver v1 cannot handle v2 protocol")
```

**Planned rejection template (NOT YET USED):**

```markdown
## Work Order Rejection: Task 3.2
**Reason:** Version incompatibility
**Sender:** PM v2.0.3 (protocol v2.1.0)
**Receiver:** Builder v1.5.0 (supports protocol v1.x.x only)
**Action Required:** Upgrade Builder to v2.x.x OR downgrade PM to v1.x.x
```

---

## 5. Tool Dependency Validation

**Problem:** `tools/traceability_checker.py` doesn't exist, but Critic tries to run it → crash.

### Validation Before Invocation

```bash
#!/bin/bash
# tools/validate_tool.sh - Check tool exists and is executable

TOOL_PATH="$1"

# Check 1: Tool exists
if [ ! -f "$TOOL_PATH" ]; then
  echo "❌ FAIL: Tool not found: $TOOL_PATH"
  exit 1
fi

# Check 2: Tool is executable
if [ ! -x "$TOOL_PATH" ]; then
  echo "❌ FAIL: Tool not executable: $TOOL_PATH"
  exit 1
fi

# Check 3: Dependencies installed (for Python tools)
if [[ "$TOOL_PATH" == *.py ]]; then
  # Extract imports from tool
  IMPORTS=$(grep -E "^import |^from " "$TOOL_PATH" | awk '{print $2}' | cut -d. -f1)

  for module in $IMPORTS; do
    if ! python3 -c "import $module" 2>/dev/null; then
      echo "❌ FAIL: Missing Python dependency: $module"
      exit 1
    fi
  done
fi

echo "✅ PASS: Tool validated: $TOOL_PATH"
exit 0
```

### Graceful Degradation

**Critical tools:** BLOCK if missing
**Nice-to-have tools:** WARN if missing, proceed without

```bash
# Critic evaluation workflow

# Critical tool: Security scanner
if ! tools/validate_tool.sh tools/security_scanner.py; then
  echo "🔴 BLOCKING: Security scanner missing, cannot proceed"
  # Escalate to PM
  exit 1
fi

# Nice-to-have tool: Metrics collector
if ! tools/validate_tool.sh tools/metric_aggregator.py; then
  echo "WARNING: Metric aggregator missing, proceeding without metrics"
  # Continue without metrics
fi
```

---

## 6. Task State Machine

**Valid states and transitions:**

```
┌─────────┐  PM assigns   ┌─────────────┐  Builder    ┌──────────┐
│ Planned │─────────────>│ In Progress │────────────>│ Reviewed │
└─────────┘               └─────────────┘  submits    └──────────┘
                                                            │
                           ┌──────────┐  Critic approves   │
                           │ Approved │<────────────────────┘
                           └──────────┘
                                │
                           ┌─────────┐  PM promotes
                           │ Merged  │
                           └─────────┘
                                │
                           ┌──────────┐  After 2 weeks
                           │ Archived │
                           └──────────┘
```

**State transition rules:**

| Current State | Allowed Next States | Forbidden Transitions |
|---------------|--------------------|-----------------------|
| Planned | In Progress | ❌ Approved (must go through review) |
| In Progress | Reviewed, Planned (if abandoned) | ❌ Merged (must be approved first) |
| Reviewed | Approved, In Progress (if rejected) | ❌ Archived (must be merged first) |
| Approved | Merged | ❌ Planned (cannot unplan approved work) |
| Merged | Archived | ❌ In Progress (immutable after merge) |
| Archived | (terminal state) | ❌ Any (immutable) |

**State file:** `LogBook/tasks/[task-id]/state.json`

```json
{
  "task_id": "3.2.1",
  "current_state": "In Progress",
  "state_history": [
    {"state": "Planned", "timestamp": "2025-12-21T09:00:00Z", "agent": "PM"},
    {"state": "In Progress", "timestamp": "2025-12-21T10:00:00Z", "agent": "Builder-A"}
  ]
}
```

---

## 7. Data Corruption Detection
**Status:** PLANNED - Not yet implemented

**Problem:** LogBook file corrupted (power outage, disk failure) → silent data loss.

**IMPORTANT:** The checksum validation system described below is not yet implemented:
- LogBook files currently use YAML format without checksums
- No LogBook entries contain "checksum" fields
- The JSON format with SHA256 hashes is planned for future implementation
- Current corruption detection relies on git integrity and file system checks

### Checksum Validation (PLANNED)

**Future Design:** Every LogBook write will include SHA256 checksum validation when implemented.

**Example planned format:**

```json
{
  "data": {
    "task_id": "3.2",
    "status": "completed",
    "tests_passed": 10
  },
  "checksum": "sha256:abc123def456...",
  "timestamp": "2025-12-21T10:00:00Z"
}
```

**Example validation logic (planned):**

```bash
#!/bin/bash
# Example checksum validation script (PLANNED - not yet implemented)
# Current production: Use tools/validate_logbook.py for YAML schema validation only

FILE="$1"

# Extract data and checksum
DATA=$(jq -r '.data' "$FILE")
STORED_CHECKSUM=$(jq -r '.checksum' "$FILE" | cut -d: -f2)

# Compute checksum of data
COMPUTED_CHECKSUM=$(echo "$DATA" | sha256sum | awk '{print $1}')

if [ "$STORED_CHECKSUM" = "$COMPUTED_CHECKSUM" ]; then
  echo "✅ PASS: File integrity verified"
  exit 0
else
  echo "❌ FAIL: CORRUPTION DETECTED"
  echo "  Stored:   $STORED_CHECKSUM"
  echo "  Computed: $COMPUTED_CHECKSUM"
  exit 1
fi
```

### Corruption Recovery (PLANNED)

**Current capability:** Git provides primary corruption detection and recovery through version control integrity checks.

**Planned enhanced recovery process (when checksum validation is implemented):**

1. **Alert PM immediately:**
   ```bash
   echo "🚨 CORRUPTION: $FILE" >> LogBook/pm/corruption_events.log
   ```

2. **Restore from Git history:**
   ```bash
   # Find last known good version
   git log --all -- "$FILE"

   # Restore from commit
   git show abc123:LogBook/progress/task-3.2.json > "$FILE"
   ```

3. **Log corruption event:**
   ```json
   {
     "file": "LogBook/progress/task-3.2.json",
     "detected": "2025-12-21T14:00:00Z",
     "recovered_from": "git commit abc123",
     "data_loss": "15 minutes of progress"
   }
   ```

4. **Human investigation required:**
   - Escalate to Level 3 (Approval)
   - Investigate cause (disk failure? bug in tool?)
   - Verify recovered data is correct

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
| 1.0.1 | 2026-01-05 | IF-Lane-Z | Clarified planned vs active status for Section 4 |

---

**End of Edge Cases & Recovery Procedures**
