#!/usr/bin/env python3
"""
security_scanner.py - the system Security Scanner

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Security Tool

Purpose:
    Scans the system codebase for security vulnerabilities:
    - Hardcoded secrets and credentials
    - SQL injection patterns
    - Command injection risks
    - Insecure configurations
    - Dependency vulnerabilities

Usage:
    python3 security_scanner.py scan --path task001/
    python3 security_scanner.py scan --path . --severity high,critical
    python3 security_scanner.py check --type secrets
    python3 security_scanner.py report --output security-report.json
    python3 security_scanner.py report --severity critical --output critical-only.json
"""

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

class SecuritySeverity:
    """Security issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class SecurityFinding:
    """Represents a security finding."""
    finding_id: str
    category: str
    severity: str
    title: str
    description: str
    file_path: str
    line_number: int
    code_snippet: str
    remediation: str
    cwe_id: Optional[str] = None
    confidence: float = 1.0
    false_positive: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet[:100] + "..." if len(self.code_snippet) > 100 else self.code_snippet,
            "remediation": self.remediation,
            "cwe_id": self.cwe_id,
            "confidence": self.confidence,
            "false_positive": self.false_positive
        }

@dataclass
class ScanResult:
    """Complete scan result."""
    scan_id: str
    timestamp: str
    scan_path: str
    duration_ms: int
    files_scanned: int
    findings: List[SecurityFinding]
    summary: Dict[str, int]

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "timestamp": self.timestamp,
            "scan_path": self.scan_path,
            "duration_ms": self.duration_ms,
            "files_scanned": self.files_scanned,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary
        }

class SecurityScanner:
    """Scans for security vulnerabilities."""

    # Secret patterns
    SECRET_PATTERNS = [
        (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']', "API Key", "CWE-798"),
        (r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']([^\s"\']{8,})["\']', "Password/Secret", "CWE-798"),
        (r'(?i)(token|auth[_-]?token|bearer)\s*[:=]\s*["\']([a-zA-Z0-9_\-\.]{20,})["\']', "Token", "CWE-798"),
        (r'(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[:=]\s*["\']?(AKIA[A-Z0-9]{16})["\']?', "AWS Access Key", "CWE-798"),
        (r'(?i)(private[_-]?key|privkey)\s*[:=]\s*["\']([^\s"\']{20,})["\']', "Private Key", "CWE-798"),
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', "Private Key Block", "CWE-798"),
        (r'ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token", "CWE-798"),
        (r'sk-[a-zA-Z0-9]{48}', "OpenAI API Key", "CWE-798"),
    ]

    # Injection patterns
    INJECTION_PATTERNS = [
        (r'execute\s*\(\s*["\']?\s*\+', "SQL Injection (string concat)", "CWE-89", SecuritySeverity.CRITICAL),
        (r'cursor\.execute\s*\(\s*f["\']', "SQL Injection (f-string)", "CWE-89", SecuritySeverity.CRITICAL),
        (r'cursor\.execute\s*\(\s*["\'].*%s.*%', "SQL Injection (% formatting)", "CWE-89", SecuritySeverity.HIGH),
        (r'os\.system\s*\(\s*["\']?\s*\+', "Command Injection", "CWE-78", SecuritySeverity.CRITICAL),
        (r'subprocess\.(run|call|Popen)\s*\(\s*["\']?\s*\+', "Command Injection", "CWE-78", SecuritySeverity.CRITICAL),
        (r'subprocess\.(run|call|Popen)\s*\(\s*f["\']', "Command Injection (f-string)", "CWE-78", SecuritySeverity.CRITICAL),
        (r'eval\s*\(', "Code Injection (eval)", "CWE-94", SecuritySeverity.CRITICAL),
        (r'exec\s*\(', "Code Injection (exec)", "CWE-94", SecuritySeverity.CRITICAL),
        (r'pickle\.loads?\s*\(', "Unsafe Deserialization", "CWE-502", SecuritySeverity.HIGH),
        (r'yaml\.load\s*\([^,)]+\)', "Unsafe YAML Load", "CWE-502", SecuritySeverity.HIGH),
    ]

    # Insecure configuration patterns
    CONFIG_PATTERNS = [
        (r'DEBUG\s*=\s*True', "Debug Mode Enabled", "CWE-489", SecuritySeverity.MEDIUM),
        (r'verify\s*=\s*False', "SSL Verification Disabled", "CWE-295", SecuritySeverity.HIGH),
        (r'ALLOWED_HOSTS\s*=\s*\[\s*["\']?\*["\']?\s*\]', "Wildcard Host Allowed", "CWE-183", SecuritySeverity.MEDIUM),
        (r'chmod\s*\(\s*["\']?0?777', "World-writable Permissions", "CWE-732", SecuritySeverity.MEDIUM),
    ]

    # File extensions to scan
    SCAN_EXTENSIONS = {".py", ".js", ".ts", ".yaml", ".yml", ".json", ".sh", ".bash", ".env"}

    # Directories to skip
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".snapshots"}

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.findings: List[SecurityFinding] = []
        self.finding_counter = 0

    def _generate_finding_id(self) -> str:
        """Generate unique finding ID."""
        self.finding_counter += 1
        return f"SEC-{datetime.utcnow().strftime('%Y%m%d')}-{self.finding_counter:04d}"

    def _calculate_entropy(self, data: str) -> float:
        """Calculate Shannon entropy."""
        if not data:
            return 0
        freq = {}
        for char in data:
            freq[char] = freq.get(char, 0) + 1
        entropy = 0
        for count in freq.values():
            p = count / len(data)
            entropy -= p * math.log2(p)
        return entropy

    def scan_file(self, file_path: Path) -> List[SecurityFinding]:
        """Scan a single file for security issues."""
        findings = []

        try:
            content = file_path.read_text(errors='ignore')
            lines = content.split('\n')
        except Exception:
            return findings

        rel_path = str(file_path)

        # Scan for secrets
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//'):
                continue

            for pattern, secret_type, cwe_id in self.SECRET_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        finding_id=self._generate_finding_id(),
                        category="secrets",
                        severity=SecuritySeverity.CRITICAL,
                        title=f"Hardcoded {secret_type} Detected",
                        description=f"Potential hardcoded {secret_type} found in source code",
                        file_path=rel_path,
                        line_number=line_num,
                        code_snippet=line.strip(),
                        remediation=f"Remove hardcoded {secret_type} and use environment variables",
                        cwe_id=cwe_id,
                        confidence=0.9
                    ))

            # Check for high-entropy strings (potential secrets)
            strings = re.findall(r'["\']([a-zA-Z0-9_\-]{20,})["\']', line)
            for s in strings:
                entropy = self._calculate_entropy(s)
                if entropy > 4.5:
                    findings.append(SecurityFinding(
                        finding_id=self._generate_finding_id(),
                        category="secrets",
                        severity=SecuritySeverity.MEDIUM,
                        title="High-Entropy String Detected",
                        description=f"String with high entropy ({entropy:.2f}) may be a secret",
                        file_path=rel_path,
                        line_number=line_num,
                        code_snippet=s[:30] + "...",
                        remediation="Verify if this is a secret and move to secure configuration",
                        cwe_id="CWE-798",
                        confidence=0.6
                    ))

        # Scan for injection vulnerabilities
        for line_num, line in enumerate(lines, 1):
            for pattern, vuln_type, cwe_id, severity in self.INJECTION_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        finding_id=self._generate_finding_id(),
                        category="injection",
                        severity=severity,
                        title=f"{vuln_type} Vulnerability",
                        description=f"Potential {vuln_type} vulnerability detected",
                        file_path=rel_path,
                        line_number=line_num,
                        code_snippet=line.strip(),
                        remediation=f"Use parameterized queries or safe APIs to prevent {vuln_type}",
                        cwe_id=cwe_id,
                        confidence=0.8
                    ))

        # Scan for insecure configurations
        for line_num, line in enumerate(lines, 1):
            for pattern, config_issue, cwe_id, severity in self.CONFIG_PATTERNS:
                if re.search(pattern, line):
                    findings.append(SecurityFinding(
                        finding_id=self._generate_finding_id(),
                        category="configuration",
                        severity=severity,
                        title=f"Insecure Configuration: {config_issue}",
                        description=f"{config_issue} can lead to security vulnerabilities",
                        file_path=rel_path,
                        line_number=line_num,
                        code_snippet=line.strip(),
                        remediation=f"Review and secure the configuration for {config_issue}",
                        cwe_id=cwe_id,
                        confidence=0.9
                    ))

        return findings

    def scan_directory(self, scan_path: Optional[str] = None) -> ScanResult:
        """Scan a directory for security issues."""
        import time
        start_time = time.time()

        target = Path(scan_path) if scan_path else self.base_path
        self.findings = []
        self.finding_counter = 0
        files_scanned = 0

        for file_path in target.rglob("*"):
            if file_path.is_file():
                # Skip excluded directories
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue

                # Only scan relevant extensions
                if file_path.suffix not in self.SCAN_EXTENSIONS:
                    continue

                files_scanned += 1
                self.findings.extend(self.scan_file(file_path))

        duration_ms = int((time.time() - start_time) * 1000)

        # Calculate summary
        summary = {
            "critical": sum(1 for f in self.findings if f.severity == SecuritySeverity.CRITICAL),
            "high": sum(1 for f in self.findings if f.severity == SecuritySeverity.HIGH),
            "medium": sum(1 for f in self.findings if f.severity == SecuritySeverity.MEDIUM),
            "low": sum(1 for f in self.findings if f.severity == SecuritySeverity.LOW),
            "info": sum(1 for f in self.findings if f.severity == SecuritySeverity.INFO),
            "total": len(self.findings)
        }

        return ScanResult(
            scan_id=f"SCAN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            scan_path=str(target),
            duration_ms=duration_ms,
            files_scanned=files_scanned,
            findings=self.findings,
            summary=summary
        )

    def check_category(self, category: str, scan_path: Optional[str] = None) -> List[SecurityFinding]:
        """Check for specific category of issues."""
        result = self.scan_directory(scan_path)
        return [f for f in result.findings if f.category == category]

def main():
    parser = argparse.ArgumentParser(description="the system Security Scanner")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for vulnerabilities")
    scan_parser.add_argument("--path", default=".", help="Path to scan")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check specific category")
    check_parser.add_argument("--type", required=True, choices=["secrets", "injection", "configuration"])
    check_parser.add_argument("--path", default=".", help="Path to scan")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate security report")
    report_parser.add_argument("--path", default=".", help="Path to scan")
    report_parser.add_argument("--output", "-o", help="Output file")

    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--severity", help="Filter by severity levels (comma-separated: critical,high,medium,low,info)")

    args = parser.parse_args()

    scanner = SecurityScanner()

    # Parse severity filter if provided
    severity_filter = None
    if hasattr(args, 'severity') and args.severity:
        severity_filter = set(s.strip().lower() for s in args.severity.split(','))

    if args.command == "scan":
        result = scanner.scan_directory(args.path)

        # Apply severity filter
        if severity_filter:
            result.findings = [f for f in result.findings if f.severity in severity_filter]
            # Recalculate summary
            result.summary = {
                "critical": sum(1 for f in result.findings if f.severity == SecuritySeverity.CRITICAL),
                "high": sum(1 for f in result.findings if f.severity == SecuritySeverity.HIGH),
                "medium": sum(1 for f in result.findings if f.severity == SecuritySeverity.MEDIUM),
                "low": sum(1 for f in result.findings if f.severity == SecuritySeverity.LOW),
                "info": sum(1 for f in result.findings if f.severity == SecuritySeverity.INFO),
                "total": len(result.findings)
            }

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\nSecurity Scan Results")
            print("=" * 60)
            print(f"Scan ID: {result.scan_id}")
            print(f"Path: {result.scan_path}")
            print(f"Files Scanned: {result.files_scanned}")
            print(f"Duration: {result.duration_ms}ms")
            print(f"\nFindings Summary:")
            print(f"  Critical: {result.summary['critical']}")
            print(f"  High: {result.summary['high']}")
            print(f"  Medium: {result.summary['medium']}")
            print(f"  Low: {result.summary['low']}")
            print(f"  Total: {result.summary['total']}")

            if result.findings:
                print(f"\nTop Findings:")
                for f in result.findings[:10]:
                    icon = {"critical": "\U0001f534", "high": "\U0001f7e0", "medium": "\U0001f7e1", "low": "\U0001f7e2"}.get(f.severity, "\u26aa")
                    print(f"\n  {icon} [{f.severity.upper()}] {f.title}")
                    print(f"     File: {f.file_path}:{f.line_number}")
                    print(f"     {f.description}")

    elif args.command == "check":
        findings = scanner.check_category(args.type, args.path)

        if args.format == "json":
            print(json.dumps([f.to_dict() for f in findings], indent=2))
        else:
            print(f"\n{args.type.title()} Check Results: {len(findings)} findings")
            for f in findings:
                print(f"\n  [{f.severity.upper()}] {f.title}")
                print(f"     {f.file_path}:{f.line_number}")

    elif args.command == "report":
        result = scanner.scan_directory(args.path)

        # Apply severity filter
        if severity_filter:
            result.findings = [f for f in result.findings if f.severity in severity_filter]
            result.summary = {
                "critical": sum(1 for f in result.findings if f.severity == SecuritySeverity.CRITICAL),
                "high": sum(1 for f in result.findings if f.severity == SecuritySeverity.HIGH),
                "medium": sum(1 for f in result.findings if f.severity == SecuritySeverity.MEDIUM),
                "low": sum(1 for f in result.findings if f.severity == SecuritySeverity.LOW),
                "info": sum(1 for f in result.findings if f.severity == SecuritySeverity.INFO),
                "total": len(result.findings)
            }

        report = result.to_dict()

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(report, indent=2))

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
