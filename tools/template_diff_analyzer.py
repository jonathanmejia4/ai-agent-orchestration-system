#!/usr/bin/env python3
"""
Template Diff Analyzer - Semantic Version Change Detection

Analyzes template changes between versions to determine appropriate
semantic version bumps (MAJOR, MINOR, or PATCH) based on the nature
of changes detected.

Usage:
    python3 tools/template_diff_analyzer.py <template-name> <old-version> <new-version>
    python3 tools/template_diff_analyzer.py api-crud 2.3.0 current
    python3 tools/template_diff_analyzer.py --template-dir templates/api-crud/
    python3 tools/template_diff_analyzer.py --format json
    python3 tools/template_diff_analyzer.py --help

Exit Codes:
    0 - Analysis completed successfully

Referenced in:
    - PLANNING/TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md:278

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import json
import difflib
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

class VersionBump(Enum):
    """Semantic version bump types"""
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"
    NONE = "NONE"

class ChangeCategory(Enum):
    """Change categorization"""
    BREAKING = "breaking"
    FEATURE = "feature"
    FIX = "fix"
    DOCS = "docs"
    REFACTOR = "refactor"
    STYLE = "style"

@dataclass
class Change:
    """Detected change"""
    category: ChangeCategory
    description: str
    file_path: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    severity: str = "info"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value,
            'description': self.description,
            'file_path': self.file_path,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'severity': self.severity
        }

@dataclass
class AnalysisResult:
    """Complete analysis result"""
    template_name: str
    old_version: str
    new_version: str
    timestamp: str
    recommended_bump: VersionBump
    confidence: float  # 0.0 to 1.0
    changes: List[Change] = field(default_factory=list)
    breaking_changes: int = 0
    new_features: int = 0
    fixes: int = 0
    summary: str = ""

    def add_change(self, change: Change):
        self.changes.append(change)
        if change.category == ChangeCategory.BREAKING:
            self.breaking_changes += 1
        elif change.category == ChangeCategory.FEATURE:
            self.new_features += 1
        elif change.category == ChangeCategory.FIX:
            self.fixes += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'template_name': self.template_name,
            'old_version': self.old_version,
            'new_version': self.new_version,
            'timestamp': self.timestamp,
            'recommended_bump': self.recommended_bump.value,
            'confidence': self.confidence,
            'summary': self.summary,
            'statistics': {
                'breaking_changes': self.breaking_changes,
                'new_features': self.new_features,
                'fixes': self.fixes,
                'total_changes': len(self.changes)
            },
            'changes': [c.to_dict() for c in self.changes]
        }

class TemplateDiffAnalyzer:
    """Template version diff analyzer"""

    # File patterns indicating breaking changes
    BREAKING_PATTERNS = [
        r'\.ts$',  # TypeScript files (API changes)
        r'\.js$',  # JavaScript files
        r'\.py$',  # Python files
        r'service\..*$',  # Service files
        r'api\..*$',  # API files
        r'schema\..*$',  # Schema files
        r'interface\..*$',  # Interface files
    ]

    # File patterns for documentation
    DOC_PATTERNS = [
        r'README\.md$',
        r'\.md$',
        r'docs/',
        r'CHANGELOG',
    ]

    # Keywords indicating breaking changes in content
    BREAKING_KEYWORDS = [
        'breaking', 'removed', 'deleted', 'incompatible',
        'deprecated', 'changed signature', 'renamed',
    ]

    # Keywords indicating new features
    FEATURE_KEYWORDS = [
        'added', 'new', 'feature', 'support for',
        'implement', 'introduce',
    ]

    def __init__(self, template_name: str, old_version: str, new_version: str,
                 template_dir: Optional[Path] = None, verbose: bool = False):
        self.template_name = template_name
        self.old_version = old_version
        self.new_version = new_version
        self.template_dir = template_dir
        self.verbose = verbose
        self.result = AnalysisResult(
            template_name=template_name,
            old_version=old_version,
            new_version=new_version,
            timestamp=datetime.now().isoformat(),
            recommended_bump=VersionBump.NONE,
            confidence=0.0
        )

    def log(self, message: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def find_template_versions(self) -> Tuple[Optional[Path], Optional[Path]]:
        """Find template version directories"""
        if not self.template_dir:
            # Search common locations
            search_paths = [
                Path('templates') / self.template_name,
                Path('.task') / 'templates' / self.template_name,
            ]
            for path in search_paths:
                if path.exists():
                    self.template_dir = path
                    break

        if not self.template_dir or not self.template_dir.exists():
            return None, None

        # Look for version directories
        old_dir = self.template_dir / self.old_version
        new_dir = self.template_dir / self.new_version

        # If "current" is specified, use the base template dir
        if self.new_version.lower() == 'current':
            new_dir = self.template_dir

        return old_dir if old_dir.exists() else None, new_dir if new_dir.exists() else None

    def get_file_list(self, directory: Path) -> Set[str]:
        """Get list of files in directory"""
        files = set()
        if directory.exists():
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    relative = file_path.relative_to(directory)
                    files.add(str(relative))
        return files

    def analyze_file_changes(self, old_files: Set[str], new_files: Set[str]):
        """Analyze file-level changes"""
        added = new_files - old_files
        removed = old_files - new_files
        common = old_files & new_files

        # Removed files are potential breaking changes
        for file_path in removed:
            is_breaking = any(re.search(p, file_path) for p in self.BREAKING_PATTERNS)
            if is_breaking:
                self.result.add_change(Change(
                    category=ChangeCategory.BREAKING,
                    description=f"File removed: {file_path}",
                    file_path=file_path,
                    severity="error"
                ))
            else:
                self.result.add_change(Change(
                    category=ChangeCategory.REFACTOR,
                    description=f"File removed: {file_path}",
                    file_path=file_path,
                    severity="warning"
                ))

        # Added files are new features
        for file_path in added:
            is_docs = any(re.search(p, file_path) for p in self.DOC_PATTERNS)
            if is_docs:
                self.result.add_change(Change(
                    category=ChangeCategory.DOCS,
                    description=f"Documentation added: {file_path}",
                    file_path=file_path,
                    severity="info"
                ))
            else:
                self.result.add_change(Change(
                    category=ChangeCategory.FEATURE,
                    description=f"New file added: {file_path}",
                    file_path=file_path,
                    severity="info"
                ))

        return common

    def analyze_content_changes(self, old_dir: Path, new_dir: Path, common_files: Set[str]):
        """Analyze content-level changes in common files"""
        for file_path in common_files:
            old_file = old_dir / file_path
            new_file = new_dir / file_path

            try:
                old_content = old_file.read_text()
                new_content = new_file.read_text()
            except Exception as e:
                self.log(f"Could not read {file_path}: {e}")
                continue

            if old_content == new_content:
                continue

            # Generate diff
            diff = list(difflib.unified_diff(
                old_content.splitlines(),
                new_content.splitlines(),
                lineterm=''
            ))

            if not diff:
                continue

            # Analyze diff for breaking changes
            added_lines = [l[1:] for l in diff if l.startswith('+') and not l.startswith('+++')]
            removed_lines = [l[1:] for l in diff if l.startswith('-') and not l.startswith('---')]

            # Check for breaking change indicators
            is_breaking = False
            is_feature = False
            is_docs = any(re.search(p, file_path) for p in self.DOC_PATTERNS)

            # Check for API/interface changes
            if any(re.search(p, file_path) for p in self.BREAKING_PATTERNS):
                # Look for signature changes
                for line in removed_lines:
                    if re.search(r'(def |function |class |interface |export )', line):
                        is_breaking = True
                        break
                    if any(kw in line.lower() for kw in self.BREAKING_KEYWORDS):
                        is_breaking = True
                        break

            # Check for new features
            for line in added_lines:
                if any(kw in line.lower() for kw in self.FEATURE_KEYWORDS):
                    is_feature = True
                    break

            # Categorize change
            if is_breaking:
                self.result.add_change(Change(
                    category=ChangeCategory.BREAKING,
                    description=f"API/structure change in {file_path}",
                    file_path=file_path,
                    severity="error"
                ))
            elif is_feature:
                self.result.add_change(Change(
                    category=ChangeCategory.FEATURE,
                    description=f"New functionality in {file_path}",
                    file_path=file_path,
                    severity="info"
                ))
            elif is_docs:
                self.result.add_change(Change(
                    category=ChangeCategory.DOCS,
                    description=f"Documentation update in {file_path}",
                    file_path=file_path,
                    severity="info"
                ))
            else:
                self.result.add_change(Change(
                    category=ChangeCategory.FIX,
                    description=f"Changes in {file_path}",
                    file_path=file_path,
                    severity="info"
                ))

    def analyze_changelog(self, new_dir: Path):
        """Analyze CHANGELOG if available"""
        changelog_paths = [
            new_dir / 'CHANGELOG.md',
            new_dir / 'CHANGELOG',
            new_dir / 'HISTORY.md',
        ]

        for changelog_path in changelog_paths:
            if changelog_path.exists():
                try:
                    content = changelog_path.read_text().lower()

                    # Look for breaking change mentions
                    if 'breaking' in content or 'incompatible' in content:
                        self.result.add_change(Change(
                            category=ChangeCategory.BREAKING,
                            description="CHANGELOG mentions breaking changes",
                            file_path=str(changelog_path.name),
                            severity="warning"
                        ))

                except Exception as e:
                    self.log(f"Could not read changelog: {e}")

    def determine_version_bump(self):
        """Determine recommended version bump based on changes"""
        if self.result.breaking_changes > 0:
            self.result.recommended_bump = VersionBump.MAJOR
            self.result.confidence = 0.9
        elif self.result.new_features > 0:
            self.result.recommended_bump = VersionBump.MINOR
            self.result.confidence = 0.8
        elif self.result.fixes > 0 or len(self.result.changes) > 0:
            self.result.recommended_bump = VersionBump.PATCH
            self.result.confidence = 0.7
        else:
            self.result.recommended_bump = VersionBump.NONE
            self.result.confidence = 0.5

    def analyze(self) -> AnalysisResult:
        """Run complete analysis"""
        print(f"\n{'='*60}")
        print(f"Template Diff Analysis")
        print(f"{'='*60}\n")

        print(f"Template:    {self.template_name}")
        print(f"Old version: {self.old_version}")
        print(f"New version: {self.new_version}")
        print()

        # Find version directories
        old_dir, new_dir = self.find_template_versions()

        if old_dir and new_dir:
            print(f"Analyzing directories...")
            print(f"  Old: {old_dir}")
            print(f"  New: {new_dir}")
            print()

            # Get file lists
            old_files = self.get_file_list(old_dir)
            new_files = self.get_file_list(new_dir)

            print(f"Files in old version: {len(old_files)}")
            print(f"Files in new version: {len(new_files)}")
            print()

            # Analyze changes
            print("Analyzing changes...")
            common_files = self.analyze_file_changes(old_files, new_files)
            self.analyze_content_changes(old_dir, new_dir, common_files)
            self.analyze_changelog(new_dir)

        else:
            print("Note: Could not find version directories for comparison.")
            print("Performing analysis based on template metadata...")

            # Try to analyze template.yaml for version info
            if self.template_dir and (self.template_dir / 'template.yaml').exists():
                self.result.add_change(Change(
                    category=ChangeCategory.FIX,
                    description="Template metadata exists",
                    file_path="template.yaml",
                    severity="info"
                ))

        # Determine version bump
        self.determine_version_bump()

        # Generate summary
        self.result.summary = self._generate_summary()

        return self.result

    def _generate_summary(self) -> str:
        """Generate human-readable summary"""
        parts = []

        if self.result.breaking_changes > 0:
            parts.append(f"{self.result.breaking_changes} breaking change(s)")
        if self.result.new_features > 0:
            parts.append(f"{self.result.new_features} new feature(s)")
        if self.result.fixes > 0:
            parts.append(f"{self.result.fixes} fix(es)/update(s)")

        if not parts:
            return "No significant changes detected"

        return ", ".join(parts)

    def print_result(self):
        """Print analysis result"""
        print("\n" + "="*60)
        print("Analysis Result")
        print("="*60 + "\n")

        # Recommended bump
        bump = self.result.recommended_bump
        if bump == VersionBump.MAJOR:
            color = "\033[91m"  # Red
        elif bump == VersionBump.MINOR:
            color = "\033[93m"  # Yellow
        elif bump == VersionBump.PATCH:
            color = "\033[92m"  # Green
        else:
            color = "\033[90m"  # Gray

        print(f"Recommended bump: {color}{bump.value}\033[0m")
        print(f"Confidence: {self.result.confidence:.0%}")
        print(f"Summary: {self.result.summary}")
        print()

        # Changes by category
        if self.result.changes:
            print("Changes detected:")
            for change in self.result.changes[:20]:
                if change.category == ChangeCategory.BREAKING:
                    icon = "\033[91m✗\033[0m"
                elif change.category == ChangeCategory.FEATURE:
                    icon = "\033[92m+\033[0m"
                else:
                    icon = "\033[90m•\033[0m"

                print(f"  {icon} [{change.category.value}] {change.description}")

            if len(self.result.changes) > 20:
                print(f"  ... and {len(self.result.changes) - 20} more changes")

def main():
    parser = argparse.ArgumentParser(
        description='Template Diff Analyzer - Semantic version change detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s api-crud 2.3.0 2.4.0
    %(prog)s api-crud 2.3.0 current
    %(prog)s --template-dir templates/api-crud/ --old 1.0.0 --new 2.0.0
    %(prog)s api-crud 2.3.0 current --format json

Exit Codes:
    0 - Analysis completed (always succeeds)
        """
    )

    parser.add_argument('template_name', nargs='?', help='Template name')
    parser.add_argument('old_version', nargs='?', help='Old version')
    parser.add_argument('new_version', nargs='?', default='current',
                        help='New version (default: current)')
    parser.add_argument('--template-dir', '-d', type=Path,
                        help='Template directory path')
    parser.add_argument('--old', type=str, help='Old version (alternative)')
    parser.add_argument('--new', type=str, help='New version (alternative)')
    parser.add_argument('--format', '-f', choices=['text', 'json'], default='text',
                        help='Output format')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output file for analysis report')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Validate arguments
    template_name = args.template_name or 'unknown'
    old_version = args.old or args.old_version or '0.0.0'
    new_version = args.new or args.new_version or 'current'

    # Create analyzer
    analyzer = TemplateDiffAnalyzer(
        template_name=template_name,
        old_version=old_version,
        new_version=new_version,
        template_dir=args.template_dir,
        verbose=args.verbose
    )

    # Run analysis
    result = analyzer.analyze()

    # Output
    if args.format == 'json':
        print(json.dumps(result.to_dict(), indent=2))
    else:
        analyzer.print_result()

    # Save report
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\nReport saved: {args.output}")

    sys.exit(0)

if __name__ == '__main__':
    main()
