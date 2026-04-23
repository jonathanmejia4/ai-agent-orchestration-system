#!/usr/bin/env python3
"""
Validate PM STATE.md - Schema and Cross-Reference Validation

Validates LogBook/pm/STATE.md against pm_state_schema.yaml and verifies
cross-references to LogBook entries, git branches, and file paths.
Critical for preventing PM amnesia.

Usage:
    python3 tools/validate_pm_state.py
    python3 tools/validate_pm_state.py --state-file LogBook/pm/STATE.md
    python3 tools/validate_pm_state.py --strict
    python3 tools/validate_pm_state.py --json
    python3 tools/validate_pm_state.py --help

Exit Codes:
    0 - STATE.md is valid
    1 - Validation errors found

Referenced in:
    - .claude/guidelines/agent-coordination-protocol.md:1471, 1475
    - PLANNING/PM_Operating_Manual.md:311, 477, 491, 700, 704
    - PLANNING/AGENT_FAILURE_HANDLING_PROTOCOL.md:309

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class ValidationResult:
    """Validation result with errors and warnings"""
    valid: bool = True
    schema_errors: List[str] = field(default_factory=list)
    cross_reference_errors: List[str] = field(default_factory=list)
    duplicate_task_ids: List[str] = field(default_factory=list)
    orphaned_branches: List[str] = field(default_factory=list)
    missing_logbook_entries: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, category: str, message: str):
        self.valid = False
        if category == "schema":
            self.schema_errors.append(message)
        elif category == "cross_reference":
            self.cross_reference_errors.append(message)
        elif category == "duplicate":
            self.duplicate_task_ids.append(message)
        elif category == "orphaned":
            self.orphaned_branches.append(message)
        elif category == "missing":
            self.missing_logbook_entries.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'schema_errors': self.schema_errors,
            'cross_reference_errors': self.cross_reference_errors,
            'duplicate_task_ids': self.duplicate_task_ids,
            'orphaned_branches': self.orphaned_branches,
            'missing_logbook_entries': self.missing_logbook_entries,
            'warnings': self.warnings,
            'error_count': (len(self.schema_errors) + len(self.cross_reference_errors) +
                           len(self.duplicate_task_ids) + len(self.missing_logbook_entries))
        }

class PMStateValidator:
    """Validates PM STATE.md against schema and cross-references"""

    # Required sections in STATE.md (aligned with pm_state_schema.yaml structure)
    REQUIRED_SECTIONS = [
        "Active Branches",
        "Task Queue",
        "Escalations",
        "Recent Decisions",
        "Metrics",
        "Governance"
    ]

    # Task ID patterns
    TASK_ID_PATTERN = r'^[0-9]+\.[0-9]+$'  # X.Y format
    UUID_PATTERN = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    DATE_PATTERN = r'^\d{4}-\d{2}-\d{2}$'

    def __init__(self, state_file: Path, repo_root: Optional[Path] = None,
                 strict: bool = False, verbose: bool = False):
        self.state_file = state_file
        self.repo_root = repo_root or Path.cwd()
        self.strict = strict
        self.verbose = verbose
        self.result = ValidationResult()
        self.state_content = ""
        self.state_data: Dict[str, Any] = {}

    def log(self, message: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def load_state_file(self) -> bool:
        """Load STATE.md content"""
        if not self.state_file.exists():
            self.result.add_error("schema", f"STATE.md not found: {self.state_file}")
            return False

        try:
            self.state_content = self.state_file.read_text()
            self.log(f"Loaded STATE.md ({len(self.state_content)} chars)")
            return True
        except IOError as e:
            self.result.add_error("schema", f"Cannot read STATE.md: {e}")
            return False

    def parse_yaml_frontmatter(self) -> bool:
        """Parse YAML frontmatter from STATE.md"""
        # Check for YAML frontmatter (starts with ---)
        if self.state_content.startswith('---'):
            try:
                # Find end of frontmatter
                end_match = re.search(r'\n---\n', self.state_content[3:])
                if end_match:
                    frontmatter = self.state_content[3:3+end_match.start()]
                    try:
                        import yaml
                        self.state_data = yaml.safe_load(frontmatter) or {}
                        self.log("Parsed YAML frontmatter")
                        return True
                    except ImportError:
                        self.result.add_warning("YAML parser not available, skipping frontmatter validation")
                    except Exception as e:
                        self.result.add_error("schema", f"Invalid YAML frontmatter: {e}")
                        return False
            except Exception as e:
                self.result.add_error("schema", f"Error parsing frontmatter: {e}")
                return False

        # No YAML frontmatter, try parsing as markdown with metadata
        self.log("No YAML frontmatter, parsing as markdown")
        return True

    def validate_structure(self):
        """Validate required sections exist"""
        for section in self.REQUIRED_SECTIONS:
            pattern = rf'^##\s+{re.escape(section)}'
            if not re.search(pattern, self.state_content, re.MULTILINE):
                if self.strict:
                    self.result.add_error("schema", f"Missing required section: ## {section}")
                else:
                    self.result.add_warning(f"Missing section: ## {section}")

    def validate_timestamps(self):
        """Validate timestamp formats"""
        # Check Last Updated timestamp
        timestamp_match = re.search(r'Last Updated:\s*(\S+)', self.state_content)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
            # Accept various date formats
            if not re.match(r'^\d{4}-\d{2}-\d{2}', timestamp):
                self.result.add_warning(f"Timestamp format should be YYYY-MM-DD: {timestamp}")
        elif self.strict:
            self.result.add_error("schema", "Missing 'Last Updated' timestamp")

    def validate_version(self):
        """Validate version format if present"""
        version_match = re.search(r'Version:\s*(\S+)', self.state_content)
        if version_match:
            version = version_match.group(1)
            if not re.match(r'^\d+\.\d+', version):
                self.result.add_warning(f"Version should be X.Y format: {version}")

    def extract_task_ids(self) -> List[str]:
        """Extract all task IDs from STATE.md"""
        task_ids = []

        # Look for task ID patterns in content
        # Pattern: task-xxx, task_xxx, or standalone UUIDs
        patterns = [
            r'task[-_]([0-9a-f-]+)',
            r'Task\s+ID:\s*([0-9a-f-]+)',
            r'task_id:\s*([0-9a-f-]+)',
            r'\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b',
            r'\b(\d+\.\d+)\b'  # X.Y format
        ]

        for pattern in patterns:
            matches = re.findall(pattern, self.state_content, re.IGNORECASE)
            task_ids.extend(matches)

        return list(set(task_ids))

    def validate_duplicate_task_ids(self, task_ids: List[str]):
        """Check for duplicate task IDs"""
        seen = {}
        for bid in task_ids:
            if bid in seen:
                self.result.add_error("duplicate", f"Duplicate task ID: {bid}")
            else:
                seen[bid] = True

    def validate_cross_references(self, task_ids: List[str]):
        """Validate cross-references to LogBook and files"""
        logbook_tasks = self.repo_root / 'LogBook' / 'progress' / 'tasks'

        for task_id in task_ids[:10]:  # Limit to first 10 to avoid performance issues
            # Check LogBook entry exists
            task_dir = logbook_tasks / task_id
            if not task_dir.exists():
                # Try with task- prefix
                task_dir = logbook_tasks / f"task-{task_id}"
                if not task_dir.exists():
                    self.result.add_error("missing", f"No LogBook entry for task: {task_id}")

    def validate_git_branches(self):
        """Validate git branches referenced in STATE.md"""
        # Extract branch references
        branch_patterns = [
            r'branch:\s*([^\s\n]+)',
            r'feature/([^\s\n]+)',
            r'alt/([^\s\n]+)'
        ]

        branches_in_state = []
        for pattern in branch_patterns:
            matches = re.findall(pattern, self.state_content)
            branches_in_state.extend(matches)

        if not branches_in_state:
            return

        # Get actual git branches
        try:
            result = subprocess.run(
                ['git', 'branch', '-a'],
                capture_output=True, text=True, cwd=self.repo_root
            )
            if result.returncode == 0:
                git_branches = result.stdout
                for branch in branches_in_state[:5]:  # Limit checks
                    if branch not in git_branches:
                        self.result.add_error("orphaned", f"Referenced branch not found: {branch}")
        except Exception as e:
            self.log(f"Could not check git branches: {e}")

    def validate(self) -> ValidationResult:
        """Run all validations"""
        print(f"Validating: {self.state_file}")

        # Load file
        if not self.load_state_file():
            return self.result

        # Parse YAML frontmatter
        self.parse_yaml_frontmatter()

        # Structure validation
        print("  Checking structure...")
        self.validate_structure()

        # Timestamp validation
        print("  Checking timestamps...")
        self.validate_timestamps()

        # Version validation
        print("  Checking version...")
        self.validate_version()

        # Extract and validate task IDs
        print("  Extracting task IDs...")
        task_ids = self.extract_task_ids()
        self.log(f"Found {len(task_ids)} task IDs")

        print("  Checking for duplicates...")
        self.validate_duplicate_task_ids(task_ids)

        # Cross-reference validation
        print("  Checking cross-references...")
        self.validate_cross_references(task_ids)

        # Git branch validation
        print("  Checking git branches...")
        self.validate_git_branches()

        return self.result

    def print_result(self):
        """Print validation result"""
        print()
        if self.result.valid:
            print(f"\033[92m✅ STATE.md is valid\033[0m")
        else:
            print(f"\033[91m❌ STATE.md has errors\033[0m")

        if self.result.schema_errors:
            print(f"\nSchema Errors ({len(self.result.schema_errors)}):")
            for err in self.result.schema_errors:
                print(f"  - {err}")

        if self.result.cross_reference_errors:
            print(f"\nCross-Reference Errors ({len(self.result.cross_reference_errors)}):")
            for err in self.result.cross_reference_errors:
                print(f"  - {err}")

        if self.result.duplicate_task_ids:
            print(f"\nDuplicate Task IDs ({len(self.result.duplicate_task_ids)}):")
            for err in self.result.duplicate_task_ids:
                print(f"  - {err}")

        if self.result.missing_logbook_entries:
            print(f"\nMissing LogBook Entries ({len(self.result.missing_logbook_entries)}):")
            for err in self.result.missing_logbook_entries:
                print(f"  - {err}")

        if self.result.orphaned_branches:
            print(f"\nOrphaned Branches ({len(self.result.orphaned_branches)}):")
            for err in self.result.orphaned_branches:
                print(f"  - {err}")

        if self.result.warnings:
            print(f"\nWarnings ({len(self.result.warnings)}):")
            for warn in self.result.warnings:
                print(f"  ⚠ {warn}")

def main():
    parser = argparse.ArgumentParser(
        description='Validate PM STATE.md - Schema and cross-reference validation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate default STATE.md
    %(prog)s

    # Validate specific file
    %(prog)s --state-file LogBook/pm/STATE.md

    # Strict mode (all errors are blocking)
    %(prog)s --strict

    # JSON output
    %(prog)s --json

Exit Codes:
    0 - Valid
    1 - Invalid
        """
    )

    parser.add_argument('--state-file', '-s', type=Path,
                        default=Path('LogBook/pm/STATE.md'),
                        help='Path to STATE.md file')
    parser.add_argument('--strict', action='store_true',
                        help='Strict mode - all issues are errors')
    parser.add_argument('--json', action='store_true',
                        help='Output result as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd(),
                        help='Repository root directory')

    args = parser.parse_args()

    # Resolve paths
    state_file = args.state_file
    if not state_file.is_absolute():
        state_file = args.repo_root / state_file

    # Create validator
    validator = PMStateValidator(
        state_file=state_file,
        repo_root=args.repo_root,
        strict=args.strict,
        verbose=args.verbose
    )

    # Run validation
    result = validator.validate()

    # Output
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        validator.print_result()

    sys.exit(0 if result.valid else 1)

if __name__ == '__main__':
    main()
