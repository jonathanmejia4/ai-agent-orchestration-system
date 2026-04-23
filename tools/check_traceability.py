#!/usr/bin/env python3
"""
Template Traceability Metadata Validator

Validates that generated output files contain required the system provenance headers
for Traceability by Construction compliance.

Usage:
    python3 tools/check_traceability.py <file>
    python3 tools/check_traceability.py --files file1.py file2.py
    python3 tools/check_traceability.py <file> --required-headers template,template-version
    python3 tools/check_traceability.py <file> --verbose
    python3 tools/check_traceability.py --help

Exit Codes:
    0 - All required headers present and valid
    1 - Missing required headers
    2 - Invalid header format or values

Referenced in:
    - PLANNING/TEMPLATE_COMPLIANCE_POLICY.md:179, 278, 279

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field, asdict

# Recognized code families
RECOGNIZED_FAMILIES = {
    'python', 'javascript', 'typescript', 'go', 'rust', 'java',
    'shell', 'bash', 'yaml', 'json', 'markdown', 'sql',
    'config', 'template', 'schema', 'test', 'doc'
}

# Default required headers
DEFAULT_REQUIRED_HEADERS = ['template', 'template-version', 'template-family']

# Semver pattern
SEMVER_PATTERN = re.compile(r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$')

@dataclass
class HeaderInfo:
    """Information about a found header"""
    key: str
    value: str
    line_number: int
    valid: bool = True
    error: Optional[str] = None

@dataclass
class TraceabilityResult:
    """Result of traceability check"""
    file_path: str
    valid: bool = True
    headers_found: Dict[str, HeaderInfo] = field(default_factory=dict)
    missing_headers: List[str] = field(default_factory=list)
    invalid_headers: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path': self.file_path,
            'valid': self.valid,
            'headers_found': {k: asdict(v) for k, v in self.headers_found.items()},
            'missing_headers': self.missing_headers,
            'invalid_headers': self.invalid_headers,
            'errors': self.errors
        }

class TraceabilityChecker:
    """Validates the system traceability metadata in generated files"""

    # Pattern to match @saf:<key>=<value> headers
    HEADER_PATTERN = re.compile(r'@saf:([a-zA-Z0-9_-]+)=([^\s\n\r]+)')

    def __init__(self, required_headers: Optional[List[str]] = None,
                 verbose: bool = False):
        self.required_headers = set(required_headers or DEFAULT_REQUIRED_HEADERS)
        self.verbose = verbose

    def log(self, message: str):
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def validate_header_value(self, key: str, value: str) -> Tuple[bool, Optional[str]]:
        """Validate header value based on key type"""
        if key == 'template-version':
            # Must be valid semver
            if not SEMVER_PATTERN.match(value):
                return False, f"Invalid semver format: {value}"

        elif key == 'template-family':
            # Must be recognized family
            if value.lower() not in RECOGNIZED_FAMILIES:
                # Warn but don't fail for unknown families
                self.log(f"Warning: Unrecognized family '{value}'")

        elif key == 'template':
            # Must be non-empty
            if not value or value.isspace():
                return False, "Template name cannot be empty"

        return True, None

    def check_file(self, file_path: Path) -> TraceabilityResult:
        """Check a single file for traceability headers"""
        result = TraceabilityResult(file_path=str(file_path))

        if not file_path.exists():
            result.valid = False
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            result.valid = False
            result.errors.append(f"Error reading file: {e}")
            return result

        # Search for @saf: headers in first 100 lines (header section)
        lines = content.split('\n')[:100]
        found_keys: Set[str] = set()

        for i, line in enumerate(lines, 1):
            matches = self.HEADER_PATTERN.findall(line)
            for key, value in matches:
                self.log(f"Found header at line {i}: @saf:{key}={value}")

                # Validate the header value
                valid, error = self.validate_header_value(key, value)

                header_info = HeaderInfo(
                    key=key,
                    value=value,
                    line_number=i,
                    valid=valid,
                    error=error
                )

                result.headers_found[key] = header_info
                found_keys.add(key)

                if not valid:
                    result.invalid_headers.append(key)

        # Check for missing required headers
        for required in self.required_headers:
            if required not in found_keys:
                result.missing_headers.append(required)

        # Determine overall validity
        result.valid = (
            len(result.missing_headers) == 0 and
            len(result.invalid_headers) == 0 and
            len(result.errors) == 0
        )

        return result

    def check_files(self, file_paths: List[Path]) -> List[TraceabilityResult]:
        """Check multiple files"""
        return [self.check_file(fp) for fp in file_paths]

def print_result(result: TraceabilityResult, verbose: bool = False):
    """Print result for a single file"""
    if result.valid:
        print(f"\033[92m✅ Traceability metadata valid: {result.file_path}\033[0m")
    else:
        print(f"\033[91m❌ Traceability check failed: {result.file_path}\033[0m")

    if result.missing_headers:
        print(f"   Missing headers: {', '.join(result.missing_headers)}")

    if result.invalid_headers:
        print(f"   Invalid headers: {', '.join(result.invalid_headers)}")
        for key in result.invalid_headers:
            if key in result.headers_found:
                header = result.headers_found[key]
                print(f"      {key}: {header.error}")

    if result.errors:
        for error in result.errors:
            print(f"   Error: {error}")

    if verbose and result.headers_found:
        print(f"   Found headers:")
        for key, header in result.headers_found.items():
            status = "✓" if header.valid else "✗"
            print(f"      {status} @saf:{key}={header.value} (line {header.line_number})")

def print_summary(results: List[TraceabilityResult], format: str = "text"):
    """Print summary of all results"""
    if format == "json":
        output = {
            'total': len(results),
            'passed': sum(1 for r in results if r.valid),
            'failed': sum(1 for r in results if not r.valid),
            'results': [r.to_dict() for r in results]
        }
        print(json.dumps(output, indent=2))
        return

    passed = sum(1 for r in results if r.valid)
    failed = len(results) - passed

    print()
    if failed == 0:
        print(f"\033[92m✅ All {passed} file(s) passed traceability checks\033[0m")
    else:
        print(f"\033[91m❌ {failed}/{len(results)} file(s) failed traceability checks\033[0m")

def main():
    parser = argparse.ArgumentParser(
        description='Validate the system traceability metadata in generated files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check single file
    %(prog)s generated_code.py

    # Check multiple files
    %(prog)s --files file1.py file2.py file3.py

    # Custom required headers
    %(prog)s file.py --required-headers template,template-version

    # Verbose output
    %(prog)s file.py --verbose

    # JSON output
    %(prog)s file.py --json

Exit Codes:
    0 - All required headers present and valid
    1 - Missing required headers
    2 - Invalid header format or values
        """
    )

    parser.add_argument('file', nargs='?', type=Path,
                       help='File to check (or use --files for multiple)')
    parser.add_argument('--files', '-f', nargs='+', type=Path,
                       help='Multiple files to check')
    parser.add_argument('--required-headers', '-r',
                       default=','.join(DEFAULT_REQUIRED_HEADERS),
                       help=f'Comma-separated required headers (default: {",".join(DEFAULT_REQUIRED_HEADERS)})')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')

    args = parser.parse_args()

    # Collect files to check
    files_to_check: List[Path] = []
    if args.file:
        files_to_check.append(args.file)
    if args.files:
        files_to_check.extend(args.files)

    if not files_to_check:
        parser.print_help()
        sys.exit(2)

    # Parse required headers
    required_headers = [h.strip() for h in args.required_headers.split(',')]

    # Run checks
    checker = TraceabilityChecker(
        required_headers=required_headers,
        verbose=args.verbose
    )

    results = checker.check_files(files_to_check)

    # Print results
    if args.json:
        print_summary(results, format="json")
    else:
        for result in results:
            print_result(result, verbose=args.verbose)
        if len(results) > 1:
            print_summary(results)

    # Determine exit code
    has_missing = any(r.missing_headers for r in results)
    has_invalid = any(r.invalid_headers for r in results)
    has_errors = any(r.errors for r in results)

    if has_errors or has_invalid:
        sys.exit(2)
    elif has_missing:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
