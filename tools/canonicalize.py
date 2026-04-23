#!/usr/bin/env python3
"""
Canonicalization utilities for idempotent generation.

This module provides functions to ensure stable, deterministic output
for YAML and text content, addressing Cause 2 (Unstable Ordering) and
Cause 4 (Line Ending Inconsistency) from IDEMPOTENT_GENERATION_POLICY.

See: PLANNING/future/IDEMPOTENT_GENERATION_POLICY.md Section 6
"""

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

# Register representer for OrderedDict to output as regular dict
def _represent_ordereddict(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())

yaml.add_representer(OrderedDict, _represent_ordereddict)

def sort_dict(obj: Any) -> Any:
    """Recursively sort dictionary keys at all levels.

    Args:
        obj: Any object (dict, list, or primitive)

    Returns:
        Object with all nested dicts having sorted keys
    """
    if isinstance(obj, dict):
        return OrderedDict(sorted((k, sort_dict(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return [sort_dict(item) for item in obj]
    else:
        return obj

def canonical_yaml_dump(data: Dict[str, Any], default_flow_style: bool = False) -> str:
    """Dump YAML with sorted keys at all levels.

    This ensures deterministic output regardless of the order
    keys were added to the dictionary.

    Args:
        data: Dictionary to serialize
        default_flow_style: If True, use inline style for collections

    Returns:
        YAML string with alphabetically sorted keys

    Example:
        >>> data = {'z': 1, 'a': 2, 'nested': {'y': 3, 'b': 4}}
        >>> print(canonical_yaml_dump(data))
        a: 2
        nested:
          b: 4
          y: 3
        z: 1
    """
    sorted_data = sort_dict(data)
    return yaml.dump(
        sorted_data,
        default_flow_style=default_flow_style,
        sort_keys=False,  # We already sorted
        allow_unicode=True,
        width=120
    )

def canonical_yaml_load(content: str) -> Dict[str, Any]:
    """Load YAML and return with sorted keys.

    Args:
        content: YAML string to parse

    Returns:
        Dictionary with all keys sorted
    """
    data = yaml.safe_load(content)
    if data is None:
        return {}
    return sort_dict(data)

def normalize_line_endings(content: str) -> str:
    """Convert all line endings to LF (Unix style).

    Handles:
    - CRLF (Windows) -> LF
    - CR (old Mac) -> LF

    Args:
        content: Text content with potentially mixed line endings

    Returns:
        Content with all line endings normalized to LF
    """
    return content.replace('\r\n', '\n').replace('\r', '\n')

def canonical_json_dump(data: Dict[str, Any], indent: int = 2) -> str:
    """Dump JSON with sorted keys at all levels.

    Args:
        data: Dictionary to serialize
        indent: Number of spaces for indentation

    Returns:
        JSON string with alphabetically sorted keys
    """
    sorted_data = sort_dict(data)
    return json.dumps(sorted_data, indent=indent, ensure_ascii=False)

def canonicalize_file(
    input_path: Path,
    output_path: Path = None,
    normalize_endings: bool = True
) -> str:
    """Canonicalize a YAML or JSON file.

    Args:
        input_path: Path to input file
        output_path: Optional path for output (defaults to overwriting input)
        normalize_endings: Whether to normalize line endings to LF

    Returns:
        Canonicalized content
    """
    content = input_path.read_text(encoding='utf-8')

    # Determine file type
    suffix = input_path.suffix.lower()

    if suffix in ('.yaml', '.yml'):
        data = yaml.safe_load(content)
        if data is not None:
            canonical = canonical_yaml_dump(data)
        else:
            canonical = content
    elif suffix == '.json':
        data = json.loads(content)
        canonical = canonical_json_dump(data)
    else:
        # For other files, just normalize line endings
        canonical = content

    if normalize_endings:
        canonical = normalize_line_endings(canonical)

    # Write output
    out = output_path or input_path
    out.write_text(canonical, encoding='utf-8')

    return canonical

def main():
    """CLI entry point for canonicalize tool."""
    parser = argparse.ArgumentParser(
        description='Canonicalize YAML/JSON files for idempotent generation',
        epilog='See PLANNING/future/IDEMPOTENT_GENERATION_POLICY.md for details'
    )
    parser.add_argument(
        'files',
        nargs='+',
        type=Path,
        help='Files to canonicalize (YAML or JSON)'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file (only valid with single input file)'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check if files are already canonical (exit 1 if not)'
    )
    parser.add_argument(
        '--no-normalize-endings',
        action='store_true',
        help='Skip line ending normalization'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress output'
    )

    args = parser.parse_args()

    if args.output and len(args.files) > 1:
        parser.error('--output can only be used with a single input file')

    exit_code = 0

    for file_path in args.files:
        if not file_path.exists():
            print(f'ERROR: File not found: {file_path}', file=sys.stderr)
            exit_code = 1
            continue

        original = file_path.read_text(encoding='utf-8')

        if args.check:
            # Check mode: compare without modifying
            try:
                canonical = canonicalize_file(
                    file_path,
                    output_path=Path('/dev/null'),  # Dummy
                    normalize_endings=not args.no_normalize_endings
                )
                # Re-read to check
                suffix = file_path.suffix.lower()
                if suffix in ('.yaml', '.yml'):
                    data = yaml.safe_load(original)
                    if data is not None:
                        canonical = canonical_yaml_dump(data)
                        if not args.no_normalize_endings:
                            canonical = normalize_line_endings(canonical)
                        normalized_original = normalize_line_endings(original) if not args.no_normalize_endings else original
                        if normalized_original != canonical:
                            if not args.quiet:
                                print(f'NOT CANONICAL: {file_path}')
                            exit_code = 1
                        elif not args.quiet:
                            print(f'CANONICAL: {file_path}')
            except Exception as e:
                print(f'ERROR: {file_path}: {e}', file=sys.stderr)
                exit_code = 1
        else:
            # Canonicalize mode
            try:
                output = args.output if args.output else file_path
                canonicalize_file(
                    file_path,
                    output_path=output,
                    normalize_endings=not args.no_normalize_endings
                )
                if not args.quiet:
                    print(f'Canonicalized: {file_path}')
            except Exception as e:
                print(f'ERROR: {file_path}: {e}', file=sys.stderr)
                exit_code = 1

    return exit_code

if __name__ == '__main__':
    sys.exit(main())
