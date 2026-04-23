#!/usr/bin/env python3
"""
the system Issue Dependencies Analyzer

Computes dependencies between issues based on:
1. Affected paths overlap (if A creates X and B references X, B depends on A)
2. Related issue references in content
3. Lane-based logical grouping

Usage:
    python3 tools/compute_dependencies.py                    # Analyze only
    python3 tools/compute_dependencies.py --update           # Update frontmatter
    python3 tools/compute_dependencies.py --lane G           # Single lane
    python3 tools/compute_dependencies.py --graph            # Output DOT graph
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
from dataclasses import dataclass, field

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class IssueInfo:
    """Information about an issue."""
    issue_id: str
    lane: str
    status: str
    severity: int
    affected_paths: List[str] = field(default_factory=list)
    creates_paths: List[str] = field(default_factory=list)
    references_paths: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    filepath: str = ""

# =============================================================================
# PARSING
# =============================================================================

def parse_issue(filepath: str) -> Optional[IssueInfo]:
    """Parse an issue file and extract dependency info."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    if not content.startswith('---'):
        return None

    end = content.find('\n---\n', 3)
    if end < 0:
        return None

    try:
        fm = yaml.safe_load(content[4:end])
    except yaml.YAMLError:
        return None

    issue = IssueInfo(
        issue_id=fm.get('issue_id', os.path.basename(filepath).replace('.md', '')),
        lane=fm.get('lane', ''),
        status=fm.get('status', 'OPEN'),
        severity=fm.get('severity', 5),
        affected_paths=fm.get('affected_paths', []),
        depends_on=fm.get('depends_on', []),
        blocks=fm.get('blocks', []),
        related=fm.get('related', []),
        filepath=filepath,
    )

    # Extract paths from content
    rest = content[end + 5:]

    # Find paths being created (Fix Objective: Create X)
    for match in re.finditer(r'Create\s+(?:directory|file)?:?\s*`?([^\s`\n,]+(?:/[^\s`\n,]+)+)`?', rest):
        path = match.group(1).strip('`').strip()
        if path and len(path) > 3:
            issue.creates_paths.append(path)

    # Find paths being referenced
    for match in re.finditer(r'Referenced\s+path:\s*`?([^\s`\n]+)`?', rest):
        path = match.group(1).strip('`').strip()
        path = re.sub(r':\d+.*$', '', path)
        if path and len(path) > 3:
            issue.references_paths.append(path)

    # Extract related issues from content
    for match in re.finditer(r'Related.*?issues?:\s*([^\n]+)', rest, re.IGNORECASE):
        refs = re.findall(r'([A-Z]-?\d+)', match.group(1))
        issue.related.extend(refs)

    # Dedupe
    issue.related = list(set(issue.related))
    issue.creates_paths = list(set(issue.creates_paths))
    issue.references_paths = list(set(issue.references_paths))

    return issue

def load_all_issues(issues_dir: str, lane: str = None) -> Dict[str, IssueInfo]:
    """Load all issues into a dictionary."""
    issues = {}

    if lane:
        pattern = os.path.join(issues_dir, lane.upper(), '*.md')
    else:
        pattern = os.path.join(issues_dir, '*', '*.md')

    for filepath in glob.glob(pattern):
        if 'TEMPLATE' in filepath.upper():
            continue

        issue = parse_issue(filepath)
        if issue:
            issues[issue.issue_id] = issue

    return issues

# =============================================================================
# DEPENDENCY COMPUTATION
# =============================================================================

def compute_dependencies(issues: Dict[str, IssueInfo]) -> Dict[str, Dict[str, List[str]]]:
    """
    Compute dependencies between issues.

    Returns dict with:
    - depends_on: issues that must be fixed before this one
    - blocks: issues that this one blocks
    - related: issues that touch similar paths
    """
    # Build path -> issue mapping
    path_creators: Dict[str, str] = {}  # path -> issue_id that creates it
    path_referencers: Dict[str, List[str]] = defaultdict(list)  # path -> issue_ids that reference it

    for issue_id, issue in issues.items():
        for path in issue.creates_paths:
            path_creators[path] = issue_id

        for path in issue.references_paths:
            path_referencers[path].append(issue_id)

        for path in issue.affected_paths:
            if path:
                path_referencers[path].append(issue_id)

    # Compute dependencies
    dependencies = {}

    for issue_id, issue in issues.items():
        deps = {
            'depends_on': set(),
            'blocks': set(),
            'related': set(issue.related),
        }

        # If this issue references a path that another issue creates,
        # this issue depends on that other issue
        all_refs = set(issue.references_paths + issue.affected_paths)
        for path in all_refs:
            if path in path_creators:
                creator = path_creators[path]
                if creator != issue_id:
                    deps['depends_on'].add(creator)

        # If this issue creates a path that another issue references,
        # this issue blocks that other issue
        for path in issue.creates_paths:
            for referencer in path_referencers.get(path, []):
                if referencer != issue_id:
                    deps['blocks'].add(referencer)

        # Find related issues (same paths but different issues)
        for path in all_refs:
            for other_id in path_referencers.get(path, []):
                if other_id != issue_id:
                    deps['related'].add(other_id)

        # Same lane issues with close IDs are related
        for other_id, other in issues.items():
            if other_id != issue_id and other.lane == issue.lane:
                try:
                    num1 = int(re.search(r'\d+', issue_id).group())
                    num2 = int(re.search(r'\d+', other_id).group())
                    if abs(num1 - num2) <= 3:
                        deps['related'].add(other_id)
                except:
                    pass

        # Remove self-references and duplicates
        deps['depends_on'] -= {issue_id}
        deps['blocks'] -= {issue_id}
        deps['related'] -= {issue_id}
        deps['related'] -= deps['depends_on']
        deps['related'] -= deps['blocks']

        # Convert to sorted lists
        dependencies[issue_id] = {
            'depends_on': sorted(deps['depends_on']),
            'blocks': sorted(deps['blocks']),
            'related': sorted(deps['related'])[:5],  # Limit related
        }

    return dependencies

def get_verification_order(issues: Dict[str, IssueInfo],
                          dependencies: Dict[str, Dict[str, List[str]]]) -> List[str]:
    """
    Compute optimal verification order (topological sort).
    Issues with no dependencies come first.
    """
    # Build dependency graph
    in_degree = {issue_id: 0 for issue_id in issues}
    for issue_id, deps in dependencies.items():
        in_degree[issue_id] = len(deps['depends_on'])

    # Start with issues that have no dependencies
    queue = [
        (issues[id].severity, id)
        for id in issues
        if in_degree[id] == 0
    ]
    queue.sort(reverse=True)  # Higher severity first

    order = []
    while queue:
        # Pop highest severity issue with no remaining dependencies
        _, issue_id = queue.pop(0)
        order.append(issue_id)

        # Reduce in-degree of issues this one blocks
        for blocked_id in dependencies.get(issue_id, {}).get('blocks', []):
            if blocked_id in in_degree:
                in_degree[blocked_id] -= 1
                if in_degree[blocked_id] == 0:
                    queue.append((issues[blocked_id].severity, blocked_id))
                    queue.sort(reverse=True)

    # Add any remaining issues (cycles or missing refs)
    remaining = [id for id in issues if id not in order]
    remaining.sort(key=lambda x: (-issues[x].severity, x))
    order.extend(remaining)

    return order

# =============================================================================
# UPDATE FRONTMATTER
# =============================================================================

def update_issue_frontmatter(issue: IssueInfo, deps: Dict[str, List[str]]) -> bool:
    """Update issue file with computed dependencies."""
    try:
        with open(issue.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return False

    if not content.startswith('---'):
        return False

    end = content.find('\n---\n', 3)
    if end < 0:
        return False

    # Parse and update frontmatter
    try:
        fm = yaml.safe_load(content[4:end])
    except yaml.YAMLError:
        return False

    # Update dependencies
    fm['depends_on'] = deps['depends_on']
    fm['blocks'] = deps['blocks']
    fm['related'] = deps['related']

    # Rebuild frontmatter
    fm_lines = ['---']

    # Preserve order of known fields
    known_fields = [
        'issue_id', 'lane', 'type_tags', 'severity', 'severity_level',
        'status', 'category', 'user_approval_required',
    ]

    for field in known_fields:
        if field in fm:
            val = fm[field]
            if isinstance(val, list):
                if val:
                    items = ', '.join(f'"{v}"' for v in val)
                    fm_lines.append(f'{field}: [{items}]')
                else:
                    fm_lines.append(f'{field}: []')
            elif isinstance(val, bool):
                fm_lines.append(f'{field}: {str(val).lower()}')
            elif isinstance(val, str):
                fm_lines.append(f'{field}: "{val}"')
            else:
                fm_lines.append(f'{field}: {val}')

    # Add verification section
    fm_lines.append('')
    fm_lines.append('# Verification Configuration')
    if 'verification_pattern' in fm:
        fm_lines.append(f'verification_pattern: "{fm["verification_pattern"]}"')
    if 'verification_depth' in fm:
        fm_lines.append(f'verification_depth: "{fm["verification_depth"]}"')

    # Add affected paths
    fm_lines.append('')
    fm_lines.append('# Affected Paths')
    paths = fm.get('affected_paths', [])
    if paths:
        fm_lines.append('affected_paths:')
        for p in paths[:3]:
            fm_lines.append(f'  - "{p}"')
    else:
        fm_lines.append('affected_paths: []')

    # Add dependencies
    fm_lines.append('')
    fm_lines.append('# Dependencies (auto-computed)')

    for dep_type in ['depends_on', 'blocks', 'related']:
        vals = deps.get(dep_type, [])
        if vals:
            items = ', '.join(f'"{v}"' for v in vals)
            fm_lines.append(f'{dep_type}: [{items}]')
        else:
            fm_lines.append(f'{dep_type}: []')

    fm_lines.append('---')

    # Rebuild content
    rest = content[end + 5:]
    new_content = '\n'.join(fm_lines) + '\n' + rest

    try:
        with open(issue.filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    except Exception:
        return False

# =============================================================================
# OUTPUT
# =============================================================================

def generate_dot_graph(issues: Dict[str, IssueInfo],
                       dependencies: Dict[str, Dict[str, List[str]]]) -> str:
    """Generate DOT format graph for visualization."""
    lines = [
        'digraph System_Dependencies {',
        '  rankdir=LR;',
        '  node [shape=box];',
        '',
    ]

    # Group by lane
    lanes = defaultdict(list)
    for issue_id, issue in issues.items():
        lanes[issue.lane].append(issue_id)

    for lane, issue_ids in sorted(lanes.items()):
        lines.append(f'  subgraph cluster_{lane} {{')
        lines.append(f'    label="Lane {lane}";')
        for issue_id in sorted(issue_ids):
            status = issues[issue_id].status
            color = 'green' if status == 'RESOLVED' else 'red'
            lines.append(f'    "{issue_id}" [color={color}];')
        lines.append('  }')
        lines.append('')

    # Add edges
    for issue_id, deps in dependencies.items():
        for dep in deps['depends_on']:
            if dep in issues:
                lines.append(f'  "{dep}" -> "{issue_id}" [label="blocks"];')

    lines.append('}')
    return '\n'.join(lines)

def print_summary(issues: Dict[str, IssueInfo],
                  dependencies: Dict[str, Dict[str, List[str]]],
                  order: List[str]) -> None:
    """Print dependency analysis summary."""
    print()
    print("=" * 70)
    print("DEPENDENCY ANALYSIS SUMMARY")
    print("=" * 70)
    print()

    total_deps = sum(len(d['depends_on']) for d in dependencies.values())
    total_blocks = sum(len(d['blocks']) for d in dependencies.values())
    total_related = sum(len(d['related']) for d in dependencies.values())

    print(f"Total Issues:        {len(issues)}")
    print(f"Total Dependencies:  {total_deps}")
    print(f"Total Blocks:        {total_blocks}")
    print(f"Total Related:       {total_related}")
    print()

    # Issues with most dependencies
    print("Issues with Most Dependencies:")
    sorted_by_deps = sorted(
        dependencies.items(),
        key=lambda x: len(x[1]['depends_on']),
        reverse=True
    )[:5]
    for issue_id, deps in sorted_by_deps:
        if deps['depends_on']:
            print(f"  {issue_id}: depends on {deps['depends_on']}")

    print()

    # Issues that block the most
    print("Issues that Block the Most:")
    sorted_by_blocks = sorted(
        dependencies.items(),
        key=lambda x: len(x[1]['blocks']),
        reverse=True
    )[:5]
    for issue_id, deps in sorted_by_blocks:
        if deps['blocks']:
            print(f"  {issue_id}: blocks {deps['blocks'][:3]}...")

    print()

    # Recommended verification order (first 10)
    print("Recommended Verification Order (first 10):")
    for i, issue_id in enumerate(order[:10], 1):
        issue = issues[issue_id]
        status = "\u2705" if issue.status == 'RESOLVED' else "\u274c"
        print(f"  {i}. {issue_id} {status} (severity: {issue.severity})")

    print()

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Compute and update the system issue dependencies'
    )
    parser.add_argument('--update', action='store_true',
                        help='Update issue frontmatter with dependencies')
    parser.add_argument('--lane', '-l', type=str, help='Process single lane')
    parser.add_argument('--graph', action='store_true',
                        help='Output DOT graph to stdout')
    parser.add_argument('--order', action='store_true',
                        help='Output verification order')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)

    args = parser.parse_args()

    print("=" * 70)
    print("Issue Dependencies Analyzer")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load issues
    print("Loading issues...")
    issues = load_all_issues(args.issues_dir, args.lane)
    print(f"Loaded {len(issues)} issues")
    print()

    # Compute dependencies
    print("Computing dependencies...")
    dependencies = compute_dependencies(issues)

    # Compute verification order
    order = get_verification_order(issues, dependencies)

    # Output
    if args.graph:
        print(generate_dot_graph(issues, dependencies))
    elif args.order:
        print("VERIFICATION ORDER:")
        for i, issue_id in enumerate(order, 1):
            issue = issues[issue_id]
            deps = dependencies[issue_id]
            dep_str = f" (after: {', '.join(deps['depends_on'][:2])})" if deps['depends_on'] else ""
            print(f"{i:3}. {issue_id}{dep_str}")
    else:
        print_summary(issues, dependencies, order)

    # Update frontmatter if requested
    if args.update:
        print()
        print("Updating issue frontmatter...")
        updated = 0
        for issue_id, issue in issues.items():
            if update_issue_frontmatter(issue, dependencies[issue_id]):
                updated += 1

        print(f"Updated {updated}/{len(issues)} issues")
        print()
        print("   \u2554" + "\u2550" * 59 + "\u2557")
        print("   \u2551" + " " * 59 + "\u2551")
        print("   \u2551   \u2705  DEPENDENCIES COMPUTED - Frontmatter updated        \u2551")
        print("   \u2551" + " " * 59 + "\u2551")
        print("   \u255a" + "\u2550" * 59 + "\u255d")
    else:
        print()
        print("Run with --update to update issue frontmatter")

    print("=" * 70)

if __name__ == '__main__':
    main()
