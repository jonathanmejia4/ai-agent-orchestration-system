#!/usr/bin/env python3
"""
Batch Verification Runner

Runs verification across multiple issues and generates summary reports.
Designed for agent use to verify fixes in bulk.

Usage:
    python3 tools/batch_verify.py                    # Verify all OPEN issues
    python3 tools/batch_verify.py --lane G           # Verify lane G only
    python3 tools/batch_verify.py --issues G-01,G-02 # Specific issues
    python3 tools/batch_verify.py --resolved         # Verify resolved issues
    python3 tools/batch_verify.py --output report.json
"""

import os
import re
import sys
import glob
import json
import yaml
import subprocess
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
MAX_WORKERS = 4
COMMAND_TIMEOUT = 10  # seconds per command

# =============================================================================
# PARSING
# =============================================================================

def parse_frontmatter(filepath: str) -> Optional[Dict]:
    """Parse YAML frontmatter from issue file."""
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
        return yaml.safe_load(content[4:end])
    except yaml.YAMLError:
        return None

def extract_verification_commands(filepath: str) -> List[Dict]:
    """Extract verification commands from issue file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []

    # Find Verification Commands section
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

    # Fallback: look for any test commands
    if not commands:
        for line in cmd_section.split('\n'):
            line = line.strip()
            if line.startswith('test ') or line.startswith('python3 '):
                commands.append({
                    'check': 'check',
                    'name': 'verification',
                    'command': line
                })

    return commands

def get_issue_status(filepath: str) -> str:
    """Get issue status from file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return "UNKNOWN"

    if 'status: "RESOLVED"' in content or 'Status: RESOLVED' in content:
        return "RESOLVED"
    return "OPEN"

# =============================================================================
# VERIFICATION
# =============================================================================

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

def verify_issue(filepath: str) -> Dict:
    """Verify a single issue and return results."""
    basename = os.path.basename(filepath)
    issue_id = basename.replace('.md', '')

    result = {
        'issue_id': issue_id,
        'filepath': filepath,
        'status': get_issue_status(filepath),
        'checks': [],
        'passed': 0,
        'failed': 0,
        'total': 0,
        'verified': False,
        'timestamp': datetime.now().isoformat()
    }

    # Get frontmatter
    frontmatter = parse_frontmatter(filepath)
    if frontmatter:
        result['pattern'] = frontmatter.get('verification_pattern', 'unknown')
        result['severity'] = frontmatter.get('severity', 0)

    # Get verification commands
    commands = extract_verification_commands(filepath)
    result['total'] = len(commands)

    if not commands:
        result['error'] = "No verification commands found"
        return result

    # Run each command
    for cmd_info in commands:
        exit_code, stdout, stderr = run_command(cmd_info['command'])

        check_result = {
            'name': cmd_info['name'],
            'command': cmd_info['command'],
            'exit_code': exit_code,
            'stdout': stdout[:200],  # Truncate
            'passed': 'PASS' in stdout.upper() or exit_code == 0
        }

        result['checks'].append(check_result)

        if check_result['passed']:
            result['passed'] += 1
        else:
            result['failed'] += 1

    # Determine if fully verified
    result['verified'] = result['passed'] == result['total'] and result['total'] > 0

    return result

def verify_issues_parallel(filepaths: List[str], max_workers: int = MAX_WORKERS) -> List[Dict]:
    """Verify multiple issues in parallel."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(verify_issue, fp): fp for fp in filepaths}

        for future in as_completed(future_to_file):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                filepath = future_to_file[future]
                results.append({
                    'issue_id': os.path.basename(filepath).replace('.md', ''),
                    'filepath': filepath,
                    'error': str(e)
                })

    return results

# =============================================================================
# REPORTING
# =============================================================================

def generate_report(results: List[Dict]) -> Dict:
    """Generate summary report from verification results."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_issues': len(results),
        'verified': 0,
        'failed': 0,
        'errors': 0,
        'total_checks': 0,
        'passed_checks': 0,
        'by_status': {'OPEN': 0, 'RESOLVED': 0},
        'by_pattern': {},
        'issues': results
    }

    for r in results:
        if 'error' in r and not r.get('checks'):
            report['errors'] += 1
            continue

        if r.get('verified'):
            report['verified'] += 1
        else:
            report['failed'] += 1

        report['total_checks'] += r.get('total', 0)
        report['passed_checks'] += r.get('passed', 0)

        status = r.get('status', 'UNKNOWN')
        if status in report['by_status']:
            report['by_status'][status] += 1

        pattern = r.get('pattern', 'unknown')
        if pattern not in report['by_pattern']:
            report['by_pattern'][pattern] = {'total': 0, 'verified': 0}
        report['by_pattern'][pattern]['total'] += 1
        if r.get('verified'):
            report['by_pattern'][pattern]['verified'] += 1

    return report

def print_report(report: Dict, verbose: bool = False):
    """Print verification report to console."""
    print("=" * 70)
    print("the system BATCH VERIFICATION REPORT")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print()

    print("-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"   Total Issues:     {report['total_issues']}")
    print(f"   Fully Verified:   {report['verified']}")
    print(f"   Failed:           {report['failed']}")
    print(f"   Errors:           {report['errors']}")
    print()
    print(f"   Total Checks:     {report['total_checks']}")
    print(f"   Passed Checks:    {report['passed_checks']}")

    if report['total_checks'] > 0:
        pct = report['passed_checks'] / report['total_checks'] * 100
        print(f"   Check Pass Rate:  {pct:.1f}%")

    print()
    print("-" * 70)
    print("BY STATUS")
    print("-" * 70)
    for status, count in report['by_status'].items():
        print(f"   {status}: {count}")

    print()
    print("-" * 70)
    print("BY PATTERN")
    print("-" * 70)
    for pattern, stats in sorted(report['by_pattern'].items()):
        pct = (stats['verified'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"   {pattern}: {stats['verified']}/{stats['total']} ({pct:.1f}%)")

    if verbose:
        print()
        print("-" * 70)
        print("FAILED ISSUES")
        print("-" * 70)
        for issue in report['issues']:
            if not issue.get('verified') and 'error' not in issue:
                print(f"   {issue['issue_id']}: {issue.get('passed', 0)}/{issue.get('total', 0)} checks passed")
                for check in issue.get('checks', []):
                    if not check.get('passed'):
                        print(f"      - {check['name']}: FAILED")

    print()
    print("=" * 70)

    # Final status
    if report['verified'] == report['total_issues']:
        print("\u2705 ALL ISSUES VERIFIED")
    elif report['verified'] > 0:
        pct = report['verified'] / report['total_issues'] * 100
        print(f"\u26a0\ufe0f  {pct:.1f}% OF ISSUES VERIFIED")
    else:
        print("\u274c NO ISSUES VERIFIED")

    print("=" * 70)

# =============================================================================
# MAIN
# =============================================================================

def get_issue_files(issues_dir: str, lane: str = None, issue_ids: List[str] = None,
                    include_resolved: bool = False) -> List[str]:
    """Get list of issue files to verify."""
    if issue_ids:
        # Specific issues
        files = []
        for issue_id in issue_ids:
            # Try to find the file
            pattern = os.path.join(issues_dir, '*', f'{issue_id}.md')
            matches = glob.glob(pattern)
            files.extend(matches)
        return files

    if lane:
        pattern = os.path.join(issues_dir, lane.upper(), '*.md')
    else:
        pattern = os.path.join(issues_dir, '*', '*.md')

    files = glob.glob(pattern)
    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    if not include_resolved:
        # Filter to OPEN issues only
        files = [f for f in files if get_issue_status(f) == 'OPEN']

    return sorted(files)

def main():
    parser = argparse.ArgumentParser(
        description='Run batch verification across the system issues'
    )
    parser.add_argument('--lane', '-l', type=str, help='Verify single lane')
    parser.add_argument('--issues', '-i', type=str, help='Comma-separated issue IDs')
    parser.add_argument('--resolved', '-r', action='store_true', help='Include resolved issues')
    parser.add_argument('--output', '-o', type=str, help='Output JSON report file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show failed details')
    parser.add_argument('--workers', '-w', type=int, default=MAX_WORKERS, help='Parallel workers')
    parser.add_argument('--issues-dir', '-d', type=str, default=ISSUES_DIR)

    args = parser.parse_args()

    # Get files to verify
    issue_ids = args.issues.split(',') if args.issues else None
    files = get_issue_files(
        args.issues_dir,
        lane=args.lane,
        issue_ids=issue_ids,
        include_resolved=args.resolved
    )

    if not files:
        print("No issues to verify")
        sys.exit(0)

    print(f"Verifying {len(files)} issues...")
    print()

    # Run verification
    results = verify_issues_parallel(files, max_workers=args.workers)

    # Generate report
    report = generate_report(results)

    # Print report
    print_report(report, verbose=args.verbose)

    # Save JSON if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {args.output}")

    # Exit code based on results
    if report['verified'] == report['total_issues']:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
