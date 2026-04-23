#!/usr/bin/env python3
"""
Template Compliance Checker - Validates Templates Against the system Standards

Checks templates for required files, correct structure, metadata completeness,
placeholder format, and adherence to the system template conventions.

Usage:
    # Check a specific template directory
    python3 tools/template_compliance_checker.py PLANNING/templates/preview/

    # Check all templates
    python3 tools/template_compliance_checker.py --all

    # Output in JSON format
    python3 tools/template_compliance_checker.py PLANNING/templates/preview/ --json

    # Strict mode (fail on warnings)
    python3 tools/template_compliance_checker.py PLANNING/templates/preview/ --strict

Exit Codes:
    0 - All checks passed
    1 - Compliance errors found
    2 - Error (missing files, invalid structure, etc.)

Referenced in:
    - TEMPLATE_COMPLIANCE_POLICY.md:1570, 1677, 1679

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import yaml
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class ComplianceIssue:
    """Represents a compliance issue"""
    level: str  # 'error', 'warning', 'info'
    code: str   # e.g., 'TC001'
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None

@dataclass
class ComplianceResult:
    """Result of compliance check"""
    template_path: str
    passed: bool
    errors: List[ComplianceIssue] = field(default_factory=list)
    warnings: List[ComplianceIssue] = field(default_factory=list)
    info: List[ComplianceIssue] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_issue(self, issue: ComplianceIssue):
        if issue.level == 'error':
            self.errors.append(issue)
            self.passed = False
        elif issue.level == 'warning':
            self.warnings.append(issue)
        else:
            self.info.append(issue)

class TemplateComplianceChecker:
    """Validates templates against the system standards"""

    # Required files for different template types
    REQUIRED_FILES = {
        'preview': ['preview.json.template', 'preview.md.template'],
        'task': ['task.yaml.template'],
        'work_order': ['work_order.yaml.template'],
        'verdict': ['verdict.yaml.template'],
        'default': []
    }

    # Valid placeholder pattern: {{VARIABLE_NAME}}
    PLACEHOLDER_PATTERN = re.compile(r'\{\{([A-Z][A-Z0-9_]*)\}\}')

    # Invalid placeholder patterns
    INVALID_PLACEHOLDER_PATTERNS = [
        (re.compile(r'\{([A-Z][A-Z0-9_]*)\}'), 'Single braces instead of double'),
        (re.compile(r'\{\{\s+([A-Z][A-Z0-9_]*)\s+\}\}'), 'Spaces inside braces'),
        (re.compile(r'\{\{([a-z][a-z0-9_]*)\}\}'), 'Lowercase variable name'),
        (re.compile(r'\$\{([A-Z][A-Z0-9_]*)\}'), 'Shell-style variable syntax'),
        (re.compile(r'%\{([A-Z][A-Z0-9_]*)\}'), 'Percent-brace syntax'),
    ]

    # Required metadata fields
    REQUIRED_METADATA = ['name', 'version', 'description']

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.results: List[ComplianceResult] = []

    def check_template(self, template_path: Path) -> ComplianceResult:
        """Check a single template directory for compliance"""
        result = ComplianceResult(
            template_path=str(template_path),
            passed=True
        )

        if not template_path.exists():
            result.add_issue(ComplianceIssue(
                level='error',
                code='TC001',
                message=f'Template directory does not exist: {template_path}'
            ))
            return result

        if not template_path.is_dir():
            result.add_issue(ComplianceIssue(
                level='error',
                code='TC002',
                message=f'Path is not a directory: {template_path}'
            ))
            return result

        # Run all checks
        self._check_readme(template_path, result)
        self._check_required_files(template_path, result)
        self._check_yaml_syntax(template_path, result)
        self._check_json_syntax(template_path, result)
        self._check_placeholders(template_path, result)
        self._check_metadata(template_path, result)
        self._check_naming_conventions(template_path, result)

        self.results.append(result)
        return result

    def _check_readme(self, template_path: Path, result: ComplianceResult):
        """Check for README.md documentation"""
        readme = template_path / 'README.md'
        if not readme.exists():
            result.add_issue(ComplianceIssue(
                level='warning',
                code='TC010',
                message='Missing README.md documentation',
                file=str(template_path),
                suggestion='Create README.md explaining template purpose and usage'
            ))
        else:
            # Check README has required sections
            content = readme.read_text()
            required_sections = ['Purpose', 'Usage', 'Variables']
            for section in required_sections:
                if section.lower() not in content.lower():
                    result.add_issue(ComplianceIssue(
                        level='info',
                        code='TC011',
                        message=f'README.md missing recommended section: {section}',
                        file=str(readme),
                        suggestion=f'Add a "{section}" section to README.md'
                    ))

    def _check_required_files(self, template_path: Path, result: ComplianceResult):
        """Check for required files based on template type"""
        template_type = template_path.name

        required = self.REQUIRED_FILES.get(template_type, self.REQUIRED_FILES['default'])

        for req_file in required:
            file_path = template_path / req_file
            if not file_path.exists():
                result.add_issue(ComplianceIssue(
                    level='error',
                    code='TC020',
                    message=f'Missing required file: {req_file}',
                    file=str(template_path),
                    suggestion=f'Create {req_file} in {template_path}'
                ))

    def _check_yaml_syntax(self, template_path: Path, result: ComplianceResult):
        """Validate YAML files syntax"""
        yaml_files = list(template_path.glob('*.yaml')) + list(template_path.glob('*.yml'))

        for yaml_file in yaml_files:
            try:
                content = yaml_file.read_text()
                # Replace placeholders with dummy values for parsing
                test_content = self.PLACEHOLDER_PATTERN.sub('PLACEHOLDER_VALUE', content)
                yaml.safe_load(test_content)
            except yaml.YAMLError as e:
                result.add_issue(ComplianceIssue(
                    level='error',
                    code='TC030',
                    message=f'Invalid YAML syntax: {e}',
                    file=str(yaml_file)
                ))

    def _check_json_syntax(self, template_path: Path, result: ComplianceResult):
        """Validate JSON files syntax"""
        json_files = list(template_path.glob('*.json')) + list(template_path.glob('*.json.template'))

        for json_file in json_files:
            try:
                content = json_file.read_text()
                # Replace placeholders with dummy values for parsing
                test_content = self.PLACEHOLDER_PATTERN.sub('"PLACEHOLDER_VALUE"', content)
                json.loads(test_content)
            except json.JSONDecodeError as e:
                result.add_issue(ComplianceIssue(
                    level='error',
                    code='TC031',
                    message=f'Invalid JSON syntax: {e}',
                    file=str(json_file)
                ))

    def _check_placeholders(self, template_path: Path, result: ComplianceResult):
        """Check placeholder format in all template files"""
        template_files = (
            list(template_path.glob('*.template')) +
            list(template_path.glob('*.md')) +
            list(template_path.glob('*.yaml')) +
            list(template_path.glob('*.yml')) +
            list(template_path.glob('*.json'))
        )

        for template_file in template_files:
            if template_file.name == 'README.md':
                continue

            content = template_file.read_text()
            lines = content.split('\n')

            # Check for invalid placeholder patterns
            for pattern, description in self.INVALID_PLACEHOLDER_PATTERNS:
                for line_num, line in enumerate(lines, 1):
                    matches = pattern.findall(line)
                    for match in matches:
                        result.add_issue(ComplianceIssue(
                            level='warning',
                            code='TC040',
                            message=f'Invalid placeholder format ({description}): {match}',
                            file=str(template_file),
                            line=line_num,
                            suggestion='Use {{VARIABLE_NAME}} format with uppercase letters'
                        ))

            # Find valid placeholders and check naming
            valid_placeholders = self.PLACEHOLDER_PATTERN.findall(content)
            for placeholder in valid_placeholders:
                # Check for reserved/common names
                if placeholder in ['ID', 'NAME', 'TYPE']:
                    result.add_issue(ComplianceIssue(
                        level='info',
                        code='TC041',
                        message=f'Generic placeholder name: {placeholder}',
                        file=str(template_file),
                        suggestion='Consider more descriptive name like TASK_ID, USER_NAME, etc.'
                    ))

    def _check_metadata(self, template_path: Path, result: ComplianceResult):
        """Check for metadata file and required fields"""
        metadata_files = ['metadata.yaml', 'metadata.yml', 'template.yaml', 'manifest.yaml']

        metadata_found = False
        for meta_file in metadata_files:
            meta_path = template_path / meta_file
            if meta_path.exists():
                metadata_found = True
                try:
                    with open(meta_path, 'r') as f:
                        metadata = yaml.safe_load(f)

                    if metadata:
                        for field in self.REQUIRED_METADATA:
                            if field not in metadata:
                                result.add_issue(ComplianceIssue(
                                    level='warning',
                                    code='TC050',
                                    message=f'Missing metadata field: {field}',
                                    file=str(meta_path),
                                    suggestion=f'Add "{field}" field to metadata'
                                ))

                        # Check version format
                        version = metadata.get('version')
                        if version and not re.match(r'^\d+\.\d+(\.\d+)?$', str(version)):
                            result.add_issue(ComplianceIssue(
                                level='warning',
                                code='TC051',
                                message=f'Non-standard version format: {version}',
                                file=str(meta_path),
                                suggestion='Use semantic versioning (e.g., 1.0.0)'
                            ))
                except yaml.YAMLError as e:
                    result.add_issue(ComplianceIssue(
                        level='error',
                        code='TC052',
                        message=f'Invalid metadata YAML: {e}',
                        file=str(meta_path)
                    ))
                break

        if not metadata_found:
            result.add_issue(ComplianceIssue(
                level='info',
                code='TC053',
                message='No metadata file found',
                file=str(template_path),
                suggestion='Consider adding metadata.yaml with template information'
            ))

    def _check_naming_conventions(self, template_path: Path, result: ComplianceResult):
        """Check file naming conventions"""
        for file_path in template_path.iterdir():
            if file_path.is_file():
                name = file_path.name

                # Check for spaces in filename
                if ' ' in name:
                    result.add_issue(ComplianceIssue(
                        level='error',
                        code='TC060',
                        message=f'Filename contains spaces: {name}',
                        file=str(file_path),
                        suggestion='Use underscores or hyphens instead of spaces'
                    ))

                # Check for uppercase in extension
                if file_path.suffix and file_path.suffix != file_path.suffix.lower():
                    result.add_issue(ComplianceIssue(
                        level='warning',
                        code='TC061',
                        message=f'Uppercase file extension: {file_path.suffix}',
                        file=str(file_path),
                        suggestion='Use lowercase file extensions'
                    ))

    def check_all_templates(self, root_path: Path) -> List[ComplianceResult]:
        """Check all templates under a root path"""
        template_dirs = [
            root_path / 'PLANNING' / 'templates',
            root_path / 'templates',
            root_path / 'archives' / 'golden' / 'templates',
        ]

        for template_root in template_dirs:
            if template_root.exists():
                for subdir in template_root.iterdir():
                    if subdir.is_dir() and not subdir.name.startswith('.'):
                        self.check_template(subdir)

        return self.results

    def check_stage_0_5_gate(self, template_path: Path, target_stage: int = 1) -> Tuple[bool, str]:
        """
        Stage 0.5 Gate: Validates templates before use in Stage 1+

        Per README.md:498 - Templates cannot be used in Stage 1+ unless
        compliance PASSED. This gate blocks template usage if:
        - Template has any compliance errors
        - Template lacks required metadata
        - Template has unresolved placeholder issues

        Args:
            template_path: Path to the template directory
            target_stage: Target stage (1+) - default is Stage 1

        Returns:
            Tuple of (passed: bool, message: str)
        """
        if target_stage < 1:
            return True, f"Stage 0.5 gate not required for Stage {target_stage}"

        # Run compliance check
        result = self.check_template(template_path)

        # Gate conditions (J-43: Stage 0.5 gate enforcement)
        if result.errors:
            error_codes = [e.code for e in result.errors]
            return False, (
                f"Stage 0.5 GATE BLOCKED: Template {template_path.name} has "
                f"{len(result.errors)} compliance error(s): {', '.join(error_codes)}. "
                f"Templates cannot be used in Stage {target_stage}+ until all errors are resolved."
            )

        # Check for critical warnings that should block stage 1+
        critical_warning_codes = ['TC040', 'TC050', 'TC051']  # Placeholder and metadata issues
        critical_warnings = [w for w in result.warnings if w.code in critical_warning_codes]

        if critical_warnings and self.strict:
            warning_codes = [w.code for w in critical_warnings]
            return False, (
                f"Stage 0.5 GATE BLOCKED (strict mode): Template {template_path.name} has "
                f"{len(critical_warnings)} critical warning(s): {', '.join(warning_codes)}. "
                f"Resolve warnings or disable strict mode."
            )

        # Check for compliance stamp/record
        compliance_record = template_path / '.compliance_passed'
        if compliance_record.exists():
            try:
                record_data = yaml.safe_load(compliance_record.read_text())
                last_check = record_data.get('checked_at', 'unknown')
                return True, f"Stage 0.5 GATE PASSED: Template compliant (last check: {last_check})"
            except:
                pass

        # Write compliance record on success
        try:
            compliance_data = {
                'template': template_path.name,
                'passed': True,
                'checked_at': datetime.now().isoformat(),
                'errors': 0,
                'warnings': len(result.warnings),
                'gate_version': '0.5'
            }
            compliance_record.write_text(yaml.dump(compliance_data, default_flow_style=False))
        except:
            pass  # Non-critical if we can't write

        return True, f"Stage 0.5 GATE PASSED: Template {template_path.name} is compliant for Stage {target_stage}+"

    def enforce_stage_0_5_gate(self, template_path: Path, target_stage: int = 1) -> None:
        """
        Enforce Stage 0.5 gate - exits with error if gate fails.

        This is the blocking enforcement method for CI/pre-commit use.
        """
        passed, message = self.check_stage_0_5_gate(template_path, target_stage)
        print(message)
        if not passed:
            sys.exit(1)

    def generate_report(self, format: str = 'text') -> str:
        """Generate compliance report"""
        if format == 'json':
            return json.dumps([asdict(r) for r in self.results], indent=2)

        lines = ['=' * 60, 'TEMPLATE COMPLIANCE REPORT', '=' * 60, '']

        total_errors = 0
        total_warnings = 0

        for result in self.results:
            lines.append(f"Template: {result.template_path}")
            lines.append(f"  Status: {'PASSED' if result.passed else 'FAILED'}")
            lines.append(f"  Errors: {len(result.errors)}")
            lines.append(f"  Warnings: {len(result.warnings)}")

            total_errors += len(result.errors)
            total_warnings += len(result.warnings)

            if result.errors:
                lines.append('  Errors:')
                for issue in result.errors:
                    lines.append(f"    [{issue.code}] {issue.message}")
                    if issue.file:
                        lines.append(f"           File: {issue.file}")
                    if issue.suggestion:
                        lines.append(f"           Fix: {issue.suggestion}")

            if result.warnings:
                lines.append('  Warnings:')
                for issue in result.warnings:
                    lines.append(f"    [{issue.code}] {issue.message}")
                    if issue.suggestion:
                        lines.append(f"           Fix: {issue.suggestion}")

            lines.append('')

        lines.append('=' * 60)
        lines.append(f"SUMMARY: {len(self.results)} templates checked")
        lines.append(f"  Total Errors: {total_errors}")
        lines.append(f"  Total Warnings: {total_warnings}")

        all_passed = all(r.passed for r in self.results)
        if self.strict:
            all_passed = all_passed and total_warnings == 0

        lines.append(f"  Overall: {'PASSED' if all_passed else 'FAILED'}")
        lines.append('=' * 60)

        return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(
        description='Validate templates against the system compliance standards',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s PLANNING/templates/preview/
    %(prog)s --all
    %(prog)s PLANNING/templates/preview/ --json
    %(prog)s PLANNING/templates/preview/ --strict
        """
    )

    parser.add_argument('template_path', type=Path, nargs='?',
                        help='Path to template directory')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Check all templates in repository')
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')
    parser.add_argument('--strict', '-s', action='store_true',
                        help='Treat warnings as errors')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Only output on failure')
    parser.add_argument('--stage-gate', type=int, metavar='N',
                        help='Enforce Stage 0.5 gate for Stage N (blocks if template not compliant)')

    args = parser.parse_args()

    if not args.template_path and not args.all:
        parser.error('Either template_path or --all is required')

    checker = TemplateComplianceChecker(strict=args.strict)

    # Stage 0.5 gate mode (J-43)
    if args.stage_gate is not None:
        if not args.template_path:
            parser.error('--stage-gate requires template_path')
        checker.enforce_stage_0_5_gate(args.template_path, args.stage_gate)
        sys.exit(0)

    if args.all:
        # Find repository root
        repo_root = Path.cwd()
        while repo_root != repo_root.parent:
            if (repo_root / '.git').exists():
                break
            repo_root = repo_root.parent
        checker.check_all_templates(repo_root)
    else:
        checker.check_template(args.template_path)

    # Generate report
    format = 'json' if args.json else 'text'
    report = checker.generate_report(format)

    # Determine exit status
    all_passed = all(r.passed for r in checker.results)
    if args.strict:
        total_warnings = sum(len(r.warnings) for r in checker.results)
        all_passed = all_passed and total_warnings == 0

    if not args.quiet or not all_passed:
        print(report)

    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()
