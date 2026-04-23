#!/usr/bin/env python3
"""
Template Family Validator for the system.

Validates template metadata files for template family compliance.
Ensures templates declare valid family membership and follow family-specific rules.

See: PLANNING/TEMPLATE_FAMILIES_POLICY.md Step 7 (CI gates)

Usage:
    python3 tools/family_validator.py --verify <template_metadata.yaml>
    python3 tools/family_validator.py --verify-all
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# Canonical template families as defined in TEMPLATE_FAMILIES_POLICY.md
CANONICAL_FAMILIES = {
    'code',     # Source code templates (functions, classes, modules)
    'config',   # Configuration file templates (YAML, JSON, env files)
    'data',     # Data structure templates (schemas, fixtures)
    'infra',    # Infrastructure templates (Docker, CI, deployment)
    'docs',     # Documentation templates (README, API docs)
    'test',     # Test templates (unit tests, integration tests)
    'schema',   # Schema definition templates (JSON Schema, YAML Schema)
}

# Family-specific validation rules
FAMILY_RULES = {
    'code': {
        'required_fields': ['language', 'output_extension'],
        'forbidden_patterns': [],
        'description': 'Source code generation templates'
    },
    'config': {
        'required_fields': ['config_format'],
        'forbidden_patterns': ['def ', 'function ', 'class '],  # No logic in config
        'description': 'Configuration file templates'
    },
    'data': {
        'required_fields': [],
        'forbidden_patterns': [],
        'description': 'Data structure templates'
    },
    'infra': {
        'required_fields': [],
        'forbidden_patterns': [],
        'description': 'Infrastructure-as-code templates'
    },
    'docs': {
        'required_fields': [],
        'forbidden_patterns': [],
        'description': 'Documentation templates'
    },
    'test': {
        'required_fields': ['test_framework'],
        'forbidden_patterns': [],
        'description': 'Test suite templates'
    },
    'schema': {
        'required_fields': ['schema_type'],
        'forbidden_patterns': [],
        'description': 'Schema definition templates'
    },
}

class ValidationResult:
    """Result of a validation check."""

    def __init__(self, passed: bool, message: str, details: Optional[List[str]] = None):
        self.passed = passed
        self.message = message
        self.details = details or []

    def __bool__(self):
        return self.passed

    def __str__(self):
        status = 'PASS' if self.passed else 'FAIL'
        result = f'[{status}] {self.message}'
        if self.details:
            for detail in self.details:
                result += f'\n       - {detail}'
        return result

def load_template_metadata(path: Path) -> Tuple[Optional[Dict], Optional[str]]:
    """Load and parse template metadata file.

    Args:
        path: Path to template_metadata.yaml

    Returns:
        Tuple of (metadata dict, error message if any)
    """
    if not path.exists():
        return None, f'File not found: {path}'

    try:
        content = path.read_text(encoding='utf-8')
        metadata = yaml.safe_load(content)
        if metadata is None:
            return None, f'Empty or invalid YAML: {path}'
        return metadata, None
    except yaml.YAMLError as e:
        return None, f'YAML parse error: {e}'
    except Exception as e:
        return None, f'Error reading file: {e}'

def validate_family_field(metadata: Dict) -> ValidationResult:
    """Check that template_family field exists and is valid.

    Args:
        metadata: Template metadata dictionary

    Returns:
        ValidationResult with pass/fail status
    """
    if 'template_family' not in metadata:
        return ValidationResult(
            False,
            'Missing template_family field',
            ['Templates must declare a template_family from: ' + ', '.join(sorted(CANONICAL_FAMILIES))]
        )

    family = metadata['template_family']

    if not isinstance(family, str):
        return ValidationResult(
            False,
            f'template_family must be a string, got {type(family).__name__}',
            []
        )

    if family not in CANONICAL_FAMILIES:
        return ValidationResult(
            False,
            f"Invalid template family: '{family}'",
            [f'Valid families are: {", ".join(sorted(CANONICAL_FAMILIES))}']
        )

    return ValidationResult(True, f"Valid template family: '{family}'")

def validate_family_rules(metadata: Dict, template_content: Optional[str] = None) -> ValidationResult:
    """Validate family-specific rules.

    Args:
        metadata: Template metadata dictionary
        template_content: Optional template file content for pattern checking

    Returns:
        ValidationResult with pass/fail status
    """
    family = metadata.get('template_family')
    if not family or family not in FAMILY_RULES:
        return ValidationResult(True, 'No family rules to check')

    rules = FAMILY_RULES[family]
    issues = []

    # Check required fields
    for field in rules.get('required_fields', []):
        if field not in metadata:
            issues.append(f"Missing required field for '{family}' family: {field}")

    # Check forbidden patterns in template content
    if template_content:
        for pattern in rules.get('forbidden_patterns', []):
            if pattern in template_content:
                issues.append(f"Forbidden pattern for '{family}' family: '{pattern}'")

    if issues:
        return ValidationResult(
            False,
            f"Family-specific rule violations for '{family}'",
            issues
        )

    return ValidationResult(True, f"Family rules validated for '{family}'")

def validate_template_metadata(path: Path, verbose: bool = False) -> Tuple[bool, List[str]]:
    """Validate a single template metadata file.

    Args:
        path: Path to template_metadata.yaml
        verbose: Whether to print detailed output

    Returns:
        Tuple of (passed, list of messages)
    """
    messages = []
    all_passed = True

    # Load metadata
    metadata, error = load_template_metadata(path)
    if error:
        return False, [f'ERROR: {error}']

    # Run validations
    checks = [
        validate_family_field(metadata),
        validate_family_rules(metadata),
    ]

    for result in checks:
        messages.append(str(result))
        if not result.passed:
            all_passed = False

    return all_passed, messages

def find_template_metadata_files(base_path: Path) -> List[Path]:
    """Find all template_metadata.yaml files in a directory tree.

    Args:
        base_path: Base directory to search

    Returns:
        List of paths to template_metadata.yaml files
    """
    return list(base_path.rglob('template_metadata.yaml'))

def main():
    """CLI entry point for family_validator tool."""
    parser = argparse.ArgumentParser(
        description='Validate template family compliance',
        epilog='See PLANNING/TEMPLATE_FAMILIES_POLICY.md for details'
    )
    parser.add_argument(
        '--verify',
        type=Path,
        help='Verify a single template_metadata.yaml file'
    )
    parser.add_argument(
        '--verify-all',
        action='store_true',
        help='Verify all template_metadata.yaml files in archives/golden/templates/'
    )
    parser.add_argument(
        '--base-path',
        type=Path,
        default=Path('archives/golden/templates'),
        help='Base path for --verify-all (default: archives/golden/templates)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Only output on failure'
    )
    parser.add_argument(
        '--list-families',
        action='store_true',
        help='List all valid template families and exit'
    )

    args = parser.parse_args()

    if args.list_families:
        print('Valid Template Families:')
        print('-' * 40)
        for family in sorted(CANONICAL_FAMILIES):
            rules = FAMILY_RULES.get(family, {})
            desc = rules.get('description', 'No description')
            print(f'  {family:12} - {desc}')
        return 0

    if not args.verify and not args.verify_all:
        parser.print_help()
        return 1

    exit_code = 0
    total = 0
    passed = 0

    if args.verify:
        # Single file validation
        files = [args.verify]
    else:
        # Find all template metadata files
        files = find_template_metadata_files(args.base_path)
        if not files:
            if not args.quiet:
                print(f'No template_metadata.yaml files found in {args.base_path}')
            return 0

    for file_path in files:
        total += 1
        success, messages = validate_template_metadata(file_path, args.verbose)

        if success:
            passed += 1
            if not args.quiet:
                print(f'PASS: {file_path}')
                if args.verbose:
                    for msg in messages:
                        print(f'  {msg}')
        else:
            exit_code = 1
            print(f'FAIL: {file_path}')
            for msg in messages:
                print(f'  {msg}')

    if total > 1 and not args.quiet:
        print()
        print(f'Summary: {passed}/{total} templates passed validation')

    return exit_code

if __name__ == '__main__':
    sys.exit(main())
