#!/usr/bin/env python3
"""
Template Family Validator
Version: 1.0.0
Last Updated: 2025-12-31
Owner: Planner
Classification: MEDIUM - Template Governance

Validates template family membership and variant symmetry per README.md:808-809.

Features:
- Verifies templates have required 'family' field
- Checks Code and Test families have symmetric variants
- Validates family relationships in template metadata

Usage:
    python tools/template_family_validator.py --templates-dir templates/
    python tools/template_family_validator.py --check-symmetry
    python tools/template_family_validator.py --verbose

Exit Codes:
    0: All validations passed
    1: Validation failures found
    2: Configuration/runtime error
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import yaml

@dataclass
class ValidationResult:
    """Result of template family validation."""
    template_path: str
    has_family: bool
    family_name: Optional[str]
    variants: List[str]
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class SymmetryResult:
    """Result of variant symmetry check."""
    family: str
    code_variants: Set[str]
    test_variants: Set[str]
    symmetric: bool
    missing_test_variants: Set[str]
    missing_code_variants: Set[str]

# Template families per TEMPLATE_FAMILIES_POLICY.md
KNOWN_FAMILIES = [
    "api-crud",
    "service-base",
    "integration-test",
    "unit-test",
    "security-test",
    "performance-test",
    "task-scaffold",
    "workflow-scaffold",
]

# Required metadata fields for templates
REQUIRED_METADATA_FIELDS = ["family", "version", "description"]

def find_template_metadata(template_dir: Path) -> Optional[Path]:
    """Find metadata file in template directory."""
    candidates = [
        template_dir / "metadata.yaml",
        template_dir / "template_metadata.yaml",
        template_dir / "metadata.yml",
        template_dir / "template.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

def load_metadata(metadata_path: Path) -> Optional[Dict]:
    """Load and parse template metadata file."""
    try:
        with open(metadata_path, 'r') as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, IOError) as e:
        print(f"Error loading {metadata_path}: {e}", file=sys.stderr)
        return None

def validate_template_family(template_dir: Path) -> ValidationResult:
    """Validate a single template's family membership."""
    result = ValidationResult(
        template_path=str(template_dir),
        has_family=False,
        family_name=None,
        variants=[]
    )

    metadata_path = find_template_metadata(template_dir)
    if not metadata_path:
        result.issues.append(f"No metadata file found in {template_dir}")
        return result

    metadata = load_metadata(metadata_path)
    if not metadata:
        result.issues.append(f"Failed to parse metadata from {metadata_path}")
        return result

    # Check for family field
    if "family" in metadata:
        result.has_family = True
        result.family_name = metadata["family"]

        # Validate family name is known
        if result.family_name not in KNOWN_FAMILIES:
            result.warnings.append(
                f"Unknown family '{result.family_name}'. "
                f"Known families: {', '.join(KNOWN_FAMILIES)}"
            )
    else:
        result.issues.append("Missing required 'family' field in metadata")

    # Check for variants
    if "variants" in metadata:
        result.variants = metadata.get("variants", [])
    elif "variant" in metadata:
        result.variants = [metadata["variant"]]

    # Check other required fields
    for field_name in REQUIRED_METADATA_FIELDS:
        if field_name not in metadata:
            result.warnings.append(f"Missing recommended field: '{field_name}'")

    return result

def check_variant_symmetry(
    templates_dir: Path,
    code_family_pattern: str = "*-code*",
    test_family_pattern: str = "*-test*"
) -> List[SymmetryResult]:
    """Check that Code and Test families have symmetric variants."""
    results = []

    # Group templates by base family name
    families: Dict[str, Dict[str, Set[str]]] = defaultdict(
        lambda: {"code": set(), "test": set()}
    )

    for template_dir in templates_dir.iterdir():
        if not template_dir.is_dir():
            continue

        metadata_path = find_template_metadata(template_dir)
        if not metadata_path:
            continue

        metadata = load_metadata(metadata_path)
        if not metadata or "family" not in metadata:
            continue

        family = metadata["family"]
        variants = metadata.get("variants", [])
        if not variants and "variant" in metadata:
            variants = [metadata["variant"]]

        # Determine if code or test family
        template_name = template_dir.name.lower()
        if "test" in template_name or "test" in family.lower():
            families[family]["test"].update(variants if variants else [template_name])
        else:
            families[family]["code"].update(variants if variants else [template_name])

    # Check symmetry for each family
    for family_name, type_variants in families.items():
        code_variants = type_variants["code"]
        test_variants = type_variants["test"]

        # Find asymmetries
        missing_tests = code_variants - test_variants
        missing_code = test_variants - code_variants

        results.append(SymmetryResult(
            family=family_name,
            code_variants=code_variants,
            test_variants=test_variants,
            symmetric=len(missing_tests) == 0 and len(missing_code) == 0,
            missing_test_variants=missing_tests,
            missing_code_variants=missing_code
        ))

    return results

def validate_all_templates(templates_dir: Path, verbose: bool = False) -> Tuple[List[ValidationResult], bool]:
    """Validate all templates in directory."""
    results = []
    all_valid = True

    if not templates_dir.exists():
        print(f"Templates directory not found: {templates_dir}", file=sys.stderr)
        return results, False

    for template_dir in sorted(templates_dir.iterdir()):
        if not template_dir.is_dir():
            continue

        # Skip hidden directories and __pycache__
        if template_dir.name.startswith(('.', '_')):
            continue

        result = validate_template_family(template_dir)
        results.append(result)

        if result.issues:
            all_valid = False

        if verbose:
            status = "PASS" if not result.issues else "FAIL"
            print(f"[{status}] {template_dir.name}: family={result.family_name or 'MISSING'}")
            for issue in result.issues:
                print(f"  ERROR: {issue}")
            for warning in result.warnings:
                print(f"  WARN: {warning}")

    return results, all_valid

def main():
    parser = argparse.ArgumentParser(
        description="Validate template family membership and variant symmetry"
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path("templates"),
        help="Path to templates directory (default: templates/)"
    )
    parser.add_argument(
        "--check-symmetry",
        action="store_true",
        help="Check Code/Test family variant symmetry"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Validate all templates
    results, all_valid = validate_all_templates(args.templates_dir, args.verbose)

    if not results:
        print("No templates found to validate", file=sys.stderr)
        sys.exit(2)

    # Count statistics
    total = len(results)
    with_family = sum(1 for r in results if r.has_family)
    with_issues = sum(1 for r in results if r.issues)
    with_warnings = sum(1 for r in results if r.warnings)

    # Check variant symmetry if requested
    symmetry_results = []
    symmetry_ok = True
    if args.check_symmetry:
        symmetry_results = check_variant_symmetry(args.templates_dir)
        for sr in symmetry_results:
            if not sr.symmetric:
                symmetry_ok = False
                if args.verbose:
                    print(f"\n[ASYMMETRY] Family: {sr.family}")
                    if sr.missing_test_variants:
                        print(f"  Missing test variants: {sr.missing_test_variants}")
                    if sr.missing_code_variants:
                        print(f"  Missing code variants: {sr.missing_code_variants}")

    # JSON output
    if args.json:
        output = {
            "summary": {
                "total_templates": total,
                "with_family": with_family,
                "with_issues": with_issues,
                "with_warnings": with_warnings,
                "all_valid": all_valid and (symmetry_ok or not args.check_symmetry)
            },
            "templates": [
                {
                    "path": r.template_path,
                    "has_family": r.has_family,
                    "family": r.family_name,
                    "variants": r.variants,
                    "issues": r.issues,
                    "warnings": r.warnings
                }
                for r in results
            ]
        }
        if args.check_symmetry:
            output["symmetry"] = [
                {
                    "family": sr.family,
                    "symmetric": sr.symmetric,
                    "code_variants": list(sr.code_variants),
                    "test_variants": list(sr.test_variants),
                    "missing_test_variants": list(sr.missing_test_variants),
                    "missing_code_variants": list(sr.missing_code_variants)
                }
                for sr in symmetry_results
            ]
        print(json.dumps(output, indent=2))
    else:
        # Summary output
        print(f"\n{'='*50}")
        print("Template Family Validation Summary")
        print(f"{'='*50}")
        print(f"Total templates:    {total}")
        print(f"With family field:  {with_family} ({with_family*100//total if total else 0}%)")
        print(f"With issues:        {with_issues}")
        print(f"With warnings:      {with_warnings}")

        if args.check_symmetry:
            asymmetric = sum(1 for sr in symmetry_results if not sr.symmetric)
            print(f"Asymmetric families: {asymmetric}")

    # Determine exit code
    if args.strict and with_warnings > 0:
        all_valid = False

    if not all_valid or (args.check_symmetry and not symmetry_ok):
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
