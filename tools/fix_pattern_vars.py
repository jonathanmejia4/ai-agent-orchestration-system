#!/usr/bin/env python3
"""
Fix malformed pattern_vars in issue files.

Fixes three bug types:
  BUG-VER-001: Extract file paths from grep commands
  BUG-VER-002: Convert glob patterns to directory_path + file_pattern
  BUG-VER-003: Add missing required pattern_vars for verification patterns

Usage:
  python3 tools/fix_pattern_vars.py --dry-run  # Preview changes
  python3 tools/fix_pattern_vars.py            # Apply fixes
"""
import os
import re
import sys

def extract_file_from_grep(grep_cmd):
    """
    Extract file path(s) from a grep command.

    Examples:
        'grep -n "PLANNING/" .claude/agents/Planner.md' -> '.claude/agents/Planner.md'
        'grep -rn "LogBook/" .claude/agents/ .claude/guidelines/' -> '.claude/agents/'
        'grep -n \\"PLANNING/\\" .claude/agents/Planner.md' -> '.claude/agents/Planner.md'
    """
    # Normalize escaped quotes
    grep_cmd = grep_cmd.replace('\\"', '"').replace("\\'", "'")

    # Pattern: grep [flags] "pattern" file1 [file2 ...]
    # We need to find the part AFTER the search pattern

    # Look for file paths (starting with ./ or a word char, ending before | or end)
    # Match paths like .claude/agents/file.md or PLANNING/file.md
    matches = re.findall(r'(?:^|\s)([.a-zA-Z_][a-zA-Z0-9_./-]+\.(?:md|yaml|yml|py|sh|json|txt))', grep_cmd)
    if matches:
        return matches[0]

    # Try to find directory paths
    matches = re.findall(r'(?:^|\s)([.a-zA-Z_][a-zA-Z0-9_/-]+/)(?:\s|$|\|)', grep_cmd)
    if matches:
        return matches[0]

    # Fallback: look for anything after the quoted pattern
    match = re.search(r'["\'][^"\']*["\']\s+(.+?)(?:\s*\|.*)?$', grep_cmd)
    if match:
        files_part = match.group(1).strip()
        first_file = files_part.split()[0]
        if first_file and not first_file.startswith('-'):
            return first_file

    return None

def convert_glob_to_directory(glob_path):
    """
    Convert glob pattern to directory_path and file_pattern.

    Examples:
        'integration/adapters/*.py' -> ('integration/adapters', '*.py')
        'tools/**/*.sh' -> ('tools', '**/*.sh')
    """
    # Find the last / before the glob pattern
    match = re.match(r'^(.+?)/(\*\*.*/.*|\*\.[a-z]+)$', glob_path, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)

    # Simple case: dir/*.ext
    match = re.match(r'^(.+)/(\*\.[a-z]+)$', glob_path, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)

    return None, None

def fix_issue_file(issue_file, dry_run=False):
    """
    Fix pattern_vars in a single issue file.
    Returns (changed, changes_made) tuple.
    """
    with open(issue_file, 'r') as f:
        content = f.read()

    original_content = content
    changes = []

    # Find frontmatter
    fm_match = re.match(r'^(---\n)(.*?)(\n---)', content, re.DOTALL)
    if not fm_match:
        return False, []

    frontmatter = fm_match.group(2)

    # BUG-VER-001: Fix grep commands in file_path
    # Look for file_path values that start with "grep" or 'grep'
    # Handle escaped quotes inside the YAML string
    file_path_match = re.search(r'(\s*file_path:\s*)"((?:[^"\\]|\\.)*)"\s*$', frontmatter, re.MULTILINE)
    if file_path_match:
        file_path_value = file_path_match.group(2).replace('\\"', '"')
        if file_path_value.startswith('grep') or file_path_value.startswith('find'):
            extracted = extract_file_from_grep(file_path_value)
            if extracted:
                old_line = file_path_match.group(0)
                new_line = f'{file_path_match.group(1)}"{extracted}"'
                frontmatter = frontmatter.replace(old_line, new_line)
                changes.append(f"BUG-VER-001: Extracted '{extracted}' from grep command")

    # BUG-VER-002: Fix glob patterns in file_path
    glob_match = re.search(r'file_path:\s*["\']?([^"\'\n]+\*\.[a-z]+)["\']?', frontmatter, re.IGNORECASE)
    if glob_match:
        glob_path = glob_match.group(1)
        directory, pattern = convert_glob_to_directory(glob_path)
        if directory and pattern:
            # Replace file_path with directory_path and file_pattern
            old_line_match = re.search(r'(\s*file_path:\s*)["\']?[^"\'\n]+\*\.[a-z]+["\']?', frontmatter, re.IGNORECASE)
            if old_line_match:
                old_line = old_line_match.group(0)
                indent = re.match(r'\s*', old_line_match.group(0)).group(0)
                new_lines = f'{indent}directory_path: "{directory}"\n{indent}file_pattern: "{pattern}"'
                frontmatter = frontmatter.replace(old_line, new_lines)
                changes.append(f"BUG-VER-002: Converted glob '{glob_path}' to directory_path + file_pattern")

    # BUG-VER-003: Add missing pattern_vars
    # Check verification_pattern
    pattern_match = re.search(r'verification_pattern:\s*["\']?([a-z_]+)["\']?', frontmatter)
    if pattern_match:
        verification_pattern = pattern_match.group(1)

        # Required vars by pattern
        required_vars = {
            'policy_alignment': {'source_file': 'ISSUE_CATALOG.md'},
            'missing_file': {'file_path': ''},  # Can't auto-populate
            'ghost_reference': {'ghost_pattern': ''},
        }

        if verification_pattern in required_vars:
            for var, default in required_vars[verification_pattern].items():
                # Check if var already exists
                if not re.search(rf'{var}:\s*\S', frontmatter):
                    # Only add if we have a default value
                    if default:
                        # Find pattern_vars section and add the variable
                        pv_match = re.search(r'(pattern_vars:.*?)(\n[a-z]|\n---|\Z)', frontmatter, re.DOTALL)
                        if pv_match:
                            pv_section = pv_match.group(1)
                            # Add the missing variable
                            new_pv = f'{pv_section}\n  {var}: "{default}"'
                            frontmatter = frontmatter.replace(pv_section, new_pv)
                            changes.append(f"BUG-VER-003: Added {var}: '{default}' for {verification_pattern}")

    # Reconstruct the content
    if changes:
        new_content = fm_match.group(1) + frontmatter + fm_match.group(3) + content[fm_match.end():]

        if not dry_run:
            with open(issue_file, 'w') as f:
                f.write(new_content)

        return True, changes

    return False, []

def fix_all_issues(issues_dir='issues', dry_run=False):
    """Fix all issue files."""
    total_fixed = 0
    all_changes = []

    for lane in sorted(os.listdir(issues_dir)):
        lane_dir = os.path.join(issues_dir, lane)
        if not os.path.isdir(lane_dir):
            continue

        for filename in sorted(os.listdir(lane_dir)):
            if not filename.endswith('.md'):
                continue

            issue_file = os.path.join(lane_dir, filename)
            changed, changes = fix_issue_file(issue_file, dry_run)

            if changed:
                total_fixed += 1
                for change in changes:
                    all_changes.append((issue_file, change))

    return total_fixed, all_changes

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fix malformed pattern_vars in issue files')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--issues-dir', default='issues', help='Issues directory path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all changes')
    args = parser.parse_args()

    print(f"{'DRY RUN - ' if args.dry_run else ''}Fixing pattern_vars in {args.issues_dir}/")
    print('='*60)

    total_fixed, all_changes = fix_all_issues(args.issues_dir, args.dry_run)

    # Group by bug type
    by_bug = {}
    for file, change in all_changes:
        bug = change.split(':')[0]
        if bug not in by_bug:
            by_bug[bug] = []
        by_bug[bug].append((file, change))

    for bug in sorted(by_bug.keys()):
        print(f"\n{bug}: {len(by_bug[bug])} fixes")
        if args.verbose:
            for file, change in by_bug[bug][:20]:
                print(f"  {file}: {change}")
            if len(by_bug[bug]) > 20:
                print(f"  ... and {len(by_bug[bug]) - 20} more")

    print(f"\n{'='*60}")
    print(f"TOTAL: {total_fixed} files {'would be ' if args.dry_run else ''}modified")
    print(f"       {len(all_changes)} changes {'would be ' if args.dry_run else ''}applied")
    print('='*60)

    if args.dry_run:
        print("\nRun without --dry-run to apply changes")

if __name__ == '__main__':
    main()
