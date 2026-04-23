# Rollback Procedures Guidelines
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** CRITICAL - Recovery Procedures
**Status:** PLANNED - Infrastructure not yet implemented

## Overview

This document defines the **planned** rollback procedures for all pipeline stages. Rollbacks are triggered when stage gates fail or critical errors occur.

**IMPORTANT:** Most rollback infrastructure described in this document is not yet implemented:
- `LogBook/pm/rollbacks/` directory does not exist
- `.task/base/` and `.task/regions/` backup directories do not exist
- `tools/task_rollback.py` does not exist
- Automated rollback execution is not implemented

Current rollback process is **manual** - developers must manually revert changes and update LogBook entries.

## Rollback Principles

1. **Data Preservation:** Never lose user work
2. **Atomic Operations:** Rollback completely or not at all
3. **Audit Trail:** Log all rollback events
4. **Notification:** Alert relevant parties

## Stage-Specific Rollbacks

### Stage 1: STRUCTURAL_GENERATION → PLANNING

**Trigger Conditions:**
- Template not found
- Schema validation failed
- Wiring configuration invalid

**Rollback Steps:**
1. Delete generated structural files
2. Preserve `.task/checkpoint_plan.yaml`
3. Log failure reason
4. Notify Planner for plan revision

**Preserved:**
- Action plan
- Work order
- Dependency graph

**Deleted:**
- Generated source files
- Wiring Section 2

---

### Stage 2: PLUGIN_ATTACHMENT → STRUCTURAL_GENERATION

**Trigger Conditions:**
- Plugin incompatibility detected
- Extension point validation failed
- Variant composition invalid

**Rollback Steps:**
1. Remove attached plugins
2. Restore pre-plugin file state
3. Log incompatibility details
4. Notify Planner for plugin revision

**Preserved:**
- Structural generation output
- Wiring Section 1

**Deleted:**
- Plugin attachments
- Wiring Section 2 & 3

---

### Stage 3: BEHAVIORAL_GENERATION → PLUGIN_ATTACHMENT

**Trigger Conditions:**
- Idempotence check failed
- Protected region corruption
- Dependency order violation

**Rollback Steps (PLANNED - not yet automated):**
1. Restore pre-behavioral files from `.task/base/` (directory not yet created)
2. Preserve protected regions from `.task/regions/` (directory not yet created)
3. Log generation failure
4. Notify Builder

**Preserved:**
- Plugin configuration
- Protected regions
- Base versions

**Deleted:**
- Behavioral code

---

### Stage 4: TESTING → IMPLEMENTATION

**Trigger Conditions:**
- Unit tests failed
- Contract tests failed
- Security scan critical findings

**Rollback Steps:**
1. Mark tests as failed
2. Preserve all source code
3. Generate failure report
4. Notify Builder with specific failures

**Preserved:**
- All source code
- Test files
- Previous test results

**Deleted:**
- Nothing (code needs fixing, not removal)

---

### Stage 5: REVIEW → IMPLEMENTATION

**Trigger Conditions:**
- Critic rejected task
- Critical issues found

**Rollback Steps:**
1. Record rejection verdict
2. Preserve all code
3. Create issue list for Builder
4. Notify Builder with required changes

**Preserved:**
- All source code
- Review comments
- Previous verdicts

**Deleted:**
- Nothing

---

### Stage 6: PROMOTION → REVIEW

**Trigger Conditions:**
- Merge conflict
- CI pipeline failed
- Post-deploy smoke test failed

**Rollback Steps:**
1. Revert merge (if merged)
2. Restore main branch
3. Log promotion failure
4. Notify PM and Builder

**Preserved:**
- Alt-branch with all work
- Review verdict

**Deleted:**
- Failed merge commit (if applicable)

---

## Emergency Rollback

For critical production issues (PLANNED - not yet implemented):

```bash
# Full task rollback (tool does not yet exist)
# tools/task_rollback.py --task-id <id> --to-stage <stage>

# With audit (tool does not yet exist)
# tools/task_rollback.py --task-id <id> --to-stage PLANNING --reason "Critical bug"
```

**Current workaround:** Manual git revert and LogBook entry update

## Rollback Audit

All rollbacks SHOULD BE logged to (directory not yet created):
```yaml
# LogBook/pm/rollbacks/<timestamp>-<task-id>.yaml (planned location)
rollback:
  task_id: "task-2.3"
  timestamp: "2025-12-25T14:30:00Z"
  from_stage: "TESTING"
  to_stage: "IMPLEMENTATION"
  reason: "Unit tests failed"
  triggered_by: "stage_gate"
  agent: "Builder"
  files_affected:
    - preserved: ["src/auth/*"]
    - deleted: []
  duration_seconds: 5
```

**Current practice:** Rollback events logged to main LogBook entries, not separate rollbacks/ directory

## Rollback Limits

| Stage | Max Rollbacks | Action on Exceed |
|-------|---------------|------------------|
| Stage 1-2 | 3 | Escalate to PM |
| Stage 3-4 | 5 | Escalate to PM |
| Stage 5-6 | 2 | Escalate to User |

## Related Documents
- PLANNING/TASK_LIFECYCLE_STAGES.md
- PLANNING/GOVERNANCE_MODEL.md
- tools/task_rollback.py (not yet implemented)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
