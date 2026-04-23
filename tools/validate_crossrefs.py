#!/usr/bin/env python3
"""
the system Cross-Reference Validator

Validates that all issue cross-references are valid:
- depends_on references exist
- blocks references exist
- related references exist
- No circular dependencies
- No self-references

Usage:
    python3 tools/validate_crossrefs.py
    python3 tools/validate_crossrefs.py --fix    # Auto-fix invalid refs
"""

import os
import re
import sys
import glob
import yaml
import argparse
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"

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

def get_all_issue_ids(issues_dir: str) -> Set[str]:
    """Get set of all valid issue IDs."""
    issue_ids = set()

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        basename = os.path.basename(filepath)
        issue_id = basename.replace('.md', '')
        issue_ids.add(issue_id)

        # Also check frontmatter for issue_id
        fm, _ = parse_frontmatter(filepath)
        if fm and 'issue_id' in fm:
            issue_ids.add(fm['issue_id'])

    return issue_ids

def load_all_issues(issues_dir: str) -> Dict[str, Dict]:
    """Load all issue frontmatter data."""
    issues = {}

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        fm, content = parse_frontmatter(filepath)
        if fm:
            issue_id = fm.get('issue_id', os.path.basename(filepath).replace('.md', ''))
            issues[issue_id] = {
                'filepath': filepath,
                'frontmatter': fm,
                'depends_on': fm.get('depends_on', []) or [],
                'blocks': fm.get('blocks', []) or [],
                'related': fm.get('related', []) or [],
            }

    return issues

# =============================================================================
# VALIDATION
# =============================================================================

def find_invalid_references(issues: Dict[str, Dict], valid_ids: Set[str]) -> Dict[str, List[Tuple[str, str, str]]]:
    """Find all invalid cross-references."""
    invalid = defaultdict(list)

    for issue_id, data in issues.items():
        for ref_type in ['depends_on', 'blocks', 'related']:
            refs = data.get(ref_type, [])
            if not refs:
                continue

            for ref in refs:
                # Skip empty refs
                if not ref or ref == '':
                    continue

                # Check self-reference
                if ref == issue_id:
                    invalid[issue_id].append((ref_type, ref, "self-reference"))
                    continue

                # Check if reference exists
                if ref not in valid_ids:
                    invalid[issue_id].append((ref_type, ref, "not found"))

    return dict(invalid)

def find_circular_dependencies(issues: Dict[str, Dict]) -> List[List[str]]:
    """Find circular dependency chains."""
    cycles = []

    def find_cycle(start: str, current: str, path: List[str], visited: Set[str]) -> Optional[List[str]]:
        if current in visited:
            if current == start and len(path) > 1:
                return path + [current]
            return None

        visited.add(current)
        path.append(current)

        deps = issues.get(current, {}).get('depends_on', [])
        for dep in deps:
            if dep in issues:
                result = find_cycle(start, dep, path.copy(), visited.copy())
                if result:
                    return result

        return None

    # Check each issue for cycles
    checked = set()
    for issue_id in issues:
        if issue_id in checked:
            continue

        cycle = find_cycle(issue_id, issue_id, [], set())
        if cycle:
            # Normalize cycle to avoid duplicates
            min_idx = cycle.index(min(cycle[:-1]))
            normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]

            if normalized not in cycles:
                cycles.append(normalized)

        checked.add(issue_id)

    return cycles

def check_bidirectional_consistency(issues: Dict[str, Dict]) -> List[Tuple[str, str, str]]:
    """Check that depends_on and blocks are consistent."""
    inconsistencies = []

    for issue_id, data in issues.items():
        # If A depends_on B, then B should block A
        for dep in data.get('depends_on', []):
            if dep in issues:
                blocks = issues[dep].get('blocks', [])
                if issue_id not in blocks:
                    inconsistencies.append((issue_id, dep, "depends_on not reflected in blocks"))

        # If A blocks B, then B should depend_on A
        for blocked in data.get('blocks', []):
            if blocked in issues:
                deps = issues[blocked].get('depends_on', [])
                if issue_id not in deps:
                    inconsistencies.append((issue_id, blocked, "blocks not reflected in depends_on"))

    return inconsistencies

# =============================================================================
# FIXING
# =============================================================================

def fix_invalid_references(issues: Dict[str, Dict], invalid_refs: Dict[str, List[Tuple[str, str, str]]]) -> int:
    """Remove invalid references from issues."""
    fixed = 0

    for issue_id, refs in invalid_refs.items():
        if issue_id not in issues:
            continue

        filepath = issues[issue_id]['filepath']

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        modified = False

        for ref_type, ref, reason in refs:
            # Remove the invalid reference from the array
            pattern = rf'({ref_type}:\s*\[)([^\]]*)\]'
            match = re.search(pattern, content)
            if match:
                refs_str = match.group(2)
                # Remove the invalid ref
                refs_list = [r.strip().strip('"\'') for r in refs_str.split(',') if r.strip()]
                refs_list = [r for r in refs_list if r != ref]
                new_refs = ', '.join(f'"{r}"' for r in refs_list if r)
                new_section = f'{match.group(1)}{new_refs}]'
                content = content[:match.start()] + new_section + content[match.end():]
                modified = True

        if modified:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed += 1
            except:
                pass

    return fixed

# =============================================================================
# REPORTING
# =============================================================================

def run_validation(issues_dir: str, fix: bool = False) -> bool:
    """Run full cross-reference validation."""
    print("=" * 70)
    print("the system CROSS-REFERENCE VALIDATOR")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load data
    print("Loading issues...")
    valid_ids = get_all_issue_ids(issues_dir)
    issues = load_all_issues(issues_dir)
    print(f"Found {len(issues)} issues with {len(valid_ids)} unique IDs")
    print()

    all_valid = True

    # Check 1: Invalid references
    print("-" * 70)
    print("CHECK 1: Invalid References")
    print("-" * 70)
    invalid_refs = find_invalid_references(issues, valid_ids)
    if invalid_refs:
        print(f"   Found {len(invalid_refs)} issues with invalid references:")
        for issue_id, refs in list(invalid_refs.items())[:10]:
            for ref_type, ref, reason in refs:
                print(f"      {issue_id}: {ref_type} -> {ref} ({reason})")
        if len(invalid_refs) > 10:
            print(f"      ... and {len(invalid_refs) - 10} more")
        print("   \u274c FAILED")
        all_valid = False

        if fix:
            print()
            print("   Fixing invalid references...")
            fixed = fix_invalid_references(issues, invalid_refs)
            print(f"   Fixed {fixed} issues")
    else:
        print("   No invalid references found")
        print("   \u2705 PASSED")

    # Check 2: Circular dependencies
    print()
    print("-" * 70)
    print("CHECK 2: Circular Dependencies")
    print("-" * 70)
    cycles = find_circular_dependencies(issues)
    if cycles:
        print(f"   Found {len(cycles)} circular dependency chains:")
        for cycle in cycles[:5]:
            print(f"      {' -> '.join(cycle)}")
        if len(cycles) > 5:
            print(f"      ... and {len(cycles) - 5} more")
        print("   \u26a0\ufe0f  WARNING (may be intentional)")
    else:
        print("   No circular dependencies found")
        print("   \u2705 PASSED")

    # Check 3: Bidirectional consistency
    print()
    print("-" * 70)
    print("CHECK 3: Bidirectional Consistency")
    print("-" * 70)
    inconsistencies = check_bidirectional_consistency(issues)
    if inconsistencies:
        print(f"   Found {len(inconsistencies)} inconsistencies:")
        for issue_id, ref, reason in inconsistencies[:10]:
            print(f"      {issue_id} <-> {ref}: {reason}")
        if len(inconsistencies) > 10:
            print(f"      ... and {len(inconsistencies) - 10} more")
        print("   \u26a0\ufe0f  WARNING (may be acceptable)")
    else:
        print("   All cross-references are bidirectionally consistent")
        print("   \u2705 PASSED")

    # Summary
    print()
    print("=" * 70)

    total_issues = len(issues)
    issues_with_deps = sum(1 for i in issues.values() if i.get('depends_on'))
    issues_with_blocks = sum(1 for i in issues.values() if i.get('blocks'))
    issues_with_related = sum(1 for i in issues.values() if i.get('related'))

    print("SUMMARY")
    print("-" * 70)
    print(f"   Total issues:           {total_issues}")
    print(f"   With depends_on:        {issues_with_deps}")
    print(f"   With blocks:            {issues_with_blocks}")
    print(f"   With related:           {issues_with_related}")
    print()
    print(f"   Invalid references:     {len(invalid_refs)}")
    print(f"   Circular dependencies:  {len(cycles)}")
    print(f"   Inconsistencies:        {len(inconsistencies)}")

    print()
    if all_valid:
        print("\u2705 CROSS-REFERENCES VALID")
    else:
        print("\u26a0\ufe0f  CROSS-REFERENCES HAVE ISSUES")

    print("=" * 70)

    return all_valid

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Validate the system issue cross-references'
    )
    parser.add_argument('--fix', action='store_true', help='Auto-fix invalid references')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)

    args = parser.parse_args()

    valid = run_validation(args.issues_dir, fix=args.fix)
    sys.exit(0 if valid else 1)

if __name__ == '__main__':
    main()
