#!/usr/bin/env python3
"""
Fix malformed YAML frontmatter in issue files.

Cleans up affected_paths that contain non-path content.
"""

import os
import re
import glob
import yaml

ISSUES_DIR = "issues"

def clean_path(path: str) -> str:
    """Clean a potential file path."""
    # Remove quotes
    path = path.strip().strip('"').strip("'")

    # Skip if it contains problem patterns
    skip_patterns = [
        'python3 -c',
        'import yaml',
        '&&',
        '||',
        'echo',
        'test -',
        'Scope/',
        'Blast radius',
        'Evidence',
        'Source 1',
        'Source 2',
        '**',
        'contains',
        'Description',
    ]

    for pattern in skip_patterns:
        if pattern in path:
            return ""

    # Must look like a path
    if '/' not in path and not path.endswith(('.md', '.py', '.yaml', '.yml', '.json')):
        return ""

    # Remove line numbers
    path = re.sub(r':\d+.*$', '', path)

    # Must be reasonable length
    if len(path) < 3 or len(path) > 100:
        return ""

    return path

def fix_issue_frontmatter(filepath: str) -> bool:
    """Fix frontmatter in a single issue file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False

    if not content.startswith('---'):
        return False

    # Find frontmatter end
    end_match = re.search(r'\n---\n', content[3:])
    if not end_match:
        return False

    end_pos = end_match.start() + 4
    frontmatter_text = content[4:end_pos]
    rest = content[end_pos + 4:]

    # Try to parse
    try:
        fm = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        # Frontmatter is malformed - rebuild it
        fm = rebuild_frontmatter(filepath, content)
        if not fm:
            return False

    # Clean affected_paths
    if 'affected_paths' in fm and isinstance(fm['affected_paths'], list):
        cleaned = []
        for path in fm['affected_paths']:
            if isinstance(path, str):
                clean = clean_path(path)
                if clean:
                    cleaned.append(clean)
        fm['affected_paths'] = cleaned[:3] if cleaned else []

    # Rebuild frontmatter
    new_frontmatter = build_frontmatter(fm)
    new_content = f"---\n{new_frontmatter}---\n{rest}"

    # Verify it parses
    try:
        yaml.safe_load(new_frontmatter)
    except yaml.YAMLError as e:
        print(f"Error: rebuilt frontmatter still invalid for {filepath}: {e}")
        return False

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True

def rebuild_frontmatter(filepath: str, content: str) -> dict:
    """Rebuild frontmatter from content when YAML is malformed."""
    basename = os.path.basename(filepath).replace('.md', '')
    lane = os.path.basename(os.path.dirname(filepath)).upper()

    fm = {
        'issue_id': basename,
        'lane': lane,
        'type_tags': [],
        'severity': 5,
        'severity_level': 'MEDIUM',
        'status': 'OPEN',
        'category': '',
        'user_approval_required': False,
        'verification_pattern': 'missing_file',
        'verification_depth': 'STANDARD',
        'affected_paths': [],
        'depends_on': [],
        'blocks': [],
        'related': [],
    }

    # Extract from content
    # Type tags
    match = re.search(r'type_tags:\s*\[([^\]]+)\]', content)
    if match:
        tags = [t.strip().strip('"') for t in match.group(1).split(',')]
        fm['type_tags'] = tags

    # Severity
    match = re.search(r'severity:\s*(\d+)', content)
    if match:
        fm['severity'] = int(match.group(1))

    match = re.search(r'severity_level:\s*"?(\w+)"?', content)
    if match:
        fm['severity_level'] = match.group(1).upper()

    # Status
    if 'status: "RESOLVED"' in content or 'Status: RESOLVED' in content:
        fm['status'] = 'RESOLVED'

    # Category
    match = re.search(r'category:\s*"?([A-Z])"?', content)
    if match:
        fm['category'] = match.group(1)

    # Related
    match = re.search(r'related:\s*\[([^\]]*)\]', content)
    if match:
        related = [r.strip().strip('"') for r in match.group(1).split(',') if r.strip()]
        fm['related'] = related

    return fm

def build_frontmatter(fm: dict) -> str:
    """Build clean YAML frontmatter from dict."""
    lines = [
        f'issue_id: "{fm.get("issue_id", "")}"',
        f'lane: "{fm.get("lane", "")}"',
    ]

    # Type tags
    tags = fm.get('type_tags', [])
    if tags:
        tags_str = ', '.join(f'"{t}"' for t in tags)
        lines.append(f'type_tags: [{tags_str}]')
    else:
        lines.append('type_tags: []')

    lines.extend([
        f'severity: {fm.get("severity", 5)}',
        f'severity_level: "{fm.get("severity_level", "MEDIUM")}"',
        f'status: "{fm.get("status", "OPEN")}"',
        f'category: "{fm.get("category", "")}"',
        f'user_approval_required: {str(fm.get("user_approval_required", False)).lower()}',
        '',
        '# Verification Configuration',
        f'verification_pattern: "{fm.get("verification_pattern", "missing_file")}"',
        f'verification_depth: "{fm.get("verification_depth", "STANDARD")}"',
    ])

    # Affected paths
    paths = fm.get('affected_paths', [])
    if paths:
        lines.append('')
        lines.append('# Affected Paths')
        lines.append('affected_paths:')
        for path in paths[:3]:
            lines.append(f'  - "{path}"')
    else:
        lines.append('')
        lines.append('# Affected Paths')
        lines.append('affected_paths: []')

    # Dependencies
    lines.extend([
        '',
        '# Dependencies',
        'depends_on: []',
        'blocks: []',
    ])

    # Related
    related = fm.get('related', [])
    if related:
        related_str = ', '.join(f'"{r}"' for r in related)
        lines.append(f'related: [{related_str}]')
    else:
        lines.append('related: []')

    lines.append('')

    return '\n'.join(lines)

def main():
    """Fix all malformed frontmatter."""
    fixed = 0
    errors = 0

    for filepath in glob.glob(os.path.join(ISSUES_DIR, '*', '*.md')):
        if 'TEMPLATE' in filepath.upper():
            continue

        result = fix_issue_frontmatter(filepath)
        if result:
            fixed += 1
        else:
            # Check if it was already OK
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                if content.startswith('---'):
                    end = content.find('\n---\n', 3)
                    if end > 0:
                        yaml.safe_load(content[4:end])
            except:
                errors += 1
                print(f"Could not fix: {filepath}")

    print(f"\nFixed: {fixed} files")
    print(f"Errors: {errors} files")

if __name__ == '__main__':
    main()
