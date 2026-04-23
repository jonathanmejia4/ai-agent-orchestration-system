#!/usr/bin/env python3
"""
audit_trail_validator.py - Audit Trail Validator

Document Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Compliance Tool

Purpose:
    Validates audit trails across a system components.
    Ensures traceability, completeness, and integrity of audit records.

Usage:
    python3 audit_trail_validator.py validate
    python3 audit_trail_validator.py validate --strict
    python3 audit_trail_validator.py check-integrity
    python3 audit_trail_validator.py report --format json
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

@dataclass
class AuditEntry:
    """Represents an audit trail entry."""
    entry_id: str
    timestamp: str
    actor: str
    action: str
    target: str
    result: str
    details: Dict = field(default_factory=dict)
    source_file: str = ""

@dataclass
class ValidationResult:
    """Result of an audit validation check."""
    check_name: str
    passed: bool
    severity: str
    message: str
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "details": self.details
        }

class AuditTrailValidator:
    """Validates the system audit trails."""

    REQUIRED_FIELDS = ["timestamp", "actor", "action", "target", "result"]

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.audit_entries: List[AuditEntry] = []
        self.results: List[ValidationResult] = []
        self._load_audit_entries()

    def _load_audit_entries(self):
        """Load all audit entries from the system."""
        audit_sources = [
            ("LogBook/pm/audit_log.yaml", "pm"),
            ("LogBook/builder/execution_log.yaml", "builder"),
            ("LogBook/critic/verdict_log.yaml", "critic"),
            ("LogBook/planner/planning_log.yaml", "planner"),
        ]

        for source_path, source_type in audit_sources:
            full_path = self.base_path / source_path
            if full_path.exists():
                self._load_from_file(full_path, source_type)

        # Also load from work order history
        self._load_work_order_audit()

    def _load_from_file(self, file_path: Path, source_type: str):
        """Load audit entries from a specific file."""
        if not HAS_YAML:
            return

        try:
            with open(file_path) as f:
                data = yaml.safe_load(f) or {}

            # Handle different log formats
            entries = []
            if "executions" in data:
                entries = data["executions"]
            elif "verdicts" in data:
                entries = data["verdicts"]
            elif "planning_entries" in data:
                entries = data["planning_entries"]
            elif "entries" in data:
                entries = data["entries"]
            elif "audit_log" in data:
                entries = data["audit_log"]

            for entry_data in entries:
                entry = AuditEntry(
                    entry_id=entry_data.get("execution_id") or
                             entry_data.get("verdict_id") or
                             entry_data.get("planning_id") or
                             entry_data.get("entry_id", "unknown"),
                    timestamp=entry_data.get("timestamp", ""),
                    actor=source_type,
                    action=entry_data.get("action") or
                           entry_data.get("review_type") or
                           entry_data.get("planning_type", "unknown"),
                    target=entry_data.get("work_order_id") or
                           entry_data.get("task_id") or
                           entry_data.get("target", "system"),
                    result=entry_data.get("status") or
                           entry_data.get("verdict", "unknown"),
                    details=entry_data.get("details", {}),
                    source_file=str(file_path)
                )
                self.audit_entries.append(entry)

        except Exception:
            pass

    def _load_work_order_audit(self):
        """Load audit entries from work order history."""
        wo_queue = self.base_path / "LogBook/pm/WO_QUEUE.yaml"
        if not wo_queue.exists() or not HAS_YAML:
            return

        try:
            with open(wo_queue) as f:
                data = yaml.safe_load(f) or {}

            for wo in data.get("work_orders", []):
                history = wo.get("history", [])
                for event in history:
                    entry = AuditEntry(
                        entry_id=f"{wo.get('work_order_id', 'unknown')}-{event.get('timestamp', '')}",
                        timestamp=event.get("timestamp", ""),
                        actor=event.get("agent", "system"),
                        action=event.get("action", "update"),
                        target=wo.get("work_order_id", "unknown"),
                        result=event.get("new_status", "unknown"),
                        details=event,
                        source_file=str(wo_queue)
                    )
                    self.audit_entries.append(entry)

        except Exception:
            pass

    def validate_all(self) -> List[ValidationResult]:
        """Run all validation checks."""
        self.results = []

        checks = [
            self._check_completeness,
            self._check_temporal_consistency,
            self._check_actor_validity,
            self._check_action_validity,
            self._check_traceability,
            self._check_gaps,
            self._check_duplicates,
        ]

        for check in checks:
            result = check()
            self.results.append(result)

        return self.results

    def _check_completeness(self) -> ValidationResult:
        """Check that all entries have required fields."""
        incomplete = []

        for entry in self.audit_entries:
            missing_fields = []
            if not entry.timestamp:
                missing_fields.append("timestamp")
            if not entry.actor:
                missing_fields.append("actor")
            if not entry.action:
                missing_fields.append("action")
            if not entry.target:
                missing_fields.append("target")
            if not entry.result:
                missing_fields.append("result")

            if missing_fields:
                incomplete.append({
                    "entry_id": entry.entry_id,
                    "missing": missing_fields,
                    "source": entry.source_file
                })

        passed = len(incomplete) == 0
        return ValidationResult(
            check_name="completeness",
            passed=passed,
            severity="high" if not passed else "info",
            message=f"Found {len(incomplete)} incomplete entries" if incomplete else "All entries complete",
            details={"incomplete_entries": incomplete[:10]}  # Limit to first 10
        )

    def _check_temporal_consistency(self) -> ValidationResult:
        """Check that timestamps are valid and in order."""
        issues = []

        sorted_entries = sorted(
            [e for e in self.audit_entries if e.timestamp],
            key=lambda x: x.timestamp
        )

        for i, entry in enumerate(sorted_entries):
            # Validate timestamp format
            try:
                datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
            except Exception:
                issues.append({
                    "entry_id": entry.entry_id,
                    "issue": "invalid_timestamp_format",
                    "timestamp": entry.timestamp
                })

        # Check for future timestamps
        now = datetime.utcnow()
        for entry in self.audit_entries:
            if entry.timestamp:
                try:
                    ts = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                    if ts.replace(tzinfo=None) > now:
                        issues.append({
                            "entry_id": entry.entry_id,
                            "issue": "future_timestamp",
                            "timestamp": entry.timestamp
                        })
                except Exception:
                    pass

        passed = len(issues) == 0
        return ValidationResult(
            check_name="temporal_consistency",
            passed=passed,
            severity="medium" if not passed else "info",
            message=f"Found {len(issues)} temporal issues" if issues else "All timestamps valid",
            details={"issues": issues[:10]}
        )

    def _check_actor_validity(self) -> ValidationResult:
        """Check that actors are valid agents."""
        valid_actors = {"pm", "builder", "critic", "planner", "system", "user"}
        invalid = []

        for entry in self.audit_entries:
            if entry.actor and entry.actor.lower() not in valid_actors:
                invalid.append({
                    "entry_id": entry.entry_id,
                    "actor": entry.actor
                })

        passed = len(invalid) == 0
        return ValidationResult(
            check_name="actor_validity",
            passed=passed,
            severity="low" if not passed else "info",
            message=f"Found {len(invalid)} entries with unknown actors" if invalid else "All actors valid",
            details={"invalid_actors": invalid[:10]}
        )

    def _check_action_validity(self) -> ValidationResult:
        """Check that actions are recognized."""
        valid_actions = {
            "create", "update", "delete", "approve", "reject",
            "build", "validate", "deploy", "rollback",
            "initialize", "complete", "block", "unblock",
            "assign", "escalate", "resolve", "review",
            "code", "architecture", "security", "documentation",
            "strategic", "tactical", "resource", "risk", "dependency"
        }
        unrecognized = []

        for entry in self.audit_entries:
            if entry.action and entry.action.lower() not in valid_actions:
                unrecognized.append({
                    "entry_id": entry.entry_id,
                    "action": entry.action
                })

        # This is informational, not a failure
        return ValidationResult(
            check_name="action_validity",
            passed=True,
            severity="info",
            message=f"Found {len(unrecognized)} entries with custom actions",
            details={"custom_actions": unrecognized[:10]}
        )

    def _check_traceability(self) -> ValidationResult:
        """Check that work orders have complete audit trails."""
        wo_audit = {}

        # Group by target (work order)
        for entry in self.audit_entries:
            if entry.target and entry.target.startswith("WO-"):
                if entry.target not in wo_audit:
                    wo_audit[entry.target] = []
                wo_audit[entry.target].append(entry)

        incomplete_trails = []

        for wo_id, entries in wo_audit.items():
            actions = {e.action for e in entries}
            # Check for lifecycle completeness
            has_create = any(a in actions for a in ["create", "initialize", "assign"])
            has_terminal = any(a in actions for a in ["complete", "approve", "reject", "cancel"])

            # If old work order without terminal state
            if has_create and not has_terminal:
                # Check if it's old enough to warrant concern
                if entries:
                    latest = max(e.timestamp for e in entries if e.timestamp)
                    try:
                        ts = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                        age_days = (datetime.utcnow() - ts.replace(tzinfo=None)).days
                        if age_days > 7:  # Week-old without completion
                            incomplete_trails.append({
                                "work_order": wo_id,
                                "last_action": latest,
                                "age_days": age_days
                            })
                    except Exception:
                        pass

        passed = len(incomplete_trails) == 0
        return ValidationResult(
            check_name="traceability",
            passed=passed,
            severity="medium" if not passed else "info",
            message=f"Found {len(incomplete_trails)} work orders with incomplete trails" if incomplete_trails else "All work orders have complete trails",
            details={"incomplete_trails": incomplete_trails[:10]}
        )

    def _check_gaps(self) -> ValidationResult:
        """Check for gaps in audit coverage."""
        sources_with_entries = set()

        for entry in self.audit_entries:
            if entry.source_file:
                sources_with_entries.add(Path(entry.source_file).name)

        expected_sources = {
            "execution_log.yaml",
            "verdict_log.yaml",
            "planning_log.yaml",
            "WO_QUEUE.yaml"
        }

        missing = expected_sources - sources_with_entries

        return ValidationResult(
            check_name="coverage_gaps",
            passed=len(missing) == 0,
            severity="medium" if missing else "info",
            message=f"Missing audit coverage for {len(missing)} sources" if missing else "Full audit coverage",
            details={"missing_sources": list(missing)}
        )

    def _check_duplicates(self) -> ValidationResult:
        """Check for duplicate entries."""
        seen = set()
        duplicates = []

        for entry in self.audit_entries:
            key = f"{entry.entry_id}:{entry.timestamp}:{entry.action}"
            if key in seen:
                duplicates.append({
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp
                })
            seen.add(key)

        passed = len(duplicates) == 0
        return ValidationResult(
            check_name="duplicates",
            passed=passed,
            severity="low" if not passed else "info",
            message=f"Found {len(duplicates)} duplicate entries" if duplicates else "No duplicates found",
            details={"duplicates": duplicates[:10]}
        )

    def check_integrity(self) -> ValidationResult:
        """Check integrity of audit files."""
        issues = []

        audit_files = list(self.base_path.glob("LogBook/**/*.yaml"))

        for audit_file in audit_files:
            try:
                content = audit_file.read_text()

                # Check for corruption indicators
                if '\x00' in content:
                    issues.append({
                        "file": str(audit_file),
                        "issue": "null_bytes_detected"
                    })

                # Validate YAML
                if HAS_YAML:
                    try:
                        yaml.safe_load(content)
                    except Exception as e:
                        issues.append({
                            "file": str(audit_file),
                            "issue": f"yaml_parse_error: {str(e)[:50]}"
                        })

            except Exception as e:
                issues.append({
                    "file": str(audit_file),
                    "issue": f"read_error: {str(e)[:50]}"
                })

        passed = len(issues) == 0
        return ValidationResult(
            check_name="integrity",
            passed=passed,
            severity="critical" if not passed else "info",
            message=f"Found {len(issues)} integrity issues" if issues else "All files pass integrity check",
            details={"issues": issues}
        )

    def get_report(self) -> dict:
        """Generate comprehensive validation report."""
        if not self.results:
            self.validate_all()

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_checks": len(self.results),
                "passed": passed,
                "failed": failed,
                "total_entries_analyzed": len(self.audit_entries)
            },
            "results": [r.to_dict() for r in self.results],
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []

        for result in self.results:
            if not result.passed:
                if result.check_name == "completeness":
                    recommendations.append("Ensure all audit entries include required fields: timestamp, actor, action, target, result")
                elif result.check_name == "temporal_consistency":
                    recommendations.append("Review and fix entries with invalid timestamps")
                elif result.check_name == "traceability":
                    recommendations.append("Update stale work orders or close incomplete ones")
                elif result.check_name == "coverage_gaps":
                    recommendations.append("Enable audit logging for all agent types")
                elif result.check_name == "integrity":
                    recommendations.append("Investigate and repair corrupted audit files immediately")

        return recommendations

def main():
    parser = argparse.ArgumentParser(description="Audit Trail Validator")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate audit trails")
    validate_parser.add_argument("--strict", action="store_true", help="Fail on any issue")

    # Integrity command
    integrity_parser = subparsers.add_parser("check-integrity", help="Check file integrity")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate validation report")

    # Common arguments
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    validator = AuditTrailValidator()

    if args.command == "validate":
        results = validator.validate_all()

        if args.format == "json":
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            print("\nAudit Trail Validation Results")
            print("=" * 50)

            for result in results:
                status = "\033[92mPASS\033[0m" if result.passed else f"\033[91mFAIL\033[0m"
                print(f"[{status}] {result.check_name}: {result.message}")

            passed = sum(1 for r in results if r.passed)
            print(f"\nTotal: {passed}/{len(results)} checks passed")

        if args.strict and any(not r.passed for r in results):
            return 1

    elif args.command == "check-integrity":
        result = validator.check_integrity()

        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        else:
            status = "PASS" if result.passed else "FAIL"
            print(f"\nIntegrity Check: {status}")
            print(result.message)
            if result.details.get("issues"):
                for issue in result.details["issues"]:
                    print(f"  - {issue['file']}: {issue['issue']}")

        return 0 if result.passed else 1

    elif args.command == "report":
        report = validator.get_report()

        if args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            print("\nAudit Trail Validation Report")
            print("=" * 50)
            print(f"Generated: {report['timestamp']}")
            print(f"\nSummary:")
            print(f"  Total Checks: {report['summary']['total_checks']}")
            print(f"  Passed: {report['summary']['passed']}")
            print(f"  Failed: {report['summary']['failed']}")
            print(f"  Entries Analyzed: {report['summary']['total_entries_analyzed']}")

            if report['recommendations']:
                print(f"\nRecommendations:")
                for rec in report['recommendations']:
                    print(f"  - {rec}")

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
