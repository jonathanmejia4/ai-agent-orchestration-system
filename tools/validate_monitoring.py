#!/usr/bin/env python3
"""
Monitoring Event Validator
Version: 1.0.0
Last Updated: 2026-01-05
Owner: PM
Classification: HIGH - Observability Validation

Validates monitoring event files against monitoring_event_schema.yaml.

Usage:
    python tools/validate_monitoring.py <monitoring_event_file>
    python tools/validate_monitoring.py --check-all
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

@dataclass
class ValidationResult:
    """Result of validating a monitoring event."""
    file: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    passed: bool

# Required fields (matches monitoring_event_schema.yaml:13-17)
REQUIRED_FIELDS = [
    'event_id',
    'event_type',
    'timestamp',
    'source',
]

# Required source fields (matches monitoring_event_schema.yaml:49-50)
REQUIRED_SOURCE_FIELDS = ['component']

# Valid event_type values (matches monitoring_event_schema.yaml:30-38)
VALID_EVENT_TYPES = [
    'metric',
    'log',
    'trace',
    'alert',
    'health_check',
    'state_change',
    'error',
    'audit',
]

# Valid severity values (matches monitoring_event_schema.yaml:72-77)
VALID_SEVERITIES = ['debug', 'info', 'warning', 'error', 'critical']

# Valid category values (matches monitoring_event_schema.yaml:83-90)
VALID_CATEGORIES = [
    'performance',
    'availability',
    'security',
    'compliance',
    'capacity',
    'change',
    'incident',
]

# Valid metric type values (matches monitoring_event_schema.yaml:117-121)
VALID_METRIC_TYPES = ['gauge', 'counter', 'histogram', 'summary']

# Valid log level values (matches monitoring_event_schema.yaml:138-144)
VALID_LOG_LEVELS = ['TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']

# Valid trace status values (matches monitoring_event_schema.yaml:174-177)
VALID_TRACE_STATUSES = ['ok', 'error', 'timeout']

# Valid alert status values (matches monitoring_event_schema.yaml:195-199)
VALID_ALERT_STATUSES = ['firing', 'resolved', 'acknowledged', 'suppressed']

# Valid alert threshold operators (matches monitoring_event_schema.yaml:207)
VALID_THRESHOLD_OPERATORS = ['>', '>=', '<', '<=', '==', '!=']

# Valid health_check status values (matches monitoring_event_schema.yaml:230-234)
VALID_HEALTH_CHECK_STATUSES = ['healthy', 'degraded', 'unhealthy', 'unknown']

# Valid state_change entity_type values (matches monitoring_event_schema.yaml:253-257)
VALID_ENTITY_TYPES = ['agent', 'task', 'work_order', 'pipeline']

# Valid audit actor type values (matches monitoring_event_schema.yaml:307-310)
VALID_ACTOR_TYPES = ['agent', 'user', 'system']

# Valid audit outcome values (matches monitoring_event_schema.yaml:324-327)
VALID_AUDIT_OUTCOMES = ['success', 'failure', 'denied']

# Valid environment values (matches monitoring_event_schema.yaml:357-360)
VALID_ENVIRONMENTS = ['development', 'staging', 'production']

# Valid retention policy values (matches monitoring_event_schema.yaml:374-378)
VALID_RETENTION_POLICIES = ['default', 'extended', 'compliance', 'minimal']

# Pattern for event_id (matches monitoring_event_schema.yaml:22)
EVENT_ID_PATTERN = r'^EVT-[A-Z]{2,4}-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}$'

class MonitoringValidator:
    """Validates monitoring event files."""

    DEFAULT_SCHEMA_PATH = Path("PLANNING/schemas/monitoring_event_schema.yaml")

    def __init__(self, schema_path: Path = None):
        if schema_path is None:
            schema_path = self.DEFAULT_SCHEMA_PATH
        self.schema_path = schema_path
        self.schema = self._load_schema()

    def _load_schema(self) -> Optional[Dict]:
        """Load validation schema."""
        if not self.schema_path or not self.schema_path.exists():
            script_dir = Path(__file__).parent.parent
            alt_path = script_dir / self.schema_path
            if alt_path.exists():
                self.schema_path = alt_path
            else:
                return None
        with open(self.schema_path, 'r') as f:
            return yaml.safe_load(f)

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single monitoring event file."""
        issues: List[str] = []
        warnings: List[str] = []

        if not file_path.exists():
            return ValidationResult(
                file=str(file_path),
                status="error",
                issues=[f"File not found: {file_path}"],
                warnings=[],
                passed=False
            )

        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return ValidationResult(
                file=str(file_path),
                status="error",
                issues=[f"YAML parse error: {e}"],
                warnings=[],
                passed=False
            )

        if not isinstance(data, dict):
            return ValidationResult(
                file=str(file_path),
                status="error",
                issues=["Monitoring event must be a YAML mapping"],
                warnings=[],
                passed=False
            )

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate event_id pattern
        if 'event_id' in data:
            evt_id = data['event_id']
            if not isinstance(evt_id, str) or not re.match(EVENT_ID_PATTERN, evt_id):
                issues.append(f"Invalid event_id format: {evt_id}. Expected: EVT-XX-YYYYMMDD-HHMMSS-xxxxxxxx")

        # Validate event_type
        event_type = data.get('event_type')
        if 'event_type' in data:
            if event_type not in VALID_EVENT_TYPES:
                issues.append(f"Invalid event_type: {event_type}. Valid: {VALID_EVENT_TYPES}")

        # Validate source
        if 'source' in data:
            source = data['source']
            if not isinstance(source, dict):
                issues.append("source must be an object")
            else:
                for field in REQUIRED_SOURCE_FIELDS:
                    if field not in source:
                        issues.append(f"Missing required source field: {field}")

        # Validate severity
        if 'severity' in data:
            if data['severity'] not in VALID_SEVERITIES:
                issues.append(f"Invalid severity: {data['severity']}. Valid: {VALID_SEVERITIES}")

        # Validate category
        if 'category' in data:
            if data['category'] not in VALID_CATEGORIES:
                issues.append(f"Invalid category: {data['category']}. Valid: {VALID_CATEGORIES}")

        # Validate event-type-specific data
        if event_type == 'metric' and 'metric' in data:
            self._validate_metric(data['metric'], issues, warnings)
        elif event_type == 'log' and 'log' in data:
            self._validate_log(data['log'], issues, warnings)
        elif event_type == 'trace' and 'trace' in data:
            self._validate_trace(data['trace'], issues, warnings)
        elif event_type == 'alert' and 'alert' in data:
            self._validate_alert(data['alert'], issues, warnings)
        elif event_type == 'health_check' and 'health_check' in data:
            self._validate_health_check(data['health_check'], issues, warnings)
        elif event_type == 'state_change' and 'state_change' in data:
            self._validate_state_change(data['state_change'], issues, warnings)
        elif event_type == 'error' and 'error' in data:
            self._validate_error(data['error'], issues, warnings)
        elif event_type == 'audit' and 'audit' in data:
            self._validate_audit(data['audit'], issues, warnings)

        # Warn if event_type specific data is missing
        if event_type and event_type in VALID_EVENT_TYPES:
            if event_type not in data and event_type not in ['error']:
                warnings.append(f"Event type is '{event_type}' but no '{event_type}' data block present")

        # Validate context if present
        if 'context' in data and isinstance(data['context'], dict):
            context = data['context']
            if 'environment' in context:
                if context['environment'] not in VALID_ENVIRONMENTS:
                    issues.append(f"Invalid context.environment: {context['environment']}. Valid: {VALID_ENVIRONMENTS}")

        # Validate retention if present
        if 'retention' in data and isinstance(data['retention'], dict):
            retention = data['retention']
            if 'policy' in retention:
                if retention['policy'] not in VALID_RETENTION_POLICIES:
                    issues.append(f"Invalid retention.policy: {retention['policy']}. Valid: {VALID_RETENTION_POLICIES}")

        # Determine status
        if issues:
            status = "error"
            passed = False
        elif warnings:
            status = "warning"
            passed = True
        else:
            status = "valid"
            passed = True

        return ValidationResult(
            file=str(file_path),
            status=status,
            issues=issues,
            warnings=warnings,
            passed=passed
        )

    def _validate_metric(self, metric: Dict, issues: List[str], warnings: List[str]):
        """Validate metric event data."""
        if not isinstance(metric, dict):
            issues.append("metric must be an object")
            return

        if 'type' in metric:
            if metric['type'] not in VALID_METRIC_TYPES:
                issues.append(f"Invalid metric.type: {metric['type']}. Valid: {VALID_METRIC_TYPES}")

        if 'value' in metric:
            if not isinstance(metric['value'], (int, float)):
                issues.append("metric.value must be a number")

        # Recommended fields
        if 'name' not in metric:
            warnings.append("Missing recommended metric field: name")
        if 'value' not in metric:
            warnings.append("Missing recommended metric field: value")

    def _validate_log(self, log: Dict, issues: List[str], warnings: List[str]):
        """Validate log event data."""
        if not isinstance(log, dict):
            issues.append("log must be an object")
            return

        if 'level' in log:
            if log['level'] not in VALID_LOG_LEVELS:
                issues.append(f"Invalid log.level: {log['level']}. Valid: {VALID_LOG_LEVELS}")

        if 'message' not in log:
            warnings.append("Missing recommended log field: message")

    def _validate_trace(self, trace: Dict, issues: List[str], warnings: List[str]):
        """Validate trace event data."""
        if not isinstance(trace, dict):
            issues.append("trace must be an object")
            return

        if 'status' in trace:
            if trace['status'] not in VALID_TRACE_STATUSES:
                issues.append(f"Invalid trace.status: {trace['status']}. Valid: {VALID_TRACE_STATUSES}")

        if 'duration_ms' in trace:
            if not isinstance(trace['duration_ms'], (int, float)):
                issues.append("trace.duration_ms must be a number")

        if 'trace_id' not in trace:
            warnings.append("Missing recommended trace field: trace_id")

    def _validate_alert(self, alert: Dict, issues: List[str], warnings: List[str]):
        """Validate alert event data."""
        if not isinstance(alert, dict):
            issues.append("alert must be an object")
            return

        if 'status' in alert:
            if alert['status'] not in VALID_ALERT_STATUSES:
                issues.append(f"Invalid alert.status: {alert['status']}. Valid: {VALID_ALERT_STATUSES}")

        if 'threshold' in alert and isinstance(alert['threshold'], dict):
            threshold = alert['threshold']
            if 'operator' in threshold:
                if threshold['operator'] not in VALID_THRESHOLD_OPERATORS:
                    issues.append(f"Invalid alert.threshold.operator: {threshold['operator']}. Valid: {VALID_THRESHOLD_OPERATORS}")
            if 'value' in threshold:
                if not isinstance(threshold['value'], (int, float)):
                    issues.append("alert.threshold.value must be a number")

        if 'name' not in alert:
            warnings.append("Missing recommended alert field: name")

    def _validate_health_check(self, health_check: Dict, issues: List[str], warnings: List[str]):
        """Validate health_check event data."""
        if not isinstance(health_check, dict):
            issues.append("health_check must be an object")
            return

        if 'status' in health_check:
            if health_check['status'] not in VALID_HEALTH_CHECK_STATUSES:
                issues.append(f"Invalid health_check.status: {health_check['status']}. Valid: {VALID_HEALTH_CHECK_STATUSES}")

        if 'response_time_ms' in health_check:
            if not isinstance(health_check['response_time_ms'], (int, float)):
                issues.append("health_check.response_time_ms must be a number")

        if 'consecutive_failures' in health_check:
            if not isinstance(health_check['consecutive_failures'], int):
                issues.append("health_check.consecutive_failures must be an integer")

        if 'check_name' not in health_check:
            warnings.append("Missing recommended health_check field: check_name")

    def _validate_state_change(self, state_change: Dict, issues: List[str], warnings: List[str]):
        """Validate state_change event data."""
        if not isinstance(state_change, dict):
            issues.append("state_change must be an object")
            return

        if 'entity_type' in state_change:
            if state_change['entity_type'] not in VALID_ENTITY_TYPES:
                issues.append(f"Invalid state_change.entity_type: {state_change['entity_type']}. Valid: {VALID_ENTITY_TYPES}")

        if 'previous_state' not in state_change:
            warnings.append("Missing recommended state_change field: previous_state")
        if 'new_state' not in state_change:
            warnings.append("Missing recommended state_change field: new_state")

    def _validate_error(self, error: Dict, issues: List[str], warnings: List[str]):
        """Validate error event data."""
        if not isinstance(error, dict):
            issues.append("error must be an object")
            return

        if 'recoverable' in error:
            if not isinstance(error['recoverable'], bool):
                issues.append("error.recoverable must be a boolean")

        if 'message' not in error:
            warnings.append("Missing recommended error field: message")

    def _validate_audit(self, audit: Dict, issues: List[str], warnings: List[str]):
        """Validate audit event data."""
        if not isinstance(audit, dict):
            issues.append("audit must be an object")
            return

        if 'actor' in audit and isinstance(audit['actor'], dict):
            actor = audit['actor']
            if 'type' in actor:
                if actor['type'] not in VALID_ACTOR_TYPES:
                    issues.append(f"Invalid audit.actor.type: {actor['type']}. Valid: {VALID_ACTOR_TYPES}")

        if 'outcome' in audit:
            if audit['outcome'] not in VALID_AUDIT_OUTCOMES:
                issues.append(f"Invalid audit.outcome: {audit['outcome']}. Valid: {VALID_AUDIT_OUTCOMES}")

        if 'action' not in audit:
            warnings.append("Missing recommended audit field: action")

    def validate_all(self, events_dir: Path = None) -> List[ValidationResult]:
        """Validate all monitoring event files."""
        events_dir = events_dir or Path("LogBook/events")
        results = []

        if not events_dir.exists():
            return results

        for evt_file in events_dir.rglob("*.yaml"):
            if 'schema' not in evt_file.name:
                result = self.validate_file(evt_file)
                results.append(result)

        for evt_file in events_dir.rglob("*.yml"):
            if 'schema' not in evt_file.name:
                result = self.validate_file(evt_file)
                results.append(result)

        return results

def format_text(results: List[ValidationResult]) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Monitoring Event Validation Results")
    lines.append("=" * 60)
    lines.append("")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    for result in results:
        status_icon = "+" if result.passed else "X"
        lines.append(f"{status_icon} {result.file}: {result.status}")

        for issue in result.issues:
            lines.append(f"  ERROR: {issue}")
        for warning in result.warnings:
            lines.append(f"  WARN: {warning}")

        if result.issues or result.warnings:
            lines.append("")

    lines.append("=" * 60)
    lines.append(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")
    lines.append("=" * 60)

    return "\n".join(lines)

def format_json(results: List[ValidationResult]) -> str:
    """Format results as JSON."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [asdict(r) for r in results]
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate monitoring event files against schema"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to monitoring event file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all monitoring events in LogBook/events"
    )
    parser.add_argument(
        "--events-dir",
        type=Path,
        default=Path("LogBook/events"),
        help="Directory containing monitoring event files"
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

    validator = MonitoringValidator()

    if args.check_all:
        results = validator.validate_all(args.events_dir)
    elif args.file:
        results = [validator.validate_file(Path(args.file))]
    else:
        results = validator.validate_all(args.events_dir)

    # Format output
    if args.format == "json":
        output = format_json(results)
    else:
        output = format_text(results)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Exit code
    sys.exit(0 if all(r.passed for r in results) else 1)

if __name__ == "__main__":
    main()
