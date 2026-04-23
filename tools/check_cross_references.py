#!/usr/bin/env python3
"""
Cross-Reference Integrity Validator

Validates that file references in documentation point to existing files.
Detects broken links, stale references, and ghost references.

Usage:
    python3 tools/check_cross_references.py --dir PLANNING/
    python3 tools/check_cross_references.py --file PM_Operating_Manual.md
    python3 tools/check_cross_references.py --all
    python3 tools/check_cross_references.py --help

Exit Codes:
    0 - All references valid
    1 - Broken references found
    2 - Parse error or invalid input

Referenced in:
    - PM_Operating_Manual.md:377 (LogBook cross-ref validation)
    - agent-coordination-protocol.md:1448 (LogBook entry cross-refs)

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from difflib import get_close_matches

# File extensions to scan for references
SCANNABLE_EXTENSIONS = {'.md', '.yaml', '.yml', '.json', '.txt'}

# File extensions that are commonly referenced
REFERENCEABLE_EXTENSIONS = {
    '.md', '.yaml', '.yml', '.json', '.py', '.sh', '.js', '.ts',
    '.html', '.css', '.txt', '.xml', '.toml'
}

@dataclass
class Reference:
    """A file reference found in a document"""
    source_file: str
    line_number: int
    reference: str
    reference_type: str  # file_path, line_ref, see_ref, etc.
    exists: bool = False
    suggested_fix: Optional[str] = None

@dataclass
class ValidationResult:
    """Result of cross-reference validation"""
    total_references: int = 0
    valid_references: int = 0
    broken_references: int = 0
    files_scanned: int = 0
    references: List[Reference] = field(default_factory=list)
    broken: List[Reference] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.broken_references == 0 and len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.is_valid,
            'total_references': self.total_references,
            'valid_references': self.valid_references,
            'broken_references': self.broken_references,
            'files_scanned': self.files_scanned,
            'broken': [asdict(r) for r in self.broken],
            'errors': self.errors
        }

class CrossReferenceChecker:
    """Validates cross-references in documentation"""

    # Patterns to detect file references
    REFERENCE_PATTERNS = [
        # file.ext:line_number (e.g., PM_Operating_Manual.md:377)
        (r'([a-zA-Z0-9_\-./]+\.(md|py|sh|yaml|yml|json|js|ts)):(\d+)', 'line_ref'),
        # path/to/file.ext
        (r'(?:^|[\s`"\'])((?:\.\.?/)?(?:[a-zA-Z0-9_\-]+/)*[a-zA-Z0-9_\-]+\.(md|py|sh|yaml|yml|json|js|ts|html|css))(?:[\s`"\']|$)', 'file_path'),
        # tools/script.py, PLANNING/doc.md
        (r'(?:tools|PLANNING|LogBook|tasks|templates|tests|\.claude|\.github)/[a-zA-Z0-9_\-./]+\.(md|py|sh|yaml|yml|json)', 'file_path'),
        # See file.ext or Referenced in file.ext
        (r'(?:See|see|Referenced in|referenced in|Ref:|ref:)\s+[`"]?([a-zA-Z0-9_\-./]+\.(md|py|sh|yaml|yml))[`"]?', 'see_ref'),
    ]

    # Paths to ignore (external references, templates, etc.)
    IGNORE_PATTERNS = [
        r'^https?://',           # URLs
        r'^#',                   # Anchor links
        r'\{\{.*\}\}',          # Template variables
        r'<.*>',                # Placeholder variables
        r'example\.',           # Example files
        r'your[-_]?',           # Placeholder names
    ]

    def __init__(self, repo_root: Optional[Path] = None,
                 verbose: bool = False, allowlist: Optional[List[str]] = None):
        self.repo_root = repo_root or Path.cwd()
        self.verbose = verbose
        self.allowlist = set(allowlist or [])
        self.all_files: Set[str] = set()

    def log(self, message: str):
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def build_file_index(self):
        """Build index of all files in repository"""
        self.all_files = set()
        for path in self.repo_root.rglob('*'):
            if path.is_file():
                # Store relative path
                rel_path = path.relative_to(self.repo_root)
                self.all_files.add(str(rel_path))
                # Also store just filename for fuzzy matching
                self.all_files.add(path.name)
        self.log(f"Indexed {len(self.all_files)} files")

    def should_ignore(self, reference: str) -> bool:
        """Check if reference should be ignored"""
        for pattern in self.IGNORE_PATTERNS:
            if re.search(pattern, reference):
                return True
        if reference in self.allowlist:
            return True
        return False

    def normalize_path(self, reference: str, source_file: Path) -> str:
        """Normalize a file reference to absolute path"""
        # Remove leading ./
        reference = reference.lstrip('./')

        # Handle relative paths
        if reference.startswith('../'):
            # Resolve relative to source file
            source_dir = source_file.parent
            ref_path = source_dir / reference
            try:
                return str(ref_path.resolve().relative_to(self.repo_root))
            except ValueError:
                return reference

        return reference

    def file_exists(self, reference: str, source_file: Path) -> Tuple[bool, Optional[str]]:
        """Check if referenced file exists, return suggested fix if not"""
        normalized = self.normalize_path(reference, source_file)

        # Check exact match
        full_path = self.repo_root / normalized
        if full_path.exists():
            return True, None

        # Check if file exists elsewhere
        filename = Path(reference).name
        if filename in self.all_files:
            return True, None  # Found somewhere

        # Find similar files for suggestion
        suggestions = get_close_matches(filename,
                                        [f for f in self.all_files if '/' not in f],
                                        n=1, cutoff=0.6)
        if suggestions:
            return False, suggestions[0]

        return False, None

    def extract_references(self, file_path: Path) -> List[Reference]:
        """Extract file references from a file"""
        references = []

        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            self.log(f"Error reading {file_path}: {e}")
            return references

        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for pattern, ref_type in self.REFERENCE_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    # Get the file reference (first capturing group)
                    ref = match.group(1) if match.lastindex >= 1 else match.group(0)

                    # Skip if should be ignored
                    if self.should_ignore(ref):
                        continue

                    # Check if file exists
                    exists, suggestion = self.file_exists(ref, file_path)

                    reference = Reference(
                        source_file=str(file_path.relative_to(self.repo_root)),
                        line_number=line_num,
                        reference=ref,
                        reference_type=ref_type,
                        exists=exists,
                        suggested_fix=suggestion
                    )
                    references.append(reference)

        return references

    def check_file(self, file_path: Path) -> List[Reference]:
        """Check a single file for cross-references"""
        if file_path.suffix not in SCANNABLE_EXTENSIONS:
            return []
        return self.extract_references(file_path)

    def check_directory(self, dir_path: Path) -> ValidationResult:
        """Check all files in a directory"""
        result = ValidationResult()

        if not dir_path.exists():
            result.errors.append(f"Directory not found: {dir_path}")
            return result

        # Build file index
        self.build_file_index()

        # Scan files
        for file_path in dir_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in SCANNABLE_EXTENSIONS:
                result.files_scanned += 1
                refs = self.check_file(file_path)
                result.references.extend(refs)

        # Categorize results
        result.total_references = len(result.references)
        for ref in result.references:
            if ref.exists:
                result.valid_references += 1
            else:
                result.broken_references += 1
                result.broken.append(ref)

        return result

    def check_all(self) -> ValidationResult:
        """Check entire repository"""
        return self.check_directory(self.repo_root)

def print_result(result: ValidationResult, format: str = "text"):
    """Print validation result"""
    if format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return

    print()
    if result.is_valid:
        print(f"\033[92m✅ All cross-references valid\033[0m")
    else:
        print(f"\033[91m❌ Broken cross-references found\033[0m")

    print(f"\nFiles scanned: {result.files_scanned}")
    print(f"Total references: {result.total_references}")
    print(f"Valid: {result.valid_references}")
    print(f"Broken: {result.broken_references}")

    if result.broken:
        print(f"\n\033[91mBroken References:\033[0m")
        for ref in result.broken[:20]:  # Limit to first 20
            print(f"  {ref.source_file}:{ref.line_number}")
            print(f"    → {ref.reference}")
            if ref.suggested_fix:
                print(f"    💡 Did you mean: {ref.suggested_fix}")
        if len(result.broken) > 20:
            print(f"  ... and {len(result.broken) - 20} more")

    if result.errors:
        print(f"\n\033[93mErrors:\033[0m")
        for error in result.errors:
            print(f"  {error}")

def main():
    parser = argparse.ArgumentParser(
        description='Validate cross-references in documentation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check PLANNING directory
    %(prog)s --dir PLANNING/

    # Check single file
    %(prog)s --file PM_Operating_Manual.md

    # Check entire repository
    %(prog)s --all

    # JSON output for CI
    %(prog)s --dir PLANNING/ --format json

Exit Codes:
    0 - All references valid
    1 - Broken references found
    2 - Parse error or invalid input
        """
    )

    parser.add_argument('--dir', '-d', type=Path,
                       help='Directory to check')
    parser.add_argument('--file', '-f', type=Path,
                       help='Single file to check')
    parser.add_argument('--all', '-a', action='store_true',
                       help='Check entire repository')
    parser.add_argument('--format', choices=['text', 'json'], default='text',
                       help='Output format')
    parser.add_argument('--allowlist', nargs='*', default=[],
                       help='Files to ignore (external refs, planned files)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd(),
                       help='Repository root')

    args = parser.parse_args()

    if not any([args.dir, args.file, args.all]):
        parser.print_help()
        sys.exit(2)

    checker = CrossReferenceChecker(
        repo_root=args.repo_root,
        verbose=args.verbose,
        allowlist=args.allowlist
    )

    if args.file:
        # Check single file
        checker.build_file_index()
        refs = checker.check_file(args.file)
        result = ValidationResult(
            files_scanned=1,
            total_references=len(refs),
            references=refs
        )
        for ref in refs:
            if ref.exists:
                result.valid_references += 1
            else:
                result.broken_references += 1
                result.broken.append(ref)
    elif args.dir:
        result = checker.check_directory(args.dir)
    else:
        result = checker.check_all()

    print_result(result, args.format)

    if result.errors:
        sys.exit(2)
    elif not result.is_valid:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
