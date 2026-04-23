#!/usr/bin/env python3
"""
cross_reference_validator.py - Cross-Reference Validation Tool

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - System Integrity

Purpose:
    Validates cross-references between the system documents, ensuring all references
    to files, sections, and anchors are valid and resolvable.

Usage:
    python3 cross_reference_validator.py [options]
    python3 cross_reference_validator.py --path PLANNING/
    python3 cross_reference_validator.py --fix-broken
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CrossReference:
    """Represents a cross-reference found in a document."""
    source_file: str
    source_line: int
    reference_type: str  # file, section, anchor, url
    target: str
    context: str
    valid: bool = False
    error: str = ""

@dataclass
class ValidationReport:
    """Complete cross-reference validation report."""
    timestamp: str
    files_scanned: int
    references_found: int
    valid_references: int
    broken_references: int
    warnings: int
    broken_refs: List[CrossReference] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "files_scanned": self.files_scanned,
            "references_found": self.references_found,
            "valid_references": self.valid_references,
            "broken_references": self.broken_references,
            "warnings": self.warnings,
            "broken_refs": [
                {
                    "source": r.source_file,
                    "line": r.source_line,
                    "type": r.reference_type,
                    "target": r.target,
                    "error": r.error
                }
                for r in self.broken_refs
            ]
        }

# =============================================================================
# Reference Patterns
# =============================================================================

class ReferencePatterns:
    """Patterns for detecting cross-references in documents."""

    # Markdown link: [text](path)
    MARKDOWN_LINK = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    # Markdown reference: [text][ref] or [ref]
    MARKDOWN_REF = re.compile(r'\[([^\]]+)\]\[([^\]]*)\]|\[([^\]]+)\](?!\()')

    # Reference definition: [ref]: path
    MARKDOWN_REF_DEF = re.compile(r'^\s*\[([^\]]+)\]:\s*(.+)$', re.MULTILINE)

    # File path reference: path/to/file.ext
    FILE_PATH = re.compile(r'(?:^|\s|"|\'|`)([A-Za-z0-9_./-]+\.(md|yaml|yml|py|sh|json))(?:\s|"|\'|`|$|:|\))')

    # Line reference: file.ext:123
    LINE_REF = re.compile(r'([A-Za-z0-9_./:-]+\.(md|yaml|yml|py|sh)):(\d+)')

    # Section anchor: #section-name
    SECTION_ANCHOR = re.compile(r'#([a-z0-9-]+)')

    # YAML reference: $ref or !include
    YAML_REF = re.compile(r'(?:\$ref:\s*|!include\s+)([^\s]+)')

    # Code block reference: Reference: path/file.md:line
    DOC_REF = re.compile(r'Reference:\s*([^\s:]+)(?::(\d+))?')

# =============================================================================
# Cross Reference Validator
# =============================================================================

class CrossReferenceValidator:
    """Validates cross-references in the system documents."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path).resolve()
        self.references: List[CrossReference] = []
        self.reference_defs: Dict[str, str] = {}
        self.file_cache: Set[str] = set()
        self.section_cache: Dict[str, Set[str]] = {}

    def scan_directory(self, path: str = ".", extensions: List[str] = None) -> int:
        """Scan directory for files to validate."""
        if extensions is None:
            extensions = [".md", ".yaml", ".yml", ".py"]

        scan_path = self.base_path / path
        files_found = 0

        for ext in extensions:
            for file_path in scan_path.rglob(f"*{ext}"):
                rel_path = str(file_path.relative_to(self.base_path))
                self.file_cache.add(rel_path)
                files_found += 1

        return files_found

    def extract_references(self, file_path: str) -> List[CrossReference]:
        """Extract all cross-references from a file."""
        refs = []
        full_path = self.base_path / file_path

        if not full_path.exists():
            return refs

        try:
            content = full_path.read_text(encoding='utf-8')
        except Exception:
            return refs

        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            # Skip code blocks
            if line.strip().startswith('```'):
                continue

            # Markdown links
            for match in ReferencePatterns.MARKDOWN_LINK.finditer(line):
                text, target = match.groups()
                if not target.startswith(('http://', 'https://', 'mailto:')):
                    refs.append(CrossReference(
                        source_file=file_path,
                        source_line=line_num,
                        reference_type="file" if not '#' in target else "anchor",
                        target=target,
                        context=line.strip()[:100]
                    ))

            # Line references (file.md:123)
            for match in ReferencePatterns.LINE_REF.finditer(line):
                file_ref, ext, line_ref = match.groups()
                refs.append(CrossReference(
                    source_file=file_path,
                    source_line=line_num,
                    reference_type="line",
                    target=f"{file_ref}:{line_ref}",
                    context=line.strip()[:100]
                ))

            # Document references (Reference: path/file.md)
            for match in ReferencePatterns.DOC_REF.finditer(line):
                target_file = match.group(1)
                target_line = match.group(2)
                target = f"{target_file}:{target_line}" if target_line else target_file
                refs.append(CrossReference(
                    source_file=file_path,
                    source_line=line_num,
                    reference_type="doc_ref",
                    target=target,
                    context=line.strip()[:100]
                ))

        # Extract reference definitions for later resolution
        for match in ReferencePatterns.MARKDOWN_REF_DEF.finditer(content):
            ref_name, ref_target = match.groups()
            self.reference_defs[ref_name.lower()] = ref_target.strip()

        return refs

    def extract_sections(self, file_path: str) -> Set[str]:
        """Extract section anchors from a markdown file."""
        sections = set()
        full_path = self.base_path / file_path

        if not full_path.exists() or not file_path.endswith('.md'):
            return sections

        try:
            content = full_path.read_text(encoding='utf-8')
        except Exception:
            return sections

        # Match markdown headers
        header_pattern = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)

        for match in header_pattern.finditer(content):
            header_text = match.group(1).strip()
            # Convert to anchor format (lowercase, spaces to hyphens)
            anchor = re.sub(r'[^\w\s-]', '', header_text.lower())
            anchor = re.sub(r'[-\s]+', '-', anchor).strip('-')
            sections.add(anchor)

        self.section_cache[file_path] = sections
        return sections

    def validate_reference(self, ref: CrossReference) -> CrossReference:
        """Validate a single cross-reference."""
        target = ref.target

        # Handle anchor references (file.md#section or just #section)
        if '#' in target:
            parts = target.split('#', 1)
            file_part = parts[0] if parts[0] else ref.source_file
            anchor_part = parts[1]

            # Resolve relative path
            if file_part and not file_part.startswith('/'):
                source_dir = Path(ref.source_file).parent
                resolved = (source_dir / file_part).as_posix()
                # Normalize path
                resolved = str(Path(resolved))
            else:
                resolved = file_part

            # Check file exists
            if resolved and resolved not in self.file_cache:
                full_check = self.base_path / resolved
                if not full_check.exists():
                    ref.valid = False
                    ref.error = f"File not found: {resolved}"
                    return ref

            # Check anchor exists
            if anchor_part:
                if resolved not in self.section_cache:
                    self.extract_sections(resolved)
                sections = self.section_cache.get(resolved, set())
                if anchor_part.lower() not in sections:
                    ref.valid = False
                    ref.error = f"Section anchor not found: #{anchor_part}"
                    return ref

            ref.valid = True
            return ref

        # Handle line references (file.md:123)
        if ref.reference_type == "line" and ':' in target:
            file_part, line_part = target.rsplit(':', 1)

            # Check file exists
            if file_part not in self.file_cache:
                full_check = self.base_path / file_part
                if not full_check.exists():
                    ref.valid = False
                    ref.error = f"File not found: {file_part}"
                    return ref

            # Check line number is valid
            try:
                line_num = int(line_part)
                full_path = self.base_path / file_part
                line_count = len(full_path.read_text().split('\n'))
                if line_num > line_count:
                    ref.valid = False
                    ref.error = f"Line {line_num} exceeds file length ({line_count} lines)"
                    return ref
            except (ValueError, Exception):
                pass

            ref.valid = True
            return ref

        # Handle plain file references
        # Resolve relative path
        if not target.startswith('/'):
            source_dir = Path(ref.source_file).parent
            resolved = (source_dir / target).as_posix()
            resolved = str(Path(resolved))
        else:
            resolved = target

        # Check in file cache first
        if resolved in self.file_cache:
            ref.valid = True
            return ref

        # Check filesystem
        full_check = self.base_path / resolved
        if full_check.exists():
            ref.valid = True
            self.file_cache.add(resolved)
        else:
            ref.valid = False
            ref.error = f"File not found: {resolved}"

        return ref

    def validate_all(self, path: str = ".") -> ValidationReport:
        """Validate all cross-references in the specified path."""
        # Scan for files
        files_scanned = self.scan_directory(path)

        # Extract references from all files
        all_refs = []
        for file_path in list(self.file_cache):
            refs = self.extract_references(file_path)
            all_refs.extend(refs)

        # Validate each reference
        broken_refs = []
        valid_count = 0

        for ref in all_refs:
            validated = self.validate_reference(ref)
            if validated.valid:
                valid_count += 1
            else:
                broken_refs.append(validated)

        return ValidationReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            files_scanned=files_scanned,
            references_found=len(all_refs),
            valid_references=valid_count,
            broken_references=len(broken_refs),
            warnings=0,
            broken_refs=broken_refs
        )

    def suggest_fixes(self, broken_ref: CrossReference) -> List[str]:
        """Suggest possible fixes for a broken reference."""
        suggestions = []
        target = broken_ref.target.split('#')[0].split(':')[0]
        target_name = Path(target).name if target else ""

        if not target_name:
            return suggestions

        # Find similar files
        for cached_file in self.file_cache:
            if target_name in cached_file:
                suggestions.append(cached_file)
            elif Path(cached_file).name == target_name:
                suggestions.append(cached_file)

        return suggestions[:5]  # Limit to 5 suggestions

# =============================================================================
# CLI Interface
# =============================================================================

def print_report(report: ValidationReport, verbose: bool = False):
    """Print validation report."""
    print("\n" + "=" * 60)
    print("Cross-Reference Validation Report")
    print("=" * 60)
    print(f"Timestamp: {report.timestamp}")
    print(f"Files Scanned: {report.files_scanned}")
    print(f"References Found: {report.references_found}")
    print(f"Valid: {report.valid_references}")
    print(f"Broken: {report.broken_references}")

    if report.broken_refs:
        print("\n" + "-" * 40)
        print("Broken References:")
        print("-" * 40)

        for ref in report.broken_refs:
            print(f"\n  File: {ref.source_file}:{ref.source_line}")
            print(f"  Target: {ref.target}")
            print(f"  Error: {ref.error}")
            if verbose:
                print(f"  Context: {ref.context}")

    print("\n" + "=" * 60)
    if report.broken_references == 0:
        print("\033[92m✓ All cross-references are valid\033[0m")
    else:
        print(f"\033[91m✗ {report.broken_references} broken references found\033[0m")

def main():
    parser = argparse.ArgumentParser(
        description="Validate cross-references in the system documents"
    )
    parser.add_argument(
        "--path", "-p",
        default=".",
        help="Path to scan (default: current directory)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if broken references found"
    )
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="Suggest fixes for broken references"
    )

    args = parser.parse_args()

    validator = CrossReferenceValidator()
    report = validator.validate_all(args.path)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report, args.verbose)

        if args.suggest and report.broken_refs:
            print("\nSuggested Fixes:")
            for ref in report.broken_refs:
                suggestions = validator.suggest_fixes(ref)
                if suggestions:
                    print(f"\n  {ref.target} -> ")
                    for s in suggestions:
                        print(f"    - {s}")

    if args.strict and report.broken_references > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
