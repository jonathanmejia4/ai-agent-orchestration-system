#!/usr/bin/env python3
"""
Validate Critic Verdict - Schema and Completeness Validator

Validates critic verdict files against critic_verdict_schema.yaml and enforces
dimension completeness, consistency rules, and critical dimension requirements.

Usage:
    python3 tools/validate_critic_verdict.py <verdict_file>
    python3 tools/validate_critic_verdict.py --all LogBook/critic/verdicts/
    python3 tools/validate_critic_verdict.py --check-dimension Security LogBook/critic/verdicts/
    python3 tools/validate_critic_verdict.py --json <verdict_file>
    python3 tools/validate_critic_verdict.py --help

Exit Codes:
    0 - Validation passed
    1 - Validation errors found
    2 - Error (missing files, invalid arguments)

Referenced in:
    - PLANNING/schemas/critic_verdict_schema.yaml:392
    - PLANNING/STAGE_GATED_GENERATION_PIPELINE_POLICY.md:49, 184, 1761, 2076
    - .claude/guidelines/agent-coordination-protocol.md

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Optional YAML support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

# Required dimensions for complete verdict
# Issue M-15: Aligned with PLANNING/schemas/critic_verdict_schema.yaml
REQUIRED_DIMENSIONS = [
    "Dependencies",
    "Effort",
    "ExecutionReady",
    "SpecFit",
    "Verification",
    "SecurityPolicy",
    "ACL"
]

# Critical dimensions that must PASS for APPROVED verdict
# Issue M-15: Aligned with schema (SecurityPolicy, SpecFit, Verification)
CRITICAL_DIMENSIONS = ["SecurityPolicy", "SpecFit", "Verification"]

# Valid verdict values
VALID_VERDICTS = ["APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"]

# Valid recommendations
VALID_RECOMMENDATIONS = ["promote_to_main", "rework_required", "escalate_to_human"]

# Valid dimension results
VALID_DIMENSION_RESULTS = ["PASS", "FAIL", "SKIP"]

@dataclass
class ValidationResult:
    """Verdict validation result"""
    valid: bool = True
    verdict_file: Optional[str] = None
    verdict_id: Optional[str] = None
    schema_errors: List[str] = field(default_factory=list)
    missing_dimensions: List[str] = field(default_factory=list)
    consistency_errors: List[str] = field(default_factory=list)
    critical_dimension_failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, category: str, message: str):
        self.valid = False
        if category == "schema":
            self.schema_errors.append(message)
        elif category == "dimension":
            self.missing_dimensions.append(message)
        elif category == "consistency":
            self.consistency_errors.append(message)
        elif category == "critical":
            self.critical_dimension_failures.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'verdict_file': self.verdict_file,
            'verdict_id': self.verdict_id,
            'schema_errors': self.schema_errors,
            'missing_dimensions': self.missing_dimensions,
            'consistency_errors': self.consistency_errors,
            'critical_dimension_failures': self.critical_dimension_failures,
            'warnings': self.warnings,
            'error_count': (len(self.schema_errors) + len(self.missing_dimensions) +
                           len(self.consistency_errors) + len(self.critical_dimension_failures))
        }

@dataclass
class BatchResult:
    """Batch validation result"""
    total_files: int = 0
    valid_files: int = 0
    invalid_files: int = 0
    dimension_coverage: Dict[str, int] = field(default_factory=dict)
    results: List[ValidationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_files': self.total_files,
            'valid_files': self.valid_files,
            'invalid_files': self.invalid_files,
            'dimension_coverage': self.dimension_coverage,
            'results': [r.to_dict() for r in self.results]
        }

class CriticVerdictValidator:
    """Validates critic verdict files"""

    # Verdict ID pattern: VER-YYYYMMDD-NNN
    VERDICT_ID_PATTERN = r'^VER-\d{8}-\d{3}$'

    # Review ID pattern: REV-YYYYMMDD-NNN
    REVIEW_ID_PATTERN = r'^REV-\d{8}-\d{3}$'

    # UUID v4 pattern
    UUID_PATTERN = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'

    # ISO 8601 timestamp pattern
    ISO_TIMESTAMP_PATTERN = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'

    # ISO 8601 duration pattern
    ISO_DURATION_PATTERN = r'^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?$'

    def __init__(self, repo_root: Optional[Path] = None, verbose: bool = False):
        self.repo_root = repo_root or Path.cwd()
        self.verbose = verbose
        self.schema_path = self.repo_root / 'PLANNING' / 'schemas' / 'critic_verdict_schema.yaml'

    def log(self, message: str):
        """Log message if verbose"""
        if self.verbose:
            print(f"  [DEBUG] {message}", file=sys.stderr)

    def load_verdict(self, path: Path) -> Optional[Dict]:
        """Load a verdict YAML file"""
        if not HAS_YAML:
            return None

        if not path.exists():
            return None

        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.log(f"Error loading {path}: {e}")
            return None

    def validate_schema(self, verdict: Dict, result: ValidationResult):
        """Validate verdict against schema requirements"""
        # Check verdict_id format
        verdict_id = verdict.get('verdict_id', '')
        if verdict_id:
            result.verdict_id = verdict_id
            if not re.match(self.VERDICT_ID_PATTERN, verdict_id):
                result.add_error("schema", f"Invalid verdict_id format: {verdict_id} (expected VER-YYYYMMDD-NNN)")
        else:
            result.add_error("schema", "Missing required field: verdict_id")

        # Check review_id format
        review_id = verdict.get('review_id', '')
        if review_id:
            if not re.match(self.REVIEW_ID_PATTERN, review_id):
                result.add_warning(f"Review ID format may be non-standard: {review_id}")
        else:
            result.add_error("schema", "Missing required field: review_id")

        # Check task_id (UUID v4 or X.Y format)
        task_id = verdict.get('task_id', '')
        if task_id:
            if not (re.match(self.UUID_PATTERN, str(task_id).lower()) or
                    re.match(r'^\d+\.\d+$', str(task_id))):
                result.add_warning(f"task_id format may be non-standard: {task_id}")
        else:
            result.add_error("schema", "Missing required field: task_id")

        # Check timestamp
        timestamp = verdict.get('timestamp', '')
        if timestamp:
            if not re.match(self.ISO_TIMESTAMP_PATTERN, str(timestamp)):
                result.add_error("schema", f"Invalid timestamp format: {timestamp} (expected ISO 8601)")
        else:
            result.add_error("schema", "Missing required field: timestamp")

        # Check final_verdict enum
        final_verdict = verdict.get('final_verdict', '')
        if final_verdict:
            if final_verdict not in VALID_VERDICTS:
                result.add_error("schema", f"Invalid final_verdict: {final_verdict} (expected one of {VALID_VERDICTS})")
        else:
            result.add_error("schema", "Missing required field: final_verdict")

        # Check recommendation enum
        recommendation = verdict.get('recommendation', '')
        if recommendation:
            if recommendation not in VALID_RECOMMENDATIONS:
                result.add_error("schema", f"Invalid recommendation: {recommendation} (expected one of {VALID_RECOMMENDATIONS})")
        else:
            result.add_error("schema", "Missing required field: recommendation")

        # Validate effort metrics if present
        effort = verdict.get('effort_metrics', {})
        if effort:
            self._validate_effort_metrics(effort, result)

    def _validate_effort_metrics(self, effort: Dict, result: ValidationResult):
        """Validate effort metrics section"""
        # Check estimated_effort duration format
        estimated = effort.get('estimated_effort', '')
        if estimated and not re.match(self.ISO_DURATION_PATTERN, str(estimated)):
            result.add_warning(f"estimated_effort not ISO 8601 duration: {estimated}")

        # Check actual_effort duration format
        actual = effort.get('actual_effort', '')
        if actual and not re.match(self.ISO_DURATION_PATTERN, str(actual)):
            result.add_warning(f"actual_effort not ISO 8601 duration: {actual}")

        # Check effort_accuracy range
        accuracy = effort.get('effort_accuracy')
        if accuracy is not None:
            try:
                acc_val = float(accuracy)
                if acc_val < 0 or acc_val > 100:
                    result.add_error("schema", f"effort_accuracy out of range: {accuracy} (expected 0-100)")
            except (ValueError, TypeError):
                result.add_error("schema", f"effort_accuracy not numeric: {accuracy}")

    def validate_dimensions(self, verdict: Dict, result: ValidationResult):
        """Validate dimension completeness"""
        dimension_results = verdict.get('dimension_results', {})

        if not dimension_results:
            result.add_error("dimension", "No dimension_results found")
            return

        # Check all required dimensions are present
        for dim in REQUIRED_DIMENSIONS:
            if dim not in dimension_results:
                result.add_error("dimension", f"Missing required dimension: {dim}")
            else:
                dim_data = dimension_results[dim]
                self._validate_dimension_entry(dim, dim_data, result)

    def _validate_dimension_entry(self, dim_name: str, dim_data: Dict, result: ValidationResult):
        """Validate a single dimension entry"""
        if not isinstance(dim_data, dict):
            result.add_error("schema", f"Dimension {dim_name} is not a dict")
            return

        # Check result field
        dim_result = dim_data.get('result', '')
        if dim_result not in VALID_DIMENSION_RESULTS:
            result.add_error("schema", f"Dimension {dim_name} has invalid result: {dim_result}")

        # Check score field
        score = dim_data.get('score')
        if score is not None:
            try:
                score_val = float(score)
                if score_val < 0 or score_val > 100:
                    result.add_error("schema", f"Dimension {dim_name} score out of range: {score}")
            except (ValueError, TypeError):
                result.add_error("schema", f"Dimension {dim_name} score not numeric: {score}")

    def validate_consistency(self, verdict: Dict, result: ValidationResult):
        """Validate consistency rules from schema"""
        final_verdict = verdict.get('final_verdict', '')
        conditions = verdict.get('conditions', [])
        rejection_reasons = verdict.get('rejection_reasons', [])
        recommendation = verdict.get('recommendation', '')

        # Rule 1: If APPROVED → conditions/rejection_reasons MUST be empty
        if final_verdict == 'APPROVED':
            if conditions:
                result.add_error("consistency", "APPROVED verdict should not have conditions")
            if rejection_reasons:
                result.add_error("consistency", "APPROVED verdict should not have rejection_reasons")

        # Rule 2: If APPROVED_WITH_CONDITIONS → conditions non-empty, rejection_reasons empty
        if final_verdict == 'APPROVED_WITH_CONDITIONS':
            if not conditions:
                result.add_error("consistency", "APPROVED_WITH_CONDITIONS requires non-empty conditions")
            if rejection_reasons:
                result.add_error("consistency", "APPROVED_WITH_CONDITIONS should not have rejection_reasons")

        # Rule 3: If REJECTED → rejection_reasons non-empty
        if final_verdict == 'REJECTED':
            if not rejection_reasons:
                result.add_error("consistency", "REJECTED verdict requires non-empty rejection_reasons")

        # Rule 4: If APPROVED/APPROVED_WITH_CONDITIONS → recommendation = "promote_to_main"
        if final_verdict in ['APPROVED', 'APPROVED_WITH_CONDITIONS']:
            if recommendation != 'promote_to_main':
                result.add_error("consistency",
                    f"{final_verdict} should have recommendation='promote_to_main', got '{recommendation}'")

        # Rule 5: If REJECTED → recommendation = "rework_required" or "escalate_to_human"
        if final_verdict == 'REJECTED':
            if recommendation not in ['rework_required', 'escalate_to_human']:
                result.add_error("consistency",
                    f"REJECTED should have recommendation='rework_required' or 'escalate_to_human', got '{recommendation}'")

    def validate_critical_dimensions(self, verdict: Dict, result: ValidationResult):
        """Validate critical dimensions pass for approved verdicts"""
        final_verdict = verdict.get('final_verdict', '')
        dimension_results = verdict.get('dimension_results', {})

        # Critical dimensions must PASS for APPROVED/APPROVED_WITH_CONDITIONS
        if final_verdict in ['APPROVED', 'APPROVED_WITH_CONDITIONS']:
            for dim in CRITICAL_DIMENSIONS:
                if dim in dimension_results:
                    dim_result = dimension_results[dim].get('result', '')
                    if dim_result != 'PASS':
                        result.add_error("critical",
                            f"Critical dimension {dim} must PASS for {final_verdict}, got '{dim_result}'")

    def validate(self, verdict_path: Path) -> ValidationResult:
        """Run full validation on a verdict file"""
        result = ValidationResult(verdict_file=str(verdict_path))

        if not HAS_YAML:
            result.add_error("schema", "YAML parser not available (pip install pyyaml)")
            return result

        if not verdict_path.exists():
            result.add_error("schema", f"Verdict file not found: {verdict_path}")
            return result

        verdict = self.load_verdict(verdict_path)
        if not verdict:
            result.add_error("schema", f"Failed to parse verdict file: {verdict_path}")
            return result

        # Run all validations
        self.log("Running schema validation...")
        self.validate_schema(verdict, result)

        self.log("Running dimension validation...")
        self.validate_dimensions(verdict, result)

        self.log("Running consistency validation...")
        self.validate_consistency(verdict, result)

        self.log("Running critical dimension validation...")
        self.validate_critical_dimensions(verdict, result)

        return result

    def validate_batch(self, directory: Path,
                       check_dimension: Optional[str] = None) -> BatchResult:
        """Validate all verdict files in a directory"""
        batch = BatchResult()

        # Initialize dimension coverage
        for dim in REQUIRED_DIMENSIONS:
            batch.dimension_coverage[dim] = 0

        # Find verdict files
        verdict_files = list(directory.glob('*.yaml')) + list(directory.glob('*.yml'))

        for verdict_path in verdict_files:
            batch.total_files += 1

            result = self.validate(verdict_path)
            batch.results.append(result)

            if result.valid:
                batch.valid_files += 1
            else:
                batch.invalid_files += 1

            # Track dimension coverage
            verdict = self.load_verdict(verdict_path)
            if verdict:
                dimensions = verdict.get('dimension_results', {})
                for dim in dimensions:
                    if dim in batch.dimension_coverage:
                        batch.dimension_coverage[dim] += 1

        return batch

def print_result(result: ValidationResult, format: str = "text"):
    """Print validation result"""
    if format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return

    print()
    if result.valid:
        print(f"\033[92m✅ Verdict validation passed\033[0m")
    else:
        print(f"\033[91m❌ Verdict validation failed\033[0m")

    if result.verdict_id:
        print(f"Verdict ID: {result.verdict_id}")
    if result.verdict_file:
        print(f"File: {result.verdict_file}")

    if result.schema_errors:
        print(f"\nSchema Errors ({len(result.schema_errors)}):")
        for err in result.schema_errors:
            print(f"  - {err}")

    if result.missing_dimensions:
        print(f"\nMissing Dimensions ({len(result.missing_dimensions)}):")
        for err in result.missing_dimensions:
            print(f"  - {err}")

    if result.consistency_errors:
        print(f"\nConsistency Errors ({len(result.consistency_errors)}):")
        for err in result.consistency_errors:
            print(f"  - {err}")

    if result.critical_dimension_failures:
        print(f"\nCritical Dimension Failures ({len(result.critical_dimension_failures)}):")
        for err in result.critical_dimension_failures:
            print(f"  - {err}")

    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for warn in result.warnings:
            print(f"  ⚠ {warn}")

def print_batch_result(batch: BatchResult, format: str = "text"):
    """Print batch validation result"""
    if format == "json":
        print(json.dumps(batch.to_dict(), indent=2))
        return

    print("\n" + "=" * 60)
    print("CRITIC VERDICT BATCH VALIDATION")
    print("=" * 60)

    print(f"\nTotal files: {batch.total_files}")
    print(f"  Valid: {batch.valid_files}")
    print(f"  Invalid: {batch.invalid_files}")

    if batch.dimension_coverage:
        print("\nDimension Coverage:")
        for dim, count in sorted(batch.dimension_coverage.items()):
            pct = (count / batch.total_files * 100) if batch.total_files > 0 else 0
            print(f"  {dim}: {count}/{batch.total_files} ({pct:.1f}%)")

    if batch.invalid_files > 0:
        print("\nInvalid Verdicts:")
        for r in batch.results:
            if not r.valid:
                print(f"  - {r.verdict_file}: {r.to_dict()['error_count']} errors")

def main():
    parser = argparse.ArgumentParser(
        description='Validate critic verdict files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate single verdict
    %(prog)s LogBook/critic/verdicts/VER-20251223-001.yaml

    # Validate all verdicts in directory
    %(prog)s --all LogBook/critic/verdicts/

    # Check specific dimension coverage
    %(prog)s --check-dimension Security LogBook/critic/verdicts/

    # JSON output
    %(prog)s --json VER-20251223-001.yaml

Exit Codes:
    0 - Validation passed
    1 - Validation errors found
    2 - Error (missing files, invalid arguments)
        """
    )

    parser.add_argument('path', nargs='?', type=Path,
                       help='Verdict file or directory to validate')
    parser.add_argument('--all', '-a', action='store_true',
                       help='Validate all verdict files in directory')
    parser.add_argument('--check-dimension', '-d', metavar='DIM',
                       help='Check coverage for specific dimension')
    parser.add_argument('--json', action='store_true',
                       help='Output result as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd(),
                       help='Repository root directory')

    args = parser.parse_args()

    if not args.path:
        parser.print_help()
        sys.exit(2)

    validator = CriticVerdictValidator(
        repo_root=args.repo_root,
        verbose=args.verbose
    )

    # Determine validation mode
    if args.all or args.path.is_dir():
        directory = args.path if args.path.is_dir() else args.path.parent
        batch = validator.validate_batch(directory, args.check_dimension)
        print_batch_result(batch, 'json' if args.json else 'text')
        sys.exit(0 if batch.invalid_files == 0 else 1)
    else:
        result = validator.validate(args.path)
        print_result(result, 'json' if args.json else 'text')
        sys.exit(0 if result.valid else 1)

if __name__ == '__main__':
    main()
