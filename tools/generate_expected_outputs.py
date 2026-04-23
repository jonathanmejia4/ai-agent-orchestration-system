#!/usr/bin/env python3
"""
the system Expected Outputs Generator

Generates structured expected output templates for verification commands.
Creates machine-comparable output specs that agents can check against.

Usage:
    python3 tools/generate_expected_outputs.py              # Dry run
    python3 tools/generate_expected_outputs.py --apply      # Apply to all
    python3 tools/generate_expected_outputs.py --lane G     # Single lane
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

# Expected outputs by check type
EXPECTED_OUTPUTS = {
    'file_exists': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'file_not_empty': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'dir_exists': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'has_readme': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'git_tracked': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'valid_json': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'valid_yaml': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'valid_syntax': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'executable': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'target_exists': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'has_title': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'not_empty': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'no_stub_markers': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'has_content': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'has_jobs': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
    'exists': {'exit_code': 0, 'stdout': 'PASS', 'stderr': ''},
}

# =============================================================================
# PARSING
# =============================================================================

def parse_frontmatter(filepath: str) -> Tuple[Optional[Dict], str]:
    """Parse frontmatter from file."""
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

def extract_checks_from_content(content: str) -> List[str]:
    """Extract check names from verification commands section."""
    checks = []

    # Find verification commands section
    match = re.search(r'\*\*Verification Commands.*?```bash(.*?)```', content, re.DOTALL)
    if not match:
        return checks

    commands_section = match.group(1)

    # Extract check names from comments like "# Check 1: file_exists"
    for match in re.finditer(r'#\s*Check\s*\d+:\s*(\w+)', commands_section):
        check_name = match.group(1)
        checks.append(check_name)

    return checks

def has_expected_outputs_yaml(content: str) -> bool:
    """Check if content already has YAML expected outputs."""
    return '**Expected Outputs (Machine-Readable)**' in content

# =============================================================================
# GENERATION
# =============================================================================

def generate_expected_outputs_section(checks: List[str], issue_id: str) -> str:
    """Generate structured expected outputs section."""
    if not checks:
        return ""

    lines = [
        "",
        "**Expected Outputs (Machine-Readable)**",
        "",
        "```yaml",
        f"# Expected verification results for {issue_id}",
        f"# Agent: Compare actual output against these values",
        f"issue_id: \"{issue_id}\"",
        f"total_checks: {len(checks)}",
        "expected_results:",
    ]

    for i, check in enumerate(checks, 1):
        expected = EXPECTED_OUTPUTS.get(check, EXPECTED_OUTPUTS['exists'])
        lines.append(f"  check_{i}:")
        lines.append(f"    name: \"{check}\"")
        lines.append(f"    exit_code: {expected['exit_code']}")
        lines.append(f"    stdout_contains: \"{expected['stdout']}\"")
        if expected.get('stderr'):
            lines.append(f"    stderr: \"{expected['stderr']}\"")

    lines.extend([
        "",
        "# Verification passes when:",
        f"pass_criteria: \"all {len(checks)} checks return exit_code=0 and stdout contains 'PASS'\"",
        "```",
        "",
        "**Quick Verification**",
        "```bash",
        f"# Run all checks and count passes",
        f"python3 tools/verify_issue.py {issue_id} | grep -c 'PASS'",
        f"# Expected output: {len(checks)}",
        "```",
        "",
    ])

    return '\n'.join(lines)

def insert_expected_outputs(content: str, outputs_section: str) -> str:
    """Insert expected outputs section after verification commands."""
    # Find end of existing Expected Output section (non-YAML version)
    match = re.search(r'(\*\*Expected Output\*\*\n```.*?```\n)', content, re.DOTALL)
    if match:
        # Insert after the existing expected output
        insert_pos = match.end()
        return content[:insert_pos] + outputs_section + content[insert_pos:]

    # Find verification commands section end
    match = re.search(r'(\*\*Verification Commands.*?```\n)', content, re.DOTALL)
    if match:
        insert_pos = match.end()
        return content[:insert_pos] + outputs_section + content[insert_pos:]

    # Fallback: append before Cross-References
    match = re.search(r'(\n\*\*Cross-References)', content)
    if match:
        return content[:match.start()] + outputs_section + content[match.start():]

    return content

# =============================================================================
# PROCESSING
# =============================================================================

def process_issue(filepath: str, dry_run: bool = True) -> Tuple[bool, str]:
    """Process a single issue file."""
    frontmatter, content = parse_frontmatter(filepath)

    if frontmatter is None:
        return False, "No frontmatter"

    # Check if already has YAML expected outputs
    if has_expected_outputs_yaml(content):
        return False, "Already has expected outputs"

    # Extract checks from content
    checks = extract_checks_from_content(content)

    if not checks:
        return False, "No verification commands found"

    # Generate outputs section
    issue_id = frontmatter.get('issue_id', os.path.basename(filepath).replace('.md', ''))
    outputs_section = generate_expected_outputs_section(checks, issue_id)

    # Insert into content
    new_content = insert_expected_outputs(content, outputs_section)

    if dry_run:
        return True, f"Would add expected outputs for {len(checks)} checks"

    # Write back
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True, f"Added expected outputs for {len(checks)} checks"
    except Exception as e:
        return False, f"Write error: {e}"

def process_all(issues_dir: str, lane: str = None, dry_run: bool = True) -> Dict[str, int]:
    """Process all issues."""
    stats = {'processed': 0, 'skipped': 0, 'no_commands': 0, 'errors': 0}

    if lane:
        files = glob.glob(os.path.join(issues_dir, lane.upper(), '*.md'))
    else:
        files = glob.glob(os.path.join(issues_dir, '*', '*.md'))

    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    print("=" * 70)
    print("the system EXPECTED OUTPUTS GENERATOR")
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
        elif 'No verification' in message:
            stats['no_commands'] += 1
        elif 'Already has' in message:
            stats['skipped'] += 1
        else:
            stats['errors'] += 1
            print(f"\u274c {basename}: {message}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Processed:    {stats['processed']}")
    print(f"Skipped:      {stats['skipped']}")
    print(f"No commands:  {stats['no_commands']}")
    print(f"Errors:       {stats['errors']}")

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
        description='Generate expected outputs for the system issue verification'
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
