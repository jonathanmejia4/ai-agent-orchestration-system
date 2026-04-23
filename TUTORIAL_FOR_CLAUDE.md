# Tutorial for Claude - Issue Hunting & Fixing System

> **Purpose:** This guide teaches Claude (AI assistants) how to operate the issue hunting and fixing framework.

---

## Available Slash Commands (Skills)

When a user types these commands, follow the corresponding protocol:

| Command | Action |
|---------|--------|
| `/find-all` | Read `.claude/commands/find-all.md` and execute the IH-Orchestrator Run ALL protocol |
| `/fix-all` | Read `.claude/commands/fix-all.md` and execute the IF-Orchestrator Run ALL protocol |
| `/verify-fixes` | Read `.claude/commands/verify-fixes.md` and execute the verification protocol |

### Arguments

Each command can take arguments:
- `/find-all lanes G H I` - Only run specific lanes
- `/fix-all status` - Check current signal status
- `/verify-fixes G` - Verify only lane G

---

## Important: Lanes Are Customizable

**The lane definitions and search patterns are NOT fixed.** The user can (and should) customize:
- What each lane searches for
- The grep/glob patterns used
- The file locations to scan
- The lane names and descriptions

When asked to hunt or fix, always read the lane agent file first - it contains the user's custom definitions for what to look for.

---

## System Overview

This is a **parallel issue management system** with two phases:

1. **Issue Hunting** - AI agents scan the codebase for problems
2. **Issue Fixing** - AI agents resolve discovered issues

**Key Principle:** File-based signals for coordination (NO TaskOutput - saves 99% context).

---

## Architecture

```
ai-agent-orchestration-system/
├── .claude/agents/
│   ├── issue-hunters/           # 26 hunter agents (A-Z)
│   │   ├── IH-Orchestrator.md   # Controls all hunters
│   │   ├── IH-Lane-A.md         # Lane A hunter
│   │   └── ...
│   └── issue-fixers/            # 26 fixer agents (A-Z)
│       ├── IF-Orchestrator.md   # Controls all fixers
│       ├── IF-Lane-A.md         # Lane A fixer
│       └── ...
├── issues/                       # Issue files by lane
│   ├── D/                        # Marketing issues
│   ├── E/                        # Customer service issues
│   └── ...
├── LogBook/
│   ├── issue-hunting/
│   │   ├── orchestrator-state.yaml
│   │   └── signals/              # .done files for completion
│   └── issue-fixing/
│       ├── orchestrator-state.yaml
│       └── signals/              # .done and .status files
├── ISSUE_CATALOG.md              # Central registry
├── tools/                        # Python scripts
└── PLANNING/schemas/             # YAML validation schemas
```

---

## Lane Specializations

| Lane | Focus Area | What to Look For |
|------|------------|------------------|
| A | API Contract Drift | OpenAPI/docs vs route implementation mismatches |
| B | Broken Flows | Broken navigation, dead-end user paths |
| C | Configuration Drift | Code vs `.env.example` / `config.yaml` mismatches |
| D | Marketing Infrastructure | Lead gen, campaigns, funnels |
| E | Customer Services | Support, GDPR, data protection |
| F | Frontend Accessibility | WCAG 2.1 AA violations in HTML/JSX/Vue |
| G | Ghost References | Missing files, broken links |
| H | Stubs & Placeholders | TODOs, NotImplemented, incomplete |
| I | Agent Contradictions | Guidelines vs implementation |
| J | Enforcement Gaps | Rules not enforced |
| K | LogBook Contracts | Logging, audit trails |
| L | CI/Hooks Automation | Pipelines, pre-commit hooks |
| M | Schema Issues | Validation, config drift |
| N | Template Issues | Deprecated patterns |
| O | Spec Conflicts | SSOT drift |
| P | Security & Policy | Vulnerabilities, access control |
| Q | Planner Contracts | Planning consistency |
| R | Builder TDD | Test-driven development |
| S | Critic Orchestrator | Quality evaluation |
| T | PM Governance | Project management |
| U | Versioning | Changelogs, versions |
| V | Integration Config | External services |
| W | Tests & Validation | Test coverage |
| X | Docs & Reference | Documentation |
| Y | Tooling Contracts | CLI consistency |
| Z | Weird Edges | High-impact edge cases |

---

## How to Run Issue Hunting

### As an Orchestrator

If you are the IH-Orchestrator, follow these steps:

#### 1. Read Your Agent File
```
Read .claude/agents/issue-hunters/IH-Orchestrator.md
```

#### 2. Clean Slate
```bash
rm -f LogBook/issue-hunting/signals/*.done
```

#### 3. Reset State
```python
# Reset orchestrator-state.yaml to running state
```

#### 4. Spawn ALL 26 Hunters (ONE message)
```
For EACH lane A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z:
  Task:
    description: "Hunt Lane {X}"
    model: opus
    subagent_type: general-purpose
    run_in_background: true
    prompt: |
      Read .claude/agents/issue-hunters/IH-Lane-{X}.md
      Hunt for issues, create files, commit, touch .done file
```

#### 5. Poll for Completion (DO NOT USE TaskOutput!)
```bash
while true; do
    count=$(ls LogBook/issue-hunting/signals/*.done 2>/dev/null | wc -l)
    echo "Completed: $count/26"
    [ "$count" -ge 26 ] && break
    sleep 45
done
```

#### 6. Sync & Push
```bash
python3 tools/sync_catalog_stats.py
git add ISSUE_CATALOG.md
git commit -m "Issue hunting complete"
git push
```

---

### As a Lane Hunter

If you are IH-Lane-{X}, follow these steps:

#### 1. Read Your Lane Definition
```
Read .claude/agents/issue-hunters/IH-Lane-{X}.md
```

#### 2. Scan the Codebase
Search for issues matching your lane's specialization using:
- Grep for patterns (TODOs, FIXME, etc.)
- Glob for file patterns
- Read to examine suspicious files

#### 3. Create Issue Files
For each issue found, create `issues/{X}/{X}-NN.md`:
```markdown
# {X}-NN: Brief title

## Status
OPEN

## Severity
LOW | MEDIUM | HIGH | CRITICAL

## Description
What is the problem?

## Location
- `path/to/file.py:123`

## Evidence
```code
The problematic code
```

## Suggested Fix
How to resolve it.

## Type Tags
- tag1
- tag2
```

#### 4. Commit Your Work
```bash
git add issues/{X}/
git commit -m "Lane {X} hunting: found N issues

{X}-01: Brief description
{X}-02: Brief description
...
"
```

#### 5. Signal Completion (CRITICAL!)
```bash
touch LogBook/issue-hunting/signals/{X}.done
```

---

## How to Run Issue Fixing

### As an Orchestrator

If you are the IF-Orchestrator:

#### 1. Read Your Agent File
```
Read .claude/agents/issue-fixers/IF-Orchestrator.md
```

#### 2. Clean Slate & Check Lanes
```bash
rm -f LogBook/issue-fixing/signals/*.done
rm -f LogBook/issue-fixing/signals/*.status
```

Parse ISSUE_CATALOG.md to find which lanes are at 100% (skip those).

#### 3. Spawn Fixers for Active Lanes
```
For EACH lane that is NOT at 100%:
  Task:
    description: "Fix Lane {X}"
    model: opus
    subagent_type: general-purpose
    run_in_background: true
    prompt: |
      Read .claude/agents/issue-fixers/IF-Lane-{X}.md
      Fix issues, mark resolved, commit, touch .done file
```

#### 4. Poll for Completion
```bash
while true; do
    done_count=$(ls LogBook/issue-fixing/signals/*.done 2>/dev/null | wc -l)
    echo "Done: $done_count/$expected"
    [ "$done_count" -ge "$expected" ] && break
    sleep 45
done
```

#### 5. Sync & Push
```bash
python3 tools/sync_catalog_stats.py --verbose
git add ISSUE_CATALOG.md LogBook/
git commit -m "Issue fixing complete"
git push
```

---

### As a Lane Fixer

If you are IF-Lane-{X}:

#### 1. Read Your Lane Definition
```
Read .claude/agents/issue-fixers/IF-Lane-{X}.md
```

#### 2. Find Open Issues
Check ISSUE_CATALOG.md "Open Issues by Lane" section for Lane {X}.

#### 3. Write Status Updates
```bash
echo "STARTING" > LogBook/issue-fixing/signals/{X}.status
```

#### 4. Assess Complexity Before Each Fix
- **LOW**: Quick fix, <10 lines
- **MEDIUM**: Moderate, 10-50 lines
- **HIGH**: Significant, multiple files
- **EXTREME**: Major refactor - FIX ONLY THIS ONE

If EXTREME, update status:
```bash
echo "COMPLEX: {X}-NN (EXTREME - reason)" > LogBook/issue-fixing/signals/{X}.status
```

#### 5. Fix Issues (Max 5, unless EXTREME)
- Make the actual code changes
- Test your changes work
- Update issue file status to RESOLVED

#### 6. Commit
```bash
git add .
git commit -m "Lane {X} fixing: resolved N issues

{X}-01: Description of fix
{X}-02: Description of fix
"
```

#### 7. Signal Completion
```bash
echo "COMPLETE" > LogBook/issue-fixing/signals/{X}.status
touch LogBook/issue-fixing/signals/{X}.done
```

---

## Critical Rules

### DO
- Always read your agent file first
- Use file signals (.done files) for completion
- Commit your own work (agents are autonomous)
- Update issue status when resolved
- Poll signals directory for completion status

### DO NOT
- Never use TaskOutput (blows context from 3k to 265k tokens)
- Never commit stubs, placeholders, or partial fixes
- Never skip the .done file signal
- Never fix issues from other lanes
- Never exceed 5 issues per run (1 for EXTREME)

---

## File Signal Pattern

**Why?** TaskOutput returns full agent transcripts (~50k tokens each). With 26 agents, that's 1.3M tokens. File signals use ~3k total.

**How it works:**
1. Orchestrator spawns agents with `run_in_background: true`
2. Agents do their work autonomously
3. Agents write `.done` file when finished
4. Orchestrator polls directory for `.done` file count
5. When count equals expected, all done

---

## Tools Reference

| Tool | Purpose |
|------|---------|
| `sync_catalog_stats.py` | Update ISSUE_CATALOG.md from issue files |
| `verify_issue.py` | Verify a single issue is resolved |
| `batch_verify.py` | Verify multiple issues |
| `issue_stats.py` | Generate statistics |
| `add_issue.py` | Create new issue file |
| `schema_validator.py` | Validate YAML files |

---

## State Files

| File | Purpose |
|------|---------|
| `LogBook/issue-hunting/orchestrator-state.yaml` | Hunter orchestrator state |
| `LogBook/issue-fixing/orchestrator-state.yaml` | Fixer orchestrator state |
| `ISSUE_CATALOG.md` | Central issue registry |

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Permission denied | Stop, write BLOCKED to status, create .done |
| No issues found | Mark complete with 0 issues |
| EXTREME complexity | Fix only that issue, skip rest |
| Git conflict | Resolve conflict, re-commit |

---

## Summary

1. **Orchestrator** spawns all lane agents in parallel
2. **Lane agents** work autonomously (read, fix, commit, signal)
3. **File signals** (.done files) indicate completion
4. **Orchestrator** polls signals, syncs catalog, pushes
5. **No TaskOutput** = 99% context savings
