#!/usr/bin/env python3
"""
Daily Digest Generator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: MEDIUM - Reporting

Generates daily digest reports of the system activity.
Summarizes commits, issues, deployments, and metrics.
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass
class CommitSummary:
    """Summary of a commit."""
    hash: str
    author: str
    message: str
    files_changed: int
    timestamp: datetime

@dataclass
class IssueSummary:
    """Summary of an issue."""
    id: str
    title: str
    status: str
    priority: str

@dataclass
class MetricsSummary:
    """Summary of metrics."""
    tests_passed: int = 0
    tests_failed: int = 0
    coverage_percent: float = 0.0
    build_duration_seconds: int = 0
    issues_resolved: int = 0
    issues_opened: int = 0

@dataclass
class DailyDigest:
    """A daily digest report."""
    date: str
    commits: List[CommitSummary] = field(default_factory=list)
    issues: List[IssueSummary] = field(default_factory=list)
    metrics: MetricsSummary = field(default_factory=MetricsSummary)
    highlights: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class DigestGenerator:
    """Generates daily digest reports."""

    def __init__(self, repo_path: str = "."):
        """
        Initialize generator.

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

    def _get_commits(self, since: datetime) -> List[CommitSummary]:
        """Get commits since a date."""
        since_str = since.strftime('%Y-%m-%d')

        output = self._run_git([
            "log",
            f"--since={since_str}",
            "--pretty=format:%H|%an|%ai|%s",
            "--shortstat"
        ])

        if not output:
            return []

        commits = []
        lines = output.strip().split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if '|' in line and len(line.split('|')) == 4:
                parts = line.split('|')
                try:
                    timestamp = datetime.fromisoformat(
                        parts[2].strip().replace(' ', 'T')[:19]
                    )
                except ValueError:
                    timestamp = datetime.now()

                # Get files changed from next line
                files_changed = 0
                if i + 1 < len(lines) and 'file' in lines[i + 1]:
                    stat_line = lines[i + 1]
                    import re
                    match = re.search(r'(\d+) file', stat_line)
                    if match:
                        files_changed = int(match.group(1))
                    i += 1

                commits.append(CommitSummary(
                    hash=parts[0].strip()[:8],
                    author=parts[1].strip(),
                    message=parts[3].strip()[:100],
                    files_changed=files_changed,
                    timestamp=timestamp
                ))

            i += 1

        return commits

    def _get_issues_from_catalog(self) -> List[IssueSummary]:
        """Get issues from ISSUE_CATALOG.md."""
        catalog_path = os.path.join(self.repo_path, "ISSUE_CATALOG.md")
        if not os.path.exists(catalog_path):
            return []

        issues = []
        try:
            with open(catalog_path, 'r') as f:
                content = f.read()

            import re
            # Find issue headers
            issue_pattern = re.compile(
                r'###\s+(A\d+):\s+(.+?)\n.*?'
                r'\*\*Status:\*\*\s*(.*?)\n',
                re.DOTALL
            )

            for match in issue_pattern.finditer(content[:50000]):  # First 50K chars
                status = match.group(3).strip()
                # Only include recent/active issues
                if 'NOT RESOLVED' in status:
                    issues.append(IssueSummary(
                        id=match.group(1),
                        title=match.group(2).strip()[:50],
                        status="open",
                        priority="normal"
                    ))

        except Exception:
            pass

        return issues[:20]  # Limit to 20 issues

    def _calculate_metrics(
        self,
        commits: List[CommitSummary],
        issues: List[IssueSummary]
    ) -> MetricsSummary:
        """Calculate daily metrics."""
        metrics = MetricsSummary()

        # Count issues
        metrics.issues_opened = len([i for i in issues if i.status == "open"])

        # Estimate resolved from commit messages
        for commit in commits:
            msg = commit.message.lower()
            if 'resolved' in msg or 'fixed' in msg or 'closes' in msg:
                metrics.issues_resolved += 1

        return metrics

    def _generate_highlights(
        self,
        commits: List[CommitSummary],
        issues: List[IssueSummary],
        metrics: MetricsSummary
    ) -> List[str]:
        """Generate digest highlights."""
        highlights = []

        if commits:
            highlights.append(f"📝 {len(commits)} commits today")

            # Top contributors
            authors = {}
            for c in commits:
                authors[c.author] = authors.get(c.author, 0) + 1

            if authors:
                top_author = max(authors.items(), key=lambda x: x[1])
                highlights.append(f"👤 Top contributor: {top_author[0]} ({top_author[1]} commits)")

        if metrics.issues_resolved > 0:
            highlights.append(f"✅ {metrics.issues_resolved} issues resolved")

        if metrics.issues_opened > 0:
            highlights.append(f"📋 {metrics.issues_opened} open issues")

        return highlights

    def _generate_warnings(
        self,
        commits: List[CommitSummary],
        issues: List[IssueSummary]
    ) -> List[str]:
        """Generate warnings."""
        warnings = []

        # Check for breaking changes
        for commit in commits:
            if 'BREAKING' in commit.message.upper():
                warnings.append(f"⚠️ Breaking change: {commit.message[:50]}")

        # Check for critical issues
        critical = [i for i in issues if i.priority == "critical"]
        if critical:
            warnings.append(f"🔴 {len(critical)} critical issues open")

        return warnings

    def generate(self, date: Optional[datetime] = None) -> DailyDigest:
        """
        Generate a daily digest.

        Args:
            date: Date to generate digest for (default: today)

        Returns:
            DailyDigest
        """
        if date is None:
            date = datetime.now()

        since = date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Gather data
        commits = self._get_commits(since)
        issues = self._get_issues_from_catalog()
        metrics = self._calculate_metrics(commits, issues)
        highlights = self._generate_highlights(commits, issues, metrics)
        warnings = self._generate_warnings(commits, issues)

        return DailyDigest(
            date=date.strftime('%Y-%m-%d'),
            commits=commits,
            issues=issues,
            metrics=metrics,
            highlights=highlights,
            warnings=warnings
        )

    def format_markdown(self, digest: DailyDigest) -> str:
        """Format digest as markdown."""
        lines = [
            f"# Daily Digest - {digest.date}",
            f"Generated: {datetime.now().isoformat()}",
            "",
        ]

        if digest.highlights:
            lines.append("## Highlights")
            for h in digest.highlights:
                lines.append(f"- {h}")
            lines.append("")

        if digest.warnings:
            lines.append("## Warnings")
            for w in digest.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if digest.commits:
            lines.append("## Commits")
            for c in digest.commits[:10]:
                lines.append(f"- `{c.hash}` {c.message} ({c.author})")
            if len(digest.commits) > 10:
                lines.append(f"- ... and {len(digest.commits) - 10} more")
            lines.append("")

        if digest.issues:
            lines.append("## Open Issues")
            for i in digest.issues[:10]:
                lines.append(f"- [{i.id}] {i.title}")
            if len(digest.issues) > 10:
                lines.append(f"- ... and {len(digest.issues) - 10} more")
            lines.append("")

        lines.append("## Metrics")
        lines.append(f"- Issues resolved: {digest.metrics.issues_resolved}")
        lines.append(f"- Issues opened: {digest.metrics.issues_opened}")
        lines.append("")

        return '\n'.join(lines)

    def format_json(self, digest: DailyDigest) -> str:
        """Format digest as JSON."""
        return json.dumps({
            "date": digest.date,
            "highlights": digest.highlights,
            "warnings": digest.warnings,
            "commits": [
                {
                    "hash": c.hash,
                    "author": c.author,
                    "message": c.message,
                    "files_changed": c.files_changed
                }
                for c in digest.commits
            ],
            "issues": [
                {
                    "id": i.id,
                    "title": i.title,
                    "status": i.status
                }
                for i in digest.issues
            ],
            "metrics": {
                "issues_resolved": digest.metrics.issues_resolved,
                "issues_opened": digest.metrics.issues_opened
            }
        }, indent=2)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate daily digest report"
    )
    parser.add_argument("-r", "--repo", default=".",
                        help="Repository path")
    parser.add_argument("-d", "--date", help="Date (YYYY-MM-DD)")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("--format", choices=["markdown", "json"],
                        default="markdown", help="Output format")

    args = parser.parse_args()

    generator = DigestGenerator(repo_path=args.repo)

    date = None
    if args.date:
        date = datetime.fromisoformat(args.date)

    digest = generator.generate(date)

    if args.format == "json":
        output = generator.format_json(digest)
    else:
        output = generator.format_markdown(digest)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Digest written to: {args.output}")
    else:
        print(output)

if __name__ == "__main__":
    main()
