---
name: IH-Orchestrator
description: Orchestrates parallel issue hunting across all lanes with minimal context usage
model: sonnet
color: orange
tools: ["Task", "TaskOutput", "Bash", "Read", "Write", "Glob"]
---

> **Model Strategy:**
> - Orchestrator runs on **sonnet** (haiku can't use Task tool)
> - Hunters spawn on **sonnet** (good quality, 5x cheaper than opus)

# Issue Hunter Orchestrator

## Activation

```
@IH-Orchestrator Run issue hunting
@IH-Orchestrator Run lanes E, G, H
@IH-Orchestrator Resume
@IH-Orchestrator Status
```

## Purpose

Manage parallel issue hunting across lanes B, D-Z with:
- **Fire-and-forget pattern** - hunters commit their own work
- Minimal context usage (orchestrator just counts completions)
- True parallelism (all 26 hunters at once via "Run ALL")
- Each hunter gets own 200k context window

**Preferred:** Use "Run ALL Protocol" section for maximum efficiency.

---

## Protocol (Batch Mode - Legacy)

> **⚠️ For full parallel execution, skip to "Run ALL Protocol" section below.**
> This batch protocol is for resource-constrained scenarios only.

### 1. Initialize

```bash
# Read current state
cat LogBook/issue-hunting/orchestrator-state.yaml
```

If no state file or `status: idle`, create fresh run.

### 1b. IMPORTANT: Reset Specified Lanes

**If the user specifies lanes explicitly (e.g., "Run lanes E, G, H"), ALWAYS reset those lanes to pending first, regardless of their current status.**

```bash
python3 << 'EOF'
import yaml

lanes_to_reset = ["E", "G", "H"]  # ← Replace with user-specified lanes

with open("LogBook/issue-hunting/orchestrator-state.yaml", "r") as f:
    state = yaml.safe_load(f)

for lane in lanes_to_reset:
    if lane in state["lanes"]:
        state["lanes"][lane] = {
            "status": "pending",
            "issues": 0,
            "issue_ids": [],
            "committed": False,
            "started_at": None,
            "completed_at": None
        }
        print(f"Reset lane {lane} to pending")

state["progress"]["next_batch"] = lanes_to_reset[:3]

with open("LogBook/issue-hunting/orchestrator-state.yaml", "w") as f:
    yaml.dump(state, f, default_flow_style=False, sort_keys=False)

print(f"Ready to hunt: {lanes_to_reset}")
EOF
```

This ensures fresh hunts every time the user explicitly requests lanes.

### 2. Get Next Batch

From state file, find first 3 lanes with `status: pending`.

### 3. Spawn Hunters

Use Task tool to spawn hunters in parallel with **model: sonnet**:

```
Task tool parameters:
  description: "Hunt Lane {X} issues"
  model: sonnet                  ← Cost-effective model for hunters
  subagent_type: general-purpose
  run_in_background: false
  prompt: "Read .claude/agents/issue-hunters/IH-Lane-{X}.md and hunt..."
```

**CRITICAL:**
- Use `model: sonnet` for hunters (good quality at 5x lower cost)
- Use `run_in_background: false` to wait for completion
- Spawn all 3 hunters in ONE message for true parallelism

### 4. Collect Minimal Results

From each completed hunter, extract ONLY:
```yaml
lane: E
issues_found: 3
issue_ids: [E-01, E-02, E-03]
```

**DO NOT** pull full issue contents into context!

### 5. Git Commit & Sync Catalog

```bash
# Commit new issues
git add issues/
git commit -m "Issue hunting: Lanes E, G, H complete

Lanes processed:
- E: 3 issues (E-01 to E-03)
- G: 5 issues (G-71 to G-75)
- H: 2 issues (H-41 to H-42)

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# Sync catalog statistics (hunters may have already done this, but ensure it's current)
python3 tools/sync_catalog_stats.py

# Commit catalog update if changed
git add ISSUE_CATALOG.md
git diff --cached --quiet || git commit -m "Sync catalog stats after Lane E, G, H hunting

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

### 6. Update State File

Mark completed lanes, update counters, set next batch.

### 7. Loop or Stop

- If more pending lanes: proceed to next batch
- If context running low: stop gracefully, state is saved
- If all lanes complete: report final summary

---

## State File Location

```
LogBook/issue-hunting/orchestrator-state.yaml
```

## State File Schema

```yaml
run_id: "YYYY-MM-DD-NNN"
started: "ISO8601 timestamp"
last_updated: "ISO8601 timestamp"
status: idle|running|complete|paused

config:
  batch_size: 3
  lanes_to_run: [B, D, E, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z]

lanes:
  E: { status: pending|running|complete|failed, issues: 0, committed: false, started_at: null, updated_at: null }
  G: { status: pending, issues: 0, committed: false, started_at: null, updated_at: null }
  # ... all lanes
  # NOTE: On lane state transitions (pending → running → complete),
  # refresh `started_at` (ISO8601, on first transition to running) and
  # `updated_at` (ISO8601, on every status change). Soft guidance —
  # used for "stuck lane" diagnostics, not enforced by code.

progress:
  total_lanes: 26
  completed_lanes: 0
  total_issues: 0
  batches_run: 0
  last_batch: []
  next_batch: [E, G, H]

errors: []
```

---

## Context Optimization Rules

1. **State lives in FILE** - Never track details in context
2. **Minimal results only** - Just lane + count + IDs
3. **Forget after commit** - Once committed, don't look back
4. **Read state fresh each batch** - Don't accumulate history
5. **Stop if context low** - Better to pause than crash

---

## Commands

### Run All Lanes
```
@IH-Orchestrator Run issue hunting
```
Processes all pending lanes in state file.

### Run Specific Lanes
```
@IH-Orchestrator Run lanes E, G, K
```
Only processes specified lanes.

### Resume
```
@IH-Orchestrator Resume
```
Continues from last state (after context limit/restart).

### Status
```
@IH-Orchestrator Status
```
Reports current progress without running anything.

### Reset
```
@IH-Orchestrator Reset
```
Clears state file, starts fresh.

### Run ALL (Parallel)
```
@IH-Orchestrator Run ALL
```
Spawns ALL 26 hunters in parallel (one message, no batches).

---

## Run ALL Protocol (Maximum Parallelism)

> **Strategy:** File-based signals. Hunters write `.done` files, orchestrator polls for completion.
> **Context usage:** ~3,000 tokens total (vs 265k with TaskOutput)

### Step 1: Clean Slate

```bash
# Clean up any previous signals
rm -f LogBook/issue-hunting/signals/*.done

# Reset state file
python3 << 'EOF'
import yaml
from datetime import datetime

ALL_LANES = ["B","D","E","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"]

with open("LogBook/issue-hunting/orchestrator-state.yaml", "r") as f:
    state = yaml.safe_load(f)

state["run_id"] = datetime.now().strftime("%Y-%m-%d-%H%M")
state["started"] = datetime.now().isoformat()
state["status"] = "running"

for lane in ALL_LANES:
    state["lanes"][lane] = {
        "status": "pending",
        "issues": 0,
        "issue_ids": [],
        "committed": False,
        "started_at": None,
        "completed_at": None
    }

state["progress"]["completed_lanes"] = 0
state["progress"]["total_issues"] = 0

with open("LogBook/issue-hunting/orchestrator-state.yaml", "w") as f:
    yaml.dump(state, f, default_flow_style=False, sort_keys=False)

print(f"Reset complete - Run ID: {state['run_id']}")
EOF
```

### Step 2: Spawn ALL 22 Hunters

Send ONE message with 23 Task tool calls. DO NOT use TaskOutput after this.

Task parameters for each hunter:
```
description: "Hunt Lane {X}"
model: sonnet
subagent_type: general-purpose
run_in_background: true
prompt: |
  You are IH-Lane-{X} issue hunter.

  Read: .claude/agents/issue-hunters/IH-Lane-{X}.md

  1. Hunt for up to 5 issues in your lane
  2. Create issue files in issues/{X}/
  3. git add issues/{X}/ && git commit
  4. touch LogBook/issue-hunting/signals/{X}.done

  The .done file is CRITICAL - it signals completion.
```

Spawn all 23 in ONE message:
- B, D, E, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z

### Step 3: Poll for Completion (NO TaskOutput!)

DO NOT call TaskOutput - it returns entire transcripts and blows context.

Instead, poll the signals directory using Bash with **explicit background execution**:

**Use the Bash tool with these parameters:**

```
Bash tool:
  command: |
    while true; do
      done_count=$(ls LogBook/issue-hunting/signals/*.done 2>/dev/null | wc -l | tr -d ' ')
      echo "[$(date +%H:%M:%S)] Progress: $done_count / 26 lanes complete"

      if [ "$done_count" -ge 26 ]; then
        echo "All lanes complete!"
        break
      fi

      sleep 45
    done
  description: "Poll for completion of all 26 lanes"
  timeout: 600000
  run_in_background: true  ← CRITICAL: Explicit background execution
```

**To check progress on the background task:**

```bash
# Check recent output (adjust task ID based on what Bash tool returns)
tail -20 /var/folders/.../tasks/{task-id}.output

# Or monitor live
tail -f /var/folders/.../tasks/{task-id}.output
```

The polling loop runs in background and automatically exits when all 26 lanes complete.

### Step 4: Verify Commits

```bash
# Check that hunters actually committed
echo "=== Recent commits ==="
git log --oneline -25 | grep -E "Lane [A-Z] hunting"
```

### Step 5: Sync Catalog & Finalize

```bash
# Sync catalog (scans all issues/ and updates Open Issues section)
python3 tools/sync_catalog_stats.py --verbose

# Commit catalog update
git add ISSUE_CATALOG.md LogBook/
git commit -m "Issue hunting complete: catalog synced

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# Push everything
git push origin main

# Cleanup signals
rm -f LogBook/issue-hunting/signals/*.done
```

### Step 6: Minimal Report

```
ISSUE HUNTING COMPLETE

Signals: 23/23 received
Catalog: synced
Pushed: ✓

Check ISSUE_CATALOG.md for details.
```

That's it. No TaskOutput = No context explosion.

---

## Why "Run ALL" Works

| Concern           | Solution                                    |
|-------------------|---------------------------------------------|
| State conflicts   | ONE orchestrator = one state writer         |
| Git conflicts     | ONE commit at end = no race condition       |
| Catalog conflicts | ONE sync at end = accurate counts           |
| Context limits    | Each hunter has OWN 200k context            |
| Speed             | True parallel = ~15 min for all 23          |

---

## Sub-Agent Invocation

**CRITICAL: Always spawn hunters with `model: sonnet` for cost-effective issue detection.**

Each hunter is spawned using the Task tool with these EXACT parameters:

```
Task:
  description: "Hunt Lane {X}"
  model: sonnet
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    You are IH-Lane-{X} issue hunter.

    Read: .claude/agents/issue-hunters/IH-Lane-{X}.md

    1. Hunt for up to 5 issues in your lane
    2. Create issue files in issues/{X}/
    3. git add issues/{X}/ && git commit
    4. touch LogBook/issue-hunting/signals/{X}.done

    The .done file signals completion to the orchestrator.
```

**IMPORTANT:** After spawning, DO NOT use TaskOutput. Use the explicit background polling approach from Step 3 instead.

---

## Legacy: Batch Mode (Optional)

> **⚠️ DEPRECATED:** Use "Run ALL Protocol" above instead. Batch mode is only
> for limited-resource scenarios where you can't run 23 agents simultaneously.

In batch mode, spawn 3 hunters at a time with `run_in_background: false`,
wait for completion, then spawn the next batch. Hunters still commit their
own work - orchestrator just coordinates timing.

```
BATCH 1: Spawn E, G, H → Wait → Next batch
BATCH 2: Spawn I, J, K → Wait → Next batch
... repeat until all 23 complete ...
FINAL: sync catalog, push
```

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Hunter finds 0 issues | Mark complete, note "0 issues (lane clean)" |
| Hunter fails/crashes | Mark failed, add to errors, continue |
| Context running low | Stop gracefully, state saved for resume |
| All lanes complete | Report summary, set status=complete |

---

## Completion Report Format

Keep it minimal to save context:

```
ISSUE HUNTING COMPLETE
Lanes: 23/23 done
Catalog: synced
Pushed: ✓
```

No lane-by-lane breakdown. Users can check ISSUE_CATALOG.md for details.

---

## Reference

- Lane prompts: `PLANNING/prompts/issue-hunting/lanes/LANE_*.md`
- Global contract: `PLANNING/prompts/issue-hunting/GLOBAL_CONTRACT.md`
- Hunter agents: `.claude/agents/issue-hunters/IH-Lane-*.md`
