#!/usr/bin/env python3
"""
Remove Step 2b½/2c½ (proactive permission checks) from all lane fixer specs.
These steps are being replaced with reactive permission handling in the orchestrator prompt.
"""

import re
from pathlib import Path

LANE_LETTERS = "BDEGHIJKLMNOPQRSTUVWXYZ"
AGENTS_DIR = Path(".claude/agents/issue-fixers")

def remove_permission_steps(file_path: Path) -> tuple[bool, str]:
    """
    Remove Step 2b½/2c½ sections from a lane fixer spec.

    Returns:
        (success, message) tuple
    """
    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content

    # Pattern matches the step header through to the next step header
    # We need to be careful to preserve the following steps
    patterns = [
        (r'#### 2c½\. Check Permission Requirements.*?(?=####)', "2c½"),
        (r'#### 2b½\. Check Permission Requirements.*?(?=####)', "2b½"),
    ]

    removed_steps = []
    for pattern, step_name in patterns:
        if re.search(pattern, content, flags=re.DOTALL):
            content = re.sub(pattern, '', content, flags=re.DOTALL)
            removed_steps.append(step_name)

    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)

        if removed_steps:
            return True, f"Removed: {', '.join(removed_steps)}"
        else:
            return True, "No permission steps found"
    else:
        return False, "No changes needed"

def main():
    print("Removing proactive permission check steps from lane fixer specs...")
    print()

    removed_count = 0
    skipped_count = 0

    for lane in LANE_LETTERS:
        file_path = AGENTS_DIR / f"IF-Lane-{lane}.md"

        if not file_path.exists():
            print(f"⚠️  Lane {lane}: File not found - {file_path}")
            skipped_count += 1
            continue

        success, message = remove_permission_steps(file_path)

        if success:
            print(f"✓ Lane {lane}: {message}")
            removed_count += 1
        else:
            print(f"○ Lane {lane}: {message}")
            skipped_count += 1

    print()
    print(f"Summary: {removed_count} modified, {skipped_count} skipped")
    print("Proactive permission steps removed - specs now use reactive pattern from orchestrator.")

if __name__ == "__main__":
    main()
