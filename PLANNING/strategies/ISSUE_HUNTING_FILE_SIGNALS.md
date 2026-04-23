# Issue Hunting: File Signals Strategy

> **Status:** Production Ready
> **Last Updated:** 2026-01-04
> **Context Usage:** ~3,400 tokens (vs 265,000 with TaskOutput)

---

## Overview

This document describes the **file-based signal strategy** for running all 21 issue hunters in parallel without exhausting the orchestrator's context window.

### The Problem

When using `TaskOutput` to collect results from sub-agents, Claude returns the **entire transcript** of each agent's session - every file read, every search, every tool call. With 26 hunters, this means:

```
26 hunters × ~12,000 tokens each = 252,000+ tokens
```

This exceeds the 200k context limit and causes the orchestrator to fail.

### The Solution

**File-based signals.** Instead of using TaskOutput:
- Hunters write an empty `.done` file when finished
- Orchestrator polls the file system to count completions
- Zero transcript data enters orchestrator context

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                │
│                     (sonnet, ~3,400 tokens)                         │
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
│                     21 HUNTERS (parallel)                           │
│                  (opus, each has own 200k context)                  │
│                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐     ┌─────────┐               │
│  │ Lane E  │ │ Lane G  │ │ Lane H  │ ... │ Lane Z  │               │
│  │         │ │         │ │         │     │         │               │
│  │ Hunt    │ │ Hunt    │ │ Hunt    │     │ Hunt    │               │
│  │ Commit  │ │ Commit  │ │ Commit  │     │ Commit  │               │
│  │ Signal  │ │ Signal  │ │ Signal  │     │ Signal  │               │
│  └────┬────┘ └────┬────┘ └────┬────┘     └────┬────┘               │
│       │           │           │               │                     │
└───────┼───────────┼───────────┼───────────────┼─────────────────────┘
        │           │           │               │
        ▼           ▼           ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LogBook/issue-hunting/signals/                         │
│                                                                     │
│     E.done    G.done    H.done    ...    Z.done                     │
│                                                                     │
│              (empty files - existence = completion)                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Signals Directory

**Location:** `LogBook/issue-hunting/signals/`

**Contents:**
- `.gitkeep` - Ensures directory exists in git
- `{LANE}.done` - Created by hunters when complete (e.g., `E.done`, `G.done`)

**Lifecycle:**
```
Start of run    → rm -f *.done (clean slate)
During hunting  → Hunters create .done files as they finish
End of run      → 21 .done files present
Next run        → rm -f *.done (repeat)
```

### 2. Orchestrator

**File:** `.claude/agents/issue-hunters/IH-Orchestrator.md`

**Model:** sonnet (haiku can't use Task tool)

**Key Protocol - "Run ALL Protocol":**

| Step | Action | Context Cost |
|------|--------|--------------|
| 1 | Clean signals, reset state | ~500 tokens |
| 2 | Spawn 21 Tasks in ONE message | ~2,000 tokens |
| 3 | Poll loop (NO TaskOutput) | ~500 tokens |
| 4 | Sync catalog | ~200 tokens |
| 5 | Commit and push | ~200 tokens |
| **Total** | | **~3,400 tokens** |

### 3. Hunter Agents

**Files:** `.claude/agents/issue-hunters/IH-Lane-{E,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z}.md`

**Model:** opus (spawned by orchestrator)

**Each Hunter:**
1. Reads their lane-specific instructions
2. Searches codebase for issues (max 3 per run)
3. Creates issue files in `issues/{LANE}/`
4. Commits their own work: `git add issues/{LANE}/ && git commit`
5. Signals completion: `touch LogBook/issue-hunting/signals/{LANE}.done`

---

## Step-by-Step Execution

### Step 1: Clean Slate

```bash
# Remove any previous signal files
rm -f LogBook/issue-hunting/signals/*.done

# Reset orchestrator state
python3 << 'EOF'
import yaml
from datetime import datetime

ALL_LANES = ["E","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"]

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
        "committed": False
    }

with open("LogBook/issue-hunting/orchestrator-state.yaml", "w") as f:
    yaml.dump(state, f, default_flow_style=False, sort_keys=False)

print(f"Reset complete - Run ID: {state['run_id']}")
EOF
```

### Step 2: Spawn All 21 Hunters

Send ONE message with 21 Task tool calls:

```
For each lane in [E, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z]:

Task:
  description: "Hunt Lane {LANE}"
  model: opus
  subagent_type: general-purpose
  run_in_background: true
  prompt: |
    You are IH-Lane-{LANE} issue hunter.

    Read: .claude/agents/issue-hunters/IH-Lane-{LANE}.md

    1. Hunt for up to 3 issues in your lane
    2. Create issue files in issues/{LANE}/
    3. git add issues/{LANE}/ && git commit
    4. touch LogBook/issue-hunting/signals/{LANE}.done

    The .done file signals completion to the orchestrator.
```

**Critical:** All 21 must be in ONE message for true parallelism.

### Step 3: Poll for Completion

**DO NOT USE TaskOutput** - it returns entire transcripts.

```bash
echo "Waiting for hunters to complete..."
echo "Checking every 45 seconds for 21 .done files..."

while true; do
    count=$(ls LogBook/issue-hunting/signals/*.done 2>/dev/null | wc -l | tr -d ' ')
    echo "$(date +%H:%M:%S) - Completed: $count/21"

    if [ "$count" -ge 21 ]; then
        echo "All 26 hunters complete!"
        break
    fi

    sleep 45
done
```

**Timeline example:**
```
00:00  Completed: 0/21   (just started)
00:30  Completed: 3/21   (fast lanes done)
01:00  Completed: 8/21
01:30  Completed: 14/21
02:00  Completed: 19/21
02:30  Completed: 21/21  ← All done!
```

### Step 4: Verify Commits

```bash
echo "=== Recent commits ==="
git log --oneline -25 | grep -E "Lane [A-Z] hunting"
```

### Step 5: Sync Catalog and Push

```bash
# Sync catalog (scans all issues/ and populates Open Issues section)
python3 tools/sync_catalog_stats.py --verbose

# Commit catalog update
git add ISSUE_CATALOG.md LogBook/
git commit -m "Issue hunting complete: catalog synced

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# Push everything (hunter commits + catalog commit)
git push origin main

# Cleanup signals for next run
rm -f LogBook/issue-hunting/signals/*.done
```

### Step 6: Report

```
ISSUE HUNTING COMPLETE

Signals: 21/21 received
Catalog: synced
Pushed: ✓

Check ISSUE_CATALOG.md for details.
```

---

## User Prompt

Copy and paste this to run issue hunting:

```
Read .claude/agents/issue-hunters/IH-Orchestrator.md

Run ALL 26 lanes using the "Run ALL Protocol" with file-based signals:

1. Clean signals directory (rm -f signals/*.done) and reset state
2. Spawn ALL 26 hunters in ONE message (model: opus, run_in_background: true)
3. Poll signals/*.done until count = 21 (DO NOT use TaskOutput!)
4. Sync catalog: python3 tools/sync_catalog_stats.py
5. git commit catalog update and push
6. Report minimal summary
```

---

## Why This Works

| Problem | Old Approach | File Signals Approach |
|---------|--------------|----------------------|
| Collecting results | TaskOutput (full transcript) | Poll file count |
| Tokens per hunter | ~12,000 | 0 |
| Total context | 265,000+ (FAILS) | ~3,400 (SUCCESS) |
| Know when done | Parse TaskOutput | Count .done files |
| Hunter commits | Orchestrator commits all | Each hunter commits own |

### Key Insights

1. **TaskOutput is the enemy** - It returns everything, not just the final message
2. **File system is free** - Checking file existence costs ~0 tokens
3. **Hunters are independent** - They can commit their own work
4. **Polling is cheap** - A bash loop uses minimal context
5. **Parallelism preserved** - All 21 still run simultaneously

---

## File Locations

| File | Purpose |
|------|---------|
| `.claude/agents/issue-hunters/IH-Orchestrator.md` | Orchestrator agent definition |
| `.claude/agents/issue-hunters/IH-Lane-{X}.md` | 21 hunter agent definitions |
| `LogBook/issue-hunting/signals/` | Signal files directory |
| `LogBook/issue-hunting/signals/.gitkeep` | Keeps directory in git |
| `LogBook/issue-hunting/orchestrator-state.yaml` | Run state persistence |
| `tools/sync_catalog_stats.py` | Updates ISSUE_CATALOG.md |
| `ISSUE_CATALOG.md` | Issue catalog with statistics |

---

## Troubleshooting

### Poll shows 0/21 for a long time
- Hunters may still be searching
- Check if hunters are running: look for opus processes
- Normal for first few minutes

### Some hunters never signal
- Check if hunter crashed (look in issues/{LANE}/ for partial work)
- Hunter may have found 0 issues but still should signal
- Re-run with just that lane: modify prompt to specify lanes

### Git push fails
- Multiple hunters committed simultaneously (rare)
- Run: `git pull --rebase && git push`

### Catalog not updated
- Verify sync ran: `python3 tools/sync_catalog_stats.py --verbose`
- Check for issues in issues/ directories

---

## Comparison: Old vs New

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
3.4k │────┤ spawn → poll → sync → done ✓    │
     │    └──────────────────────────────────┘
     └─────────────────────────────────────────►
       Start                                Time
```

---

## Version History

| Date | Change |
|------|--------|
| 2026-01-04 | Initial implementation of file signals strategy |
| 2026-01-04 | Max 5 issues per hunter |
| 2026-01-04 | Added fire-and-forget pattern (hunters commit own work) |
| 2026-01-04 | Replaced TaskOutput with file polling |
