#!/usr/bin/env python3
"""
traceability_mapper.py - the system Traceability Mapping Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Analysis Tool

Purpose:
    Maps traceability relationships across the system artifacts:
    - Work orders -> Tasks -> Files
    - Templates -> Generated code
    - Policies -> Implementations
    - Requirements -> Test coverage

Usage:
    python3 traceability_mapper.py map --from work_order --id WO-2025-001
    python3 traceability_mapper.py trace --artifact task001 --depth 3
    python3 traceability_mapper.py coverage --type requirements
    python3 traceability_mapper.py export --format dot
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class TraceLink:
    """Represents a traceability link between artifacts."""
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    link_type: str  # implements, generates, tests, depends_on, etc.
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": {"type": self.source_type, "id": self.source_id},
            "target": {"type": self.target_type, "id": self.target_id},
            "link_type": self.link_type,
            "confidence": self.confidence,
            "metadata": self.metadata
        }

@dataclass
class TraceabilityMatrix:
    """Complete traceability matrix."""
    generated_at: str
    links: List[TraceLink]
    artifacts: Dict[str, List[str]]  # type -> list of IDs
    coverage: Dict[str, float]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "links": [l.to_dict() for l in self.links],
            "artifacts": self.artifacts,
            "coverage": self.coverage,
            "statistics": {
                "total_links": len(self.links),
                "artifact_types": len(self.artifacts),
                "total_artifacts": sum(len(v) for v in self.artifacts.values())
            }
        }

class TraceabilityMapper:
    """Maps traceability relationships across the system."""

    # Artifact types
    ARTIFACT_TYPES = [
        "work_order",
        "task",
        "template",
        "policy",
        "guideline",
        "schema",
        "tool",
        "test",
        "file"
    ]

    # Link types
    LINK_TYPES = [
        "implements",      # WO -> task
        "generates",       # template -> file
        "tests",           # test -> file
        "depends_on",      # task -> task
        "enforces",        # policy -> guideline
        "validates",       # schema -> file
        "references",      # any -> any
        "modifies",        # WO -> file
        "creates"          # WO -> artifact
    ]

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.links: List[TraceLink] = []
        self.artifacts: Dict[str, Set[str]] = defaultdict(set)

    def discover_artifacts(self):
        """Discover all artifacts in the system."""
        # Discover tasks
        for task_dir in self.base_path.glob("task*"):
            if task_dir.is_dir():
                self.artifacts["task"].add(task_dir.name)

        # Discover work orders
        wo_queue = self.base_path / "LogBook" / "pm" / "WO_QUEUE.yaml"
        if wo_queue.exists() and HAS_YAML:
            try:
                with open(wo_queue) as f:
                    data = yaml.safe_load(f) or {}
                for wo in data.get("work_orders", []):
                    wo_id = wo.get("work_order_id")
                    if wo_id:
                        self.artifacts["work_order"].add(wo_id)
            except Exception:
                pass

        # Discover templates
        for template_file in self.base_path.glob("templates/**/*.yaml"):
            self.artifacts["template"].add(template_file.stem)

        # Discover policies
        for policy_file in self.base_path.glob(".claude/policies/*.md"):
            self.artifacts["policy"].add(policy_file.stem)

        # Discover guidelines
        for guideline_file in self.base_path.glob(".claude/guidelines/*.md"):
            self.artifacts["guideline"].add(guideline_file.stem)

        # Discover schemas
        for schema_file in self.base_path.glob("PLANNING/schemas/*.yaml"):
            self.artifacts["schema"].add(schema_file.stem)

        # Discover tools
        for tool_file in self.base_path.glob("tools/*.py"):
            self.artifacts["tool"].add(tool_file.stem)

        # Discover tests
        for test_file in self.base_path.glob("**/test_*.py"):
            self.artifacts["test"].add(str(test_file.relative_to(self.base_path)))

    def build_links(self):
        """Build traceability links between artifacts."""
        self._link_work_orders_to_tasks()
        self._link_tasks_to_files()
        self._link_tasks_to_dependencies()
        self._link_tests_to_files()
        self._link_policies_to_guidelines()
        self._link_schemas_to_files()

    def _link_work_orders_to_tasks(self):
        """Link work orders to their target tasks."""
        wo_queue = self.base_path / "LogBook" / "pm" / "WO_QUEUE.yaml"
        if not wo_queue.exists() or not HAS_YAML:
            return

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            for wo in data.get("work_orders", []):
                wo_id = wo.get("work_order_id")
                task_id = wo.get("task_id")
                if wo_id and task_id:
                    self.links.append(TraceLink(
                        source_type="work_order",
                        source_id=wo_id,
                        target_type="task",
                        target_id=task_id,
                        link_type="implements",
                        confidence=1.0,
                        metadata={
                            "status": wo.get("status"),
                            "assigned_to": wo.get("assigned_to")
                        }
                    ))
        except Exception:
            pass

    def _link_tasks_to_files(self):
        """Link tasks to their source files."""
        for task_id in self.artifacts.get("task", []):
            task_dir = self.base_path / task_id
            if not task_dir.exists():
                continue

            # Link to source files
            for src_file in (task_dir / "src").rglob("*"):
                if src_file.is_file():
                    rel_path = str(src_file.relative_to(self.base_path))
                    self.artifacts["file"].add(rel_path)
                    self.links.append(TraceLink(
                        source_type="task",
                        source_id=task_id,
                        target_type="file",
                        target_id=rel_path,
                        link_type="creates",
                        confidence=1.0
                    ))

            # Link to test files
            for test_file in (task_dir / "tests").rglob("test_*.py"):
                if test_file.is_file():
                    rel_path = str(test_file.relative_to(self.base_path))
                    self.links.append(TraceLink(
                        source_type="task",
                        source_id=task_id,
                        target_type="test",
                        target_id=rel_path,
                        link_type="creates",
                        confidence=1.0
                    ))

    def _link_tasks_to_dependencies(self):
        """Link tasks to their dependencies."""
        for task_id in self.artifacts.get("task", []):
            manifest = self.base_path / task_id / "task.yaml"
            if not manifest.exists() or not HAS_YAML:
                continue

            try:
                with open(manifest) as f:
                    data = yaml.safe_load(f) or {}

                for dep in data.get("dependencies", []):
                    dep_id = dep if isinstance(dep, str) else dep.get("task_id")
                    if dep_id:
                        self.links.append(TraceLink(
                            source_type="task",
                            source_id=task_id,
                            target_type="task",
                            target_id=dep_id,
                            link_type="depends_on",
                            confidence=1.0
                        ))
            except Exception:
                pass

    def _link_tests_to_files(self):
        """Link test files to the files they test."""
        for test_path in self.artifacts.get("test", []):
            test_file = self.base_path / test_path
            if not test_file.exists():
                continue

            try:
                content = test_file.read_text()

                # Look for imports to find tested modules
                import re
                imports = re.findall(r'from\s+(\S+)\s+import|import\s+(\S+)', content)
                for imp in imports:
                    module = imp[0] or imp[1]
                    if module and not module.startswith(("pytest", "unittest", "mock")):
                        self.links.append(TraceLink(
                            source_type="test",
                            source_id=test_path,
                            target_type="file",
                            target_id=module.replace(".", "/") + ".py",
                            link_type="tests",
                            confidence=0.8
                        ))
            except Exception:
                pass

    def _link_policies_to_guidelines(self):
        """Link policies to implementing guidelines."""
        for policy_id in self.artifacts.get("policy", []):
            policy_file = self.base_path / ".claude" / "policies" / f"{policy_id}.md"
            if not policy_file.exists():
                continue

            try:
                content = policy_file.read_text()

                # Look for guideline references
                import re
                refs = re.findall(r'guidelines/([a-z\-]+)\.md', content)
                for ref in refs:
                    self.links.append(TraceLink(
                        source_type="policy",
                        source_id=policy_id,
                        target_type="guideline",
                        target_id=ref,
                        link_type="enforces",
                        confidence=0.9
                    ))
            except Exception:
                pass

    def _link_schemas_to_files(self):
        """Link schemas to files they validate."""
        for schema_id in self.artifacts.get("schema", []):
            # Schema typically validates files with matching names
            for file_id in self.artifacts.get("file", []):
                if schema_id.replace("_schema", "") in file_id:
                    self.links.append(TraceLink(
                        source_type="schema",
                        source_id=schema_id,
                        target_type="file",
                        target_id=file_id,
                        link_type="validates",
                        confidence=0.7
                    ))

    def trace_artifact(
        self,
        artifact_type: str,
        artifact_id: str,
        depth: int = 3,
        direction: str = "both"
    ) -> List[TraceLink]:
        """Trace all links from/to an artifact."""
        traced = []
        visited = set()

        def trace_recursive(atype: str, aid: str, current_depth: int):
            if current_depth <= 0:
                return
            if (atype, aid) in visited:
                return
            visited.add((atype, aid))

            for link in self.links:
                if direction in ("both", "forward"):
                    if link.source_type == atype and link.source_id == aid:
                        traced.append(link)
                        trace_recursive(link.target_type, link.target_id, current_depth - 1)

                if direction in ("both", "backward"):
                    if link.target_type == atype and link.target_id == aid:
                        traced.append(link)
                        trace_recursive(link.source_type, link.source_id, current_depth - 1)

        trace_recursive(artifact_type, artifact_id, depth)
        return traced

    def calculate_coverage(self) -> Dict[str, float]:
        """Calculate traceability coverage by type."""
        coverage = {}

        for artifact_type, artifacts in self.artifacts.items():
            if not artifacts:
                coverage[artifact_type] = 0.0
                continue

            linked = set()
            for link in self.links:
                if link.source_type == artifact_type:
                    linked.add(link.source_id)
                if link.target_type == artifact_type:
                    linked.add(link.target_id)

            coverage[artifact_type] = len(linked) / len(artifacts) if artifacts else 0.0

        return coverage

    def get_matrix(self) -> TraceabilityMatrix:
        """Get complete traceability matrix."""
        return TraceabilityMatrix(
            generated_at=datetime.utcnow().isoformat() + "Z",
            links=self.links,
            artifacts={k: list(v) for k, v in self.artifacts.items()},
            coverage=self.calculate_coverage()
        )

    def export_dot(self) -> str:
        """Export as DOT graph format."""
        lines = ["digraph Traceability {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")

        # Define node styles by type
        type_colors = {
            "work_order": "lightblue",
            "task": "lightgreen",
            "file": "lightyellow",
            "test": "lightpink",
            "policy": "lightcoral",
            "guideline": "lavender",
            "schema": "lightgray",
            "template": "lightsalmon",
            "tool": "lightcyan"
        }

        # Add nodes
        for artifact_type, artifacts in self.artifacts.items():
            color = type_colors.get(artifact_type, "white")
            for artifact_id in artifacts:
                safe_id = artifact_id.replace("/", "_").replace(".", "_").replace("-", "_")
                lines.append(f'  {safe_id} [label="{artifact_id}" style=filled fillcolor="{color}"];')

        # Add edges
        for link in self.links:
            src_id = link.source_id.replace("/", "_").replace(".", "_").replace("-", "_")
            tgt_id = link.target_id.replace("/", "_").replace(".", "_").replace("-", "_")
            lines.append(f'  {src_id} -> {tgt_id} [label="{link.link_type}"];')

        lines.append("}")
        return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="the system Traceability Mapper")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Map command
    map_parser = subparsers.add_parser("map", help="Map traceability from artifact")
    map_parser.add_argument("--from", dest="from_type", required=True, help="Source artifact type")
    map_parser.add_argument("--id", required=True, help="Source artifact ID")
    map_parser.add_argument("--depth", type=int, default=3, help="Trace depth")

    # Trace command
    trace_parser = subparsers.add_parser("trace", help="Trace artifact relationships")
    trace_parser.add_argument("--artifact", required=True, help="Artifact ID")
    trace_parser.add_argument("--type", help="Artifact type")
    trace_parser.add_argument("--depth", type=int, default=3)
    trace_parser.add_argument("--direction", choices=["forward", "backward", "both"], default="both")

    # Coverage command
    coverage_parser = subparsers.add_parser("coverage", help="Calculate coverage")
    coverage_parser.add_argument("--type", help="Filter by artifact type")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export traceability data")
    export_parser.add_argument("--format", choices=["json", "dot", "matrix"], default="json")
    export_parser.add_argument("--output", "-o", help="Output file")

    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover all artifacts")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    mapper = TraceabilityMapper()
    mapper.discover_artifacts()
    mapper.build_links()

    if args.command == "map":
        links = mapper.trace_artifact(args.from_type, args.id, args.depth, "forward")

        if args.format == "json":
            print(json.dumps([l.to_dict() for l in links], indent=2))
        else:
            print(f"\nTraceability from {args.from_type}:{args.id}")
            print("=" * 50)
            for link in links:
                print(f"  -> [{link.link_type}] {link.target_type}:{link.target_id}")

    elif args.command == "trace":
        artifact_type = args.type
        if not artifact_type:
            # Try to infer type
            for atype, artifacts in mapper.artifacts.items():
                if args.artifact in artifacts:
                    artifact_type = atype
                    break

        if not artifact_type:
            print(f"Could not determine type for {args.artifact}")
            return 1

        links = mapper.trace_artifact(artifact_type, args.artifact, args.depth, args.direction)

        if args.format == "json":
            print(json.dumps([l.to_dict() for l in links], indent=2))
        else:
            print(f"\nTrace for {artifact_type}:{args.artifact} (depth={args.depth})")
            print("=" * 50)
            for link in links:
                print(f"  {link.source_type}:{link.source_id}")
                print(f"    --[{link.link_type}]-->")
                print(f"  {link.target_type}:{link.target_id}")
                print()

    elif args.command == "coverage":
        coverage = mapper.calculate_coverage()

        if args.format == "json":
            print(json.dumps(coverage, indent=2))
        else:
            print("\nTraceability Coverage")
            print("=" * 40)
            for atype, cov in sorted(coverage.items()):
                bar = "#" * int(cov * 20)
                print(f"  {atype:15} [{bar:20}] {cov*100:.1f}%")

    elif args.command == "export":
        if args.format == "dot":
            output = mapper.export_dot()
        elif args.format == "matrix":
            matrix = mapper.get_matrix()
            output = json.dumps(matrix.to_dict(), indent=2)
        else:
            output = json.dumps(mapper.get_matrix().to_dict(), indent=2)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Exported to {args.output}")
        else:
            print(output)

    elif args.command == "discover":
        if args.format == "json":
            print(json.dumps({k: list(v) for k, v in mapper.artifacts.items()}, indent=2))
        else:
            print("\nDiscovered Artifacts")
            print("=" * 40)
            for atype, artifacts in sorted(mapper.artifacts.items()):
                print(f"\n{atype} ({len(artifacts)}):")
                for a in sorted(artifacts)[:10]:
                    print(f"  - {a}")
                if len(artifacts) > 10:
                    print(f"  ... and {len(artifacts) - 10} more")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
