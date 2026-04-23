#!/usr/bin/env python3
"""
DAG Cycle Detection Tool

Detects and reports all cycles in dependency graphs, essential for
identifying circular dependencies that would prevent successful task execution.

Usage:
    python3 tools/find_cycles.py .task/deps.yaml
    python3 tools/find_cycles.py --graph deps.yaml --format json
    python3 tools/find_cycles.py --graph deps.yaml --verbose
    python3 tools/find_cycles.py --help

Exit Codes:
    0 - No cycles found (DAG is acyclic)
    1 - Cycles found (DAG is not acyclic)
    2 - Invalid graph file or parse error

Referenced in:
    - PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md:485, 1141, 1147, 1365, 1390, 1483
    - .claude/guidelines/README.md:844

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# Optional YAML support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class NodeColor(Enum):
    """DFS node coloring for cycle detection"""
    WHITE = "unvisited"    # Not yet visited
    GRAY = "in_progress"   # Currently in DFS path (being processed)
    BLACK = "completed"    # Fully processed

@dataclass
class Cycle:
    """Represents a detected cycle"""
    path: List[str]  # Node IDs forming the cycle

    def __str__(self) -> str:
        if not self.path:
            return "(empty cycle)"
        return " → ".join(self.path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'length': len(self.path),
            'display': str(self)
        }

@dataclass
class CycleDetectionResult:
    """Result of cycle detection"""
    has_cycles: bool = False
    cycles: List[Cycle] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'has_cycles': self.has_cycles,
            'cycle_count': len(self.cycles),
            'cycles': [c.to_dict() for c in self.cycles],
            'node_count': self.node_count,
            'edge_count': self.edge_count,
            'errors': self.errors
        }

class CycleDetector:
    """Detects cycles in directed graphs using DFS"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.graph: Dict[str, List[str]] = {}
        self.color: Dict[str, NodeColor] = {}
        self.parent: Dict[str, Optional[str]] = {}
        self.cycles: List[Cycle] = []

    def log(self, message: str):
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def parse_graph(self, graph_file: Path) -> Optional[Dict[str, List[str]]]:
        """Parse dependency graph from YAML/JSON file"""
        if not graph_file.exists():
            return None

        try:
            content = graph_file.read_text()

            if graph_file.suffix in ('.yaml', '.yml'):
                if not HAS_YAML:
                    self.log("PyYAML not installed, trying JSON parse")
                    data = json.loads(content)
                else:
                    data = yaml.safe_load(content)
            else:
                data = json.loads(content)

            # Extract graph structure
            # Supports multiple formats:
            # 1. { "nodes": [...], "edges": [...] }
            # 2. { "node_id": ["dep1", "dep2"], ... }
            # 3. { "dependencies": { "node_id": ["dep1", "dep2"], ... } }

            graph: Dict[str, List[str]] = {}

            if 'nodes' in data and 'edges' in data:
                # Format 1: nodes and edges
                for node in data['nodes']:
                    node_id = node if isinstance(node, str) else node.get('id', str(node))
                    graph[node_id] = []

                for edge in data['edges']:
                    if isinstance(edge, dict):
                        src = edge.get('from') or edge.get('source')
                        dst = edge.get('to') or edge.get('target')
                    elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
                        src, dst = edge[0], edge[1]
                    else:
                        continue

                    if src and dst:
                        if src not in graph:
                            graph[src] = []
                        graph[src].append(dst)
                        if dst not in graph:
                            graph[dst] = []

            elif 'dependencies' in data:
                # Format 3: dependencies dict
                graph = data['dependencies']

            else:
                # Format 2: direct adjacency list
                graph = data

            # Ensure all referenced nodes exist
            all_nodes = set(graph.keys())
            for deps in graph.values():
                for dep in deps:
                    if dep not in graph:
                        graph[dep] = []
                    all_nodes.add(dep)

            return graph

        except Exception as e:
            self.log(f"Error parsing graph: {e}")
            return None

    def find_cycles(self, graph: Dict[str, List[str]]) -> CycleDetectionResult:
        """Find all cycles in the graph using DFS"""
        result = CycleDetectionResult()
        self.graph = graph
        self.cycles = []

        # Initialize all nodes as WHITE (unvisited)
        self.color = {node: NodeColor.WHITE for node in graph}
        self.parent = {node: None for node in graph}

        result.node_count = len(graph)
        result.edge_count = sum(len(deps) for deps in graph.values())

        self.log(f"Graph has {result.node_count} nodes and {result.edge_count} edges")

        # Run DFS from each unvisited node
        for node in graph:
            if self.color[node] == NodeColor.WHITE:
                self._dfs(node, [])

        result.cycles = self.cycles
        result.has_cycles = len(self.cycles) > 0

        return result

    def _dfs(self, node: str, path: List[str]):
        """DFS traversal with cycle detection"""
        self.color[node] = NodeColor.GRAY
        current_path = path + [node]
        self.log(f"Visiting {node} (path: {' → '.join(current_path)})")

        for neighbor in self.graph.get(node, []):
            if self.color[neighbor] == NodeColor.GRAY:
                # Found a back edge - cycle detected!
                # Build the cycle path
                cycle_start_idx = current_path.index(neighbor)
                cycle_path = current_path[cycle_start_idx:] + [neighbor]
                cycle = Cycle(path=cycle_path)
                self.log(f"Cycle detected: {cycle}")
                self.cycles.append(cycle)

            elif self.color[neighbor] == NodeColor.WHITE:
                self.parent[neighbor] = node
                self._dfs(neighbor, current_path)

        self.color[node] = NodeColor.BLACK

def print_result(result: CycleDetectionResult, format: str = "text"):
    """Print cycle detection result"""
    if format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return

    if result.errors:
        for error in result.errors:
            print(f"\033[91mError: {error}\033[0m")
        return

    print(f"\nGraph: {result.node_count} nodes, {result.edge_count} edges")
    print()

    if not result.has_cycles:
        print(f"\033[92m✅ No cycles found - DAG is acyclic\033[0m")
    else:
        print(f"\033[91m❌ Cycles detected!\033[0m")
        print()
        print(f"Total cycles found: {len(result.cycles)}")
        print()

        for i, cycle in enumerate(result.cycles, 1):
            print(f"  Cycle {i}: {cycle}")

        print()
        print("\033[93mAction required:\033[0m Remove one edge from each cycle to break it.")
        print("  Tip: Look for the least critical dependency in each cycle.")

def main():
    parser = argparse.ArgumentParser(
        description='Detect cycles in dependency graphs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check a dependency graph file
    %(prog)s .task/deps.yaml

    # JSON output for CI/CD
    %(prog)s --graph deps.yaml --format json

    # Verbose mode for debugging
    %(prog)s --graph deps.yaml --verbose

Graph file formats supported:
    1. { "nodes": ["A", "B"], "edges": [{"from": "A", "to": "B"}] }
    2. { "A": ["B", "C"], "B": ["C"] }  (adjacency list)
    3. { "dependencies": { "A": ["B"], "B": ["C"] } }

Exit Codes:
    0 - No cycles found (DAG is acyclic)
    1 - Cycles found (DAG is not acyclic)
    2 - Invalid graph file or parse error
        """
    )

    parser.add_argument('graph_file', nargs='?', type=Path,
                       help='Dependency graph file (.yaml, .yml, .json)')
    parser.add_argument('--graph', '-g', type=Path,
                       help='Dependency graph file (alternative to positional)')
    parser.add_argument('--format', '-f', choices=['text', 'json'], default='text',
                       help='Output format')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output with DFS trace')

    args = parser.parse_args()

    # Get graph file path
    graph_file = args.graph_file or args.graph
    if not graph_file:
        parser.print_help()
        sys.exit(2)

    # Initialize detector
    detector = CycleDetector(verbose=args.verbose)

    # Parse graph
    graph = detector.parse_graph(graph_file)
    if graph is None:
        result = CycleDetectionResult(errors=[f"Cannot parse graph file: {graph_file}"])
        print_result(result, args.format)
        sys.exit(2)

    # Find cycles
    result = detector.find_cycles(graph)
    print_result(result, args.format)

    # Exit code
    if result.errors:
        sys.exit(2)
    elif result.has_cycles:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
