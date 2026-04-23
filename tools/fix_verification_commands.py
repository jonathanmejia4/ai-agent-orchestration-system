#!/usr/bin/env python3
"""
Fix Malformed Verification Commands in Issue Files

Z-28 Fix: This script scans all issue files and fixes common malformed
verification command patterns that cause false negative verification results.

Patterns Fixed:
1. test -f on directories → test -d
2. Wildcards in test → ls with redirect
3. Comment characters in paths → remove #
4. Placeholder variables → test parent directory
5. Multi-part commands as paths → extract valid command
6. Absolute paths → relative paths
7. wc -l incorrectly in test → remove test wrapper

Usage:
    python3 tools/fix_verification_commands.py              # Dry run (default)
    python3 tools/fix_verification_commands.py --apply      # Apply fixes
    python3 tools/fix_verification_commands.py --report     # Generate report only
"""

import os
import re
import sys
import glob
import argparse
from typing import List, Tuple, Dict
from dataclasses import dataclass

@dataclass
class FixResult:
    """Result of fixing a single command."""
    file_path: str
    line_num: int
    original: str
    fixed: str
    pattern: str
    was_changed: bool

def fix_directory_test(line: str) -> Tuple[str, bool, str]:
    """Fix test -f on directory paths (ending in /)."""
    pattern = r'test\s+-f\s+(\S+/)\s*&&'
    if re.search(pattern, line):
        fixed = re.sub(r'test\s+-f\s+(\S+/)', r'test -d \1', line)
        return fixed, True, "directory_test"
    return line, False, ""

def fix_wildcard_test(line: str) -> Tuple[str, bool, str]:
    """Fix wildcards in test command."""
    pattern = r'test\s+-[fd]\s+(\S*\*\S*)\s*&&\s*echo\s+"?PASS"?'
    match = re.search(pattern, line)
    if match:
        path = match.group(1)
        fixed = re.sub(
            pattern,
            f'ls {path} >/dev/null 2>&1 && echo "PASS"',
            line
        )
        return fixed, True, "wildcard_test"
    return line, False, ""

def fix_comment_in_path(line: str) -> Tuple[str, bool, str]:
    """Remove comment characters from paths."""
    pattern = r'test\s+-([fd])\s+#\s*(\S+)'
    if re.search(pattern, line):
        fixed = re.sub(pattern, r'test -\1 \2', line)
        return fixed, True, "comment_in_path"
    return line, False, ""

def fix_placeholder_path(line: str) -> Tuple[str, bool, str]:
    """Handle placeholder variables - test parent directory."""
    pattern = r'test\s+-[fd]\s+/?(\S*)<[a-z_-]+>(\S*)\s*&&\s*echo\s+"?PASS"?'
    match = re.search(pattern, line)
    if match:
        parent_path = match.group(1).rstrip('/')
        if parent_path:
            fixed = re.sub(
                pattern,
                f'test -d {parent_path}/ && echo "PASS"',
                line
            )
            return fixed, True, "placeholder_path"
    return line, False, ""

def fix_multi_command_path(line: str) -> Tuple[str, bool, str]:
    """Fix multi-part commands used as paths."""
    pattern = r'test\s+-[fd]\s+(ls|cat|grep|find)\s+'
    if re.search(pattern, line):
        # Remove the test -f/d prefix, keep the actual command
        fixed = re.sub(r'test\s+-[fd]\s+', '', line, count=1)
        return fixed, True, "multi_command_path"
    return line, False, ""

def fix_absolute_path(line: str) -> Tuple[str, bool, str]:
    """Fix absolute paths to relative."""
    pattern = r'test\s+-([fd])\s+/([A-Za-z])'
    if re.search(pattern, line):
        fixed = re.sub(pattern, r'test -\1 \2', line)
        return fixed, True, "absolute_path"
    return line, False, ""

def fix_wc_in_test(line: str) -> Tuple[str, bool, str]:
    """Fix wc -l incorrectly placed in test."""
    pattern = r'test\s+-[fd]\s+wc\s+-l\s+'
    if re.search(pattern, line):
        fixed = re.sub(r'test\s+-[fd]\s+', '', line, count=1)
        return fixed, True, "wc_in_test"
    return line, False, ""

def fix_test_s_ls_path(line: str) -> Tuple[str, bool, str]:
    """Fix test -s ls PATH → test -d PATH."""
    pattern = r'test\s+-s\s+ls\s+(\S+)'
    match = re.search(pattern, line)
    if match:
        path = match.group(1)
        # Use -d for directories (ending in /) or -e for files
        test_flag = '-d' if path.endswith('/') else '-e'
        fixed = re.sub(pattern, f'test {test_flag} {path}', line)
        return fixed, True, "test_s_ls_path"
    return line, False, ""

def fix_git_ls_files_ls_path(line: str) -> Tuple[str, bool, str]:
    """Fix git ls-files --error-unmatch ls PATH → git ls-files --error-unmatch PATH."""
    pattern = r'git\s+ls-files\s+--error-unmatch\s+ls\s+(\S+)'
    match = re.search(pattern, line)
    if match:
        path = match.group(1)
        # For directories, use different approach - find files in dir
        if path.endswith('/'):
            # Check for any files in directory
            fixed = re.sub(pattern, f'ls {path} >/dev/null 2>&1', line)
        else:
            fixed = re.sub(pattern, f'git ls-files --error-unmatch {path}', line)
        return fixed, True, "git_ls_files_ls_path"
    return line, False, ""

def fix_affected_paths_ls(line: str) -> Tuple[str, bool, str]:
    """Fix affected_paths with 'ls ' prefix in YAML."""
    # Match lines like:  - "ls LogBook/progress/"
    pattern = r'^(\s*-\s*["\']?)ls\s+(\S+)(["\']?\s*)$'
    match = re.search(pattern, line)
    if match:
        prefix = match.group(1)
        path = match.group(2)
        suffix = match.group(3)
        fixed = f'{prefix}{path}{suffix}\n'
        return fixed, True, "affected_paths_ls"
    return line, False, ""

# All fix functions in order of priority
FIX_FUNCTIONS = [
    fix_multi_command_path,  # First: extract commands from test wrapper
    fix_wc_in_test,          # Similar: wc commands in test wrapper
    fix_test_s_ls_path,      # Fix test -s ls PATH
    fix_git_ls_files_ls_path,  # Fix git ls-files with ls PATH
    fix_directory_test,      # Then: fix directory tests
    fix_wildcard_test,       # Then: fix wildcards
    fix_comment_in_path,     # Then: fix comments
    fix_placeholder_path,    # Then: fix placeholders
    fix_absolute_path,       # Finally: fix absolute paths
    fix_affected_paths_ls,   # Fix affected_paths YAML
]

def fix_line(line: str) -> Tuple[str, bool, str]:
    """Apply all fixes to a line."""
    for fix_func in FIX_FUNCTIONS:
        fixed, changed, pattern = fix_func(line)
        if changed:
            return fixed, True, pattern
    return line, False, ""

def process_file(file_path: str, apply: bool = False) -> List[FixResult]:
    """Process a single issue file and return fixes."""
    results = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return results

    modified = False
    new_lines = []

    for i, line in enumerate(lines, 1):
        # Process lines that might need fixing:
        # 1. test commands with PASS/FAIL
        # 2. git ls-files commands
        # 3. affected_paths with 'ls ' prefix
        should_check = (
            ('test -' in line and ('PASS' in line or 'FAIL' in line)) or
            ('git ls-files' in line and 'ls ' in line) or
            (re.match(r'\s*-\s*["\']?ls\s+', line))
        )

        if should_check:
            fixed, changed, pattern = fix_line(line)
            if changed:
                results.append(FixResult(
                    file_path=file_path,
                    line_num=i,
                    original=line.strip(),
                    fixed=fixed.strip(),
                    pattern=pattern,
                    was_changed=True
                ))
                new_lines.append(fixed)
                modified = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if apply and modified:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"Error writing {file_path}: {e}")

    return results

def scan_issues(issues_dir: str = "issues") -> List[str]:
    """Find all issue files."""
    pattern = os.path.join(issues_dir, '*', '*.md')
    files = [f for f in glob.glob(pattern)
             if 'TEMPLATE' not in f.upper()]
    return sorted(files)

def generate_report(results: List[FixResult]) -> str:
    """Generate a summary report."""
    lines = []
    lines.append("# Verification Command Fix Report")
    lines.append("")
    lines.append(f"**Total fixes:** {len(results)}")
    lines.append("")

    # Group by pattern
    by_pattern: Dict[str, List[FixResult]] = {}
    for r in results:
        if r.pattern not in by_pattern:
            by_pattern[r.pattern] = []
        by_pattern[r.pattern].append(r)

    lines.append("## Fixes by Pattern")
    lines.append("")
    for pattern, fixes in sorted(by_pattern.items(), key=lambda x: -len(x[1])):
        lines.append(f"- **{pattern}**: {len(fixes)} fixes")

    lines.append("")
    lines.append("## Detailed Fixes")
    lines.append("")

    # Group by file
    by_file: Dict[str, List[FixResult]] = {}
    for r in results:
        if r.file_path not in by_file:
            by_file[r.file_path] = []
        by_file[r.file_path].append(r)

    for file_path, fixes in sorted(by_file.items()):
        issue_id = os.path.basename(file_path).replace('.md', '')
        lines.append(f"### {issue_id}")
        for fix in fixes:
            lines.append(f"- Line {fix.line_num} ({fix.pattern}):")
            lines.append(f"  - Before: `{fix.original[:60]}...`")
            lines.append(f"  - After:  `{fix.fixed[:60]}...`")
        lines.append("")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description='Fix malformed verification commands in issue files'
    )
    parser.add_argument('--apply', '-a', action='store_true',
                        help='Apply fixes to files (default is dry run)')
    parser.add_argument('--report', '-r', action='store_true',
                        help='Generate detailed report')
    parser.add_argument('--issues-dir', default='issues',
                        help='Issues directory (default: issues)')
    parser.add_argument('--file', '-f', type=str,
                        help='Process single file only')

    args = parser.parse_args()

    if args.file:
        files = [args.file]
    else:
        files = scan_issues(args.issues_dir)

    print(f"Scanning {len(files)} issue files...")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print("")

    all_results = []
    for file_path in files:
        results = process_file(file_path, apply=args.apply)
        all_results.extend(results)
        if results:
            print(f"  {os.path.basename(file_path)}: {len(results)} fixes")

    print("")
    print("=" * 60)
    print(f"SUMMARY")
    print("=" * 60)
    print(f"Files scanned: {len(files)}")
    print(f"Total fixes:   {len(all_results)}")

    # Count by pattern
    patterns = {}
    for r in all_results:
        patterns[r.pattern] = patterns.get(r.pattern, 0) + 1

    print("")
    print("Fixes by pattern:")
    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count}")

    if args.report:
        report = generate_report(all_results)
        report_path = "LogBook/verification/command_fix_report.md"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport written to: {report_path}")

    if not args.apply and all_results:
        print("")
        print("This was a DRY RUN. Run with --apply to apply fixes.")

    return 0 if len(all_results) >= 0 else 1

if __name__ == '__main__':
    sys.exit(main())
