#!/usr/bin/env python3
"""
Pattern Variable Bindings Generator

Adds explicit pattern_vars to issue frontmatter for agent verification.
Extracts paths and values from content and makes them machine-readable.

Usage:
    python3 tools/add_pattern_vars.py              # Dry run
    python3 tools/add_pattern_vars.py --apply      # Apply to all
    python3 tools/add_pattern_vars.py --lane G     # Single lane
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

# Pattern type to expected variables mapping
PATTERN_VARS = {
    'missing_file': ['file_path'],
    'missing_directory': ['dir_path'],
    'json_schema': ['file_path', 'schema_url'],
    'yaml_schema': ['file_path'],
    'python_script': ['script_path'],
    'ghost_reference': ['source_file', 'referenced_path', 'line_number'],
    'workflow_file': ['workflow_path'],
    'markdown_doc': ['doc_path'],
    'stub_implementation': ['file_path', 'function_name'],
    'policy_violation': ['policy_file', 'target_file'],
    'contradiction': ['file1_path', 'file2_path'],
    'broken_link': ['source_file', 'link_target'],
    'duplicate_entry': ['file_path', 'entry_name'],
}

# =============================================================================
# PARSING
# =============================================================================

def parse_frontmatter(filepath: str) -> Tuple[Optional[Dict], str, int, int]:
    """Parse frontmatter and return metadata, content, and positions."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None, "", 0, 0

    if not content.startswith('---'):
        return None, content, 0, 0

    end = content.find('\n---\n', 3)
    if end < 0:
        return None, content, 0, 0

    try:
        fm = yaml.safe_load(content[4:end])
        return fm, content, 4, end
    except yaml.YAMLError:
        return None, content, 0, 0

def extract_paths_from_content(content: str) -> List[str]:
    """Extract file paths from issue content."""
    paths = []

    # Match backtick-enclosed paths
    for match in re.finditer(r'`([^`\n]+/[^`\n]+)`', content):
        path = match.group(1)
        # Clean path
        path = re.sub(r':\d+.*$', '', path)  # Remove line numbers
        path = path.strip()
        # Skip non-paths
        if any(skip in path.lower() for skip in ['http', 'python3', 'echo', 'test ', '&&', '||']):
            continue
        if len(path) > 3 and path not in paths:
            paths.append(path)

    return paths[:10]  # Limit to 10

def extract_line_numbers(content: str) -> List[str]:
    """Extract line number references."""
    line_nums = []
    for match in re.finditer(r':(\d+)(?:\D|$)', content):
        line_nums.append(match.group(1))
    return line_nums[:5]

def extract_function_names(content: str) -> List[str]:
    """Extract function/method names."""
    names = []
    # Look for function references
    for match in re.finditer(r'`(\w+)\(\)`', content):
        names.append(match.group(1))
    # Look for def statements
    for match in re.finditer(r'def\s+(\w+)\s*\(', content):
        if match.group(1) not in names:
            names.append(match.group(1))
    return names[:5]

# =============================================================================
# VARIABLE GENERATION
# =============================================================================

def generate_pattern_vars(frontmatter: Dict, content: str) -> Dict[str, str]:
    """Generate pattern variables based on issue type and content."""
    pattern_type = frontmatter.get('verification_pattern', 'missing_file')
    affected_paths = frontmatter.get('affected_paths', [])

    vars_dict = {}

    # Get paths from content as fallback
    content_paths = extract_paths_from_content(content)
    all_paths = affected_paths + [p for p in content_paths if p not in affected_paths]

    # Generate variables based on pattern type
    if pattern_type == 'missing_file':
        if all_paths:
            vars_dict['file_path'] = all_paths[0]

    elif pattern_type == 'missing_directory':
        if all_paths:
            path = all_paths[0]
            # Ensure it's a directory (no extension or ends with /)
            if not re.search(r'\.\w+$', path):
                vars_dict['dir_path'] = path.rstrip('/')
            else:
                vars_dict['dir_path'] = os.path.dirname(path)

    elif pattern_type in ['json_schema', 'yaml_schema']:
        if all_paths:
            vars_dict['file_path'] = all_paths[0]
        vars_dict['schema_url'] = 'http://json-schema.org/draft-07/schema#'

    elif pattern_type == 'python_script':
        py_paths = [p for p in all_paths if p.endswith('.py')]
        if py_paths:
            vars_dict['script_path'] = py_paths[0]
        elif all_paths:
            vars_dict['script_path'] = all_paths[0]

    elif pattern_type == 'ghost_reference':
        if len(all_paths) >= 2:
            vars_dict['source_file'] = all_paths[0]
            vars_dict['referenced_path'] = all_paths[1]
        elif all_paths:
            vars_dict['source_file'] = all_paths[0]
            vars_dict['referenced_path'] = 'UNKNOWN'
        line_nums = extract_line_numbers(content)
        if line_nums:
            vars_dict['line_number'] = line_nums[0]

    elif pattern_type == 'workflow_file':
        workflow_paths = [p for p in all_paths if 'workflow' in p.lower() or '.github' in p]
        if workflow_paths:
            vars_dict['workflow_path'] = workflow_paths[0]
        elif all_paths:
            vars_dict['workflow_path'] = all_paths[0]

    elif pattern_type == 'markdown_doc':
        md_paths = [p for p in all_paths if p.endswith('.md')]
        if md_paths:
            vars_dict['doc_path'] = md_paths[0]
        elif all_paths:
            vars_dict['doc_path'] = all_paths[0]

    elif pattern_type == 'stub_implementation':
        if all_paths:
            vars_dict['file_path'] = all_paths[0]
        func_names = extract_function_names(content)
        if func_names:
            vars_dict['function_name'] = func_names[0]
        else:
            vars_dict['function_name'] = 'UNKNOWN'

    elif pattern_type == 'policy_violation':
        policy_paths = [p for p in all_paths if 'policy' in p.lower() or 'guideline' in p.lower()]
        other_paths = [p for p in all_paths if p not in policy_paths]
        if policy_paths:
            vars_dict['policy_file'] = policy_paths[0]
        if other_paths:
            vars_dict['target_file'] = other_paths[0]
        elif len(all_paths) >= 2:
            vars_dict['policy_file'] = all_paths[0]
            vars_dict['target_file'] = all_paths[1]

    elif pattern_type == 'contradiction':
        if len(all_paths) >= 2:
            vars_dict['file1_path'] = all_paths[0]
            vars_dict['file2_path'] = all_paths[1]
        elif all_paths:
            vars_dict['file1_path'] = all_paths[0]
            vars_dict['file2_path'] = 'UNKNOWN'

    elif pattern_type == 'broken_link':
        if len(all_paths) >= 2:
            vars_dict['source_file'] = all_paths[0]
            vars_dict['link_target'] = all_paths[1]
        elif all_paths:
            vars_dict['source_file'] = all_paths[0]
            vars_dict['link_target'] = 'UNKNOWN'

    elif pattern_type == 'duplicate_entry':
        if all_paths:
            vars_dict['file_path'] = all_paths[0]
        # Try to extract entry name from content
        match = re.search(r'duplicate.*?[`"]([^`"]+)[`"]', content, re.IGNORECASE)
        if match:
            vars_dict['entry_name'] = match.group(1)
        else:
            vars_dict['entry_name'] = 'UNKNOWN'

    else:
        # Default: just use first path
        if all_paths:
            vars_dict['file_path'] = all_paths[0]

    return vars_dict

def has_pattern_vars(content: str) -> bool:
    """Check if content already has pattern_vars in frontmatter."""
    return 'pattern_vars:' in content[:2000]

def insert_pattern_vars(content: str, fm_start: int, fm_end: int, vars_dict: Dict[str, str]) -> str:
    """Insert pattern_vars into frontmatter."""
    if not vars_dict:
        return content

    # Build YAML for pattern_vars
    vars_yaml = "pattern_vars:\n"
    for key, value in vars_dict.items():
        # Escape quotes in values
        escaped_value = value.replace('"', '\\"')
        vars_yaml += f'  {key}: "{escaped_value}"\n'

    # Find insertion point (before depends_on)
    frontmatter = content[fm_start:fm_end]

    # Insert before depends_on line
    match = re.search(r'\ndepends_on:', frontmatter)
    if match:
        insert_pos = fm_start + match.start() + 1
        return content[:insert_pos] + vars_yaml + content[insert_pos:]

    # Or insert at end of frontmatter
    return content[:fm_end] + '\n' + vars_yaml + content[fm_end:]

# =============================================================================
# PROCESSING
# =============================================================================

def process_issue(filepath: str, dry_run: bool = True) -> Tuple[bool, str]:
    """Process a single issue file."""
    frontmatter, content, fm_start, fm_end = parse_frontmatter(filepath)

    if not frontmatter:
        return False, "No frontmatter"

    if has_pattern_vars(content):
        return False, "Already has pattern_vars"

    # Generate pattern variables
    vars_dict = generate_pattern_vars(frontmatter, content)

    if not vars_dict:
        return False, "Could not extract variables"

    if dry_run:
        var_count = len(vars_dict)
        var_names = ', '.join(vars_dict.keys())
        return True, f"Would add {var_count} vars: {var_names}"

    # Insert pattern_vars
    new_content = insert_pattern_vars(content, fm_start, fm_end, vars_dict)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        var_count = len(vars_dict)
        return True, f"Added {var_count} pattern vars"
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
    print("the system PATTERN VARIABLE BINDINGS GENERATOR")
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
    print(f"Pattern vars added: {stats['processed']}")
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
        description='Add pattern variable bindings to the system issue frontmatter'
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
