#!/usr/bin/env python3
"""
dag_validator.py - DAG integrity validation with 7 mechanical checks

Validates dependency graphs by running 7 mechanical checks:
1. Acyclic (No Cycles) - DFS cycle detection
2. Connected (All Nodes Reachable) - BFS from root(s)
3. No Orphans - Nodes with no edges
4. No Duplicate Edges - Duplicate dependency declarations
5. No Self-Loops - Tasks depending on themselves
6. Node-Edge Correspondence - Edge endpoints exist as nodes
7. Stage Consistency - Dependencies across stages

Exit codes:
  0 - All checks pass (valid DAG)
  1 - One or more checks fail (invalid DAG)
  2 - Graph file parsing error

Usage:
  python tools/dag_validator.py graph.yaml
  python tools/dag_validator.py .task/graph.yaml --verbose
  python tools/dag_validator.py .task/graph.yaml --format=json

Reference: PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md
"""

import argparse
import json
import sys
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

class CheckStatus(Enum):
    """Status for individual checks."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

class DAGValidator:
    """Validates DAG integrity with 7 mechanical checks."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str]] = []
        self.adjacency: dict[str, list[str]] = defaultdict(list)
        self.reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self.stages: dict[str, int] = {}
        self.check_results: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def load_graph(self, graph_path: Path) -> bool:
        """Load and parse the graph file."""
        try:
            with open(graph_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                self.errors.append("Empty graph file")
                return False

            # Support nested graph structure (graph.nodes, graph.edges) as well as root-level
            # Issue Q-19: .task/graph.yaml uses nested structure, so check both locations
            graph_container = data.get("graph", {})

            # Parse nodes - check nested graph.nodes first, then root-level nodes/tasks
            nodes_data = graph_container.get("nodes", data.get("nodes", data.get("tasks", [])))
            if isinstance(nodes_data, list):
                for node in nodes_data:
                    if isinstance(node, dict):
                        node_id = node.get("id", node.get("task_id", node.get("name")))
                        if node_id:
                            self.nodes[str(node_id)] = node
                            if "stage" in node:
                                self.stages[str(node_id)] = int(node["stage"])
                    elif isinstance(node, str):
                        self.nodes[node] = {"id": node}
            elif isinstance(nodes_data, dict):
                for node_id, node_data in nodes_data.items():
                    self.nodes[str(node_id)] = node_data if isinstance(node_data, dict) else {"id": node_id}
                    if isinstance(node_data, dict) and "stage" in node_data:
                        self.stages[str(node_id)] = int(node_data["stage"])

            # Parse edges - check nested graph.edges first, then root-level edges/dependencies
            edges_data = graph_container.get("edges", data.get("edges", data.get("dependencies", [])))
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

            # Also check for inline dependencies in nodes
            for node_id, node_data in self.nodes.items():
                if isinstance(node_data, dict):
                    deps = node_data.get("dependencies", node_data.get("depends_on", []))
                    if isinstance(deps, list):
                        for dep in deps:
                            dep_id = str(dep)
                            edge = (dep_id, node_id)  # dependency points TO this node
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

    def check_acyclic(self) -> dict[str, Any]:
        """Check 1: Detect cycles using DFS (Acyclic check)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self.nodes}
        cycles = []
        path = []

        def dfs(node: str) -> bool:
            color[node] = GRAY
            path.append(node)

            for neighbor in self.adjacency.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    # Found cycle - extract it
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                    return True
                elif color[neighbor] == WHITE:
                    if dfs(neighbor):
                        return True

            path.pop()
            color[node] = BLACK
            return False

        for node in self.nodes:
            if color[node] == WHITE:
                dfs(node)

        result = {
            "check": "Acyclic (No Cycles)",
            "check_id": 1,
            "status": CheckStatus.PASS if not cycles else CheckStatus.FAIL,
        }

        if cycles:
            result["message"] = f"Found {len(cycles)} cycle(s)"
            result["details"] = [" → ".join(cycle) for cycle in cycles]
        else:
            result["message"] = "No cycles detected"

        return result

    def check_connected(self) -> dict[str, Any]:
        """Check 2: Verify all nodes are reachable from root(s)."""
        if not self.nodes:
            return {
                "check": "Connected (All Nodes Reachable)",
                "check_id": 2,
                "status": CheckStatus.PASS,
                "message": "No nodes to check"
            }

        # Find root nodes (nodes with no incoming edges)
        roots = [n for n in self.nodes if n not in self.reverse_adjacency or not self.reverse_adjacency[n]]

        if not roots:
            # If no explicit roots, use all nodes as potential starting points
            roots = list(self.nodes.keys())

        # BFS from all roots
        reachable = set()
        queue = list(roots)
        while queue:
            node = queue.pop(0)
            if node in reachable:
                continue
            reachable.add(node)
            for neighbor in self.adjacency.get(node, []):
                if neighbor not in reachable and neighbor in self.nodes:
                    queue.append(neighbor)

        unreachable = set(self.nodes.keys()) - reachable

        result = {
            "check": "Connected (All Nodes Reachable)",
            "check_id": 2,
            "status": CheckStatus.PASS if not unreachable else CheckStatus.WARN,
        }

        if unreachable:
            result["message"] = f"Found {len(unreachable)} unreachable node(s)"
            result["details"] = list(unreachable)
        else:
            result["message"] = f"All {len(self.nodes)} nodes are reachable"

        return result

    def check_no_orphans(self) -> dict[str, Any]:
        """Check 3: Detect orphan nodes (no incoming or outgoing edges)."""
        orphans = []

        for node in self.nodes:
            has_outgoing = node in self.adjacency and self.adjacency[node]
            has_incoming = node in self.reverse_adjacency and self.reverse_adjacency[node]

            if not has_outgoing and not has_incoming:
                orphans.append(node)

        # Single node graph is not an orphan if it's the only node
        if len(self.nodes) == 1 and len(orphans) == 1:
            orphans = []

        result = {
            "check": "No Orphans",
            "check_id": 3,
            "status": CheckStatus.PASS if not orphans else CheckStatus.WARN,
        }

        if orphans:
            result["message"] = f"Found {len(orphans)} orphan node(s) with no edges"
            result["details"] = orphans
        else:
            result["message"] = "No orphan nodes found"

        return result

    def check_no_duplicate_edges(self) -> dict[str, Any]:
        """Check 4: Identify duplicate dependency declarations."""
        edge_counts: dict[tuple, int] = defaultdict(int)
        for edge in self.edges:
            edge_counts[edge] += 1

        duplicates = [(edge, count) for edge, count in edge_counts.items() if count > 1]

        result = {
            "check": "No Duplicate Edges",
            "check_id": 4,
            "status": CheckStatus.PASS if not duplicates else CheckStatus.FAIL,
        }

        if duplicates:
            result["message"] = f"Found {len(duplicates)} duplicate edge(s)"
            result["details"] = [f"{e[0]} → {e[1]} (declared {c} times)" for e, c in duplicates]
        else:
            result["message"] = f"No duplicate edges among {len(self.edges)} total edges"

        return result

    def check_no_self_loops(self) -> dict[str, Any]:
        """Check 5: Detect tasks that depend on themselves."""
        self_loops = [edge for edge in self.edges if edge[0] == edge[1]]

        result = {
            "check": "No Self-Loops",
            "check_id": 5,
            "status": CheckStatus.PASS if not self_loops else CheckStatus.FAIL,
        }

        if self_loops:
            result["message"] = f"Found {len(self_loops)} self-loop(s)"
            result["details"] = [f"{e[0]} → {e[1]}" for e in self_loops]
        else:
            result["message"] = "No self-loops detected"

        return result

    def check_node_edge_correspondence(self) -> dict[str, Any]:
        """Check 6: Verify all edge endpoints exist as nodes."""
        missing_nodes = set()

        for source, target in self.edges:
            if source not in self.nodes:
                missing_nodes.add(f"Source '{source}' (in edge {source} → {target})")
            if target not in self.nodes:
                missing_nodes.add(f"Target '{target}' (in edge {source} → {target})")

        result = {
            "check": "Node-Edge Correspondence",
            "check_id": 6,
            "status": CheckStatus.PASS if not missing_nodes else CheckStatus.FAIL,
        }

        if missing_nodes:
            result["message"] = f"Found {len(missing_nodes)} edge endpoint(s) without corresponding node"
            result["details"] = list(missing_nodes)
        else:
            result["message"] = "All edge endpoints correspond to existing nodes"

        return result

    def check_stage_consistency(self) -> dict[str, Any]:
        """Check 7: Warn if a task depends on a later-stage task."""
        inconsistencies = []

        for source, target in self.edges:
            source_stage = self.stages.get(source)
            target_stage = self.stages.get(target)

            if source_stage is not None and target_stage is not None:
                # Edge goes from source to target
                # If source is in a later stage than target, that's unusual
                # (typically dependencies flow from earlier to later stages)
                if source_stage > target_stage:
                    inconsistencies.append({
                        "edge": f"{source} → {target}",
                        "issue": f"Stage {source_stage} depends on stage {target_stage}",
                        "source_stage": source_stage,
                        "target_stage": target_stage
                    })

        result = {
            "check": "Stage Consistency",
            "check_id": 7,
            "status": CheckStatus.PASS if not inconsistencies else CheckStatus.WARN,
        }

        if not self.stages:
            result["message"] = "No stage information available (skipped)"
            result["status"] = CheckStatus.PASS
        elif inconsistencies:
            result["message"] = f"Found {len(inconsistencies)} unusual cross-stage dependency pattern(s)"
            result["details"] = [f"{i['edge']}: {i['issue']}" for i in inconsistencies]
        else:
            result["message"] = "Stage dependencies are consistent"

        return result

    def run_all_checks(self) -> list[dict[str, Any]]:
        """Run all 7 mechanical checks."""
        self.check_results = [
            self.check_acyclic(),
            self.check_connected(),
            self.check_no_orphans(),
            self.check_no_duplicate_edges(),
            self.check_no_self_loops(),
            self.check_node_edge_correspondence(),
            self.check_stage_consistency(),
        ]
        return self.check_results

    def get_overall_status(self) -> tuple[str, int]:
        """Get overall validation status and exit code."""
        has_failures = any(r["status"] == CheckStatus.FAIL for r in self.check_results)
        has_warnings = any(r["status"] == CheckStatus.WARN for r in self.check_results)

        if has_failures:
            return "INVALID", 1
        elif has_warnings:
            return "VALID (with warnings)", 0
        else:
            return "VALID", 0

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []

        lines.append("=" * 60)
        lines.append("DAG VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append(f"Nodes: {len(self.nodes)}")
        lines.append(f"Edges: {len(self.edges)}")
        lines.append("")

        if self.errors:
            lines.append("⚠️  PARSE ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
            lines.append("")

        lines.append("7 MECHANICAL CHECKS:")
        lines.append("-" * 40)

        for result in self.check_results:
            status = result["status"]
            if status == CheckStatus.PASS:
                icon = "✅"
            elif status == CheckStatus.WARN:
                icon = "⚠️"
            else:
                icon = "❌"

            lines.append(f"\n{icon} Check {result['check_id']}: {result['check']}")
            lines.append(f"   Status: {status.value.upper()}")
            lines.append(f"   {result['message']}")

            if self.verbose and "details" in result:
                lines.append("   Details:")
                for detail in result["details"][:10]:  # Limit to 10 items
                    lines.append(f"     - {detail}")
                if len(result.get("details", [])) > 10:
                    lines.append(f"     ... and {len(result['details']) - 10} more")

        # Overall status
        overall_status, _ = self.get_overall_status()
        lines.append("\n" + "=" * 60)

        if overall_status == "VALID":
            lines.append("✅ OVERALL: VALID - All checks passed")
        elif overall_status == "VALID (with warnings)":
            lines.append("⚠️  OVERALL: VALID (with warnings)")
        else:
            lines.append("❌ OVERALL: INVALID - One or more checks failed")

        lines.append("=" * 60)

        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        overall_status, exit_code = self.get_overall_status()

        # Convert CheckStatus enums to strings
        results_serializable = []
        for r in self.check_results:
            r_copy = dict(r)
            r_copy["status"] = r["status"].value
            results_serializable.append(r_copy)

        output = {
            "summary": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "overall_status": overall_status,
                "exit_code": exit_code,
                "checks_passed": sum(1 for r in self.check_results if r["status"] == CheckStatus.PASS),
                "checks_warned": sum(1 for r in self.check_results if r["status"] == CheckStatus.WARN),
                "checks_failed": sum(1 for r in self.check_results if r["status"] == CheckStatus.FAIL),
            },
            "checks": results_serializable,
            "errors": self.errors
        }

        return json.dumps(output, indent=2)

    def write_validation_to_graph(self, graph_path: Path) -> bool:
        """Write validation results back to the graph file."""
        try:
            with open(graph_path, 'r') as f:
                data = yaml.safe_load(f) or {}

            overall_status, _ = self.get_overall_status()

            # Add/update validation section
            data["validation"] = {
                "status": overall_status,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "checks": {
                    f"check_{r['check_id']}": {
                        "name": r["check"],
                        "status": r["status"].value,
                        "message": r["message"]
                    }
                    for r in self.check_results
                }
            }

            with open(graph_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            return True
        except Exception as e:
            self.errors.append(f"Failed to write validation results: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Validate DAG integrity with 7 mechanical checks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
7 Mechanical Checks:
  1. Acyclic (No Cycles)         - DFS cycle detection
  2. Connected (All Reachable)   - BFS from root(s)
  3. No Orphans                  - Nodes with no edges
  4. No Duplicate Edges          - Duplicate declarations
  5. No Self-Loops               - Self-dependencies
  6. Node-Edge Correspondence    - Edge endpoints exist
  7. Stage Consistency           - Cross-stage patterns

Exit codes:
  0 - All checks pass (valid DAG)
  1 - One or more checks fail (invalid DAG)
  2 - Graph file parsing error

Examples:
  %(prog)s graph.yaml              # Basic validation
  %(prog)s .task/graph.yaml -v    # Verbose output
  %(prog)s graph.yaml --format=json # JSON for CI/CD
  %(prog)s graph.yaml --write      # Write results to graph
        """
    )

    parser.add_argument(
        "graph_file",
        help="Path to the dependency graph file (.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with full details"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--write", "-w",
        action="store_true",
        help="Write validation results back to graph file"
    )

    args = parser.parse_args()

    graph_path = Path(args.graph_file)
    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}", file=sys.stderr)
        sys.exit(2)

    # Run validation
    validator = DAGValidator(verbose=args.verbose)

    if not validator.load_graph(graph_path):
        if args.format == "json":
            print(json.dumps({"error": validator.errors, "status": "PARSE_ERROR"}, indent=2))
        else:
            print(f"❌ Failed to load graph: {'; '.join(validator.errors)}", file=sys.stderr)
        sys.exit(2)

    validator.run_all_checks()

    # Write results if requested
    if args.write:
        validator.write_validation_to_graph(graph_path)

    # Output results
    if args.format == "json":
        print(validator.format_json_output())
    else:
        print(validator.format_text_output())

    # Exit with appropriate code
    _, exit_code = validator.get_overall_status()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
