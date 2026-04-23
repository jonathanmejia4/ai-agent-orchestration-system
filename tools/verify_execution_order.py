#!/usr/bin/env python3
"""
verify_execution_order.py - DAG execution order verification tool

Verifies that tasks were executed in topological dependency order by
comparing execution timestamps in logbook against the dependency graph.
Validates: dependency.completed < current_task.started for all dependencies.

Exit codes:
  0 - Order respected (all dependencies completed before dependents started)
  1 - Violations detected (some tasks started before dependencies completed)
  2 - File/parse error

Usage:
  python tools/verify_execution_order.py logbook.yaml graph.yaml
  python tools/verify_execution_order.py .task/logbook.yaml .task/graph.yaml --verbose
  python tools/verify_execution_order.py logbook.yaml graph.yaml --format=json

Reference: PLANNING/DEPENDENCY_GRAPH_AND_TOPOLOGICAL_BUILD_ORDER_POLICY.md:1362,1438,1486
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

class ExecutionOrderVerifier:
    """Verify task execution followed dependency order."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str]] = []
        self.reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self.execution_records: dict[str, dict] = {}
        self.violations: list[dict] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def load_graph(self, graph_path: Path) -> bool:
        """Load and parse the dependency graph file."""
        try:
            with open(graph_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                self.errors.append("Empty graph file")
                return False

            # Parse nodes
            nodes_data = data.get("nodes", data.get("tasks", []))
            if isinstance(nodes_data, list):
                for node in nodes_data:
                    if isinstance(node, dict):
                        node_id = str(node.get("id", node.get("task_id", node.get("name", ""))))
                        if node_id:
                            self.nodes[node_id] = node
                    elif isinstance(node, str):
                        self.nodes[node] = {"id": node}
            elif isinstance(nodes_data, dict):
                for node_id, node_data in nodes_data.items():
                    node_id = str(node_id)
                    self.nodes[node_id] = node_data if isinstance(node_data, dict) else {"id": node_id}

            # Parse edges
            edges_data = data.get("edges", data.get("dependencies", []))
            if isinstance(edges_data, list):
                for edge in edges_data:
                    if isinstance(edge, dict):
                        source = str(edge.get("from", edge.get("source", edge.get("parent", ""))))
                        target = str(edge.get("to", edge.get("target", edge.get("child", ""))))
                        if source and target:
                            self.edges.append((source, target))
                            self.reverse_adjacency[target].append(source)
                    elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
                        source, target = str(edge[0]), str(edge[1])
                        self.edges.append((source, target))
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
                                self.reverse_adjacency[node_id].append(dep_id)

            if not self.nodes:
                self.errors.append("No nodes found in graph")
                return False

            return True

        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error in graph: {e}")
            return False
        except FileNotFoundError:
            self.errors.append(f"Graph file not found: {graph_path}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading graph: {e}")
            return False

    def load_logbook(self, logbook_path: Path) -> bool:
        """Load and parse the execution logbook."""
        try:
            with open(logbook_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                self.errors.append("Empty logbook file")
                return False

            # Parse execution records
            # Support various logbook formats
            entries = data.get("entries", data.get("executions", data.get("tasks", [])))

            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        task_id = str(entry.get("task_id", entry.get("id", entry.get("task", ""))))
                        if task_id:
                            self.execution_records[task_id] = {
                                "task_id": task_id,
                                "started": self._parse_timestamp(
                                    entry.get("started", entry.get("start_time", entry.get("started_at")))
                                ),
                                "completed": self._parse_timestamp(
                                    entry.get("completed", entry.get("end_time", entry.get("completed_at", entry.get("finished"))))
                                ),
                                "status": entry.get("status", "unknown"),
                                "raw": entry
                            }
            elif isinstance(entries, dict):
                for task_id, entry_data in entries.items():
                    task_id = str(task_id)
                    if isinstance(entry_data, dict):
                        self.execution_records[task_id] = {
                            "task_id": task_id,
                            "started": self._parse_timestamp(
                                entry_data.get("started", entry_data.get("start_time"))
                            ),
                            "completed": self._parse_timestamp(
                                entry_data.get("completed", entry_data.get("end_time", entry_data.get("finished")))
                            ),
                            "status": entry_data.get("status", "unknown"),
                            "raw": entry_data
                        }

            if not self.execution_records:
                self.warnings.append("No execution records found in logbook")

            return True

        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error in logbook: {e}")
            return False
        except FileNotFoundError:
            self.errors.append(f"Logbook file not found: {logbook_path}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading logbook: {e}")
            return False

    def _parse_timestamp(self, ts: Any) -> Optional[datetime]:
        """Parse various timestamp formats into datetime."""
        if ts is None:
            return None

        if isinstance(ts, datetime):
            return ts

        if isinstance(ts, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(ts)

        if isinstance(ts, str):
            # Try common ISO formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue

            # Try parsing with timezone offset
            try:
                # Handle ISO format with timezone
                if "+" in ts or ts.endswith("Z"):
                    clean_ts = ts.replace("Z", "+00:00")
                    return datetime.fromisoformat(clean_ts)
            except ValueError:
                pass

        return None

    def verify_order(self) -> bool:
        """
        Verify execution order: dependency.completed < current_task.started.
        Returns True if order respected, False if violations found.
        """
        self.violations = []

        for task_id in self.execution_records:
            task_record = self.execution_records[task_id]
            task_started = task_record.get("started")

            if not task_started:
                self.warnings.append(f"Task {task_id}: No start time recorded")
                continue

            # Get dependencies from graph
            dependencies = self.reverse_adjacency.get(task_id, [])

            for dep_id in dependencies:
                dep_record = self.execution_records.get(dep_id)

                if not dep_record:
                    # Dependency wasn't executed - could be an issue
                    self.warnings.append(
                        f"Task {task_id}: Dependency {dep_id} has no execution record"
                    )
                    continue

                dep_completed = dep_record.get("completed")

                if not dep_completed:
                    self.warnings.append(
                        f"Task {task_id}: Dependency {dep_id} has no completion time"
                    )
                    continue

                # Core validation: dependency must complete before dependent starts
                if dep_completed > task_started:
                    violation = {
                        "task_id": task_id,
                        "dependency_id": dep_id,
                        "task_started": task_started.isoformat() if task_started else None,
                        "dependency_completed": dep_completed.isoformat() if dep_completed else None,
                        "violation_type": "ORDER_VIOLATION",
                        "message": (
                            f"Task {task_id} started at {task_started.isoformat()} "
                            f"but dependency {dep_id} completed at {dep_completed.isoformat()}"
                        ),
                        "time_gap_seconds": (task_started - dep_completed).total_seconds()
                    }
                    self.violations.append(violation)

        return len(self.violations) == 0

    def get_execution_summary(self) -> dict:
        """Get summary of execution analysis."""
        executed_tasks = set(self.execution_records.keys())
        graph_tasks = set(self.nodes.keys())

        missing_from_logbook = graph_tasks - executed_tasks
        extra_in_logbook = executed_tasks - graph_tasks

        # Calculate execution timeline
        all_starts = [
            r["started"] for r in self.execution_records.values()
            if r.get("started")
        ]
        all_completions = [
            r["completed"] for r in self.execution_records.values()
            if r.get("completed")
        ]

        earliest_start = min(all_starts) if all_starts else None
        latest_completion = max(all_completions) if all_completions else None
        total_duration = None
        if earliest_start and latest_completion:
            total_duration = (latest_completion - earliest_start).total_seconds()

        return {
            "graph_tasks": len(graph_tasks),
            "executed_tasks": len(executed_tasks),
            "missing_from_logbook": sorted(missing_from_logbook),
            "extra_in_logbook": sorted(extra_in_logbook),
            "total_dependencies_checked": sum(len(self.reverse_adjacency.get(b, [])) for b in executed_tasks),
            "earliest_start": earliest_start.isoformat() if earliest_start else None,
            "latest_completion": latest_completion.isoformat() if latest_completion else None,
            "total_duration_seconds": total_duration
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("EXECUTION ORDER VERIFICATION REPORT")
        lines.append("=" * 60)

        if self.errors:
            lines.append("")
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
            return "\n".join(lines)

        # Summary
        summary = self.get_execution_summary()
        lines.append(f"Graph tasks: {summary['graph_tasks']}")
        lines.append(f"Executed tasks: {summary['executed_tasks']}")
        lines.append(f"Dependencies checked: {summary['total_dependencies_checked']}")

        if summary.get("total_duration_seconds"):
            duration_hrs = summary["total_duration_seconds"] / 3600
            lines.append(f"Total execution time: {duration_hrs:.2f} hours")

        # Status
        lines.append("")
        lines.append("-" * 40)
        if self.violations:
            lines.append(f"STATUS: FAILED - {len(self.violations)} ORDER VIOLATION(S) DETECTED")
        else:
            lines.append("STATUS: PASSED - All dependencies respected")

        # Violations
        if self.violations:
            lines.append("")
            lines.append("=" * 60)
            lines.append("VIOLATIONS:")
            lines.append("-" * 40)
            for i, v in enumerate(self.violations, 1):
                lines.append(f"\n  [{i}] {v['message']}")
                lines.append(f"      Gap: {abs(v['time_gap_seconds']):.1f} seconds")
                if self.verbose:
                    lines.append(f"      Task started: {v['task_started']}")
                    lines.append(f"      Dependency completed: {v['dependency_completed']}")

        # Warnings
        if self.warnings:
            lines.append("")
            lines.append("=" * 60)
            lines.append("WARNINGS:")
            lines.append("-" * 40)
            for warning in self.warnings[:20]:  # Limit warnings shown
                lines.append(f"  - {warning}")
            if len(self.warnings) > 20:
                lines.append(f"  ... and {len(self.warnings) - 20} more warnings")

        # Missing tasks
        if summary["missing_from_logbook"]:
            lines.append("")
            lines.append("=" * 60)
            lines.append("TASKS NOT EXECUTED (in graph but not in logbook):")
            lines.append("-" * 40)
            for task in sorted(summary["missing_from_logbook"])[:20]:
                lines.append(f"  - {task}")
            if len(summary["missing_from_logbook"]) > 20:
                lines.append(f"  ... and {len(summary['missing_from_logbook']) - 20} more")

        # Verbose: all execution records
        if self.verbose and self.execution_records:
            lines.append("")
            lines.append("=" * 60)
            lines.append("EXECUTION TIMELINE:")
            lines.append("-" * 40)

            # Sort by start time
            sorted_records = sorted(
                self.execution_records.items(),
                key=lambda x: x[1].get("started") or datetime.min
            )

            for task_id, record in sorted_records:
                started = record.get("started")
                completed = record.get("completed")
                status = record.get("status", "?")
                deps = self.reverse_adjacency.get(task_id, [])
                deps_str = f" (deps: {', '.join(deps[:3])}{'...' if len(deps) > 3 else ''})" if deps else ""

                if started and completed:
                    duration = (completed - started).total_seconds()
                    lines.append(
                        f"  {task_id}: {started.strftime('%H:%M:%S')} -> "
                        f"{completed.strftime('%H:%M:%S')} ({duration:.1f}s) [{status}]{deps_str}"
                    )
                elif started:
                    lines.append(f"  {task_id}: {started.strftime('%H:%M:%S')} -> ? [{status}]{deps_str}")
                else:
                    lines.append(f"  {task_id}: ? -> ? [{status}]{deps_str}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        summary = self.get_execution_summary()

        output = {
            "status": "FAILED" if self.violations else "PASSED",
            "order_respected": len(self.violations) == 0,
            "summary": summary,
            "violations": self.violations,
            "violation_count": len(self.violations),
            "warnings": self.warnings,
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "execution_records": {
                task_id: {
                    "started": rec["started"].isoformat() if rec.get("started") else None,
                    "completed": rec["completed"].isoformat() if rec.get("completed") else None,
                    "status": rec.get("status"),
                    "dependencies": self.reverse_adjacency.get(task_id, [])
                }
                for task_id, rec in self.execution_records.items()
            } if self.verbose else {}
        }

        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Verify tasks executed in dependency order",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - Order respected (all dependencies completed before dependents started)
  1 - Violations detected (some tasks started before dependencies completed)
  2 - File/parse error

Examples:
  %(prog)s logbook.yaml graph.yaml                    # Basic verification
  %(prog)s .task/logbook.yaml .task/graph.yaml -v  # Verbose timeline
  %(prog)s logbook.yaml graph.yaml --format=json      # JSON for CI

Validation rule: For each task B with dependencies D1, D2, ...:
  D1.completed < B.started AND D2.completed < B.started AND ...
        """
    )

    parser.add_argument(
        "logbook_file",
        help="Path to execution logbook (.yaml)"
    )

    parser.add_argument(
        "graph_file",
        help="Path to dependency graph (.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with execution timeline"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    logbook_path = Path(args.logbook_file)
    graph_path = Path(args.graph_file)

    # Check files exist
    if not logbook_path.exists():
        print(f"Error: Logbook file not found: {logbook_path}", file=sys.stderr)
        sys.exit(2)

    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}", file=sys.stderr)
        sys.exit(2)

    # Run verification
    verifier = ExecutionOrderVerifier(verbose=args.verbose)

    if not verifier.load_graph(graph_path):
        if args.format == "json":
            print(json.dumps({"error": verifier.errors, "status": "LOAD_ERROR"}, indent=2))
        else:
            print(f"Failed to load graph: {'; '.join(verifier.errors)}", file=sys.stderr)
        sys.exit(2)

    if not verifier.load_logbook(logbook_path):
        if args.format == "json":
            print(json.dumps({"error": verifier.errors, "status": "LOAD_ERROR"}, indent=2))
        else:
            print(f"Failed to load logbook: {'; '.join(verifier.errors)}", file=sys.stderr)
        sys.exit(2)

    # Verify order
    order_respected = verifier.verify_order()

    # Output results
    if args.format == "json":
        print(verifier.format_json_output())
    else:
        print(verifier.format_text_output())

    # Exit code based on verification result
    if verifier.errors:
        sys.exit(2)
    elif order_respected:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
