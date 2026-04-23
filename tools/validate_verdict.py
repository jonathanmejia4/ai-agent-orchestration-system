#!/usr/bin/env python3
"""
Verdict Validator
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Critic
Classification: HIGH - Quality Assurance

Validates Critic verdict files for completeness and scoring integrity.

Usage:
    python tools/validate_verdict.py <verdict_file>
    python tools/validate_verdict.py --check-current
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

@dataclass
class ValidationResult:
    """Result of validating a verdict."""
    file: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    score_valid: bool
    passed: bool

# Required fields for verdicts
REQUIRED_FIELDS = [
    'version',
    'verdict',
]

# Required verdict sub-fields
VERDICT_REQUIRED = [
    'task_id',
    'status',
    'overall_score',
]

# Required dimensions (7-dimension assessment)
# Must match PLANNING/schemas/critic_verdict_schema.yaml
# Issue M-15: Aligned with schema dimension names
REQUIRED_DIMENSIONS = [
    'Dependencies',
    'Effort',
    'ExecutionReady',
    'SpecFit',
    'Verification',
    'SecurityPolicy',
    'ACL',
]

# Valid verdict statuses
VALID_STATUSES = ['pending', 'pass', 'fail', 'conditional', 'needs_review']

class VerdictValidator:
    """Validates Critic verdict files."""

    def __init__(self, schema_path: Path = None):
        self.schema_path = schema_path
        self.schema = self._load_schema() if schema_path else None

    def _load_schema(self) -> Optional[Dict]:
        """Load validation schema if provided."""
        if not self.schema_path or not self.schema_path.exists():
            return None
        with open(self.schema_path, 'r') as f:
            return yaml.safe_load(f)

    def validate_file(self, verdict_path: Path) -> ValidationResult:
        """Validate a single verdict file."""
        issues: List[str] = []
        warnings: List[str] = []
        score_valid = True

        if not verdict_path.exists():
            return ValidationResult(
                file=str(verdict_path),
                status="error",
                issues=[f"File not found: {verdict_path}"],
                warnings=[],
                score_valid=False,
                passed=False
            )

        try:
            with open(verdict_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return ValidationResult(
                file=str(verdict_path),
                status="error",
                issues=[f"YAML parse error: {e}"],
                warnings=[],
                score_valid=False,
                passed=False
            )

        if not isinstance(data, dict):
            return ValidationResult(
                file=str(verdict_path),
                status="error",
                issues=["Verdict must be a YAML mapping"],
                warnings=[],
                score_valid=False,
                passed=False
            )

        # Check required top-level fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate verdict section
        verdict = data.get('verdict', {})
        if not isinstance(verdict, dict):
            issues.append("'verdict' must be a mapping")
        else:
            # Check required verdict fields
            for field in VERDICT_REQUIRED:
                if field not in verdict:
                    issues.append(f"Missing required verdict field: {field}")

            # Validate status
            status = verdict.get('status')
            if status and status not in VALID_STATUSES:
                issues.append(f"Invalid status: {status}. Valid: {VALID_STATUSES}")

            # Validate overall score
            overall_score = verdict.get('overall_score')
            if overall_score is not None:
                if not isinstance(overall_score, (int, float)):
                    issues.append("overall_score must be numeric")
                    score_valid = False
                elif not (0 <= overall_score <= 10):
                    issues.append(f"overall_score must be 0-10, got {overall_score}")
                    score_valid = False

        # Validate dimensions
        dimensions = data.get('dimensions', {})
        if not dimensions:
            warnings.append("No dimensions defined")
        else:
            dim_issues, dim_warnings, dim_score_valid = self._validate_dimensions(dimensions)
            issues.extend(dim_issues)
            warnings.extend(dim_warnings)
            if not dim_score_valid:
                score_valid = False

        # Validate findings
        findings = data.get('findings', [])
        if findings:
            finding_issues = self._validate_findings(findings)
            issues.extend(finding_issues)

        # Check for recommended fields
        recommended = ['reviewed_at', 'reviewer', 'task_version']
        for field in recommended:
            if field not in verdict:
                warnings.append(f"Missing recommended field: verdict.{field}")

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
            file=str(verdict_path),
            status=status,
            issues=issues,
            warnings=warnings,
            score_valid=score_valid,
            passed=passed
        )

    def _validate_dimensions(
        self,
        dimensions: Dict[str, Any]
    ) -> tuple[List[str], List[str], bool]:
        """Validate dimension scores."""
        issues = []
        warnings = []
        score_valid = True

        # Check for missing dimensions
        for dim in REQUIRED_DIMENSIONS:
            if dim not in dimensions:
                warnings.append(f"Missing dimension: {dim}")

        # Validate each dimension
        for dim_name, dim_data in dimensions.items():
            if not isinstance(dim_data, dict):
                issues.append(f"Dimension '{dim_name}' must be a mapping")
                continue

            # Validate score
            score = dim_data.get('score')
            if score is not None:
                if not isinstance(score, (int, float)):
                    issues.append(f"Dimension '{dim_name}' score must be numeric")
                    score_valid = False
                elif not (0 <= score <= 10):
                    issues.append(f"Dimension '{dim_name}' score must be 0-10, got {score}")
                    score_valid = False

            # Validate status
            status = dim_data.get('status')
            valid_dim_statuses = ['PASS', 'FAIL', 'WARN', 'SKIP', None]
            if status and status not in valid_dim_statuses:
                issues.append(f"Dimension '{dim_name}' has invalid status: {status}")

        return issues, warnings, score_valid

    def _validate_findings(self, findings: Any) -> List[str]:
        """Validate findings list."""
        issues = []

        if not isinstance(findings, list):
            issues.append("'findings' must be a list")
            return issues

        for i, finding in enumerate(findings):
            if not isinstance(finding, dict):
                issues.append(f"Finding {i} must be a mapping")
                continue

            # Required finding fields
            if 'severity' not in finding:
                issues.append(f"Finding {i} missing 'severity'")
            else:
                valid_severities = ['critical', 'high', 'medium', 'low', 'info']
                if finding['severity'] not in valid_severities:
                    issues.append(f"Finding {i} has invalid severity: {finding['severity']}")

            if 'message' not in finding:
                issues.append(f"Finding {i} missing 'message'")

        return issues

    def validate_current(self) -> ValidationResult:
        """Validate the current task's verdict."""
        verdict_path = Path(".task/verdict.yaml")
        return self.validate_file(verdict_path)

def format_text(result: ValidationResult) -> str:
    """Format result as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Verdict Validation Results")
    lines.append("=" * 60)
    lines.append("")

    status_icon = "✓" if result.passed else "✗"
    lines.append(f"{status_icon} {result.file}: {result.status}")
    lines.append(f"  Score valid: {result.score_valid}")
    lines.append("")

    if result.issues:
        lines.append("Errors:")
        for issue in result.issues:
            lines.append(f"  - {issue}")
        lines.append("")

    if result.warnings:
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")
        lines.append("")

    lines.append("=" * 60)
    status = "PASSED" if result.passed else "FAILED"
    lines.append(f"Status: {status}")
    lines.append("=" * 60)

    return "\n".join(lines)

def format_json(result: ValidationResult) -> str:
    """Format result as JSON."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "result": asdict(result)
    }
    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Validate Critic verdict files"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to verdict file to validate"
    )
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Validate current task's verdict (.task/verdict.yaml)"
    )
    parser.add_argument(
        "--schema",
        type=Path,
        help="Path to validation schema"
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

    validator = VerdictValidator(args.schema)

    if args.check_current:
        result = validator.validate_current()
    elif args.file:
        result = validator.validate_file(Path(args.file))
    else:
        # Default: check current
        result = validator.validate_current()

    # Format output
    if args.format == "json":
        output = format_json(result)
    else:
        output = format_text(result)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Exit code
    sys.exit(0 if result.passed else 1)

if __name__ == "__main__":
    main()
