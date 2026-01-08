#!/usr/bin/env python3
"""
Minimal Demo: File-Signal Orchestration

This script demonstrates the file-based signaling pattern used for
multi-agent orchestration WITHOUT requiring any AI API calls.

What it demonstrates:
1. Orchestrator reads issue catalog
2. Spawns "workers" for each lane (simulated)
3. Workers write .status files as they progress
4. Workers write .done files when complete
5. Orchestrator polls for completion signals
6. Final report is generated

Usage:
    python3 scripts/run_demo_file_signals.py

Output:
    - LogBook/issue-fixing/signals/*.status
    - LogBook/issue-fixing/signals/*.done
    - examples/output/sample_run_report.md
"""

import os
import re
import sys
import time
import threading
from datetime import datetime
from pathlib import Path


# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def get_repo_root() -> Path:
    """Get the repository root directory."""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent


def print_header(text: str) -> None:
    """Print a styled header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def print_step(step: int, text: str) -> None:
    """Print a step indicator."""
    print(f"{Colors.BLUE}[Step {step}]{Colors.END} {text}")


def print_ok(text: str) -> None:
    """Print success message."""
    print(f"  {Colors.GREEN}✓{Colors.END} {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"  {Colors.YELLOW}→{Colors.END} {text}")


def clean_signals(signals_dir: Path) -> None:
    """Remove old signal files."""
    for ext in ['*.done', '*.status']:
        for f in signals_dir.glob(ext):
            f.unlink()


def parse_catalog(catalog_path: Path) -> dict:
    """Parse the issue catalog and return open issues by lane."""
    with open(catalog_path, 'r') as f:
        content = f.read()

    lanes = {}

    # Find each lane section
    for lane in ['E', 'M']:
        pattern = rf'### Lane {lane} -.*?\n\|.*?\n\|[-|]+\|\n(.*?)<!-- LANE_{lane}_ISSUES -->'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            rows = match.group(1).strip().split('\n')
            issues = []
            for row in rows:
                if row.startswith('|') and 'OPEN' in row:
                    cols = [c.strip() for c in row.split('|')]
                    if len(cols) >= 5:
                        issues.append({
                            'id': cols[1],
                            'title': cols[2],
                            'severity': cols[3],
                            'status': cols[5] if len(cols) > 5 else 'OPEN'
                        })
            lanes[lane] = issues

    return lanes


def simulate_lane_worker(lane: str, issues: list, repo_root: Path) -> dict:
    """
    Simulate a lane worker processing issues.

    In the real system, this would be a separate agent with its own context.
    Here we simulate the file-signal behavior.
    """
    signals_dir = repo_root / 'LogBook' / 'issue-fixing' / 'signals'
    demo_dir = repo_root / 'examples' / 'minimal_demo'

    result = {
        'lane': lane,
        'issues_found': len(issues),
        'issues_fixed': 0,
        'fixed_ids': []
    }

    # Write starting status
    status_file = signals_dir / f'{lane}.status'
    status_file.write_text(f"STARTING: scanning catalog for Lane {lane}\n")

    if not issues:
        status_file.write_text(f"COMPLETE: Lane {lane} is clean (0 issues)\n")
        (signals_dir / f'{lane}.done').touch()
        return result

    # Simulate complexity assessment
    time.sleep(0.1)  # Brief pause to simulate work
    status_file.write_text(f"NORMAL: fixing {len(issues)} issues\n")

    # Process each issue (simulate fixing by modifying config files)
    for issue in issues:
        issue_id = issue['id']
        issue_file = demo_dir / 'issues' / lane / f'{issue_id}.md'

        if not issue_file.exists():
            continue

        # Read issue to get fix requirements
        issue_content = issue_file.read_text()

        # Simulate applying the fix based on lane
        if lane == 'E':
            config_file = demo_dir / 'config' / 'guidelines.yaml'
            config_content = config_file.read_text()

            # Apply fixes based on issue
            if issue_id == 'E-01' and 'data_retention:' not in config_content:
                config_content += "\ndata_retention:\n  retention_days: 365\n  review_frequency: quarterly\n"
            elif issue_id == 'E-02' and 'third_party_sharing:' not in config_content:
                config_content = config_content.replace(
                    "privacy:",
                    "privacy:\n  third_party_sharing: documented"
                )
            elif issue_id == 'E-03' and 'response_time_hours:' not in config_content:
                config_content = config_content.replace(
                    "customer_service:",
                    "customer_service:\n  response_time_hours: 24"
                )

            config_file.write_text(config_content)

        elif lane == 'M':
            config_file = demo_dir / 'config' / 'schema.yaml'
            config_content = config_file.read_text()

            if issue_id == 'M-01' and 'schema_version:' not in config_content:
                config_content = f"schema_version: \"1.0.0\"\n\n{config_content}"
            elif issue_id == 'M-02' and 'strict_mode:' not in config_content:
                config_content = config_content.replace(
                    "validation:",
                    "validation:\n  strict_mode: true"
                )

            config_file.write_text(config_content)

        # Mark issue as resolved in the issue file
        updated_issue = issue_content.replace('status: "OPEN"', 'status: "RESOLVED"')
        updated_issue = updated_issue.replace('**Status:** OPEN', '**Status:** RESOLVED')

        # Add resolution section
        resolution = f"""
---

## Resolution

- **Fixed:** {datetime.now().strftime('%Y-%m-%d')}
- **Fixed By:** Demo Lane Worker (simulated)
- **Verification:** Passed
"""
        updated_issue += resolution
        issue_file.write_text(updated_issue)

        result['issues_fixed'] += 1
        result['fixed_ids'].append(issue_id)

        # Update status
        status_file.write_text(f"WORKING: fixed {result['issues_fixed']}/{len(issues)} issues\n")
        time.sleep(0.1)  # Brief pause between issues

    # Signal completion
    status_file.write_text(f"COMPLETE: fixed {result['issues_fixed']} issues\n")
    (signals_dir / f'{lane}.done').touch()

    return result


def poll_for_completion(signals_dir: Path, lanes: list, timeout: int = 30) -> bool:
    """
    Poll for .done files from all lanes.

    This demonstrates the key orchestration pattern:
    - NO transcript parsing
    - Just check for file existence
    - Minimal context usage
    """
    start = time.time()

    while time.time() - start < timeout:
        done_count = sum(1 for lane in lanes if (signals_dir / f'{lane}.done').exists())

        # Show status
        status_parts = []
        for lane in lanes:
            status_file = signals_dir / f'{lane}.status'
            if status_file.exists():
                status = status_file.read_text().strip().split('\n')[-1]
                done = "✓" if (signals_dir / f'{lane}.done').exists() else "○"
                status_parts.append(f"{lane}:{done}")

        print(f"  {Colors.CYAN}Polling:{Colors.END} {' | '.join(status_parts)} ({done_count}/{len(lanes)} done)")

        if done_count == len(lanes):
            return True

        time.sleep(0.5)

    return False


def generate_report(results: list, repo_root: Path) -> Path:
    """Generate the final run report."""
    output_dir = repo_root / 'examples' / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / 'sample_run_report.md'

    total_found = sum(r['issues_found'] for r in results)
    total_fixed = sum(r['issues_fixed'] for r in results)

    report = f"""# Demo Run Report

> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **Demo Type:** File-Signal Orchestration

## Summary

| Metric | Value |
|--------|-------|
| Lanes processed | {len(results)} |
| Issues found | {total_found} |
| Issues fixed | {total_fixed} |
| Completion | {'100%' if total_fixed == total_found else f'{100*total_fixed//total_found}%'} |

## Results by Lane

"""

    for r in results:
        fixed_list = ', '.join(r['fixed_ids']) if r['fixed_ids'] else 'None'
        report += f"""### Lane {r['lane']}

- **Issues found:** {r['issues_found']}
- **Issues fixed:** {r['issues_fixed']}
- **Fixed IDs:** {fixed_list}

"""

    report += """## Signals Generated

The following signal files were created:

| File | Purpose |
|------|---------|
| `LogBook/issue-fixing/signals/E.status` | Lane E progress updates |
| `LogBook/issue-fixing/signals/E.done` | Lane E completion signal |
| `LogBook/issue-fixing/signals/M.status` | Lane M progress updates |
| `LogBook/issue-fixing/signals/M.done` | Lane M completion signal |

## Key Demonstration Points

1. **File-based signaling** - No agent transcript parsing required
2. **Parallel-ready** - Each lane worker operates independently
3. **Minimal context** - Orchestrator only reads small status files
4. **Idempotent** - Can re-run safely after cleanup

---

*This report was generated by the demo orchestration script.*
"""

    report_path.write_text(report)
    return report_path


def copy_signals_to_examples(signals_dir: Path, repo_root: Path) -> None:
    """Copy generated signals to examples/output for reference."""
    output_signals = repo_root / 'examples' / 'output' / 'signals'
    output_signals.mkdir(parents=True, exist_ok=True)

    for f in signals_dir.glob('*'):
        if f.suffix in ['.status', '.done']:
            dest = output_signals / f.name
            dest.write_text(f.read_text() if f.suffix == '.status' else '')


def main() -> int:
    """Main entry point."""
    print_header("FILE-SIGNAL ORCHESTRATION DEMO")
    print(f"{Colors.YELLOW}Demonstrating file-based agent coordination{Colors.END}")
    print(f"{Colors.YELLOW}NO AI API calls - pure orchestration pattern{Colors.END}\n")

    repo_root = get_repo_root()
    signals_dir = repo_root / 'LogBook' / 'issue-fixing' / 'signals'
    catalog_path = repo_root / 'examples' / 'minimal_demo' / 'SAF_ISSUE_CATALOG.md'

    # Ensure directories exist
    signals_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Clean old signals
    print_step(1, "Cleaning old signals...")
    clean_signals(signals_dir)
    print_ok("Signal directory cleaned")

    # Step 2: Parse catalog
    print_step(2, "Reading issue catalog...")
    if not catalog_path.exists():
        print(f"{Colors.RED}ERROR: Catalog not found: {catalog_path}{Colors.END}")
        return 1

    lanes_issues = parse_catalog(catalog_path)
    for lane, issues in lanes_issues.items():
        print_info(f"Lane {lane}: {len(issues)} open issues")

    # Step 3: Spawn lane workers in parallel (using threading)
    print_step(3, "Spawning lane workers in PARALLEL...")
    print_info("In production: dozens of parallel agents via Task tool")
    print_info("In demo: Threaded simulation with same signal behavior")

    results = []
    results_lock = threading.Lock()

    def worker_thread(lane: str, issues: list):
        result = simulate_lane_worker(lane, issues, repo_root)
        with results_lock:
            results.append(result)

    threads = []
    for lane, issues in lanes_issues.items():
        print_info(f"Starting Lane {lane} worker...")
        t = threading.Thread(target=worker_thread, args=(lane, issues))
        threads.append(t)
        t.start()

    # Step 4: Poll for completion
    print_step(4, "Polling for completion signals...")
    lanes = list(lanes_issues.keys())
    success = poll_for_completion(signals_dir, lanes)

    if not success:
        print(f"{Colors.RED}ERROR: Timeout waiting for completion{Colors.END}")
        return 1

    # Ensure all threads finished
    for t in threads:
        t.join()

    print_ok("All lanes completed!")

    # Step 5: Generate report
    print_step(5, "Generating report...")
    report_path = generate_report(results, repo_root)
    print_ok(f"Report: {report_path.relative_to(repo_root)}")

    # Copy signals to examples
    copy_signals_to_examples(signals_dir, repo_root)
    print_ok("Signals copied to examples/output/signals/")

    # Summary
    print_header("DEMO COMPLETE")

    total_fixed = sum(r['issues_fixed'] for r in results)
    print(f"  Lanes:        {Colors.BOLD}{len(results)}{Colors.END}")
    print(f"  Issues fixed: {Colors.GREEN}{Colors.BOLD}{total_fixed}{Colors.END}")
    print(f"  Signals:      {Colors.BOLD}LogBook/issue-fixing/signals/{Colors.END}")
    print(f"  Report:       {Colors.BOLD}examples/output/sample_run_report.md{Colors.END}")
    print()
    print(f"{Colors.CYAN}This demonstrates the file-signal orchestration pattern.{Colors.END}")
    print(f"{Colors.CYAN}Lane workers ran in PARALLEL threads (simulating real agent behavior).{Colors.END}")
    print(f"{Colors.CYAN}Real system uses Claude agents with this same signaling approach.{Colors.END}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
