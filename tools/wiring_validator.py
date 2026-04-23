#!/usr/bin/env python3
"""
wiring_validator.py - the system Wiring Validator

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - System Integrity

Purpose:
    Validates the "wiring" between a system components - ensuring
    all references, dependencies, and integrations are valid.

Usage:
    python3 wiring_validator.py validate
    python3 wiring_validator.py check-integration agent-workflow
    python3 wiring_validator.py report
"""

import argparse
import json
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
class WiringIssue:
    """Represents a wiring issue."""
    issue_id: str
    category: str
    severity: str
    source: str
    target: str
    description: str
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "severity": self.severity,
            "source": self.source,
            "target": self.target,
            "description": self.description,
            "recommendation": self.recommendation
        }

class WiringValidator:
    """Validates a system component wiring."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.issues: List[WiringIssue] = []

    def validate_all(self) -> List[WiringIssue]:
        """Run all wiring validations."""
        self.issues = []

        validators = [
            self._validate_agent_wiring,
            self._validate_task_dependencies,
            self._validate_work_order_references,
            self._validate_schema_references,
            self._validate_tool_integrations,
            self._validate_workflow_wiring,
            self._validate_logbook_structure,
        ]

        for validator in validators:
            try:
                issues = validator()
                self.issues.extend(issues)
            except Exception as e:
                self.issues.append(WiringIssue(
                    issue_id=f"ERR-{len(self.issues)+1:03d}",
                    category="validation_error",
                    severity="medium",
                    source=validator.__name__,
                    target="",
                    description=f"Validation error: {e}"
                ))

        return self.issues

    def _validate_agent_wiring(self) -> List[WiringIssue]:
        """Validate agent interconnections."""
        issues = []

        # Required agent directories
        required_agents = ["pm", "builder", "critic", "planner"]

        for agent in required_agents:
            agent_dir = self.base_path / "LogBook" / agent
            if not agent_dir.exists():
                issues.append(WiringIssue(
                    issue_id=f"WIRE-{len(issues)+1:03d}",
                    category="missing_agent",
                    severity="high",
                    source="LogBook",
                    target=f"LogBook/{agent}",
                    description=f"Agent directory missing: {agent}",
                    recommendation=f"Create LogBook/{agent}/ directory"
                ))
                continue

            # Check for required files
            state_file = agent_dir / "STATE.md"
            if not state_file.exists():
                issues.append(WiringIssue(
                    issue_id=f"WIRE-{len(issues)+1:03d}",
                    category="missing_state",
                    severity="high",
                    source=f"LogBook/{agent}",
                    target=f"LogBook/{agent}/STATE.md",
                    description=f"Agent state file missing for {agent}",
                    recommendation=f"Create STATE.md for {agent}"
                ))

        # Check PM has required operational files
        pm_required = ["WO_QUEUE.yaml"]
        for required in pm_required:
            if not (self.base_path / "LogBook/pm" / required).exists():
                issues.append(WiringIssue(
                    issue_id=f"WIRE-{len(issues)+1:03d}",
                    category="missing_pm_file",
                    severity="high",
                    source="LogBook/pm",
                    target=f"LogBook/pm/{required}",
                    description=f"PM required file missing: {required}",
                    recommendation=f"Create {required}"
                ))

        return issues

    def _validate_task_dependencies(self) -> List[WiringIssue]:
        """Validate task dependency wiring."""
        issues = []

        if not HAS_YAML:
            return issues

        task_ids = set()
        task_deps = {}

        for task_dir in self.base_path.glob("task*"):
            if not task_dir.is_dir():
                continue

            task_id = task_dir.name
            task_ids.add(task_id)

            manifest = task_dir / "task.yaml"
            if manifest.exists():
                try:
                    with open(manifest) as f:
                        data = yaml.safe_load(f) or {}
                    deps = data.get("dependencies", [])
                    task_deps[task_id] = [
                        d if isinstance(d, str) else d.get("task_id", str(d))
                        for d in deps
                    ]
                except Exception:
                    pass

        # Check dependencies exist
        for task_id, deps in task_deps.items():
            for dep in deps:
                if dep not in task_ids:
                    issues.append(WiringIssue(
                        issue_id=f"WIRE-{len(issues)+1:03d}",
                        category="missing_dependency",
                        severity="high",
                        source=task_id,
                        target=dep,
                        description=f"Task {task_id} depends on non-existent {dep}",
                        recommendation=f"Create {dep} or remove dependency"
                    ))

        # Check for circular dependencies
        def has_cycle(task: str, visited: Set, stack: Set) -> Optional[List[str]]:
            visited.add(task)
            stack.add(task)

            for dep in task_deps.get(task, []):
                if dep not in visited:
                    cycle = has_cycle(dep, visited, stack)
                    if cycle:
                        return [task] + cycle
                elif dep in stack:
                    return [task, dep]

            stack.remove(task)
            return None

        for task_id in task_ids:
            cycle = has_cycle(task_id, set(), set())
            if cycle:
                issues.append(WiringIssue(
                    issue_id=f"WIRE-{len(issues)+1:03d}",
                    category="circular_dependency",
                    severity="critical",
                    source=cycle[0],
                    target=" -> ".join(cycle),
                    description=f"Circular dependency detected",
                    recommendation="Remove circular dependency"
                ))
                break  # Only report once

        return issues

    def _validate_work_order_references(self) -> List[WiringIssue]:
        """Validate work order reference wiring."""
        issues = []

        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if not wo_queue.exists() or not HAS_YAML:
            return issues

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            wo_ids = set()
            for wo in data.get("work_orders", []):
                wo_id = wo.get("work_order_id")
                if wo_id:
                    wo_ids.add(wo_id)

            for wo in data.get("work_orders", []):
                wo_id = wo.get("work_order_id", "unknown")

                # Check task reference
                task_id = wo.get("task_id")
                if task_id:
                    task_path = self.base_path / task_id
                    if not task_path.exists():
                        issues.append(WiringIssue(
                            issue_id=f"WIRE-{len(issues)+1:03d}",
                            category="invalid_task_ref",
                            severity="medium",
                            source=wo_id,
                            target=task_id,
                            description=f"WO references non-existent task",
                            recommendation=f"Create {task_id} or update reference"
                        ))

                # Check dependency references
                for dep in wo.get("dependencies", []):
                    dep_id = dep if isinstance(dep, str) else dep.get("work_order_id")
                    if dep_id and dep_id not in wo_ids:
                        issues.append(WiringIssue(
                            issue_id=f"WIRE-{len(issues)+1:03d}",
                            category="invalid_wo_dependency",
                            severity="high",
                            source=wo_id,
                            target=dep_id,
                            description=f"WO depends on non-existent WO",
                            recommendation="Remove invalid dependency"
                        ))

                # Check agent assignment
                agent = wo.get("agent")
                if agent and agent not in ["pm", "builder", "critic", "planner"]:
                    issues.append(WiringIssue(
                        issue_id=f"WIRE-{len(issues)+1:03d}",
                        category="invalid_agent",
                        severity="medium",
                        source=wo_id,
                        target=agent,
                        description=f"WO assigned to unknown agent",
                        recommendation="Use valid agent: pm, builder, critic, planner"
                    ))

        except Exception:
            pass

        return issues

    def _validate_schema_references(self) -> List[WiringIssue]:
        """Validate schema reference wiring."""
        issues = []

        schema_dir = self.base_path / "PLANNING/schemas"
        if not schema_dir.exists():
            return issues

        available_schemas = {f.stem for f in schema_dir.glob("*.yaml")}

        # Check if commonly referenced schemas exist
        expected_schemas = [
            "work_order_queue_schema",
            "task_schema",
            "verdict_schema"
        ]

        for schema in expected_schemas:
            if schema not in available_schemas:
                issues.append(WiringIssue(
                    issue_id=f"WIRE-{len(issues)+1:03d}",
                    category="missing_schema",
                    severity="medium",
                    source="PLANNING/schemas",
                    target=f"{schema}.yaml",
                    description=f"Expected schema missing",
                    recommendation=f"Create {schema}.yaml"
                ))

        return issues

    def _validate_tool_integrations(self) -> List[WiringIssue]:
        """Validate tool integration wiring."""
        issues = []

        tools_dir = self.base_path / "tools"
        if not tools_dir.exists():
            return issues

        # Check tools are executable
        for tool in tools_dir.glob("*.py"):
            content = tool.read_text()

            # Check for proper shebang
            if not content.startswith("#!/usr/bin/env python3"):
                issues.append(WiringIssue(
                    issue_id=f"WIRE-{len(issues)+1:03d}",
                    category="tool_shebang",
                    severity="low",
                    source=f"tools/{tool.name}",
                    target="",
                    description="Missing or incorrect shebang",
                    recommendation="Add #!/usr/bin/env python3"
                ))

            # Check for main function
            if "if __name__ ==" not in content:
                issues.append(WiringIssue(
                    issue_id=f"WIRE-{len(issues)+1:03d}",
                    category="tool_entrypoint",
                    severity="low",
                    source=f"tools/{tool.name}",
                    target="",
                    description="No main entrypoint",
                    recommendation="Add if __name__ == '__main__' block"
                ))

        return issues

    def _validate_workflow_wiring(self) -> List[WiringIssue]:
        """Validate GitHub workflow wiring."""
        issues = []

        workflows_dir = self.base_path / ".github/workflows"
        if not workflows_dir.exists():
            return issues

        for workflow in workflows_dir.glob("*.yml"):
            try:
                if HAS_YAML:
                    with open(workflow) as f:
                        data = yaml.safe_load(f) or {}

                    # Check for required fields
                    if "name" not in data:
                        issues.append(WiringIssue(
                            issue_id=f"WIRE-{len(issues)+1:03d}",
                            category="workflow_name",
                            severity="low",
                            source=f".github/workflows/{workflow.name}",
                            target="",
                            description="Workflow missing name",
                            recommendation="Add name field"
                        ))

                    if "on" not in data:
                        issues.append(WiringIssue(
                            issue_id=f"WIRE-{len(issues)+1:03d}",
                            category="workflow_trigger",
                            severity="medium",
                            source=f".github/workflows/{workflow.name}",
                            target="",
                            description="Workflow missing trigger",
                            recommendation="Add 'on' field with triggers"
                        ))

            except Exception:
                pass

        return issues

    def _validate_logbook_structure(self) -> List[WiringIssue]:
        """Validate LogBook structure wiring."""
        issues = []

        logbook = self.base_path / "LogBook"
        if not logbook.exists():
            issues.append(WiringIssue(
                issue_id=f"WIRE-{len(issues)+1:03d}",
                category="missing_logbook",
                severity="critical",
                source=".",
                target="LogBook",
                description="LogBook directory missing",
                recommendation="Create LogBook directory structure"
            ))
            return issues

        # Check README exists
        if not (logbook / "README.md").exists():
            issues.append(WiringIssue(
                issue_id=f"WIRE-{len(issues)+1:03d}",
                category="missing_readme",
                severity="low",
                source="LogBook",
                target="LogBook/README.md",
                description="LogBook README missing",
                recommendation="Create README.md documenting structure"
            ))

        return issues

    def generate_report(self) -> Dict:
        """Generate wiring validation report."""
        if not self.issues:
            self.validate_all()

        by_category = {}
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for issue in self.issues:
            cat = issue.category
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

        return {
            "report_id": f"WIRING-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_issues": len(self.issues),
            "by_severity": by_severity,
            "by_category": by_category,
            "issues": [i.to_dict() for i in self.issues],
            "status": "pass" if len(self.issues) == 0 else "fail"
        }

def main():
    parser = argparse.ArgumentParser(description="the system Wiring Validator")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate all wiring")
    validate_parser.add_argument("--strict", action="store_true")

    # Check command
    check_parser = subparsers.add_parser("check-integration", help="Check specific integration")
    check_parser.add_argument("integration", choices=[
        "agent-workflow", "task-dependencies", "work-orders", "schemas", "tools"
    ])

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--output", "-o", help="Output file")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    validator = WiringValidator()

    if args.command == "validate":
        issues = validator.validate_all()

        if args.format == "json":
            print(json.dumps([i.to_dict() for i in issues], indent=2))
        else:
            print("\nWiring Validation Results")
            print("=" * 50)

            if issues:
                print(f"\nFound {len(issues)} wiring issues:")
                for issue in issues:
                    severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity, "⚪")
                    print(f"\n{severity_icon} [{issue.severity.upper()}] {issue.issue_id}")
                    print(f"   Category: {issue.category}")
                    print(f"   {issue.source} -> {issue.target}")
                    print(f"   {issue.description}")
            else:
                print("\n✓ All wiring validated successfully")

        if args.strict and issues:
            return 1

    elif args.command == "check-integration":
        # Run specific validator
        check_map = {
            "agent-workflow": validator._validate_agent_wiring,
            "task-dependencies": validator._validate_task_dependencies,
            "work-orders": validator._validate_work_order_references,
            "schemas": validator._validate_schema_references,
            "tools": validator._validate_tool_integrations
        }

        checker = check_map.get(args.integration)
        if checker:
            issues = checker()
            print(f"\n{args.integration} check: {len(issues)} issues found")
            for issue in issues:
                print(f"  - {issue.description}")

    elif args.command == "report":
        report = validator.generate_report()

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to {args.output}")
        elif args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            print(f"\nWiring Report: {report['report_id']}")
            print("=" * 50)
            print(f"Total Issues: {report['total_issues']}")
            print(f"Status: {report['status'].upper()}")
            print(f"\nBy Severity:")
            for sev, count in report['by_severity'].items():
                print(f"  {sev}: {count}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
