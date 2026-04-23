#!/usr/bin/env python3
"""
Bulk RESOLVED Issues Verifier

Systematically verifies all RESOLVED issues using Level 3 verification.
Features:
- Checkpoints every 2 issues to prevent data loss
- Generates detailed audit trail
- Re-catalogs failures with ultra-detailed specifications
- Provides pass rate analysis

Usage:
    python3 tools/verify_all_resolved.py
"""

import os
import sys
import yaml
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Configuration
REPO_ROOT = Path(__file__).parent.parent
STATE_FILE = REPO_ROOT / "LogBook/verification/FIX_VERIFICATION_STATE.yaml"
EVIDENCE_DIR = REPO_ROOT / "LogBook/verification/evidence"
AUDIT_REPORT = REPO_ROOT / "LogBook/verification/VERIFICATION_AUDIT_REPORT.md"
ISSUES_DIR = REPO_ROOT / "issues"

# Verification levels
VERIFICATION_LEVEL = "DEEP"  # Level 3: all 6 checks

def load_state():
    """Load verification state from YAML."""
    with open(STATE_FILE, 'r') as f:
        return yaml.safe_load(f)

def save_state(state):
    """Save verification state to YAML."""
    with open(STATE_FILE, 'w') as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)

def find_all_resolved_issues():
    """Find all RESOLVED issues across all lanes."""
    resolved = []

    for lane_dir in sorted(ISSUES_DIR.glob("*")):
        if not lane_dir.is_dir():
            continue

        lane = lane_dir.name
        if lane == "TEMPLATE":
            continue

        for issue_file in sorted(lane_dir.glob("*.md")):
            if issue_file.name == "TEMPLATE.md":
                continue

            # Check if RESOLVED
            with open(issue_file, 'r') as f:
                content = f.read()
                if 'status: "RESOLVED"' in content:
                    issue_id = issue_file.stem
                    resolved.append({
                        'lane': lane,
                        'issue_id': issue_id,
                        'file_path': str(issue_file.relative_to(REPO_ROOT))
                    })

    return resolved

def verify_single_issue(issue_id):
    """Run verification on a single issue using verify_issue.py."""
    cmd = [
        'python3',
        str(REPO_ROOT / 'tools/verify_issue.py'),
        issue_id,
        '--deep',
        '--update'
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT)
        )

        # Parse output to determine pass/fail
        output = result.stdout + result.stderr
        passed = ('PASS' in output and result.returncode == 0)

        # Extract evidence file if created
        evidence_files = list(EVIDENCE_DIR.glob(f"*/{issue_id}_*.json"))
        evidence_path = str(evidence_files[-1]) if evidence_files else None

        return {
            'issue_id': issue_id,
            'passed': passed,
            'exit_code': result.returncode,
            'output': output,
            'evidence_path': evidence_path,
            'timestamp': datetime.now().isoformat()
        }

    except subprocess.TimeoutExpired:
        return {
            'issue_id': issue_id,
            'passed': False,
            'error': 'Verification timed out',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'issue_id': issue_id,
            'passed': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def update_lane_stats(state, lane, result):
    """Update lane statistics based on verification result."""
    if lane not in state['lanes']:
        state['lanes'][lane] = {
            'total_issues': 0,
            'resolved_issues': 0,
            'verified_count': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'current_issue': 'NOT_STARTED',
            'failed_issues': []
        }

    lane_stats = state['lanes'][lane]
    lane_stats['verified_count'] += 1

    if result['passed']:
        lane_stats['passed'] += 1
    else:
        lane_stats['failed'] += 1
        lane_stats['failed_issues'].append(result['issue_id'])

def checkpoint_state(state, issue_count):
    """Save state checkpoint."""
    state['last_checkpoint'] = datetime.now().isoformat()
    state['issues_since_last_checkpoint'] = 0
    state['stats']['checkpoint_count'] += 1
    save_state(state)
    print(f"  [CHECKPOINT] Saved state after {issue_count} issues")

def generate_recatalog_spec(issue_id, evidence_path):
    """Generate ultra-detailed re-catalog specification for failed issue."""
    spec = {
        'issue_id': issue_id,
        'lane': issue_id[0],
        'reason': 'VERIFICATION_FAILED',
        'original_status': 'RESOLVED',
        'new_status': 'REVERIFY',
        'timestamp': datetime.now().isoformat()
    }

    # Load evidence if available
    if evidence_path and os.path.exists(evidence_path):
        with open(evidence_path, 'r') as f:
            evidence = json.load(f)
            spec['failed_checks'] = evidence.get('checks', [])
            spec['verification_pattern'] = evidence.get('verification_pattern', 'unknown')

    return spec

def create_reverify_issue(issue_id, spec):
    """Create REVERIFY issue file with ultra-detailed specifications."""
    lane = issue_id[0]
    reverify_file = ISSUES_DIR / lane / f"{issue_id}-REVERIFY.md"

    content = f"""---
issue_id: "{issue_id}-REVERIFY"
lane: "{lane}"
status: "REVERIFY"
priority: "HIGH"
parent_issue: "{issue_id}"
created: "{spec['timestamp']}"
verification_failed: true
---

# {issue_id} - RE-VERIFICATION REQUIRED

## Issue
Original issue {issue_id} was marked RESOLVED but failed Level 3 verification.

## Failed Verification Details
- **Original Status**: {spec['original_status']}
- **Verification Timestamp**: {spec['timestamp']}
- **Pattern**: {spec.get('verification_pattern', 'unknown')}

## Failed Checks
"""

    if 'failed_checks' in spec:
        for check in spec['failed_checks']:
            if not check.get('passed', True):
                content += f"""
### {check.get('name', 'Unknown Check')}
- **Command**: `{check.get('command', 'N/A')}`
- **Expected Exit**: {check.get('expected', 0)}
- **Actual Exit**: {check.get('actual', 'N/A')}
- **Error**: {check.get('error', 'N/A')}
- **Output**:
```
{check.get('output', 'N/A')[:200]}
```
"""

    content += """
## Required Actions
1. Investigate why original fix did not pass verification
2. Re-implement fix with stricter validation
3. Re-run verification before marking RESOLVED
4. Update verification commands if needed

## Acceptance Criteria
- All 6 Level 3 verification checks must pass
- Evidence must be collected and stored
- Pass rate must be 100% (not 95%)
"""

    with open(reverify_file, 'w') as f:
        f.write(content)

    return str(reverify_file.relative_to(REPO_ROOT))

def generate_audit_report(state, results, failed_specs):
    """Generate final audit report."""
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0

    report = f"""# Fix Verification Audit Report

**Session ID**: {state['session_id']}
**Generated**: {datetime.now().isoformat()}
**Verification Level**: Level 3 (DEEP - All 6 Checks)

## Executive Summary

- **Total RESOLVED Issues Verified**: {total}
- **Passed Verification**: {passed}
- **Failed Verification**: {failed}
- **Pass Rate**: {pass_rate:.1f}%
- **Target Pass Rate**: >95%
- **Status**: {'✅ PASS' if pass_rate >= 95 else '❌ FAIL - Below Target'}

## Verification Methodology

### Level 3 Verification (6 Checks)
1. **File Existence**: Verify all referenced files exist
2. **Content Validation**: Validate file contents match expected patterns
3. **Schema Validation**: Verify YAML/JSON schema compliance
4. **Git Verification**: Confirm files are tracked in git
5. **Integration Checks**: Run integration tests where applicable
6. **Cross-Reference Validation**: Verify internal references are valid

## Results by Lane

"""

    # Lane breakdown
    lane_results = {}
    for result in results:
        lane = result['issue_id'][0]
        if lane not in lane_results:
            lane_results[lane] = {'total': 0, 'passed': 0, 'failed': 0}
        lane_results[lane]['total'] += 1
        if result['passed']:
            lane_results[lane]['passed'] += 1
        else:
            lane_results[lane]['failed'] += 1

    report += "| Lane | Total | Passed | Failed | Pass Rate |\n"
    report += "|------|-------|--------|--------|-----------|\n"

    for lane in sorted(lane_results.keys()):
        stats = lane_results[lane]
        lane_pass_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        report += f"| {lane} | {stats['total']} | {stats['passed']} | {stats['failed']} | {lane_pass_rate:.1f}% |\n"

    report += f"\n## Failed Issues ({failed})\n\n"

    if failed > 0:
        for spec in failed_specs:
            report += f"### {spec['issue_id']}\n"
            report += f"- **Lane**: {spec['lane']}\n"
            report += f"- **Reason**: {spec['reason']}\n"
            report += f"- **Pattern**: {spec.get('verification_pattern', 'unknown')}\n"
            report += f"- **Re-catalog File**: Created at `issues/{spec['lane']}/{spec['issue_id']}-REVERIFY.md`\n\n"
    else:
        report += "No failed issues. All RESOLVED issues passed verification.\n\n"

    report += f"""
## Checkpoint Summary
- **Total Checkpoints**: {state['stats']['checkpoint_count']}
- **Session Duration**: {state['session_id']} to {datetime.now().isoformat()}

## Evidence Storage
All verification evidence stored in:
- `LogBook/verification/evidence/<LANE>/<ISSUE_ID>_<TIMESTAMP>.json`

## Next Steps
"""

    if pass_rate >= 95:
        report += """
✅ **VERIFICATION PASSED**
- All or nearly all RESOLVED issues verified successfully
- No major action required
- Continue monitoring new RESOLVED issues
"""
    else:
        report += f"""
❌ **VERIFICATION FAILED** (Pass Rate: {pass_rate:.1f}% < 95%)

Required Actions:
1. Review all {failed} failed issues in REVERIFY files
2. Re-implement fixes according to ultra-detailed specifications
3. Re-run verification after fixes
4. Achieve >95% pass rate before promotion to golden lane

**BLOCKING**: This verification result BLOCKS promotion to golden lane.
"""

    report += f"""
---
*Generated by Critic-FixVerifier*
*Verification Tool: tools/verify_issue.py*
*State File: LogBook/verification/FIX_VERIFICATION_STATE.yaml*
"""

    with open(AUDIT_REPORT, 'w') as f:
        f.write(report)

    print(f"\n[AUDIT REPORT] Generated: {AUDIT_REPORT}")

def main():
    """Main verification workflow."""
    print("="*70)
    print("FIX VERIFICATION - Level 3 (DEEP)")
    print("="*70)

    # Load state
    state = load_state()
    print(f"\nSession ID: {state['session_id']}")

    # Find all RESOLVED issues
    print("\n[1/4] Scanning for RESOLVED issues...")
    resolved_issues = find_all_resolved_issues()
    print(f"Found {len(resolved_issues)} RESOLVED issues")

    # Update state
    state['stats']['total_resolved'] = len(resolved_issues)

    # Verify each issue
    print(f"\n[2/4] Verifying issues (Level 3 - DEEP)...")
    results = []
    failed_specs = []

    for idx, issue_info in enumerate(resolved_issues, 1):
        issue_id = issue_info['issue_id']
        lane = issue_info['lane']

        print(f"\n[{idx}/{len(resolved_issues)}] Verifying {issue_id}...", end=" ")

        # Update state
        state['next_to_verify'] = issue_info
        state['lanes'][lane]['current_issue'] = issue_id

        # Run verification
        result = verify_single_issue(issue_id)
        results.append(result)

        # Update stats
        update_lane_stats(state, lane, result)
        state['stats']['total_verified'] += 1

        if result['passed']:
            state['stats']['total_passed'] += 1
            print("✅ PASS")
        else:
            state['stats']['total_failed'] += 1
            print("❌ FAIL")

            # Generate re-catalog spec
            spec = generate_recatalog_spec(issue_id, result.get('evidence_path'))
            failed_specs.append(spec)

        # Update pass rate
        state['stats']['pass_rate'] = (state['stats']['total_passed'] / state['stats']['total_verified'] * 100)

        # Checkpoint every 2 issues
        state['issues_since_last_checkpoint'] += 1
        if state['issues_since_last_checkpoint'] >= 2:
            checkpoint_state(state, state['stats']['total_verified'])

    # Final checkpoint
    checkpoint_state(state, state['stats']['total_verified'])

    # Re-catalog failures
    if failed_specs:
        print(f"\n[3/4] Re-cataloging {len(failed_specs)} failed issues...")
        for spec in failed_specs:
            reverify_file = create_reverify_issue(spec['issue_id'], spec)
            print(f"  Created: {reverify_file}")
    else:
        print("\n[3/4] No failed issues to re-catalog")

    # Generate audit report
    print("\n[4/4] Generating audit report...")
    generate_audit_report(state, results, failed_specs)

    # Final summary
    print("\n" + "="*70)
    print("VERIFICATION COMPLETE")
    print("="*70)
    print(f"Total Verified: {len(results)}")
    print(f"Passed: {state['stats']['total_passed']}")
    print(f"Failed: {state['stats']['total_failed']}")
    print(f"Pass Rate: {state['stats']['pass_rate']:.1f}%")
    print(f"Target: >95%")

    if state['stats']['pass_rate'] >= 95:
        print("\n✅ STATUS: VERIFICATION PASSED")
        return 0
    else:
        print("\n❌ STATUS: VERIFICATION FAILED (Below 95% threshold)")
        return 1

if __name__ == '__main__':
    sys.exit(main())
