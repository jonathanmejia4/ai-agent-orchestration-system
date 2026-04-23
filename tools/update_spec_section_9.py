#!/usr/bin/env python3
"""
update_ssot_section_9.py - Update SSOT wiring.yaml Section 9 (Dependency Graph)

Synchronizes dependency graph data from graph.yaml into wiring.yaml Section 9.

Usage:
    python tools/update_ssot_section_9.py <wiring.yaml> <graph.yaml>
    python tools/update_ssot_section_9.py --help

Examples:
    python tools/update_ssot_section_9.py .task/wiring.yaml .task/graph.yaml
    python tools/update_ssot_section_9.py .task/wiring.yaml .task/graph.yaml --dry-run

Reference: PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

def load_yaml(path: Path) -> Optional[Dict]:
    """Load YAML file safely."""
    try:
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Error: File not found: {path}", file=sys.stderr)
        return None
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in {path}: {e}", file=sys.stderr)
        return None

def save_yaml(path: Path, data: Dict, dry_run: bool = False) -> bool:
    """Save data to YAML file."""
    if dry_run:
        print("--- Dry run: Would write to", path)
        print(yaml.dump(data, default_flow_style=False, sort_keys=False))
        return True

    try:
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"Error: Failed to write {path}: {e}", file=sys.stderr)
        return False

def compute_topological_order(graph_data: Dict) -> List[Dict]:
    """Compute topological order from graph data."""
    nodes = graph_data.get('graph', {}).get('nodes', [])
    edges = graph_data.get('graph', {}).get('edges', [])

    if not nodes:
        # Use precomputed analysis if available
        analysis = graph_data.get('analysis', {})
        return analysis.get('topological_order', [])

    # Build adjacency and in-degree maps
    in_degree = {node.get('id'): 0 for node in nodes}
    adjacency = {node.get('id'): [] for node in nodes}
    node_info = {node.get('id'): node for node in nodes}

    for edge in edges:
        from_id = edge.get('from')
        to_id = edge.get('to')
        if from_id in adjacency and to_id in in_degree:
            adjacency[from_id].append(to_id)
            in_degree[to_id] += 1

    # Kahn's algorithm for topological sort
    result = []
    wave = 0
    queue = [nid for nid, deg in in_degree.items() if deg == 0]

    while queue:
        wave_nodes = []
        next_queue = []

        for node_id in queue:
            node = node_info.get(node_id, {})
            deps = [e.get('from') for e in edges if e.get('to') == node_id]

            wave_nodes.append({
                'task_id': node_id,
                'short_id': node_id[:8] if len(node_id) > 8 else node_id,
                'name': node.get('label') or node.get('name', node_id),
                'wave': wave,
                'can_start_after': deps if deps else None,
                'can_start_immediately': wave == 0
            })

            for neighbor in adjacency.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_queue.append(neighbor)

        result.extend(wave_nodes)
        queue = next_queue
        wave += 1

    return result

def compute_parallel_sets(topo_order: List[Dict]) -> List[Dict]:
    """Group nodes by wave into parallel sets."""
    waves = {}
    for node in topo_order:
        w = node.get('wave', 0)
        if w not in waves:
            waves[w] = []
        waves[w].append(node.get('short_id') or node.get('task_id'))

    return [
        {
            'wave': wave,
            'tasks': tasks,
            'max_effort_hours': len(tasks) * 2.0  # Estimate
        }
        for wave, tasks in sorted(waves.items())
    ]

def compute_critical_path(topo_order: List[Dict]) -> Dict:
    """Estimate critical path from topological order."""
    if not topo_order:
        return {'path': [], 'total_effort_hours': 0}

    # Simple heuristic: path through highest-wave nodes
    waves = {}
    for node in topo_order:
        w = node.get('wave', 0)
        if w not in waves:
            waves[w] = node

    path = [waves[w].get('short_id') or waves[w].get('task_id')
            for w in sorted(waves.keys())]

    return {
        'path': path,
        'total_effort_hours': len(path) * 2.0  # Estimate
    }

def compute_metrics(topo_order: List[Dict], parallel_sets: List[Dict]) -> Dict:
    """Compute concurrency metrics."""
    max_parallel = max((len(ps.get('tasks', [])) for ps in parallel_sets), default=0)
    total = len(topo_order)
    waves = len(parallel_sets)

    return {
        'total_tasks': total,
        'max_parallel_tasks': max_parallel,
        'avg_parallel_tasks': round(total / waves, 2) if waves else 0,
        'total_waves': waves
    }

def update_section_9(wiring_data: Dict, graph_data: Dict, graph_path: Path) -> Dict:
    """Update Section 9 in wiring data with graph information."""

    # Compute dependency graph components
    topo_order = compute_topological_order(graph_data)
    parallel_sets = compute_parallel_sets(topo_order)
    critical_path = compute_critical_path(topo_order)
    metrics = compute_metrics(topo_order, parallel_sets)

    # Build Section 9
    section_9 = {
        'graph_file': str(graph_path),
        'graph_version': graph_data.get('version', '1.0.0'),
        'last_updated': datetime.now().isoformat(),
        'topological_order': topo_order,
        'parallel_sets': parallel_sets,
        'critical_path': critical_path,
        'metrics': metrics
    }

    # Update wiring data
    wiring_data['section_9_dependency_graph'] = section_9

    return wiring_data

def main():
    parser = argparse.ArgumentParser(
        description='Update SSOT wiring.yaml Section 9 with dependency graph data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s .task/wiring.yaml .task/graph.yaml
  %(prog)s .task/wiring.yaml .task/graph.yaml --dry-run
  %(prog)s --help

Reference: PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md
        """
    )

    parser.add_argument('wiring_path', type=Path, nargs='?',
                        help='Path to wiring.yaml file')
    parser.add_argument('graph_path', type=Path, nargs='?',
                        help='Path to graph.yaml file')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print changes without writing')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Validate arguments
    if not args.wiring_path or not args.graph_path:
        parser.print_help()
        print("\nError: Both wiring.yaml and graph.yaml paths are required", file=sys.stderr)
        sys.exit(1)

    # Load files
    wiring_data = load_yaml(args.wiring_path)
    if wiring_data is None:
        sys.exit(1)

    graph_data = load_yaml(args.graph_path)
    if graph_data is None:
        sys.exit(1)

    if args.verbose:
        print(f"Loaded wiring.yaml: {args.wiring_path}")
        print(f"Loaded graph.yaml: {args.graph_path}")

    # Update Section 9
    updated_wiring = update_section_9(wiring_data, graph_data, args.graph_path)

    # Save result
    if save_yaml(args.wiring_path, updated_wiring, args.dry_run):
        if not args.dry_run:
            print(f"Updated Section 9 in {args.wiring_path}")

        metrics = updated_wiring.get('section_9_dependency_graph', {}).get('metrics', {})
        print(f"  Total tasks: {metrics.get('total_tasks', 0)}")
        print(f"  Max parallel: {metrics.get('max_parallel_tasks', 0)}")
        print(f"  Total waves: {metrics.get('total_waves', 0)}")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
