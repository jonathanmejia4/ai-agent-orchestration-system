#!/usr/bin/env python3
"""
Automated Resolution Detector

Detects issues that are actually fixed but not marked as RESOLVED.
Runs verification commands and updates status if all checks pass.

Usage:
    python3 tools/auto_resolve.py                    # Detect only
    python3 tools/auto_resolve.py --mark             # Mark as resolved
    python3 tools/auto_resolve.py --lane G           # Single lane
    python3 tools/auto_resolve.py --mark --lane G    # Mark lane G
"""

import os
import re
import sys
import glob
import yaml
import subprocess
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
COMMAND_TIMEOUT = 10  # seconds

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

def get_issue_status(content: str) -> str:
    """Get issue status from content."""
    if 'status: "RESOLVED"' in content or 'Status: RESOLVED' in content:
        return "RESOLVED"
    return "OPEN"

def extract_verification_commands(content: str) -> List[Dict]:
    """Extract verification commands from issue file."""
    match = re.search(r'\*\*Verification Commands.*?\*\*.*?```bash\n(.*?)```', content, re.DOTALL)
    if not match:
        return []

    cmd_section = match.group(1)
    commands = []

    # Parse individual checks
    check_pattern = r'#\s*(Check\s*\d+):\s*([^\n]+)\n([^\n#]+)'
    for m in re.finditer(check_pattern, cmd_section):
        cmd = m.group(3).strip()
        if cmd and not cmd.startswith('#'):
            commands.append({
                'check': m.group(1).strip(),
                'name': m.group(2).strip(),
                'command': cmd
            })

    # Fallback: look for test commands
    if not commands:
        for line in cmd_section.split('\n'):
            line = line.strip()
            if line.startswith('test ') or 'echo' in line:
                commands.append({
                    'check': 'check',
                    'name': 'verification',
                    'command': line
                })

    return commands

def run_command(command: str, timeout: int = COMMAND_TIMEOUT) -> Tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)

# =============================================================================
# DETECTION
# =============================================================================

def check_issue_resolved(filepath: str) -> Tuple[bool, int, int, str]:
    """
    Check if an issue is actually resolved.
    Returns: (is_resolved, passed_count, total_count, details)
    """
    frontmatter, content, _, _ = parse_frontmatter(filepath)

    if not frontmatter:
        return False, 0, 0, "No frontmatter"

    commands = extract_verification_commands(content)
    if not commands:
        return False, 0, 0, "No verification commands"

    passed = 0
    total = len(commands)
    details = []

    for cmd_info in commands:
        exit_code, stdout, stderr = run_command(cmd_info['command'])

        # Check if passed
        is_pass = 'PASS' in stdout.upper() or (exit_code == 0 and 'FAIL' not in stdout.upper())

        if is_pass:
            passed += 1
        else:
            details.append(f"{cmd_info['name']}: FAILED")

    is_resolved = passed == total and total > 0

    if is_resolved:
        return True, passed, total, "All checks pass"
    else:
        return False, passed, total, "; ".join(details[:3])

def mark_as_resolved(filepath: str) -> bool:
    """Mark an issue as RESOLVED."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return False

    # Update status in frontmatter
    content = re.sub(r'status:\s*"OPEN"', 'status: "RESOLVED"', content)
    content = re.sub(r'Status:\s*OPEN', 'Status: RESOLVED', content)

    # Add resolution date if not present
    if 'Date Resolved:' in content and '(leave blank' not in content.split('Date Resolved:')[1][:50]:
        pass  # Already has date
    else:
        today = datetime.now().strftime('%Y-%m-%d')
        content = re.sub(
            r'Date Resolved:\s*\(leave blank[^)]*\)',
            f'Date Resolved: {today}',
            content
        )
        content = re.sub(
            r'Date Resolved:\s*$',
            f'Date Resolved: {today}',
            content,
            flags=re.MULTILINE
        )

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except:
        return False

# =============================================================================
# PROCESSING
# =============================================================================

def process_all(issues_dir: str, lane: str = None, mark: bool = False) -> Dict[str, int]:
    """Process all OPEN issues to detect resolved ones."""
    stats = {
        'scanned': 0,
        'already_resolved': 0,
        'newly_resolved': 0,
        'still_open': 0,
        'errors': 0,
        'marked': 0
    }

    if lane:
        files = glob.glob(os.path.join(issues_dir, lane.upper(), '*.md'))
    else:
        files = glob.glob(os.path.join(issues_dir, '*', '*.md'))

    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    print("=" * 70)
    print("the system AUTOMATED RESOLUTION DETECTOR")
    print("=" * 70)
    print(f"Mode: {'MARK RESOLVED' if mark else 'DETECT ONLY'}")
    print(f"Files to scan: {len(files)}")
    print("=" * 70)
    print()

    newly_resolved = []

    for filepath in sorted(files):
        basename = os.path.basename(filepath)
        stats['scanned'] += 1

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            stats['errors'] += 1
            continue

        # Skip already resolved
        if get_issue_status(content) == "RESOLVED":
            stats['already_resolved'] += 1
            continue

        # Check if actually resolved
        is_resolved, passed, total, details = check_issue_resolved(filepath)

        if is_resolved:
            stats['newly_resolved'] += 1
            newly_resolved.append((basename, passed, total))
            print(f"\u2705 {basename}: RESOLVED ({passed}/{total} checks pass)")

            if mark:
                if mark_as_resolved(filepath):
                    stats['marked'] += 1
                    print(f"   \u2192 Marked as RESOLVED")
                else:
                    print(f"   \u2192 Failed to mark")
        else:
            stats['still_open'] += 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"   Total scanned:      {stats['scanned']}")
    print(f"   Already resolved:   {stats['already_resolved']}")
    print(f"   Newly detected:     {stats['newly_resolved']}")
    print(f"   Still open:         {stats['still_open']}")
    print(f"   Errors:             {stats['errors']}")

    if mark:
        print(f"   Marked resolved:    {stats['marked']}")

    if newly_resolved and not mark:
        print()
        print("-" * 70)
        print("ISSUES READY TO RESOLVE")
        print("-" * 70)
        for basename, passed, total in newly_resolved:
            print(f"   {basename} ({passed}/{total} checks)")
        print()
        print("Run with --mark to mark these as RESOLVED")

    print("=" * 70)

    return stats

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Detect and mark resolved the system issues'
    )
    parser.add_argument('--mark', '-m', action='store_true', help='Mark detected issues as RESOLVED')
    parser.add_argument('--lane', '-l', type=str, help='Process single lane')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)

    args = parser.parse_args()

    stats = process_all(
        args.issues_dir,
        lane=args.lane,
        mark=args.mark
    )

    sys.exit(0)

if __name__ == '__main__':
    main()
