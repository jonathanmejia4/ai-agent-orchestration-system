#!/usr/bin/env python3
"""
Coverage Reporter
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Quality Metrics

Generates and analyzes test coverage reports.

Usage:
    python tools/coverage_reporter.py
    python tools/coverage_reporter.py --min-coverage 80
    python tools/coverage_reporter.py --html
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

@dataclass
class FileCoverage:
    """Coverage for a single file."""
    file: str
    statements: int
    covered: int
    missing: int
    coverage_percent: float
    missing_lines: List[int]

@dataclass
class CoverageReport:
    """Complete coverage report."""
    timestamp: str
    total_statements: int
    total_covered: int
    total_missing: int
    coverage_percent: float
    min_coverage: float
    files: List[FileCoverage]
    uncovered_files: List[str]
    passed: bool

class CoverageReporter:
    """Generates and analyzes coverage reports."""

    def __init__(self, min_coverage: float = 80.0):
        self.min_coverage = min_coverage

    def run_coverage(self, source_dir: Path = None) -> CoverageReport:
        """Run coverage and generate report."""
        source_dir = source_dir or Path("src")

        # Run pytest with coverage
        cmd = [
            "python", "-m", "pytest",
            "--cov=" + str(source_dir),
            "--cov-report=json",
            "--cov-report=term-missing",
            "-q"
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return self._empty_report("Test execution timed out")
        except FileNotFoundError:
            return self._empty_report("pytest or pytest-cov not installed")

        # Parse coverage.json
        return self._parse_coverage_json()

    def _parse_coverage_json(self) -> CoverageReport:
        """Parse coverage.json file."""
        coverage_file = Path("coverage.json")

        if not coverage_file.exists():
            return self._empty_report("coverage.json not found")

        try:
            with open(coverage_file) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return self._empty_report("Invalid coverage.json")

        files = []
        totals = data.get("totals", {})

        for file_path, file_data in data.get("files", {}).items():
            summary = file_data.get("summary", {})
            files.append(FileCoverage(
                file=file_path,
                statements=summary.get("num_statements", 0),
                covered=summary.get("covered_lines", 0),
                missing=summary.get("missing_lines", 0),
                coverage_percent=summary.get("percent_covered", 0),
                missing_lines=file_data.get("missing_lines", [])
            ))

        # Find uncovered files
        uncovered = [f.file for f in files if f.coverage_percent == 0]

        coverage_percent = totals.get("percent_covered", 0)
        passed = coverage_percent >= self.min_coverage

        return CoverageReport(
            timestamp=datetime.now().isoformat(),
            total_statements=totals.get("num_statements", 0),
            total_covered=totals.get("covered_lines", 0),
            total_missing=totals.get("missing_lines", 0),
            coverage_percent=coverage_percent,
            min_coverage=self.min_coverage,
            files=files,
            uncovered_files=uncovered,
            passed=passed
        )

    def _empty_report(self, message: str) -> CoverageReport:
        """Generate empty report with error."""
        return CoverageReport(
            timestamp=datetime.now().isoformat(),
            total_statements=0,
            total_covered=0,
            total_missing=0,
            coverage_percent=0,
            min_coverage=self.min_coverage,
            files=[],
            uncovered_files=[],
            passed=False
        )

    def generate_html(self, output_dir: Path = None):
        """Generate HTML coverage report."""
        output_dir = output_dir or Path("htmlcov")

        cmd = [
            "python", "-m", "coverage", "html",
            "-d", str(output_dir)
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True)
            print(f"HTML report generated in {output_dir}")
        except Exception as e:
            print(f"Failed to generate HTML report: {e}")

    def analyze_trends(self, history_file: Path = None) -> Dict[str, Any]:
        """Analyze coverage trends from history."""
        history_file = history_file or Path(".coverage_history.json")

        if not history_file.exists():
            return {"trend": "unknown", "history": []}

        try:
            with open(history_file) as f:
                history = json.load(f)
        except Exception:
            return {"trend": "unknown", "history": []}

        if len(history) < 2:
            return {"trend": "insufficient_data", "history": history}

        # Calculate trend
        recent = history[-5:]
        if len(recent) >= 2:
            first = recent[0].get("coverage_percent", 0)
            last = recent[-1].get("coverage_percent", 0)

            if last > first + 1:
                trend = "improving"
            elif last < first - 1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        return {"trend": trend, "history": history}

def format_text(report: CoverageReport) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Coverage Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Minimum Required: {report.min_coverage}%")
    lines.append("")
    lines.append(f"Total Statements: {report.total_statements}")
    lines.append(f"Covered: {report.total_covered}")
    lines.append(f"Missing: {report.total_missing}")
    lines.append(f"Coverage: {report.coverage_percent:.1f}%")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    icon = "✓" if report.passed else "✗"
    lines.append(f"{icon} Status: {status}")
    lines.append("")

    # Show files with low coverage
    low_coverage = [f for f in report.files if f.coverage_percent < report.min_coverage]
    if low_coverage:
        lines.append("Files Below Threshold:")
        for f in sorted(low_coverage, key=lambda x: x.coverage_percent):
            lines.append(f"  {f.file}: {f.coverage_percent:.1f}%")
        lines.append("")

    # Show uncovered files
    if report.uncovered_files:
        lines.append("Uncovered Files:")
        for f in report.uncovered_files[:10]:
            lines.append(f"  {f}")
        if len(report.uncovered_files) > 10:
            lines.append(f"  ... and {len(report.uncovered_files) - 10} more")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: CoverageReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_statements": report.total_statements,
        "total_covered": report.total_covered,
        "total_missing": report.total_missing,
        "coverage_percent": report.coverage_percent,
        "min_coverage": report.min_coverage,
        "passed": report.passed,
        "files": [asdict(f) for f in report.files],
        "uncovered_files": report.uncovered_files
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Generate coverage reports"
    )

    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Minimum coverage percentage (default: 80)"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("src"),
        help="Source directory to measure"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file"
    )

    args = parser.parse_args()

    reporter = CoverageReporter(args.min_coverage)
    report = reporter.run_coverage(args.source)

    if args.html:
        reporter.generate_html()

    # Format output
    if args.format == "json":
        output = format_json(report)
    else:
        output = format_text(report)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    sys.exit(0 if report.passed else 1)

if __name__ == "__main__":
    main()
