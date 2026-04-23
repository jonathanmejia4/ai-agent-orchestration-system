#!/usr/bin/env python3
"""
compliance_reporter.py - Compliance Reporter

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Compliance

Purpose:
    Generates compliance reports for the system,
    tracks policy adherence, and identifies violations.

Usage:
    python3 compliance_reporter.py report
    python3 compliance_reporter.py check --category agent-boundaries
    python3 compliance_reporter.py export --format html
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class ComplianceCheck:
    """Represents a compliance check result."""
    check_id: str
    category: str
    name: str
    status: str  # pass, fail, warning, skipped
    severity: str
    details: str
    evidence: List[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "severity": self.severity,
            "details": self.details,
            "evidence": self.evidence,
            "recommendation": self.recommendation
        }

class ComplianceReporter:
    """Generates the system compliance reports."""

    CATEGORIES = [
        "agent-boundaries",
        "state-management",
        "audit-trail",
        "access-control",
        "schema-validation",
        "workflow-compliance"
    ]

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.checks: List[ComplianceCheck] = []

    def run_all_checks(self) -> List[ComplianceCheck]:
        """Run all compliance checks."""
        self.checks = []

        check_methods = [
            self._check_agent_boundaries,
            self._check_state_management,
            self._check_audit_trail,
            self._check_access_control,
            self._check_schema_validation,
            self._check_workflow_compliance,
        ]

        for method in check_methods:
            try:
                checks = method()
                self.checks.extend(checks)
            except Exception as e:
                self.checks.append(ComplianceCheck(
                    check_id=f"ERR-{len(self.checks)+1:03d}",
                    category="error",
                    name=method.__name__,
                    status="fail",
                    severity="medium",
                    details=f"Check failed: {e}"
                ))

        return self.checks

    def _check_agent_boundaries(self) -> List[ComplianceCheck]:
        """Check agent boundary compliance."""
        checks = []

        # Check PM directory is not modified by other agents
        pm_dir = self.base_path / "LogBook/pm"
        if pm_dir.exists():
            checks.append(ComplianceCheck(
                check_id="COMP-001",
                category="agent-boundaries",
                name="PM Directory Exists",
                status="pass",
                severity="high",
                details="PM LogBook directory exists"
            ))
        else:
            checks.append(ComplianceCheck(
                check_id="COMP-001",
                category="agent-boundaries",
                name="PM Directory Exists",
                status="fail",
                severity="high",
                details="PM LogBook directory missing",
                recommendation="Create LogBook/pm/ directory"
            ))

        # Check each agent has own directory
        agents = ["builder", "critic", "planner"]
        for agent in agents:
            agent_dir = self.base_path / "LogBook" / agent
            status = "pass" if agent_dir.exists() else "fail"
            checks.append(ComplianceCheck(
                check_id=f"COMP-00{len(checks)+1}",
                category="agent-boundaries",
                name=f"{agent.title()} Directory Exists",
                status=status,
                severity="high",
                details=f"{agent} LogBook directory {'exists' if status == 'pass' else 'missing'}"
            ))

        return checks

    def _check_state_management(self) -> List[ComplianceCheck]:
        """Check state management compliance."""
        checks = []

        # Check for STATE.md files
        agents = ["pm", "builder", "critic", "planner"]
        for agent in agents:
            state_file = self.base_path / "LogBook" / agent / "STATE.md"
            status = "pass" if state_file.exists() else "fail"
            checks.append(ComplianceCheck(
                check_id=f"COMP-S{len(checks)+1:02d}",
                category="state-management",
                name=f"{agent.title()} State File",
                status=status,
                severity="high",
                details=f"STATE.md {'exists' if status == 'pass' else 'missing'} for {agent}",
                recommendation="" if status == "pass" else f"Create LogBook/{agent}/STATE.md"
            ))

        # Check WO_QUEUE exists
        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        status = "pass" if wo_queue.exists() else "fail"
        checks.append(ComplianceCheck(
            check_id=f"COMP-S{len(checks)+1:02d}",
            category="state-management",
            name="Work Order Queue",
            status=status,
            severity="high",
            details=f"WO_QUEUE.yaml {'exists' if status == 'pass' else 'missing'}"
        ))

        return checks

    def _check_audit_trail(self) -> List[ComplianceCheck]:
        """Check audit trail compliance."""
        checks = []

        # Check for execution log
        exec_log = self.base_path / "LogBook/builder/execution_log.yaml"
        status = "pass" if exec_log.exists() else "warning"
        checks.append(ComplianceCheck(
            check_id="COMP-A01",
            category="audit-trail",
            name="Execution Log",
            status=status,
            severity="medium",
            details=f"Builder execution log {'exists' if status == 'pass' else 'missing'}"
        ))

        # Check for verdict log
        verdict_log = self.base_path / "LogBook/critic/verdict_log.yaml"
        status = "pass" if verdict_log.exists() else "warning"
        checks.append(ComplianceCheck(
            check_id="COMP-A02",
            category="audit-trail",
            name="Verdict Log",
            status=status,
            severity="medium",
            details=f"Critic verdict log {'exists' if status == 'pass' else 'missing'}"
        ))

        # Check for planning log
        planning_log = self.base_path / "LogBook/planner/planning_log.yaml"
        status = "pass" if planning_log.exists() else "warning"
        checks.append(ComplianceCheck(
            check_id="COMP-A03",
            category="audit-trail",
            name="Planning Log",
            status=status,
            severity="medium",
            details=f"Planner planning log {'exists' if status == 'pass' else 'missing'}"
        ))

        return checks

    def _check_access_control(self) -> List[ComplianceCheck]:
        """Check access control compliance."""
        checks = []

        # Check for sensitive files
        sensitive_patterns = [".env", "credentials", "secrets", "*.key", "*.pem"]
        found_sensitive = []

        for pattern in sensitive_patterns:
            for f in self.base_path.rglob(pattern):
                if f.is_file() and ".git" not in str(f):
                    found_sensitive.append(str(f))

        if found_sensitive:
            checks.append(ComplianceCheck(
                check_id="COMP-AC01",
                category="access-control",
                name="Sensitive Files Check",
                status="warning",
                severity="high",
                details=f"Found {len(found_sensitive)} potentially sensitive files",
                evidence=found_sensitive[:5],
                recommendation="Ensure sensitive files are in .gitignore"
            ))
        else:
            checks.append(ComplianceCheck(
                check_id="COMP-AC01",
                category="access-control",
                name="Sensitive Files Check",
                status="pass",
                severity="high",
                details="No sensitive files found in repository"
            ))

        # Check .gitignore exists
        gitignore = self.base_path / ".gitignore"
        status = "pass" if gitignore.exists() else "warning"
        checks.append(ComplianceCheck(
            check_id="COMP-AC02",
            category="access-control",
            name="Gitignore Present",
            status=status,
            severity="medium",
            details=f".gitignore {'exists' if status == 'pass' else 'missing'}"
        ))

        return checks

    def _check_schema_validation(self) -> List[ComplianceCheck]:
        """Check schema validation compliance."""
        checks = []

        schema_dir = self.base_path / "PLANNING/schemas"
        if not schema_dir.exists():
            checks.append(ComplianceCheck(
                check_id="COMP-SC01",
                category="schema-validation",
                name="Schema Directory",
                status="fail",
                severity="high",
                details="Schema directory missing",
                recommendation="Create PLANNING/schemas/ directory"
            ))
            return checks

        schemas = list(schema_dir.glob("*.yaml"))
        checks.append(ComplianceCheck(
            check_id="COMP-SC01",
            category="schema-validation",
            name="Schema Directory",
            status="pass",
            severity="high",
            details=f"Found {len(schemas)} schema files"
        ))

        # Validate each schema
        if HAS_YAML:
            invalid = []
            for schema in schemas:
                try:
                    with open(schema) as f:
                        yaml.safe_load(f)
                except Exception as e:
                    invalid.append(f"{schema.name}: {e}")

            if invalid:
                checks.append(ComplianceCheck(
                    check_id="COMP-SC02",
                    category="schema-validation",
                    name="Schema Validity",
                    status="fail",
                    severity="high",
                    details=f"{len(invalid)} invalid schemas",
                    evidence=invalid[:5]
                ))
            else:
                checks.append(ComplianceCheck(
                    check_id="COMP-SC02",
                    category="schema-validation",
                    name="Schema Validity",
                    status="pass",
                    severity="high",
                    details="All schemas are valid YAML"
                ))

        return checks

    def _check_workflow_compliance(self) -> List[ComplianceCheck]:
        """Check workflow compliance."""
        checks = []

        workflows_dir = self.base_path / ".github/workflows"
        if not workflows_dir.exists():
            checks.append(ComplianceCheck(
                check_id="COMP-WF01",
                category="workflow-compliance",
                name="Workflows Directory",
                status="warning",
                severity="medium",
                details="GitHub workflows directory missing"
            ))
            return checks

        workflows = list(workflows_dir.glob("*.yml"))
        checks.append(ComplianceCheck(
            check_id="COMP-WF01",
            category="workflow-compliance",
            name="Workflows Directory",
            status="pass",
            severity="medium",
            details=f"Found {len(workflows)} workflow files"
        ))

        return checks

    def generate_report(self) -> Dict:
        """Generate compliance report."""
        if not self.checks:
            self.run_all_checks()

        # Aggregate results
        by_status = {"pass": 0, "fail": 0, "warning": 0, "skipped": 0}
        by_category = {}
        by_severity = {"high": 0, "medium": 0, "low": 0}

        for check in self.checks:
            by_status[check.status] = by_status.get(check.status, 0) + 1
            by_category[check.category] = by_category.get(check.category, 0) + 1
            if check.status == "fail":
                by_severity[check.severity] = by_severity.get(check.severity, 0) + 1

        total = len(self.checks)
        passed = by_status.get("pass", 0)
        compliance_score = (passed / total * 100) if total > 0 else 0

        return {
            "report_id": f"COMPLIANCE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_checks": total,
                "passed": passed,
                "failed": by_status.get("fail", 0),
                "warnings": by_status.get("warning", 0),
                "compliance_score": round(compliance_score, 1)
            },
            "by_status": by_status,
            "by_category": by_category,
            "failed_by_severity": by_severity,
            "checks": [c.to_dict() for c in self.checks],
            "recommendations": self._get_recommendations()
        }

    def _get_recommendations(self) -> List[str]:
        """Get prioritized recommendations."""
        recommendations = []

        # High severity failures first
        for check in self.checks:
            if check.status == "fail" and check.severity == "high":
                if check.recommendation:
                    recommendations.append(check.recommendation)

        # Then medium severity
        for check in self.checks:
            if check.status == "fail" and check.severity == "medium":
                if check.recommendation:
                    recommendations.append(check.recommendation)

        # Then warnings
        for check in self.checks:
            if check.status == "warning":
                if check.recommendation:
                    recommendations.append(check.recommendation)

        return recommendations[:10]  # Top 10

    def export_html(self) -> str:
        """Export report as HTML."""
        report = self.generate_report()

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Compliance Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        .warning {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>Compliance Report</h1>
    <p>Generated: {report['generated_at']}</p>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Compliance Score:</strong> {report['summary']['compliance_score']}%</p>
        <p><strong>Total Checks:</strong> {report['summary']['total_checks']}</p>
        <p><span class="pass">Passed: {report['summary']['passed']}</span> |
           <span class="fail">Failed: {report['summary']['failed']}</span> |
           <span class="warning">Warnings: {report['summary']['warnings']}</span></p>
    </div>

    <h2>Checks</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Category</th>
            <th>Name</th>
            <th>Status</th>
            <th>Details</th>
        </tr>
"""

        for check in self.checks:
            status_class = check.status
            html += f"""        <tr>
            <td>{check.check_id}</td>
            <td>{check.category}</td>
            <td>{check.name}</td>
            <td class="{status_class}">{check.status.upper()}</td>
            <td>{check.details}</td>
        </tr>
"""

        html += """    </table>
</body>
</html>"""

        return html

def main():
    parser = argparse.ArgumentParser(description="Compliance Reporter")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate compliance report")
    report_parser.add_argument("--output", "-o", help="Output file")

    # Check command
    check_parser = subparsers.add_parser("check", help="Run specific checks")
    check_parser.add_argument("--category", choices=ComplianceReporter.CATEGORIES)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export report")
    export_parser.add_argument("--format", choices=["json", "html"], default="json")
    export_parser.add_argument("--output", "-o", help="Output file")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    reporter = ComplianceReporter()

    if args.command == "report":
        report = reporter.generate_report()

        if args.format == "json" or args.output:
            output = json.dumps(report, indent=2)
            if args.output:
                Path(args.output).write_text(output)
                print(f"Report saved to {args.output}")
            else:
                print(output)
        else:
            print(f"\nCompliance Report: {report['report_id']}")
            print("=" * 50)
            print(f"Compliance Score: {report['summary']['compliance_score']}%")
            print(f"Total Checks: {report['summary']['total_checks']}")
            print(f"Passed: {report['summary']['passed']}")
            print(f"Failed: {report['summary']['failed']}")
            print(f"Warnings: {report['summary']['warnings']}")

            if report['recommendations']:
                print("\nTop Recommendations:")
                for i, rec in enumerate(report['recommendations'][:5], 1):
                    print(f"  {i}. {rec}")

    elif args.command == "check":
        reporter.run_all_checks()

        if args.category:
            checks = [c for c in reporter.checks if c.category == args.category]
        else:
            checks = reporter.checks

        for check in checks:
            icon = {"pass": "✓", "fail": "✗", "warning": "⚠"}.get(check.status, "?")
            print(f"{icon} [{check.status.upper()}] {check.name}: {check.details}")

    elif args.command == "export":
        if args.format == "html":
            output = reporter.export_html()
        else:
            output = json.dumps(reporter.generate_report(), indent=2)

        if args.output:
            Path(args.output).write_text(output)
            print(f"Exported to {args.output}")
        else:
            print(output)

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
