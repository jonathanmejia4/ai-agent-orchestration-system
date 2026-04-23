#!/usr/bin/env python3
"""
verify_security_test_coverage.py - Security Test Coverage Verifier

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: CRITICAL - Security Validation Tool

Purpose:
    Verifies that all security-sensitive code has corresponding security tests.
    Detects gaps in security test coverage.
    Enforces security testing requirements per the system policy.

Usage:
    python3 verify_security_test_coverage.py --dir tasks/
    python3 verify_security_test_coverage.py --dir tasks/ --min-coverage 80
    python3 verify_security_test_coverage.py --dir tasks/ --report security-coverage.json
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass
class SecurityPattern:
    """Represents a security-sensitive code pattern."""
    name: str
    pattern: str
    category: str
    severity: str
    requires_test: bool = True
    test_patterns: List[str] = field(default_factory=list)

@dataclass
class SecurityFinding:
    """Represents a security-sensitive code location."""
    file_path: str
    line_number: int
    pattern_name: str
    category: str
    severity: str
    code_snippet: str
    has_test: bool = False
    test_file: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "pattern_name": self.pattern_name,
            "category": self.category,
            "severity": self.severity,
            "code_snippet": self.code_snippet,
            "has_test": self.has_test,
            "test_file": self.test_file
        }

@dataclass
class CoverageReport:
    """Security test coverage report."""
    total_findings: int
    covered_findings: int
    coverage_percent: float
    findings_by_category: Dict[str, int]
    uncovered_findings: List[SecurityFinding]
    covered_findings_list: List[SecurityFinding]

    def to_dict(self) -> dict:
        return {
            "total_findings": self.total_findings,
            "covered_findings": self.covered_findings,
            "coverage_percent": self.coverage_percent,
            "findings_by_category": self.findings_by_category,
            "uncovered_findings": [f.to_dict() for f in self.uncovered_findings],
            "covered_findings": [f.to_dict() for f in self.covered_findings_list]
        }

class SecurityTestCoverageVerifier:
    """Verifies security test coverage for code."""

    # Security-sensitive patterns to detect
    SECURITY_PATTERNS = [
        SecurityPattern(
            name="authentication",
            pattern=r"(authenticate|login|logout|session|token|jwt|oauth|api_key|password)",
            category="authentication",
            severity="critical",
            test_patterns=["test_auth", "test_login", "test_session", "test_token"]
        ),
        SecurityPattern(
            name="authorization",
            pattern=r"(authorize|permission|role|access_control|acl|rbac|can_access|is_allowed)",
            category="authorization",
            severity="critical",
            test_patterns=["test_permission", "test_role", "test_access", "test_authorize"]
        ),
        SecurityPattern(
            name="input_validation",
            pattern=r"(validate|sanitize|escape|filter_input|clean_input|xss|injection)",
            category="input_validation",
            severity="high",
            test_patterns=["test_validate", "test_sanitize", "test_input", "test_xss"]
        ),
        SecurityPattern(
            name="cryptography",
            pattern=r"(encrypt|decrypt|hash|hmac|sign|verify_signature|crypto|cipher|aes|rsa)",
            category="cryptography",
            severity="critical",
            test_patterns=["test_encrypt", "test_decrypt", "test_hash", "test_crypto"]
        ),
        SecurityPattern(
            name="sql_operations",
            pattern=r"(execute|cursor|query|sql|select|insert|update|delete|raw_sql)",
            category="sql_injection",
            severity="critical",
            test_patterns=["test_sql", "test_query", "test_injection"]
        ),
        SecurityPattern(
            name="file_operations",
            pattern=r"(open\s*\(|read_file|write_file|file_path|path_traversal|upload)",
            category="file_security",
            severity="high",
            test_patterns=["test_file", "test_path", "test_upload"]
        ),
        SecurityPattern(
            name="network_operations",
            pattern=r"(request|fetch|http|https|socket|connect|url|endpoint)",
            category="network_security",
            severity="high",
            test_patterns=["test_request", "test_http", "test_endpoint"]
        ),
        SecurityPattern(
            name="secrets_handling",
            pattern=r"(secret|private_key|api_secret|credentials|password|env\[)",
            category="secrets_management",
            severity="critical",
            test_patterns=["test_secret", "test_credential"]
        ),
        SecurityPattern(
            name="rate_limiting",
            pattern=r"(rate_limit|throttle|quota|limit_requests)",
            category="dos_protection",
            severity="medium",
            test_patterns=["test_rate", "test_throttle", "test_limit"]
        ),
        SecurityPattern(
            name="logging_audit",
            pattern=r"(audit_log|security_log|log_access|log_event)",
            category="audit_logging",
            severity="medium",
            test_patterns=["test_audit", "test_log"]
        )
    ]

    def __init__(self, patterns: Optional[List[SecurityPattern]] = None):
        self.patterns = patterns or self.SECURITY_PATTERNS

    def _find_security_patterns(self, file_path: Path) -> List[SecurityFinding]:
        """Find security-sensitive code patterns in a file."""
        findings = []

        try:
            content = file_path.read_text()
            lines = content.split('\n')
        except Exception:
            return findings

        for pattern in self.patterns:
            regex = re.compile(pattern.pattern, re.IGNORECASE)

            for i, line in enumerate(lines, 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue

                if regex.search(line):
                    findings.append(SecurityFinding(
                        file_path=str(file_path),
                        line_number=i,
                        pattern_name=pattern.name,
                        category=pattern.category,
                        severity=pattern.severity,
                        code_snippet=line.strip()[:100]
                    ))

        return findings

    def _find_test_files(self, source_dir: Path) -> Dict[str, Path]:
        """Find all test files and map them to source files."""
        test_files = {}

        # Find test files
        for test_file in source_dir.rglob("test_*.py"):
            test_files[str(test_file)] = test_file

        for test_file in source_dir.rglob("*_test.py"):
            test_files[str(test_file)] = test_file

        # Check tests/ directories
        for tests_dir in source_dir.rglob("tests"):
            if tests_dir.is_dir():
                for test_file in tests_dir.rglob("*.py"):
                    test_files[str(test_file)] = test_file

        return test_files

    def _check_test_coverage(
        self,
        finding: SecurityFinding,
        test_files: Dict[str, Path]
    ) -> Tuple[bool, Optional[str]]:
        """Check if a security finding has corresponding test coverage."""
        source_path = Path(finding.file_path)
        source_name = source_path.stem

        # Find the pattern info
        pattern = next((p for p in self.patterns if p.name == finding.pattern_name), None)
        if not pattern:
            return False, None

        # Look for test files
        for test_path_str, test_path in test_files.items():
            try:
                test_content = test_path.read_text().lower()
            except Exception:
                continue

            # Check if test file relates to source file
            if source_name.lower() in test_path.name.lower():
                # Check for security test patterns
                for test_pattern in pattern.test_patterns:
                    if test_pattern.lower() in test_content:
                        return True, str(test_path)

            # Check if test file contains any of the test patterns
            for test_pattern in pattern.test_patterns:
                if test_pattern.lower() in test_content:
                    # Verify it's testing the right category
                    if finding.category.lower() in test_content:
                        return True, str(test_path)

        return False, None

    def verify_coverage(self, source_dir: Path) -> CoverageReport:
        """Verify security test coverage for a directory."""
        all_findings = []
        covered = []
        uncovered = []
        by_category: Dict[str, int] = {}

        # Find all test files
        test_files = self._find_test_files(source_dir)

        # Scan source files for security patterns
        for source_file in source_dir.rglob("*.py"):
            # Skip test files
            if "test" in source_file.name.lower() or "tests" in str(source_file):
                continue

            findings = self._find_security_patterns(source_file)
            all_findings.extend(findings)

        # Check coverage for each finding
        for finding in all_findings:
            # Count by category
            by_category[finding.category] = by_category.get(finding.category, 0) + 1

            # Check if covered
            has_test, test_file = self._check_test_coverage(finding, test_files)
            finding.has_test = has_test
            finding.test_file = test_file

            if has_test:
                covered.append(finding)
            else:
                uncovered.append(finding)

        # Calculate coverage
        total = len(all_findings)
        coverage_percent = (len(covered) / total * 100) if total > 0 else 100.0

        return CoverageReport(
            total_findings=total,
            covered_findings=len(covered),
            coverage_percent=round(coverage_percent, 2),
            findings_by_category=by_category,
            uncovered_findings=uncovered,
            covered_findings_list=covered
        )

    def verify_file(self, file_path: Path, tests_dir: Optional[Path] = None) -> CoverageReport:
        """Verify security test coverage for a single file."""
        findings = self._find_security_patterns(file_path)

        # Find test files
        test_files = {}
        if tests_dir:
            test_files = self._find_test_files(tests_dir)
        else:
            # Look for tests in parent directory
            parent = file_path.parent
            test_files = self._find_test_files(parent)

        covered = []
        uncovered = []
        by_category: Dict[str, int] = {}

        for finding in findings:
            by_category[finding.category] = by_category.get(finding.category, 0) + 1

            has_test, test_file = self._check_test_coverage(finding, test_files)
            finding.has_test = has_test
            finding.test_file = test_file

            if has_test:
                covered.append(finding)
            else:
                uncovered.append(finding)

        total = len(findings)
        coverage_percent = (len(covered) / total * 100) if total > 0 else 100.0

        return CoverageReport(
            total_findings=total,
            covered_findings=len(covered),
            coverage_percent=round(coverage_percent, 2),
            findings_by_category=by_category,
            uncovered_findings=uncovered,
            covered_findings_list=covered
        )

def main():
    parser = argparse.ArgumentParser(
        description="Verify security test coverage for code"
    )
    parser.add_argument(
        "--dir", "-d",
        help="Directory to scan"
    )
    parser.add_argument(
        "--file", "-f",
        help="Single file to scan"
    )
    parser.add_argument(
        "--min-coverage", "-m",
        type=float,
        default=80.0,
        help="Minimum coverage percentage required (default: 80)"
    )
    parser.add_argument(
        "--report", "-r",
        help="Output report file (JSON)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--fail-on-uncovered",
        action="store_true",
        help="Exit with error if any security code is uncovered"
    )

    args = parser.parse_args()

    if not args.dir and not args.file:
        print("Error: Must specify --dir or --file", file=sys.stderr)
        return 1

    verifier = SecurityTestCoverageVerifier()

    if args.dir:
        report = verifier.verify_coverage(Path(args.dir))
    else:
        report = verifier.verify_file(Path(args.file))

    # Output report
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Report saved to {args.report}")

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("=" * 60)
        print("SECURITY TEST COVERAGE REPORT")
        print("=" * 60)
        print(f"\nTotal security-sensitive findings: {report.total_findings}")
        print(f"Covered by tests: {report.covered_findings}")
        print(f"Coverage: {report.coverage_percent}%")
        print(f"Minimum required: {args.min_coverage}%")

        if report.findings_by_category:
            print("\nFindings by Category:")
            for category, count in sorted(report.findings_by_category.items()):
                print(f"  {category}: {count}")

        if report.uncovered_findings:
            print("\n" + "-" * 60)
            print("UNCOVERED SECURITY CODE:")
            print("-" * 60)

            # Group by severity
            by_severity = {"critical": [], "high": [], "medium": [], "low": []}
            for finding in report.uncovered_findings:
                by_severity.get(finding.severity, by_severity["medium"]).append(finding)

            for severity in ["critical", "high", "medium", "low"]:
                findings = by_severity[severity]
                if findings:
                    print(f"\n{severity.upper()} ({len(findings)}):")
                    for f in findings[:10]:  # Limit output
                        print(f"  {f.file_path}:{f.line_number}")
                        print(f"    Pattern: {f.pattern_name} ({f.category})")
                        print(f"    Code: {f.code_snippet[:60]}...")

        print("\n" + "=" * 60)
        if report.coverage_percent >= args.min_coverage:
            print(f"✅ Coverage meets minimum threshold ({args.min_coverage}%)")
        else:
            print(f"❌ Coverage below minimum threshold ({args.min_coverage}%)")

    # Exit codes
    if args.fail_on_uncovered and report.uncovered_findings:
        return 1
    if report.coverage_percent < args.min_coverage:
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
