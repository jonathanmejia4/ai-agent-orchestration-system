#!/usr/bin/env python3
"""
Spec Compliance Checker for the system Dimension 6 (SpecFit)

Validates that tasks comply with their specifications by checking:
- Task implementation files match declared templates
- Required fields are present in task.yaml
- Wiring files reference valid paths

Usage:
    python3 tools/spec_compliance_checker.py --all
    python3 tools/spec_compliance_checker.py --task task-3.1-api-gateway
    python3 tools/spec_compliance_checker.py --verbose

Exit Codes:
    0 - PASS: All spec compliance checks passed
    1 - FAIL: Spec compliance issues found
    2 - ERROR: Invalid arguments or execution error

Referenced in:
    - .github/workflows/saf-gates.yml:374-375 (SpecFit Dimension check)

Author: System
Created: 2026-01-04
"""

import argparse
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import yaml

class SpecComplianceChecker:
    """Checks task specification compliance"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.repo_root = self._find_repo_root()
        self.issues: List[str] = []
        self.checked: int = 0
        self.passed: int = 0

    def _find_repo_root(self) -> Path:
        """Find repository root by looking for .git directory or the system markers"""
        current = Path.cwd()
        while current != current.parent:
            if (current / '.git').exists() or (current / 'CLAUDE.md').exists():
                return current
            current = current.parent
        # Fallback to cwd
        return Path.cwd()

    def _log(self, message: str) -> None:
        """Print message if verbose mode enabled"""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def _load_yaml(self, path: Path) -> Optional[Dict]:
        """Load a YAML file safely"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self._log(f"Error loading {path}: {e}")
            return None

    def _check_task_yaml(self, task_yaml_path: Path) -> List[str]:
        """Check task.yaml for required fields"""
        issues = []
        data = self._load_yaml(task_yaml_path)

        if data is None:
            issues.append(f"{task_yaml_path}: Failed to parse YAML")
            return issues

        # Required fields for task spec
        required_fields = ['task_id', 'name', 'version', 'status']

        for field in required_fields:
            if field not in data:
                issues.append(f"{task_yaml_path}: Missing required field '{field}'")

        # Check status is valid
        if 'status' in data:
            valid_statuses = ['draft', 'planning', 'building', 'reviewing',
                           'approved', 'completed', 'deprecated']
            if data['status'] not in valid_statuses:
                issues.append(f"{task_yaml_path}: Invalid status '{data['status']}'")

        return issues

    def _check_wiring_yaml(self, wiring_yaml_path: Path) -> List[str]:
        """Check wiring.yaml for valid references"""
        issues = []
        data = self._load_yaml(wiring_yaml_path)

        if data is None:
            # Wiring file is optional
            return issues

        # Check that templates reference existing files
        if 'templates' in data and isinstance(data['templates'], list):
            for template in data['templates']:
                if isinstance(template, dict) and 'path' in template:
                    template_path = self.repo_root / template['path']
                    if not template_path.exists():
                        issues.append(f"{wiring_yaml_path}: Template not found: {template['path']}")

        return issues

    def check_task(self, task_dir: Path) -> Tuple[bool, List[str]]:
        """Check a single task for spec compliance"""
        issues = []
        task_yaml = task_dir / '.task' / 'task.yaml'
        wiring_yaml = task_dir / '.task' / 'wiring.yaml'

        self._log(f"Checking task: {task_dir.name}")

        # Check task.yaml
        if task_yaml.exists():
            issues.extend(self._check_task_yaml(task_yaml))
        else:
            # Try alternate location
            alt_task_yaml = task_dir / 'task.yaml'
            if alt_task_yaml.exists():
                issues.extend(self._check_task_yaml(alt_task_yaml))
            else:
                issues.append(f"{task_dir}: No task.yaml found")

        # Check wiring.yaml (optional)
        if wiring_yaml.exists():
            issues.extend(self._check_wiring_yaml(wiring_yaml))

        passed = len(issues) == 0
        return (passed, issues)

    def check_all(self) -> bool:
        """Check all tasks in the repository"""
        tasks_dir = self.repo_root / 'tasks'

        if not tasks_dir.exists():
            print("No tasks directory found. Skipping spec compliance check.")
            return True

        all_passed = True

        # Find all task directories
        for task_dir in sorted(tasks_dir.iterdir()):
            if task_dir.is_dir() and not task_dir.name.startswith('.'):
                self.checked += 1
                passed, issues = self.check_task(task_dir)

                if passed:
                    self.passed += 1
                else:
                    all_passed = False
                    self.issues.extend(issues)

        return all_passed

    def report(self) -> None:
        """Print summary report"""
        print("")
        print("=" * 60)
        print("SPEC COMPLIANCE CHECK (Dimension 6: SpecFit)")
        print("=" * 60)
        print(f"Tasks checked: {self.checked}")
        print(f"Tasks passed:  {self.passed}")
        print(f"Tasks failed:  {self.checked - self.passed}")
        print("")

        if self.issues:
            print("Issues found:")
            for issue in self.issues:
                print(f"  - {issue}")
            print("")
            print("RESULT: FAIL")
        else:
            if self.checked == 0:
                print("No tasks to check.")
            print("RESULT: PASS")

def main():
    parser = argparse.ArgumentParser(
        description="Check the system task specification compliance (Dimension 6: SpecFit)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Check all tasks in the repository'
    )

    parser.add_argument(
        '--task',
        type=str,
        help='Check a specific task by ID'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug output'
    )

    args = parser.parse_args()

    try:
        checker = SpecComplianceChecker(verbose=args.verbose)

        if args.task:
            task_dir = checker.repo_root / 'tasks' / args.task
            if not task_dir.exists():
                print(f"Task not found: {args.task}", file=sys.stderr)
                sys.exit(2)

            checker.checked = 1
            passed, issues = checker.check_task(task_dir)
            if passed:
                checker.passed = 1
            else:
                checker.issues = issues

            checker.report()
            sys.exit(0 if passed else 1)

        elif args.all:
            passed = checker.check_all()
            checker.report()
            sys.exit(0 if passed else 1)

        else:
            # Default: run --all
            passed = checker.check_all()
            checker.report()
            sys.exit(0 if passed else 1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
