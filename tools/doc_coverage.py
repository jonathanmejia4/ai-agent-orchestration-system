#!/usr/bin/env python3
"""
Documentation Coverage Analyzer
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Documentation Quality

Analyzes documentation coverage for the codebase.
Reports on documented vs undocumented code elements.

Usage:
    python tools/doc_coverage.py --source src/
    python tools/doc_coverage.py --check-all
    python tools/doc_coverage.py --min-coverage 80
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import re

@dataclass
class CodeElement:
    """Represents a code element (module, class, function)."""
    name: str
    type: str  # module, class, function, method
    file: str
    line: int
    has_docstring: bool
    docstring_length: int = 0
    docstring_quality: str = "none"  # none, minimal, adequate, good

@dataclass
class FileCoverage:
    """Documentation coverage for a single file."""
    file: str
    total_elements: int
    documented: int
    undocumented: int
    coverage_percent: float
    elements: List[CodeElement]

@dataclass
class CoverageReport:
    """Complete documentation coverage report."""
    timestamp: str
    total_files: int
    total_elements: int
    documented: int
    undocumented: int
    coverage_percent: float
    files: List[FileCoverage]
    undocumented_list: List[CodeElement]
    passed: bool
    min_coverage: float

class DocCoverageAnalyzer:
    """Analyzes documentation coverage in Python code."""

    # Minimum docstring lengths for quality levels
    QUALITY_THRESHOLDS = {
        'minimal': 10,
        'adequate': 50,
        'good': 100,
    }

    def __init__(self, min_coverage: float = 80.0):
        self.min_coverage = min_coverage

    def analyze_file(self, file_path: Path) -> FileCoverage:
        """Analyze documentation coverage in a single file."""
        elements: List[CodeElement] = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError) as e:
            # Return empty coverage for unparseable files
            return FileCoverage(
                file=str(file_path),
                total_elements=0,
                documented=0,
                undocumented=0,
                coverage_percent=100.0,
                elements=[]
            )

        # Check module docstring
        module_doc = ast.get_docstring(tree)
        elements.append(CodeElement(
            name=file_path.stem,
            type="module",
            file=str(file_path),
            line=1,
            has_docstring=module_doc is not None,
            docstring_length=len(module_doc) if module_doc else 0,
            docstring_quality=self._assess_quality(module_doc)
        ))

        # Walk the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                elements.append(CodeElement(
                    name=node.name,
                    type="class",
                    file=str(file_path),
                    line=node.lineno,
                    has_docstring=doc is not None,
                    docstring_length=len(doc) if doc else 0,
                    docstring_quality=self._assess_quality(doc)
                ))

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Determine if method or function
                elem_type = "function"
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        for child in ast.iter_child_nodes(parent):
                            if child is node:
                                elem_type = "method"
                                break

                # Skip private methods for coverage (optional)
                if node.name.startswith('_') and not node.name.startswith('__'):
                    continue

                doc = ast.get_docstring(node)
                elements.append(CodeElement(
                    name=node.name,
                    type=elem_type,
                    file=str(file_path),
                    line=node.lineno,
                    has_docstring=doc is not None,
                    docstring_length=len(doc) if doc else 0,
                    docstring_quality=self._assess_quality(doc)
                ))

        # Calculate coverage
        documented = sum(1 for e in elements if e.has_docstring)
        total = len(elements)
        coverage = (documented / total * 100) if total > 0 else 100.0

        return FileCoverage(
            file=str(file_path),
            total_elements=total,
            documented=documented,
            undocumented=total - documented,
            coverage_percent=round(coverage, 2),
            elements=elements
        )

    def _assess_quality(self, docstring: Optional[str]) -> str:
        """Assess docstring quality based on length and content."""
        if not docstring:
            return "none"

        length = len(docstring)

        if length >= self.QUALITY_THRESHOLDS['good']:
            return "good"
        elif length >= self.QUALITY_THRESHOLDS['adequate']:
            return "adequate"
        elif length >= self.QUALITY_THRESHOLDS['minimal']:
            return "minimal"
        else:
            return "none"

    def analyze_directory(self, dir_path: Path) -> CoverageReport:
        """Analyze all Python files in a directory."""
        files: List[FileCoverage] = []
        undocumented_list: List[CodeElement] = []

        for py_file in dir_path.rglob("*.py"):
            # Skip test files and __pycache__
            if '__pycache__' in str(py_file):
                continue
            if 'test_' in py_file.name or '_test.py' in py_file.name:
                continue

            file_coverage = self.analyze_file(py_file)
            files.append(file_coverage)

            # Collect undocumented elements
            for elem in file_coverage.elements:
                if not elem.has_docstring:
                    undocumented_list.append(elem)

        # Calculate totals
        total_elements = sum(f.total_elements for f in files)
        documented = sum(f.documented for f in files)
        undocumented = total_elements - documented
        coverage = (documented / total_elements * 100) if total_elements > 0 else 100.0

        passed = coverage >= self.min_coverage

        return CoverageReport(
            timestamp=datetime.now().isoformat(),
            total_files=len(files),
            total_elements=total_elements,
            documented=documented,
            undocumented=undocumented,
            coverage_percent=round(coverage, 2),
            files=files,
            undocumented_list=undocumented_list,
            passed=passed,
            min_coverage=self.min_coverage
        )

    def analyze_all(self) -> CoverageReport:
        """Analyze common source directories."""
        all_files: List[FileCoverage] = []
        undocumented_list: List[CodeElement] = []

        source_dirs = ['src', 'tools', 'scripts', 'hooks']
        for dir_name in source_dirs:
            dir_path = Path(dir_name)
            if dir_path.exists():
                report = self.analyze_directory(dir_path)
                all_files.extend(report.files)
                undocumented_list.extend(report.undocumented_list)

        # Calculate totals
        total_elements = sum(f.total_elements for f in all_files)
        documented = sum(f.documented for f in all_files)
        undocumented = total_elements - documented
        coverage = (documented / total_elements * 100) if total_elements > 0 else 100.0

        passed = coverage >= self.min_coverage

        return CoverageReport(
            timestamp=datetime.now().isoformat(),
            total_files=len(all_files),
            total_elements=total_elements,
            documented=documented,
            undocumented=undocumented,
            coverage_percent=round(coverage, 2),
            files=all_files,
            undocumented_list=undocumented_list,
            passed=passed,
            min_coverage=self.min_coverage
        )

def format_text(report: CoverageReport) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Documentation Coverage Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append(f"Minimum Coverage: {report.min_coverage}%")
    lines.append("")
    lines.append(f"Files Analyzed: {report.total_files}")
    lines.append(f"Total Elements: {report.total_elements}")
    lines.append(f"Documented: {report.documented}")
    lines.append(f"Undocumented: {report.undocumented}")
    lines.append(f"Coverage: {report.coverage_percent}%")
    lines.append("")

    status = "PASSED" if report.passed else "FAILED"
    status_icon = "✓" if report.passed else "✗"
    lines.append(f"{status_icon} Status: {status}")
    lines.append("")

    # Show files with low coverage
    low_coverage_files = [f for f in report.files if f.coverage_percent < report.min_coverage]
    if low_coverage_files:
        lines.append("Files Below Threshold:")
        for f in sorted(low_coverage_files, key=lambda x: x.coverage_percent):
            lines.append(f"  {f.file}: {f.coverage_percent}% ({f.undocumented} undocumented)")
        lines.append("")

    # Show undocumented elements (top 20)
    if report.undocumented_list:
        lines.append("Undocumented Elements (top 20):")
        for elem in report.undocumented_list[:20]:
            lines.append(f"  [{elem.type}] {elem.name} ({elem.file}:{elem.line})")
        if len(report.undocumented_list) > 20:
            lines.append(f"  ... and {len(report.undocumented_list) - 20} more")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

def format_json(report: CoverageReport) -> str:
    """Format report as JSON."""
    data = {
        "timestamp": report.timestamp,
        "min_coverage": report.min_coverage,
        "total_files": report.total_files,
        "total_elements": report.total_elements,
        "documented": report.documented,
        "undocumented": report.undocumented,
        "coverage_percent": report.coverage_percent,
        "passed": report.passed,
        "files": [
            {
                "file": f.file,
                "total_elements": f.total_elements,
                "documented": f.documented,
                "coverage_percent": f.coverage_percent
            }
            for f in report.files
        ],
        "undocumented_elements": [
            asdict(e) for e in report.undocumented_list
        ]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze documentation coverage"
    )

    parser.add_argument(
        "--source", "-s",
        type=Path,
        help="Source directory to analyze"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Analyze all common source directories"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Minimum coverage percentage (default: 80)"
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

    analyzer = DocCoverageAnalyzer(args.min_coverage)

    if args.source:
        report = analyzer.analyze_directory(args.source)
    elif args.check_all:
        report = analyzer.analyze_all()
    else:
        # Default: analyze all
        report = analyzer.analyze_all()

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
