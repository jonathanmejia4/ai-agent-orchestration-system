#!/usr/bin/env python3
"""
Security Test Generator
Version: 1.0.0
Last Updated: 2026-01-05
Owner: Builder
Classification: MEDIUM - Test Infrastructure

Generates security test files from Jinja2 templates.
Templates are located in templates/tests/security/.

Usage:
    python3 tools/generate_security_tests.py --task-id <task_id>
    python3 tools/generate_security_tests.py --task-id 3.1 --template auth_jwt
    python3 tools/generate_security_tests.py --list-templates

Referenced in:
    - tests/security/__init__.py
    - tests/security/README.md
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Try to import jinja2, provide helpful error if not installed
try:
    from jinja2 import Environment, FileSystemLoader, TemplateError
except ImportError:
    print("Error: jinja2 is required. Install with: pip install jinja2")
    sys.exit(1)

# Default configuration
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "tests" / "security"
OUTPUT_DIR = Path(__file__).parent.parent / "tests" / "security"

# Template to test file mapping
TEMPLATE_MAPPING = {
    "auth_jwt": "test_auth_sec020.py",
    "rbac_role": "test_validation_sec021.py",
    "audit_log": "test_audit_sec022.py",
    "rate_limit": "test_rate_limit_sec023.py",
}

def list_templates() -> List[str]:
    """List available templates."""
    templates = []
    if TEMPLATE_DIR.exists():
        for template_file in TEMPLATE_DIR.glob("*.jinja2"):
            template_name = template_file.stem.replace(".py", "")
            templates.append(template_name)
    return templates

def get_template_context(task_id: str) -> Dict:
    """Generate template context from task ID."""
    return {
        "task_id": task_id,
        "module_name": f"task_{task_id.replace('.', '_')}",
        "class_prefix": f"Task{task_id.replace('.', '')}",
        "generated_by": "generate_security_tests.py",
        "generation_date": "2026-01-05",
    }

def generate_test(
    template_name: str,
    task_id: str,
    output_dir: Optional[Path] = None,
    dry_run: bool = False
) -> Optional[Path]:
    """
    Generate a test file from a template.

    Args:
        template_name: Name of template (without .py.jinja2 extension)
        task_id: Task ID to generate tests for
        output_dir: Output directory (defaults to tests/security/<task_id>/)
        dry_run: If True, print output instead of writing file

    Returns:
        Path to generated file, or None if dry_run
    """
    template_file = TEMPLATE_DIR / f"{template_name}.py.jinja2"

    if not template_file.exists():
        print(f"Error: Template not found: {template_file}")
        return None

    # Set up Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )

    try:
        template = env.get_template(f"{template_name}.py.jinja2")
    except TemplateError as e:
        print(f"Error loading template: {e}")
        return None

    # Generate context and render
    context = get_template_context(task_id)

    try:
        rendered = template.render(**context)
    except TemplateError as e:
        print(f"Error rendering template: {e}")
        return None

    if dry_run:
        print(f"--- Generated from {template_name} for task {task_id} ---")
        print(rendered)
        return None

    # Determine output path
    if output_dir is None:
        output_dir = OUTPUT_DIR / task_id.replace(".", "_")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Use mapping or default naming
    output_filename = TEMPLATE_MAPPING.get(
        template_name,
        f"test_{template_name}_{task_id.replace('.', '_')}.py"
    )
    output_path = output_dir / output_filename

    output_path.write_text(rendered)
    print(f"Generated: {output_path}")

    return output_path

def generate_all_tests(task_id: str, output_dir: Optional[Path] = None, dry_run: bool = False) -> List[Path]:
    """Generate all security tests for a task."""
    templates = list_templates()
    generated = []

    for template_name in templates:
        result = generate_test(template_name, task_id, output_dir, dry_run)
        if result:
            generated.append(result)

    return generated

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate security tests from templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List available templates
    python3 tools/generate_security_tests.py --list-templates

    # Generate all tests for a task
    python3 tools/generate_security_tests.py --task-id 3.1

    # Generate specific test type
    python3 tools/generate_security_tests.py --task-id 3.1 --template auth_jwt

    # Preview without writing files
    python3 tools/generate_security_tests.py --task-id 3.1 --dry-run
        """
    )

    parser.add_argument(
        "--task-id",
        help="Task ID to generate tests for (e.g., 3.1)"
    )
    parser.add_argument(
        "--template",
        help="Specific template to use (default: all)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: tests/security/<task_id>/)"
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List available templates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated code without writing files"
    )

    args = parser.parse_args()

    if args.list_templates:
        templates = list_templates()
        if templates:
            print("Available templates:")
            for t in templates:
                print(f"  - {t}")
        else:
            print(f"No templates found in {TEMPLATE_DIR}")
        return 0

    if not args.task_id:
        parser.print_help()
        print("\nError: --task-id is required (unless using --list-templates)")
        return 1

    if args.template:
        result = generate_test(
            args.template,
            args.task_id,
            args.output_dir,
            args.dry_run
        )
        if result is None and not args.dry_run:
            return 1
    else:
        generated = generate_all_tests(
            args.task_id,
            args.output_dir,
            args.dry_run
        )
        if not generated and not args.dry_run:
            print("No tests were generated")
            return 1
        print(f"\nGenerated {len(generated)} test file(s)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
