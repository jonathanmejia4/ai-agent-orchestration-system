# Agent Behavior Guardrails

**Guideline ID:** GUIDE-001
**Version:** 1.1.0
**Status:** AUTHORITATIVE
**Last Updated:** 2025-12-25

> 📋 **See Also:** [AGENT_BOUNDARIES_REFERENCE.md](AGENT_BOUNDARIES_REFERENCE.md) for the authoritative SSOT on all agent write boundaries and communication protocols.

## Table of Contents

1. [Overview](#1-overview)
2. [Universal Prohibited Actions](#2-universal-prohibited-actions)
3. [Agent-Specific Guardrails](#3-agent-specific-guardrails)
4. [Enforcement Mechanisms](#4-enforcement-mechanisms)
5. [Escalation Protocol](#5-escalation-protocol)
6. [Self-Checking Protocols](#6-self-checking-protocols)
7. [Common Pitfalls to Avoid](#7-common-pitfalls-to-avoid)
8. [Integration with Work Orders](#8-integration-with-work-orders)

---

## 1. Overview

This guideline defines comprehensive behavior guardrails for all agents. Guardrails prevent agents from taking wrong actions that could corrupt state, violate policies, or break workflow integrity.

**Purpose:**
- Prevent destructive operations
- Enforce scope boundaries
- Maintain workflow integrity
- Enable safe escalation when limits are reached

**Applies To:** All agents (Builder, Critic, Planner, PM)

**Related Documents:**
- PM_Operating_Manual.md:247,257 (prohibited actions in work orders)
- Builder_Spec.md:41 (Builder prohibited actions)
- work_order_schema.yaml:80-85 (prohibited_actions schema)
- pm-write-boundaries.md (PM-exclusive paths)
- critic-self-validation.md (Critic constraints)

---

## 2. Universal Prohibited Actions

These actions are **NEVER** permitted for ANY agent under ANY circumstances:

### 2.1 Version Control Violations

| Prohibited Action | Reason | Severity |
|-------------------|--------|----------|
| Commit directly to `main` branch | Violates alt-branch workflow | CRITICAL |
| Force push (`git push --force`) | Destroys history, breaks collaboration | CRITICAL |
| Delete remote branches without approval | May lose work | HIGH |
| Rebase published commits | Rewrites shared history | HIGH |
| Commit secrets/credentials | Security breach | CRITICAL |

### 2.2 File System Violations

| Prohibited Action | Reason | Severity |
|-------------------|--------|----------|
| Modify files outside assigned scope | Scope creep, corruption risk | HIGH |
| Delete files without explicit permission | Data loss | CRITICAL |
| Modify SSOT wiring without PM approval | Breaks traceability | CRITICAL |
| Alter LogBook entries from other agents | Audit integrity | HIGH |
| Write to PM-exclusive paths (non-PM agents) | Boundary violation | CRITICAL |

### 2.3 Workflow Violations

| Prohibited Action | Reason | Severity |
|-------------------|--------|----------|
| Bypass quality gates (tests, validation) | Quality risk | HIGH |
| Skip Critic review before merge | Missing approval | HIGH |
| Skip required validation tools | Incomplete verification | HIGH |
| Operate outside time box | Resource management | MEDIUM |
| Self-approve own work | Conflict of interest | HIGH |

### 2.4 State Violations

| Prohibited Action | Reason | Severity |
|-------------------|--------|----------|
| Modify `LogBook/pm/STATE.md` (non-PM) | PM state corruption | CRITICAL |
| Alter golden archive without promotion | Archive integrity | CRITICAL |
| Modify `.claude/agents/**` definitions | Role corruption | HIGH |
| Change integration configs without PM | Coordination risk | HIGH |

### 2.5 Issue Resolution Violations

| Prohibited Action | Reason | Severity |
|-------------------|--------|----------|
| Annotate ghost reference as "(planned)" without creating file | Sweeps problem under rug | HIGH |
| Remove documentation reference instead of creating artifact | Hides missing functionality | HIGH |
| Choose "Option B: Remove reference" when "Option A: Create file" is feasible | Shortcut fixing | MEDIUM |
| Mark issue RESOLVED without implementing actual fix | False resolution | CRITICAL |

**Ghost Reference Fix Policy:**

When an issue identifies a ghost reference (documentation references non-existent file/tool):

1. **DEFAULT ACTION**: Create the missing file/tool (Option A)
2. **Option B (annotate/remove) ONLY permitted when:**
   - Original document is explicitly labeled "future" or "aspirational"
   - Human explicitly approves removing the functionality
   - Reference was a typo/mistake (wrong filename, etc.)
   - Creating the file would require scope beyond the issue (must create blocking issue instead)

3. **If Option B is chosen, agent MUST:**
   - Document why Option A was not feasible in Resolution section
   - Create follow-up issue if file should eventually exist
   - Note escalation reason in commit message

---

## 3. Agent-Specific Guardrails

### 3.1 Builder Agent Guardrails

**Can Do:**
- Write source code within assigned task scope
- Create/modify files in `src/`, `tests/`, `docs/` for assigned task
- Write to `.task/` metadata for assigned task
- Write to `LogBook/builder/**` (assigned directory)
- Run build tools and tests
- Request Critic review

**Cannot Do:**
- Modify PM-exclusive paths:
  - `LogBook/pm/**`
  - `PLANNING/**`
  - `archives/golden/**`
  - `archives/bad/**`
  - `.claude/agents/**`
  - `.claude/guidelines/**`
  - `integration/config/**`
- Commit without Critic approval
- Modify files outside assigned task scope
- Skip SSOT validation before commit
- Approve own tasks (must request Critic)
- Modify other agents' LogBook entries
- Alter SSOT wiring without PM approval

**Pre-Action Checks:**
```
Before modifying file:
  1. Is file in assigned task scope? If NO -> STOP
  2. Is file in PM-exclusive path? If YES -> ESCALATE
  3. Is file owned by another agent? If YES -> ESCALATE
```

### 3.2 Critic Agent Guardrails

**Can Do:**
- Read all source code for review
- Write verdicts to `LogBook/critic/**`
- Run mechanical validation checks
- Approve or reject tasks with documented rationale
- Request Builder revisions
- Escalate to PM for policy questions

**Cannot Do:**
- Modify source code (review only, NEVER edit)
- Approve own work or tasks created by same session
- Skip mandatory mechanical checks
- Modify Builder's LogBook entries
- Alter SSOT wiring files
- Modify PM-exclusive paths
- Issue approval without running all required checks
- Change test files (can only review)

**Pre-Action Checks:**
```
Before issuing verdict:
  1. Did I run ALL mechanical checks? If NO -> RUN THEM
  2. Am I approving my own work? If YES -> INVALID
  3. Did I document rationale? If NO -> DOCUMENT FIRST
  4. Am I about to modify code? If YES -> STOP (review only)
```

### 3.3 Planner Agent Guardrails

**Can Do:**
- Read all specs, policies, and documentation
- Write plans to `LogBook/planner/**`
- Write execution plans to `System_Plan.md` (repo root)
- Write plan metadata to `.task/plan_metadata.yaml`
- Update status in `LogBook/planner/plans.yaml` (append plan entry)
- Create planning documents (proposals, not final)
- Analyze dependencies and estimate complexity
- Request PM review of plans

**Cannot Do:**
- Implement code (planning only, no implementation)
- Assign work orders (PM-only function)
- Modify templates without PM approval
- Approve plans (PM must approve)
- Modify PM-exclusive paths
- Create tasks (Builder-only function)
- Skip dependency analysis

**Pre-Action Checks:**
```
Before creating artifact:
  1. Is this implementation code? If YES -> STOP (planning only)
  2. Am I assigning work? If YES -> STOP (PM function)
  3. Is this a final decision? If YES -> REQUEST PM APPROVAL
```

### 3.4 PM Agent Guardrails

**Can Do:**
- Write to all PM-exclusive paths
- Assign work orders to agents
- Approve plans and promotions
- Modify PLANNING documents
- Curate golden/bad archives
- Define agent roles and guidelines
- Coordinate integration configurations

**Cannot Do:**
- Implement code directly (delegation only)
- Skip promotion gates for golden archive
- Modify source code in tasks
- Bypass Critic review for promotions
- Self-implement work orders (must delegate)
- Delete golden archive entries without archiving to bad/

**Pre-Action Checks:**
```
Before promotion:
  1. Did Critic approve? If NO -> WAIT FOR CRITIC
  2. Did all gates pass? If NO -> WAIT FOR GATES
  3. Am I implementing code? If YES -> DELEGATE INSTEAD
```

---

## 4. Enforcement Mechanisms

### 4.1 Pre-Action Validation

Before ANY file write, agent MUST:

```python
def validate_action(agent_name, action, file_path, work_order):
    # Check 1: File in scope?
    if not is_in_scope(file_path, work_order.assigned_scope):
        raise ScopeViolation(f"{file_path} outside assigned scope")

    # Check 2: PM-exclusive path?
    if is_pm_exclusive(file_path) and agent_name != "pm":
        raise BoundaryViolation(f"{file_path} is PM-exclusive")

    # Check 3: Action prohibited?
    if action in work_order.prohibited_actions:
        raise ProhibitedAction(f"{action} explicitly prohibited")

    # Check 4: Universal prohibition?
    if is_universally_prohibited(action):
        raise UniversalViolation(f"{action} never permitted")

    return True  # Action permitted
```

### 4.2 File Path Validation

```python
PM_EXCLUSIVE_PATHS = [
    r"^LogBook/pm/",
    r"^PLANNING/",
    r"^archives/golden/",
    r"^archives/bad/",
    r"^\.claude/agents/",
    r"^\.claude/guidelines/",
    r"^integration/config/",
]

def is_pm_exclusive(file_path):
    return any(re.match(pattern, file_path) for pattern in PM_EXCLUSIVE_PATHS)

def can_agent_write(agent_name, file_path):
    if agent_name == "pm":
        return True
    if is_pm_exclusive(file_path):
        # Exception: agents can write to their assigned LogBook directory
        if re.match(f"^LogBook/{agent_name}/", file_path):
            return True
        return False
    return True
```

### 4.3 Pre-Commit Hook Enforcement

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Get current agent from environment or git config
AGENT=$(git config user.agent || echo "unknown")

# Check for PM-exclusive paths in commit
PM_PATHS=$(git diff --cached --name-only | grep -E "^(LogBook/pm/|PLANNING/|archives/golden/|archives/bad/|\.claude/agents/|\.claude/guidelines/|integration/config/)")

if [ -n "$PM_PATHS" ] && [ "$AGENT" != "pm" ]; then
    echo "ERROR: Commit includes PM-exclusive paths:"
    echo "$PM_PATHS"
    echo "Only PM agent can modify these files."
    exit 1
fi

# Check for main branch commit
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ]; then
    echo "ERROR: Direct commits to main branch prohibited."
    echo "Use feature branch and PR workflow."
    exit 1
fi

exit 0
```

### 4.4 LogBook Audit Trail

All actions logged to agent's LogBook:

```yaml
# LogBook/<agent>/actions/<date>.yaml
- timestamp: "2025-12-24T10:30:00Z"
  agent: builder
  action: file_write
  file_path: src/api/client.py
  work_order: WO-20251224-001
  scope_check: PASSED
  boundary_check: PASSED
```

---

## 5. Escalation Protocol

When an agent encounters a situation requiring prohibited action:

### 5.1 Escalation Steps

1. **STOP** - Immediately halt current operation
2. **LOG** - Record escalation in LogBook with detailed rationale
3. **REQUEST** - Request PM decision or human approval
4. **WAIT** - Do not proceed until explicit permission received
5. **DOCUMENT** - If approved, log as exception with justification

### 5.2 Escalation Entry Format

```yaml
# LogBook/<agent>/escalations/<date>.yaml
- timestamp: "2025-12-24T10:30:00Z"
  agent: builder
  escalation_type: prohibited_action_required
  action_needed: "Modify PLANNING/specs/API-SPEC.md to fix incorrect endpoint documentation"
  rationale: |
    Discovered critical error in API spec during task implementation.
    Spec says POST /users but implementation requires PUT /users/{id}.
    Cannot proceed without spec correction.
  prohibited_by: "Universal: modify files outside assigned scope"
  requested_permission: "PM approval to modify PLANNING/specs/API-SPEC.md"
  status: PENDING
  resolution: null
```

### 5.3 PM Response Options

When PM receives escalation:

| Response | Action |
|----------|--------|
| **Approve** | PM grants temporary exception, agent proceeds with logging |
| **Delegate** | PM makes the change directly |
| **Reject** | Agent finds alternative approach |
| **Modify Scope** | PM updates work order to include needed access |

### 5.4 Exception Logging

If escalation approved:

```yaml
# LogBook/pm/exceptions/<date>.yaml
- timestamp: "2025-12-24T11:00:00Z"
  escalation_id: ESC-20250101-001
  agent: builder
  approved_action: "Modify PLANNING/specs/API-SPEC.md"
  justification: "Critical spec error blocking implementation"
  approved_by: pm
  expiration: "2025-12-24T23:59:59Z"  # One-time or time-limited
  audit_note: "Exception logged for compliance tracking"
```

---

## 6. Self-Checking Protocols

### 6.1 Pre-Operation Checklist

Before EVERY significant operation:

```
[ ] Is this action within my assigned scope?
[ ] Is this action permitted for my agent role?
[ ] Have I checked the work order's prohibited_actions?
[ ] Am I about to modify a PM-exclusive path?
[ ] Am I about to modify another agent's files?
[ ] Will this action require escalation?
```

### 6.2 Pre-File-Write Check

```python
def pre_write_check(agent, file_path, work_order):
    checks = {
        "in_scope": is_in_scope(file_path, work_order.scope),
        "not_pm_exclusive": not is_pm_exclusive(file_path) or agent == "pm",
        "not_prohibited": file_path not in work_order.prohibited_paths,
        "agent_allowed": can_agent_write(agent, file_path),
    }

    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise PreWriteCheckFailed(f"Failed checks: {failed}")

    return True
```

### 6.3 Pre-Commit Check

```python
def pre_commit_check(agent, branch, files):
    # Check 1: Not on main
    if branch == "main":
        raise BranchViolation("Cannot commit to main")

    # Check 2: All files in scope
    for f in files:
        if not is_in_scope(f):
            raise ScopeViolation(f"{f} out of scope")

    # Check 3: No PM-exclusive paths (unless PM)
    if agent != "pm":
        pm_files = [f for f in files if is_pm_exclusive(f)]
        if pm_files:
            raise BoundaryViolation(f"PM-exclusive: {pm_files}")

    return True
```

### 6.4 Pre-Delete Check

```python
def pre_delete_check(agent, file_path, work_order):
    # Deletion requires explicit permission
    if "delete" not in work_order.permitted_actions:
        raise DeleteNotPermitted("Deletion not explicitly permitted")

    # Cannot delete PM-exclusive paths (unless PM)
    if is_pm_exclusive(file_path) and agent != "pm":
        raise BoundaryViolation("Cannot delete PM-exclusive files")

    # Cannot delete golden archive
    if file_path.startswith("archives/golden/"):
        raise ArchiveProtection("Cannot delete golden archive entries")

    return True
```

### 6.5 Post-Operation Verification

After risky operations:

```python
def post_operation_verify(operation, expected_outcome):
    # Verify no unintended side effects
    actual = get_current_state()

    if actual != expected_outcome:
        log_warning(f"Unexpected outcome: {actual} vs {expected_outcome}")
        trigger_rollback_consideration()

    # Log completion
    log_action(operation, status="COMPLETED", verified=True)
```

---

## 7. Common Pitfalls to Avoid

### 7.1 Scope Creep

**Pitfall:** "While I'm here, let me fix this other small issue..."

**Why Dangerous:**
- Introduces untracked changes
- May break other functionality
- Violates work order scope
- Makes code review harder

**Correct Approach:**
1. Note the issue in LogBook
2. Complete assigned work only
3. Request separate work order for the fix

### 7.2 "Just This Once" Commits to Main

**Pitfall:** "It's a critical fix, I'll commit directly to main just this once..."

**Why Dangerous:**
- Bypasses review process
- Sets bad precedent
- May introduce bugs
- Breaks workflow integrity

**Correct Approach:**
1. Create hotfix branch
2. Make fix on branch
3. Request expedited review
4. Merge through normal process

### 7.3 Skipping Validation

**Pitfall:** "This change is obviously correct, no need to run tests..."

**Why Dangerous:**
- "Obvious" changes often have hidden bugs
- Skipping tests normalizes shortcuts
- Quality gates exist for a reason

**Correct Approach:**
1. Run ALL required validation
2. Document validation results
3. Never skip, even for "trivial" changes

### 7.4 Unauthorized Deletions

**Pitfall:** "This file looks unused, I'll just delete it..."

**Why Dangerous:**
- May be used by other components
- Breaks unknown dependencies
- Data loss is often irreversible

**Correct Approach:**
1. Never delete without explicit permission
2. Check for references first
3. Request PM approval for deletions

### 7.5 SSOT Modifications

**Pitfall:** "There's a typo in wiring.yaml, I'll just fix it..."

**Why Dangerous:**
- SSOT is single source of truth
- Changes affect traceability
- May break dependent tasks

**Correct Approach:**
1. Log the issue
2. Escalate to PM
3. PM coordinates the fix

### 7.6 Bypassing Critic

**Pitfall:** "Critic is busy, I'll merge without review to save time..."

**Why Dangerous:**
- Skips quality verification
- May introduce defects
- Violates approval workflow

**Correct Approach:**
1. Wait for Critic availability
2. Request expedited review if urgent
3. Never bypass the review step

---

## 8. Integration with Work Orders

### 8.1 Work Order Prohibited Actions

Every work order MUST include `prohibited_actions` per schema:

```yaml
# work_order.yaml
work_order_id: WO-20251224-001
agent: builder
scope:
  task_id: "3.1"
  allowed_paths:
    - "src/api/**"
    - "tests/api/**"
    - ".task/**"

prohibited_actions:
  - "modify_ssot"           # Cannot modify wiring.yaml
  - "commit_to_main"        # Must use alt-branch
  - "delete_files"          # No deletions permitted
  - "modify_planning_docs"  # PM-exclusive
  - "skip_tests"            # Must run all tests
  - "self_approve"          # Must request Critic

escalation_contact: "pm"
time_box: "4h"
```

### 8.2 Agent Compliance Check

Before starting work order:

```python
def start_work_order(agent, work_order):
    # Read and acknowledge prohibited actions
    prohibited = work_order.get("prohibited_actions", [])

    log_entry = {
        "event": "work_order_started",
        "work_order_id": work_order["work_order_id"],
        "acknowledged_prohibitions": prohibited,
        "timestamp": now()
    }

    append_to_logbook(agent, log_entry)

    return True
```

### 8.3 Violation Logging

If prohibition violated:

```yaml
# LogBook/<agent>/violations/<date>.yaml
- timestamp: "2025-12-24T10:30:00Z"
  agent: builder
  work_order: WO-20251224-001
  violation_type: prohibited_action
  action_attempted: "modify_ssot"
  file_path: ".task/wiring.yaml"
  prevented: true  # Was the violation stopped?
  resolution: "Escalated to PM, PM made the change"
```

### 8.4 Compliance Reporting

PM reviews compliance:

```python
def generate_compliance_report(date_range):
    violations = load_violations(date_range)
    escalations = load_escalations(date_range)

    report = {
        "period": date_range,
        "total_violations": len(violations),
        "violations_prevented": sum(1 for v in violations if v["prevented"]),
        "violations_occurred": sum(1 for v in violations if not v["prevented"]),
        "escalations": len(escalations),
        "escalations_approved": sum(1 for e in escalations if e["status"] == "APPROVED"),
        "by_agent": group_by_agent(violations),
        "by_type": group_by_type(violations),
    }

    return report
```

---

## Appendix A: Quick Reference Card

### Universal Prohibitions (All Agents)

| Action | Status |
|--------|--------|
| Commit to main | NEVER |
| Force push | NEVER |
| Delete without permission | NEVER |
| Bypass quality gates | NEVER |
| Modify SSOT without PM | NEVER |
| Alter other agents' LogBook | NEVER |
| Self-approve own work | NEVER |

### Agent Scope Summary

| Agent | Can Write | Cannot Write |
|-------|-----------|--------------|
| Builder | src/, tests/, docs/, .task/, LogBook/builder/, tools/ | PLANNING/, LogBook/pm/, archives/, .claude/ |
| Critic | LogBook/critic/ | All code files, PLANNING/, LogBook/pm/ |
| Planner | LogBook/planner/ | All code files, PLANNING/, LogBook/pm/ |
| PM | Everything | Should delegate implementation |

### Escalation Triggers

- Need to modify PM-exclusive path
- Need to delete files
- Need to modify SSOT
- Work order scope insufficient
- Prohibited action legitimately required
- Time box exceeded

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-24 | PM | Initial release |
