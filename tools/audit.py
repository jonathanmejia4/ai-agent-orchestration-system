#!/usr/bin/env python3
"""
Audit - Documentation Quality Gates and Metrics Collection

Parses Sphinx build logs, runs quality gates (linkcheck, doctest),
collects documentation metrics, compares against thresholds, and
generates comprehensive audit reports.

Usage:
    python3 tools/audit.py
    python3 tools/audit.py --build-log _build/sphinx.log
    python3 tools/audit.py --thresholds thresholds.yaml
    python3 tools/audit.py --output docs_audit.json
    python3 tools/audit.py --help

Exit Codes:
    0 - All quality gates passed
    1 - One or more quality gates failed
    2 - Error (file not found, parse error, etc.)

Referenced in:
    - PLANNING/DATA_MODELS.md:852
    - PLANNING/RKC_ARCHITECTURE.md:479, 826

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import json
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

class GateStatus(Enum):
    """Quality gate status"""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"

@dataclass
class QualityGate:
    """Result of a quality gate check"""
    name: str
    status: GateStatus
    message: str
    value: Optional[Any] = None
    threshold: Optional[Any] = None
    details: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'value': self.value,
            'threshold': self.threshold,
            'details': self.details
        }

@dataclass
class BuildMetrics:
    """Documentation build metrics"""
    build_duration_seconds: float = 0.0
    total_pages: int = 0
    total_files: int = 0
    html_size_bytes: int = 0
    warnings_count: int = 0
    errors_count: int = 0
    doctests_passed: int = 0
    doctests_failed: int = 0
    links_checked: int = 0
    links_broken: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class AuditReport:
    """Complete audit report"""
    timestamp: str
    overall_status: str  # PASS, FAIL, ERROR
    build_metrics: BuildMetrics = field(default_factory=BuildMetrics)
    quality_gates: List[QualityGate] = field(default_factory=list)
    gates_passed: int = 0
    gates_failed: int = 0
    gates_warned: int = 0
    summary: str = ""

    def add_gate(self, gate: QualityGate):
        self.quality_gates.append(gate)
        if gate.status == GateStatus.PASS:
            self.gates_passed += 1
        elif gate.status == GateStatus.FAIL:
            self.gates_failed += 1
        elif gate.status == GateStatus.WARN:
            self.gates_warned += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'overall_status': self.overall_status,
            'summary': self.summary,
            'statistics': {
                'gates_passed': self.gates_passed,
                'gates_failed': self.gates_failed,
                'gates_warned': self.gates_warned,
                'total_gates': len(self.quality_gates)
            },
            'build_metrics': self.build_metrics.to_dict(),
            'quality_gates': [g.to_dict() for g in self.quality_gates]
        }

class DocumentationAuditor:
    """Documentation quality auditor"""

    DEFAULT_THRESHOLDS = {
        'max_warnings': 10,
        'max_errors': 0,
        'min_pages': 1,
        'max_build_duration_seconds': 300,
        'max_broken_links': 0,
        'min_doctest_pass_rate': 0.95,
        'max_html_size_mb': 100,
    }

    def __init__(self, docs_dir: Path, build_dir: Path,
                 thresholds: Optional[Dict] = None, verbose: bool = False):
        self.docs_dir = docs_dir
        self.build_dir = build_dir
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.verbose = verbose
        self.report = AuditReport(
            timestamp=datetime.now().isoformat(),
            overall_status="PENDING"
        )

    def log(self, message: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def parse_build_log(self, log_path: Path) -> Tuple[int, int, float]:
        """Parse Sphinx build log for warnings, errors, and duration"""
        warnings = 0
        errors = 0
        duration = 0.0

        if not log_path.exists():
            self.log(f"Build log not found: {log_path}")
            return warnings, errors, duration

        try:
            content = log_path.read_text()

            # Count warnings
            warning_patterns = [
                r'WARNING:',
                r'\bwarning\b',
                r'\.py:\d+: warning:',
            ]
            for pattern in warning_patterns:
                warnings += len(re.findall(pattern, content, re.IGNORECASE))

            # Count errors
            error_patterns = [
                r'ERROR:',
                r'\berror\b',
                r'FAILED',
                r'Exception',
            ]
            for pattern in error_patterns:
                errors += len(re.findall(pattern, content, re.IGNORECASE))

            # Extract duration
            duration_match = re.search(r'build succeeded.*?(\d+\.?\d*)\s*seconds?', content, re.IGNORECASE)
            if duration_match:
                duration = float(duration_match.group(1))
            else:
                # Try alternative format
                duration_match = re.search(r'total time:\s*(\d+\.?\d*)', content, re.IGNORECASE)
                if duration_match:
                    duration = float(duration_match.group(1))

        except Exception as e:
            self.log(f"Error parsing build log: {e}")

        return warnings, errors, duration

    def count_pages(self) -> int:
        """Count generated HTML pages"""
        html_dir = self.build_dir / 'html'
        if not html_dir.exists():
            html_dir = self.build_dir

        html_files = list(html_dir.rglob('*.html'))
        return len(html_files)

    def calculate_html_size(self) -> int:
        """Calculate total HTML output size in bytes"""
        html_dir = self.build_dir / 'html'
        if not html_dir.exists():
            html_dir = self.build_dir

        total_size = 0
        for file_path in html_dir.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size

    def run_linkcheck(self) -> Tuple[int, int, List[str]]:
        """Run Sphinx linkcheck and return results"""
        checked = 0
        broken = 0
        broken_links = []

        # Check for linkcheck output
        linkcheck_output = self.build_dir / 'linkcheck' / 'output.txt'
        if not linkcheck_output.exists():
            linkcheck_output = self.build_dir / 'linkcheck.txt'

        if linkcheck_output.exists():
            try:
                content = linkcheck_output.read_text()
                lines = content.split('\n')

                for line in lines:
                    if line.strip():
                        checked += 1
                        if '[broken]' in line.lower() or 'error' in line.lower():
                            broken += 1
                            broken_links.append(line.strip()[:200])

            except Exception as e:
                self.log(f"Error reading linkcheck output: {e}")
        else:
            # Try running linkcheck
            try:
                result = subprocess.run(
                    ['sphinx-build', '-b', 'linkcheck', str(self.docs_dir), str(self.build_dir / 'linkcheck')],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(self.docs_dir.parent)
                )
                # Parse output
                for line in result.stdout.split('\n'):
                    if 'broken' in line.lower():
                        broken += 1
                        broken_links.append(line.strip()[:200])
                    elif line.strip():
                        checked += 1
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.log("Linkcheck skipped (sphinx-build not available or timeout)")

        return checked, broken, broken_links

    def run_doctest(self) -> Tuple[int, int]:
        """Run Sphinx doctest and return pass/fail counts"""
        passed = 0
        failed = 0

        # Check for doctest output
        doctest_output = self.build_dir / 'doctest' / 'output.txt'
        if doctest_output.exists():
            try:
                content = doctest_output.read_text()

                # Parse doctest results
                pass_match = re.search(r'(\d+)\s+tests?\s+passed', content, re.IGNORECASE)
                fail_match = re.search(r'(\d+)\s+tests?\s+failed', content, re.IGNORECASE)

                if pass_match:
                    passed = int(pass_match.group(1))
                if fail_match:
                    failed = int(fail_match.group(1))

            except Exception as e:
                self.log(f"Error reading doctest output: {e}")
        else:
            # Try running doctest
            try:
                result = subprocess.run(
                    ['sphinx-build', '-b', 'doctest', str(self.docs_dir), str(self.build_dir / 'doctest')],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(self.docs_dir.parent)
                )
                # Parse output
                for line in result.stdout.split('\n'):
                    if 'passed' in line.lower():
                        match = re.search(r'(\d+)', line)
                        if match:
                            passed = int(match.group(1))
                    if 'failed' in line.lower():
                        match = re.search(r'(\d+)', line)
                        if match:
                            failed = int(match.group(1))
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.log("Doctest skipped (sphinx-build not available or timeout)")

        return passed, failed

    def collect_metrics(self, build_log: Optional[Path] = None) -> BuildMetrics:
        """Collect all build metrics"""
        metrics = BuildMetrics()

        # Parse build log
        if build_log:
            warnings, errors, duration = self.parse_build_log(build_log)
            metrics.warnings_count = warnings
            metrics.errors_count = errors
            metrics.build_duration_seconds = duration

        # Count pages and files
        metrics.total_pages = self.count_pages()
        metrics.total_files = len(list(self.build_dir.rglob('*'))) if self.build_dir.exists() else 0
        metrics.html_size_bytes = self.calculate_html_size()

        # Run quality checks
        checked, broken, _ = self.run_linkcheck()
        metrics.links_checked = checked
        metrics.links_broken = broken

        passed, failed = self.run_doctest()
        metrics.doctests_passed = passed
        metrics.doctests_failed = failed

        self.report.build_metrics = metrics
        return metrics

    def check_warnings(self) -> QualityGate:
        """Check warnings against threshold"""
        name = "Build Warnings"
        value = self.report.build_metrics.warnings_count
        threshold = self.thresholds['max_warnings']

        if value > threshold:
            return QualityGate(name, GateStatus.FAIL,
                f"Too many warnings: {value} (max: {threshold})",
                value=value, threshold=threshold)
        elif value > threshold * 0.8:
            return QualityGate(name, GateStatus.WARN,
                f"Approaching warning limit: {value} (max: {threshold})",
                value=value, threshold=threshold)
        else:
            return QualityGate(name, GateStatus.PASS,
                f"Warnings within limit: {value}",
                value=value, threshold=threshold)

    def check_errors(self) -> QualityGate:
        """Check errors against threshold"""
        name = "Build Errors"
        value = self.report.build_metrics.errors_count
        threshold = self.thresholds['max_errors']

        if value > threshold:
            return QualityGate(name, GateStatus.FAIL,
                f"Build errors detected: {value} (max: {threshold})",
                value=value, threshold=threshold)
        else:
            return QualityGate(name, GateStatus.PASS,
                f"No build errors",
                value=value, threshold=threshold)

    def check_page_count(self) -> QualityGate:
        """Check minimum page count"""
        name = "Page Count"
        value = self.report.build_metrics.total_pages
        threshold = self.thresholds['min_pages']

        if value < threshold:
            return QualityGate(name, GateStatus.FAIL,
                f"Insufficient pages: {value} (min: {threshold})",
                value=value, threshold=threshold)
        else:
            return QualityGate(name, GateStatus.PASS,
                f"Page count OK: {value} pages",
                value=value, threshold=threshold)

    def check_build_duration(self) -> QualityGate:
        """Check build duration against threshold"""
        name = "Build Duration"
        value = self.report.build_metrics.build_duration_seconds
        threshold = self.thresholds['max_build_duration_seconds']

        if value == 0:
            return QualityGate(name, GateStatus.SKIP,
                "Build duration not available",
                value=value, threshold=threshold)
        elif value > threshold:
            return QualityGate(name, GateStatus.WARN,
                f"Build slower than expected: {value:.1f}s (max: {threshold}s)",
                value=value, threshold=threshold)
        else:
            return QualityGate(name, GateStatus.PASS,
                f"Build duration OK: {value:.1f}s",
                value=value, threshold=threshold)

    def check_broken_links(self) -> QualityGate:
        """Check for broken links"""
        name = "Link Check"
        value = self.report.build_metrics.links_broken
        checked = self.report.build_metrics.links_checked
        threshold = self.thresholds['max_broken_links']

        if checked == 0:
            return QualityGate(name, GateStatus.SKIP,
                "No links checked",
                value=value, threshold=threshold)
        elif value > threshold:
            return QualityGate(name, GateStatus.FAIL,
                f"Broken links found: {value} (max: {threshold})",
                value=value, threshold=threshold)
        else:
            return QualityGate(name, GateStatus.PASS,
                f"All {checked} links valid",
                value=value, threshold=threshold)

    def check_doctests(self) -> QualityGate:
        """Check doctest pass rate"""
        name = "Doctest Results"
        passed = self.report.build_metrics.doctests_passed
        failed = self.report.build_metrics.doctests_failed
        total = passed + failed
        threshold = self.thresholds['min_doctest_pass_rate']

        if total == 0:
            return QualityGate(name, GateStatus.SKIP,
                "No doctests found",
                value=0, threshold=threshold)

        pass_rate = passed / total
        if pass_rate < threshold:
            return QualityGate(name, GateStatus.FAIL,
                f"Doctest pass rate too low: {pass_rate:.1%} (min: {threshold:.0%})",
                value=pass_rate, threshold=threshold)
        else:
            return QualityGate(name, GateStatus.PASS,
                f"Doctests passed: {passed}/{total} ({pass_rate:.1%})",
                value=pass_rate, threshold=threshold)

    def check_output_size(self) -> QualityGate:
        """Check output size against threshold"""
        name = "Output Size"
        value_bytes = self.report.build_metrics.html_size_bytes
        value_mb = value_bytes / (1024 * 1024)
        threshold = self.thresholds['max_html_size_mb']

        if value_mb > threshold:
            return QualityGate(name, GateStatus.WARN,
                f"Output larger than expected: {value_mb:.1f}MB (max: {threshold}MB)",
                value=value_mb, threshold=threshold)
        else:
            return QualityGate(name, GateStatus.PASS,
                f"Output size OK: {value_mb:.1f}MB",
                value=value_mb, threshold=threshold)

    def run_audit(self, build_log: Optional[Path] = None) -> AuditReport:
        """Run complete audit"""
        print(f"\n{'='*60}")
        print("Documentation Audit")
        print(f"{'='*60}\n")

        # Collect metrics
        print("Collecting build metrics...")
        self.collect_metrics(build_log)

        print(f"  Pages:     {self.report.build_metrics.total_pages}")
        print(f"  Files:     {self.report.build_metrics.total_files}")
        print(f"  Size:      {self.report.build_metrics.html_size_bytes / 1024:.1f} KB")
        print(f"  Warnings:  {self.report.build_metrics.warnings_count}")
        print(f"  Errors:    {self.report.build_metrics.errors_count}")
        print()

        # Run quality gates
        print("Running quality gates...\n")

        gates = [
            self.check_errors,
            self.check_warnings,
            self.check_page_count,
            self.check_build_duration,
            self.check_broken_links,
            self.check_doctests,
            self.check_output_size,
        ]

        for gate_func in gates:
            gate = gate_func()
            self.report.add_gate(gate)

            if gate.status == GateStatus.PASS:
                icon = "\033[92m✓\033[0m"
            elif gate.status == GateStatus.FAIL:
                icon = "\033[91m✗\033[0m"
            elif gate.status == GateStatus.WARN:
                icon = "\033[93m⚠\033[0m"
            else:
                icon = "\033[90m○\033[0m"

            print(f"  {icon} {gate.name}: {gate.message}")

        # Determine overall status
        if self.report.gates_failed > 0:
            self.report.overall_status = "FAIL"
            self.report.summary = f"Audit failed: {self.report.gates_failed} gate(s) failed"
        elif self.report.gates_warned > 0:
            self.report.overall_status = "PASS_WITH_WARNINGS"
            self.report.summary = f"Audit passed with {self.report.gates_warned} warning(s)"
        else:
            self.report.overall_status = "PASS"
            self.report.summary = "All quality gates passed"

        return self.report

    def save_report(self, output_path: Path):
        """Save audit report to file"""
        with open(output_path, 'w') as f:
            json.dump(self.report.to_dict(), f, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description='Documentation Audit - Quality gates and metrics collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s
    %(prog)s --docs-dir docs/ --build-dir _build/
    %(prog)s --build-log _build/sphinx.log
    %(prog)s --thresholds thresholds.yaml
    %(prog)s --output docs_audit.json

Exit Codes:
    0 - All quality gates passed
    1 - One or more quality gates failed
    2 - Error
        """
    )

    parser.add_argument('--docs-dir', '-d', type=Path, default=Path('docs'),
                        help='Documentation source directory (default: docs/)')
    parser.add_argument('--build-dir', '-b', type=Path, default=Path('_build'),
                        help='Build output directory (default: _build/)')
    parser.add_argument('--build-log', '-l', type=Path,
                        help='Path to Sphinx build log')
    parser.add_argument('--thresholds', '-t', type=Path,
                        help='YAML file with custom thresholds')
    parser.add_argument('--output', '-o', type=Path, default=Path('docs_audit.json'),
                        help='Output file for audit report (default: docs_audit.json)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--json', action='store_true',
                        help='Output report as JSON to stdout')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Run checks without saving report')

    args = parser.parse_args()

    # Load custom thresholds
    thresholds = None
    if args.thresholds and args.thresholds.exists():
        try:
            with open(args.thresholds) as f:
                thresholds = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load thresholds: {e}")

    # Create auditor
    auditor = DocumentationAuditor(
        docs_dir=args.docs_dir,
        build_dir=args.build_dir,
        thresholds=thresholds,
        verbose=args.verbose
    )

    # Run audit
    report = auditor.run_audit(build_log=args.build_log)

    # Print summary
    print(f"\n{'='*60}")
    if report.overall_status == "PASS":
        print(f"\033[92m✅ AUDIT PASSED\033[0m - {report.summary}")
    elif report.overall_status == "PASS_WITH_WARNINGS":
        print(f"\033[93m⚠️  AUDIT PASSED WITH WARNINGS\033[0m - {report.summary}")
    else:
        print(f"\033[91m❌ AUDIT FAILED\033[0m - {report.summary}")
    print(f"{'='*60}")

    # Statistics
    print(f"\nStatistics:")
    print(f"  Passed:  {report.gates_passed}")
    print(f"  Failed:  {report.gates_failed}")
    print(f"  Warned:  {report.gates_warned}")

    # Save report
    if not args.dry_run:
        auditor.save_report(args.output)
        print(f"\nReport saved: {args.output}")

    # JSON output
    if args.json:
        print(f"\n{json.dumps(report.to_dict(), indent=2)}")

    # Exit code
    if report.overall_status == "FAIL":
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
