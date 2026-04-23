#!/usr/bin/env python3
"""
Regenerate embedded verification commands in issue files.

This script reads the corrected pattern_vars from YAML frontmatter
and regenerates the embedded verification command sections.

Fixes the issue where frontmatter was corrected but embedded commands
still contain old malformed values (grep commands, glob patterns, etc.)

Usage:
    python3 tools/regenerate_verification_commands.py --dry-run  # Preview
    python3 tools/regenerate_verification_commands.py             # Apply
    python3 tools/regenerate_verification_commands.py --issue I-01  # Single issue
"""

import os
import re
import sys
import yaml
import argparse
from typing import Dict, Any, Optional, Tuple, List

# =============================================================================
# VERIFICATION COMMAND TEMPLATES
# =============================================================================

# Templates for different verification patterns
PATTERN_TEMPLATES = {
    'missing_file': '''```bash
# Verification for {issue_id}
# Pattern: missing_file
# Target: {file_path}

# Check 1: file_exists
test -f {file_path} && echo "PASS" || echo "FAIL"

# Check 2: file_not_empty
test -s {file_path} && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files --error-unmatch {file_path} 2>/dev/null && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'missing_directory': '''```bash
# Verification for {issue_id}
# Pattern: missing_directory
# Target: {directory_path}

# Check 1: dir_exists
test -d {directory_path} && echo "PASS" || echo "FAIL"

# Check 2: has_contents
ls {directory_path}/ | head -5 && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files {directory_path}/ | head -1 && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'json_schema': '''```bash
# Verification for {issue_id}
# Pattern: json_schema
# Target: {file_path}

# Check 1: file_exists
test -f {file_path} && echo "PASS" || echo "FAIL"

# Check 2: valid_json
python3 -m json.tool {file_path} > /dev/null && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files --error-unmatch {file_path} 2>/dev/null && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'yaml_schema': '''```bash
# Verification for {issue_id}
# Pattern: yaml_schema
# Target: {file_path}

# Check 1: file_exists
test -f {file_path} && echo "PASS" || echo "FAIL"

# Check 2: valid_yaml
python3 -c "import yaml; yaml.safe_load(open('{file_path}'))" && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files --error-unmatch {file_path} 2>/dev/null && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'python_script': '''```bash
# Verification for {issue_id}
# Pattern: python_script
# Target: {file_path}

# Check 1: file_exists
test -f {file_path} && echo "PASS" || echo "FAIL"

# Check 2: valid_syntax
python3 -m py_compile {file_path} && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files --error-unmatch {file_path} 2>/dev/null && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'ghost_reference': '''```bash
# Verification for {issue_id}
# Pattern: ghost_reference
# Target: {source_file}

# Check 1: target_exists
test -e {source_file} && echo "PASS" || echo "FAIL"

# Check 2: file_not_empty
test -s {source_file} && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files --error-unmatch {source_file} 2>/dev/null && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'policy_alignment': '''```bash
# Verification for {issue_id}
# Pattern: policy_alignment
# Target: {source_file}

# Check 1: file_exists
test -f {source_file} && echo "PASS" || echo "FAIL"

# Check 2: file_has_content
test -s {source_file} && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files --error-unmatch {source_file} 2>/dev/null && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'workflow_file': '''```bash
# Verification for {issue_id}
# Pattern: workflow_file
# Target: {file_path}

# Check 1: file_exists
test -f {file_path} && echo "PASS" || echo "FAIL"

# Check 2: valid_yaml
python3 -c "import yaml; yaml.safe_load(open('{file_path}'))" && echo "PASS" || echo "FAIL"

# Check 3: has_jobs
grep -q "jobs:" {file_path} && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',

    'stub_implementation': '''```bash
# Verification for {issue_id}
# Pattern: stub_implementation
# Target: {file_path}

# Check 1: file_exists
test -f {file_path} && echo "PASS" || echo "FAIL"

# Check 2: no_stub_markers
! grep -qiE "(TODO|FIXME|STUB|NOT.?IMPLEMENTED)" {file_path} && echo "PASS" || echo "FAIL"

# Check 3: git_tracked
git ls-files --error-unmatch {file_path} 2>/dev/null && echo "PASS" || echo "FAIL"

# Full automated verification
python3 tools/verify_issue.py {issue_id}
```''',
}

EXPECTED_OUTPUT_TEMPLATE = '''**Expected Output**
```
file_exists: PASS
file_not_empty: PASS
git_tracked: PASS
Result: ALL 3 CHECKS PASSED
```

**Expected Outputs (Machine-Readable)**

```yaml
# Expected verification results for {issue_id}
# Agent: Compare actual output against these values
issue_id: "{issue_id}"
total_checks: 3
expected_results:
  check_1:
    name: "file_exists"
    exit_code: 0
    stdout_contains: "PASS"
  check_2:
    name: "file_not_empty"
    exit_code: 0
    stdout_contains: "PASS"
  check_3:
    name: "git_tracked"
    exit_code: 0
    stdout_contains: "PASS"

# Verification passes when:
pass_criteria: "all 3 checks return exit_code=0 and stdout contains 'PASS'"
```

**Quick Verification**
```bash
# Run all checks and count passes
python3 tools/verify_issue.py {issue_id} | grep -c 'PASS'
# Expected output: 3
```'''

# =============================================================================
# PARSING
# =============================================================================

def parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
    """Parse YAML frontmatter from issue content."""
    if not content.startswith('---'):
        return None

    end = content.find('\n---\n', 3)
    if end < 0:
        # Try with just \n---
        end = content.find('\n---', 3)
        if end < 0:
            return None

    try:
        return yaml.safe_load(content[4:end])
    except yaml.YAMLError:
        return None

def get_file_path_from_vars(pattern_vars: Dict[str, Any]) -> Optional[str]:
    """Extract the primary file path from pattern_vars."""
    # Priority order for path extraction
    keys = ['file_path', 'source_file', 'script_path', 'directory_path', 'dir_path']

    for key in keys:
        if key in pattern_vars:
            value = pattern_vars[key]
            if value and isinstance(value, str):
                # Skip if it's a command (shouldn't happen after fix_pattern_vars.py)
                if not value.startswith('grep') and not value.startswith('find'):
                    return value

    return None

def build_variables(frontmatter: Dict[str, Any]) -> Dict[str, str]:
    """Build template variables from frontmatter."""
    issue_id = frontmatter.get('issue_id', 'UNKNOWN')
    pattern_vars = frontmatter.get('pattern_vars', {}) or {}

    variables = {
        'issue_id': issue_id,
        'lane': frontmatter.get('lane', issue_id[0] if issue_id else ''),
    }

    # Add all pattern_vars
    for key, value in pattern_vars.items():
        if value and isinstance(value, str):
            variables[key] = value

    # Handle directory_path + file_pattern combination
    if 'directory_path' in variables and 'file_pattern' in variables:
        # Create a combined path for display purposes
        variables['file_path'] = f"{variables['directory_path']}/{variables['file_pattern']}"

    # Fallback: extract from affected_paths if no file_path
    if 'file_path' not in variables and 'source_file' not in variables:
        affected = frontmatter.get('affected_paths', [])
        if affected and len(affected) > 0:
            path = affected[0]
            # Clean it
            path = re.sub(r':\d+.*$', '', path).strip('`')
            if '/' in path:
                variables['file_path'] = path

    return variables

def generate_verification_section(frontmatter: Dict[str, Any]) -> Optional[str]:
    """Generate the verification commands section from frontmatter."""
    pattern = frontmatter.get('verification_pattern', 'missing_file')
    variables = build_variables(frontmatter)

    # Get template
    template = PATTERN_TEMPLATES.get(pattern)
    if not template:
        # Fallback to missing_file template
        template = PATTERN_TEMPLATES['missing_file']

    # Map alternative variable names
    if 'file_path' not in variables:
        if 'source_file' in variables:
            variables['file_path'] = variables['source_file']
        elif 'script_path' in variables:
            variables['file_path'] = variables['script_path']

    # Check we have required variables
    if 'file_path' not in variables and 'source_file' not in variables and 'directory_path' not in variables:
        return None

    # Substitute variables in template
    try:
        commands_section = template.format(**variables)
    except KeyError as e:
        # Missing variable - use placeholder
        missing_var = str(e).strip("'")
        variables[missing_var] = f"<{missing_var}>"
        commands_section = template.format(**variables)

    # Generate expected output section
    expected_section = EXPECTED_OUTPUT_TEMPLATE.format(**variables)

    return f"**Verification Commands (Copy-Paste Ready)**\n\n{commands_section}\n\n{expected_section}"

# =============================================================================
# FILE PROCESSING
# =============================================================================

def process_issue_file(filepath: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Process a single issue file and regenerate verification commands.

    Returns:
        (changed, message) tuple
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Error reading file: {e}"

    # Parse frontmatter
    frontmatter = parse_frontmatter(content)
    if not frontmatter:
        return False, "No frontmatter found"

    # Generate new verification section
    new_section = generate_verification_section(frontmatter)
    if not new_section:
        return False, "Cannot generate verification (missing variables)"

    # Find and replace the verification commands section
    # Pattern: **Verification Commands ... **Quick Verification** ... # Expected output: N
    pattern = r'\*\*Verification Commands.*?# Expected output: \d+\n```'

    match = re.search(pattern, content, re.DOTALL)
    if not match:
        # Try alternate pattern without Quick Verification
        pattern = r'\*\*Verification Commands.*?```yaml\n.*?```'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return False, "Cannot find verification section to replace"

    old_section = match.group(0)

    # Check if sections are the same (no changes needed)
    if old_section.strip() == new_section.strip():
        return False, "No changes needed"

    # Replace
    new_content = content[:match.start()] + new_section + content[match.end():]

    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return True, "Verification commands regenerated"

def process_all_issues(issues_dir: str = 'issues', dry_run: bool = False) -> Dict[str, int]:
    """Process all issue files."""
    stats = {
        'total': 0,
        'changed': 0,
        'skipped': 0,
        'errors': 0,
    }

    changes = []

    for lane in sorted(os.listdir(issues_dir)):
        lane_dir = os.path.join(issues_dir, lane)
        if not os.path.isdir(lane_dir):
            continue

        for filename in sorted(os.listdir(lane_dir)):
            if not filename.endswith('.md'):
                continue
            if 'TEMPLATE' in filename.upper():
                continue

            filepath = os.path.join(lane_dir, filename)
            stats['total'] += 1

            changed, message = process_issue_file(filepath, dry_run)

            if 'Error' in message:
                stats['errors'] += 1
            elif changed:
                stats['changed'] += 1
                changes.append((filepath, message))
            else:
                stats['skipped'] += 1

    return stats, changes

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Regenerate embedded verification commands in issue files'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without applying')
    parser.add_argument('--issue', '-i', type=str,
                        help='Process single issue (e.g., I-01)')
    parser.add_argument('--lane', '-l', type=str,
                        help='Process all issues in lane')
    parser.add_argument('--issues-dir', default='issues',
                        help='Issues directory path')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show details of changes')

    args = parser.parse_args()

    print(f"{'DRY RUN - ' if args.dry_run else ''}Regenerating verification commands")
    print('=' * 60)

    if args.issue:
        # Single issue
        lane = args.issue[0].upper()
        filepath = os.path.join(args.issues_dir, lane, f"{args.issue}.md")

        if not os.path.exists(filepath):
            # Try with hyphen format
            filepath = os.path.join(args.issues_dir, lane, f"{lane}-{args.issue[1:].lstrip('-')}.md")

        if not os.path.exists(filepath):
            print(f"Issue file not found: {args.issue}")
            sys.exit(1)

        changed, message = process_issue_file(filepath, args.dry_run)
        print(f"{args.issue}: {message}")

        if changed and args.verbose:
            # Show preview
            with open(filepath, 'r') as f:
                content = f.read()
            frontmatter = parse_frontmatter(content)
            new_section = generate_verification_section(frontmatter)
            print("\nGenerated verification section:")
            print(new_section[:500] + "..." if len(new_section) > 500 else new_section)

        sys.exit(0 if changed else 1)

    elif args.lane:
        # Single lane
        lane_dir = os.path.join(args.issues_dir, args.lane.upper())
        if not os.path.isdir(lane_dir):
            print(f"Lane directory not found: {args.lane}")
            sys.exit(1)

        changed_count = 0
        for filename in sorted(os.listdir(lane_dir)):
            if not filename.endswith('.md') or 'TEMPLATE' in filename.upper():
                continue

            filepath = os.path.join(lane_dir, filename)
            changed, message = process_issue_file(filepath, args.dry_run)

            if changed:
                changed_count += 1
                print(f"  {filename}: {message}")

        print(f"\nLane {args.lane.upper()}: {changed_count} files {'would be ' if args.dry_run else ''}changed")
        sys.exit(0)

    else:
        # All issues
        stats, changes = process_all_issues(args.issues_dir, args.dry_run)

        print(f"\nSummary:")
        print(f"  Total files:  {stats['total']}")
        print(f"  Changed:      {stats['changed']}")
        print(f"  Skipped:      {stats['skipped']}")
        print(f"  Errors:       {stats['errors']}")

        if args.verbose and changes:
            print(f"\nChanged files:")
            for filepath, message in changes[:20]:
                print(f"  {filepath}")
            if len(changes) > 20:
                print(f"  ... and {len(changes) - 20} more")

        print('=' * 60)

        if args.dry_run:
            print("\nRun without --dry-run to apply changes")

        sys.exit(0)

if __name__ == '__main__':
    main()
