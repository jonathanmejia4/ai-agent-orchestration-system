# PM Write Boundaries Protocol

> **Document Version:** 1.0.0
> **Last Updated:** 2025-01-15
> **Classification:** CRITICAL - Scope Enforcement
> **Reference:** ROLLBACK_PROCEDURES.md:156, FAILURE_MODES.md:234

## Purpose

This document defines the **exclusive write boundaries** for the Project Manager (PM) agent within the the system. It establishes which files and paths are PM-exclusive, which are shared, and the enforcement mechanisms that prevent boundary violations.

**Why This Matters:**
- Prevents scope creep and unauthorized modifications
- Maintains clear ownership and accountability
- Enables reliable rollback and audit trails
- Prevents agent conflicts and data corruption

---

## 1. PM-Exclusive Write Paths

The following 7 paths are **exclusively writable by PM**. No other agent may create, modify, or delete files in these locations.

### 1.1 Primary PM-Exclusive Paths

| # | Path Pattern | Purpose | Contains |
|---|--------------|---------|----------|
| 1 | `LogBook/pm/` | PM activity logs | STATE.md, decisions, escalations |
| 2 | `PLANNING/MASTER_PLAN.md` | Project master plan | Phases, milestones, dependencies |
| 3 | `PLANNING/WORK_ORDER_QUEUE.yaml` | Active work orders | Pending, in-progress, blocked WOs |
| 4 | `ISSUE_CATALOG.md` | Issue tracking | All issues with status |
| 5 | `PLANNING/PROJECT_CONTEXT.md` | Project context | Goals, constraints, decisions |
| 6 | `PLANNING/MILESTONE_TRACKER.md` | Milestone tracking | Progress, dates, dependencies |
| 7 | `LogBook/pm/escalations/` | Escalation records | Critical escalations from all agents |
| 8 | `LogBook/work-orders/` | Work order files | Individual work order YAML files |
| 9 | `.claude/guidelines/` | governance guidelines | Policy documents maintained by PM |

### 1.2 Path Specifications

```yaml
pm_exclusive_paths:
  # Full directory ownership
  - path: "LogBook/pm/"
    type: directory
    recursive: true
    description: "All PM activity logging"

  - path: "LogBook/pm/escalations/"
    type: directory
    recursive: true
    description: "Escalation records from all agents"

  # Specific file ownership
  - path: "PLANNING/MASTER_PLAN.md"
    type: file
    description: "Project master plan and phase definitions"

  - path: "PLANNING/WORK_ORDER_QUEUE.yaml"
    type: file
    description: "Work order queue management"

  - path: "ISSUE_CATALOG.md"
    type: file
    description: "Issue catalog and resolution tracking"

  - path: "PLANNING/PROJECT_CONTEXT.md"
    type: file
    description: "High-level project context"

  - path: "PLANNING/MILESTONE_TRACKER.md"
    type: file
    description: "Milestone and progress tracking"
```

---

## 2. Agent-Assigned LogBook Exceptions

Each agent has **exclusive write access** to their own LogBook directory. This is an exception to PM's escalation logging rights.

### 2.1 Agent LogBook Assignments

| Agent | Exclusive LogBook Path | May Write To |
|-------|----------------------|--------------|
| **Builder** | `LogBook/builder/` | progress.yaml, actions, errors |
| **Critic** | `LogBook/critic/` | verdicts.yaml, reviews, feedback |
| **Planner** | `LogBook/planner/` | planning_log.yaml, analysis, recommendations |
| **PM** | `LogBook/pm/` | STATE.md, decisions, escalations |

### 2.2 Cross-Agent LogBook Rules

```
RULE: Agents may ONLY write to their assigned LogBook directory
EXCEPTION: PM escalation records are stored in LogBook/pm/escalations/
PROHIBITION: No agent may write to another agent's LogBook directory
```

### 2.3 LogBook Path Validation

```python
def validate_logbook_write(agent: str, target_path: str) -> bool:
    """
    Validate that an agent can write to the target LogBook path.

    Returns True if write is allowed, False otherwise.
    """
    # Define agent-to-path mappings
    agent_logbook_paths = {
        "builder": "LogBook/builder/",
        "critic": "LogBook/critic/",
        "planner": "LogBook/planner/",
        "pm": "LogBook/pm/"
    }

    # PM exception for escalations
    pm_additional_paths = ["LogBook/pm/escalations/"]

    agent = agent.lower()

    # Check if path is in agent's assigned directory
    if agent in agent_logbook_paths:
        allowed_path = agent_logbook_paths[agent]
        if target_path.startswith(allowed_path):
            return True

    # Check PM escalation exception
    if agent == "pm":
        for path in pm_additional_paths:
            if target_path.startswith(path):
                return True

    return False
```

---

## 3. Shared Write Paths

The following paths allow writes from **multiple designated agents** under specific conditions.

### 3.1 Shared Path Definitions

| Path Pattern | Allowed Agents | Conditions |
|--------------|----------------|------------|
| `Task/` | Builder (create), Critic (review flags) | Builder creates, Critic adds review metadata |
| `tests/` | Builder | Test file creation/modification |
| `src/` | Builder | Implementation code |
| `.github/workflows/` | Builder, PM | CI/CD workflows |
| `tools/` | Builder | Utility tools and scripts |

### 3.2 Shared Path Rules

```yaml
shared_paths:
  - path: "Task/"
    agents:
      - agent: builder
        permissions: [create, modify, delete]
        conditions: "Must have active work order"
      - agent: critic
        permissions: [modify]
        conditions: "Review metadata only (verdict, review_status)"

  - path: "tests/"
    agents:
      - agent: builder
        permissions: [create, modify, delete]
        conditions: "Test files for implementations"

  - path: "src/"
    agents:
      - agent: builder
        permissions: [create, modify, delete]
        conditions: "Implementation per work order"

  - path: ".github/workflows/"
    agents:
      - agent: builder
        permissions: [create, modify]
        conditions: "CI/CD for implementations"
      - agent: pm
        permissions: [create, modify]
        conditions: "Project-level workflows"

  - path: "tools/"
    agents:
      - agent: builder
        permissions: [create, modify, delete]
        conditions: "Utility tools per work order"
```

---

## 4. Read-Only Paths

The following paths are **read-only for most agents** and have restricted write access.

### 4.1 Read-Only Path Definitions

| Path | Write Access | Read Access | Purpose |
|------|--------------|-------------|---------|
| `CLAUDE.md` | Human only | All agents | System configuration |
| `.claude/` | Human/PM | All agents | Claude guidelines |
| `FAILURE_MODES.md` | Human/PM | All agents | Failure documentation |
| `ROLLBACK_PROCEDURES.md` | Human/PM | All agents | Rollback procedures |
| `README.md` | Human | All agents | Project documentation |

### 4.2 Read-Only Enforcement

```python
READ_ONLY_PATHS = [
    "CLAUDE.md",
    "README.md",
    "LICENSE",
    ".gitignore",
]

PM_WRITABLE_DOCS = [
    "FAILURE_MODES.md",
    "ROLLBACK_PROCEDURES.md",
    ".claude/guidelines/",
]

def is_read_only(path: str, agent: str) -> bool:
    """Check if path is read-only for the given agent."""
    # Absolute read-only for all agents
    for ro_path in READ_ONLY_PATHS:
        if path == ro_path or path.startswith(ro_path + "/"):
            return True

    # PM-writable docs
    if agent.lower() == "pm":
        for pm_path in PM_WRITABLE_DOCS:
            if path == pm_path or path.startswith(pm_path):
                return False

    # For other agents, these are read-only
    for pm_path in PM_WRITABLE_DOCS:
        if path == pm_path or path.startswith(pm_path):
            return True

    return False
```

---

## 5. Enforcement Mechanisms

### 5.1 Pre-Write Validation

Every write operation MUST pass through validation before execution.

```python
class WriteValidator:
    """Validates write operations against PM boundaries."""

    def __init__(self, agent: str):
        self.agent = agent.lower()
        self.violations = []

    def validate_write(self, target_path: str, operation: str) -> dict:
        """
        Validate a write operation.

        Args:
            target_path: Path to write to
            operation: 'create', 'modify', or 'delete'

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "violation_type": str or None,
                "escalation_required": bool
            }
        """
        result = {
            "allowed": False,
            "reason": "",
            "violation_type": None,
            "escalation_required": False
        }

        # Check read-only paths
        if self._is_read_only(target_path):
            result["reason"] = f"Path is read-only: {target_path}"
            result["violation_type"] = "READ_ONLY_VIOLATION"
            result["escalation_required"] = True
            return result

        # Check PM-exclusive paths
        if self._is_pm_exclusive(target_path) and self.agent != "pm":
            result["reason"] = f"Path is PM-exclusive: {target_path}"
            result["violation_type"] = "PM_EXCLUSIVE_VIOLATION"
            result["escalation_required"] = True
            return result

        # Check LogBook boundaries
        if target_path.startswith("LogBook/"):
            if not self._validate_logbook_access(target_path):
                result["reason"] = f"Agent {self.agent} cannot write to {target_path}"
                result["violation_type"] = "LOGBOOK_BOUNDARY_VIOLATION"
                result["escalation_required"] = True
                return result

        # Check agent-specific permissions
        if not self._has_permission(target_path, operation):
            result["reason"] = f"Agent {self.agent} lacks {operation} permission for {target_path}"
            result["violation_type"] = "PERMISSION_DENIED"
            return result

        result["allowed"] = True
        result["reason"] = "Write operation permitted"
        return result

    def _is_read_only(self, path: str) -> bool:
        """Check if path is read-only."""
        read_only = ["CLAUDE.md", "README.md", "LICENSE", ".gitignore"]
        return any(path == p or path.startswith(p + "/") for p in read_only)

    def _is_pm_exclusive(self, path: str) -> bool:
        """Check if path is PM-exclusive."""
        pm_exclusive = [
            "LogBook/pm/",
            "LogBook/pm/escalations/",
            "PLANNING/MASTER_PLAN.md",
            "PLANNING/WORK_ORDER_QUEUE.yaml",
            "ISSUE_CATALOG.md",
            "PLANNING/PROJECT_CONTEXT.md",
            "PLANNING/MILESTONE_TRACKER.md",
            "LogBook/work-orders/",
        ]
        return any(path.startswith(p) or path == p for p in pm_exclusive)

    def _validate_logbook_access(self, path: str) -> bool:
        """Validate LogBook write access."""
        agent_paths = {
            "builder": "LogBook/builder/",
            "critic": "LogBook/critic/",
            "planner": "LogBook/planner/",
            "pm": "LogBook/pm/",
        }

        # Check agent's own LogBook
        if self.agent in agent_paths:
            if path.startswith(agent_paths[self.agent]):
                return True

        # PM escalation exception (escalations are in LogBook/pm/escalations/)
        if self.agent == "pm" and path.startswith("LogBook/pm/escalations/"):
            return True

        return False

    def _has_permission(self, path: str, operation: str) -> bool:
        """Check if agent has permission for operation on path."""
        # Define permissions per agent
        permissions = {
            "builder": {
                "paths": ["Task/", "tests/", "src/", "tools/", ".github/workflows/"],
                "operations": ["create", "modify", "delete"]
            },
            "critic": {
                "paths": ["Task/"],  # Review metadata only
                "operations": ["modify"]
            },
            "planner": {
                "paths": [],  # Analysis only, no direct writes
                "operations": []
            },
            "pm": {
                "paths": ["PLANNING/", ".claude/guidelines/", "FAILURE_MODES.md", "ROLLBACK_PROCEDURES.md"],
                "operations": ["create", "modify", "delete"]
            }
        }

        if self.agent not in permissions:
            return False

        agent_perms = permissions[self.agent]

        # Check operation permission
        if operation not in agent_perms["operations"]:
            return False

        # Check path permission
        for allowed_path in agent_perms["paths"]:
            if path.startswith(allowed_path) or path == allowed_path:
                return True

        return False
```

### 5.2 Pre-Commit Hook Integration

```bash
#!/bin/bash
# .git/hooks/pre-commit (excerpt for PM boundary enforcement)

# Get list of staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

# PM-exclusive paths
PM_EXCLUSIVE_PATHS=(
    "LogBook/pm/"
    "LogBook/pm/escalations/"
    "PLANNING/MASTER_PLAN.md"
    "PLANNING/WORK_ORDER_QUEUE.yaml"
    "ISSUE_CATALOG.md"
    "PLANNING/PROJECT_CONTEXT.md"
    "PLANNING/MILESTONE_TRACKER.md"
)

# Check for PM boundary violations
# Note: This requires commit metadata or environment variable indicating agent
CURRENT_AGENT="${AGENT:-unknown}"

if [ "$CURRENT_AGENT" != "pm" ] && [ "$CURRENT_AGENT" != "unknown" ]; then
    for file in $STAGED_FILES; do
        for pm_path in "${PM_EXCLUSIVE_PATHS[@]}"; do
            if [[ "$file" == "$pm_path"* ]] || [[ "$file" == "$pm_path" ]]; then
                echo "ERROR: PM boundary violation detected!"
                echo "Agent '$CURRENT_AGENT' attempted to modify PM-exclusive path: $file"
                echo "This commit has been blocked."
                exit 1
            fi
        done
    done
fi

echo "PM boundary check passed"
```

### 5.3 Runtime Enforcement

```python
def enforce_pm_boundaries(func):
    """
    Decorator to enforce PM write boundaries on file operations.

    Usage:
        @enforce_pm_boundaries
        def write_file(agent: str, path: str, content: str):
            ...
    """
    def wrapper(agent: str, path: str, *args, **kwargs):
        validator = WriteValidator(agent)
        result = validator.validate_write(path, "modify")

        if not result["allowed"]:
            if result["escalation_required"]:
                # Log escalation
                log_boundary_violation(agent, path, result)
                raise PMBoundaryViolationError(
                    f"PM Boundary Violation: {result['reason']}"
                )
            else:
                raise PermissionError(result["reason"])

        return func(agent, path, *args, **kwargs)

    return wrapper


class PMBoundaryViolationError(Exception):
    """Raised when a PM boundary violation is detected."""
    pass
```

---

## 6. Escalation Protocol for Violations

When a boundary violation is detected, the following escalation protocol MUST be followed.

### 6.1 Violation Severity Levels

| Level | Description | Examples | Response |
|-------|-------------|----------|----------|
| **CRITICAL** | PM-exclusive path violation | Writing to MASTER_PLAN.md | Block + immediate escalation |
| **HIGH** | LogBook cross-agent write | Builder writing to Critic LogBook | Block + escalation |
| **MEDIUM** | Read-only path attempt | Modifying CLAUDE.md | Block + warning |
| **LOW** | Soft boundary crossing | Accessing deprecated path | Warning only |

### 6.2 Escalation Steps

```
STEP 1: DETECT
  - Pre-write validation catches violation
  - Log violation details

STEP 2: BLOCK
  - Prevent write operation
  - Return error to calling agent

STEP 3: LOG
  - Record in LogBook/pm/escalations/boundary_violations.yaml
  - Include: timestamp, agent, path, operation, violation_type

STEP 4: NOTIFY
  - Alert PM of violation (via LogBook/pm/STATE.md)
  - Flag for human review if CRITICAL

STEP 5: AUDIT
  - Add to audit trail
  - Track repeat violations by agent
```

### 6.3 Violation Logging Format

```yaml
# LogBook/pm/escalations/boundary_violations.yaml
violations:
  - violation_id: "BV-2025-001"
    timestamp: "2025-01-15T10:30:00Z"
    agent: "builder"
    target_path: "LogBook/pm/STATE.md"
    operation: "modify"
    violation_type: "PM_EXCLUSIVE_VIOLATION"
    severity: "CRITICAL"
    blocked: true
    escalated_to: "pm"
    resolution: "pending"

  - violation_id: "BV-2025-002"
    timestamp: "2025-01-15T11:45:00Z"
    agent: "critic"
    target_path: "LogBook/builder/progress.yaml"
    operation: "modify"
    violation_type: "LOGBOOK_BOUNDARY_VIOLATION"
    severity: "HIGH"
    blocked: true
    escalated_to: "pm"
    resolution: "reviewed - agent reminded of boundaries"
```

---

## 7. Audit Trail Requirements

### 7.1 Required Audit Information

Every write operation must log:

```yaml
audit_entry:
  timestamp: "ISO 8601 format"
  agent: "executing agent"
  operation: "create|modify|delete"
  target_path: "full path"
  validation_result: "allowed|blocked"
  violation_type: "null if allowed"
  work_order_id: "if applicable"
  checksum_before: "SHA256 of file before (if modify/delete)"
  checksum_after: "SHA256 of file after (if create/modify)"
```

### 7.2 Audit Log Location

```
LogBook/audit/
  ├── writes/
  │   ├── 2025-01/
  │   │   ├── builder_writes.yaml
  │   │   ├── critic_writes.yaml
  │   │   ├── planner_writes.yaml
  │   │   └── pm_writes.yaml
  │   └── ...
  └── violations/
      └── boundary_violations.yaml
```

### 7.3 Audit Retention

- **Write logs:** 90 days minimum
- **Violation logs:** 1 year minimum
- **CRITICAL violations:** Permanent retention

---

## 8. Quick Reference Matrix

### 8.1 Agent Write Permissions Matrix

| Path | PM | Builder | Critic | Planner |
|------|-----|---------|--------|---------|
| `LogBook/pm/` | W | - | - | - |
| `LogBook/builder/` | - | W | - | - |
| `LogBook/critic/` | - | - | W | - |
| `LogBook/planner/` | - | - | - | W |
| `LogBook/pm/escalations/` | W | - | - | - |
| `PLANNING/MASTER_PLAN.md` | W | - | - | - |
| `PLANNING/WORK_ORDER_QUEUE.yaml` | W | - | - | - |
| `ISSUE_CATALOG.md` | W | - | - | - |
| `Task/` | - | W | R* | - |
| `src/` | - | W | - | - |
| `tests/` | - | W | - | - |
| `tools/` | - | W | - | - |
| `CLAUDE.md` | - | - | - | - |

**Legend:** W = Write, R = Read only, R* = Review metadata only, - = No access

### 8.2 Enforcement Checklist

```markdown
Before ANY write operation:
[ ] Identify executing agent
[ ] Validate target path against boundaries
[ ] Check PM-exclusive paths
[ ] Check LogBook boundaries
[ ] Verify operation type permissions
[ ] Log validation result
[ ] Block if violation detected
[ ] Escalate if required
[ ] Create audit entry
```

---

## 9. Implementation Integration

### 9.1 Integration with agent-guardrails.md

This document extends `.claude/guidelines/agent-guardrails.md` with specific path boundary enforcement. Both documents MUST be read together for complete understanding of agent constraints.

### 9.2 Integration with Tools

The following tools enforce PM write boundaries:
- `tools/validate_logbook.py` - Validates LogBook entries and paths
- `tools/ssot_validator.py` - Validates SSOT compliance
- `tools/idempotence_validator.py` - Validates operation safety

### 9.3 CI/CD Integration

PM boundaries are enforced in CI via:
- Pre-commit hooks (local enforcement)
- GitHub Actions workflows (PR validation)
- Merge gate checks (final validation)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-15 | PM | Initial document creation |

---

**CRITICAL REMINDER:** Violations of PM write boundaries are treated as security incidents. Repeated violations may result in agent session termination and mandatory review.
