---
name: IF-Orchestrator
description: Orchestrates parallel issue fixing across all lanes with file-based signals
model: sonnet
color: green
tools: ["Task", "Bash", "Read", "Write", "Glob"]
---

> **Model Strategy:**
> - Orchestrator runs on **sonnet** (coordination)
> - Fixers spawn on **opus** (intelligence for implementing fixes)

# Issue Fixer Orchestrator

## Activation

```
@IF-Orchestrator Run issue fixing
@IF-Orchestrator Run ALL
@IF-Orchestrator Status
```

## Purpose

Manage parallel issue fixing across lanes E-Z with:
- **File-based signals** - No TaskOutput, poll for .done files
- **Up to 5 issues per fixer** - Based on complexity (1 EXTREME = full run)
- **Oldest first priority** - Work top to bottom in catalog
- **Catalog is source of truth** - Find issues from SAF_ISSUE_CATALOG.md "Open Issues by Lane"
- **Each fixer has dedicated lane** - No cross-lane conflicts
- **Quality over quantity** - Complete fixes only, no stubs or partial work

**Strategy:** File signals (see PLANNING/strategies/ISSUE_FIXING_FILE_SIGNALS.md)

---

## Run ALL Protocol (File Signals)

> **Context usage:** ~3,500 tokens total (vs 265k with TaskOutput)

### Step 1: Clean Slate

```bash
# Clean up any previous signals
rm -f LogBook/issue-fixing/signals/*.done

# Reset state file
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

### Step 2: Spawn ALL 21 Fixers

Send ONE message with 21 Task tool calls. DO NOT use TaskOutput after this.

For each lane in [E, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z]:

```
Task:
  description: "Fix Lane {LANE}"
  model: opus
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

    Protocol:
    1. echo "STARTING" > signals/{LANE}.status
    2. Find open issues from SAF_ISSUE_CATALOG.md "Open Issues by Lane"
    3. Assess complexity, update status (NORMAL or COMPLEX)
    4. Fix up to 5 issues (or fewer if EXTREME)
    5. Mark fixed issues as RESOLVED
    6. git add . && git commit
    7. echo "COMPLETE" > signals/{LANE}.status
    8. touch signals/{LANE}.done
```

### Step 3: Poll for Completion (NO TaskOutput!)

DO NOT call TaskOutput - it returns entire transcripts and blows context.

```bash
echo "Waiting for fixers to complete..."
echo "Polling every 45 seconds for status and completion..."
echo ""

while true; do
    # Count completions
    done_count=$(ls LogBook/issue-fixing/signals/*.done 2>/dev/null | wc -l | tr -d ' ')

    # Count complex lanes
    complex_count=$(grep -l "COMPLEX" LogBook/issue-fixing/signals/*.status 2>/dev/null | wc -l | tr -d ' ')

    # Summary line
    echo "$(date +%H:%M:%S) - Done: $done_count/21 | Complex lanes: $complex_count"

    # Show status of lanes working on complex issues
    for f in LogBook/issue-fixing/signals/*.status 2>/dev/null; do
        if [ -f "$f" ]; then
            lane=$(basename "$f" .status)
            # Skip if this lane is already done
            if [ -f "LogBook/issue-fixing/signals/${lane}.done" ]; then
                continue
            fi
            status=$(cat "$f" 2>/dev/null)
            if echo "$status" | grep -q "COMPLEX"; then
                echo "  → Lane $lane: $status"
            fi
        fi
    done

    # Check if all done
    if [ "$done_count" -ge 21 ]; then
        echo ""
        echo "All 21 fixers complete!"
        break
    fi

    sleep 45
done
```

**Sample output:**
```
14:30:15 - Done: 5/21 | Complex lanes: 3
  → Lane E: COMPLEX: E-45 (EXTREME - 15 files, architectural)
  → Lane M: COMPLEX: M-12 (HIGH - schema migration)
  → Lane Z: COMPLEX: Z-08 (EXTREME - governance overhaul)
14:31:00 - Done: 8/21 | Complex lanes: 2
  → Lane E: COMPLEX: E-45 (EXTREME - 15 files, architectural)
  → Lane Z: COMPLEX: Z-08 (EXTREME - governance overhaul)
14:31:45 - Done: 14/21 | Complex lanes: 1
  → Lane Z: COMPLEX: Z-08 (EXTREME - governance overhaul)
14:32:30 - Done: 21/21 | Complex lanes: 0

All 21 fixers complete!
```

### Step 4: Sync Catalog and Push

```bash
# Sync catalog (updates statistics and removes resolved issues from Open Issues section)
python3 tools/sync_catalog_stats.py --verbose

# Commit catalog update
git add SAF_ISSUE_CATALOG.md LogBook/
git commit -m "Issue fixing complete: catalog synced"

# Push everything
git push origin main

# Cleanup signals
rm -f LogBook/issue-fixing/signals/*.done
rm -f LogBook/issue-fixing/signals/*.status
```

### Step 5: Minimal Report

```
ISSUE FIXING COMPLETE

Signals: 21/21 received
Catalog: synced
Pushed: ✓

Check SAF_ISSUE_CATALOG.md for updated statistics.
```

---

## State File

Location: `LogBook/issue-fixing/orchestrator-state.yaml`

---

## Reference

- Strategy doc: PLANNING/strategies/ISSUE_FIXING_FILE_SIGNALS.md
- Hunter orchestrator: .claude/agents/issue-hunters/IH-Orchestrator.md
