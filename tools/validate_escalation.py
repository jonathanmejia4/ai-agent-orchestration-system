#!/usr/bin/env python3
"""
Escalation Event Validator
Version: 1.0.0
Last Updated: 2026-01-05
Owner: PM
Classification: HIGH - Workflow Validation

Validates escalation event files against escalation_event_schema.yaml.

Usage:
    python tools/validate_escalation.py <escalation_file>
    python tools/validate_escalation.py --check-all
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
    """Result of validating an escalation event."""
    file: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    passed: bool

# Required fields (matches escalation_event_schema.yaml:13-21)
REQUIRED_FIELDS = [
    'escalation_id',
    'timestamp',
    'source_agent',
    'target_agent',
    'severity',
    'category',
    'summary',
    'status',
]

# Valid source_agent values (matches escalation_event_schema.yaml:35-36)
VALID_SOURCE_AGENTS = ['pm', 'builder', 'critic', 'planner']

# Valid target_agent values (matches escalation_event_schema.yaml:40-41)
VALID_TARGET_AGENTS = ['pm', 'builder', 'critic', 'planner', 'human']

# Valid severity values (matches escalation_event_schema.yaml:45-51)
VALID_SEVERITIES = ['info', 'warning', 'urgent', 'critical', 'emergency']

# Valid category values (matches escalation_event_schema.yaml:55-66)
VALID_CATEGORIES = [
    'blocker',
    'scope_violation',
    'resource_conflict',
    'deadline_risk',
    'quality_concern',
    'policy_violation',
    'dependency_issue',
    'security_concern',
    'approval_required',
    'clarification_needed',
]

# Valid status values (matches escalation_event_schema.yaml:81-88)
VALID_STATUSES = [
    'open',
    'acknowledged',
    'in_progress',
    'resolved',
    'closed',
    'escalated_further',
]

# Valid action_type values (matches escalation_event_schema.yaml:127-132)
VALID_ACTION_TYPES = [
    'decision_needed',
    'approval_needed',
    'resource_needed',
    'guidance_needed',
    'intervention_needed',
]

# Valid resolution_type values (matches escalation_event_schema.yaml:148-154)
VALID_RESOLUTION_TYPES = [
    'approved',
    'denied',
    'workaround_provided',
    'deferred',
    'not_applicable',
]

# Pattern for escalation_id (matches escalation_event_schema.yaml:25)
ESCALATION_ID_PATTERN = r'^ESC-[0-9]{4}-[0-9]{3}$'

# Pattern for work_order_id (matches escalation_event_schema.yaml:96)
WORK_ORDER_ID_PATTERN = r'^WO-[0-9]{8}-[0-9]{3}$'

class EscalationValidator:
    """Validates escalation event files."""

    DEFAULT_SCHEMA_PATH = Path("PLANNING/schemas/escalation_event_schema.yaml")

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
        """Validate a single escalation event file."""
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
                issues=["Escalation event must be a YAML mapping"],
                warnings=[],
                passed=False
            )

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate escalation_id pattern
        if 'escalation_id' in data:
            esc_id = data['escalation_id']
            if not isinstance(esc_id, str) or not re.match(ESCALATION_ID_PATTERN, esc_id):
                issues.append(f"Invalid escalation_id format: {esc_id}. Expected: ESC-YYYY-NNN")

        # Validate source_agent
        if 'source_agent' in data:
            if data['source_agent'] not in VALID_SOURCE_AGENTS:
                issues.append(f"Invalid source_agent: {data['source_agent']}. Valid: {VALID_SOURCE_AGENTS}")

        # Validate target_agent
        if 'target_agent' in data:
            if data['target_agent'] not in VALID_TARGET_AGENTS:
                issues.append(f"Invalid target_agent: {data['target_agent']}. Valid: {VALID_TARGET_AGENTS}")

        # Validate severity
        if 'severity' in data:
            if data['severity'] not in VALID_SEVERITIES:
                issues.append(f"Invalid severity: {data['severity']}. Valid: {VALID_SEVERITIES}")

        # Validate category
        if 'category' in data:
            if data['category'] not in VALID_CATEGORIES:
                issues.append(f"Invalid category: {data['category']}. Valid: {VALID_CATEGORIES}")

        # Validate status
        if 'status' in data:
            if data['status'] not in VALID_STATUSES:
                issues.append(f"Invalid status: {data['status']}. Valid: {VALID_STATUSES}")

        # Validate summary length
        if 'summary' in data:
            summary = data['summary']
            if isinstance(summary, str):
                if len(summary) < 20:
                    warnings.append(f"Summary too short ({len(summary)} chars). Minimum: 20")
                if len(summary) > 500:
                    issues.append(f"Summary too long ({len(summary)} chars). Maximum: 500")

        # Validate context if present
        if 'context' in data and isinstance(data['context'], dict):
            context = data['context']
            if 'work_order_id' in context:
                wo_id = context['work_order_id']
                if not isinstance(wo_id, str) or not re.match(WORK_ORDER_ID_PATTERN, wo_id):
                    issues.append(f"Invalid work_order_id format: {wo_id}. Expected: WO-YYYYMMDD-NNN")

        # Validate requested_action if present
        if 'requested_action' in data and isinstance(data['requested_action'], dict):
            req_action = data['requested_action']
            if 'action_type' in req_action:
                if req_action['action_type'] not in VALID_ACTION_TYPES:
                    issues.append(f"Invalid action_type: {req_action['action_type']}. Valid: {VALID_ACTION_TYPES}")

        # Validate resolution if present
        if 'resolution' in data and isinstance(data['resolution'], dict):
            resolution = data['resolution']
            if 'resolution_type' in resolution:
                if resolution['resolution_type'] not in VALID_RESOLUTION_TYPES:
                    issues.append(f"Invalid resolution_type: {resolution['resolution_type']}. Valid: {VALID_RESOLUTION_TYPES}")

        # Check for recommended fields
        recommended = ['details', 'context', 'impact']
        for field in recommended:
            if field not in data:
                warnings.append(f"Missing recommended field: {field}")

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

    def validate_all(self, escalations_dir: Path = None) -> List[ValidationResult]:
        """Validate all escalation event files."""
        escalations_dir = escalations_dir or Path("LogBook/escalations")
        results = []

        if not escalations_dir.exists():
            return results

        for esc_file in escalations_dir.rglob("*.yaml"):
            if 'schema' not in esc_file.name:
                result = self.validate_file(esc_file)
                results.append(result)

        for esc_file in escalations_dir.rglob("*.yml"):
            if 'schema' not in esc_file.name:
                result = self.validate_file(esc_file)
                results.append(result)

        return results

def format_text(results: List[ValidationResult]) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Escalation Event Validation Results")
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
        description="Validate escalation event files against schema"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to escalation event file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all escalation events in LogBook/escalations"
    )
    parser.add_argument(
        "--escalations-dir",
        type=Path,
        default=Path("LogBook/escalations"),
        help="Directory containing escalation event files"
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

    validator = EscalationValidator()

    if args.check_all:
        results = validator.validate_all(args.escalations_dir)
    elif args.file:
        results = [validator.validate_file(Path(args.file))]
    else:
        results = validator.validate_all(args.escalations_dir)

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
