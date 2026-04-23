#!/usr/bin/env python3
"""
performance_profiler.py - the system Performance Profiler

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Analysis Tool

Purpose:
    Profiles the system performance including:
    - Tool execution times
    - Workflow bottlenecks
    - Resource usage
    - Agent performance metrics

Usage:
    python3 performance_profiler.py profile --tool validate_work_order.py
    python3 performance_profiler.py analyze --logs LogBook/
    python3 performance_profiler.py report --period weekly
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class ExecutionProfile:
    """Profile for a single execution."""
    profile_id: str
    command: str
    start_time: str
    end_time: str
    duration_ms: int
    exit_code: int
    memory_peak_mb: float
    cpu_time_ms: int
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "command": self.command,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "memory_peak_mb": self.memory_peak_mb,
            "cpu_time_ms": self.cpu_time_ms,
            "success": self.success,
            "metadata": self.metadata
        }

@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""
    period: str
    start_date: str
    end_date: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    max_duration_ms: float
    min_duration_ms: float
    total_cpu_time_ms: int
    avg_memory_mb: float
    by_command: Dict[str, Dict[str, Any]]

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.successful_executions / max(1, self.total_executions) * 100,
            "duration": {
                "avg_ms": self.avg_duration_ms,
                "p50_ms": self.p50_duration_ms,
                "p95_ms": self.p95_duration_ms,
                "p99_ms": self.p99_duration_ms,
                "max_ms": self.max_duration_ms,
                "min_ms": self.min_duration_ms
            },
            "resources": {
                "total_cpu_time_ms": self.total_cpu_time_ms,
                "avg_memory_mb": self.avg_memory_mb
            },
            "by_command": self.by_command
        }

class PerformanceProfiler:
    """Profiles the system performance."""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.profiles: List[ExecutionProfile] = []
        self._load_profiles()

    def _load_profiles(self):
        """Load existing profiles from logs."""
        profiles_file = self.base_path / "LogBook" / "shared" / "performance_profiles.yaml"
        if profiles_file.exists() and HAS_YAML:
            try:
                with open(profiles_file) as f:
                    data = yaml.safe_load(f) or {}
                for p in data.get("profiles", []):
                    self.profiles.append(ExecutionProfile(
                        profile_id=p.get("profile_id"),
                        command=p.get("command"),
                        start_time=p.get("start_time"),
                        end_time=p.get("end_time"),
                        duration_ms=p.get("duration_ms", 0),
                        exit_code=p.get("exit_code", 0),
                        memory_peak_mb=p.get("memory_peak_mb", 0),
                        cpu_time_ms=p.get("cpu_time_ms", 0),
                        success=p.get("success", True),
                        metadata=p.get("metadata", {})
                    ))
            except Exception:
                pass

    def _save_profiles(self):
        """Save profiles to log file."""
        if not HAS_YAML:
            return

        profiles_dir = self.base_path / "LogBook" / "shared"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        profiles_file = profiles_dir / "performance_profiles.yaml"

        data = {
            "profiles": [p.to_dict() for p in self.profiles[-1000:]],  # Keep last 1000
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

        with open(profiles_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def _generate_profile_id(self) -> str:
        """Generate unique profile ID."""
        return f"PROF-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    def profile_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        timeout: int = 300
    ) -> ExecutionProfile:
        """Profile a command execution."""
        import resource

        profile_id = self._generate_profile_id()
        full_command = command if not args else f"{command} {' '.join(args)}"

        start_time = datetime.utcnow()
        start_resources = resource.getrusage(resource.RUSAGE_CHILDREN)

        try:
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                timeout=timeout
            )
            exit_code = result.returncode
            success = exit_code == 0
        except subprocess.TimeoutExpired:
            exit_code = -1
            success = False
        except Exception as e:
            exit_code = -2
            success = False

        end_time = datetime.utcnow()
        end_resources = resource.getrusage(resource.RUSAGE_CHILDREN)

        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        cpu_time_ms = int(
            (end_resources.ru_utime - start_resources.ru_utime +
             end_resources.ru_stime - start_resources.ru_stime) * 1000
        )
        memory_peak_mb = end_resources.ru_maxrss / 1024  # Convert to MB

        profile = ExecutionProfile(
            profile_id=profile_id,
            command=full_command,
            start_time=start_time.isoformat() + "Z",
            end_time=end_time.isoformat() + "Z",
            duration_ms=duration_ms,
            exit_code=exit_code,
            memory_peak_mb=memory_peak_mb,
            cpu_time_ms=cpu_time_ms,
            success=success
        )

        self.profiles.append(profile)
        self._save_profiles()

        return profile

    def analyze_logs(self, logs_path: Optional[str] = None) -> List[ExecutionProfile]:
        """Analyze execution logs for performance data."""
        log_dir = Path(logs_path) if logs_path else self.base_path / "LogBook"
        analyzed = []

        for log_file in log_dir.rglob("execution_log.yaml"):
            if not HAS_YAML:
                continue

            try:
                with open(log_file) as f:
                    data = yaml.safe_load(f) or {}

                for entry in data.get("entries", []):
                    start = entry.get("start_time", entry.get("timestamp"))
                    end = entry.get("end_time")

                    if start and end:
                        try:
                            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                        except:
                            duration_ms = entry.get("duration_ms", 0)
                    else:
                        duration_ms = entry.get("duration_ms", 0)

                    profile = ExecutionProfile(
                        profile_id=entry.get("entry_id", self._generate_profile_id()),
                        command=entry.get("operation", "unknown"),
                        start_time=start or "",
                        end_time=end or "",
                        duration_ms=duration_ms,
                        exit_code=0 if entry.get("status") == "success" else 1,
                        memory_peak_mb=0,
                        cpu_time_ms=0,
                        success=entry.get("status") == "success",
                        metadata={"source": str(log_file)}
                    )
                    analyzed.append(profile)

            except Exception:
                pass

        return analyzed

    def calculate_metrics(
        self,
        period: str = "all",
        command_filter: Optional[str] = None
    ) -> PerformanceMetrics:
        """Calculate aggregated performance metrics."""
        now = datetime.utcnow()

        # Determine date range
        if period == "daily":
            start_date = now - timedelta(days=1)
        elif period == "weekly":
            start_date = now - timedelta(weeks=1)
        elif period == "monthly":
            start_date = now - timedelta(days=30)
        else:
            start_date = datetime.min

        # Filter profiles
        filtered = []
        for p in self.profiles:
            try:
                p_time = datetime.fromisoformat(p.start_time.replace("Z", "+00:00").replace("+00:00", ""))
                if p_time >= start_date:
                    if not command_filter or command_filter in p.command:
                        filtered.append(p)
            except:
                pass

        if not filtered:
            return PerformanceMetrics(
                period=period,
                start_date=start_date.isoformat() + "Z",
                end_date=now.isoformat() + "Z",
                total_executions=0,
                successful_executions=0,
                failed_executions=0,
                avg_duration_ms=0,
                p50_duration_ms=0,
                p95_duration_ms=0,
                p99_duration_ms=0,
                max_duration_ms=0,
                min_duration_ms=0,
                total_cpu_time_ms=0,
                avg_memory_mb=0,
                by_command={}
            )

        # Calculate metrics
        durations = sorted([p.duration_ms for p in filtered])
        n = len(durations)

        def percentile(data: List[float], p: float) -> float:
            k = (len(data) - 1) * (p / 100)
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (data[c] - data[f]) * (k - f)

        # Group by command
        by_command: Dict[str, Dict[str, Any]] = {}
        for p in filtered:
            cmd_key = p.command.split()[0] if p.command else "unknown"
            if cmd_key not in by_command:
                by_command[cmd_key] = {
                    "count": 0,
                    "success": 0,
                    "failed": 0,
                    "total_duration_ms": 0,
                    "durations": []
                }
            by_command[cmd_key]["count"] += 1
            by_command[cmd_key]["total_duration_ms"] += p.duration_ms
            by_command[cmd_key]["durations"].append(p.duration_ms)
            if p.success:
                by_command[cmd_key]["success"] += 1
            else:
                by_command[cmd_key]["failed"] += 1

        # Calculate per-command metrics
        for cmd, stats in by_command.items():
            stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
            stats["success_rate"] = stats["success"] / stats["count"] * 100
            del stats["durations"]  # Remove raw data

        return PerformanceMetrics(
            period=period,
            start_date=start_date.isoformat() + "Z",
            end_date=now.isoformat() + "Z",
            total_executions=n,
            successful_executions=sum(1 for p in filtered if p.success),
            failed_executions=sum(1 for p in filtered if not p.success),
            avg_duration_ms=sum(durations) / n,
            p50_duration_ms=percentile(durations, 50),
            p95_duration_ms=percentile(durations, 95),
            p99_duration_ms=percentile(durations, 99),
            max_duration_ms=max(durations),
            min_duration_ms=min(durations),
            total_cpu_time_ms=sum(p.cpu_time_ms for p in filtered),
            avg_memory_mb=sum(p.memory_peak_mb for p in filtered) / n,
            by_command=by_command
        )

    def get_slow_operations(
        self,
        threshold_ms: int = 5000,
        limit: int = 20
    ) -> List[ExecutionProfile]:
        """Get operations exceeding duration threshold."""
        slow = [p for p in self.profiles if p.duration_ms > threshold_ms]
        slow.sort(key=lambda p: p.duration_ms, reverse=True)
        return slow[:limit]

def main():
    parser = argparse.ArgumentParser(description="the system Performance Profiler")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Profile a command")
    profile_parser.add_argument("--tool", required=True, help="Tool/command to profile")
    profile_parser.add_argument("--args", nargs="*", help="Command arguments")
    profile_parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze logs")
    analyze_parser.add_argument("--logs", help="Logs directory")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("--period", choices=["daily", "weekly", "monthly", "all"], default="weekly")
    report_parser.add_argument("--command", help="Filter by command")
    report_parser.add_argument("--output", "-o", help="Output file")

    # Slow command
    slow_parser = subparsers.add_parser("slow", help="Find slow operations")
    slow_parser.add_argument("--threshold", type=int, default=5000, help="Threshold in ms")
    slow_parser.add_argument("--limit", type=int, default=20, help="Max results")

    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    profiler = PerformanceProfiler()

    if args.command == "profile":
        profile = profiler.profile_command(args.tool, args.args, args.timeout)

        if args.format == "json":
            print(json.dumps(profile.to_dict(), indent=2))
        else:
            icon = "\u2705" if profile.success else "\u274c"
            print(f"\n{icon} Profile: {profile.profile_id}")
            print(f"   Command: {profile.command}")
            print(f"   Duration: {profile.duration_ms}ms")
            print(f"   CPU Time: {profile.cpu_time_ms}ms")
            print(f"   Memory Peak: {profile.memory_peak_mb:.1f}MB")
            print(f"   Exit Code: {profile.exit_code}")

    elif args.command == "analyze":
        profiles = profiler.analyze_logs(args.logs)

        if args.format == "json":
            print(json.dumps([p.to_dict() for p in profiles], indent=2))
        else:
            print(f"\nAnalyzed {len(profiles)} executions")
            if profiles:
                durations = [p.duration_ms for p in profiles]
                print(f"  Avg Duration: {sum(durations)/len(durations):.0f}ms")
                print(f"  Max Duration: {max(durations)}ms")
                print(f"  Success Rate: {sum(1 for p in profiles if p.success)/len(profiles)*100:.1f}%")

    elif args.command == "report":
        metrics = profiler.calculate_metrics(args.period, args.command)
        report = metrics.to_dict()

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to {args.output}")
        elif args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            print(f"\nPerformance Report ({metrics.period})")
            print("=" * 50)
            print(f"Period: {metrics.start_date[:10]} to {metrics.end_date[:10]}")
            print(f"Total Executions: {metrics.total_executions}")
            print(f"Success Rate: {report['success_rate']:.1f}%")
            print(f"\nDuration:")
            print(f"  Average: {metrics.avg_duration_ms:.0f}ms")
            print(f"  P50: {metrics.p50_duration_ms:.0f}ms")
            print(f"  P95: {metrics.p95_duration_ms:.0f}ms")
            print(f"  P99: {metrics.p99_duration_ms:.0f}ms")

    elif args.command == "slow":
        slow = profiler.get_slow_operations(args.threshold, args.limit)

        if args.format == "json":
            print(json.dumps([p.to_dict() for p in slow], indent=2))
        else:
            print(f"\nSlow Operations (>{args.threshold}ms): {len(slow)}")
            for p in slow:
                print(f"\n  {p.duration_ms}ms - {p.command[:50]}")
                print(f"    Time: {p.start_time}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
