#!/usr/bin/env python3
"""
Equivalence Contract Validator
Version: 1.0.0
Last Updated: 2025-12-29
Owner: Critic
Classification: HIGH - Template Validation

Validates that all templates have equivalence contracts for drift detection.

Usage:
    python tools/validate_equivalence_contracts.py
    python tools/validate_equivalence_contracts.py --template-dir templates/
    python tools/validate_equivalence_contracts.py --verbose

See: PLANNING/TEMPLATE_DRIFT_DETECTION_POLICY.md (Section 6, Task 6)
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
class ContractValidationResult:
    """Result of validating a template's equivalence contract."""
    template_id: str
    template_file: str
    has_contract: bool
    contract_file: Optional[str]
    issues: List[str]
    passed: bool

@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    total_templates: int
    with_contracts: int
    without_contracts: int
    results: List[ContractValidationResult]
    passed: bool

# Required fields for equivalence contracts
CONTRACT_REQUIRED_FIELDS = [
    'equivalence_function',
    'test_inputs',
    'invariants'
]

def find_template_families(template_dir: Path) -> List[Path]:
    """Find all template family directories."""
    families = []
    if not template_dir.exists():
        return families

    for item in template_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            metadata = item / 'metadata.yaml'
            if metadata.exists():
                families.append(item)

    return families

def load_metadata(metadata_file: Path) -> Optional[Dict[str, Any]]:
    """Load and parse a metadata.yaml file."""
    try:
        with open(metadata_file) as f:
            return yaml.safe_load(f)
    except Exception:
        return None

def find_contract_for_template(template_id: str, family_dir: Path, contracts_dir: Path) -> Optional[Path]:
    """Find equivalence contract file for a template."""
    # Check in family directory
    contract_in_family = family_dir / f"{template_id}.contract.yaml"
    if contract_in_family.exists():
        return contract_in_family

    # Check in contracts directory
    contract_in_contracts = contracts_dir / f"{template_id}_equivalence_contract.yaml"
    if contract_in_contracts.exists():
        return contract_in_contracts

    # Check for family-level contract
    family_contract = contracts_dir / f"{family_dir.name}_compliance_contract.yaml"
    if family_contract.exists():
        return family_contract

    return None

def validate_contract(contract_file: Path) -> List[str]:
    """Validate contract has required fields."""
    issues = []
    try:
        with open(contract_file) as f:
            contract = yaml.safe_load(f)

        if not contract:
            issues.append("Contract file is empty")
            return issues

        for field in CONTRACT_REQUIRED_FIELDS:
            if field not in contract:
                issues.append(f"Missing required field: {field}")
    except Exception as e:
        issues.append(f"Failed to parse contract: {e}")

    return issues

def validate_template(template: Dict[str, Any], family_dir: Path, contracts_dir: Path) -> ContractValidationResult:
    """Validate a single template has an equivalence contract."""
    template_id = template.get('id', 'unknown')
    template_file = template.get('file', 'unknown')

    contract_file = find_contract_for_template(template_id, family_dir, contracts_dir)

    if contract_file:
        issues = validate_contract(contract_file)
        return ContractValidationResult(
            template_id=template_id,
            template_file=template_file,
            has_contract=True,
            contract_file=str(contract_file),
            issues=issues,
            passed=len(issues) == 0
        )
    else:
        return ContractValidationResult(
            template_id=template_id,
            template_file=template_file,
            has_contract=False,
            contract_file=None,
            issues=["No equivalence contract found"],
            passed=False
        )

def validate_all_templates(template_dir: Path, verbose: bool = False) -> ValidationReport:
    """Validate all templates have equivalence contracts."""
    results = []
    contracts_dir = template_dir / 'compliance' / 'contracts'

    families = find_template_families(template_dir)

    for family_dir in families:
        metadata_file = family_dir / 'metadata.yaml'
        metadata = load_metadata(metadata_file)

        if not metadata:
            continue

        templates = metadata.get('templates', [])
        for template in templates:
            result = validate_template(template, family_dir, contracts_dir)
            results.append(result)

            if verbose:
                status = "PASS" if result.passed else "FAIL"
                print(f"  [{status}] {result.template_id}")
                for issue in result.issues:
                    print(f"         - {issue}")

    with_contracts = sum(1 for r in results if r.has_contract)
    without_contracts = sum(1 for r in results if not r.has_contract)
    all_passed = all(r.passed for r in results) if results else True

    return ValidationReport(
        timestamp=datetime.now().isoformat(),
        total_templates=len(results),
        with_contracts=with_contracts,
        without_contracts=without_contracts,
        results=results,
        passed=all_passed
    )

def main():
    parser = argparse.ArgumentParser(
        description='Validate templates have equivalence contracts'
    )
    parser.add_argument(
        '--template-dir',
        type=Path,
        default=Path('templates'),
        help='Template directory to scan (default: templates/)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    args = parser.parse_args()

    if args.verbose:
        print(f"Scanning templates in: {args.template_dir}")

    report = validate_all_templates(args.template_dir, args.verbose)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"\nEquivalence Contract Validation Report")
        print(f"=" * 40)
        print(f"Total templates: {report.total_templates}")
        print(f"With contracts:  {report.with_contracts}")
        print(f"Without contracts: {report.without_contracts}")
        print(f"Status: {'PASS' if report.passed else 'FAIL'}")

        if not report.passed:
            print(f"\nTemplates missing contracts:")
            for r in report.results:
                if not r.has_contract:
                    print(f"  - {r.template_id} ({r.template_file})")

    sys.exit(0 if report.passed else 1)

if __name__ == '__main__':
    main()
