# Planner Templates Guidelines
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** MEDIUM - Planning Artifacts

## Overview

This document provides templates for Planner output artifacts, ensuring consistent and complete planning documentation.

## Action Plan Template

```yaml
# .task/execution_plan.yaml
version: "1.0.0"

metadata:
  task_id: "<task-id>"
  work_order_id: "<work-order-id>"
  created_by: "Planner"
  created_at: "<ISO-8601 timestamp>"
  approved_by: null  # PM fills this
  approved_at: null

summary:
  title: "<Brief description of the task>"
  type: "<feature|fix|refactor|infrastructure>"
  estimated_duration: "<ISO 8601 duration, e.g., PT4H>"
  complexity: "<low|medium|high>"
  risk_level: "<low|medium|high>"

objectives:
  - "<Primary objective>"
  - "<Secondary objective>"

constraints:
  - "<Constraint from work order>"
  - "<Technical constraint>"

actions:
  - action_id: "ACT-001"
    type: "create_file"  # create_file|modify_file|delete_file|create_directory|run_command|run_tests|review|validate|document|configure|integrate|deploy|other
    description: "<Detailed description of what this action accomplishes>"
    status: "pending"  # pending|in_progress|completed|blocked|cancelled
    estimated_hours: <number>
    dependencies: []
    assigned_to: "Builder"
    acceptance_criteria:
      - "<Criterion 1>"
      - "<Criterion 2>"

  - action_id: "ACT-002"
    type: "modify_file"
    description: "<Detailed description>"
    status: "pending"
    dependencies: ["ACT-001"]
    # ... more fields

risks:
  - id: "risk-001"
    description: "<Risk description>"
    probability: "<low|medium|high>"
    impact: "<low|medium|high>"
    mitigation: "<Mitigation strategy>"

success_criteria:
  - "<Overall success criterion 1>"
  - "<Overall success criterion 2>"

notes: |
  Additional context or considerations for Builder.
```

## Dependency Graph Template

```yaml
# .task/deps.yaml
version: "1.0.0"

task_id: "<task-id>"
generated_at: "<ISO-8601 timestamp>"

# Internal action dependencies
action_dependencies:
  ACT-001: []
  ACT-002: ["ACT-001"]
  ACT-003: ["ACT-001"]
  ACT-004: ["ACT-002", "ACT-003"]

# External task dependencies
task_dependencies:
  - task_id: "<other-task-id>"
    type: "<hard|soft>"
    reason: "<Why this dependency exists>"
    status: "<pending|available>"

# Package dependencies
package_dependencies:
  - name: "<package-name>"
    version: "<version-constraint>"
    purpose: "<Why needed>"

# Service dependencies
service_dependencies:
  - name: "<service-name>"
    required_for: ["ACT-002", "ACT-003"]
    mock_available: <true|false>

# Dependency analysis
analysis:
  total_actions: <number>
  max_depth: <number>
  critical_path: ["ACT-001", "ACT-002", "ACT-004"]
  parallelizable_groups:
    - ["ACT-002", "ACT-003"]
```

## Wiring Template (Section 1 - Planner)

```yaml
# .task/wiring.yaml (Planner fills Section 1)
version: "1.0.0"

task_id: "<task-id>"

# Section 1: Template Selection (Planner)
templates:
  primary:
    id: "<template-id>"
    version: "<pinned-version>"
    source: "registry"
    reason: "<Why this template>"

  plugins:
    - id: "<plugin-id>"
      version: "<pinned-version>"
      extension_point: "<where-attached>"
      configuration:
        key: value

  variants:
    - id: "<variant-id>"
      applies_to: "<template-id>"

# Section 2: Structural Output (Builder fills after Stage 1)
# structural:
#   files_generated: []
#   extension_points: []

# Section 3: Behavioral Output (Builder fills after Stage 3)
# behavioral:
#   files_generated: []
#   protected_regions: []
```

## Risk Assessment Template

```yaml
# Embedded in execution_plan.yaml or separate file

risks:
  technical:
    - id: "tech-001"
      category: "complexity"
      description: "Complex authentication flow"
      probability: "medium"
      impact: "high"
      mitigation: "Spike first, prototype approach"
      contingency: "Fall back to simpler auth"

  schedule:
    - id: "sched-001"
      category: "dependency"
      description: "Waiting on auth-service task"
      probability: "low"
      impact: "high"
      mitigation: "Mock auth-service for development"
      contingency: "Reorder tasks"

  resource:
    - id: "res-001"
      category: "availability"
      description: "Builder may have competing priorities"
      probability: "medium"
      impact: "medium"
      mitigation: "Front-load critical tasks"
```

## Estimation Template

```yaml
# Action estimation breakdown

estimates:
  ACT-001:
    optimistic_hours: 1
    likely_hours: 2
    pessimistic_hours: 4
    # PERT estimate: (O + 4L + P) / 6 = 2.17 hours

  ACT-002:
    optimistic_hours: 2
    likely_hours: 4
    pessimistic_hours: 8
    # PERT estimate: 4.33 hours

summary:
  total_optimistic: 3
  total_likely: 6
  total_pessimistic: 12
  pert_estimate: 6.5
  confidence_level: "medium"
  buffer_percentage: 20
  final_estimate: 7.8
```

## Handoff Checklist

Before requesting PM approval:

```markdown
## Action Plan Checklist

- [ ] All work order requirements addressed
- [ ] Tasks decomposed to <8 hour chunks
- [ ] Dependencies identified and documented
- [ ] Template versions pinned
- [ ] Risks assessed with mitigations
- [ ] Success criteria defined
- [ ] Estimates provided

## Validation

- [ ] `tools/validate_action_plan.py` passes
- [ ] `tools/find_cycles.py` finds no cycles
- [ ] `tools/template_version_checker.py` passes

## Handoff

- [ ] Execution plan in `.task/execution_plan.yaml`
- [ ] Dependencies in `.task/deps.yaml`
- [ ] Wiring Section 1 in `.task/wiring.yaml`
- [ ] Ready for PM review
```

## Related Documents
- PLANNING/Agent_Decision_Matrix.md
- PLANNING/CRITICAL_PATH_ANALYSIS.md
- .claude/guidelines/planner-constraints.md

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
