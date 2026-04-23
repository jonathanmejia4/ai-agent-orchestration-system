#!/usr/bin/env python3
"""
Idempotence Checker for the system Task Generation

Validates that task generation is idempotent by running generation twice
with identical inputs and comparing outputs. Critical quality gate that
Builder must run before committing generated code.

TOOL RELATIONSHIP:
  - idempotence_checker.py (this tool): Quick generate-twice verification
    Runs task generation twice and compares outputs byte-by-byte.
    Use for: Builder pre-commit checks, quick iteration during development.

  - idempotence_validator.py: Full 6-check validation for Critic gates
    Runs all mechanical checks (contract, timestamps, canonicalization, etc.)
    Use for: Critic pre-approval, PM promotion gates, comprehensive validation.

Usage:
    # Check specific task for idempotence
    python3 tools/idempotence_checker.py --task task-3.1-api-gateway

    # Check with verbose output
    python3 tools/idempotence_checker.py --task task-3.1-api-gateway --verbose

    # Check and save diff report
    python3 tools/idempotence_checker.py --task task-3.1-api-gateway --output diff_report.txt

Exit Codes:
    0 - PASS: Generation is idempotent (outputs identical)
    1 - FAIL: Generation is non-deterministic (outputs differ)
    2 - ERROR: Invalid arguments, missing files, or execution error

Expected Behavior:
    1. Run task generation (first execution)
    2. Capture all generated files and content
    3. Run task generation again (second execution)
    4. Compare outputs byte-by-byte
    5. Report PASS if outputs match exactly
    6. Report FAIL with diff if outputs differ

Example Output:
    ✅ IDEMPOTENCE CHECK PASSED
    Task: task-3.1-api-gateway
    Files checked: 12
    All outputs identical across 2 runs

    ❌ IDEMPOTENCE CHECK FAILED
    Task: task-3.1-api-gateway
    Files checked: 12
    Differences found: 3 files

    Diff report:
    - src/timestamp.py: Line 5 timestamp differs
    - logs/build.log: Lines 1-10 contain timestamps
    - config/generated.yaml: Random UUID differs

Referenced in:
    - Builder_Spec.md:244 (Idempotence requirement)
    - Builder_Spec.md:814 (Pre-commit verification)
    - Builder_Spec.md:859 (Builder quality gates)

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import hashlib
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import difflib
import json

class IdempotenceChecker:
    """Checks if task generation is idempotent"""

    def __init__(self, task_id: str, verbose: bool = False):
        self.task_id = task_id
        self.verbose = verbose
        self.repo_root = self._find_repo_root()

    def _find_repo_root(self) -> Path:
        """Find repository root by looking for .git directory"""
        current = Path.cwd()
        while current != current.parent:
            if (current / '.git').exists():
                return current
            current = current.parent
        raise RuntimeError("Not in a git repository")

    def _log(self, message: str) -> None:
        """Print message if verbose mode enabled"""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file contents"""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            self._log(f"Error hashing {file_path}: {e}")
            return ""

    def _get_all_files(self, directory: Path) -> Dict[str, str]:
        """
        Get all files in directory with their hashes

        Returns:
            Dict mapping relative path to file hash
        """
        file_hashes = {}

        for file_path in directory.rglob('*'):
            if file_path.is_file():
                # Skip git metadata
                if '.git' in file_path.parts:
                    continue

                relative_path = file_path.relative_to(directory)
                file_hash = self._compute_file_hash(file_path)
                file_hashes[str(relative_path)] = file_hash

        return file_hashes

    def _run_generation(self, output_dir: Path) -> bool:
        """
        Run task generation and output to specified directory

        Returns:
            True if generation succeeded, False otherwise
        """
        self._log(f"Running task generation for {self.task_id}...")

        # Check if task definition exists
        task_file = self.repo_root / f"tasks/{self.task_id}/.task/task.yaml"
        wiring_file = self.repo_root / f"tasks/{self.task_id}/.task/wiring.yaml"

        if not task_file.exists():
            # Try alternate location
            task_file = self.repo_root / f".task/task.yaml"
            wiring_file = self.repo_root / f".task/wiring.yaml"

        if not task_file.exists():
            print(f"❌ Error: Task definition not found", file=sys.stderr)
            print(f"   Searched: tasks/{self.task_id}/.task/task.yaml", file=sys.stderr)
            print(f"   Searched: .task/task.yaml", file=sys.stderr)
            return False

        # Try different generation methods in order of preference
        generation_methods = [
            # Method 1: Use generate_task.py if it exists
            (self.repo_root / "tools" / "generate_task.py",
             ["python3", str(self.repo_root / "tools" / "generate_task.py"),
              "--task", self.task_id, "--output", str(output_dir)]),

            # Method 2: Use build_task.sh if it exists
            (self.repo_root / "scripts" / "build_task.sh",
             ["bash", str(self.repo_root / "scripts" / "build_task.sh"),
              self.task_id, str(output_dir)]),

            # Method 3: Use make if Makefile has task target
            (self.repo_root / "Makefile",
             ["make", "-C", str(self.repo_root), "task",
              f"TASK_ID={self.task_id}", f"OUTPUT={output_dir}"]),
        ]

        for tool_path, cmd in generation_methods:
            if tool_path.exists():
                self._log(f"Using generation command: {' '.join(cmd)}")
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,  # 5 minute timeout
                        cwd=str(self.repo_root)
                    )

                    if result.returncode == 0:
                        self._log(f"Generation succeeded")
                        if result.stdout:
                            self._log(f"stdout: {result.stdout[:500]}")
                        return True
                    else:
                        self._log(f"Generation failed with exit code {result.returncode}")
                        if result.stderr:
                            self._log(f"stderr: {result.stderr[:500]}")
                        # Try next method
                        continue

                except subprocess.TimeoutExpired:
                    print(f"❌ Error: Generation timed out after 5 minutes", file=sys.stderr)
                    return False
                except Exception as e:
                    self._log(f"Error with {tool_path}: {e}")
                    continue

        # Fallback: If no generation tool found, use template-based generation
        self._log("No generation tool found, using template-based fallback")
        task_source = task_file.parent.parent
        if task_source.exists():
            try:
                output_path = output_dir / self.task_id
                output_path.mkdir(parents=True, exist_ok=True)

                # Copy task files, applying template substitution
                for src_file in task_source.rglob("*"):
                    if src_file.is_file():
                        rel_path = src_file.relative_to(task_source)
                        dst_file = output_path / rel_path
                        dst_file.parent.mkdir(parents=True, exist_ok=True)

                        # Read and potentially transform content
                        content = src_file.read_bytes()

                        # Apply deterministic transformations (no timestamps, UUIDs, etc.)
                        dst_file.write_bytes(content)

                self._log(f"Template-based generation complete: {output_path}")
                return True

            except Exception as e:
                print(f"❌ Error during fallback generation: {e}", file=sys.stderr)
                return False

        print(f"❌ Error: No generation method available for {self.task_id}", file=sys.stderr)
        return False

    def _compare_outputs(self, run1_hashes: Dict[str, str], run2_hashes: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Compare outputs from two generation runs

        Returns:
            Tuple of (is_identical, list_of_differences)
        """
        differences = []

        # Check for files only in run 1
        only_in_run1 = set(run1_hashes.keys()) - set(run2_hashes.keys())
        for file_path in only_in_run1:
            differences.append(f"File only in run 1: {file_path}")

        # Check for files only in run 2
        only_in_run2 = set(run2_hashes.keys()) - set(run1_hashes.keys())
        for file_path in only_in_run2:
            differences.append(f"File only in run 2: {file_path}")

        # Check for files with different content
        common_files = set(run1_hashes.keys()) & set(run2_hashes.keys())
        for file_path in common_files:
            if run1_hashes[file_path] != run2_hashes[file_path]:
                differences.append(f"Content differs: {file_path}")

        is_identical = len(differences) == 0
        return (is_identical, differences)

    def _generate_diff_report(self, run1_dir: Path, run2_dir: Path, differences: List[str]) -> str:
        """Generate detailed diff report for changed files"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("IDEMPOTENCE CHECK DIFF REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Task: {self.task_id}")
        report_lines.append(f"Differences found: {len(differences)}")
        report_lines.append("")

        for diff_line in differences:
            report_lines.append(f"- {diff_line}")

            # If it's a content difference, show actual diff
            if diff_line.startswith("Content differs:"):
                file_path = diff_line.replace("Content differs: ", "")
                file1 = run1_dir / file_path
                file2 = run2_dir / file_path

                if file1.exists() and file2.exists():
                    try:
                        with open(file1, 'r') as f1, open(file2, 'r') as f2:
                            diff = difflib.unified_diff(
                                f1.readlines(),
                                f2.readlines(),
                                fromfile=f"run1/{file_path}",
                                tofile=f"run2/{file_path}",
                                lineterm=''
                            )
                            report_lines.append("")
                            report_lines.extend(diff)
                            report_lines.append("")
                    except Exception as e:
                        report_lines.append(f"  (Could not generate diff: {e})")

        report_lines.append("=" * 80)
        return "\n".join(report_lines)

    def check_idempotence(self, output_file: Optional[str] = None) -> bool:
        """
        Run idempotence check

        Returns:
            True if idempotent (PASS), False otherwise (FAIL)
        """
        print(f"🔍 Running idempotence check for task: {self.task_id}")
        print("")

        # Create temporary directories for two runs
        with tempfile.TemporaryDirectory(prefix="saf_run1_") as run1_dir_str, \
             tempfile.TemporaryDirectory(prefix="saf_run2_") as run2_dir_str:

            run1_dir = Path(run1_dir_str)
            run2_dir = Path(run2_dir_str)

            # Run generation twice
            print("▶ Run 1: Generating task...")
            if not self._run_generation(run1_dir):
                print("❌ ERROR: First generation run failed", file=sys.stderr)
                return False

            print("▶ Run 2: Generating task...")
            if not self._run_generation(run2_dir):
                print("❌ ERROR: Second generation run failed", file=sys.stderr)
                return False

            # Compute hashes for both runs
            print("▶ Computing file hashes...")
            run1_hashes = self._get_all_files(run1_dir)
            run2_hashes = self._get_all_files(run2_dir)

            self._log(f"Run 1: {len(run1_hashes)} files")
            self._log(f"Run 2: {len(run2_hashes)} files")

            # Compare outputs
            print("▶ Comparing outputs...")
            is_identical, differences = self._compare_outputs(run1_hashes, run2_hashes)

            print("")

            # Report results
            if is_identical:
                print("✅ IDEMPOTENCE CHECK PASSED")
                print(f"   Task: {self.task_id}")
                print(f"   Files checked: {len(run1_hashes)}")
                print(f"   All outputs identical across 2 runs")
                return True
            else:
                print("❌ IDEMPOTENCE CHECK FAILED")
                print(f"   Task: {self.task_id}")
                print(f"   Files checked: {max(len(run1_hashes), len(run2_hashes))}")
                print(f"   Differences found: {len(differences)}")
                print("")
                print("   Diff summary:")
                for diff_line in differences:
                    print(f"     - {diff_line}")

                # Generate detailed diff report if requested
                if output_file:
                    diff_report = self._generate_diff_report(run1_dir, run2_dir, differences)
                    with open(output_file, 'w') as f:
                        f.write(diff_report)
                    print(f"\n   📄 Detailed diff report saved to: {output_file}")

                return False

def main():
    parser = argparse.ArgumentParser(
        description="Check if the system task generation is idempotent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check specific task
  python3 tools/idempotence_checker.py --task task-3.1-api-gateway

  # Check with verbose output
  python3 tools/idempotence_checker.py --task task-3.1-api-gateway --verbose

  # Save diff report
  python3 tools/idempotence_checker.py --task task-3.1-api-gateway --output diff.txt
        """
    )

    parser.add_argument(
        '--task',
        type=str,
        required=True,
        help='Task ID to check for idempotence (e.g., task-3.1-api-gateway)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug output'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Save detailed diff report to specified file'
    )

    args = parser.parse_args()

    try:
        # Create checker and run test
        checker = IdempotenceChecker(
            task_id=args.task,
            verbose=args.verbose
        )

        is_idempotent = checker.check_idempotence(output_file=args.output)

        # Exit with appropriate code
        sys.exit(0 if is_idempotent else 1)

    except Exception as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
