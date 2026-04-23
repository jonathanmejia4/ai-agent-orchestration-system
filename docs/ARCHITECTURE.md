# Architecture Overview

How the Project Arrow framework works.

---

## Design Principles

### 1. Lane-Based Specialization

Each lane (A-Z) handles a specific domain:
- Reduces cognitive load per agent
- Enables parallel execution without conflicts
- Improves accuracy through focus

### 2. File-Based Orchestration

**Problem:** Traditional agent systems return full transcripts (100k+ tokens)

**Solution:** File-based signals

```bash
# Agent completes work
touch LogBook/issue-hunting/signals/A.done

# Orchestrator polls
while [ $(ls signals/*.done | wc -l) -lt 26 ]; do
    sleep 30
done
```

**Result:** ~3k tokens instead of 265k (99% reduction)

### 3. Two-Phase Workflow

**Phase 1: Hunters** find and document issues
**Phase 2: Fixers** implement and verify solutions

Each phase runs independently.

---

## System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ORCHESTRATOR (Sonnet)                          │
│                                                                         │
│  1. Reset state & signals                                               │
│  2. Spawn agents in parallel ───────────────────────────────────────┐   │
│  3. Poll for .done files                                            │   │
│  4. When all complete:                                              │   │
│     - Sync catalog                                                  │   │
│     - Commit & push                                                 │   │
│     - Cleanup signals                                               │   │
└─────────────────────────────────────────────────────────────────────────┘
                                                                      │
     ┌────────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐       ┌──────────────┐
│  Lane A      │  │  Lane B      │  │  Lane C      │  ...  │  Lane Z      │
│  (Opus)      │  │  (Opus)      │  │  (Opus)      │       │  (Opus)      │
│              │  │              │  │              │       │              │
│  1. Scan     │  │  1. Scan     │  │  1. Scan     │       │  1. Scan     │
│  2. Create   │  │  2. Create   │  │  2. Create   │       │  2. Create   │
│     issues   │  │     issues   │  │     issues   │       │     issues   │
│  3. Commit   │  │  3. Commit   │  │  3. Commit   │       │  3. Commit   │
│  4. Signal   │  │  4. Signal   │  │  4. Signal   │       │  4. Signal   │
│     .done    │  │     .done    │  │     .done    │       │     .done    │
└──────────────┘  └──────────────┘  └──────────────┘       └──────────────┘
```

---

## Context Optimization

### The Problem

With many agents running in parallel, naive approaches blow up context:

| Approach | Context Used | Problem |
|----------|--------------|---------|
| TaskOutput for each | 265k tokens | Entire transcript returned |
| Batch + Wait | 50k tokens | Sequential, slow |
| File signals | 3k tokens | Minimal, parallel |

### The Solution

**Fire-and-forget with file signals:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Context Usage Comparison                            │
│                                                                         │
│  Traditional (TaskOutput):                                              │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐         │
│  │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ ... │         │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘         │
│  Total: ~265k tokens (context exhausted!)                               │
│                                                                         │
│  File-based signals:                                                    │
│  ┌───┐                                                                  │
│  │3k │  (Poll loop + completion count only)                            │
│  └───┘                                                                  │
│  Total: ~3k tokens (99% reduction!)                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Issue Lifecycle

```
┌──────────────┐
│   HUNTING    │
│              │
│ Hunter scans │
│ Creates file │
│ Status: OPEN │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   CATALOG    │
│              │
│ Sync stats   │
│ Track counts │
└──────┬───────┘
       │
       ▼
┌──────────────┐      ┌──────────────┐
│   FIXING     │      │  STILL OPEN  │
│              │      │              │
│ Fixer works  │─────▶│ Verification │
│ Implements   │ fail │ failed       │
│ Verifies     │      └──────────────┘
└──────┬───────┘
       │ pass
       ▼
┌──────────────┐
│   RESOLVED   │
│              │
│ Issue fixed  │
│ Verified     │
└──────────────┘
```

---

## State Management

### Orchestrator State

```yaml
run_id: "2026-01-07-1430"
started: "2026-01-07T14:30:00"
status: running

lanes:
  A:
    status: completed
    issues: 5
    committed: true
  B:
    status: in_progress
    issues: 0

progress:
  total_lanes: 26
  completed_lanes: 12
  total_issues: 45
```

### Benefits

- Human-readable
- Git-trackable
- Easy to debug
- No database needed

---

## Scalability

| Factor | Limit | Mitigation |
|--------|-------|------------|
| Context limits | 200k per agent | Each lane gets own window |
| API rate limits | ~5 concurrent | Batch spawning respected |
| Time | ~15-20 min | Full parallel execution |

---

## Error Handling

| Error | Response |
|-------|----------|
| Permissions error | Skip and log |
| Verification failure | Revert and skip |
| Timeout | Signal partial completion |
| Context exhaustion | Commit partial, signal done |

---

## Key Learnings

1. **Specialization beats generalization** - Focused agents outperform general ones
2. **File signals beat transcript returns** - 99% context reduction
3. **Parallel beats sequential** - Simultaneous context windows
4. **Verification must be built-in** - Each issue has automated checks
5. **State as files** - YAML states easier than databases
6. **Quality over quantity** - One complete fix > five partial fixes
