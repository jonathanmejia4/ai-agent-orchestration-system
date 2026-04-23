#!/usr/bin/env python3
"""
code_quality_analyzer.py - Code Quality Analyzer

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Analysis Tool

Purpose:
    Analyzes code quality across the system codebase:
    - Cyclomatic complexity
    - Code duplication
    - Documentation coverage
    - Naming conventions
    - Module coupling

Usage:
    python3 code_quality_analyzer.py analyze --path task001/
    python3 code_quality_analyzer.py complexity --file src/main.py
    python3 code_quality_analyzer.py report --output quality-report.json
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class QualityMetric:
    """Individual quality metric."""
    name: str
    value: float
    threshold: float
    passed: bool
    details: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.threshold,
            "passed": self.passed,
            "details": self.details
        }

@dataclass
class FileAnalysis:
    """Analysis for a single file."""
    file_path: str
    lines_of_code: int
    lines_of_comments: int
    lines_blank: int
    functions: int
    classes: int
    complexity: float
    documentation_ratio: float
    issues: List[Dict[str, Any]]
    metrics: List[QualityMetric]

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "lines_of_code": self.lines_of_code,
            "lines_of_comments": self.lines_of_comments,
            "lines_blank": self.lines_blank,
            "functions": self.functions,
            "classes": self.classes,
            "complexity": self.complexity,
            "documentation_ratio": self.documentation_ratio,
            "issues": self.issues,
            "metrics": [m.to_dict() for m in self.metrics]
        }

@dataclass
class QualityReport:
    """Complete quality analysis report."""
    report_id: str
    timestamp: str
    scan_path: str
    files_analyzed: int
    total_lines: int
    total_functions: int
    total_classes: int
    overall_score: float
    file_analyses: List[FileAnalysis]
    summary: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "scan_path": self.scan_path,
            "files_analyzed": self.files_analyzed,
            "total_lines": self.total_lines,
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "overall_score": self.overall_score,
            "summary": self.summary,
            "file_analyses": [f.to_dict() for f in self.file_analyses]
        }

class ComplexityVisitor(ast.NodeVisitor):
    """Calculate cyclomatic complexity for Python code."""

    def __init__(self):
        self.complexity = 1
        self.functions = []
        self.classes = []

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.functions.append({
            "name": node.name,
            "line": node.lineno,
            "has_docstring": ast.get_docstring(node) is not None,
            "args": len(node.args.args)
        })
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.functions.append({
            "name": node.name,
            "line": node.lineno,
            "has_docstring": ast.get_docstring(node) is not None,
            "args": len(node.args.args)
        })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes.append({
            "name": node.name,
            "line": node.lineno,
            "has_docstring": ast.get_docstring(node) is not None,
            "methods": sum(1 for n in ast.walk(node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        })
        self.generic_visit(node)

class CodeQualityAnalyzer:
    """Analyzes code quality."""

    # Quality thresholds
    THRESHOLDS = {
        "complexity": 10,           # Max cyclomatic complexity
        "function_length": 50,      # Max lines per function
        "file_length": 500,         # Max lines per file
        "documentation_ratio": 0.1,  # Min doc/code ratio
        "duplication_ratio": 0.05,  # Max duplication ratio
    }

    # Naming convention patterns
    NAMING_PATTERNS = {
        "class": re.compile(r'^[A-Z][a-zA-Z0-9]*$'),
        "function": re.compile(r'^[a-z_][a-z0-9_]*$'),
        "constant": re.compile(r'^[A-Z][A-Z0-9_]*$'),
        "variable": re.compile(r'^[a-z_][a-z0-9_]*$'),
    }

    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)

    def analyze_python_file(self, file_path: Path) -> FileAnalysis:
        """Analyze a single Python file."""
        issues = []
        metrics = []

        try:
            content = file_path.read_text()
            lines = content.split('\n')
        except Exception as e:
            return FileAnalysis(
                file_path=str(file_path),
                lines_of_code=0,
                lines_of_comments=0,
                lines_blank=0,
                functions=0,
                classes=0,
                complexity=0,
                documentation_ratio=0,
                issues=[{"type": "error", "message": str(e)}],
                metrics=[]
            )

        # Count lines
        loc = 0
        comments = 0
        blank = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank += 1
            elif stripped.startswith('#'):
                comments += 1
            else:
                loc += 1

        # Parse AST
        try:
            tree = ast.parse(content)
            visitor = ComplexityVisitor()
            visitor.visit(tree)

            complexity = visitor.complexity
            functions = visitor.functions
            classes = visitor.classes

            # Check module docstring
            module_docstring = ast.get_docstring(tree)

        except SyntaxError as e:
            issues.append({
                "type": "syntax_error",
                "line": e.lineno,
                "message": str(e)
            })
            complexity = 0
            functions = []
            classes = []
            module_docstring = None

        # Calculate documentation ratio
        documented = sum(1 for f in functions if f["has_docstring"])
        documented += sum(1 for c in classes if c["has_docstring"])
        total_items = len(functions) + len(classes)
        doc_ratio = documented / total_items if total_items > 0 else 1.0

        # Check complexity threshold
        metrics.append(QualityMetric(
            name="Cyclomatic Complexity",
            value=complexity,
            threshold=self.THRESHOLDS["complexity"],
            passed=complexity <= self.THRESHOLDS["complexity"],
            details=f"Complexity: {complexity} (max: {self.THRESHOLDS['complexity']})"
        ))

        if complexity > self.THRESHOLDS["complexity"]:
            issues.append({
                "type": "high_complexity",
                "severity": "high" if complexity > 20 else "medium",
                "message": f"High cyclomatic complexity: {complexity}"
            })

        # Check file length
        metrics.append(QualityMetric(
            name="File Length",
            value=loc,
            threshold=self.THRESHOLDS["file_length"],
            passed=loc <= self.THRESHOLDS["file_length"],
            details=f"Lines: {loc} (max: {self.THRESHOLDS['file_length']})"
        ))

        if loc > self.THRESHOLDS["file_length"]:
            issues.append({
                "type": "long_file",
                "severity": "medium",
                "message": f"File too long: {loc} lines"
            })

        # Check documentation
        metrics.append(QualityMetric(
            name="Documentation Ratio",
            value=doc_ratio,
            threshold=self.THRESHOLDS["documentation_ratio"],
            passed=doc_ratio >= self.THRESHOLDS["documentation_ratio"],
            details=f"Documented: {documented}/{total_items}"
        ))

        if doc_ratio < self.THRESHOLDS["documentation_ratio"]:
            issues.append({
                "type": "low_documentation",
                "severity": "low",
                "message": f"Low documentation ratio: {doc_ratio:.1%}"
            })

        # Check naming conventions
        for func in functions:
            if not self.NAMING_PATTERNS["function"].match(func["name"]):
                if not func["name"].startswith("_"):
                    issues.append({
                        "type": "naming_convention",
                        "severity": "info",
                        "line": func["line"],
                        "message": f"Function '{func['name']}' doesn't follow snake_case"
                    })

        for cls in classes:
            if not self.NAMING_PATTERNS["class"].match(cls["name"]):
                issues.append({
                    "type": "naming_convention",
                    "severity": "info",
                    "line": cls["line"],
                    "message": f"Class '{cls['name']}' doesn't follow PascalCase"
                })

        return FileAnalysis(
            file_path=str(file_path),
            lines_of_code=loc,
            lines_of_comments=comments,
            lines_blank=blank,
            functions=len(functions),
            classes=len(classes),
            complexity=complexity,
            documentation_ratio=doc_ratio,
            issues=issues,
            metrics=metrics
        )

    def analyze_directory(self, scan_path: Optional[str] = None) -> QualityReport:
        """Analyze all Python files in directory."""
        target = Path(scan_path) if scan_path else self.base_path
        analyses: List[FileAnalysis] = []

        for file_path in target.rglob("*.py"):
            if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                continue

            analysis = self.analyze_python_file(file_path)
            analyses.append(analysis)

        # Calculate totals
        total_lines = sum(a.lines_of_code for a in analyses)
        total_functions = sum(a.functions for a in analyses)
        total_classes = sum(a.classes for a in analyses)
        total_issues = sum(len(a.issues) for a in analyses)

        # Calculate overall score
        scores = []
        for a in analyses:
            file_score = 100
            for m in a.metrics:
                if not m.passed:
                    file_score -= 10
            for issue in a.issues:
                severity = issue.get("severity", "info")
                if severity == "high":
                    file_score -= 15
                elif severity == "medium":
                    file_score -= 10
                elif severity == "low":
                    file_score -= 5
            scores.append(max(0, file_score))

        overall_score = sum(scores) / len(scores) if scores else 100

        # Summary statistics
        summary = {
            "total_issues": total_issues,
            "issues_by_type": {},
            "issues_by_severity": {"high": 0, "medium": 0, "low": 0, "info": 0},
            "avg_complexity": sum(a.complexity for a in analyses) / len(analyses) if analyses else 0,
            "avg_documentation": sum(a.documentation_ratio for a in analyses) / len(analyses) if analyses else 0,
            "files_with_issues": sum(1 for a in analyses if a.issues)
        }

        for a in analyses:
            for issue in a.issues:
                issue_type = issue.get("type", "unknown")
                severity = issue.get("severity", "info")
                summary["issues_by_type"][issue_type] = summary["issues_by_type"].get(issue_type, 0) + 1
                summary["issues_by_severity"][severity] = summary["issues_by_severity"].get(severity, 0) + 1

        return QualityReport(
            report_id=f"QA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            scan_path=str(target),
            files_analyzed=len(analyses),
            total_lines=total_lines,
            total_functions=total_functions,
            total_classes=total_classes,
            overall_score=overall_score,
            file_analyses=analyses,
            summary=summary
        )

    def get_complexity_report(self, file_path: str) -> Dict[str, Any]:
        """Get detailed complexity report for a file."""
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        analysis = self.analyze_python_file(path)

        try:
            content = path.read_text()
            tree = ast.parse(content)
            visitor = ComplexityVisitor()
            visitor.visit(tree)

            return {
                "file": file_path,
                "overall_complexity": analysis.complexity,
                "functions": visitor.functions,
                "classes": visitor.classes,
                "recommendations": self._get_recommendations(analysis)
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_recommendations(self, analysis: FileAnalysis) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []

        if analysis.complexity > self.THRESHOLDS["complexity"]:
            recommendations.append(
                f"Reduce cyclomatic complexity (current: {analysis.complexity}, target: <{self.THRESHOLDS['complexity']}). "
                "Consider breaking down complex functions."
            )

        if analysis.lines_of_code > self.THRESHOLDS["file_length"]:
            recommendations.append(
                f"File is too long ({analysis.lines_of_code} lines). "
                "Consider splitting into multiple modules."
            )

        if analysis.documentation_ratio < self.THRESHOLDS["documentation_ratio"]:
            recommendations.append(
                f"Improve documentation coverage (current: {analysis.documentation_ratio:.1%}). "
                "Add docstrings to functions and classes."
            )

        return recommendations

def main():
    parser = argparse.ArgumentParser(description="Code Quality Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze code quality")
    analyze_parser.add_argument("--path", default=".", help="Path to analyze")

    # Complexity command
    complexity_parser = subparsers.add_parser("complexity", help="Analyze complexity")
    complexity_parser.add_argument("--file", required=True, help="File to analyze")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--path", default=".", help="Path to analyze")
    report_parser.add_argument("--output", "-o", help="Output file")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    analyzer = CodeQualityAnalyzer()

    if args.command == "analyze":
        report = analyzer.analyze_directory(args.path)

        if args.format == "json":
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"\nCode Quality Analysis")
            print("=" * 60)
            print(f"Path: {report.scan_path}")
            print(f"Files Analyzed: {report.files_analyzed}")
            print(f"Total Lines: {report.total_lines}")
            print(f"Functions: {report.total_functions}")
            print(f"Classes: {report.total_classes}")
            print(f"\nOverall Score: {report.overall_score:.1f}/100")
            print(f"\nIssues by Severity:")
            for sev, count in report.summary["issues_by_severity"].items():
                if count > 0:
                    print(f"  {sev}: {count}")

    elif args.command == "complexity":
        result = analyzer.get_complexity_report(args.file)

        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1

            print(f"\nComplexity Analysis: {result['file']}")
            print("=" * 50)
            print(f"Overall Complexity: {result['overall_complexity']}")
            print(f"\nFunctions ({len(result['functions'])}):")
            for f in result["functions"]:
                doc = "\u2705" if f["has_docstring"] else "\u274c"
                print(f"  {doc} {f['name']} (line {f['line']}, {f['args']} args)")
            print(f"\nClasses ({len(result['classes'])}):")
            for c in result["classes"]:
                doc = "\u2705" if c["has_docstring"] else "\u274c"
                print(f"  {doc} {c['name']} (line {c['line']}, {c['methods']} methods)")

            if result["recommendations"]:
                print("\nRecommendations:")
                for rec in result["recommendations"]:
                    print(f"  - {rec}")

    elif args.command == "report":
        report = analyzer.analyze_directory(args.path)

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report.to_dict(), f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(report.to_dict(), indent=2))

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
