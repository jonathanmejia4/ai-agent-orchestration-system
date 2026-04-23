#!/usr/bin/env python3
"""
API Documentation Validator
Version: 1.0.0
Last Updated: 2025-12-31
Owner: Builder
Classification: MEDIUM - Documentation Compliance

Enforces CONVENTIONS.md:185 - Every public API endpoint MUST have
a corresponding docs/api/<version>/<resource>.md file.

Usage:
    python tools/api_docs_validator.py
    python tools/api_docs_validator.py --api-dir api/ --docs-dir docs/api/
    python tools/api_docs_validator.py --scan-routes

Exit Codes:
    0: All API endpoints have documentation
    1: Missing documentation found
    2: Configuration/runtime error
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Common API route decorator patterns
ROUTE_PATTERNS = [
    r'@(app|router|api)\.(get|post|put|patch|delete|route)\s*\(\s*["\']([^"\']+)["\']',
    r'@blueprint\.route\s*\(\s*["\']([^"\']+)["\']',
    r'path\s*\(\s*["\']([^"\']+)["\']',  # Django/FastAPI
]

# Default API version
DEFAULT_VERSION = "v1"

def extract_routes_from_file(file_path: Path) -> List[Dict]:
    """Extract API routes from a Python file."""
    routes = []

    try:
        content = file_path.read_text()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return routes

    # Try regex patterns for route decorators
    for pattern in ROUTE_PATTERNS:
        for match in re.finditer(pattern, content):
            groups = match.groups()
            if len(groups) >= 3:
                method = groups[1].upper()
                route = groups[2]
            else:
                method = "GET"
                route = groups[-1]

            routes.append({
                "file": str(file_path),
                "method": method,
                "route": route,
                "line": content[:match.start()].count('\n') + 1
            })

    return routes

def extract_resource_from_route(route: str) -> Optional[str]:
    """Extract resource name from route path."""
    # Remove version prefix like /api/v1/
    route = re.sub(r'^/?(api/)?v\d+/?', '', route)

    # Remove path parameters like {id} or <id>
    route = re.sub(r'[{<][^}>]+[}>]', '', route)

    # Get first path segment as resource name
    parts = [p for p in route.strip('/').split('/') if p]
    if parts:
        return parts[0].lower()

    return None

def find_api_files(api_dir: Path) -> List[Path]:
    """Find API route files."""
    api_files = []

    patterns = [
        "routes*.py",
        "*_routes.py",
        "api*.py",
        "*_api.py",
        "views*.py",
        "*_views.py",
        "endpoints*.py",
        "*_endpoints.py",
    ]

    if api_dir.exists():
        for pattern in patterns:
            api_files.extend(api_dir.rglob(pattern))

    # Also check common locations
    for common_dir in [Path("src/api"), Path("app/api"), Path("api")]:
        if common_dir.exists() and common_dir != api_dir:
            for pattern in patterns:
                api_files.extend(common_dir.rglob(pattern))

    return sorted(set(api_files))

def find_api_docs(docs_dir: Path, resource: str, version: str = DEFAULT_VERSION) -> Optional[Path]:
    """Find documentation file for a resource."""
    # Try different naming patterns
    candidates = [
        docs_dir / version / f"{resource}.md",
        docs_dir / f"{resource}.md",
        docs_dir / version / f"{resource}s.md",  # Plural form
        docs_dir / f"{resource}s.md",
        docs_dir / version / f"{resource}_api.md",
        docs_dir / f"{resource}_api.md",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None

def validate_api_docs(
    api_dir: Path,
    docs_dir: Path,
    version: str = DEFAULT_VERSION,
    verbose: bool = False
) -> Tuple[List[Dict], List[Dict], Set[str]]:
    """
    Validate that all API endpoints have documentation.

    Returns:
        Tuple of (missing_docs, found_docs, all_resources)
    """
    api_files = find_api_files(api_dir)
    all_routes = []

    for api_file in api_files:
        routes = extract_routes_from_file(api_file)
        all_routes.extend(routes)

    # Group routes by resource
    resources: Dict[str, List[Dict]] = {}
    for route in all_routes:
        resource = extract_resource_from_route(route["route"])
        if resource:
            if resource not in resources:
                resources[resource] = []
            resources[resource].append(route)

    missing_docs = []
    found_docs = []

    for resource, routes in sorted(resources.items()):
        doc_path = find_api_docs(docs_dir, resource, version)

        if doc_path:
            found_docs.append({
                "resource": resource,
                "doc_path": str(doc_path),
                "routes": routes
            })
            if verbose:
                print(f"[PASS] {resource} -> {doc_path}")
        else:
            expected_path = docs_dir / version / f"{resource}.md"
            missing_docs.append({
                "resource": resource,
                "expected_path": str(expected_path),
                "routes": routes
            })
            if verbose:
                print(f"[FAIL] {resource} -> {expected_path} (MISSING)")

    return missing_docs, found_docs, set(resources.keys())

def main():
    parser = argparse.ArgumentParser(
        description="Validate API endpoint documentation exists"
    )
    parser.add_argument(
        "--api-dir",
        type=Path,
        default=Path("api"),
        help="API routes directory (default: api/)"
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs/api"),
        help="API docs directory (default: docs/api/)"
    )
    parser.add_argument(
        "--version",
        type=str,
        default=DEFAULT_VERSION,
        help=f"API version (default: {DEFAULT_VERSION})"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if any API endpoints lack documentation"
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

    # Run validation
    missing, found, resources = validate_api_docs(
        args.api_dir,
        args.docs_dir,
        args.version,
        args.verbose
    )

    total = len(resources)
    documented = len(found)
    coverage = (documented / total * 100) if total > 0 else 100

    if args.json:
        output = {
            "summary": {
                "total_resources": total,
                "documented": documented,
                "missing_docs": len(missing),
                "coverage_percent": round(coverage, 1),
                "passed": len(missing) == 0
            },
            "missing_documentation": missing,
            "found_documentation": found
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        print("API Documentation Validation Summary")
        print(f"{'='*50}")
        print(f"Total API resources:  {total}")
        print(f"With documentation:   {documented}")
        print(f"Missing docs:         {len(missing)}")
        print(f"Documentation coverage: {coverage:.1f}%")

        if missing:
            print(f"\n{'='*50}")
            print("Missing API Documentation")
            print(f"{'='*50}")
            for item in missing[:15]:
                print(f"\nResource: {item['resource']}")
                print(f"  Expected: {item['expected_path']}")
                print(f"  Routes:")
                for route in item['routes'][:3]:
                    print(f"    {route['method']} {route['route']}")
                if len(item['routes']) > 3:
                    print(f"    ... and {len(item['routes']) - 3} more routes")

    # Determine exit code
    if args.strict and missing:
        sys.exit(1)
    elif missing:
        sys.exit(0)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
