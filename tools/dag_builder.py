#!/usr/bin/env python3
"""
DAG Builder - Constructs Dependency Graphs from Task Plans

Parses task plan files and constructs directed acyclic graphs (DAGs) representing
task dependencies. Validates acyclicity, calculates topological order, and outputs
the graph structure for use by Builder and PM agents.

Usage:
    # Build graph from task plan
    python3 tools/dag_builder.py PLANNING/task_plan.yaml --output .task/graph.yaml

    # Validate only (no output file)
    python3 tools/dag_builder.py PLANNING/task_plan.yaml --validate

    # Output in JSON format
    python3 tools/dag_builder.py PLANNING/task_plan.yaml --output graph.json --format json

    # Visualize graph (outputs DOT format)
    python3 tools/dag_builder.py PLANNING/task_plan.yaml --dot graph.dot

Exit Codes:
    0 - Success (graph built, no cycles)
    1 - Cycle detected (not a DAG)
    2 - Error (missing files, invalid YAML, etc.)

Referenced in:
    - DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md:1013, 1019, 1028, 1667, 1697

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict, deque
from datetime import datetime

class DAGBuilder:
    """Builds directed acyclic graphs from task plans"""

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, str]] = []
        self.adjacency: Dict[str, List[str]] = defaultdict(list)
        self.reverse_adjacency: Dict[str, List[str]] = defaultdict(list)
        self.cycles: List[List[str]] = []

    def parse_task_plan(self, plan_path: Path) -> bool:
        """
        Parse a task plan YAML file and extract nodes/edges.

        Expected format:
            tasks:
              - id: task-1.1
                name: "Setup database schema"
                depends_on: []
              - id: task-1.2
                name: "Create user model"
                depends_on: [task-1.1]

        Returns:
            True if parsing succeeded, False otherwise
        """
        try:
            with open(plan_path, 'r') as f:
                plan_data = yaml.safe_load(f)

            if not plan_data:
                print(f"Error: Empty or invalid YAML in {plan_path}", file=sys.stderr)
                return False

            # Handle different plan formats
            tasks = plan_data.get('tasks', [])
            if not tasks:
                # Try alternative formats
                tasks = plan_data.get('phases', [])
                if tasks:
                    # Flatten phases structure
                    tasks = self._flatten_phases(tasks)
                else:
                    # Maybe it's a flat list
                    if isinstance(plan_data, list):
                        tasks = plan_data

            if not tasks:
                print(f"Error: No tasks found in {plan_path}", file=sys.stderr)
                return False

            # Process each task
            for task in tasks:
                task_id = task.get('id') or task.get('task_id') or task.get('name')
                if not task_id:
                    print(f"Warning: Task missing id field, skipping: {task}", file=sys.stderr)
                    continue

                # Store node information
                self.nodes[task_id] = {
                    'id': task_id,
                    'label': task.get('name') or task.get('label') or task_id,
                    'description': task.get('description', ''),
                    'status': task.get('status', 'pending'),
                    'priority': task.get('priority', 0),
                    'dependencies': []
                }

                # Process dependencies
                depends_on = task.get('depends_on', []) or task.get('dependencies', [])
                if isinstance(depends_on, str):
                    depends_on = [depends_on]

                self.nodes[task_id]['dependencies'] = depends_on

                for dep in depends_on:
                    self.adjacency[dep].append(task_id)
                    self.reverse_adjacency[task_id].append(dep)
                    self.edges.append({'from': dep, 'to': task_id})

            return True

        except yaml.YAMLError as e:
            print(f"Error: Invalid YAML in {plan_path}: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error: Failed to parse {plan_path}: {e}", file=sys.stderr)
            return False

    def _flatten_phases(self, phases: List[Dict]) -> List[Dict]:
        """Flatten phases structure into task list"""
        tasks = []
        for phase in phases:
            phase_tasks = phase.get('tasks', [])
            tasks.extend(phase_tasks)
        return tasks

    def detect_cycles(self) -> List[List[str]]:
        """
        Detect all cycles in the graph using DFS.

        Returns:
            List of cycles, where each cycle is a list of node IDs
        """
        self.cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.adjacency.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    self.cycles.append(cycle)
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return self.cycles

    def is_acyclic(self) -> bool:
        """Check if the graph is acyclic (valid DAG)"""
        return len(self.detect_cycles()) == 0

    def topological_sort(self) -> Optional[List[str]]:
        """
        Perform topological sort using Kahn's algorithm.

        Returns:
            List of node IDs in topological order, or None if cycle exists
        """
        # Calculate in-degrees
        in_degree = defaultdict(int)
        for node in self.nodes:
            in_degree[node] = len(self.reverse_adjacency.get(node, []))

        # Find all nodes with no incoming edges
        queue = deque([node for node in self.nodes if in_degree[node] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            for neighbor in self.adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If result doesn't contain all nodes, there's a cycle
        if len(result) != len(self.nodes):
            return None

        return result

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Group nodes into parallel execution levels.

        Returns:
            List of lists, where each inner list contains nodes that can be
            executed in parallel (same dependency level)
        """
        if not self.is_acyclic():
            return []

        levels = []
        remaining = set(self.nodes.keys())
        completed = set()

        while remaining:
            # Find nodes whose dependencies are all completed
            ready = []
            for node in remaining:
                deps = set(self.reverse_adjacency.get(node, []))
                if deps.issubset(completed):
                    ready.append(node)

            if not ready:
                # Should not happen if graph is acyclic
                break

            levels.append(sorted(ready))
            completed.update(ready)
            remaining -= set(ready)

        return levels

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate graph metrics"""
        metrics = {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'is_acyclic': self.is_acyclic(),
            'max_depth': 0,
            'root_nodes': [],
            'leaf_nodes': [],
            'avg_dependencies': 0.0
        }

        # Find root nodes (no dependencies)
        for node in self.nodes:
            if not self.reverse_adjacency.get(node):
                metrics['root_nodes'].append(node)

        # Find leaf nodes (no dependents)
        for node in self.nodes:
            if not self.adjacency.get(node):
                metrics['leaf_nodes'].append(node)

        # Calculate max depth and average dependencies
        if self.nodes:
            total_deps = sum(len(self.reverse_adjacency.get(n, [])) for n in self.nodes)
            metrics['avg_dependencies'] = round(total_deps / len(self.nodes), 2)

            # Calculate depth using BFS from roots
            depths = {}
            queue = deque([(n, 0) for n in metrics['root_nodes']])
            while queue:
                node, depth = queue.popleft()
                if node not in depths or depths[node] < depth:
                    depths[node] = depth
                    metrics['max_depth'] = max(metrics['max_depth'], depth)
                    for neighbor in self.adjacency.get(node, []):
                        queue.append((neighbor, depth + 1))

        return metrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to dictionary format"""
        topo_order = self.topological_sort()
        parallel_groups = self.get_parallel_groups()
        metrics = self.calculate_metrics()

        return {
            'nodes': [
                {
                    'id': node_id,
                    'name': data['label'],  # Template uses 'name' not 'label'
                    'type': 'implementation',  # Default type per graph.yaml template
                    'estimated_duration_minutes': 0,  # Default per graph.yaml template
                    'assigned_to': 'Builder',  # Default per graph.yaml template
                    'status': data['status'],
                    # Also include original fields for backward compatibility
                    'description': data['description'],
                    'priority': data['priority'],
                    'dependencies': data['dependencies']
                }
                for node_id, data in self.nodes.items()
            ],
            'edges': self.edges,
            'topological_order': topo_order or [],
            'parallel_groups': parallel_groups,
            'metadata': {
                'total_nodes': metrics['total_nodes'],
                'total_edges': metrics['total_edges'],
                'is_acyclic': metrics['is_acyclic'],
                'max_depth': metrics['max_depth'],
                'root_nodes': metrics['root_nodes'],
                'leaf_nodes': metrics['leaf_nodes'],
                'avg_dependencies': metrics['avg_dependencies'],
                'generated_at': datetime.now().isoformat(),
                'generator': 'tools/dag_builder.py'
            }
        }

    def to_dot(self) -> str:
        """Convert graph to DOT format for visualization"""
        lines = ['digraph TaskDAG {', '    rankdir=TB;', '    node [shape=box];', '']

        # Add nodes
        for node_id, data in self.nodes.items():
            label = data['label'].replace('"', '\\"')
            status = data['status']
            color = {
                'completed': 'green',
                'in_progress': 'yellow',
                'blocked': 'red',
                'pending': 'white'
            }.get(status, 'white')
            lines.append(f'    "{node_id}" [label="{label}" style=filled fillcolor={color}];')

        lines.append('')

        # Add edges
        for edge in self.edges:
            lines.append(f'    "{edge["from"]}" -> "{edge["to"]}";')

        lines.append('}')
        return '\n'.join(lines)

    def save(self, output_path: Path, format: str = 'yaml') -> bool:
        """Save graph to file"""
        try:
            data = self.to_dict()

            with open(output_path, 'w') as f:
                if format == 'json':
                    json.dump(data, f, indent=2)
                elif format == 'dot':
                    f.write(self.to_dot())
                else:  # yaml
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            return True
        except Exception as e:
            print(f"Error: Failed to save graph to {output_path}: {e}", file=sys.stderr)
            return False

def main():
    parser = argparse.ArgumentParser(
        description='Build dependency graphs from task plans',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s PLANNING/task_plan.yaml --output .task/graph.yaml
    %(prog)s PLANNING/task_plan.yaml --validate
    %(prog)s PLANNING/task_plan.yaml --dot graph.dot
        """
    )

    parser.add_argument('plan_path', type=Path, help='Path to task plan YAML file')
    parser.add_argument('--output', '-o', type=Path, help='Output file path')
    parser.add_argument('--format', '-f', choices=['yaml', 'json', 'dot'], default='yaml',
                        help='Output format (default: yaml)')
    parser.add_argument('--validate', '-v', action='store_true',
                        help='Validate only, do not write output')
    parser.add_argument('--dot', type=Path, help='Output DOT file for visualization')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output')

    args = parser.parse_args()

    # Validate input file exists
    if not args.plan_path.exists():
        print(f"Error: Task plan not found: {args.plan_path}", file=sys.stderr)
        sys.exit(2)

    # Build the DAG
    builder = DAGBuilder()

    if not builder.parse_task_plan(args.plan_path):
        sys.exit(2)

    # Check for cycles
    cycles = builder.detect_cycles()

    if cycles:
        if not args.quiet:
            print("CIRCULAR DEPENDENCIES DETECTED:", file=sys.stderr)
            for cycle in cycles:
                cycle_str = ' -> '.join(cycle)
                print(f"  {cycle_str}", file=sys.stderr)
        sys.exit(1)

    # Calculate metrics
    metrics = builder.calculate_metrics()

    if not args.quiet:
        print(f"DAG Analysis for: {args.plan_path}")
        print(f"  Nodes: {metrics['total_nodes']}")
        print(f"  Edges: {metrics['total_edges']}")
        print(f"  Max Depth: {metrics['max_depth']}")
        print(f"  Root Nodes: {len(metrics['root_nodes'])}")
        print(f"  Leaf Nodes: {len(metrics['leaf_nodes'])}")
        print(f"  Avg Dependencies: {metrics['avg_dependencies']}")
        print(f"  Is Acyclic: {metrics['is_acyclic']}")

        # Show parallel groups
        parallel_groups = builder.get_parallel_groups()
        if parallel_groups:
            print(f"\nParallel Execution Groups ({len(parallel_groups)} levels):")
            for i, group in enumerate(parallel_groups):
                print(f"  Level {i}: {', '.join(group)}")

    # Save output if requested
    if args.output and not args.validate:
        if builder.save(args.output, args.format):
            if not args.quiet:
                print(f"\nGraph saved to: {args.output}")
        else:
            sys.exit(2)

    # Save DOT file if requested
    if args.dot and not args.validate:
        if builder.save(args.dot, 'dot'):
            if not args.quiet:
                print(f"DOT file saved to: {args.dot}")
        else:
            sys.exit(2)

    if not args.quiet:
        print("\n DAG is valid (no cycles detected)")

    sys.exit(0)

if __name__ == '__main__':
    main()
