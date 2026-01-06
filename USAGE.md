# Usage Guide

## Quick Start

This system demonstrates parallel AI agent orchestration for automated issue resolution.

## Running the System

### Step 1: Hunt for Issues

Spawn 21 specialized hunter agents to scan for problems:

```bash
@IH-Orchestrator Run ALL
```

**What happens:**
- 21 hunter agents execute in parallel
- Each scans specific problem domain (Lane E-Z)
- Results cataloged in issue registry
- Takes ~15 minutes to complete

### Step 2: Fix Issues

Spawn 21 specialized fixer agents to resolve problems:

```bash
@IF-Orchestrator Run ALL
```

**What happens:**
- 21 fixer agents execute in parallel
- Each fixes up to 5 issues (oldest first)
- Agents commit their own work
- Takes ~15 minutes to complete

### Step 3: Verify and Sync

Verify fixes and update statistics:

```bash
python tools/verify_issue.py <ISSUE_ID>
python tools/sync_catalog_stats.py --verbose
```

## Output Locations

- **Issue catalog**: `SAF_ISSUE_CATALOG.md`
- **Verification evidence**: `LogBook/verification/evidence/`
- **Orchestrator states**: `LogBook/issue-hunting/orchestrator-state.yaml`

## Architecture Highlights

- **File-based signaling**: 98.9% context reduction (3k vs 265k tokens)
- **Parallel execution**: 21 simultaneous context windows
- **Autonomous agents**: Each agent commits its own work
- **Verified results**: 1,352 issues resolved, 91.9% completion rate

## Extending the System

To add a new lane (problem domain):

1. Create `IH-Lane-X.md` (hunter agent)
2. Create `IF-Lane-X.md` (fixer agent)
3. Update orchestrator lane lists
4. Run orchestrators to execute

## Real-World Performance

- **Traditional approach**: 118 issues x 30 min = 59 hours
- **With orchestration**: 118 issues / 21 lanes = 1.4 hours
- **Productivity gain**: 42x faster

---

For detailed architecture explanation, see [ARCHITECTURE.md](ARCHITECTURE.md).
