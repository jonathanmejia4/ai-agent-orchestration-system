#!/usr/bin/env python3
"""
scan_timestamps.py - Detect timestamp violations in generated code

Scans generated files for forbidden timestamp patterns that break idempotence.
Timestamps in code cause "generate twice, get different output" failures.

Exit codes:
  0 - No violations found
  1 - Violations found
  2 - File/parse error

Usage:
  python tools/scan_timestamps.py <path>
  python tools/scan_timestamps.py <path> --fix
  python tools/scan_timestamps.py <path> --format=json

Reference: IDEMPOTENT_GENERATION_POLICY.md:1018-1083
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Forbidden timestamp patterns by language
TIMESTAMP_PATTERNS = {
    # Python patterns
    "python": [
        (r"\bdatetime\.now\(\)", "datetime.now()"),
        (r"\bdatetime\.utcnow\(\)", "datetime.utcnow()"),
        (r"\btime\.time\(\)", "time.time()"),
        (r"\btime\.ctime\(\)", "time.ctime()"),
        (r"\btime\.strftime\(", "time.strftime()"),
        (r"\bdate\.today\(\)", "date.today()"),
        (r"\btimestamp\s*=\s*int\(time\.", "timestamp = int(time...)"),
    ],
    # JavaScript/TypeScript patterns
    "javascript": [
        (r"\bDate\.now\(\)", "Date.now()"),
        (r"\bnew Date\(\)", "new Date()"),
        (r"\bDate\(\)", "Date()"),
        (r"\.getTime\(\)", ".getTime()"),
        (r"\.toISOString\(\)", ".toISOString()"),
        (r"\bperformance\.now\(\)", "performance.now()"),
    ],
    # Java patterns
    "java": [
        (r"\bSystem\.currentTimeMillis\(\)", "System.currentTimeMillis()"),
        (r"\bSystem\.nanoTime\(\)", "System.nanoTime()"),
        (r"\bnew Date\(\)", "new Date()"),
        (r"\bInstant\.now\(\)", "Instant.now()"),
        (r"\bLocalDateTime\.now\(\)", "LocalDateTime.now()"),
        (r"\bZonedDateTime\.now\(\)", "ZonedDateTime.now()"),
    ],
    # Go patterns
    "go": [
        (r"\btime\.Now\(\)", "time.Now()"),
        (r"\btime\.Unix\(", "time.Unix()"),
    ],
    # Ruby patterns
    "ruby": [
        (r"\bTime\.now", "Time.now"),
        (r"\bTime\.new", "Time.new"),
        (r"\bDateTime\.now", "DateTime.now"),
    ],
    # System-specific patterns (allowed only in .task/ metadata)
    "saf": [
        (r"@saf:generated-at", "@saf:generated-at"),
        (r"generated_at:", "generated_at:"),
        (r"timestamp:", "timestamp:"),
    ],
}

# File extensions to language mapping
EXTENSION_MAP = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".yaml": "saf",
    ".yml": "saf",
}

# Directories to exclude
EXCLUDED_DIRS = {
    "node_modules",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    ".saf",
    "vendor",
}

# Files/patterns where timestamps are allowed (metadata only)
ALLOWED_PATTERNS = [
    r"\.task/.*",  # .task/ metadata files
    r"wiring\.yaml$",
    r"metadata\.yaml$",
    r"\.saf/.*",
]

@dataclass
class Violation:
    """Represents a timestamp violation."""
    file_path: str
    line_number: int
    line_content: str
    pattern_name: str
    language: str
    can_fix: bool = False

class TimestampScanner:
    """Scan files for timestamp violations."""

    def __init__(
        self,
        verbose: bool = False,
        include_metadata: bool = False
    ):
        self.verbose = verbose
        self.include_metadata = include_metadata
        self.violations: list[Violation] = []
        self.files_scanned: int = 0
        self.errors: list[str] = []

    def scan_path(self, path: Path) -> None:
        """Scan a file or directory for timestamp violations."""
        if path.is_file():
            self._scan_file(path)
        elif path.is_dir():
            self._scan_directory(path)
        else:
            self.errors.append(f"Path not found: {path}")

    def _scan_directory(self, dir_path: Path) -> None:
        """Recursively scan a directory."""
        for item in dir_path.iterdir():
            # Skip excluded directories
            if item.is_dir():
                if item.name in EXCLUDED_DIRS:
                    if self.verbose:
                        print(f"  Skipping excluded dir: {item}")
                    continue
                self._scan_directory(item)
            elif item.is_file():
                self._scan_file(item)

    def _scan_file(self, file_path: Path) -> None:
        """Scan a single file for violations."""
        # Check if file extension is supported
        ext = file_path.suffix.lower()
        if ext not in EXTENSION_MAP:
            return

        # Check if file is in allowed location (metadata)
        if not self.include_metadata:
            rel_path = str(file_path)
            for pattern in ALLOWED_PATTERNS:
                if re.search(pattern, rel_path):
                    if self.verbose:
                        print(f"  Skipping metadata file: {file_path}")
                    return

        language = EXTENSION_MAP[ext]
        patterns = TIMESTAMP_PATTERNS.get(language, [])

        # Add the system patterns for yaml files
        if ext in [".yaml", ".yml"]:
            patterns = TIMESTAMP_PATTERNS.get("saf", [])

        if not patterns:
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            self.files_scanned += 1

            for line_num, line in enumerate(lines, 1):
                for pattern, pattern_name in patterns:
                    if re.search(pattern, line):
                        # Check if it's in a comment
                        if self._is_in_comment(line, language):
                            continue

                        self.violations.append(Violation(
                            file_path=str(file_path),
                            line_number=line_num,
                            line_content=line.rstrip(),
                            pattern_name=pattern_name,
                            language=language,
                            can_fix=self._can_auto_fix(pattern_name)
                        ))

        except Exception as e:
            self.errors.append(f"Error reading {file_path}: {e}")

    def _is_in_comment(self, line: str, language: str) -> bool:
        """Check if the match is likely in a comment."""
        stripped = line.lstrip()

        if language == "python":
            return stripped.startswith("#")
        elif language in ["javascript", "java", "go"]:
            return stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")
        elif language == "ruby":
            return stripped.startswith("#")

        return False

    def _can_auto_fix(self, pattern_name: str) -> bool:
        """Determine if a violation can be auto-fixed."""
        # Most timestamp patterns can't be auto-fixed without breaking logic
        # Only system-specific metadata patterns could potentially be removed
        return pattern_name in ["@saf:generated-at", "generated_at:", "timestamp:"]

    def fix_violations(self, dry_run: bool = False) -> int:
        """Attempt to fix violations (remove the system metadata timestamps)."""
        fixed_count = 0
        files_to_fix: dict[str, list[int]] = {}

        # Group violations by file
        for v in self.violations:
            if v.can_fix:
                if v.file_path not in files_to_fix:
                    files_to_fix[v.file_path] = []
                files_to_fix[v.file_path].append(v.line_number)

        for file_path, line_numbers in files_to_fix.items():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # Remove lines with violations (in reverse order to preserve line numbers)
                for line_num in sorted(line_numbers, reverse=True):
                    if 1 <= line_num <= len(lines):
                        if dry_run:
                            print(f"  Would remove line {line_num} from {file_path}")
                        else:
                            lines[line_num - 1] = ""  # Clear the line
                        fixed_count += 1

                if not dry_run:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)

            except Exception as e:
                self.errors.append(f"Error fixing {file_path}: {e}")

        return fixed_count

    def get_summary(self) -> dict:
        """Get scan summary."""
        by_language = {}
        by_pattern = {}

        for v in self.violations:
            by_language[v.language] = by_language.get(v.language, 0) + 1
            by_pattern[v.pattern_name] = by_pattern.get(v.pattern_name, 0) + 1

        return {
            "files_scanned": self.files_scanned,
            "total_violations": len(self.violations),
            "fixable_violations": sum(1 for v in self.violations if v.can_fix),
            "by_language": by_language,
            "by_pattern": by_pattern,
            "errors": len(self.errors)
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("TIMESTAMP VIOLATION SCAN")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nFiles scanned: {summary['files_scanned']}")
        lines.append(f"Violations found: {summary['total_violations']}")
        lines.append(f"Fixable: {summary['fixable_violations']}")

        if summary["total_violations"] > 0:
            lines.append("\nBy Language:")
            for lang, count in sorted(summary["by_language"].items()):
                lines.append(f"  {lang}: {count}")

            lines.append("\nBy Pattern:")
            for pattern, count in sorted(summary["by_pattern"].items()):
                lines.append(f"  {pattern}: {count}")

            lines.append("\n" + "-" * 40)
            lines.append("VIOLATIONS:")
            lines.append("-" * 40)

            # Group by file
            by_file: dict[str, list[Violation]] = {}
            for v in self.violations:
                if v.file_path not in by_file:
                    by_file[v.file_path] = []
                by_file[v.file_path].append(v)

            for file_path, file_violations in sorted(by_file.items()):
                lines.append(f"\n{file_path}:")
                for v in sorted(file_violations, key=lambda x: x.line_number):
                    fix_marker = " [fixable]" if v.can_fix else ""
                    lines.append(f"  Line {v.line_number}: {v.pattern_name}{fix_marker}")
                    if self.verbose:
                        # Truncate long lines
                        content = v.line_content[:80] + "..." if len(v.line_content) > 80 else v.line_content
                        lines.append(f"    > {content}")

        if not self.violations:
            lines.append("\n✓ No timestamp violations found")

        if self.errors and self.verbose:
            lines.append("\n" + "-" * 40)
            lines.append("ERRORS:")
            for error in self.errors[:5]:
                lines.append(f"  - {error}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        output = {
            "summary": self.get_summary(),
            "violations": [
                {
                    "file": v.file_path,
                    "line": v.line_number,
                    "pattern": v.pattern_name,
                    "language": v.language,
                    "can_fix": v.can_fix,
                    "content": v.line_content
                }
                for v in self.violations
            ],
            "errors": self.errors
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Scan for timestamp violations in generated code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - No violations found
  1 - Violations found
  2 - File/parse error

Examples:
  %(prog)s src/                    # Scan src directory
  %(prog)s --fix src/              # Scan and fix violations
  %(prog)s --format=json src/      # JSON output
  %(prog)s --include-metadata .    # Include .task/ metadata files
        """
    )

    parser.add_argument(
        "path",
        type=Path,
        help="File or directory to scan"
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix violations (removes the system metadata timestamps)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what --fix would do without making changes"
    )

    parser.add_argument(
        "--include-metadata",
        action="store_true",
        help="Include .task/ metadata files in scan (normally excluded)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including line content"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(2)

    scanner = TimestampScanner(
        verbose=args.verbose,
        include_metadata=args.include_metadata
    )

    if args.verbose:
        print(f"Scanning: {args.path}")

    scanner.scan_path(args.path)

    # Handle fix mode
    if args.fix or args.dry_run:
        fixed = scanner.fix_violations(dry_run=args.dry_run)
        if args.dry_run:
            print(f"\nWould fix {fixed} violations")
        else:
            print(f"\nFixed {fixed} violations")

    # Output results
    if args.format == "json":
        print(scanner.format_json_output())
    else:
        print(scanner.format_text_output())

    # Exit code
    summary = scanner.get_summary()
    if summary["total_violations"] > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
