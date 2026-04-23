# Builder Quality Standards Guidelines
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** HIGH - Code Quality Requirements

## Overview

This document defines the quality standards that Builder must meet for all code produced. These standards are enforced by stage gates and Critic review.

## Code Quality Requirements

### 1. Test Coverage

**Minimum Thresholds:**
| Type | Threshold | Enforcement |
|------|-----------|-------------|
| Line Coverage | 80% | Block promotion |
| Branch Coverage | 70% | Warning |
| Function Coverage | 90% | Block promotion |

**Requirements:**
- All public functions must have tests
- Edge cases must be covered
- Error paths must be tested

### 2. Security Standards

**Zero Tolerance:**
- No SQL injection vulnerabilities
- No XSS vulnerabilities
- No hardcoded secrets
- No unsafe deserialization

**Required Checks:**
```bash
tools/security_scanner.py --severity high,critical
```

### 3. Code Style

**Enforcement:**
- Must pass linting without errors
- Must follow project style guide
- Must have consistent formatting

**Tools:**
- Python: `flake8`, `black`
- TypeScript: `eslint`, `prettier`
- Go: `golint`, `gofmt`

### 4. Documentation

**Required:**
- Public API documentation
- Complex logic comments
- README for new modules

**Optional:**
- Internal function docs
- Implementation notes

### 5. Error Handling

**Requirements:**
- All errors must be caught or propagated
- Meaningful error messages
- Proper error types/codes
- No silent failures

### 6. Performance

**Guidelines:**
- No O(n²) or worse in hot paths
- Database queries must be indexed
- No N+1 query patterns
- Async operations where appropriate

## Quality Checklist

Before requesting review, Builder must verify:

```markdown
- [ ] All tests passing locally
- [ ] Coverage meets thresholds
- [ ] Security scan clean (no HIGH/CRITICAL)
- [ ] Lint passes without errors
- [ ] Code reviewed self-review
- [ ] Error handling complete
- [ ] Documentation updated
```

## Quality Gates

### Pre-Commit Gate
```bash
# Runs automatically via pre-commit hook
tools/code_quality_analyzer.py --check lint
tools/security_scanner.py --quick
```

### Pre-Review Gate
```bash
# Run before requesting Critic review
tools/qa_metrics_collector.py --check thresholds
tools/integration_test_runner.py
```

### Promotion Gate
```bash
# Final quality check before merge
tools/gate_validator.py --agent builder --check-all
tools/compliance_reporter.py check
```

## Quality Metrics

Builder's code is measured on:

| Metric | Target | Weight |
|--------|--------|--------|
| Test Coverage | ≥80% | 25% |
| Security Score | 100% | 30% |
| Lint Score | 100% | 15% |
| Complexity | ≤10 | 15% |
| Documentation | ≥70% | 15% |

**Overall Quality Score:** Weighted average must be ≥80%

## Common Quality Issues

### Issue: Low Test Coverage
**Fix:** Add unit tests for uncovered code paths

### Issue: Security Finding
**Fix:** Address immediately, block all other work

### Issue: High Complexity
**Fix:** Refactor into smaller functions

### Issue: Lint Violations
**Fix:** Run auto-formatter, fix remaining manually

## Quality Improvement

Builder should:
1. Review Critic feedback patterns
2. Learn from past rejections
3. Use quality tools proactively
4. Ask for guidance when unsure

## Related Documents
- PLANNING/MONITORING_STRATEGY.md
- tools/qa_metrics_collector.py
- tools/code_quality_analyzer.py

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |
