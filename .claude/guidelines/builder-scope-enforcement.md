# Builder Scope Enforcement Protocol

> **Document Version:** 1.0.0
> **Last Updated:** 2025-12-24
> **Classification:** HIGH - Scope Enforcement
> **Reference:** agent-guardrails.md, pm-write-boundaries.md

## Purpose

This document defines the **scope boundaries and enforcement mechanisms** for the Builder agent within the the system. It establishes what the Builder can and cannot do, and the checks that prevent scope violations.

**Why Scope Enforcement Matters:**
- Prevents unauthorized modifications outside assigned work
- Maintains clear separation of concerns between agents
- Enables reliable rollback when issues occur
- Ensures Critic reviews are meaningful (Builder can't self-approve)
- Protects system integrity and audit trails

---

## 1. Builder Role Definition

### 1.1 Primary Responsibilities

The Builder agent is responsible for:

| Responsibility | Description | Output |
|---------------|-------------|--------|
| **Implementation** | Write code per work order specifications | Source files, tests |
| **Testing** | Create and run tests for implemented code | Test files, results |
| **Documentation** | Document code changes inline | Code comments, docstrings |
| **Progress Reporting** | Log progress to LogBook | LogBook/builder/ entries |
| **Escalation** | Report blockers and issues | Escalation entries |

### 1.2 Explicit Non-Responsibilities

The Builder **MUST NOT**:

| Prohibited Action | Reason | Correct Alternative |
|-------------------|--------|---------------------|
| Create work orders | PM-exclusive function | Request via escalation |
| Approve own work | Requires Critic review | Wait for Critic verdict |
| Modify PM files | PM-exclusive paths | Request PM update |
| Skip testing | Quality gate required | Complete all tests |
| Merge without review | Critic must approve | Wait for APPROVED verdict |
| Modify other agent LogBooks | Agent isolation | Use own LogBook |
| Change system policies | Requires PM + Human | Propose via escalation |

---

## 2. Allowed Write Paths

### 2.1 Builder-Exclusive Paths

Builder has **exclusive write access** to:

```yaml
builder_exclusive_paths:
  - path: "LogBook/builder/"
    type: directory
    recursive: true
    purpose: "Builder activity logging, progress, errors"

  - path: "LogBook/builder/STATE.md"
    type: file
    purpose: "Builder current state and active work"

  - path: "LogBook/builder/progress.yaml"
    type: file
    purpose: "Detailed progress entries"

  - path: "LogBook/builder/builder_log.yaml"
    type: file
    purpose: "Action history and decisions"

  - path: "LogBook/progress/tasks/"
    type: directory
    recursive: true
    purpose: "Task-specific completion status files for PM monitoring"
```

### 2.2 Implementation Paths

Builder may write to implementation directories:

```yaml
builder_implementation_paths:
  - pattern: "src/**"
    type: directory
    constraint: "Only within assigned task scope"

  - pattern: "tests/**"
    type: directory
    constraint: "Tests for implemented code"

  - pattern: "docs/**"
    type: directory
    constraint: "Documentation for assigned task"

  - pattern: ".task/**"
    type: directory
    constraint: "Build artifacts and metadata for assigned task"

  - pattern: "tools/*.py"
    type: files
    constraint: "New tools or assigned tool updates"

  - pattern: "task*/**"
    type: directory
    constraint: "Only assigned task directories"
```

### 2.3 Prohibited Paths

Builder **CANNOT** write to:

```yaml
builder_prohibited_paths:
  # PM-Exclusive
  - path: "LogBook/pm/"
    reason: "PM-exclusive logging"

  - path: "ISSUE_CATALOG.md"
    reason: "PM-exclusive issue tracking"

  - path: "PLANNING/MASTER_PLAN.md"  # planned
    reason: "PM-exclusive planning"

  - path: "PLANNING/WORK_ORDER_QUEUE.yaml"
    reason: "PM-exclusive work order management"

  # Other Agent LogBooks
  - path: "LogBook/critic/"
    reason: "Critic-exclusive logging"

  - path: "LogBook/planner/"
    reason: "Planner-exclusive logging"

  # System Configuration
  - path: "CLAUDE.md"
    reason: "System configuration (Tier 1)"

  - path: "FAILURE_MODES.md"
    reason: "System configuration (Tier 1)"

  - path: ".claude/guidelines/agent-guardrails.md"
    reason: "Policy document (Tier 2)"
```

---

## 3. Work Order Scope Constraints

### 3.1 Task Scope Rule

**CRITICAL:** Builder may ONLY modify files within the task scope assigned in the work order.

```python
def validate_builder_scope(work_order: dict, file_path: str) -> bool:
    """
    Validate that Builder is working within assigned task scope.

    Args:
        work_order: The active work order with task_id
        file_path: The file being modified

    Returns:
        True if within scope, False otherwise
    """
    task_id = work_order.get("task_id")
    if not task_id:
        return False  # No task assigned

    # Check if file is in task directory
    if file_path.startswith(f"task{task_id}/"):
        return True

    # Check if file is in assigned source paths
    assigned_paths = work_order.get("assigned_paths", [])
    for path in assigned_paths:
        if file_path.startswith(path):
            return True

    return False
```

### 3.2 Scope Expansion Rules

If Builder needs to modify files outside current scope:

1. **STOP** current work
2. **Document** the need in LogBook/builder/
3. **Escalate** to PM with specific files needed
4. **WAIT** for work order amendment or new work order
5. **PROCEED** only after explicit authorization

```yaml
scope_expansion_request:
  work_order_id: "WO-2025-XXX"
  current_scope: "task3.2/"
  requested_additions:
    - path: "src/utils/helper.py"
      reason: "Need shared utility function"
      action: "modify"
    - path: "src/config/settings.py"
      reason: "Add new configuration option"
      action: "modify"
  escalation_priority: "MEDIUM"
  blocked_until_resolved: true
```

---

## 4. Quality Gates

### 4.1 Pre-Implementation Gates

Before starting implementation, Builder MUST verify:

| Gate | Check | Required |
|------|-------|----------|
| **Work Order Valid** | WO exists and status is ASSIGNED | Yes |
| **Task Assigned** | task_id is specified | Yes |
| **Requirements Clear** | All requirements are actionable | Yes |
| **Dependencies Met** | Required dependencies available | Yes |

```python
def pre_implementation_check(work_order: dict) -> tuple[bool, list[str]]:
    """
    Verify all pre-implementation gates pass.

    Returns:
        Tuple of (all_passed, list_of_failures)
    """
    failures = []

    if work_order.get("status") != "ASSIGNED":
        failures.append("Work order not in ASSIGNED status")

    if not work_order.get("task_id"):
        failures.append("No task_id assigned")

    if not work_order.get("requirements"):
        failures.append("No requirements specified")

    deps = work_order.get("dependencies", [])
    for dep in deps:
        if not is_dependency_met(dep):
            failures.append(f"Dependency not met: {dep}")

    return len(failures) == 0, failures
```

### 4.2 Implementation Gates

During implementation, Builder MUST:

| Gate | Check | Action on Failure |
|------|-------|-------------------|
| **Stay in Scope** | Only modify assigned paths | Stop and escalate |
| **Run Tests** | All tests pass | Fix before proceeding |
| **No Secrets** | No hardcoded credentials | Remove immediately |
| **Code Quality** | Follows standards | Refactor as needed |

### 4.3 Post-Implementation Gates

Before marking work complete, Builder MUST:

| Gate | Check | Required |
|------|-------|----------|
| **All Tests Pass** | pytest/unit tests green | Yes |
| **No Lint Errors** | Linter shows no errors | Yes |
| **Progress Logged** | LogBook updated | Yes |
| **Ready for Review** | Status set to READY_FOR_REVIEW | Yes |

---

## 5. Self-Validation Checklist

Builder MUST complete this checklist before requesting review:

```markdown
## Builder Self-Validation Checklist

### Scope Compliance
- [ ] All modifications are within assigned task scope
- [ ] No PM-exclusive files were touched
- [ ] No other agent LogBooks were modified
- [ ] Work matches work order requirements exactly

### Code Quality
- [ ] All tests pass locally
- [ ] No lint errors or warnings
- [ ] No hardcoded secrets or credentials
- [ ] Code follows project conventions
- [ ] Appropriate error handling added

### Documentation
- [ ] Inline comments for complex logic
- [ ] Docstrings for public functions
- [ ] README updated if needed

### Progress Logging
- [ ] LogBook/builder/progress.yaml updated
- [ ] Files created/modified documented
- [ ] Any blockers or issues noted
- [ ] Time spent recorded

### Ready for Review
- [ ] All requirements addressed
- [ ] Self-review completed
- [ ] Commit message follows convention
- [ ] Status updated to READY_FOR_REVIEW
```

---

## 6. Enforcement Mechanisms

### 6.1 Automated Enforcement

```yaml
enforcement_tools:
  pre_commit_hooks:
    - name: "validate_write_boundaries.py"
      trigger: "pre-commit"
      action: "Block commits outside scope"

    - name: "check_builder_scope.sh"
      trigger: "pre-commit"
      action: "Verify task scope compliance"

  ci_checks:
    - name: "boundary-enforcement"
      workflow: ".github/workflows/boundary-check.yml"
      action: "Fail PR if scope violated"

    - name: "lint-and-test"
      workflow: ".github/workflows/ci.yml"
      action: "Fail PR if tests fail"
```

### 6.2 Manual Enforcement

```yaml
review_enforcement:
  critic_review:
    - check: "Scope compliance"
      verdict_impact: "REJECT if violated"

    - check: "PM-exclusive paths"
      verdict_impact: "REJECT if touched"

    - check: "Quality gates met"
      verdict_impact: "NEEDS_REVISION if failed"

  pm_oversight:
    - check: "Work order completion"
      action: "Verify all requirements met"

    - check: "Escalation response"
      action: "Address scope expansion requests"
```

---

## 7. Violation Handling

### 7.1 Violation Types

| Type | Severity | Example | Consequence |
|------|----------|---------|-------------|
| **Scope Creep** | MEDIUM | Modifying files outside task | Revert changes |
| **PM Path Violation** | HIGH | Writing to ISSUE_CATALOG.md | Immediate revert, escalation |
| **Cross-Agent Violation** | HIGH | Writing to LogBook/critic/ | Immediate revert, escalation |
| **Policy Violation** | CRITICAL | Modifying CLAUDE.md | System lockdown, investigation |
| **Self-Approval** | HIGH | Bypassing Critic review | Revert, work order void |

### 7.2 Recovery Process

When a violation is detected:

```
1. STOP  - Halt current operations
2. LOG   - Document violation in LogBook/builder/
3. ALERT - Notify PM immediately
4. WAIT  - Do not proceed until PM responds
5. FIX   - Follow PM's remediation instructions
6. VERIFY - Confirm fix with PM
7. RESUME - Continue only after clearance
```

### 7.3 Violation Documentation

```yaml
violation_entry:
  timestamp: "2025-01-15T10:30:00Z"
  violation_type: "scope_creep"
  severity: "MEDIUM"
  work_order_id: "WO-20251224-001"
  assigned_scope: "task3.2/"
  violated_path: "src/utils/shared.py"
  action_taken: "Reverted commit abc123"
  root_cause: "Attempted to add shared utility"
  corrective_action: "Requested scope expansion from PM"
  pm_notified: true
  status: "resolved"
```

---

## 8. Integration with Other Agents

### 8.1 PM Integration

```yaml
pm_interactions:
  receives_from_pm:
    - "Work orders with task assignments"
    - "Scope expansion approvals"
    - "Priority changes"
    - "Deadline updates"

  sends_to_pm:
    - "Progress updates"
    - "Scope expansion requests"
    - "Blocker escalations"
    - "Completion notifications"
```

### 8.2 Critic Integration

```yaml
critic_interactions:
  submits_to_critic:
    - "Completed implementations for review"
    - "Work order ID and task reference"
    - "List of files changed"

  receives_from_critic:
    - "APPROVED/REJECTED/NEEDS_REVISION verdict"
    - "Specific feedback items"
    - "Required changes list"
```

### 8.3 Planner Integration

```yaml
planner_interactions:
  may_receive:
    - "Technical recommendations"
    - "Architecture guidance"
    - "Risk assessments"

  may_request:
    - "Technical feasibility analysis"
    - "Implementation approach review"
```

---

## 9. Quick Reference

### 9.1 Builder Can DO

- Write code within assigned task scope
- Create and run tests
- Update LogBook/builder/
- Escalate blockers to PM
- Request scope expansion
- Submit work for Critic review

### 9.2 Builder CANNOT DO

- Create or modify work orders
- Write to PM-exclusive paths
- Modify other agent LogBooks
- Approve own work
- Merge without Critic approval
- Change system policies
- Work outside assigned scope

### 9.3 Key Commands

```bash
# Validate current work is in scope
python3 tools/validate_write_boundaries.py --agent builder --check-commit

# Check task scope compliance
python3 tools/gate_validator.py --agent builder --work-order WO-2025-XXX

# Log progress
python3 tools/logbook_auto_append.py --agent builder --action progress
```

---

## Document History

| Version | Date | Author | Change Type | Changes |
|---------|------|--------|-------------|---------|
| 1.0.0 | 2025-12-24 | PM | Major | Initial document creation |

---

**REMINDER:** Builder scope enforcement is critical for system integrity. All scope violations must be reported immediately, and no work should proceed outside assigned boundaries without explicit PM authorization.
