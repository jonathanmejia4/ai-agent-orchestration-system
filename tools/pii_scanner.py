#!/usr/bin/env python3
"""
PII Scanner Tool

Scans files, databases, and logs for Personally Identifiable Information (PII).

Requirements (per LANE_E.md Data Protection Files):
- Pattern detection for common PII (emails, phone numbers, SSN, credit cards)
- Name detection (common first/last names)
- Address pattern detection
- Custom PII patterns configurable per product
- Integration with LogBook/support/conversations/ scanning
- Report generation with PII locations and severity

Per LogBook/support/README.md:74:
- "Personal details (names, addresses) must be masked"

Usage:
    python pii_scanner.py --scan <file_or_directory>   # Scan for PII
    python pii_scanner.py --scan-logbook               # Scan support conversations
    python pii_scanner.py --report <output_file>       # Generate PII report
    python pii_scanner.py --test                       # Run self-test
"""

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    CUSTOM = "custom"

class PIISeverity(Enum):
    """Severity levels for PII findings."""
    CRITICAL = "critical"  # SSN, credit card, passport
    HIGH = "high"          # Full name + address combination
    MEDIUM = "medium"      # Email, phone number
    LOW = "low"            # Partial name, IP address

@dataclass
class PIIPattern:
    """Definition of a PII detection pattern."""
    pii_type: PIIType
    pattern: re.Pattern
    severity: PIISeverity
    description: str
    validator: Optional[callable] = None

@dataclass
class PIIFinding:
    """A single PII detection finding."""
    pii_type: PIIType
    severity: PIISeverity
    value: str
    masked_value: str
    file_path: str
    line_number: int
    context: str
    detected_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pii_type": self.pii_type.value,
            "severity": self.severity.value,
            "masked_value": self.masked_value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self._mask_context(),
            "detected_at": self.detected_at.isoformat()
        }

    def _mask_context(self) -> str:
        """Return context with PII masked."""
        return self.context.replace(self.value, self.masked_value)

@dataclass
class PIIScanResult:
    """Result of a PII scan."""
    scan_path: str
    scan_time: datetime
    files_scanned: int
    findings: list[PIIFinding]
    errors: list[str] = field(default_factory=list)

    @property
    def total_findings(self) -> int:
        """Total number of PII findings."""
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        """Count of critical severity findings."""
        return sum(1 for f in self.findings if f.severity == PIISeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count of high severity findings."""
        return sum(1 for f in self.findings if f.severity == PIISeverity.HIGH)

    def summary(self) -> str:
        """Generate summary of scan results."""
        lines = [
            f"PII Scan Results",
            f"================",
            f"Scan Path: {self.scan_path}",
            f"Scan Time: {self.scan_time.isoformat()}",
            f"Files Scanned: {self.files_scanned}",
            f"",
            f"Findings Summary:",
            f"  Critical: {self.critical_count}",
            f"  High: {self.high_count}",
            f"  Medium: {sum(1 for f in self.findings if f.severity == PIISeverity.MEDIUM)}",
            f"  Low: {sum(1 for f in self.findings if f.severity == PIISeverity.LOW)}",
            f"  Total: {self.total_findings}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "scan_path": self.scan_path,
            "scan_time": self.scan_time.isoformat(),
            "files_scanned": self.files_scanned,
            "findings": [f.to_dict() for f in self.findings],
            "errors": self.errors,
            "summary": {
                "total": self.total_findings,
                "critical": self.critical_count,
                "high": self.high_count
            }
        }

class PIIPatternLibrary:
    """
    Library of PII detection patterns.

    Includes built-in patterns for common PII types
    and support for custom patterns.
    """

    def __init__(self):
        """Initialize pattern library with default patterns."""
        self._patterns: list[PIIPattern] = []
        self._load_default_patterns()

    def _load_default_patterns(self) -> None:
        """Load default PII detection patterns."""
        # Email addresses
        self._patterns.append(PIIPattern(
            pii_type=PIIType.EMAIL,
            pattern=re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                re.IGNORECASE
            ),
            severity=PIISeverity.MEDIUM,
            description="Email address"
        ))

        # Phone numbers (various formats)
        self._patterns.append(PIIPattern(
            pii_type=PIIType.PHONE,
            pattern=re.compile(
                r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ),
            severity=PIISeverity.MEDIUM,
            description="Phone number (US format)"
        ))

        # Social Security Numbers
        self._patterns.append(PIIPattern(
            pii_type=PIIType.SSN,
            pattern=re.compile(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b'),
            severity=PIISeverity.CRITICAL,
            description="Social Security Number",
            validator=self._validate_ssn
        ))

        # Credit Card Numbers (major brands)
        self._patterns.append(PIIPattern(
            pii_type=PIIType.CREDIT_CARD,
            pattern=re.compile(
                r'\b(?:4[0-9]{12}(?:[0-9]{3})?|'  # Visa
                r'5[1-5][0-9]{14}|'               # Mastercard
                r'3[47][0-9]{13}|'                # Amex
                r'6(?:011|5[0-9]{2})[0-9]{12})\b'  # Discover
            ),
            severity=PIISeverity.CRITICAL,
            description="Credit card number",
            validator=self._validate_credit_card
        ))

        # IP Addresses
        self._patterns.append(PIIPattern(
            pii_type=PIIType.IP_ADDRESS,
            pattern=re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
            ),
            severity=PIISeverity.LOW,
            description="IP address"
        ))

        # Date of Birth patterns
        self._patterns.append(PIIPattern(
            pii_type=PIIType.DATE_OF_BIRTH,
            pattern=re.compile(
                r'\b(?:DOB|date of birth|born|birthday)[\s:]+\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
                re.IGNORECASE
            ),
            severity=PIISeverity.MEDIUM,
            description="Date of birth"
        ))

        # US Street Address patterns
        self._patterns.append(PIIPattern(
            pii_type=PIIType.ADDRESS,
            pattern=re.compile(
                r'\b\d{1,5}\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|'
                r'Drive|Dr|Lane|Ln|Court|Ct|Way|Circle|Cir)\.?(?:\s+(?:Apt|Suite|Unit|#)\s*\w+)?\b',
                re.IGNORECASE
            ),
            severity=PIISeverity.HIGH,
            description="Street address"
        ))

    def _validate_ssn(self, value: str) -> bool:
        """
        Validate SSN format and rules.

        SSN cannot start with 000, 666, or 900-999.
        Middle digits cannot be 00.
        Last digits cannot be 0000.
        """
        digits = re.sub(r'[^\d]', '', value)
        if len(digits) != 9:
            return False

        area = int(digits[:3])
        group = int(digits[3:5])
        serial = int(digits[5:])

        # Invalid area numbers
        if area == 0 or area == 666 or area >= 900:
            return False

        # Invalid group or serial
        if group == 0 or serial == 0:
            return False

        return True

    def _validate_credit_card(self, value: str) -> bool:
        """
        Validate credit card using Luhn algorithm.
        """
        digits = re.sub(r'[^\d]', '', value)
        if len(digits) < 13 or len(digits) > 19:
            return False

        # Luhn algorithm
        total = 0
        for i, digit in enumerate(reversed(digits)):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n

        return total % 10 == 0

    def add_pattern(self, pattern: PIIPattern) -> None:
        """Add a custom PII pattern."""
        self._patterns.append(pattern)

    def get_patterns(self) -> list[PIIPattern]:
        """Get all registered patterns."""
        return self._patterns.copy()

class PIIMasker:
    """
    Utility for masking PII values.

    Different masking strategies based on PII type.
    """

    @staticmethod
    def mask(value: str, pii_type: PIIType) -> str:
        """
        Mask a PII value based on its type.

        Args:
            value: The PII value to mask
            pii_type: Type of PII

        Returns:
            Masked value
        """
        if pii_type == PIIType.EMAIL:
            # user@domain.com -> u***@d***.com
            parts = value.split('@')
            if len(parts) == 2:
                user = parts[0][0] + '***' if parts[0] else '***'
                domain_parts = parts[1].split('.')
                domain = domain_parts[0][0] + '***' if domain_parts[0] else '***'
                tld = '.'.join(domain_parts[1:]) if len(domain_parts) > 1 else 'com'
                return f"{user}@{domain}.{tld}"
            return '***@***.***'

        elif pii_type == PIIType.PHONE:
            # Show last 4 digits only
            digits = re.sub(r'[^\d]', '', value)
            return f"***-***-{digits[-4:]}" if len(digits) >= 4 else '***-***-****'

        elif pii_type == PIIType.SSN:
            # Show last 4 digits only
            digits = re.sub(r'[^\d]', '', value)
            return f"***-**-{digits[-4:]}" if len(digits) >= 4 else '***-**-****'

        elif pii_type == PIIType.CREDIT_CARD:
            # Show last 4 digits only
            digits = re.sub(r'[^\d]', '', value)
            return f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else '****-****-****-****'

        elif pii_type == PIIType.IP_ADDRESS:
            # Show first octet only
            parts = value.split('.')
            return f"{parts[0]}.***.***.**" if parts else '***.***.***.***'

        elif pii_type == PIIType.ADDRESS:
            # Mask street number and name
            return '[ADDRESS REDACTED]'

        elif pii_type == PIIType.NAME:
            # Show first initial only
            parts = value.split()
            return ' '.join(p[0] + '***' for p in parts if p)

        else:
            # Generic masking
            return '[REDACTED]'

class PIIScanner:
    """
    Main PII scanning utility.

    Scans files and directories for PII using pattern matching.
    """

    # File extensions to scan by default
    DEFAULT_EXTENSIONS = {
        '.txt', '.log', '.md', '.json', '.yaml', '.yml',
        '.csv', '.py', '.js', '.ts', '.html', '.xml',
        '.sql', '.env', '.cfg', '.ini', '.conf'
    }

    # Directories to skip
    SKIP_DIRS = {
        '.git', 'node_modules', '__pycache__', '.venv',
        'venv', 'env', '.env', 'build', 'dist'
    }

    def __init__(
        self,
        pattern_library: Optional[PIIPatternLibrary] = None,
        extensions: Optional[set[str]] = None
    ):
        """
        Initialize PII scanner.

        Args:
            pattern_library: Custom pattern library (uses default if not provided)
            extensions: File extensions to scan (uses default if not provided)
        """
        self._patterns = pattern_library or PIIPatternLibrary()
        self._extensions = extensions or self.DEFAULT_EXTENSIONS
        self._masker = PIIMasker()

    def scan_file(self, file_path: str) -> list[PIIFinding]:
        """
        Scan a single file for PII.

        Args:
            file_path: Path to file to scan

        Returns:
            List of PII findings
        """
        findings = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                for pattern in self._patterns.get_patterns():
                    matches = pattern.pattern.findall(line)
                    for match in matches:
                        # Apply validator if present
                        if pattern.validator and not pattern.validator(match):
                            continue

                        finding = PIIFinding(
                            pii_type=pattern.pii_type,
                            severity=pattern.severity,
                            value=match,
                            masked_value=self._masker.mask(match, pattern.pii_type),
                            file_path=file_path,
                            line_number=line_num,
                            context=line.strip()[:200]
                        )
                        findings.append(finding)
                        logger.debug(
                            f"Found {pattern.pii_type.value} in {file_path}:{line_num}"
                        )

        except Exception as e:
            logger.error(f"Error scanning {file_path}: {e}")

        return findings

    def scan_directory(
        self,
        dir_path: str,
        recursive: bool = True
    ) -> PIIScanResult:
        """
        Scan a directory for PII.

        Args:
            dir_path: Path to directory to scan
            recursive: Whether to scan subdirectories

        Returns:
            PIIScanResult with all findings
        """
        start_time = datetime.utcnow()
        all_findings = []
        files_scanned = 0
        errors = []

        path = Path(dir_path)
        if not path.exists():
            return PIIScanResult(
                scan_path=dir_path,
                scan_time=start_time,
                files_scanned=0,
                findings=[],
                errors=[f"Path does not exist: {dir_path}"]
            )

        # Get files to scan
        if path.is_file():
            files = [path]
        elif recursive:
            files = [
                p for p in path.rglob('*')
                if p.is_file()
                and p.suffix.lower() in self._extensions
                and not any(skip in p.parts for skip in self.SKIP_DIRS)
            ]
        else:
            files = [
                p for p in path.glob('*')
                if p.is_file()
                and p.suffix.lower() in self._extensions
            ]

        # Scan each file
        for file_path in files:
            try:
                findings = self.scan_file(str(file_path))
                all_findings.extend(findings)
                files_scanned += 1
            except Exception as e:
                errors.append(f"Error scanning {file_path}: {e}")
                logger.error(f"Error scanning {file_path}: {e}")

        return PIIScanResult(
            scan_path=dir_path,
            scan_time=start_time,
            files_scanned=files_scanned,
            findings=all_findings,
            errors=errors
        )

    def scan_logbook_conversations(self, logbook_path: str = "LogBook/support/conversations/") -> PIIScanResult:
        """
        Scan LogBook support conversations for PII.

        Per LogBook/support/README.md requirements, personal details
        must be masked in support conversations.

        Args:
            logbook_path: Path to conversations directory

        Returns:
            PIIScanResult with findings
        """
        logger.info(f"Scanning LogBook conversations at: {logbook_path}")
        return self.scan_directory(logbook_path, recursive=True)

def generate_report(result: PIIScanResult, output_path: str, format: str = "json") -> None:
    """
    Generate a PII scan report.

    Args:
        result: Scan results to report
        output_path: Path for output file
        format: Output format (json or text)
    """
    if format == "json":
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
    else:
        with open(output_path, 'w') as f:
            f.write(result.summary())
            f.write("\n\n")
            f.write("Detailed Findings:\n")
            f.write("-" * 60 + "\n")
            for finding in result.findings:
                f.write(f"\n{finding.pii_type.value.upper()} [{finding.severity.value}]\n")
                f.write(f"  File: {finding.file_path}:{finding.line_number}\n")
                f.write(f"  Masked: {finding.masked_value}\n")
                f.write(f"  Context: {finding._mask_context()[:100]}...\n")

    logger.info(f"Report saved to: {output_path}")

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PII Scanner - Detect Personally Identifiable Information"
    )
    parser.add_argument(
        "--scan",
        metavar="PATH",
        help="Scan a file or directory for PII"
    )
    parser.add_argument(
        "--scan-logbook",
        action="store_true",
        help="Scan LogBook/support/conversations/ for PII"
    )
    parser.add_argument(
        "--report",
        metavar="OUTPUT_FILE",
        help="Generate report to specified file"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Report format (default: json)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-test with test data"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scanner = PIIScanner()

    if args.scan:
        result = scanner.scan_directory(args.scan)
        print(result.summary())

        if args.report:
            generate_report(result, args.report, args.format)
        else:
            print("\nFindings:")
            for finding in result.findings[:10]:  # Show first 10
                print(f"  [{finding.severity.value}] {finding.pii_type.value}: "
                      f"{finding.masked_value} in {finding.file_path}:{finding.line_number}")
            if len(result.findings) > 10:
                print(f"  ... and {len(result.findings) - 10} more findings")

    elif args.scan_logbook:
        result = scanner.scan_logbook_conversations()
        print(result.summary())

        if args.report:
            generate_report(result, args.report, args.format)

    elif args.test:
        print("Running PII Scanner self-test...")
        print()

        test_data = [
            ("test@example.com", PIIType.EMAIL, True),
            ("555-123-4567", PIIType.PHONE, True),
            ("123-45-6789", PIIType.SSN, True),
            ("4111111111111111", PIIType.CREDIT_CARD, True),
            ("192.168.1.1", PIIType.IP_ADDRESS, True),
            ("123 Main Street", PIIType.ADDRESS, True),
            ("not-pii-data", None, False),
        ]

        for test_value, expected_type, should_match in test_data:
            # Create temp test line
            findings = []
            for pattern in scanner._patterns.get_patterns():
                if pattern.pattern.search(test_value):
                    findings.append(pattern.pii_type)

            if should_match:
                if expected_type in findings:
                    print(f"  PASS: '{test_value}' detected as {expected_type.value}")
                else:
                    print(f"  FAIL: '{test_value}' should be detected as {expected_type.value}")
            else:
                if not findings:
                    print(f"  PASS: '{test_value}' correctly not detected as PII")
                else:
                    print(f"  FAIL: '{test_value}' incorrectly detected as {findings}")

        # Test masking
        print("\nMasking tests:")
        masker = PIIMasker()
        print(f"  Email mask: test@example.com -> {masker.mask('test@example.com', PIIType.EMAIL)}")
        print(f"  Phone mask: 555-123-4567 -> {masker.mask('555-123-4567', PIIType.PHONE)}")
        print(f"  SSN mask: 123-45-6789 -> {masker.mask('123-45-6789', PIIType.SSN)}")
        print(f"  CC mask: 4111111111111111 -> {masker.mask('4111111111111111', PIIType.CREDIT_CARD)}")

        print("\nSelf-test complete.")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
