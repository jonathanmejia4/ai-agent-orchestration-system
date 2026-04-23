#!/usr/bin/env python3
"""
Add Issue to Catalog Tool

Adds a new issue entry to the Open Issues section of ISSUE_CATALOG.md.
Used by issue hunters after creating issue files.

Usage:
    python3 tools/add_issue_to_catalog.py add --id G-71 --title "Ghost reference to tools/missing.py" --severity "7/10 HIGH" --tags "GhostRef, MissingTool"

    python3 tools/add_issue_to_catalog.py remove --id G-71

    # Show help for add command:
    python3 tools/add_issue_to_catalog.py add --help

Can also be called programmatically:
    from tools.add_issue_to_catalog import add_issue
    add_issue("G-71", "Ghost reference to tools/missing.py", "7/10 HIGH", "GhostRef, MissingTool")
"""

import os
import re
import sys
import argparse
from pathlib import Path

CATALOG_PATH = "ISSUE_CATALOG.md"

# Lane markers in the catalog
LANE_MARKERS = {
    'D': '<!-- LANE_D_ISSUES -->',
    'E': '<!-- LANE_E_ISSUES -->',
    'G': '<!-- LANE_G_ISSUES -->',
    'H': '<!-- LANE_H_ISSUES -->',
    'I': '<!-- LANE_I_ISSUES -->',
    'J': '<!-- LANE_J_ISSUES -->',
    'K': '<!-- LANE_K_ISSUES -->',
    'L': '<!-- LANE_L_ISSUES -->',
    'M': '<!-- LANE_M_ISSUES -->',
    'N': '<!-- LANE_N_ISSUES -->',
    'O': '<!-- LANE_O_ISSUES -->',
    'P': '<!-- LANE_P_ISSUES -->',
    'Q': '<!-- LANE_Q_ISSUES -->',
    'R': '<!-- LANE_R_ISSUES -->',
    'S': '<!-- LANE_S_ISSUES -->',
    'T': '<!-- LANE_T_ISSUES -->',
    'U': '<!-- LANE_U_ISSUES -->',
    'V': '<!-- LANE_V_ISSUES -->',
    'W': '<!-- LANE_W_ISSUES -->',
    'X': '<!-- LANE_X_ISSUES -->',
    'Y': '<!-- LANE_Y_ISSUES -->',
    'Z': '<!-- LANE_Z_ISSUES -->',
}

def get_lane_from_id(issue_id: str) -> str:
    """Extract lane letter from issue ID (e.g., 'G-71' -> 'G')."""
    match = re.match(r'^([A-Z])-\d+$', issue_id)
    if not match:
        raise ValueError(f"Invalid issue ID format: {issue_id}. Expected format: X-NN (e.g., G-71)")
    return match.group(1)

def issue_exists_in_catalog(content: str, issue_id: str) -> bool:
    """Check if issue already exists in the catalog."""
    # Look for the issue ID in a table row
    pattern = rf'\|\s*{re.escape(issue_id)}\s*\|'
    return bool(re.search(pattern, content))

def add_issue(issue_id: str, title: str, severity: str, type_tags: str, status: str = "OPEN") -> bool:
    """
    Add an issue to the catalog's Open Issues section.

    Args:
        issue_id: Issue ID (e.g., "G-71")
        title: Short title for the issue
        severity: Severity string (e.g., "7/10 HIGH")
        type_tags: Comma-separated type tags (e.g., "GhostRef, MissingTool")
        status: Issue status (default: "OPEN")

    Returns:
        True if issue was added, False if it already exists or error occurred
    """
    if not os.path.exists(CATALOG_PATH):
        print(f"ERROR: Catalog file not found: {CATALOG_PATH}")
        return False

    # Get lane from issue ID
    try:
        lane = get_lane_from_id(issue_id)
    except ValueError as e:
        print(f"ERROR: {e}")
        return False

    if lane not in LANE_MARKERS:
        print(f"ERROR: Unknown lane: {lane}")
        return False

    # Read catalog
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if issue already exists
    if issue_exists_in_catalog(content, issue_id):
        print(f"SKIP: Issue {issue_id} already exists in catalog")
        return False

    # Find the lane marker
    marker = LANE_MARKERS[lane]
    if marker not in content:
        print(f"ERROR: Lane marker not found in catalog: {marker}")
        return False

    # Create the table row
    # Truncate title if too long
    display_title = title[:60] + "..." if len(title) > 60 else title
    row = f"| {issue_id} | {display_title} | {severity} | {type_tags} | {status} |"

    # Insert the row after the marker
    # The marker is on its own line, we insert the row on the next line
    new_content = content.replace(
        marker,
        f"{row}\n{marker}"
    )

    # Write back
    with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✅ Added {issue_id} to catalog: {display_title}")
    return True

def remove_issue(issue_id: str) -> bool:
    """
    Remove an issue from the catalog (used when marking as RESOLVED).

    Args:
        issue_id: Issue ID to remove (e.g., "G-71")

    Returns:
        True if issue was removed, False if not found or error occurred
    """
    if not os.path.exists(CATALOG_PATH):
        print(f"ERROR: Catalog file not found: {CATALOG_PATH}")
        return False

    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match the issue row
    pattern = rf'\| {re.escape(issue_id)} \|[^\n]+\|\n'

    if not re.search(pattern, content):
        print(f"SKIP: Issue {issue_id} not found in catalog")
        return False

    # Remove the row
    new_content = re.sub(pattern, '', content)

    with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✅ Removed {issue_id} from catalog open issues")
    return True

def update_issue_status(issue_id: str, new_status: str) -> bool:
    """
    Update an issue's status in the catalog.

    Args:
        issue_id: Issue ID (e.g., "G-71")
        new_status: New status (e.g., "RESOLVED")

    Returns:
        True if updated, False otherwise
    """
    if new_status == "RESOLVED":
        # Remove from open issues section
        return remove_issue(issue_id)

    # For other status changes, update in place
    if not os.path.exists(CATALOG_PATH):
        return False

    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match and update status
    pattern = rf'(\| {re.escape(issue_id)} \|[^|]+\|[^|]+\|[^|]+\|)\s*\w+\s*\|'
    replacement = rf'\1 {new_status} |'

    new_content = re.sub(pattern, replacement, content)

    if new_content == content:
        print(f"SKIP: Issue {issue_id} not found or status unchanged")
        return False

    with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✅ Updated {issue_id} status to {new_status}")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Add or manage issues in ISSUE_CATALOG.md"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new issue')
    add_parser.add_argument('--id', required=True, help='Issue ID (e.g., G-71)')
    add_parser.add_argument('--title', required=True, help='Issue title')
    add_parser.add_argument('--severity', required=True, help='Severity (e.g., "7/10 HIGH")')
    add_parser.add_argument('--tags', required=True, help='Type tags (e.g., "GhostRef, MissingTool")')
    add_parser.add_argument('--status', default='OPEN', help='Status (default: OPEN)')

    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove an issue (mark as resolved)')
    remove_parser.add_argument('--id', required=True, help='Issue ID to remove')

    # Simple positional args for quick usage
    parser.add_argument('args', nargs='*', help='Quick add: <id> <title> <severity> <tags>')

    args = parser.parse_args()

    # Handle subcommands
    if args.command == 'add':
        success = add_issue(args.id, args.title, args.severity, args.tags, args.status)
        return 0 if success else 1

    if args.command == 'remove':
        success = remove_issue(args.id)
        return 0 if success else 1

    # Handle positional args for quick usage
    if len(args.args) >= 4:
        issue_id, title, severity, tags = args.args[0], args.args[1], args.args[2], ' '.join(args.args[3:])
        success = add_issue(issue_id, title, severity, tags)
        return 0 if success else 1

    # No valid command
    parser.print_help()
    return 1

if __name__ == "__main__":
    sys.exit(main())
