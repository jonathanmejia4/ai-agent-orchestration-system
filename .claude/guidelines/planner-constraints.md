# Planner Constraints Guidelines
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** HIGH - Agent Behavior Control

## Overview

This document defines the constraints and boundaries that the Planner agent must operate within. Violating these constraints triggers escalation to PM.

## Hard Constraints (MUST)

### 1. Work Order Scope
- **MUST** only plan tasks within the assigned work order scope
- **MUST NOT** add tasks not covered by the work order
- **MUST** escalate if work order scope is unclear

### 2. Template Selection
- **MUST** select templates from the approved registry only
- **MUST** use pinned template versions (no floating versions)
- **MUST NOT** use deprecated templates for new tasks
- **MUST** verify template compatibility before selection

### 3. Dependency Management
- **MUST** identify all task dependencies
- **MUST** ensure dependency graph is acyclic (DAG)
- **MUST** use `tools/find_cycles.py` to validate
- **MUST NOT** create circular dependencies

### 4. Output Artifacts
- **MUST** produce execution plan in `.task/execution_plan.yaml`
- **MUST** produce dependency graph in `.task/deps.yaml`
- **MUST** produce wiring in `.task/wiring.yaml`
- **MUST** request PM approval before handoff

### 5. Write Boundaries
- **CAN** write to `.task/` directory
- **CAN** write to `LogBook/planner/` directory (plan status tracking)
- **CANNOT** write to `LogBook/pm/`
- **CANNOT** write to source code
- **CANNOT** write to `.claude/agents/`

## Soft Constraints (SHOULD)

### 1. Task Granularity
- **SHOULD** decompose tasks to 2-4 hour chunks
- **MUST** avoid tasks larger than 4 hours (hard limit per agent-operating-principles)
- **SHOULD** create parallel-executable tasks when possible

### 2. Risk Assessment
- **SHOULD** identify high-risk tasks
- **SHOULD** front-load risky tasks for early feedback
- **SHOULD** include buffer time for unknowns

### 3. Resource Estimation
- **SHOULD** estimate task durations
- **SHOULD** identify required tools/dependencies
- **SHOULD** flag resource constraints

## Escalation Triggers

Escalate to PM when:
1. Work order requirements are ambiguous
2. Required template not in registry
3. Circular dependency detected
4. Task exceeds complexity threshold
5. External dependency required
6. Scope creep detected

## Constraint Validation

Before submitting execution plan:
```bash
# Validate execution plan
tools/validate_action_plan.py .task/execution_plan.yaml

# Check dependencies
tools/find_cycles.py .task/deps.yaml

# Verify templates
tools/template_version_checker.py .task/wiring.yaml
```

## Examples

### Good: Proper Task Decomposition
```yaml
tasks:
  - id: "task-001"
    description: "Create user model"
    duration: "PT2H"  # ISO 8601 duration format
    dependencies: []
  - id: "task-002"
    description: "Add validation logic"
    duration: "PT3H"
    dependencies: ["task-001"]
```

### Bad: Overly Large Task
```yaml
tasks:
  - id: "task-001"
    description: "Implement entire user system"  # Too vague, too large
    duration: "PT40H"  # Exceeds 4-hour time box
    dependencies: []
```

## Related Documents
- PLANNING/AGENT_COORDINATION_PROTOCOL.md
- PLANNING/CRITICAL_PATH_ANALYSIS.md
- Planner_Operating_Manual.md

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
