# EXAMPLE GUIDELINE - Error Handling (Reference)

> **THIS IS AN EXAMPLE** from the framework FileSystem project.
> Use this as a REFERENCE for structure and format.
> Create YOUR OWN guidelines for your business needs.
>
> **For a SaaS/SMMA marketing agency, consider guidelines like:**
> - `client-communication-standards.md` - Response times, tone, escalation paths
> - `content-review-process.md` - Approval workflow, QA checklists
> - `campaign-naming-conventions.md` - UTM patterns, ad naming, folder structure
> - `data-retention-policy.md` - Client data handling, GDPR compliance
> - `brand-voice-guidelines.md` - Messaging consistency across channels

---

# Error Handling Standards Guidelines

**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** HIGH - Code Quality

## Overview

This document defines the error handling standards for all code. Proper error handling ensures system reliability and debuggability.

## Core Principles

1. **Fail Fast:** Detect errors early, don't propagate invalid state
2. **Fail Loud:** Log errors with context, never silently ignore
3. **Fail Safe:** Graceful degradation when possible
4. **Fail Traceable:** Include enough context for debugging

## Error Categories

### 1. Recoverable Errors
Errors that can be handled and execution can continue.

```python
# Good: Handle and continue
try:
    result = fetch_data(url)
except NetworkError as e:
    logger.warning(f"Network error, using cache: {e}")
    result = get_cached_data()
```

### 2. Non-Recoverable Errors
Errors that require stopping execution.

```python
# Good: Fail with context
if not config_file.exists():
    raise ConfigurationError(
        f"Required config file not found: {config_file}",
        suggestion="Run 'saf init' to create config"
    )
```

### 3. Validation Errors
Input validation failures.

```python
# Good: Clear validation error
def validate_task_id(task_id: str) -> None:
    if not re.match(r'^task-\d+\.\d+$', task_id):
        raise ValidationError(
            f"Invalid task ID format: {task_id}",
            expected="task-X.Y (e.g., task-2.3)"
        )
```

## Error Handling Patterns

### Pattern 1: Try-Except with Logging
```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise OperationError(f"Failed to complete: {e}") from e
```

### Pattern 2: Context Managers
```python
@contextmanager
def safe_file_operation(path: Path):
    try:
        yield open(path, 'r')
    except FileNotFoundError:
        raise FileError(f"File not found: {path}")
    except PermissionError:
        raise FileError(f"Permission denied: {path}")
```

### Pattern 3: Result Types
```python
from dataclasses import dataclass
from typing import Union

@dataclass
class Success:
    value: Any

@dataclass
class Failure:
    error: str
    code: str

Result = Union[Success, Failure]

def safe_parse(data: str) -> Result:
    try:
        return Success(json.loads(data))
    except json.JSONDecodeError as e:
        return Failure(str(e), "PARSE_ERROR")
```

## Error Message Format

### Required Components
1. **What happened:** Clear description of the error
2. **Where:** File, function, or component
3. **Why:** Root cause if known
4. **How to fix:** Actionable suggestion

### Example
```
ERROR: Template validation failed
  File: .task/wiring.yaml
  Reason: Template 'service-base@1.5.0' is deprecated
  Fix: Update to 'service-base@2.0.0' or use 'service-golden@1.0.0'
  See: PLANNING/TEMPLATE_EVOLUTION_STRATEGY.md
```

## Logging Standards

### Log Levels
| Level | Use Case |
|-------|----------|
| DEBUG | Detailed diagnostic info |
| INFO | Normal operation events |
| WARNING | Unexpected but handled |
| ERROR | Failed operation |
| CRITICAL | System failure |

### Log Context
```python
logger.error(
    "Stage gate failed",
    extra={
        "task_id": task_id,
        "stage": "TESTING",
        "gate": "coverage_check",
        "threshold": 80,
        "actual": 65,
    }
)
```

## Anti-Patterns

### Don't: Catch and Ignore
```python
# BAD
try:
    risky_operation()
except Exception:
    pass  # Silent failure!
```

### Don't: Catch Too Broadly
```python
# BAD
try:
    result = complex_operation()
except Exception as e:  # Catches everything
    print(f"Error: {e}")
```

### Don't: Lose Context
```python
# BAD
try:
    result = operation()
except SpecificError:
    raise GenericError("Something went wrong")  # Lost original error
```

## Error Recovery

### Automatic Recovery
```python
@retry(max_attempts=3, backoff=exponential)
def fetch_with_retry(url: str) -> Response:
    return requests.get(url, timeout=30)
```

### Manual Recovery
```python
def safe_operation_with_recovery():
    try:
        return primary_operation()
    except PrimaryError:
        logger.warning("Primary failed, trying fallback")
        return fallback_operation()
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
