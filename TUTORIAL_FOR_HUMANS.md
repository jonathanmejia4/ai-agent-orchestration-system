# Tutorial for Humans - Issue Hunting & Fixing System

> **Purpose:** Step-by-step guide for humans to operate the issue hunting and fixing agents.

---

## The Fastest Way: Slash Commands

Just type these in Claude Code:

| Command | What It Does |
|---------|--------------|
| `/find-all` | Hunt for issues across ALL lanes in parallel |
| `/fix-all` | Fix ALL open issues across lanes in parallel |
| `/verify-fixes` | Verify all RESOLVED issues are actually fixed |

### Daily Workflow (3 Commands)

```bash
# 1. Hunt for new issues
/find-all

# 2. Fix what was found
/fix-all

# 3. Verify the fixes worked
/verify-fixes
```

That's it. The system handles parallelization, signaling, catalog updates, and git commits automatically.

### Running Specific Lanes

```bash
# Hunt only specific lanes
/find-all lanes G H I

# Fix only specific lanes
/fix-all lanes G H

# Verify specific lane
/verify-fixes G
```

---

## Before You Start: This Is YOUR System

**The lanes and search patterns are completely customizable.** The defaults are examples from software development - change them to fit YOUR business:

| Instead of This | Make It This |
|-----------------|--------------|
| Lane H: "Stubs & Placeholders" | Lane A: "Ad Campaign Issues" |
| Search for `TODO` in code | Search for broken UTM links |
| Look in `src/` directory | Look in your website files |

**To customize what a lane looks for:**
1. Open `.claude/agents/issue-hunters/IH-Lane-X.md`
2. Edit the "What to Look For" section
3. Change the grep/glob search patterns
4. Done - that's it!

See `CUSTOMIZATION_GUIDE.md` for more details.

---

## Quick Start

### Prerequisites

1. **Claude Code CLI** installed and configured
2. **Git** repository initialized
3. **Python 3** for sync scripts

### First-Time Setup

```bash
# Clone the repo (if not already)
git clone git@github.com:YOUR_USERNAME/project-arrow.git
cd project-arrow

# Install dependencies
pip install pyyaml

# Verify structure
ls .claude/agents/issue-hunters/  # Should show 22 hunters + orchestrator
ls .claude/agents/issue-fixers/   # Should show 22 fixers + orchestrator
ls issues/                        # Should show lane folders (D, E, G, H, ...)
```

---

## Running Issue Hunters

### Option 1: Run ALL Lanes (Recommended)

Copy and paste this EXACT prompt into Claude Code:

```
Read .claude/agents/issue-hunters/IH-Orchestrator.md

Run ALL 22 lanes (D-Z, excluding A,B,C,F) using the "Run ALL Protocol" with file-based signals:

1. Clean signals directory (rm -f LogBook/issue-hunting/signals/*.done) and reset state
2. Spawn ALL 22 hunters in ONE message (model: opus, run_in_background: true)
3. Poll LogBook/issue-hunting/signals/*.done until count = 22 (DO NOT use TaskOutput!)
4. Sync catalog: python3 tools/sync_catalog_stats.py
5. git commit catalog update and push
6. Report minimal summary
```

### Option 2: Run Specific Lanes

```
Read .claude/agents/issue-hunters/IH-Orchestrator.md

Run lanes D, E, G using the "Run ALL Protocol" pattern:

1. Clean signals directory
2. Reset only lanes D, E, G to pending
3. Spawn 3 hunters (model: opus, run_in_background: true)
4. Poll for 3 .done files
5. Sync catalog and push
```

### What Happens

1. **Orchestrator** cleans up previous signals
2. **22 agents** spawn in parallel (each gets 200k context)
3. **Agents hunt** for issues in their specialized lane
4. **Agents commit** their findings to `issues/{LANE}/`
5. **Agents signal** completion via `.done` files
6. **Orchestrator polls** signals directory
7. **Catalog syncs** when all complete
8. **Push to remote**

### Expected Duration

- 22 lanes in parallel: ~10-15 minutes
- Single lane: ~2-5 minutes

---

## Running Issue Fixers

### Option 1: Run ALL Lanes (Recommended)

Copy and paste this EXACT prompt into Claude Code:

```
Read .claude/agents/issue-fixers/IF-Orchestrator.md

Run the "Run ALL Protocol" with file-based signals:

1. Clean slate & check lane status:
   - rm -f LogBook/issue-fixing/signals/*.done
   - rm -f LogBook/issue-fixing/signals/*.status
   - Run Python script (Step 1) to:
     - Parse ISSUE_CATALOG.md "Lane Completion Status" section
     - Identify lanes at 100% (skip these)
     - Write lanes_to_run.txt with active lanes
     - Reset orchestrator-state.yaml

2. Spawn fixers for lanes that NEED WORK (skip 100% lanes):
   - Read LogBook/issue-fixing/signals/lanes_to_run.txt
   - Spawn ONE Task per lane in ONE message
   - model: opus
   - subagent_type: general-purpose
   - run_in_background: true
   - Each fixer reads its own IF-Lane-{LANE}.md

3. Poll for completion (DO NOT use TaskOutput!):
   - Get expected count from lanes_to_run.txt
   - Count LogBook/issue-fixing/signals/*.done until expected
   - Monitor .status files for COMPLEX lanes
   - Poll every 45 seconds

4. After all complete:
   - Sync catalog: python3 tools/sync_catalog_stats.py --verbose
   - git add ISSUE_CATALOG.md LogBook/
   - git commit and push

5. Cleanup:
   - rm -f LogBook/issue-fixing/signals/*.done
   - rm -f LogBook/issue-fixing/signals/*.status
   - rm -f LogBook/issue-fixing/signals/lanes_to_run.txt

6. Report: lanes run, lanes skipped (100%), signals received, catalog synced
```

### Option 2: Fix Specific Lanes

```
Read .claude/agents/issue-fixers/IF-Orchestrator.md

Fix only lanes E and G:

1. Clean signals
2. Spawn 2 fixers (E and G) with file signals
3. Poll for 2 .done files
4. Sync catalog and push
```

### What Happens

1. **Orchestrator** checks which lanes have open issues
2. **Skips** lanes that are already 100% complete
3. **Spawns fixers** for lanes with work to do
4. **Fixers work** autonomously (up to 5 issues each)
5. **Status files** show progress (STARTING, COMPLEX, COMPLETE)
6. **Done files** signal completion
7. **Catalog syncs** when all complete

### Expected Duration

- Full run (22 lanes): ~15-30 minutes
- Complex issues (EXTREME): May take longer
- Already at 100%: Skipped instantly

---

## Checking Status

### View Issue Catalog

```bash
cat ISSUE_CATALOG.md
```

Look at:
- **Summary Statistics** - Total, Resolved, Open, Progress
- **Lane Completion Status** - Per-lane percentages
- **Open Issues by Lane** - Detailed issue list

### View Orchestrator State

```bash
# Hunting state
cat LogBook/issue-hunting/orchestrator-state.yaml

# Fixing state
cat LogBook/issue-fixing/orchestrator-state.yaml
```

### View Signals (During Run)

```bash
# Watch completion signals
watch -n 5 'ls -la LogBook/issue-hunting/signals/'

# Or for fixing
watch -n 5 'ls -la LogBook/issue-fixing/signals/'
```

### Run Statistics

```bash
python3 tools/issue_stats.py
```

---

## Useful Commands

### Sync Catalog Manually

```bash
python3 tools/sync_catalog_stats.py --verbose
```

### Verify an Issue is Fixed

```bash
python3 tools/verify_issue.py E-01
```

### Add a New Issue Manually

```bash
python3 tools/add_issue.py E "Title of issue" --severity HIGH
```

### Validate YAML Files

```bash
python3 tools/schema_validator.py path/to/file.yaml
```

---

## Common Scenarios

### "I want to scan for new issues"

Use the hunting prompt above. Hunters will find new problems.

### "I want to fix existing issues"

Use the fixing prompt above. Fixers will resolve open issues.

### "A lane is stuck"

Check the status file:
```bash
cat LogBook/issue-fixing/signals/{LANE}.status
```

If it says BLOCKED, there's a permission issue. Run that lane manually.

### "I want to add a custom lane"

See CUSTOMIZATION_GUIDE.md for how to add new lanes.

### "Catalog is out of sync"

```bash
python3 tools/sync_catalog_stats.py --verbose
git add ISSUE_CATALOG.md
git commit -m "Sync catalog stats"
git push
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No .done files appearing" | Check if agents are running. Look at Claude Code output. |
| "Catalog not updating" | Run `python3 tools/sync_catalog_stats.py` manually |
| "Git conflicts" | Pull latest, resolve conflicts, re-run |
| "Permission denied" | Agent hit a file it can't modify. Check status file. |
| "Agent took too long" | EXTREME complexity issues take time. Check status file. |

---

## Lane Reference

| Lane | What It Hunts For |
|------|-------------------|
| D | Marketing infrastructure issues |
| E | Customer service problems |
| G | Ghost references (missing files/links) |
| H | Stubs and placeholders (TODOs) |
| I | Agent vs guideline contradictions |
| J | Rules that aren't enforced |
| K | Logging and audit trail issues |
| L | CI/CD and hook problems |
| M | Schema validation issues |
| N | Template compliance issues |
| O | SSOT and spec conflicts |
| P | Security vulnerabilities |
| Q | Planning consistency issues |
| R | TDD and test issues |
| S | Quality evaluation gaps |
| T | Project management issues |
| U | Versioning problems |
| V | Integration config issues |
| W | Test coverage gaps |
| X | Documentation issues |
| Y | Tooling interface issues |
| Z | Weird edge cases |

---

## File Locations

| What | Where |
|------|-------|
| Hunter agents | `.claude/agents/issue-hunters/` |
| Fixer agents | `.claude/agents/issue-fixers/` |
| Issue files | `issues/{LANE}/{LANE}-NN.md` |
| Catalog | `ISSUE_CATALOG.md` |
| Hunting state | `LogBook/issue-hunting/orchestrator-state.yaml` |
| Fixing state | `LogBook/issue-fixing/orchestrator-state.yaml` |
| Hunting signals | `LogBook/issue-hunting/signals/` |
| Fixing signals | `LogBook/issue-fixing/signals/` |
| Tools | `tools/` |
| Schemas | `PLANNING/schemas/` |

---

## Next Steps

1. **Customize Lanes** - Edit what each lane looks for (see CUSTOMIZATION_GUIDE.md)
2. **Add Guidelines** - Create `.claude/guidelines/` with your standards
3. **Integrate CI** - Add pre-commit hooks from `.pre-commit-config.yaml`
