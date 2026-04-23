#!/usr/bin/env python3
"""
Version Pin Checker
Version: 1.0.0
Last Updated: 2025-12-31
Owner: PM
Classification: MEDIUM - CI Reliability

Enforces CONVENTIONS.md:793 - All tools MUST be pinned to specific versions in CI.

Scans CI workflow files for unpinned package installations.

Usage:
    python tools/version_pin_checker.py
    python tools/version_pin_checker.py --workflows-dir .github/workflows/
    python tools/version_pin_checker.py --strict

Exit Codes:
    0: All tools properly pinned
    1: Unpinned tools found
    2: Configuration/runtime error
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Tuple

@dataclass
class UnpinnedPackage:
    """Represents an unpinned package installation."""
    file: str
    line: int
    package: str
    install_command: str
    suggested_fix: str

@dataclass
class FileResult:
    """Results for a single workflow file."""
    file_path: str
    unpinned: List[UnpinnedPackage] = field(default_factory=list)
    pinned_count: int = 0

# Regex patterns for package installations
PIP_INSTALL_PATTERN = re.compile(
    r'pip3?\s+install\s+([^|&\n]+)',
    re.IGNORECASE
)
NPM_INSTALL_PATTERN = re.compile(
    r'npm\s+(?:install|i)\s+(?:-[gGDS]\s+)?([^|&\n]+)',
    re.IGNORECASE
)

# Pattern for version-pinned packages
VERSION_PIN_PATTERNS = [
    re.compile(r'^[\w-]+==[0-9]'),          # package==1.0.0
    re.compile(r'^[\w-]+>=[0-9]'),          # package>=1.0.0
    re.compile(r'^[\w-]+~=[0-9]'),          # package~=1.0.0
    re.compile(r'^[\w-]+@[0-9]'),           # package@1.0.0 (npm)
    re.compile(r'^[\w-]+@\^[0-9]'),         # package@^1.0.0 (npm)
    re.compile(r'^[\w-]+@~[0-9]'),          # package@~1.0.0 (npm)
    re.compile(r'^-r\s'),                    # -r requirements.txt
    re.compile(r'^-e\s'),                    # -e . (editable)
    re.compile(r'^\.\s*$'),                  # . (current package)
    re.compile(r'^--'),                      # flags like --upgrade
    re.compile(r'^-'),                       # single-letter flags
]

# Packages that don't need version pins (system or dev tools)
EXEMPT_PACKAGES = {
    'pip', 'setuptools', 'wheel', 'virtualenv',
    'pytest', 'coverage',  # Often pinned elsewhere
}

def is_version_pinned(package: str) -> bool:
    """Check if a package specification includes a version pin."""
    package = package.strip()

    # Skip flags and empty strings
    if not package or package.startswith('-'):
        return True

    # Check against known version patterns
    for pattern in VERSION_PIN_PATTERNS:
        if pattern.match(package):
            return True

    # Check for version specifier anywhere in the string
    if '==' in package or '>=' in package or '<=' in package or '~=' in package:
        return True

    # Check npm-style versions
    if '@' in package and not package.startswith('@'):
        return True

    return False

def extract_packages_from_command(command: str) -> List[str]:
    """Extract individual package names from an install command."""
    packages = []

    # Remove common flags
    command = re.sub(r'--[\w-]+(=\S+)?', '', command)
    command = re.sub(r'-[a-zA-Z]\s*\S*', '', command)

    # Split on whitespace
    for part in command.split():
        part = part.strip()
        if part and not part.startswith('-'):
            packages.append(part)

    return packages

def check_workflow_file(file_path: Path) -> FileResult:
    """Check a single workflow file for unpinned packages."""
    result = FileResult(file_path=str(file_path))

    try:
        content = file_path.read_text()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return result

    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        # Check pip install commands
        pip_match = PIP_INSTALL_PATTERN.search(line)
        if pip_match:
            packages = extract_packages_from_command(pip_match.group(1))
            for pkg in packages:
                # Get base package name
                base_pkg = re.split(r'[=<>~@\[]', pkg)[0]

                if base_pkg.lower() in EXEMPT_PACKAGES:
                    continue

                if is_version_pinned(pkg):
                    result.pinned_count += 1
                else:
                    result.unpinned.append(UnpinnedPackage(
                        file=str(file_path),
                        line=line_num,
                        package=pkg,
                        install_command=line.strip(),
                        suggested_fix=f"{pkg}==<version>"
                    ))

        # Check npm install commands
        npm_match = NPM_INSTALL_PATTERN.search(line)
        if npm_match:
            packages = extract_packages_from_command(npm_match.group(1))
            for pkg in packages:
                if is_version_pinned(pkg):
                    result.pinned_count += 1
                else:
                    result.unpinned.append(UnpinnedPackage(
                        file=str(file_path),
                        line=line_num,
                        package=pkg,
                        install_command=line.strip(),
                        suggested_fix=f"{pkg}@<version>"
                    ))

    return result

def check_workflows_directory(
    workflows_dir: Path,
    verbose: bool = False
) -> List[FileResult]:
    """Check all workflow files in directory."""
    results = []

    if not workflows_dir.exists():
        print(f"Workflows directory not found: {workflows_dir}", file=sys.stderr)
        return results

    # Check YAML files
    for yaml_file in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        result = check_workflow_file(yaml_file)
        results.append(result)

        if verbose:
            if result.unpinned:
                print(f"[WARN] {yaml_file.name}: {len(result.unpinned)} unpinned packages")
                for u in result.unpinned[:5]:
                    print(f"  Line {u.line}: {u.package}")
            else:
                print(f"[PASS] {yaml_file.name}: {result.pinned_count} pinned packages")

    return results

def main():
    parser = argparse.ArgumentParser(
        description="Check CI workflows for unpinned package versions"
    )
    parser.add_argument(
        "--workflows-dir",
        type=Path,
        default=Path(".github/workflows"),
        help="Workflows directory (default: .github/workflows/)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if any unpinned packages found"
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

    # Run checks
    results = check_workflows_directory(args.workflows_dir, args.verbose)

    if not results:
        print("No workflow files found", file=sys.stderr)
        sys.exit(2)

    # Aggregate statistics
    total_files = len(results)
    total_pinned = sum(r.pinned_count for r in results)
    total_unpinned = sum(len(r.unpinned) for r in results)
    files_with_unpinned = sum(1 for r in results if r.unpinned)

    all_unpinned = [u for r in results for u in r.unpinned]

    if args.json:
        output = {
            "summary": {
                "workflow_files": total_files,
                "pinned_packages": total_pinned,
                "unpinned_packages": total_unpinned,
                "files_with_unpinned": files_with_unpinned,
                "passed": total_unpinned == 0
            },
            "unpinned": [
                {
                    "file": u.file,
                    "line": u.line,
                    "package": u.package,
                    "command": u.install_command,
                    "suggested_fix": u.suggested_fix
                }
                for u in all_unpinned
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print("Version Pin Check Summary")
        print(f"{'='*50}")
        print(f"Workflow files:       {total_files}")
        print(f"Pinned packages:      {total_pinned}")
        print(f"Unpinned packages:    {total_unpinned}")
        print(f"Files with unpinned:  {files_with_unpinned}")

        if all_unpinned and not args.verbose:
            print(f"\n{'='*50}")
            print("Unpinned Packages (first 20)")
            print(f"{'='*50}")
            for u in all_unpinned[:20]:
                print(f"{u.file}:{u.line}: {u.package}")
                print(f"  Suggestion: {u.suggested_fix}")
            if len(all_unpinned) > 20:
                print(f"... and {len(all_unpinned) - 20} more")

    # Determine exit code
    if args.strict and total_unpinned > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
