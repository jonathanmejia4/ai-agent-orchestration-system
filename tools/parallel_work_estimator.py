#!/usr/bin/env python3
"""
parallel_work_estimator.py - DAG parallel execution time estimator

Estimates time savings from parallel task execution vs sequential execution.
Calculates how many parallel Builder agents are needed for maximum speedup
and provides resource allocation recommendations.

Exit codes:
  0 - Analysis successful
  1 - Invalid graph or missing data

Usage:
  python tools/parallel_work_estimator.py graph.yaml
  python tools/parallel_work_estimator.py .task/graph.yaml --verbose
  python tools/parallel_work_estimator.py graph.yaml --format=json

Reference: PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

class ParallelWorkEstimator:
    """Estimates parallel vs sequential execution time for DAG."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str]] = []
        self.adjacency: dict[str, list[str]] = defaultdict(list)
        self.reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self.build_times: dict[str, float] = {}
        self.waves: list[list[str]] = []
        self.errors: list[str] = []

    def load_graph(self, graph_path: Path) -> bool:
        """Load and parse the graph file."""
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

            # Check for inline dependencies
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
        except Exception as e:
            self.errors.append(f"Error loading graph: {e}")
            return False

    def compute_parallel_waves(self) -> list[list[str]]:
        """
        Compute parallel waves using topological sort.
        Nodes in the same wave can be executed in parallel.
        """
        # Calculate in-degree for each node
        in_degree = {node: 0 for node in self.nodes}
        for source, target in self.edges:
            if target in in_degree:
                in_degree[target] += 1

        # Group nodes into waves
        waves = []
        remaining = set(self.nodes.keys())

        while remaining:
            # Find all nodes with in-degree 0 (can be executed now)
            wave = [n for n in remaining if in_degree[n] == 0]

            if not wave:
                # Cycle detected or error
                self.errors.append(f"Unable to compute waves - possible cycle. Remaining: {remaining}")
                break

            waves.append(wave)

            # Update in-degrees
            for node in wave:
                remaining.remove(node)
                for neighbor in self.adjacency.get(node, []):
                    if neighbor in in_degree:
                        in_degree[neighbor] -= 1

        self.waves = waves
        return waves

    def calculate_sequential_time(self) -> float:
        """Calculate total time if all tasks are executed sequentially."""
        return sum(self.build_times.values())

    def calculate_parallel_time(self) -> float:
        """Calculate total time with parallel execution (sum of wave max times)."""
        if not self.waves:
            self.compute_parallel_waves()

        total = 0
        for wave in self.waves:
            wave_max = max(self.build_times.get(n, 1.0) for n in wave) if wave else 0
            total += wave_max

        return total

    def get_wave_details(self) -> list[dict]:
        """Get detailed information about each wave."""
        if not self.waves:
            self.compute_parallel_waves()

        details = []
        for i, wave in enumerate(self.waves):
            wave_times = {n: self.build_times.get(n, 1.0) for n in wave}
            max_time = max(wave_times.values()) if wave_times else 0
            max_task = max(wave_times.keys(), key=lambda k: wave_times[k]) if wave_times else None

            details.append({
                "wave_number": i + 1,
                "tasks": wave,
                "task_count": len(wave),
                "task_times": wave_times,
                "wave_duration": max_time,
                "bottleneck_task": max_task,
                "total_work": sum(wave_times.values())
            })

        return details

    def get_resource_requirements(self) -> dict:
        """Analyze parallel resource requirements."""
        if not self.waves:
            self.compute_parallel_waves()

        task_counts = [len(wave) for wave in self.waves]
        max_parallel = max(task_counts) if task_counts else 0
        avg_parallel = sum(task_counts) / len(task_counts) if task_counts else 0

        # Find wave with max parallelism
        max_wave_idx = task_counts.index(max_parallel) + 1 if task_counts else 0

        return {
            "max_parallel_workers": max_parallel,
            "max_parallel_wave": max_wave_idx,
            "avg_parallel_workers": round(avg_parallel, 2),
            "total_waves": len(self.waves),
            "workers_per_wave": task_counts
        }

    def get_recommendations(self) -> list[str]:
        """Generate recommendations for parallel execution."""
        recommendations = []
        resources = self.get_resource_requirements()
        seq_time = self.calculate_sequential_time()
        par_time = self.calculate_parallel_time()

        max_workers = resources["max_parallel_workers"]
        avg_workers = resources["avg_parallel_workers"]

        # Optimal worker count recommendation
        if max_workers <= 2:
            recommendations.append(f"Low parallelism potential: Only {max_workers} workers needed at peak")
        elif max_workers <= 5:
            recommendations.append(f"Moderate parallelism: Provision {max_workers} Builder agents for optimal throughput")
        else:
            recommendations.append(f"High parallelism opportunity: Provision {max_workers} Builder agents for maximum speedup")

        # Average vs max worker analysis
        if avg_workers < max_workers * 0.5:
            recommendations.append(
                f"Consider elastic scaling: Avg workers ({avg_workers:.1f}) is significantly lower than peak ({max_workers})"
            )

        # Speedup analysis
        if seq_time > 0:
            speedup = (seq_time - par_time) / seq_time * 100
            if speedup > 50:
                recommendations.append(f"High ROI: Parallelization saves {speedup:.1f}% of execution time")
            elif speedup > 25:
                recommendations.append(f"Moderate ROI: Parallelization saves {speedup:.1f}% of execution time")
            else:
                recommendations.append(f"Limited parallelism benefit: Only {speedup:.1f}% time savings")

        # Wave analysis
        wave_details = self.get_wave_details()
        if wave_details:
            bottleneck_wave = max(wave_details, key=lambda w: w["wave_duration"])
            if bottleneck_wave["wave_duration"] > par_time * 0.3:
                bottleneck = bottleneck_wave["bottleneck_task"]
                recommendations.append(
                    f"Bottleneck: Wave {bottleneck_wave['wave_number']} ({bottleneck}) accounts for "
                    f"{bottleneck_wave['wave_duration']:.1f}h of {par_time:.1f}h total"
                )

        return recommendations

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []

        lines.append("=" * 60)
        lines.append("PARALLEL WORK ESTIMATION REPORT")
        lines.append("=" * 60)
        lines.append(f"Nodes: {len(self.nodes)}")
        lines.append(f"Edges: {len(self.edges)}")
        lines.append("")

        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
            return "\n".join(lines)

        # Time analysis
        seq_time = self.calculate_sequential_time()
        par_time = self.calculate_parallel_time()
        savings = seq_time - par_time
        speedup_pct = (savings / seq_time * 100) if seq_time > 0 else 0

        lines.append("TIME ANALYSIS:")
        lines.append("-" * 40)
        lines.append(f"  Sequential execution: {seq_time:.1f} hours")
        lines.append(f"  Parallel execution:   {par_time:.1f} hours")
        lines.append(f"  Time saved:           {savings:.1f} hours ({speedup_pct:.1f}% faster)")

        # Resource requirements
        lines.append("\n" + "=" * 60)
        lines.append("RESOURCE REQUIREMENTS:")
        lines.append("-" * 40)
        resources = self.get_resource_requirements()
        lines.append(f"  Max parallel workers: {resources['max_parallel_workers']} (Wave {resources['max_parallel_wave']})")
        lines.append(f"  Avg parallel workers: {resources['avg_parallel_workers']}")
        lines.append(f"  Total waves:          {resources['total_waves']}")

        # Wave breakdown
        if self.verbose:
            lines.append("\n" + "=" * 60)
            lines.append("WAVE BREAKDOWN:")
            lines.append("-" * 40)
            for wave in self.get_wave_details():
                lines.append(f"\n  Wave {wave['wave_number']}:")
                lines.append(f"    Tasks: {len(wave['tasks'])} ({', '.join(wave['tasks'][:5])}{'...' if len(wave['tasks']) > 5 else ''})")
                lines.append(f"    Duration: {wave['wave_duration']:.1f}h (bottleneck: {wave['bottleneck_task']})")
                lines.append(f"    Total work: {wave['total_work']:.1f}h")

        # Recommendations
        lines.append("\n" + "=" * 60)
        lines.append("RECOMMENDATIONS:")
        lines.append("-" * 40)
        for rec in self.get_recommendations():
            lines.append(f"  • {rec}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        seq_time = self.calculate_sequential_time()
        par_time = self.calculate_parallel_time()
        savings = seq_time - par_time
        speedup_pct = (savings / seq_time * 100) if seq_time > 0 else 0

        output = {
            "summary": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "total_waves": len(self.waves)
            },
            "time_analysis": {
                "sequential_hours": round(seq_time, 2),
                "parallel_hours": round(par_time, 2),
                "savings_hours": round(savings, 2),
                "speedup_percentage": round(speedup_pct, 1)
            },
            "resources": self.get_resource_requirements(),
            "waves": self.get_wave_details(),
            "recommendations": self.get_recommendations(),
            "errors": self.errors
        }

        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Estimate parallel vs sequential execution time for DAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Analysis successful
  1 - Invalid graph or missing data

Examples:
  %(prog)s graph.yaml              # Basic analysis
  %(prog)s .task/graph.yaml -v    # Verbose with wave breakdown
  %(prog)s graph.yaml --format=json # JSON for dashboards
        """
    )

    parser.add_argument(
        "graph_file",
        help="Path to the dependency graph file (.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with per-wave breakdown"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    graph_path = Path(args.graph_file)
    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    estimator = ParallelWorkEstimator(verbose=args.verbose)

    if not estimator.load_graph(graph_path):
        if args.format == "json":
            print(json.dumps({"error": estimator.errors, "status": "LOAD_ERROR"}, indent=2))
        else:
            print(f"❌ Failed to load graph: {'; '.join(estimator.errors)}", file=sys.stderr)
        sys.exit(1)

    estimator.compute_parallel_waves()

    # Output results
    if args.format == "json":
        print(estimator.format_json_output())
    else:
        print(estimator.format_text_output())

    # Exit code based on success
    if estimator.errors:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
