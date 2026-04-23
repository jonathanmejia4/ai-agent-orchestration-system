#!/usr/bin/env python3
"""
Add Permission Handling section to all IF-Lane-*.md agent specs

Inserts a standardized "Permission Handling" section after "Status Signals"
and before "Find Open Issues" in each lane fixer agent spec.
"""

import os
import re
import glob


PERMISSION_HANDLING_SECTION = '''
### Permission Handling

**Before ANY unsafe operation (deletions, out-of-scope modifications):**

1. **Check with guardrails:**
```python
from tools.permission_guardrails import SafetyGuardrail, Decision

guardrail = SafetyGuardrail(agent="IF-Lane-{LANE}", lane="{LANE}")
result = guardrail.check_operation(
    operation_type="delete_file",  # or "modify_file", "create_file", etc.
    target_path="path/to/file.py",
    context={{"issue_id": issue_id}}
)
```

2. **If SAFE → Proceed directly:**
```python
if result.decision == Decision.AUTO_APPROVE:
    # Execute operation immediately
    os.remove("path/to/file.py")
    # or os.rename(), open(..., 'w'), etc.
    print(f"Operation auto-approved: {{result.reason}}")
```

3. **If UNSAFE → Request permission:**
```python
if result.decision == Decision.REQUEST_REQUIRED:
    from tools.permission_request import PermissionRequest

    pr = PermissionRequest(lane="{LANE}", agent="IF-Lane-{LANE}")

    request_id = pr.request_permission(
        operation_type="delete_file",
        target="path/to/file.py",
        reason="Detailed justification (e.g., 'No references found, deprecated 6mo ago')",
        options=[
            {{
                "option_id": "A",
                "label": "Delete file",
                "description": "Permanently remove the file",
                "pros": ["Clean codebase"],
                "cons": ["Permanent deletion"]
            }},
            {{
                "option_id": "B",
                "label": "Archive instead",
                "description": "Move to archives/deprecated/",
                "pros": ["Recoverable if needed"],
                "cons": ["Adds clutter"]
            }}
        ],
        recommended="B",  # Suggest safest option
        issue_id=issue_id,
        context={{
            "verification_performed": [
                "grep -r 'deprecated_file' → 0 results",
                "git log --follow file.py → last commit 6mo ago"
            ]
        }}
    )

    # Wait for user decision (timeout 5 min)
    approval = pr.wait_for_approval(request_id, timeout_seconds=300)

    if approval and approval["decision"] == "APPROVED":
        chosen = approval["chosen_option"]
        if chosen == "A":
            os.remove("path/to/file.py")
        elif chosen == "B":
            os.makedirs("archives/deprecated", exist_ok=True)
            os.rename("path/to/file.py", "archives/deprecated/file.py")

        print(f"Operation completed: Option {{chosen}}")
    else:
        # Permission denied or timeout
        print("Permission denied or timeout - skipping operation")
        # Update issue status to BLOCKED
        echo "BLOCKED: Permission timeout on delete operation" > LogBook/issue-fixing/signals/{LANE}.status
        # Continue with other issues

    # Clean up request/approval files
    pr.cleanup_request()
```

4. **Timeout handling:**
If permission request times out after 5 minutes:
- Write BLOCKED status
- Update issue with `status: "BLOCKED_ON_PERMISSION"`
- Continue with other issues (non-blocking failure)

**Safety Tiers:**

| Tier | Operations | Behavior |
|------|-----------|----------|
| SAFE | Read files, git status/diff/log, write to own LogBook, create issues in own lane | Auto-approve immediately |
| CONDITIONAL | Update OPEN issues in own lane, create files in scope | Auto-approve with validation |
| UNSAFE | Delete files, modify PM-exclusive paths, modify out-of-scope files | Request permission |

'''


def add_permission_handling(file_path: str, lane: str):
    """Add permission handling section to a single lane agent spec"""

    with open(file_path, 'r') as f:
        content = f.read()

    # Check if already has permission handling
    if 'Permission Handling' in content:
        print(f"✓ SKIP: {lane} - already has Permission Handling section")
        return False

    # Find insertion point (after Status Signals, before Find Open Issues)
    # Pattern: look for "### 1. Find Open Issues" or similar
    pattern = r'(### Status Signals.*?)(### \d+\. Find Open Issues)'

    # Replace {LANE} placeholder in template
    section = PERMISSION_HANDLING_SECTION.replace('{LANE}', lane)

    # Insert the section
    def replacer(match):
        return match.group(1) + section + '\n' + match.group(2)

    new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)

    if new_content == content:
        print(f"⚠️  WARN: {lane} - could not find insertion point")
        return False

    # Write updated content
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"✓ UPDATED: {lane} - added Permission Handling section")
    return True


def main():
    """Update all IF-Lane-*.md files"""
    print("Adding Permission Handling to all lane fixers...")
    print("=" * 60)

    # Find all lane fixer specs
    lane_files = glob.glob(".claude/agents/issue-fixers/IF-Lane-*.md")
    lane_files.sort()

    updated = 0
    skipped = 0
    failed = 0

    for file_path in lane_files:
        # Extract lane letter from filename
        basename = os.path.basename(file_path)
        lane = basename.replace("IF-Lane-", "").replace(".md", "")

        result = add_permission_handling(file_path, lane)

        if result is True:
            updated += 1
        elif result is False and 'already has' in str(result):
            skipped += 1
        else:
            failed += 1

    print("=" * 60)
    print(f"Summary:")
    print(f"  Updated: {updated}")
    print(f"  Skipped (already has): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(lane_files)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
