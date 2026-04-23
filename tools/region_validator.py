#!/usr/bin/env python3
"""
Region Validator - Protected Region Validation Tool
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Template Infrastructure

Validates protected regions in generated files to ensure:
- Region markers are properly paired
- Region content is preserved during regeneration
- Region boundaries don't overlap
- Region naming conventions are followed
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

class RegionType(Enum):
    """Types of protected regions."""
    PROTECTED = "protected"  # User code that must be preserved
    GENERATED = "generated"  # Auto-generated, can be overwritten
    LOCKED = "locked"  # Locked by PM, requires approval to change
    DEPRECATED = "deprecated"  # Marked for removal

class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class Region:
    """Represents a protected region in a file."""
    name: str
    region_type: RegionType
    start_line: int
    end_line: int
    content: str
    content_hash: str
    file_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationIssue:
    """A validation issue found in a file."""
    file_path: str
    line_number: int
    severity: ValidationSeverity
    code: str
    message: str
    region_name: Optional[str] = None

@dataclass
class ValidationResult:
    """Result of validating a file or directory."""
    valid: bool
    files_checked: int
    regions_found: int
    issues: List[ValidationIssue] = field(default_factory=list)
    regions: List[Region] = field(default_factory=list)

    def add_issue(self, issue: ValidationIssue):
        """Add a validation issue."""
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.valid = False

class RegionValidator:
    """Validates protected regions in files."""

    # Region marker patterns for different file types
    MARKERS = {
        'python': {
            'start': re.compile(r'#\s*REGION:(\w+):START(?:\s+type=(\w+))?'),
            'end': re.compile(r'#\s*REGION:(\w+):END'),
        },
        'javascript': {
            'start': re.compile(r'//\s*REGION:(\w+):START(?:\s+type=(\w+))?'),
            'end': re.compile(r'//\s*REGION:(\w+):END'),
        },
        'html': {
            'start': re.compile(r'<!--\s*REGION:(\w+):START(?:\s+type=(\w+))?\s*-->'),
            'end': re.compile(r'<!--\s*REGION:(\w+):END\s*-->'),
        },
        'yaml': {
            'start': re.compile(r'#\s*REGION:(\w+):START(?:\s+type=(\w+))?'),
            'end': re.compile(r'#\s*REGION:(\w+):END'),
        },
        'shell': {
            'start': re.compile(r'#\s*REGION:(\w+):START(?:\s+type=(\w+))?'),
            'end': re.compile(r'#\s*REGION:(\w+):END'),
        },
    }

    # File extension to marker type mapping
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'javascript',
        '.jsx': 'javascript',
        '.tsx': 'javascript',
        '.html': 'html',
        '.htm': 'html',
        '.xml': 'html',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.sh': 'shell',
        '.bash': 'shell',
    }

    def __init__(self, strict: bool = False):
        """
        Initialize validator.

        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict

    def validate_file(self, file_path: str) -> ValidationResult:
        """
        Validate a single file for region correctness.

        Args:
            file_path: Path to file to validate

        Returns:
            ValidationResult
        """
        result = ValidationResult(valid=True, files_checked=1, regions_found=0)

        if not os.path.exists(file_path):
            result.add_issue(ValidationIssue(
                file_path=file_path,
                line_number=0,
                severity=ValidationSeverity.ERROR,
                code="FILE_NOT_FOUND",
                message=f"File not found: {file_path}"
            ))
            return result

        # Determine file type
        ext = Path(file_path).suffix.lower()
        marker_type = self.EXTENSION_MAP.get(ext, 'python')
        markers = self.MARKERS.get(marker_type, self.MARKERS['python'])

        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
        except Exception as e:
            result.add_issue(ValidationIssue(
                file_path=file_path,
                line_number=0,
                severity=ValidationSeverity.ERROR,
                code="READ_ERROR",
                message=f"Failed to read file: {e}"
            ))
            return result

        # Track open regions
        open_regions: Dict[str, Tuple[int, Optional[str]]] = {}
        found_regions: List[Region] = []

        for line_num, line in enumerate(lines, 1):
            # Check for start marker
            start_match = markers['start'].search(line)
            if start_match:
                region_name = start_match.group(1)
                region_type_str = start_match.group(2) if start_match.lastindex >= 2 else None

                # Check for duplicate open region
                if region_name in open_regions:
                    result.add_issue(ValidationIssue(
                        file_path=file_path,
                        line_number=line_num,
                        severity=ValidationSeverity.ERROR,
                        code="DUPLICATE_REGION_START",
                        message=f"Region '{region_name}' started but previous instance not closed",
                        region_name=region_name
                    ))
                else:
                    open_regions[region_name] = (line_num, region_type_str)

            # Check for end marker
            end_match = markers['end'].search(line)
            if end_match:
                region_name = end_match.group(1)

                if region_name not in open_regions:
                    result.add_issue(ValidationIssue(
                        file_path=file_path,
                        line_number=line_num,
                        severity=ValidationSeverity.ERROR,
                        code="UNMATCHED_REGION_END",
                        message=f"Region '{region_name}' end marker without matching start",
                        region_name=region_name
                    ))
                else:
                    start_line, type_str = open_regions.pop(region_name)

                    # Extract region content
                    region_content = '\n'.join(lines[start_line:line_num-1])
                    content_hash = hashlib.sha256(region_content.encode()).hexdigest()[:16]

                    # Determine region type
                    try:
                        region_type = RegionType(type_str) if type_str else RegionType.PROTECTED
                    except ValueError:
                        region_type = RegionType.PROTECTED
                        result.add_issue(ValidationIssue(
                            file_path=file_path,
                            line_number=start_line,
                            severity=ValidationSeverity.WARNING,
                            code="INVALID_REGION_TYPE",
                            message=f"Unknown region type '{type_str}', defaulting to 'protected'",
                            region_name=region_name
                        ))

                    region = Region(
                        name=region_name,
                        region_type=region_type,
                        start_line=start_line,
                        end_line=line_num,
                        content=region_content,
                        content_hash=content_hash,
                        file_path=file_path
                    )
                    found_regions.append(region)
                    result.regions_found += 1

        # Check for unclosed regions
        for region_name, (start_line, _) in open_regions.items():
            result.add_issue(ValidationIssue(
                file_path=file_path,
                line_number=start_line,
                severity=ValidationSeverity.ERROR,
                code="UNCLOSED_REGION",
                message=f"Region '{region_name}' not closed",
                region_name=region_name
            ))

        # Validate region naming conventions
        for region in found_regions:
            if not re.match(r'^[a-z][a-z0-9_]*$', region.name):
                result.add_issue(ValidationIssue(
                    file_path=file_path,
                    line_number=region.start_line,
                    severity=ValidationSeverity.WARNING,
                    code="INVALID_REGION_NAME",
                    message=f"Region name '{region.name}' should be lowercase with underscores",
                    region_name=region.name
                ))

            # Check for empty regions
            if not region.content.strip():
                result.add_issue(ValidationIssue(
                    file_path=file_path,
                    line_number=region.start_line,
                    severity=ValidationSeverity.WARNING,
                    code="EMPTY_REGION",
                    message=f"Region '{region.name}' is empty",
                    region_name=region.name
                ))

        result.regions = found_regions

        # In strict mode, warnings become errors
        if self.strict:
            for issue in result.issues:
                if issue.severity == ValidationSeverity.WARNING:
                    issue.severity = ValidationSeverity.ERROR
                    result.valid = False

        return result

    def validate_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
        recursive: bool = True
    ) -> ValidationResult:
        """
        Validate all files in a directory.

        Args:
            directory: Directory path
            extensions: File extensions to check (default: all supported)
            recursive: Whether to search recursively

        Returns:
            Combined ValidationResult
        """
        if extensions is None:
            extensions = list(self.EXTENSION_MAP.keys())

        result = ValidationResult(valid=True, files_checked=0, regions_found=0)

        path = Path(directory)
        if not path.exists():
            result.add_issue(ValidationIssue(
                file_path=directory,
                line_number=0,
                severity=ValidationSeverity.ERROR,
                code="DIRECTORY_NOT_FOUND",
                message=f"Directory not found: {directory}"
            ))
            return result

        # Find files
        pattern = '**/*' if recursive else '*'
        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                file_result = self.validate_file(str(file_path))
                result.files_checked += file_result.files_checked
                result.regions_found += file_result.regions_found
                result.issues.extend(file_result.issues)
                result.regions.extend(file_result.regions)
                if not file_result.valid:
                    result.valid = False

        return result

    def compare_regions(
        self,
        old_file: str,
        new_file: str
    ) -> List[ValidationIssue]:
        """
        Compare regions between two versions of a file.

        Args:
            old_file: Path to old version
            new_file: Path to new version

        Returns:
            List of issues found
        """
        issues = []

        old_result = self.validate_file(old_file)
        new_result = self.validate_file(new_file)

        old_regions = {r.name: r for r in old_result.regions}
        new_regions = {r.name: r for r in new_result.regions}

        # Check for removed protected regions
        for name, region in old_regions.items():
            if region.region_type == RegionType.PROTECTED and name not in new_regions:
                issues.append(ValidationIssue(
                    file_path=new_file,
                    line_number=0,
                    severity=ValidationSeverity.ERROR,
                    code="PROTECTED_REGION_REMOVED",
                    message=f"Protected region '{name}' was removed",
                    region_name=name
                ))

        # Check for modified protected regions
        for name, new_region in new_regions.items():
            if name in old_regions:
                old_region = old_regions[name]
                if (old_region.region_type == RegionType.PROTECTED and
                    old_region.content_hash != new_region.content_hash):
                    issues.append(ValidationIssue(
                        file_path=new_file,
                        line_number=new_region.start_line,
                        severity=ValidationSeverity.WARNING,
                        code="PROTECTED_REGION_MODIFIED",
                        message=f"Protected region '{name}' content changed",
                        region_name=name
                    ))

        return issues

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate protected regions in files"
    )
    parser.add_argument("path", help="File or directory to validate")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Recursively validate directories")
    parser.add_argument("-s", "--strict", action="store_true",
                        help="Treat warnings as errors")
    parser.add_argument("-e", "--extensions", nargs="+",
                        help="File extensions to check")
    parser.add_argument("--compare", help="Compare with another file/version")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    validator = RegionValidator(strict=args.strict)

    if args.compare:
        issues = validator.compare_regions(args.path, args.compare)
        if args.json:
            print(json.dumps([{
                "file": i.file_path,
                "line": i.line_number,
                "severity": i.severity.value,
                "code": i.code,
                "message": i.message
            } for i in issues], indent=2))
        else:
            for issue in issues:
                print(f"{issue.severity.value.upper()}: {issue.message}")
        sys.exit(1 if issues else 0)

    if os.path.isdir(args.path):
        result = validator.validate_directory(
            args.path,
            extensions=args.extensions,
            recursive=args.recursive
        )
    else:
        result = validator.validate_file(args.path)

    if args.json:
        output = {
            "valid": result.valid,
            "files_checked": result.files_checked,
            "regions_found": result.regions_found,
            "issues": [{
                "file": i.file_path,
                "line": i.line_number,
                "severity": i.severity.value,
                "code": i.code,
                "message": i.message,
                "region": i.region_name
            } for i in result.issues],
            "regions": [{
                "name": r.name,
                "type": r.region_type.value,
                "file": r.file_path,
                "start": r.start_line,
                "end": r.end_line,
                "hash": r.content_hash
            } for r in result.regions] if args.verbose else []
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Files checked: {result.files_checked}")
        print(f"Regions found: {result.regions_found}")
        print(f"Valid: {'Yes' if result.valid else 'No'}")

        if result.issues:
            print(f"\nIssues ({len(result.issues)}):")
            for issue in result.issues:
                symbol = "!" if issue.severity == ValidationSeverity.ERROR else "?"
                print(f"  [{symbol}] {issue.file_path}:{issue.line_number} - {issue.message}")

        if args.verbose and result.regions:
            print(f"\nRegions:")
            for region in result.regions:
                print(f"  - {region.name} ({region.region_type.value}): "
                      f"lines {region.start_line}-{region.end_line}")

    sys.exit(0 if result.valid else 1)

if __name__ == "__main__":
    main()
