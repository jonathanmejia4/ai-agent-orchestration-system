#!/usr/bin/env python3
"""
change_impact_analyzer.py - Change Impact Analyzer

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Analysis Tool

Purpose:
    Analyzes the impact of proposed changes across the system,
    identifies affected components, and assesses risk levels.

Usage:
    python3 change_impact_analyzer.py analyze --file src/main.py
    python3 change_impact_analyzer.py analyze --task task001
    python3 change_impact_analyzer.py report --work-order WO-2025-001
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class ImpactItem:
    """Represents an impact item."""
    item_type: str
    identifier: str
    impact_level: str  # high, medium, low
    description: str
    affected_by: str
    risk_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.item_type,
            "identifier": self.identifier,
            "impact_level": self.impact_level,
            "description": self.description,
            "affected_by": self.affected_by,
            "risk_factors": self.risk_factors
        }

@dataclass
class ImpactAnalysis:
    """Complete impact analysis result."""
    analysis_id: str
    timestamp: str
    target: str
    target_type: str
    overall_risk: str
    impacts: List[ImpactItem]
    recommendations: List[str]
    metrics: Dict

    def to_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "timestamp": self.timestamp,
            "target": self.target,
            "target_type": self.target_type,
            "overall_risk": self.overall_risk,
            "impacts": [i.to_dict() for i in self.impacts],
            "recommendations": self.recommendations,
            "metrics": self.metrics
        }

class ChangeImpactAnalyzer:
    """Analyzes change impacts across the system."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.dependency_graph: Dict[str, Set[str]] = {}
        self._build_dependency_graph()

    def _build_dependency_graph(self):
        """Build dependency graph from tasks and work orders."""
        # Build task dependencies
        for task_dir in self.base_path.glob("task*"):
            if not task_dir.is_dir():
                continue

            task_id = task_dir.name
            manifest = task_dir / "task.yaml"

            if manifest.exists() and HAS_YAML:
                try:
                    with open(manifest) as f:
                        data = yaml.safe_load(f) or {}

                    deps = data.get("dependencies", [])
                    self.dependency_graph[task_id] = set(
                        d if isinstance(d, str) else d.get("task_id", str(d))
                        for d in deps
                    )
                except Exception:
                    self.dependency_graph[task_id] = set()

    def analyze_file_change(self, file_path: str) -> ImpactAnalysis:
        """Analyze impact of a file change."""
        path = Path(file_path)
        impacts = []
        recommendations = []

        # Determine file type and location
        if "task" in str(path):
            # Task file change
            task_match = re.search(r'(task\d+)', str(path))
            if task_match:
                task_id = task_match.group(1)
                impacts.extend(self._analyze_task_impact(task_id))
                recommendations.append(f"Verify {task_id} tests pass")

        if "LogBook" in str(path):
            # LogBook change
            agent_match = re.search(r'LogBook/(\w+)/', str(path))
            if agent_match:
                agent = agent_match.group(1)
                impacts.append(ImpactItem(
                    item_type="agent_state",
                    identifier=agent,
                    impact_level="medium",
                    description=f"Agent {agent} state may be affected",
                    affected_by=str(path)
                ))
                recommendations.append(f"Verify {agent} agent state consistency")

        if "PLANNING" in str(path):
            # Planning/policy change
            impacts.append(ImpactItem(
                item_type="policy",
                identifier=str(path),
                impact_level="high",
                description="Policy/planning document change",
                affected_by=str(path),
                risk_factors=["May affect agent behavior", "Requires review"]
            ))
            recommendations.append("Review policy change with PM")

        if ".claude" in str(path):
            # Agent guideline change
            impacts.append(ImpactItem(
                item_type="guideline",
                identifier=str(path),
                impact_level="high",
                description="Agent guideline change",
                affected_by=str(path),
                risk_factors=["Affects agent behavior directly"]
            ))
            recommendations.append("All agents should acknowledge guideline change")

        # Determine overall risk
        overall_risk = self._calculate_overall_risk(impacts)

        return ImpactAnalysis(
            analysis_id=f"IMP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            target=str(file_path),
            target_type="file",
            overall_risk=overall_risk,
            impacts=impacts,
            recommendations=recommendations,
            metrics={
                "total_impacts": len(impacts),
                "high_impacts": sum(1 for i in impacts if i.impact_level == "high"),
                "medium_impacts": sum(1 for i in impacts if i.impact_level == "medium"),
                "low_impacts": sum(1 for i in impacts if i.impact_level == "low")
            }
        )

    def analyze_task_change(self, task_id: str) -> ImpactAnalysis:
        """Analyze impact of a task change."""
        impacts = self._analyze_task_impact(task_id)
        recommendations = []

        # Add standard recommendations
        recommendations.append(f"Run all tests for {task_id}")
        recommendations.append("Verify dependent tasks are not broken")

        if any(i.impact_level == "high" for i in impacts):
            recommendations.append("Consider staging deployment")
            recommendations.append("Prepare rollback plan")

        overall_risk = self._calculate_overall_risk(impacts)

        return ImpactAnalysis(
            analysis_id=f"IMP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            target=task_id,
            target_type="task",
            overall_risk=overall_risk,
            impacts=impacts,
            recommendations=recommendations,
            metrics={
                "total_impacts": len(impacts),
                "direct_dependents": sum(1 for i in impacts if "depends on" in i.description),
                "indirect_dependents": sum(1 for i in impacts if "indirect" in i.description.lower())
            }
        )

    def _analyze_task_impact(self, task_id: str) -> List[ImpactItem]:
        """Analyze what would be impacted by a task change."""
        impacts = []

        # Find direct dependents
        for other_task, deps in self.dependency_graph.items():
            if task_id in deps:
                impacts.append(ImpactItem(
                    item_type="task",
                    identifier=other_task,
                    impact_level="high",
                    description=f"{other_task} depends on {task_id}",
                    affected_by=task_id,
                    risk_factors=["Direct dependency", "May break if API changes"]
                ))

        # Find work orders referencing this task
        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if wo_queue.exists() and HAS_YAML:
            try:
                with open(wo_queue) as f:
                    data = yaml.safe_load(f) or {}

                for wo in data.get("work_orders", []):
                    if wo.get("task_id") == task_id:
                        status = wo.get("status", "UNKNOWN")
                        if status not in ("COMPLETED", "CANCELLED"):
                            impacts.append(ImpactItem(
                                item_type="work_order",
                                identifier=wo.get("work_order_id", "unknown"),
                                impact_level="medium",
                                description=f"Active work order on {task_id}",
                                affected_by=task_id,
                                risk_factors=[f"Status: {status}"]
                            ))
            except Exception:
                pass

        return impacts

    def analyze_work_order(self, work_order_id: str) -> ImpactAnalysis:
        """Analyze impact of a work order."""
        impacts = []
        recommendations = []

        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if not wo_queue.exists() or not HAS_YAML:
            return ImpactAnalysis(
                analysis_id=f"IMP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.utcnow().isoformat() + "Z",
                target=work_order_id,
                target_type="work_order",
                overall_risk="unknown",
                impacts=[],
                recommendations=["WO_QUEUE not found"],
                metrics={}
            )

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            wo = None
            for w in data.get("work_orders", []):
                if w.get("work_order_id") == work_order_id:
                    wo = w
                    break

            if not wo:
                return ImpactAnalysis(
                    analysis_id=f"IMP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    target=work_order_id,
                    target_type="work_order",
                    overall_risk="unknown",
                    impacts=[],
                    recommendations=[f"Work order {work_order_id} not found"],
                    metrics={}
                )

            # Analyze task impact
            task_id = wo.get("task_id")
            if task_id:
                task_impacts = self._analyze_task_impact(task_id)
                impacts.extend(task_impacts)
                recommendations.append(f"Verify impact on {task_id}")

            # Check dependencies
            for dep in wo.get("dependencies", []):
                dep_id = dep if isinstance(dep, str) else dep.get("work_order_id")
                impacts.append(ImpactItem(
                    item_type="work_order_dependency",
                    identifier=dep_id,
                    impact_level="medium",
                    description=f"Depends on {dep_id}",
                    affected_by=work_order_id
                ))

            # Check what depends on this WO
            for other_wo in data.get("work_orders", []):
                other_deps = other_wo.get("dependencies", [])
                for dep in other_deps:
                    dep_id = dep if isinstance(dep, str) else dep.get("work_order_id")
                    if dep_id == work_order_id:
                        impacts.append(ImpactItem(
                            item_type="dependent_work_order",
                            identifier=other_wo.get("work_order_id"),
                            impact_level="high",
                            description=f"{other_wo.get('work_order_id')} depends on this",
                            affected_by=work_order_id,
                            risk_factors=["Blocking dependency"]
                        ))

        except Exception as e:
            recommendations.append(f"Error analyzing: {e}")

        overall_risk = self._calculate_overall_risk(impacts)

        return ImpactAnalysis(
            analysis_id=f"IMP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            target=work_order_id,
            target_type="work_order",
            overall_risk=overall_risk,
            impacts=impacts,
            recommendations=recommendations,
            metrics={
                "total_impacts": len(impacts),
                "blocking_count": sum(1 for i in impacts if "blocking" in str(i.risk_factors).lower())
            }
        )

    def _calculate_overall_risk(self, impacts: List[ImpactItem]) -> str:
        """Calculate overall risk level."""
        if not impacts:
            return "low"

        high_count = sum(1 for i in impacts if i.impact_level == "high")
        medium_count = sum(1 for i in impacts if i.impact_level == "medium")

        if high_count >= 3:
            return "critical"
        elif high_count >= 1:
            return "high"
        elif medium_count >= 3:
            return "medium"
        else:
            return "low"

def main():
    parser = argparse.ArgumentParser(description="Change Impact Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze change impact")
    analyze_parser.add_argument("--file", help="File path to analyze")
    analyze_parser.add_argument("--task", help="Task ID to analyze")
    analyze_parser.add_argument("--work-order", help="Work order ID to analyze")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate impact report")
    report_parser.add_argument("--work-order", required=True)
    report_parser.add_argument("--output", "-o", help="Output file")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    analyzer = ChangeImpactAnalyzer()

    if args.command == "analyze":
        if args.file:
            analysis = analyzer.analyze_file_change(args.file)
        elif args.task:
            analysis = analyzer.analyze_task_change(args.task)
        elif args.work_order:
            analysis = analyzer.analyze_work_order(args.work_order)
        else:
            print("Specify --file, --task, or --work-order")
            return 1

        if args.format == "json":
            print(json.dumps(analysis.to_dict(), indent=2))
        else:
            print(f"\nImpact Analysis: {analysis.analysis_id}")
            print("=" * 50)
            print(f"Target: {analysis.target} ({analysis.target_type})")
            print(f"Overall Risk: {analysis.overall_risk.upper()}")
            print(f"Total Impacts: {len(analysis.impacts)}")

            if analysis.impacts:
                print("\nImpacted Items:")
                for impact in analysis.impacts:
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(impact.impact_level, "⚪")
                    print(f"  {icon} {impact.identifier}: {impact.description}")

            if analysis.recommendations:
                print("\nRecommendations:")
                for rec in analysis.recommendations:
                    print(f"  - {rec}")

    elif args.command == "report":
        analysis = analyzer.analyze_work_order(args.work_order)

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(analysis.to_dict(), f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(analysis.to_dict(), indent=2))

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
