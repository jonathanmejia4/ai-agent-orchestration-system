# Issue Hunter Sub-Agents

> **Purpose:** Specialized agents for parallel issue hunting across 22 lanes (D-Z)
> **Location:** `.claude/agents/issue-hunters/`
> **Global Rules:** `PLANNING/prompts/issue-hunting/GLOBAL_CONTRACT.md`

---

## Overview

Each agent hunts for issues in ONE specific lane. Agents are designed to run in parallel (3 at a time recommended).

## Agents

| Agent | Lane | Specialization |
|-------|------|----------------|
| IH-Lane-D | D | Marketing Infrastructure & Lead Generation |
| IH-Lane-E | E | Customer Services & Data Protection |
| IH-Lane-G | G | Ghost References & Missing Artifacts |
| IH-Lane-H | H | Stubs & Placeholders |
| IH-Lane-I | I | Agent ↔ Guideline Contradictions |
| IH-Lane-J | J | Enforcement Gaps |
| IH-Lane-K | K | LogBook Contracts & Write Discipline |
| IH-Lane-L | L | CI/Hooks Automation |
| IH-Lane-M | M | Schema Issues |
| IH-Lane-N | N | Template Issues |
| IH-Lane-O | O | Spec Conflicts / SSOT Drift |
| IH-Lane-P | P | Security & Policy |
| IH-Lane-Q | Q | Planner Contracts |
| IH-Lane-R | R | Builder TDD & Idempotence |
| IH-Lane-S | S | Critic Orchestrator |
| IH-Lane-T | T | PM Governance |
| IH-Lane-U | U | Versioning & Changelogs |
| IH-Lane-V | V | Integration Config |
| IH-Lane-W | W | Tests & Validation |
| IH-Lane-X | X | Docs Site & Reference |
| IH-Lane-Y | Y | Tooling Interface Contracts |
| IH-Lane-Z | Z | Weird Edges & High Impact |

## Invocation

```
@IH-Lane-E Hunt for issues
```

## Rules (All Agents)

1. **10 issues maximum** per run
2. **Failure allowed** - finding 0 is acceptable, do not fabricate
3. **Evidence required** - file:line + quoted snippet
4. **Dedup mandatory** - check existing issues first
5. **Output** - create `issues/<LANE>/<LANE>-<NN>.md` files

## After Any Hunt

```bash
python3 tools/sync_catalog_stats.py
```

## Parallel Execution

Run up to 3 hunters simultaneously:
```
Instance 1: @IH-Lane-E, @IH-Lane-G, @IH-Lane-H
Instance 2: @IH-Lane-I, @IH-Lane-J, @IH-Lane-K
...
```

---

**Global Contract:** `PLANNING/prompts/issue-hunting/GLOBAL_CONTRACT.md`
**Lane Prompts:** `PLANNING/prompts/issue-hunting/lanes/LANE_<X>.md`
