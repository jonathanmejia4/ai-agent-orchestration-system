# Documentation Standards Guidelines
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** MEDIUM - Documentation Quality

## Overview

This document defines the documentation standards for all artifacts, including code, configuration, and planning documents.

## Documentation Types

### 1. Code Documentation

#### Docstrings (Required for Public APIs)
```python
def validate_task(task_id: str, strict: bool = False) -> ValidationResult:
    """Validate a task against framework requirements.

    Args:
        task_id: The unique identifier for the task (format: task-X.Y)
        strict: If True, treat warnings as errors

    Returns:
        ValidationResult containing status and any issues found

    Raises:
        TaskNotFoundError: If task_id doesn't exist
        ValidationError: If task fails validation in strict mode

    Example:
        >>> result = validate_task("task-2.3")
        >>> if result.is_valid:
        ...     print("Task is valid")
    """
```

#### Inline Comments (For Complex Logic)
```python
# Calculate critical path using Kahn's algorithm
# Time complexity: O(V + E) where V = tasks, E = dependencies
def calculate_critical_path(graph: DAG) -> List[Task]:
    # Initialize in-degree map for topological sort
    in_degree = {node: 0 for node in graph.nodes}
    ...
```

### 2. Configuration Documentation

#### YAML Headers
```yaml
# Stage Gates Configuration
# Version: 1.0.0
# Last Updated: 2025-12-25
# Owner: PM
# Classification: HIGH - Pipeline Control
#
# Purpose: Defines stage gate validators and rollback behavior
# Related: PLANNING/TASK_LIFECYCLE_STAGES.md
```

#### Inline Explanations
```yaml
stages:
  stage_2_plugin_attachment:
    gates:
      - id: plugin_compatibility
        name: "Plugin Compatibility Check"
        # Prevents incompatible plugin combinations (e.g., caching + real-time)
        # that would cause runtime errors in Stage 3
        validator: "tools/plugin_compatibility_checker.py"
```

### 3. Planning Documents

#### Standard Header
```markdown
# Document Title
**Version:** X.Y.Z
**Last Updated:** YYYY-MM-DD
**Owner:** [PM|Planner|Builder|Critic]
**Classification:** [CRITICAL|HIGH|MEDIUM|LOW]

## Overview
Brief description of document purpose.
```

#### Section Structure
1. Overview (what and why)
2. Details (how)
3. Examples (show, don't just tell)
4. Related Documents (cross-references)

### 4. API Documentation

```markdown
## Endpoint: POST /api/tasks

Create a new task.

### Request
```json
{
  "name": "api-gateway",
  "type": "feature",
  "template": "service-base@2.0.0"
}
```

### Response
```json
{
  "task_id": "task-2.3",
  "status": "created",
  "next_stage": "PLANNING"
}
```

### Errors
| Code | Description |
|------|-------------|
| 400 | Invalid request body |
| 409 | Task already exists |
```

## Documentation Requirements

### Required Documentation
| Artifact | Documentation Required |
|----------|----------------------|
| Public API | Docstring + examples |
| Configuration | Header + inline comments |
| PLANNING docs | Full structure |
| Tools | Usage help + examples |

### Optional Documentation
| Artifact | When to Document |
|----------|-----------------|
| Private functions | Complex logic only |
| Tests | Non-obvious setup |
| Internal modules | Architecture decisions |

## Quality Standards

### Clarity
- Use simple, direct language
- Define acronyms on first use
- Include examples for complex concepts

### Completeness
- Document all public interfaces
- Include error cases
- Provide troubleshooting tips

### Currency
- Update docs with code changes
- Include last updated date
- Mark deprecated content

### Consistency
- Follow standard formats
- Use consistent terminology
- Match existing style

## Documentation Review

Documentation is reviewed as part of Critic review:
- Accuracy: Does it match the code?
- Completeness: Are all public APIs documented?
- Clarity: Is it understandable?

## Tools

### Docstring Checker
```bash
# Check docstring coverage
tools/doc_coverage.py --path src/
```

### Markdown Linter
```bash
# Lint markdown files
markdownlint PLANNING/*.md
```

## Examples

### Good Documentation
```python
def calculate_quality_score(metrics: QAMetrics) -> float:
    """Calculate overall quality score from individual metrics.

    The score is a weighted average of:
    - Test coverage (25%)
    - Security score (30%)
    - Lint score (15%)
    - Complexity (15%)
    - Documentation (15%)

    Args:
        metrics: QAMetrics object with individual scores

    Returns:
        Float between 0.0 and 100.0 representing overall quality

    Example:
        >>> metrics = QAMetrics(coverage=85, security=100, lint=95)
        >>> score = calculate_quality_score(metrics)
        >>> print(f"Quality: {score:.1f}%")
        Quality: 91.5%
    """
```

### Poor Documentation
```python
def calc_score(m):
    """Calculate score."""  # Too brief, no args/returns
    return m.c * 0.25 + m.s * 0.3 + m.l * 0.15  # Unclear abbreviations
```

## Related Documents
- .claude/guidelines/builder-quality-standards.md
- PLANNING/GOVERNANCE_MODEL.md

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
