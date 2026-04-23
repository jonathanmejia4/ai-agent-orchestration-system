# Issue Fixing: File Signals Strategy

> **Status:** Production Ready
> **Last Updated:** 2026-01-04
> **Context Usage:** ~3,500 tokens (vs 265k with TaskOutput)

---

## Overview

This document describes the **file-based signal strategy** for running all 21 issue fixers in parallel without exhausting the orchestrator's context window.

### The Problem

When using `TaskOutput` to collect results from sub-agents, Claude returns the **entire transcript** of each agent's session - every file read, every edit, every tool call. With 26 fixers, this means:

```
26 fixers × ~12,000 tokens each = 252,000+ tokens
```

This exceeds the 200k context limit and causes the orchestrator to fail.

### The Solution

**File-based signals.** Instead of using TaskOutput:
- Fixers write an empty `.done` file when finished
- Orchestrator polls the file system to count completions
- Zero transcript data enters orchestrator context

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                │
│                  (IF-Orchestrator, sonnet, ~3,500 tokens)           │
│                                                                     │
│  1. rm signals/*.done                                               │
│  2. Spawn 21 Tasks (fire-and-forget)                                │
│  3. Poll: ls signals/*.done | wc -l                                 │
│  4. When count=21 → sync catalog → push                             │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ Spawns (run_in_background: true)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      21 FIXERS (parallel)                           │
│                  (opus, each has own 200k context)                  │
│                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐     ┌─────────┐               │
│  │ Lane E  │ │ Lane G  │ │ Lane H  │ ... │ Lane Z  │               │
│  │         │ │         │ │         │     │         │               │
│  │ Find    │ │ Find    │ │ Find    │     │ Find    │               │
│  │ Fix     │ │ Fix     │ │ Fix     │     │ Fix     │               │
│  │ Commit  │ │ Commit  │ │ Commit  │     │ Commit  │               │
│  │ Signal  │ │ Signal  │ │ Signal  │     │ Signal  │               │
│  └────┬────┘ └────┬────┘ └────┬────┘     └────┬────┘               │
│       │           │           │               │                     │
└───────┼───────────┼───────────┼───────────────┼─────────────────────┘
        │           │           │               │
        ▼           ▼           ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LogBook/issue-fixing/signals/                          │
│                                                                     │
│     E.done    G.done    H.done    ...    Z.done                     │
│                                                                     │
│              (empty files - existence = completion)                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Status Signals

In addition to `.done` files for completion, fixers write `.status` files to communicate progress:

### Signal Types

| Signal | Meaning | Example |
|--------|---------|---------|
| STARTING | Fixer has started | `STARTING: scanning catalog for Lane E` |
| NORMAL | Working on low/medium complexity | `NORMAL: fixing up to 5 issues` |
| COMPLEX | Working on high/extreme complexity | `COMPLEX: E-45 (EXTREME - 15 files)` |
| COMPLETE | Finished all work | `COMPLETE: fixed 3 issues` |

### File Pattern

```
LogBook/issue-fixing/signals/
├── E.status    "COMPLEX: E-45 (EXTREME - architectural)"
├── E.done      (created when complete)
├── G.status    "NORMAL: fixing 4 issues"
├── G.done      (created when complete)
...
```

### Benefits

1. **Real-time visibility** - See what each lane is working on
2. **Complexity awareness** - Understand why some lanes produce fewer fixes
3. **Zero context cost** - File reads don't consume orchestrator tokens
4. **Debugging** - If a lane stalls, status shows where it stopped

### Orchestrator Output

```
14:30:15 - Done: 5/21 | Complex lanes: 3
  → Lane E: COMPLEX: E-45 (EXTREME - 15 files, architectural)
  → Lane M: COMPLEX: M-12 (HIGH - schema migration)
  → Lane Z: COMPLEX: Z-08 (EXTREME - governance overhaul)
```

---

## Fixer Flow (Per Lane)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    IF-Lane-G Fixer Flow                             │
└─────────────────────────────────────────────────────────────────────┘

STEP 1: Find Issues from CATALOG (Source of Truth)
──────────────────────────────────────────────────
ISSUE_CATALOG.md → "Open Issues by Lane" section

### Lane G - Ghost References
| ID    | Title                  | Severity   | Tags      | Status |
|-------|------------------------|------------|-----------|--------|
| G-71  | Missing tools/foo.py   | 7/10 HIGH  | GhostRef  | OPEN   |
| G-72  | Broken link in docs    | 5/10 MED   | GhostRef  | OPEN   |
| G-73  | Stale import path      | 4/10 LOW   | GhostRef  | OPEN   |

Extract issue IDs: G-71, G-72, G-73 (oldest first = top to bottom)


STEP 2: Read FULL ISSUE FILE for each issue
───────────────────────────────────────────
cat issues/G/G-71.md

├── Problem Description (what's wrong)
├── Evidence (file paths, line numbers, quotes)
├── affected_paths (which files to modify)
├── Fix Requirements (exactly what to do)
└── Verification Commands (how to test the fix)


STEP 3: Implement the Fix
─────────────────────────
├── Read affected files
├── Make minimal changes (Edit tool)
├── Run verification commands
├── If verification passes:
│   └── Update issue file: status → RESOLVED
├── If verification fails:
│   └── Revert changes, skip issue
└── Repeat for next issue (max 5)


STEP 4: Commit and Signal
─────────────────────────
git add .
git commit -m "Lane G fixing: 3 issues resolved"
touch LogBook/issue-fixing/signals/G.done
```

---

## Components

### 1. Signals Directory

**Location:** `LogBook/issue-fixing/signals/`

**Contents:**
- `.gitkeep` - Ensures directory exists in git
- `{LANE}.done` - Created by fixers when complete (e.g., `E.done`, `G.done`)

**Lifecycle:**
```
Start of run    → rm -f *.done (clean slate)
During fixing   → Fixers create .done files as they finish
End of run      → 21 .done files present
Next run        → rm -f *.done (repeat)
```

### 2. Orchestrator

**File:** `.claude/agents/issue-fixers/IF-Orchestrator.md`

**Model:** sonnet (haiku can't use Task tool)

**Key Protocol - "Run ALL Protocol":**

| Step | Action | Context Cost |
|------|--------|--------------|
| 1 | Clean signals, reset state | ~500 tokens |
| 2 | Spawn 21 Tasks in ONE message | ~2,000 tokens |
| 3 | Poll loop (NO TaskOutput) | ~600 tokens |
| 4 | Sync catalog | ~200 tokens |
| 5 | Commit and push | ~200 tokens |
| **Total** | | **~3,500 tokens** |

### 3. Fixer Agents

**Files:** `.claude/agents/issue-fixers/IF-Lane-{E,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z}.md`

**Model:** opus (spawned by orchestrator)

**Each Fixer:**
1. Reads open issues from ISSUE_CATALOG.md (source of truth)
2. Reads full issue file for each issue
3. Implements the fix (max 5 issues, oldest first)
4. Runs verification commands
5. Marks fixed issues as RESOLVED
6. Commits their own work: `git add . && git commit`
7. Signals completion: `touch LogBook/issue-fixing/signals/{LANE}.done`

---

## Step-by-Step Execution

### Step 1: Clean Slate

```bash
# Remove any previous signal files
rm -f LogBook/issue-fixing/signals/*.done

# Reset orchestrator state
python3 << 'EOF'
import yaml
from datetime import datetime

ALL_LANES = ["E","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"]

state = {
    "run_id": datetime.now().strftime("%Y-%m-%d-%H%M"),
    "started": datetime.now().isoformat(),
    "status": "running",
    "lanes": {},
    "progress": {
        "total_lanes": 21,
        "completed_lanes": 0,
        "total_fixed": 0
    }
}

for lane in ALL_LANES:
    state["lanes"][lane] = {
        "status": "pending",
        "issues_fixed": 0,
        "issue_ids": []
    }

with open("LogBook/issue-fixing/orchestrator-state.yaml", "w") as f:
    yaml.dump(state, f, default_flow_style=False, sort_keys=False)

print(f"Reset complete - Run ID: {state['run_id']}")
EOF
```

### Step 2: Spawn All 21 Fixers

Send ONE message with 21 Task tool calls:

```
For each lane in [E, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z]:

Task:
  description: "Fix Lane {LANE}"
  model: opus
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    You are IF-Lane-{LANE} issue fixer.

    Read: .claude/agents/issue-fixers/IF-Lane-{LANE}.md

    1. Find open issues for Lane {LANE} from ISSUE_CATALOG.md "Open Issues by Lane" section
    2. Fix up to 5 issues (work top to bottom = oldest first)
    3. Mark each fixed issue as RESOLVED in the issue file
    4. git add . && git commit
    5. touch LogBook/issue-fixing/signals/{LANE}.done

    The catalog is your source of truth for open issues.
```

**Critical:** All 21 must be in ONE message for true parallelism.

### Step 3: Poll for Completion

**DO NOT USE TaskOutput** - it returns entire transcripts.

```bash
echo "Waiting for fixers to complete..."
echo "Checking every 45 seconds for 21 .done files..."

while true; do
    count=$(ls LogBook/issue-fixing/signals/*.done 2>/dev/null | wc -l | tr -d ' ')
    echo "$(date +%H:%M:%S) - Completed: $count/21"

    if [ "$count" -ge 21 ]; then
        echo "All 26 fixers complete!"
        break
    fi

    sleep 45
done
```

**Timeline example:**
```
00:00  Completed: 0/21   (just started)
00:45  Completed: 4/21   (fast lanes done)
01:30  Completed: 10/21
02:15  Completed: 16/21
03:00  Completed: 21/21  ← All done!
```

### Step 4: Verify Commits

```bash
echo "=== Recent commits ==="
git log --oneline -25 | grep -E "Lane [A-Z] fixing"
```

### Step 5: Sync Catalog and Push

```bash
# Sync catalog (updates statistics, removes resolved from Open Issues)
python3 tools/sync_catalog_stats.py --verbose

# Commit catalog update
git add ISSUE_CATALOG.md LogBook/
git commit -m "Issue fixing complete: catalog synced

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# Push everything (fixer commits + catalog commit)
git push origin main

# Cleanup signals for next run
rm -f LogBook/issue-fixing/signals/*.done
```

### Step 6: Report

```
ISSUE FIXING COMPLETE

Signals: 21/21 received
Catalog: synced
Pushed: ✓

Check ISSUE_CATALOG.md for updated statistics.
```

---

## User Prompt

Copy and paste this to run issue fixing:

```
Read .claude/agents/issue-fixers/IF-Orchestrator.md

Run ALL 26 lanes using the "Run ALL Protocol" with file-based signals:

1. Clean signals directory (rm -f LogBook/issue-fixing/signals/*.done) and reset state
2. Spawn ALL 26 fixers in ONE message (model: opus, run_in_background: true)
3. Poll LogBook/issue-fixing/signals/*.done until count = 21 (DO NOT use TaskOutput!)
4. Sync catalog: python3 tools/sync_catalog_stats.py
5. git commit catalog update and push
6. Report minimal summary
```

---

## Why This Works

| Problem | Old Approach | File Signals Approach |
|---------|--------------|----------------------|
| Collecting results | TaskOutput (full transcript) | Poll file count |
| Tokens per fixer | ~12,000 | 0 |
| Total context | 265,000+ (FAILS) | ~3,500 (SUCCESS) |
| Know when done | Parse TaskOutput | Count .done files |
| Fixer commits | Orchestrator commits all | Each fixer commits own |

### Key Insights

1. **TaskOutput is the enemy** - It returns everything, not just the final message
2. **File system is free** - Checking file existence costs ~0 tokens
3. **Fixers are independent** - They can commit their own work
4. **Polling is cheap** - A bash loop uses minimal context
5. **Parallelism preserved** - All 21 still run simultaneously
6. **Catalog is source of truth** - Fixers find issues from catalog, not directory scan

---

## Comparison: Hunters vs Fixers

| Aspect | Hunters | Fixers |
|--------|---------|--------|
| Purpose | Find new issues | Fix existing issues |
| Directory | `.claude/agents/issue-hunters/` | `.claude/agents/issue-fixers/` |
| Signals | `LogBook/issue-hunting/signals/` | `LogBook/issue-fixing/signals/` |
| State | `issue-hunting/orchestrator-state.yaml` | `issue-fixing/orchestrator-state.yaml` |
| Action | Create issue files | Fix code, mark RESOLVED |
| Max per run | 5 issues found | 5 issues fixed |
| Input | Scans codebase | Reads from catalog |
| Output | New `issues/{X}/{X}-NN.md` | Modified code + updated issue files |

**Both can run concurrently without conflicts** - they use separate signal directories and state files.

---

## File Locations

| File | Purpose |
|------|---------|
| `.claude/agents/issue-fixers/IF-Orchestrator.md` | Orchestrator agent definition |
| `.claude/agents/issue-fixers/IF-Lane-{X}.md` | 26 fixer agent definitions |
| `LogBook/issue-fixing/signals/` | Signal files directory |
| `LogBook/issue-fixing/signals/.gitkeep` | Keeps directory in git |
| `LogBook/issue-fixing/orchestrator-state.yaml` | Run state persistence |
| `tools/sync_catalog_stats.py` | Updates ISSUE_CATALOG.md |
| `ISSUE_CATALOG.md` | Issue catalog (source of truth) |

---

## Lane Specializations

| Lane | Focus Area | Typical Fixes |
|------|------------|---------------|
| E | Customer Services & Data Protection | Policy updates, guideline additions |
| G | Ghost References & Missing Artifacts | Create missing files, fix broken refs |
| H | Stubs & Placeholders | Implement stubs, remove placeholders |
| I | Agent ↔ Guideline Contradictions | Align agent/guideline language |
| J | Policy Enforcement Gaps | Add enforcement checks |
| K | LogBook Contract Violations | Fix LogBook structure/writes |
| L | CI/Workflow Configuration | Fix workflow configs |
| M | Schema Definition Drift | Update/align schemas |
| N | Template Consistency | Fix template issues |
| O | API Contract Drift | Align API definitions |
| P | Security & Compliance | Security fixes |
| Q | Performance & Scalability | Performance improvements |
| R | Observability & Monitoring | Add monitoring/logging |
| S | Data Integrity & Validation | Add validation |
| T | Error Handling & Recovery | Improve error handling |
| U | Configuration Management | Fix configs |
| V | Dependency Management | Fix dependencies |
| W | Test Harness Gaps | Add/fix tests |
| X | Docs Site & Reference | Fix documentation |
| Y | Tooling Interface & CLI | Fix tool interfaces |
| Z | Weird Edges & High Impact | Edge case fixes |

---

## Troubleshooting

### Poll shows 0/21 for a long time
- Fixers may still be working on complex issues
- Check if fixers are running: look for opus processes
- Normal for first few minutes (fixers need to read, understand, implement, verify)

### Some fixers never signal
- Check if fixer crashed (look for partial commits)
- Fixer may have found 0 issues but still should signal
- Check the lane's Open Issues section - maybe it was empty

### Git push fails
- Multiple fixers committed simultaneously (rare)
- Run: `git pull --rebase && git push`

### Issues still showing as OPEN after run
- Fixer may have skipped unfixable issues
- Check issue file for skip notes
- Verification may have failed

### Fixer modified wrong files
- Issue's `affected_paths` may have been inaccurate
- Review the issue file's Fix Requirements section

---

## Actual Observed Results

**Issue Fixer Run - 2026-01-04:**

```
Context Usage (Orchestrator):
├── Total: 115k/200k tokens (57%)
├── Messages: 52k tokens
├── Free space: 85k tokens remaining
└── Status: SUCCESS ✓

All 26 fixers completed without context overflow.
```

**Comparison:**

| Metric | TaskOutput Method | File Signals Method |
|--------|-------------------|---------------------|
| Context used | 265k+ (OVERFLOW) | 115k (57%) |
| Free space | -65k (FAILED) | +85k remaining |
| Completion | ❌ Failed | ✅ Success |

---

## Context Usage Comparison

```
OLD METHOD (TaskOutput):
========================
Orchestrator context over time:

     │ 265k ─────────────────────────────── X FAIL
     │                                   ╱
     │                                 ╱
     │                               ╱
     │                             ╱ (collecting 21 transcripts)
     │                           ╱
     │                         ╱
     │         ╱─────────────╱
     │       ╱
     │     ╱ (spawning)
     │   ╱
     │ ╱
200k ├─────────────────────────────────────────
     │
     └─────────────────────────────────────────►
       Start                                Time


NEW METHOD (File Signals):
==========================
Orchestrator context over time:

200k ├─────────────────────────────────────────
     │
     │
     │
     │
     │
     │
     │
     │
     │
     │    ┌──────────────────────────────────┐
3.5k │────┤ spawn → poll → sync → done ✓    │
     │    └──────────────────────────────────┘
     └─────────────────────────────────────────►
       Start                                Time
```

---

## Running Hunters and Fixers Concurrently

Both systems can run at the same time:

```
Terminal 1 (Hunters):
$ claude
> [paste hunter prompt]
> Spawning 26 hunters...
> Polling issue-hunting/signals/...

Terminal 2 (Fixers):
$ claude
> [paste fixer prompt]
> Spawning 26 fixers...
> Polling issue-fixing/signals/...
```

**No conflicts because:**
- Separate signal directories
- Separate state files
- Hunters create new files, fixers modify existing
- Both sync catalog at end (sync_catalog_stats.py handles this)

---

## Version History

| Date | Change |
|------|--------|
| 2026-01-04 | Initial implementation of issue fixer system |
| 2026-01-04 | File-based signals (same pattern as hunters) |
| 2026-01-04 | 5 issues per fixer, oldest first priority |
| 2026-01-04 | Catalog as source of truth for finding issues |
| 2026-01-04 | Poll interval: 45 seconds |
