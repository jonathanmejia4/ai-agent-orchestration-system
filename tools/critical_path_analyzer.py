#!/usr/bin/env python3
"""
critical_path_analyzer.py - DAG critical path and bottleneck analyzer

Identifies bottleneck tasks on the critical path, calculates the critical
path (longest path through dependency graph), and performs bottleneck analysis
showing which tasks contribute most to total build time.

Exit codes:
  0 - Analysis successful
  1 - Invalid graph or missing data
  2 - File parsing error

Usage:
  python tools/critical_path_analyzer.py graph.yaml
  python tools/critical_path_analyzer.py .task/graph.yaml --verbose
  python tools/critical_path_analyzer.py graph.yaml --format=json

Reference: PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

class CriticalPathAnalyzer:
    """Analyzes DAG critical path and identifies bottlenecks."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str]] = []
        self.adjacency: dict[str, list[str]] = defaultdict(list)
        self.reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self.build_times: dict[str, float] = {}
        self.critical_path: list[str] = []
        self.critical_path_duration: float = 0
        self.bottlenecks: list[dict] = []
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
                            # Extract build time (default to 1.0 if not specified)
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

            # Also check for inline dependencies
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

    def find_root_nodes(self) -> list[str]:
        """Find nodes with no incoming edges (entry points)."""
        return [n for n in self.nodes if n not in self.reverse_adjacency or not self.reverse_adjacency[n]]

    def find_leaf_nodes(self) -> list[str]:
        """Find nodes with no outgoing edges (exit points)."""
        return [n for n in self.nodes if n not in self.adjacency or not self.adjacency[n]]

    def calculate_critical_path(self) -> list[str]:
        """
        Calculate the critical path using longest path algorithm.
        Returns the path that takes the most time from roots to leaves.
        """
        # Use dynamic programming to find longest path
        # dist[node] = (longest distance to reach node, predecessor)
        dist: dict[str, tuple[float, str | None]] = {}

        # Topological sort using Kahn's algorithm
        in_degree = defaultdict(int)
        for node in self.nodes:
            in_degree[node] = len(self.reverse_adjacency.get(node, []))

        # Initialize distances for root nodes
        queue = []
        for node in self.nodes:
            if in_degree[node] == 0:
                dist[node] = (self.build_times.get(node, 1.0), None)
                queue.append(node)

        # Process in topological order
        topo_order = []
        while queue:
            node = queue.pop(0)
            topo_order.append(node)

            for neighbor in self.adjacency.get(node, []):
                in_degree[neighbor] -= 1

                # Update distance if this path is longer
                new_dist = dist[node][0] + self.build_times.get(neighbor, 1.0)
                if neighbor not in dist or new_dist > dist[neighbor][0]:
                    dist[neighbor] = (new_dist, node)

                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if not dist:
            return []

        # Find the node with maximum distance (end of critical path)
        max_node = max(dist.keys(), key=lambda n: dist[n][0])
        self.critical_path_duration = dist[max_node][0]

        # Reconstruct path
        path = []
        current = max_node
        while current is not None:
            path.append(current)
            current = dist[current][1]

        path.reverse()
        self.critical_path = path
        return path

    def analyze_bottlenecks(self) -> list[dict]:
        """Analyze which tasks on critical path contribute most to duration."""
        if not self.critical_path:
            return []

        bottlenecks = []
        for node in self.critical_path:
            build_time = self.build_times.get(node, 1.0)
            percentage = (build_time / self.critical_path_duration * 100) if self.critical_path_duration > 0 else 0

            node_data = self.nodes.get(node, {})
            name = node_data.get("name", node_data.get("title", node)) if isinstance(node_data, dict) else node

            bottlenecks.append({
                "node_id": node,
                "name": name,
                "build_time": build_time,
                "percentage": round(percentage, 1),
                "is_major_bottleneck": percentage >= 20
            })

        # Sort by percentage contribution (highest first)
        bottlenecks.sort(key=lambda x: x["percentage"], reverse=True)
        self.bottlenecks = bottlenecks
        return bottlenecks

    def get_optimization_recommendations(self) -> list[str]:
        """Generate optimization recommendations based on bottleneck analysis."""
        recommendations = []

        if not self.bottlenecks:
            return ["No bottlenecks identified - graph may be empty or disconnected"]

        # Top bottleneck recommendation
        top = self.bottlenecks[0]
        recommendations.append(
            f"Priority 1: Optimize '{top['name']}' ({top['build_time']:.1f} hours, "
            f"{top['percentage']:.1f}% of critical path)"
        )

        # Additional major bottlenecks
        major = [b for b in self.bottlenecks[1:] if b["is_major_bottleneck"]]
        for i, b in enumerate(major[:2], 2):
            recommendations.append(
                f"Priority {i}: Optimize '{b['name']}' ({b['build_time']:.1f} hours, "
                f"{b['percentage']:.1f}% of critical path)"
            )

        # General recommendations
        if len(self.critical_path) > 5:
            recommendations.append(
                f"Consider parallelizing: Critical path has {len(self.critical_path)} sequential steps"
            )

        if self.critical_path_duration > 10:
            recommendations.append(
                f"Total critical path duration ({self.critical_path_duration:.1f} hours) suggests "
                "breaking down large tasks"
            )

        return recommendations

    def find_all_critical_paths(self) -> list[list[str]]:
        """Find all paths with duration equal to the critical path."""
        if not self.critical_path:
            return []

        all_paths = []
        target_duration = self.critical_path_duration
        tolerance = 0.01  # Allow small floating point differences

        def dfs_paths(node: str, current_path: list[str], current_duration: float):
            current_path = current_path + [node]
            current_duration += self.build_times.get(node, 1.0)

            neighbors = self.adjacency.get(node, [])
            if not neighbors:  # Leaf node
                if abs(current_duration - target_duration) <= tolerance:
                    all_paths.append(current_path)
            else:
                for neighbor in neighbors:
                    dfs_paths(neighbor, current_path, current_duration)

        # Start from all root nodes
        for root in self.find_root_nodes():
            dfs_paths(root, [], 0)

        return all_paths

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []

        lines.append("=" * 60)
        lines.append("CRITICAL PATH ANALYSIS REPORT")
        lines.append("=" * 60)
        lines.append(f"Nodes: {len(self.nodes)}")
        lines.append(f"Edges: {len(self.edges)}")
        lines.append("")

        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
            return "\n".join(lines)

        # Critical Path
        lines.append("CRITICAL PATH:")
        lines.append("-" * 40)
        if self.critical_path:
            path_str = " → ".join(self.critical_path)
            lines.append(f"  {path_str}")
            lines.append(f"\n  Total Duration: {self.critical_path_duration:.1f} hours")
            lines.append(f"  Steps: {len(self.critical_path)}")
        else:
            lines.append("  No critical path found (graph may be empty or disconnected)")

        # Bottleneck Analysis
        lines.append("\n" + "=" * 60)
        lines.append("BOTTLENECK ANALYSIS")
        lines.append("-" * 40)

        if self.bottlenecks:
            for b in self.bottlenecks:
                marker = "🔴" if b["is_major_bottleneck"] else "  "
                lines.append(
                    f"{marker} {b['name']}: {b['build_time']:.1f} hours "
                    f"({b['percentage']:.1f}% of critical path)"
                )
        else:
            lines.append("  No bottlenecks identified")

        # Recommendations
        lines.append("\n" + "=" * 60)
        lines.append("OPTIMIZATION RECOMMENDATIONS")
        lines.append("-" * 40)

        recommendations = self.get_optimization_recommendations()
        for rec in recommendations:
            lines.append(f"  • {rec}")

        # Alternative critical paths (if verbose)
        if self.verbose:
            all_paths = self.find_all_critical_paths()
            if len(all_paths) > 1:
                lines.append("\n" + "=" * 60)
                lines.append(f"ALTERNATIVE CRITICAL PATHS ({len(all_paths)} total)")
                lines.append("-" * 40)
                for i, path in enumerate(all_paths[:5], 1):
                    lines.append(f"  Path {i}: " + " → ".join(path))
                if len(all_paths) > 5:
                    lines.append(f"  ... and {len(all_paths) - 5} more paths")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        output = {
            "summary": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "critical_path_duration": self.critical_path_duration,
                "critical_path_length": len(self.critical_path),
                "major_bottlenecks": sum(1 for b in self.bottlenecks if b["is_major_bottleneck"])
            },
            "critical_path": {
                "nodes": self.critical_path,
                "duration": self.critical_path_duration,
                "formatted": " → ".join(self.critical_path) if self.critical_path else ""
            },
            "bottlenecks": self.bottlenecks,
            "recommendations": self.get_optimization_recommendations(),
            "errors": self.errors
        }

        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze DAG critical path and identify bottlenecks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Analysis successful
  1 - Invalid graph or missing data
  2 - File parsing error

Examples:
  %(prog)s graph.yaml              # Basic analysis
  %(prog)s .task/graph.yaml -v    # Verbose with alternative paths
  %(prog)s graph.yaml --format=json # JSON output for CI/CD
        """
    )

    parser.add_argument(
        "graph_file",
        help="Path to the dependency graph file (.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with alternative paths"
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
        sys.exit(2)

    # Run analysis
    analyzer = CriticalPathAnalyzer(verbose=args.verbose)

    if not analyzer.load_graph(graph_path):
        if args.format == "json":
            print(json.dumps({"error": analyzer.errors, "status": "PARSE_ERROR"}, indent=2))
        else:
            print(f"❌ Failed to load graph: {'; '.join(analyzer.errors)}", file=sys.stderr)
        sys.exit(2)

    analyzer.calculate_critical_path()
    analyzer.analyze_bottlenecks()

    # Output results
    if args.format == "json":
        print(analyzer.format_json_output())
    else:
        print(analyzer.format_text_output())

    # Exit code based on success
    if analyzer.errors:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
