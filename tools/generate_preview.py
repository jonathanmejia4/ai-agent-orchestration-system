#!/usr/bin/env python3
"""
the system Preview Generator

Generates a spec-to-diff preview for a task before code generation.
Part of the Stage -1 (Preview & Approval) gate.

Usage:
    python3 tools/generate_preview.py --task <task_id>

See: PLANNING/SPEC_TO_DIFF_PREVIEWS_POLICY.md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

def analyze_task_spec(task_dir: Path) -> dict:
    """Analyze task specification to determine file changes."""
    import yaml

    files_to_create = []
    files_to_modify = []
    files_to_delete = []
    notes = []

    task_yaml = task_dir / ".task" / "task.yaml"
    wiring_yaml = task_dir / ".task" / "wiring.yaml"

    # Analyze task.yaml for template references
    if task_yaml.exists():
        try:
            with open(task_yaml) as f:
                spec = yaml.safe_load(f) or {}

            # Check outputs section for files to create
            outputs = spec.get("outputs", [])
            for output in outputs:
                if isinstance(output, dict):
                    path = output.get("path", "")
                    if path:
                        files_to_create.append({
                            "path": path,
                            "template": output.get("template", "unknown"),
                            "type": output.get("type", "file")
                        })
                elif isinstance(output, str):
                    files_to_create.append({"path": output, "template": "direct", "type": "file"})

            # Check for deprecated/removal markers
            deprecated = spec.get("deprecated", [])
            for dep in deprecated:
                if isinstance(dep, str):
                    files_to_delete.append({"path": dep, "reason": "deprecated"})

            # Check for modifications to existing files
            modifications = spec.get("modify", []) or spec.get("patches", [])
            for mod in modifications:
                if isinstance(mod, dict):
                    files_to_modify.append({
                        "path": mod.get("path", ""),
                        "operation": mod.get("operation", "patch"),
                        "lines_affected": mod.get("lines", "unknown")
                    })

            notes.append(f"Analyzed task.yaml: {len(outputs)} outputs defined")

        except Exception as e:
            notes.append(f"Warning: Could not parse task.yaml: {e}")

    # Analyze wiring.yaml for dependencies
    if wiring_yaml.exists():
        try:
            with open(wiring_yaml) as f:
                wiring = yaml.safe_load(f) or {}

            deps = wiring.get("dependencies", [])
            notes.append(f"Found {len(deps)} dependencies in wiring.yaml")

            # Check for protected regions that might be modified
            protected = wiring.get("protected_regions", [])
            for region in protected:
                if isinstance(region, dict) and region.get("file"):
                    files_to_modify.append({
                        "path": region["file"],
                        "operation": "protected_region_update",
                        "region": region.get("name", "unnamed")
                    })

        except Exception as e:
            notes.append(f"Warning: Could not parse wiring.yaml: {e}")

    # Scan for source files in task directory
    src_dir = task_dir / "src"
    if src_dir.exists():
        for src_file in src_dir.rglob("*"):
            if src_file.is_file() and not src_file.name.startswith("."):
                rel_path = src_file.relative_to(task_dir)
                files_to_create.append({
                    "path": str(rel_path),
                    "template": "source",
                    "type": "source_file"
                })

    return {
        "files_to_create": files_to_create,
        "files_to_modify": files_to_modify,
        "files_to_delete": files_to_delete,
        "notes": notes
    }

def calculate_risk_score(changes: dict) -> int:
    """Calculate risk score based on change analysis."""
    score = 0

    # More files = higher risk
    create_count = len(changes.get("files_to_create", []))
    modify_count = len(changes.get("files_to_modify", []))
    delete_count = len(changes.get("files_to_delete", []))

    score += min(create_count * 2, 30)  # Up to 30 points for creations
    score += min(modify_count * 5, 40)  # Up to 40 points for modifications
    score += min(delete_count * 10, 30) # Up to 30 points for deletions

    # Check for high-risk patterns
    for mod in changes.get("files_to_modify", []):
        path = mod.get("path", "")
        if any(p in path for p in ["config", "security", "auth", "secret"]):
            score += 10

    return min(score, 100)

def generate_preview(task_id: str, output_dir: Path) -> dict:
    """Generate a preview for the specified task."""
    # Look for task definition
    task_dir = Path("tasks") / task_id
    if not task_dir.exists():
        task_dir = Path(".task")  # Fallback to current directory

    # Analyze the task spec
    if (task_dir / ".task").exists() or task_dir.exists():
        changes = analyze_task_spec(task_dir)
    else:
        changes = {
            "files_to_create": [],
            "files_to_modify": [],
            "files_to_delete": [],
            "notes": [f"Task directory not found: {task_dir}"]
        }

    risk_score = calculate_risk_score(changes)
    notes_list = changes.pop("notes", [])

    preview = {
        "task_id": task_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "generator": "tools/generate_preview.py",
        "status": "pending_approval",
        "changes": changes,
        "risk_score": risk_score,
        "notes": "; ".join(notes_list) if notes_list else "Preview generated - awaiting approval",
        "summary": {
            "total_files_affected": len(changes["files_to_create"]) + len(changes["files_to_modify"]) + len(changes["files_to_delete"]),
            "creates": len(changes["files_to_create"]),
            "modifies": len(changes["files_to_modify"]),
            "deletes": len(changes["files_to_delete"])
        }
    }

    # Create preview directory
    preview_dir = output_dir / task_id
    preview_dir.mkdir(parents=True, exist_ok=True)

    # Write preview file
    preview_file = preview_dir / "preview.json"
    with open(preview_file, 'w') as f:
        json.dump(preview, f, indent=2)

    return preview

def main():
    parser = argparse.ArgumentParser(
        description="Generate spec-to-diff preview for a task"
    )
    parser.add_argument('--task', '-b', required=True,
                        help='Task ID to generate preview for')
    parser.add_argument('--output-dir', '-o', type=Path,
                        default=Path('LogBook/previews'),
                        help='Output directory for previews')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    print(f"Generating preview for task: {args.task}")
    preview = generate_preview(args.task, args.output_dir)

    preview_path = args.output_dir / args.task / "preview.json"
    print(f"Preview written to: {preview_path}")

    if args.verbose:
        print(json.dumps(preview, indent=2))

    print("\nNext steps:")
    print(f"  1. Review the preview: cat {preview_path}")
    print(f"  2. Approve: python tools/approve_preview.py --task {args.task} --decision approved")

    return 0

if __name__ == "__main__":
    sys.exit(main())
