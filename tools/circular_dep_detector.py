#!/usr/bin/env python3
"""
Circular Dependency Detector

Detects circular dependencies in task dependency graphs by analyzing wiring.yaml files.
Used by CI to prevent merging tasks that introduce circular dependencies.

Usage:
    python3 tools/circular_dep_detector.py --task <task_id>
    python3 tools/circular_dep_detector.py --full
    python3 tools/circular_dep_detector.py --wiring-file <path>

Exit Codes:
    0 - No circular dependencies detected
    1 - Circular dependencies found
    2 - Error (file not found, invalid YAML, etc.)

Examples:
    python3 tools/circular_dep_detector.py --task 3.1
    python3 tools/circular_dep_detector.py --full
    python3 tools/circular_dep_detector.py --wiring-file tasks/3.1/.task/wiring.yaml

Output:
    JSON report with detected cycles, dependency paths, and resolution suggestions

References:
    - .claude/guidelines/quality-standards.md - Section on dependency validation
    - ISSUE_CATALOG.md - Issue A24

Author: System
Created: 2025-12-23
"""

import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

class CircularDependencyDetector:
    """
    Detects circular dependencies in task dependency graphs using DFS.
    """

    def __init__(self, wiring_file: Optional[str] = None):
        """
        Initialize detector.

        Args:
            wiring_file: Optional specific wiring.yaml file to analyze
        """
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.cycles: List[List[str]] = []
        self.wiring_file = wiring_file

    def load_wiring_yaml(self, file_path: Path) -> Optional[Dict]:
        """
        Load and parse wiring.yaml file.

        Args:
            file_path: Path to wiring.yaml file

        Returns:
            Parsed YAML dict or None if error
        """
        try:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"{RED}ERROR{NC}: Wiring file not found: {file_path}", file=sys.stderr)
            return None
        except yaml.YAMLError as e:
            print(f"{RED}ERROR{NC}: Invalid YAML in {file_path}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"{RED}ERROR{NC}: Failed to read {file_path}: {e}", file=sys.stderr)
            return None

    def build_dependency_graph_from_file(self, wiring_file: Path) -> bool:
        """
        Build dependency graph from a single wiring.yaml file.

        Args:
            wiring_file: Path to wiring.yaml file

        Returns:
            True if successful, False otherwise
        """
        wiring = self.load_wiring_yaml(wiring_file)
        if wiring is None:
            return False

        # Extract task ID from file path or wiring content
        task_id = wiring.get('task_id')
        if not task_id:
            # Try to infer from path: tasks/3.1/.task/wiring.yaml -> 3.1
            parts = wiring_file.parts
            if 'tasks' in parts:
                task_index = parts.index('tasks')
                if task_index + 1 < len(parts):
                    task_id = parts[task_index + 1]

        if not task_id:
            print(f"{YELLOW}WARNING{NC}: Could not determine task_id from {wiring_file}", file=sys.stderr)
            return False

        # Add dependencies to graph
        dependencies = wiring.get('dependencies', [])
        for dep in dependencies:
            if isinstance(dep, dict):
                dep_id = dep.get('task_id')
            else:
                dep_id = dep

            if dep_id:
                self.graph[task_id].append(dep_id)

        # Ensure task exists in graph even if it has no dependencies
        if task_id not in self.graph:
            self.graph[task_id] = []

        return True

    def build_full_dependency_graph(self, tasks_dir: Path = Path('tasks')) -> bool:
        """
        Build complete dependency graph from all wiring.yaml files in tasks directory.

        Args:
            tasks_dir: Path to tasks directory

        Returns:
            True if successful, False otherwise
        """
        if not tasks_dir.exists():
            print(f"{RED}ERROR{NC}: Tasks directory not found: {tasks_dir}", file=sys.stderr)
            return False

        # Find all wiring.yaml files
        wiring_files = list(tasks_dir.glob('**/.task/wiring.yaml'))

        if not wiring_files:
            print(f"{YELLOW}WARNING{NC}: No wiring.yaml files found in {tasks_dir}", file=sys.stderr)
            return True  # Not an error, just no tasks

        success = True
        for wiring_file in wiring_files:
            if not self.build_dependency_graph_from_file(wiring_file):
                success = False

        return success

    def detect_cycles_dfs(self, start_node: str) -> List[List[str]]:
        """
        Detect all cycles reachable from start_node using DFS.

        Args:
            start_node: Node to start DFS from

        Returns:
            List of cycles (each cycle is a list of node IDs)
        """
        visited: Set[str] = set()
        rec_stack: List[str] = []
        cycles: List[List[str]] = []

        def dfs(node: str) -> None:
            """Recursive DFS helper"""
            visited.add(node)
            rec_stack.append(node)

            # Check all neighbors
            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = rec_stack.index(neighbor)
                    cycle = rec_stack[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.pop()

        dfs(start_node)
        return cycles

    def detect_all_cycles(self) -> List[List[str]]:
        """
        Detect all cycles in the dependency graph.

        Returns:
            List of all unique cycles found
        """
        all_cycles: List[List[str]] = []
        visited_global: Set[str] = set()

        for node in self.graph:
            if node not in visited_global:
                cycles = self.detect_cycles_dfs(node)
                for cycle in cycles:
                    # Normalize cycle representation for deduplication
                    # (rotate to start with smallest ID)
                    min_idx = cycle[:-1].index(min(cycle[:-1]))  # Exclude duplicate end node
                    normalized = cycle[min_idx:-1] + [cycle[min_idx]]

                    # Check if this cycle is already recorded
                    if normalized not in all_cycles:
                        all_cycles.append(normalized)

                # Mark all nodes in these cycles as visited
                for cycle in cycles:
                    visited_global.update(cycle)

        return all_cycles

    def generate_resolution_suggestions(self, cycle: List[str]) -> List[str]:
        """
        Generate suggestions for resolving a circular dependency.

        Args:
            cycle: List of task IDs forming a cycle

        Returns:
            List of resolution suggestion strings
        """
        suggestions = []

        # Suggestion 1: Remove weakest dependency
        suggestions.append(
            f"Remove one dependency from the cycle (e.g., {cycle[-2]} -> {cycle[-1]})"
        )

        # Suggestion 2: Introduce intermediate task
        suggestions.append(
            f"Introduce an intermediate task to break the cycle"
        )

        # Suggestion 3: Refactor to extract common functionality
        suggestions.append(
            f"Extract common functionality into a shared task that {cycle[0]} and {cycle[1]} both depend on"
        )

        # Suggestion 4: Use dependency injection
        suggestions.append(
            f"Use dependency injection or inversion of control to break the circular reference"
        )

        return suggestions

    def generate_report(self, task_id: Optional[str] = None) -> dict:
        """
        Generate JSON report of circular dependencies.

        Args:
            task_id: Optional specific task to check (None for full graph)

        Returns:
            Report dictionary with cycles, paths, and suggestions
        """
        # Detect cycles
        if task_id:
            cycles = self.detect_cycles_dfs(task_id)
        else:
            cycles = self.detect_all_cycles()

        # Build report
        report = {
            "status": "fail" if cycles else "pass",
            "cycles_detected": len(cycles),
            "cycles": [],
            "graph_summary": {
                "total_tasks": len(self.graph),
                "total_dependencies": sum(len(deps) for deps in self.graph.values())
            }
        }

        # Add cycle details
        for i, cycle in enumerate(cycles):
            cycle_report = {
                "cycle_id": i + 1,
                "path": cycle,
                "length": len(cycle) - 1,  # Exclude duplicate end node
                "resolution_suggestions": self.generate_resolution_suggestions(cycle)
            }
            report["cycles"].append(cycle_report)

        return report

    def print_human_readable_report(self, report: dict) -> None:
        """
        Print human-readable version of report to stdout.

        Args:
            report: Report dictionary from generate_report()
        """
        if report["status"] == "pass":
            print(f"{GREEN}✓ No circular dependencies detected{NC}")
            print(f"\nGraph Summary:")
            print(f"  Total tasks: {report['graph_summary']['total_tasks']}")
            print(f"  Total dependencies: {report['graph_summary']['total_dependencies']}")
        else:
            print(f"{RED}✗ {report['cycles_detected']} circular dependenc{'y' if report['cycles_detected'] == 1 else 'ies'} detected{NC}")
            print(f"\nGraph Summary:")
            print(f"  Total tasks: {report['graph_summary']['total_tasks']}")
            print(f"  Total dependencies: {report['graph_summary']['total_dependencies']}")
            print()

            for cycle_info in report["cycles"]:
                print(f"{YELLOW}Cycle #{cycle_info['cycle_id']}{NC} (length {cycle_info['length']}):")
                print(f"  Path: {' -> '.join(cycle_info['path'])}")
                print(f"\n  {BLUE}Resolution Suggestions:{NC}")
                for j, suggestion in enumerate(cycle_info['resolution_suggestions'], 1):
                    print(f"    {j}. {suggestion}")
                print()

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Detect circular dependencies in task dependency graphs',
        epilog='Examples:\n'
               '  %(prog)s --task 3.1\n'
               '  %(prog)s --full\n'
               '  %(prog)s --wiring-file tasks/3.1/.task/wiring.yaml',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--task', metavar='ID',
                      help='Check specific task by ID (e.g., 3.1)')
    group.add_argument('--full', action='store_true',
                      help='Check full dependency graph (all tasks)')
    group.add_argument('--wiring-file', metavar='PATH',
                      help='Check specific wiring.yaml file')

    parser.add_argument('--json', action='store_true',
                       help='Output JSON report only (no human-readable text)')
    parser.add_argument('--tasks-dir', metavar='DIR', default='tasks',
                       help='Tasks directory (default: tasks)')

    args = parser.parse_args()

    # Initialize detector
    detector = CircularDependencyDetector()

    # Build dependency graph
    if args.wiring_file:
        wiring_path = Path(args.wiring_file)
        if not detector.build_dependency_graph_from_file(wiring_path):
            sys.exit(2)
        task_id = None  # Will check all tasks in the file

    elif args.task:
        # Load full graph, then check specific task
        tasks_dir = Path(args.tasks_dir)
        if not detector.build_full_dependency_graph(tasks_dir):
            sys.exit(2)
        task_id = args.task

        # Verify task exists
        if task_id not in detector.graph:
            print(f"{RED}ERROR{NC}: Task '{task_id}' not found in dependency graph", file=sys.stderr)
            sys.exit(2)

    else:  # args.full
        tasks_dir = Path(args.tasks_dir)
        if not detector.build_full_dependency_graph(tasks_dir):
            sys.exit(2)
        task_id = None  # Check all tasks

    # Generate report
    report = detector.generate_report(task_id)

    # Output report
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        detector.print_human_readable_report(report)
        if report["status"] == "fail":
            print(f"\n{BLUE}JSON Report:{NC}")
            print(json.dumps(report, indent=2))

    # Exit with appropriate code
    if report["status"] == "pass":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
