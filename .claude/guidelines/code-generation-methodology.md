# Code Generation Methodology
**Purpose:** Guidelines for generating production code through the framework task-by-task approach
**Audience:** Builder agents, Planner agents
**Authority:** Orchestration Methodology + Golden Task Archive patterns

---

## 1. Task-by-Task Philosophy

**Core Concept:** Transform complex specifications into production code through small, verified, reusable "tasks" (micro-tasks).

### What is a Task?

A task is:
- **Atomic:** Single, testable unit of work
- **Bounded:** ≤ 4 hours of effort
- **Verified:** Passes CI + Critic review before promotion
- **Documented:** Has clear inputs, outputs, acceptance criteria
- **Traceable:** Complete LogBook trail from spec → code

---

## 2. Task Lifecycle

```
Spec → Planner → Micro-Task Task → Builder → Code → Critic → Verification
  ↓                                                                ↓
  ↓                                                                ↓
  └────────────────── PM Coordination ─────────────────────────────┘
                              ↓
                    [✅ Golden] or [🟥 Bad] Archive
```

### States:
1. **Planned:** Planner decomposes spec into tasks
2. **Assigned:** PM assigns task to Builder
3. **Built:** Builder implements code
4. **Reviewed:** Critic evaluates against 7 dimensions
5. **Approved:** Meets quality gates
6. **Archived:** Golden (reusable) or Bad (learning)

---

## 3. Decomposition Rules (Planner)

When breaking specs into tasks:

### Size Constraints
- **Time:** ≤ 4 hours
- **Scope:** Single responsibility
- **Dependencies:** Explicit and minimal
- **Reversibility:** Can be rolled back if needed

### Task Granularity Examples

**Too Large:**
```
❌ "Implement authentication system"
   → 20+ hours, multiple components, unclear boundaries
```

**Correct Size:**
```
✅ "Create User model with email/password fields"
   → 2 hours, single file, clear acceptance criteria

✅ "Add password hashing to User.save() method"
   → 1.5 hours, single method, testable

✅ "Write unit tests for User authentication"
   → 3 hours, bounded test suite
```

---

## 4. Implementation Rules (Builder)

### Before Writing Code

1. **Read the micro-task specification completely**
   - Understand inputs, outputs, constraints
   - Identify dependencies
   - Clarify acceptance criteria

2. **Check for Golden Tasks**
   - Search `/archives/golden/` for similar patterns
   - Reuse verified solutions when applicable
   - Adapt, don't copy blindly

3. **Verify write permissions**
   - Ensure files are within assigned scope
   - Check no protected path violations

### During Implementation

1. **One task at a time**
   - Complete current task before starting next
   - Don't "helpfully" expand scope
   - Stay within time/scope bounds

2. **Incremental commits**
   - Commit frequently with clear messages
   - Each commit maps to progress milestone
   - Never silent or batch commits

3. **Test-Driven Development (TDD) - MANDATORY**
   - **Write tests FIRST** before any implementation code
   - Run tests - they MUST fail initially (red phase)
   - Write minimal code to make tests pass (green phase)
   - Refactor while keeping tests passing (refactor phase)
   - See Builder.md "Step 3: Write Test FIRST" for detailed TDD workflow

### After Implementation

1. **Self-review checklist:**
   - [ ] Code meets acceptance criteria
   - [ ] Tests pass locally
   - [ ] No security vulnerabilities (OWASP top 10)
   - [ ] Documentation updated
   - [ ] LogBook entry written

2. **Submit to Critic:**
   - Provide artifact paths
   - Link to acceptance criteria
   - Include test results

---

## 5. Quality Verification (Critic)

Critic evaluates tasks across **7 dimensions** (see quality-standards.md for full detail):

### 1. Dependency Integrity
- Are dependencies correctly identified?
- No circular dependencies?
- Execution order viable?

### 2. Effort Accuracy
- Is time estimate realistic?
- Scope matches ≤ 4 hour constraint?
- Complexity appropriately bounded?

### 3. Execution Readiness
- Clear inputs/outputs defined?
- Acceptance criteria testable?
- No ambiguous requirements?

### 4. Spec Fit
- Implementation matches specification?
- No scope creep or additions?
- Requirements fully addressed?

### 5. Verification Quality
- Tests comprehensive?
- Edge cases covered?
- Reproducible results?

**Verdict Options:**
- ✅ **Approved:** All dimensions pass
- 🟨 **Conditional:** Minor fixes needed
- 🟥 **Blocked:** Major issues, requires rework
- ❌ **Rejected:** Fundamentally flawed

---

## 6. Golden Task Criteria

A task qualifies for Golden Archive when:

**ALL required:**
- [ ] CI + Critic approval (✅)
- [ ] Verification score meets canonical threshold
- [ ] Reproducibility evidence exists
- [ ] Learning value confirmed (reusable pattern)
- [ ] Complete documentation
- [ ] No security vulnerabilities

**Archive location:** `/archives/golden/<category>/`

**Metadata required:**
- Pattern name and description
- Use cases and constraints
- Dependencies and prerequisites
- Example usage
- Verification results

---

## 7. Bad Task Learning

Failed tasks go to Bad Archive for learning:

**Triggers (ANY):**
- Repeated failure after N cycles
- Structural flaw confirmed
- Rejected by Critic with no remediation path

**Archive location:** `/archives/bad/<category>/`

**Required learning notes:**
- What was attempted
- Why it failed
- What was learned
- Alternative approaches
- Conditions to avoid

**Purpose:** Prevent repeating mistakes, inform future planning

---

## 8. Anti-Patterns to Avoid

### Planning Anti-Patterns
- ❌ Vague tasks without acceptance criteria
- ❌ Multi-day mega-tasks
- ❌ Hidden dependencies
- ❌ Scope creep during execution

### Building Anti-Patterns
- ❌ Coding without reading spec completely
- ❌ Expanding scope "to be helpful"
- ❌ Skipping tests "to save time"
- ❌ Silent assumptions not documented

### Review Anti-Patterns
- ❌ Rubber-stamp approvals
- ❌ Ignoring security vulnerabilities
- ❌ Subjective "looks good" verdicts
- ❌ Missing edge case coverage

---

## 9. Code Security Baseline

**Every task must avoid OWASP Top 10:**

1. Injection (SQL, command, XSS)
2. Broken authentication
3. Sensitive data exposure
4. XML external entities
5. Broken access control
6. Security misconfiguration
7. Cross-site scripting (XSS)
8. Insecure deserialization
9. Using components with known vulnerabilities
10. Insufficient logging & monitoring

**Rule:** If security vulnerability detected, immediately fix before proceeding.

---

## 10. Reusability & Patterns

### When to Create a Golden Task Pattern

- Used successfully ≥ 2 times
- Generalizable across contexts
- Well-documented and tested
- No context-specific dependencies

### Pattern Categories

- **Data Models:** Common entity structures
- **API Endpoints:** Standard CRUD patterns
- **Authentication:** Login, session, token patterns
- **Validation:** Input sanitization, error handling
- **Testing:** Test harness templates

---

## Success Metrics

**Task-level:**
- Time estimate accuracy (actual vs planned)
- First-pass approval rate
- Security vulnerability count (target: 0)
- Test coverage percentage

**System-level:**
- Golden task reuse frequency
- Bad task learning application
- Spec → production cycle time
- Defect escape rate to production

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-25 | PM | Initial document creation |

---

**End of Code Generation Methodology**
