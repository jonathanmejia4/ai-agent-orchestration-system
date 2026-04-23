#!/usr/bin/env python3
"""
detect_vendor_type_leakage.py - Vendor Type Leakage Detector

Document Version: 1.0.0
Last Updated: 2026-01-09
Owner: PM
Classification: CRITICAL - Security Validation Tool

Purpose:
    Detects vendor-specific type information leaking into public APIs.
    Identifies coupling to specific vendors/implementations that should be abstracted.
    Ensures clean separation between internal implementations and public interfaces.

Usage:
    python3 detect_vendor_type_leakage.py --dir src/
    python3 detect_vendor_type_leakage.py --file api/endpoints.py --strict
    python3 detect_vendor_type_leakage.py --dir src/ --vendor aws --vendor azure
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class LeakageViolation:
    """Represents a vendor type leakage violation."""
    file_path: str
    line_number: int
    vendor: str
    leak_type: str
    code_snippet: str
    severity: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "vendor": self.vendor,
            "leak_type": self.leak_type,
            "code_snippet": self.code_snippet,
            "severity": self.severity,
            "recommendation": self.recommendation
        }


class VendorTypeLeakageDetector:
    """Detects vendor-specific types leaking into APIs."""

    # Vendor-specific patterns to detect
    VENDOR_PATTERNS = {
        "aws": {
            "imports": [
                r"from\s+boto3",
                r"import\s+boto3",
                r"from\s+botocore",
                r"from\s+aws_cdk",
            ],
            "types": [
                r"S3Object",
                r"DynamoDBTable",
                r"LambdaFunction",
                r"EC2Instance",
                r"boto3\.\w+",
                r"botocore\.\w+",
            ],
            "strings": [
                r"arn:aws:",
                r"s3://",
                r"dynamodb://",
            ],
        },
        "azure": {
            "imports": [
                r"from\s+azure\.",
                r"import\s+azure\.",
            ],
            "types": [
                r"BlobClient",
                r"ContainerClient",
                r"CosmosClient",
                r"AzureFunction",
            ],
            "strings": [
                r"https://\w+\.blob\.core\.windows\.net",
                r"https://\w+\.documents\.azure\.com",
            ],
        },
        "gcp": {
            "imports": [
                r"from\s+google\.cloud",
                r"import\s+google\.cloud",
            ],
            "types": [
                r"storage\.Client",
                r"bigquery\.Client",
                r"firestore\.Client",
            ],
            "strings": [
                r"gs://",
                r"projects/[^/]+/locations",
            ],
        },
        "database": {
            "imports": [
                r"from\s+sqlalchemy",
                r"import\s+psycopg2",
                r"import\s+mysql\.connector",
                r"import\s+pymongo",
            ],
            "types": [
                r"Session",
                r"Engine",
                r"Connection",
                r"Cursor",
                r"MongoClient",
            ],
            "strings": [
                r"postgresql://",
                r"mysql://",
                r"mongodb://",
            ],
        },
    }

    # Files/patterns that are allowed to have vendor types
    ALLOWED_LOCATIONS = [
        r"adapters?/",
        r"providers?/",
        r"infrastructure/",
        r"impl/",
        r"_impl\.py$",
        r"_adapter\.py$",
    ]

    def __init__(self, vendors: Optional[List[str]] = None, strict: bool = False):
        self.vendors = vendors or list(self.VENDOR_PATTERNS.keys())
        self.strict = strict

    def _is_allowed_location(self, file_path: str) -> bool:
        """Check if file is in an allowed location for vendor types."""
        for pattern in self.ALLOWED_LOCATIONS:
            if re.search(pattern, file_path):
                return True
        return False

    def _check_imports(self, content: str, file_path: str, vendor: str) -> List[LeakageViolation]:
        """Check for vendor-specific imports in public API files."""
        violations = []
        patterns = self.VENDOR_PATTERNS.get(vendor, {}).get("imports", [])
        lines = content.split('\n')

        for pattern in patterns:
            regex = re.compile(pattern)
            for i, line in enumerate(lines, 1):
                if regex.search(line):
                    violations.append(LeakageViolation(
                        file_path=file_path,
                        line_number=i,
                        vendor=vendor,
                        leak_type="import",
                        code_snippet=line.strip()[:80],
                        severity="HIGH",
                        recommendation=f"Move {vendor} imports to adapter/provider layer"
                    ))

        return violations

    def _check_type_annotations(self, content: str, file_path: str, vendor: str) -> List[LeakageViolation]:
        """Check for vendor-specific types in function signatures."""
        violations = []
        type_patterns = self.VENDOR_PATTERNS.get(vendor, {}).get("types", [])
        lines = content.split('\n')

        # Look for type annotations
        for pattern in type_patterns:
            regex = re.compile(pattern)
            for i, line in enumerate(lines, 1):
                # Check function signatures and type hints
                if '->' in line or ':' in line:
                    if regex.search(line):
                        violations.append(LeakageViolation(
                            file_path=file_path,
                            line_number=i,
                            vendor=vendor,
                            leak_type="type_annotation",
                            code_snippet=line.strip()[:80],
                            severity="HIGH",
                            recommendation=f"Use abstract interface instead of {vendor}-specific type"
                        ))

        return violations

    def _check_string_literals(self, content: str, file_path: str, vendor: str) -> List[LeakageViolation]:
        """Check for vendor-specific string literals (URIs, ARNs, etc.)."""
        violations = []
        string_patterns = self.VENDOR_PATTERNS.get(vendor, {}).get("strings", [])
        lines = content.split('\n')

        for pattern in string_patterns:
            regex = re.compile(pattern)
            for i, line in enumerate(lines, 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue

                if regex.search(line):
                    violations.append(LeakageViolation(
                        file_path=file_path,
                        line_number=i,
                        vendor=vendor,
                        leak_type="string_literal",
                        code_snippet=line.strip()[:80],
                        severity="MEDIUM",
                        recommendation=f"Move {vendor}-specific URIs to configuration"
                    ))

        return violations

    def _check_return_types(self, file_path: Path, vendor: str) -> List[LeakageViolation]:
        """Check for vendor-specific return types using AST."""
        violations = []

        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return violations

        type_patterns = self.VENDOR_PATTERNS.get(vendor, {}).get("types", [])

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check return annotation
                if node.returns:
                    return_str = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
                    for pattern in type_patterns:
                        if re.search(pattern, return_str):
                            violations.append(LeakageViolation(
                                file_path=str(file_path),
                                line_number=node.lineno,
                                vendor=vendor,
                                leak_type="return_type",
                                code_snippet=f"def {node.name}(...) -> {return_str}",
                                severity="HIGH",
                                recommendation=f"Return abstract type instead of {vendor}-specific type"
                            ))

        return violations

    def check_file(self, file_path: Path) -> List[LeakageViolation]:
        """Check a single file for vendor type leakage."""
        violations = []

        # Skip allowed locations unless in strict mode
        if not self.strict and self._is_allowed_location(str(file_path)):
            return violations

        try:
            content = file_path.read_text()
        except Exception:
            return violations

        for vendor in self.vendors:
            violations.extend(self._check_imports(content, str(file_path), vendor))
            violations.extend(self._check_type_annotations(content, str(file_path), vendor))
            violations.extend(self._check_string_literals(content, str(file_path), vendor))
            violations.extend(self._check_return_types(file_path, vendor))

        return violations

    def check_directory(self, dir_path: Path, recursive: bool = True) -> List[LeakageViolation]:
        """Check all Python files in a directory."""
        violations = []

        if recursive:
            files = dir_path.rglob("*.py")
        else:
            files = dir_path.glob("*.py")

        for file_path in files:
            # Skip test files
            if "test" in file_path.name.lower():
                continue

            violations.extend(self.check_file(file_path))

        return violations


def main():
    parser = argparse.ArgumentParser(
        description="Detect vendor-specific type leakage in public APIs"
    )
    parser.add_argument(
        "--file", "-f",
        help="Single file to check"
    )
    parser.add_argument(
        "--dir", "-d",
        help="Directory to check"
    )
    parser.add_argument(
        "--vendor", "-v",
        action="append",
        help="Specific vendors to check (can be repeated)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Check all files including adapters/providers"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for report"
    )
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Exit with error on HIGH severity violations"
    )

    args = parser.parse_args()

    if not args.file and not args.dir:
        print("Error: Must specify --file or --dir", file=sys.stderr)
        return 1

    detector = VendorTypeLeakageDetector(
        vendors=args.vendor,
        strict=args.strict
    )

    if args.file:
        violations = detector.check_file(Path(args.file))
    else:
        violations = detector.check_directory(Path(args.dir))

    # Sort by severity
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    violations.sort(key=lambda v: (severity_order.get(v.severity, 99), v.file_path))

    # Output results
    if args.format == "json":
        result = {
            "total_violations": len(violations),
            "by_vendor": {},
            "by_type": {},
            "violations": [v.to_dict() for v in violations]
        }

        for v in violations:
            result["by_vendor"][v.vendor] = result["by_vendor"].get(v.vendor, 0) + 1
            result["by_type"][v.leak_type] = result["by_type"].get(v.leak_type, 0) + 1

        output = json.dumps(result, indent=2)
    else:
        lines = []
        lines.append("=" * 60)
        lines.append("VENDOR TYPE LEAKAGE REPORT")
        lines.append("=" * 60)
        lines.append(f"\nTotal violations: {len(violations)}")

        if violations:
            # Summary by vendor
            by_vendor: Dict[str, int] = {}
            for v in violations:
                by_vendor[v.vendor] = by_vendor.get(v.vendor, 0) + 1

            lines.append("\nViolations by vendor:")
            for vendor, count in sorted(by_vendor.items()):
                lines.append(f"  {vendor}: {count}")

            lines.append("\n" + "-" * 60)
            lines.append("VIOLATIONS:")
            lines.append("-" * 60)

            current_file = None
            for v in violations:
                if v.file_path != current_file:
                    current_file = v.file_path
                    lines.append(f"\n{v.file_path}:")

                icon = "🔴" if v.severity == "HIGH" else "🟡"
                lines.append(f"  {icon} Line {v.line_number}: [{v.vendor}] {v.leak_type}")
                lines.append(f"     {v.code_snippet}")
                lines.append(f"     → {v.recommendation}")

        lines.append("\n" + "=" * 60)
        if not violations:
            lines.append("✅ No vendor type leakage detected")
        elif any(v.severity == "HIGH" for v in violations):
            lines.append("❌ HIGH severity vendor leakage found!")
        else:
            lines.append("⚠️ Vendor type leakage detected - review recommended")

        output = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)

    # Exit code
    if args.fail_on_high and any(v.severity == "HIGH" for v in violations):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
