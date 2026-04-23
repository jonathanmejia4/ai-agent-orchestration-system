#!/usr/bin/env python3
"""
Dependency Catalog Generator

Generates dual-format dependency catalog:
1. DEPENDENCY_CATALOG.md - Human-readable markdown
2. PLANNING/dependencies/current_graph.yaml - Machine-readable YAML

Features:
- Leverages existing dependency_analyzer.py
- Broken dependency detection (flags missing files)
- Change detection via checksum
- Historical snapshots
- Impact zone computation

Version: 1.0.0
Created: 2026-01-09
Author: Builder Agent
"""

import os
import sys
import json
import hashlib
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import yaml
except ImportError:
    print("Error: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)

from dependency_analyzer import DependencyAnalyzer, DependencyGraph, Node, Edge


@dataclass
class BrokenDependency:
    """A dependency that references a missing file."""
    source: str
    source_path: str
    target: str
    target_path: str
    dep_type: str
    line: Optional[int]
    status: str = "MISSING"


@dataclass
class ImpactZone:
    """Impact analysis for a high-connectivity component."""
    node_id: str
    node_path: str
    directly_affected: List[str]
    transitively_affected: List[str]
    total_affected: int
    risk_level: str


class DependencyCatalogGenerator:
    """Generates dual-format dependency catalog."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.analyzer = DependencyAnalyzer(str(self.root_path))
        self.graph: Optional[DependencyGraph] = None

        # Output paths
        self.yaml_output = self.root_path / "PLANNING" / "dependencies" / "current_graph.yaml"
        self.md_output = self.root_path / "DEPENDENCY_CATALOG.md"
        self.history_dir = self.root_path / "PLANNING" / "dependencies" / "history"

        # Ensure directories exist
        self.yaml_output.parent.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def compute_checksum(self) -> str:
        """Compute checksum of dependency-relevant files for change detection."""
        hasher = hashlib.sha256()

        # File patterns to include
        patterns = ['**/*.py', '**/*.yaml', '**/*.yml', '**/*.j2', '**/*.jinja2', '**/*.md']
        skip_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.task', 'dist', 'build'}

        files_hashed = 0
        for pattern in patterns:
            for file_path in sorted(self.root_path.glob(pattern)):
                # Skip excluded directories
                if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                    continue

                try:
                    stat = file_path.stat()
                    # Hash path + mtime + size for speed (not full content)
                    hasher.update(str(file_path.relative_to(self.root_path)).encode())
                    hasher.update(str(stat.st_mtime_ns).encode())
                    hasher.update(str(stat.st_size).encode())
                    files_hashed += 1
                except (OSError, IOError):
                    continue

        return f"sha256:{hasher.hexdigest()[:16]}:{files_hashed}"

    def has_changes(self) -> bool:
        """Check if dependencies have changed since last generation."""
        if not self.yaml_output.exists():
            return True

        try:
            with open(self.yaml_output) as f:
                data = yaml.safe_load(f)
                old_checksum = data.get('metadata', {}).get('checksum', '')
        except (yaml.YAMLError, IOError):
            return True

        new_checksum = self.compute_checksum()
        return old_checksum != new_checksum

    def find_broken_dependencies(self) -> List[BrokenDependency]:
        """Find all edges where target file doesn't exist."""
        broken = []

        for edge in self.graph.edges:
            # Get target path from node if exists, otherwise derive from ID
            target_node = None
            for node in self.graph.nodes:
                if node.id == edge.target:
                    target_node = node
                    break

            if target_node:
                target_path = target_node.path
            else:
                # Derive path from ID (reverse of _get_node_id)
                target_path = edge.target.replace('.', '/') + '.py'

            # Check if file exists
            full_path = self.root_path / target_path

            # Try multiple extensions
            exists = False
            for ext in ['', '.py', '.yaml', '.yml', '.md', '.j2']:
                check_path = self.root_path / (target_path.rstrip('.py') + ext) if ext else full_path
                if check_path.exists():
                    exists = True
                    break

            if not exists and not self._is_stdlib_or_external(edge.target):
                # Get source path
                source_node = None
                for node in self.graph.nodes:
                    if node.id == edge.source:
                        source_node = node
                        break

                source_path = source_node.path if source_node else edge.source.replace('.', '/')

                broken.append(BrokenDependency(
                    source=edge.source,
                    source_path=source_path,
                    target=edge.target,
                    target_path=target_path,
                    dep_type=edge.type,
                    line=edge.line,
                ))

        return broken

    def _is_stdlib_or_external(self, node_id: str) -> bool:
        """Check if a node ID refers to stdlib or external package."""
        stdlib_modules = {
            'os', 're', 'json', 'sys', 'pathlib', 'datetime', 'typing',
            'dataclasses', 'collections', 'argparse', 'hashlib', 'shutil',
            'subprocess', 'logging', 'unittest', 'pytest', 'yaml', 'io',
            'time', 'random', 'math', 'functools', 'itertools', 'copy',
            'tempfile', 'glob', 'fnmatch', 'abc', 'enum', 'contextlib',
        }

        base_module = node_id.split('.')[0]
        return base_module in stdlib_modules

    def compute_impact_zones(self, top_n: int = 20) -> List[ImpactZone]:
        """Compute impact zones for top N highest-connectivity nodes."""
        # Build reverse adjacency for dependents
        reverse_adj: Dict[str, Set[str]] = {}
        for edge in self.graph.edges:
            if edge.target not in reverse_adj:
                reverse_adj[edge.target] = set()
            reverse_adj[edge.target].add(edge.source)

        # Count dependents for each node
        dependent_counts = []
        for node in self.graph.nodes:
            direct = reverse_adj.get(node.id, set())
            dependent_counts.append((node.id, node.path, len(direct)))

        # Sort by dependent count descending
        dependent_counts.sort(key=lambda x: x[2], reverse=True)

        # Compute full impact for top N
        impact_zones = []
        for node_id, node_path, _ in dependent_counts[:top_n]:
            impact = self.analyzer.analyze_impact(node_path)

            impact_zones.append(ImpactZone(
                node_id=node_id,
                node_path=node_path,
                directly_affected=impact.directly_affected,
                transitively_affected=impact.transitively_affected,
                total_affected=impact.total_affected,
                risk_level=impact.risk_level,
            ))

        return impact_zones

    def generate(self, force: bool = False) -> bool:
        """Main generation method."""
        if not force and not self.has_changes():
            print("No dependency changes detected. Use --force to regenerate.")
            return False

        print("Building dependency graph...")
        self.graph = self.analyzer.build_graph()

        print("Detecting broken dependencies...")
        broken_deps = self.find_broken_dependencies()

        print("Computing impact zones...")
        impact_zones = self.compute_impact_zones()

        print("Finding orphan components...")
        orphans = self.analyzer.find_unused()

        print("Generating YAML output...")
        self._write_yaml_output(broken_deps, impact_zones, orphans)

        print("Generating Markdown catalog...")
        self._write_markdown_output(broken_deps, impact_zones, orphans)

        print("Creating historical snapshot...")
        self._create_snapshot()

        print(f"\nCatalog generated successfully!")
        print(f"  - YAML: {self.yaml_output}")
        print(f"  - Markdown: {self.md_output}")
        print(f"  - Components: {len(self.graph.nodes)}")
        print(f"  - Dependencies: {len(self.graph.edges)}")
        print(f"  - Broken: {len(broken_deps)}")
        print(f"  - Cycles: {len(self.graph.cycles)}")

        return True

    def _write_yaml_output(self, broken_deps: List[BrokenDependency],
                           impact_zones: List[ImpactZone], orphans: List[str]) -> None:
        """Write machine-readable YAML."""
        data = {
            'metadata': {
                'version': '1.0.0',
                'generated_at': datetime.now().isoformat(),
                'generated_by': 'tools/generate_dependency_catalog.py',
                'root_path': str(self.root_path),
                'checksum': self.compute_checksum(),
            },
            'statistics': {
                'total_nodes': len(self.graph.nodes),
                'total_edges': len(self.graph.edges),
                'cycles_detected': len(self.graph.cycles),
                'broken_dependencies': len(broken_deps),
                'orphan_nodes': len(orphans),
                'nodes_by_type': self.graph.stats.get('nodes_by_type', {}),
                'edges_by_type': self.graph.stats.get('edges_by_type', {}),
            },
            'validation': {
                'is_valid_dag': len(self.graph.cycles) == 0,
                'last_validated': datetime.now().isoformat(),
                'checks': {
                    'acyclic': 'pass' if len(self.graph.cycles) == 0 else 'fail',
                    'no_broken_deps': 'pass' if len(broken_deps) == 0 else 'warn',
                    'no_orphans': 'pass' if len(orphans) == 0 else 'warn',
                },
            },
            'nodes': [
                {
                    'id': n.id,
                    'path': n.path,
                    'type': n.type,
                    'name': n.name,
                    'imports': n.imports,
                    'exports': n.exports,
                }
                for n in self.graph.nodes
            ],
            'edges': [
                {
                    'source': e.source,
                    'target': e.target,
                    'type': e.type,
                    'line': e.line,
                }
                for e in self.graph.edges
            ],
            'broken_dependencies': [
                {
                    'source': b.source,
                    'source_path': b.source_path,
                    'target': b.target,
                    'target_path': b.target_path,
                    'type': b.dep_type,
                    'line': b.line,
                    'status': b.status,
                }
                for b in broken_deps
            ],
            'impact_zones': {
                iz.node_id: {
                    'path': iz.node_path,
                    'directly_affected': iz.directly_affected,
                    'transitively_affected': iz.transitively_affected,
                    'total_affected': iz.total_affected,
                    'risk_level': iz.risk_level,
                }
                for iz in impact_zones
            },
            'cycles': self.graph.cycles,
            'orphans': orphans,
        }

        with open(self.yaml_output, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, width=120)

    def _write_markdown_output(self, broken_deps: List[BrokenDependency],
                                impact_zones: List[ImpactZone], orphans: List[str]) -> None:
        """Write human-readable Markdown catalog."""
        lines = []

        # Header
        lines.extend([
            "# Dependency Catalog",
            "",
            f"> **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> **Generated By:** `tools/generate_dependency_catalog.py`",
            f"> **Data Source:** `PLANNING/dependencies/current_graph.yaml`",
            "",
            "---",
            "",
        ])

        # Statistics Dashboard
        lines.extend([
            "## Statistics Dashboard",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Components | {len(self.graph.nodes)} |",
            f"| Total Dependencies | {len(self.graph.edges)} |",
            f"| Circular Dependencies | {len(self.graph.cycles)} |",
        ])

        # Highlight broken deps
        if broken_deps:
            lines.append(f"| **Broken Dependencies** | **{len(broken_deps)}** |")
        else:
            lines.append(f"| Broken Dependencies | 0 |")

        lines.extend([
            f"| Orphan Components | {len(orphans)} |",
            f"| DAG Valid | {'TRUE' if len(self.graph.cycles) == 0 else 'FALSE'} |",
            "",
        ])

        # Component breakdown
        lines.extend([
            "### Component Breakdown",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for node_type, count in sorted(self.graph.stats.get('nodes_by_type', {}).items()):
            lines.append(f"| {node_type} | {count} |")
        lines.append("")

        # Broken Dependencies section
        lines.extend([
            "---",
            "",
            "## Broken Dependencies (Missing Files)",
            "",
        ])

        if broken_deps:
            lines.extend([
                "> Dependencies that reference files that don't exist",
                "",
                "| Source File | Missing Dependency | Type | Line |",
                "|-------------|-------------------|------|------|",
            ])
            for bd in broken_deps[:50]:  # Limit to 50
                line_str = str(bd.line) if bd.line else "-"
                lines.append(f"| `{bd.source_path}` | `{bd.target_path}` | {bd.dep_type} | {line_str} |")

            if len(broken_deps) > 50:
                lines.append(f"\n*...and {len(broken_deps) - 50} more. See YAML for complete list.*")
        else:
            lines.append("*No broken dependencies detected.*")

        lines.append("")

        # Circular Dependencies
        lines.extend([
            "---",
            "",
            "## Circular Dependency Warnings",
            "",
        ])

        if self.graph.cycles:
            lines.extend([
                "| Cycle # | Components |",
                "|---------|------------|",
            ])
            for i, cycle in enumerate(self.graph.cycles[:10], 1):
                cycle_str = " -> ".join(cycle[:5])
                if len(cycle) > 5:
                    cycle_str += "..."
                lines.append(f"| {i} | {cycle_str} |")

            if len(self.graph.cycles) > 10:
                lines.append(f"\n*...and {len(self.graph.cycles) - 10} more cycles.*")
        else:
            lines.append("*No circular dependencies detected.*")

        lines.append("")

        # Critical Paths & Bottlenecks
        lines.extend([
            "---",
            "",
            "## Critical Paths & Bottlenecks",
            "",
            "> Components that, when changed, affect the most other files",
            "",
            "| Rank | Component | Dependents | Risk Level |",
            "|------|-----------|------------|------------|",
        ])

        for i, iz in enumerate(impact_zones[:20], 1):
            risk_emoji = {'critical': 'CRITICAL', 'high': 'HIGH', 'medium': 'MEDIUM', 'low': 'LOW'}.get(iz.risk_level, iz.risk_level)
            lines.append(f"| {i} | `{iz.node_path}` | {iz.total_affected} | {risk_emoji} |")

        lines.append("")

        # Impact Zones (expandable)
        lines.extend([
            "---",
            "",
            "## Impact Zones",
            "",
            "> When file X changes, these files may need updating",
            "",
        ])

        for iz in impact_zones[:10]:
            lines.extend([
                f"<details>",
                f"<summary><code>{iz.node_path}</code> ({iz.total_affected} dependents)</summary>",
                "",
                f"**Direct Dependents ({len(iz.directly_affected)}):**",
            ])
            for dep in iz.directly_affected[:10]:
                lines.append(f"- `{dep}`")
            if len(iz.directly_affected) > 10:
                lines.append(f"- *...and {len(iz.directly_affected) - 10} more*")

            lines.extend([
                "",
                f"**Transitive Dependents ({len(iz.transitively_affected)}):**",
            ])
            for dep in iz.transitively_affected[:10]:
                lines.append(f"- `{dep}`")
            if len(iz.transitively_affected) > 10:
                lines.append(f"- *...and {len(iz.transitively_affected) - 10} more*")

            lines.extend(["", "</details>", ""])

        # Component Registry by Type
        lines.extend([
            "---",
            "",
            "## Component Registry by Type",
            "",
        ])

        # Group nodes by type
        nodes_by_type: Dict[str, List[Node]] = {}
        for node in self.graph.nodes:
            if node.type not in nodes_by_type:
                nodes_by_type[node.type] = []
            nodes_by_type[node.type].append(node)

        for node_type in ['module', 'config', 'template', 'documentation']:
            if node_type not in nodes_by_type:
                continue

            type_label = {'module': 'Python Modules', 'config': 'YAML Configurations',
                         'template': 'Templates', 'documentation': 'Documentation'}.get(node_type, node_type)

            nodes = nodes_by_type[node_type]
            lines.extend([
                f"### {type_label} ({len(nodes)})",
                "",
                "<details>",
                f"<summary>Show {len(nodes)} {type_label.lower()}</summary>",
                "",
                "| Name | Path |",
                "|------|------|",
            ])

            for node in sorted(nodes, key=lambda n: n.path)[:100]:
                lines.append(f"| {node.name} | `{node.path}` |")

            if len(nodes) > 100:
                lines.append(f"\n*...and {len(nodes) - 100} more*")

            lines.extend(["", "</details>", ""])

        # Orphan Components
        lines.extend([
            "---",
            "",
            "## Orphan Components",
            "",
            "> Files with no dependencies and no dependents",
            "",
        ])

        if orphans:
            lines.extend([
                "<details>",
                f"<summary>Show {len(orphans)} orphans</summary>",
                "",
            ])
            for orphan in orphans[:50]:
                lines.append(f"- `{orphan}`")
            if len(orphans) > 50:
                lines.append(f"\n*...and {len(orphans) - 50} more*")
            lines.extend(["", "</details>"])
        else:
            lines.append("*No orphan components detected.*")

        lines.extend([
            "",
            "---",
            "",
            "## Metadata",
            "",
            f"- **Version:** 1.0.0",
            f"- **Schema:** `PLANNING/dependencies/current_graph.yaml`",
            f"- **Generator:** `tools/generate_dependency_catalog.py`",
            f"- **Checksum:** `{self.compute_checksum()}`",
            "",
        ])

        # Write file
        with open(self.md_output, 'w') as f:
            f.write('\n'.join(lines))

    def _create_snapshot(self) -> None:
        """Create historical snapshot."""
        if not self.yaml_output.exists():
            return

        # Create dated snapshot
        date_str = datetime.now().strftime('%Y-%m-%d')
        snapshot_path = self.history_dir / f"{date_str}-graph.yaml"

        # Copy current to snapshot
        shutil.copy2(self.yaml_output, snapshot_path)

        # Prune old snapshots (keep last 30)
        snapshots = sorted(self.history_dir.glob('*-graph.yaml'))
        while len(snapshots) > 30:
            oldest = snapshots.pop(0)
            oldest.unlink()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate Dependency Catalog (Markdown + YAML)'
    )
    parser.add_argument(
        '--root', '-r',
        default='.',
        help='Root directory to analyze (default: current directory)'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force regeneration even if no changes detected'
    )
    parser.add_argument(
        '--check', '-c',
        action='store_true',
        help='Check mode: exit 1 if catalog is stale, 0 if current'
    )
    parser.add_argument(
        '--yaml-only',
        action='store_true',
        help='Generate YAML output only'
    )
    parser.add_argument(
        '--md-only',
        action='store_true',
        help='Generate Markdown output only'
    )

    args = parser.parse_args()

    # Find root - walk up to find project root
    root = Path(args.root).resolve()
    if not (root / 'PLANNING').exists():
        # Try to find the system root
        check = root
        for _ in range(5):
            if (check / 'PLANNING').exists() and (check / 'tools').exists():
                root = check
                break
            check = check.parent

    generator = DependencyCatalogGenerator(str(root))

    if args.check:
        if generator.has_changes():
            print("Dependency catalog is STALE. Run regeneration.")
            sys.exit(1)
        print("Dependency catalog is UP TO DATE.")
        sys.exit(0)

    success = generator.generate(force=args.force)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
