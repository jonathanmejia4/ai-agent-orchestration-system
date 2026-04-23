#!/usr/bin/env python3
"""
Issue Frontmatter Generator

Adds machine-readable YAML frontmatter to all issue files for easier agent parsing.

Features:
- Extracts metadata from existing issue content
- Generates standardized YAML frontmatter
- Preserves original content
- Adds verification pattern references
- Includes dependency tracking fields

Usage:
    python3 tools/add_frontmatter.py              # Dry-run (show what would change)
    python3 tools/add_frontmatter.py --apply      # Apply changes to all files
    python3 tools/add_frontmatter.py --lane G     # Process only Lane G
    python3 tools/add_frontmatter.py --file G-01  # Process single issue
"""

import os
import re
import sys
import glob
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"

# Map Type Tags to verification patterns
TYPE_TAG_TO_PATTERN = {
    "GhostRef": "ghost_reference",
    "MissingFile": "missing_file",
    "MissingDir": "missing_directory",
    "MissingSchema": "json_schema",
    "Stub": "stub_implementation",
    "ConfigError": "yaml_schema",
    "WorkflowGap": "workflow_file",
    "DocDrift": "markdown_doc",
    "PolicyViolation": "policy_alignment",
    "Contradiction": "policy_alignment",
}

# Severity to depth mapping
SEVERITY_TO_DEPTH = {
    "HIGH": "DEEP",
    "MEDIUM": "STANDARD",
    "LOW": "QUICK",
}

# Category descriptions
CATEGORY_DESCRIPTIONS = {
    'A': 'Missing file/artifact',
    'B': 'Structural/Path issues',
    'C': 'Tooling/CI',
    'D': 'Guidelines/Policies',
    'E': 'CI/Workflow gap',
    'F': 'Documentation/LogBook',
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class IssueMetadata:
    """Parsed metadata from an issue file."""
    issue_id: str = ""
    lane: str = ""
    title: str = ""
    type_tags: List[str] = field(default_factory=list)
    severity_score: int = 0
    severity_level: str = "MEDIUM"
    status: str = "OPEN"
    category: str = ""
    category_desc: str = ""
    user_approval: str = "NO"
    date_discovered: str = ""
    date_resolved: str = ""
    verification_pattern: str = ""
    verification_depth: str = "STANDARD"
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    file_paths: List[str] = field(default_factory=list)

# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def extract_issue_id(filepath: str, content: str) -> str:
    """Extract issue ID from filename or content."""
    # Try filename first
    basename = os.path.basename(filepath).replace('.md', '')

    # Check if it matches pattern like G-01, A001, H-31, etc.
    if re.match(r'^[A-Z]-?\d+$', basename):
        return basename

    # Try to extract from content header
    match = re.search(r'#\s*\[LANE\s+([A-Z])\]\s*Issue\s+([A-Z]-?\d+)', content, re.IGNORECASE)
    if match:
        return match.group(2)

    # Try older format: # Issue A001:
    match = re.search(r'#\s*Issue\s+([A-Z]-?\d+)', content, re.IGNORECASE)
    if match:
        return match.group(1)

    return basename

def extract_lane(filepath: str) -> str:
    """Extract lane letter from filepath."""
    parts = filepath.split(os.sep)
    for part in parts:
        if len(part) == 1 and part.isalpha():
            return part.upper()
    return ""

def extract_type_tags(content: str) -> List[str]:
    """Extract type tags from content."""
    match = re.search(r'[-*]\s*Type\s*Tags?:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
    if match:
        tags_str = match.group(1).strip()
        # Remove any bold markers
        tags_str = re.sub(r'\*\*', '', tags_str)
        # Split by comma and clean
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        return tags
    return []

def extract_severity(content: str) -> Tuple[int, str]:
    """Extract severity score and level from content."""
    # Pattern: Severity: 8/10 HIGH
    match = re.search(r'Severity:\s*(\d+)/10\s*(HIGH|MEDIUM|LOW|CRITICAL)', content, re.IGNORECASE)
    if match:
        score = int(match.group(1))
        level = match.group(2).upper()
        if level == 'CRITICAL':
            level = 'HIGH'
        return score, level

    # Pattern without /10: Severity: 8 HIGH
    match = re.search(r'Severity:\s*(\d+)\s*(HIGH|MEDIUM|LOW)', content, re.IGNORECASE)
    if match:
        score = int(match.group(1))
        level = match.group(2).upper()
        return score, level

    return 5, "MEDIUM"

def extract_status(content: str) -> str:
    """Extract status from content."""
    match = re.search(r'[-*]\s*Status:\s*(RESOLVED|OPEN|CLOSED)', content, re.IGNORECASE)
    if match:
        status = match.group(1).upper()
        return 'RESOLVED' if status == 'CLOSED' else status

    # Check for checkmark in header
    if re.search(r'^#\s*\u2705', content):
        return 'RESOLVED'

    return 'OPEN'

def extract_category(content: str) -> Tuple[str, str]:
    """Extract category letter and description."""
    match = re.search(r'Category\s*\(internal\):\s*([A-Z])\s*\(([^)]+)\)', content, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).strip()

    match = re.search(r'Category\s*\(internal\):\s*([A-Z])', content, re.IGNORECASE)
    if match:
        cat = match.group(1).upper()
        return cat, CATEGORY_DESCRIPTIONS.get(cat, "")

    return "", ""

def extract_user_approval(content: str) -> str:
    """Extract user approval setting."""
    match = re.search(r'User\s*Approval:\s*(YES|NO|REQUIRED|RECOMMENDED)', content, re.IGNORECASE)
    if match:
        val = match.group(1).upper()
        if val in ('REQUIRED', 'RECOMMENDED'):
            return 'YES'
        return val
    return 'NO'

def extract_dates(content: str) -> Tuple[str, str]:
    """Extract discovered and resolved dates."""
    discovered = ""
    resolved = ""

    match = re.search(r'Date\s*Discovered:\s*(\d{4}-\d{2}-\d{2})', content, re.IGNORECASE)
    if match:
        discovered = match.group(1)

    match = re.search(r'Date\s*Resolved:\s*(\d{4}-\d{2}-\d{2})', content, re.IGNORECASE)
    if match:
        resolved = match.group(1)

    return discovered, resolved

def extract_related_issues(content: str) -> List[str]:
    """Extract related issue references."""
    related = []

    # Pattern: Related to A001, G-17
    match = re.search(r'Related\s+(?:to|existing\s+issues):\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
    if match:
        refs = re.findall(r'([A-Z]-?\d+)', match.group(1))
        related.extend(refs)

    # Pattern: Cross-References section
    match = re.search(r'Cross-References.*?Related\s+existing\s+issues:\s*(.+?)(?:\n|$)', content, re.IGNORECASE | re.DOTALL)
    if match:
        refs = re.findall(r'([A-Z]-?\d+)', match.group(1))
        related.extend(refs)

    return list(set(related))

def extract_file_paths(content: str) -> List[str]:
    """Extract file paths mentioned in the issue."""
    paths = []

    # Common path patterns
    patterns = [
        r'`([^`]+\.(py|yaml|yml|json|md|sh|rst))`',  # Backtick paths
        r'`([^`]+/[^`]+)`',  # Any path with /
        r'Referenced\s+path:\s*`?([^\s`]+)`?',  # Referenced path field
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            if isinstance(match, tuple):
                path = match[0]
            else:
                path = match
            # Filter out obvious non-paths
            if '/' in path and not path.startswith('http'):
                paths.append(path)

    return list(set(paths))[:5]  # Limit to 5 most relevant

def determine_verification_pattern(type_tags: List[str]) -> str:
    """Determine best verification pattern based on type tags."""
    for tag in type_tags:
        if tag in TYPE_TAG_TO_PATTERN:
            return TYPE_TAG_TO_PATTERN[tag]
    return "missing_file"  # Default pattern

def parse_issue_file(filepath: str) -> Optional[IssueMetadata]:
    """Parse an issue file and extract all metadata."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return None

    # Skip if already has frontmatter
    if content.startswith('---'):
        return None

    # Skip template file
    if 'TEMPLATE' in filepath.upper():
        return None

    metadata = IssueMetadata()

    metadata.issue_id = extract_issue_id(filepath, content)
    metadata.lane = extract_lane(filepath)
    metadata.type_tags = extract_type_tags(content)
    metadata.severity_score, metadata.severity_level = extract_severity(content)
    metadata.status = extract_status(content)
    metadata.category, metadata.category_desc = extract_category(content)
    metadata.user_approval = extract_user_approval(content)
    metadata.date_discovered, metadata.date_resolved = extract_dates(content)
    metadata.related = extract_related_issues(content)
    metadata.file_paths = extract_file_paths(content)

    # Derived fields
    metadata.verification_pattern = determine_verification_pattern(metadata.type_tags)
    metadata.verification_depth = SEVERITY_TO_DEPTH.get(metadata.severity_level, "STANDARD")

    # Extract title from header
    match = re.search(r'^#\s*.+?Issue\s+[A-Z]-?\d+[:\s]*(.+?)$', content, re.MULTILINE)
    if match:
        metadata.title = match.group(1).strip()

    return metadata

# =============================================================================
# FRONTMATTER GENERATION
# =============================================================================

def generate_frontmatter(metadata: IssueMetadata) -> str:
    """Generate YAML frontmatter from metadata."""
    lines = [
        '---',
        f'issue_id: "{metadata.issue_id}"',
        f'lane: "{metadata.lane}"',
    ]

    # Type tags as array
    if metadata.type_tags:
        tags_str = ', '.join(f'"{t}"' for t in metadata.type_tags)
        lines.append(f'type_tags: [{tags_str}]')
    else:
        lines.append('type_tags: []')

    # Severity
    lines.append(f'severity: {metadata.severity_score}')
    lines.append(f'severity_level: "{metadata.severity_level}"')

    # Status
    lines.append(f'status: "{metadata.status}"')

    # Category
    if metadata.category:
        lines.append(f'category: "{metadata.category}"')

    # User approval
    lines.append(f'user_approval_required: {str(metadata.user_approval == "YES").lower()}')

    # Dates
    if metadata.date_discovered:
        lines.append(f'date_discovered: "{metadata.date_discovered}"')
    if metadata.date_resolved:
        lines.append(f'date_resolved: "{metadata.date_resolved}"')

    # Verification
    lines.append('')
    lines.append('# Verification Configuration')
    lines.append(f'verification_pattern: "{metadata.verification_pattern}"')
    lines.append(f'verification_depth: "{metadata.verification_depth}"')

    # File paths (limited)
    if metadata.file_paths:
        lines.append('')
        lines.append('# Affected Paths')
        lines.append('affected_paths:')
        for path in metadata.file_paths[:3]:
            lines.append(f'  - "{path}"')

    # Dependencies (empty by default - to be filled)
    lines.append('')
    lines.append('# Dependencies (fill in during analysis)')
    lines.append('depends_on: []')
    lines.append('blocks: []')

    # Related issues
    if metadata.related:
        related_str = ', '.join(f'"{r}"' for r in metadata.related)
        lines.append(f'related: [{related_str}]')
    else:
        lines.append('related: []')

    lines.append('---')
    lines.append('')

    return '\n'.join(lines)

def add_frontmatter_to_file(filepath: str, dry_run: bool = True) -> bool:
    """Add frontmatter to a single issue file."""
    metadata = parse_issue_file(filepath)

    if metadata is None:
        return False

    frontmatter = generate_frontmatter(metadata)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return False

    new_content = frontmatter + original_content

    if dry_run:
        print(f"\n{'='*60}")
        print(f"FILE: {filepath}")
        print(f"{'='*60}")
        print("FRONTMATTER TO ADD:")
        print(frontmatter)
        print("-" * 40)
        return True

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    except Exception as e:
        print(f"Error writing {filepath}: {e}", file=sys.stderr)
        return False

# =============================================================================
# BATCH PROCESSING
# =============================================================================

def process_all_issues(issues_dir: str, lane: Optional[str] = None,
                       issue_id: Optional[str] = None, dry_run: bool = True) -> Dict[str, int]:
    """Process all issue files and add frontmatter."""
    stats = {
        'processed': 0,
        'skipped': 0,
        'errors': 0,
        'already_has_frontmatter': 0,
    }

    if issue_id:
        # Single file mode
        lane_letter = issue_id[0].upper()
        pattern = os.path.join(issues_dir, lane_letter, f"{issue_id}.md")
        files = glob.glob(pattern)
        if not files:
            # Try with hyphen
            pattern = os.path.join(issues_dir, lane_letter, f"{lane_letter}-{issue_id[1:]}.md")
            files = glob.glob(pattern)
    elif lane:
        # Single lane mode
        pattern = os.path.join(issues_dir, lane.upper(), '*.md')
        files = glob.glob(pattern)
    else:
        # All files mode
        pattern = os.path.join(issues_dir, '*', '*.md')
        files = glob.glob(pattern)

    # Filter out templates
    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    print(f"\n{'='*70}")
    print(f"the system ISSUE FRONTMATTER GENERATOR")
    print(f"{'='*70}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLYING CHANGES'}")
    print(f"Files to process: {len(files)}")
    print(f"{'='*70}\n")

    for filepath in sorted(files):
        # Check if already has frontmatter
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                first_line = f.readline()
            if first_line.strip() == '---':
                stats['already_has_frontmatter'] += 1
                if not dry_run:
                    continue
                print(f"SKIP (has frontmatter): {filepath}")
                continue
        except Exception:
            stats['errors'] += 1
            continue

        success = add_frontmatter_to_file(filepath, dry_run)

        if success:
            stats['processed'] += 1
        else:
            stats['skipped'] += 1

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Files processed:           {stats['processed']}")
    print(f"Files skipped:             {stats['skipped']}")
    print(f"Already has frontmatter:   {stats['already_has_frontmatter']}")
    print(f"Errors:                    {stats['errors']}")
    print(f"{'='*70}\n")

    if dry_run and stats['processed'] > 0:
        print("To apply changes, run with --apply flag")

    return stats

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Add YAML frontmatter to the system issue files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--apply', action='store_true',
                        help='Apply changes (default is dry-run)')
    parser.add_argument('--lane', '-l', type=str,
                        help='Process only specified lane (e.g., G, H, A)')
    parser.add_argument('--file', '-f', type=str,
                        help='Process single issue file (e.g., G-01, A001)')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR,
                        help=f'Issues directory (default: {ISSUES_DIR})')

    args = parser.parse_args()

    if not os.path.isdir(args.issues_dir):
        print(f"Error: Issues directory not found: {args.issues_dir}", file=sys.stderr)
        sys.exit(1)

    dry_run = not args.apply

    stats = process_all_issues(
        args.issues_dir,
        lane=args.lane,
        issue_id=args.file,
        dry_run=dry_run
    )

    if stats['errors'] > 0:
        sys.exit(1)

    sys.exit(0)

if __name__ == '__main__':
    main()
