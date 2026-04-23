# Critic Self-Validation Protocol

> **Document Version:** 1.0.0
> **Last Updated:** 2025-01-15
> **Classification:** CRITICAL - Review Integrity
> **Reference:** FAILURE_MODES.md:456, ROLLBACK_PROCEDURES.md:289

## Purpose

This document defines the **mandatory self-validation protocols** for the Critic agent within the the system. Before issuing any verdict, the Critic MUST perform these validation checks to ensure review integrity, detect bias, and maintain audit trail compliance.

**Why This Matters:**
- Prevents rubber-stamp approvals and arbitrary rejections
- Ensures verdicts are based on objective criteria
- Detects and mitigates reviewer bias
- Maintains credibility of the review process
- Provides audit trail for all review decisions

---

## 1. Self-Validation Checklist

The Critic MUST complete this checklist BEFORE issuing any verdict.

### 1.1 Pre-Review Validation

```yaml
pre_review_checklist:
  - id: PRE-001
    check: "Have I read the COMPLETE implementation?"
    required: true
    failure_action: "Cannot proceed - read all relevant files first"

  - id: PRE-002
    check: "Have I reviewed the associated work order?"
    required: true
    failure_action: "Cannot proceed - review WO requirements first"

  - id: PRE-003
    check: "Have I checked for related previous reviews?"
    required: true
    failure_action: "Cannot proceed - check review history"

  - id: PRE-004
    check: "Am I reviewing within my assigned scope?"
    required: true
    failure_action: "Cannot proceed - escalate to PM if out of scope"

  - id: PRE-005
    check: "Have I declared any conflicts of interest?"
    required: true
    failure_action: "Cannot proceed - document conflicts first"
```

### 1.2 During-Review Validation

```yaml
during_review_checklist:
  - id: DUR-001
    check: "Am I evaluating against OBJECTIVE criteria?"
    required: true
    bias_indicator: "Subjective language detected"

  - id: DUR-002
    check: "Have I tested/verified claims, not just read code?"
    required: true
    failure_action: "Run tests or validation before verdict"

  - id: DUR-003
    check: "Am I considering the full context, not just snippets?"
    required: true
    bias_indicator: "Cherry-picking code sections"

  - id: DUR-004
    check: "Have I checked for SSOT compliance?"
    required: true
    failure_action: "Run schema_validator.py"

  - id: DUR-005
    check: "Have I verified idempotence requirements?"
    required: true
    failure_action: "Run idempotence_validator.py"
```

### 1.3 Pre-Verdict Validation

```yaml
pre_verdict_checklist:
  - id: VER-001
    check: "Is my verdict supported by specific evidence?"
    required: true
    failure_action: "Document evidence before issuing verdict"

  - id: VER-002
    check: "Have I considered alternative interpretations?"
    required: true
    bias_indicator: "Single-perspective analysis"

  - id: VER-003
    check: "Would another Critic reach the same conclusion?"
    required: true
    bias_indicator: "Inconsistent with past similar reviews"

  - id: VER-004
    check: "Is my feedback actionable and specific?"
    required: true
    failure_action: "Revise feedback to be actionable"

  - id: VER-005
    check: "Have I applied severity levels consistently?"
    required: true
    failure_action: "Review severity guidelines"
```

---

## 2. Bias Detection Mechanisms

### 2.1 Bias Types to Monitor

| Bias Type | Description | Detection Method | Mitigation |
|-----------|-------------|------------------|------------|
| **Confirmation Bias** | Looking for evidence to support predetermined conclusion | Compare evidence for/against | List counter-evidence explicitly |
| **Recency Bias** | Over-weighting recent interactions | Review history across time | Consider full context |
| **Anchoring Bias** | Over-relying on first impression | Re-review after initial assessment | Second-pass review |
| **Availability Bias** | Judging based on easily recalled examples | Systematic checklist review | Use standardized criteria |
| **Severity Inflation** | Over-escalating minor issues | Compare to severity guidelines | Calibrate with examples |
| **Severity Deflation** | Under-reporting serious issues | Compare to severity guidelines | Explicit severity mapping |
| **Agent Bias** | Treating agents differently | Track verdicts by agent | Statistical analysis |

### 2.2 Bias Detection Queries

Before issuing a verdict, the Critic MUST ask:

```markdown
## Bias Self-Check Questions

1. CONFIRMATION BIAS CHECK:
   - What evidence CONTRADICTS my current conclusion?
   - Have I weighted contrary evidence fairly?
   - Am I ignoring inconvenient facts?

2. CONSISTENCY CHECK:
   - How did I verdict similar issues in the past?
   - Am I applying the same standard to this agent as others?
   - Would I verdict this differently if Builder X vs Builder Y submitted it?

3. PROPORTIONALITY CHECK:
   - Does the severity match the actual impact?
   - Am I making mountains out of molehills?
   - Am I dismissing serious issues as minor?

4. EVIDENCE CHECK:
   - Is every claim in my verdict backed by specific evidence?
   - Can I point to exact lines/files for each issue?
   - Would my evidence convince a neutral observer?

5. COMPLETENESS CHECK:
   - Did I review ALL relevant code, not just samples?
   - Did I actually run tests/validators?
   - Did I check SSOT and idempotence compliance?
```

### 2.3 Automated Bias Detection

```python
class BiasDetector:
    """Detects potential bias in Critic verdicts."""

    def __init__(self, verdict_history: list):
        self.history = verdict_history

    def detect_agent_bias(self, current_verdict: dict) -> dict:
        """
        Detect if Critic treats agents differently.

        Returns bias indicators and statistical analysis.
        """
        agent = current_verdict.get("agent")
        verdict = current_verdict.get("verdict")

        # Calculate approval rates by agent
        agent_stats = self._calculate_agent_stats()

        # Check for statistical outliers
        if agent in agent_stats:
            agent_approval_rate = agent_stats[agent]["approval_rate"]
            overall_approval_rate = self._overall_approval_rate()

            deviation = abs(agent_approval_rate - overall_approval_rate)

            if deviation > 0.20:  # 20% deviation threshold
                return {
                    "bias_detected": True,
                    "bias_type": "AGENT_BIAS",
                    "agent": agent,
                    "agent_approval_rate": agent_approval_rate,
                    "overall_rate": overall_approval_rate,
                    "deviation": deviation,
                    "recommendation": "Review verdict for potential agent bias"
                }

        return {"bias_detected": False}

    def detect_severity_drift(self, current_verdict: dict) -> dict:
        """
        Detect if severity ratings are drifting over time.
        """
        recent_verdicts = self.history[-20:]  # Last 20 verdicts
        older_verdicts = self.history[-50:-20] if len(self.history) > 50 else []

        if not older_verdicts:
            return {"bias_detected": False, "reason": "Insufficient history"}

        recent_severity_avg = self._average_severity(recent_verdicts)
        older_severity_avg = self._average_severity(older_verdicts)

        drift = recent_severity_avg - older_severity_avg

        if abs(drift) > 0.5:  # Half severity level drift
            drift_type = "INFLATION" if drift > 0 else "DEFLATION"
            return {
                "bias_detected": True,
                "bias_type": f"SEVERITY_{drift_type}",
                "recent_avg": recent_severity_avg,
                "historical_avg": older_severity_avg,
                "drift": drift,
                "recommendation": f"Severity ratings drifting {drift_type.lower()}"
            }

        return {"bias_detected": False}

    def detect_rubber_stamping(self, recent_window: int = 10) -> dict:
        """
        Detect if Critic is rubber-stamping approvals without thorough review.
        """
        recent = self.history[-recent_window:]

        if not recent:
            return {"bias_detected": False}

        # Check for suspiciously fast reviews
        fast_reviews = [v for v in recent if v.get("review_duration_minutes", 0) < 5]

        # Check for all-approval streaks
        approval_streak = all(v.get("verdict") == "APPROVED" for v in recent)

        # Check for lack of detailed feedback
        shallow_reviews = [v for v in recent if len(v.get("feedback", "")) < 100]

        if len(fast_reviews) > 5 or (approval_streak and len(recent) > 5) or len(shallow_reviews) > 7:
            return {
                "bias_detected": True,
                "bias_type": "RUBBER_STAMPING",
                "fast_reviews": len(fast_reviews),
                "approval_streak": approval_streak,
                "shallow_reviews": len(shallow_reviews),
                "recommendation": "Reviews may lack thoroughness - slow down and provide detailed feedback"
            }

        return {"bias_detected": False}

    def _calculate_agent_stats(self) -> dict:
        """Calculate verdict statistics by agent."""
        stats = {}
        for verdict in self.history:
            agent = verdict.get("agent", "unknown")
            if agent not in stats:
                stats[agent] = {"total": 0, "approved": 0}
            stats[agent]["total"] += 1
            if verdict.get("verdict") == "APPROVED":
                stats[agent]["approved"] += 1

        for agent in stats:
            if stats[agent]["total"] > 0:
                stats[agent]["approval_rate"] = stats[agent]["approved"] / stats[agent]["total"]
            else:
                stats[agent]["approval_rate"] = 0

        return stats

    def _overall_approval_rate(self) -> float:
        """Calculate overall approval rate."""
        if not self.history:
            return 0.0
        approved = sum(1 for v in self.history if v.get("verdict") == "APPROVED")
        return approved / len(self.history)

    def _average_severity(self, verdicts: list) -> float:
        """Calculate average severity from verdicts."""
        severity_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        severities = [severity_map.get(v.get("severity", "MEDIUM"), 2) for v in verdicts]
        return sum(severities) / len(severities) if severities else 2.0
```

---

## 3. Verdict Validation Requirements

### 3.0 Scope Clarification (Issue S-34)

**IMPORTANT:** This self-validation protocol has different applicability:

| Workflow | self_validation Required | Rationale |
|----------|-------------------------|-----------|
| **PlanAuditor verdicts** | YES (mandatory) | Human-facing plan reviews need bias tracking |
| **Orchestrator task verdicts** | OPTIONAL (recommended) | Orchestrator aggregates dimension critic outputs; self-validation may be performed at dimension level |
| **Dimension critic results** | NO | Dimension critics return structured results, not standalone verdicts |

The `self_validation` field is defined as **optional** in `critic_verdict_detailed_schema.yaml` (lines 202-216) to accommodate both workflows. The validation code below (Section 3.2) is intended for **standalone verdicts** where thorough bias checking is critical. Orchestrator aggregate verdicts may omit self_validation if dimension critics performed their own validation.

### 3.1 Valid Verdict Structure

Every standalone verdict SHOULD include (MUST for PlanAuditor):

```yaml
verdict_entry:
  # Required metadata
  verdict_id: "VER-20250115-XXX"
  timestamp: "2025-01-15T10:30:00Z"
  agent: "critic"
  task_id: "X.Y"
  work_order_id: "WO-XXXX-XXX"

  # Required verdict information
  verdict: "APPROVED | REJECTED | NEEDS_REVISION | PENDING"
  confidence: 0.0-1.0  # Critic's confidence in verdict
  review_duration_minutes: integer

  # Required evidence
  evidence:
    files_reviewed:
      - path: "path/to/file"
        lines_reviewed: "all | 1-100"
    tests_run:
      - name: "test name"
        result: "pass | fail"
    validators_executed:
      - name: "schema_validator"
        result: "pass | fail"

  # Required analysis
  analysis:
    strengths: ["list of positive aspects"]
    issues: ["list of issues found"]
    severity_breakdown:
      critical: 0
      high: 0
      medium: 0
      low: 0

  # Required feedback (if not APPROVED)
  feedback:
    summary: "Brief summary of feedback"
    actionable_items:
      - item: "Specific action needed"
        severity: "HIGH | MEDIUM | LOW"
        reference: "file:line or description"

  # Required self-validation
  self_validation:
    pre_review_complete: true
    during_review_complete: true
    pre_verdict_complete: true
    bias_checks_performed: true
    bias_detected: false
    conflicts_declared: []
```

### 3.2 Verdict Validation Rules

```python
def validate_verdict(verdict: dict) -> dict:
    """
    Validate a Critic verdict for completeness and integrity.

    Returns validation result with any issues found.
    """
    errors = []
    warnings = []

    # Required fields check (Issue S-34: self_validation is optional for Orchestrator)
    # For PlanAuditor: all fields including self_validation are required
    # For Orchestrator: self_validation is optional (recommended but not required)
    required_fields = [
        "verdict_id", "timestamp", "agent", "task_id",
        "verdict", "confidence", "evidence", "analysis"
        # "self_validation" - optional for Orchestrator, required for PlanAuditor
    ]

    for field in required_fields:
        if field not in verdict:
            errors.append(f"Missing required field: {field}")

    # Verdict value check
    valid_verdicts = ["APPROVED", "REJECTED", "NEEDS_REVISION", "PENDING"]
    if verdict.get("verdict") not in valid_verdicts:
        errors.append(f"Invalid verdict value: {verdict.get('verdict')}")

    # Confidence range check
    confidence = verdict.get("confidence", 0)
    if not (0.0 <= confidence <= 1.0):
        errors.append(f"Confidence out of range: {confidence}")

    # Evidence check
    evidence = verdict.get("evidence", {})
    if not evidence.get("files_reviewed"):
        errors.append("No files reviewed - evidence required")

    # Self-validation check (Issue S-34: optional for Orchestrator, required for PlanAuditor)
    self_val = verdict.get("self_validation", {})
    if self_val:
        required_checks = [
            "pre_review_complete", "during_review_complete",
            "pre_verdict_complete", "bias_checks_performed"
        ]
        for check in required_checks:
            if not self_val.get(check):
                errors.append(f"Self-validation incomplete: {check}")
    else:
        # Missing self_validation is a warning for Orchestrator, not an error
        warnings.append("No self_validation section - recommended for audit trail")

    # Feedback required for non-APPROVED verdicts
    if verdict.get("verdict") != "APPROVED":
        if not verdict.get("feedback", {}).get("actionable_items"):
            errors.append("Non-APPROVED verdict requires actionable feedback")

    # Low confidence warning
    if confidence < 0.7:
        warnings.append(f"Low confidence ({confidence}) - consider additional review")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
```

---

## 4. Cross-Reference Verification

### 4.1 Required Cross-References

Before finalizing a verdict, the Critic MUST verify:

| Reference Type | Source | Verification Method |
|----------------|--------|---------------------|
| **Work Order** | PLANNING/WORK_ORDER_QUEUE.yaml | Check requirements match implementation |
| **Previous Verdicts** | LogBook/critic/verdicts/VER-*.yaml | Check for contradictions |
| **Builder LogBook** | LogBook/builder/progress.yaml | Verify claimed completion |
| **SSOT** | ISSUE_CATALOG.md | Check issue tracking |
| **Test Results** | CI/CD or local tests | Verify tests pass |
| **Task Dependencies** | Task/manifest files | Check dependency satisfaction |

### 4.2 Cross-Reference Validation Code

```python
class CrossReferenceValidator:
    """Validates cross-references for Critic verdicts."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)

    def validate_work_order_match(
        self,
        task_id: str,
        work_order_id: str,
        implementation_summary: str
    ) -> dict:
        """
        Verify implementation matches work order requirements.
        """
        wo_path = self.base_path / "PLANNING" / "WORK_ORDER_QUEUE.yaml"

        if not wo_path.exists():
            return {"valid": False, "error": "Work order queue not found"}

        with open(wo_path) as f:
            queue = yaml.safe_load(f)

        # Find the work order
        work_order = None
        for wo in queue.get("work_orders", []):
            if wo.get("work_order_id") == work_order_id:
                work_order = wo
                break

        if not work_order:
            return {"valid": False, "error": f"Work order {work_order_id} not found"}

        # Check task_id matches
        if work_order.get("task_id") != task_id:
            return {
                "valid": False,
                "error": f"Task ID mismatch: WO has {work_order.get('task_id')}, reviewing {task_id}"
            }

        return {
            "valid": True,
            "work_order": work_order,
            "requirements": work_order.get("requirements", [])
        }

    def check_previous_verdicts(self, task_id: str) -> dict:
        """
        Check for previous verdicts on this task.
        """
        verdicts_dir = self.base_path / "LogBook" / "critic" / "verdicts"

        if not verdicts_dir.exists():
            return {"has_previous": False, "verdicts": []}

        # Glob for individual verdict files
        previous = []
        for verdict_file in verdicts_dir.glob("VER-*.yaml"):
            with open(verdict_file) as f:
                data = yaml.safe_load(f) or {}
            if data.get("task_id") == task_id:
                previous.append(data)

        return {
            "has_previous": len(previous) > 0,
            "verdicts": previous,
            "last_verdict": previous[-1] if previous else None
        }

    def verify_builder_claims(self, task_id: str, work_order_id: str) -> dict:
        """
        Verify Builder's claimed completion status.
        """
        progress_path = self.base_path / "LogBook" / "builder" / "progress.yaml"

        if not progress_path.exists():
            return {"verified": False, "error": "Builder progress log not found"}

        with open(progress_path) as f:
            data = yaml.safe_load(f) or {}

        # Find matching entry
        entries = [
            e for e in data.get("entries", [])
            if e.get("task_id") == task_id or e.get("work_order_id") == work_order_id
        ]

        if not entries:
            return {"verified": False, "error": "No matching Builder entry found"}

        latest = entries[-1]
        return {
            "verified": True,
            "claimed_status": latest.get("status"),
            "claimed_completion": latest.get("completion_percentage"),
            "entry": latest
        }
```

### 4.3 Cross-Reference Checklist

```markdown
## Cross-Reference Verification Checklist

[ ] Work Order Requirements
    - [ ] All requirements listed in WO are addressed
    - [ ] No scope creep beyond WO requirements
    - [ ] Task ID matches WO assignment

[ ] Previous Verdicts
    - [ ] Checked for prior reviews of this task
    - [ ] If NEEDS_REVISION, verified issues addressed
    - [ ] No contradictory verdicts being issued

[ ] Builder Claims
    - [ ] Builder marked as complete before review
    - [ ] Builder's claimed scope matches actual changes
    - [ ] Builder's LogBook entry exists

[ ] Schema Compliance
    - [ ] Ran schema_validator.py
    - [ ] No schema violations detected
    - [ ] Any catalog references are accurate

[ ] Test Verification
    - [ ] Unit tests exist for new code
    - [ ] All tests pass
    - [ ] Test coverage meets threshold

[ ] Dependency Check
    - [ ] All dependencies satisfied
    - [ ] No circular dependencies introduced
    - [ ] Version constraints respected
```

---

## 5. Conflict of Interest Protocol

### 5.1 Conflict Types

| Conflict Type | Example | Required Action |
|---------------|---------|-----------------|
| **Self-Review** | Critic reviewing own code | REJECT - escalate to PM |
| **Prior Involvement** | Critic previously worked on task | DISCLOSE - may proceed with disclosure |
| **Agent Relationship** | Personal bias toward/against agent | DISCLOSE - consider recusal |
| **Time Pressure** | External pressure for quick approval | DISCLOSE - document and resist |
| **Outcome Interest** | Critic benefits from specific verdict | REJECT - escalate to PM |

### 5.2 Conflict Declaration

Before starting a review, the Critic MUST declare conflicts:

```yaml
conflict_declaration:
  reviewer: "critic"
  task_id: "X.Y"
  work_order_id: "WO-XXXX-XXX"
  timestamp: "2025-01-15T10:00:00Z"

  conflicts_identified:
    - type: "PRIOR_INVOLVEMENT"
      description: "Previously suggested this approach in planning phase"
      severity: "LOW"
      decision: "PROCEED_WITH_DISCLOSURE"

    - type: "TIME_PRESSURE"
      description: "PM requested expedited review"
      severity: "MEDIUM"
      decision: "PROCEED_WITH_DISCLOSURE"

  no_conflicts_statement: false  # Set to true if no conflicts exist

  recusal_required: false  # Set to true if conflicts require recusal
```

### 5.3 Conflict Resolution Flow

```
STEP 1: IDENTIFY
  - Review conflict types checklist
  - Document any potential conflicts

STEP 2: ASSESS SEVERITY
  - LOW: Minor prior involvement
  - MEDIUM: Relationship or pressure factors
  - HIGH: Direct interest in outcome
  - CRITICAL: Self-review or direct benefit

STEP 3: DECIDE
  - LOW/MEDIUM: Proceed with disclosure
  - HIGH: Consider recusal, escalate to PM
  - CRITICAL: Must recuse, escalate to PM

STEP 4: DOCUMENT
  - Record conflict in verdict entry
  - Include in LogBook/critic/ entry

STEP 5: PROCEED OR RECUSE
  - If proceeding: Apply extra scrutiny
  - If recusing: Escalate to PM for alternate reviewer
```

---

## 6. Self-Validation Enforcement

### 6.1 Automated Enforcement

```python
def enforce_self_validation(verdict_func):
    """
    Decorator to enforce self-validation before verdict issuance.
    """
    def wrapper(critic_agent, task_id: str, work_order_id: str, **kwargs):
        # Pre-review validation
        pre_review = critic_agent.validate_pre_review(task_id, work_order_id)
        if not pre_review["complete"]:
            raise SelfValidationError(
                f"Pre-review validation failed: {pre_review['missing']}"
            )

        # Check for conflicts
        conflicts = critic_agent.check_conflicts(task_id, work_order_id)
        if conflicts["recusal_required"]:
            raise ConflictOfInterestError(
                f"Recusal required: {conflicts['reason']}"
            )

        # Run bias detection
        bias_check = critic_agent.detect_bias()
        if bias_check["bias_detected"]:
            # Log warning but allow to proceed with disclosure
            critic_agent.log_bias_warning(bias_check)

        # Execute verdict function
        verdict = verdict_func(critic_agent, task_id, work_order_id, **kwargs)

        # Post-verdict validation
        validation = validate_verdict(verdict)
        if not validation["valid"]:
            raise VerdictValidationError(
                f"Verdict validation failed: {validation['errors']}"
            )

        # Attach self-validation record
        verdict["self_validation"] = {
            "pre_review_complete": True,
            "during_review_complete": True,
            "pre_verdict_complete": True,
            "bias_checks_performed": True,
            "bias_detected": bias_check.get("bias_detected", False),
            "conflicts_declared": conflicts.get("conflicts", [])
        }

        return verdict

    return wrapper


class SelfValidationError(Exception):
    """Raised when self-validation fails."""
    pass


class ConflictOfInterestError(Exception):
    """Raised when conflict of interest requires recusal."""
    pass


class VerdictValidationError(Exception):
    """Raised when verdict fails validation."""
    pass
```

### 6.2 Pre-Commit Hook for Verdicts

```bash
#!/bin/bash
# .git/hooks/pre-commit (Critic verdict validation excerpt)

# Check for verdict files being committed
VERDICT_FILES=$(git diff --cached --name-only | grep -E "LogBook/critic/.*\.yaml$")

if [ -n "$VERDICT_FILES" ]; then
    echo "Validating Critic verdicts..."

    for file in $VERDICT_FILES; do
        # Run verdict validator
        python tools/validate_review_verdict.py "$file"

        if [ $? -ne 0 ]; then
            echo "ERROR: Verdict validation failed for $file"
            echo "Please ensure all self-validation steps are complete."
            exit 1
        fi
    done

    echo "All verdicts validated successfully"
fi
```

---

## 7. Audit Trail Integration

### 7.1 Verdict Logging

Every verdict MUST be logged to:

```
LogBook/critic/
├── verdicts/             # Individual verdict files
│   └── VER-<task-id>.yaml
├── self_validation/      # Self-validation records
│   └── 2025-01/
│       └── SVR-2025-XXX.yaml
└── bias_reports/         # Bias detection reports
    └── 2025-01/
        └── BIAS-2025-XXX.yaml
```

### 7.2 Self-Validation Record Format

```yaml
# LogBook/critic/self_validation/SVR-2025-XXX.yaml
self_validation_record:
  record_id: "SVR-2025-XXX"
  verdict_id: "VER-20250115-XXX"
  timestamp: "2025-01-15T10:30:00Z"
  task_id: "X.Y"
  work_order_id: "WO-XXXX-XXX"

  pre_review:
    completed: true
    checks:
      PRE-001: {status: "pass", notes: ""}
      PRE-002: {status: "pass", notes: ""}
      PRE-003: {status: "pass", notes: "No previous reviews"}
      PRE-004: {status: "pass", notes: ""}
      PRE-005: {status: "pass", notes: "No conflicts declared"}

  during_review:
    completed: true
    checks:
      DUR-001: {status: "pass", notes: "Used objective criteria"}
      DUR-002: {status: "pass", notes: "Ran unit tests"}
      DUR-003: {status: "pass", notes: "Reviewed all files"}
      DUR-004: {status: "pass", notes: "schema_validator passed"}
      DUR-005: {status: "pass", notes: "idempotence_validator passed"}

  pre_verdict:
    completed: true
    checks:
      VER-001: {status: "pass", notes: "Evidence documented"}
      VER-002: {status: "pass", notes: "Alternative considered"}
      VER-003: {status: "pass", notes: "Consistent with history"}
      VER-004: {status: "pass", notes: "Feedback is actionable"}
      VER-005: {status: "pass", notes: "Severity calibrated"}

  bias_detection:
    performed: true
    bias_detected: false
    checks_run:
      - agent_bias: false
      - severity_drift: false
      - rubber_stamping: false

  cross_references:
    work_order_verified: true
    previous_verdicts_checked: true
    builder_claims_verified: true
    ssot_compliant: true
    tests_verified: true

  conflicts:
    declared: []
    recusal_required: false
```

---

## 8. Quick Reference

### 8.1 Critic Self-Validation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    CRITIC SELF-VALIDATION                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. PRE-REVIEW                                              │
│     ├── Read complete implementation                        │
│     ├── Review work order                                   │
│     ├── Check previous reviews                              │
│     ├── Verify scope                                        │
│     └── Declare conflicts                                   │
│                                                              │
│  2. DURING REVIEW                                           │
│     ├── Apply objective criteria                            │
│     ├── Run tests/validators                                │
│     ├── Review full context                                 │
│     └── Check SSOT/idempotence                              │
│                                                              │
│  3. PRE-VERDICT                                             │
│     ├── Document evidence                                   │
│     ├── Consider alternatives                               │
│     ├── Verify consistency                                  │
│     ├── Ensure actionable feedback                          │
│     └── Calibrate severity                                  │
│                                                              │
│  4. BIAS DETECTION                                          │
│     ├── Agent bias check                                    │
│     ├── Severity drift check                                │
│     └── Rubber-stamping check                               │
│                                                              │
│  5. CROSS-REFERENCE                                         │
│     ├── Work order requirements                             │
│     ├── Previous verdicts                                   │
│     ├── Builder claims                                      │
│     └── Test results                                        │
│                                                              │
│  6. ISSUE VERDICT                                           │
│     ├── Complete verdict structure                          │
│     ├── Attach self-validation record                       │
│     └── Log to LogBook/critic/                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Red Flags Checklist

Before issuing ANY verdict, ensure NONE of these red flags are present:

```markdown
## RED FLAGS - STOP AND REASSESS IF ANY ARE TRUE

[ ] I haven't read all the relevant code
[ ] I'm rushing due to time pressure
[ ] I have a predetermined conclusion
[ ] I'm reviewing my own work
[ ] I'm ignoring evidence that contradicts my conclusion
[ ] My feedback is vague or non-actionable
[ ] I haven't run any tests or validators
[ ] I'm treating this agent differently than others
[ ] I'm approving without finding ANY issues (suspicious)
[ ] I'm rejecting without providing clear reasons
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-15 | PM | Initial document creation |

---

**CRITICAL REMINDER:** Self-validation is NOT optional. Every verdict without complete self-validation is invalid and will be rejected. The integrity of the entire review process depends on Critic discipline.
