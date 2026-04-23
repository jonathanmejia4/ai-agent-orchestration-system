# Testing Strategy Guidelines
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** HIGH - Quality Assurance

## Overview

This document defines the testing strategy for the framework tasks, including test types, coverage requirements, and best practices.

## Test Pyramid

```
        /       /  \      E2E Tests (10%)
      /----\     - User journeys
     /      \    - Critical paths
    /--------\   Integration Tests (20%)
   /          \  - Component interaction
  /------------\ - API contracts
 /              \ Unit Tests (70%)
/----------------\ - Functions
                   - Classes
                   - Modules
```

## Test Types

### 1. Unit Tests
Test individual functions and classes in isolation.

**Characteristics:**
- Fast (<100ms per test)
- No external dependencies
- Mocked dependencies
- High coverage (80%+)

**Example:**
```python
def test_validate_task_id_valid():
    assert validate_task_id("task-2.3") is True

def test_validate_task_id_invalid():
    with pytest.raises(ValidationError):
        validate_task_id("invalid-id")
```

### 2. Integration Tests
Test component interactions and external integrations.

**Characteristics:**
- Medium speed (1-10s per test)
- Real database (test instance)
- Mocked external services
- Focus on boundaries

**Example:**
```python
@pytest.mark.integration
def test_task_creation_flow(db_session):
    task = create_task("api-gateway", template="service-base@2.0.0")
    assert db_session.query(Task).get(task.id) is not None
    assert task.stage == "PLANNING"
```

### 3. Contract Tests
Verify adapter implementations match interface contracts.

**Characteristics:**
- Test interface compliance
- Run against all adapters
- Generated from interface definitions

**Example:**
```python
@pytest.mark.contract
def test_auth_provider_contract(auth_adapter):
    # All IAuthProvider implementations must pass these tests
    token = auth_adapter.authenticate("user", "pass")
    assert auth_adapter.validate_token(token) is True
    assert auth_adapter.get_user_id(token) == "user"
```

### 4. E2E Tests
Test complete user journeys.

**Characteristics:**
- Slow (30s+ per test)
- Real environment
- Critical paths only
- High value assertions

**Example:**
```python
@pytest.mark.e2e
def test_complete_task_lifecycle(browser):
    # Create task
    browser.create_task("test-task")

    # Wait for planning
    browser.wait_for_stage("PLANNING")

    # Approve and build
    browser.approve_action_plan()
    browser.wait_for_stage("COMPLETED")

    assert browser.get_task_status("test-task") == "COMPLETED"
```

### 5. Security Tests
Verify security requirements.

**Types:**
- Static analysis (SAST)
- Dependency scanning
- Secret detection
- Vulnerability checks

**Tools:**
```bash
tools/security_scanner.py --full
```

## Coverage Requirements

| Test Type | Coverage Target | Blocking |
|-----------|----------------|----------|
| Unit | 80% line | Yes |
| Unit | 70% branch | Warning |
| Integration | Critical paths | Yes |
| Contract | All adapters | Yes |
| E2E | Happy paths | Warning |

## Test Organization

```
tests/
├── conftest.py                  # Root-level shared fixtures and markers
├── test_*.py                    # Root-level tool tests (task_scanner, etc.)
├── unit/
│   ├── conftest.py              # Unit test fixtures
│   ├── test_validators/         # Validation test modules
│   │   └── test_yaml_validation.py
│   ├── test_generators/         # Generator test modules
│   │   └── test_content_generation.py
│   └── test_utilities/          # Utility test modules
│       └── test_common_utils.py
├── integration/
│   ├── README.md
│   ├── common/                  # Shared integration utilities
│   └── fixtures/                # Integration test fixtures
├── drift/
│   ├── conftest.py              # Drift test fixtures
│   ├── auth/                    # Auth template drift tests
│   └── api/                     # API template drift tests
├── security/                    # Security-focused tests
├── smoke/                       # Quick smoke tests
├── e2e/                         # End-to-end workflow tests
│   ├── __init__.py
│   ├── conftest.py              # E2E test fixtures
│   ├── test_full_workflows.py   # Full workflow tests
│   └── monetization/            # Monetization E2E tests
├── performance/                 # Performance benchmarks
│   ├── conftest.py              # Performance test fixtures
│   ├── README.md                # Performance testing guide
│   ├── test_api_performance.py  # API performance tests
│   ├── test_batch_performance.py # Batch operation tests
│   └── test_db_performance.py   # Database performance tests
├── fixtures/
│   ├── conftest.py
│   └── sample_data.yaml
└── mocks/
    ├── auth_mock.py              # Authentication mocking
    ├── payment_mock.py           # Payment service mocking
    └── storage_mock.py           # Storage/file system mocking

# Future directories (not yet implemented):
# └── contract/                  # Contract tests for adapters
```

## Test Naming

```python
# Pattern: test_<what>_<condition>_<expected>

def test_validate_task_id_with_valid_format_returns_true():
    ...

def test_validate_task_id_with_invalid_format_raises_error():
    ...

def test_create_task_when_template_missing_fails():
    ...
```

## Test Fixtures

### Shared Fixtures
```python
# conftest.py
@pytest.fixture
def sample_task():
    return Task(id="task-2.3", type="feature")

@pytest.fixture
def mock_auth_provider():
    return MockAuthProvider()
```

### Database Fixtures
```python
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
```

## Best Practices

### Do's
- Test behavior, not implementation
- Use descriptive test names
- Keep tests independent
- Use fixtures for setup
- Test edge cases

### Don'ts
- Don't test private methods directly
- Don't depend on test order
- Don't use sleep() for timing
- Don't ignore flaky tests
- Don't skip tests without reason

## Test Execution

### Local Development
```bash
# Run unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run specific test
pytest tests/unit/test_validators/test_yaml_validation.py::test_validate_yaml
```

### CI Pipeline
```bash
# Full test suite
pytest tests/ --tb=short --junitxml=results.xml

# With parallel execution
pytest tests/ -n auto
```

## Flaky Test Policy

1. Identify flaky test
2. Mark with `@pytest.mark.flaky`
3. Create issue to fix
4. Fix within 1 sprint
5. Remove mark after fix

## Related Documents
- integration/tests/config.yaml
- .claude/guidelines/builder-quality-standards.md
- tools/integration_test_runner.py

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
