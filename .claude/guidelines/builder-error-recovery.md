# Builder Error Recovery Guide

**Document Version:** 1.0.0
**Last Updated:** 2025-12-24
**Owner:** PM
**Classification:** HIGH - Agent Guidelines

## Purpose

This guide provides Builder agents with procedures for recovering from common errors during task implementation. It ensures consistent error handling and prevents cascading failures.

---

## 1. Error Classification

### 1.1 Error Severity Levels

| Level | Description | Recovery Time | Escalation |
|-------|-------------|--------------|------------|
| **CRITICAL** | Work cannot continue | Immediate | Required |
| **HIGH** | Major functionality blocked | < 30 minutes | If unresolved |
| **MEDIUM** | Partial functionality affected | < 1 hour | Optional |
| **LOW** | Minor issues, workarounds exist | < 2 hours | Not required |

### 1.2 Error Categories

1. **Compilation/Syntax Errors** - Code won't parse
2. **Runtime Errors** - Code fails during execution
3. **Test Failures** - Tests don't pass
4. **Dependency Errors** - Missing or incompatible dependencies
5. **Environment Errors** - System/configuration issues
6. **Integration Errors** - External service failures
7. **Resource Errors** - Memory, disk, timeout issues

---

## 2. Recovery Procedures by Error Type

### 2.1 Compilation/Syntax Errors

**Symptoms:**
- Import errors
- SyntaxError exceptions
- IndentationError
- NameError for undefined variables

**Recovery Steps:**

```python
# Step 1: Identify the error location
# Read the full error traceback

# Step 2: Check for common issues
common_issues = [
    "Missing import statement",
    "Typo in variable/function name",
    "Incorrect indentation",
    "Missing closing bracket/quote",
    "Python version incompatibility"
]

# Step 3: Fix and verify
# Make minimal change to fix the issue
# Run syntax check: python -m py_compile <file>

# Step 4: Run full test suite
# pytest tests/ -v
```

**Prevention:**
- Use IDE/linter for real-time feedback
- Run `ruff check` before committing
- Follow consistent code style

### 2.2 Runtime Errors

**Symptoms:**
- TypeError, ValueError during execution
- AttributeError on object access
- KeyError, IndexError on collections

**Recovery Steps:**

```python
# Step 1: Capture full stack trace
import traceback
try:
    # problematic code
    pass
except Exception as e:
    traceback.print_exc()
    # Log to LogBook/builder/errors/

# Step 2: Add defensive checks
def safe_operation(data):
    if data is None:
        return default_value
    if not isinstance(data, expected_type):
        raise TypeError(f"Expected {expected_type}, got {type(data)}")
    return process(data)

# Step 3: Add unit test for error case
def test_handles_none_input():
    result = safe_operation(None)
    assert result == default_value

# Step 4: Document the fix
# Add comment explaining why check was added
```

**Prevention:**
- Type hints with runtime validation
- Defensive programming
- Comprehensive error handling

### 2.3 Test Failures

**Symptoms:**
- pytest reports failures
- Assertions don't match expected values
- Test timeouts

**Recovery Steps:**

```python
# Step 1: Isolate failing test
# pytest tests/test_module.py::test_specific -v

# Step 2: Analyze failure
"""
Common failure patterns:
1. Expected value changed - Update test or fix code
2. Test environment issue - Check fixtures
3. Timing/race condition - Add synchronization
4. Mock not matching - Update mock setup
"""

# Step 3: Debug with verbose output
# pytest tests/test_module.py -v --tb=long

# Step 4: Fix based on root cause
# If test is wrong: Update test
# If code is wrong: Fix code and verify

# Step 5: Run related tests
# pytest tests/ -k "related_feature"

# Step 6: Run full suite before commit
# pytest tests/ --tb=short
```

**Prevention:**
- Write tests before code (TDD)
- Use fixtures for consistent setup
- Avoid flaky tests (no random, proper async handling)

### 2.4 Dependency Errors

**Symptoms:**
- ModuleNotFoundError
- ImportError
- Version conflicts
- pip install failures

**Recovery Steps:**

```bash
# Step 1: Identify missing dependency
pip show <package>  # Check if installed

# Step 2: Check version requirements
pip show <package> | grep Version
# Compare with requirements.txt

# Step 3: Install or fix version
pip install <package>==<version>

# Step 4: Update requirements
pip freeze | grep <package> >> requirements.txt

# Step 5: Verify import works
python -c "import <package>; print(<package>.__version__)"
```

**Escalation Trigger:**
- Dependency requires system-level changes
- Version conflict with existing code
- Security vulnerability in dependency

### 2.5 Environment Errors

**Symptoms:**
- Permission denied
- File not found (config, resources)
- Environment variable missing
- Port already in use

**Recovery Steps:**

```python
# Step 1: Check environment
import os
import sys

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"PATH: {os.environ.get('PATH', 'NOT SET')}")

# Step 2: Verify required files exist
required_files = [
    "config/settings.yaml",
    ".env",
]
for f in required_files:
    if not os.path.exists(f):
        print(f"MISSING: {f}")

# Step 3: Check permissions
import stat
file_stat = os.stat("some_file")
print(f"Permissions: {oct(file_stat.st_mode)}")

# Step 4: Create missing resources with defaults
if not os.path.exists("config/settings.yaml"):
    # Create with safe defaults
    create_default_config()
```

**Escalation Trigger:**
- Requires admin/root access
- External system configuration needed
- Security-sensitive changes required

### 2.6 Integration Errors

**Symptoms:**
- Connection refused/timeout
- HTTP 4xx/5xx errors
- Authentication failures
- Data format mismatches

**Recovery Steps:**

```python
# Step 1: Verify service availability
import requests

def check_service(url):
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Service unavailable: {e}")
        return False

# Step 2: Implement retry logic
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def call_external_service():
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Step 3: Add fallback/circuit breaker
class CircuitBreaker:
    def __init__(self, failure_threshold=5):
        self.failures = 0
        self.threshold = failure_threshold
        self.is_open = False

    def call(self, func):
        if self.is_open:
            return fallback_response()
        try:
            result = func()
            self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.is_open = True
            raise

# Step 4: Mock for testing
# Create mock responses for unit tests
# Don't depend on external services in tests
```

**Escalation Trigger:**
- External service is down (not Builder's issue)
- API contract changed
- Authentication credentials invalid

### 2.7 Resource Errors

**Symptoms:**
- MemoryError
- Disk full
- Process timeout
- Too many open files

**Recovery Steps:**

```python
# Step 1: Identify resource usage
import psutil

def check_resources():
    print(f"Memory: {psutil.virtual_memory().percent}%")
    print(f"Disk: {psutil.disk_usage('/').percent}%")
    print(f"CPU: {psutil.cpu_percent()}%")

# Step 2: Optimize memory usage
# Use generators instead of lists
def process_large_file(filename):
    with open(filename) as f:
        for line in f:  # Generator, not f.readlines()
            yield process_line(line)

# Step 3: Clean up resources
import gc
gc.collect()  # Force garbage collection

# Step 4: Add resource limits
import resource
# Limit memory to 1GB
resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))

# Step 5: Implement chunked processing
def process_in_chunks(data, chunk_size=1000):
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        process_chunk(chunk)
        gc.collect()  # Clean up after each chunk
```

**Escalation Trigger:**
- Requires infrastructure changes
- Data volume exceeds capacity
- System resources consistently exhausted

---

## 3. Escalation Procedures

### 3.1 When to Escalate

**Immediate Escalation (CRITICAL):**
- Security vulnerability discovered
- Data corruption risk
- Cannot proceed without PM decision
- External system outage

**Escalate if Unresolved (HIGH):**
- Error persists after 30 minutes of debugging
- Requires changes outside task scope
- Need clarification on requirements

### 3.2 Escalation Format

```yaml
# Log to: LogBook/pm/escalations/
escalation:
  timestamp: "2025-12-24T10:30:00Z"
  agent: "builder"
  task_id: "task001"

  error:
    type: "integration_error"
    severity: "HIGH"
    message: "Cannot connect to authentication service"
    stack_trace: |
      Traceback (most recent call last):
        File "src/auth.py", line 42, in authenticate
          response = requests.post(auth_url, json=payload)
        requests.exceptions.ConnectionError: Connection refused

  attempted_recovery:
    - "Verified service URL is correct"
    - "Checked network connectivity"
    - "Attempted retry with exponential backoff"
    - "Reviewed service documentation"

  blocking: true
  impact: "Cannot complete authentication module"

  request:
    type: "external_assistance"
    message: "Need confirmation that auth service is available"
```

---

## 4. Recovery Checklists

### 4.1 Before Attempting Recovery

- [ ] Capture full error message and stack trace
- [ ] Note the exact command/operation that failed
- [ ] Check if error is reproducible
- [ ] Review recent changes that might have caused the error
- [ ] Check if same error exists in similar code

### 4.2 After Successful Recovery

- [ ] Verify the original operation now succeeds
- [ ] Run related tests to check for side effects
- [ ] Document the fix in code comments if non-obvious
- [ ] Add test case to prevent regression
- [ ] Update LogBook with recovery details
- [ ] Consider if similar issues might exist elsewhere

### 4.3 After Escalation

- [ ] Continue work on non-blocked items if possible
- [ ] Document workarounds attempted
- [ ] Prepare detailed context for PM
- [ ] Be ready to implement PM's solution quickly

---

## 5. Error Logging Requirements

### 5.1 Required Log Fields

```yaml
# LogBook/builder/errors/<task_id>_<timestamp>.yaml
error_log:
  task_id: "task001"
  timestamp: "2025-12-24T10:30:00Z"

  error:
    type: "runtime_error"
    class: "ValueError"
    message: "Invalid input format"
    file: "src/parser.py"
    line: 42
    stack_trace: |
      ...

  context:
    operation: "Parsing configuration file"
    input_summary: "YAML file, 150 lines"
    environment: "Python 3.11, Ubuntu 22.04"

  resolution:
    status: "resolved"  # resolved, escalated, workaround
    method: "Added input validation"
    time_to_resolve_minutes: 15
    changes_made:
      - file: "src/parser.py"
        description: "Added schema validation before parsing"
```

### 5.2 Error Pattern Tracking

Log recurring errors to identify systemic issues:

```yaml
error_pattern:
  pattern_id: "PARSE-001"
  description: "YAML parsing fails on special characters"
  occurrences: 3
  first_seen: "2025-12-20"
  last_seen: "2025-12-24"
  recommended_fix: "Add input sanitization"
  status: "open"  # Track until permanently fixed
```

---

## 6. Prevention Strategies

### 6.1 Defensive Coding

```python
# Always validate inputs
def process_user_data(data: dict) -> Result:
    # Validate required fields
    required = ["name", "email", "role"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # Validate types
    if not isinstance(data["name"], str):
        raise TypeError("name must be string")

    # Validate values
    if data["role"] not in VALID_ROLES:
        raise ValueError(f"Invalid role: {data['role']}")

    # Now safe to process
    return do_processing(data)
```

### 6.2 Error Boundaries

```python
# Contain errors at boundaries
class ErrorBoundary:
    def __init__(self, fallback_value=None):
        self.fallback = fallback_value
        self.errors = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.errors.append({
                "type": exc_type.__name__,
                "message": str(exc_val)
            })
            # Log but don't propagate
            return True
        return False

# Usage
with ErrorBoundary(fallback_value=[]) as boundary:
    result = risky_operation()
if boundary.errors:
    log_errors(boundary.errors)
    result = boundary.fallback
```

---

## Related Documents

- [AGENT_FAILURE_HANDLING_PROTOCOL.md](../../PLANNING/AGENT_FAILURE_HANDLING_PROTOCOL.md)
- [error-handling-standards.md](./error-handling-standards.md)
- [builder-scope-enforcement.md](./builder-scope-enforcement.md)
- [FAILURE_MODES.md](../../PLANNING/FAILURE_MODES.md)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
