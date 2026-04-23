# Planner Best Practices Guide

**Document Version:** 1.0.0
**Last Updated:** 2025-12-24
**Owner:** PM
**Classification:** HIGH - Agent Guidelines

## Purpose

This guide provides best practices for the Planner agent to ensure effective task decomposition, accurate dependency mapping, and quality work order generation.

---

## 1. Task Decomposition Principles

### 1.1 Right-Sizing Tasks

**DO:**
- Create tasks that represent a single, cohesive unit of work
- Target ≤4 hours of builder effort per task (hard constraint)
- Ensure each task has a clear, testable outcome
- Include all necessary context for independent execution

**DON'T:**
- Create tasks that exceed 4 hours (decompose further)
- Create trivial tasks (<30 minutes effort)
- Split logically connected code across multiple tasks
- Create tasks with circular dependencies

### 1.2 Decomposition Strategy

```yaml
# Good decomposition example
work_order:
  task-1.1:
    scope: "User authentication module"
    includes:
      - Login endpoint
      - Session management
      - Token validation
    excludes:
      - User registration (separate task)
      - Password reset (separate task)

  task-1.2:
    scope: "User registration module"
    depends_on: [task-1.1]  # Uses auth types
```

### 1.3 Scope Boundaries

Define clear boundaries for each task:

| Good Boundary | Bad Boundary |
|--------------|--------------|
| Single API endpoint + tests | "All API endpoints" |
| One data model + repository | "Database layer" |
| Specific feature component | "Frontend improvements" |
| Integration adapter | "All external services" |

---

## 2. Dependency Mapping

### 2.1 Dependency Types

1. **Hard Dependencies** - Must complete before work can begin
   ```yaml
   depends_on:
     - task-1.1  # Required types/interfaces
   ```

2. **Soft Dependencies** - Preferred order but not blocking
   ```yaml
   preferred_after:
     - task-1.2  # Better if completed first
   ```

3. **Interface Dependencies** - Need interface definition only
   ```yaml
   requires_interface:
     - task-1.1.UserService  # Just the contract
   ```

### 2.2 Avoiding Cycles

Before finalizing dependencies:

```python
# Mental model for cycle detection
def check_for_cycles(task):
    visited = set()
    path = []

    def dfs(current):
        if current in path:
            raise CycleError(f"Cycle: {' -> '.join(path + [current])}")
        if current in visited:
            return

        visited.add(current)
        path.append(current)

        for dep in current.depends_on:
            dfs(dep)

        path.pop()

    dfs(task)
```

### 2.3 Dependency Best Practices

1. **Minimize cross-task dependencies**
   - If task A needs 5+ things from task B, consider merging

2. **Use interface-level dependencies when possible**
   - Define interfaces early, implement later

3. **Document why dependencies exist**
   ```yaml
   depends_on:
     - task-1.1  # Uses UserType and AuthService interface
   dependency_reason: "Requires user types for request validation"
   ```

---

## 3. Work Order Quality

### 3.1 Complete Work Orders

Every work order MUST include:

```yaml
work_order:
  id: "WO-20251224-001"
  created_at: "2025-12-24T10:00:00Z"

  # Context (WHY)
  objective: "Implement user authentication system"
  business_value: "Enable secure user access"

  # Scope (WHAT)
  tasks:
    - task_id: "task-1.1"
      description: "Authentication module"
      acceptance_criteria:
        - "Login endpoint returns JWT on valid credentials"
        - "Invalid credentials return 401"
        - "Unit test coverage > 80%"

  # Constraints (HOW)
  constraints:
    technology: ["Python 3.11+", "FastAPI"]
    patterns: ["Repository pattern", "Dependency injection"]

  # Dependencies (ORDER)
  execution_order:
    wave_1: [task001]
    wave_2: [task002, task003]  # Parallel after wave_1
```

### 3.2 Acceptance Criteria

Write SMART acceptance criteria:

| Attribute | Example |
|-----------|---------|
| **S**pecific | "Login endpoint at POST /api/auth/login" |
| **M**easurable | "Response time < 200ms for valid requests" |
| **A**chievable | Based on existing infrastructure |
| **R**elevant | Directly supports the objective |
| **T**ime-bound | Implied by task estimate |

### 3.3 Context Provision

Include sufficient context for Builder:

```yaml
task:
  id: task001

  # Essential context
  context:
    # What exists
    existing_code:
      - "src/models/user.py - User model already defined"
      - "src/db/session.py - Database session available"

    # What to create
    files_to_create:
      - "src/auth/service.py"
      - "src/auth/router.py"
      - "tests/test_auth.py"

    # Reference materials
    references:
      - "PLANNING/schemas/user.yaml"

    # Constraints
    must_follow:
      - "Use bcrypt for password hashing"
      - "JWT tokens expire in 24 hours"
```

---

## 4. Estimation Guidelines

### 4.1 Effort Estimation

Use this framework for estimates:

| Complexity | Effort | Characteristics |
|------------|--------|-----------------|
| Simple | 1-2 hours | Single file, clear pattern, no integration |
| Medium | 2-3 hours | 2-3 files, some integration, standard patterns |
| Complex | 3-4 hours | Multiple files, external integration, testing |
| Very Complex | >4 hours | MUST split into multiple tasks (≤4h constraint) |

### 4.2 Buffer Factors

Apply multipliers for:

- **New technology**: 1.5x
- **External integration**: 1.3x
- **Complex testing**: 1.2x
- **Unclear requirements**: 1.5x (consider clarifying first)

### 4.3 Parallel Work Calculation

```python
def calculate_critical_path(tasks):
    """Calculate minimum time with parallel execution."""
    waves = topological_sort_into_waves(tasks)

    total_time = 0
    for wave in waves:
        # Wave time is max of parallel tasks
        wave_time = max(task.estimate for task in wave)
        total_time += wave_time

    return total_time
```

---

## 5. Communication Patterns

### 5.1 Escalation Triggers

Escalate to PM when:

1. **Ambiguous requirements**
   ```yaml
   escalation:
     type: "clarification_needed"
     question: "Should authentication support OAuth2 or JWT only?"
     options: ["JWT only", "JWT + OAuth2", "OAuth2 only"]
     impact: "Affects task scope and dependencies"
   ```

2. **Scope creep detected**
   ```yaml
   escalation:
     type: "scope_change"
     original_scope: "User authentication"
     requested_scope: "User authentication + authorization + audit logging"
     recommendation: "Split into 3 work orders"
   ```

3. **Technical blockers**
   ```yaml
   escalation:
     type: "technical_blocker"
     blocker: "Required API endpoint not documented"
     suggested_resolution: "Need API spec from external team"
   ```

### 5.2 Progress Updates

Report progress at milestones:

```yaml
progress_update:
  work_order_id: "WO-20251224-001"
  status: "in_progress"
  completed_tasks: [task001, task002]
  in_progress_tasks: [task003]
  blocked_tasks: []
  completion_percent: 66
  estimated_completion: "2025-12-24T18:00:00Z"
```

---

## 6. Quality Checklist

Before submitting any work order, verify:

### Planning Quality
- [ ] Objective is clear and business-aligned
- [ ] All tasks have complete acceptance criteria
- [ ] Dependencies are mapped and cycle-free
- [ ] Estimates are realistic with appropriate buffers

### Technical Quality
- [ ] Task scope is appropriate (not too large/small)
- [ ] Files to create/modify are identified
- [ ] Required context is included
- [ ] Technology constraints are specified

### Process Quality
- [ ] Work order follows schema
- [ ] SSOT references are valid
- [ ] Cross-references are accurate
- [ ] Escalation points are identified

---

## 7. Anti-Patterns to Avoid

### 7.1 Planning Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Big Bang Task | Single task for entire feature | Decompose into 3-5 focused tasks |
| Micro Tasks | 10+ tiny tasks for simple feature | Combine related work |
| Hidden Dependencies | Unstated assumptions | Document all dependencies |
| Scope Creep | Adding features during planning | Stick to original objective |
| Gold Plating | Over-engineering in plans | YAGNI - plan only what's needed |

### 7.2 Communication Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Silent Blocker | Not escalating blockers | Escalate immediately |
| Assumption Making | Guessing requirements | Ask PM for clarification |
| Over-Communication | Constant trivial updates | Report at milestones only |
| Under-Documentation | Missing context in work orders | Use complete templates |

---

## 8. Templates

### 8.1 Work Order Template

```yaml
work_order:
  id: "WO-YYYY-NNN"
  version: "1.0.0"
  created_at: "YYYY-MM-DDTHH:MM:SSZ"
  created_by: "planner"

  objective: ""
  business_value: ""

  tasks:
    - task_id: ""
      description: ""
      estimated_hours: 0
      acceptance_criteria: []
      dependencies: []
      files_to_create: []
      files_to_modify: []

  constraints:
    technology: []
    patterns: []
    security: []

  execution_plan:
    wave_1: []
    wave_2: []

  risks:
    - risk: ""
      mitigation: ""

  notes: ""
```

### 8.2 Task Template

```yaml
task:
  id: ""
  work_order: ""

  scope:
    description: ""
    includes: []
    excludes: []

  acceptance_criteria:
    - criterion: ""
      verification: ""

  context:
    existing_code: []
    references: []
    constraints: []

  dependencies:
    hard: []
    soft: []
    interfaces: []

  estimate:
    hours: 0
    confidence: ""  # high/medium/low
    buffer_reason: ""
```

---

## Related Documents

- [Planner_Operating_Manual.md](../../PLANNING/Planner_Operating_Manual.md)
- [Planner_Decision_Matrix.md](../../PLANNING/Planner_Decision_Matrix.md)
- [work_order_schema.yaml](../../PLANNING/schemas/work_order_schema.yaml)
- [TASK_LIFECYCLE_STAGES.md](../../PLANNING/TASK_LIFECYCLE_STAGES.md)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
