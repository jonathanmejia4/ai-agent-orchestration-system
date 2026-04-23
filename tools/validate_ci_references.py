#!/usr/bin/env python3
"""
CI Workflow Cross-Reference Validator

Validates that workflow files referenced in PLANNING docs actually exist
in .github/workflows/ and detects orphaned/undocumented workflows.

Usage:
    python3 tools/validate_ci_references.py
    python3 tools/validate_ci_references.py --policy PLANNING/CI_WORKFLOW_TRIGGER_PROTOCOL.md
    python3 tools/validate_ci_references.py --find-orphans
    python3 tools/validate_ci_references.py --json
    python3 tools/validate_ci_references.py --help

Exit Codes:
    0 - All references valid
    1 - Missing or orphaned workflows found
    2 - Error

Referenced in:
    - PLANNING/CI_WORKFLOW_TRIGGER_PROTOCOL.md:26, 32, 46, 52, 66, 78, 85

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field, asdict

@dataclass
class ValidationResult:
    """CI reference validation result"""
    valid: bool = True
    referenced_workflows: List[str] = field(default_factory=list)
    existing_workflows: List[str] = field(default_factory=list)
    missing_workflows: List[str] = field(default_factory=list)
    orphaned_workflows: List[str] = field(default_factory=list)
    reference_locations: Dict[str, List[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'referenced_workflows': self.referenced_workflows,
            'existing_workflows': self.existing_workflows,
            'missing_workflows': self.missing_workflows,
            'orphaned_workflows': self.orphaned_workflows,
            'reference_locations': self.reference_locations,
            'warnings': self.warnings,
            'missing_count': len(self.missing_workflows),
            'orphaned_count': len(self.orphaned_workflows)
        }

class CIReferenceValidator:
    """Validates CI workflow cross-references"""

    # Workflow filename patterns
    WORKFLOW_PATTERN = r'[a-zA-Z0-9_-]+\.ya?ml'

    # Files to scan for workflow references
    POLICY_FILES = [
        'PLANNING/CI_WORKFLOW_TRIGGER_PROTOCOL.md',
        'PLANNING/STAGE_GATED_GENERATION_PIPELINE_POLICY.md',
        '.claude/guidelines/agent-coordination-protocol.md',
        'PLANNING/Builder_Operating_Manual.md',
        'PLANNING/PM_Operating_Manual.md',
    ]

    def __init__(self, repo_root: Optional[Path] = None, verbose: bool = False):
        self.repo_root = repo_root or Path.cwd()
        self.verbose = verbose
        self.workflows_dir = self.repo_root / '.github' / 'workflows'

    def log(self, message: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def get_existing_workflows(self) -> Set[str]:
        """Get list of existing workflow files"""
        workflows = set()
        if self.workflows_dir.exists():
            for f in self.workflows_dir.iterdir():
                if f.suffix in ['.yml', '.yaml']:
                    workflows.add(f.name)
        return workflows

    def extract_workflow_references(self, file_path: Path) -> Dict[str, List[str]]:
        """Extract workflow file references from a file"""
        references: Dict[str, List[str]] = {}

        if not file_path.exists():
            return references

        try:
            content = file_path.read_text()
            lines = content.split('\n')

            for i, line in enumerate(lines, 1):
                # Look for workflow references
                # Patterns: workflow_name.yml, workflows/name.yml, gh workflow run name.yml
                matches = re.findall(r'(?:workflows?/)?([a-zA-Z0-9_-]+\.ya?ml)', line)
                for match in matches:
                    # Normalize .yaml to .yml
                    normalized = match.replace('.yaml', '.yml')
                    if normalized not in references:
                        references[normalized] = []
                    references[normalized].append(f"{file_path}:{i}")

        except Exception as e:
            self.log(f"Error reading {file_path}: {e}")

        return references

    def scan_all_policy_files(self) -> Dict[str, List[str]]:
        """Scan all policy files for workflow references"""
        all_references: Dict[str, List[str]] = {}

        for policy_file in self.POLICY_FILES:
            path = self.repo_root / policy_file
            if path.exists():
                refs = self.extract_workflow_references(path)
                for workflow, locations in refs.items():
                    if workflow not in all_references:
                        all_references[workflow] = []
                    all_references[workflow].extend(locations)

        # Also scan PLANNING/*.md for any workflow references
        planning_dir = self.repo_root / 'PLANNING'
        if planning_dir.exists():
            for md_file in planning_dir.glob('*.md'):
                if md_file.name not in [Path(f).name for f in self.POLICY_FILES]:
                    refs = self.extract_workflow_references(md_file)
                    for workflow, locations in refs.items():
                        if workflow not in all_references:
                            all_references[workflow] = []
                        all_references[workflow].extend(locations)

        return all_references

    def validate(self, policy_file: Optional[Path] = None,
                 find_orphans: bool = True) -> ValidationResult:
        """Run validation"""
        result = ValidationResult()

        # Get existing workflows
        existing = self.get_existing_workflows()
        result.existing_workflows = sorted(existing)
        self.log(f"Found {len(existing)} existing workflows")

        # Get referenced workflows
        if policy_file:
            references = self.extract_workflow_references(policy_file)
        else:
            references = self.scan_all_policy_files()

        result.referenced_workflows = sorted(references.keys())
        result.reference_locations = references
        self.log(f"Found {len(references)} referenced workflows")

        # Find missing workflows (referenced but don't exist)
        for workflow in references:
            if workflow not in existing:
                result.missing_workflows.append(workflow)
                result.valid = False

        # Find orphaned workflows (exist but not referenced)
        if find_orphans:
            referenced_set = set(references.keys())
            for workflow in existing:
                if workflow not in referenced_set:
                    result.orphaned_workflows.append(workflow)
                    # Orphans are warnings, not errors
                    result.warnings.append(f"Undocumented workflow: {workflow}")

        return result

def print_result(result: ValidationResult, format: str = "text"):
    """Print validation result"""
    if format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return

    print()
    if result.valid:
        print(f"\033[92m✅ CI workflow references valid\033[0m")
    else:
        print(f"\033[91m❌ CI workflow reference errors found\033[0m")

    print(f"\nExisting workflows: {len(result.existing_workflows)}")
    print(f"Referenced workflows: {len(result.referenced_workflows)}")

    if result.missing_workflows:
        print(f"\n\033[91mMissing Workflows ({len(result.missing_workflows)}):\033[0m")
        for workflow in result.missing_workflows:
            print(f"  ❌ {workflow}")
            if workflow in result.reference_locations:
                for loc in result.reference_locations[workflow][:3]:
                    print(f"      Referenced in: {loc}")

    if result.orphaned_workflows:
        print(f"\n\033[93mOrphaned/Undocumented Workflows ({len(result.orphaned_workflows)}):\033[0m")
        for workflow in result.orphaned_workflows[:10]:
            print(f"  ⚠ {workflow}")
        if len(result.orphaned_workflows) > 10:
            print(f"  ... and {len(result.orphaned_workflows) - 10} more")

    if result.warnings and not result.orphaned_workflows:
        print(f"\nWarnings ({len(result.warnings)}):")
        for warn in result.warnings:
            print(f"  ⚠ {warn}")

def main():
    parser = argparse.ArgumentParser(
        description='Validate CI workflow cross-references',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate all policy files
    %(prog)s

    # Check specific policy file
    %(prog)s --policy PLANNING/CI_WORKFLOW_TRIGGER_PROTOCOL.md

    # Find orphaned workflows only
    %(prog)s --find-orphans

    # JSON output
    %(prog)s --json

Exit Codes:
    0 - All references valid
    1 - Missing workflows found
    2 - Error
        """
    )

    parser.add_argument('--policy', '-p', type=Path,
                       help='Specific policy file to validate')
    parser.add_argument('--find-orphans', '-o', action='store_true',
                       help='Also find orphaned/undocumented workflows')
    parser.add_argument('--json', action='store_true',
                       help='Output result as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd(),
                       help='Repository root directory')

    args = parser.parse_args()

    validator = CIReferenceValidator(
        repo_root=args.repo_root,
        verbose=args.verbose
    )

    result = validator.validate(
        policy_file=args.policy,
        find_orphans=args.find_orphans or args.policy is None
    )

    print_result(result, 'json' if args.json else 'text')
    sys.exit(0 if result.valid else 1)

if __name__ == '__main__':
    main()
