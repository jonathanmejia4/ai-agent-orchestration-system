# Critic Escalation Rules

**Document Version:** 1.0.0
**Last Updated:** 2025-12-24
**Owner:** PM
**Classification:** CRITICAL - Agent Behavior

## Purpose

This document defines when and how the Critic agent must escalate issues to the PM. Proper escalation ensures quality gates are enforced while avoiding bottlenecks.

## Escalation Severity Levels

> **SSOT Reference:** Severity and category values defined in `PLANNING/ESCALATION_PROTOCOL.md`

### Severity: low (No Escalation Required)
- Minor style inconsistencies
- Documentation formatting issues
- Non-blocking suggestions
- Cosmetic improvements

**Action:** Log in verdict, continue review.

### Severity: medium (Optional Escalation)
- Minor code quality issues
- Missing optional documentation
- Non-critical test gaps
- Performance suggestions

**Action:** Include in verdict, escalate only if pattern repeats 3+ times.

### Severity: high (Mandatory Escalation)
- Security vulnerabilities
- Breaking API changes
- Critical bugs
- Missing required tests
- Schema violations

**Action:** MUST escalate to PM before proceeding.

### Severity: critical (Immediate Escalation)
- Data integrity risks
- Production safety concerns
- Compliance violations
- Agent boundary violations

**Action:** STOP review, escalate immediately, await PM decision.

## Escalation Triggers

### Automatic Escalation Required

1. **Security Issues**
   - SQL injection vulnerabilities
   - XSS vulnerabilities
   - Command injection risks
   - Hardcoded credentials
   - Insecure cryptography

2. **Data Integrity**
   - Potential data loss
   - Race conditions
   - Inconsistent state handling
   - Missing validation

3. **Compliance Violations**
   - Agent boundary violations
   - PM-exclusive path modifications
   - Unauthorized escalation chains
   - Policy version mismatches

4. **Quality Gate Failures**
   - Test coverage below threshold
   - Build failures
   - Schema validation failures
   - Dependency conflicts

### Conditional Escalation

Escalate if ANY of these conditions are met:

```yaml
escalate_if:
  - severity >= "high"
  - security_issues > 0
  - breaking_changes == true
  - confidence_score < 0.7
  - repeated_issue_count >= 3
  - affects_multiple_tasks == true
```

## Escalation Protocol

### Step 1: Document Finding

```yaml
finding:
  finding_id: "FND-YYYY-NNN"
  severity: "critical|high|medium|low"  # Per ESCALATION_PROTOCOL.md
  finding_type: "security|quality|compliance|integrity"  # What was found
  escalation_category: "blocker|conflict|resource|timeout|policy|unknown"  # Per ESCALATION_PROTOCOL.md
  description: "Clear description of the issue"
  evidence:
    - file: "path/to/file"
      line: 42
      code_snippet: "problematic code"
  impact: "What could go wrong"
  recommendation: "Suggested fix"
```

**Finding Type to Escalation Category Mapping:**
| Finding Type | Default Escalation Category |
|--------------|----------------------------|
| security | blocker |
| quality | policy |
| compliance | policy |
| integrity | blocker |

### Step 2: Determine Escalation Severity

```python
def determine_escalation_severity(finding):
    """Returns severity per ESCALATION_PROTOCOL.md: critical|high|medium|low"""
    if finding.finding_type == "security":
        return "critical"
    if finding.severity == "critical":
        return "critical"
    if finding.severity == "high":
        return "high"
    if is_repeated(finding, threshold=3):
        return "high"
    if finding.severity == "medium":
        return "medium"
    return "low"
```

### Step 3: Create Escalation Record

```yaml
escalation:
  escalation_id: "ESC-YYYYMMDD-NNN"
  timestamp: "ISO8601"
  source_agent: "critic"
  target_agent: "pm"
  severity: "critical"
  work_order_id: "WO-YYYYMMDD-NNN"
  task_id: "task-X.Y"
  summary: "Brief description"
  findings:
    - finding_id: "FND-YYYY-001"
    - finding_id: "FND-YYYY-002"
  recommended_action: "block|review|proceed_with_caution"
  status: "open"
```

### Step 4: Notify PM

Write escalation entry to `LogBook/pm/escalations/<date>.yaml` (per agent-guardrails.md format) and update work order status:

```yaml
# Update work order
work_order:
  status: "BLOCKED"
  blocked_reason: "Critic escalation: ESC-YYYYMMDD-NNN"
  blocked_at: "timestamp"
```

## Decision Matrix

| Issue Type | Severity | Escalate? | Block Work? | PM Action Required |
|------------|----------|-----------|-------------|-------------------|
| Security Vuln | Critical | YES | YES | Immediate Review |
| Security Vuln | High | YES | YES | Review within 1h |
| Breaking Change | High | YES | YES | Approval Required |
| Test Missing | High | YES | NO | Review Decision |
| Test Missing | Medium | IF REPEATED | NO | Batch Review |
| Style Issue | Low | NO | NO | None |
| Docs Missing | Medium | OPTIONAL | NO | Track Only |
| Schema Invalid | High | YES | YES | Fix Required |

## Escalation Response SLAs

| Severity | Response Time | Resolution Time |
|----------|---------------|-----------------|
| Critical | Immediate | 1 hour |
| High | 1 hour | 4 hours |
| Medium | 4 hours | 24 hours |
| Low | 24 hours | 1 week |

## Anti-Patterns to Avoid

### DO NOT Escalate

1. Personal preferences not backed by standards
2. Issues already documented as accepted technical debt
3. Problems in code not modified by current work order
4. Theoretical issues without evidence
5. Performance concerns without measurements

### DO NOT Block Without Escalation

1. Never reject a work order without creating an escalation
2. Never block Builder without PM visibility
3. Never make policy decisions - defer to PM

## Verdict Structure with Escalations

```yaml
verdict:
  verdict_id: "VER-YYYYMMDD-NNN"
  work_order_id: "WO-YYYYMMDD-NNN"
  timestamp: "ISO8601"
  verdict: "rejected|approved_with_conditions|approved"
  confidence: 0.85

  escalations:
    - escalation_id: "ESC-YYYYMMDD-001"
      severity: "critical"
      blocking: true
    - escalation_id: "ESC-YYYYMMDD-002"
      severity: "high"
      blocking: false

  summary: |
    Review completed with 2 escalations.
    1 critical issue requires PM review before approval.

  conditions:
    - "Resolve ESC-YYYYMMDD-001 before proceeding"
    - "Address ESC-YYYYMMDD-002 in follow-up work order"
```

## Integration with Other Agents

### To PM
- All BLOCKER and CRITICAL escalations
- Blocked work orders
- Policy clarification requests

### From Builder
- Clarification requests (non-blocking)
- Technical feasibility concerns

### To Builder
- Verdict with conditions
- Required changes list
- Approval with caveats

## Monitoring and Metrics

Track these metrics for escalation health:

```yaml
metrics:
  total_escalations: count
  by_severity:
    critical: count
    high: count
    medium: count
  avg_resolution_time: duration
  false_positive_rate: percentage
  escalation_to_verdict_ratio: ratio
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-24 | Initial version |
