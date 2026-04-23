#!/usr/bin/env python3
"""
check_canonicalization.py - Verify generators use stable ordering

Checks that generator code uses canonicalization utilities (sorted keys,
OrderedDict, stable iteration) to ensure deterministic output.

Unstable ordering breaks idempotence - different key orders on each run
produce different output even with identical inputs.

Exit codes:
  0 - No violations found
  1 - Violations found
  2 - File/parse error

Usage:
  python tools/check_canonicalization.py <path>
  python tools/check_canonicalization.py <path> --format=json

Reference: IDEMPOTENT_GENERATION_POLICY.md:1066, 1670
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Patterns that indicate potential unstable ordering issues
UNSTABLE_PATTERNS = {
    "python": [
        # Dict iteration without sorting
        (r"for\s+\w+\s+in\s+\w+\.keys\(\)", "dict.keys() iteration without sorted()"),
        (r"for\s+\w+\s+in\s+\w+\.values\(\)", "dict.values() iteration without sorted()"),
        (r"for\s+\w+,\s*\w+\s+in\s+\w+\.items\(\)", "dict.items() iteration without sorted()"),
        # Set iteration
        (r"for\s+\w+\s+in\s+set\(", "set iteration (non-deterministic order)"),
        (r"for\s+\w+\s+in\s+\{[^}]+\}", "set literal iteration"),
        # JSON dumps without sort_keys
        (r"json\.dumps?\([^)]*\)", "json.dump/dumps (check for sort_keys=True)"),
        # YAML dump without default_flow_style
        (r"yaml\.dump\([^)]*\)", "yaml.dump (check for sort_keys)"),
        # Random operations
        (r"\brandom\.", "random module usage"),
        (r"\buuid\.", "uuid module usage (consider deterministic IDs)"),
        # Glob without sorting
        (r"\.glob\(", "glob() results (non-deterministic order)"),
        (r"\bglob\.glob\(", "glob.glob() (sort results for stability)"),
        # os.listdir without sorting
        (r"os\.listdir\(", "os.listdir() (non-deterministic order)"),
        # Dict comprehension
        (r"\{[^}]+for\s+\w+\s+in\s+", "dict comprehension (verify sorted input)"),
    ],
    "javascript": [
        # Object iteration
        (r"Object\.keys\([^)]+\)(?!\.sort)", "Object.keys() without .sort()"),
        (r"Object\.values\([^)]+\)(?!\.sort)", "Object.values() without .sort()"),
        (r"Object\.entries\([^)]+\)(?!\.sort)", "Object.entries() without .sort()"),
        # for...in without sorted keys
        (r"for\s*\([^)]+\s+in\s+", "for...in loop (non-deterministic order)"),
        # Set iteration
        (r"new Set\(", "Set iteration (non-deterministic order)"),
        (r"\.forEach\(", "forEach on object/map (verify order)"),
        # JSON stringify
        (r"JSON\.stringify\([^,)]+\)", "JSON.stringify without replacer (key order)"),
        # Random
        (r"Math\.random\(", "Math.random() usage"),
        (r"\bcrypto\.random", "crypto.random usage"),
        # UUID
        (r"\buuid\(", "uuid() (consider deterministic IDs)"),
        (r"\buuidv4\(", "uuidv4() (consider deterministic IDs)"),
        # fs.readdir without sorting
        (r"fs\.readdir", "fs.readdir (sort results for stability)"),
        (r"fs\.readdirSync", "fs.readdirSync (sort results for stability)"),
    ],
    "go": [
        # Map iteration
        (r"for\s+\w+,?\s*\w*\s*:?=\s*range\s+", "map range iteration (non-deterministic)"),
        # Random
        (r"rand\.", "rand package usage"),
        # UUID
        (r"uuid\.", "uuid package usage"),
    ],
}

# Good patterns that indicate proper canonicalization
GOOD_PATTERNS = {
    "python": [
        r"sorted\(",
        r"OrderedDict",
        r"sort_keys\s*=\s*True",
        r"\.sort\(",
        r"collections\.OrderedDict",
    ],
    "javascript": [
        r"\.sort\(",
        r"Object\.keys\([^)]+\)\.sort\(",
        r"Object\.entries\([^)]+\)\.sort\(",
        r"new Map\(",  # Map preserves insertion order
    ],
    "go": [
        r"sort\.",
        r"sort\.Strings\(",
        r"sort\.Slice\(",
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
    ".go": "go",
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
    "vendor",
}

@dataclass
class Violation:
    """Represents a canonicalization violation."""
    file_path: str
    line_number: int
    line_content: str
    pattern_name: str
    language: str
    severity: str  # high, medium, low
    suggestion: str

class CanonicalizationChecker:
    """Check for canonicalization issues in generator code."""

    def __init__(self, verbose: bool = False, strict: bool = False):
        self.verbose = verbose
        self.strict = strict
        self.violations: list[Violation] = []
        self.good_practices: list[dict] = []
        self.files_scanned: int = 0
        self.errors: list[str] = []

    def scan_path(self, path: Path) -> None:
        """Scan a file or directory."""
        if path.is_file():
            self._scan_file(path)
        elif path.is_dir():
            self._scan_directory(path)
        else:
            self.errors.append(f"Path not found: {path}")

    def _scan_directory(self, dir_path: Path) -> None:
        """Recursively scan a directory."""
        for item in dir_path.iterdir():
            if item.is_dir():
                if item.name in EXCLUDED_DIRS:
                    if self.verbose:
                        print(f"  Skipping excluded dir: {item}")
                    continue
                self._scan_directory(item)
            elif item.is_file():
                self._scan_file(item)

    def _scan_file(self, file_path: Path) -> None:
        """Scan a single file."""
        ext = file_path.suffix.lower()
        if ext not in EXTENSION_MAP:
            return

        language = EXTENSION_MAP[ext]

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.splitlines()

            self.files_scanned += 1

            # Check for bad patterns
            self._check_patterns(file_path, lines, language)

            # Check for good patterns (for reporting)
            self._check_good_patterns(file_path, content, language)

            # For Python, do AST analysis
            if language == "python":
                self._analyze_python_ast(file_path, content)

        except Exception as e:
            self.errors.append(f"Error scanning {file_path}: {e}")

    def _check_patterns(self, file_path: Path, lines: list[str], language: str) -> None:
        """Check for unstable patterns."""
        patterns = UNSTABLE_PATTERNS.get(language, [])

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if self._is_comment(line, language):
                continue

            for pattern, pattern_name in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check if it's mitigated by a good pattern on same line
                    if self._has_mitigation(line, language):
                        continue

                    severity = self._determine_severity(pattern_name)
                    suggestion = self._get_suggestion(pattern_name, language)

                    self.violations.append(Violation(
                        file_path=str(file_path),
                        line_number=line_num,
                        line_content=line.strip(),
                        pattern_name=pattern_name,
                        language=language,
                        severity=severity,
                        suggestion=suggestion
                    ))

    def _check_good_patterns(self, file_path: Path, content: str, language: str) -> None:
        """Track good canonicalization practices."""
        patterns = GOOD_PATTERNS.get(language, [])

        for pattern in patterns:
            if re.search(pattern, content):
                self.good_practices.append({
                    "file": str(file_path),
                    "pattern": pattern,
                    "language": language
                })

    def _analyze_python_ast(self, file_path: Path, content: str) -> None:
        """Analyze Python AST for deeper checks."""
        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                # Check for json.dumps without sort_keys
                if isinstance(node, ast.Call):
                    if self._is_json_dumps(node):
                        if not self._has_sort_keys_arg(node):
                            self.violations.append(Violation(
                                file_path=str(file_path),
                                line_number=node.lineno,
                                line_content="json.dumps(...)",
                                pattern_name="json.dumps without sort_keys=True",
                                language="python",
                                severity="high",
                                suggestion="Add sort_keys=True to json.dumps() for stable output"
                            ))

        except SyntaxError:
            pass  # Skip files with syntax errors
        except Exception as e:
            if self.verbose:
                self.errors.append(f"AST analysis failed for {file_path}: {e}")

    def _is_json_dumps(self, node: ast.Call) -> bool:
        """Check if call is json.dumps or json.dump."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in ["dumps", "dump"]
        return False

    def _has_sort_keys_arg(self, node: ast.Call) -> bool:
        """Check if call has sort_keys=True."""
        for keyword in node.keywords:
            if keyword.arg == "sort_keys":
                if isinstance(keyword.value, ast.Constant):
                    return keyword.value.value is True
        return False

    def _is_comment(self, line: str, language: str) -> bool:
        """Check if line is a comment."""
        stripped = line.lstrip()
        if language == "python":
            return stripped.startswith("#")
        elif language in ["javascript", "go"]:
            return stripped.startswith("//") or stripped.startswith("/*")
        return False

    def _has_mitigation(self, line: str, language: str) -> bool:
        """Check if line has a mitigation pattern."""
        patterns = GOOD_PATTERNS.get(language, [])
        for pattern in patterns:
            if re.search(pattern, line):
                return True
        return False

    def _determine_severity(self, pattern_name: str) -> str:
        """Determine severity based on pattern."""
        high_severity = [
            "dict.items() iteration",
            "dict.keys() iteration",
            "Object.keys()",
            "Object.entries()",
            "map range iteration",
            "json.dumps",
            "JSON.stringify",
        ]
        low_severity = [
            "uuid",
            "random",
        ]

        for hs in high_severity:
            if hs in pattern_name.lower():
                return "high"
        for ls in low_severity:
            if ls in pattern_name.lower():
                return "low" if not self.strict else "medium"
        return "medium"

    def _get_suggestion(self, pattern_name: str, language: str) -> str:
        """Get suggestion for fixing the issue."""
        suggestions = {
            "dict.keys() iteration": "Use sorted(dict.keys()) for deterministic order",
            "dict.values() iteration": "Use [dict[k] for k in sorted(dict.keys())] for deterministic order",
            "dict.items() iteration": "Use sorted(dict.items()) for deterministic order",
            "set iteration": "Convert to sorted list: sorted(set_var)",
            "json.dump": "Add sort_keys=True parameter",
            "yaml.dump": "Add sort_keys=True or default_flow_style=False",
            "glob()": "Sort results: sorted(path.glob(...))",
            "os.listdir()": "Sort results: sorted(os.listdir(...))",
            "Object.keys()": "Add .sort() after Object.keys()",
            "Object.entries()": "Add .sort() after Object.entries()",
            "for...in loop": "Use Object.keys().sort().forEach() instead",
            "JSON.stringify": "Use JSON.stringify(obj, Object.keys(obj).sort())",
            "fs.readdir": "Sort the callback results",
            "map range iteration": "Extract keys, sort them, then iterate",
            "random": "Use deterministic seed or avoid in generators",
            "uuid": "Use deterministic ID generation based on inputs",
        }

        for key, suggestion in suggestions.items():
            if key.lower() in pattern_name.lower():
                return suggestion

        return "Ensure deterministic ordering in output"

    def get_summary(self) -> dict:
        """Get scan summary."""
        by_severity = {"high": 0, "medium": 0, "low": 0}
        by_language = {}

        for v in self.violations:
            by_severity[v.severity] = by_severity.get(v.severity, 0) + 1
            by_language[v.language] = by_language.get(v.language, 0) + 1

        return {
            "files_scanned": self.files_scanned,
            "total_violations": len(self.violations),
            "by_severity": by_severity,
            "by_language": by_language,
            "good_practices_found": len(self.good_practices),
            "errors": len(self.errors)
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("CANONICALIZATION CHECK")
        lines.append("=" * 60)

        summary = self.get_summary()
        lines.append(f"\nFiles scanned: {summary['files_scanned']}")
        lines.append(f"Violations found: {summary['total_violations']}")
        lines.append(f"Good practices found: {summary['good_practices_found']}")

        if summary["total_violations"] > 0:
            lines.append("\nBy Severity:")
            for sev, count in summary["by_severity"].items():
                if count > 0:
                    lines.append(f"  {sev}: {count}")

            lines.append("\n" + "-" * 40)
            lines.append("VIOLATIONS:")
            lines.append("-" * 40)

            # Group by severity
            for severity in ["high", "medium", "low"]:
                sev_violations = [v for v in self.violations if v.severity == severity]
                if not sev_violations:
                    continue

                lines.append(f"\n{severity.upper()}:")
                for v in sev_violations:
                    lines.append(f"\n  {v.file_path}:{v.line_number}")
                    lines.append(f"    Issue: {v.pattern_name}")
                    lines.append(f"    Fix: {v.suggestion}")
                    if self.verbose:
                        content = v.line_content[:60] + "..." if len(v.line_content) > 60 else v.line_content
                        lines.append(f"    Code: {content}")

        if not self.violations:
            lines.append("\n✓ No canonicalization issues found")

        if self.good_practices and self.verbose:
            lines.append("\n" + "-" * 40)
            lines.append("GOOD PRACTICES FOUND:")
            for gp in self.good_practices[:10]:
                lines.append(f"  {gp['file']}: {gp['pattern']}")

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
                    "severity": v.severity,
                    "suggestion": v.suggestion,
                    "language": v.language,
                    "content": v.line_content
                }
                for v in self.violations
            ],
            "good_practices": self.good_practices,
            "errors": self.errors
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Check for canonicalization issues in generator code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - No violations found
  1 - Violations found
  2 - File/parse error

Examples:
  %(prog)s tools/                  # Check tools directory
  %(prog)s --strict src/           # Strict mode (random/uuid are medium severity)
  %(prog)s --format=json .         # JSON output
        """
    )

    parser.add_argument(
        "path",
        type=Path,
        help="File or directory to check"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode (elevate severity of random/uuid patterns)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including code snippets"
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

    checker = CanonicalizationChecker(
        verbose=args.verbose,
        strict=args.strict
    )

    if args.verbose:
        print(f"Checking: {args.path}")

    checker.scan_path(args.path)

    # Output results
    if args.format == "json":
        print(checker.format_json_output())
    else:
        print(checker.format_text_output())

    # Exit code
    summary = checker.get_summary()
    if summary["total_violations"] > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
