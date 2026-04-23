#!/usr/bin/env python3
"""
Region Interface Checker
Version: 1.0.0
Last Updated: 2025-12-25
Owner: Builder
Classification: HIGH - Template Infrastructure

Validates that protected regions in templates expose consistent interfaces.
Ensures region contracts are maintained across template versions.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

class InterfaceType(Enum):
    """Types of region interfaces."""
    FUNCTION = "function"
    CLASS = "class"
    VARIABLE = "variable"
    IMPORT = "import"
    EXPORT = "export"
    HOOK = "hook"
    SLOT = "slot"

@dataclass
class InterfaceElement:
    """An element exposed by a region interface."""
    name: str
    interface_type: InterfaceType
    signature: Optional[str] = None
    doc: Optional[str] = None
    line_number: int = 0
    required: bool = True

@dataclass
class RegionInterface:
    """Interface contract for a protected region."""
    region_name: str
    file_path: str
    elements: List[InterfaceElement] = field(default_factory=list)
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)

@dataclass
class InterfaceViolation:
    """A violation of the region interface contract."""
    region_name: str
    file_path: str
    element_name: str
    violation_type: str
    message: str
    severity: str = "error"

@dataclass
class CheckResult:
    """Result of interface checking."""
    valid: bool
    regions_checked: int
    violations: List[InterfaceViolation] = field(default_factory=list)
    interfaces: List[RegionInterface] = field(default_factory=list)

class RegionInterfaceChecker:
    """Checks region interface contracts."""

    # Patterns for extracting interface elements
    PYTHON_PATTERNS = {
        InterfaceType.FUNCTION: re.compile(
            r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?:'
        ),
        InterfaceType.CLASS: re.compile(
            r'^(\s*)class\s+(\w+)\s*(?:\(([^)]*)\))?:'
        ),
        InterfaceType.VARIABLE: re.compile(
            r'^(\s*)(\w+)\s*(?::\s*([^=]+))?\s*='
        ),
        InterfaceType.IMPORT: re.compile(
            r'^(?:from\s+[\w.]+\s+)?import\s+(.+)'
        ),
    }

    JS_PATTERNS = {
        InterfaceType.FUNCTION: re.compile(
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)'
        ),
        InterfaceType.CLASS: re.compile(
            r'(?:export\s+)?class\s+(\w+)\s*(?:extends\s+(\w+))?'
        ),
        InterfaceType.VARIABLE: re.compile(
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::\s*([^=]+))?\s*='
        ),
        InterfaceType.EXPORT: re.compile(
            r'export\s+(?:default\s+)?(\w+)'
        ),
    }

    # Region interface marker pattern
    INTERFACE_MARKER = re.compile(
        r'#\s*INTERFACE:(\w+)\s*(?:version=([^\s]+))?'
    )

    def __init__(self, contracts_path: Optional[str] = None):
        """
        Initialize checker.

        Args:
            contracts_path: Path to interface contracts JSON
        """
        self.contracts: Dict[str, RegionInterface] = {}
        if contracts_path and os.path.exists(contracts_path):
            self._load_contracts(contracts_path)

    def _load_contracts(self, contracts_path: str):
        """Load interface contracts from JSON."""
        try:
            with open(contracts_path, 'r') as f:
                data = json.load(f)

            for region_name, contract_data in data.get('contracts', {}).items():
                elements = [
                    InterfaceElement(
                        name=e['name'],
                        interface_type=InterfaceType(e['type']),
                        signature=e.get('signature'),
                        required=e.get('required', True)
                    )
                    for e in contract_data.get('elements', [])
                ]
                self.contracts[region_name] = RegionInterface(
                    region_name=region_name,
                    file_path=contract_data.get('file', ''),
                    elements=elements,
                    version=contract_data.get('version', '1.0.0'),
                    dependencies=contract_data.get('dependencies', [])
                )
        except Exception as e:
            print(f"Warning: Failed to load contracts: {e}", file=sys.stderr)

    def extract_interface(
        self,
        file_path: str,
        region_name: str,
        content: str
    ) -> RegionInterface:
        """
        Extract interface elements from region content.

        Args:
            file_path: Source file path
            region_name: Name of the region
            content: Region content

        Returns:
            RegionInterface with extracted elements
        """
        elements = []
        lines = content.splitlines()

        # Determine file type
        ext = Path(file_path).suffix.lower()
        if ext in ['.py']:
            patterns = self.PYTHON_PATTERNS
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            patterns = self.JS_PATTERNS
        else:
            patterns = self.PYTHON_PATTERNS

        for line_num, line in enumerate(lines, 1):
            for iface_type, pattern in patterns.items():
                match = pattern.match(line)
                if match:
                    groups = match.groups()

                    if iface_type == InterfaceType.FUNCTION:
                        # Extract function name and signature
                        if ext in ['.py']:
                            indent, name, params, return_type = groups[0], groups[1], groups[2], groups[3] if len(groups) > 3 else None
                        else:
                            name, params = groups[0], groups[1] if len(groups) > 1 else ''
                            return_type = None

                        signature = f"({params})"
                        if return_type:
                            signature += f" -> {return_type.strip()}"

                        elements.append(InterfaceElement(
                            name=name,
                            interface_type=iface_type,
                            signature=signature,
                            line_number=line_num
                        ))

                    elif iface_type == InterfaceType.CLASS:
                        name = groups[1] if ext in ['.py'] else groups[0]
                        elements.append(InterfaceElement(
                            name=name,
                            interface_type=iface_type,
                            line_number=line_num
                        ))

                    elif iface_type == InterfaceType.VARIABLE:
                        if ext in ['.py']:
                            name = groups[1]
                        else:
                            name = groups[0]
                        elements.append(InterfaceElement(
                            name=name,
                            interface_type=iface_type,
                            line_number=line_num
                        ))

        return RegionInterface(
            region_name=region_name,
            file_path=file_path,
            elements=elements
        )

    def check_interface(
        self,
        current: RegionInterface,
        contract: RegionInterface
    ) -> List[InterfaceViolation]:
        """
        Check if current interface matches contract.

        Args:
            current: Current interface from code
            contract: Expected interface from contract

        Returns:
            List of violations
        """
        violations = []
        current_elements = {e.name: e for e in current.elements}
        contract_elements = {e.name: e for e in contract.elements}

        # Check for missing required elements
        for name, expected in contract_elements.items():
            if expected.required and name not in current_elements:
                violations.append(InterfaceViolation(
                    region_name=current.region_name,
                    file_path=current.file_path,
                    element_name=name,
                    violation_type="MISSING_ELEMENT",
                    message=f"Required {expected.interface_type.value} '{name}' is missing"
                ))
            elif name in current_elements:
                actual = current_elements[name]

                # Check type match
                if actual.interface_type != expected.interface_type:
                    violations.append(InterfaceViolation(
                        region_name=current.region_name,
                        file_path=current.file_path,
                        element_name=name,
                        violation_type="TYPE_MISMATCH",
                        message=f"'{name}' is {actual.interface_type.value}, "
                               f"expected {expected.interface_type.value}"
                    ))

                # Check signature match for functions
                if (expected.signature and actual.signature and
                    expected.signature != actual.signature):
                    violations.append(InterfaceViolation(
                        region_name=current.region_name,
                        file_path=current.file_path,
                        element_name=name,
                        violation_type="SIGNATURE_MISMATCH",
                        message=f"'{name}' signature mismatch: "
                               f"got {actual.signature}, expected {expected.signature}",
                        severity="warning"
                    ))

        return violations

    def check_file(self, file_path: str) -> CheckResult:
        """
        Check all regions in a file.

        Args:
            file_path: Path to file

        Returns:
            CheckResult
        """
        result = CheckResult(valid=True, regions_checked=0)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
        except Exception as e:
            result.violations.append(InterfaceViolation(
                region_name="",
                file_path=file_path,
                element_name="",
                violation_type="READ_ERROR",
                message=str(e)
            ))
            result.valid = False
            return result

        # Find regions and extract interfaces
        ext = Path(file_path).suffix.lower()
        if ext in ['.py', '.yaml', '.yml', '.sh']:
            start_pattern = re.compile(r'#\s*REGION:(\w+):START')
            end_pattern = re.compile(r'#\s*REGION:(\w+):END')
        else:
            start_pattern = re.compile(r'//\s*REGION:(\w+):START')
            end_pattern = re.compile(r'//\s*REGION:(\w+):END')

        open_regions: Dict[str, int] = {}

        for line_num, line in enumerate(lines):
            start_match = start_pattern.search(line)
            if start_match:
                open_regions[start_match.group(1)] = line_num

            end_match = end_pattern.search(line)
            if end_match:
                region_name = end_match.group(1)
                if region_name in open_regions:
                    start_line = open_regions.pop(region_name)
                    region_content = '\n'.join(lines[start_line+1:line_num])

                    # Extract interface
                    interface = self.extract_interface(
                        file_path, region_name, region_content
                    )
                    result.interfaces.append(interface)
                    result.regions_checked += 1

                    # Check against contract if exists
                    if region_name in self.contracts:
                        violations = self.check_interface(
                            interface, self.contracts[region_name]
                        )
                        result.violations.extend(violations)
                        if any(v.severity == "error" for v in violations):
                            result.valid = False

        return result

    def check_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
        recursive: bool = True
    ) -> CheckResult:
        """Check all files in a directory."""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx']

        result = CheckResult(valid=True, regions_checked=0)
        path = Path(directory)

        pattern = '**/*' if recursive else '*'
        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                file_result = self.check_file(str(file_path))
                result.regions_checked += file_result.regions_checked
                result.violations.extend(file_result.violations)
                result.interfaces.extend(file_result.interfaces)
                if not file_result.valid:
                    result.valid = False

        return result

    def generate_contracts(self, result: CheckResult) -> Dict[str, Any]:
        """
        Generate interface contracts from scan result.

        Args:
            result: CheckResult with extracted interfaces

        Returns:
            Contract dictionary
        """
        contracts = {}

        for interface in result.interfaces:
            contracts[interface.region_name] = {
                "file": interface.file_path,
                "version": "1.0.0",
                "elements": [
                    {
                        "name": e.name,
                        "type": e.interface_type.value,
                        "signature": e.signature,
                        "required": True
                    }
                    for e in interface.elements
                ],
                "dependencies": interface.dependencies
            }

        return {"contracts": contracts}

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check region interface contracts"
    )
    parser.add_argument("path", help="File or directory to check")
    parser.add_argument("-c", "--contracts", help="Path to contracts JSON")
    parser.add_argument("-e", "--extensions", nargs="+",
                        help="File extensions to check")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Check directories recursively")
    parser.add_argument("--generate", help="Generate contracts to file")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    checker = RegionInterfaceChecker(contracts_path=args.contracts)

    if os.path.isdir(args.path):
        result = checker.check_directory(
            args.path,
            extensions=args.extensions,
            recursive=args.recursive
        )
    else:
        result = checker.check_file(args.path)

    # Generate contracts if requested
    if args.generate:
        contracts = checker.generate_contracts(result)
        with open(args.generate, 'w') as f:
            json.dump(contracts, f, indent=2)
        print(f"Contracts written to: {args.generate}")

    # Output results
    if args.json:
        output = {
            "valid": result.valid,
            "regions_checked": result.regions_checked,
            "violations": [
                {
                    "region": v.region_name,
                    "file": v.file_path,
                    "element": v.element_name,
                    "type": v.violation_type,
                    "message": v.message,
                    "severity": v.severity
                }
                for v in result.violations
            ],
            "interfaces": [
                {
                    "region": i.region_name,
                    "file": i.file_path,
                    "elements": [
                        {"name": e.name, "type": e.interface_type.value}
                        for e in i.elements
                    ]
                }
                for i in result.interfaces
            ] if args.verbose else []
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Regions checked: {result.regions_checked}")
        print(f"Valid: {'Yes' if result.valid else 'No'}")

        if result.violations:
            print(f"\nViolations ({len(result.violations)}):")
            for v in result.violations:
                symbol = "!" if v.severity == "error" else "?"
                print(f"  [{symbol}] {v.file_path} - {v.region_name}: {v.message}")

        if args.verbose and result.interfaces:
            print(f"\nInterfaces found:")
            for i in result.interfaces:
                print(f"  {i.region_name} ({len(i.elements)} elements)")

    sys.exit(0 if result.valid else 1)

if __name__ == "__main__":
    main()
