#!/usr/bin/env python3
"""
template_upgrade_planner.py - Template upgrade planning tool

This is a wrapper for template_upgrade_assistant.py that provides
backwards compatibility for references to the "planner" name.

For template upgrade planning and migration assistance, this tool
analyzes breaking changes, creates Template Upgrade Tasks, and
guides teams through version migrations.

Exit codes:
  0 - Success
  1 - Failure
  2 - Cancelled
  3 - Error

Usage:
  python tools/template_upgrade_planner.py --task 3.1 --from api@1.0.0 --to api@2.0.0
  python tools/template_upgrade_planner.py --task 3.1 --from api@1.0.0 --to api@2.0.0 --dry-run

Note: This tool delegates to template_upgrade_assistant.py for actual functionality.
      The "assistant" provides interactive upgrade guidance and automation.

Referenced in:
  - PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md (upgrade workflows)
  - Template deprecation procedures
  - Breaking change migration guides

Author: System
Created: 2026-01-09 (Lane B remediation - name compatibility wrapper)
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Delegate to template_upgrade_assistant.py with same arguments."""

    # Path to the actual implementation
    assistant_path = Path(__file__).parent / "template_upgrade_assistant.py"

    if not assistant_path.exists():
        print(f"Error: template_upgrade_assistant.py not found at {assistant_path}", file=sys.stderr)
        print("", file=sys.stderr)
        print("The template upgrade planner requires template_upgrade_assistant.py", file=sys.stderr)
        print("to be present in the tools/ directory.", file=sys.stderr)
        return 3

    # Pass all arguments through to the assistant
    cmd = [sys.executable, str(assistant_path)] + sys.argv[1:]

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nUpgrade planning cancelled by user", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error running template_upgrade_assistant.py: {e}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    sys.exit(main())
