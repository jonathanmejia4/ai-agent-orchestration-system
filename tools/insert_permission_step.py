#!/usr/bin/env python3
"""
Insert Step 2c½ (Permission Check) into all lane fixer specifications.

This script automates the insertion of permission checking workflow step
between Step 2c (Assess Complexity) and Step 2d (Implement the Fix).
"""

import re
from pathlib import Path

LANE_LETTERS = "BDEGHIJKLMNOPQRSTUVWXYZ"
BASE_DIR = Path(__file__).parent.parent
AGENTS_DIR = BASE_DIR / ".claude/agents/issue-fixers"


def get_step_2c_half_template(lane: str) -> str:
    """Generate Step 2c½ content for a specific lane."""
    return f"""#### 2c½. Check Permission Requirements

**BEFORE implementing the fix, check if operations are safe:**

1. **Identify operations needed:**
   ```python
   # List all operations this fix will require
   operations = []
   if will_create_files:
       operations.append(("create_file", target_path))
   if will_delete_files:
       operations.append(("delete_file", target_path))
   if will_modify_files:
       operations.append(("modify_file", target_path))
   ```

2. **Check with guardrails:**
   ```python
   from tools.permission_guardrails import SafetyGuardrail, Decision

   guardrail = SafetyGuardrail(agent="IF-Lane-{lane}", lane="{lane}")
   unsafe_operations = []

   for operation_type, target in operations:
       result = guardrail.check_operation(
           operation_type=operation_type,
           target_path=target,
           context={{"issue_id": issue_id}}
       )

       if result.decision == Decision.AUTO_APPROVE:
           print(f"✓ SAFE: {{operation_type}} on {{target}} - {{result.reason}}")
       else:
           print(f"⚠ UNSAFE: {{operation_type}} on {{target}} - requires permission")
           unsafe_operations.append((operation_type, target, result))
   ```

3. **Request permission for UNSAFE operations:**
   ```python
   if unsafe_operations:
       from tools.permission_request import PermissionRequest

       pr = PermissionRequest(lane="{lane}", agent="IF-Lane-{lane}")

       for operation_type, target, result in unsafe_operations:
           request_id = pr.request_permission(
               operation_type=operation_type,
               target=target,
               reason=f"Required for fixing {{issue_id}}: {{result.reason}}",
               options=[
                   {{
                       "option_id": "A",
                       "label": f"Allow {{operation_type}}",
                       "description": f"Proceed with {{operation_type}} on {{target}}",
                       "pros": ["Completes the fix", "Resolves the issue"],
                       "cons": [result.risk_summary if hasattr(result, 'risk_summary') else "Modifies protected path"]
                   }},
                   {{
                       "option_id": "B",
                       "label": "Skip this issue",
                       "description": "Mark issue as BLOCKED_ON_PERMISSION",
                       "pros": ["Safe - no changes", "Can review manually"],
                       "cons": ["Issue remains unresolved"]
                   }}
               ],
               recommended="B",  # Default to safe option
               issue_id=issue_id
           )

           # Wait for user decision (10 min timeout)
           approval = pr.wait_for_approval(request_id, timeout_seconds=600)

           if not approval or approval["decision"] != "APPROVED" or approval["chosen_option"] != "A":
               # Permission denied or timeout - mark issue as blocked
               Path("LogBook/issue-fixing/signals/{lane}.status").write_text(
                   f"BLOCKED: Permission denied or timeout for {{operation_type}}\\n"
               )

               # Update issue status to BLOCKED_ON_PERMISSION
               # (Implementation depends on current issue tracking format)

               pr.cleanup_request()
               continue  # Skip to next issue

           pr.cleanup_request()
   ```

4. **Proceed to Step 2d only if:**
   - All operations are SAFE (auto-approved), OR
   - User approved all UNSAFE operations (Option A)

**See "Permission Handling" section above (lines 57-166) for complete reference.**

"""


def update_permission_handling_section(content: str, step_num: str) -> str:
    """Add cross-reference to permission check step in Permission Handling section."""
    # Find the Permission Handling header and add integration note
    pattern = r'(### Permission Handling\n)'
    replacement = (
        r'\1\n**INTEGRATED INTO WORKFLOW:** This section provides reference documentation. '
        f'Permission checks are executed at **Step {step_num}: Check Permission Requirements** '
        'in the workflow below.\n'
    )

    return re.sub(pattern, replacement, content)




def insert_step_2c_half(file_path: Path, lane: str) -> bool:
    """Insert Step 2c½ into a lane fixer spec file."""
    try:
        content = file_path.read_text()

        # Check if Step 2c½ already exists
        if "Check Permission Requirements" in content:
            print(f"  ⏭  Lane {lane}: Step 2c½ already exists, skipping")
            return False

        # Try three different patterns based on lane structure
        patterns = [
            # Pattern 1: Lane B (2c Assess → 2d Implement)
            (r'(#### 2c\. Assess Complexity.*?)(\n#### 2d\. Implement)', "2c½", "2d"),
            # Pattern 2: Most lanes (2b Assess BEFORE Starting → 2c Implement)
            (r'(#### 2b\. Assess Complexity BEFORE Starting.*?)(\n#### 2c\. Implement)', "2b½", "2c"),
            # Pattern 3: Lane D (2b Assess → 2c Implement)
            (r'(#### 2b\. Assess Complexity.*?)(\n#### 2c\. Implement)', "2b½", "2c"),
        ]

        matched = False
        for pattern, new_step_num, next_step_num in patterns:
            if re.search(pattern, content, re.DOTALL):
                # Insert Step with appropriate numbering
                step_content = get_step_2c_half_template(lane).replace(
                    "#### 2c½.", f"#### {new_step_num}."
                )
                new_content = re.sub(
                    pattern,
                    r'\1\n\n' + step_content + r'\2',
                    content,
                    flags=re.DOTALL
                )

                # Update Permission Handling section
                new_content = update_permission_handling_section(new_content, new_step_num)

                # Update next step prerequisites
                prereq_pattern = f'(#### {next_step_num}\\. Implement the Fix\\n)'
                prereq_replacement = (
                    r'\1\n**Prerequisites:** Step ' + new_step_num +
                    ' must pass (all operations cleared by guardrails or user approval).\n'
                )
                new_content = re.sub(prereq_pattern, prereq_replacement, new_content)

                # Write back
                file_path.write_text(new_content)
                print(f"  ✓ Lane {lane}: Step {new_step_num} inserted successfully")
                matched = True
                return True

        if not matched:
            print(f"  ❌ Lane {lane}: Could not find insertion point")
            return False

    except Exception as e:
        print(f"  ❌ Lane {lane}: Error - {e}")
        return False


def main():
    """Main execution."""
    print("Inserting Step 2c½ into all lane fixer specifications...\n")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for lane in LANE_LETTERS:
        file_path = AGENTS_DIR / f"IF-Lane-{lane}.md"

        if not file_path.exists():
            print(f"  ⚠  Lane {lane}: File not found, skipping")
            skip_count += 1
            continue

        result = insert_step_2c_half(file_path, lane)
        if result:
            success_count += 1
        elif result is False:
            skip_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  ✓ Successfully updated: {success_count}")
    print(f"  ⏭  Skipped (already exists): {skip_count}")
    print(f"  ❌ Failed: {fail_count}")
    print(f"{'='*60}\n")

    if success_count > 0:
        print("Step 2c½ has been integrated into lane fixer workflows.")
        print("Next: Run verification commands to confirm all updates.")


if __name__ == "__main__":
    main()
