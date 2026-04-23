# Quality Standards & Verification
**Version:** 1.0.0
**Last Updated:** 2025-12-25
**Owner:** PM
**Classification:** MEDIUM - Quality Standards

**Purpose:** Define quality thresholds, testing requirements, and verification procedures
**Audience:** All agents (especially Builder and Critic)
**Authority:** Orchestration Methodology + Industry best practices

---

## 1. Quality Philosophy

**Core Principle:** Quality is not negotiable. Every task must meet defined standards before promotion.

**Quality is:**
- **Measurable:** Objective criteria, not subjective opinion
- **Repeatable:** Same inputs → same assessment
- **Traceable:** Evidence-backed decisions
- **Improvable:** Metrics inform continuous improvement

---

## 1.5 Tiered Quality Targets

**Anti-Pattern:** Setting 100% perfection targets for everything creates:
- Constant failures and discouragement
- Perverse incentives (gaming metrics, fake coverage)
- Reduced focus on what actually matters
- Impossible standards that force workarounds

**Approach:** Realistic, tiered quality targets based on criticality

### Three-Tier System

**Tier 1 - Critical (≥95% required):**
- Security policy compliance
- Breaking API contract violations
- Data corruption risks
- Production-blocking defects

**Tier 2 - Important (≥85% required):**
- Test coverage for business logic
- Spec coverage for features
- Documentation completeness
- Performance within SLA

**Tier 3 - Best Effort (≥70% acceptable):**
- Code style consistency
- Comment coverage
- Refactoring opportunities
- Non-critical optimizations

### Application in the framework

**When defining thresholds for quality dimensions:**
- Use ✅/🟨/🟥 three-tier system (not binary pass/fail)
- Set ✅ Pass thresholds at 90% (standard) or tier-adjusted based on criticality
- Allow 🟨 Conditional approvals with minor gaps
- Reserve 🟥 Fail for significant problems only

**Example (Dimension 4 - Spec Fit):**
```markdown
**Thresholds:**
- ✅ Pass: ≥90% spec coverage, minimal scope creep (≤1 unplanned feature)
- 🟨 Conditional: 80-89% coverage, or minor interpretation differences
- 🟥 Fail: <80% coverage, missing requirements, or significant scope creep
```

**Why 90% instead of 100%:**
- Allows for edge cases in legacy code
- Permits documented technical debt
- Acknowledges real-world constraints
- Still maintains very high quality bar

**Forbidden Targets:**
- ❌ "100% coverage" (unrealistic)
- ❌ "0% violations" (inverse unrealistic)
- ❌ "No warnings allowed" (too strict)
- ❌ "Perfect compliance" (subjective)

---

## 2. Seven Dimensions of Quality

Every code task is evaluated across **7 mandatory dimensions**:

### Dimension 1: Dependency Integrity

**Definition:** Correctness and completeness of dependency identification and ordering

**Criteria:**
- [ ] All external dependencies explicitly declared
- [ ] No circular dependencies
- [ ] Execution order is viable and deterministic
- [ ] Version constraints specified (when applicable)
- [ ] Dependency changes logged

**Measurement:**
- Dependency graph analysis (automated)
- Build success rate
- Integration test results

**Thresholds:**
- ✅ Pass: All dependencies correct, no cycles
- 🟨 Conditional: Minor version mismatches
- 🟥 Fail: Circular deps or missing critical deps

#### Circular Dependency Detection

**Problem:** Circular dependencies (A depends on B, B depends on A) cause build failures, infinite loops, and deployment deadlocks. They must be detected early.

**Current Status:**
- ⚠️ No automated tool yet (technical debt)
- Manual detection required
- Tool backlog: `tools/circular_dep_detector.py` (planned)

**Manual Detection Procedure:**

1. **Collect dependency declarations:**
   ```bash
   # Extract all task dependencies from SSOT wiring files
   find PLANNING -name "wiring.yaml" -exec grep -A 5 "dependencies:" {} \;

   # Output format: task-id → depends on → [list of task IDs]
   ```

2. **Build dependency graph:**

   Create `/PLANNING/dependencies/dependency_graph.md`:
   ```markdown
   ## Dependency Graph (Updated: YYYY-MM-DD)

   Task A → depends on → [B, C]
   Task B → depends on → [D]
   Task C → depends on → [E]
   Task D → depends on → [A]  ← CYCLE DETECTED: A → B → D → A
   ```

3. **Run cycle detection (manual DFS):**

   Start from each task, follow dependencies, mark visited nodes:
   - If you encounter a node marked "in current path" → **CIRCULAR DEPENDENCY DETECTED**
   - If you encounter a node marked "fully explored" → safe, backtrack
   - When backtracking, mark node as "fully explored"

4. **Document findings:**
   ```markdown
   ## Circular Dependency Report (YYYY-MM-DD)

   **Cycles found:** [count]

   ### Cycle 1:
   - Path: Task A → Task B → Task D → Task A
   - Severity: 🔴 Blocking (prevents deployment)
   - Resolution options:
     1. Refactor Task D to remove dependency on A
     2. Extract shared code to new Task F, have A and D depend on F
     3. Invert dependency (make A depend on D instead of D on A)
   - Recommended: Option 2
   ```

5. **PM action:**
   - If cycles found → **BLOCK** all tasks in cycle
   - Escalate to human for resolution decision (Level 3 - Approval)
   - Track cycle in `LogBook/pm/circular_dependencies/YYYY-MM-DD.md`

**Frequency of Manual Checks:**
- **Before each promotion:** Check dependencies of task being promoted
- **Monthly:** Full dependency graph review (all tasks)
- **When dependency changes:** Re-run detection on affected subgraph

**Automated Tool (Planned):**

**Tool:** `tools/circular_dep_detector.py`

**Usage:**
```bash
# Check single task
python3 tools/circular_dep_detector.py --task 3.1

# Check full dependency graph
python3 tools/circular_dep_detector.py --full

# Output: JSON report with cycles, paths, resolution suggestions
```

**Expected output:**
```json
{
  "cycles_found": 1,
  "cycles": [
    {
      "path": ["task-A", "task-B", "task-D", "task-A"],
      "severity": "blocking",
      "resolution_options": [
        "Refactor task-D to remove dependency on task-A",
        "Extract shared code to new task",
        "Invert dependency direction"
      ]
    }
  ],
  "timestamp": "2025-01-15T14:30:00Z"
}
```

**CI Integration (Future):**
- Run `circular_dep_detector.py` on every PR that modifies `wiring.yaml`
- Block merge if cycles detected
- Add to pre-merge gates (see §6 CI/CD Quality Gates)

**Technical Debt Item:**
- **Priority:** Medium (manual detection works, but slow and error-prone)
- **Effort:** ~8 hours (implement tool + tests + CI integration)
- **Owner:** Builder (when available)
- **Tracking:** Add to `LogBook/technical-debt/circular_dep_automation.md`

**Interim Mitigation:**
- PM performs monthly manual review
- Planner checks dependencies during task decomposition
- Critic verifies no new cycles introduced during evaluation

**Success Metric:**
- Zero circular dependencies in production
- Detection time < 5 minutes (automated) vs 30 minutes (manual)

---

### Dimension 2: Effort Accuracy

**Definition:** Alignment between estimated and actual effort

**Criteria:**
- [ ] Time estimate ≤ 4 hours
- [ ] Actual time within 25% of estimate
- [ ] Scope matches original task definition
- [ ] Complexity appropriate for task size

**Measurement:**
- Planned hours vs actual hours
- Task completion velocity
- Scope creep indicators

**Measurement Protocol:**
1. **Data Sources:**
   - `time_estimate`: From task specification `.task/task.yaml` (ISO 8601 duration)
   - `time_actual`: Recorded by Builder in manifest after completion (ISO 8601 duration)
   - `time_variance`: Auto-calculated as `(actual - estimate) / estimate`

2. **Variance Calculation:**
   ```
   variance = (time_actual - time_estimate) / time_estimate
   Example: PT5H actual, PT4H estimate → (5-4)/4 = 0.25 (25% over budget)
   Example: PT3H actual, PT4H estimate → (3-4)/4 = -0.25 (25% under budget)
   ```

3. **Scoring:**
   - Score = 100 × (1 - |variance|) if |variance| ≤ 0.25
   - Score = 50 × (1 - |variance|) if 0.25 < |variance| ≤ 0.50
   - Score = 0 if |variance| > 0.50
   - Example: 10% variance → Score = 100 × (1 - 0.10) = 90

4. **Critic-Effort Agent Verification:**
   - Read `time_estimate` and `time_actual` from `.task/task.yaml`
   - Verify `time_variance` calculation is correct
   - Apply scoring formula above
   - Report PASS/FAIL based on thresholds

**Thresholds:**
- ✅ Pass: Actual within 25% of estimate
- 🟨 Conditional: 25-50% variance
- 🟥 Fail: >50% variance or >4 hours total

**Purpose:** Improve future planning accuracy via Golden Task learning

---

### Dimension 3: Execution Readiness

**Definition:** Clarity and completeness of task specification and acceptance criteria

**Criteria:**
- [ ] Clear inputs and outputs defined
- [ ] Acceptance criteria are testable
- [ ] No ambiguous requirements
- [ ] Required context provided
- [ ] Success conditions binary (pass/fail)

**Measurement:**
- Acceptance criteria coverage
- Rework frequency
- Clarification request count

**Thresholds:**
- ✅ Pass: All criteria clear and testable
- 🟨 Conditional: Minor ambiguities resolved during work
- 🟥 Fail: Fundamental ambiguities blocking progress

---

### Dimension 4: Spec Fit

**Definition:** Alignment between implementation and specification

**Criteria:**
- [ ] All spec requirements addressed
- [ ] No undocumented additions (scope creep)
- [ ] Behavior matches specified intent
- [ ] Edge cases from spec handled
- [ ] Acceptance criteria from spec met

**Measurement:**
- Requirements traceability matrix
- Spec coverage percentage
- Unplanned feature count

**Thresholds:**
- ✅ Pass: ≥90% spec coverage, minimal scope creep (≤1 unplanned feature with rationale)
- 🟨 Conditional: 85-94% spec coverage, or minor interpretation differences
- 🟥 Fail: <80% coverage, missing requirements, or significant scope creep

---

### Dimension 5: Verification Quality

**Definition:** Adequacy and effectiveness of testing and validation

**Criteria:**
- [ ] Unit tests for all new functions/methods
- [ ] Integration tests for interactions
- [ ] Edge cases covered
- [ ] Error conditions tested
- [ ] Tests are reproducible
- [ ] Test coverage ≥ 80% (configurable)

**Measurement:**
- Code coverage percentage
- Test pass rate
- Edge case coverage
- Mutation testing score (when applicable)

**Thresholds:**
- ✅ Pass: Coverage ≥80%, all tests pass, edge cases covered
- 🟨 Conditional: Coverage 60-79%, minor gaps
- 🟥 Fail: Coverage <60%, critical gaps, tests failing

---

### Dimension 6: Security & Policy Compliance

**Definition:** Compliance with security policies and security gate requirements (POLICY-023)

**Criteria:**
- [ ] No hard-coded secrets (SEC-001)
- [ ] All endpoints declare auth_policy, validation_policy, audit_logging (SEC-010)
- [ ] No SQL/command injection vectors (SEC-030, SEC-031)
- [ ] Vendor SDKs only in /adapters/ directory (SEC-032)
- [ ] No high/critical CVEs in dependencies (SEC-033)
- [ ] Auth tests exist for non-public endpoints (SEC-020)
- [ ] Validation tests exist for strict endpoints (SEC-021)
- [ ] Audit logging tests exist when required (SEC-022)
- [ ] Database tables declare PII/encryption fields (SEC-050)
- [ ] External integrations declare security_boundary (SEC-051)

**Measurement:**
- Security scan results (truffleHog, Bandit, npm audit)
- SSOT security field completeness
- Security test coverage
- Policy violation count

**Thresholds:**
- ✅ Pass: All 11 blocking policies pass, warnings acceptable
- 🟨 Conditional: N/A (security is binary)
- 🟥 Fail: ANY blocking policy fails (SEC-001, SEC-010, SEC-020, SEC-021, SEC-022, SEC-030, SEC-031, SEC-032, SEC-033, SEC-050, SEC-051)

**Policy Reference:** POLICY-023, PLANNING/policy/security_policies.yaml

**Specialized Critic:** `.claude/agents/Critic-SecurityPolicy.md`

---

### Dimension 7: Anti-Corruption Layer Compliance

**Definition:** Compliance with Ports-and-Adapters architecture to prevent vendor coupling (POLICY-024)

**Criteria:**
- [ ] ALL vendor SDK imports are in /adapters/ directory (SEC-032)
- [ ] Port interfaces use ONLY internal types (no vendor types)
- [ ] Each adapter has mapper for vendor ↔ internal type conversions
- [ ] Adapter handles vendor errors → internal error taxonomy
- [ ] Contract tests exist for all ports
- [ ] SSOT Section 7 (adapter wiring) declared
- [ ] No vendor imports in /src/ or /ports/

**Measurement:**
- Vendor import scan (grep for vendor SDKs outside /adapters/)
- Port interface purity (no vendor types in signatures)
- Adapter implementation completeness
- Contract test coverage

**Thresholds:**
- ✅ Pass: All vendor SDKs isolated, ports pure, adapters complete, contract tests exist
- 🟨 Conditional: Minor mapper improvements needed
- 🟥 Fail: Vendor SDK outside /adapters/, vendor types in ports, missing contract tests

**Policy Reference:** POLICY-024

**Specialized Critic:** `.claude/agents/Critic-ACL.md`

---

## 3. Code Quality Standards

### Code Style & Readability

**Required:**
- Consistent naming conventions (camelCase, snake_case per language)
- Meaningful variable/function names
- Comments for complex logic (not obvious code)
- No dead code or commented-out sections
- Max function length: 50 lines (guideline)
- Max file length: 500 lines (guideline)

**Tools:**
- Linters (pylint, eslint, etc.)
- Formatters (black, prettier, etc.)
- Static analysis (mypy, TypeScript compiler)

**Threshold:** All automated checks pass (errors blocked, warnings acceptable with documentation)

---

### Security Standards (OWASP Top 10)

**Critical vulnerabilities (Zero tolerance):**

1. **Injection**
   - [ ] No SQL injection vectors
   - [ ] No command injection vectors
   - [ ] Inputs sanitized/parameterized

2. **Broken Authentication**
   - [ ] Passwords hashed (bcrypt/Argon2)
   - [ ] Session management secure
   - [ ] MFA supported (when applicable)

3. **Sensitive Data Exposure**
   - [ ] No secrets in code
   - [ ] Encryption for data at rest/transit
   - [ ] Proper key management

4. **XML External Entities (XXE)**
   - [ ] XML parsers configured securely
   - [ ] External entity processing disabled

5. **Broken Access Control**
   - [ ] Authorization checks on all endpoints
   - [ ] Principle of least privilege
   - [ ] No default credentials

6. **Security Misconfiguration**
   - [ ] No debug mode in production
   - [ ] Minimal surface area
   - [ ] Security headers configured

7. **Cross-Site Scripting (XSS)**
   - [ ] Outputs escaped/encoded
   - [ ] Content Security Policy used
   - [ ] Input validation

8. **Insecure Deserialization**
   - [ ] No untrusted deserialization
   - [ ] Signature verification
   - [ ] Type validation

9. **Using Components with Known Vulnerabilities**
   - [ ] Dependencies scanned (Dependabot, Snyk)
   - [ ] No critical CVEs
   - [ ] Regular updates

10. **Insufficient Logging & Monitoring**
    - [ ] Security events logged
    - [ ] Log injection prevented
    - [ ] Sensitive data not logged

**Threshold:** Zero critical/high vulnerabilities (blocking)

**Tools:**
- SAST scanners (Bandit, SonarQube)
- Dependency scanners (npm audit, pip-audit)
- Secret scanners (truffleHog, detect-secrets)

---

### Performance Standards

**Guidelines (not blocking, but logged):**
- API endpoints: < 200ms p95 latency
- Database queries: < 100ms
- Page load: < 3s
- Memory usage: No leaks detected

**Measurement:**
- Profiling during testing
- Load testing for critical paths
- Memory leak detection tools

**Threshold:**
- 🟨 Warning: Performance degradation >20%
- 🟥 Blocker: Performance degradation >50% or critical regression

---

## 4. Testing Standards

### Test Pyramid Structure

```
        ┌──────────┐
        │    E2E   │  (Few - expensive, slow)
        ├──────────┤
        │Integration│ (Some - moderate cost)
        ├──────────┤
        │   Unit   │  (Many - cheap, fast)
        └──────────┘
```

**Distribution guideline:**
- 70% Unit tests
- 20% Integration tests
- 10% E2E tests

---

### Unit Testing Standards

**Required for:**
- All public functions/methods
- All business logic
- All edge cases
- All error conditions

**Test characteristics:**
- Fast (< 1s per test)
- Isolated (no external dependencies)
- Repeatable (same result every run)
- Deterministic (no flakiness)

**Coverage target:** ≥80% line coverage

**Format (example Python):**
```python
def test_user_creation_with_valid_email():
    """Test that User is created successfully with valid email."""
    user = User(email="test@example.com", password="SecurePass123!")
    assert user.email == "test@example.com"
    assert user.password_hash is not None
    assert user.password != "SecurePass123!"  # hashed

def test_user_creation_with_invalid_email():
    """Test that User creation fails with invalid email."""
    with pytest.raises(ValidationError):
        User(email="invalid-email", password="SecurePass123!")
```

---

### Integration Testing Standards

**Required for:**
- Database interactions
- API endpoint behavior
- Service-to-service communication
- External dependency integration

**Test characteristics:**
- Moderate speed (< 10s per test)
- Controlled external deps (mocks, test DBs)
- Reproducible state (setup/teardown)

**Coverage target:** Critical paths covered

---

### End-to-End Testing Standards

**Required for:**
- Critical user flows
- Multi-service workflows
- UI + API + DB integration

**Test characteristics:**
- Slower (acceptable)
- Full stack execution
- Representative data

**Coverage target:** Happy path + major error paths

---

## 5. Documentation Standards

### Code Documentation

**Required:**
- Module-level docstrings
- Function/method docstrings (params, returns, raises)
- Complex algorithm explanations
- API endpoint documentation

**Format (example Python):**
```python
def calculate_user_score(user_id: int, metrics: dict) -> float:
    """Calculate composite score for user based on metrics.

    Args:
        user_id: Unique identifier for user
        metrics: Dictionary containing metric_name -> value pairs

    Returns:
        Float score between 0.0 and 100.0

    Raises:
        ValueError: If user_id is invalid or metrics is empty

    Example:
        >>> calculate_user_score(123, {"activity": 50, "engagement": 75})
        62.5
    """
```

---

### Artifact Documentation

**Every task must produce:**

1. **Implementation Notes**
   - What was built
   - Key design decisions
   - Tradeoffs made

2. **Test Summary**
   - Coverage percentage
   - Edge cases tested
   - Known limitations

3. **Integration Guide**
   - How to use the task
   - Dependencies required
   - Example usage

**Location:** `/LogBook/<category>/alt/<branch>/[task-id].md`

---

## 6. CI/CD Quality Gates

### Pre-Merge Gates (Blocking)

**All must pass:**
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage ≥ 80%
- [ ] Linter passes (no errors)
- [ ] Security scan passes (no critical/high)
- [ ] Build succeeds
- [ ] Critic approval (✅)

**Optional (non-blocking):**
- [ ] Performance benchmarks (warning only)
- [ ] Complexity metrics (warning only)

---

### Post-Merge Validation

**After promotion to main:**
- [ ] E2E tests pass
- [ ] Deployment to staging succeeds
- [ ] Smoke tests pass
- [ ] Monitoring shows no regressions

---

## 7. Critic Evaluation Procedure

### Step-by-Step Evaluation

**Critic must follow this sequence:**

1. **Read work order and acceptance criteria**
   - Understand what was requested
   - Identify success conditions

2. **Examine artifacts**
   - Code implementation
   - Test files
   - Documentation

3. **Run automated checks**
   - Execute test suite
   - Run linter
   - Run security scanner
   - Check coverage report

4. **Evaluate 7 dimensions**
   - Score each dimension: Pass/Conditional/Fail
   - Document specific findings
   - Provide evidence for each score

5. **Determine overall verdict**
   - ✅ Approved: All 7 dimensions pass, OR ≥6 dimensions pass with remaining conditional
   - 🟨 Conditional: ≥5 dimensions pass with specific fixes listed
   - 🟥 Blocked: <5 dimensions pass, or any critical dimension fails
   - ❌ Rejected: Fundamental flaw, start over

6. **Write verdict to LogBook**
   - Complete evaluation report
   - Link to evidence
   - Specify required actions (if any)

---

## 8. Quality Metrics & Improvement

### Track Over Time

**Task-level metrics:**
- First-pass approval rate
- Average rework cycles
- Time in review
- Defect density (bugs per 1000 LOC)

**System-level metrics:**
- CI pass rate
- Mean time to promotion
- Golden task reuse rate
- Production incident rate

**Learning metrics:**
- Effort estimation accuracy trend
- Security vulnerability trend
- Test coverage trend
- Code quality score trend

### Improvement Actions

**When metrics degrade:**
1. Analyze recent Bad Tasks for patterns
2. Update Golden Task guidelines
3. Enhance Planner decomposition rules
4. Tighten quality gates if needed

**When metrics improve:**
1. Archive successful patterns as Golden Tasks
2. Share learnings across agents
3. Consider loosening non-critical gates

---

## 9. Quality Anti-Patterns

### DON'T

❌ **Rubber-stamp approvals**
   - Every dimension must be evaluated

❌ **"Good enough" mentality**
   - Gates exist for a reason

❌ **Skip tests "to ship faster"**
   - Increases rework and defects

❌ **Ignore security warnings**
   - Zero tolerance for critical vulnerabilities

❌ **Subjective quality assessment**
   - Use objective, measurable criteria

❌ **Bypass CI checks**
   - No direct merges without gates

---

## 10. Rollback & Recovery Procedures

**Philosophy:** Every promotion decision must be reversible. Fear of irreversibility creates conservative, slow decision-making. Documented rollback procedures enable confident, rapid iteration.

### 10.1 Task Rollback (Golden → Bad)

**Trigger:** Promoted task causes production issues or fails post-deployment validation

**Procedure:**

1. **Stop further usage:**
   - Add `DEPRECATED: [reason]` marker to task documentation
   - Update `archives/golden/INDEX.md` to mark task as deprecated
   - Notify teams via LogBook entry

2. **Investigate root cause:**
   - Document what went wrong in `LogBook/rollback/[task-id]/analysis.md`
   - Determine if issue was preventable (missed test, wrong acceptance criteria, etc.)
   - Identify which quality dimension failed

3. **Execute rollback:**
   ```bash
   # Move task from golden to bad archive
   mv archives/golden/[category]/[task-id]/ archives/bad/[category]/[task-id]/

   # Update index files
   # Add rollback entry to LogBook
   echo "Rollback: [task-id] moved to bad archive - [reason]" >> LogBook/rollback/ROLLBACK_LOG.md
   ```

4. **Update LogBook:**
   - Create `LogBook/rollback/[task-id]/rollback.md` with:
     - Timestamp of rollback
     - Reason for rollback
     - Root cause analysis
     - Corrective actions taken
     - Link to replacement task (if available)

5. **Update quality gates:**
   - If rollback reveals gap in quality checks, update gates
   - Add test case that would have caught the issue
   - Update Critic evaluation criteria if needed

**Rollback time budget:** < 1 hour from decision to completion

---

### 10.2 Template Rollback (Retire Broken Version)

**Trigger:** Template produces buggy/insecure code despite passing generation tests

**Procedure:**

1. **Immediate deprecation:**
   - Add `@saf:deprecated` marker to template header
   - Set `status: deprecated` in template metadata
   - Update `templates/[family]/INDEX.md`

2. **Identify affected tasks:**
   ```bash
   # Find all tasks using broken template
   grep -r "template: [template-name]" archives/golden/ LogBook/
   ```

3. **Assess damage scope:**
   - How many tasks used this template?
   - Are any in production?
   - What's the severity of the bug?

4. **Choose rollback strategy:**

   **Option A - Patch in place (minor bug):**
   - Fix template
   - Regenerate affected tasks
   - Validate regenerated output
   - Promote fixed template as new version

   **Option B - Full revert (major bug):**
   - Revert to previous template version
   - Mark current version as `retired`
   - Move to `templates/[family]/retired/[version]/`
   - Regenerate all affected tasks with previous version

   **Option C - Emergency replacement:**
   - Create new template from scratch
   - Migrate affected tasks to new template
   - Archive broken template permanently

5. **Document lessons learned:**
   - `LogBook/rollback/templates/[template-name]-[version].md`
   - What went wrong
   - Why generation tests didn't catch it
   - New test cases added
   - Updated template validation rules

**Rollback time budget:** < 4 hours from detection to mitigation

---

### 10.3 Policy Rollback (Revert Policy Change)

**Trigger:** New policy creates more problems than it solves

**Procedure:**

1. **Assess policy impact:**
   - How many tasks/agents affected?
   - What's breaking?
   - Can we grandfather existing work?

2. **Execute policy revert:**
   ```bash
   # Revert policy file to previous version
   git log -- PLANNING/policy/[policy-file].yaml  # Find previous commit
   git checkout [commit-hash] -- PLANNING/policy/[policy-file].yaml
   git commit -m "Rollback: Revert [policy-name] due to [reason]"
   ```

3. **Update PM state:**
   - `LogBook/pm/STATE.md` - Note policy rollback
   - `LogBook/rollback/policy/[policy-name].md` - Full analysis

4. **Notify agents:**
   - Add announcement to `LogBook/daily-summary/[date].md`
   - Update agent guidelines if policy was referenced

5. **Fix affected work:**
   - Option A: Grandfather (allow existing work to complete under old rules)
   - Option B: Rework (apply old policy to in-flight work)
   - Document choice in rollback log

**Policy rollback approval:** Requires human escalation (PM cannot unilaterally rollback policies)

**Rollback time budget:** < 2 hours from decision to revert commit

---

### 10.4 LogBook Undo (Correct Accidental Entries)

**Trigger:** Incorrect LogBook entry (wrong data, typo, premature approval, etc.)

**Procedure:**

1. **DO NOT delete original entry** (audit trail must be complete)

2. **Add correction entry:**
   ```markdown
   ## CORRECTION: [Original Entry Title]
   **Date:** [ISO timestamp]
   **Corrects:** [link to original entry]

   **Original (incorrect):**
   [What was wrong]

   **Corrected:**
   [What it should be]

   **Reason for correction:**
   [Why the error occurred]
   ```

3. **Update index files:**
   - Add `[CORRECTED]` marker to original entry in INDEX.md
   - Link to correction entry

4. **Special case - Premature approvals:**
   If Critic approved work that should have been blocked:
   - Create correction entry marking work as `CONDITIONAL` or `BLOCKED`
   - PM re-evaluates based on corrected verdict
   - Builder addresses issues before re-submitting

5. **LogBook integrity check:**
   - Verify correction entry is properly linked
   - Ensure newest-first ordering is maintained
   - Update metrics if correction affects them

**Undo time budget:** < 30 minutes

---

### 10.5 Git Branch Rollback (Undo Bad Merge)

**Trigger:** Merged code breaks main branch, needs immediate revert

**Procedure:**

1. **Revert merge commit:**
   ```bash
   # Find merge commit
   git log --oneline --merges

   # Revert it
   git revert -m 1 [merge-commit-hash]
   git push origin main
   ```

2. **Document revert:**
   - `LogBook/rollback/git/[date]-[branch-name].md`
   - Why merge was reverted
   - What broke
   - Fix plan

3. **Fix and re-merge:**
   - Fix issues in feature branch
   - Re-run full CI/CD
   - Get fresh Critic approval
   - Re-merge when ready

**Rollback time budget:** < 15 minutes (emergency)

---

### 10.6 Rollback Metrics (Track Recovery Effectiveness)

**Track these metrics:**
- Rollback frequency (by type: task/template/policy/git)
- Time to rollback (actual vs budget)
- Root cause categories (missed test, wrong criteria, tool failure, etc.)
- Re-promotion success rate (% of rolled-back tasks that eventually succeed)

**Goal:** Rollback rate < 5% of promotions

**Location:** `LogBook/metrics/rollback_metrics.json`

**Review cadence:** Monthly retrospective

---

### 10.7 Rollback Anti-Patterns

❌ **Delete evidence**
   - Never delete failed tasks, keep in bad archive

❌ **Silent rollback**
   - Always document in LogBook

❌ **Blame-focused rollback**
   - Focus on system improvement, not fault

❌ **Preventive rollback paralysis**
   - Don't avoid promotions due to rollback fear
   - Rollbacks are normal and healthy

❌ **Skipping root cause analysis**
   - Every rollback is a learning opportunity

---

## 11. Scalability Limits & Performance Thresholds

**Philosophy:** The framework must scale from 10 tasks to 1000+ tasks without fundamental redesign. This section defines known limits, performance expectations, and mitigation strategies.

### 11.1 Task Scale Limits

**Tested scale ranges:**
- **Small project:** 1-50 tasks (well-tested, no special considerations)
- **Medium project:** 51-250 tasks (requires attention to dependency resolution)
- **Large project:** 251-1000 tasks (requires LogBook optimization and metrics rollup)
- **Enterprise project:** 1000+ tasks (requires partitioning, see below)

**Known bottlenecks at scale:**

| Scale          | Bottleneck                     | Mitigation Strategy                          |
|----------------|--------------------------------|----------------------------------------------|
| 50+ tasks     | Dependency resolution slow     | Use dependency graph caching                 |
| 100+ tasks    | LogBook file count high        | Implement monthly rollup/archival            |
| 250+ tasks    | Index file parsing slow        | Switch to JSON indexes for machine reading   |
| 500+ tasks    | Critic review queue grows      | Parallelize Critic evaluations               |
| 1000+ tasks   | Archive directory too large    | Partition by category AND year               |

---

### 11.2 Dependency Resolution Complexity

**Algorithmic complexity:** O(n²) worst-case for dependency resolution (n = number of tasks)

**Performance expectations:**
- **10 tasks:** < 1 second to resolve dependencies
- **50 tasks:** < 5 seconds
- **100 tasks:** < 15 seconds
- **250 tasks:** < 60 seconds (1 minute)
- **500 tasks:** < 5 minutes (requires optimization)
- **1000+ tasks:** Requires dependency graph caching or incremental resolution

**Mitigation strategies:**
1. **Lazy resolution:** Only resolve dependencies for active branches
2. **Caching:** Store resolved dependency graph in `PLANNING/dependencies/cache/`
3. **Incremental updates:** Only recompute affected subgraphs when tasks change
4. **Circular dependency detection:** Fail fast before attempting full resolution

**When to escalate:** If dependency resolution takes > 5 minutes, human review required for refactoring

---

### 11.3 LogBook Performance Degradation

**File count thresholds:**
- **Comfortable:** < 500 files in LogBook (no performance issues)
- **Warning:** 500-2000 files (noticeable slowdown in search/indexing)
- **Critical:** 2000+ files (significant degradation, rollup required)

**LogBook rollup strategy:**

**Monthly rollup (automated):**
```bash
# Run on 1st of each month
tools/logbook_rollup.sh --month $(date -d "last month" +%Y-%m)

# Creates:
# - LogBook/rollups/monthly/YYYY-MM.md (human-readable summary)
# - LogBook/rollups/monthly/YYYY-MM.json (machine-readable metrics)
# - Moves original files to LogBook/archive/YYYY-MM/
```

**Rollup includes:**
- Task completion count (by category)
- Approval/conditional/blocked/rejected counts
- Average time per task
- Top 5 blockers/delays
- Rollback count
- Links to archived detailed entries

**Retention policy:**
- Keep last 3 months of detailed logs online
- Keep last 12 months of monthly rollups
- Archive older than 12 months to cold storage (optional)

---

### 11.4 Archive Indexing Limits

**Current index structure:** Single `INDEX.md` per category in `/archives/golden/` and `/archives/bad/`

**Scalability limits:**
- **Comfortable:** < 100 tasks per category (INDEX.md manageable)
- **Warning:** 100-500 tasks per category (INDEX.md slow to parse)
- **Critical:** 500+ tasks per category (INDEX.md unwieldy, requires partitioning)

**Partitioning strategy at scale:**

**Option A - Temporal partitioning:**
```
archives/golden/[category]/
  ├── 2024/
  │   ├── INDEX.md (2024 tasks only)
  │   └── [task-id]/
  ├── 2025/
  │   ├── INDEX.md (2025 tasks only)
  │   └── [task-id]/
  └── INDEX.md (master index with year links)
```

**Option B - Alphabetical partitioning:**
```
archives/golden/[category]/
  ├── A-F/
  │   ├── INDEX.md (tasks A-F)
  │   └── [task-id]/
  ├── G-M/
  ├── N-Z/
  └── INDEX.md (master index)
```

**Recommendation:** Use temporal partitioning (easier to prune old tasks)

---

### 11.5 Active Branch Limits (PM Bandwidth)

**PM context window limitations:**
- **Comfortable:** 1-5 active branches (PM can track easily)
- **Warning:** 6-15 active branches (requires strict STATE.md discipline)
- **Critical:** 15+ active branches (PM context overload, escalate)

**Mitigation strategies:**
1. **Branch pruning policy:** Close stale branches (no activity > 7 days)
2. **Priority tiers:** PM focuses on Tier 1 (critical) branches, delegates Tier 2/3
3. **Parallel PM instances:** For enterprise scale, run multiple PM agents with category partitioning

**Branch lifecycle:**
- **New:** Just created, high priority
- **Active:** Work in progress, daily updates
- **Stale:** No activity > 7 days, warn owner
- **Abandoned:** No activity > 14 days, auto-close with escalation notice

---

### 11.6 Metrics Rollup Strategy

**Real-time metrics (always current):**
- CI pass rate (last 7 days)
- Task completion velocity (tasks/day)
- Current blocker count

**Rolled-up metrics (computed periodically):**
- First-pass approval rate (monthly)
- Golden task reuse rate (quarterly)
- Template adoption rate (quarterly)
- Security vulnerability trends (monthly)

**Computation frequency:**
- **Hourly:** CI pass rate
- **Daily:** Task completion velocity, blocker count
- **Weekly:** Critic evaluation turnaround time
- **Monthly:** Approval rates, rollback rates, effort estimation accuracy
- **Quarterly:** Reuse rates, template metrics, long-term trends

**Storage:**
- Real-time metrics: `LogBook/metrics/current.json`
- Historical metrics: `LogBook/metrics/history/YYYY-MM.json`

---

### 11.7 Performance Budgets

**Philosophy:** Every the operation has a time budget. Exceeding budgets triggers optimization or escalation.

#### Agent Operation Budgets

| Operation | Target | Warning | Critical | Escalation Action |
|-----------|--------|---------|----------|-------------------|
| **Planner: Task decomposition** | < 5 min | 5-10 min | > 10 min | Simplify spec, break into smaller units |
| **Planner: Dependency resolution** | < 15 sec (100 tasks) | 15-60 sec | > 5 min | Enable caching, escalate for refactoring |
| **Builder: Implement task** | < 4 hours | 4-6 hours | > 6 hours | Task too large, re-decompose |
| **Builder: Run tests** | < 5 min | 5-10 min | > 10 min | Optimize tests, parallelize |
| **Critic: Evaluate 1 task** | < 30 min | 30-60 min | > 60 min | Automate checks, reduce manual review |
| **Critic: Run security scan** | < 2 min | 2-5 min | > 5 min | Reduce scan scope, cache results |
| **PM: Governance cycle** | < 10 min | 10-20 min | > 20 min | Reduce active branches, delegate |
| **PM: LogBook index parsing** | < 5 sec | 5-15 sec | > 15 sec | Implement rollup, switch to JSON |
| **PM: Metrics computation** | < 10 min | 10-30 min | > 30 min | Pre-compute, cache, incremental updates |

---

#### Workflow Time Budgets

| Workflow | Target End-to-End Time | Breakdown |
|----------|------------------------|-----------|
| **Plan → Approve Plan** | < 1 hour | Planner: 30 min, PM review: 15 min, PlanAuditor: 15 min |
| **Build → Critic Approval** | < 5 hours | Builder: 3.5 hours, Critic: 1 hour, PM coordination: 30 min |
| **Task → Golden Archive** | < 24 hours | Build+review: 5 hours, CI: 30 min, PM promotion: 15 min, cooldown: 18 hours |
| **Template Creation** | < 8 hours | Design: 2 hours, implement: 4 hours, test: 1 hour, review: 1 hour |
| **Rollback (Task)** | < 1 hour | Decision: 15 min, execution: 30 min, LogBook: 15 min |
| **Rollback (Template)** | < 4 hours | Investigation: 1 hour, fix/revert: 2 hours, validation: 1 hour |
| **Policy Change** | < 2 hours | Draft: 30 min, review: 1 hour, deployment: 30 min |

---

#### CI/CD Performance Budgets

| Stage | Target | Warning | Critical |
|-------|--------|---------|----------|
| **Linter** | < 30 sec | 30-60 sec | > 60 sec |
| **Unit tests** | < 2 min | 2-5 min | > 5 min |
| **Integration tests** | < 5 min | 5-10 min | > 10 min |
| **Security scan** | < 2 min | 2-5 min | > 5 min |
| **Build** | < 3 min | 3-10 min | > 10 min |
| **E2E tests** | < 15 min | 15-30 min | > 30 min |
| **Full CI pipeline** | < 25 min | 25-45 min | > 45 min |

**Mitigation when CI exceeds budget:**
- Parallelize test suites
- Cache dependencies
- Reduce test scope (run full suite nightly, subset on PR)
- Invest in faster CI infrastructure

---

#### LogBook Performance Budgets

| Operation | Target | Warning | Critical | Mitigation |
|-----------|--------|---------|----------|------------|
| **Write single entry** | < 1 sec | 1-3 sec | > 3 sec | Check disk I/O |
| **Read single entry** | < 0.5 sec | 0.5-2 sec | > 2 sec | Use SSD, reduce file size |
| **Parse INDEX.md** | < 5 sec | 5-15 sec | > 15 sec | Switch to JSON, implement pagination |
| **Search LogBook** | < 10 sec | 10-30 sec | > 30 sec | Implement full-text search index |
| **Monthly rollup** | < 30 min | 30-60 min | > 60 min | Incremental rollup, parallel processing |

---

#### Scalability-Dependent Budgets

As task count increases, budgets adjust:

**At 50 tasks:**
- Dependency resolution: < 5 seconds (target)
- LogBook parsing: < 3 seconds
- Metrics computation: < 5 minutes

**At 100 tasks:**
- Dependency resolution: < 15 seconds (target)
- LogBook parsing: < 5 seconds
- Metrics computation: < 10 minutes

**At 250 tasks:**
- Dependency resolution: < 60 seconds (target, requires caching)
- LogBook parsing: < 10 seconds (requires JSON indexes)
- Metrics computation: < 20 minutes (requires pre-computation)

**At 500+ tasks:**
- All operations require optimization (see §11 Scalability)
- Manual metrics computation no longer viable
- Requires automated rollup and caching infrastructure

---

#### When Budget Is Exceeded

**PM actions:**

1. **Warning threshold exceeded:**
   - Log performance metric to `LogBook/metrics/performance_degradation.json`
   - Monitor trend (one-time spike vs sustained degradation)
   - Schedule optimization for next sprint

2. **Critical threshold exceeded:**
   - Immediate escalation (Level 2 - Consultation)
   - Document affected operations
   - Implement temporary workaround (e.g., reduce active branches)
   - Prioritize optimization work

3. **Repeated critical threshold breaches:**
   - Escalation (Level 3 - Approval required)
   - System architecture review
   - May require major refactoring or infrastructure upgrade

---

#### Performance Metrics Tracking

**Location:** `LogBook/metrics/performance/`

**Files:**
- `agent_timings.json` - How long each agent operation takes
- `workflow_durations.json` - End-to-end workflow times
- `ci_performance.json` - CI pipeline stage timings
- `logbook_performance.json` - LogBook read/write/search times

**Collection frequency:** Every operation (automated instrumentation)

**Review frequency:** Weekly (PM checks for trends)

**Alerting:** Auto-alert when critical threshold exceeded

---

#### Performance Budget Anti-Patterns

❌ **Ignore budgets \"just this once\"**
   - Slippery slope to slow system

❌ **No instrumentation**
   - Can't optimize what you don't measure

❌ **Optimize prematurely**
   - Only optimize when budget exceeded

❌ **Accept degradation as inevitable**
   - Most slowdowns are fixable with proper analysis

---

### 11.8 Scalability Warning Signs

**PM must escalate if:**
- Dependency resolution > 5 minutes
- LogBook has > 2000 files without rollup
- Archive category has > 500 tasks without partitioning
- Active branches > 15
- Critic review backlog > 20 tasks
- Metrics computation takes > 10 minutes

**Escalation action:** Human review for system optimization or architecture refactoring

---

### 11.9 Tested Limits (As of Policy Creation)

**Current testing status:**
- ✅ Tested: 1-50 tasks (production-ready)
- 🟡 Partially tested: 51-100 tasks (field testing in progress)
- ❓ Untested: 100+ tasks (theoretical limits, needs validation)
- ❓ Untested: 1000+ tasks (requires partitioning strategy)

**Recommendation:** Validate scalability assumptions with real workloads before hitting limits

---

### 11.10 Scalability Roadmap

**Phase 1 (Current - 50 tasks):**
- Single-file indexes
- Manual metrics computation
- PM handles all branches

**Phase 2 (50-250 tasks):**
- Dependency graph caching
- Automated monthly LogBook rollup
- JSON machine-readable indexes

**Phase 3 (250-1000 tasks):**
- Temporal archive partitioning
- Parallel Critic evaluations
- Automated metrics computation

**Phase 4 (1000+ tasks - Future):**
- Category-partitioned PM instances
- Distributed dependency resolution
- Tiered archive storage (hot/warm/cold)

---

## 12. Success Criteria

**High-quality the system:**
- First-pass approval rate > 75%
- CI pass rate > 95%
- Test coverage > 80% system-wide
- Zero critical security vulnerabilities
- Production incident rate < 1 per month
- Mean time to promotion < 24 hours
- Golden task reuse rate > 30%

**Evidence of continuous improvement:**
- Metrics trending positively over time
- Bad task archive growing slower than golden
- Estimation accuracy improving
- Rework cycles decreasing

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |

---

**End of Quality Standards & Verification**
