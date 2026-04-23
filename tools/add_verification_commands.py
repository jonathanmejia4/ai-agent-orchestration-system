#!/usr/bin/env python3
"""
Verification Commands Generator

Adds copy-paste ready bash verification commands to all issue files.
Reads frontmatter and content to generate appropriate checks.

Usage:
    python3 tools/add_verification_commands.py              # Dry run
    python3 tools/add_verification_commands.py --apply      # Apply to all
    python3 tools/add_verification_commands.py --lane G     # Single lane
    python3 tools/add_verification_commands.py --file G-01  # Single file
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
# PATH VALIDATION (T-11 Fix)
# =============================================================================

# Shell metacharacters that indicate a command, not a path
SHELL_METACHARACTERS = frozenset(['|', '>', '<', ';', '&', '$', '`', '(', ')'])

# Common shell commands that are often captured incorrectly
SHELL_COMMAND_PREFIXES = frozenset([
    'ls', 'cat', 'grep', 'find', 'echo', 'test', 'rm', 'mv', 'cp', 'mkdir',
    'python', 'python3', 'bash', 'sh', 'chmod', 'chown', 'cd', 'pwd',
])

# Template variable patterns that should never be in final paths
TEMPLATE_PATTERNS = ['<', '>', '{', '}']

def is_valid_path(path: str) -> bool:
    """
    Validate that a string is a valid filesystem path, not a shell command.

    Returns False if:
    - Contains shell metacharacters (|, >, <, ;, &, etc.)
    - Starts with a shell command (ls, cat, grep, etc.)
    - Contains unsubstituted template variables (<task-id>, {path}, etc.)
    - Is too short to be meaningful
    """
    if not path or len(path) < 3:
        return False

    # Check for shell metacharacters
    for char in SHELL_METACHARACTERS:
        if char in path:
            return False

    # Check for template variables
    for pattern in TEMPLATE_PATTERNS:
        if pattern in path:
            return False

    # Check if starts with shell command
    first_word = path.split()[0] if ' ' in path else path.split('/')[0]
    if first_word.lower() in SHELL_COMMAND_PREFIXES:
        return False

    # Check for spaces (valid paths shouldn't have unquoted spaces in shell context)
    if ' ' in path:
        return False

    return True

def is_directory_path(path: str) -> bool:
    """Check if path appears to be a directory (ends with / or no extension)."""
    if path.endswith('/'):
        return True
    # No extension and doesn't look like a file
    basename = os.path.basename(path.rstrip('/'))
    return '.' not in basename

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"

# Command templates by verification pattern
COMMAND_TEMPLATES = {
    'missing_file': [
        ('file_exists', 'test -f {path} && echo "PASS" || echo "FAIL"'),
        ('file_not_empty', 'test -s {path} && echo "PASS" || echo "FAIL"'),
        ('git_tracked', 'git ls-files --error-unmatch {path} 2>/dev/null && echo "PASS" || echo "FAIL"'),
    ],
    'missing_directory': [
        ('dir_exists', 'test -d {path} && echo "PASS" || echo "FAIL"'),
        ('has_readme', 'test -f {path}/README.md && echo "PASS" || echo "FAIL"'),
        ('git_tracked', 'git ls-files {path}/ 2>/dev/null | head -1 | grep -q . && echo "PASS" || echo "FAIL"'),
    ],
    'json_schema': [
        ('file_exists', 'test -f {path} && echo "PASS" || echo "FAIL"'),
        ('valid_json', 'python3 -m json.tool {path} >/dev/null 2>&1 && echo "PASS" || echo "FAIL"'),
        ('git_tracked', 'git ls-files --error-unmatch {path} 2>/dev/null && echo "PASS" || echo "FAIL"'),
    ],
    'yaml_schema': [
        ('file_exists', 'test -f {path} && echo "PASS" || echo "FAIL"'),
        ('valid_yaml', 'python3 -c "import yaml; yaml.safe_load(open(\'{path}\'))" 2>/dev/null && echo "PASS" || echo "FAIL"'),
        ('git_tracked', 'git ls-files --error-unmatch {path} 2>/dev/null && echo "PASS" || echo "FAIL"'),
    ],
    'python_script': [
        ('file_exists', 'test -f {path} && echo "PASS" || echo "FAIL"'),
        ('valid_syntax', 'python3 -m py_compile {path} 2>/dev/null && echo "PASS" || echo "FAIL"'),
        ('executable', 'head -1 {path} | grep -q python && echo "PASS" || echo "FAIL"'),
        ('git_tracked', 'git ls-files --error-unmatch {path} 2>/dev/null && echo "PASS" || echo "FAIL"'),
    ],
    'ghost_reference': [
        ('target_exists', 'test -e {path} && echo "PASS" || echo "FAIL"'),
        ('git_tracked', 'git ls-files --error-unmatch {path} 2>/dev/null && echo "PASS" || echo "FAIL"'),
    ],
    'markdown_doc': [
        ('file_exists', 'test -f {path} && echo "PASS" || echo "FAIL"'),
        ('has_title', 'head -5 {path} | grep -q "^#" && echo "PASS" || echo "FAIL"'),
        ('not_empty', 'test $(wc -l < {path}) -gt 5 && echo "PASS" || echo "FAIL"'),
    ],
    'stub_implementation': [
        ('file_exists', 'test -f {path} && echo "PASS" || echo "FAIL"'),
        ('no_stub_markers', '! grep -qiE "(TODO|FIXME|STUB|NOT.?IMPLEMENTED)" {path} && echo "PASS" || echo "FAIL"'),
        ('has_content', 'test $(wc -l < {path}) -gt 20 && echo "PASS" || echo "FAIL"'),
    ],
    'workflow_file': [
        ('file_exists', 'test -f {path} && echo "PASS" || echo "FAIL"'),
        ('valid_yaml', 'python3 -c "import yaml; yaml.safe_load(open(\'{path}\'))" 2>/dev/null && echo "PASS" || echo "FAIL"'),
        ('has_jobs', 'grep -q "jobs:" {path} && echo "PASS" || echo "FAIL"'),
    ],
}

# Default template for unknown patterns
DEFAULT_TEMPLATE = [
    ('exists', 'test -e {path} && echo "PASS" || echo "FAIL"'),
    ('git_tracked', 'git ls-files --error-unmatch {path} 2>/dev/null && echo "PASS" || echo "FAIL"'),
]

# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def parse_frontmatter(filepath: str) -> Tuple[Optional[Dict], str, str]:
    """Parse frontmatter and return (frontmatter, rest_of_content, full_content)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, "", ""

    if not content.startswith('---'):
        return None, content, content

    end = content.find('\n---\n', 3)
    if end < 0:
        return None, content, content

    try:
        fm = yaml.safe_load(content[4:end])
        rest = content[end + 5:]
        return fm, rest, content
    except yaml.YAMLError:
        return None, content, content

def extract_paths_from_content(content: str) -> List[str]:
    """Extract file paths from issue content.

    T-11 Fix: Validates paths to reject shell commands and template variables.
    """
    paths = []

    # Pattern 1: Backtick paths with extensions
    for match in re.finditer(r'`([^`]+\.(py|yaml|yml|json|md|sh|rst|txt))`', content):
        path = match.group(1)
        # Clean line numbers
        path = re.sub(r':\d+.*$', '', path)
        if '/' in path and len(path) > 3 and is_valid_path(path):
            paths.append(path)

    # Pattern 2: Referenced path field
    for match in re.finditer(r'Referenced\s+path:\s*`?([^\s`\n]+)`?', content):
        path = match.group(1).strip('`')
        path = re.sub(r':\d+.*$', '', path)
        if path and '/' in path and is_valid_path(path):
            paths.append(path)

    # Pattern 3: Directory paths ending with /
    for match in re.finditer(r'`([^`]+/)`', content):
        path = match.group(1).rstrip('/')
        if len(path) > 3 and is_valid_path(path):
            paths.append(path)

    # Pattern 4: Fix Objective paths
    for match in re.finditer(r'Create\s+(?:directory|file)?:?\s*`?([^\s`\n,]+(?:/[^\s`\n,]+)+)`?', content):
        path = match.group(1).strip('`')
        if len(path) > 3 and is_valid_path(path):
            paths.append(path)

    # Dedupe while preserving order, with validation
    seen = set()
    unique = []
    for p in paths:
        p_clean = p.strip().lstrip('/')
        if p_clean not in seen and len(p_clean) > 3 and is_valid_path(p_clean):
            seen.add(p_clean)
            unique.append(p_clean)

    return unique[:5]

def determine_pattern(frontmatter: Dict, content: str, paths: List[str]) -> str:
    """Determine the best verification pattern."""
    # Try frontmatter first
    if frontmatter and 'verification_pattern' in frontmatter:
        pattern = frontmatter['verification_pattern']
        if pattern in COMMAND_TEMPLATES:
            return pattern

    # Infer from type tags
    type_tags = frontmatter.get('type_tags', []) if frontmatter else []

    if 'MissingDir' in type_tags:
        return 'missing_directory'
    if 'MissingSchema' in type_tags:
        # Check if JSON or YAML
        if paths and any(p.endswith('.json') for p in paths):
            return 'json_schema'
        return 'yaml_schema'
    if 'Stub' in type_tags:
        return 'stub_implementation'
    if 'GhostRef' in type_tags:
        return 'ghost_reference'
    if 'WorkflowGap' in type_tags:
        return 'workflow_file'
    if 'DocDrift' in type_tags:
        return 'markdown_doc'

    # Infer from paths
    if paths:
        first_path = paths[0]
        if first_path.endswith('/') or 'directory' in content.lower():
            return 'missing_directory'
        if first_path.endswith('.json'):
            return 'json_schema'
        if first_path.endswith(('.yaml', '.yml')):
            return 'yaml_schema'
        if first_path.endswith('.py'):
            return 'python_script'
        if first_path.endswith('.md'):
            return 'markdown_doc'

    return 'missing_file'

# =============================================================================
# COMMAND GENERATION
# =============================================================================

def generate_commands(pattern: str, paths: List[str], issue_id: str) -> str:
    """Generate verification commands section.

    T-11 Fix: Uses correct test operators (-d for directories, -f for files).
    """
    if not paths:
        # No paths - generate placeholder
        return f"""
**Verification Commands (Copy-Paste Ready)**

```bash
# No specific paths found - manual verification required
# Issue: {issue_id}
echo "Manual verification needed for {issue_id}"
```

**Expected Output**
```
All checks should output: PASS
```
"""

    templates = COMMAND_TEMPLATES.get(pattern, DEFAULT_TEMPLATE)
    primary_path = paths[0]

    # T-11 Fix: If path is a directory but using file pattern, switch to directory pattern
    if is_directory_path(primary_path) and pattern == 'missing_file':
        pattern = 'missing_directory'
        templates = COMMAND_TEMPLATES.get('missing_directory', DEFAULT_TEMPLATE)

    lines = [
        "",
        "**Verification Commands (Copy-Paste Ready)**",
        "",
        "```bash",
        f"# Verification for {issue_id}",
        f"# Pattern: {pattern}",
        f"# Target: {primary_path}",
        "",
    ]

    check_num = 1
    for name, template in templates:
        cmd = template.format(path=primary_path)
        lines.append(f"# Check {check_num}: {name}")
        lines.append(cmd)
        lines.append("")
        check_num += 1

    # Add full verification command
    lines.append(f"# Full automated verification")
    lines.append(f"python3 tools/verify_issue.py {issue_id}")
    lines.append("```")
    lines.append("")

    # Add expected output
    lines.append("**Expected Output**")
    lines.append("```")
    for name, _ in templates:
        lines.append(f"{name}: PASS")
    lines.append(f"Result: ALL {len(templates)} CHECKS PASSED")
    lines.append("```")
    lines.append("")

    return '\n'.join(lines)

def has_verification_section(content: str) -> bool:
    """Check if content already has verification commands section."""
    return '**Verification Commands' in content or '## Verification Commands' in content

def insert_verification_section(content: str, commands: str) -> str:
    """Insert verification commands section into content."""
    # Find a good insertion point - after "Detailed Fix Requirements" or before "Cross-References"

    # Try after Acceptance Criteria
    match = re.search(r'(\*\*Detailed Fix Requirements.*?)(\n\*\*Cross-References|\n\*\*Dedup|\n---\n## |\Z)',
                      content, re.DOTALL)
    if match:
        insert_pos = match.end(1)
        return content[:insert_pos] + "\n" + commands + content[insert_pos:]

    # Try before Cross-References
    match = re.search(r'(\n)(\*\*Cross-References)', content)
    if match:
        return content[:match.start(1)] + "\n" + commands + content[match.start(1):]

    # Try before Dedup
    match = re.search(r'(\n)(\*\*Dedup)', content)
    if match:
        return content[:match.start(1)] + "\n" + commands + content[match.start(1):]

    # Append before final ---
    if content.rstrip().endswith('---'):
        return content.rstrip()[:-3] + "\n" + commands + "\n---\n"

    # Just append
    return content + "\n" + commands

# =============================================================================
# PROCESSING
# =============================================================================

def process_issue(filepath: str, dry_run: bool = True) -> Tuple[bool, str]:
    """Process a single issue file."""
    frontmatter, rest, full_content = parse_frontmatter(filepath)

    if frontmatter is None:
        return False, "No frontmatter"

    # Check if already has verification section
    if has_verification_section(rest):
        return False, "Already has verification section"

    # Extract paths - T-11 Fix: Validate paths from frontmatter
    raw_paths = frontmatter.get('affected_paths', [])
    paths = [p for p in raw_paths if is_valid_path(p)]

    # If frontmatter paths are invalid, extract from content
    if not paths:
        paths = extract_paths_from_content(rest)

    # Determine pattern
    pattern = determine_pattern(frontmatter, rest, paths)

    # Generate commands
    issue_id = frontmatter.get('issue_id', os.path.basename(filepath).replace('.md', ''))
    commands = generate_commands(pattern, paths, issue_id)

    # Insert into content
    new_rest = insert_verification_section(rest, commands)

    # Rebuild full content
    fm_end = full_content.find('\n---\n', 3)
    new_content = full_content[:fm_end + 5] + new_rest

    if dry_run:
        return True, f"Would add {pattern} commands ({len(paths)} paths)"

    # Write back
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True, f"Added {pattern} commands ({len(paths)} paths)"
    except Exception as e:
        return False, f"Write error: {e}"

def process_all(issues_dir: str, lane: str = None, issue_id: str = None,
                dry_run: bool = True) -> Dict[str, int]:
    """Process all issues."""
    stats = {'processed': 0, 'skipped': 0, 'errors': 0}

    # Determine files to process
    if issue_id:
        lane_letter = issue_id[0].upper()
        patterns = [
            os.path.join(issues_dir, lane_letter, f"{issue_id}.md"),
            os.path.join(issues_dir, lane_letter, f"{lane_letter}-{issue_id[1:].lstrip('-')}.md"),
        ]
        files = [p for p in patterns if os.path.exists(p)]
        if not files:
            files = glob.glob(os.path.join(issues_dir, lane_letter, f"*{issue_id}*.md"))
    elif lane:
        files = glob.glob(os.path.join(issues_dir, lane.upper(), '*.md'))
    else:
        files = glob.glob(os.path.join(issues_dir, '*', '*.md'))

    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    print("=" * 70)
    print("the system VERIFICATION COMMANDS GENERATOR")
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
        elif 'Already has' in message:
            stats['skipped'] += 1
            if dry_run:
                print(f"\u23ed\ufe0f  {basename}: {message}")
        else:
            stats['errors'] += 1
            print(f"\u274c {basename}: {message}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Processed: {stats['processed']}")
    print(f"Skipped:   {stats['skipped']}")
    print(f"Errors:    {stats['errors']}")

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
        description='Add verification commands to the system issue files'
    )
    parser.add_argument('--apply', action='store_true', help='Apply changes')
    parser.add_argument('--lane', '-l', type=str, help='Process single lane')
    parser.add_argument('--file', '-f', type=str, help='Process single file')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)

    args = parser.parse_args()

    stats = process_all(
        args.issues_dir,
        lane=args.lane,
        issue_id=args.file,
        dry_run=not args.apply
    )

    sys.exit(0 if stats['errors'] == 0 else 1)

if __name__ == '__main__':
    main()
