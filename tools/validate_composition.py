#!/usr/bin/env python3
"""
Variant Composition Validator for the system.

Validates variant combinations against composition rules:
- Allowed combinations
- Forbidden combinations
- Mutex groups (mutually exclusive variants)
- Conditional requirements (variant A requires variant B)

See: PLANNING/TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md Task 4

Usage:
    python3 tools/validate_composition.py --variants variant1,variant2 --template template-name
    python3 tools/validate_composition.py --wiring .task/wiring.yaml
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

class CompositionError:
    """Represents a composition validation error."""

    def __init__(self, error_type: str, message: str, variants: List[str]):
        self.error_type = error_type
        self.message = message
        self.variants = variants

    def __str__(self):
        return f'[{self.error_type}] {self.message}: {", ".join(self.variants)}'

class CompositionRules:
    """Holds composition rules for a template."""

    def __init__(self, rules_data: Optional[Dict] = None):
        self.allowed_combinations: List[Set[str]] = []
        self.forbidden_combinations: List[Set[str]] = []
        self.mutex_groups: List[Set[str]] = []
        self.conditional_requirements: Dict[str, List[str]] = {}

        if rules_data:
            self._parse_rules(rules_data)

    def _parse_rules(self, data: Dict):
        """Parse rules from YAML data."""
        # Parse allowed combinations
        for combo in data.get('allowed_combinations', []):
            if isinstance(combo, list):
                self.allowed_combinations.append(set(combo))

        # Parse forbidden combinations
        for combo in data.get('forbidden_combinations', []):
            if isinstance(combo, list):
                self.forbidden_combinations.append(set(combo))

        # Parse mutex groups
        for group in data.get('mutex_groups', []):
            if isinstance(group, list):
                self.mutex_groups.append(set(group))

        # Parse conditional requirements (requires/depends_on)
        for req in data.get('conditional_requirements', []):
            if isinstance(req, dict):
                variant = req.get('variant')
                requires = req.get('requires', [])
                if variant and requires:
                    self.conditional_requirements[variant] = (
                        requires if isinstance(requires, list) else [requires]
                    )

def load_wiring_file(path: Path) -> Tuple[Optional[Dict], Optional[str]]:
    """Load and parse wiring.yaml file.

    Args:
        path: Path to wiring.yaml

    Returns:
        Tuple of (wiring dict, error message if any)
    """
    if not path.exists():
        return None, f'File not found: {path}'

    try:
        content = path.read_text(encoding='utf-8')
        data = yaml.safe_load(content)
        if data is None:
            return None, f'Empty or invalid YAML: {path}'
        return data, None
    except yaml.YAMLError as e:
        return None, f'YAML parse error: {e}'
    except Exception as e:
        return None, f'Error reading file: {e}'

def load_composition_rules(template_name: str, rules_path: Optional[Path] = None) -> CompositionRules:
    """Load composition rules for a template.

    Args:
        template_name: Name of the template
        rules_path: Optional explicit path to rules file

    Returns:
        CompositionRules object (may be empty if no rules found)
    """
    # Default search paths
    search_paths = [
        Path(f'archives/golden/templates/{template_name}/composition_rules.yaml'),
        Path(f'PLANNING/templates/{template_name}/composition_rules.yaml'),
        Path(f'.task/composition_rules.yaml'),
    ]

    if rules_path:
        search_paths.insert(0, rules_path)

    for path in search_paths:
        if path.exists():
            data, error = load_wiring_file(path)
            if data and not error:
                return CompositionRules(data)

    # Return empty rules if no file found
    return CompositionRules()

def validate_allowed_combinations(
    variants: Set[str],
    rules: CompositionRules
) -> List[CompositionError]:
    """Validate that variants form an allowed combination.

    Args:
        variants: Set of active variants
        rules: Composition rules

    Returns:
        List of errors (empty if valid)
    """
    errors = []

    # If allowed_combinations is empty, all combinations are allowed
    if not rules.allowed_combinations:
        return []

    # Check if variants match any allowed combination
    for allowed in rules.allowed_combinations:
        if variants == allowed or variants.issubset(allowed):
            return []

    errors.append(CompositionError(
        'NOT_ALLOWED',
        'Variant combination is not in allowed_combinations',
        sorted(variants)
    ))

    return errors

def validate_forbidden_combinations(
    variants: Set[str],
    rules: CompositionRules
) -> List[CompositionError]:
    """Validate that no forbidden combinations are present.

    Args:
        variants: Set of active variants
        rules: Composition rules

    Returns:
        List of errors (empty if valid)
    """
    errors = []

    for forbidden in rules.forbidden_combinations:
        if forbidden.issubset(variants):
            errors.append(CompositionError(
                'FORBIDDEN',
                'Forbidden variant combination detected',
                sorted(forbidden)
            ))

    return errors

def validate_mutex_groups(
    variants: Set[str],
    rules: CompositionRules
) -> List[CompositionError]:
    """Validate that mutex groups are respected.

    A mutex group contains variants that cannot be used together.
    At most one variant from each mutex group can be active.

    Args:
        variants: Set of active variants
        rules: Composition rules

    Returns:
        List of errors (empty if valid)
    """
    errors = []

    for mutex_group in rules.mutex_groups:
        active_in_group = variants.intersection(mutex_group)
        if len(active_in_group) > 1:
            errors.append(CompositionError(
                'MUTEX_VIOLATION',
                'Multiple variants from mutex group are active',
                sorted(active_in_group)
            ))

    return errors

def validate_conditional_requirements(
    variants: Set[str],
    rules: CompositionRules
) -> List[CompositionError]:
    """Validate conditional requirements are met.

    If variant A requires variant B, then having A without B is an error.

    Args:
        variants: Set of active variants
        rules: Composition rules

    Returns:
        List of errors (empty if valid)
    """
    errors = []

    for variant, required in rules.conditional_requirements.items():
        if variant in variants:
            missing = [r for r in required if r not in variants]
            if missing:
                errors.append(CompositionError(
                    'MISSING_REQUIREMENT',
                    f"Variant '{variant}' requires missing variants",
                    missing
                ))

    return errors

def validate_composition(
    variants: Set[str],
    rules: CompositionRules
) -> Tuple[bool, List[CompositionError]]:
    """Run all composition validations.

    Args:
        variants: Set of active variants
        rules: Composition rules to validate against

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []

    errors.extend(validate_forbidden_combinations(variants, rules))
    errors.extend(validate_mutex_groups(variants, rules))
    errors.extend(validate_conditional_requirements(variants, rules))

    # Only check allowed combinations if specified
    if rules.allowed_combinations:
        errors.extend(validate_allowed_combinations(variants, rules))

    return len(errors) == 0, errors

def extract_variants_from_wiring(wiring: Dict) -> Set[str]:
    """Extract active variants from a wiring.yaml file.

    Args:
        wiring: Parsed wiring.yaml content

    Returns:
        Set of active variant names
    """
    variants = set()

    # Check composition.variants or variants at top level
    composition = wiring.get('composition', {})
    variant_list = composition.get('variants', wiring.get('variants', []))

    if isinstance(variant_list, list):
        for v in variant_list:
            if isinstance(v, str):
                variants.add(v)
            elif isinstance(v, dict) and 'name' in v:
                variants.add(v['name'])

    return variants

def main():
    """CLI entry point for validate_composition tool."""
    parser = argparse.ArgumentParser(
        description='Validate variant composition against rules',
        epilog='See PLANNING/TEMPLATE_VARIANTS_AND_PARAMETER_PACKS_POLICY.md for details'
    )
    parser.add_argument(
        '--variants',
        type=str,
        help='Comma-separated list of variant names to validate'
    )
    parser.add_argument(
        '--template',
        type=str,
        help='Template name to load rules from'
    )
    parser.add_argument(
        '--wiring',
        type=Path,
        help='Path to wiring.yaml file to validate'
    )
    parser.add_argument(
        '--rules',
        type=Path,
        help='Explicit path to composition_rules.yaml file'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Only output on failure'
    )

    args = parser.parse_args()

    # Determine variants to validate
    if args.wiring:
        wiring_data, error = load_wiring_file(args.wiring)
        if error:
            print(f'ERROR: {error}', file=sys.stderr)
            return 1
        variants = extract_variants_from_wiring(wiring_data)
        template_name = wiring_data.get('identity', {}).get('template', args.template)
    elif args.variants:
        variants = set(v.strip() for v in args.variants.split(',') if v.strip())
        template_name = args.template
    else:
        parser.print_help()
        return 1

    if not variants:
        if not args.quiet:
            print('No variants specified or found in wiring file')
        return 0

    # Load rules
    rules = load_composition_rules(template_name or '', args.rules)

    # Validate
    is_valid, errors = validate_composition(variants, rules)

    if is_valid:
        if not args.quiet:
            print(f'PASS: Variant composition is valid')
            if args.verbose:
                print(f'  Variants: {", ".join(sorted(variants))}')
        return 0
    else:
        print(f'FAIL: Variant composition is invalid')
        for error in errors:
            print(f'  {error}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
