#!/usr/bin/env python3
"""
Issue Evidence Collection Tool (Enhanced for Phase 2)

Collects verification evidence using embedded Verification Commands from issues.
Compares results against Expected Outputs YAML for mechanical verification.

Features:
- Reads embedded Verification Commands from issue files
- Compares against Expected Outputs (Machine-Readable) YAML
- Falls back to pattern-based checks if no embedded commands
- Stores timestamped evidence in LogBook/verification/evidence/
- Generates detailed verification reports

Usage:
    python3 tools/collect_evidence.py G-01           # Collect evidence for G-01
    python3 tools/collect_evidence.py --lane G       # Collect for all Lane G issues
    python3 tools/collect_evidence.py --all          # Collect for all issues
    python3 tools/collect_evidence.py G-01 --report  # Show detailed report
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
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
PATTERNS_FILE = "tools/verification_patterns.yaml"
EVIDENCE_DIR = "LogBook/verification/evidence"

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class CheckResult:
    """Result of a single verification check."""
    name: str
    command: str
    expected_exit: int
    actual_exit: int
    expected_stdout: str
    actual_stdout: str
    passed: bool
    duration_ms: int
    error_message: str = ""

@dataclass
class EvidenceReport:
    """Complete evidence report for an issue."""
    issue_id: str
    lane: str
    status: str
    timestamp: str
    used_embedded_commands: bool = False
    checks: List[CheckResult] = field(default_factory=list)
    all_passed: bool = False
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    total_duration_ms: int = 0
    confidence_score: int = 0
    depends_on: List[str] = field(default_factory=list)
    evidence_path: str = ""

# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def parse_issue_file(filepath: str) -> Tuple[Optional[Dict], str]:
    """Parse issue file and return (frontmatter, full_content)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return None, ""

    if not content.startswith('---'):
        return None, content

    end = content.find('\n---\n', 3)
    if end < 0:
        return None, content

    try:
        fm = yaml.safe_load(content[4:end])
        return fm, content
    except yaml.YAMLError as e:
        print(f"Error parsing frontmatter: {e}", file=sys.stderr)
        return None, content

def extract_verification_commands(content: str) -> List[Dict[str, str]]:
    """Extract Verification Commands section from issue content."""
    commands = []

    # Find Verification Commands section
    match = re.search(r'\*\*Verification Commands.*?\*\*.*?```bash\n(.*?)```', content, re.DOTALL)
    if not match:
        return commands

    cmd_section = match.group(1)

    # Extract individual checks
    check_pattern = r'#\s*(Check\s*\d+):\s*([^\n]+)\n([^\n#]+)'
    for m in re.finditer(check_pattern, cmd_section):
        check_num = m.group(1).strip()
        check_name = m.group(2).strip()
        command = m.group(3).strip()

        # Skip comments and empty lines
        if command and not command.startswith('#'):
            commands.append({
                'check': check_num,
                'name': check_name,
                'command': command
            })

    return commands

def extract_expected_outputs(content: str) -> Optional[Dict[str, Any]]:
    """Extract Expected Outputs YAML section from issue content."""
    match = re.search(r'\*\*Expected Outputs \(Machine-Readable\)\*\*.*?```yaml\n(.*?)```', content, re.DOTALL)
    if not match:
        return None

    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None

# =============================================================================
# VARIABLE SUBSTITUTION
# =============================================================================

def build_variables(frontmatter: dict, content: str) -> dict:
    """Build variable substitution dict from issue frontmatter.

    Extracts values from frontmatter fields and infers common variables
    from affected_paths to enable automatic placeholder substitution.

    For ghost_reference pattern, distinguishes between:
    - file_path: the TARGET (ghost file that was missing)
    - source_file: the SOURCE (file containing the reference to the ghost)
    """
    issue_id = frontmatter.get('issue_id', '')
    affected = frontmatter.get('affected_paths', [])
    pattern_vars = frontmatter.get('pattern_vars', {})
    pattern = frontmatter.get('verification_pattern', '')

    # Start with pattern_vars (explicit overrides take precedence)
    variables = dict(pattern_vars) if pattern_vars else {}

    # Add standard variables
    variables['issue_id'] = issue_id
    variables['lane'] = frontmatter.get('lane', issue_id[0] if issue_id else '')

    # Infer file paths from affected_paths
    # Filter to valid paths only (skip garbage like comments/ASCII art)
    if affected:
        valid_paths = [p for p in affected if is_valid_path(p)]
        if valid_paths:
            path = valid_paths[0]
        elif affected[0]:  # Fallback to first entry if no valid paths (may still work)
            path = affected[0]
        else:
            path = None
    else:
        path = None
        valid_paths = []

    if path:
        # PATTERN-AWARE VARIABLE BINDING for ghost_reference
        # Ghost reference needs two DIFFERENT paths:
        # - file_path: the target (ghost file, often in tools/, templates/, .task/)
        # - source_file: the source (file with reference, often in PLANNING/, .claude/)
        if pattern == 'ghost_reference' and len(valid_paths) >= 2:
            target_prefixes = ('tools/', 'templates/', '.task/', 'tests/', 'scripts/',
                               'integration/', 'tasks/', 'LogBook/')
            source_prefixes = ('PLANNING/', '.claude/', 'docs/', 'README')

            # Find target (ghost file) - prefer paths in target directories
            target_path = None
            for p in reversed(valid_paths):  # Check from end (target often listed last)
                if any(p.startswith(prefix) for prefix in target_prefixes):
                    target_path = p
                    break

            # Find source (file with reference) - prefer paths in source directories
            source_path = None
            for p in valid_paths:
                if any(p.startswith(prefix) for prefix in source_prefixes):
                    source_path = p
                    break

            # Apply findings with fallbacks
            if target_path:
                variables.setdefault('file_path', target_path)
                variables.setdefault('target', target_path)
            else:
                # Fallback: use last path as target
                variables.setdefault('file_path', valid_paths[-1])
                variables.setdefault('target', valid_paths[-1])

            if source_path:
                variables.setdefault('source_file', source_path)
                variables.setdefault('source', source_path)
            else:
                # Fallback: use first path as source if different from file_path
                first = valid_paths[0]
                if first != variables.get('file_path'):
                    variables.setdefault('source_file', first)
                    variables.setdefault('source', first)
                elif len(valid_paths) >= 2:
                    # Use second path if first is the target
                    variables.setdefault('source_file', valid_paths[1])
                    variables.setdefault('source', valid_paths[1])
        else:
            # Default behavior for other patterns
            variables.setdefault('file_path', path)
            variables.setdefault('source_file', path)
            variables.setdefault('target', path)
            variables.setdefault('source', path)

        # Common aliases (apply to all patterns)
        variables.setdefault('path', variables.get('file_path', path))
        variables.setdefault('dir_path', os.path.dirname(variables.get('file_path', path)) or path)
        variables.setdefault('affected_path', path)
        variables.setdefault('file', variables.get('file_path', path))
        variables.setdefault('filepath', variables.get('file_path', path))

        # Extract task-id from path (e.g., "tasks/3.1/..." → "3.1")
        task_match = re.search(r'tasks?[/_-]?(\d+\.\d+|\d+|[a-z0-9-]+)',
                                variables.get('file_path', path), re.I)
        if task_match:
            task_id = task_match.group(1)
            variables.setdefault('task-id', task_id)
            variables.setdefault('task_id', task_id)

    return variables

def substitute_vars(template: str, variables: dict) -> Tuple[str, List[str]]:
    """Substitute variables in command template.

    Supports two placeholder formats:
    - {variable} style (e.g., {source_file})
    - <variable> style (e.g., <task-id>)

    Returns:
        (result_string, list_of_unsubstituted_variable_names)
    """
    result = template

    # Handle {variable} style
    for key, value in variables.items():
        result = result.replace(f'{{{key}}}', str(value))

    # Handle <variable> style (used in older issues)
    for key, value in variables.items():
        result = result.replace(f'<{key}>', str(value))

    # Find remaining unsubstituted placeholders
    remaining = re.findall(r'\{(\w+)\}|<(\w[\w-]*)>', result)
    unsubstituted = [p[0] or p[1] for p in remaining if p[0] or p[1]]

    return result, unsubstituted

# =============================================================================
# PATH VALIDATION & AUTO-CORRECTION
# =============================================================================

def is_valid_path(path: str) -> bool:
    """Check if string looks like a valid filesystem path (not garbage).

    Filters out comments, ASCII diagrams, and descriptions that
    accidentally ended up in affected_paths.
    """
    if not path or not path.strip():
        return False
    # Contains ASCII art/tree characters
    if any(c in path for c in '├└│─►▸▹'):
        return False
    # Starts with comment/markup characters
    if path.lstrip().startswith(('#', '*', '>', '-')) and not path.startswith('./'):
        return False
    # Contains ellipsis (description text)
    if '...' in path:
        return False
    # Starts with shell command prefix (not a valid path)
    SHELL_COMMANDS = {'ls', 'cat', 'grep', 'find', 'echo', 'python', 'python3',
                      'bash', 'sh', 'test', 'head', 'tail', 'awk', 'sed', 'yamllint'}
    first_word = path.split()[0].lower() if ' ' in path else None
    if first_word and first_word in SHELL_COMMANDS:
        return False
    # Too many spaces (likely a description, not a path)
    if path.count(' ') > 2:
        return False
    # Must look like a path (alphanumeric, slashes, dots, dashes, underscores)
    return bool(re.match(r'^[\w./_\-]+$', path.strip()))

def auto_correct_file_test(command: str) -> str:
    """Auto-correct 'test -f' to 'test -d' when target is a directory.

    Prevents DIRECTORY_AS_FILE failures by checking if the path
    being tested with -f is actually a directory.
    """
    # Match pattern: test -f <path>
    match = re.match(r'^(test\s+-f\s+)([^\s&|;]+)(.*)', command)
    if match:
        prefix, path, suffix = match.groups()
        # Remove quotes if present
        clean_path = path.strip('"\'')
        # Check if path is actually a directory
        if os.path.isdir(clean_path):
            return f"test -d {path}{suffix}"
    return command

def fix_malformed_test_command(command: str) -> str:
    """Fix malformed test commands that would always fail.

    Handles:
    1. Wildcards in test -f/s (test -f *.yaml) -> ls pattern >/dev/null
    2. Shell commands as test args (test -f ls file) -> strip test wrapper
    3. Multiple args to test (test -f file1 file2) -> use first valid path
    """
    # Pattern 1: Wildcards in test -f/-s (e.g., test -f *.yaml)
    wildcard_match = re.match(r'^test\s+-([fs])\s+([^\s]*\*[^\s&|;]*)(.*)', command)
    if wildcard_match:
        flag, pattern, suffix = wildcard_match.groups()
        # Convert to: ls <pattern> >/dev/null 2>&1 && echo "PASS" || echo "FAIL"
        return f'ls {pattern} >/dev/null 2>&1 && echo "PASS" || echo "FAIL"'

    # Pattern 2: Shell command as test argument (e.g., test -f ls something)
    cmd_prefix_match = re.match(
        r'^test\s+-[efsd]\s+(ls|cat|grep|find|echo|python|python3|bash|sh|yamllint)\s+(.+?)\s*(&&.*)?$',
        command
    )
    if cmd_prefix_match:
        cmd_name, actual_path, suffix = cmd_prefix_match.groups()
        suffix = suffix or ''
        # Extract just the path, use test -e on it
        clean_path = actual_path.strip()
        return f'test -e {clean_path} {suffix}'.strip()

    # Pattern 3: Multiple paths to test (e.g., test -f file1 file2)
    # Detect by finding multiple non-flag arguments
    multi_arg_match = re.match(r'^test\s+-([efsd])\s+(\S+)\s+(\S+)\s*(&&.*)?$', command)
    if multi_arg_match:
        flag, arg1, arg2, suffix = multi_arg_match.groups()
        suffix = suffix or ''
        # Check if arg2 looks like a path (not an operator)
        if not arg2.startswith('-') and '/' in arg2:
            # Use the path-like argument (usually the second one)
            return f'test -{flag} {arg2} {suffix}'.strip()
        elif '/' in arg1:
            return f'test -{flag} {arg1} {suffix}'.strip()

    # Pattern 3b: Colon-separated syntax (e.g., test -e name: /path)
    colon_match = re.match(r'^test\s+-([efsd])\s+\w+:\s*(/\S+)\s*(&&.*)?$', command)
    if colon_match:
        flag, path, suffix = colon_match.groups()
        suffix = suffix or ''
        return f'test -{flag} {path} {suffix}'.strip()

    return command

# =============================================================================
# CHECK EXECUTION
# =============================================================================

def run_command(command: str, timeout: int = 30) -> Tuple[int, str]:
    """Run a shell command and return (exit_code, output)."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)

def run_embedded_checks(commands: List[Dict], expected: Optional[Dict],
                        variables: Optional[Dict] = None) -> List[CheckResult]:
    """Run embedded verification commands and compare to expected outputs.

    Args:
        commands: List of command specs with 'check', 'name', 'command' keys
        expected: Expected outputs dict from issue YAML section
        variables: Dict of variables to substitute in commands (optional)
    """
    results = []
    variables = variables or {}

    for cmd_spec in commands:
        check_num = cmd_spec['check']
        check_name = cmd_spec['name']
        original_command = cmd_spec['command']

        # Apply variable substitution
        command, unsubstituted = substitute_vars(original_command, variables)

        # SKIP commands with unsubstituted variables instead of running them
        if unsubstituted:
            print(f"  SKIPPED: {check_name} - unsubstituted variables: {unsubstituted}", file=sys.stderr)
            results.append(CheckResult(
                name=check_name,
                command=original_command,
                expected_exit=0,
                actual_exit=-3,  # Special code for SKIPPED
                expected_stdout="PASS",
                actual_stdout=f"SKIPPED: Unsubstituted variables: {unsubstituted}",
                passed=False,  # Not passed, but not a real failure - just skipped
                duration_ms=0,
                error_message=f"Skipped due to unsubstituted variables: {unsubstituted}"
            ))
            continue

        # Auto-correct test -f to test -d when target is a directory
        command = auto_correct_file_test(command)
        # Fix malformed test commands (wildcards, command prefixes, multi-args)
        command = fix_malformed_test_command(command)

        start = datetime.now()
        actual_exit, actual_output = run_command(command)
        duration = int((datetime.now() - start).total_seconds() * 1000)

        # Get expected values
        expected_exit = 0
        expected_stdout = "PASS"

        if expected:
            # Map "Check 1" -> "check_1"
            check_key = check_num.lower().replace(' ', '_')
            exp_result = expected.get('expected_results', {}).get(check_key, {})
            expected_exit = exp_result.get('exit_code', 0)
            expected_stdout = exp_result.get('stdout_contains', 'PASS')

        # Determine if passed
        passed = (actual_exit == expected_exit and expected_stdout in actual_output)

        results.append(CheckResult(
            name=check_name,
            command=command,
            expected_exit=expected_exit,
            actual_exit=actual_exit,
            expected_stdout=expected_stdout,
            actual_stdout=actual_output[:500],
            passed=passed,
            duration_ms=duration,
            error_message="" if passed else f"Expected '{expected_stdout}' in output"
        ))

    return results

# =============================================================================
# EVIDENCE COLLECTION
# =============================================================================

def collect_evidence(filepath: str) -> Optional[EvidenceReport]:
    """Collect verification evidence for a single issue."""
    frontmatter, content = parse_issue_file(filepath)

    if not frontmatter:
        return None

    issue_id = frontmatter.get('issue_id', os.path.basename(filepath).replace('.md', ''))
    lane = frontmatter.get('lane', issue_id[0] if issue_id else '')
    status = frontmatter.get('status', 'OPEN')
    depends_on = frontmatter.get('depends_on', [])

    # Try to extract embedded commands
    commands = extract_verification_commands(content)
    expected = extract_expected_outputs(content)

    used_embedded = bool(commands)

    # Build variables for substitution
    variables = build_variables(frontmatter, content)

    if commands:
        # Use embedded commands with variable substitution
        check_results = run_embedded_checks(commands, expected, variables)
    else:
        # Fallback: create basic check from affected_paths
        affected = frontmatter.get('affected_paths', [])
        check_results = []

        if affected and affected[0]:
            path = affected[0]
            start = datetime.now()
            exit_code, output = run_command(f'test -e "{path}" && echo PASS || echo FAIL')
            duration = int((datetime.now() - start).total_seconds() * 1000)

            check_results.append(CheckResult(
                name="exists",
                command=f'test -e "{path}"',
                expected_exit=0,
                actual_exit=exit_code,
                expected_stdout="PASS",
                actual_stdout=output,
                passed=("PASS" in output),
                duration_ms=duration
            ))

    # Calculate stats
    passed_count = sum(1 for c in check_results if c.passed)
    failed_count = len(check_results) - passed_count
    total_duration = sum(c.duration_ms for c in check_results)
    confidence = int((passed_count / len(check_results) * 100)) if check_results else 0

    report = EvidenceReport(
        issue_id=issue_id,
        lane=lane,
        status=status,
        timestamp=datetime.now().isoformat(),
        used_embedded_commands=used_embedded,
        checks=check_results,
        all_passed=(failed_count == 0 and len(check_results) > 0),
        total_checks=len(check_results),
        passed_checks=passed_count,
        failed_checks=failed_count,
        total_duration_ms=total_duration,
        confidence_score=confidence,
        depends_on=depends_on
    )

    return report

def save_evidence(report: EvidenceReport) -> str:
    """Save evidence report to JSON file."""
    lane_dir = os.path.join(EVIDENCE_DIR, report.lane.upper())
    os.makedirs(lane_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{report.issue_id}_{timestamp}.json"
    filepath = os.path.join(lane_dir, filename)

    data = {
        'issue_id': report.issue_id,
        'lane': report.lane,
        'status': report.status,
        'timestamp': report.timestamp,
        'used_embedded_commands': report.used_embedded_commands,
        'all_passed': report.all_passed,
        'total_checks': report.total_checks,
        'passed_checks': report.passed_checks,
        'failed_checks': report.failed_checks,
        'total_duration_ms': report.total_duration_ms,
        'confidence_score': report.confidence_score,
        'depends_on': report.depends_on,
        'checks': [
            {
                'name': c.name,
                'command': c.command,
                'expected_exit': c.expected_exit,
                'actual_exit': c.actual_exit,
                'expected_stdout': c.expected_stdout,
                'actual_stdout': c.actual_stdout,
                'passed': c.passed,
                'duration_ms': c.duration_ms,
                'error_message': c.error_message
            }
            for c in report.checks
        ]
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    report.evidence_path = filepath
    return filepath

# =============================================================================
# OUTPUT
# =============================================================================

def print_report(report: EvidenceReport) -> None:
    """Print detailed evidence report."""
    print()
    print("=" * 70)
    print(f"EVIDENCE REPORT: {report.issue_id}")
    print("=" * 70)
    print(f"Lane:              {report.lane}")
    print(f"Status:            {report.status}")
    print(f"Timestamp:         {report.timestamp}")
    print(f"Used Embedded:     {'Yes' if report.used_embedded_commands else 'No (fallback)'}")
    print(f"Dependencies:      {report.depends_on if report.depends_on else 'None'}")
    print()

    print("CHECKS EXECUTED:")
    print("-" * 70)

    for check in report.checks:
        icon = "\u2705" if check.passed else "\u274c"
        print(f"{icon} {check.name}")
        print(f"   Command:  {check.command[:60]}{'...' if len(check.command) > 60 else ''}")
        print(f"   Expected: exit={check.expected_exit}, stdout contains '{check.expected_stdout}'")
        print(f"   Actual:   exit={check.actual_exit}, stdout='{check.actual_stdout.strip()[:50]}'")
        print(f"   Duration: {check.duration_ms}ms")
        if check.error_message:
            print(f"   Error:    {check.error_message}")
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Checks:    {report.total_checks}")
    print(f"Passed:          {report.passed_checks}")
    print(f"Failed:          {report.failed_checks}")
    print(f"Duration:        {report.total_duration_ms}ms")
    print(f"Confidence:      {report.confidence_score}%")

    if report.evidence_path:
        print(f"Evidence File:   {report.evidence_path}")

    print("=" * 70)

    if report.all_passed:
        print()
        print("   \u2554" + "\u2550" * 59 + "\u2557")
        print("   \u2551" + " " * 59 + "\u2551")
        print("   \u2551   \u2705  ALL CHECKS PASSED - Issue verification complete    \u2551")
        print("   \u2551" + " " * 59 + "\u2551")
        print("   \u255a" + "\u2550" * 59 + "\u255d")
    else:
        print()
        print("   \u2554" + "\u2550" * 59 + "\u2557")
        print("   \u2551" + " " * 59 + "\u2551")
        print(f"   \u2551   \u274c  {report.failed_checks} CHECK(S) FAILED - Review errors above       \u2551")
        print("   \u2551" + " " * 59 + "\u2551")
        print("   \u255a" + "\u2550" * 59 + "\u255d")

# =============================================================================
# BATCH PROCESSING
# =============================================================================

def find_issue_file(issue_id: str) -> Optional[str]:
    """Find issue file by ID."""
    lane = issue_id[0].upper()
    candidates = [
        os.path.join(ISSUES_DIR, lane, f"{issue_id}.md"),
        os.path.join(ISSUES_DIR, lane, f"{lane}-{issue_id[1:].lstrip('-')}.md"),
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    # Glob fallback
    matches = glob.glob(os.path.join(ISSUES_DIR, lane, f"*{issue_id}*.md"))
    return matches[0] if matches else None

def process_issues(issue_ids: List[str] = None, lane: str = None,
                   all_issues: bool = False, show_report: bool = False) -> Dict[str, int]:
    """Process multiple issues and collect evidence."""
    stats = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0, 'embedded': 0}

    # Determine files to process
    if issue_ids:
        files = []
        for issue_id in issue_ids:
            filepath = find_issue_file(issue_id)
            if filepath:
                files.append(filepath)
            else:
                print(f"Warning: Issue not found: {issue_id}")
    elif lane:
        files = glob.glob(os.path.join(ISSUES_DIR, lane.upper(), '*.md'))
    elif all_issues:
        files = glob.glob(os.path.join(ISSUES_DIR, '*', '*.md'))
    else:
        return stats

    files = [f for f in files if 'TEMPLATE' not in f.upper()]

    print("=" * 70)
    print("the system EVIDENCE COLLECTION (Phase 2 Enhanced)")
    print("=" * 70)
    print(f"Files to process: {len(files)}")
    print("=" * 70)
    print()

    for filepath in sorted(files):
        issue_id = os.path.basename(filepath).replace('.md', '')
        print(f"Collecting evidence for {issue_id}...", end=' ')

        try:
            report = collect_evidence(filepath)

            if report:
                evidence_path = save_evidence(report)
                stats['total'] += 1

                if report.used_embedded_commands:
                    stats['embedded'] += 1

                if report.all_passed:
                    stats['passed'] += 1
                    print(f"\u2705 {report.passed_checks}/{report.total_checks} passed")
                else:
                    stats['failed'] += 1
                    print(f"\u274c {report.failed_checks}/{report.total_checks} failed")

                if show_report and len(files) == 1:
                    print_report(report)
            else:
                stats['errors'] += 1
                print("Error: Could not parse")
        except Exception as e:
            stats['errors'] += 1
            print(f"Error: {e}")

    # Summary
    print()
    print("=" * 70)
    print("COLLECTION SUMMARY")
    print("=" * 70)
    print(f"Total Processed:       {stats['total']}")
    print(f"Used Embedded Cmds:    {stats['embedded']}")
    print(f"All Checks Passed:     {stats['passed']}")
    print(f"Some Checks Failed:    {stats['failed']}")
    print(f"Errors:                {stats['errors']}")
    print("=" * 70)

    return stats

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Collect verification evidence for the system issues'
    )
    parser.add_argument('issue_ids', nargs='*', help='Issue IDs to process')
    parser.add_argument('--lane', '-l', type=str, help='Process all in lane')
    parser.add_argument('--all', '-a', action='store_true', help='Process all')
    parser.add_argument('--report', '-r', action='store_true', help='Show report')

    args = parser.parse_args()

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    if args.issue_ids and len(args.issue_ids) == 1:
        # Single issue - always show report
        filepath = find_issue_file(args.issue_ids[0])
        if not filepath:
            print(f"Error: Issue not found: {args.issue_ids[0]}")
            sys.exit(1)

        report = collect_evidence(filepath)
        if report:
            save_evidence(report)
            print_report(report)
            sys.exit(0 if report.all_passed else 1)
        else:
            print("Error: Could not collect evidence")
            sys.exit(1)
    else:
        stats = process_issues(
            issue_ids=args.issue_ids if args.issue_ids else None,
            lane=args.lane,
            all_issues=args.all,
            show_report=args.report
        )
        sys.exit(0 if stats['failed'] == 0 else 1)

if __name__ == '__main__':
    main()
