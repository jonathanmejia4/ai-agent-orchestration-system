#!/usr/bin/env python3
"""
Issue Verification Tool

Main tool for agents to verify if an issue fix was successful.
Reads issue frontmatter, runs verification checks, updates status.

Features:
- Reads YAML frontmatter for verification configuration
- Runs appropriate verification pattern checks
- Collects evidence and stores it
- Can update issue status based on results
- Generates verification reports
- Auto-corrects malformed verification commands

Usage:
    python3 tools/verify_issue.py G-01              # Verify single issue
    python3 tools/verify_issue.py G-01 --update     # Verify and update status
    python3 tools/verify_issue.py --lane G          # Verify all in lane
    python3 tools/verify_issue.py --all             # Verify all issues
    python3 tools/verify_issue.py G-01 --quick      # Quick check only
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
from dataclasses import dataclass

# =============================================================================
# MALFORMED COMMAND DETECTION AND AUTO-CORRECTION
# =============================================================================

# Patterns that indicate malformed verification commands
MALFORMED_PATTERNS = [
    # Command used as file path (test -f ls foo)
    (r'test\s+-[efds]\s+(ls|cat|grep|find|echo|test|python|python3)\s',
     "Shell command used as file path"),
    # Unsubstituted template variables
    (r'<[a-z_-]+>', "Unsubstituted template variable"),
    (r'\{[a-z_]+\}', "Unsubstituted template placeholder"),
    # Wrong test operator for path type
    (r'test\s+-f\s+\S+/$', "Using -f on directory path (should be -d)"),
]


def auto_correct_command(command: str) -> tuple:
    """
    Attempt to auto-correct common malformed verification commands.

    Handles the 5 main malformed patterns:
    1. test -f on directories → test -d
    2. Wildcards in test → ls with redirect
    3. Comment characters in paths → remove #
    4. Placeholder variables → test parent directory
    5. Multi-part commands as paths → extract valid command

    Returns:
        (corrected_command: str, was_corrected: bool, correction_note: str)
    """
    original = command
    corrected = command
    notes = []

    # Pattern 1: Fix test -f on directory paths (ending in /)
    # e.g., test -f LogBook/audit/ → test -d LogBook/audit/
    dir_pattern = r'test\s+-f\s+(\S+/)\s*&&'
    match = re.search(dir_pattern, corrected)
    if match:
        corrected = re.sub(r'test\s+-f\s+(\S+/)', r'test -d \1', corrected)
        notes.append("Changed -f to -d for directory path")

    # Pattern 2: Fix wildcards in test command (any test flag)
    # e.g., test -f templates/*.jinja2 → ls templates/*.jinja2 >/dev/null 2>&1
    # e.g., test -s LogBook/*/STATE.md → ls LogBook/*/STATE.md >/dev/null 2>&1
    wildcard_pattern = r'test\s+-[fdse]\s+(\S*\*\S*)\s*&&\s*echo\s+"?PASS"?'
    match = re.search(wildcard_pattern, corrected)
    if match:
        path = match.group(1)
        corrected = re.sub(
            wildcard_pattern,
            f'ls {path} >/dev/null 2>&1 && echo "PASS"',
            corrected
        )
        notes.append("Converted wildcard test to ls command")

    # Pattern 2b: Fix wildcards in git ls-files
    # e.g., git ls-files --error-unmatch PATH/* → ls PATH/* >/dev/null 2>&1
    git_wildcard_pattern = r'git\s+ls-files\s+--error-unmatch\s+(\S*\*\S*)'
    match = re.search(git_wildcard_pattern, corrected)
    if match:
        path = match.group(1)
        corrected = re.sub(
            git_wildcard_pattern + r'.*&&\s*echo\s+"?PASS"?',
            f'ls {path} >/dev/null 2>&1 && echo "PASS"',
            corrected
        )
        notes.append("Converted git ls-files wildcard to ls command")

    # Pattern 3: Remove comment characters from paths
    # e.g., test -f # LogBook/foo → test -f LogBook/foo
    comment_pattern = r'test\s+-([fd])\s+#\s*(\S+)'
    match = re.search(comment_pattern, corrected)
    if match:
        corrected = re.sub(comment_pattern, r'test -\1 \2', corrected)
        notes.append("Removed comment character from path")

    # Pattern 4: Handle placeholder variables - test parent directory
    # e.g., test -f /LogBook/bricks/<brick-id>/status.yaml → test -d LogBook/bricks/
    # e.g., test -s /LogBook/bricks/<brick-id>/status.yaml → test -d LogBook/bricks/
    placeholder_pattern = r'test\s+-[fdse]\s+/?(\S*)<[a-z_-]+>(\S*)'
    match = re.search(placeholder_pattern, corrected)
    if match:
        parent_path = match.group(1).rstrip('/')
        if parent_path:
            corrected = re.sub(
                placeholder_pattern + r'\s*&&\s*echo\s+"?PASS"?',
                f'test -d {parent_path}/ && echo "PASS"',
                corrected
            )
            notes.append(f"Replaced placeholder with parent directory test: {parent_path}/")

    # Pattern 4b: Handle placeholder variables in git ls-files
    # e.g., git ls-files /LogBook/<brick-id>/status.yaml → ls LogBook/ >/dev/null 2>&1
    git_placeholder_pattern = r'git\s+ls-files\s+--error-unmatch\s+/?(\S*)<[a-z_-]+>(\S*)'
    match = re.search(git_placeholder_pattern, corrected)
    if match:
        parent_path = match.group(1).rstrip('/')
        if parent_path:
            corrected = re.sub(
                git_placeholder_pattern + r'.*&&\s*echo\s+"?PASS"?',
                f'ls {parent_path}/ >/dev/null 2>&1 && echo "PASS"',
                corrected
            )
            notes.append(f"Replaced git ls-files placeholder with ls: {parent_path}/")

    # Pattern 5: Fix multi-part commands used as paths
    # e.g., test -f ls LogBook/builder/ && grep → ls LogBook/builder/ && grep
    multi_cmd_pattern = r'test\s+-[fd]\s+(ls|cat|grep|find)\s+'
    match = re.search(multi_cmd_pattern, corrected)
    if match:
        # Remove the test -f/d prefix, keep the actual command
        corrected = re.sub(r'test\s+-[fd]\s+', '', corrected, count=1)
        notes.append("Removed incorrect test wrapper from command")

    # Pattern 6: Fix paths starting with /
    # e.g., /LogBook/foo → LogBook/foo (relative paths in project)
    abs_path_pattern = r'test\s+-([fd])\s+/([A-Za-z])'
    if re.search(abs_path_pattern, corrected):
        corrected = re.sub(abs_path_pattern, r'test -\1 \2', corrected)
        notes.append("Converted absolute path to relative")

    # Pattern 7: Fix wc -l incorrectly placed in test
    # e.g., test -f wc -l docs/foo → wc -l docs/foo
    wc_pattern = r'test\s+-[fd]\s+wc\s+-l\s+'
    if re.search(wc_pattern, corrected):
        corrected = re.sub(r'test\s+-[fd]\s+', '', corrected, count=1)
        notes.append("Removed incorrect test wrapper from wc command")

    was_corrected = corrected != original
    correction_note = "; ".join(notes) if notes else ""

    return corrected, was_corrected, correction_note


def is_malformed_command(command: str) -> tuple:
    """
    Check if a verification command is malformed.

    Returns:
        (is_malformed: bool, reason: str)
    """
    import re

    for pattern, reason in MALFORMED_PATTERNS:
        if re.search(pattern, command):
            return True, reason

    # Check for common path malformations
    if 'test -' in command:
        # Extract the path being tested
        match = re.search(r'test\s+-[efds]\s+(\S+)', command)
        if match:
            path = match.group(1)
            # Path should not contain spaces or start with shell commands
            if ' ' in path and not path.startswith('"'):
                return True, "Path contains unquoted spaces"
            # Path should not be a shell command
            first_word = path.split('/')[0] if '/' in path else path.split()[0] if ' ' in path else path
            if first_word.lower() in ['ls', 'cat', 'grep', 'find', 'echo', 'test', 'python', 'python3', 'wc']:
                return True, f"Path starts with shell command '{first_word}'"

    return False, ""


# =============================================================================
# CONFIGURATION
# =============================================================================

ISSUES_DIR = "issues"
PATTERNS_FILE = "tools/verification_patterns.yaml"
EVIDENCE_DIR = "LogBook/verification/evidence"

# =============================================================================
# PATTERNS LOADING
# =============================================================================

def load_patterns() -> Dict[str, Any]:
    """Load verification patterns from YAML."""
    if not os.path.exists(PATTERNS_FILE):
        print(f"Warning: Patterns file not found: {PATTERNS_FILE}")
        return {'patterns': {}}

    with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# =============================================================================
# FRONTMATTER PARSING
# =============================================================================

def parse_frontmatter(filepath: str) -> Optional[Dict[str, Any]]:
    """Parse YAML frontmatter from issue file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    if not content.startswith('---'):
        return None

    end = content.find('\n---\n', 3)
    if end < 0:
        return None

    try:
        return yaml.safe_load(content[4:end])
    except yaml.YAMLError as e:
        print(f"Error parsing frontmatter: {e}")
        return None

def extract_verification_commands(content: str) -> List[Dict[str, str]]:
    """Extract Verification Commands section from issue content."""
    commands = []

    # Find Verification Commands section
    match = re.search(r'\*\*Verification Commands.*?\*\*.*?```bash\n(.*?)```', content, re.DOTALL)
    if not match:
        return commands

    cmd_section = match.group(1)

    # Extract individual checks
    check_pattern = r'# (Check \d+): ([^\n]+)\n([^\n]+)'
    for match in re.finditer(check_pattern, cmd_section):
        check_num = match.group(1)
        check_name = match.group(2).strip()
        command = match.group(3).strip()

        commands.append({
            'check': check_num,
            'name': check_name,
            'command': command
        })

    return commands

def extract_expected_outputs(content: str) -> Optional[Dict[str, Any]]:
    """Extract Expected Outputs YAML section from issue content."""
    # Find Expected Outputs (Machine-Readable) section
    match = re.search(r'\*\*Expected Outputs \(Machine-Readable\)\*\*.*?```yaml\n(.*?)```', content, re.DOTALL)
    if not match:
        return None

    try:
        expected = yaml.safe_load(match.group(1))
        return expected
    except yaml.YAMLError as e:
        print(f"Warning: Failed to parse expected outputs YAML: {e}")
        return None

def extract_target_paths(frontmatter: Dict[str, Any], content: str) -> List[str]:
    """Extract paths to check from frontmatter and content."""
    paths = []

    # From frontmatter
    affected = frontmatter.get('affected_paths', [])
    for path in affected:
        # Clean path
        clean = re.sub(r':\d+.*$', '', path)
        clean = clean.strip('`')
        if '/' in clean and not clean.startswith('test'):
            paths.append(clean)

    # From content - referenced paths
    matches = re.findall(r'Referenced\s+path:\s*`?([^\s`\n]+)`?', content)
    paths.extend(matches)

    # From Evidence section
    matches = re.findall(r'`([^`]+\.(py|yaml|yml|json|md|sh))`', content)
    for match in matches:
        if isinstance(match, tuple):
            path = match[0]
        else:
            path = match
        if '/' in path:
            paths.append(path)

    # Dedupe and clean
    clean_paths = []
    for path in paths:
        clean = path.strip()
        if clean and clean not in clean_paths and '/' in clean:
            # Remove line numbers
            clean = re.sub(r':\d+.*$', '', clean)
            if len(clean) > 3:
                clean_paths.append(clean)

    return clean_paths[:5]

# =============================================================================
# CHECK EXECUTION
# =============================================================================

def run_command(command: str, timeout: int = 30) -> Tuple[int, str]:
    """Run a shell command and return exit code and output."""
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
        return -1, "Command timed out"
    except Exception as e:
        return -1, str(e)

def substitute_vars(template: str, variables: Dict[str, str]) -> str:
    """Substitute variables in command template."""
    result = template
    for key, value in variables.items():
        result = result.replace(f'{{{key}}}', str(value))
    return result

def run_pattern_checks(pattern_name: str, patterns: Dict[str, Any],
                       variables: Dict[str, str], depth: str = "STANDARD") -> List[Dict]:
    """Run verification checks for a pattern."""
    results = []

    pattern = patterns.get('patterns', {}).get(pattern_name, {})
    checks = pattern.get('checks', [])

    # Filter by depth
    depth_levels = patterns.get('depth_levels', {})
    allowed_checks = depth_levels.get(depth, {}).get('checks', ['existence', 'content_validation', 'git_tracking'])

    for check in checks:
        name = check.get('name', '')

        # Skip checks not in depth level
        check_type = 'existence' if 'exist' in name else 'content_validation'
        if check_type not in allowed_checks and depth != "DEEP":
            continue

        command = substitute_vars(check.get('command', ''), variables)
        expected = check.get('expected_exit', 0)

        start = datetime.now()
        actual, output = run_command(command)
        duration = int((datetime.now() - start).total_seconds() * 1000)

        passed = (actual == expected)

        results.append({
            'name': name,
            'command': command,
            'expected': expected,
            'actual': actual,
            'output': output[:500],
            'passed': passed,
            'duration_ms': duration,
            'error': check.get('failure_message', '') if not passed else ''
        })

    return results

# =============================================================================
# ISSUE VERIFICATION
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
    pattern = os.path.join(ISSUES_DIR, lane, f"*{issue_id}*.md")
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def verify_issue(issue_id: str, depth: str = "STANDARD",
                 update_status: bool = False) -> Dict[str, Any]:
    """Verify a single issue and return results."""
    filepath = find_issue_file(issue_id)

    if not filepath:
        return {
            'issue_id': issue_id,
            'error': f"Issue file not found for {issue_id}",
            'passed': False
        }

    # Read file
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {
            'issue_id': issue_id,
            'error': f"Error reading file: {e}",
            'passed': False
        }

    # Parse frontmatter
    frontmatter = parse_frontmatter(filepath)

    if not frontmatter:
        return {
            'issue_id': issue_id,
            'error': "No frontmatter found",
            'passed': False
        }

    # Check dependencies - verify all dependent issues are resolved
    depends_on = frontmatter.get('depends_on', [])
    unresolved_deps = []
    if depends_on:
        for dep_id in depends_on:
            dep_file = find_issue_file(dep_id)
            if dep_file:
                dep_frontmatter = parse_frontmatter(dep_file)
                if dep_frontmatter:
                    dep_status = dep_frontmatter.get('status', 'OPEN')
                    if dep_status.upper() != 'RESOLVED':
                        unresolved_deps.append(dep_id)
            else:
                # Dependency file not found - treat as unresolved
                unresolved_deps.append(f"{dep_id} (not found)")

    # Try to use embedded Verification Commands first
    verification_commands = extract_verification_commands(content)
    expected_outputs = extract_expected_outputs(content)

    check_results = []

    if verification_commands:
        # Use embedded commands
        for cmd_spec in verification_commands:
            command = cmd_spec['command']

            # Try auto-correction first
            corrected_cmd, was_corrected, correction_note = auto_correct_command(command)

            # Check for malformed commands before execution
            malformed, malform_reason = is_malformed_command(corrected_cmd)
            if malformed:
                check_results.append({
                    'name': cmd_spec['name'],
                    'command': command,
                    'expected': 0,
                    'actual': -2,  # Special code for malformed
                    'output': f"MALFORMED COMMAND: {malform_reason}",
                    'passed': False,
                    'duration_ms': 0,
                    'error': f"Malformed command detected: {malform_reason}",
                    'malformed': True
                })
                continue

            # Use corrected command for execution
            exec_command = corrected_cmd

            start = datetime.now()
            actual_exit, output = run_command(exec_command)
            duration = int((datetime.now() - start).total_seconds() * 1000)

            # Check against expected outputs if available
            passed = False
            if expected_outputs:
                check_num = cmd_spec['check'].replace('Check ', 'check_')
                expected = expected_outputs.get('expected_results', {}).get(check_num, {})
                expected_exit = expected.get('exit_code', 0)
                expected_stdout = expected.get('stdout_contains', 'PASS')

                passed = (actual_exit == expected_exit and expected_stdout in output)
            else:
                # Fallback: check if output contains PASS
                passed = (actual_exit == 0 and 'PASS' in output)

            check_results.append({
                'name': cmd_spec['name'],
                'command': command,
                'corrected_command': corrected_cmd if was_corrected else None,
                'correction_note': correction_note if was_corrected else None,
                'expected': 0,
                'actual': actual_exit,
                'output': output[:500],
                'passed': passed,
                'duration_ms': duration,
                'error': '' if passed else 'Check failed',
                'was_auto_corrected': was_corrected
            })
    else:
        # Fallback to pattern-based verification
        patterns = load_patterns()
        pattern_name = frontmatter.get('verification_pattern', 'missing_file')
        fm_depth = frontmatter.get('verification_depth', depth)

        target_paths = extract_target_paths(frontmatter, content)

        variables = {
            'issue_id': issue_id,
            'lane': frontmatter.get('lane', issue_id[0]),
        }

        if target_paths:
            variables['file_path'] = target_paths[0]
            variables['dir_path'] = os.path.dirname(target_paths[0]) or target_paths[0]
            variables['script_path'] = target_paths[0]

        check_results = run_pattern_checks(pattern_name, patterns, variables, fm_depth)

    # Calculate results
    passed_count = sum(1 for c in check_results if c['passed'])
    failed_count = len(check_results) - passed_count
    all_passed = (failed_count == 0 and len(check_results) > 0)

    # If there are unresolved dependencies, add warning to results
    if unresolved_deps:
        check_results.append({
            'name': 'dependency_check',
            'command': 'check_dependencies',
            'expected': 0,
            'actual': 1,
            'output': f"Unresolved dependencies: {', '.join(unresolved_deps)}",
            'passed': False,
            'duration_ms': 0,
            'error': f"Dependencies not satisfied: {', '.join(unresolved_deps)}"
        })
        # Recalculate after adding dependency check
        passed_count = sum(1 for c in check_results if c['passed'])
        failed_count = len(check_results) - passed_count
        all_passed = (failed_count == 0 and len(check_results) > 0)

    result = {
        'issue_id': issue_id,
        'lane': frontmatter.get('lane', ''),
        'status': frontmatter.get('status', 'OPEN'),
        'pattern': frontmatter.get('verification_pattern', 'embedded_commands'),
        'depth': frontmatter.get('verification_depth', depth),
        'depends_on': depends_on,
        'unresolved_dependencies': unresolved_deps,
        'target_paths': extract_target_paths(frontmatter, content),
        'checks': check_results,
        'passed': all_passed,
        'passed_count': passed_count,
        'failed_count': failed_count,
        'total_checks': len(check_results),
        'confidence': int((passed_count / len(check_results) * 100)) if check_results else 0,
        'timestamp': datetime.now().isoformat(),
        'used_embedded_commands': bool(verification_commands)
    }

    # Save evidence
    try:
        save_evidence(result)
    except Exception as e:
        result['evidence_error'] = str(e)

    # Update issue status if requested
    if update_status and all_passed:
        try:
            update_issue_verified(filepath, result)
            result['status_updated'] = True
        except Exception as e:
            result['update_error'] = str(e)

    return result

def save_evidence(result: Dict[str, Any]) -> str:
    """Save verification evidence to file."""
    lane = result.get('lane', result['issue_id'][0])
    lane_dir = os.path.join(EVIDENCE_DIR, lane.upper())
    os.makedirs(lane_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{result['issue_id']}_{timestamp}.json"
    filepath = os.path.join(lane_dir, filename)

    # Prepare data
    data = {
        'issue_id': result['issue_id'],
        'lane': lane,
        'timestamp': result['timestamp'],
        'all_passed': result['passed'],
        'passed_checks': result['passed_count'],
        'failed_checks': result['failed_count'],
        'total_checks': result['total_checks'],
        'confidence_score': result['confidence'],
        'verification_pattern': result['pattern'],
        'verification_depth': result['depth'],
        'affected_paths': result['target_paths'],
        'checks': result['checks']
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    return filepath

def update_issue_verified(filepath: str, result: Dict[str, Any]) -> None:
    """Update issue file to mark as verified."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update frontmatter status if exists
    if content.startswith('---'):
        end = content.find('\n---\n', 3)
        if end > 0:
            frontmatter_text = content[4:end]
            rest = content[end+5:]

            # Add verified date
            if 'date_verified:' not in frontmatter_text:
                frontmatter_text += f'\ndate_verified: "{datetime.now().strftime("%Y-%m-%d")}"\n'
                frontmatter_text += f'verification_confidence: {result["confidence"]}\n'

            content = f"---\n{frontmatter_text}\n---\n{rest}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def print_result(result: Dict[str, Any], verbose: bool = False) -> None:
    """Print verification result."""
    issue_id = result['issue_id']

    if 'error' in result:
        print(f"\u274c {issue_id}: {result['error']}")
        return

    icon = "\u2705" if result['passed'] else "\u274c"
    status = "PASS" if result['passed'] else "FAIL"

    print(f"\n{'='*60}")
    print(f"{icon} {issue_id}: {status}")
    print(f"{'='*60}")
    print(f"Pattern:     {result['pattern']}")
    print(f"Depth:       {result['depth']}")
    print(f"Checks:      {result['passed_count']}/{result['total_checks']} passed")
    print(f"Confidence:  {result['confidence']}%")

    if result.get('target_paths'):
        print(f"Targets:     {', '.join(result['target_paths'][:2])}")

    print(f"\nCheck Results:")
    print(f"{'-'*60}")

    for check in result['checks']:
        # Special icon for malformed commands
        if check.get('malformed'):
            c_icon = "\u26a0\ufe0f"  # Warning sign for malformed
        elif check['passed']:
            c_icon = "\u2705"
        else:
            c_icon = "\u274c"

        # Show auto-correction indicator
        correction_marker = " [AUTO-CORRECTED]" if check.get('was_auto_corrected') else ""
        print(f"  {c_icon} {check['name']}{correction_marker}")

        if verbose or not check['passed']:
            print(f"      Command: {check['command'][:50]}...")
            if check.get('was_auto_corrected'):
                print(f"      Corrected: {check.get('corrected_command', '')[:50]}...")
                print(f"      Fix applied: {check.get('correction_note', '')}")
            if check.get('malformed'):
                print(f"      Status: MALFORMED COMMAND - {check['error']}")
            else:
                print(f"      Exit: expected={check['expected']}, actual={check['actual']}")
            if check['error'] and not check.get('malformed'):
                print(f"      Error: {check['error']}")
            if check['output'] and not check['passed']:
                print(f"      Output: {check['output'][:80]}...")

    print(f"{'='*60}")

# =============================================================================
# BATCH PROCESSING
# =============================================================================

def verify_lane(lane: str, depth: str = "STANDARD") -> Dict[str, int]:
    """Verify all issues in a lane."""
    pattern = os.path.join(ISSUES_DIR, lane.upper(), '*.md')
    files = [f for f in glob.glob(pattern) if 'TEMPLATE' not in f.upper()]

    stats = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0}

    print(f"\nVerifying Lane {lane.upper()}: {len(files)} issues")
    print(f"{'='*60}")

    for filepath in sorted(files):
        issue_id = os.path.basename(filepath).replace('.md', '')
        result = verify_issue(issue_id, depth)

        stats['total'] += 1

        if 'error' in result:
            stats['errors'] += 1
            icon = "\u26a0\ufe0f"
        elif result['passed']:
            stats['passed'] += 1
            icon = "\u2705"
        else:
            stats['failed'] += 1
            icon = "\u274c"

        checks = f"{result.get('passed_count', 0)}/{result.get('total_checks', 0)}"
        print(f"{icon} {issue_id}: {checks} checks passed")

    print(f"\n{'='*60}")
    print(f"Lane {lane.upper()} Summary:")
    print(f"  Total:   {stats['total']}")
    print(f"  Passed:  {stats['passed']}")
    print(f"  Failed:  {stats['failed']}")
    print(f"  Errors:  {stats['errors']}")
    print(f"{'='*60}")

    return stats

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Verify issue fixes',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('issue_ids', nargs='*', help='Issue IDs to verify')
    parser.add_argument('--lane', '-l', type=str, help='Verify all issues in lane')
    parser.add_argument('--all', '-a', action='store_true', help='Verify all issues')
    parser.add_argument('--update', '-u', action='store_true', help='Update issue status on pass')
    parser.add_argument('--quick', '-q', action='store_true', help='Quick verification only')
    parser.add_argument('--deep', '-d', action='store_true', help='Deep verification')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Determine depth
    if args.quick:
        depth = "QUICK"
    elif args.deep:
        depth = "DEEP"
    else:
        depth = "STANDARD"

    # Process
    if args.lane:
        stats = verify_lane(args.lane, depth)
        sys.exit(0 if stats['failed'] == 0 else 1)

    elif args.all:
        total_stats = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0}
        for lane_dir in sorted(glob.glob(os.path.join(ISSUES_DIR, '*'))):
            if os.path.isdir(lane_dir):
                lane = os.path.basename(lane_dir)
                stats = verify_lane(lane, depth)
                for k in total_stats:
                    total_stats[k] += stats[k]

        print(f"\n{'='*60}")
        print("OVERALL SUMMARY")
        print(f"{'='*60}")
        print(f"Total Issues: {total_stats['total']}")
        print(f"Passed: {total_stats['passed']}")
        print(f"Failed: {total_stats['failed']}")
        print(f"Errors: {total_stats['errors']}")
        sys.exit(0 if total_stats['failed'] == 0 else 1)

    elif args.issue_ids:
        all_passed = True
        for issue_id in args.issue_ids:
            result = verify_issue(issue_id, depth, args.update)
            print_result(result, args.verbose)
            if not result.get('passed', False):
                all_passed = False
        sys.exit(0 if all_passed else 1)

    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
