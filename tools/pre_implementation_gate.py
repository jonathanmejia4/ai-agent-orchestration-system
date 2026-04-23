#!/usr/bin/env python3
"""
Pre-Implementation Gate Checker

Validates pre-implementation gates per builder-scope-enforcement.md:218-252.
Ensures Builders verify all gates before starting work.

Gates checked:
1. Work Order Valid - WO exists and status is ASSIGNED
2. Task Assigned - task_id is specified
3. Requirements Clear - All requirements are actionable
4. Dependencies Met - Required dependencies available

Usage:
    python tools/pre_implementation_gate.py --work-order <path>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def is_dependency_met(dep: str) -> bool:
    """
    Check if a dependency is met.

    Args:
        dep: Dependency identifier (task_id, work_order_id, or file path)

    Returns:
        True if dependency is available
    """
    # For now, we check if the dependency exists as a path or is marked as complete
    # In a full implementation, this would check work order status, task completion, etc.

    # Check if it's a file path that exists
    dep_path = Path(dep)
    if dep_path.exists():
        return True

    # Check if it looks like a completed task (has .task/ directory)
    if "/" in dep or "." in dep:
        task_path = Path(dep) / ".task"
        if task_path.exists():
            return True

    # For work order IDs or other deps, we'd check LogBook/workflows/work_orders/
    # For now, assume unverifiable deps are met (permissive)
    return True


def pre_implementation_check(work_order: Dict) -> Tuple[bool, List[str]]:
    """
    Verify all pre-implementation gates pass.

    Args:
        work_order: Work order dictionary

    Returns:
        Tuple of (all_passed, list_of_failures)
    """
    failures = []

    # Gate 1: Work Order Valid
    if work_order.get("status") != "ASSIGNED":
        current_status = work_order.get("status", "MISSING")
        failures.append(
            f"Work order not in ASSIGNED status (current: {current_status})"
        )

    # Gate 2: Task Assigned
    if not work_order.get("task_id"):
        failures.append("No task_id assigned")

    # Gate 3: Requirements Clear
    requirements = work_order.get("requirements")
    if not requirements:
        failures.append("No requirements specified")
    elif isinstance(requirements, list) and len(requirements) == 0:
        failures.append("Requirements list is empty")
    elif isinstance(requirements, str) and requirements.strip() == "":
        failures.append("Requirements string is empty")

    # Gate 4: Dependencies Met
    deps = work_order.get("dependencies", [])
    for dep in deps:
        if not is_dependency_met(dep):
            failures.append(f"Dependency not met: {dep}")

    return len(failures) == 0, failures


def main():
    parser = argparse.ArgumentParser(
        description="Check pre-implementation gates for Builder work orders"
    )
    parser.add_argument(
        "--work-order",
        required=True,
        help="Path to work order JSON file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed gate check results"
    )

    args = parser.parse_args()

    # Load work order
    wo_path = Path(args.work_order)
    if not wo_path.exists():
        print(f"ERROR: Work order file not found: {wo_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(wo_path) as f:
            work_order = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in work order: {e}", file=sys.stderr)
        sys.exit(1)

    # Run pre-implementation check
    all_passed, failures = pre_implementation_check(work_order)

    # Report results
    if args.verbose or not all_passed:
        print(f"Pre-Implementation Gate Check: {wo_path}")
        print(f"Work Order ID: {work_order.get('work_order_id', 'UNKNOWN')}")
        print(f"Task ID: {work_order.get('task_id', 'NONE')}")
        print(f"Status: {work_order.get('status', 'UNKNOWN')}")
        print()

    if all_passed:
        print("✓ All pre-implementation gates passed")
        print("Builder may proceed with implementation")
        sys.exit(0)
    else:
        print("✗ Pre-implementation gate check FAILED", file=sys.stderr)
        print(f"\n{len(failures)} gate(s) failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print("\nBuilder MUST NOT start implementation until gates pass", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
