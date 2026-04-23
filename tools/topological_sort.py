#!/usr/bin/env python3
"""
topological_sort.py - DAG topological ordering and analysis tool

Computes topological order of tasks using Kahn's algorithm, identifies
parallel work sets (waves), and calculates critical path. PM uses output
to populate SSOT Section 9 (Build Order & Scheduling).

Exit codes:
  0 - Success
  1 - Cycle detected or invalid graph
  2 - File/parse error

Usage:
  python tools/topological_sort.py graph.yaml
  python tools/topological_sort.py .task/graph.yaml --format=json
  python tools/topological_sort.py graph.yaml --verbose --ssot-format

Reference: PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md
"""

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml

class TopologicalSorter:
    """Compute topological order, parallel waves, and critical path for DAG."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str]] = []
        self.adjacency: dict[str, list[str]] = defaultdict(list)
        self.reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self.build_times: dict[str, float] = {}
        self.topological_order: list[str] = []
        self.waves: list[list[str]] = []
        self.critical_path: list[str] = []
        self.critical_path_length: float = 0.0
        self.errors: list[str] = []

    def load_graph(self, graph_path: Path) -> bool:
        """Load and parse the dependency graph file."""
        try:
            with open(graph_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                self.errors.append("Empty graph file")
                return False

            # Parse nodes with build times
            nodes_data = data.get("nodes", data.get("tasks", []))
            if isinstance(nodes_data, list):
                for node in nodes_data:
                    if isinstance(node, dict):
                        node_id = str(node.get("id", node.get("task_id", node.get("name", ""))))
                        if node_id:
                            self.nodes[node_id] = node
                            build_time = node.get("build_time", node.get("duration", node.get("time", 1.0)))
                            self.build_times[node_id] = float(build_time)
                    elif isinstance(node, str):
                        self.nodes[node] = {"id": node}
                        self.build_times[node] = 1.0
            elif isinstance(nodes_data, dict):
                for node_id, node_data in nodes_data.items():
                    node_id = str(node_id)
                    self.nodes[node_id] = node_data if isinstance(node_data, dict) else {"id": node_id}
                    if isinstance(node_data, dict):
                        build_time = node_data.get("build_time", node_data.get("duration", 1.0))
                        self.build_times[node_id] = float(build_time)
                    else:
                        self.build_times[node_id] = 1.0

            # Parse edges
            edges_data = data.get("edges", data.get("dependencies", []))
            if isinstance(edges_data, list):
                for edge in edges_data:
                    if isinstance(edge, dict):
                        source = str(edge.get("from", edge.get("source", edge.get("parent", ""))))
                        target = str(edge.get("to", edge.get("target", edge.get("child", ""))))
                        if source and target:
                            self.edges.append((source, target))
                            self.adjacency[source].append(target)
                            self.reverse_adjacency[target].append(source)
                    elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
                        source, target = str(edge[0]), str(edge[1])
                        self.edges.append((source, target))
                        self.adjacency[source].append(target)
                        self.reverse_adjacency[target].append(source)

            # Check for inline dependencies in node definitions
            for node_id, node_data in self.nodes.items():
                if isinstance(node_data, dict):
                    deps = node_data.get("dependencies", node_data.get("depends_on", []))
                    if isinstance(deps, list):
                        for dep in deps:
                            dep_id = str(dep)
                            edge = (dep_id, node_id)
                            if edge not in self.edges:
                                self.edges.append(edge)
                                self.adjacency[dep_id].append(node_id)
                                self.reverse_adjacency[node_id].append(dep_id)

            if not self.nodes:
                self.errors.append("No nodes found in graph")
                return False

            return True

        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error: {e}")
            return False
        except FileNotFoundError:
            self.errors.append(f"File not found: {graph_path}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading graph: {e}")
            return False

    def compute_topological_order(self) -> list[str]:
        """
        Compute topological order using Kahn's algorithm.
        Returns empty list if cycle detected.
        """
        # Calculate in-degree for each node
        in_degree = {node: 0 for node in self.nodes}
        for source, target in self.edges:
            if target in in_degree:
                in_degree[target] += 1

        # Initialize queue with nodes having in-degree 0
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            # Sort to ensure deterministic order for nodes with same in-degree
            current = queue.popleft()
            result.append(current)

            # Reduce in-degree of neighbors
            for neighbor in sorted(self.adjacency.get(current, [])):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            # Re-sort queue for deterministic output
            queue = deque(sorted(queue))

        # Check for cycle
        if len(result) != len(self.nodes):
            remaining = set(self.nodes.keys()) - set(result)
            self.errors.append(f"Cycle detected! Nodes in cycle: {sorted(remaining)}")
            return []

        self.topological_order = result
        return result

    def compute_parallel_waves(self) -> list[list[str]]:
        """
        Compute parallel execution waves (levels).
        Nodes in the same wave have no dependencies between them.
        """
        if not self.topological_order:
            if not self.compute_topological_order():
                return []

        # Calculate level for each node (longest path from any root)
        levels: dict[str, int] = {}

        for node in self.topological_order:
            predecessors = self.reverse_adjacency.get(node, [])
            if not predecessors:
                levels[node] = 0
            else:
                levels[node] = max(levels.get(pred, 0) for pred in predecessors) + 1

        # Group nodes by level
        max_level = max(levels.values()) if levels else 0
        waves = [[] for _ in range(max_level + 1)]
        for node, level in levels.items():
            waves[level].append(node)

        # Sort each wave for deterministic output
        self.waves = [sorted(wave) for wave in waves]
        return self.waves

    def compute_critical_path(self) -> tuple[list[str], float]:
        """
        Compute the critical path (longest weighted path) through the DAG.
        Returns (path_nodes, total_length).
        """
        if not self.topological_order:
            if not self.compute_topological_order():
                return [], 0.0

        # Forward pass: compute earliest completion time for each node
        earliest_completion: dict[str, float] = {}
        predecessor_on_path: dict[str, str | None] = {}

        for node in self.topological_order:
            node_time = self.build_times.get(node, 1.0)
            predecessors = self.reverse_adjacency.get(node, [])

            if not predecessors:
                earliest_completion[node] = node_time
                predecessor_on_path[node] = None
            else:
                # Find predecessor that gives maximum completion time
                max_pred = None
                max_time = 0.0
                for pred in predecessors:
                    pred_completion = earliest_completion.get(pred, 0.0)
                    if pred_completion > max_time:
                        max_time = pred_completion
                        max_pred = pred
                earliest_completion[node] = max_time + node_time
                predecessor_on_path[node] = max_pred

        # Find the node with maximum completion time
        if not earliest_completion:
            return [], 0.0

        end_node = max(earliest_completion.keys(), key=lambda n: earliest_completion[n])
        self.critical_path_length = earliest_completion[end_node]

        # Backtrack to construct critical path
        path = []
        current = end_node
        while current is not None:
            path.append(current)
            current = predecessor_on_path.get(current)

        path.reverse()
        self.critical_path = path
        return path, self.critical_path_length

    def get_node_depths(self) -> dict[str, int]:
        """Get depth (distance from roots) for each node."""
        depths: dict[str, int] = {}
        for node in self.topological_order:
            preds = self.reverse_adjacency.get(node, [])
            if not preds:
                depths[node] = 0
            else:
                depths[node] = max(depths.get(p, 0) for p in preds) + 1
        return depths

    def get_sequential_time(self) -> float:
        """Calculate total time if all nodes executed sequentially."""
        return sum(self.build_times.values())

    def get_parallel_time(self) -> float:
        """Calculate total time with optimal parallel execution."""
        if not self.waves:
            self.compute_parallel_waves()

        total = 0.0
        for wave in self.waves:
            if wave:
                wave_max = max(self.build_times.get(n, 1.0) for n in wave)
                total += wave_max
        return total

    def format_ssot_section9(self) -> str:
        """Format output for SSOT Section 9 (Build Order & Scheduling)."""
        lines = []
        lines.append("## Section 9: Build Order & Scheduling")
        lines.append("")
        lines.append("### 9.1 Topological Build Order")
        lines.append("")
        lines.append("| Position | Task ID | Build Time | Dependencies |")
        lines.append("|----------|----------|------------|--------------|")

        for i, node in enumerate(self.topological_order, 1):
            build_time = self.build_times.get(node, 1.0)
            deps = self.reverse_adjacency.get(node, [])
            deps_str = ", ".join(sorted(deps)) if deps else "None (root)"
            lines.append(f"| {i} | {node} | {build_time:.1f}h | {deps_str} |")

        lines.append("")
        lines.append("### 9.2 Parallel Execution Waves")
        lines.append("")

        for i, wave in enumerate(self.waves, 1):
            wave_times = [self.build_times.get(n, 1.0) for n in wave]
            wave_max = max(wave_times) if wave_times else 0
            wave_total = sum(wave_times)
            lines.append(f"**Wave {i}** (Duration: {wave_max:.1f}h, Total Work: {wave_total:.1f}h)")
            lines.append(f"- Tasks: {', '.join(wave)}")
            lines.append(f"- Max parallel workers: {len(wave)}")
            lines.append("")

        lines.append("### 9.3 Critical Path")
        lines.append("")
        lines.append(f"**Total Duration:** {self.critical_path_length:.1f}h")
        lines.append("")
        lines.append("| Step | Task ID | Duration | Cumulative |")
        lines.append("|------|----------|----------|------------|")

        cumulative = 0.0
        for i, node in enumerate(self.critical_path, 1):
            duration = self.build_times.get(node, 1.0)
            cumulative += duration
            lines.append(f"| {i} | {node} | {duration:.1f}h | {cumulative:.1f}h |")

        lines.append("")
        lines.append("### 9.4 Resource Summary")
        lines.append("")
        seq_time = self.get_sequential_time()
        par_time = self.get_parallel_time()
        savings = seq_time - par_time
        speedup_pct = (savings / seq_time * 100) if seq_time > 0 else 0

        max_parallel = max(len(wave) for wave in self.waves) if self.waves else 0
        avg_parallel = sum(len(wave) for wave in self.waves) / len(self.waves) if self.waves else 0

        lines.append(f"- **Total Tasks:** {len(self.nodes)}")
        lines.append(f"- **Total Dependencies:** {len(self.edges)}")
        lines.append(f"- **Sequential Time:** {seq_time:.1f}h")
        lines.append(f"- **Parallel Time:** {par_time:.1f}h")
        lines.append(f"- **Time Saved:** {savings:.1f}h ({speedup_pct:.1f}%)")
        lines.append(f"- **Max Parallel Workers:** {max_parallel}")
        lines.append(f"- **Avg Parallel Workers:** {avg_parallel:.1f}")
        lines.append(f"- **Total Waves:** {len(self.waves)}")
        lines.append("")

        return "\n".join(lines)

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("TOPOLOGICAL SORT ANALYSIS")
        lines.append("=" * 60)
        lines.append(f"Nodes: {len(self.nodes)}")
        lines.append(f"Edges: {len(self.edges)}")
        lines.append("")

        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
            return "\n".join(lines)

        # Topological Order
        lines.append("TOPOLOGICAL ORDER:")
        lines.append("-" * 40)
        for i, node in enumerate(self.topological_order, 1):
            deps = self.reverse_adjacency.get(node, [])
            deps_str = f" (depends on: {', '.join(sorted(deps))})" if deps else " (root)"
            lines.append(f"  {i:3}. {node}{deps_str}")

        # Parallel Waves
        lines.append("")
        lines.append("=" * 60)
        lines.append("PARALLEL EXECUTION WAVES:")
        lines.append("-" * 40)
        for i, wave in enumerate(self.waves, 1):
            wave_times = [self.build_times.get(n, 1.0) for n in wave]
            wave_max = max(wave_times) if wave_times else 0
            tasks_str = ", ".join(wave[:5])
            if len(wave) > 5:
                tasks_str += f"... (+{len(wave) - 5} more)"
            lines.append(f"  Wave {i}: [{len(wave)} tasks] {tasks_str}")
            lines.append(f"          Duration: {wave_max:.1f}h")

        # Critical Path
        lines.append("")
        lines.append("=" * 60)
        lines.append("CRITICAL PATH:")
        lines.append("-" * 40)
        lines.append(f"  Length: {self.critical_path_length:.1f}h")
        lines.append(f"  Path: {' -> '.join(self.critical_path)}")

        # Verbose: detailed breakdown
        if self.verbose:
            lines.append("")
            lines.append("  Detailed breakdown:")
            cumulative = 0.0
            for node in self.critical_path:
                duration = self.build_times.get(node, 1.0)
                cumulative += duration
                lines.append(f"    - {node}: {duration:.1f}h (cumulative: {cumulative:.1f}h)")

        # Summary Statistics
        lines.append("")
        lines.append("=" * 60)
        lines.append("SUMMARY:")
        lines.append("-" * 40)
        seq_time = self.get_sequential_time()
        par_time = self.get_parallel_time()
        savings = seq_time - par_time
        speedup_pct = (savings / seq_time * 100) if seq_time > 0 else 0

        lines.append(f"  Sequential execution: {seq_time:.1f}h")
        lines.append(f"  Parallel execution:   {par_time:.1f}h")
        lines.append(f"  Time saved:           {savings:.1f}h ({speedup_pct:.1f}% faster)")

        max_parallel = max(len(wave) for wave in self.waves) if self.waves else 0
        lines.append(f"  Max parallel workers: {max_parallel}")
        lines.append(f"  Total waves:          {len(self.waves)}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        seq_time = self.get_sequential_time()
        par_time = self.get_parallel_time()
        savings = seq_time - par_time
        speedup_pct = (savings / seq_time * 100) if seq_time > 0 else 0

        output = {
            "summary": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "total_waves": len(self.waves),
                "has_cycle": bool(self.errors and "Cycle" in str(self.errors))
            },
            "topological_order": self.topological_order,
            "waves": [
                {
                    "wave_number": i + 1,
                    "tasks": wave,
                    "task_count": len(wave),
                    "wave_duration": max(self.build_times.get(n, 1.0) for n in wave) if wave else 0,
                    "total_work": sum(self.build_times.get(n, 1.0) for n in wave)
                }
                for i, wave in enumerate(self.waves)
            ],
            "critical_path": {
                "nodes": self.critical_path,
                "length_hours": round(self.critical_path_length, 2),
                "node_durations": {n: self.build_times.get(n, 1.0) for n in self.critical_path}
            },
            "timing": {
                "sequential_hours": round(seq_time, 2),
                "parallel_hours": round(par_time, 2),
                "savings_hours": round(savings, 2),
                "speedup_percentage": round(speedup_pct, 1)
            },
            "resources": {
                "max_parallel_workers": max(len(w) for w in self.waves) if self.waves else 0,
                "avg_parallel_workers": round(
                    sum(len(w) for w in self.waves) / len(self.waves), 2
                ) if self.waves else 0
            },
            "errors": self.errors
        }

        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Compute topological order, parallel waves, and critical path for DAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Success
  1 - Cycle detected or invalid graph
  2 - File/parse error

Examples:
  %(prog)s graph.yaml                    # Basic topological sort
  %(prog)s .task/graph.yaml --verbose   # Detailed output
  %(prog)s graph.yaml --format=json      # JSON for automation
  %(prog)s graph.yaml --ssot-format      # SSOT Section 9 format
        """
    )

    parser.add_argument(
        "graph_file",
        help="Path to the dependency graph file (.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with detailed breakdowns"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--ssot-format",
        action="store_true",
        help="Output in SSOT Section 9 markdown format"
    )

    args = parser.parse_args()

    graph_path = Path(args.graph_file)
    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}", file=sys.stderr)
        sys.exit(2)

    # Run analysis
    sorter = TopologicalSorter(verbose=args.verbose)

    if not sorter.load_graph(graph_path):
        if args.format == "json":
            print(json.dumps({"error": sorter.errors, "status": "LOAD_ERROR"}, indent=2))
        else:
            print(f"Failed to load graph: {'; '.join(sorter.errors)}", file=sys.stderr)
        sys.exit(2)

    # Compute all analyses
    if not sorter.compute_topological_order():
        if args.format == "json":
            print(sorter.format_json_output())
        else:
            print(f"Cycle detected: {'; '.join(sorter.errors)}", file=sys.stderr)
        sys.exit(1)

    sorter.compute_parallel_waves()
    sorter.compute_critical_path()

    # Output results
    if args.ssot_format:
        print(sorter.format_ssot_section9())
    elif args.format == "json":
        print(sorter.format_json_output())
    else:
        print(sorter.format_text_output())

    sys.exit(0)

if __name__ == "__main__":
    main()
