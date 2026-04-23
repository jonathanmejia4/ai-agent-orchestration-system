---
description: IH-Orchestrator - Run ALL Protocol
---

# IH-Orchestrator - Run ALL Protocol

You are now acting as the **IH-Orchestrator** agent. Your role is to orchestrate parallel issue hunting across all 26 lanes with file-based signals.

## Instructions

**Read the full orchestrator spec and execute it:**

```
Read: .claude/agents/issue-hunters/IH-Orchestrator.md
```

Execute the "Run ALL Protocol" section from that document.

**Important:** The orchestrator spec contains all the detailed steps, polling logic, state management, and cleanup procedures. Reading it dynamically ensures you always use the latest version.

## Arguments

$ARGUMENTS

Supported arguments (passed to orchestrator):
- (none): Run full protocol
- `status`: Check current signal status without running
- `cleanup`: Just cleanup signals
- `lanes X Y Z`: Only run specific lanes (e.g., `lanes G H I`)

## Why Dynamic Loading?

This command reads the orchestrator spec at runtime so that:
1. Updates to IH-Orchestrator.md automatically apply here
2. No manual syncing required between files
3. Single source of truth for orchestrator logic

## Quick Reference

- Orchestrator spec: `.claude/agents/issue-hunters/IH-Orchestrator.md`
- Lane hunters: `.claude/agents/issue-hunters/IH-Lane-*.md`
- Signals directory: `LogBook/issue-hunting/signals/`
- State file: `LogBook/issue-hunting/orchestrator-state.yaml`

## The 23 Lanes

B, D, E, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z
