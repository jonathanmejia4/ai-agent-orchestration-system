#!/usr/bin/env python3
"""
the system Issue Catalog Restructuring Tool

Extracts issues from the monolithic ISSUE_CATALOG.md into individual files
organized by lane/category, creating a slim catalog with summaries and links.

Features:
- Strict pattern matching (prevents false splits)
- Backup creation before any changes
- Progress display during extraction
- Validation and summary report
- Dry-run mode for safe testing
- Safe by default: skips existing files unless --force is used

Usage:
    python3 tools/restructure_catalog.py --dry-run    # Test without writing
    python3 tools/restructure_catalog.py --lane G     # Extract only Lane G
    python3 tools/restructure_catalog.py              # Safe: only writes NEW files
    python3 tools/restructure_catalog.py --force      # DESTRUCTIVE: overwrites all files
"""

import os
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# =============================================================================
# CONFIGURATION
# =============================================================================

CATALOG_PATH = "ISSUE_CATALOG.md"
BACKUP_PATH = "ISSUE_CATALOG_BACKUP.md"
ISSUES_DIR = "issues"
NEW_CATALOG_PATH = "ISSUE_CATALOG_NEW.md"

# Strict regex patterns - ONLY match exact issue headers
# Lane issues can use ## or ### prefix
# Captures: (1) lane letter, (2) lane in issue ID, (3) number, (4) optional title after colon
LANE_ISSUE_PATTERN = re.compile(r'^#{2,3} \[LANE ([A-Z])\] Issue ([A-Z])-(\d+):?\s*(.*)')
CAT_A_ISSUE_PATTERN = re.compile(r'^### (A)(\d+):?\s*(.*)')
# Slim format pattern for restructured catalog: ### X-NN: Title (where X is B-Z)
# Captures: (1) lane letter, (2) number, (3) title
SLIM_LANE_PATTERN = re.compile(r'^### ([B-Z])-(\d+):?\s*(.*)')

# Expected issue counts per lane (for validation)
# Note: These are UNIQUE issue counts (after deduplication)
EXPECTED_COUNTS = {
    'A': 358,   # Category A issues (unique, not counting duplicates)
    'E': 0,     # Customer Services & Data Protection (NEW lane)
    'G': 70,
    'H': 40,    # Updated based on actual count
    'I': 50,
    'J': 50,
    'K': 40,    # Updated based on actual count
    'L': 30,
    'M': 10,
    'N': 10,
    'O': 10,
    'P': 10,
    'Q': 10,
    'R': 10,
    'S': 10,
    'T': 10,
    'U': 10,
    'V': 10,
    'W': 10,
    'X': 10,
    'Y': 10,
    'Z': 10,
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Issue:
    """Represents a single issue extracted from the catalog."""
    lane: str           # 'A', 'G', 'J', etc.
    number: str         # '001', '01', etc.
    title: str          # Issue title
    severity: str       # 'HIGH', 'MEDIUM', 'LOW'
    status: str         # 'OPEN', 'RESOLVED'
    type_tags: str      # 'GhostRef, MissingDir'
    summary: str        # 1-2 line summary
    full_content: str   # Complete issue content
    start_line: int     # Line number in original file
    end_line: int       # Line number where issue ends
    date_discovered: str = ""  # Date issue was discovered (YYYY-MM-DD)
    date_resolved: str = ""    # Date issue was resolved (YYYY-MM-DD)

# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def parse_catalog(filepath: str) -> Tuple[List[Issue], str, str]:
    """
    Parse the catalog file and extract all issues.

    Returns:
        - List of Issue objects
        - Header content (before first issue)
        - Footer content (after last issue)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    issues = []
    header_lines = []
    current_issue_lines = []
    current_issue_start = None
    current_issue_meta = None  # (lane, number)
    in_header = True

    print(f"📖 Parsing {len(lines):,} lines...")

    for i, line in enumerate(lines):
        # Check for issue patterns (old format, Category A format, and slim format)
        lane_match = LANE_ISSUE_PATTERN.match(line)
        cat_a_match = CAT_A_ISSUE_PATTERN.match(line)
        slim_match = SLIM_LANE_PATTERN.match(line)

        if lane_match or cat_a_match or slim_match:
            # Save previous issue if exists
            if current_issue_meta and current_issue_lines:
                issue = create_issue_from_lines(
                    current_issue_meta[0],
                    current_issue_meta[1],
                    current_issue_meta[2] if len(current_issue_meta) > 2 else "",
                    current_issue_lines,
                    current_issue_start,
                    i - 1
                )
                if issue:
                    issues.append(issue)

            in_header = False
            current_issue_start = i
            current_issue_lines = [line]

            if lane_match:
                # Old format: ## [LANE X] Issue X-NN: Title
                lane = lane_match.group(1)
                num = lane_match.group(3)
                header_title = lane_match.group(4).strip() if lane_match.group(4) else ""
                current_issue_meta = (lane, num, header_title)
            elif slim_match:
                # Slim format: ### X-NN: Title (lanes B-Z)
                lane = slim_match.group(1)
                num = slim_match.group(2)
                header_title = slim_match.group(3).strip() if slim_match.group(3) else ""
                current_issue_meta = (lane, num, header_title)
            else:
                # Category A format: ### A001: Title
                lane = 'A'
                num = cat_a_match.group(2)
                header_title = cat_a_match.group(3).strip() if cat_a_match.group(3) else ""
                current_issue_meta = (lane, num, header_title)

        elif in_header:
            header_lines.append(line)

        elif current_issue_meta:
            # Skip catalog-only content that shouldn't be in individual files
            # These [Full Details] links cause 404s when inside issue files
            if not line.strip().startswith('→ [Full Details](issues/'):
                current_issue_lines.append(line)

    # Don't forget the last issue
    if current_issue_meta and current_issue_lines:
        issue = create_issue_from_lines(
            current_issue_meta[0],
            current_issue_meta[1],
            current_issue_meta[2] if len(current_issue_meta) > 2 else "",
            current_issue_lines,
            current_issue_start,
            len(lines) - 1
        )
        if issue:
            issues.append(issue)

    header = ''.join(header_lines)

    return issues, header, ""

def clean_title(raw_title: str, max_length: int = 70) -> str:
    """
    Clean up a title: remove backticks, markdown, truncate at word boundary.
    """
    if not raw_title:
        return ""

    title = raw_title

    # Remove backticks and their contents, replace with clean text
    # e.g., "File `PLANNING/foo.md` is missing" -> "File PLANNING/foo.md is missing"
    title = re.sub(r'`([^`]*)`', r'\1', title)

    # Remove other markdown formatting
    title = re.sub(r'\*\*([^*]*)\*\*', r'\1', title)  # Bold
    title = re.sub(r'\*([^*]*)\*', r'\1', title)      # Italic

    # Clean up multiple spaces
    title = re.sub(r'\s+', ' ', title).strip()

    # Truncate at word boundary if too long
    if len(title) > max_length:
        truncated = title[:max_length].rsplit(' ', 1)[0]
        # Make sure we didn't cut too much
        if len(truncated) < max_length * 0.5:
            truncated = title[:max_length]
        title = truncated.rstrip('.,;:') + '...'

    return title

def extract_summary(content: str) -> str:
    """
    Extract a meaningful summary from issue content.
    Priority: Scope/Blast radius > Immediate impact > first line of Problem Description
    """
    # Try "Scope/Blast radius" first
    scope = extract_field(content, r'Scope/Blast radius:\s*(.+?)(?:\n|$)')
    if scope and len(scope) > 10:
        return clean_title(scope, 150)

    # Try "Immediate impact"
    impact = extract_field(content, r'Immediate impact:\s*(.+?)(?:\n|$)')
    if impact and len(impact) > 10:
        return clean_title(impact, 150)

    # Try "Downstream impact"
    downstream = extract_field(content, r'Downstream impact[^:]*:\s*(.+?)(?:\n|$)')
    if downstream and len(downstream) > 10:
        return clean_title(downstream, 150)

    # Fallback to "Problem:" section for Category A
    problem = extract_field(content, r'\*\*Problem:\*\*\s*\n(.+?)(?:\n\n|\*\*)')
    if problem and len(problem) > 10:
        return clean_title(problem.split('\n')[0], 150)

    return ""

def extract_dates(content: str) -> Tuple[str, str]:
    """
    Extract date discovered and date resolved from content.
    Returns (discovered, resolved) tuple.
    """
    discovered = extract_field(content, r'Date Discovered:\s*(\d{4}-\d{2}-\d{2})')
    resolved = extract_field(content, r'Date Resolved:\s*(\d{4}-\d{2}-\d{2})')
    return discovered, resolved

def create_issue_from_lines(lane: str, number: str, header_title: str,
                            lines: List[str], start_line: int, end_line: int) -> Optional[Issue]:
    """Create an Issue object from extracted lines."""
    content = ''.join(lines)
    first_line = lines[0].strip() if lines else ""

    # Extract title based on format
    title = ""

    if lane == 'A':
        # Category A format: ### A1: Title Here
        # Use header_title if provided, otherwise extract from line
        if header_title:
            title = header_title
        else:
            title_match = re.search(r'^#{2,3}\s*A\d+:\s*(.+)$', first_line)
            if title_match:
                title = title_match.group(1).strip()
    else:
        # Lane issue format: ## [LANE X] Issue X-NN: Optional Title
        # First try header title (some issues have titles on the header line)
        if header_title:
            title = header_title
        else:
            # Try to extract from "What is wrong (precise):" field
            what_wrong = extract_field(content, r'What is wrong \(precise\):\s*(.+?)(?:\n|$)')
            if what_wrong:
                title = what_wrong

            # Fallback: try "Problem Description" section
            if not title:
                problem_match = re.search(r'\*\*Problem Description\*\*\s*\n-?\s*(.+?)(?:\n|$)', content)
                if problem_match:
                    title = problem_match.group(1).strip()

    # Clean the title (remove backticks, truncate properly)
    title = clean_title(title, 70)

    # Extract other metadata
    severity = extract_field(content, r'Severity[:\s]*(\d+/10|\w+)')
    if not severity:
        severity = extract_field(content, r'\*\*Severity[^:]*:\*\*\s*(\w+)')

    status = extract_field(content, r'Status[:\s]*(\w+)')
    if not status:
        status = extract_field(content, r'\*\*Status:\*\*\s*[✅❌]?\s*(\w+)')

    type_tags = extract_field(content, r'Type Tags?[:\s]*(.+?)(?:\n|$)')

    # Generate summary from different field than title
    summary = extract_summary(content)

    # Extract dates
    date_discovered, date_resolved = extract_dates(content)

    # Clean up severity (extract just HIGH/MEDIUM/LOW)
    # First check the full severity line for keywords (handles "7/10 HIGH" format)
    severity_line = extract_field(content, r'Severity[:\s]*(.+?)(?:\n|$)')
    if severity_line:
        severity_upper = severity_line.upper()
        if 'HIGH' in severity_upper or '🔴' in severity_line:
            severity = 'HIGH'
        elif 'LOW' in severity_upper or '🟢' in severity_line:
            severity = 'LOW'
        elif 'MEDIUM' in severity_upper or '🟡' in severity_line:
            severity = 'MEDIUM'
        # Fallback to numeric rating
        elif '8/10' in severity_line or '9/10' in severity_line or '10/10' in severity_line:
            severity = 'HIGH'
        elif '7/10' in severity_line or '6/10' in severity_line or '5/10' in severity_line:
            severity = 'MEDIUM'
        elif '1/10' in severity_line or '2/10' in severity_line or '3/10' in severity_line or '4/10' in severity_line:
            severity = 'LOW'
        else:
            severity = 'MEDIUM'
    else:
        severity = 'MEDIUM'

    # Clean up status
    if status:
        status = status.upper()
        if 'RESOLVED' in status or 'COMPLETE' in status:
            status = 'RESOLVED'
        else:
            status = 'OPEN'
    else:
        status = 'OPEN'

    if not type_tags:
        type_tags = ''
    else:
        # Clean up type tags
        type_tags = clean_title(type_tags, 100)

    return Issue(
        lane=lane,
        number=number.zfill(2) if lane != 'A' else number.zfill(3),
        title=title if title else f"Issue {lane}-{number}",
        severity=severity,
        status=status,
        type_tags=type_tags,
        summary=summary,
        full_content=content,
        start_line=start_line,
        end_line=end_line,
        date_discovered=date_discovered,
        date_resolved=date_resolved
    )

def extract_field(content: str, pattern: str) -> str:
    """Extract a field value using regex."""
    match = re.search(pattern, content, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def generate_summary(content: str, title: str) -> str:
    """Generate a 1-2 line summary from issue content."""
    # Try to find Evidence or Summary section
    evidence_match = re.search(r'\*\*Evidence:\*\*\s*\n(.+?)(?:\n\n|\*\*)', content, re.DOTALL)
    if evidence_match:
        evidence = evidence_match.group(1).strip()
        # Get first line of evidence
        first_line = evidence.split('\n')[0].strip()
        if first_line.startswith('-'):
            first_line = first_line[1:].strip()
        return first_line[:200]

    # Fallback to title
    return title if title else ""

# =============================================================================
# FILE OPERATIONS
# =============================================================================

def create_backup(src: str, dst: str) -> bool:
    """Create a backup of the original catalog."""
    try:
        shutil.copy2(src, dst)
        size = os.path.getsize(dst) / (1024 * 1024)
        print(f"💾 Backup created: {dst} ({size:.2f} MB)")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def create_folder_structure(lanes: List[str], dry_run: bool = False) -> bool:
    """Create the issues/ folder structure."""
    try:
        if not dry_run:
            os.makedirs(ISSUES_DIR, exist_ok=True)

        for lane in lanes:
            lane_dir = os.path.join(ISSUES_DIR, lane)
            if not dry_run:
                os.makedirs(lane_dir, exist_ok=True)
            print(f"  📁 {'Would create' if dry_run else 'Created'}: {lane_dir}/")

        return True
    except Exception as e:
        print(f"❌ Folder creation failed: {e}")
        return False

def write_issue_file(issue: Issue, dry_run: bool = False, force: bool = False) -> str:
    """
    Write a single issue to its own file.

    Returns:
        'written' - file was written
        'skipped' - file exists and force=False
        'failed'  - write error occurred
    """
    # Determine filename
    if issue.lane == 'A':
        filename = f"A{issue.number}.md"
    else:
        filename = f"{issue.lane}-{issue.number}.md"

    filepath = os.path.join(ISSUES_DIR, issue.lane, filename)

    # Check if file already exists
    if os.path.exists(filepath) and not force:
        return 'skipped'

    if dry_run:
        return 'written'

    try:
        # Format the issue content with proper header
        formatted_content = format_issue_file(issue)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted_content)

        return 'written'
    except Exception as e:
        print(f"❌ Failed to write {filepath}: {e}")
        return False

def format_issue_file(issue: Issue) -> str:
    """Format an issue for its standalone file."""
    content = issue.full_content

    # Check if content already has a proper header
    if content.strip().startswith('###'):
        # Convert ### to # for standalone file
        content = re.sub(r'^###\s*', '# ', content, count=1)

    # Normalize Category A format to Lane format if needed
    if issue.lane == 'A':
        content = normalize_category_a(issue, content)

    # Apply post-processing fixes
    content = post_process_issue_content(content, issue)

    return content

def post_process_issue_content(content: str, issue: Issue) -> str:
    """
    Apply post-processing fixes to issue content:
    1. Normalize bold field format to dash format
    2. Auto-check acceptance boxes for RESOLVED issues
    3. Ensure closing separator exists
    4. Add N/A placeholders for empty sections
    """
    lines = content.split('\n')
    result = []

    for i, line in enumerate(lines):
        # Fix 1: Normalize **Field**: to - Field: format (for H-31+ style)
        if line.startswith('- **') and '**:' in line:
            # - **Type Tags**: value  →  - Type Tags: value
            line = re.sub(r'^- \*\*([^*]+)\*\*:\s*', r'- \1: ', line)

        # Fix 2: Auto-check acceptance boxes for RESOLVED issues
        if issue.status == 'RESOLVED' and re.match(r'^\s*- \[ \]', line):
            line = re.sub(r'^(\s*)- \[ \]', r'\1- [x]', line)

        result.append(line)

    content = '\n'.join(result)

    # Fix 3: Ensure closing separator exists
    if not content.rstrip().endswith('---'):
        content = content.rstrip() + '\n\n---\n'

    # Fix 4: Add N/A for empty required sections
    required_sections = [
        ('**Problem Description**', '- What is wrong (precise): See issue title'),
        ('**Evidence**', '- Source: See related files'),
        ('**Impact Analysis**', '- Immediate impact: See problem description'),
    ]

    for section_header, placeholder in required_sections:
        if section_header in content:
            # Check if section is empty (followed immediately by another section or end)
            pattern = re.escape(section_header) + r'\n\s*\n(\*\*|---|\Z)'
            if re.search(pattern, content):
                content = re.sub(
                    pattern,
                    section_header + '\n' + placeholder + '\n\n\\1',
                    content
                )

    return content

def split_multi_issue_file(filepath: str) -> List[Tuple[str, str]]:
    """
    Split a file containing multiple issues into separate contents.

    Returns list of (issue_id, content) tuples.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to detect issue headers within the file
    # Matches: ### ✅ A62: Title or ### A62: Title
    issue_pattern = re.compile(r'^(###\s*[✅❌]?\s*A\d+:.+)$', re.MULTILINE)

    matches = list(issue_pattern.finditer(content))

    if len(matches) <= 1:
        return []  # Single issue or no issues found

    issues = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)

        issue_content = content[start:end].strip()

        # Extract issue ID from header
        header = match.group(1)
        id_match = re.search(r'A(\d+):', header)
        if id_match:
            issue_id = f"A{id_match.group(1).zfill(3)}"
            issues.append((issue_id, issue_content))

    return issues

def fix_multi_issue_files(issues_dir: str) -> Dict[str, int]:
    """
    Find and split files containing multiple issues.

    Returns dict of {original_file: issues_split_count}
    """
    import glob

    results = {}

    for filepath in glob.glob(os.path.join(issues_dir, 'A', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        split_issues = split_multi_issue_file(filepath)

        if len(split_issues) > 1:
            print(f"  📂 Splitting {os.path.basename(filepath)} into {len(split_issues)} files...")

            # Keep the first issue in the original file
            first_id, first_content = split_issues[0]

            # Write remaining issues to new files
            for issue_id, issue_content in split_issues[1:]:
                new_filepath = os.path.join(issues_dir, 'A', f'{issue_id}.md')

                # Convert ### to # for standalone file
                issue_content = re.sub(r'^###\s*', '# ', issue_content, count=1)

                # Ensure proper ending
                if not issue_content.rstrip().endswith('---'):
                    issue_content = issue_content.rstrip() + '\n\n---\n'

                with open(new_filepath, 'w', encoding='utf-8') as f:
                    f.write(issue_content)

                print(f"    ✓ Created {issue_id}.md")

            # Update original file with just the first issue
            first_content = re.sub(r'^###\s*', '# ', first_content, count=1)
            if not first_content.rstrip().endswith('---'):
                first_content = first_content.rstrip() + '\n\n---\n'

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(first_content)

            results[filepath] = len(split_issues)

    return results

def fix_acceptance_criteria_checkboxes(issues_dir: str) -> int:
    """
    Auto-check acceptance criteria boxes for RESOLVED issues.

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Only fix RESOLVED issues
        if not re.search(r'Status:\s*RESOLVED', content, re.IGNORECASE):
            continue

        # Check if there are unchecked boxes
        if '[ ]' not in content:
            continue

        # Replace unchecked with checked
        new_content = re.sub(r'- \[ \]', '- [x]', content)

        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed_count += 1

    return fixed_count

def fix_missing_separators(issues_dir: str) -> int:
    """
    Add closing separator (---) to files that are missing it.

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.rstrip().endswith('---'):
            content = content.rstrip() + '\n\n---\n'

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            fixed_count += 1

    return fixed_count

def normalize_lane_h_format(issues_dir: str) -> int:
    """
    Normalize Lane H (H-31+) format to match standard Lane format.

    Converts:
    - **Type Tags**: value  →  - Type Tags: value
    - **Severity**: value   →  - Severity: value

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, 'H', '*.md')):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Normalize bold field format
        content = re.sub(r'^- \*\*([^*]+)\*\*:\s*', r'- \1: ', content, flags=re.MULTILINE)

        # Normalize section headers with ### to **
        content = re.sub(r'^### (Problem Description|Evidence|Impact Analysis|Detailed Fix Requirements)',
                        r'**\1**', content, flags=re.MULTILINE)

        # Fix header format: ## [LANE H] → # [LANE H]
        content = re.sub(r'^## \[LANE', r'# [LANE', content, count=1)

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def normalize_category_a(issue: Issue, content: str) -> str:
    """
    Normalize Category A format to match Lane format for consistency.

    Transforms:
    - **Status:** ✅ RESOLVED  →  - Status: RESOLVED
    - **Severity Score:** 8/10 (HIGH) 🟠  →  - Severity: 8/10 HIGH 🔴
    - **User Approval Required:**  →  - User Approval: YES/NO ✅
    - **Problem:**  →  **Problem Description**
    - **Fix Options:**  →  **Detailed Fix Requirements (DO NOT IMPLEMENT)**

    Also adds missing required sections with placeholders.
    """
    lines = content.split('\n')
    normalized = []

    # Track what we've seen
    seen_problem_desc = False
    seen_fix_requirements = False
    seen_do_not_implement = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Transform header: # A1: Title → # [LANE A] Issue A001: Title
        if line.startswith('# A') and ':' in line:
            match = re.match(r'^# A(\d+):\s*(.*)$', line)
            if match:
                num = match.group(1).zfill(3)
                title = match.group(2)
                normalized.append(f"# [LANE A] Issue A{num}: {title}")
                i += 1
                continue

        # Transform **Status:** → - Status:
        if line.startswith('**Status:**'):
            status_match = re.search(r'\*\*Status:\*\*\s*[✅❌]?\s*(\w+)', line)
            status = status_match.group(1) if status_match else 'OPEN'
            normalized.append(f"- Status: {status}")
            i += 1
            continue

        # Transform **Severity Score:** → - Severity:
        if line.startswith('**Severity Score:**') or line.startswith('**Severity:**'):
            sev_match = re.search(r'(\d+/10)\s*\(?(\w+)\)?', line)
            if sev_match:
                score = sev_match.group(1)
                level = sev_match.group(2).upper()
                emoji = '🔴' if level == 'HIGH' else ('🟡' if level == 'MEDIUM' else '🟢')
                normalized.append(f"- Severity: {score} {level} {emoji}")
            else:
                normalized.append(f"- Severity: {issue.severity}")
            i += 1
            continue

        # Transform **User Approval Required:** → - User Approval:
        if line.startswith('**User Approval Required:**') or line.startswith('**User Approval:**'):
            if 'REQUIRED' in line.upper() or 'YES' in line.upper() or 'RECOMMENDED' in line.upper():
                normalized.append("- User Approval: YES ⚠️")
            else:
                normalized.append("- User Approval: NO ✅")
            i += 1
            continue

        # Transform **Found in:** → - Found in:
        if line.startswith('**Found in:**'):
            content_after = line.replace('**Found in:**', '').strip()
            normalized.append(f"- Found in: {content_after}")
            i += 1
            continue

        # Transform **Date Discovered:** → - Date Discovered:
        if line.startswith('**Date Discovered:**'):
            content_after = line.replace('**Date Discovered:**', '').strip()
            normalized.append(f"- Date Discovered: {content_after}")
            i += 1
            continue

        # Transform **Date Resolved:** → - Date Resolved:
        if line.startswith('**Date Resolved:**'):
            content_after = line.replace('**Date Resolved:**', '').strip()
            normalized.append(f"- Date Resolved: {content_after}")
            i += 1
            continue

        # Transform **Problem:** → **Problem Description**
        if line.strip() == '**Problem:**':
            normalized.append("")
            normalized.append("**Problem Description**")
            seen_problem_desc = True
            i += 1
            # Collect subsequent lines until next section
            while i < len(lines) and not lines[i].startswith('**'):
                problem_line = lines[i]
                if problem_line.strip():
                    if not problem_line.strip().startswith('-'):
                        normalized.append(f"- What is wrong (precise): {problem_line.strip()}")
                    else:
                        normalized.append(problem_line)
                else:
                    normalized.append(problem_line)
                i += 1
            continue

        # Transform **Impact:** → **Impact Analysis**
        if line.strip() == '**Impact:**':
            normalized.append("")
            normalized.append("**Impact Analysis**")
            i += 1
            while i < len(lines) and not lines[i].startswith('**'):
                impact_line = lines[i]
                if impact_line.strip() and impact_line.strip().startswith('-'):
                    # Transform bullet to proper format
                    bullet_content = impact_line.strip()[1:].strip()
                    normalized.append(f"- Immediate impact: {bullet_content}")
                elif impact_line.strip():
                    normalized.append(f"- {impact_line.strip()}")
                else:
                    normalized.append(impact_line)
                i += 1
            continue

        # Transform **Fix Options:** → **Detailed Fix Requirements (DO NOT IMPLEMENT)**
        if line.strip() == '**Fix Options:**' or line.strip().startswith('**Fix Options'):
            normalized.append("")
            normalized.append("**Detailed Fix Requirements (DO NOT IMPLEMENT)**")
            seen_fix_requirements = True
            seen_do_not_implement = True
            i += 1
            while i < len(lines) and not lines[i].startswith('**'):
                fix_line = lines[i]
                if fix_line.strip():
                    # Clean up "Option A:", "Option B:" format
                    if fix_line.strip().startswith('-') and 'Option' in fix_line:
                        opt_content = re.sub(r'\*\*Option [A-Z]:\*\*\s*', '', fix_line.strip()[1:].strip())
                        normalized.append(f"- Required changes: {opt_content}")
                    elif fix_line.strip().startswith('-'):
                        normalized.append(fix_line)
                    else:
                        normalized.append(f"- {fix_line.strip()}")
                else:
                    normalized.append(fix_line)
                i += 1
            continue

        # Transform **Resolution Required:** → - Acceptance Criteria:
        if line.startswith('**Resolution Required:**'):
            content_after = line.replace('**Resolution Required:**', '').strip()
            normalized.append(f"- Acceptance Criteria (binary): {content_after}")
            i += 1
            continue

        # Transform **Resolution Applied:** → - Resolution Applied:
        if line.startswith('**Resolution Applied:**'):
            content_after = line.replace('**Resolution Applied:**', '').strip()
            normalized.append("")
            normalized.append("**Resolution Applied**")
            normalized.append(f"- {content_after}" if content_after else "")
            i += 1
            continue

        # Transform **Cross-References:** → - Cross-References:
        if line.startswith('**Cross-References:**'):
            content_after = line.replace('**Cross-References:**', '').strip()
            normalized.append("")
            normalized.append("**Cross-References**")
            normalized.append(f"- {content_after}" if content_after else "")
            i += 1
            continue

        # Keep Evidence and other sections
        if line.strip() == '**Evidence:**':
            normalized.append("")
            normalized.append("**Evidence**")
            i += 1
            continue

        # Default: keep line as-is
        normalized.append(line)
        i += 1

    # Add missing DO NOT IMPLEMENT warning if not present
    if not seen_do_not_implement:
        # Find where to insert it (before Cross-References or at end)
        result = '\n'.join(normalized)
        if '**Cross-References**' in result:
            result = result.replace(
                '**Cross-References**',
                '**Detailed Fix Requirements (DO NOT IMPLEMENT)**\n- Fix Objective: See resolution applied above\n- Acceptance Criteria: Issue resolved\n\n**Cross-References**'
            )
        elif result.rstrip().endswith('---'):
            result = result.rstrip()[:-3] + '\n**Detailed Fix Requirements (DO NOT IMPLEMENT)**\n- Fix Objective: See resolution applied above\n- Acceptance Criteria: Issue resolved\n\n---\n'
        else:
            result += '\n\n**Detailed Fix Requirements (DO NOT IMPLEMENT)**\n- Fix Objective: See resolution applied above\n- Acceptance Criteria: Issue resolved\n'
        return result

    return '\n'.join(normalized)

def trim_version_history(header: str, max_versions: int = 15) -> str:
    """
    Trim version history to keep only the most recent versions.
    Keeps header structure but limits version entries.
    """
    lines = header.split('\n')
    result = []
    version_count = 0
    in_version_section = False
    skipped_versions = 0

    for line in lines:
        # Detect version history lines (start with "- v")
        if line.strip().startswith('- v') and re.match(r'^- v\d+\.\d+', line.strip()):
            in_version_section = True
            version_count += 1
            if version_count <= max_versions:
                result.append(line)
            else:
                skipped_versions += 1
        else:
            # If we just finished skipping versions, add a note
            if in_version_section and skipped_versions > 0 and not line.strip().startswith('- v'):
                result.append(f"- ... ({skipped_versions} earlier versions omitted, see VERSION_HISTORY.md)\n")
                skipped_versions = 0
                in_version_section = False
            result.append(line)

    return '\n'.join(result)

def clean_header(header: str) -> str:
    """
    Remove stale/duplicate sections from header that could confuse LLMs.
    Removes:
    - 'Issue Summary by Category' section (outdated counts)
    - 'Issue Registry' section (we generate our own)
    - Everything after '# Issue Registry' header
    """
    lines = header.split('\n')
    result = []
    skip_until_next_section = False

    for line in lines:
        # Stop at Issue Registry - we generate our own
        if line.strip().startswith('# Issue Registry'):
            break

        # Detect start of stale summary section
        if '## 📊 ISSUE SUMMARY BY CATEGORY' in line.upper() or \
           '### Category A: Missing Files' in line:
            skip_until_next_section = True
            continue

        # Detect end of stale section (next major section)
        if skip_until_next_section:
            if line.startswith('## ') or line.startswith('# '):
                skip_until_next_section = False
                # Don't skip the new section header unless it's also stale
                if not ('ISSUE SUMMARY' in line.upper()):
                    result.append(line)
            elif '---' == line.strip():
                # Keep the separator, might be end of section
                skip_until_next_section = False
                result.append(line)
            continue

        result.append(line)

    return '\n'.join(result)

FORMAT_GUIDE = """
## Issue Format Guide

All issues follow a standardized format for consistency. See `issues/TEMPLATE.md` for the full template.

### Required Fields (in header)
| Field | Format | Example |
|-------|--------|---------|
| Status | `- Status: OPEN/RESOLVED` | `- Status: RESOLVED` |
| Severity | `- Severity: X/10 LEVEL EMOJI` | `- Severity: 8/10 HIGH 🔴` |
| User Approval | `- User Approval: YES/NO EMOJI` | `- User Approval: NO ✅` |
| Type Tags | `- Type Tags: tag1, tag2` | `- Type Tags: GhostRef, MissingFile` |

### Severity Levels
| Score | Level | Emoji | Meaning |
|-------|-------|-------|---------|
| 8-10 | HIGH | 🔴 | Core functionality broken, security risk |
| 5-7 | MEDIUM | 🟡 | Feature degraded, workarounds exist |
| 1-4 | LOW | 🟢 | Minor inconvenience, cosmetic |

### Required Sections
1. **Problem Description** - What's wrong, expected vs actual, scope
2. **Evidence** - Source files, quotes, existence checks
3. **Impact Analysis** - Immediate impact, downstream effects, risk rationale
4. **Detailed Fix Requirements (DO NOT IMPLEMENT)** - Fix objective, required changes, acceptance criteria

### Type Tags Reference
`GhostRef` | `MissingFile` | `MissingDir` | `MissingSchema` | `Contradiction` | `PolicyViolation` | `Stub` | `ConfigError` | `WorkflowGap` | `DocDrift`

"""

def generate_slim_catalog(issues: List[Issue], header: str, dry_run: bool = False) -> str:
    """Generate the new slim catalog with summaries and links."""

    lines = []

    # Clean header: remove stale sections, trim version history
    cleaned_header = clean_header(header)
    trimmed_header = trim_version_history(cleaned_header, max_versions=15)

    # Further trim if still too long (keep first 300 lines max)
    header_lines = trimmed_header.split('\n')
    if len(header_lines) > 300:
        header_lines = header_lines[:300]
        header_lines.append("\n... (header trimmed, see original for full content)\n")

    lines.extend([line + '\n' if not line.endswith('\n') else line for line in header_lines])
    lines.append("\n")
    lines.append("---\n")
    lines.append("\n")
    lines.append("# Issue Registry\n")
    lines.append("\n")

    # Add LLM warning
    lines.append("> ⚠️ **FOR AI AGENTS:** This registry is the SINGLE SOURCE OF TRUTH for issue status.\n")
    lines.append("> Always read the `[Full Details]` file before implementing ANY fix.\n")
    lines.append("> Each issue file contains a **\"DO NOT IMPLEMENT\"** section - read it first!\n")
    lines.append(">\n")
    lines.append("> **Note:** Full issue details are in individual files under `issues/` directory.\n")
    lines.append("> Click the [Full Details] link to see complete evidence, analysis, and resolution steps.\n")
    lines.append("\n")

    # Add format guide
    lines.append(FORMAT_GUIDE)
    lines.append("\n---\n\n")

    # Group issues by lane
    issues_by_lane: Dict[str, List[Issue]] = {}
    for issue in issues:
        if issue.lane not in issues_by_lane:
            issues_by_lane[issue.lane] = []
        issues_by_lane[issue.lane].append(issue)

    # Sort lanes
    for lane in sorted(issues_by_lane.keys()):
        lane_issues = sorted(issues_by_lane[lane], key=lambda x: int(x.number))

        # Calculate statistics
        resolved_count = sum(1 for i in lane_issues if i.status == 'RESOLVED')
        open_count = len(lane_issues) - resolved_count

        # Lane header with statistics
        lane_type = 'Category' if lane == 'A' else 'Lane'
        stats = f"{resolved_count} RESOLVED, {open_count} OPEN"
        lines.append(f"\n## {lane_type} {lane} ({len(lane_issues)} issues) — {stats}\n")
        lines.append("\n")

        for issue in lane_issues:
            # Format: ### Issue ID: Title
            # Severity | Status | Type
            # > Summary
            # [Full Details](link)

            if issue.lane == 'A':
                issue_id = f"A{issue.number}"
                link_path = f"issues/A/A{issue.number}.md"
            else:
                issue_id = f"{issue.lane}-{issue.number}"
                link_path = f"issues/{issue.lane}/{issue.lane}-{issue.number}.md"

            lines.append(f"### {issue_id}: {issue.title}\n")
            lines.append(f"**Severity:** {issue.severity} | **Status:** {issue.status}")
            if issue.type_tags:
                lines.append(f" | **Type:** {issue.type_tags}")
            lines.append("\n")

            # Add dates if available
            if issue.date_discovered or issue.date_resolved:
                date_parts = []
                if issue.date_discovered:
                    date_parts.append(f"Discovered: {issue.date_discovered}")
                if issue.date_resolved:
                    date_parts.append(f"Resolved: {issue.date_resolved}")
                lines.append(f"*{' | '.join(date_parts)}*\n")

            if issue.summary:
                lines.append(f"> {issue.summary}\n")

            lines.append(f"\n→ [Full Details]({link_path})\n")
            lines.append("\n---\n\n")

    content = ''.join(lines)

    if not dry_run:
        with open(NEW_CATALOG_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"📄 New catalog written: {NEW_CATALOG_PATH}")

    return content

def update_catalog_tool_status(written: int, skipped: int, failed: int,
                                dry_run: bool = False, force: bool = False) -> bool:
    """
    Update the tool status section in ISSUE_CATALOG.md.

    Updates the section between <!-- TOOL_STATUS_START --> and <!-- TOOL_STATUS_END -->
    with the results of the latest run.
    """
    if dry_run:
        print("   (Tool status update skipped in dry-run)")
        return True

    try:
        with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if markers exist
        if '<!-- TOOL_STATUS_START -->' not in content:
            print("   ⚠️  Tool status section not found in catalog")
            return False

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mode = "Force (overwrite)" if force else "Safe (skip existing)"

        new_status = f"""<!-- TOOL_STATUS_START -->
<details>
<summary>🔧 Restructure Tool Status (click to expand)</summary>

| Metric | Value |
|--------|-------|
| Last Run | {timestamp} |
| Issues Written | {written:,} |
| Issues Skipped | {skipped:,} |
| Failed | {failed} |
| Mode | {mode} |

</details>
<!-- TOOL_STATUS_END -->"""

        # Replace the section
        content = re.sub(
            r'<!-- TOOL_STATUS_START -->.*?<!-- TOOL_STATUS_END -->',
            new_status,
            content,
            flags=re.DOTALL
        )

        with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"   ✓ Tool status updated in {CATALOG_PATH}")
        return True

    except Exception as e:
        print(f"   ❌ Failed to update tool status: {e}")
        return False

# =============================================================================
# VALIDATION
# =============================================================================

def deduplicate_issues(issues: List[Issue]) -> Tuple[List[Issue], Dict[str, int]]:
    """
    Remove duplicate issues, keeping only the first occurrence.

    Returns:
        - Deduplicated list of issues
        - Dict of issue_id -> count of duplicates removed
    """
    seen = {}
    unique_issues = []
    duplicate_counts = {}

    for issue in issues:
        key = f"{issue.lane}-{issue.number}"
        if key not in seen:
            seen[key] = True
            unique_issues.append(issue)
        else:
            # Count duplicates
            if key not in duplicate_counts:
                duplicate_counts[key] = 0
            duplicate_counts[key] += 1

    return unique_issues, duplicate_counts

def validate_extraction(issues: List[Issue], dry_run: bool = False) -> Tuple[bool, Dict]:
    """Validate the extraction results."""

    results = {
        'total_issues': len(issues),
        'by_lane': {},
        'missing_title': 0,
        'missing_severity': 0,
        'warnings': [],
        'errors': [],
        'duplicates_removed': 0
    }

    # Count by lane
    for issue in issues:
        if issue.lane not in results['by_lane']:
            results['by_lane'][issue.lane] = 0
        results['by_lane'][issue.lane] += 1

        # Check for missing fields
        if not issue.title or issue.title.startswith('Issue '):
            results['missing_title'] += 1
        if issue.severity == 'MEDIUM' and 'MEDIUM' not in issue.full_content:
            results['missing_severity'] += 1

    # Validate against expected counts
    all_valid = True
    for lane, expected in EXPECTED_COUNTS.items():
        actual = results['by_lane'].get(lane, 0)
        if actual == 0:
            results['warnings'].append(f"Lane {lane}: No issues found (expected ~{expected})")
        elif abs(actual - expected) > expected * 0.1:  # Allow 10% variance
            results['warnings'].append(
                f"Lane {lane}: Found {actual}, expected ~{expected} (difference: {actual - expected})"
            )

    # Note: Duplicates are now handled by deduplicate_issues() before validation

    return all_valid, results

# Required sections for a well-formed issue
REQUIRED_SECTIONS = [
    ('Problem Description', '**Problem Description**'),
    ('Evidence', '**Evidence**'),
    ('Impact Analysis', '**Impact Analysis**'),
    ('DO NOT IMPLEMENT', 'DO NOT IMPLEMENT'),
]

RECOMMENDED_FIELDS = [
    ('Severity', r'Severity[:\s]'),
    ('Status', r'Status[:\s]'),
    ('Type Tags', r'Type Tags?[:\s]'),
]

def validate_required_sections(issues: List[Issue]) -> Dict:
    """
    Validate that all issues have required sections.

    Returns a dict with:
    - issues_missing_sections: List of (issue_id, missing_sections)
    - issues_missing_fields: List of (issue_id, missing_fields)
    - total_issues_checked: int
    - fully_compliant: int
    """
    results = {
        'issues_missing_sections': [],
        'issues_missing_fields': [],
        'total_issues_checked': len(issues),
        'fully_compliant': 0,
        'section_stats': {name: 0 for name, _ in REQUIRED_SECTIONS},
        'field_stats': {name: 0 for name, _ in RECOMMENDED_FIELDS},
    }

    for issue in issues:
        content = issue.full_content
        missing_sections = []
        missing_fields = []
        is_compliant = True

        # Check required sections
        for section_name, pattern in REQUIRED_SECTIONS:
            if pattern in content:
                results['section_stats'][section_name] += 1
            else:
                missing_sections.append(section_name)
                is_compliant = False

        # Check recommended fields
        for field_name, pattern in RECOMMENDED_FIELDS:
            if re.search(pattern, content, re.IGNORECASE):
                results['field_stats'][field_name] += 1
            else:
                missing_fields.append(field_name)

        if missing_sections:
            issue_id = f"{issue.lane}-{issue.number}" if issue.lane != 'A' else f"A{issue.number}"
            results['issues_missing_sections'].append((issue_id, missing_sections))

        if missing_fields:
            issue_id = f"{issue.lane}-{issue.number}" if issue.lane != 'A' else f"A{issue.number}"
            results['issues_missing_fields'].append((issue_id, missing_fields))

        if is_compliant:
            results['fully_compliant'] += 1

    return results

def print_section_validation_report(results: Dict):
    """Print the section validation report."""
    print("\n" + "=" * 60)
    print("📋 SECTION VALIDATION REPORT")
    print("=" * 60)

    total = results['total_issues_checked']
    compliant = results['fully_compliant']
    pct = (compliant / total * 100) if total > 0 else 0

    print(f"\n✅ Fully Compliant Issues: {compliant}/{total} ({pct:.1f}%)")

    print("\n📊 Required Sections Coverage:")
    for section_name, _ in REQUIRED_SECTIONS:
        count = results['section_stats'][section_name]
        pct = (count / total * 100) if total > 0 else 0
        status = "✓" if pct >= 90 else ("⚠" if pct >= 50 else "❌")
        print(f"   {status} {section_name}: {count}/{total} ({pct:.1f}%)")

    print("\n📊 Recommended Fields Coverage:")
    for field_name, _ in RECOMMENDED_FIELDS:
        count = results['field_stats'][field_name]
        pct = (count / total * 100) if total > 0 else 0
        status = "✓" if pct >= 90 else ("⚠" if pct >= 50 else "❌")
        print(f"   {status} {field_name}: {count}/{total} ({pct:.1f}%)")

    # Show issues missing critical "DO NOT IMPLEMENT" section
    missing_dni = [
        (issue_id, sections)
        for issue_id, sections in results['issues_missing_sections']
        if 'DO NOT IMPLEMENT' in sections
    ]

    if missing_dni:
        print(f"\n⚠️  Issues Missing 'DO NOT IMPLEMENT' ({len(missing_dni)}):")
        for issue_id, _ in missing_dni[:10]:  # Show first 10
            print(f"   - {issue_id}")
        if len(missing_dni) > 10:
            print(f"   ... and {len(missing_dni) - 10} more")

    print("\n" + "=" * 60)

def print_validation_report(results: Dict):
    """Print a formatted validation report."""
    print("\n" + "=" * 60)
    print("📊 VALIDATION REPORT")
    print("=" * 60)

    print(f"\n📈 Total Unique Issues: {results['total_issues']:,}")

    if results.get('duplicates_removed', 0) > 0:
        print(f"🧹 Duplicates Removed: {results['duplicates_removed']:,}")

    print("\n📁 Issues by Lane/Category:")

    for lane in sorted(results['by_lane'].keys()):
        count = results['by_lane'][lane]
        expected = EXPECTED_COUNTS.get(lane, '?')
        status = "✓" if isinstance(expected, int) and abs(count - expected) <= expected * 0.1 else "?"
        print(f"   {lane}: {count:,} issues {status}")

    if results['warnings']:
        print("\n⚠️  Warnings:")
        for w in results['warnings']:
            print(f"   - {w}")

    if results['errors']:
        print("\n❌ Errors:")
        for e in results['errors']:
            print(f"   - {e}")

    if results['missing_title'] > 0:
        print(f"\n📝 Issues with generic titles: {results['missing_title']}")

    print("\n" + "=" * 60)

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# =============================================================================
# NORMALIZATION FUNCTIONS (AI Confusion Fixes)
# =============================================================================

def normalize_section_headers(issues_dir: str) -> int:
    """
    Normalize section headers from ### format to ** format.

    Converts:
    - ### Problem Description  →  **Problem Description**
    - ### Evidence            →  **Evidence**
    - ### Impact Analysis     →  **Impact Analysis**
    - ### Detailed Fix Requirements  →  **Detailed Fix Requirements (DO NOT IMPLEMENT)**

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0
    sections_to_normalize = [
        'Problem Description',
        'Evidence',
        'Impact Analysis',
        'Detailed Fix Requirements',
        'Dedup Verification',
        'Cross-References',
    ]

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        for section in sections_to_normalize:
            # Convert ### Section to **Section**
            content = re.sub(
                rf'^###\s*{re.escape(section)}(\s*\(.*\))?',
                rf'**{section}\1**' if section != 'Detailed Fix Requirements' else f'**{section} (DO NOT IMPLEMENT)**',
                content,
                flags=re.MULTILINE
            )
            # Also handle ## Section
            content = re.sub(
                rf'^##\s*{re.escape(section)}(\s*\(.*\))?',
                rf'**{section}\1**' if section != 'Detailed Fix Requirements' else f'**{section} (DO NOT IMPLEMENT)**',
                content,
                flags=re.MULTILINE
            )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def normalize_severity_format(issues_dir: str) -> int:
    """
    Normalize severity to X/10 format.

    Converts:
    - Severity: 7 HIGH     →  Severity: 7/10 HIGH
    - Severity: 6 MEDIUM   →  Severity: 6/10 MEDIUM

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Fix severity without /10: "Severity: 7 HIGH" -> "Severity: 7/10 HIGH"
        content = re.sub(
            r'(Severity:\s*)(\d)(\s+)(HIGH|MEDIUM|LOW|CRITICAL)',
            r'\g<1>\g<2>/10\3\4',
            content,
            flags=re.IGNORECASE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def fix_severity_level_mismatch(issues_dir: str) -> int:
    """
    Fix severity level misclassification.

    Rules:
    - 7/10, 8/10, 9/10, 10/10 should be HIGH (not MEDIUM)
    - 5/10, 6/10 should be MEDIUM (not HIGH or LOW)
    - 1/10, 2/10, 3/10, 4/10 should be LOW

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # 7-10/10 should be HIGH
        content = re.sub(
            r'(Severity:\s*)(7|8|9|10)/10\s+(MEDIUM|LOW)',
            r'\g<1>\g<2>/10 HIGH',
            content,
            flags=re.IGNORECASE
        )

        # 5-6/10 should be MEDIUM
        content = re.sub(
            r'(Severity:\s*)(5|6)/10\s+(HIGH|LOW)',
            r'\g<1>\g<2>/10 MEDIUM',
            content,
            flags=re.IGNORECASE
        )

        # 1-4/10 should be LOW
        content = re.sub(
            r'(Severity:\s*)(1|2|3|4)/10\s+(HIGH|MEDIUM)',
            r'\g<1>\g<2>/10 LOW',
            content,
            flags=re.IGNORECASE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def add_severity_emojis(issues_dir: str) -> int:
    """
    Add missing severity emojis based on level.

    Rules:
    - HIGH/CRITICAL → 🔴
    - MEDIUM → 🟡
    - LOW → 🟢

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Add 🔴 for HIGH/CRITICAL if missing
        content = re.sub(
            r'(Severity:\s*\d+/10\s+)(HIGH|CRITICAL)(\s*)$',
            r'\1\2 🔴',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        # Add 🟡 for MEDIUM if missing
        content = re.sub(
            r'(Severity:\s*\d+/10\s+)(MEDIUM)(\s*)$',
            r'\1\2 🟡',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        # Add 🟢 for LOW if missing
        content = re.sub(
            r'(Severity:\s*\d+/10\s+)(LOW)(\s*)$',
            r'\1\2 🟢',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def normalize_type_tags_format(issues_dir: str) -> int:
    """
    Normalize Type Tags format from bold to dash.

    Converts:
    - **Type Tags:** value  →  - Type Tags: value

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Convert **Type Tags:** to - Type Tags:
        content = re.sub(
            r'^\*\*Type Tags:\*\*\s*',
            '- Type Tags: ',
            content,
            flags=re.MULTILINE
        )

        # Also fix - **Type Tags**: format
        content = re.sub(
            r'^- \*\*Type Tags\*\*:\s*',
            '- Type Tags: ',
            content,
            flags=re.MULTILINE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def normalize_user_approval_format(issues_dir: str) -> int:
    """
    Normalize User Approval format.

    Converts:
    - **User Approval:** NO ✅  →  - User Approval: NO ✅
    - User Approval: NO        →  - User Approval: NO ✅
    - User Approval: YES       →  - User Approval: YES ⚠️
    - User Approval: RECOMMENDED →  - User Approval: RECOMMENDED ⚠️

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Remove bold from User Approval
        content = re.sub(
            r'^- \*\*User Approval:?\*\*:?\s*',
            '- User Approval: ',
            content,
            flags=re.MULTILINE
        )

        # Add emoji for NO if missing
        content = re.sub(
            r'^(- User Approval:\s*NO)(\s*)$',
            r'\1 ✅',
            content,
            flags=re.MULTILINE
        )

        # Add emoji for YES if missing
        content = re.sub(
            r'^(- User Approval:\s*YES)(\s*)$',
            r'\1 ⚠️',
            content,
            flags=re.MULTILINE
        )

        # Add emoji for RECOMMENDED if missing
        content = re.sub(
            r'^(- User Approval:\s*RECOMMENDED)(\s*)$',
            r'\1 ⚠️',
            content,
            flags=re.MULTILINE
        )

        # Normalize YES 🔒 to YES ⚠️ for consistency
        content = re.sub(
            r'^(- User Approval:\s*YES)\s*🔒',
            r'\1 ⚠️',
            content,
            flags=re.MULTILINE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def normalize_acceptance_criteria_format(issues_dir: str) -> int:
    """
    Normalize Acceptance Criteria format.

    Converts various formats to:
    - Acceptance Criteria (binary):

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Remove bold from Acceptance Criteria
        content = re.sub(
            r'^- \*\*Acceptance Criteria:?\*\*:?\s*',
            '- Acceptance Criteria (binary): ',
            content,
            flags=re.MULTILINE
        )

        # Normalize "Acceptance Criteria:" to "Acceptance Criteria (binary):"
        content = re.sub(
            r'^- Acceptance Criteria:\s*(?!\(binary\))',
            '- Acceptance Criteria (binary): ',
            content,
            flags=re.MULTILINE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def normalize_fix_requirements_header(issues_dir: str) -> int:
    """
    Normalize Fix Requirements header format.

    Converts:
    - **Fix Required:**                    →  **Detailed Fix Requirements (DO NOT IMPLEMENT)**
    - **Detailed Fix Requirements**        →  **Detailed Fix Requirements (DO NOT IMPLEMENT)**
    - ### Detailed Fix Requirements        →  **Detailed Fix Requirements (DO NOT IMPLEMENT)**

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Normalize **Fix Required:** to proper format
        content = re.sub(
            r'^\*\*Fix Required:\*\*',
            '**Detailed Fix Requirements (DO NOT IMPLEMENT)**',
            content,
            flags=re.MULTILINE
        )

        # Normalize **Detailed Fix Requirements** without (DO NOT IMPLEMENT)
        content = re.sub(
            r'^\*\*Detailed Fix Requirements\*\*\s*(?!\(DO NOT IMPLEMENT\))',
            '**Detailed Fix Requirements (DO NOT IMPLEMENT)**',
            content,
            flags=re.MULTILINE
        )

        # Normalize ### Detailed Fix Requirements
        content = re.sub(
            r'^###?\s*Detailed Fix Requirements.*$',
            '**Detailed Fix Requirements (DO NOT IMPLEMENT)**',
            content,
            flags=re.MULTILINE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def normalize_resolution_section(issues_dir: str) -> int:
    """
    Normalize Resolution section headers.

    Converts:
    - **Resolution:**                      →  **Resolution Applied**
    - **Resolution Applied (date):**       →  **Resolution Applied**
    - **Resolution Notes**                 →  **Resolution Applied**
    - **Resolution Summary:**              →  **Resolution Applied**

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Normalize various Resolution headers
        content = re.sub(
            r'^\*\*Resolution:\*\*',
            '**Resolution Applied**',
            content,
            flags=re.MULTILINE
        )

        content = re.sub(
            r'^\*\*Resolution Applied \(\d{4}-\d{2}-\d{2}\):\*\*',
            '**Resolution Applied**',
            content,
            flags=re.MULTILINE
        )

        content = re.sub(
            r'^\*\*Resolution Notes\*\*',
            '**Resolution Applied**',
            content,
            flags=re.MULTILINE
        )

        content = re.sub(
            r'^\*\*Resolution Notes \(\d{4}-\d{2}-\d{2}\):\*\*',
            '**Resolution Applied**',
            content,
            flags=re.MULTILINE
        )

        content = re.sub(
            r'^\*\*Resolution Summary:\*\*',
            '**Resolution Applied**',
            content,
            flags=re.MULTILINE
        )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

# Standard category descriptions for normalization
CATEGORY_DESCRIPTIONS = {
    'A': 'Missing file/artifact',
    'B': 'Structural/Path issues',
    'C': 'Tooling/CI',
    'D': 'Guidelines/Policies',
    'E': 'CI/Workflow gap',
    'F': 'Documentation/LogBook',
}

def standardize_category_descriptions(issues_dir: str) -> int:
    """
    Standardize Category descriptions to use consistent wording.

    Converts various category descriptions to standard format:
    - Category (internal): A (Missing file/artifact)

    Returns count of files fixed.
    """
    import glob

    fixed_count = 0

    for filepath in glob.glob(os.path.join(issues_dir, '*', '*.md')):
        if 'TEMPLATE' in filepath:
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Normalize category descriptions
        for cat_letter, description in CATEGORY_DESCRIPTIONS.items():
            # Match any Category (internal): X (whatever) pattern
            content = re.sub(
                rf'^(- Category \(internal\):\s*{cat_letter})\s*\([^)]*\)',
                rf'\1 ({description})',
                content,
                flags=re.MULTILINE
            )

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed_count += 1

    return fixed_count

def run_post_extraction_fixes(issues_dir: str) -> Dict:
    """
    Run all post-extraction fixes on issue files.

    Returns dict with fix statistics.
    """
    print("\n" + "=" * 60)
    print("🔧 POST-EXTRACTION FIXES")
    print("=" * 60)

    results = {
        'multi_issue_files_split': 0,
        'checkboxes_fixed': 0,
        'separators_added': 0,
        'lane_h_normalized': 0,
        'section_headers_normalized': 0,
        'severity_format_fixed': 0,
        'severity_level_fixed': 0,
        'severity_emojis_added': 0,
        'type_tags_normalized': 0,
        'user_approval_normalized': 0,
        'acceptance_criteria_normalized': 0,
        'fix_requirements_normalized': 0,
        'resolution_normalized': 0,
        'category_descriptions_standardized': 0,
    }

    # Fix 1: Split multi-issue files
    print("\n📂 Step 1: Splitting multi-issue files...")
    split_results = fix_multi_issue_files(issues_dir)
    results['multi_issue_files_split'] = len(split_results)
    if split_results:
        total_new = sum(split_results.values()) - len(split_results)
        print(f"   ✓ Split {len(split_results)} files, created {total_new} new files")
    else:
        print("   ✓ No multi-issue files found")

    # Fix 2: Normalize Lane H format
    print("\n📝 Step 2: Normalizing Lane H format...")
    results['lane_h_normalized'] = normalize_lane_h_format(issues_dir)
    print(f"   ✓ Normalized {results['lane_h_normalized']} files")

    # Fix 3: Normalize section headers (### to **)
    print("\n📋 Step 3: Normalizing section headers (### → **)...")
    results['section_headers_normalized'] = normalize_section_headers(issues_dir)
    print(f"   ✓ Normalized {results['section_headers_normalized']} files")

    # Fix 4: Normalize severity format (add /10)
    print("\n🔢 Step 4: Normalizing severity format (X → X/10)...")
    results['severity_format_fixed'] = normalize_severity_format(issues_dir)
    print(f"   ✓ Fixed {results['severity_format_fixed']} files")

    # Fix 5: Fix severity level misclassification
    print("\n⚖️ Step 5: Fixing severity level misclassification...")
    results['severity_level_fixed'] = fix_severity_level_mismatch(issues_dir)
    print(f"   ✓ Fixed {results['severity_level_fixed']} files")

    # Fix 6: Add missing severity emojis
    print("\n🎨 Step 6: Adding missing severity emojis...")
    results['severity_emojis_added'] = add_severity_emojis(issues_dir)
    print(f"   ✓ Added emojis to {results['severity_emojis_added']} files")

    # Fix 7: Normalize Type Tags format
    print("\n🏷️ Step 7: Normalizing Type Tags format...")
    results['type_tags_normalized'] = normalize_type_tags_format(issues_dir)
    print(f"   ✓ Normalized {results['type_tags_normalized']} files")

    # Fix 8: Normalize User Approval format
    print("\n👤 Step 8: Normalizing User Approval format...")
    results['user_approval_normalized'] = normalize_user_approval_format(issues_dir)
    print(f"   ✓ Normalized {results['user_approval_normalized']} files")

    # Fix 9: Normalize Acceptance Criteria format
    print("\n✅ Step 9: Normalizing Acceptance Criteria format...")
    results['acceptance_criteria_normalized'] = normalize_acceptance_criteria_format(issues_dir)
    print(f"   ✓ Normalized {results['acceptance_criteria_normalized']} files")

    # Fix 10: Normalize Fix Requirements header
    print("\n🔧 Step 10: Normalizing Fix Requirements header...")
    results['fix_requirements_normalized'] = normalize_fix_requirements_header(issues_dir)
    print(f"   ✓ Normalized {results['fix_requirements_normalized']} files")

    # Fix 11: Normalize Resolution section
    print("\n📝 Step 11: Normalizing Resolution section headers...")
    results['resolution_normalized'] = normalize_resolution_section(issues_dir)
    print(f"   ✓ Normalized {results['resolution_normalized']} files")

    # Fix 12: Standardize Category descriptions
    print("\n📁 Step 12: Standardizing Category descriptions...")
    results['category_descriptions_standardized'] = standardize_category_descriptions(issues_dir)
    print(f"   ✓ Standardized {results['category_descriptions_standardized']} files")

    # Fix 13: Auto-check acceptance boxes for RESOLVED issues
    print("\n☑️ Step 13: Auto-checking acceptance boxes...")
    results['checkboxes_fixed'] = fix_acceptance_criteria_checkboxes(issues_dir)
    print(f"   ✓ Fixed {results['checkboxes_fixed']} files")

    # Fix 14: Add missing separators
    print("\n📏 Step 14: Adding missing closing separators...")
    results['separators_added'] = fix_missing_separators(issues_dir)
    print(f"   ✓ Added separators to {results['separators_added']} files")

    print("\n" + "=" * 60)
    print("📊 POST-EXTRACTION FIXES SUMMARY")
    print("=" * 60)
    print(f"   Multi-issue files split:        {results['multi_issue_files_split']}")
    print(f"   Lane H files normalized:        {results['lane_h_normalized']}")
    print(f"   Section headers normalized:     {results['section_headers_normalized']}")
    print(f"   Severity format fixed:          {results['severity_format_fixed']}")
    print(f"   Severity level corrected:       {results['severity_level_fixed']}")
    print(f"   Severity emojis added:          {results['severity_emojis_added']}")
    print(f"   Type Tags normalized:           {results['type_tags_normalized']}")
    print(f"   User Approval normalized:       {results['user_approval_normalized']}")
    print(f"   Acceptance Criteria normalized: {results['acceptance_criteria_normalized']}")
    print(f"   Fix Requirements normalized:    {results['fix_requirements_normalized']}")
    print(f"   Resolution sections normalized: {results['resolution_normalized']}")
    print(f"   Category descriptions fixed:    {results['category_descriptions_standardized']}")
    print(f"   Acceptance boxes checked:       {results['checkboxes_fixed']}")
    print(f"   Separators added:               {results['separators_added']}")
    print("=" * 60)

    return results

def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Restructure the system Issue Catalog')
    parser.add_argument('--dry-run', action='store_true',
                        help='Parse and validate without writing files')
    parser.add_argument('--lane', type=str,
                        help='Only process specific lane (e.g., G, J, A)')
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip backup creation')
    parser.add_argument('--fix-only', action='store_true',
                        help='Only run post-extraction fixes on existing files')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing issue files (default: skip existing)')
    args = parser.parse_args()

    print("=" * 60)
    print("🔧 the system ISSUE CATALOG RESTRUCTURING TOOL")
    print("=" * 60)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Working directory: {os.getcwd()}")

    # If --fix-only, just run fixes and exit
    if args.fix_only:
        print(f"🔍 Mode: FIX ONLY")
        print()
        if os.path.isdir(ISSUES_DIR):
            run_post_extraction_fixes(ISSUES_DIR)
            print(f"\n⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"❌ Issues directory not found: {ISSUES_DIR}")
            sys.exit(1)
        sys.exit(0)

    print(f"🔍 Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    if args.lane:
        print(f"🎯 Target lane: {args.lane}")
    print()

    # Step 1: Verify catalog exists
    if not os.path.exists(CATALOG_PATH):
        print(f"❌ Catalog not found: {CATALOG_PATH}")
        sys.exit(1)

    catalog_size = os.path.getsize(CATALOG_PATH) / (1024 * 1024)
    print(f"📖 Catalog: {CATALOG_PATH} ({catalog_size:.2f} MB)")

    # Step 2: Create backup
    if not args.dry_run and not args.no_backup:
        print("\n📦 Step 1: Creating backup...")
        if not create_backup(CATALOG_PATH, BACKUP_PATH):
            print("❌ Aborting due to backup failure")
            sys.exit(1)
    else:
        print("\n📦 Step 1: Backup skipped (dry-run or --no-backup)")

    # Step 3: Parse catalog
    print("\n🔍 Step 2: Parsing catalog...")
    issues, header, footer = parse_catalog(CATALOG_PATH)
    print(f"   Found {len(issues):,} issues (before deduplication)")

    # Step 3b: Deduplicate
    print("\n🧹 Step 2b: Removing duplicates...")
    issues, duplicate_counts = deduplicate_issues(issues)
    total_duplicates = sum(duplicate_counts.values())
    print(f"   Removed {total_duplicates:,} duplicates")
    print(f"   Unique issues: {len(issues):,}")

    if duplicate_counts:
        # Show top 10 most duplicated issues
        top_dupes = sorted(duplicate_counts.items(), key=lambda x: -x[1])[:10]
        print(f"   Top duplicated issues:")
        for issue_id, count in top_dupes:
            print(f"      {issue_id}: {count} duplicates removed")

    # Filter by lane if specified
    if args.lane:
        issues = [i for i in issues if i.lane == args.lane.upper()]
        print(f"   Filtered to {len(issues):,} issues in Lane {args.lane.upper()}")

    # Step 4: Validate
    print("\n✅ Step 3: Validating extraction...")
    valid, results = validate_extraction(issues, args.dry_run)
    results['duplicates_removed'] = total_duplicates
    print_validation_report(results)

    # Step 4b: Validate required sections
    print("\n📋 Step 3b: Validating required sections...")
    section_results = validate_required_sections(issues)
    print_section_validation_report(section_results)

    if results['errors']:
        print("\n❌ Aborting due to validation errors")
        sys.exit(1)

    if args.dry_run:
        print("\n🔍 DRY RUN COMPLETE - No files were modified")
        print("   Run without --dry-run to perform actual extraction")
        sys.exit(0)

    # Step 5: Create folder structure
    print("\n📁 Step 4: Creating folder structure...")
    lanes = list(set(i.lane for i in issues))
    create_folder_structure(lanes, args.dry_run)

    # Step 6: Extract issues to individual files
    print("\n📝 Step 5: Extracting issues to individual files...")
    if not args.force:
        print("   ℹ️  Skipping existing files (use --force to overwrite)")
    written_count = 0
    skipped_count = 0
    fail_count = 0

    for i, issue in enumerate(issues):
        result = write_issue_file(issue, args.dry_run, args.force)
        if result == 'written':
            written_count += 1
        elif result == 'skipped':
            skipped_count += 1
        else:
            fail_count += 1

        # Progress indicator
        if (i + 1) % 100 == 0 or i == len(issues) - 1:
            pct = ((i + 1) / len(issues)) * 100
            print(f"   Progress: {i + 1:,}/{len(issues):,} ({pct:.1f}%) - ✓ {written_count:,} / ⏭ {skipped_count:,} / ❌ {fail_count}")

    # Step 7: Generate slim catalog
    print("\n📄 Step 6: Generating slim catalog...")
    generate_slim_catalog(issues, header, args.dry_run)

    # Step 7: Run post-extraction fixes
    if not args.dry_run:
        fix_results = run_post_extraction_fixes(ISSUES_DIR)
    else:
        print("\n📝 Step 7: Post-extraction fixes (skipped in dry-run)")

    # Step 8: Final summary
    print("\n" + "=" * 60)
    print("🎉 RESTRUCTURING COMPLETE")
    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"   Issues written: {written_count:,}")
    print(f"   Issues skipped (already exist): {skipped_count:,}")
    print(f"   Failed extractions: {fail_count}")
    print(f"   Lanes processed: {len(lanes)}")

    if not args.dry_run:
        # Calculate new sizes
        new_catalog_size = os.path.getsize(NEW_CATALOG_PATH) / (1024 * 1024)
        issues_dir_size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, dn, filenames in os.walk(ISSUES_DIR)
            for f in filenames
        ) / (1024 * 1024)

        print(f"\n📦 File sizes:")
        print(f"   Original catalog: {catalog_size:.2f} MB")
        print(f"   New slim catalog: {new_catalog_size:.2f} MB")
        print(f"   Issues directory: {issues_dir_size:.2f} MB")
        print(f"   Space saved in catalog: {catalog_size - new_catalog_size:.2f} MB ({((catalog_size - new_catalog_size) / catalog_size * 100):.1f}%)")

    print(f"\n📁 Output files:")
    print(f"   Backup: {BACKUP_PATH}")
    print(f"   New catalog: {NEW_CATALOG_PATH}")
    print(f"   Issues directory: {ISSUES_DIR}/")

    print(f"\n⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Update tool status in catalog
    print("\n📊 Updating catalog tool status...")
    update_catalog_tool_status(written_count, skipped_count, fail_count,
                               args.dry_run, args.force)

    print("\n📋 Next steps:")
    print("   1. Review the new catalog: less ISSUE_CATALOG_NEW.md")
    print("   2. Spot-check some issue files: ls issues/G/")
    print("   3. If satisfied, replace original:")
    print("      mv ISSUE_CATALOG.md ISSUE_CATALOG_OLD.md")
    print("      mv ISSUE_CATALOG_NEW.md ISSUE_CATALOG.md")
    print("   4. Commit changes: git add issues/ ISSUE_CATALOG.md && git commit")

if __name__ == '__main__':
    main()
