# Permission Request Protocol

> **Document Version:** 1.0.0
> **Audience:** Agents
> **Classification:** Tier 2 - Agent Guidelines

## Overview

This protocol enables agents to request user permission for unsafe operations while running in background mode.

**Core Principle:** Check before you act. Auto-approve safe operations, request permission for unsafe ones.

---

## Quick Start

### Step 1: Import and Initialize

```python
from tools.permission_guardrails import SafetyGuardrail, Decision
from tools.permission_request import PermissionRequest

# Initialize guardrail
guardrail = SafetyGuardrail(agent="IF-Lane-E", lane="E")
```

### Step 2: Check Operation Safety

```python
result = guardrail.check_operation(
    operation_type="delete_file",  # See Operation Types below
    target_path="path/to/file.py",
    context={"issue_id": issue_id}
)
```

### Step 3: Act Based on Decision

```python
if result.decision == Decision.AUTO_APPROVE:
    # Proceed immediately
    os.remove("path/to/file.py")
    print(f"Auto-approved: {result.reason}")

elif result.decision == Decision.REQUEST_REQUIRED:
    # Request permission (see below)
    pr = PermissionRequest(lane="E", agent="IF-Lane-E")
    # ... request workflow ...
```

---

## Operation Types

| Operation Type | Common Use Cases |
|---------------|------------------|
| `read_file` | Reading any file |
| `write_file` | Creating or overwriting files |
| `modify_file` | Editing existing files |
| `delete_file` | Removing files |
| `delete_directory` | Removing directories |
| `list_directory` | Listing directory contents |
| `git_status` | Git status checks |
| `git_diff` | Git diff operations |
| `git_log` | Git log queries |
| `git_commit` | Creating commits (check branch!) |
| `create_file` | Creating new files |
| `truncate_file` | Truncating files |

---

## Safety Decision Tree

```
Operation Requested
        │
        ▼
Is it read-only? ──Yes──► AUTO_APPROVE
        │
        No
        ▼
Is it in /tmp/ or own LogBook/temp/? ──Yes──► AUTO_APPROVE
        │
        No
        ▼
Is it writing to own LogBook/{agent}/? ──Yes──► AUTO_APPROVE
        │
        No
        ▼
Is it creating issues in own lane? ──Yes──► AUTO_APPROVE
        │
        No
        ▼
Is it PM-exclusive path? ──Yes──► REQUEST_REQUIRED
        │
        No
        ▼
Is it destructive (delete/truncate)? ──Yes──► REQUEST_REQUIRED
        │
        No
        ▼
Is it commit to main branch? ──Yes──► REQUEST_REQUIRED
        │
        No
        ▼
Is it out of scope? ──Yes──► REQUEST_REQUIRED
        │
        No
        ▼
Unknown operation ──► REQUEST_REQUIRED (safe default)
```

---

## Complete Permission Request Workflow

### 1. Create Permission Request

```python
pr = PermissionRequest(lane="{LANE}", agent="IF-Lane-{LANE}")

request_id = pr.request_permission(
    operation_type="delete_file",
    target="path/to/file.py",
    reason="Clear, specific justification (why this is safe/necessary)",
    options=[
        {
            "option_id": "A",
            "label": "Short action label",
            "description": "Detailed explanation of this option",
            "pros": ["Benefit 1", "Benefit 2"],
            "cons": ["Drawback 1", "Drawback 2"]
        },
        {
            "option_id": "B",
            "label": "Alternative action",
            "description": "Why this might be better",
            "pros": ["Safer", "Recoverable"],
            "cons": ["More work"]
        }
    ],
    recommended="B",  # Recommend the safest option
    issue_id=issue_id,  # Link to issue being fixed
    context={
        "work_order_id": work_order_id,  # If applicable
        "related_files": ["file1.py", "file2.py"],
        "verification_performed": [
            "grep -r 'file.py' → 0 results",
            "git log --follow file.py → last commit 6mo ago"
        ]
    }
)
```

**Best Practices:**
- Provide 2-4 options (not just approve/reject)
- Include a safe alternative (archive instead of delete)
- Show verification steps you performed
- Recommend the safest option
- Use clear, non-technical language for labels

### 2. Wait for Approval

```python
approval = pr.wait_for_approval(
    request_id,
    timeout_seconds=600  # 10 minutes default
)
```

**During wait:**
- Orchestrator detects .request file (within 30s)
- User sees formatted prompt with options
- User selects option or rejects
- Orchestrator writes .approval file
- Agent resumes (within 5s)

### 3. Handle Response

```python
if approval and approval["decision"] == "APPROVED":
    chosen = approval["chosen_option"]

    if chosen == "A":
        # Execute Option A
        os.remove("path/to/file.py")
    elif chosen == "B":
        # Execute Option B
        os.makedirs("archives/deprecated", exist_ok=True)
        os.rename("path/to/file.py", "archives/deprecated/file.py")

    print(f"Operation completed: Option {chosen}")

elif approval and approval["decision"] == "REJECTED":
    # User explicitly rejected
    print("Permission denied by user - skipping operation")
    # Update issue status if needed

else:
    # Timeout (approval is None)
    print("Permission request timed out - skipping operation")

    # Signal blocked status
    with open("LogBook/issue-fixing/signals/{LANE}.status", 'w') as f:
        f.write(f"BLOCKED: Permission timeout on {operation_type}")

    # Update issue
    # ... mark as BLOCKED_ON_PERMISSION ...

    # Continue with other work (non-blocking failure)
```

### 4. Clean Up

```python
# Always clean up request/approval files
pr.cleanup_request()
```

This archives the files to `LogBook/permissions/archive/` for audit trail.

---

## Examples

### Example 1: Delete Deprecated File

```python
guardrail = SafetyGuardrail(agent="IF-Lane-E", lane="E")
result = guardrail.check_operation(
    operation_type="delete_file",
    target_path="src/legacy/deprecated_auth.py"
)

if result.decision == Decision.REQUEST_REQUIRED:
    pr = PermissionRequest(lane="E", agent="IF-Lane-E")

    request_id = pr.request_permission(
        operation_type="delete_file",
        target="src/legacy/deprecated_auth.py",
        reason="File deprecated 6 months ago, no active references found",
        options=[
            {
                "option_id": "A",
                "label": "Delete file",
                "description": "Permanently remove deprecated authentication module",
                "pros": ["Clean codebase", "Remove unused code"],
                "cons": ["Permanent deletion", "Cannot recover easily"]
            },
            {
                "option_id": "B",
                "label": "Archive instead",
                "description": "Move to archives/deprecated/ for future reference",
                "pros": ["Recoverable if needed", "Maintains history"],
                "cons": ["Still takes disk space"]
            },
            {
                "option_id": "C",
                "label": "Skip this issue",
                "description": "Leave file as-is, mark issue as deferred",
                "pros": ["No risk"],
                "cons": ["Issue remains open"]
            }
        ],
        recommended="B",
        issue_id="E-45",
        context={
            "verification_performed": [
                "grep -r 'deprecated_auth' src/ → 0 results",
                "grep -r 'deprecated_auth' tests/ → 0 results",
                "git log --follow src/legacy/deprecated_auth.py → last change 6mo ago",
                "git blame shows deprecated marker added 6mo ago"
            ]
        }
    )

    approval = pr.wait_for_approval(request_id, timeout_seconds=600)

    if approval and approval["decision"] == "APPROVED":
        if approval["chosen_option"] == "A":
            os.remove("src/legacy/deprecated_auth.py")
        elif approval["chosen_option"] == "B":
            os.makedirs("archives/deprecated", exist_ok=True)
            os.rename("src/legacy/deprecated_auth.py",
                     "archives/deprecated/deprecated_auth.py")
        elif approval["chosen_option"] == "C":
            print("Skipping deletion - marking issue as deferred")

    pr.cleanup_request()
```

### Example 2: Modify Out-of-Scope File

```python
# Trying to modify a file outside lane's scope
result = guardrail.check_operation(
    operation_type="modify_file",
    target_path=".claude/guidelines/some-guideline.md"
)

# result.decision == Decision.REQUEST_REQUIRED
# result.reason == "PM-exclusive path: .claude/guidelines/some-guideline.md"

# Must request permission to modify PM-exclusive paths
```

### Example 3: Safe Operation (No Request Needed)

```python
# Reading a file is always safe
result = guardrail.check_operation(
    operation_type="read_file",
    target_path="src/api/client.py"
)

# result.decision == Decision.AUTO_APPROVE
# result.reason == "Read-only operation"

# Proceed immediately
with open("src/api/client.py", 'r') as f:
    content = f.read()
```

---

## Timeout Handling

If permission request times out (default 10 minutes):

1. **Signal blocked status:**
```bash
echo "BLOCKED: Permission timeout on {operation_type}" > LogBook/issue-fixing/signals/{LANE}.status
```

2. **Update issue:**
```yaml
status: "BLOCKED_ON_PERMISSION"
blocked_reason: "User approval required for {operation_type}, request timed out"
blocked_timestamp: "2026-01-10T06:00:00Z"
```

3. **Continue with other work:**
```python
# Timeout is non-blocking - continue fixing other issues
print(f"Skipping {issue_id} due to permission timeout")
continue  # Move to next issue
```

4. **Report in completion:**
```bash
# In final status
echo "COMPLETE: fixed 4/5 issues (1 blocked on permission)" > signals/{LANE}.status
```

---

## Fallback Behavior ("Option B")

When permission request times out after 10 minutes or user rejects:

1. **Update issue status:**
   - Add `blocked_on: ["USER_APPROVAL"]` to issue frontmatter
   - OR change `status: "OPEN"` to `status: "BLOCKED_ON_PERMISSION"`

2. **Signal orchestrator:**
   ```bash
   echo "BLOCKED: Permission timeout on {operation}" > LogBook/issue-fixing/signals/{LANE}.status
   ```

3. **Continue with other issues:**
   - Do NOT halt the entire lane
   - Process remaining issues in the queue
   - Report blocked issue count in final status

4. **Clean up:**
   ```python
   pr.cleanup_request()  # Archives request/approval files
   ```

This "Option B" behavior ensures lanes make progress even when blocked on individual issues.

### Timeout and Fallback Summary

- Default timeout: **10 minutes** (600 seconds)
- Orchestrator polls every 30 seconds
- Agent polls every 5 seconds
- On timeout: Issue marked BLOCKED, agent continues with other work
- Non-blocking: Timeouts don't halt entire lanes

---

## Troubleshooting

### Q: Guardrail check is slow?

**A:** Guardrail checks should be < 1ms. If slow:
- Check for regex complexity in path matching
- Ensure not doing file I/O in check_operation()

### Q: Permission request not detected?

**A:** Orchestrator polls every 30 seconds. Wait up to 30s for detection.

### Q: Approval not received?

**A:** Check:
1. Request file created? `ls LogBook/permissions/{LANE}.request`
2. Approval file created? `ls LogBook/permissions/{LANE}.approval`
3. Request_id matches? `grep request_id LogBook/permissions/{LANE}.*`

### Q: Agent blocked on permission?

**A:** Expected for background agents on unsafe operations. Solutions:
1. Use permission request system (this protocol)
2. Request operation be approved manually
3. Find alternative safe operation

### Q: How to test permission system?

**A:**
```bash
# 1. Test guardrails
python3 tools/permission_guardrails.py --test

# 2. Test permission request
python3 tools/permission_request.py --test

# 3. Test orchestrator handler
python3 tools/orchestrator_permission_handler.py --test
```

---

## Best Practices

1. **Always check guardrails first** - Don't assume operations are safe or unsafe

2. **Provide context** - Show verification steps, explain reasoning

3. **Offer alternatives** - Give user multiple safe options, not just yes/no

4. **Recommend safest** - Use `recommended` field for safest option

5. **Handle timeouts gracefully** - Timeout is normal, continue with other work

6. **Clean up** - Always call `pr.cleanup_request()` to archive signals

7. **Non-blocking failures** - Permission issues shouldn't halt all work

8. **Clear language** - Use plain English in labels/descriptions, not code terms

---

## Related Documentation

- **Full Specification:** `PLANNING/PERMISSION_SYSTEM_SPEC.md`
- **Schema:** `PLANNING/schemas/permission_request_schema.yaml`
- **Implementation:** `tools/permission_guardrails.py`, `tools/permission_request.py`

---

*End of Protocol*
