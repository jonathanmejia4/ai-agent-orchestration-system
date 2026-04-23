#!/usr/bin/env python3
"""
Protected Regions - Extract, Validate, and Reinsert Protected Code Regions

Manages protected regions in generated files that are preserved during regeneration.
Protected regions allow controlled manual customizations within generated code.

Usage:
    # Extract regions from a file
    python3 tools/protected_regions.py extract src/service.ts

    # Validate all regions in a task
    python3 tools/protected_regions.py validate .task/

    # Reinsert regions after regeneration
    python3 tools/protected_regions.py reinsert --regions regions.json --file src/service.ts

    # Check region limits
    python3 tools/protected_regions.py check-limits src/

    # Calculate hash for region content
    python3 tools/protected_regions.py hash "region content here"

    # Run all 8 mechanical checks
    python3 tools/protected_regions.py full-check .task/

Exit Codes:
    0 - All checks passed / operation successful
    1 - Validation errors found
    2 - Error (missing files, invalid syntax, etc.)

Referenced in:
    - PROTECTED_REGIONS_POLICY.md
    - Builder.md
    - THREE_WAY_MERGE_REGENERATION_POLICY.md

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import hashlib
import json
import yaml
import glob
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

# Region name allowlist (approved names)
REGION_ALLOWLIST = [
    'custom_validation',
    'custom_logic',
    'custom_ui',
    'custom_error_mapping',
    'custom_logging',
    'custom_metrics',
    'custom_setup',        # For tests
    'custom_assertions',   # For tests
    'custom_examples',     # For docs
    'custom_notes',        # For docs
]

# Limits
MAX_REGIONS_PER_FILE = 2
MAX_LINES_PER_REGION = 80

# Comment syntax by file extension
COMMENT_SYNTAX = {
    '.py': '#',
    '.ts': '//',
    '.js': '//',
    '.tsx': '//',
    '.jsx': '//',
    '.go': '//',
    '.rs': '//',
    '.java': '//',
    '.c': '//',
    '.cpp': '//',
    '.h': '//',
    '.hpp': '//',
    '.rb': '#',
    '.sh': '#',
    '.yaml': '#',
    '.yml': '#',
    '.md': '<!--',  # Special handling for markdown
}

@dataclass
class ProtectedRegion:
    """Represents a protected region in a file"""
    name: str
    content: str
    hash: str
    start_line: int
    end_line: int
    line_count: int

@dataclass
class ValidationResult:
    """Result of region validation"""
    passed: bool
    check_name: str
    violations: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

@dataclass
class FullValidationResult:
    """Result of all 8 mechanical checks"""
    passed: bool
    checks: List[ValidationResult] = field(default_factory=list)
    total_violations: int = 0
    summary: str = ""

class ProtectedRegionManager:
    """Manages protected regions in generated files"""

    # Regex patterns for region markers
    BEGIN_PATTERN = re.compile(
        r'@saf:region\s+begin\s+name=(\w+)\s+hash=(sha256:[a-f0-9]+|PLACEHOLDER)',
        re.IGNORECASE
    )
    END_PATTERN = re.compile(
        r'@saf:region\s+end\s+name=(\w+)',
        re.IGNORECASE
    )

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def calculate_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of region content"""
        content_bytes = content.strip().encode('utf-8')
        hash_obj = hashlib.sha256(content_bytes)
        return f"sha256:{hash_obj.hexdigest()[:16]}"

    def extract_regions(self, file_path: Path) -> Dict[str, ProtectedRegion]:
        """
        Extract all protected regions from a file.

        Returns:
            Dict[region_name, ProtectedRegion]
        """
        if not file_path.exists():
            return {}

        content = file_path.read_text()
        lines = content.split('\n')
        regions = {}

        i = 0
        while i < len(lines):
            line = lines[i]
            begin_match = self.BEGIN_PATTERN.search(line)

            if begin_match:
                region_name = begin_match.group(1)
                stored_hash = begin_match.group(2)
                start_line = i + 1  # 1-indexed

                # Find matching end marker
                region_content_lines = []
                j = i + 1
                end_found = False

                while j < len(lines):
                    end_match = self.END_PATTERN.search(lines[j])
                    if end_match and end_match.group(1) == region_name:
                        end_found = True
                        end_line = j + 1  # 1-indexed
                        break
                    region_content_lines.append(lines[j])
                    j += 1

                if end_found:
                    region_content = '\n'.join(region_content_lines)
                    actual_hash = self.calculate_hash(region_content)

                    regions[region_name] = ProtectedRegion(
                        name=region_name,
                        content=region_content,
                        hash=stored_hash if stored_hash != 'PLACEHOLDER' else actual_hash,
                        start_line=start_line,
                        end_line=end_line,
                        line_count=len(region_content_lines)
                    )
                    i = j + 1
                    continue

            i += 1

        return regions

    def extract_regions_from_content(self, content: str) -> Dict[str, ProtectedRegion]:
        """Extract regions from content string instead of file"""
        lines = content.split('\n')
        regions = {}

        i = 0
        while i < len(lines):
            line = lines[i]
            begin_match = self.BEGIN_PATTERN.search(line)

            if begin_match:
                region_name = begin_match.group(1)
                stored_hash = begin_match.group(2)
                start_line = i + 1

                region_content_lines = []
                j = i + 1
                end_found = False

                while j < len(lines):
                    end_match = self.END_PATTERN.search(lines[j])
                    if end_match and end_match.group(1) == region_name:
                        end_found = True
                        end_line = j + 1
                        break
                    region_content_lines.append(lines[j])
                    j += 1

                if end_found:
                    region_content = '\n'.join(region_content_lines)
                    actual_hash = self.calculate_hash(region_content)

                    regions[region_name] = ProtectedRegion(
                        name=region_name,
                        content=region_content,
                        hash=stored_hash if stored_hash != 'PLACEHOLDER' else actual_hash,
                        start_line=start_line,
                        end_line=end_line,
                        line_count=len(region_content_lines)
                    )
                    i = j + 1
                    continue

            i += 1

        return regions

    def reinsert_regions(self, regenerated_content: str,
                         regions: Dict[str, ProtectedRegion],
                         update_hashes: bool = True) -> str:
        """
        Reinsert extracted regions into regenerated content.

        Args:
            regenerated_content: Newly generated content with PLACEHOLDER hashes
            regions: Previously extracted regions to reinsert
            update_hashes: Whether to update hashes to match content

        Returns:
            Content with regions reinserted
        """
        result = regenerated_content

        for region_name, region in regions.items():
            # Calculate new hash if updating
            new_hash = self.calculate_hash(region.content) if update_hashes else region.hash

            # Find placeholder pattern and replace
            # Pattern: @saf:region begin name=NAME hash=PLACEHOLDER followed by placeholder content
            placeholder_pattern = re.compile(
                rf'(@saf:region\s+begin\s+name={region_name}\s+hash=)PLACEHOLDER'
                rf'(.*?)(@saf:region\s+end\s+name={region_name})',
                re.DOTALL | re.IGNORECASE
            )

            def replacer(match):
                return f'{match.group(1)}{new_hash}\n{region.content}\n{match.group(3)}'

            result = placeholder_pattern.sub(replacer, result)

        return result

    # ==================== Validation Checks ====================

    def check_region_markers(self, file_path: Path) -> ValidationResult:
        """Check 1: Verify region markers are well-formed"""
        result = ValidationResult(passed=True, check_name="Region Markers Valid")

        if not file_path.exists():
            result.violations.append(f"File not found: {file_path}")
            result.passed = False
            return result

        content = file_path.read_text()

        # Find all begin markers
        begins = self.BEGIN_PATTERN.findall(content)
        begin_names = [b[0] for b in begins]

        # Find all end markers
        ends = self.END_PATTERN.findall(content)

        # Check for unmatched begins
        for name in begin_names:
            if name not in ends:
                result.violations.append(f"Missing end marker for region '{name}'")
                result.passed = False

        # Check for unmatched ends
        for name in ends:
            if name not in begin_names:
                result.violations.append(f"Missing begin marker for region '{name}'")
                result.passed = False

        # Check for duplicate region names
        if len(begin_names) != len(set(begin_names)):
            seen = set()
            duplicates = []
            for name in begin_names:
                if name in seen:
                    duplicates.append(name)
                seen.add(name)
            result.violations.append(f"Duplicate region names: {duplicates}")
            result.passed = False

        if result.passed:
            result.info.append(f"Found {len(begin_names)} valid region(s)")

        return result

    def check_region_allowlist(self, file_path: Path) -> ValidationResult:
        """Check 2: Verify region names from approved allowlist"""
        result = ValidationResult(passed=True, check_name="Region Names Allowlist")

        regions = self.extract_regions(file_path)

        for region_name in regions.keys():
            if region_name not in REGION_ALLOWLIST:
                result.violations.append(
                    f"Region '{region_name}' not in allowlist. "
                    f"Allowed: {REGION_ALLOWLIST}"
                )
                result.passed = False

        if result.passed and regions:
            result.info.append(f"All {len(regions)} region name(s) are valid")

        return result

    def check_region_limits(self, file_path: Path) -> ValidationResult:
        """Check 3: Verify region count and size limits"""
        result = ValidationResult(passed=True, check_name="Region Limits")

        regions = self.extract_regions(file_path)

        # Check per-file limit
        if len(regions) > MAX_REGIONS_PER_FILE:
            result.violations.append(
                f"{file_path}: Exceeds max {MAX_REGIONS_PER_FILE} regions per file "
                f"(has {len(regions)})"
            )
            result.passed = False

        # Check per-region line limit
        for region_name, region in regions.items():
            if region.line_count > MAX_LINES_PER_REGION:
                result.violations.append(
                    f"{file_path}:{region_name}: Exceeds max {MAX_LINES_PER_REGION} lines "
                    f"(has {region.line_count})"
                )
                result.passed = False

        if result.passed and regions:
            total_lines = sum(r.line_count for r in regions.values())
            result.info.append(
                f"{len(regions)} region(s), {total_lines} total lines "
                f"(limits: {MAX_REGIONS_PER_FILE} regions, {MAX_LINES_PER_REGION} lines/region)"
            )

        return result

    def check_ssot_correspondence(self, task_path: Path) -> ValidationResult:
        """Check 4: Verify regions in SSOT match regions in code"""
        result = ValidationResult(passed=True, check_name="SSOT Correspondence")

        wiring_path = task_path / '.task' / 'wiring.yaml'
        if not wiring_path.exists():
            result.info.append("No .task/wiring.yaml found - skipping SSOT check")
            return result

        try:
            with open(wiring_path, 'r') as f:
                wiring = yaml.safe_load(f)
        except yaml.YAMLError as e:
            result.violations.append(f"Invalid YAML in wiring.yaml: {e}")
            result.passed = False
            return result

        ssot_regions = wiring.get('protected_regions', [])
        if not ssot_regions:
            result.info.append("No protected_regions in SSOT")
            return result

        # Build SSOT index
        ssot_index = {}
        for file_entry in ssot_regions:
            file_path = file_entry.get('file', '')
            regions = file_entry.get('regions', [])
            ssot_index[file_path] = set(r.get('name', '') for r in regions)

        # Scan code for regions
        for file_pattern in ['**/*.ts', '**/*.py', '**/*.js', '**/*.go']:
            for file_path in task_path.glob(file_pattern):
                if '.task' in str(file_path):
                    continue

                regions = self.extract_regions(file_path)
                code_region_names = set(regions.keys())

                rel_path = str(file_path.relative_to(task_path))
                ssot_region_names = ssot_index.get(rel_path, set())

                # Phantom regions (SSOT has, code doesn't)
                phantom = ssot_region_names - code_region_names
                if phantom:
                    result.violations.append(
                        f"{rel_path}: Phantom regions in SSOT (not in code): {phantom}"
                    )
                    result.passed = False

                # Undeclared regions (code has, SSOT doesn't)
                undeclared = code_region_names - ssot_region_names
                if undeclared:
                    result.violations.append(
                        f"{rel_path}: Undeclared regions in code (not in SSOT): {undeclared}"
                    )
                    result.passed = False

        return result

    def check_hash_integrity(self, file_path: Path) -> ValidationResult:
        """Check 5: Verify region hashes match content"""
        result = ValidationResult(passed=True, check_name="Hash Integrity")

        content = file_path.read_text()
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]
            begin_match = self.BEGIN_PATTERN.search(line)

            if begin_match:
                region_name = begin_match.group(1)
                stored_hash = begin_match.group(2)

                if stored_hash == 'PLACEHOLDER':
                    result.info.append(f"Region '{region_name}' has PLACEHOLDER hash (empty)")
                    i += 1
                    continue

                # Find content
                region_content_lines = []
                j = i + 1
                while j < len(lines):
                    end_match = self.END_PATTERN.search(lines[j])
                    if end_match and end_match.group(1) == region_name:
                        break
                    region_content_lines.append(lines[j])
                    j += 1

                region_content = '\n'.join(region_content_lines)
                actual_hash = self.calculate_hash(region_content)

                if actual_hash != stored_hash:
                    result.violations.append(
                        f"{file_path}:{region_name}: Hash mismatch "
                        f"(stored: {stored_hash}, actual: {actual_hash})"
                    )
                    result.passed = False
                else:
                    result.info.append(f"Region '{region_name}' hash verified")

                i = j + 1
                continue

            i += 1

        return result

    def check_interface_alterations(self, file_path: Path) -> ValidationResult:
        """Check 6: Verify regions don't alter interfaces"""
        result = ValidationResult(passed=True, check_name="No Interface Alterations")

        regions = self.extract_regions(file_path)

        # Patterns that indicate interface alterations
        forbidden_patterns = [
            (r'\bdef\s+\w+\s*\(', 'function definition (Python)'),
            (r'\bfunction\s+\w+\s*\(', 'function definition (JS)'),
            (r'\bclass\s+\w+', 'class definition'),
            (r'\bexport\s+interface\b', 'exported interface'),
            (r'\bexport\s+type\b', 'exported type'),
            (r'\bexport\s+class\b', 'exported class'),
            (r'\bexport\s+function\b', 'exported function'),
            (r'app\.(get|post|put|delete|patch)\s*\(', 'route definition'),
            (r'router\.(get|post|put|delete|patch)\s*\(', 'route definition'),
        ]

        for region_name, region in regions.items():
            for pattern, description in forbidden_patterns:
                if re.search(pattern, region.content, re.IGNORECASE):
                    result.violations.append(
                        f"{file_path}:{region_name}: Contains {description} "
                        f"(interface alteration forbidden)"
                    )
                    result.passed = False

        if result.passed and regions:
            result.info.append("No interface alterations detected")

        return result

    def check_region_rationale(self, task_path: Path) -> ValidationResult:
        """Check 7: Verify all regions have documented rationale in SSOT"""
        result = ValidationResult(passed=True, check_name="Region Rationale Documented")

        wiring_path = task_path / '.task' / 'wiring.yaml'
        if not wiring_path.exists():
            result.info.append("No .task/wiring.yaml found - skipping rationale check")
            return result

        try:
            with open(wiring_path, 'r') as f:
                wiring = yaml.safe_load(f)
        except yaml.YAMLError:
            return result

        for file_entry in wiring.get('protected_regions', []):
            file_path = file_entry.get('file', '')
            for region in file_entry.get('regions', []):
                rationale = region.get('rationale', '')
                if not rationale or rationale.strip() == '':
                    result.violations.append(
                        f"{file_path}:{region.get('name', 'unknown')}: Missing rationale in SSOT"
                    )
                    result.passed = False

        return result

    def check_graduation_tracking(self, task_path: Path) -> ValidationResult:
        """Check 8: Verify graduation eligibility tracked for all regions"""
        result = ValidationResult(passed=True, check_name="Graduation Tracking")

        wiring_path = task_path / '.task' / 'wiring.yaml'
        if not wiring_path.exists():
            result.info.append("No .task/wiring.yaml found - skipping graduation check")
            return result

        try:
            with open(wiring_path, 'r') as f:
                wiring = yaml.safe_load(f)
        except yaml.YAMLError:
            return result

        for file_entry in wiring.get('protected_regions', []):
            file_path = file_entry.get('file', '')
            for region in file_entry.get('regions', []):
                region_name = region.get('name', 'unknown')
                graduation = region.get('graduation', {})

                if 'eligible' not in graduation:
                    result.violations.append(
                        f"{file_path}:{region_name}: Missing graduation.eligible field"
                    )
                    result.passed = False

                if 'usage_count' not in graduation:
                    result.violations.append(
                        f"{file_path}:{region_name}: Missing graduation.usage_count field"
                    )
                    result.passed = False

                # Check consistency
                usage_count = graduation.get('usage_count', 0)
                eligible = graduation.get('eligible', False)
                if usage_count >= 3 and not eligible:
                    result.violations.append(
                        f"{file_path}:{region_name}: Used {usage_count} times "
                        f"but not marked eligible for graduation"
                    )
                    result.passed = False

        return result

    def run_full_validation(self, task_path: Path) -> FullValidationResult:
        """Run all 8 mechanical checks for protected regions"""
        result = FullValidationResult(passed=True)

        # Get all source files
        source_files = []
        for pattern in ['**/*.ts', '**/*.py', '**/*.js', '**/*.go', '**/*.tsx', '**/*.jsx']:
            source_files.extend(task_path.glob(pattern))

        # Filter out .task directory
        source_files = [f for f in source_files if '.task' not in str(f)]

        # Run checks that operate on individual files
        for file_path in source_files:
            regions = self.extract_regions(file_path)
            if not regions:
                continue

            # Check 1: Markers
            check1 = self.check_region_markers(file_path)
            result.checks.append(check1)
            if not check1.passed:
                result.passed = False
                result.total_violations += len(check1.violations)

            # Check 2: Allowlist
            check2 = self.check_region_allowlist(file_path)
            result.checks.append(check2)
            if not check2.passed:
                result.passed = False
                result.total_violations += len(check2.violations)

            # Check 3: Limits
            check3 = self.check_region_limits(file_path)
            result.checks.append(check3)
            if not check3.passed:
                result.passed = False
                result.total_violations += len(check3.violations)

            # Check 5: Hash Integrity
            check5 = self.check_hash_integrity(file_path)
            result.checks.append(check5)
            if not check5.passed:
                result.passed = False
                result.total_violations += len(check5.violations)

            # Check 6: Interface Alterations
            check6 = self.check_interface_alterations(file_path)
            result.checks.append(check6)
            if not check6.passed:
                result.passed = False
                result.total_violations += len(check6.violations)

        # Run checks that operate on task level
        # Check 4: SSOT Correspondence
        check4 = self.check_ssot_correspondence(task_path)
        result.checks.append(check4)
        if not check4.passed:
            result.passed = False
            result.total_violations += len(check4.violations)

        # Check 7: Rationale
        check7 = self.check_region_rationale(task_path)
        result.checks.append(check7)
        if not check7.passed:
            result.passed = False
            result.total_violations += len(check7.violations)

        # Check 8: Graduation
        check8 = self.check_graduation_tracking(task_path)
        result.checks.append(check8)
        if not check8.passed:
            result.passed = False
            result.total_violations += len(check8.violations)

        # Generate summary
        passed_checks = sum(1 for c in result.checks if c.passed)
        total_checks = len(result.checks)
        result.summary = f"{passed_checks}/{total_checks} checks passed"

        return result

def main():
    parser = argparse.ArgumentParser(
        description='Manage protected regions in generated files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
    extract     Extract regions from a file
    validate    Run specific validation checks
    reinsert    Reinsert regions after regeneration
    check-limits Check region count/size limits
    hash        Calculate hash for content
    full-check  Run all 8 mechanical checks

Examples:
    %(prog)s extract src/service.ts
    %(prog)s validate .task/ --check markers
    %(prog)s full-check .task/
    %(prog)s hash "custom validation code"
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract regions from file')
    extract_parser.add_argument('file', type=Path, help='File to extract regions from')
    extract_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate regions')
    validate_parser.add_argument('path', type=Path, help='File or task path')
    validate_parser.add_argument('--check', choices=[
        'markers', 'allowlist', 'limits', 'ssot', 'hash', 'interface', 'rationale', 'graduation'
    ], help='Specific check to run')

    # Reinsert command
    reinsert_parser = subparsers.add_parser('reinsert', help='Reinsert regions')
    reinsert_parser.add_argument('--regions', type=Path, required=True, help='JSON file with regions')
    reinsert_parser.add_argument('--file', type=Path, required=True, help='File to update')
    reinsert_parser.add_argument('--output', type=Path, help='Output file (default: overwrite)')

    # Check limits command
    limits_parser = subparsers.add_parser('check-limits', help='Check region limits')
    limits_parser.add_argument('path', type=Path, help='Directory to check')

    # Hash command
    hash_parser = subparsers.add_parser('hash', help='Calculate region hash')
    hash_parser.add_argument('content', help='Content to hash')

    # Full check command
    full_parser = subparsers.add_parser('full-check', help='Run all 8 mechanical checks')
    full_parser.add_argument('task_path', type=Path, help='Task directory')
    full_parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    manager = ProtectedRegionManager(verbose=True)

    if args.command == 'extract':
        regions = manager.extract_regions(args.file)

        if args.json:
            output = {
                name: {
                    'content': r.content,
                    'hash': r.hash,
                    'start_line': r.start_line,
                    'end_line': r.end_line,
                    'line_count': r.line_count
                }
                for name, r in regions.items()
            }
            print(json.dumps(output, indent=2))
        else:
            if not regions:
                print("No protected regions found")
            else:
                for name, region in regions.items():
                    print(f"\n=== Region: {name} ===")
                    print(f"Hash: {region.hash}")
                    print(f"Lines: {region.start_line}-{region.end_line} ({region.line_count} lines)")
                    print(f"Content:\n{region.content}")

    elif args.command == 'validate':
        check_map = {
            'markers': manager.check_region_markers,
            'allowlist': manager.check_region_allowlist,
            'limits': manager.check_region_limits,
            'hash': manager.check_hash_integrity,
            'interface': manager.check_interface_alterations,
        }

        if args.check and args.check in check_map:
            result = check_map[args.check](args.path)
            print(f"Check: {result.check_name}")
            print(f"Passed: {result.passed}")
            if result.violations:
                print("Violations:")
                for v in result.violations:
                    print(f"  - {v}")
            if result.info:
                print("Info:")
                for i in result.info:
                    print(f"  - {i}")
            sys.exit(0 if result.passed else 1)
        else:
            # Run all checks
            full_result = manager.run_full_validation(args.path)
            print(f"\nValidation: {'PASSED' if full_result.passed else 'FAILED'}")
            print(f"Summary: {full_result.summary}")
            sys.exit(0 if full_result.passed else 1)

    elif args.command == 'reinsert':
        with open(args.regions, 'r') as f:
            regions_data = json.load(f)

        regions = {
            name: ProtectedRegion(
                name=name,
                content=data['content'],
                hash=data['hash'],
                start_line=data.get('start_line', 0),
                end_line=data.get('end_line', 0),
                line_count=data.get('line_count', 0)
            )
            for name, data in regions_data.items()
        }

        content = args.file.read_text()
        result = manager.reinsert_regions(content, regions)

        output_path = args.output or args.file
        output_path.write_text(result)
        print(f"Regions reinserted into: {output_path}")

    elif args.command == 'check-limits':
        violations = []
        for file_path in args.path.rglob('*'):
            if file_path.is_file() and file_path.suffix in COMMENT_SYNTAX:
                result = manager.check_region_limits(file_path)
                violations.extend(result.violations)

        if violations:
            print("Limit violations:")
            for v in violations:
                print(f"  - {v}")
            sys.exit(1)
        else:
            print("All files within region limits")

    elif args.command == 'hash':
        hash_value = manager.calculate_hash(args.content)
        print(hash_value)

    elif args.command == 'full-check':
        result = manager.run_full_validation(args.task_path)

        if args.json:
            output = {
                'passed': result.passed,
                'total_violations': result.total_violations,
                'summary': result.summary,
                'checks': [
                    {
                        'name': c.check_name,
                        'passed': c.passed,
                        'violations': c.violations,
                        'info': c.info
                    }
                    for c in result.checks
                ]
            }
            print(json.dumps(output, indent=2))
        else:
            print("=" * 60)
            print("PROTECTED REGIONS VALIDATION")
            print("=" * 60)

            for check in result.checks:
                status = "" if check.passed else ""
                print(f"\n{status} {check.check_name}")
                if check.violations:
                    for v in check.violations:
                        print(f"   {v}")
                if check.info:
                    for i in check.info:
                        print(f"   {i}")

            print("\n" + "=" * 60)
            if result.passed:
                print(f" Protected region validation PASSED ({result.summary})")
            else:
                print(f" Protected region validation FAILED")
                print(f"   {result.total_violations} violation(s) found")
            print("=" * 60)

        sys.exit(0 if result.passed else 1)

if __name__ == '__main__':
    main()
