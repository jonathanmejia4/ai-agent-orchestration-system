#!/usr/bin/env python3
"""
Variant Symmetry Checker
Version: 1.0.0
Last Updated: 2025-12-31
Owner: Planner
Classification: MEDIUM - Template Governance

Verifies Code and Test template families have symmetric variants.
Per README.md:809 - "Variant symmetry enforcement"

Usage:
    python tools/variant_symmetry_checker.py --templates-dir templates/
    python tools/variant_symmetry_checker.py --verbose

Exit Codes:
    0: All families symmetric
    1: Asymmetric variants found
    2: Configuration/runtime error
"""

import argparse
import sys
from pathlib import Path

# Import from template_family_validator for shared functionality
try:
    from template_family_validator import (
        check_variant_symmetry,
        SymmetryResult
    )
except ImportError:
    # Fallback if run standalone
    import json
    from collections import defaultdict
    from dataclasses import dataclass
    from typing import Dict, List, Optional, Set
    import yaml

    @dataclass
    class SymmetryResult:
        family: str
        code_variants: Set[str]
        test_variants: Set[str]
        symmetric: bool
        missing_test_variants: Set[str]
        missing_code_variants: Set[str]

    def find_template_metadata(template_dir: Path) -> Optional[Path]:
        candidates = [
            template_dir / "metadata.yaml",
            template_dir / "template_metadata.yaml",
            template_dir / "metadata.yml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def load_metadata(metadata_path: Path) -> Optional[Dict]:
        try:
            with open(metadata_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    def check_variant_symmetry(templates_dir: Path, **kwargs) -> List[SymmetryResult]:
        results = []
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

            template_name = template_dir.name.lower()
            if "test" in template_name or "test" in family.lower():
                families[family]["test"].update(variants if variants else [template_name])
            else:
                families[family]["code"].update(variants if variants else [template_name])

        for family_name, type_variants in families.items():
            code_variants = type_variants["code"]
            test_variants = type_variants["test"]

            results.append(SymmetryResult(
                family=family_name,
                code_variants=code_variants,
                test_variants=test_variants,
                symmetric=len(code_variants - test_variants) == 0 and len(test_variants - code_variants) == 0,
                missing_test_variants=code_variants - test_variants,
                missing_code_variants=test_variants - code_variants
            ))

        return results

def main():
    parser = argparse.ArgumentParser(
        description="Check Code/Test template family variant symmetry"
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path("templates"),
        help="Path to templates directory (default: templates/)"
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

    if not args.templates_dir.exists():
        print(f"Templates directory not found: {args.templates_dir}", file=sys.stderr)
        sys.exit(2)

    results = check_variant_symmetry(args.templates_dir)

    if not results:
        print("No template families found", file=sys.stderr)
        sys.exit(2)

    all_symmetric = True
    asymmetric_count = 0

    for sr in results:
        if not sr.symmetric:
            all_symmetric = False
            asymmetric_count += 1

            if args.verbose:
                print(f"[ASYMMETRIC] Family: {sr.family}")
                print(f"  Code variants: {sr.code_variants or '{none}'}")
                print(f"  Test variants: {sr.test_variants or '{none}'}")
                if sr.missing_test_variants:
                    print(f"  Missing test variants: {sr.missing_test_variants}")
                if sr.missing_code_variants:
                    print(f"  Missing code variants: {sr.missing_code_variants}")
        elif args.verbose:
            print(f"[SYMMETRIC] Family: {sr.family}")

    if args.json:
        import json
        output = {
            "all_symmetric": all_symmetric,
            "asymmetric_count": asymmetric_count,
            "families": [
                {
                    "family": sr.family,
                    "symmetric": sr.symmetric,
                    "code_variants": list(sr.code_variants),
                    "test_variants": list(sr.test_variants),
                    "missing_test_variants": list(sr.missing_test_variants),
                    "missing_code_variants": list(sr.missing_code_variants)
                }
                for sr in results
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nVariant Symmetry Check: {'PASS' if all_symmetric else 'FAIL'}")
        print(f"Total families: {len(results)}")
        print(f"Asymmetric: {asymmetric_count}")

    sys.exit(0 if all_symmetric else 1)

if __name__ == "__main__":
    main()
