#!/usr/bin/env python3
"""
the system Template Generator

Purpose: Generate task outputs from templates for idempotence testing.
Used by: .github/workflows/idempotence.yml
Version: 1.0.0

This script generates output files from the system templates, supporting the
idempotence testing workflow that verifies generation stability.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import Jinja2, fall back to simple replacement if not available
try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

class SystemGenerator:
    """Template generator for the system tasks."""

    def __init__(self, task_id: str, output_dir: str, dry_run: bool = False):
        self.task_id = task_id
        self.output_dir = Path(output_dir)
        self.dry_run = dry_run
        self.root = Path(__file__).parent.parent
        self.templates_dir = self.root / "templates"
        self.tasks_dir = self.root / "tasks"
        self.generated_files: List[str] = []

    def load_task_manifest(self) -> Optional[Dict[str, Any]]:
        """Load task.yaml manifest for the specified task."""
        task_path = self.tasks_dir / self.task_id / "task.yaml"
        if not task_path.exists():
            print(f"Warning: No manifest found at {task_path}", file=sys.stderr)
            return None

        try:
            import yaml
            with open(task_path) as f:
                return yaml.safe_load(f)
        except ImportError:
            print("Warning: PyYAML not installed, skipping manifest", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Warning: Failed to load manifest: {e}", file=sys.stderr)
            return None

    def get_template_context(self, manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build template rendering context."""
        context = {
            "task_id": self.task_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "generator_version": "1.0.0",
            "saf_version": "2.10.17",
        }

        if manifest:
            context.update({
                "metadata": manifest.get("metadata", {}),
                "version": manifest.get("version", "0.0.0"),
                "dependencies": manifest.get("dependencies", {}),
            })

        return context

    def render_template(self, template_path: Path, context: Dict[str, Any]) -> str:
        """Render a template with the given context."""
        if HAS_JINJA2:
            env = Environment(
                loader=FileSystemLoader(str(template_path.parent)),
                undefined=StrictUndefined,
                keep_trailing_newline=True,
            )
            template = env.get_template(template_path.name)
            return template.render(**context)
        else:
            # Simple variable substitution fallback
            content = template_path.read_text()
            for key, value in context.items():
                if isinstance(value, str):
                    content = content.replace(f"{{{{ {key} }}}}", value)
                    content = content.replace(f"{{{{{key}}}}}", value)
            return content

    def generate(self) -> bool:
        """Generate output files for the task."""
        print(f"Generating outputs for task: {self.task_id}")

        manifest = self.load_task_manifest()
        context = self.get_template_context(manifest)

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Get input templates from manifest or use defaults
        inputs = []
        if manifest and "artifacts" in manifest:
            inputs = manifest["artifacts"].get("inputs", [])

        if not inputs:
            # Default: copy task source files
            task_source = self.tasks_dir / self.task_id
            if task_source.exists():
                inputs = [str(p.relative_to(self.root)) for p in task_source.glob("**/*") if p.is_file()]

        success = True
        for input_path in inputs:
            try:
                source = self.root / input_path
                if not source.exists():
                    print(f"  Warning: Input not found: {input_path}", file=sys.stderr)
                    continue

                # Determine output path
                if source.suffix in (".jinja2", ".j2"):
                    output_name = source.stem  # Remove .jinja2 extension
                else:
                    output_name = source.name

                output_path = self.output_dir / output_name

                if self.dry_run:
                    print(f"  [DRY RUN] Would generate: {output_path}")
                else:
                    # Render template or copy file
                    if source.suffix in (".jinja2", ".j2"):
                        content = self.render_template(source, context)
                        output_path.write_text(content)
                    else:
                        shutil.copy2(source, output_path)

                    self.generated_files.append(str(output_path))
                    print(f"  Generated: {output_path}")

            except Exception as e:
                print(f"  Error processing {input_path}: {e}", file=sys.stderr)
                success = False

        # Write outputs manifest
        if not self.dry_run and self.generated_files:
            self.write_outputs_manifest()

        return success

    def write_outputs_manifest(self):
        """Write manifest of generated files for tracking."""
        manifest_path = self.output_dir / ".generated_manifest.json"
        manifest = {
            "task_id": self.task_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "files": [],
        }

        for file_path in self.generated_files:
            path = Path(file_path)
            if path.exists():
                content = path.read_bytes()
                manifest["files"].append({
                    "path": str(path.relative_to(self.output_dir)),
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                })

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        print(f"  Manifest: {manifest_path}")

def main():
    parser = argparse.ArgumentParser(
        description="the system Template Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --task=task-auth-001 --output=./output
  %(prog)s --task=task-logging-002 --output=./gen --dry-run
        """,
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task ID to generate (e.g., task-auth-001)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )

    args = parser.parse_args()

    generator = SystemGenerator(
        task_id=args.task,
        output_dir=args.output,
        dry_run=args.dry_run,
    )

    success = generator.generate()

    if success:
        print(f"\nGeneration complete: {len(generator.generated_files)} files")
        sys.exit(0)
    else:
        print("\nGeneration completed with errors", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
