#!/usr/bin/env python3
"""
Update references to removed Step 2b½/2c½ in lane fixer specs.
Replace with reactive pattern references.
"""

import re
from pathlib import Path

LANE_LETTERS = "BDEGHIJKLMNOPQRSTUVWXYZ"
AGENTS_DIR = Path(".claude/agents/issue-fixers")

def update_references(file_path: Path) -> tuple[bool, int]:
    """
    Update Step 2b½/2c½ references to reflect reactive pattern.

    Returns:
        (modified, count) tuple
    """
    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content
    changes = 0

    # Update Permission Handling section reference
    old_ref = r'\*\*INTEGRATED INTO WORKFLOW:\*\* This section provides reference documentation\. Permission checks are executed at \*\*Step 2[bc]½: Check Permission Requirements\*\* in the workflow below\.'
    new_ref = "**REACTIVE PATTERN:** Permission checks now happen automatically when operations fail. See orchestrator prompt for reactive permission handling workflow."

    if re.search(old_ref, content):
        content = re.sub(old_ref, new_ref, content)
        changes += 1

    # Update Prerequisites reference
    old_prereq = r'\*\*Prerequisites:\*\* Step 2[bc]½ must pass \(all operations cleared by guardrails or user approval\)\.'
    new_prereq = "**Prerequisites:** None - attempt operations directly. If permission denied, reactive workflow handles it."

    if re.search(old_prereq, content):
        content = re.sub(old_prereq, new_prereq, content)
        changes += 1

    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True, changes
    else:
        return False, 0

def main():
    print("Updating Step 2b½/2c½ references to reflect reactive pattern...")
    print()

    total_changes = 0

    for lane in LANE_LETTERS:
        file_path = AGENTS_DIR / f"IF-Lane-{lane}.md"

        if not file_path.exists():
            print(f"⚠️  Lane {lane}: File not found")
            continue

        modified, count = update_references(file_path)

        if modified:
            print(f"✓ Lane {lane}: Updated {count} references")
            total_changes += count
        else:
            print(f"○ Lane {lane}: No references found")

    print()
    print(f"Summary: {total_changes} references updated across all lanes")
    print("All references now reflect reactive permission pattern.")

if __name__ == "__main__":
    main()
