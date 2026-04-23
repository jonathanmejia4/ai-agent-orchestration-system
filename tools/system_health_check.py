#!/usr/bin/env python3
"""
System Health Check Tool
Version: 1.0.0
Last Updated: 2025-12-29
Owner: DevOps
Classification: HIGH - System Monitoring

Comprehensive system health check for the system infrastructure.

Usage:
    python tools/system_health_check.py
    python tools/system_health_check.py --full
    python tools/system_health_check.py --json

See: PLANNING/MONITORING_STRATEGY.md
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

@dataclass
class HealthCheck:
    """Result of a single health check."""
    name: str
    status: str  # healthy, degraded, unhealthy
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HealthReport:
    """Complete system health report."""
    timestamp: str
    overall_status: str
    checks: List[HealthCheck]
    summary: Dict[str, int]

def check_directory_exists(path: Path, name: str) -> HealthCheck:
    """Check if a required directory exists."""
    if path.exists() and path.is_dir():
        return HealthCheck(
            name=name,
            status="healthy",
            message=f"Directory exists: {path}",
            details={"path": str(path), "exists": True}
        )
    return HealthCheck(
        name=name,
        status="unhealthy",
        message=f"Directory missing: {path}",
        details={"path": str(path), "exists": False}
    )

def check_file_exists(path: Path, name: str) -> HealthCheck:
    """Check if a required file exists."""
    if path.exists() and path.is_file():
        return HealthCheck(
            name=name,
            status="healthy",
            message=f"File exists: {path}",
            details={"path": str(path), "exists": True}
        )
    return HealthCheck(
        name=name,
        status="unhealthy",
        message=f"File missing: {path}",
        details={"path": str(path), "exists": False}
    )

def check_logbook_status(base_path: Path) -> HealthCheck:
    """Check LogBook directory status."""
    logbook = base_path / "LogBook"
    if not logbook.exists():
        return HealthCheck(
            name="LogBook",
            status="unhealthy",
            message="LogBook directory missing",
            details={"path": str(logbook), "exists": False}
        )

    # Check for key LogBook subdirectories
    required_dirs = ["pm", "builder", "critic", "planner"]
    missing = [d for d in required_dirs if not (logbook / d).exists()]

    if missing:
        return HealthCheck(
            name="LogBook",
            status="degraded",
            message=f"LogBook missing subdirectories: {missing}",
            details={"missing": missing, "path": str(logbook)}
        )

    return HealthCheck(
        name="LogBook",
        status="healthy",
        message="LogBook structure intact",
        details={"path": str(logbook), "subdirs": required_dirs}
    )

def check_templates_status(base_path: Path) -> HealthCheck:
    """Check templates directory status."""
    templates = base_path / "templates"
    if not templates.exists():
        return HealthCheck(
            name="Templates",
            status="unhealthy",
            message="Templates directory missing",
            details={"path": str(templates), "exists": False}
        )

    # Count template families
    families = [d for d in templates.iterdir() if d.is_dir() and not d.name.startswith('.')]
    template_count = sum(
        len(list((f).glob("*.jinja2")))
        for f in families
    )

    return HealthCheck(
        name="Templates",
        status="healthy",
        message=f"Found {len(families)} template families, {template_count} templates",
        details={
            "families": len(families),
            "templates": template_count,
            "path": str(templates)
        }
    )

def check_tools_status(base_path: Path) -> HealthCheck:
    """Check tools directory status."""
    tools = base_path / "tools"
    if not tools.exists():
        return HealthCheck(
            name="Tools",
            status="unhealthy",
            message="Tools directory missing",
            details={"path": str(tools), "exists": False}
        )

    # Count Python tools
    python_tools = list(tools.glob("*.py"))

    return HealthCheck(
        name="Tools",
        status="healthy",
        message=f"Found {len(python_tools)} Python tools",
        details={
            "tool_count": len(python_tools),
            "path": str(tools)
        }
    )

def check_config_status(base_path: Path) -> HealthCheck:
    """Check configuration status."""
    config = base_path / "config"
    integration_config = base_path / "integration" / "config"

    config_exists = config.exists()
    integration_exists = integration_config.exists()

    if config_exists or integration_exists:
        return HealthCheck(
            name="Configuration",
            status="healthy",
            message="Configuration directories found",
            details={
                "config": config_exists,
                "integration_config": integration_exists
            }
        )

    return HealthCheck(
        name="Configuration",
        status="degraded",
        message="No configuration directories found",
        details={"config": False, "integration_config": False}
    )

def check_tasks_status(base_path: Path) -> HealthCheck:
    """Check tasks directory status."""
    tasks = base_path / "tasks"
    if not tasks.exists():
        return HealthCheck(
            name="Tasks",
            status="degraded",
            message="Tasks directory missing (may be expected)",
            details={"path": str(tasks), "exists": False}
        )

    # Count task directories
    task_dirs = [d for d in tasks.iterdir() if d.is_dir()]

    return HealthCheck(
        name="Tasks",
        status="healthy",
        message=f"Found {len(task_dirs)} tasks",
        details={
            "task_count": len(task_dirs),
            "path": str(tasks)
        }
    )

def check_saf_state(base_path: Path) -> HealthCheck:
    """Check .saf state directory."""
    saf_dir = base_path / ".saf"
    if not saf_dir.exists():
        return HealthCheck(
            name="the system State",
            status="degraded",
            message=".saf directory missing",
            details={"path": str(saf_dir), "exists": False}
        )

    subdirs = ["temp", "locks", "generated"]
    existing = [d for d in subdirs if (saf_dir / d).exists()]

    return HealthCheck(
        name="the system State",
        status="healthy",
        message=f".saf directory with {len(existing)}/{len(subdirs)} subdirs",
        details={
            "path": str(saf_dir),
            "subdirs": existing
        }
    )

def run_health_checks(base_path: Path, full: bool = False) -> HealthReport:
    """Run all health checks."""
    checks = []

    # Core directory checks
    checks.append(check_logbook_status(base_path))
    checks.append(check_templates_status(base_path))
    checks.append(check_tools_status(base_path))
    checks.append(check_config_status(base_path))

    if full:
        # Additional checks for --full mode
        checks.append(check_tasks_status(base_path))
        checks.append(check_saf_state(base_path))
        checks.append(check_directory_exists(base_path / "PLANNING", "PLANNING"))
        checks.append(check_directory_exists(base_path / ".checkpoints", "Checkpoints"))

    # Compute summary
    summary = {
        "healthy": sum(1 for c in checks if c.status == "healthy"),
        "degraded": sum(1 for c in checks if c.status == "degraded"),
        "unhealthy": sum(1 for c in checks if c.status == "unhealthy")
    }

    # Determine overall status
    if summary["unhealthy"] > 0:
        overall = "unhealthy"
    elif summary["degraded"] > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return HealthReport(
        timestamp=datetime.now().isoformat(),
        overall_status=overall,
        checks=checks,
        summary=summary
    )

def main():
    parser = argparse.ArgumentParser(
        description='System Health Check'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Run comprehensive health checks'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '--base-path',
        type=Path,
        default=Path('.'),
        help='Base path for the system repository'
    )

    args = parser.parse_args()

    report = run_health_checks(args.base_path, args.full)

    if args.json:
        output = asdict(report)
        print(json.dumps(output, indent=2))
    else:
        status_icons = {
            "healthy": "[OK]",
            "degraded": "[WARN]",
            "unhealthy": "[FAIL]"
        }

        print(f"System Health Check")
        print(f"=" * 40)
        print(f"Timestamp: {report.timestamp}")
        print(f"Overall Status: {report.overall_status.upper()}")
        print()

        for check in report.checks:
            icon = status_icons.get(check.status, "[?]")
            print(f"  {icon} {check.name}: {check.message}")

        print()
        print(f"Summary: {report.summary['healthy']} healthy, "
              f"{report.summary['degraded']} degraded, "
              f"{report.summary['unhealthy']} unhealthy")

    # Exit codes: 0=healthy, 1=degraded, 2=unhealthy
    if report.overall_status == "healthy":
        sys.exit(0)
    elif report.overall_status == "degraded":
        sys.exit(1)
    else:
        sys.exit(2)

if __name__ == '__main__':
    main()
