#!/usr/bin/env python3
"""
the system Dependency Analyzer Tool

Analyzes dependencies between a system components, builds a dependency graph,
and provides tools for impact analysis and cycle detection.

Version: 1.0.0
Created: 2025-12-25
Author: Builder Agent
"""

import os
import re
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict

@dataclass
class Node:
    """A node in the dependency graph."""
    id: str
    path: str
    type: str  # module, task, template, tool, config
    name: str
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)

@dataclass
class Edge:
    """An edge in the dependency graph."""
    source: str
    target: str
    type: str  # imports, uses, extends, references
    line: Optional[int] = None

@dataclass
class DependencyGraph:
    """Complete dependency graph."""
    timestamp: str
    root_path: str
    nodes: List[Node]
    edges: List[Edge]
    cycles: List[List[str]]
    stats: Dict[str, int]

@dataclass
class ImpactAnalysis:
    """Impact analysis result."""
    changed_file: str
    directly_affected: List[str]
    transitively_affected: List[str]
    total_affected: int
    risk_level: str  # low, medium, high, critical

class DependencyAnalyzer:
    """Analyzes dependencies between a system components."""

    def __init__(self, root_path: str):
        """Initialize analyzer."""
        self.root_path = Path(root_path).resolve()
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_adjacency: Dict[str, Set[str]] = defaultdict(set)

    def build_graph(self) -> DependencyGraph:
        """Build the complete dependency graph."""
        self.nodes = {}
        self.edges = []
        self.adjacency = defaultdict(set)
        self.reverse_adjacency = defaultdict(set)

        # Scan for all components
        self._scan_python_modules()
        self._scan_yaml_configs()
        self._scan_templates()
        self._scan_markdown_docs()

        # Build adjacency lists
        for edge in self.edges:
            self.adjacency[edge.source].add(edge.target)
            self.reverse_adjacency[edge.target].add(edge.source)

        # Detect cycles
        cycles = self._detect_cycles()

        # Calculate statistics
        stats = {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'total_cycles': len(cycles),
            'nodes_by_type': {},
            'edges_by_type': {},
        }

        for node in self.nodes.values():
            stats['nodes_by_type'][node.type] = stats['nodes_by_type'].get(node.type, 0) + 1

        for edge in self.edges:
            stats['edges_by_type'][edge.type] = stats['edges_by_type'].get(edge.type, 0) + 1

        return DependencyGraph(
            timestamp=datetime.now().isoformat(),
            root_path=str(self.root_path),
            nodes=list(self.nodes.values()),
            edges=self.edges,
            cycles=cycles,
            stats=stats,
        )

    def _get_node_id(self, path: str) -> str:
        """Generate node ID from path."""
        return path.replace('/', '.').replace('\\', '.').replace('.py', '').replace('.yaml', '').replace('.yml', '')

    def _scan_python_modules(self) -> None:
        """Scan Python modules for dependencies."""
        for py_file in self.root_path.glob('**/*.py'):
            if self._should_skip(py_file):
                continue

            rel_path = str(py_file.relative_to(self.root_path))
            node_id = self._get_node_id(rel_path)

            try:
                content = py_file.read_text(encoding='utf-8')
            except (UnicodeDecodeError, IOError):
                continue

            # Create node
            self.nodes[node_id] = Node(
                id=node_id,
                path=rel_path,
                type='module',
                name=py_file.stem,
                imports=self._extract_python_imports(content),
                exports=self._extract_python_exports(content),
            )

            # Extract import edges
            for line_num, line in enumerate(content.split('\n'), 1):
                imports = self._parse_import_line(line)
                for imp in imports:
                    # Try to find the target in our codebase
                    target_id = self._resolve_import(imp, rel_path)
                    if target_id:
                        self.edges.append(Edge(
                            source=node_id,
                            target=target_id,
                            type='imports',
                            line=line_num,
                        ))

    def _extract_python_imports(self, content: str) -> List[str]:
        """Extract import names from Python content."""
        imports = []
        for match in re.finditer(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', content, re.MULTILINE):
            if match.group(1):
                imports.append(match.group(1))
            else:
                for item in match.group(2).split(','):
                    imports.append(item.strip().split()[0])
        return imports

    def _extract_python_exports(self, content: str) -> List[str]:
        """Extract exported names from Python content."""
        exports = []
        # Classes
        for match in re.finditer(r'^class\s+([A-Z][a-zA-Z0-9_]*)', content, re.MULTILINE):
            exports.append(match.group(1))
        # Functions
        for match in re.finditer(r'^def\s+([a-z_][a-zA-Z0-9_]*)', content, re.MULTILINE):
            if not match.group(1).startswith('_'):
                exports.append(match.group(1))
        return exports

    def _parse_import_line(self, line: str) -> List[str]:
        """Parse a Python import line."""
        imports = []

        # from X import Y
        match = re.match(r'^\s*from\s+(\S+)\s+import', line)
        if match:
            imports.append(match.group(1))
            return imports

        # import X, Y, Z
        match = re.match(r'^\s*import\s+(.+)$', line)
        if match:
            for item in match.group(1).split(','):
                module = item.strip().split()[0].split('.')[0]
                if module:
                    imports.append(module)

        return imports

    def _resolve_import(self, import_name: str, from_path: str) -> Optional[str]:
        """Resolve an import to a node ID in our graph."""
        # Handle relative imports
        if import_name.startswith('.'):
            # Relative import - resolve based on current file location
            parts = from_path.split('/')
            if len(parts) > 1:
                base = '/'.join(parts[:-1])
                relative = import_name.lstrip('.')
                if relative:
                    resolved = f"{base}/{relative.replace('.', '/')}"
                else:
                    resolved = base
                return self._get_node_id(resolved)

        # Absolute import - check if it matches a module in our codebase
        import_path = import_name.replace('.', '/')

        # Try different paths
        candidates = [
            f"{import_path}.py",
            f"{import_path}/__init__.py",
            f"tools/{import_path}.py",
        ]

        for candidate in candidates:
            node_id = self._get_node_id(candidate)
            # Check if we have this node or might have it
            if node_id in self.nodes:
                return node_id
            if (self.root_path / candidate).exists():
                return self._get_node_id(candidate)

        return None

    def _scan_yaml_configs(self) -> None:
        """Scan YAML configurations for references."""
        for yaml_file in self.root_path.glob('**/*.yaml'):
            if self._should_skip(yaml_file):
                continue

            self._process_yaml_file(yaml_file)

        for yml_file in self.root_path.glob('**/*.yml'):
            if self._should_skip(yml_file):
                continue

            self._process_yaml_file(yml_file)

    def _process_yaml_file(self, yaml_file: Path) -> None:
        """Process a single YAML file."""
        rel_path = str(yaml_file.relative_to(self.root_path))
        node_id = self._get_node_id(rel_path)

        try:
            content = yaml_file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, IOError):
            return

        self.nodes[node_id] = Node(
            id=node_id,
            path=rel_path,
            type='config',
            name=yaml_file.stem,
        )

        # Strip out examples sections to avoid parsing example data as dependencies
        # This removes content after 'examples:' at the start of a line
        content_without_examples = re.sub(r'^examples:.*', '', content, flags=re.MULTILINE | re.DOTALL)

        # Look for references (skip OpenAPI internal refs starting with #/)
        for match in re.finditer(r'\$ref:\s*["\']?([^"\'\s\n]+)', content_without_examples):
            ref_path = match.group(1)
            # Skip OpenAPI internal references
            if ref_path.startswith('#/'):
                continue
            # Skip template placeholders
            if '<' in ref_path or '{{' in ref_path:
                continue
            # Resolve relative paths relative to the source file's directory
            if not ref_path.startswith('/'):
                base_dir = str(yaml_file.parent.relative_to(self.root_path))
                if base_dir != '.':
                    ref_path = f"{base_dir}/{ref_path}"
            target_id = self._get_node_id(ref_path)
            self.edges.append(Edge(
                source=node_id,
                target=target_id,
                type='references',
            ))

        # Look for file paths (skip placeholders and examples)
        # Only process paths that look like they're meant to be real files (not schema examples)
        for match in re.finditer(r'(?:path|file|template):\s*["\']?([^"\'\s\n]+\.(py|yaml|yml|j2|md))', content_without_examples):
            ref_path = match.group(1)
            # Skip template placeholders
            if '<' in ref_path or '{{' in ref_path:
                continue
            # Skip paths that are clearly examples or documentation references
            if any(x in ref_path.lower() for x in ['example', 'sample', 'test_', '/auth/', '/db/', 'query.py', 'logbook/', 'index.md']):
                continue
            target_id = self._get_node_id(ref_path)
            self.edges.append(Edge(
                source=node_id,
                target=target_id,
                type='references',
            ))

    def _scan_templates(self) -> None:
        """Scan Jinja2 templates for dependencies."""
        for template_file in self.root_path.glob('**/*.j2'):
            if self._should_skip(template_file):
                continue

            self._process_template(template_file)

        for template_file in self.root_path.glob('**/*.jinja2'):
            if self._should_skip(template_file):
                continue

            self._process_template(template_file)

    def _process_template(self, template_file: Path) -> None:
        """Process a single template file."""
        rel_path = str(template_file.relative_to(self.root_path))
        node_id = self._get_node_id(rel_path)

        try:
            content = template_file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, IOError):
            return

        self.nodes[node_id] = Node(
            id=node_id,
            path=rel_path,
            type='template',
            name=template_file.stem,
        )

        # Look for extends
        for match in re.finditer(r'\{%\s*extends\s+["\']([^"\']+)["\']', content):
            target_path = match.group(1)
            target_id = self._get_node_id(target_path)
            self.edges.append(Edge(
                source=node_id,
                target=target_id,
                type='extends',
            ))

        # Look for includes
        for match in re.finditer(r'\{%\s*include\s+["\']([^"\']+)["\']', content):
            target_path = match.group(1)
            target_id = self._get_node_id(target_path)
            self.edges.append(Edge(
                source=node_id,
                target=target_id,
                type='uses',
            ))

        # Look for imports
        for match in re.finditer(r'\{%\s*(?:from|import)\s+["\']([^"\']+)["\']', content):
            target_path = match.group(1)
            target_id = self._get_node_id(target_path)
            self.edges.append(Edge(
                source=node_id,
                target=target_id,
                type='imports',
            ))

    def _scan_markdown_docs(self) -> None:
        """Scan Markdown documents for cross-references."""
        for md_file in self.root_path.glob('**/*.md'):
            if self._should_skip(md_file):
                continue

            rel_path = str(md_file.relative_to(self.root_path))
            node_id = self._get_node_id(rel_path)

            try:
                content = md_file.read_text(encoding='utf-8')
            except (UnicodeDecodeError, IOError):
                continue

            self.nodes[node_id] = Node(
                id=node_id,
                path=rel_path,
                type='documentation',
                name=md_file.stem,
            )

            # Strip out code blocks to avoid parsing example code as dependencies
            content_without_code = re.sub(r'```[\s\S]*?```', '', content)

            # Look for markdown links (outside of code blocks)
            for match in re.finditer(r'\[.*?\]\(([^)]+\.(?:md|py|yaml|yml))\)', content_without_code):
                link_path = match.group(1)
                # Skip template placeholders and example paths
                if '<' in link_path or '{{' in link_path:
                    continue
                # Handle relative paths
                if not link_path.startswith('/'):
                    base_dir = str(md_file.parent.relative_to(self.root_path))
                    if base_dir != '.':
                        link_path = f"{base_dir}/{link_path}"
                target_id = self._get_node_id(link_path)
                self.edges.append(Edge(
                    source=node_id,
                    target=target_id,
                    type='references',
                ))

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped."""
        skip_patterns = [
            '__pycache__', '.git', 'node_modules', 'venv',
            '.task', 'dist', 'build', '.pytest_cache',
            'PLANNING/dependencies', 'PLANNING/architecture',  # Don't scan our own output
        ]

        path_str = str(path)
        return any(pattern in path_str for pattern in skip_patterns)

    def _detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the dependency graph using DFS."""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.adjacency.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return cycles

    def analyze_impact(self, changed_file: str) -> ImpactAnalysis:
        """Analyze the impact of changing a file."""
        node_id = self._get_node_id(changed_file)

        if node_id not in self.nodes:
            return ImpactAnalysis(
                changed_file=changed_file,
                directly_affected=[],
                transitively_affected=[],
                total_affected=0,
                risk_level='low',
            )

        # Find directly affected (nodes that depend on this one)
        directly_affected = list(self.reverse_adjacency.get(node_id, []))

        # Find transitively affected
        transitively_affected = set()
        to_process = set(directly_affected)
        processed = set()

        while to_process:
            current = to_process.pop()
            if current in processed:
                continue
            processed.add(current)
            transitively_affected.add(current)

            for dependent in self.reverse_adjacency.get(current, []):
                if dependent not in processed:
                    to_process.add(dependent)

        # Remove directly affected from transitive
        transitively_affected = transitively_affected - set(directly_affected)

        total = len(directly_affected) + len(transitively_affected)

        # Determine risk level
        if total == 0:
            risk_level = 'low'
        elif total <= 3:
            risk_level = 'low'
        elif total <= 10:
            risk_level = 'medium'
        elif total <= 25:
            risk_level = 'high'
        else:
            risk_level = 'critical'

        return ImpactAnalysis(
            changed_file=changed_file,
            directly_affected=directly_affected,
            transitively_affected=list(transitively_affected),
            total_affected=total,
            risk_level=risk_level,
        )

    def get_dependencies(self, file_path: str) -> List[str]:
        """Get all dependencies of a file."""
        node_id = self._get_node_id(file_path)
        return list(self.adjacency.get(node_id, []))

    def get_dependents(self, file_path: str) -> List[str]:
        """Get all files that depend on this file."""
        node_id = self._get_node_id(file_path)
        return list(self.reverse_adjacency.get(node_id, []))

    def find_unused(self) -> List[str]:
        """Find nodes with no dependents (potentially unused)."""
        all_targets = set()
        for edge in self.edges:
            all_targets.add(edge.target)

        unused = []
        for node_id in self.nodes:
            if node_id not in all_targets:
                # No other node depends on this
                node = self.nodes[node_id]
                # Skip certain types that are expected to be entry points
                if node.type not in ['documentation']:
                    unused.append(node.path)

        return unused

def generate_mermaid(graph: DependencyGraph, max_nodes: int = 50) -> str:
    """Generate Mermaid diagram from graph."""
    lines = ['graph TD']

    # Limit nodes for readability
    nodes = graph.nodes[:max_nodes]
    node_ids = {n.id for n in nodes}

    # Add nodes
    for node in nodes:
        label = node.name[:20]
        lines.append(f'    {node.id.replace(".", "_")}["{label}"]')

    # Add edges (only for included nodes)
    for edge in graph.edges:
        if edge.source in node_ids and edge.target in node_ids:
            src = edge.source.replace('.', '_')
            tgt = edge.target.replace('.', '_')
            lines.append(f'    {src} --> {tgt}')

    return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Dependency Analyzer - Analyze component dependencies'
    )
    parser.add_argument(
        'root',
        nargs='?',
        default='.',
        help='Root directory to analyze (default: current directory)'
    )
    parser.add_argument(
        '--impact', '-i',
        metavar='FILE',
        help='Analyze impact of changing a file'
    )
    parser.add_argument(
        '--deps',
        metavar='FILE',
        help='Show dependencies of a file'
    )
    parser.add_argument(
        '--dependents',
        metavar='FILE',
        help='Show files that depend on a file'
    )
    parser.add_argument(
        '--cycles',
        action='store_true',
        help='Show circular dependencies'
    )
    parser.add_argument(
        '--unused',
        action='store_true',
        help='Show potentially unused files'
    )
    parser.add_argument(
        '--mermaid',
        action='store_true',
        help='Output Mermaid diagram'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'summary', 'table'],
        default='summary',
        help='Output format (default: summary)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file (default: stdout)'
    )

    args = parser.parse_args()

    analyzer = DependencyAnalyzer(args.root)
    graph = analyzer.build_graph()

    output_lines = []

    if args.impact:
        result = analyzer.analyze_impact(args.impact)
        output_lines.extend([
            f"Impact Analysis: {result.changed_file}",
            "=" * 50,
            f"Risk Level: {result.risk_level.upper()}",
            f"Total Affected: {result.total_affected}",
            "",
            f"Directly Affected ({len(result.directly_affected)}):",
        ])
        for dep in result.directly_affected:
            output_lines.append(f"  - {dep}")
        output_lines.append(f"\nTransitively Affected ({len(result.transitively_affected)}):")
        for dep in result.transitively_affected[:20]:
            output_lines.append(f"  - {dep}")

    elif args.deps:
        deps = analyzer.get_dependencies(args.deps)
        output_lines.append(f"Dependencies of {args.deps}:")
        for dep in deps:
            output_lines.append(f"  - {dep}")

    elif args.dependents:
        deps = analyzer.get_dependents(args.dependents)
        output_lines.append(f"Dependents of {args.dependents}:")
        for dep in deps:
            output_lines.append(f"  - {dep}")

    elif args.cycles:
        output_lines.append(f"Circular Dependencies ({len(graph.cycles)}):")
        for i, cycle in enumerate(graph.cycles[:10], 1):
            output_lines.append(f"\n  Cycle {i}:")
            output_lines.append(f"    {' -> '.join(cycle)}")

    elif args.unused:
        unused = analyzer.find_unused()
        output_lines.append(f"Potentially Unused Files ({len(unused)}):")
        for f in unused[:50]:
            output_lines.append(f"  - {f}")

    elif args.mermaid:
        output_lines.append(generate_mermaid(graph))

    elif args.format == 'json':
        output_lines.append(json.dumps(asdict(graph), indent=2, default=str))

    else:
        output_lines.extend([
            "=" * 60,
            "the system Dependency Analysis",
            "=" * 60,
            f"Timestamp: {graph.timestamp}",
            f"Root Path: {graph.root_path}",
            "",
            f"Total Nodes: {graph.stats['total_nodes']}",
            f"Total Edges: {graph.stats['total_edges']}",
            f"Cycles: {graph.stats['total_cycles']}",
            "",
            "Nodes by Type:",
        ])
        for t, count in sorted(graph.stats.get('nodes_by_type', {}).items()):
            output_lines.append(f"  {t:<20} {count:>5}")
        output_lines.append("\nEdges by Type:")
        for t, count in sorted(graph.stats.get('edges_by_type', {}).items()):
            output_lines.append(f"  {t:<20} {count:>5}")

        if graph.cycles:
            output_lines.append(f"\nCircular Dependencies Found ({len(graph.cycles)}):")
            for cycle in graph.cycles[:3]:
                output_lines.append(f"  {' -> '.join(cycle[:5])}...")

    output = '\n'.join(output_lines)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results saved to {args.output}")
    else:
        print(output)

if __name__ == '__main__':
    main()
