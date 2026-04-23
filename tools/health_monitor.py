#!/usr/bin/env python3
"""
the system Health Monitor Tool

Monitors the health and status of a system components, providing
real-time health checks, status dashboards, and alerting capabilities.

Version: 1.0.0
Created: 2025-12-25
Author: Builder Agent
"""

import os
import re
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheck:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    status: HealthStatus
    checks: List[HealthCheck]
    last_check: str
    uptime_percent: float = 100.0

@dataclass
class SystemHealth:
    """Overall system health."""
    timestamp: str
    overall_status: HealthStatus
    components: List[ComponentHealth]
    total_checks: int
    healthy_checks: int
    degraded_checks: int
    unhealthy_checks: int
    alerts: List[Dict[str, Any]]

class HealthChecker:
    """Base class for health checks."""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout

    def check(self) -> HealthCheck:
        """Perform health check."""
        start = time.perf_counter()
        try:
            status, message, details = self._perform_check()
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Check failed: {str(e)}"
            details = {'error': str(e)}

        duration = (time.perf_counter() - start) * 1000

        return HealthCheck(
            name=self.name,
            status=status,
            message=message,
            duration_ms=duration,
            timestamp=datetime.now().isoformat(),
            details=details,
        )

    def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        """Implement actual check logic."""
        raise NotImplementedError

class FileSystemCheck(HealthChecker):
    """Check file system health."""

    def __init__(self, path: str, name: str = "filesystem"):
        super().__init__(name)
        self.path = Path(path)

    def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        if not self.path.exists():
            return HealthStatus.UNHEALTHY, f"Path does not exist: {self.path}", {}

        # Check read/write access
        try:
            test_file = self.path / '.health_check_test'
            test_file.write_text('test')
            test_file.unlink()
            writable = True
        except (PermissionError, IOError):
            writable = False

        # Check disk space
        try:
            stat = os.statvfs(self.path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used_percent = (total - free) / total * 100
        except (OSError, AttributeError):
            # Windows doesn't have statvfs
            used_percent = 0
            total = 0
            free = 0

        details = {
            'path': str(self.path),
            'writable': writable,
            'disk_used_percent': used_percent,
            'total_bytes': total,
            'free_bytes': free,
        }

        if not writable:
            return HealthStatus.DEGRADED, "Path is not writable", details

        if used_percent > 95:
            return HealthStatus.UNHEALTHY, f"Disk almost full: {used_percent:.1f}%", details
        elif used_percent > 85:
            return HealthStatus.DEGRADED, f"Disk space low: {used_percent:.1f}%", details

        return HealthStatus.HEALTHY, f"Filesystem healthy ({used_percent:.1f}% used)", details

class GitRepoCheck(HealthChecker):
    """Check Git repository health."""

    def __init__(self, path: str, name: str = "git"):
        super().__init__(name)
        self.path = Path(path)

    def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        git_dir = self.path / '.git'
        if not git_dir.exists():
            return HealthStatus.UNKNOWN, "Not a git repository", {'is_repo': False}

        details = {'is_repo': True, 'path': str(self.path)}

        # Check git status
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                return HealthStatus.UNHEALTHY, "Git status failed", details

            uncommitted = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            details['uncommitted_changes'] = uncommitted

            # Get current branch
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            details['branch'] = branch_result.stdout.strip()

            # Check for conflicts
            if '<<<<<<' in result.stdout or 'UU' in result.stdout:
                return HealthStatus.UNHEALTHY, "Merge conflicts detected", details

            if uncommitted > 50:
                return HealthStatus.DEGRADED, f"Many uncommitted changes: {uncommitted}", details
            elif uncommitted > 0:
                return HealthStatus.HEALTHY, f"Git healthy ({uncommitted} uncommitted)", details
            else:
                return HealthStatus.HEALTHY, "Git repository clean", details

        except subprocess.TimeoutExpired:
            return HealthStatus.UNHEALTHY, "Git check timed out", details
        except FileNotFoundError:
            return HealthStatus.UNKNOWN, "Git not installed", details

class ConfigCheck(HealthChecker):
    """Check configuration health."""

    def __init__(self, config_path: str, required_keys: List[str], name: str = "config"):
        super().__init__(name)
        self.config_path = Path(config_path)
        self.required_keys = required_keys

    def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        if not self.config_path.exists():
            return HealthStatus.UNHEALTHY, f"Config not found: {self.config_path}", {}

        try:
            content = self.config_path.read_text()
            if self.config_path.suffix in ['.yaml', '.yml']:
                import yaml
                config = yaml.safe_load(content)
            else:
                config = json.loads(content)
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Config parse error: {e}", {}

        details = {'path': str(self.config_path), 'keys_found': []}
        missing_keys = []

        for key in self.required_keys:
            if key in config:
                details['keys_found'].append(key)
            else:
                missing_keys.append(key)

        details['missing_keys'] = missing_keys

        if missing_keys:
            return HealthStatus.DEGRADED, f"Missing config keys: {missing_keys}", details

        return HealthStatus.HEALTHY, "Configuration valid", details

class ProcessCheck(HealthChecker):
    """Check if a process is running."""

    def __init__(self, process_name: str, name: Optional[str] = None):
        super().__init__(name or f"process:{process_name}")
        self.process_name = process_name

    def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        try:
            # Use pgrep for process check
            result = subprocess.run(
                ['pgrep', '-f', self.process_name],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            pids = result.stdout.strip().split('\n') if result.stdout.strip() else []

            details = {
                'process_name': self.process_name,
                'running': len(pids) > 0,
                'pids': pids,
                'count': len(pids),
            }

            if len(pids) == 0:
                return HealthStatus.UNHEALTHY, f"Process not running: {self.process_name}", details

            return HealthStatus.HEALTHY, f"Process running ({len(pids)} instances)", details

        except FileNotFoundError:
            # pgrep not available, try ps
            try:
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                running = self.process_name in result.stdout
                details = {'process_name': self.process_name, 'running': running}

                if running:
                    return HealthStatus.HEALTHY, f"Process running: {self.process_name}", details
                else:
                    return HealthStatus.UNHEALTHY, f"Process not running: {self.process_name}", details

            except Exception as e:
                return HealthStatus.UNKNOWN, f"Cannot check process: {e}", {}

class ToolCheck(HealthChecker):
    """Check the system tool health."""

    def __init__(self, tool_path: str, name: Optional[str] = None):
        super().__init__(name or f"tool:{Path(tool_path).stem}")
        self.tool_path = Path(tool_path)

    def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        details = {'path': str(self.tool_path)}

        if not self.tool_path.exists():
            return HealthStatus.UNHEALTHY, f"Tool not found: {self.tool_path}", details

        # Check syntax
        if self.tool_path.suffix == '.py':
            try:
                result = subprocess.run(
                    ['python3', '-m', 'py_compile', str(self.tool_path)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                if result.returncode != 0:
                    details['error'] = result.stderr
                    return HealthStatus.UNHEALTHY, "Syntax error in tool", details

            except subprocess.TimeoutExpired:
                return HealthStatus.DEGRADED, "Syntax check timed out", details
            except FileNotFoundError:
                return HealthStatus.UNKNOWN, "Python not found", details

        # Check permissions
        if not os.access(self.tool_path, os.R_OK):
            return HealthStatus.DEGRADED, "Tool not readable", details

        details['size_bytes'] = self.tool_path.stat().st_size
        details['modified'] = datetime.fromtimestamp(self.tool_path.stat().st_mtime).isoformat()

        return HealthStatus.HEALTHY, f"Tool healthy", details

class HealthMonitor:
    """Main health monitoring system."""

    def __init__(self, root_path: str, storage_path: str = '.task/health'):
        self.root_path = Path(root_path).resolve()
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.checkers: Dict[str, List[HealthChecker]] = {}
        self.history: List[SystemHealth] = []

    def register_component(self, component: str, checkers: List[HealthChecker]) -> None:
        """Register health checkers for a component."""
        self.checkers[component] = checkers

    def setup_default_checks(self) -> None:
        """Set up default the system health checks."""
        # File system checks
        self.register_component('filesystem', [
            FileSystemCheck(str(self.root_path), 'root'),
            FileSystemCheck(str(self.root_path / 'tools'), 'tools'),
            FileSystemCheck(str(self.root_path / 'PLANNING'), 'planning'),
        ])

        # Git checks
        self.register_component('git', [
            GitRepoCheck(str(self.root_path)),
        ])

        # Tool checks
        tools_dir = self.root_path / 'tools'
        if tools_dir.exists():
            tool_checkers = []
            for tool in list(tools_dir.glob('*.py'))[:10]:  # Limit to 10
                tool_checkers.append(ToolCheck(str(tool)))
            if tool_checkers:
                self.register_component('tools', tool_checkers)

    def check_all(self) -> SystemHealth:
        """Run all health checks."""
        components = []
        total_checks = 0
        healthy = 0
        degraded = 0
        unhealthy = 0

        for component_name, checkers in self.checkers.items():
            checks = []

            for checker in checkers:
                check = checker.check()
                checks.append(check)
                total_checks += 1

                if check.status == HealthStatus.HEALTHY:
                    healthy += 1
                elif check.status == HealthStatus.DEGRADED:
                    degraded += 1
                elif check.status == HealthStatus.UNHEALTHY:
                    unhealthy += 1

            # Determine component status
            if any(c.status == HealthStatus.UNHEALTHY for c in checks):
                component_status = HealthStatus.UNHEALTHY
            elif any(c.status == HealthStatus.DEGRADED for c in checks):
                component_status = HealthStatus.DEGRADED
            elif all(c.status == HealthStatus.HEALTHY for c in checks):
                component_status = HealthStatus.HEALTHY
            else:
                component_status = HealthStatus.UNKNOWN

            components.append(ComponentHealth(
                name=component_name,
                status=component_status,
                checks=checks,
                last_check=datetime.now().isoformat(),
            ))

        # Determine overall status
        if unhealthy > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded > 0:
            overall_status = HealthStatus.DEGRADED
        elif healthy == total_checks:
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN

        # Generate alerts for unhealthy checks
        alerts = []
        for component in components:
            for check in component.checks:
                if check.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                    alerts.append({
                        'component': component.name,
                        'check': check.name,
                        'status': check.status.value,
                        'message': check.message,
                        'timestamp': check.timestamp,
                    })

        health = SystemHealth(
            timestamp=datetime.now().isoformat(),
            overall_status=overall_status,
            components=components,
            total_checks=total_checks,
            healthy_checks=healthy,
            degraded_checks=degraded,
            unhealthy_checks=unhealthy,
            alerts=alerts,
        )

        # Save to history
        self._save_health(health)

        return health

    def check_component(self, component: str) -> Optional[ComponentHealth]:
        """Check a specific component."""
        if component not in self.checkers:
            return None

        checkers = self.checkers[component]
        checks = [checker.check() for checker in checkers]

        # Determine status
        if any(c.status == HealthStatus.UNHEALTHY for c in checks):
            status = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in checks):
            status = HealthStatus.DEGRADED
        elif all(c.status == HealthStatus.HEALTHY for c in checks):
            status = HealthStatus.HEALTHY
        else:
            status = HealthStatus.UNKNOWN

        return ComponentHealth(
            name=component,
            status=status,
            checks=checks,
            last_check=datetime.now().isoformat(),
        )

    def _save_health(self, health: SystemHealth) -> None:
        """Save health check to storage."""
        # Save to daily file
        date = health.timestamp[:10]
        daily_file = self.storage_path / f"health-{date}.jsonl"

        with open(daily_file, 'a') as f:
            # Convert to dict with proper enum handling
            health_dict = self._health_to_dict(health)
            f.write(json.dumps(health_dict) + '\n')

        # Update latest
        latest_file = self.storage_path / 'latest.json'
        with open(latest_file, 'w') as f:
            json.dump(health_dict, f, indent=2)

    def _health_to_dict(self, health: SystemHealth) -> Dict:
        """Convert SystemHealth to dict with enum handling."""
        return {
            'timestamp': health.timestamp,
            'overall_status': health.overall_status.value,
            'total_checks': health.total_checks,
            'healthy_checks': health.healthy_checks,
            'degraded_checks': health.degraded_checks,
            'unhealthy_checks': health.unhealthy_checks,
            'alerts': health.alerts,
            'components': [
                {
                    'name': c.name,
                    'status': c.status.value,
                    'last_check': c.last_check,
                    'uptime_percent': c.uptime_percent,
                    'checks': [
                        {
                            'name': ch.name,
                            'status': ch.status.value,
                            'message': ch.message,
                            'duration_ms': ch.duration_ms,
                            'timestamp': ch.timestamp,
                            'details': ch.details,
                        }
                        for ch in c.checks
                    ],
                }
                for c in health.components
            ],
        }

    def get_history(self, hours: int = 24) -> List[Dict]:
        """Get health history for the past N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        history = []

        for health_file in sorted(self.storage_path.glob('health-*.jsonl')):
            with open(health_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        ts = datetime.fromisoformat(data['timestamp'])
                        if ts >= cutoff:
                            history.append(data)

        return history

def format_health(health: SystemHealth, format: str) -> str:
    """Format health status for output."""
    if format == 'json':
        return json.dumps(
            {
                'timestamp': health.timestamp,
                'overall_status': health.overall_status.value,
                'total_checks': health.total_checks,
                'healthy_checks': health.healthy_checks,
                'degraded_checks': health.degraded_checks,
                'unhealthy_checks': health.unhealthy_checks,
                'components': [
                    {
                        'name': c.name,
                        'status': c.status.value,
                        'checks': len(c.checks),
                    }
                    for c in health.components
                ],
                'alerts': health.alerts,
            },
            indent=2,
        )

    # Status symbols
    symbols = {
        HealthStatus.HEALTHY: '✓',
        HealthStatus.DEGRADED: '!',
        HealthStatus.UNHEALTHY: '✗',
        HealthStatus.UNKNOWN: '?',
    }

    lines = [
        "=" * 60,
        "System Health Status",
        "=" * 60,
        f"Timestamp: {health.timestamp}",
        f"Overall Status: {symbols[health.overall_status]} {health.overall_status.value.upper()}",
        "",
        f"Checks: {health.healthy_checks}/{health.total_checks} healthy",
        f"  Degraded: {health.degraded_checks}",
        f"  Unhealthy: {health.unhealthy_checks}",
        "",
        "Components:",
    ]

    for component in health.components:
        symbol = symbols[component.status]
        lines.append(f"  {symbol} {component.name}: {component.status.value}")

        for check in component.checks:
            check_symbol = symbols[check.status]
            lines.append(f"      {check_symbol} {check.name}: {check.message} ({check.duration_ms:.0f}ms)")

    if health.alerts:
        lines.extend(["", f"Alerts ({len(health.alerts)}):"])
        for alert in health.alerts[:5]:
            lines.append(f"  [{alert['status'].upper()}] {alert['component']}/{alert['check']}: {alert['message']}")

    return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Health Monitor - Monitor system health'
    )
    parser.add_argument(
        'command',
        nargs='?',
        default='check',
        choices=['check', 'watch', 'history', 'component'],
        help='Command to execute'
    )
    parser.add_argument(
        '--root', '-r',
        default='.',
        help='Root directory to monitor'
    )
    parser.add_argument(
        '--component', '-c',
        help='Specific component to check'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=60,
        help='Watch interval in seconds'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Hours of history to show'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['summary', 'json'],
        default='summary',
        help='Output format'
    )

    args = parser.parse_args()

    monitor = HealthMonitor(args.root)
    monitor.setup_default_checks()

    if args.command == 'check':
        if args.component:
            component = monitor.check_component(args.component)
            if component:
                print(f"Component: {component.name}")
                print(f"Status: {component.status.value}")
                for check in component.checks:
                    print(f"  {check.name}: {check.status.value} - {check.message}")
            else:
                print(f"Unknown component: {args.component}")
        else:
            health = monitor.check_all()
            print(format_health(health, args.format))

    elif args.command == 'watch':
        print(f"Watching health every {args.interval}s (Ctrl+C to stop)")
        try:
            while True:
                health = monitor.check_all()
                os.system('clear' if os.name != 'nt' else 'cls')
                print(format_health(health, args.format))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped watching")

    elif args.command == 'history':
        history = monitor.get_history(args.hours)
        print(f"Health History (last {args.hours} hours):")
        for entry in history[-20:]:
            ts = entry['timestamp']
            status = entry['overall_status']
            healthy = entry['healthy_checks']
            total = entry['total_checks']
            print(f"  {ts}: {status} ({healthy}/{total} healthy)")

    elif args.command == 'component':
        print("Available components:")
        for name in monitor.checkers:
            print(f"  - {name}")

if __name__ == '__main__':
    main()
