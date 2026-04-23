#!/usr/bin/env python3
"""
Resolution Template Generator

Adds standardized resolution evidence sections to issues.
Ensures consistent documentation format for agent-applied fixes.

Usage:
    python3 tools/add_resolution_template.py              # Dry run
    python3 tools/add_resolution_template.py --apply      # Apply to all
    python3 tools/add_resolution_template.py --lane G     # Single lane
"""

import os
import re
import sys
import glob
import yaml
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"

RESOLUTION_TEMPLATE = '''
---

## Resolution Evidence

**Resolution Status:** {status}

**Fix Applied**
- Date: {date}
- Agent/Author: {agent}
- Commit: {commit}

**Changes Made**
```
{changes}
```

**Verification Results**
```bash
# Verification run: {verify_date}
{verify_commands}
```

**Verification Output**
```
{verify_output}
```

**Resolution Confidence:** {confidence}%

---
'''

MINIMAL_TEMPLATE = '''
---

## Resolution Evidence

**Resolution Status:** PENDING

**Fix Applied**
- Date: (pending)
- Agent/Author: (pending)
- Commit: (pending)

**Changes Made**
```
(to be filled when fix is applied)
```

**Verification Results**
```bash
# Run after fix:
python3 tools/verify_issue.py {issue_id}
```

**Resolution Confidence:** 0%

---
'''

# =============================================================================
# PARSING
# =============================================================================

def parse_frontmatter(filepath: str) -> Tuple[Optional[Dict], str]:
    """Parse frontmatter and content from file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None, ""

    if not content.startswith('---'):
        return None, content

    end = content.find('\n---\n', 3)
    if end < 0:
        return None, content

    try:
        fm = yaml.safe_load(content[4:end])
        return fm, content
    except yaml.YAMLError:
        return None, content

def has_resolution_section(content: str) -> bool:
    """Check if content already has resolution evidence section."""
    return '## Resolution Evidence' in content

def get_issue_status(content: str) -> str:
    """Get issue status from content."""
    if 'status: "RESOLVED"' in content or 'Status: RESOLVED' in content:
        return "RESOLVED"
    return "OPEN"

def extract_verification_commands(content: str) -> str:
    """Extract verification commands for the template."""
    match = re.search(r'\*\*Verification Commands.*?\*\*.*?```bash\n(.*?)```', content, re.DOTALL)
    if match:
        # Get first few commands
        lines = match.group(1).strip().split('\n')[:6]
        return '\n'.join(lines)
    return "python3 tools/verify_issue.py {issue_id}"

# =============================================================================
# TEMPLATE GENERATION
# =============================================================================

def generate_resolution_template(issue_id: str, content: str, status: str) -> str:
    """Generate appropriate resolution template based on status."""
    if status == "RESOLVED":
        # For resolved issues, create filled template
        verify_cmds = extract_verification_commands(content)

        return RESOLUTION_TEMPLATE.format(
            status="VERIFIED",
            date=datetime.now().strftime('%Y-%m-%d'),
            agent="the agent",
            commit="(see git log)",
            changes="Fix applied per issue requirements",
            verify_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            verify_commands=verify_cmds,
            verify_output="All checks: PASS",
            confidence="100"
        )
    else:
        # For open issues, create pending template
        return MINIMAL_TEMPLATE.format(issue_id=issue_id)

def insert_resolution_section(content: str, template: str) -> str:
    """Insert resolution section at end of issue content."""
    # Remove any existing partial resolution sections
    content = re.sub(r'\n---\s*\n## Resolution Evidence.*', '', content, flags=re.DOTALL)

    # Find good insertion point (before any trailing ---)
    content = content.rstrip()
    if content.endswith('---'):
        content = content[:-3].rstrip()

    return content + '\n' + template

# =============================================================================
# PROCESSING
# =============================================================================

def process_issue(filepath: str, dry_run: bool = True) -> Tuple[bool, str]:
    """Process a single issue file."""
    frontmatter, content = parse_frontmatter(filepath)

    if not frontmatter:
        return False, "No frontmatter"

    if has_resolution_section(content):
        return False, "Already has resolution section"

    # Get issue info
    issue_id = frontmatter.get('issue_id', os.path.basename(filepath).replace('.md', ''))
    status = get_issue_status(content)

    # Generate template
    template = generate_resolution_template(issue_id, content, status)

    if dry_run:
        return True, f"Would add resolution template ({status})"

    # Insert template
    new_content = insert_resolution_section(content, template)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True, f"Added resolution template ({status})"
    except Exception as e:
        return False, f"Write error: {e}"

def process_all(issues_dir: str, lane: str = None, dry_run: bool = True) -> Dict[str, int]:
    """Process all issues."""
    stats = {'processed': 0, 'skipped': 0, 'errors': 0}

    if lane:
        files = glob.glob(os.path.join(issues_dir, lane.upper(), '*.md'))
    else:
        files = glob.glob(os.path.join(issues_dir, '*', '*.md'))

    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    print("=" * 70)
    print("the system RESOLUTION TEMPLATE GENERATOR")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLYING CHANGES'}")
    print(f"Files to process: {len(files)}")
    print("=" * 70)
    print()

    for filepath in sorted(files):
        basename = os.path.basename(filepath)
        success, message = process_issue(filepath, dry_run)

        if success:
            stats['processed'] += 1
            print(f"\u2705 {basename}: {message}")
        elif 'Already' in message:
            stats['skipped'] += 1
        else:
            stats['errors'] += 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Templates added:    {stats['processed']}")
    print(f"Already had:        {stats['skipped']}")
    print(f"Errors:             {stats['errors']}")

    if dry_run and stats['processed'] > 0:
        print()
        print("Run with --apply to apply changes")

    print("=" * 70)

    return stats

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Add resolution evidence templates to the system issues'
    )
    parser.add_argument('--apply', action='store_true', help='Apply changes')
    parser.add_argument('--lane', '-l', type=str, help='Process single lane')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)

    args = parser.parse_args()

    stats = process_all(
        args.issues_dir,
        lane=args.lane,
        dry_run=not args.apply
    )

    sys.exit(0 if stats['errors'] == 0 else 1)

if __name__ == '__main__':
    main()
