#!/usr/bin/env python3
"""
Fix Implementation Checklist Generator

Converts prose fix requirements into executable step-by-step checklists.
Generates bash commands for each fix step that agents can execute.

Usage:
    python3 tools/add_fix_checklist.py              # Dry run
    python3 tools/add_fix_checklist.py --apply      # Apply to all
    python3 tools/add_fix_checklist.py --lane G     # Single lane
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

# Fix action templates by pattern
FIX_TEMPLATES = {
    'create_directory': {
        'pattern': r'create\s+(?:directory|dir|folder)[:.]?\s*`?([^\s`\n,]+)`?',
        'steps': [
            ('Create directory', 'mkdir -p {path}'),
            ('Create README', 'echo "# {dirname}\\n\\nDirectory for {purpose}" > {path}/README.md'),
            ('Verify', 'test -d {path} && echo "CREATED" || echo "FAILED"'),
        ]
    },
    'create_file': {
        'pattern': r'create\s+(?:file)[:.]?\s*`?([^\s`\n,]+\.(md|yaml|yml|json|py))`?',
        'steps': [
            ('Create file', 'touch {path}'),
            ('Add header', 'echo "# {filename}\\n\\nTODO: Add content" > {path}'),
            ('Verify', 'test -f {path} && echo "CREATED" || echo "FAILED"'),
        ]
    },
    'create_schema': {
        'pattern': r'create\s+(?:schema)[:.]?\s*`?([^\s`\n,]+\.(yaml|yml|json))`?',
        'steps': [
            ('Create schema file', 'touch {path}'),
            ('Add schema template', 'echo "$schema: http://json-schema.org/draft-07/schema#\\ntype: object\\nproperties: {{}}" > {path}'),
            ('Verify valid', 'python3 -c "import yaml; yaml.safe_load(open(\'{path}\'))" && echo "VALID" || echo "INVALID"'),
        ]
    },
    'add_import': {
        'pattern': r'add\s+(?:import|reference).*?`?([^\s`\n]+)`?\s+(?:to|in)\s+`?([^\s`\n]+)`?',
        'steps': [
            ('Backup file', 'cp {target} {target}.bak'),
            ('Add import (manual)', '# Edit {target} to add import for {import_name}'),
            ('Verify syntax', 'python3 -m py_compile {target} && echo "VALID" || echo "INVALID"'),
        ]
    },
    'update_reference': {
        'pattern': r'update\s+(?:reference|path).*?from\s+`?([^\s`\n]+)`?\s+to\s+`?([^\s`\n]+)`?',
        'steps': [
            ('Find occurrences', 'grep -r "{old_path}" --include="*.md" --include="*.yaml" .'),
            ('Update (manual)', '# Replace {old_path} with {new_path}'),
            ('Verify', 'grep -r "{new_path}" --include="*.md" .'),
        ]
    },
}

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

def extract_fix_requirements(content: str) -> List[str]:
    """Extract fix requirements from issue content."""
    requirements = []

    # Find Fix Requirements section
    match = re.search(r'\*\*Detailed Fix Requirements.*?\*\*(.*?)(?:\*\*Verification|\*\*Cross-References|\*\*Dedup|---)', content, re.DOTALL)
    if not match:
        return requirements

    section = match.group(1)

    # Extract bullet points
    for line in section.split('\n'):
        line = line.strip()
        if line.startswith('- ') and len(line) > 10:
            # Skip meta items
            if any(skip in line.lower() for skip in ['acceptance criteria', 'integration points', 'validation plan', 'fix objective']):
                continue
            requirements.append(line[2:].strip())

    return requirements

def extract_affected_paths(frontmatter: Dict, content: str) -> List[str]:
    """Get paths from frontmatter and content."""
    paths = frontmatter.get('affected_paths', [])

    # Also extract from content
    for match in re.finditer(r'`([^`]+/[^`]+)`', content):
        path = match.group(1)
        path = re.sub(r':\d+.*$', '', path)
        if len(path) > 3 and path not in paths:
            paths.append(path)

    return paths[:5]

# =============================================================================
# CHECKLIST GENERATION
# =============================================================================

def determine_fix_type(requirement: str) -> Tuple[str, Dict]:
    """Determine fix type and extract variables from requirement."""
    req_lower = requirement.lower()

    if 'create' in req_lower and ('directory' in req_lower or 'dir' in req_lower or 'folder' in req_lower):
        match = re.search(r'`([^`]+/[^`]+)`', requirement)
        if match:
            path = match.group(1).rstrip('/')
            return 'create_directory', {
                'path': path,
                'dirname': os.path.basename(path),
                'purpose': 'a system component'
            }

    if 'create' in req_lower and ('file' in req_lower or 'readme' in req_lower):
        match = re.search(r'`([^`]+\.(md|yaml|yml|json|py))`', requirement)
        if match:
            path = match.group(1)
            return 'create_file', {
                'path': path,
                'filename': os.path.basename(path)
            }

    if 'create' in req_lower and 'schema' in req_lower:
        match = re.search(r'`([^`]+\.(yaml|yml|json))`', requirement)
        if match:
            return 'create_schema', {'path': match.group(1)}

    if 'add' in req_lower and ('import' in req_lower or 'reference' in req_lower):
        return 'add_import', {'import_name': 'unknown', 'target': 'unknown'}

    if 'update' in req_lower and ('reference' in req_lower or 'path' in req_lower):
        return 'update_reference', {'old_path': 'OLD', 'new_path': 'NEW'}

    # Default: generic step
    return 'generic', {'description': requirement}

def generate_checklist(requirements: List[str], paths: List[str], issue_id: str) -> str:
    """Generate fix implementation checklist."""
    if not requirements:
        return ""

    lines = [
        "",
        "**Fix Implementation Checklist**",
        "",
        f"*Issue: {issue_id}*",
        "",
    ]

    step_num = 1

    for req in requirements[:5]:  # Limit to 5 requirements
        fix_type, variables = determine_fix_type(req)

        if fix_type == 'create_directory' and 'path' in variables:
            path = variables['path']
            dirname = variables.get('dirname', 'Directory')
            lines.extend([
                f"- [ ] **Step {step_num}: Create directory `{path}`**",
                "  ```bash",
                f"  mkdir -p {path}",
                f"  echo '# {dirname}' > {path}/README.md",
                "  ```",
                f"  *Verify:* `test -d {path} && echo OK`",
                "",
            ])
            step_num += 1

        elif fix_type == 'create_file' and 'path' in variables:
            path = variables['path']
            filename = variables.get('filename', 'File')
            lines.extend([
                f"- [ ] **Step {step_num}: Create file `{path}`**",
                "  ```bash",
                f"  touch {path}",
                f"  echo '# {filename}' > {path}",
                "  ```",
                f"  *Verify:* `test -f {path} && echo OK`",
                "",
            ])
            step_num += 1

        elif fix_type == 'create_schema' and 'path' in variables:
            path = variables['path']
            lines.extend([
                f"- [ ] **Step {step_num}: Create schema `{path}`**",
                "  ```bash",
                f"  cat > {path} << 'EOF'",
                "  $schema: http://json-schema.org/draft-07/schema#",
                "  type: object",
                "  properties:",
                "    # Add properties here",
                "  EOF",
                "  ```",
                f"  *Verify:* `python3 -c \"import yaml; yaml.safe_load(open('{path}'))\" && echo OK`",
                "",
            ])
            step_num += 1

        else:
            # Generic step
            lines.extend([
                f"- [ ] **Step {step_num}: {req[:60]}{'...' if len(req) > 60 else ''}**",
                "  ```bash",
                "  # Manual implementation required",
                f"  # {req}",
                "  ```",
                "",
            ])
            step_num += 1

    # Add final verification step
    if paths:
        primary_path = paths[0]
        lines.extend([
            f"- [ ] **Step {step_num}: Final verification**",
            "  ```bash",
            f"  python3 tools/verify_issue.py {issue_id}",
            "  ```",
            f"  *Expected:* All checks PASS",
            "",
        ])

    return '\n'.join(lines)

def has_fix_checklist(content: str) -> bool:
    """Check if content already has fix checklist."""
    return '**Fix Implementation Checklist**' in content

def insert_fix_checklist(content: str, checklist: str) -> str:
    """Insert fix checklist into content."""
    # Insert after Verification Commands section
    match = re.search(r'(\*\*Quick Verification\*\*.*?```\n)', content, re.DOTALL)
    if match:
        insert_pos = match.end()
        return content[:insert_pos] + '\n' + checklist + content[insert_pos:]

    # Insert before Cross-References
    match = re.search(r'(\n)(\*\*Cross-References)', content)
    if match:
        return content[:match.start(1)] + '\n' + checklist + content[match.start(1):]

    # Insert before Dedup
    match = re.search(r'(\n)(\*\*Dedup)', content)
    if match:
        return content[:match.start(1)] + '\n' + checklist + content[match.start(1):]

    return content

# =============================================================================
# PROCESSING
# =============================================================================

def process_issue(filepath: str, dry_run: bool = True) -> Tuple[bool, str]:
    """Process a single issue file."""
    frontmatter, content = parse_frontmatter(filepath)

    if not frontmatter:
        return False, "No frontmatter"

    if has_fix_checklist(content):
        return False, "Already has checklist"

    # Only add to OPEN issues
    if frontmatter.get('status', '') == 'RESOLVED':
        return False, "Issue resolved (skip)"

    # Extract requirements
    requirements = extract_fix_requirements(content)
    if not requirements:
        return False, "No fix requirements found"

    # Get paths
    paths = extract_affected_paths(frontmatter, content)

    # Generate checklist
    issue_id = frontmatter.get('issue_id', os.path.basename(filepath).replace('.md', ''))
    checklist = generate_checklist(requirements, paths, issue_id)

    if not checklist:
        return False, "Could not generate checklist"

    if dry_run:
        return True, f"Would add {len(requirements)} step checklist"

    # Insert checklist
    new_content = insert_fix_checklist(content, checklist)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True, f"Added {len(requirements)} step checklist"
    except Exception as e:
        return False, f"Write error: {e}"

def process_all(issues_dir: str, lane: str = None, dry_run: bool = True) -> Dict[str, int]:
    """Process all issues."""
    stats = {'processed': 0, 'skipped': 0, 'resolved': 0, 'errors': 0}

    if lane:
        files = glob.glob(os.path.join(issues_dir, lane.upper(), '*.md'))
    else:
        files = glob.glob(os.path.join(issues_dir, '*', '*.md'))

    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    print("=" * 70)
    print("the system FIX CHECKLIST GENERATOR")
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
        elif 'resolved' in message.lower():
            stats['resolved'] += 1
        elif 'Already' in message:
            stats['skipped'] += 1
        else:
            stats['errors'] += 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Checklists added:  {stats['processed']}")
    print(f"Already had:       {stats['skipped']}")
    print(f"Resolved (skip):   {stats['resolved']}")
    print(f"Errors:            {stats['errors']}")

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
        description='Add fix implementation checklists to the system issues'
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
