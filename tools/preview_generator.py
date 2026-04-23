#!/usr/bin/env python3
"""
Preview Generator - Generate Diff Previews Before Task Execution

Runs template generation in dry-run mode and generates unified diffs
showing proposed changes before actually writing files. Enables PM
approval gate before Builder executes changes.

Usage:
    # Generate preview from task plan
    python3 tools/preview_generator.py .task/task-plan.yaml

    # Generate preview with specific output directory
    python3 tools/preview_generator.py .task/task-plan.yaml --output previews/

    # Generate preview in JSON format
    python3 tools/preview_generator.py .task/task-plan.yaml --json

    # Dry-run with template directory
    python3 tools/preview_generator.py .task/task-plan.yaml --templates templates/

    # Compare against existing files
    python3 tools/preview_generator.py .task/task-plan.yaml --compare-existing

Exit Codes:
    0 - Preview generated successfully
    1 - Preview shows changes (for approval workflow)
    2 - Error (missing files, invalid plan, etc.)

Referenced in:
    - SPEC_TO_DIFF_PREVIEWS_POLICY.md:731, 1509, 1520
    - Builder_Spec.md:728

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import difflib
import hashlib
import yaml
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import tempfile
import shutil

class ChangeType(Enum):
    """Types of file changes"""
    CREATE = "create"      # New file
    MODIFY = "modify"      # Existing file changed
    DELETE = "delete"      # File to be deleted
    RENAME = "rename"      # File renamed
    UNCHANGED = "unchanged"  # No changes

@dataclass
class FileChange:
    """Represents a proposed file change"""
    path: str
    change_type: ChangeType
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    old_path: Optional[str] = None  # For renames
    diff: Optional[str] = None
    line_additions: int = 0
    line_deletions: int = 0
    hash_before: Optional[str] = None
    hash_after: Optional[str] = None

@dataclass
class PreviewResult:
    """Result of preview generation"""
    task_id: str
    task_name: str
    generated_at: str
    changes: List[FileChange] = field(default_factory=list)
    total_files: int = 0
    files_created: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_unchanged: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    requires_approval: bool = False
    approval_reasons: List[str] = field(default_factory=list)

class TemplateEngine:
    """Simple template engine for preview generation"""

    VARIABLE_PATTERN = re.compile(r'\{\{([A-Z][A-Z0-9_]*)\}\}')

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def render(self, template_name: str, variables: Dict[str, Any]) -> str:
        """Render a template with given variables"""
        template_path = self.templates_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        content = template_path.read_text()
        return self._substitute_variables(content, variables)

    def _substitute_variables(self, content: str, variables: Dict[str, Any]) -> str:
        """Substitute {{VARIABLE}} placeholders"""
        def replacer(match):
            var_name = match.group(1)
            if var_name in variables:
                return str(variables[var_name])
            return match.group(0)  # Keep original if not found

        return self.VARIABLE_PATTERN.sub(replacer, content)

    def render_string(self, template_content: str, variables: Dict[str, Any]) -> str:
        """Render a template string directly"""
        return self._substitute_variables(template_content, variables)

class PreviewGenerator:
    """Generates diff previews for task execution"""

    def __init__(self, templates_dir: Optional[Path] = None, verbose: bool = False):
        self.templates_dir = templates_dir or Path('templates')
        self.verbose = verbose
        self.template_engine = TemplateEngine(self.templates_dir)

    def calculate_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]

    def generate_diff(self, old_content: str, new_content: str,
                      old_path: str = 'old', new_path: str = 'new') -> str:
        """Generate unified diff between two contents"""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f'a/{old_path}',
            tofile=f'b/{new_path}',
            lineterm=''
        )
        return ''.join(diff)

    def count_diff_lines(self, diff_text: str) -> Tuple[int, int]:
        """Count additions and deletions in a diff"""
        additions = 0
        deletions = 0

        for line in diff_text.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1

        return additions, deletions

    def load_task_plan(self, plan_path: Path) -> Dict[str, Any]:
        """Load task plan from YAML file"""
        if not plan_path.exists():
            raise FileNotFoundError(f"Task plan not found: {plan_path}")

        with open(plan_path, 'r') as f:
            return yaml.safe_load(f)

    def load_wiring(self, task_dir: Path) -> Dict[str, Any]:
        """Load SSOT wiring file"""
        wiring_path = task_dir / '.task' / 'wiring.yaml'
        if wiring_path.exists():
            with open(wiring_path, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def get_template_variables(self, plan: Dict[str, Any],
                                wiring: Dict[str, Any]) -> Dict[str, Any]:
        """Extract template variables from plan and wiring"""
        variables = {}

        # From plan
        if 'variables' in plan:
            variables.update(plan['variables'])

        # From wiring identity
        identity = wiring.get('identity', {})
        variables['TASK_ID'] = identity.get('task_id', '')
        variables['TASK_NAME'] = identity.get('task_name', '')
        variables['SPEC_REF'] = identity.get('spec_ref', '')

        # Common variables
        variables['TIMESTAMP'] = datetime.now().isoformat()
        variables['DATE'] = datetime.now().strftime('%Y-%m-%d')

        return variables

    def generate_file_content(self, output_spec: Dict[str, Any],
                               variables: Dict[str, Any]) -> str:
        """Generate content for an output file"""
        # If template specified, render it
        if 'template' in output_spec:
            template_name = output_spec['template']
            return self.template_engine.render(template_name, variables)

        # If content specified directly, use it
        if 'content' in output_spec:
            return self.template_engine.render_string(output_spec['content'], variables)

        # If generator specified, note that generator preview is not yet supported
        # Generator execution requires subprocess management and security considerations
        if 'generator' in output_spec:
            generator = output_spec['generator']
            return (f"# Generator Preview: {generator}\n"
                    f"# Note: Generator-based previews show scaffold output.\n"
                    f"# Actual generation occurs during task execution.\n"
                    f"# Template-based previews are fully functional.\n")

        return ""

    def generate_preview(self, plan_path: Path,
                          base_dir: Optional[Path] = None) -> PreviewResult:
        """
        Generate preview of changes from task plan.

        Args:
            plan_path: Path to task plan YAML
            base_dir: Base directory for file comparisons

        Returns:
            PreviewResult with all proposed changes
        """
        base_dir = base_dir or plan_path.parent.parent

        # Load plan and wiring
        plan = self.load_task_plan(plan_path)
        task_dir = plan_path.parent
        wiring = self.load_wiring(task_dir)

        # Create result
        result = PreviewResult(
            task_id=plan.get('task_id', wiring.get('identity', {}).get('task_id', 'unknown')),
            task_name=plan.get('task_name', wiring.get('identity', {}).get('task_name', 'unknown')),
            generated_at=datetime.now().isoformat()
        )

        # Get template variables
        variables = self.get_template_variables(plan, wiring)

        # Process expected outputs
        outputs = plan.get('expected_outputs', [])
        if not outputs:
            # Try wiring outputs
            outputs = wiring.get('wiring', {})

        # Generate preview for each output file
        for output_spec in self._normalize_outputs(outputs):
            file_path = output_spec.get('path', '')
            if not file_path:
                continue

            full_path = base_dir / file_path
            new_content = self.generate_file_content(output_spec, variables)

            # Determine change type
            if full_path.exists():
                old_content = full_path.read_text()
                if old_content == new_content:
                    change_type = ChangeType.UNCHANGED
                    result.files_unchanged += 1
                else:
                    change_type = ChangeType.MODIFY
                    result.files_modified += 1
            else:
                old_content = ""
                change_type = ChangeType.CREATE
                result.files_created += 1

            # Generate diff
            diff_text = ""
            additions = 0
            deletions = 0
            if change_type != ChangeType.UNCHANGED:
                diff_text = self.generate_diff(old_content, new_content, file_path, file_path)
                additions, deletions = self.count_diff_lines(diff_text)

            # Create file change record
            change = FileChange(
                path=file_path,
                change_type=change_type,
                old_content=old_content if change_type == ChangeType.MODIFY else None,
                new_content=new_content,
                diff=diff_text if diff_text else None,
                line_additions=additions,
                line_deletions=deletions,
                hash_before=self.calculate_hash(old_content) if old_content else None,
                hash_after=self.calculate_hash(new_content) if new_content else None
            )
            result.changes.append(change)
            result.total_additions += additions
            result.total_deletions += deletions

        # Calculate totals
        result.total_files = len(result.changes)

        # Determine if approval required
        if result.files_modified > 0 or result.files_deleted > 0:
            result.requires_approval = True
            if result.files_modified > 0:
                result.approval_reasons.append(f"{result.files_modified} file(s) will be modified")
            if result.files_deleted > 0:
                result.approval_reasons.append(f"{result.files_deleted} file(s) will be deleted")
        if result.total_deletions > 50:
            result.requires_approval = True
            result.approval_reasons.append(f"Large deletion count: {result.total_deletions} lines")

        return result

    def _normalize_outputs(self, outputs: Any) -> List[Dict[str, Any]]:
        """Normalize outputs to list of dicts"""
        if isinstance(outputs, list):
            result = []
            for item in outputs:
                if isinstance(item, str):
                    result.append({'path': item})
                elif isinstance(item, dict):
                    result.append(item)
            return result
        elif isinstance(outputs, dict):
            # Wiring format with controller, service, etc.
            result = []
            for key, value in outputs.items():
                if isinstance(value, str):
                    result.append({'path': value, 'type': key})
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, str):
                            result.append({'path': v, 'type': key})
            return result
        return []

    def generate_unified_diff(self, result: PreviewResult) -> str:
        """Generate combined unified diff for all changes"""
        lines = []
        lines.append(f"# Preview for task: {result.task_name}")
        lines.append(f"# Generated at: {result.generated_at}")
        lines.append(f"# Files: {result.total_files} total")
        lines.append(f"#   Created: {result.files_created}")
        lines.append(f"#   Modified: {result.files_modified}")
        lines.append(f"#   Deleted: {result.files_deleted}")
        lines.append(f"#   Unchanged: {result.files_unchanged}")
        lines.append(f"# Lines: +{result.total_additions} -{result.total_deletions}")
        lines.append("")

        for change in result.changes:
            if change.diff:
                lines.append(change.diff)
                lines.append("")

        return '\n'.join(lines)

    def generate_manifest(self, result: PreviewResult) -> Dict[str, Any]:
        """Generate preview manifest YAML"""
        return {
            'preview': {
                'task_id': result.task_id,
                'task_name': result.task_name,
                'generated_at': result.generated_at,
                'requires_approval': result.requires_approval,
                'approval_reasons': result.approval_reasons,
                'summary': {
                    'total_files': result.total_files,
                    'files_created': result.files_created,
                    'files_modified': result.files_modified,
                    'files_deleted': result.files_deleted,
                    'files_unchanged': result.files_unchanged,
                    'total_additions': result.total_additions,
                    'total_deletions': result.total_deletions
                },
                'changes': [
                    {
                        'path': c.path,
                        'type': c.change_type.value,
                        'additions': c.line_additions,
                        'deletions': c.line_deletions,
                        'hash_before': c.hash_before,
                        'hash_after': c.hash_after
                    }
                    for c in result.changes
                    if c.change_type != ChangeType.UNCHANGED
                ]
            }
        }

    def save_preview(self, result: PreviewResult, output_dir: Path):
        """Save preview files to output directory"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save unified diff
        diff_path = output_dir / 'preview.diff'
        diff_content = self.generate_unified_diff(result)
        diff_path.write_text(diff_content)

        # Save manifest
        manifest_path = output_dir / 'preview_manifest.yaml'
        manifest = self.generate_manifest(result)
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

        # Save individual file previews
        files_dir = output_dir / 'files'
        files_dir.mkdir(exist_ok=True)

        for change in result.changes:
            if change.new_content:
                file_preview_path = files_dir / change.path
                file_preview_path.parent.mkdir(parents=True, exist_ok=True)
                file_preview_path.write_text(change.new_content)

        return diff_path, manifest_path

def main():
    parser = argparse.ArgumentParser(
        description='Generate diff previews before task execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s .task/task-plan.yaml
    %(prog)s .task/task-plan.yaml --output previews/
    %(prog)s .task/task-plan.yaml --json
    %(prog)s .task/task-plan.yaml --templates templates/
        """
    )

    parser.add_argument('plan', type=Path, help='Path to task plan YAML')
    parser.add_argument('--output', '-o', type=Path, default=Path('previews'),
                        help='Output directory for preview files')
    parser.add_argument('--templates', '-t', type=Path,
                        help='Templates directory')
    parser.add_argument('--base-dir', '-b', type=Path,
                        help='Base directory for file comparisons')
    parser.add_argument('--json', action='store_true',
                        help='Output result as JSON')
    parser.add_argument('--diff-only', action='store_true',
                        help='Only output unified diff')
    parser.add_argument('--manifest-only', action='store_true',
                        help='Only output manifest')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress output on success')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Validate inputs
    if not args.plan.exists():
        print(f"Error: Task plan not found: {args.plan}", file=sys.stderr)
        sys.exit(2)

    # Create generator
    templates_dir = args.templates or Path('templates')
    generator = PreviewGenerator(templates_dir=templates_dir, verbose=args.verbose)

    # Generate preview
    try:
        base_dir = args.base_dir or args.plan.parent.parent
        result = generator.generate_preview(args.plan, base_dir)
    except Exception as e:
        print(f"Error: Preview generation failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)

    # Output results
    if args.json:
        output = {
            'task_id': result.task_id,
            'task_name': result.task_name,
            'generated_at': result.generated_at,
            'requires_approval': result.requires_approval,
            'approval_reasons': result.approval_reasons,
            'summary': {
                'total_files': result.total_files,
                'files_created': result.files_created,
                'files_modified': result.files_modified,
                'files_deleted': result.files_deleted,
                'files_unchanged': result.files_unchanged,
                'total_additions': result.total_additions,
                'total_deletions': result.total_deletions
            },
            'changes': [
                {
                    'path': c.path,
                    'type': c.change_type.value,
                    'additions': c.line_additions,
                    'deletions': c.line_deletions,
                    'diff': c.diff
                }
                for c in result.changes
            ]
        }
        print(json.dumps(output, indent=2))

    elif args.diff_only:
        print(generator.generate_unified_diff(result))

    elif args.manifest_only:
        manifest = generator.generate_manifest(result)
        print(yaml.dump(manifest, default_flow_style=False))

    else:
        # Save full preview
        diff_path, manifest_path = generator.save_preview(result, args.output)

        if not args.quiet:
            print("=" * 60)
            print("PREVIEW GENERATED")
            print("=" * 60)
            print(f"Task: {result.task_name} ({result.task_id})")
            print(f"Generated: {result.generated_at}")
            print("")
            print("Summary:")
            print(f"  Total files: {result.total_files}")
            print(f"  Created:     {result.files_created}")
            print(f"  Modified:    {result.files_modified}")
            print(f"  Deleted:     {result.files_deleted}")
            print(f"  Unchanged:   {result.files_unchanged}")
            print(f"  Additions:   +{result.total_additions}")
            print(f"  Deletions:   -{result.total_deletions}")
            print("")
            print(f"Preview files:")
            print(f"  Diff:     {diff_path}")
            print(f"  Manifest: {manifest_path}")
            print("")

            if result.requires_approval:
                print("⚠️  APPROVAL REQUIRED")
                for reason in result.approval_reasons:
                    print(f"   - {reason}")
                print("")

            # Show changes summary
            if result.changes:
                print("Changes:")
                for change in result.changes:
                    if change.change_type == ChangeType.UNCHANGED:
                        continue
                    icon = {
                        ChangeType.CREATE: "+",
                        ChangeType.MODIFY: "~",
                        ChangeType.DELETE: "-",
                        ChangeType.RENAME: "→"
                    }.get(change.change_type, "?")
                    print(f"  [{icon}] {change.path} (+{change.line_additions}/-{change.line_deletions})")

            print("=" * 60)

    # Exit code based on whether changes exist
    if result.requires_approval:
        sys.exit(1)  # Changes require approval
    else:
        sys.exit(0)  # No changes or only creates

if __name__ == '__main__':
    main()
