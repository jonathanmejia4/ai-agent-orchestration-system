#!/usr/bin/env python3
"""
Breaking Change Frequency Analyzer
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Change Management

Analyzes git history to track breaking change frequency.
Helps identify stability patterns and high-churn areas.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class BreakingChange:
    """A breaking change detected in git history."""
    commit_hash: str
    author: str
    date: datetime
    message: str
    files_changed: List[str]
    change_type: str  # "api", "schema", "interface", "config", "unknown"
    severity: str = "major"  # "major", "minor", "patch"

@dataclass
class FileStats:
    """Statistics for a file's breaking changes."""
    file_path: str
    total_breaking_changes: int
    last_breaking_change: Optional[datetime]
    change_frequency: float  # Changes per month
    authors: List[str] = field(default_factory=list)

@dataclass
class AnalysisResult:
    """Result of breaking change analysis."""
    total_commits_analyzed: int
    breaking_changes_found: int
    time_period_days: int
    avg_changes_per_month: float
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    file_stats: Dict[str, FileStats] = field(default_factory=dict)
    hotspots: List[str] = field(default_factory=list)

class BreakingChangeAnalyzer:
    """Analyzes git history for breaking changes."""

    # Patterns that indicate breaking changes
    BREAKING_PATTERNS = [
        # Commit message patterns
        (re.compile(r'BREAKING[:\s]', re.IGNORECASE), "explicit"),
        (re.compile(r'!\s*:', re.IGNORECASE), "conventional"),  # feat!:
        (re.compile(r'breaking change', re.IGNORECASE), "explicit"),
        (re.compile(r'backwards?\s*incompatible', re.IGNORECASE), "explicit"),
        (re.compile(r'removes?\s+(?:deprecated|support)', re.IGNORECASE), "deprecation"),
        (re.compile(r'(?:major|breaking)\s+refactor', re.IGNORECASE), "refactor"),
        (re.compile(r'(?:api|schema|interface)\s+change', re.IGNORECASE), "api"),
        (re.compile(r'migration\s+required', re.IGNORECASE), "migration"),
    ]

    # File patterns that are more likely to contain breaking changes
    SENSITIVE_PATHS = [
        (re.compile(r'api/'), "api"),
        (re.compile(r'schema'), "schema"),
        (re.compile(r'interface'), "interface"),
        (re.compile(r'config'), "config"),
        (re.compile(r'\.proto$'), "schema"),
        (re.compile(r'openapi|swagger', re.IGNORECASE), "api"),
        (re.compile(r'types\.'), "interface"),
    ]

    def __init__(self, repo_path: str = "."):
        """
        Initialize analyzer.

        Args:
            repo_path: Path to git repository
        """
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> Optional[str]:
        """Run a git command."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception:
            return None

    def _parse_git_log(self, since_days: int = 90) -> List[Dict[str, Any]]:
        """Parse git log for commits."""
        since_date = (datetime.now() - timedelta(days=since_days)).strftime('%Y-%m-%d')

        output = self._run_git([
            "log",
            f"--since={since_date}",
            "--pretty=format:%H|%an|%ai|%s",
            "--name-only"
        ])

        if not output:
            return []

        commits = []
        current_commit = None

        for line in output.split('\n'):
            if '|' in line and len(line.split('|')) == 4:
                # New commit line
                if current_commit:
                    commits.append(current_commit)

                parts = line.split('|')
                try:
                    date = datetime.fromisoformat(parts[2].strip().replace(' ', 'T')[:19])
                except ValueError:
                    date = datetime.now()

                current_commit = {
                    'hash': parts[0].strip(),
                    'author': parts[1].strip(),
                    'date': date,
                    'message': parts[3].strip(),
                    'files': []
                }
            elif line.strip() and current_commit:
                # File line
                current_commit['files'].append(line.strip())

        if current_commit:
            commits.append(current_commit)

        return commits

    def _is_breaking_change(self, commit: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Determine if a commit is a breaking change.

        Returns:
            Tuple of (is_breaking, change_type)
        """
        message = commit['message']

        # Check message patterns
        for pattern, change_type in self.BREAKING_PATTERNS:
            if pattern.search(message):
                return True, change_type

        # Check for sensitive file changes with significant modification
        # Track potential breaking changes from sensitive path matches
        sensitive_match_type = None
        for file_path in commit['files']:
            for pattern, change_type in self.SENSITIVE_PATHS:
                if pattern.search(file_path):
                    # Sensitive path detected - mark as potential breaking change
                    sensitive_match_type = change_type
                    break
            if sensitive_match_type:
                break

        # If sensitive path matched, return it as a potential breaking change
        if sensitive_match_type:
            return True, sensitive_match_type

        return False, "unknown"

    def _classify_severity(self, commit: Dict[str, Any], change_type: str) -> str:
        """Classify the severity of a breaking change."""
        message = commit['message'].lower()

        if 'major' in message or 'breaking' in message:
            return "major"
        if 'minor' in message:
            return "minor"
        if 'patch' in message or 'fix' in message:
            return "patch"

        # Default based on change type
        severity_map = {
            "api": "major",
            "schema": "major",
            "interface": "major",
            "config": "minor",
            "deprecation": "minor",
            "refactor": "minor",
            "migration": "major",
        }
        return severity_map.get(change_type, "major")

    def analyze(
        self,
        since_days: int = 90,
        include_potential: bool = False
    ) -> AnalysisResult:
        """
        Analyze git history for breaking changes.

        Args:
            since_days: Number of days to look back
            include_potential: Include potential (unconfirmed) breaking changes

        Returns:
            AnalysisResult
        """
        commits = self._parse_git_log(since_days)

        result = AnalysisResult(
            total_commits_analyzed=len(commits),
            breaking_changes_found=0,
            time_period_days=since_days,
            avg_changes_per_month=0.0
        )

        file_changes: Dict[str, List[BreakingChange]] = defaultdict(list)

        for commit in commits:
            is_breaking, change_type = self._is_breaking_change(commit)

            if is_breaking:
                severity = self._classify_severity(commit, change_type)

                breaking_change = BreakingChange(
                    commit_hash=commit['hash'][:8],
                    author=commit['author'],
                    date=commit['date'],
                    message=commit['message'],
                    files_changed=commit['files'],
                    change_type=change_type,
                    severity=severity
                )

                result.breaking_changes.append(breaking_change)
                result.breaking_changes_found += 1

                for file_path in commit['files']:
                    file_changes[file_path].append(breaking_change)

        # Calculate statistics
        months = since_days / 30.0
        if months > 0:
            result.avg_changes_per_month = result.breaking_changes_found / months

        # Generate file stats
        for file_path, changes in file_changes.items():
            last_change = max(c.date for c in changes) if changes else None
            authors = list(set(c.author for c in changes))

            result.file_stats[file_path] = FileStats(
                file_path=file_path,
                total_breaking_changes=len(changes),
                last_breaking_change=last_change,
                change_frequency=len(changes) / months if months > 0 else 0,
                authors=authors
            )

        # Identify hotspots (files with high breaking change frequency)
        hotspot_threshold = 2  # More than 2 breaking changes in period
        result.hotspots = [
            path for path, stats in result.file_stats.items()
            if stats.total_breaking_changes >= hotspot_threshold
        ]

        # Sort by frequency
        result.hotspots.sort(
            key=lambda p: result.file_stats[p].total_breaking_changes,
            reverse=True
        )

        return result

    def generate_report(self, result: AnalysisResult) -> str:
        """Generate a markdown report."""
        lines = [
            "# Breaking Change Analysis Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Summary",
            f"- Analysis period: {result.time_period_days} days",
            f"- Total commits analyzed: {result.total_commits_analyzed}",
            f"- Breaking changes found: {result.breaking_changes_found}",
            f"- Average per month: {result.avg_changes_per_month:.2f}",
            ""
        ]

        if result.hotspots:
            lines.append("## Hotspots (High Churn Areas)")
            lines.append("")
            for path in result.hotspots[:10]:
                stats = result.file_stats[path]
                lines.append(f"- `{path}`: {stats.total_breaking_changes} breaking changes")
            lines.append("")

        if result.breaking_changes:
            lines.append("## Recent Breaking Changes")
            lines.append("")

            # Group by severity
            by_severity = defaultdict(list)
            for change in result.breaking_changes:
                by_severity[change.severity].append(change)

            for severity in ["major", "minor", "patch"]:
                changes = by_severity.get(severity, [])
                if changes:
                    lines.append(f"### {severity.title()} Changes ({len(changes)})")
                    lines.append("")
                    for change in changes[:5]:
                        lines.append(f"- **{change.commit_hash}** ({change.date.strftime('%Y-%m-%d')})")
                        lines.append(f"  {change.message}")
                        lines.append(f"  By: {change.author}")
                        lines.append("")

        return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze breaking change frequency in git history"
    )
    parser.add_argument("-d", "--days", type=int, default=90,
                        help="Days to analyze")
    parser.add_argument("-r", "--repo", default=".",
                        help="Repository path")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("--report", help="Write report to file")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    analyzer = BreakingChangeAnalyzer(repo_path=args.repo)
    result = analyzer.analyze(since_days=args.days)

    if args.json:
        output = {
            "total_commits": result.total_commits_analyzed,
            "breaking_changes": result.breaking_changes_found,
            "period_days": result.time_period_days,
            "avg_per_month": result.avg_changes_per_month,
            "hotspots": result.hotspots[:10],
            "changes": [
                {
                    "hash": c.commit_hash,
                    "date": c.date.isoformat(),
                    "author": c.author,
                    "message": c.message,
                    "type": c.change_type,
                    "severity": c.severity
                }
                for c in result.breaking_changes
            ] if args.verbose else []
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Analysis period: {result.time_period_days} days")
        print(f"Commits analyzed: {result.total_commits_analyzed}")
        print(f"Breaking changes: {result.breaking_changes_found}")
        print(f"Average per month: {result.avg_changes_per_month:.2f}")

        if result.hotspots:
            print(f"\nHotspots:")
            for path in result.hotspots[:5]:
                stats = result.file_stats[path]
                print(f"  {path}: {stats.total_breaking_changes} changes")

        if args.verbose and result.breaking_changes:
            print(f"\nRecent breaking changes:")
            for change in result.breaking_changes[:10]:
                print(f"  {change.commit_hash} - {change.message[:50]}...")

    if args.report:
        report = analyzer.generate_report(result)
        with open(args.report, 'w') as f:
            f.write(report)
        print(f"\nReport written to: {args.report}")

    # Exit with 1 if there are recent major breaking changes
    major_count = sum(1 for c in result.breaking_changes if c.severity == "major")
    sys.exit(1 if major_count > 0 else 0)

if __name__ == "__main__":
    main()
