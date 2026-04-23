#!/usr/bin/env python3
"""
Fix missing pattern_vars and affected_paths in issue files.

This script scans all issue files and:
1. Adds pattern_vars with file_path/source_file if affected_paths exists but pattern_vars is missing
2. Reports issues with empty affected_paths that need manual attention
3. Filters out garbage paths (ASCII art, comments, etc.)

Usage:
    python3 tools/fix_issue_frontmatter.py         # Dry run (report only)
    python3 tools/fix_issue_frontmatter.py --fix   # Actually fix files
"""

import os
import re
import sys
import yaml
import argparse
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

def is_valid_path(path: str) -> bool:
    """Check if string looks like a valid filesystem path."""
    if not path or not path.strip():
        return False
    # Contains ASCII art/tree characters
    if any(c in path for c in '├└│─►▸▹'):
        return False
    # Starts with comment/markup characters
    if path.lstrip().startswith(('#', '*', '>', '-')) and not path.startswith('./'):
        return False
    # Contains ellipsis (description text)
    if '...' in path:
        return False
    # Starts with shell command prefix
    SHELL_COMMANDS = {'ls', 'cat', 'grep', 'find', 'echo', 'python', 'python3',
                      'bash', 'sh', 'test', 'head', 'tail', 'awk', 'sed', 'yamllint'}
    first_word = path.split()[0].lower() if ' ' in path else None
    if first_word and first_word in SHELL_COMMANDS:
        return False
    # Too many spaces (likely a description, not a path)
    if path.count(' ') > 2:
        return False
    # Must look like a path
    return bool(re.match(r'^[\w./_\-]+$', path.strip()))

def parse_frontmatter(content: str) -> Tuple[Optional[Dict[str, Any]], int, int]:
    """Parse YAML frontmatter from issue content.

    Returns (frontmatter_dict, start_pos, end_pos) or (None, -1, -1) if not found.
    """
    if not content.startswith('---'):
        return None, -1, -1

    end = content.find('\n---\n', 3)
    if end < 0:
        return None, -1, -1

    try:
        fm = yaml.safe_load(content[4:end])
        return fm, 4, end
    except yaml.YAMLError:
        return None, -1, -1

def check_verification_commands(content: str) -> list:
    """Extract placeholders used in verification commands."""
    # Find Verification Commands section
    match = re.search(r'\*\*Verification Commands.*?\*\*.*?```bash\n(.*?)```', content, re.DOTALL)
    if not match:
        return []

    cmd_section = match.group(1)
    # Find all placeholders
    placeholders = re.findall(r'\{(\w+)\}|<(\w+)>', cmd_section)
    return list(set([p[0] or p[1] for p in placeholders]))

def analyze_issue(filepath: str) -> Dict[str, Any]:
    """Analyze an issue file and return its status."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    fm, start, end = parse_frontmatter(content)
    if fm is None:
        return {'status': 'no_frontmatter', 'file': filepath}

    issue_id = fm.get('issue_id', Path(filepath).stem)
    affected = fm.get('affected_paths', [])
    pattern_vars = fm.get('pattern_vars', {})
    placeholders = check_verification_commands(content)

    # Filter valid paths
    valid_paths = [p for p in affected if is_valid_path(p)]

    result = {
        'file': filepath,
        'issue_id': issue_id,
        'affected_paths': affected,
        'valid_paths': valid_paths,
        'pattern_vars': pattern_vars,
        'placeholders': placeholders,
        'status': 'ok'
    }

    # Check for issues
    if placeholders and not pattern_vars and not valid_paths:
        result['status'] = 'needs_paths'
        result['problem'] = f"Has placeholders {placeholders} but no affected_paths"
    elif placeholders and not pattern_vars.get('file_path') and not pattern_vars.get('source_file'):
        if valid_paths:
            result['status'] = 'can_fix'
            result['fix'] = {'file_path': valid_paths[0], 'source_file': valid_paths[0]}
        else:
            result['status'] = 'needs_paths'
            result['problem'] = f"Has placeholders {placeholders} but no valid paths"

    return result

def fix_issue(filepath: str, fix_data: Dict[str, str]) -> bool:
    """Add pattern_vars to issue frontmatter."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    fm, start, end = parse_frontmatter(content)
    if fm is None:
        return False

    # Add pattern_vars
    if 'pattern_vars' not in fm:
        fm['pattern_vars'] = {}

    for key, value in fix_data.items():
        if key not in fm['pattern_vars']:
            fm['pattern_vars'][key] = value

    # Rebuild content with updated frontmatter
    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_content = f"---\n{new_fm}---{content[end+3:]}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True

def main():
    parser = argparse.ArgumentParser(description='Fix issue frontmatter')
    parser.add_argument('--fix', action='store_true', help='Actually fix files (default is dry run)')
    parser.add_argument('--lane', '-l', type=str, help='Only process specific lane')
    args = parser.parse_args()

    issues_dir = Path('issues')
    if not issues_dir.exists():
        print("Error: issues/ directory not found", file=sys.stderr)
        sys.exit(1)

    stats = {'ok': 0, 'can_fix': 0, 'needs_paths': 0, 'no_frontmatter': 0, 'fixed': 0}
    issues_to_fix = []
    issues_needing_paths = []

    lanes = [args.lane.upper()] if args.lane else list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    for lane in lanes:
        lane_dir = issues_dir / lane
        if not lane_dir.exists():
            continue

        for issue_file in sorted(lane_dir.glob('*.md')):
            if 'TEMPLATE' in issue_file.name.upper():
                continue

            result = analyze_issue(str(issue_file))
            stats[result['status']] += 1

            if result['status'] == 'can_fix':
                issues_to_fix.append(result)
            elif result['status'] == 'needs_paths':
                issues_needing_paths.append(result)

    # Report
    print("=" * 60)
    print("ISSUE FRONTMATTER ANALYSIS")
    print("=" * 60)
    print(f"OK (no changes needed):     {stats['ok']}")
    print(f"Can be auto-fixed:          {stats['can_fix']}")
    print(f"Needs manual path addition: {stats['needs_paths']}")
    print(f"No frontmatter:             {stats['no_frontmatter']}")
    print("=" * 60)

    if issues_to_fix:
        print(f"\nIssues that can be auto-fixed ({len(issues_to_fix)}):")
        for issue in issues_to_fix[:10]:
            print(f"  {issue['issue_id']}: Add pattern_vars.file_path = {issue['fix']['file_path']}")
        if len(issues_to_fix) > 10:
            print(f"  ... and {len(issues_to_fix) - 10} more")

    if issues_needing_paths:
        print(f"\nIssues needing manual attention ({len(issues_needing_paths)}):")
        for issue in issues_needing_paths[:10]:
            print(f"  {issue['issue_id']}: {issue.get('problem', 'needs affected_paths')}")
        if len(issues_needing_paths) > 10:
            print(f"  ... and {len(issues_needing_paths) - 10} more")

    # Fix if requested
    if args.fix and issues_to_fix:
        print(f"\nFixing {len(issues_to_fix)} issues...")
        for issue in issues_to_fix:
            if fix_issue(issue['file'], issue['fix']):
                stats['fixed'] += 1
                print(f"  Fixed: {issue['issue_id']}")
        print(f"\nTotal fixed: {stats['fixed']}")
    elif issues_to_fix and not args.fix:
        print(f"\nRun with --fix to apply changes to {len(issues_to_fix)} issues")

if __name__ == '__main__':
    main()
