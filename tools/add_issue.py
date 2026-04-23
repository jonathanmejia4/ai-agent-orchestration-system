#!/usr/bin/env python3
"""
Add Issue Tool

Creates a new issue file with proper formatting and numbering.

Usage:
    python3 tools/add_issue.py A "Issue title" --severity 7 --tags "Tag1,Tag2"
    python3 tools/add_issue.py B "Missing config file" --severity 5 --path config.yaml

Arguments:
    lane        Lane letter (A-Z)
    title       Issue title
    --severity  Severity level 1-10 (default: 5)
    --tags      Comma-separated type tags
    --path      Affected file path (repeatable). Populates affected_paths frontmatter
                so verify_issue.py can substitute {file_path} in verification commands.
"""

import os
import re
import sys
import argparse
from datetime import datetime

ISSUES_DIR = "issues"


def get_next_issue_number(lane: str) -> int:
    """Get the next available issue number for a lane."""
    lane_dir = os.path.join(ISSUES_DIR, lane.upper())

    if not os.path.isdir(lane_dir):
        os.makedirs(lane_dir, exist_ok=True)
        return 1

    existing = []
    for f in os.listdir(lane_dir):
        match = re.match(rf'{lane.upper()}-(\d+)\.md', f)
        if match:
            existing.append(int(match.group(1)))

    return max(existing) + 1 if existing else 1


def severity_to_level(severity: int) -> str:
    """Convert numeric severity to level string."""
    if severity >= 9:
        return "CRITICAL"
    elif severity >= 7:
        return "HIGH"
    elif severity >= 4:
        return "MEDIUM"
    elif severity >= 2:
        return "LOW"
    else:
        return "TRIVIAL"


def create_issue(lane: str, title: str, severity: int = 5, tags: list = None,
                 affected_paths: list = None) -> str:
    """Create a new issue file."""
    lane = lane.upper()
    issue_num = get_next_issue_number(lane)
    issue_id = f"{lane}-{issue_num:02d}"

    severity_level = severity_to_level(severity)
    tags = tags or [f"{lane}-Issue"]
    tags_str = ', '.join(f'"{t}"' for t in tags)

    affected_paths = affected_paths or []
    if affected_paths:
        paths_yaml = "\n" + "\n".join(f'  - "{p}"' for p in affected_paths)
        affected_paths_line = f"affected_paths:{paths_yaml}"
    else:
        affected_paths_line = "affected_paths: []"

    content = f'''---
issue_id: "{issue_id}"
lane: "{lane}"
severity: {severity}
severity_level: "{severity_level}"
type_tags: [{tags_str}]
status: "OPEN"
{affected_paths_line}
---

# [LANE {lane}] Issue {issue_id}: {title}

- Type Tags: {', '.join(tags)}
- Severity: {severity}/10 ({severity_level})
- Status: OPEN
- Date Discovered: {datetime.now().strftime("%Y-%m-%d")}

---

## Problem Description

- **What is wrong:** [Describe the issue]
- **Expected:** [What should be there]
- **Actual:** [What's actually there]
- **Scope:** [Affected components]

## Evidence

```bash
# Command that demonstrates the issue
$ [command here]
[output here]
```

- **Source:** `file/path:line_number`
  > "relevant code snippet"

## Fix Requirements (DO NOT IMPLEMENT)

- [ ] Required change 1
- [ ] Required change 2

## Verification Commands

```bash
# Check 1: Verify the fix
test -f path/to/file && echo "PASS" || echo "FAIL"
```

## Dedup Verification

- **Search terms:** "{title.lower()}"
- **Files checked:** issues/{lane}/, ISSUE_CATALOG.md
- **Result:** No duplicates found
'''

    # Write the file
    lane_dir = os.path.join(ISSUES_DIR, lane)
    os.makedirs(lane_dir, exist_ok=True)

    filepath = os.path.join(lane_dir, f"{issue_id}.md")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return filepath


def main():
    parser = argparse.ArgumentParser(description='Create a new issue file')
    parser.add_argument('lane', type=str, help='Lane letter (A-Z)')
    parser.add_argument('title', type=str, help='Issue title')
    parser.add_argument('--severity', '-s', type=int, default=5, help='Severity 1-10')
    parser.add_argument('--tags', '-t', type=str, help='Comma-separated tags')
    parser.add_argument('--path', '-p', action='append', default=[],
                        help='Affected file path (repeatable). Populates affected_paths '
                             'frontmatter so verify_issue.py can substitute {file_path}.')

    args = parser.parse_args()

    if not re.match(r'^[A-Za-z]$', args.lane):
        print(f"Error: Lane must be a single letter (A-Z)")
        sys.exit(1)

    if args.severity < 1 or args.severity > 10:
        print(f"Error: Severity must be between 1 and 10")
        sys.exit(1)

    tags = args.tags.split(',') if args.tags else None
    affected_paths = args.path if args.path else []

    if not affected_paths:
        print("Warning: no --path provided; affected_paths will be empty. "
              "verify_issue.py will not be able to substitute {file_path} in verification "
              "commands and will emit a manual-verification note.")

    filepath = create_issue(args.lane, args.title, args.severity, tags, affected_paths)
    print(f"Created: {filepath}")


if __name__ == '__main__':
    main()
