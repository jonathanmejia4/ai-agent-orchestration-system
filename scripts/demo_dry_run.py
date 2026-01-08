#!/usr/bin/env python3
"""
Demo Dry-Run Script

Simulates the AI agent orchestration workflow using FILE OPERATIONS ONLY.
NO AI calls are made - this demonstrates the orchestration PATTERN.

This script:
1. Reads demo_issue.md
2. Generates demo_work_order.yaml (simulated PM dispatch)
3. Simulates fixer agents processing
4. Generates demo_verdict.yaml (simulated critic evaluation)
5. Prints summary to console

Usage:
    python3 scripts/demo_dry_run.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import yaml
import re


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


def print_header(text: str) -> None:
    """Print a styled header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def print_step(step: int, text: str) -> None:
    """Print a step indicator."""
    print(f"{Colors.BLUE}[Step {step}]{Colors.END} {text}")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"  {Colors.GREEN}[OK]{Colors.END} {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"  {Colors.YELLOW}[INFO]{Colors.END} {text}")


def get_repo_root() -> Path:
    """Get the repository root directory."""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent


def read_issue(demo_dir: Path) -> dict:
    """Read and parse the demo issue file."""
    issue_path = demo_dir / "demo_issue.md"

    if not issue_path.exists():
        raise FileNotFoundError(f"Demo issue not found: {issue_path}")

    with open(issue_path, 'r') as f:
        content = f.read()

    # Parse YAML frontmatter
    frontmatter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if frontmatter_match:
        frontmatter = yaml.safe_load(frontmatter_match.group(1))
    else:
        frontmatter = {}

    return {
        'content': content,
        'frontmatter': frontmatter,
        'issue_id': frontmatter.get('issue_id', 'UNKNOWN'),
        'lane': frontmatter.get('lane', 'X'),
        'severity': frontmatter.get('severity', 5),
        'status': frontmatter.get('status', 'OPEN')
    }


def simulate_work_order_generation(issue: dict, demo_dir: Path) -> dict:
    """Simulate PM generating a work order from the issue."""
    work_order = {
        'work_order': {
            'id': f"WO-{datetime.now().strftime('%Y%m%d')}-{issue['issue_id']}",
            'issued_by': 'Demo-Project-Manager',
            'issued_to': 'Demo-Builder',
            'brick_id': f"demo-fix-{issue['issue_id'].lower()}",
            'task_type': 'fix_issue',
            'objective': f"Resolve issue {issue['issue_id']}",
            'inputs': [
                {
                    'path': 'demo/demo_issue.md',
                    'type': 'reference',
                    'description': 'Issue to resolve'
                }
            ],
            'expected_outputs': [
                {
                    'path': 'config/settings.yaml',
                    'type': 'config',
                    'acceptance_criteria': [
                        {'criterion': 'File exists', 'testable': True}
                    ]
                }
            ],
            'time_box': 'PT30M',
            'priority': 'normal'
        },
        'metadata': {
            'created_at': datetime.now().isoformat() + 'Z',
            'demo_mode': True
        }
    }

    return work_order


def simulate_fixer_agents(issue: dict) -> list:
    """Simulate fixer agents processing the issue."""
    # In real system, multiple specialized fixers would process different aspects
    # Here we simulate 3 fixers working in parallel

    fixers = [
        {
            'fixer_id': f"IF-Lane-{issue['lane']}-Alpha",
            'action': 'Analyzed issue requirements',
            'result': 'Requirements understood'
        },
        {
            'fixer_id': f"IF-Lane-{issue['lane']}-Beta",
            'action': 'Generated fix implementation',
            'result': 'Fix code generated'
        },
        {
            'fixer_id': f"IF-Lane-{issue['lane']}-Gamma",
            'action': 'Applied fix to target location',
            'result': 'Changes applied successfully'
        }
    ]

    return fixers


def simulate_verdict(issue: dict, work_order: dict) -> dict:
    """Simulate critic orchestrator generating a verdict."""
    verdict = {
        'final_verdict': 'APPROVED',
        'brick_id': work_order['work_order']['brick_id'],
        'timestamp': datetime.now().isoformat() + 'Z',
        'overall_score': 0.94,
        'recommendation': 'APPROVE - All checks passed',
        'dimension_results': [
            {
                'dimension': 'SpecFit',
                'verdict': 'pass',
                'score': 0.95,
                'feedback': 'Output matches specification requirements'
            },
            {
                'dimension': 'Verification',
                'verdict': 'pass',
                'score': 0.92,
                'feedback': 'All verification commands passed'
            },
            {
                'dimension': 'Dependencies',
                'verdict': 'pass',
                'score': 1.0,
                'feedback': 'No dependencies - standalone fix'
            },
            {
                'dimension': 'Effort',
                'verdict': 'pass',
                'score': 0.90,
                'feedback': 'Completed within time box'
            },
            {
                'dimension': 'Security',
                'verdict': 'pass',
                'score': 0.95,
                'feedback': 'No security issues detected'
            }
        ],
        'issues_summary': {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'total': 0
        },
        'evaluation_metadata': {
            'demo_mode': True,
            'dimensions_evaluated': 5
        }
    }

    return verdict


def write_artifacts(demo_dir: Path, work_order: dict, verdict: dict) -> None:
    """Write generated artifacts to files."""
    # Write work order
    work_order_path = demo_dir / "demo_work_order_generated.yaml"
    with open(work_order_path, 'w') as f:
        f.write("# AUTO-GENERATED by demo_dry_run.py\n")
        f.write("# This demonstrates work order generation pattern\n\n")
        yaml.dump(work_order, f, default_flow_style=False, sort_keys=False)

    # Write verdict
    verdict_path = demo_dir / "demo_verdict_generated.yaml"
    with open(verdict_path, 'w') as f:
        f.write("# AUTO-GENERATED by demo_dry_run.py\n")
        f.write("# This demonstrates verdict generation pattern\n\n")
        yaml.dump(verdict, f, default_flow_style=False, sort_keys=False)


def main() -> int:
    """Main entry point."""
    print_header("AI AGENT ORCHESTRATION DEMO")
    print(f"{Colors.YELLOW}NOTE: This is a DRY RUN - NO AI calls are made{Colors.END}")
    print(f"{Colors.YELLOW}Demonstrating orchestration PATTERN only{Colors.END}\n")

    # Setup paths
    repo_root = get_repo_root()
    demo_dir = repo_root / "demo"

    if not demo_dir.exists():
        print(f"{Colors.RED}[ERROR] Demo directory not found: {demo_dir}{Colors.END}")
        return 1

    # Step 1: Read issue
    print_step(1, "Reading demo issue...")
    try:
        issue = read_issue(demo_dir)
        print_success(f"Loaded issue: {issue['issue_id']}")
        print_info(f"Lane: {issue['lane']}")
        print_info(f"Severity: {issue['severity']}/10")
        print_info(f"Status: {issue['status']}")
    except Exception as e:
        print(f"{Colors.RED}[ERROR] Failed to read issue: {e}{Colors.END}")
        return 1

    # Step 2: Generate work order (simulated PM)
    print_step(2, "Generating work order (simulated PM dispatch)...")
    work_order = simulate_work_order_generation(issue, demo_dir)
    print_success(f"Work order ID: {work_order['work_order']['id']}")
    print_info(f"Task type: {work_order['work_order']['task_type']}")
    print_info(f"Time box: {work_order['work_order']['time_box']}")

    # Step 3: Simulate fixer agents
    print_step(3, "Simulating fixer agents...")
    fixers = simulate_fixer_agents(issue)
    for fixer in fixers:
        print_success(f"{fixer['fixer_id']}: {fixer['action']}")
    print_info(f"Fixers simulated: {len(fixers)}")

    # Step 4: Generate verdict (simulated Critic Orchestrator)
    print_step(4, "Generating verdict (simulated Critic evaluation)...")
    verdict = simulate_verdict(issue, work_order)
    print_success(f"Verdict: {verdict['final_verdict']}")
    print_info(f"Overall score: {verdict['overall_score']}")
    print_info(f"Dimensions evaluated: {len(verdict['dimension_results'])}")

    # Step 5: Write artifacts
    print_step(5, "Writing artifacts to /demo...")
    write_artifacts(demo_dir, work_order, verdict)
    print_success("demo_work_order_generated.yaml")
    print_success("demo_verdict_generated.yaml")

    # Summary
    print_header("DEMO RUN COMPLETE")
    print(f"  Lane:              {Colors.BOLD}{issue['lane']}{Colors.END}")
    print(f"  Issue:             {Colors.BOLD}{issue['issue_id']}{Colors.END}")
    print(f"  Fixers simulated:  {Colors.BOLD}{len(fixers)}{Colors.END}")
    print(f"  Verdict:           {Colors.GREEN}{Colors.BOLD}{verdict['final_verdict']}{Colors.END}")
    print(f"  Artifacts written: {Colors.BOLD}/demo{Colors.END}")
    print()
    print(f"{Colors.CYAN}This demonstrates the orchestration PATTERN.{Colors.END}")
    print(f"{Colors.CYAN}Real system uses AI agents with proprietary logic.{Colors.END}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
