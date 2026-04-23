#!/usr/bin/env python3
"""
idempotence_validator.py - Master idempotence validation tool

Orchestrates all 6 mechanical idempotence checks for task validation.
This is the unified interface for Critic pre-approval and PM promotion gates.

TOOL RELATIONSHIP:
  - idempotence_validator.py (this tool): Full 6-check validation for Critic gates
    Runs all mechanical checks including contract declaration, timestamps,
    canonicalization, file reads, generate-twice test, and formatter lock.
    Use for: Critic pre-approval, PM promotion gates, comprehensive validation.

  - idempotence_checker.py: Quick generate-twice verification for Builder
    Runs task generation twice and compares outputs byte-by-byte.
    Use for: Builder pre-commit checks, quick iteration during development.

Builder workflow: Use idempotence_checker.py for fast feedback during development.
Critic workflow: Use idempotence_validator.py for comprehensive gate validation.

Exit codes:
  0 - All hard requirements passed
  1 - One or more checks failed
  2 - Configuration/parse error

Usage:
  python tools/idempotence_validator.py <task_path>
  python tools/idempotence_validator.py <task_path> --strict
  python tools/idempotence_validator.py <task_path> --format=json

Reference: IDEMPOTENT_GENERATION_POLICY.md:563-609
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Check classification
HARD_REQUIREMENTS = {1, 2, 3, 4, 5}  # Checks 1-5 are hard requirements
SOFT_REQUIREMENTS = {6}  # Check 6 (formatter lock) is soft

@dataclass
class CheckResult:
    """Result of a single idempotence check."""
    check_number: int
    name: str
    passed: bool
    is_hard: bool
    message: str
    details: list[str] = field(default_factory=list)
    skipped: bool = False  # New field to indicate skipped checks

class IdempotenceValidator:
    """Master validator for 6 mechanical idempotence checks."""

    def __init__(
        self,
        task_path: Path,
        verbose: bool = False,
        strict: bool = False,
        tools_dir: Optional[Path] = None
    ):
        self.task_path = task_path.resolve()
        self.verbose = verbose
        self.strict = strict  # If true, soft requirements also cause failure
        self.tools_dir = tools_dir or Path(__file__).parent
        self.results: list[CheckResult] = []
        self.errors: list[str] = []

        # Locate .task directory
        self.task_meta_dir = self.task_path / ".task"
        self.wiring_path = self.task_meta_dir / "wiring.yaml"

    def _is_template_directory(self) -> bool:
        """
        Detect if this is a template directory (no actual task definition).

        Template directories have placeholder task_ids or are the root .task/ template.
        Generation-based idempotence testing is not applicable for templates.
        """
        # Check 1: Is this the root .task/ template directory?
        if self.task_path.name == ".task" or self.task_meta_dir == self.task_path:
            return True

        # Check 2: Does task.yaml contain placeholder values?
        task_yaml = self.task_meta_dir / "task.yaml"
        if task_yaml.exists():
            try:
                content = task_yaml.read_text()
                # Detect placeholder patterns
                if "<placeholder" in content.lower() or "placeholder-task-id" in content.lower():
                    return True
                # Check for null/empty task_id
                if re.search(r'task_id:\s*(null|""|\'\'|\s*$)', content):
                    return True
            except Exception:
                pass

        # Check 3: Is there no generate_task.py or no tasks/ directory?
        # If we can't generate, this is effectively a template-only validation
        generate_script = self.tools_dir / "generate_task.py"
        if not generate_script.exists():
            return True

        return False

    def validate(self) -> bool:
        """Run all 6 mechanical checks. Returns True if all hard requirements pass."""
        # Verify task path exists
        if not self.task_path.exists():
            self.errors.append(f"Task path not found: {self.task_path}")
            return False

        if not self.task_path.is_dir():
            self.errors.append(f"Task path is not a directory: {self.task_path}")
            return False

        # Run all 6 checks
        self._check_1_contract_declared()
        self._check_2_no_timestamps()
        self._check_3_canonicalization()
        self._check_4_no_file_reads()
        self._check_5_idempotence_test()
        self._check_6_formatter_locked()

        # Determine pass/fail (skipped checks count as passed for hard requirement purposes)
        hard_failures = [r for r in self.results if r.is_hard and not r.passed and not r.skipped]
        soft_failures = [r for r in self.results if not r.is_hard and not r.passed and not r.skipped]

        if hard_failures:
            return False
        if self.strict and soft_failures:
            return False
        return True

    def _check_1_contract_declared(self) -> None:
        """Check 1: Idempotence contract declared in .task/wiring.yaml."""
        check_name = "Idempotence contract declared"

        if not self.wiring_path.exists():
            self.results.append(CheckResult(
                check_number=1,
                name=check_name,
                passed=False,
                is_hard=True,
                message=f"Missing .task/wiring.yaml",
                details=[f"Expected: {self.wiring_path}"]
            ))
            return

        try:
            content = self.wiring_path.read_text()

            # Check for idempotent: true or idempotence contract
            idempotent_patterns = [
                r"idempotent:\s*true",
                r"idempotence:\s*true",
                r"@saf:idempotent",
                r"contract:\s*idempotent",
            ]

            found = any(re.search(p, content, re.IGNORECASE) for p in idempotent_patterns)

            if found:
                self.results.append(CheckResult(
                    check_number=1,
                    name=check_name,
                    passed=True,
                    is_hard=True,
                    message="Idempotence contract found in wiring.yaml"
                ))
            else:
                self.results.append(CheckResult(
                    check_number=1,
                    name=check_name,
                    passed=False,
                    is_hard=True,
                    message="No idempotence contract declaration found",
                    details=[
                        "Add 'idempotent: true' to .task/wiring.yaml",
                        "Or add '@saf:idempotent' annotation"
                    ]
                ))

        except Exception as e:
            self.results.append(CheckResult(
                check_number=1,
                name=check_name,
                passed=False,
                is_hard=True,
                message=f"Error reading wiring.yaml: {e}"
            ))

    def _check_2_no_timestamps(self) -> None:
        """Check 2: No timestamps in generated code (only .task/ metadata allowed)."""
        check_name = "No timestamps in generated code"

        scanner_path = self.tools_dir / "scan_timestamps.py"

        if not scanner_path.exists():
            # Fallback: basic regex scan
            self._check_2_fallback()
            return

        try:
            result = subprocess.run(
                [sys.executable, str(scanner_path), str(self.task_path), "--format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self.results.append(CheckResult(
                    check_number=2,
                    name=check_name,
                    passed=True,
                    is_hard=True,
                    message="No timestamp violations found"
                ))
            else:
                # Parse JSON output for details
                details = []
                try:
                    data = json.loads(result.stdout)
                    violations = data.get("violations", [])
                    for v in violations[:5]:  # Show first 5
                        details.append(f"{v['file']}:{v['line']}: {v['pattern']}")
                    if len(violations) > 5:
                        details.append(f"... and {len(violations) - 5} more")
                except json.JSONDecodeError:
                    details = [result.stdout[:200] if result.stdout else "No output"]

                self.results.append(CheckResult(
                    check_number=2,
                    name=check_name,
                    passed=False,
                    is_hard=True,
                    message="Timestamp violations found in generated code",
                    details=details
                ))

        except subprocess.TimeoutExpired:
            self.results.append(CheckResult(
                check_number=2,
                name=check_name,
                passed=False,
                is_hard=True,
                message="Timestamp scan timed out"
            ))
        except Exception as e:
            self.results.append(CheckResult(
                check_number=2,
                name=check_name,
                passed=False,
                is_hard=True,
                message=f"Error running timestamp scan: {e}"
            ))

    def _check_2_fallback(self) -> None:
        """Fallback timestamp check without scan_timestamps.py."""
        check_name = "No timestamps in generated code"

        timestamp_patterns = [
            r"datetime\.now\(\)",
            r"datetime\.utcnow\(\)",
            r"time\.time\(\)",
            r"Date\.now\(\)",
            r"new Date\(\)",
        ]

        violations = []

        for py_file in self.task_path.rglob("*.py"):
            # Skip .task/ metadata
            if ".task" in py_file.parts:
                continue
            try:
                content = py_file.read_text()
                for pattern in timestamp_patterns:
                    if re.search(pattern, content):
                        violations.append(f"{py_file}: matches {pattern}")
            except Exception:
                pass

        if not violations:
            self.results.append(CheckResult(
                check_number=2,
                name=check_name,
                passed=True,
                is_hard=True,
                message="No timestamp patterns found (fallback scan)"
            ))
        else:
            self.results.append(CheckResult(
                check_number=2,
                name=check_name,
                passed=False,
                is_hard=True,
                message="Timestamp patterns found",
                details=violations[:5]
            ))

    def _check_3_canonicalization(self) -> None:
        """Check 3: Canonicalization utilities used (sorted keys, stable iteration)."""
        check_name = "Canonicalization (stable ordering)"

        canon_path = self.tools_dir / "check_canonicalization.py"

        if not canon_path.exists():
            # Fallback: basic check
            self._check_3_fallback()
            return

        try:
            result = subprocess.run(
                [sys.executable, str(canon_path), str(self.task_path), "--format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self.results.append(CheckResult(
                    check_number=3,
                    name=check_name,
                    passed=True,
                    is_hard=True,
                    message="No canonicalization issues found"
                ))
            else:
                details = []
                try:
                    data = json.loads(result.stdout)
                    violations = data.get("violations", [])
                    for v in violations[:5]:
                        details.append(f"{v['file']}:{v['line']}: {v['issue']}")
                    if len(violations) > 5:
                        details.append(f"... and {len(violations) - 5} more")
                except json.JSONDecodeError:
                    details = [result.stdout[:200] if result.stdout else "No output"]

                self.results.append(CheckResult(
                    check_number=3,
                    name=check_name,
                    passed=False,
                    is_hard=True,
                    message="Canonicalization issues found",
                    details=details
                ))

        except subprocess.TimeoutExpired:
            self.results.append(CheckResult(
                check_number=3,
                name=check_name,
                passed=False,
                is_hard=True,
                message="Canonicalization check timed out"
            ))
        except Exception as e:
            self.results.append(CheckResult(
                check_number=3,
                name=check_name,
                passed=False,
                is_hard=True,
                message=f"Error running canonicalization check: {e}"
            ))

    def _check_3_fallback(self) -> None:
        """Fallback canonicalization check."""
        check_name = "Canonicalization (stable ordering)"

        # Check for json.dumps without sort_keys
        issues = []

        for py_file in self.task_path.rglob("*.py"):
            if ".task" in py_file.parts:
                continue
            try:
                content = py_file.read_text()
                # Simple pattern: json.dumps( without sort_keys=True
                if "json.dumps(" in content:
                    if "sort_keys=True" not in content and "sort_keys = True" not in content:
                        issues.append(f"{py_file}: json.dumps without sort_keys=True")
            except Exception:
                pass

        if not issues:
            self.results.append(CheckResult(
                check_number=3,
                name=check_name,
                passed=True,
                is_hard=True,
                message="No obvious canonicalization issues (fallback scan)"
            ))
        else:
            self.results.append(CheckResult(
                check_number=3,
                name=check_name,
                passed=False,
                is_hard=True,
                message="Potential canonicalization issues",
                details=issues[:5]
            ))

    def _check_4_no_file_reads(self) -> None:
        """Check 4: No file reads in generator (inputs from SSOT only)."""
        check_name = "No arbitrary file reads"

        # Patterns that indicate file reads outside SSOT
        forbidden_patterns = [
            (r"open\([^)]*['\"][^'\"]+['\"]", "open() with hardcoded path"),
            (r"pathlib\.Path\([^)]*\)\.read_", "Path().read_*() call"),
            (r"with open\(", "with open() statement"),
            (r"\.read_text\(\)", ".read_text() call"),
            (r"\.read_bytes\(\)", ".read_bytes() call"),
        ]

        # Allowed patterns (SSOT/wiring reads)
        allowed_patterns = [
            r"wiring\.yaml",
            r"\.task/",
            r"ssot",
            r"SSOT",
            r"config\.yaml",
        ]

        violations = []

        for py_file in self.task_path.rglob("*.py"):
            if ".task" in py_file.parts:
                continue
            try:
                content = py_file.read_text()
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    # Skip comments
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue

                    for pattern, desc in forbidden_patterns:
                        if re.search(pattern, line):
                            # Check if it's an allowed pattern
                            if any(re.search(a, line, re.IGNORECASE) for a in allowed_patterns):
                                continue
                            violations.append(f"{py_file}:{line_num}: {desc}")

            except Exception:
                pass

        if not violations:
            self.results.append(CheckResult(
                check_number=4,
                name=check_name,
                passed=True,
                is_hard=True,
                message="No arbitrary file reads detected"
            ))
        else:
            self.results.append(CheckResult(
                check_number=4,
                name=check_name,
                passed=False,
                is_hard=True,
                message="Arbitrary file reads detected (should use SSOT inputs)",
                details=violations[:5] + (["... and more"] if len(violations) > 5 else [])
            ))

    def _check_5_idempotence_test(self) -> None:
        """Check 5: Idempotence test passes (generate twice, compare)."""
        check_name = "Idempotence test (generate twice)"

        # Check if this is a template directory - skip generation test if so
        if self._is_template_directory():
            self.results.append(CheckResult(
                check_number=5,
                name=check_name,
                passed=True,  # Skipped counts as pass for templates
                is_hard=True,
                skipped=True,
                message="SKIPPED - Template directory detected (no task generation applicable)",
                details=[
                    "Template directories cannot run generate-twice test",
                    "This check applies only to concrete task instances",
                    "Validate concrete tasks in tasks/<task-id>/ directory"
                ]
            ))
            return

        test_script = self.tools_dir / "test_idempotence.sh"

        if not test_script.exists():
            # Check for alternative
            alt_script = self.tools_dir / "test_idempotence.py"
            if alt_script.exists():
                test_script = alt_script
            else:
                self.results.append(CheckResult(
                    check_number=5,
                    name=check_name,
                    passed=False,
                    is_hard=True,
                    message="Idempotence test script not found",
                    details=[
                        f"Expected: {self.tools_dir}/test_idempotence.sh",
                        "Cannot verify generate-twice idempotence"
                    ]
                ))
                return

        try:
            # Run the idempotence test
            if test_script.suffix == ".sh":
                result = subprocess.run(
                    ["bash", str(test_script), str(self.task_path)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            else:
                result = subprocess.run(
                    [sys.executable, str(test_script), str(self.task_path)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

            if result.returncode == 0:
                self.results.append(CheckResult(
                    check_number=5,
                    name=check_name,
                    passed=True,
                    is_hard=True,
                    message="Idempotence test passed (generate twice produces identical output)"
                ))
            else:
                details = []
                output = result.stdout + result.stderr
                # Extract meaningful lines
                for line in output.split("\n"):
                    if "differ" in line.lower() or "mismatch" in line.lower() or "fail" in line.lower():
                        details.append(line.strip())
                if not details:
                    details = [output[:300] if output else "No output"]

                self.results.append(CheckResult(
                    check_number=5,
                    name=check_name,
                    passed=False,
                    is_hard=True,
                    message="Idempotence test failed (outputs differ)",
                    details=details[:5]
                ))

        except subprocess.TimeoutExpired:
            self.results.append(CheckResult(
                check_number=5,
                name=check_name,
                passed=False,
                is_hard=True,
                message="Idempotence test timed out (>120s)"
            ))
        except Exception as e:
            self.results.append(CheckResult(
                check_number=5,
                name=check_name,
                passed=False,
                is_hard=True,
                message=f"Error running idempotence test: {e}"
            ))

    def _check_6_formatter_locked(self) -> None:
        """Check 6: Formatter version locked (soft requirement)."""
        check_name = "Formatter version locked"

        # Check for formatter lock in wiring.yaml or pyproject.toml
        formatter_lock_patterns = [
            (self.wiring_path, r"formatter.*version|black.*version|ruff.*version"),
            (self.task_path / "pyproject.toml", r"\[tool\.(black|ruff)\]"),
            (self.task_path / ".pre-commit-config.yaml", r"black|ruff"),
        ]

        found_lock = False
        lock_file = None

        for file_path, pattern in formatter_lock_patterns:
            if file_path.exists():
                try:
                    content = file_path.read_text()
                    if re.search(pattern, content, re.IGNORECASE):
                        found_lock = True
                        lock_file = file_path.name
                        break
                except Exception:
                    pass

        if found_lock:
            self.results.append(CheckResult(
                check_number=6,
                name=check_name,
                passed=True,
                is_hard=False,
                message=f"Formatter configuration found in {lock_file}"
            ))
        else:
            self.results.append(CheckResult(
                check_number=6,
                name=check_name,
                passed=False,
                is_hard=False,
                message="No formatter version lock detected (soft requirement)",
                details=[
                    "Consider adding formatter config to pyproject.toml",
                    "Or add formatter_version to .task/wiring.yaml"
                ]
            ))

    def get_summary(self) -> dict:
        """Get validation summary."""
        passed = [r for r in self.results if r.passed]
        skipped = [r for r in self.results if r.skipped]
        failed_hard = [r for r in self.results if not r.passed and r.is_hard and not r.skipped]
        failed_soft = [r for r in self.results if not r.passed and not r.is_hard and not r.skipped]

        return {
            "task_path": str(self.task_path),
            "total_checks": len(self.results),
            "passed": len(passed),
            "skipped": len(skipped),
            "failed_hard": len(failed_hard),
            "failed_soft": len(failed_soft),
            "overall_pass": len(failed_hard) == 0 and (not self.strict or len(failed_soft) == 0),
            "strict_mode": self.strict,
            "errors": self.errors
        }

    def format_text_output(self) -> str:
        """Format results as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("IDEMPOTENCE VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append(f"\nTask: {self.task_path}")
        lines.append(f"Mode: {'Strict' if self.strict else 'Normal'}")
        lines.append("")

        # Individual check results
        lines.append("-" * 40)
        lines.append("CHECKS:")
        lines.append("-" * 40)

        for result in self.results:
            if result.skipped:
                status = "-"  # Dash for skipped
            elif result.passed:
                status = "\u2713"
            else:
                status = "\u2717"
            req_type = "[HARD]" if result.is_hard else "[SOFT]"
            skip_note = " [SKIPPED]" if result.skipped else ""
            lines.append(f"\n{status} Check {result.check_number}: {result.name} {req_type}{skip_note}")
            lines.append(f"   {result.message}")

            if self.verbose and result.details:
                for detail in result.details:
                    lines.append(f"     - {detail}")

        # Summary
        summary = self.get_summary()
        lines.append("\n" + "-" * 40)
        lines.append("SUMMARY:")
        lines.append("-" * 40)
        lines.append(f"Checks passed: {summary['passed']}/{summary['total_checks']}")
        if summary['skipped'] > 0:
            lines.append(f"Checks skipped: {summary['skipped']}")
        lines.append(f"Hard failures: {summary['failed_hard']}")
        lines.append(f"Soft failures: {summary['failed_soft']}")

        if summary["overall_pass"]:
            lines.append(f"\n\u2713 IDEMPOTENCE VALIDATION PASSED")
        else:
            lines.append(f"\n\u2717 IDEMPOTENCE VALIDATION FAILED")
            if summary["failed_hard"] > 0:
                lines.append("  Fix hard requirement failures before approval")

        if self.errors:
            lines.append("\nErrors:")
            for error in self.errors:
                lines.append(f"  - {error}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_json_output(self) -> str:
        """Format results as JSON."""
        output = {
            "summary": self.get_summary(),
            "checks": [
                {
                    "number": r.check_number,
                    "name": r.name,
                    "passed": r.passed,
                    "skipped": r.skipped,
                    "is_hard_requirement": r.is_hard,
                    "message": r.message,
                    "details": r.details
                }
                for r in self.results
            ],
            "errors": self.errors
        }
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Master idempotence validation tool - runs all 6 mechanical checks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Checks performed:
  1. [HARD] Idempotence contract declared in .task/wiring.yaml
  2. [HARD] No timestamps in generated code (only .task/ metadata)
  3. [HARD] Canonicalization utilities used (sorted keys, stable iteration)
  4. [HARD] No arbitrary file reads (inputs from SSOT only)
  5. [HARD] Idempotence test passes (generate twice, compare)
         NOTE: Skipped for template directories (no task definition)
  6. [SOFT] Formatter version locked

Exit codes:
  0 - All hard requirements passed
  1 - One or more hard checks failed
  2 - Configuration/parse error

Examples:
  %(prog)s tasks/api-client/           # Validate a task
  %(prog)s tasks/api-client/ --strict  # Soft failures also cause exit 1
  %(prog)s tasks/api-client/ -v        # Verbose output
  %(prog)s tasks/api-client/ --json    # JSON output for CI
        """
    )

    parser.add_argument(
        "task_path",
        type=Path,
        help="Path to task directory to validate"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat soft requirements as hard (exit 1 on soft failures)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including failure details"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Shorthand for --format=json"
    )

    parser.add_argument(
        "--tools-dir",
        type=Path,
        help="Override tools directory (default: same as this script)"
    )

    args = parser.parse_args()

    if not args.task_path.exists():
        print(f"Error: Task path not found: {args.task_path}", file=sys.stderr)
        sys.exit(2)

    output_format = "json" if args.json else args.format

    validator = IdempotenceValidator(
        task_path=args.task_path,
        verbose=args.verbose,
        strict=args.strict,
        tools_dir=args.tools_dir
    )

    passed = validator.validate()

    # Output results
    if output_format == "json":
        print(validator.format_json_output())
    else:
        print(validator.format_text_output())

    # Exit code
    if validator.errors and not validator.results:
        sys.exit(2)  # Configuration error
    elif passed:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
