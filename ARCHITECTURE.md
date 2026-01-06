# Architecture Deep Dive

## Design Principles

### 1. Lane-Based Specialization

Each lane represents a specific problem domain:
- Lane E: Customer services patterns
- Lane G: Reference integrity
- Lane H: Code stubs & placeholders
- Lane M: Schema validation
- ...etc

**Why lanes?**
- Reduces cognitive load (agent focuses on one problem type)
- Enables parallel execution (no cross-lane conflicts)
- Improves accuracy (deep expertise > shallow generalization)

### 2. File-Based Orchestration

**Problem:** Traditional agent systems return full transcripts (265k tokens)

**Solution:** File-based `.done` signals

```bash
# Agent completes work
touch LogBook/issue-hunting/signals/E.done

# Orchestrator polls
while [ $(ls signals/*.done | wc -l) -lt 21 ]; do
    sleep 30
done
```

**Result:** 3k tokens instead of 265k (98.9% reduction)

### 3. State Management

Orchestrator state stored in YAML:

```yaml
lanes:
  E:
    status: completed
    issues: 15
    committed: true
  G:
    status: in_progress
    issues: 0
```

**Benefits:**
- Human-readable
- Git-trackable
- Easy to debug
- No database overhead

---

## System Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ORCHESTRATOR (Sonnet)                          │
│                                                                         │
│  1. Reset state & signals                                               │
│  2. Spawn 21 agents in parallel ─────────────────────────────────────┐  │
│  3. Poll for .done files                                             │  │
│  4. When 21/21 complete:                                             │  │
│     - Sync catalog                                                   │  │
│     - Commit & push                                                  │  │
│     - Cleanup signals                                                │  │
└─────────────────────────────────────────────────────────────────────────┘
                                                                       │
     ┌─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐       ┌──────────────┐
│  Lane E      │  │  Lane G      │  │  Lane H      │  ...  │  Lane Z      │
│  (Opus)      │  │  (Opus)      │  │  (Opus)      │       │  (Opus)      │
│              │  │              │  │              │       │              │
│  1. Hunt     │  │  1. Hunt     │  │  1. Hunt     │       │  1. Hunt     │
│  2. Create   │  │  2. Create   │  │  2. Create   │       │  2. Create   │
│     issues   │  │     issues   │  │     issues   │       │     issues   │
│  3. Commit   │  │  3. Commit   │  │  3. Commit   │       │  3. Commit   │
│  4. Signal   │  │  4. Signal   │  │  4. Signal   │       │  4. Signal   │
│     .done    │  │     .done    │  │     .done    │       │     .done    │
└──────────────┘  └──────────────┘  └──────────────┘       └──────────────┘
```

### Detailed Flow

1. **Orchestrator spawns agents** (Task tool, parallel)
2. **Agents execute independently** (separate context windows)
3. **Agents commit their work** (git add, commit)
4. **Agents signal completion** (touch .done file)
5. **Orchestrator polls signals** (wait for 21/21)
6. **Orchestrator syncs catalog** (update statistics)
7. **Orchestrator commits final state** (push to main)

---

## Context Optimization

### The Problem

With 21 agents running in parallel, naive approaches blow up context:

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
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐   │
│  │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ 12k │ ... │   │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘   │
│  Total: ~265k tokens (context exhausted!)                               │
│                                                                         │
│  File-based signals:                                                    │
│  ┌───┐                                                                  │
│  │3k │  (Poll loop + completion count only)                            │
│  └───┘                                                                  │
│  Total: ~3k tokens (98.9% reduction!)                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Two-Phase Architecture

### Phase 1: Issue Hunters

**Purpose:** Find and catalog issues in the codebase

```
IH-Orchestrator (Sonnet)
    │
    ├── IH-Lane-E (Opus) → Customer service issues
    ├── IH-Lane-G (Opus) → Reference integrity issues
    ├── IH-Lane-H (Opus) → Code stub issues
    ├── IH-Lane-M (Opus) → Schema drift issues
    └── ... (21 total lanes)
```

**Each hunter:**
- Scans specific file patterns
- Creates issue files with evidence
- Commits to lane-specific directory
- Signals completion

### Phase 2: Issue Fixers

**Purpose:** Resolve issues found by hunters

```
IF-Orchestrator (Sonnet)
    │
    ├── IF-Lane-E (Opus) → Fixes E-* issues
    ├── IF-Lane-G (Opus) → Fixes G-* issues
    ├── IF-Lane-H (Opus) → Fixes H-* issues
    ├── IF-Lane-M (Opus) → Fixes M-* issues
    └── ... (21 total lanes)
```

**Each fixer:**
- Reads open issues from catalog
- Assesses complexity (LOW/MEDIUM/HIGH/EXTREME)
- Implements fixes with verification
- Marks issues as RESOLVED
- Commits and signals completion

---

## Complexity-Aware Fixing

### The Problem

Not all issues are equal. Forcing 5 issues per fixer leads to:
- Half-done fixes
- Placeholder code (`TODO`, `FIXME`)
- Context exhaustion mid-fix

### The Solution

Dynamic issue count based on complexity:

| Level | Criteria | Action |
|-------|----------|--------|
| LOW | 1-2 files | Fix up to 5 issues |
| MEDIUM | 3-5 files | Fix up to 5 issues |
| HIGH | 6-10 files | Fix 2-3 issues max |
| EXTREME | 10+ files | Fix ONLY this issue |

**Key principle:** Quality > Quantity

One perfect fix is infinitely better than five broken ones.

---

## Status Signal System

### Signal Types

| Signal | File | Meaning |
|--------|------|---------|
| STARTING | `{LANE}.status` | Agent began work |
| NORMAL | `{LANE}.status` | Working on low/medium complexity |
| COMPLEX | `{LANE}.status` | Working on high/extreme complexity |
| COMPLETE | `{LANE}.status` | Finished all work |
| Done | `{LANE}.done` | Final completion signal |

### Benefits

1. **Real-time visibility** - See what each lane is working on
2. **Complexity awareness** - Understand why some lanes produce fewer fixes
3. **Zero context cost** - File reads don't consume orchestrator tokens
4. **Debugging** - If a lane stalls, status shows where it stopped

---

## Scalability Considerations

| Factor | Limit | Mitigation |
|--------|-------|------------|
| Context limits | 200k per agent | Each lane gets own window |
| API rate limits | ~5 concurrent | Batch spawning respected |
| Cost | $$ per run | Haiku for simple, Opus for complex |
| Time | ~15-20 min | Full parallel execution |

---

## Error Handling

Agents handle failures gracefully:

| Error | Response |
|-------|----------|
| Permissions error | Skip and log |
| Verification failure | Revert and skip |
| Timeout | Signal partial completion |
| API error | Exponential backoff |
| Context exhaustion | Commit partial, signal done |

---

## Extension Points

To add new lanes:

1. Create `IH-Lane-X.md` (hunter)
2. Create `IF-Lane-X.md` (fixer)
3. Update orchestrator lane list
4. Run: `@IH-Orchestrator Run ALL`

---

## Key Learnings

1. **Specialization beats generalization** - 21 focused agents outperform 1 general agent
2. **File signals beat transcript returns** - 98.9% context reduction
3. **Parallel beats sequential** - 21 simultaneous context windows
4. **Verification must be built-in** - Each issue has automated verification
5. **State as files** - YAML states easier than databases
6. **Quality over quantity** - One complete fix > five partial fixes

---

## Metrics Achieved

| Metric | Value |
|--------|-------|
| Total issues found | 1,471 |
| Issues resolved | 1,352 (91.9%) |
| Context reduction | 98.9% |
| Parallel agents | 21 |
| Avg resolution time | 15-20 min per full run |
