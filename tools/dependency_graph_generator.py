#!/usr/bin/env python3
"""
dependency_graph_generator.py - the system Dependency Graph Generator

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Analysis Tool

Purpose:
    Generates dependency graphs for the system tasks, work orders,
    and system components. Supports multiple output formats.

Usage:
    python3 dependency_graph_generator.py --type tasks --output graph.dot
    python3 dependency_graph_generator.py --type work-orders --format json
    python3 dependency_graph_generator.py --type all --output deps.png
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class Node:
    """Represents a node in the dependency graph."""
    id: str
    label: str
    node_type: str
    status: str = "unknown"
    metadata: Dict = field(default_factory=dict)

@dataclass
class Edge:
    """Represents an edge (dependency) in the graph."""
    source: str
    target: str
    edge_type: str = "depends_on"
    metadata: Dict = field(default_factory=dict)

@dataclass
class DependencyGraph:
    """Dependency graph data structure."""
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        if not any(n.id == node.id for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all dependencies of a node."""
        return [e.target for e in self.edges if e.source == node_id]

    def get_dependents(self, node_id: str) -> List[str]:
        """Get all nodes that depend on this node."""
        return [e.source for e in self.edges if e.target == node_id]

    def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the dependency graph."""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for dep in self.get_dependencies(node_id):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])
                    return True

            path.pop()
            rec_stack.remove(node_id)
            return False

        for node in self.nodes:
            if node.id not in visited:
                dfs(node.id)

        return cycles

    def topological_sort(self) -> Optional[List[str]]:
        """Return topological order if no cycles exist."""
        if self.detect_cycles():
            return None

        in_degree = {n.id: 0 for n in self.nodes}
        for edge in self.edges:
            if edge.target in in_degree:
                in_degree[edge.target] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for edge in self.edges:
                if edge.source == node:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)

        return result if len(result) == len(self.nodes) else None

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "type": n.node_type,
                    "status": n.status,
                    "metadata": n.metadata
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.edge_type,
                    "metadata": e.metadata
                }
                for e in self.edges
            ]
        }

class DependencyGraphGenerator:
    """Generates dependency graphs for a system components."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.graph = DependencyGraph()

    def generate_task_graph(self) -> DependencyGraph:
        """Generate dependency graph for tasks."""
        self.graph = DependencyGraph()

        for task_dir in self.base_path.glob("task*"):
            if not task_dir.is_dir():
                continue

            task_id = task_dir.name
            manifest = task_dir / "task.yaml"

            status = "unknown"
            dependencies = []
            metadata = {}

            if manifest.exists() and HAS_YAML:
                try:
                    with open(manifest) as f:
                        data = yaml.safe_load(f) or {}
                    status = data.get("status", "unknown")
                    dependencies = data.get("dependencies", [])
                    metadata = {
                        "version": data.get("version", "0.0.0"),
                        "priority": data.get("priority", "medium"),
                        "owner": data.get("owner", "unknown")
                    }
                except Exception:
                    pass

            node = Node(
                id=task_id,
                label=task_id,
                node_type="task",
                status=status,
                metadata=metadata
            )
            self.graph.add_node(node)

            for dep in dependencies:
                dep_id = dep if isinstance(dep, str) else dep.get("task_id", str(dep))
                edge = Edge(
                    source=task_id,
                    target=dep_id,
                    edge_type="depends_on"
                )
                self.graph.add_edge(edge)

        return self.graph

    def generate_work_order_graph(self) -> DependencyGraph:
        """Generate dependency graph for work orders."""
        self.graph = DependencyGraph()

        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if not wo_queue.exists() or not HAS_YAML:
            return self.graph

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            for wo in data.get("work_orders", []):
                wo_id = wo.get("work_order_id", "unknown")
                node = Node(
                    id=wo_id,
                    label=wo.get("title", wo_id),
                    node_type="work_order",
                    status=wo.get("status", "unknown"),
                    metadata={
                        "priority": wo.get("priority", "medium"),
                        "agent": wo.get("agent", "unassigned"),
                        "task_id": wo.get("task_id")
                    }
                )
                self.graph.add_node(node)

                for dep in wo.get("dependencies", []):
                    dep_id = dep if isinstance(dep, str) else dep.get("work_order_id", str(dep))
                    edge = Edge(
                        source=wo_id,
                        target=dep_id,
                        edge_type="depends_on"
                    )
                    self.graph.add_edge(edge)

                # Add task relationship if exists
                task_id = wo.get("task_id")
                if task_id:
                    edge = Edge(
                        source=wo_id,
                        target=task_id,
                        edge_type="targets"
                    )
                    self.graph.add_edge(edge)

        except Exception:
            pass

        return self.graph

    def generate_agent_graph(self) -> DependencyGraph:
        """Generate agent interaction graph."""
        self.graph = DependencyGraph()

        agents = ["pm", "builder", "critic", "planner"]

        for agent in agents:
            node = Node(
                id=agent,
                label=agent.upper(),
                node_type="agent",
                status="active"
            )
            self.graph.add_node(node)

        # Standard agent workflow relationships
        relationships = [
            ("pm", "planner", "delegates_planning"),
            ("pm", "builder", "assigns_work"),
            ("builder", "critic", "requests_review"),
            ("critic", "pm", "reports_verdict"),
            ("planner", "pm", "provides_analysis"),
        ]

        for source, target, edge_type in relationships:
            edge = Edge(source=source, target=target, edge_type=edge_type)
            self.graph.add_edge(edge)

        return self.graph

    def generate_full_graph(self) -> DependencyGraph:
        """Generate complete system dependency graph."""
        self.graph = DependencyGraph()

        # Add all graphs
        task_graph = self.generate_task_graph()
        for node in task_graph.nodes:
            self.graph.add_node(node)
        for edge in task_graph.edges:
            self.graph.add_edge(edge)

        wo_graph = self.generate_work_order_graph()
        for node in wo_graph.nodes:
            self.graph.add_node(node)
        for edge in wo_graph.edges:
            self.graph.add_edge(edge)

        agent_graph = self.generate_agent_graph()
        for node in agent_graph.nodes:
            self.graph.add_node(node)
        for edge in agent_graph.edges:
            self.graph.add_edge(edge)

        return self.graph

    def to_dot(self, graph: DependencyGraph = None) -> str:
        """Export graph to DOT format (Graphviz)."""
        g = graph or self.graph

        lines = ["digraph System_Dependencies {"]
        lines.append("  rankdir=TB;")
        lines.append("  node [shape=box];")
        lines.append("")

        # Node styles by type
        type_styles = {
            "task": 'style=filled,fillcolor="#e1f5fe"',
            "work_order": 'style=filled,fillcolor="#fff3e0"',
            "agent": 'style=filled,fillcolor="#e8f5e9",shape=ellipse'
        }

        status_colors = {
            "active": "#4caf50",
            "completed": "#2196f3",
            "blocked": "#f44336",
            "pending": "#ff9800"
        }

        for node in g.nodes:
            style = type_styles.get(node.node_type, "")
            color = status_colors.get(node.status, "#9e9e9e")
            lines.append(f'  "{node.id}" [{style},color="{color}",label="{node.label}"];')

        lines.append("")

        edge_styles = {
            "depends_on": 'style=solid',
            "targets": 'style=dashed',
            "delegates_planning": 'style=dotted,color="#1976d2"',
            "assigns_work": 'style=solid,color="#388e3c"',
            "requests_review": 'style=solid,color="#f57c00"',
            "reports_verdict": 'style=solid,color="#7b1fa2"',
            "provides_analysis": 'style=dotted,color="#0097a7"'
        }

        for edge in g.edges:
            style = edge_styles.get(edge.edge_type, "")
            lines.append(f'  "{edge.source}" -> "{edge.target}" [{style},label="{edge.edge_type}"];')

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self, graph: DependencyGraph = None) -> str:
        """Export graph to Mermaid format."""
        g = graph or self.graph

        lines = ["graph TD"]

        for node in g.nodes:
            shape_start, shape_end = {
                "task": ("[", "]"),
                "work_order": ("(", ")"),
                "agent": ("((", "))")
            }.get(node.node_type, ("[", "]"))

            lines.append(f"  {node.id}{shape_start}{node.label}{shape_end}")

        for edge in g.edges:
            arrow = {
                "depends_on": "-->",
                "targets": "-.->",
                "delegates_planning": "-->",
                "assigns_work": "-->",
                "requests_review": "-->",
                "reports_verdict": "-->",
                "provides_analysis": "-->"
            }.get(edge.edge_type, "-->")

            lines.append(f"  {edge.source} {arrow}|{edge.edge_type}| {edge.target}")

        return "\n".join(lines)

    def analyze(self, graph: DependencyGraph = None) -> dict:
        """Analyze dependency graph for issues."""
        g = graph or self.graph

        cycles = g.detect_cycles()
        topo_order = g.topological_sort()

        # Find orphans (no dependencies and no dependents)
        orphans = []
        for node in g.nodes:
            deps = g.get_dependencies(node.id)
            dependents = g.get_dependents(node.id)
            if not deps and not dependents:
                orphans.append(node.id)

        # Find roots (no dependencies)
        roots = [n.id for n in g.nodes if not g.get_dependencies(n.id)]

        # Find leaves (no dependents)
        leaves = [n.id for n in g.nodes if not g.get_dependents(n.id)]

        # Calculate depths
        depths = {}
        if topo_order:
            for node_id in topo_order:
                deps = g.get_dependencies(node_id)
                if deps:
                    depths[node_id] = max(depths.get(d, 0) for d in deps) + 1
                else:
                    depths[node_id] = 0

        return {
            "node_count": len(g.nodes),
            "edge_count": len(g.edges),
            "has_cycles": len(cycles) > 0,
            "cycles": cycles,
            "topological_order": topo_order,
            "roots": roots,
            "leaves": leaves,
            "orphans": orphans,
            "max_depth": max(depths.values()) if depths else 0,
            "depths": depths
        }

def main():
    parser = argparse.ArgumentParser(description="the system Dependency Graph Generator")
    parser.add_argument("--type", choices=["tasks", "work-orders", "agents", "all"],
                        default="all", help="Graph type to generate")
    parser.add_argument("--format", choices=["json", "dot", "mermaid"],
                        default="json", help="Output format")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--analyze", action="store_true", help="Include analysis")
    parser.add_argument("--check-cycles", action="store_true", help="Check for cycles only")

    args = parser.parse_args()

    generator = DependencyGraphGenerator()

    # Generate appropriate graph
    if args.type == "tasks":
        graph = generator.generate_task_graph()
    elif args.type == "work-orders":
        graph = generator.generate_work_order_graph()
    elif args.type == "agents":
        graph = generator.generate_agent_graph()
    else:
        graph = generator.generate_full_graph()

    if args.check_cycles:
        cycles = graph.detect_cycles()
        if cycles:
            print(f"Found {len(cycles)} cycle(s):")
            for cycle in cycles:
                print(f"  {' -> '.join(cycle)}")
            return 1
        else:
            print("No cycles detected")
            return 0

    # Generate output
    if args.format == "dot":
        output = generator.to_dot(graph)
    elif args.format == "mermaid":
        output = generator.to_mermaid(graph)
    else:
        result = graph.to_dict()
        if args.analyze:
            result["analysis"] = generator.analyze(graph)
        output = json.dumps(result, indent=2)

    # Write or print output
    if args.output:
        Path(args.output).write_text(output)
        print(f"Graph written to {args.output}")
    else:
        print(output)

    return 0

if __name__ == "__main__":
    sys.exit(main())
