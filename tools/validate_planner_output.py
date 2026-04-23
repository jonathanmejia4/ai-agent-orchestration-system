#!/usr/bin/env python3
"""
Planner Output Validator
Version: 1.0.0
Last Updated: 2026-01-05
Owner: Planner
Classification: HIGH - Planning Validation

Validates planner output files against planner_output_schema.yaml.

Usage:
    python tools/validate_planner_output.py <planner_output_file>
    python tools/validate_planner_output.py --check-all
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
    """Result of validating a planner output."""
    file: str
    status: str  # valid, warning, error
    issues: List[str]
    warnings: List[str]
    passed: bool

# Required fields (matches planner_output_schema.yaml:13-18)
REQUIRED_FIELDS = [
    'analysis_id',
    'timestamp',
    'request_type',
    'analysis',
    'recommendations',
]

# Valid request_type values (matches planner_output_schema.yaml:32-40)
VALID_REQUEST_TYPES = [
    'feasibility_analysis',
    'effort_estimation',
    'risk_assessment',
    'dependency_analysis',
    'architecture_review',
    'implementation_planning',
    'resource_optimization',
]

# Valid assessment values (matches planner_output_schema.yaml:76-77)
VALID_ASSESSMENTS = ['favorable', 'neutral', 'concerning', 'blocking']

# Valid complexity values (matches planner_output_schema.yaml:89-90)
VALID_COMPLEXITIES = ['low', 'medium', 'high', 'very_high']

# Valid probability values (matches planner_output_schema.yaml:133-134)
VALID_PROBABILITIES = ['low', 'medium', 'high']

# Valid impact values (matches planner_output_schema.yaml:136-137)
VALID_IMPACTS = ['low', 'medium', 'high', 'critical']

# Valid approach values (matches planner_output_schema.yaml:153-159)
VALID_APPROACHES = [
    'proceed_as_planned',
    'proceed_with_modifications',
    'additional_analysis_needed',
    'not_recommended',
    'defer',
]

# Pattern for analysis_id (matches planner_output_schema.yaml:22-23)
ANALYSIS_ID_PATTERN = r'^ANL-[0-9]{4}-[0-9]{3}$'

class PlannerOutputValidator:
    """Validates planner output files."""

    DEFAULT_SCHEMA_PATH = Path("PLANNING/schemas/planner_output_schema.yaml")

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
        """Validate a single planner output file."""
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
                issues=["Planner output must be a YAML mapping"],
                warnings=[],
                passed=False
            )

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate analysis_id pattern
        if 'analysis_id' in data:
            anl_id = data['analysis_id']
            if not isinstance(anl_id, str) or not re.match(ANALYSIS_ID_PATTERN, anl_id):
                issues.append(f"Invalid analysis_id format: {anl_id}. Expected: ANL-YYYY-NNN")

        # Validate request_type
        if 'request_type' in data:
            if data['request_type'] not in VALID_REQUEST_TYPES:
                issues.append(f"Invalid request_type: {data['request_type']}. Valid: {VALID_REQUEST_TYPES}")

        # Validate analysis object
        if 'analysis' in data:
            analysis_issues, analysis_warnings = self._validate_analysis(data['analysis'])
            issues.extend(analysis_issues)
            warnings.extend(analysis_warnings)

        # Validate risks if present
        if 'risks' in data and isinstance(data['risks'], list):
            risk_issues, risk_warnings = self._validate_risks(data['risks'])
            issues.extend(risk_issues)
            warnings.extend(risk_warnings)

        # Validate recommendations object
        if 'recommendations' in data:
            rec_issues, rec_warnings = self._validate_recommendations(data['recommendations'])
            issues.extend(rec_issues)
            warnings.extend(rec_warnings)

        # Check for recommended fields
        recommended = ['request_context', 'risks', 'constraints', 'metadata']
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

    def _validate_analysis(self, analysis: Any) -> tuple[List[str], List[str]]:
        """Validate analysis object."""
        issues = []
        warnings = []

        if not isinstance(analysis, dict):
            issues.append("analysis must be an object")
            return issues, warnings

        # Required fields in analysis
        if 'summary' not in analysis:
            issues.append("analysis missing required field: summary")
        else:
            summary = analysis['summary']
            if isinstance(summary, str):
                if len(summary) < 50:
                    warnings.append(f"analysis.summary too short ({len(summary)} chars). Minimum: 50")
                if len(summary) > 500:
                    issues.append(f"analysis.summary too long ({len(summary)} chars). Maximum: 500")

        if 'findings' not in analysis:
            issues.append("analysis missing required field: findings")
        elif isinstance(analysis['findings'], list):
            for i, finding in enumerate(analysis['findings']):
                if not isinstance(finding, dict):
                    issues.append(f"analysis.findings[{i}] must be an object")
                    continue
                if 'aspect' not in finding:
                    issues.append(f"analysis.findings[{i}] missing required field: aspect")
                if 'assessment' not in finding:
                    issues.append(f"analysis.findings[{i}] missing required field: assessment")
                elif finding['assessment'] not in VALID_ASSESSMENTS:
                    issues.append(f"Invalid analysis.findings[{i}].assessment: {finding['assessment']}. Valid: {VALID_ASSESSMENTS}")

        # Validate technical_analysis if present
        if 'technical_analysis' in analysis and isinstance(analysis['technical_analysis'], dict):
            tech = analysis['technical_analysis']
            if 'complexity' in tech and tech['complexity'] not in VALID_COMPLEXITIES:
                issues.append(f"Invalid analysis.technical_analysis.complexity: {tech['complexity']}. Valid: {VALID_COMPLEXITIES}")

        # Validate effort_estimate if present
        if 'effort_estimate' in analysis and isinstance(analysis['effort_estimate'], dict):
            effort = analysis['effort_estimate']
            if 'confidence' in effort:
                conf = effort['confidence']
                if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
                    issues.append(f"analysis.effort_estimate.confidence must be a number between 0 and 1")

        return issues, warnings

    def _validate_risks(self, risks: List) -> tuple[List[str], List[str]]:
        """Validate risks array."""
        issues = []
        warnings = []

        for i, risk in enumerate(risks):
            if not isinstance(risk, dict):
                issues.append(f"risks[{i}] must be an object")
                continue

            # Required fields in risk
            if 'risk' not in risk:
                issues.append(f"risks[{i}] missing required field: risk")
            if 'probability' not in risk:
                issues.append(f"risks[{i}] missing required field: probability")
            elif risk['probability'] not in VALID_PROBABILITIES:
                issues.append(f"Invalid risks[{i}].probability: {risk['probability']}. Valid: {VALID_PROBABILITIES}")
            if 'impact' not in risk:
                issues.append(f"risks[{i}] missing required field: impact")
            elif risk['impact'] not in VALID_IMPACTS:
                issues.append(f"Invalid risks[{i}].impact: {risk['impact']}. Valid: {VALID_IMPACTS}")

        return issues, warnings

    def _validate_recommendations(self, recommendations: Any) -> tuple[List[str], List[str]]:
        """Validate recommendations object."""
        issues = []
        warnings = []

        if not isinstance(recommendations, dict):
            issues.append("recommendations must be an object")
            return issues, warnings

        # Required field
        if 'primary_recommendation' not in recommendations:
            issues.append("recommendations missing required field: primary_recommendation")

        # Validate approach if present
        if 'approach' in recommendations:
            if recommendations['approach'] not in VALID_APPROACHES:
                issues.append(f"Invalid recommendations.approach: {recommendations['approach']}. Valid: {VALID_APPROACHES}")

        # Validate implementation_phases if present
        if 'implementation_phases' in recommendations and isinstance(recommendations['implementation_phases'], list):
            for i, phase in enumerate(recommendations['implementation_phases']):
                if not isinstance(phase, dict):
                    issues.append(f"recommendations.implementation_phases[{i}] must be an object")
                    continue
                if 'phase' not in phase:
                    issues.append(f"recommendations.implementation_phases[{i}] missing required field: phase")
                if 'description' not in phase:
                    issues.append(f"recommendations.implementation_phases[{i}] missing required field: description")

        return issues, warnings

    def validate_all(self, outputs_dir: Path = None) -> List[ValidationResult]:
        """Validate all planner output files."""
        outputs_dir = outputs_dir or Path("LogBook/planner")
        results = []

        if not outputs_dir.exists():
            return results

        for output_file in outputs_dir.rglob("*.yaml"):
            if 'schema' not in output_file.name:
                result = self.validate_file(output_file)
                results.append(result)

        for output_file in outputs_dir.rglob("*.yml"):
            if 'schema' not in output_file.name:
                result = self.validate_file(output_file)
                results.append(result)

        return results

def format_text(results: List[ValidationResult]) -> str:
    """Format results as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("Planner Output Validation Results")
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
        description="Validate planner output files against schema"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to planner output file to validate"
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Validate all planner outputs in LogBook/planner"
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=Path("LogBook/planner"),
        help="Directory containing planner output files"
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

    validator = PlannerOutputValidator()

    if args.check_all:
        results = validator.validate_all(args.outputs_dir)
    elif args.file:
        results = [validator.validate_file(Path(args.file))]
    else:
        results = validator.validate_all(args.outputs_dir)

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
