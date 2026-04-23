# Agent Boundaries Reference (SSOT)

**Version:** 1.0.1
**Status:** Authoritative
**Last Updated:** 2026-01-05
**Purpose:** Single Source of Truth for all agent write boundaries, communication protocols, and handoff procedures.

> ⚠️ **This document is AUTHORITATIVE.** If any other document contradicts this reference, THIS document takes precedence. Report contradictions to PM for resolution.

---

## 1. Write Boundaries by Agent

### 1.1 PM (Project Manager)

**CAN Write To:**
| Path | Purpose |
|------|---------|
| `LogBook/pm/` | PM activity logs, STATE.md, decisions |
| `LogBook/pm/escalations/` | Escalation records from all agents |
| `PLANNING/**` | All planning documents, policies, schemas |
| `.claude/agents/` | Agent specifications |
| `.claude/guidelines/` | Guideline documents |
| `archives/golden/` | Approved templates |
| `archives/bad/` | Rejected templates |
| `integration/config/` | Integration configurations |
| `ISSUE_CATALOG.md` | Issue tracking |

**CANNOT Write To:**
- Source code (tasks/, src/, lib/)
- Test implementations (tests/)
- Template content (templates/**/content/)

---

### 1.2 Planner

**CAN Write To:**
| Path | Purpose |
|------|---------|
| `.task/plan_metadata.yaml` | Plan output metadata |
| `.task/checkpoint_plan.yaml` | Checkpoint plan structure |
| `.task/deps.yaml` | Dependency graph |
| `.task/wiring.yaml` | Wiring configuration |
| `LogBook/planner/**` | Plan outputs (plans.yaml, planning_log.yaml, WO_QUEUE.yaml, STATE.md, etc.) |

**CANNOT Write To:**
- `PLANNING/**` (PM-exclusive)
- `LogBook/pm/**` (PM-exclusive)
- Source code
- `.claude/agents/` or `.claude/guidelines/`

> **Rationale:** Planner outputs go to `.task/` directory which is the working area for task-related artifacts. PLANNING/ is PM-owned for governance documents.

---

### 1.3 Builder

**CAN Write To:**
| Path | Purpose |
|------|---------|
| `tasks/<assigned-task-id>/**` | Task implementation (scoped) |
| `tests/<assigned-task-id>/**` | Task tests (scoped) |
| `.task/` | Build artifacts |
| `LogBook/progress/tasks/**` | Task status files |
| `LogBook/builder/**` | Builder activity logging, state, progress |
| `LogBook/previews/**` | Preview files for PM approval |

**CANNOT Write To:**
- Any task outside assigned scope
- `PLANNING/**`
- `LogBook/pm/**`
- `.claude/`

> **Scope Rule:** Builder can ONLY modify files within the task ID specified in the current work order.

---

### 1.4 Critic (All Specialist Agents)

**CAN Write To:**
| Path | Purpose |
|------|---------|
| `LogBook/critic/**` | All Critic outputs |
| `LogBook/critic/plan-audits/` | PlanAuditor outputs |
| `LogBook/critic/verdicts/` | Verdict files |
| `.task/verdict.yaml` | Current task verdict |

**CANNOT Write To:**
- Source code (read-only access)
- `PLANNING/**`
- `LogBook/pm/**`
- `tasks/**` (read-only)

---

## 2. Communication Protocols

### 2.1 Work Order Format

**Standard:** YAML format (`.yaml` extension)

```yaml
# work_order.yaml
id: WO-XXXX
title: "Work order title"
issuer: Project-Manager  # PM is always issuer
assignee: Builder|Planner|Critic
priority: critical|high|medium|low
task_id: "task-xxx"  # If applicable
created_at: "2025-12-25T00:00:00Z"
deadline: "2025-12-26T00:00:00Z"
description: |
  Detailed work description
acceptance_criteria:
  - Criterion 1
  - Criterion 2
```

> **Note:** Markdown (.md) work orders are deprecated. Use YAML for machine-parseable work orders.

---

### 2.2 Review Request Workflow

**Two-Step Process:**
1. **Builder writes status file** (for audit trail)
2. **PM invokes Critic** (for execution)

**Step 1: Builder writes review request file**
```yaml
# Located at: LogBook/progress/tasks/<task-id>/status.yaml
task_id: "task-xxx"
status: "IMPLEMENTATION_COMPLETE"
requested_by: Builder
requested_at: "2025-12-25T12:00:00Z"
artifacts:
  - path: "tasks/task-xxx/implementation.py"
  - path: "tests/test_task_xxx.py"
```

**Step 2: PM invokes Critic**
PM reads the status file and invokes `@Critic-Orchestrator` with task details.
Critic writes verdict to `LogBook/critic/verdicts/VER-<task-id>.yaml`.

---

### 2.3 Agent Handoff Protocol

#### Planner → Builder (via PM)
```
1. Planner completes plan → writes to .task/checkpoint_plan.yaml
2. Planner signals completion → LogBook/planner/plans.yaml (appends plan entry)
3. PM reviews plan → invokes Critic-PlanAuditor
4. PlanAuditor approves → PM issues work order to Builder
5. Builder receives work order → begins execution
```

#### Builder → Critic (via PM)
```
1. Builder completes task → writes to tasks/<task-id>/
2. Builder signals completion → LogBook/progress/tasks/<task-id>/status.yaml
3. PM detects completion → invokes Critic for review
4. Critic reviews → writes verdict to LogBook/critic/verdicts/
5. PM evaluates verdict → approves/rejects/requests changes
```

> **Rule:** All cross-agent handoffs are PM-mediated. Agents do NOT communicate directly.

---

## 3. Critic System Clarification

### Agent Count
- **3 Core Agents:** PM, Planner, Builder
- **Critic Subsystem:** 1 Orchestrator + 7 Dimension Specialists + 2 Special Critics (PlanAuditor, FixVerifier) = 10 Critic-related agents
- **Total System:** 3 core + 10 Critic = 13 agent specifications

### Critic Dimension Specialists
1. Critic-Dependencies (Dimension 1: Dependency Integrity)
2. Critic-Effort (Dimension 2: Effort Accuracy)
3. Critic-ExecutionReady (Dimension 3: Execution Readiness)
4. Critic-SpecFit (Dimension 4: Spec Fit)
5. Critic-Verification (Dimension 5: Verification Quality)
6. Critic-SecurityPolicy (Dimension 6: Security & Policy Compliance)
7. Critic-ACL (Dimension 7: Anti-Corruption Layer Compliance)

### Other Critic Agents (Non-Dimension)
- Critic-PlanAuditor (plan-specific review)
- Critic-FixVerifier (fix verification)

---

## 4. Critic .task/ Permissions

**Clarification:** Critic CAN write to `.task/verdict.yaml` for the current task under review. This is the ONLY .task/ file Critic may modify.

| File | Critic Permission |
|------|-------------------|
| `.task/verdict.yaml` | WRITE (current task only) |
| `.task/plan_metadata.yaml` | READ ONLY |
| `.task/checkpoint_plan.yaml` | READ ONLY |
| `.task/*.yaml` (other) | READ ONLY |

---

## 5. Cross-Reference Resolution

When documents conflict:
1. This document (AGENT_BOUNDARIES_REFERENCE.md) is authoritative
2. PM_AGENT_SPECIFICATION.md is authoritative for PM behavior
3. Individual agent specs defer to this reference for boundaries
4. Guidelines defer to agent specs for agent-specific behavior

---

## Related Documents

- [Agent Guardrails](agent-guardrails.md)
- [Agent Operating Principles](agent-operating-principles.md)
- [PM Write Boundaries](pm-write-boundaries.md)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.1 | 2026-01-05 | Fixed I-61 (PM LogBook scope), I-62 (deps.yaml naming), I-64 (Critic names), I-65 (Builder LogBook path) |
| 1.0.0 | 2025-12-25 | Initial SSOT creation to resolve Lane I contradictions |
