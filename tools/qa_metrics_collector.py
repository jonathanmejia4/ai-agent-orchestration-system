#!/usr/bin/env python3
"""
the system QA Metrics Collector
Version: 1.0.0
Last Updated: 2025-12-25
Owner: PM
Classification: HIGH - Quality Assurance Tool

Collects and aggregates QA metrics across the system.
Tracks test coverage, code quality, and defect metrics.

Usage:
    python tools/qa_metrics_collector.py collect
    python tools/qa_metrics_collector.py report
    python tools/qa_metrics_collector.py trends --days 30
    python tools/qa_metrics_collector.py export --format json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import yaml

@dataclass
class TestMetrics:
    """Test execution metrics."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    pass_rate: float = 0.0

@dataclass
class CoverageMetrics:
    """Code coverage metrics."""
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    function_coverage: float = 0.0
    lines_covered: int = 0
    lines_total: int = 0
    uncovered_files: List[str] = field(default_factory=list)

@dataclass
class CodeQualityMetrics:
    """Code quality metrics."""
    total_issues: int = 0
    critical_issues: int = 0
    major_issues: int = 0
    minor_issues: int = 0
    code_smells: int = 0
    duplications: int = 0
    complexity_violations: int = 0

@dataclass
class DefectMetrics:
    """Defect tracking metrics."""
    total_defects: int = 0
    open_defects: int = 0
    closed_defects: int = 0
    critical_defects: int = 0
    defect_density: float = 0.0
    mean_time_to_fix_hours: float = 0.0

@dataclass
class QAReport:
    """Complete QA metrics report."""
    timestamp: str
    period_start: str
    period_end: str
    tests: TestMetrics
    coverage: CoverageMetrics
    quality: CodeQualityMetrics
    defects: DefectMetrics
    overall_score: float = 0.0
    grade: str = "F"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'tests': asdict(self.tests),
            'coverage': asdict(self.coverage),
            'quality': asdict(self.quality),
            'defects': asdict(self.defects),
            'overall_score': self.overall_score,
            'grade': self.grade
        }

class QAMetricsCollector:
    """Collects and aggregates QA metrics."""

    # Scoring weights
    WEIGHTS = {
        'test_pass_rate': 0.25,
        'coverage': 0.25,
        'quality': 0.25,
        'defects': 0.25
    }

    # Grade thresholds
    GRADES = [
        (90, 'A'),
        (80, 'B'),
        (70, 'C'),
        (60, 'D'),
        (0, 'F')
    ]

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the metrics collector."""
        self.project_root = project_root or Path.cwd()
        self.metrics_dir = self.project_root / ".qa_metrics"
        self.history_dir = self.metrics_dir / "history"
        self.reports_dir = self.project_root / "reports" / "qa"

        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def collect_test_metrics(self) -> TestMetrics:
        """Collect test execution metrics."""
        metrics = TestMetrics()

        # Try to read pytest results
        pytest_results = self.project_root / ".pytest_cache" / "results.json"
        if pytest_results.exists():
            with open(pytest_results, 'r') as f:
                data = json.load(f)
            metrics.total_tests = data.get('total', 0)
            metrics.passed = data.get('passed', 0)
            metrics.failed = data.get('failed', 0)
            metrics.skipped = data.get('skipped', 0)
            metrics.errors = data.get('errors', 0)
            metrics.duration_seconds = data.get('duration', 0.0)

        # Fallback: count test files
        if metrics.total_tests == 0:
            test_files = list(self.project_root.rglob("test_*.py"))
            test_files += list(self.project_root.rglob("*_test.py"))

            for test_file in test_files:
                content = test_file.read_text()
                test_count = len(re.findall(r'def test_', content))
                metrics.total_tests += test_count

        # Calculate pass rate
        if metrics.total_tests > 0:
            metrics.pass_rate = (metrics.passed / metrics.total_tests) * 100

        return metrics

    def collect_coverage_metrics(self) -> CoverageMetrics:
        """Collect code coverage metrics."""
        metrics = CoverageMetrics()

        # Try to read coverage.json
        coverage_file = self.project_root / "coverage.json"
        if coverage_file.exists():
            with open(coverage_file, 'r') as f:
                data = json.load(f)

            totals = data.get('totals', {})
            metrics.line_coverage = totals.get('percent_covered', 0.0)
            metrics.lines_covered = totals.get('covered_lines', 0)
            metrics.lines_total = totals.get('num_statements', 0)

            # Find uncovered files
            files = data.get('files', {})
            for filepath, file_data in files.items():
                if file_data.get('summary', {}).get('percent_covered', 100) < 50:
                    metrics.uncovered_files.append(filepath)

        # Try coverage.xml (Cobertura format)
        coverage_xml = self.project_root / "coverage.xml"
        if coverage_xml.exists() and metrics.line_coverage == 0:
            import xml.etree.ElementTree as ET
            tree = ET.parse(coverage_xml)
            root = tree.getroot()

            line_rate = root.get('line-rate', '0')
            branch_rate = root.get('branch-rate', '0')

            metrics.line_coverage = float(line_rate) * 100
            metrics.branch_coverage = float(branch_rate) * 100

        # Fallback: estimate from test presence
        if metrics.line_coverage == 0:
            src_files = list(self.project_root.rglob("*.py"))
            src_files = [f for f in src_files if 'test' not in str(f).lower()]

            tested_files = 0
            for src_file in src_files:
                test_file = src_file.parent / f"test_{src_file.name}"
                if test_file.exists():
                    tested_files += 1

            if len(src_files) > 0:
                metrics.line_coverage = (tested_files / len(src_files)) * 100

        return metrics

    def collect_quality_metrics(self) -> CodeQualityMetrics:
        """Collect code quality metrics."""
        metrics = CodeQualityMetrics()

        # Check for linter results
        lint_results = [
            self.project_root / ".flake8_results.json",
            self.project_root / ".pylint_results.json",
            self.project_root / ".ruff_results.json"
        ]

        for lint_file in lint_results:
            if lint_file.exists():
                with open(lint_file, 'r') as f:
                    data = json.load(f)

                metrics.total_issues += len(data.get('issues', []))

                for issue in data.get('issues', []):
                    severity = issue.get('severity', 'minor').lower()
                    if severity == 'critical' or severity == 'error':
                        metrics.critical_issues += 1
                    elif severity == 'major' or severity == 'warning':
                        metrics.major_issues += 1
                    else:
                        metrics.minor_issues += 1

        # Fallback: run basic checks
        if metrics.total_issues == 0:
            # Count TODO/FIXME comments
            for py_file in self.project_root.rglob("*.py"):
                if 'test' in str(py_file).lower():
                    continue
                try:
                    content = py_file.read_text()
                    todos = len(re.findall(r'#\s*(TODO|FIXME|XXX|HACK)', content))
                    metrics.code_smells += todos

                    # Check for long functions (> 50 lines)
                    functions = re.findall(r'def \w+\([^)]*\):[^def]*', content, re.DOTALL)
                    for func in functions:
                        if func.count('\n') > 50:
                            metrics.complexity_violations += 1
                except Exception:
                    pass

            metrics.total_issues = (metrics.code_smells +
                                    metrics.complexity_violations)

        return metrics

    def collect_defect_metrics(self) -> DefectMetrics:
        """Collect defect tracking metrics."""
        metrics = DefectMetrics()

        # Check ISSUE_CATALOG.md for defect counts
        issue_catalog = self.project_root / "ISSUE_CATALOG.md"
        if issue_catalog.exists():
            content = issue_catalog.read_text()

            # Count issues by status
            not_resolved = len(re.findall(r'NOT RESOLVED', content))
            resolved = len(re.findall(r'✅ RESOLVED', content))

            metrics.open_defects = not_resolved
            metrics.closed_defects = resolved
            metrics.total_defects = not_resolved + resolved

            # Count critical issues
            critical = len(re.findall(r'CRITICAL.*NOT RESOLVED', content))
            metrics.critical_defects = critical

        # Calculate defect density (defects per 1000 lines)
        total_lines = 0
        for py_file in self.project_root.rglob("*.py"):
            if 'test' not in str(py_file).lower():
                try:
                    total_lines += len(py_file.read_text().splitlines())
                except Exception:
                    pass

        if total_lines > 0:
            metrics.defect_density = (metrics.open_defects / total_lines) * 1000

        return metrics

    def calculate_overall_score(self, tests: TestMetrics, coverage: CoverageMetrics,
                                quality: CodeQualityMetrics, defects: DefectMetrics) -> float:
        """Calculate overall QA score (0-100)."""
        scores = {}

        # Test pass rate score
        scores['test_pass_rate'] = min(100, tests.pass_rate)

        # Coverage score
        scores['coverage'] = min(100, coverage.line_coverage)

        # Quality score (inverse of issues)
        max_issues = 100  # Normalize against expected max
        quality_score = max(0, 100 - (quality.total_issues / max_issues * 100))
        scores['quality'] = quality_score

        # Defect score (inverse of open defects)
        max_defects = 50  # Normalize against expected max
        defect_score = max(0, 100 - (defects.open_defects / max_defects * 100))
        scores['defects'] = defect_score

        # Weighted average
        overall = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)

        return round(overall, 2)

    def calculate_grade(self, score: float) -> str:
        """Calculate letter grade from score."""
        for threshold, grade in self.GRADES:
            if score >= threshold:
                return grade
        return 'F'

    def collect_all_metrics(self) -> QAReport:
        """Collect all metrics and generate report."""
        timestamp = datetime.utcnow().isoformat() + "Z"

        tests = self.collect_test_metrics()
        coverage = self.collect_coverage_metrics()
        quality = self.collect_quality_metrics()
        defects = self.collect_defect_metrics()

        overall_score = self.calculate_overall_score(tests, coverage, quality, defects)
        grade = self.calculate_grade(overall_score)

        report = QAReport(
            timestamp=timestamp,
            period_start=timestamp,
            period_end=timestamp,
            tests=tests,
            coverage=coverage,
            quality=quality,
            defects=defects,
            overall_score=overall_score,
            grade=grade
        )

        # Save to history
        self._save_to_history(report)

        return report

    def _save_to_history(self, report: QAReport) -> None:
        """Save report to history."""
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        history_file = self.history_dir / f"{date_str}.yaml"

        history = []
        if history_file.exists():
            with open(history_file, 'r') as f:
                history = yaml.safe_load(f) or []

        history.append(report.to_dict())

        with open(history_file, 'w') as f:
            yaml.dump(history, f, default_flow_style=False)

    def get_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get metrics trends over time."""
        trends = []
        cutoff = datetime.utcnow() - timedelta(days=days)

        for history_file in sorted(self.history_dir.glob("*.yaml")):
            file_date = datetime.strptime(history_file.stem, '%Y-%m-%d')
            if file_date < cutoff:
                continue

            with open(history_file, 'r') as f:
                day_data = yaml.safe_load(f) or []

            if day_data:
                # Use last entry of the day
                trends.append({
                    'date': history_file.stem,
                    'data': day_data[-1]
                })

        return trends

    def generate_report(self, format: str = 'text') -> str:
        """Generate formatted report."""
        report = self.collect_all_metrics()

        if format == 'text':
            return self._format_text_report(report)
        elif format == 'json':
            return json.dumps(report.to_dict(), indent=2)
        elif format == 'yaml':
            return yaml.dump(report.to_dict(), default_flow_style=False)
        elif format == 'html':
            return self._format_html_report(report)
        else:
            return json.dumps(report.to_dict(), indent=2)

    def _format_text_report(self, report: QAReport) -> str:
        """Format report as text."""
        lines = []
        lines.append("=" * 60)
        lines.append("the system QA METRICS REPORT")
        lines.append(f"Generated: {report.timestamp}")
        lines.append("=" * 60)

        lines.append(f"\nOVERALL SCORE: {report.overall_score}/100 (Grade: {report.grade})")

        lines.append("\n--- TEST METRICS ---")
        lines.append(f"Total Tests: {report.tests.total_tests}")
        lines.append(f"Passed: {report.tests.passed}")
        lines.append(f"Failed: {report.tests.failed}")
        lines.append(f"Skipped: {report.tests.skipped}")
        lines.append(f"Pass Rate: {report.tests.pass_rate:.1f}%")

        lines.append("\n--- COVERAGE METRICS ---")
        lines.append(f"Line Coverage: {report.coverage.line_coverage:.1f}%")
        lines.append(f"Branch Coverage: {report.coverage.branch_coverage:.1f}%")
        lines.append(f"Lines Covered: {report.coverage.lines_covered}/{report.coverage.lines_total}")

        lines.append("\n--- QUALITY METRICS ---")
        lines.append(f"Total Issues: {report.quality.total_issues}")
        lines.append(f"Critical: {report.quality.critical_issues}")
        lines.append(f"Major: {report.quality.major_issues}")
        lines.append(f"Minor: {report.quality.minor_issues}")
        lines.append(f"Code Smells: {report.quality.code_smells}")

        lines.append("\n--- DEFECT METRICS ---")
        lines.append(f"Total Defects: {report.defects.total_defects}")
        lines.append(f"Open: {report.defects.open_defects}")
        lines.append(f"Closed: {report.defects.closed_defects}")
        lines.append(f"Critical: {report.defects.critical_defects}")
        lines.append(f"Defect Density: {report.defects.defect_density:.2f}/KLOC")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    def _format_html_report(self, report: QAReport) -> str:
        """Format report as HTML."""
        grade_color = {
            'A': '#4CAF50',
            'B': '#8BC34A',
            'C': '#FFC107',
            'D': '#FF9800',
            'F': '#f44336'
        }.get(report.grade, '#999')

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>the system QA Metrics Report</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; }}
        .grade {{ font-size: 3em; font-weight: bold; color: {grade_color}; }}
        .score {{ font-size: 1.5em; color: #666; }}
        .metric {{ display: inline-block; text-align: center; padding: 15px; margin: 5px; background: #f9f9f9; border-radius: 8px; min-width: 120px; }}
        .metric .value {{ font-size: 1.8em; font-weight: bold; color: #333; }}
        .metric .label {{ color: #666; font-size: 0.9em; }}
        .progress {{ background: #ddd; border-radius: 10px; height: 20px; overflow: hidden; }}
        .progress-fill {{ background: #4CAF50; height: 100%; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>the system QA Metrics Report</h1>
        <p>Generated: {report.timestamp}</p>

        <div class="card" style="text-align: center;">
            <div class="grade">{report.grade}</div>
            <div class="score">{report.overall_score}/100</div>
        </div>

        <div class="card">
            <h2>Test Metrics</h2>
            <div class="metric"><div class="value">{report.tests.total_tests}</div><div class="label">Total</div></div>
            <div class="metric"><div class="value">{report.tests.passed}</div><div class="label">Passed</div></div>
            <div class="metric"><div class="value">{report.tests.failed}</div><div class="label">Failed</div></div>
            <div class="metric"><div class="value">{report.tests.pass_rate:.1f}%</div><div class="label">Pass Rate</div></div>
        </div>

        <div class="card">
            <h2>Coverage</h2>
            <p>Line Coverage: {report.coverage.line_coverage:.1f}%</p>
            <div class="progress"><div class="progress-fill" style="width: {report.coverage.line_coverage}%;"></div></div>
        </div>

        <div class="card">
            <h2>Quality Issues</h2>
            <div class="metric"><div class="value">{report.quality.total_issues}</div><div class="label">Total</div></div>
            <div class="metric"><div class="value">{report.quality.critical_issues}</div><div class="label">Critical</div></div>
            <div class="metric"><div class="value">{report.quality.major_issues}</div><div class="label">Major</div></div>
        </div>

        <div class="card">
            <h2>Defects</h2>
            <div class="metric"><div class="value">{report.defects.open_defects}</div><div class="label">Open</div></div>
            <div class="metric"><div class="value">{report.defects.closed_defects}</div><div class="label">Closed</div></div>
            <div class="metric"><div class="value">{report.defects.critical_defects}</div><div class="label">Critical</div></div>
        </div>
    </div>
</body>
</html>"""

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system QA Metrics Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Collect command
    collect_parser = subparsers.add_parser('collect', help='Collect metrics')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('--format', choices=['text', 'json', 'yaml', 'html'], default='text')
    report_parser.add_argument('--output', '-o', help='Output file')

    # Trends command
    trends_parser = subparsers.add_parser('trends', help='Show trends')
    trends_parser.add_argument('--days', '-d', type=int, default=30, help='Days to analyze')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export metrics')
    export_parser.add_argument('--format', choices=['json', 'yaml', 'csv'], default='json')
    export_parser.add_argument('--output', '-o', help='Output file')

    args = parser.parse_args()

    if not args.command:
        args.command = 'report'
        args.format = 'text'
        args.output = None

    collector = QAMetricsCollector()

    try:
        if args.command == 'collect':
            report = collector.collect_all_metrics()
            print(f"Metrics collected: Score={report.overall_score}, Grade={report.grade}")

        elif args.command == 'report':
            output = collector.generate_report(args.format)
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
                print(f"Report saved to {args.output}")
            else:
                print(output)

        elif args.command == 'trends':
            trends = collector.get_trends(args.days)
            print(f"\nQA Trends (last {args.days} days)")
            print("-" * 50)
            for entry in trends:
                data = entry['data']
                print(f"{entry['date']}: Score={data['overall_score']}, Grade={data['grade']}")

        elif args.command == 'export':
            report = collector.collect_all_metrics()
            if args.format == 'json':
                output = json.dumps(report.to_dict(), indent=2)
            elif args.format == 'yaml':
                output = yaml.dump(report.to_dict(), default_flow_style=False)
            else:
                output = json.dumps(report.to_dict(), indent=2)

            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
                print(f"Exported to {args.output}")
            else:
                print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
