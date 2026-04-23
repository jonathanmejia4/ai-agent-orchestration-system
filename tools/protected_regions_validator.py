#!/usr/bin/env python3
"""
Protected Regions Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Stage Gate Validator

Validates that protected regions in generated files are properly defined,
intact, and haven't been corrupted during regeneration.

Usage:
    python tools/protected_regions_validator.py <file_path>
    python tools/protected_regions_validator.py --check-directory <dir>
    python tools/protected_regions_validator.py --verify-hashes
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import yaml

@dataclass
class ProtectedRegion:
    """Represents a protected region in a file."""
    name: str
    start_line: int
    end_line: int
    content_hash: str
    content: str
    valid: bool
    issues: List[str]

@dataclass
class FileValidationResult:
    """Result of validating a single file."""
    file: str
    status: str  # valid, warning, error, no_regions
    regions: List[ProtectedRegion]
    issues: List[str]
    passed: bool

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    total_files: int
    total_regions: int
    valid_files: int
    files_with_issues: int
    results: List[FileValidationResult]
    passed: bool

class ProtectedRegionsValidator:
    """Validates protected regions in files."""

    # Region marker patterns
    PATTERNS = {
        # Standard format: # PROTECTED-REGION:name
        'start': re.compile(
            r'[#/\-]+\s*PROTECTED[-_]REGION[-_]?START\s*:\s*(\w+)',
            re.IGNORECASE
        ),
        'end': re.compile(
            r'[#/\-]+\s*PROTECTED[-_]REGION[-_]?END\s*:\s*(\w+)',
            re.IGNORECASE
        ),
        # Alternative format: <!-- PROTECTED:name -->
        'html_start': re.compile(
            r'<!--\s*PROTECTED[-_]?START\s*:\s*(\w+)\s*-->',
            re.IGNORECASE
        ),
        'html_end': re.compile(
            r'<!--\s*PROTECTED[-_]?END\s*:\s*(\w+)\s*-->',
            re.IGNORECASE
        ),
        # Hash format: # PROTECTED-REGION:name:hash=abc123
        'hash': re.compile(r'hash\s*=\s*([a-fA-F0-9]{8,64})', re.IGNORECASE),
    }

    # File extensions that support protected regions
    SUPPORTED_EXTENSIONS = {
        '.py', '.js', '.ts', '.tsx', '.jsx',
        '.yaml', '.yml', '.json',
        '.md', '.rst', '.txt',
        '.html', '.css', '.scss',
        '.sh', '.bash',
        '.go', '.rs', '.java',
    }

    def __init__(self, hash_store_path: Path = None):
        self.hash_store_path = hash_store_path or Path(".task/regions/hashes.yaml")
        self.hash_store = self._load_hash_store()

    def _load_hash_store(self) -> Dict[str, Dict[str, str]]:
        """Load stored region hashes."""
        if not self.hash_store_path.exists():
            return {}

        try:
            with open(self.hash_store_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _save_hash_store(self):
        """Save region hashes."""
        self.hash_store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.hash_store_path, 'w') as f:
            yaml.dump(self.hash_store, f, default_flow_style=False)

    def validate_file(self, file_path: Path) -> FileValidationResult:
        """Validate protected regions in a file."""
        file_name = str(file_path)
        regions: List[ProtectedRegion] = []
        issues: List[str] = []

        if not file_path.exists():
            return FileValidationResult(
                file=file_name,
                status="error",
                regions=[],
                issues=[f"File not found: {file_path}"],
                passed=False
            )

        if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
            return FileValidationResult(
                file=file_name,
                status="no_regions",
                regions=[],
                issues=[f"Unsupported file type: {file_path.suffix}"],
                passed=True
            )

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            return FileValidationResult(
                file=file_name,
                status="error",
                regions=[],
                issues=[f"Error reading file: {e}"],
                passed=False
            )

        # Find all protected regions
        regions = self._find_regions(content, lines, file_name)

        if not regions:
            return FileValidationResult(
                file=file_name,
                status="no_regions",
                regions=[],
                issues=[],
                passed=True
            )

        # Validate each region
        for region in regions:
            issues.extend(region.issues)

        # Check for overlapping regions
        overlap_issues = self._check_overlaps(regions)
        issues.extend(overlap_issues)

        # Verify hashes if stored
        hash_issues = self._verify_hashes(file_name, regions)
        issues.extend(hash_issues)

        # Determine status
        if any(not r.valid for r in regions) or issues:
            status = "error" if any("corrupt" in i.lower() or "missing" in i.lower() for i in issues) else "warning"
            passed = status != "error"
        else:
            status = "valid"
            passed = True

        return FileValidationResult(
            file=file_name,
            status=status,
            regions=regions,
            issues=issues,
            passed=passed
        )

    def _find_regions(
        self,
        content: str,
        lines: List[str],
        file_name: str
    ) -> List[ProtectedRegion]:
        """Find all protected regions in content."""
        regions = []
        open_regions: Dict[str, int] = {}

        for i, line in enumerate(lines):
            line_num = i + 1

            # Check for region start
            for pattern_name in ['start', 'html_start']:
                match = self.PATTERNS[pattern_name].search(line)
                if match:
                    region_name = match.group(1)
                    if region_name in open_regions:
                        # Nested region with same name
                        regions.append(ProtectedRegion(
                            name=region_name,
                            start_line=line_num,
                            end_line=-1,
                            content_hash="",
                            content="",
                            valid=False,
                            issues=[f"Nested region with same name: {region_name} at line {line_num}"]
                        ))
                    else:
                        open_regions[region_name] = line_num

            # Check for region end
            for pattern_name in ['end', 'html_end']:
                match = self.PATTERNS[pattern_name].search(line)
                if match:
                    region_name = match.group(1)
                    if region_name in open_regions:
                        start_line = open_regions.pop(region_name)

                        # Extract region content
                        region_lines = lines[start_line:i]
                        region_content = '\n'.join(region_lines)
                        content_hash = self._compute_hash(region_content)

                        regions.append(ProtectedRegion(
                            name=region_name,
                            start_line=start_line,
                            end_line=line_num,
                            content_hash=content_hash,
                            content=region_content[:500],  # Truncate for storage
                            valid=True,
                            issues=[]
                        ))
                    else:
                        # End without start
                        regions.append(ProtectedRegion(
                            name=region_name,
                            start_line=-1,
                            end_line=line_num,
                            content_hash="",
                            content="",
                            valid=False,
                            issues=[f"Region end without start: {region_name} at line {line_num}"]
                        ))

        # Check for unclosed regions
        for region_name, start_line in open_regions.items():
            regions.append(ProtectedRegion(
                name=region_name,
                start_line=start_line,
                end_line=-1,
                content_hash="",
                content="",
                valid=False,
                issues=[f"Unclosed region: {region_name} starting at line {start_line}"]
            ))

        return regions

    def _compute_hash(self, content: str) -> str:
        """Compute hash of region content."""
        # Normalize content before hashing
        normalized = content.strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _check_overlaps(self, regions: List[ProtectedRegion]) -> List[str]:
        """Check for overlapping regions."""
        issues = []
        valid_regions = [r for r in regions if r.start_line > 0 and r.end_line > 0]

        for i, r1 in enumerate(valid_regions):
            for r2 in valid_regions[i+1:]:
                # Check for overlap
                if (r1.start_line < r2.end_line and r1.end_line > r2.start_line):
                    issues.append(
                        f"Overlapping regions: {r1.name} ({r1.start_line}-{r1.end_line}) "
                        f"and {r2.name} ({r2.start_line}-{r2.end_line})"
                    )

        return issues

    def _verify_hashes(
        self,
        file_name: str,
        regions: List[ProtectedRegion]
    ) -> List[str]:
        """Verify region hashes against stored values."""
        issues = []
        stored = self.hash_store.get(file_name, {})

        for region in regions:
            if not region.valid:
                continue

            stored_hash = stored.get(region.name)
            if stored_hash and stored_hash != region.content_hash:
                issues.append(
                    f"Region content changed: {region.name} "
                    f"(expected {stored_hash[:8]}..., got {region.content_hash[:8]}...)"
                )

        return issues

    def update_hashes(self, file_path: Path) -> None:
        """Update stored hashes for a file."""
        result = self.validate_file(file_path)
        file_name = str(file_path)

        if file_name not in self.hash_store:
            self.hash_store[file_name] = {}

        for region in result.regions:
            if region.valid:
                self.hash_store[file_name][region.name] = region.content_hash

        self._save_hash_store()

    def validate_directory(self, dir_path: Path) -> ValidationReport:
        """Validate all files in a directory."""
        results = []

        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in self.SUPPORTED_EXTENSIONS:
                result = self.validate_file(file_path)
                if result.status != "no_regions":
                    results.append(result)

        return self._generate_report(results)

    def verify_all_hashes(self) -> ValidationReport:
        """Verify hashes for all files in hash store."""
        results = []

        for file_name in self.hash_store:
            file_path = Path(file_name)
            if file_path.exists():
                result = self.validate_file(file_path)
                results.append(result)
            else:
                results.append(FileValidationResult(
                    file=file_name,
                    status="error",
                    regions=[],
                    issues=[f"File no longer exists: {file_name}"],
                    passed=False
                ))

        return self._generate_report(results)

    def _generate_report(self, results: List[FileValidationResult]) -> ValidationReport:
        """Generate validation report."""
        total_regions = sum(len(r.regions) for r in results)
        valid_count = sum(1 for r in results if r.passed)
        issue_count = len(results) - valid_count

        passed = all(r.passed for r in results)

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_files=len(results),
            total_regions=total_regions,
            valid_files=valid_count,
            files_with_issues=issue_count,
            results=results,
            passed=passed
        )

def format_text(report: ValidationReport) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Protected Regions Validation Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Files Checked: {report.total_files}")
    lines.append(f"Total Regions: {report.total_regions}")
    lines.append("")
    lines.append(f"Valid Files: {report.valid_files}")
    lines.append(f"Files with Issues: {report.files_with_issues}")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"Status: {status}")
    lines.append("")

    # Show issues
    for result in report.results:
        if result.issues or result.status == "error":
            lines.append(f"{result.file} [{result.status.upper()}]:")
            for issue in result.issues:
                lines.append(f"  - {issue}")
            for region in result.regions:
                if not region.valid:
                    for issue in region.issues:
                        lines.append(f"  - {issue}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: ValidationReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "total_files": report.total_files,
        "total_regions": report.total_regions,
        "valid_files": report.valid_files,
        "files_with_issues": report.files_with_issues,
        "passed": report.passed,
        "results": [
            {
                "file": r.file,
                "status": r.status,
                "regions": [asdict(reg) for reg in r.regions],
                "issues": r.issues,
                "passed": r.passed
            }
            for r in report.results
        ]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate protected regions in files"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to file to validate"
    )
    parser.add_argument(
        "--check-directory",
        type=Path,
        help="Validate all files in directory"
    )
    parser.add_argument(
        "--verify-hashes",
        action="store_true",
        help="Verify hashes for all tracked files"
    )
    parser.add_argument(
        "--update-hashes",
        action="store_true",
        help="Update stored hashes for file"
    )
    parser.add_argument(
        "--hash-store",
        type=Path,
        default=Path(".task/regions/hashes.yaml"),
        help="Path to hash store file"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file"
    )

    args = parser.parse_args()

    validator = ProtectedRegionsValidator(args.hash_store)

    if args.verify_hashes:
        report = validator.verify_all_hashes()
    elif args.check_directory:
        report = validator.validate_directory(args.check_directory)
    elif args.file:
        if args.update_hashes:
            validator.update_hashes(Path(args.file))
            print(f"Updated hashes for {args.file}")
            sys.exit(0)

        result = validator.validate_file(Path(args.file))
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            total_files=1,
            total_regions=len(result.regions),
            valid_files=1 if result.passed else 0,
            files_with_issues=0 if result.passed else 1,
            results=[result],
            passed=result.passed
        )
    else:
        parser.print_help()
        sys.exit(1)

    # Format output
    if args.format == "json":
        output = format_json(report)
    else:
        output = format_text(report)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Exit code
    sys.exit(0 if report.passed else 1)

if __name__ == "__main__":
    main()
