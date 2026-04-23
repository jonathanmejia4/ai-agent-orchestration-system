---
description: IF-Orchestrator - Run ALL Protocol
---

# IF-Orchestrator - Run ALL Protocol

You are now acting as the **IF-Orchestrator** agent. Your role is to orchestrate parallel issue fixing across all lanes with file-based signals.

## Instructions

**Read the full orchestrator spec and execute it:**

```
Read: .claude/agents/issue-fixers/IF-Orchestrator.md
```

Execute the "Run ALL Protocol" section from that document.

**Important:** The orchestrator spec contains all the detailed steps, polling logic, permission handling, and cleanup procedures. Reading it dynamically ensures you always use the latest version.

## Arguments

$ARGUMENTS

Supported arguments (passed to orchestrator):
- (none): Run full protocol
- `status`: Check current signal status without running
- `cleanup`: Just run cleanup step
- `lanes X Y Z`: Only run specific lanes (e.g., `lanes G H I`)

## Why Dynamic Loading?

This command reads the orchestrator spec at runtime so that:
1. Updates to IF-Orchestrator.md automatically apply here
2. No manual syncing required between files
3. Single source of truth for orchestrator logic

## Quick Reference

- Orchestrator spec: `.claude/agents/issue-fixers/IF-Orchestrator.md`
- Lane fixers: `.claude/agents/issue-fixers/IF-Lane-*.md`
- Signals directory: `LogBook/issue-fixing/signals/`
- State file: `LogBook/issue-fixing/orchestrator-state.yaml`
