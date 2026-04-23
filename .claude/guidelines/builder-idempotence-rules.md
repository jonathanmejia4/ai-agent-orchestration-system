# Builder Idempotence Rules

**Document Version:** 1.0.0
**Last Updated:** 2025-12-24
**Owner:** PM
**Classification:** CRITICAL - Agent Behavior

## Purpose

This document defines idempotence requirements for the Builder agent. All Builder operations MUST be idempotent - running the same operation multiple times produces the same result as running it once.

## Core Principles

### 1. Repeatability
Every Builder operation must be safely repeatable without side effects:
- Running a build twice produces identical output
- Re-applying a change doesn't corrupt state
- Interrupted operations can be restarted cleanly

### 2. Determinism
Given the same inputs, Builder must produce the same outputs:
- No random values without seeds
- No timestamp-dependent logic in generated code
- No environment-specific behavior

### 3. Atomicity
Operations must complete fully or not at all:
- Partial changes must be rolled back
- State files must be consistent
- No orphaned resources

## Idempotence Requirements

### File Operations

#### MUST DO
```python
# Idempotent file write - same content = no change
def write_file_idempotent(path, content):
    if path.exists():
        existing = path.read_text()
        if existing == content:
            return  # No change needed
    path.write_text(content)
```

#### MUST NOT DO
```python
# Non-idempotent - appends on every run
def write_file_bad(path, content):
    with open(path, 'a') as f:
        f.write(content)  # WRONG: accumulates
```

### Directory Operations

#### MUST DO
```python
# Idempotent directory creation
def ensure_directory(path):
    path.mkdir(parents=True, exist_ok=True)
```

#### MUST NOT DO
```python
# Non-idempotent - fails on second run
def create_directory_bad(path):
    path.mkdir()  # WRONG: raises if exists
```

### State Modifications

#### MUST DO
```yaml
# Check current state before modifying
steps:
  - check: "Is target state already achieved?"
  - skip_if: "State matches desired"
  - apply: "Only if change needed"
  - verify: "Confirm state matches expected"
```

#### MUST NOT DO
```yaml
# Blind state modification
steps:
  - apply: "Change without checking"  # WRONG
```

## Idempotence Patterns

### Pattern 1: Check-Then-Act

```python
def idempotent_operation(target_state):
    current_state = get_current_state()
    if current_state == target_state:
        log("Already in target state, skipping")
        return
    apply_changes(target_state)
    verify_state(target_state)
```

### Pattern 2: Declarative State

```yaml
# Declare desired state, not actions
task:
  task_id: task-1.1
  status: completed  # Desired state
  files:
    - path: src/main.py
      content_hash: abc123  # Expected content
```

### Pattern 3: Transactional Changes

```python
def atomic_update(work_order):
    backup = create_backup()
    try:
        apply_changes(work_order)
        verify_changes(work_order)
        commit_changes()
    except Exception:
        restore_backup(backup)
        raise
    finally:
        cleanup_backup(backup)
```

### Pattern 4: Content-Addressed Storage

```python
def store_artifact(content):
    hash = sha256(content)
    path = f"artifacts/{hash}"
    if not path.exists():
        write_file(path, content)
    return hash
```

## Prohibited Practices

### 1. Timestamps in Generated Code

```python
# WRONG - different output each run
def generate_file():
    return f"# Generated at {datetime.now()}"

# CORRECT - no timestamps in content
def generate_file():
    return "# Generated file"
```

### 2. Random Values Without Seeds

```python
# WRONG - non-deterministic
def generate_id():
    return uuid4()

# CORRECT - deterministic from inputs
def generate_id(work_order_id, sequence):
    return f"{work_order_id}-{sequence:03d}"
```

### 3. Cumulative Modifications

```python
# WRONG - accumulates on each run
def update_log(entry):
    with open("log.txt", "a") as f:
        f.write(entry)

# CORRECT - replace entire file or use append-log with dedup
def update_log(entries):
    unique_entries = deduplicate(entries)
    write_file("log.txt", "\n".join(unique_entries))
```

### 4. Order-Dependent Operations

```python
# WRONG - result depends on execution order
def apply_changes(changes):
    for change in changes:
        apply(change)

# CORRECT - sort for deterministic order
def apply_changes(changes):
    for change in sorted(changes, key=lambda c: c.priority):
        apply(change)
```

## Verification Checklist

Before completing any work order, Builder MUST verify:

```yaml
# Aligned with tools/idempotence_validator.py (Checks 1-6)
# Checks 1-5 are HARD requirements, Check 6 is SOFT

idempotence_checklist:
  - name: "Contract declared"
    check: "Is idempotence contract declared in .task/wiring.yaml?"
    validator_check: "Check 1"
    required: HARD

  - name: "No timestamps"
    check: "Are generated files timestamp-free?"
    validator_check: "Check 2"
    required: HARD

  - name: "Canonicalization"
    check: "Are all outputs canonicalized (sorted, normalized)?"
    validator_check: "Check 3"
    required: HARD

  - name: "No file reads"
    check: "Does code avoid file reads within idempotent operations?"
    validator_check: "Check 4"
    required: HARD

  - name: "Idempotence test"
    check: "Does test verify re-run produces identical output?"
    validator_check: "Check 5"
    required: HARD

  - name: "Formatter locked"
    check: "Is code formatter version locked for deterministic formatting?"
    validator_check: "Check 6"
    required: SOFT
```

## Testing Idempotence

### Automated Test

```python
def test_idempotence(work_order):
    # First run
    result1 = execute_work_order(work_order)
    state1 = capture_state()

    # Second run (should be no-op)
    result2 = execute_work_order(work_order)
    state2 = capture_state()

    # Verify identical results
    assert result1 == result2, "Results must match"
    assert state1 == state2, "State must not change"
    assert count_file_modifications() == 0, "No files should change"
```

### Manual Verification

1. Execute work order
2. Record all file modifications
3. Execute work order again
4. Verify no new modifications
5. Verify state unchanged

## Exception Handling

### Recoverable Failures

```python
def recoverable_operation():
    checkpoint = save_checkpoint()
    try:
        perform_operation()
    except RecoverableError:
        restore_checkpoint(checkpoint)
        # Safe to retry
        raise RetryableError()
```

### Non-Recoverable Failures

```python
def critical_operation():
    if not can_safely_proceed():
        raise NonRecoverableError("Cannot proceed safely")
    # Only proceed if idempotence guaranteed
    perform_operation()
```

## State File Requirements

### Format Requirements

```yaml
# State files must be:
# 1. Fully serializable
# 2. Deterministically ordered
# 3. Hash-verifiable

state:
  version: "1.0.0"
  last_hash: "sha256:abc123..."
  entries:
    - key: "sorted_key_1"
      value: "value_1"
    - key: "sorted_key_2"
      value: "value_2"
```

### Update Protocol

```python
def update_state(new_data):
    current = load_state()
    merged = merge_state(current, new_data)
    if compute_hash(merged) == current.last_hash:
        return  # No change
    merged.last_hash = compute_hash(merged)
    save_state(merged)
```

## Integration Points

### With Critic

Critic verifies idempotence as part of review:
- Check for timestamp pollution
- Verify deterministic outputs
- Test re-run safety

### With PM

PM tracks idempotence failures:
- Escalate violations
- Update work order requirements
- Enforce compliance

## Monitoring

Track these metrics:

```yaml
idempotence_metrics:
  total_operations: count
  idempotent_verified: count
  violations_detected: count
  retry_count: count
  rollback_count: count
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-24 | Initial version |
