#!/usr/bin/env python3
"""
the system Log Aggregator

Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Core Tool

Aggregates and analyzes logs from multiple the system sources:
- LogBook entries from all agents
- Build logs
- Test output
- CI/CD pipeline logs

Provides:
- Log collection and normalization
- Pattern detection and alerting
- Trend analysis
- Report generation
"""

import os
import sys
import json
import yaml
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Generator
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, Counter
import hashlib

class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class LogSource(Enum):
    """Log source types."""
    PM = "pm"
    BUILDER = "builder"
    PLANNER = "planner"
    CRITIC = "critic"
    SYSTEM = "system"
    CI = "ci"
    TEST = "test"

@dataclass
class LogEntry:
    """Normalized log entry."""
    id: str
    timestamp: datetime
    source: LogSource
    level: LogLevel
    message: str
    file_path: str
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    raw_content: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value,
            "level": self.level.value,
            "message": self.message,
            "file_path": self.file_path,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "context": self.context,
        }

@dataclass
class LogPattern:
    """Detected log pattern."""
    pattern_id: str
    pattern: str
    count: int
    first_seen: datetime
    last_seen: datetime
    level: LogLevel
    sources: List[LogSource]
    sample_messages: List[str] = field(default_factory=list)

@dataclass
class AggregationResult:
    """Result of log aggregation."""
    total_entries: int
    entries_by_level: Dict[str, int]
    entries_by_source: Dict[str, int]
    time_range: Tuple[datetime, datetime]
    patterns: List[LogPattern]
    errors: List[LogEntry]
    warnings: List[LogEntry]

class LogParser:
    """Parses various log formats."""

    # Common log patterns
    TIMESTAMP_PATTERNS = [
        r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)',
        r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})',
        r'(\w{3} \d{1,2} \d{2}:\d{2}:\d{2})',
    ]

    LEVEL_PATTERNS = {
        LogLevel.DEBUG: r'\b(DEBUG|TRACE)\b',
        LogLevel.INFO: r'\b(INFO|NOTICE)\b',
        LogLevel.WARNING: r'\b(WARN(?:ING)?)\b',
        LogLevel.ERROR: r'\b(ERROR|ERR)\b',
        LogLevel.CRITICAL: r'\b(CRITICAL|FATAL|SEVERE)\b',
    }

    def parse_yaml_log(self, content: str, filepath: Path) -> List[LogEntry]:
        """Parse YAML formatted log file."""
        entries = []

        try:
            data = yaml.safe_load(content)
            if not data:
                return entries

            # Handle single entry or list
            if isinstance(data, dict):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    entry = self._parse_yaml_entry(item, filepath)
                    if entry:
                        entries.append(entry)

        except yaml.YAMLError:
            # Treat as plain text
            pass

        return entries

    def _parse_yaml_entry(self, data: Dict, filepath: Path) -> Optional[LogEntry]:
        """Parse a single YAML log entry."""
        try:
            # Extract timestamp
            timestamp_str = data.get('timestamp') or data.get('time') or data.get('date')
            if timestamp_str:
                timestamp = self._parse_timestamp(str(timestamp_str))
            else:
                timestamp = datetime.utcnow()

            # Extract level
            level_str = data.get('level') or data.get('severity') or 'info'
            level = self._parse_level(str(level_str))

            # Extract message
            message = data.get('message') or data.get('msg') or data.get('description') or str(data)

            # Extract source from filepath
            source = self._infer_source_from_path(filepath)

            # Generate ID
            entry_id = hashlib.md5(f"{timestamp.isoformat()}:{message[:100]}".encode()).hexdigest()[:12]

            return LogEntry(
                id=entry_id,
                timestamp=timestamp,
                source=source,
                level=level,
                message=str(message),
                file_path=str(filepath),
                agent_id=data.get('agent_id') or data.get('agent'),
                task_id=data.get('task_id') or data.get('task'),
                session_id=data.get('session_id') or data.get('session'),
                context=data.get('context') or data.get('metadata') or {},
            )
        except Exception:
            return None

    def parse_markdown_log(self, content: str, filepath: Path) -> List[LogEntry]:
        """Parse markdown formatted log file."""
        entries = []
        source = self._infer_source_from_path(filepath)

        # Split by headers or date patterns
        sections = re.split(r'\n(?=#{1,3} |\d{4}-\d{2}-\d{2})', content)

        for section in sections:
            if not section.strip():
                continue

            # Try to extract timestamp from header
            timestamp = datetime.utcnow()
            timestamp_match = re.search(self.TIMESTAMP_PATTERNS[0], section)
            if timestamp_match:
                timestamp = self._parse_timestamp(timestamp_match.group(1))

            # Determine level
            level = self._infer_level_from_content(section)

            # Get first line as message summary
            lines = section.strip().split('\n')
            message = lines[0].strip('#').strip() if lines else section[:200]

            entry_id = hashlib.md5(f"{timestamp.isoformat()}:{message[:50]}".encode()).hexdigest()[:12]

            entries.append(LogEntry(
                id=entry_id,
                timestamp=timestamp,
                source=source,
                level=level,
                message=message,
                file_path=str(filepath),
                raw_content=section[:1000],
            ))

        return entries

    def parse_text_log(self, content: str, filepath: Path) -> List[LogEntry]:
        """Parse plain text log file."""
        entries = []
        source = self._infer_source_from_path(filepath)

        for line in content.split('\n'):
            if not line.strip():
                continue

            # Try to extract timestamp
            timestamp = datetime.utcnow()
            for pattern in self.TIMESTAMP_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    timestamp = self._parse_timestamp(match.group(1))
                    break

            # Determine level
            level = self._infer_level_from_content(line)

            entry_id = hashlib.md5(f"{timestamp.isoformat()}:{line[:50]}".encode()).hexdigest()[:12]

            entries.append(LogEntry(
                id=entry_id,
                timestamp=timestamp,
                source=source,
                level=level,
                message=line.strip(),
                file_path=str(filepath),
            ))

        return entries

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse various timestamp formats."""
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        return datetime.utcnow()

    def _parse_level(self, level_str: str) -> LogLevel:
        """Parse log level from string."""
        level_upper = level_str.upper()

        if level_upper in ('DEBUG', 'TRACE'):
            return LogLevel.DEBUG
        elif level_upper in ('INFO', 'NOTICE'):
            return LogLevel.INFO
        elif level_upper in ('WARN', 'WARNING'):
            return LogLevel.WARNING
        elif level_upper in ('ERROR', 'ERR'):
            return LogLevel.ERROR
        elif level_upper in ('CRITICAL', 'FATAL', 'SEVERE'):
            return LogLevel.CRITICAL

        return LogLevel.INFO

    def _infer_level_from_content(self, content: str) -> LogLevel:
        """Infer log level from content."""
        content_upper = content.upper()

        for level, pattern in self.LEVEL_PATTERNS.items():
            if re.search(pattern, content_upper):
                return level

        # Check for error indicators
        if any(word in content_upper for word in ['FAIL', 'EXCEPTION', 'TRACEBACK']):
            return LogLevel.ERROR

        return LogLevel.INFO

    def _infer_source_from_path(self, filepath: Path) -> LogSource:
        """Infer log source from file path."""
        path_str = str(filepath).lower()

        if 'logbook/pm' in path_str:
            return LogSource.PM
        elif 'logbook/builder' in path_str:
            return LogSource.BUILDER
        elif 'logbook/planner' in path_str:
            return LogSource.PLANNER
        elif 'logbook/critic' in path_str:
            return LogSource.CRITIC
        elif '.github' in path_str or 'ci' in path_str:
            return LogSource.CI
        elif 'test' in path_str:
            return LogSource.TEST

        return LogSource.SYSTEM

class LogAggregator:
    """Aggregates and analyzes logs."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.parser = LogParser()
        self.entries: List[LogEntry] = []

    def collect_logs(
        self,
        directories: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        sources: Optional[List[LogSource]] = None,
    ) -> int:
        """Collect logs from specified directories."""
        if directories is None:
            directories = [
                "LogBook",
                ".github/workflows",
                "logs",
            ]

        collected = 0

        for dir_name in directories:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue

            for filepath in self._find_log_files(dir_path):
                entries = self._parse_file(filepath)

                for entry in entries:
                    # Apply filters
                    if since and entry.timestamp < since:
                        continue
                    if until and entry.timestamp > until:
                        continue
                    if sources and entry.source not in sources:
                        continue

                    self.entries.append(entry)
                    collected += 1

        return collected

    def _find_log_files(self, directory: Path) -> Generator[Path, None, None]:
        """Find all log files in directory."""
        extensions = ['.yaml', '.yml', '.md', '.log', '.txt']

        for ext in extensions:
            for filepath in directory.rglob(f"*{ext}"):
                if filepath.is_file():
                    yield filepath

    def _parse_file(self, filepath: Path) -> List[LogEntry]:
        """Parse a log file."""
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return []

        suffix = filepath.suffix.lower()

        if suffix in ['.yaml', '.yml']:
            return self.parser.parse_yaml_log(content, filepath)
        elif suffix == '.md':
            return self.parser.parse_markdown_log(content, filepath)
        else:
            return self.parser.parse_text_log(content, filepath)

    def aggregate(self) -> AggregationResult:
        """Aggregate collected logs."""
        if not self.entries:
            return AggregationResult(
                total_entries=0,
                entries_by_level={},
                entries_by_source={},
                time_range=(datetime.utcnow(), datetime.utcnow()),
                patterns=[],
                errors=[],
                warnings=[],
            )

        # Count by level
        level_counts = Counter(e.level.value for e in self.entries)

        # Count by source
        source_counts = Counter(e.source.value for e in self.entries)

        # Time range
        timestamps = [e.timestamp for e in self.entries]
        time_range = (min(timestamps), max(timestamps))

        # Extract errors and warnings
        errors = [e for e in self.entries if e.level == LogLevel.ERROR]
        warnings = [e for e in self.entries if e.level == LogLevel.WARNING]
        critical = [e for e in self.entries if e.level == LogLevel.CRITICAL]
        errors.extend(critical)

        # Detect patterns
        patterns = self._detect_patterns()

        return AggregationResult(
            total_entries=len(self.entries),
            entries_by_level=dict(level_counts),
            entries_by_source=dict(source_counts),
            time_range=time_range,
            patterns=patterns,
            errors=errors[:100],  # Limit to most recent 100
            warnings=warnings[:100],
        )

    def _detect_patterns(self) -> List[LogPattern]:
        """Detect recurring patterns in logs."""
        patterns: Dict[str, LogPattern] = {}

        # Simple pattern detection based on message prefixes
        for entry in self.entries:
            # Normalize message for pattern detection
            normalized = self._normalize_message(entry.message)
            pattern_key = hashlib.md5(normalized.encode()).hexdigest()[:8]

            if pattern_key in patterns:
                patterns[pattern_key].count += 1
                patterns[pattern_key].last_seen = max(patterns[pattern_key].last_seen, entry.timestamp)
                if entry.source not in patterns[pattern_key].sources:
                    patterns[pattern_key].sources.append(entry.source)
            else:
                patterns[pattern_key] = LogPattern(
                    pattern_id=pattern_key,
                    pattern=normalized[:100],
                    count=1,
                    first_seen=entry.timestamp,
                    last_seen=entry.timestamp,
                    level=entry.level,
                    sources=[entry.source],
                    sample_messages=[entry.message[:200]],
                )

        # Return patterns sorted by count
        return sorted(patterns.values(), key=lambda p: p.count, reverse=True)[:50]

    def _normalize_message(self, message: str) -> str:
        """Normalize message for pattern detection."""
        # Replace numbers, IDs, timestamps with placeholders
        normalized = re.sub(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*\b', '<TIMESTAMP>', message)
        normalized = re.sub(r'\b[0-9a-f]{8,}\b', '<ID>', normalized)
        normalized = re.sub(r'\b\d+\b', '<NUM>', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized.strip()[:200]

    def generate_report(self, result: AggregationResult, format: str = "markdown") -> str:
        """Generate a report from aggregation result."""
        if format == "json":
            return self._generate_json_report(result)
        else:
            return self._generate_markdown_report(result)

    def _generate_markdown_report(self, result: AggregationResult) -> str:
        """Generate markdown report."""
        lines = [
            "# the system Log Aggregation Report",
            "",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            f"**Total Entries:** {result.total_entries:,}",
            f"**Time Range:** {result.time_range[0].isoformat()} to {result.time_range[1].isoformat()}",
            "",
            "---",
            "",
            "## Summary by Level",
            "",
            "| Level | Count |",
            "|-------|-------|",
        ]

        for level, count in sorted(result.entries_by_level.items()):
            lines.append(f"| {level} | {count:,} |")

        lines.extend([
            "",
            "## Summary by Source",
            "",
            "| Source | Count |",
            "|--------|-------|",
        ])

        for source, count in sorted(result.entries_by_source.items()):
            lines.append(f"| {source} | {count:,} |")

        if result.errors:
            lines.extend([
                "",
                "## Recent Errors",
                "",
            ])
            for error in result.errors[:10]:
                lines.append(f"- **[{error.timestamp.isoformat()}]** {error.message[:100]}")

        if result.patterns:
            lines.extend([
                "",
                "## Recurring Patterns",
                "",
                "| Pattern | Count | Level |",
                "|---------|-------|-------|",
            ])
            for pattern in result.patterns[:10]:
                lines.append(f"| {pattern.pattern[:50]}... | {pattern.count} | {pattern.level.value} |")

        return "\n".join(lines)

    def _generate_json_report(self, result: AggregationResult) -> str:
        """Generate JSON report."""
        data = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_entries": result.total_entries,
            "entries_by_level": result.entries_by_level,
            "entries_by_source": result.entries_by_source,
            "time_range": {
                "start": result.time_range[0].isoformat(),
                "end": result.time_range[1].isoformat(),
            },
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "pattern_count": len(result.patterns),
        }

        return json.dumps(data, indent=2)

    def query(
        self,
        level: Optional[LogLevel] = None,
        source: Optional[LogSource] = None,
        pattern: Optional[str] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Query collected logs."""
        results = self.entries

        if level:
            results = [e for e in results if e.level == level]

        if source:
            results = [e for e in results if e.source == source]

        if pattern:
            regex = re.compile(pattern, re.IGNORECASE)
            results = [e for e in results if regex.search(e.message)]

        # Sort by timestamp descending
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)

        return results[:limit]

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="the system Log Aggregator")

    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Collect command
    collect_parser = subparsers.add_parser("collect", help="Collect and aggregate logs")
    collect_parser.add_argument("--dirs", nargs="+", help="Directories to scan")
    collect_parser.add_argument("--since", help="Only logs after this date (ISO format)")
    collect_parser.add_argument("--until", help="Only logs before this date (ISO format)")
    collect_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    collect_parser.add_argument("--output", "-o", help="Output file")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query logs")
    query_parser.add_argument("--level", choices=["debug", "info", "warning", "error", "critical"])
    query_parser.add_argument("--source", choices=["pm", "builder", "planner", "critic", "system", "ci", "test"])
    query_parser.add_argument("--pattern", help="Regex pattern to search")
    query_parser.add_argument("--limit", type=int, default=50)

    # Stats command
    subparsers.add_parser("stats", help="Show log statistics")

    args = parser.parse_args()

    aggregator = LogAggregator(args.project_root)

    if args.command == "collect":
        since = datetime.fromisoformat(args.since) if args.since else None
        until = datetime.fromisoformat(args.until) if args.until else None

        count = aggregator.collect_logs(
            directories=args.dirs,
            since=since,
            until=until,
        )

        print(f"Collected {count} log entries")

        result = aggregator.aggregate()
        report = aggregator.generate_report(result, format=args.format)

        if args.output:
            Path(args.output).write_text(report)
            print(f"Report written to: {args.output}")
        else:
            print(report)

    elif args.command == "query":
        aggregator.collect_logs()

        level = LogLevel(args.level) if args.level else None
        source = LogSource(args.source) if args.source else None

        entries = aggregator.query(
            level=level,
            source=source,
            pattern=args.pattern,
            limit=args.limit,
        )

        for entry in entries:
            print(f"[{entry.timestamp.isoformat()}] [{entry.level.value}] {entry.message[:100]}")

    elif args.command == "stats":
        count = aggregator.collect_logs()
        result = aggregator.aggregate()

        print(f"Total entries: {result.total_entries}")
        print(f"Errors: {len(result.errors)}")
        print(f"Warnings: {len(result.warnings)}")
        print(f"Patterns detected: {len(result.patterns)}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
