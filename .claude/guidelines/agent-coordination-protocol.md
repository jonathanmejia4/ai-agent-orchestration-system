# Agent Coordination Protocol
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** MEDIUM - Coordination Guidelines

**Purpose:** Define how agents communicate, hand off work, and resolve conflicts
**Audience:** All agents (PM, Planner, Builder, Critic)
**Authority:** PM specification + Operating Manual

> **SSOT Reference:** The authoritative coordination protocol with YAML work order schemas is at
> `PLANNING/AGENT_COORDINATION_PROTOCOL.md`. This document provides the conceptual overview
> and quick-reference guidance; for formal path specifications and YAML schemas, refer to the SSOT.

---

## 1. Core Agent Loop

The system operates as a coordinated loop of specialized agents:

```
    ┌─────────────────────────────────────────────┐
    │                                             │
    ▼                                             │
[Planner] → [PM] → [Builder] → [Critic] → [PM] ──┘
    ↑         │                            │
    │         └─── Governance Layer ───────┘
    │
    └────────── Spec / Requirements
```

### Agent Roles

**Planner:**
- Decomposes specs into micro-tasks
- Identifies dependencies
- Estimates effort
- Does NOT implement code

**PM (Project Manager):**
- Control tower / coordinator
- Enforces gates and governance
- Maintains LogBook audit trail
- Issues work orders
- Does NOT implement code

**Builder:**
- Implements product code
- Writes tests
- Executes assigned micro-tasks
- Does NOT modify governance or CI

**Critic:**
- Quality guardian
- Reviews across 7 dimensions
- Approves or blocks work
- Does NOT implement fixes

---

## 2. Communication Protocol

### Work Orders (PM → Planner/Builder)

**Delivery Mechanism:** PM writes work orders to `/LogBook/work-orders/WO-*.yaml`. Builder autonomously polls this directory every 2 minutes for new assignments (see Builder.md "Work Order Polling"). Direct invocation (`@Builder`) is also supported for immediate work.

**Format:**
```markdown
## Work Order: [Task ID]
**Assigned to:** [Agent Name]
**Issued by:** PM
**Date:** [ISO timestamp]

### Objective
[Clear, single-sentence goal]

### Input Artifacts
- Path: `/path/to/input1.md`
- Path: `/path/to/spec.md`

### Expected Outputs
- [ ] `/path/to/output1.py`
- [ ] Tests passing for output1
- [ ] LogBook entry

### Acceptance Criteria
1. [Testable criterion 1]
2. [Testable criterion 2]

### Prohibited Actions
- Do NOT modify `/protected/path/**`
- Do NOT expand scope beyond stated objective

### Deadline
[Realistic timeframe]

### Dependencies
- Requires completion of: [Task IDs]

---
**PM Signature:** [Agent ID + timestamp]
```

### Progress Updates (Agent → PM)

**Format:**
```markdown
## Progress Update: [Task ID]
**Agent:** [Name]
**Status:** [In Progress | Blocked | Completed]
**Date:** [ISO timestamp]

### Work Completed
- [Concrete deliverable 1]
- [Concrete deliverable 2]

### Artifacts Created
- `/path/to/file1.py`
- `/path/to/test1.py`

### Blockers (if any)
- [Specific blocker with context]

### Next Steps
- [Immediate next action]

### Evidence
- CI run: [link or ID]
- Test results: [path to results]
```

### Review Requests (Builder → Critic)

**Format:**
```markdown
## Review Request: [Task ID]
**Submitted by:** Builder
**Date:** [ISO timestamp]

### Artifacts for Review
- Implementation: `/path/to/code.py`
- Tests: `/path/to/test.py`
- Documentation: `/path/to/docs.md`

### Acceptance Criteria (from work order)
[Copy from original work order]

### Self-Assessment
- [ ] Code meets acceptance criteria
- [ ] Tests pass locally
- [ ] No security vulnerabilities
- [ ] Documentation complete

### Test Results
[Output or link to test run]

### Request
Please evaluate across 7 dimensions and provide verdict.
```

### Critic Verdict (Critic → PM)

**Orchestrator outputs TWO files after task evaluation:**

#### File 1: Structured Verdict (REQUIRED - Machine-Readable)

**Location:** `/LogBook/critic/verdicts/VER-<task-id>.yaml`
**Purpose:** Machine-readable verdict for PM automation
**Schema:** `/PLANNING/schemas/critic_verdict_schema.yaml`
**Consumer:** Project-Manager (programmatic decision-making)
**PM Action:** **PM reads THIS file ONLY** to make promotion decisions

**Format:**
```yaml
critic_verdict:
  verdict_id: VER-20251223-001
  task_id: task-1.1-init-repo
  evaluated_at: "2025-12-23T14:30:00Z"
  evaluated_by: Critic-Orchestrator

  final_verdict: APPROVED  # APPROVED | APPROVED_WITH_CONDITIONS | REJECTED
  overall_score: 0.94

  dimensions:
    - dimension: 1
      name: "Dependency Integrity"
      verdict: PASS
      score: 95
    - dimension: 2
      name: "Effort Accuracy"
      verdict: PASS
      score: 90
    # ... (all 7 dimensions)

  conditions: []  # If APPROVED_WITH_CONDITIONS
  required_fixes: []  # If REJECTED
```

#### Verdict Format: YAML Only (Standardized)

**Decision:** As of 2025-12-30, verdict format is **YAML ONLY** (Issue B5 resolved).

**Location:** `/LogBook/critic/verdicts/VER-<task-id>.yaml`
**Purpose:** Machine-readable verdict for PM automation and human review
**Consumers:** PM (programmatic), Human operators (readable YAML)
**Note:** Markdown format deprecated - YAML serves both machine and human needs

**IMPORTANT - PM Workflow:**
1. PM invokes: `@Critic-Orchestrator Evaluate task <task-id>`
2. Orchestrator writes YAML verdict to `/LogBook/critic/verdicts/VER-<task-id>.yaml`
3. **PM reads `/LogBook/critic/verdicts/VER-<task-id>.yaml`**
4. PM makes promotion decision based on `final_verdict` field

**YAML is Authoritative:**
- YAML file is the single source of truth
- Schema-driven, machine-readable, easier to validate
- PM automation depends on YAML structure
- Human-readable comments allowed in YAML for context

---

## 3. Handoff Protocol

### When Builder completes work:

1. **Builder actions:**
   - Commit all changes
   - Run local tests
   - Write LogBook entry
   - Submit review request to Critic (via LogBook)

2. **PM monitors:**
   - Verifies review request is complete
   - Routes to Critic
   - Updates task status to "Under Review"

3. **Critic reviews:**
   - Evaluates 7 dimensions
   - Writes verdict to LogBook
   - Returns control to PM

4. **PM resolves:**
   - If ✅ Approved: Mark task complete, proceed to next
   - If 🟨 Conditional: Route fixes back to Builder
   - If 🟥 Blocked: Investigate and potentially escalate
   - If ❌ Rejected: Archive to Bad, start remediation

---

## 4. Conflict Resolution

### Priority Order (Higher overrides lower)

1. **Spec text** (authoritative requirements)
2. **CI results** (automated verification)
3. **Critic findings** (quality assessment)
4. **Planner intent** (design decisions)
5. **Human arbiter** (final escalation)

### When Conflicts Arise

**Example: Planner vs Critic**
- Planner estimates 2 hours
- Critic finds actual effort was 6 hours
- **Resolution:** Critic's actual measurement overrides Planner estimate
- **Learning:** Update Golden Task patterns with accurate estimates

**Example: Builder vs Spec**
- Builder implements additional "helpful" features beyond spec
- Spec is authoritative
- **Resolution:** Revert non-spec features, focus on spec compliance
- **Learning:** Archive as Bad Task (scope creep)

### Escalation Triggers

PM must escalate to human when:
- Same task blocked ≥ 2 full cycles
- Planner/Critic signals unresolvable conflict
- Security, safety, or irreversible risk detected
- CI red persists beyond threshold
- Spec is ambiguous or silent on critical decision

---

## 5. State Synchronization

### Single Source of Truth

**Repository state is authoritative.**

All agents must:
- Read current repo state before each action
- Write results immediately after completion
- Never rely on cached or chat memory
- Verify changes are committed before handoff

### PM State File

**Location:** `/LogBook/pm/STATE.md`

**Purpose:** PM's persistent working memory

**Required sections:**
- Active branches and categories
- Current task queue (priorities)
- Blockers and escalations
- Scheduled governance actions
- Agent status (AI/Teams)

**Update frequency:**
- First read: Beginning of work session
- Last write: End of work session
- Interim: After any significant decision

---

## 6. Parallel Work Coordination

### When Multiple Tasks Can Run in Parallel

**PM determines parallelizability:**

**Independent tasks (CAN run parallel):**
```
Task A: Create User model
Task B: Create Product model
→ No shared dependencies, parallel OK
```

**Dependent tasks (MUST run sequential):**
```
Task A: Create User model
Task B: Add authentication to User model
→ B depends on A, sequential required
```

### Coordination Mechanism

1. PM maintains dependency graph in `/PLANNING/dependencies/`
2. Assigns only independent tasks simultaneously
3. Monitors for integration conflicts
4. Resolves merge conflicts via designated owner

---

## 7. Error Handling & Recovery

### When Agent Encounters Error

**Immediate actions:**
1. Stop current work
2. Document error in LogBook
3. Assess severity:
   - **Low:** Retry once, then notify PM
   - **Medium:** Notify PM immediately
   - **High:** Escalate to human

**Error report format:**
```markdown
## Error Report: [Task ID]
**Agent:** [Name]
**Severity:** Low | Medium | High
**Date:** [ISO timestamp]

### Error Description
[What happened]

### Context
- Task: [What was being attempted]
- Artifact: [File or path involved]
- State: [Repo state at time of error]

### Impact
[What is blocked or broken]

### Attempted Recovery
[What was tried]

### Recommendation
[Suggested next action]
```

### PM Recovery Actions

**Based on severity:**
- **Low:** Assign to different agent or retry with clarification
- **Medium:** Review task decomposition, potentially break down further
- **High:** Pause all related work, escalate to human

---

## 7.5 Timeout & Retry Strategy

**Problem:** Without timeouts, agents can block forever waiting for responses. Without retries, transient failures cause permanent failures.

### Timeout Matrix

| Operation | Timeout | Retry Strategy | Give Up After | On Timeout Action |
|-----------|---------|----------------|---------------|-------------------|
| **Critic review (per task)** | 2 hours | N/A (escalate) | 1 attempt | Escalate to human (Level 3) |
| **PM work order creation** | 30 min | 2 retries with clarification | 3 attempts | Escalate to human (Level 2) |
| **Builder implementation** | 4 hours | N/A (task too large) | 1 task | Escalate to PM for re-decomposition |
| **Planner decomposition** | 30 min | 1 retry with simplified spec | 2 attempts | Escalate to human (Level 2) |
| **Tool execution** | 10 min | 3 retries, exponential backoff | 3 attempts | Escalate to PM (tool failure) |
| **LogBook write** | 30 sec | 5 retries, 1s delay | 5 attempts | Escalate to PM (data loss risk) |
| **Git operations** | 2 min | 3 retries (network issues) | 3 attempts | Escalate to PM (repo access issue) |
| **CI pipeline run** | 45 min | 1 retry (flaky tests allowed) | 2 attempts | Escalate to PM (pipeline broken) |
| **Dependency resolution** | 5 min | 1 retry with cache clear | 2 attempts | Escalate to human (circular deps) |
| **PM governance cycle** | 10 min | N/A (PM must complete) | 1 attempt | Escalate to human (PM overload) |
| **Agent waiting for work order** | 24 hours | Poll every hour | 24 polls | Agent goes idle, notifies PM |
| **PM waiting for Critic verdict** | 4 hours | Ping Critic after 2 hours | 1 ping | Escalate to human (Critic stuck) |
| **Builder waiting for tests** | 10 min | 1 retry (tests may be flaky) | 2 attempts | Escalate to PM (tests failing) |

**Note on Polling Frequency Modes:**
- **Active Polling (Normal Mode):** Builder polls for work orders every 2 minutes when actively seeking work
- **Idle Polling (Timeout Mode):** Agents poll every 1 hour after initial 24-hour timeout period
- **Rationale:** High frequency (2 min) when expecting work; low frequency (1 hour) during extended idle to reduce resource usage

See Builder.md for mode-specific polling details.

---

### Retry Implementation Patterns

#### Pattern 1: Exponential Backoff (Network/Transient Failures)

**Use for:** Git operations, tool execution, external API calls

**Implementation:**
```bash
#!/bin/bash
# Exponential backoff retry

OPERATION="$1"
MAX_RETRIES=3
BACKOFF_BASE=2

for attempt in $(seq 1 $MAX_RETRIES); do
  echo "Attempt $attempt/$MAX_RETRIES: $OPERATION"

  if eval "$OPERATION"; then
    echo "SUCCESS"
    exit 0
  fi

  if [ $attempt -lt $MAX_RETRIES ]; then
    DELAY=$((BACKOFF_BASE ** attempt))
    echo "FAILED, retrying in ${DELAY}s..."
    sleep "$DELAY"
  fi
done

echo "FAILED after $MAX_RETRIES attempts"
exit 1
```

**Usage:**
```bash
tools/retry.sh "git push origin main"
# Attempt 1: immediate
# Attempt 2: 2 second delay
# Attempt 3: 4 second delay
```

---

#### Pattern 2: Immediate Retry with Clarification (Logic Errors)

**Use for:** PM work order creation, Planner decomposition

**Implementation:**
```markdown
## Retry with Clarification

**Attempt 1:** Execute with original inputs
**On Failure:** Analyze error, clarify ambiguous spec, retry with enhanced spec
**Attempt 2:** Execute with clarified inputs
**On Failure:** Escalate to human

**Example:**
Planner attempts task decomposition:
- Attempt 1: Fails (spec too vague: "improve performance")
- Clarification: Request specific metric targets ("reduce latency to <100ms")
- Attempt 2: Succeeds with clarified spec
```

---

#### Pattern 3: Timeout with Progress Check (Long Operations)

**Use for:** Critic review, Builder implementation, CI pipeline

**Implementation:**
```bash
#!/bin/bash
# Timeout with progress check

TIMEOUT_SECONDS=7200  # 2 hours
CHECK_INTERVAL=600     # 10 minutes
OPERATION_PID=$1

START_TIME=$(date +%s)

while true; do
  ELAPSED=$(($(date +%s) - START_TIME))

  # Check if operation still running
  if ! kill -0 "$OPERATION_PID" 2>/dev/null; then
    echo "Operation completed"
    exit 0
  fi

  # Check timeout
  if [ "$ELAPSED" -ge "$TIMEOUT_SECONDS" ]; then
    echo "TIMEOUT after ${ELAPSED}s"
    kill -TERM "$OPERATION_PID"  # Graceful termination
    sleep 10
    kill -KILL "$OPERATION_PID" 2>/dev/null  # Force kill if still running
    exit 1
  fi

  # Progress check
  if [ $((ELAPSED % CHECK_INTERVAL)) -eq 0 ]; then
    echo "Still running... elapsed: ${ELAPSED}s / ${TIMEOUT_SECONDS}s"
  fi

  sleep 10
done
```

---

### Timeout Escalation Workflow

**When operation exceeds timeout:**

1. **Agent detects timeout:**
   - Stop current operation (gracefully if possible)
   - Capture current state (logs, partial outputs)
   - Document timeout in LogBook

2. **Agent reports to PM:**
   ```markdown
   ## Timeout Report: [Task ID]
   **Agent:** Critic
   **Operation:** Task 3.2 evaluation
   **Timeout:** 2 hours (exceeded)
   **Elapsed:** 2 hours 15 minutes
   **State:** Completed 5/7 dimensions, stuck on Dimension 6 (Security)
   **Recommendation:** Human review of security policy for this task type
   ```

3. **PM evaluates timeout:**
   - Is this the first occurrence? → Retry once
   - Is this recurring (same task/agent)? → Escalate to human
   - Is partial progress salvageable? → Create continuation task

4. **PM action:**
   - **Salvageable:** "Resume Critic eval for task 3.2 starting at Dimension 6"
   - **Not salvageable:** "Human review required: Critic timeout on security dimension"

---

### Agent Polling Strategy (Avoid Busy-Waiting)

**Problem:** Agent waiting indefinitely for work order wastes resources.

**Solution:** Exponential backoff polling with maximum wait time.

**Implementation:**
```bash
#!/bin/bash
# Agent poll for work with exponential backoff

MIN_INTERVAL=60      # 1 minute
MAX_INTERVAL=3600    # 1 hour (don't check more than hourly)
MAX_WAIT_TIME=86400  # 24 hours (give up after 1 day)

INTERVAL=$MIN_INTERVAL
TOTAL_WAIT=0

while true; do
  # Check for work
  if [ -f "LogBook/work-orders/WO-assigned-to-me.yaml" ]; then
    echo "Work order found!"
    exit 0
  fi

  # Check if max wait time exceeded
  TOTAL_WAIT=$((TOTAL_WAIT + INTERVAL))
  if [ "$TOTAL_WAIT" -ge "$MAX_WAIT_TIME" ]; then
    echo "No work after 24 hours, going idle"
    echo "$(date): Agent went idle (no work for 24h)" >> LogBook/pm/idle-agents.log
    exit 1
  fi

  # Wait and increase interval
  echo "No work, waiting ${INTERVAL}s..."
  sleep "$INTERVAL"

  # Exponential backoff (cap at MAX_INTERVAL)
  INTERVAL=$((INTERVAL * 2))
  if [ "$INTERVAL" -gt "$MAX_INTERVAL" ]; then
    INTERVAL=$MAX_INTERVAL
  fi
done
```

**Polling schedule:**
- 0-1 min: Check immediately
- 1-3 min: Check every 1 min
- 3-7 min: Check every 2 min
- 7-15 min: Check every 4 min
- 15-31 min: Check every 8 min
- 31 min - 24 hours: Check every 1 hour

---

### Deadlock Detection

**Problem:** Agent A waiting for Agent B, Agent B waiting for Agent A → deadlock.

**Prevention:**
- No circular dependencies in work orders
- PM maintains dependency graph
- Agents never wait for each other directly (only via PM)

**Detection:**
If PM detects no progress for > 4 hours across all agents:
1. Check for circular waits in LogBook/progress/
2. Identify deadlock participants
3. Break deadlock by canceling lowest-priority task
4. Escalate to human

---

### Timeout Metrics

**Track in `LogBook/metrics/timeouts.json`:**
```json
{
  "timeouts": [
    {
      "agent": "Critic",
      "operation": "task-3.2-evaluation",
      "timeout_limit": 7200,
      "actual_duration": 8100,
      "timestamp": "2025-12-21T14:30:00Z",
      "resolved": "escalated_to_human"
    }
  ],
  "timeout_rate": 0.02,  // 2% of operations timeout
  "most_common_timeout": "critic_review"
}
```

**Goal:** Timeout rate < 5%

**PM reviews monthly:** Identify patterns, adjust timeouts if needed.

---

### Timeout Anti-Patterns

❌ **Infinite wait (no timeout)**
   - Always set explicit timeout

❌ **Too short timeout (false positives)**
   - Set timeout at 2x expected duration

❌ **No retry on transient failures**
   - Network glitches are common, retry 3x

❌ **Blocking wait (busy-loop)**
   - Use exponential backoff polling

❌ **Silent timeout (no logging)**
   - Always log timeout events to LogBook

---

## 8. Asynchronous Coordination

### LogBook as Message Bus

Agents may not interact in real-time. LogBook serves as asynchronous message bus.

**Pattern:**
1. Agent A writes work order to `/LogBook/work-orders/WO-[task-id].yaml`
2. Agent B polls `/LogBook/work-orders/` for assigned tasks
3. Agent B writes progress to `/LogBook/progress/[task-id].yaml`
4. Agent A reads progress updates on next cycle

**Polling frequency:**
- PM: Every governance cycle (configurable)
- Builder: When available for new work
- Critic: When review queue not empty

---

## 8.5 LogBook Concurrent Write Protocol

**Problem:** Multiple agents writing to LogBook simultaneously can cause race conditions and data loss.

**Scenario:**
```
Builder A (task 1.1): Writes LogBook/metrics/current.json at 10:00:00.500
Builder B (task 1.2): Writes LogBook/metrics/current.json at 10:00:00.501
Result: Builder A's data LOST (clobbered by Builder B)
```

### Safe Write Patterns

#### Pattern 1: Agent-Specific Files (Preferred)

**Rule:** Each agent writes to its own file, no sharing.

**Good:**
```
LogBook/progress/task-1.1.md  ← Builder A only
LogBook/progress/task-1.2.md  ← Builder B only
LogBook/critic/task-1.1/review.md  ← Critic only
```

**Bad:**
```
LogBook/progress/all-tasks.md  ← Multiple writers (race condition!)
LogBook/metrics/current.json  ← Multiple writers (race condition!)
```

---

#### Pattern 2: Atomic Write-Then-Rename (Required for Shared Files)

**Rule:** For shared files (e.g., `metrics/current.json`), use atomic operations.

**WRONG (race condition):**
```bash
# Direct write - NOT SAFE
echo "$data" > LogBook/metrics/current.json
```

**CORRECT (atomic):**
```bash
# Write to temp file, then atomic rename
TEMP_FILE="LogBook/metrics/current.json.tmp.$$"
echo "$data" > "$TEMP_FILE"
mv "$TEMP_FILE" "LogBook/metrics/current.json"  # Atomic on POSIX filesystems
```

**Why safe:** `mv` is atomic within the same filesystem. Last writer wins, but no partial/corrupt writes.

---

#### Pattern 3: Read-Merge-Write for JSON Arrays (Required for Append Operations)

**Rule:** When multiple agents append to same JSON file, use read-merge-write with retry.

**Example:** Multiple builders adding metrics to `LogBook/metrics/history.json`

**CORRECT implementation:**
```bash
#!/bin/bash
# tools/logbook_append.sh - Append to JSON array with retry

FILE="$1"
NEW_ENTRY="$2"
MAX_RETRIES=5

for attempt in $(seq 1 $MAX_RETRIES); do
  # 1. Read current file (or initialize empty array)
  if [ -f "$FILE" ]; then
    CURRENT=$(cat "$FILE")
  else
    CURRENT="[]"
  fi

  # 2. Merge new entry
  MERGED=$(echo "$CURRENT" | jq --argjson entry "$NEW_ENTRY" '. + [$entry]')

  # 3. Atomic write
  TEMP_FILE="$FILE.tmp.$$"
  echo "$MERGED" > "$TEMP_FILE"

  # 4. Attempt atomic rename
  if mv "$TEMP_FILE" "$FILE" 2>/dev/null; then
    echo "SUCCESS: Appended to $FILE"
    exit 0
  else
    echo "RETRY $attempt/$MAX_RETRIES: Another agent modified $FILE"
    sleep 0.$((RANDOM % 10))  # Random backoff 0-0.9 seconds
  fi
done

echo "FAILED: Could not append after $MAX_RETRIES attempts"
exit 1
```

**Usage:**
```bash
NEW_METRIC='{"task":"1.1","time":3.5,"status":"completed"}'
tools/logbook_append.sh LogBook/metrics/history.json "$NEW_METRIC"
```

---

### File Locking (Alternative for High Contention)

**When to use:** If file has > 10 concurrent writers, use explicit file locking.

**Implementation (flock):**
```bash
#!/bin/bash
# Write with file lock

(
  flock -x 200  # Exclusive lock on file descriptor 200

  # Critical section - only one process at a time
  CURRENT=$(cat LogBook/metrics/current.json)
  MERGED=$(echo "$CURRENT" | jq --argjson entry "$NEW_ENTRY" '. + [$entry]')
  echo "$MERGED" > LogBook/metrics/current.json

) 200>/var/lock/logbook_metrics.lock  # Lock file path
```

**Lock timeout:**
```bash
flock -x -w 30 200  # Wait max 30 seconds for lock, then fail
```

---

### Designated Writer Pattern (Best for High-Frequency Writes)

**Rule:** For files with very high write frequency (> 100/minute), designate a single writer.

**Example:** `LogBook/metrics/current.json` (updated by many tasks)

**Solution:** PM is the **only** writer to `current.json`. Agents send updates to PM via message queue.

**Workflow:**
```
Builder A → Writes to LogBook/queue/metrics-builder-a.json
Builder B → Writes to LogBook/queue/metrics-builder-b.json
PM → Reads all queues, merges, writes to LogBook/metrics/current.json (single writer)
```

**Advantage:** No contention, no retry loops, guaranteed consistency.

---

### Agent-Specific Write Guidelines

**PM:**
- Writes to: `LogBook/pm/**`, `LogBook/metrics/**`, `LogBook/daily-summary/**`
- Owns: `STATE.md`, `escalations/**`, `rollback/**`
- Uses: Atomic write-then-rename for all shared files

**Builder:**
- Writes to: `LogBook/progress/task-[id].md` (agent-specific, no contention)
- Appends to: `LogBook/metrics/history.json` (use `logbook_append.sh`)
- **Never** directly writes to PM-owned files

**Critic:**
- Writes to: `LogBook/critic/[task-id]/**` (agent-specific, no contention)
- **Never** modifies Builder or PM files

**Planner:**
- Writes to: `PLANNING/dependencies/**`, `PLANNING/tasks/**`
- Appends to: `LogBook/metrics/history.json` (use `logbook_append.sh`)

---

### Concurrency Testing

**Before deploying multi-agent system:**

```bash
# Test concurrent writes (simulate 10 builders writing simultaneously)
for i in {1..10}; do
  (
    METRIC='{"task":"'$i'","status":"test"}'
    tools/logbook_append.sh LogBook/test.json "$METRIC"
  ) &
done
wait

# Verify no data loss
EXPECTED_COUNT=10
ACTUAL_COUNT=$(jq 'length' LogBook/test.json)

if [ "$ACTUAL_COUNT" -eq "$EXPECTED_COUNT" ]; then
  echo "✅ PASS: All 10 writes succeeded"
else
  echo "❌ FAIL: Expected $EXPECTED_COUNT, got $ACTUAL_COUNT (data loss!)"
fi
```

---

### Race Condition Detection

**Symptoms of race conditions:**
- JSON parse errors ("unexpected token")
- Missing log entries
- Truncated files
- Inconsistent metrics counts

**Debugging:**
```bash
# Check for truncated/corrupt JSON files
find LogBook -name "*.json" -exec jq empty {} \; 2>&1 | grep -i error

# Check for partial writes (incomplete lines)
find LogBook -name "*.md" -exec tail -1 {} \; | grep -v "^$" | wc -l

# Monitor file modification times (detect rapid rewrites)
watch -n 0.1 'stat -c "%Y %n" LogBook/metrics/current.json'
```

---

### Mandatory Write Protocol Summary

**All agents MUST:**
1. **Use agent-specific files** when possible (preferred)
2. **Use atomic write-then-rename** for shared files
3. **Use `logbook_append.sh`** for appending to JSON arrays
4. **Never** use direct `echo > file` for shared files
5. **Retry on write conflicts** (max 5 attempts with backoff)
6. **Escalate to PM** if write fails after retries

**PM MUST:**
- Audit LogBook for race condition symptoms monthly
- Run concurrency tests before increasing parallel agent count
- Monitor for missing log entries or data loss

**Violations:** Any agent that violates write protocol causes **data loss** → immediate escalation to human.

---

## 9. Coordination Anti-Patterns

### DON'T

❌ **Assume other agents' intent**
   - Always read their artifacts explicitly

❌ **Modify another agent's work without permission**
   - Request via PM work order

❌ **Communicate critical info via chat only**
   - Write to LogBook

❌ **Skip handoff protocols "to save time"**
   - Leads to state desync and errors

❌ **Bypass PM coordination**
   - Direct agent-to-agent is forbidden

❌ **Invent your own protocol**
   - Follow established patterns

---

## 10. Inter-Agent Communication Protocols

**Purpose:** Define message formats and handoff mechanisms for agent-to-agent communication

### 10.1 Communication Paradigm

**The system uses file-based handoffs via Claude Code agent invocation.**

**How agents communicate:**
1. **PM invokes Builder:** PM writes work order to chat, invokes `@Builder` via Claude Code
2. **Builder executes:** Builder reads work order, executes task, writes completion status to LogBook
3. **PM invokes Critic:** PM writes review request, invokes `@Critic-Orchestrator`
4. **Critic evaluates:** Critic reads task artifacts, writes verdict to LogBook
5. **PM reads verdict:** PM reads LogBook verdict, takes action (promote/reject/rework)

**Not used in the framework:**
- ❌ Direct API calls between agents (agents don't run as services)
- ❌ Message queues or pub/sub (agents are invoked on-demand)
- ❌ Shared memory or global state (LogBook is the shared state)

### 10.2 PM → Builder Work Order Protocol

**Schema:** `/PLANNING/schemas/work_order_schema.yaml`

**Handoff Mechanism:**
1. PM writes work order in markdown format in chat
2. PM invokes Builder: `@Builder`
3. Builder validates work order against schema
4. Builder executes task, updates LogBook with progress
5. Builder signals completion via LogBook entry

**Work Order Fields (see schema for full specification):**
- **id:** Unique work order ID (WO-YYYYMMDD-NNN)
- **task_id:** UUID linking to task specification
- **task_type:** implement_task | review_task | audit_plan
- **inputs:** List of input files/specs required
- **expected_outputs:** List of artifacts to produce with acceptance criteria
- **prohibited_actions:** List of actions Builder must not perform
- **time_box:** ISO 8601 duration (e.g., "PT4H")

**Example Invocation:**
```markdown
@Builder

**Work Order:** WO-20251222-001
**Task ID:** 550e8400-e29b-41d4-a716-446655440000
**Spec:** /PLANNING/specs/user-auth-service.md
**Task:** Implement user authentication service with JWT tokens
**Time Box:** PT4H
**Acceptance Criteria:**
- Implement authenticate(), refresh_token(), validate_token() methods
- 10+ unit tests with >90% code coverage
- Valid .task/task.yaml manifest
```

### 10.3 Builder → PM Completion Protocol

**Handoff Mechanism:**
1. Builder completes work on alt branch
2. Builder writes completion entry to `/LogBook/<category>/alt/<branch>/INDEX.md`
3. Builder notifies PM: "Task completed, ready for review"
4. PM reads LogBook entry, initiates Critic review

**Completion Entry Fields:**
- **status:** COMPLETE | BLOCKED | ESCALATED
- **branch:** Alt branch name (e.g., alt-user-auth-v1)
- **files_changed:** Count of modified files
- **tests_added:** Count of new test cases
- **actual_time:** ISO 8601 duration of actual work time
- **blockers:** List of blockers (if status=BLOCKED)

### 10.4 PM → Critic Review Request Protocol

**Schema:** `/PLANNING/schemas/review_request_schema.yaml`

**Handoff Mechanism:**
1. PM writes review request in chat
2. PM invokes Critic: `@Critic-Orchestrator`
3. Critic validates review request against schema
4. Critic orchestrates 7 dimension specialists
5. Critic writes verdict to LogBook

**Review Request Fields:**
- **review_id:** Unique review ID (REV-YYYYMMDD-NNN)
- **task_id:** UUID of task to review
- **branch_name:** Alt branch containing task implementation
- **spec_path:** Path to original task specification
- **manifest_path:** Path to .task/task.yaml
- **review_scope:** List of dimensions to evaluate (or "all" for full review)

**Example Invocation:**
```markdown
@Critic-Orchestrator

**Review Request:** REV-20251222-001
**Task ID:** 550e8400-e29b-41d4-a716-446655440000
**Branch:** alt-user-auth-v1
**Spec:** /PLANNING/specs/user-auth-service.md
**Manifest:** /alt-user-auth-v1/.task/task.yaml
**Scope:** all dimensions
```

### 10.5 Critic → PM Verdict Protocol

**Schema:** `/PLANNING/schemas/critic_verdict_schema.yaml`
**Format:** YAML only (standardized per Issue B5 resolution)

**Handoff Mechanism:**
1. Orchestrator coordinates all 7 dimension critics
2. Orchestrator writes verdict to `/LogBook/critic/verdicts/VER-<task-id>.yaml`
3. Orchestrator returns summary verdict to PM
4. PM reads YAML verdict for detailed scoring and rationale

**Verdict Fields:**
- **verdict_id:** Unique verdict ID (VER-YYYYMMDD-NNN)
- **task_id:** ID of reviewed task
- **final_verdict:** APPROVED | APPROVED_WITH_CONDITIONS | REJECTED
- **overall_score:** Weighted score (0.0 - 1.0, threshold: 0.9)
- **dimension_results:** Array of dimension → verdict + score + feedback
- **conditions:** List of conditions (if APPROVED_WITH_CONDITIONS)
- **required_fixes:** List of fixes (if REJECTED)
- **recommendation:** promote_to_main | rework_required | escalate_to_human

**Example Verdict Entry (`/LogBook/critic/verdicts/VER-task-2.3.yaml`):**
```yaml
# Critic Verdict: VER-20251222-001
verdict_id: "VER-20251222-001"
task_id: "task-2.3-daily-digest"
timestamp: "2025-12-22T14:30:00Z"
final_verdict: "APPROVED_WITH_CONDITIONS"
overall_score: 0.92

dimension_results:
  - dimension: "spec_fit"
    verdict: "pass"
    score: 0.98
    feedback: "All requirements from spec implemented"
  - dimension: "verification"
    verdict: "pass"
    score: 0.94
    feedback: "12 tests, 94% coverage"
  - dimension: "dependency_integrity"
    verdict: "pass"
    score: 1.0
    feedback: "No circular dependencies"
  - dimension: "effort_accuracy"
    verdict: "fail"
    score: 0.72
    feedback: "Actual 5.5h vs estimate 4h (38% over)"
  - dimension: "execution_ready"
    verdict: "pass"
    score: 1.0
    feedback: "All acceptance criteria met"
  - dimension: "security_policy"
    verdict: "pass"
    score: 1.0
    feedback: "No security violations"
  - dimension: "acl"
    verdict: "pass"
    score: 0.95
    feedback: "Anti-corruption layer properly implemented"

conditions:
  - "Update time estimates for similar tasks to account for 38% overrun"
  - "Add API documentation for refresh_token() method"

recommendation: "promote_to_main"
```

## Recommendation

**Promote to main** after addressing documentation condition.
```

### 10.6 Error Handling in Communication

**If work order is malformed:**
- Builder validates against `/PLANNING/schemas/work_order_schema.yaml`
- Builder rejects with error message: "Malformed work order: missing required field `time_box`"
- Builder does NOT execute task
- PM must re-issue corrected work order

**If review request is incomplete:**
- Critic validates against `/PLANNING/schemas/review_request_schema.yaml`
- Critic returns error: "Review request invalid: task_id not found"
- PM must provide correct task_id

**If Critic verdict conflicts:**
- PM reads LogBook verdict for full rationale
- If verdict unclear, PM escalates to human for decision
- PM does not override Critic verdict without human approval

### 10.7 Agent Invocation via Claude Code

**Agents are invoked via Claude Code's @ mention feature:**

- `@Project-Manager` - Invoke PM
- `@Planner` - Invoke Planner for task decomposition
- `@Builder` - Invoke Builder
- `@Critic-Orchestrator` - Invoke Critic Orchestrator
- `@Critic-PlanAuditor` - Invoke Plan Auditor
- `@Critic-SpecFit` - Invoke SpecFit dimension specialist (rarely invoked directly)
- `@Critic-Verification` - Invoke Verification specialist (rarely invoked directly)
- `@Critic-Dependencies` - Invoke Dependencies specialist (rarely invoked directly)
- `@Critic-Effort` - Invoke Effort specialist (rarely invoked directly)
- `@Critic-ExecutionReady` - Invoke ExecutionReady specialist (rarely invoked directly)
- `@Critic-SecurityPolicy` - Invoke SecurityPolicy specialist (rarely invoked directly)
- `@Critic-ACL` - Invoke ACL specialist (rarely invoked directly)

**Invocation Rules:**
- PM typically invokes Builder, Critic-Orchestrator, and PlanAuditor
- Critic-Orchestrator invokes the 7 dimension specialists internally
- PlanAuditor is invoked for plan review before work order creation
- Direct invocation of dimension specialists is rare (used for debugging)
- User can invoke any agent directly for testing/debugging

---

## 13. Success Criteria

**Well-coordinated system:**
- All agent actions traceable via LogBook
- No silent handoffs or assumptions
- Conflicts resolved via documented priority order
- Parallel work executes without merge conflicts
- Errors handled gracefully with recovery paths
- Human interventions are rare and well-justified

**Metrics:**
- Handoff completion rate
- Average time in "Under Review" state
- Conflict frequency (target: rare)
- Escalation rate (target: <5%)
- State synchronization errors (target: 0)

---

## 11. Critic Multi-Agent Architecture

**Purpose:** Document the framework's 10-agent Critic system and invocation protocols (7 dimension specialists + Orchestrator + PlanAuditor + FixVerifier)

### 11.1 Why 7 Dimension Specialists vs 1 Monolithic Critic?

**Problem with Monolithic Critic:**
- Single agent responsible for 7 orthogonal quality dimensions becomes overwhelmed
- Quality degradation: superficial reviews when task complexity is high
- No specialization: agent lacks deep expertise in each dimension (security, dependencies, testing, etc.)
- Long context: reviewing all 7 dimensions in single prompt exceeds token limits for large tasks

**Solution: Dimension Decomposition**
- **1 Orchestrator** coordinates review across 7 specialist agents
- **7 Specialists** each focus on one quality dimension with domain-specific expertise
- Sequential execution: specialists are invoked in sequence for deterministic evaluation
- Reduced cognitive load per agent: each specialist has focused scope

**Analogy:** Like surgical team (anesthesiologist, surgeon, nurse) vs solo generalist

### 11.2 Critic Agent Roles

**11.2.1 Critic-PlanAuditor**
- **When:** Reviews planning artifacts (decomposition plans, task specs) before Builder executes
- **Invoked by:** PM after Planner creates decomposition plan
- **Responsibilities:**
  - Validate task decomposition granularity (not too large, not too small)
  - Check dependency ordering (no circular deps, correct sequencing)
  - Verify time estimates are realistic (based on historical data)
  - Ensure all specifications are actionable (Builder can execute)
- **Output:** APPROVED / NEEDS_REVISION with specific feedback
- **Blocks:** Builder cannot start until PlanAuditor approves plan

**11.2.2 Critic-Orchestrator**
- **When:** Reviews completed task implementations before promotion to main
- **Invoked by:** PM after Builder completes task on alt branch
- **Responsibilities:**
  1. Invokes all 7 dimension specialists in sequence (per Critic-Orchestrator.md)
  2. Aggregates verdicts from specialists
  3. Identifies conflicts between dimensions (e.g., Security wants lockdown, ExecutionReady says incomplete)
  4. Makes final APPROVED / APPROVED_WITH_CONDITIONS / REJECTED decision
  5. Documents rationale in LogBook
- **Output:** Final verdict + aggregated feedback from all specialists
- **Blocks:** PM cannot promote task to main until Orchestrator approves

**11.2.3 Seven Dimension Specialists**

**Critic-SpecFit**
- **Dimension:** Specification alignment
- **Checks:**
  - Generated code matches specification requirements
  - No scope creep (features not in spec)
  - No gaps (spec requirements missing)
- **Evidence:** Side-by-side spec vs code comparison

**Critic-Verification**
- **Dimension:** Test coverage and correctness
- **Checks:**
  - Test coverage ≥ 80% (configurable)
  - All edge cases tested
  - Tests actually pass (not just exist)
  - Test quality (assertions meaningful, not trivial)
- **Evidence:** Coverage reports, test execution results

**Critic-Dependencies**
- **Dimension:** Dependency management
- **Checks:**
  - Dependencies explicitly declared in manifest
  - No circular dependencies
  - Version pinning (no floating versions like "latest")
  - License compliance (no GPL in proprietary code)
- **Evidence:** Dependency graph, lock file analysis

**Critic-Effort**
- **Dimension:** Time estimate accuracy
- **Checks:**
  - Actual time vs estimated time ratio (target: 0.8-1.2x)
  - If overrun >50%, flag for PM review
  - Capture lessons learned for future estimation
- **Evidence:** `time_estimate` vs `time_actual` in `.task/task.yaml`

**Critic-ExecutionReady**
- **Dimension:** Implementation completeness
- **Checks:**
  - No TODOs or FIXMEs in shipped code
  - Error handling present (no silent failures)
  - Logging at appropriate levels
  - Documentation (function docstrings, README updates)
- **Evidence:** Code scan for markers, exception handling review

**Critic-SecurityPolicy**
- **Dimension:** Security compliance
- **Checks:**
  - No hardcoded secrets (API keys, passwords)
  - Input validation present (SQL injection, XSS prevention)
  - Authentication/authorization enforced
  - Compliance with org security policies
- **Evidence:** Secret scanner results, security policy checklist

**Critic-ACL (Anti-Corruption Layer)**
- **Dimension:** Ports-and-Adapters architecture compliance
- **Checks:**
  - External dependencies isolated behind adapters
  - No vendor lock-in (can swap database, cloud provider)
  - Clean separation: domain logic ≠ infrastructure
  - Interface stability (breaking changes versioned)
- **Evidence:** Dependency diagram, adapter interface review

### 11.3 Invocation Protocol

**11.3.1 Plan Review Flow**
```
PM receives plan from Planner
     ↓
PM invokes Critic-PlanAuditor
     ↓
PlanAuditor reviews plan (decomposition, dependencies, estimates)
     ↓
PlanAuditor returns verdict (APPROVED / NEEDS_REVISION)
     ↓
if APPROVED:
    PM assigns work order to Builder
if NEEDS_REVISION:
    PM sends feedback to Planner, requests revision
```

**11.3.2 Task Review Flow**
```
Builder completes task on alt branch
     ↓
Builder notifies PM (progress update with status=COMPLETE)
     ↓
PM invokes Critic-Orchestrator
     ↓
Orchestrator invokes 7 specialists IN SEQUENCE:
    - Critic-SpecFit
    - Critic-Verification
    - Critic-Dependencies
    - Critic-Effort
    - Critic-ExecutionReady
    - Critic-SecurityPolicy
    - Critic-ACL
     ↓
Each specialist returns verdict (PASS / FAIL) + feedback
     ↓
Orchestrator aggregates verdicts:
    - ALL PASS → APPROVED
    - ANY FAIL (critical dimension) → REJECTED
    - SOME FAIL (non-critical) → APPROVED_WITH_CONDITIONS
     ↓
Orchestrator returns final verdict to PM
     ↓
if APPROVED or APPROVED_WITH_CONDITIONS:
    PM promotes task to main
    PM updates LogBook with Critic verdicts
if REJECTED:
    PM sends feedback to Builder, requests fixes
```

**11.3.3 Sequential Specialist Invocation**

**Benefits:**
- Deterministic reviews: 7 specialists run sequentially for consistent evaluation order
- Independent assessments: specialists don't influence each other's verdicts
- Scalability: add new dimension specialists without slowing down reviews

**Implementation:**
- PM launches 7 specialist agents sequentially (in order defined by Orchestrator)
- Each specialist operates on same task artifacts (code, tests, manifest)
- Orchestrator waits for all specialists to complete before aggregating
- Timeout: if any specialist exceeds 5 minutes, escalate to PM

### 11.4 Decision Matrix: PlanAuditor vs Orchestrator

| Scenario | Agent to Invoke | Rationale |
|----------|-----------------|-----------|
| Reviewing decomposition plan before execution | **PlanAuditor** | Plan review is pre-execution (no code yet) |
| Reviewing completed task implementation | **Orchestrator** | Task review requires all 7 dimensions (code exists) |
| Checking if time estimates are realistic | **PlanAuditor** | Estimates set during planning phase |
| Validating test coverage of completed task | **Orchestrator** | Tests exist only after Builder completes task |
| Ensuring dependency graph is acyclic | **PlanAuditor** | Dependencies declared in plan (before coding) |
| Scanning for hardcoded secrets | **Orchestrator** | Secrets can only be detected in code (post-implementation) |

**Rule of Thumb:**
- **Before Builder starts:** PlanAuditor
- **After Builder finishes:** Orchestrator

### 11.5 Conflict Resolution Between Specialists

**Scenario:** Two specialists disagree on verdict
- **Example:** SecurityPolicy says FAIL (hardcoded secret found), ExecutionReady says PASS (code complete)

**Orchestrator Resolution:**
1. Check dimension priority by classification
2. Critical dimensions: Security, SpecFit, Verification (FAIL in any → REJECTED)
3. Non-critical dimensions: Dependencies, Effort, ACL, ExecutionReady (FAIL → APPROVED_WITH_CONDITIONS)

**Dimension Classification (All 7 Clearly Defined):**
| Dimension | Classification | Rationale |
|-----------|----------------|-----------|
| Security (Dim 6) | CRITICAL | Security failures are non-negotiable |
| SpecFit (Dim 4) | CRITICAL | Implementation must match specification |
| Verification (Dim 5) | CRITICAL | Untested code is unsafe to promote |
| Dependencies (Dim 1) | NON-CRITICAL | Can ship with TODO for dep cleanup |
| Effort (Dim 2) | NON-CRITICAL | Estimation errors don't block delivery |
| ACL (Dim 7) | NON-CRITICAL | Minor access issues can be fixed post-merge |
| ExecutionReady (Dim 3) | NON-CRITICAL | Can ship with minor runtime warnings |

**Escalation Trigger:**
- If 3+ specialists FAIL, escalate to PM for human review (likely fundamental issue)
- If specialist verdicts contradict policy, escalate to PM (e.g., policy says "ship fast," Security says "never ship with TODO")

### 11.6 Specialist Agent Files

**Location:** `.claude/agents/`

**Files:**
- `Critic-PlanAuditor.md` - Plan review coordinator
- `Critic-Orchestrator.md` - Task review coordinator
- `Critic-Dependencies.md` - Dimension 1 (Dependency Integrity)
- `Critic-Effort.md` - Dimension 2 (Effort Accuracy)
- `Critic-ExecutionReady.md` - Dimension 3 (Execution Readiness)
- `Critic-SpecFit.md` - Dimension 4 (Spec Fit)
- `Critic-Verification.md` - Dimension 5 (Verification Quality)
- `Critic-SecurityPolicy.md` - Dimension 6 (Security & Policy Compliance)
- `Critic-ACL.md` - Dimension 7 (Anti-Corruption Layer Compliance)

**Note:** Each specialist agent has detailed prompt with domain-specific expertise (security best practices, dependency management patterns, etc.)

### 11.7 Success Metrics

**Critic System Health:**
- Specialist verdict consistency: >90% agreement rate (no conflicting verdicts)
- Orchestrator decision time: <10 minutes (including sequential specialist execution)
- False positive rate: <10% (tasks rejected but should have passed)
- False negative rate: <5% (tasks approved but should have failed)

**Quality Improvement:**
- Defect escape rate: <2% (bugs found in production that Critic should have caught)
- Rework rate: <20% (tasks requiring revision after Critic feedback)
- Time-to-approval: <1 hour (from Builder completion to Critic approval)

---

## 12. Agent Recovery & State Management

**Purpose:** Define how agents recover from session interruptions and maintain state continuity

### 12.1 PM State Persistence

**PM State File:** `/LogBook/pm/STATE.md`
**Schema:** `/PLANNING/schemas/pm_state_schema.yaml`

PM maintains persistent working memory to enable recovery from session interruptions.

**State Components:**
- **active_branches:** All active alt branches with task work in progress
- **task_queue:** Prioritized queue of tasks awaiting execution
- **escalations:** Active issues requiring human intervention
- **recent_decisions:** Last 20 PM decisions for audit trail
- **metrics:** System health metrics (promotion rate, CI pass rate, cycle time)
- **governance:** Compliance tracking (policy overrides, Teams notifications status)

**Update Frequency:**
- After every PM decision (task assignment, work order issuance, promotion, etc.)
- At session start (read and validate)
- At session end (write and flush logs)

### 12.2 Recovery Protocol (PM Session Interruption)

If PM session restarts, PM executes:

1. **Read State File**
   - Load `/LogBook/pm/STATE.md`
   - Parse active_branches, task_queue, escalations

2. **Validate Consistency**
   - Verify all `active_branches` exist in git: `git branch -a`
   - Cross-reference with LogBook entries: `/LogBook/<category>/alt/<branch>/INDEX.md`
   - Check task_spec_paths reference existing files

3. **Resume In-Progress Work**
   - Identify tasks with status `in_progress`
   - Re-issue work orders to assigned agents
   - Update last_updated timestamps

4. **Handle Inconsistencies**
   - If branch exists but no LogBook entry → **ESCALATE (orphaned branch)**
   - If LogBook entry exists but no branch → Mark task as failed, **ESCALATE**
   - If STATE.md malformed → Reconstruct from LogBook entries
   - If LogBook entries missing → **ESCALATE TO HUMAN**

5. **Resume Normal Operations**
   - Process task_queue in priority order
   - Monitor active escalations
   - Continue workflow cycle

### 12.3 State Corruption Scenarios

| Scenario | Detection | Recovery Action |
|----------|-----------|----------------|
| STATE.md malformed (invalid YAML/markdown) | Parse error on session start | Reconstruct from LogBook entries, escalate if reconstruction fails |
| Active branch in STATE.md but no git branch | `git branch -a` doesn't list branch | Mark task as failed, escalate, remove from active_branches |
| Git branch exists but no LogBook entry | LogBook INDEX.md missing | Escalate (orphaned branch), do not resume work |
| LogBook entry exists but task_spec_path missing | File not found | Escalate (spec deleted), mark task as blocked |
| Duplicate task IDs in STATE.md | Schema validation fails | Escalate (data corruption), use LogBook as source of truth |

### 12.4 Other Agents State Management

**Builder:** Stateless (receives work orders, produces output, no persistent state)

**Critic:** Stateless (receives task for review, returns verdict, no persistent state)

**Planner:** Currently fulfilled by PM (see PM_Operating_Manual.md Section 8.5)

**Why PM is the only agent with persistent state:**
- PM orchestrates all workflow decisions (task assignment, promotions, escalations)
- Other agents are execution-only (receive input, produce output, exit)
- Centralized state in PM prevents distributed state synchronization issues
- PM's LogBook-backed state provides single source of truth for recovery

### 12.5 Handoff After Recovery

When PM resumes after interruption:

1. **Notify Human (if critical):**
   - If escalations exist → Send summary to user
   - If state corruption detected → Require human acknowledgment before resuming

2. **Resume Agent Communications:**
   - Re-establish communication with Builder/Critic agents
   - Re-issue work orders for interrupted builds
   - Verify agents can access required files

3. **Audit Trail Integrity:**
   - Log recovery event in `/LogBook/pm/sessions/SESSION-YYYYMMDD-HHMMSS.yaml`
   - Document any state inconsistencies resolved
   - Update metrics (e.g., session interruption count)

---

## 12. Agent Invocation Syntax Standards

**Standard Pattern:** `@<agent-name> <command>`

All agents use a consistent invocation syntax for clarity and correct Claude Code agent invocation.

###  Core Agents (Human or PM invokes)

- `@Project-Manager <task description>`
- `@Planner <planning request>`
- `@Builder Implement task <task-id>`
- `@Critic-Orchestrator Evaluate task <task-id>`
- `@Critic-PlanAuditor Audit plan <plan-id>`

### Individual Dimension Critics (Orchestrator invokes)

**NOTE:** These are typically invoked by Critic-Orchestrator, not directly by PM or humans.

- `@Critic-Dependencies <task-id>`
- `@Critic-Effort <task-id>`
- `@Critic-ExecutionReady <task-id>`
- `@Critic-SpecFit <task-id>`
- `@Critic-Verification <task-id>`
- `@Critic-SecurityPolicy <task-id>`
- `@Critic-ACL <task-id>`

### Invocation Examples

**PM assigns work to Builder:**
```
@Builder Implement task task-1.1-init-repo
```

**PM requests task evaluation:**
```
@Critic-Orchestrator Evaluate task task-1.1-init-repo
```

**PM requests plan audit:**
```
@Critic-PlanAuditor Audit plan System_Plan.md
```

**Orchestrator invokes dimension critic (automated):**
```
@Critic-Dependencies task-1.1-init-repo
```

### Anti-Patterns (DO NOT USE)

❌ `@agent-Critic-Dependencies` (old syntax)
❌ `@Dependencies` (missing "Critic")
❌ `Builder` (missing @ symbol)
❌ `@Builder` (missing "the framework" prefix)

### Rationale

- **Consistency:** All agents use same `@<name>` pattern
- **Clarity:** `@` symbol clearly marks agent invocation
- **Namespacing:** `` prefix avoids conflicts with other tools
- **Claude Code compatibility:** Matches Claude Code agent invocation syntax

---

## 13. Complete Task Evaluation Workflow (End-to-End)

This section provides a step-by-step walkthrough of the complete task evaluation workflow from Builder completion to PM promotion decision.

### 13.1 Workflow Overview

```
[Builder Completes] → [PM Detects] → [PM Invokes Orchestrator] → [Orchestrator Runs 7 Critics]
                                                                          ↓
[PM Promotes/Rejects] ← [PM Reads Verdict] ← [Orchestrator Writes Verdict]
```

### 13.2 Step-by-Step Workflow

**STEP 1: Builder Completes Task**
- **Agent:** Builder
- **Action:** Builder finishes implementing task per work order
- **File Written:** `/LogBook/progress/tasks/<task-id>/status.yaml`
- **Status Value:** `COMPLETE_READY_FOR_REVIEW`
- **Signal:** File-based completion signal (PM monitors this directory)

**Example:**
```yaml
# /LogBook/progress/tasks/task-2.3-daily-digest/status.yaml
task_id: "task-2.3-daily-digest"
status: "COMPLETE_READY_FOR_REVIEW"
completed_at: "2025-12-23T14:30:00Z"
builder_agent: "Builder"
work_order: "/LogBook/work-orders/WO-20251223-002.yaml"
```

---

**STEP 2: PM Detects Completion**
- **Agent:** Project-Manager
- **Monitoring:** PM polls `/LogBook/progress/tasks/*/status.yaml` every 2 minutes
- **Detection:** Finds `status: COMPLETE_READY_FOR_REVIEW`
- **Action:** PM updates STATE.md to `TASK_IN_REVIEW`
- **Next Step:** PM prepares to invoke Orchestrator

**PM State Update:**
```yaml
# LogBook/pm/STATE.md
current_state: "TASK_IN_REVIEW"
active_task: "task-2.3-daily-digest"
review_initiated_at: "2025-12-23T14:32:00Z"
```

---

**STEP 3: PM Invokes Orchestrator**
- **Agent:** Project-Manager
- **Invocation Syntax:**
  ```
  @Critic-Orchestrator Evaluate task task-2.3-daily-digest
  ```
- **Parameters Passed:**
  - Task ID: task-2.3-daily-digest
  - Task location: /alt/task-2.3-daily-digest/
  - Work order reference: WO-20251223-002.yaml
- **Expected Output:** Verdict file written by Orchestrator

---

**STEP 4: Orchestrator Coordinates 7 Dimension Critics**
- **Agent:** Critic-Orchestrator
- **Action:** Automatically invokes all 7 dimension critics in sequence:
  1. Critic-Dependencies (dependency_integrity)
  2. Critic-Effort (effort_accuracy)
  3. Critic-ExecutionReady (execution_ready)
  4. Critic-SpecFit (spec_fit)
  5. Critic-Verification (verification)
  6. Critic-SecurityPolicy (security_policy)
  7. Critic-ACL (acl)

**Internal Protocol:**
```python
# Pseudo-code for Orchestrator
dimension_results = []
for critic in [Dependencies, Effort, ExecutionReady, SpecFit, Verification, SecurityPolicy, ACL]:
    result = invoke_critic(critic, task_id)
    dimension_results.append(result)

overall_score = calculate_weighted_score(dimension_results)
final_verdict = "APPROVED" if overall_score >= 0.9 else "REJECTED"
```

---

**STEP 5: Orchestrator Writes Verdict File**
- **Agent:** Critic-Orchestrator
- **File Written:** `/LogBook/critic/verdicts/VER-<task-id>.yaml`
- **Format:** YAML (per `critic_verdict_schema.yaml`)
- **Location:** `/LogBook/critic/verdicts/VER-task-2.3-daily-digest.yaml`

**Example Verdict:**
```yaml
# /LogBook/critic/verdicts/VER-task-2.3-daily-digest.yaml
final_verdict: "APPROVED"
task_id: "task-2.3-daily-digest"
timestamp: "2025-12-23T14:35:00Z"
overall_score: 0.96

dimension_results:
  - dimension: "dependency_integrity"
    verdict: "pass"
    score: 1.0
  - dimension: "effort_accuracy"
    verdict: "pass"
    score: 0.95
  # ... (all 7 dimensions)
```

---

**STEP 6: PM Detects Verdict Completion**
- **Agent:** Project-Manager
- **Monitoring:** PM watches for verdict file creation
- **Detection:** File `/LogBook/critic/verdicts/VER-<task-id>.yaml` exists
- **Action:** PM reads verdict file

**Read Command:**
```bash
cat /LogBook/critic/verdicts/VER-task-2.3-daily-digest.yaml
```

---

**STEP 7: PM Makes Promotion Decision**
- **Agent:** Project-Manager
- **Decision Logic:**
  ```
  IF overall_score >= 0.9 AND final_verdict == "APPROVED":
      decision = PROMOTE
  ELSE:
      decision = REJECT_WITH_FEEDBACK
  ```

**CASE A: APPROVED (Promote to Main)**
- PM writes promotion record: `/LogBook/pm/promotions/PROM-<task-id>.md`
- PM executes promotion:
  ```bash
  git checkout main
  git merge alt/task-2.3-daily-digest
  git tag task-2.3-daily-digest
  ```
- PM updates STATE.md: `PROMOTION_COMPLETE`

**CASE B: REJECTED (Return to Builder)**
- PM creates fix work order: `/LogBook/work-orders/WO-<date>-FIX-<task-id>.yaml`
- PM includes verdict feedback and required fixes
- PM invokes Builder with fix work order:
  ```
  @Builder Fix task task-2.3-daily-digest based on verdict VER-task-2.3-daily-digest
  ```
- PM updates STATE.md: `TASK_IN_FIX_CYCLE`

---

**STEP 8: Workflow Complete**
- PM updates `/LogBook/progress/INDEX.md` with task status
- PM logs decision to `/LogBook/pm/decisions/DEC-<date>-<task-id>.md`
- Workflow returns to idle state, awaiting next task completion

### 13.3 File Locations Summary

| Step | File | Purpose |
|------|------|---------|
| 1 | `/LogBook/progress/tasks/<task-id>/status.yaml` | Builder completion signal |
| 3 | N/A (invocation only) | PM → Orchestrator |
| 5 | `/LogBook/critic/verdicts/VER-<task-id>.yaml` | Orchestrator verdict output |
| 7A | `/LogBook/pm/promotions/PROM-<task-id>.md` | Promotion record (if approved) |
| 7B | `/LogBook/work-orders/WO-<date>-FIX-<task-id>.yaml` | Fix work order (if rejected) |

### 13.4 Monitoring Points

**For Operators:**
- Monitor `/LogBook/progress/tasks/*/status.yaml` to see task completion
- Monitor `/LogBook/critic/verdicts/VER-*.yaml` to see evaluation results
- Monitor `/LogBook/pm/promotions/PROM-*.md` to see promotion decisions

**For PM Agent:**
- Poll `/LogBook/progress/tasks/*/status.yaml` every 2 minutes (normal mode)
- Poll every 30 seconds when task is in active evaluation
- Escalate if verdict file not created within 10 minutes

### 13.5 Error Handling

**Timeout Scenarios:**
- If Orchestrator doesn't write verdict within 10 minutes → PM escalates
- If Builder doesn't update status within work order time box → PM escalates
- If dimension critic crashes → Orchestrator marks dimension as ERROR and continues

**Recovery Procedures:**
- Stuck evaluations: PM can re-invoke Orchestrator
- Missing verdict file: PM checks Orchestrator logs, retries once
- Corrupted verdict: PM escalates to human for manual review

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-26 | PM | Initial document creation |

---

**End of Agent Coordination Protocol**
