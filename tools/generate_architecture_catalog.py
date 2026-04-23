#!/usr/bin/env python3
"""
Architecture Catalog Generator

Generates a comprehensive catalog of the repository's folder structure,
documenting where files live at a glance.

Outputs:
- ARCHITECTURE_CATALOG.md (human-readable)
- PLANNING/architecture/current_structure.yaml (machine-readable)

Usage:
    python3 tools/generate_architecture_catalog.py --force    # Force regenerate
    python3 tools/generate_architecture_catalog.py --check    # Check if stale
    python3 tools/generate_architecture_catalog.py            # Normal run

Version: 1.0.0
Created: 2026-01-09
Owner: PM
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:
    print("Error: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


# Directories to skip during scanning
SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    '.idea', '.vscode', '.DS_Store', '.saf', '.state_backups',
    'eggs', '*.egg-info', 'dist', 'build', '.tox', '.pytest_cache',
    '.mypy_cache', '.coverage', 'htmlcov'
}

# Known directory purposes (fallback when no README exists)
KNOWN_PURPOSES = {
    '.claude': 'Agent framework configuration',
    '.claude/agents': 'Agent role definitions (PM, Builder, Critic, etc.)',
    '.claude/guidelines': 'Operating procedures & policies',
    '.claude/commands': 'Skill definitions for /slash commands',
    '.claude/hooks': 'Git hooks for automation',
    '.github': 'GitHub configuration',
    '.github/workflows': 'CI/CD workflow definitions',
    '.github/scripts': 'GitHub Actions helper scripts',
    'PLANNING': 'Strategic planning documents',
    'PLANNING/business': 'Business strategy & marketing tools',
    'PLANNING/dependencies': 'Dependency graph storage',
    'PLANNING/schemas': 'YAML validation schemas',
    'PLANNING/specs': 'Technical specifications',
    'PLANNING/architecture': 'Architecture catalog data',
    'PLANNING/policies': 'Governance policies',
    'PLANNING/future': 'Future feature plans',
    'PLANNING/examples': 'Example configurations',
    'PLANNING/action_plans': 'Action plan templates',
    'PLANNING/checklists': 'Verification checklists',
    'PLANNING/migrations': 'Migration guides',
    'PLANNING/prompts': 'Agent prompt templates',
    'LogBook': 'Audit logs & agent state',
    'LogBook/agents': 'Agent activity logs',
    'LogBook/pm': 'Project Manager decisions',
    'LogBook/planner': 'Planner decision logs',
    'LogBook/critic': 'Critic verdicts & reviews',
    'LogBook/verification': 'Verification results',
    'LogBook/audit': 'Audit trail logs',
    'LogBook/work-orders': 'Work order queue',
    'LogBook/orchestrator': 'Orchestrator state',
    'LogBook/progress': 'Progress tracking',
    'LogBook/exceptions': 'Exception logs',
    'src': 'Application source code',
    'src/auth': 'Authentication (MFA, OAuth)',
    'src/accounts': 'User account management',
    'src/payments': 'Payment processing',
    'src/billing': 'Billing & invoicing',
    'src/subscriptions': 'Subscription management',
    'src/checkout': 'Payment checkout flow',
    'src/notifications': 'Notification system',
    'src/support': 'Customer support features',
    'src/security': 'Security features',
    'src/licensing': 'License management',
    'src/accessibility': 'Accessibility features',
    'src/consent': 'Consent management',
    'src/feedback': 'User feedback system',
    'src/loyalty': 'Loyalty program',
    'src/onboarding': 'User onboarding',
    'src/products': 'Product management',
    'src/data': 'Data utilities',
    'src/trust': 'Trust & safety',
    'tools': 'Utility scripts & automation',
    'tools/hooks': 'Git hook scripts',
    'tools/ai-adapter': 'AI adapter utilities',
    'templates': 'Jinja2 code templates',
    'templates/compliance': 'Compliance templates',
    'tests': 'Test suites',
    'tests/unit': 'Unit tests',
    'tests/integration': 'Integration tests',
    'tests/security': 'Security tests',
    'tests/drift': 'Drift detection tests',
    'docs': 'Documentation (Sphinx)',
    'docs/architecture': 'Architecture documentation',
    'docs/api': 'API documentation',
    'docs/guides': 'User guides',
    'docs/meta': 'Meta documentation',
    'issues': 'Issue tracking (lanes A-Z)',
    'tasks': 'Task implementations',
    'plugins': 'Agent plugins',
    'config': 'Configuration files',
    'infrastructure': 'Infrastructure & deployment',
    'infrastructure/providers': 'Cloud providers (AWS, GCP, Azure)',
    'infrastructure/failover': 'Failover logic',
    'infrastructure/monitoring': 'Health monitoring',
    'infrastructure/kubernetes': 'Kubernetes configs',
    'infrastructure/terraform': 'Terraform IaC',
    'api': 'API definitions',
    'archives': 'Archived content',
    'archives/golden': 'Golden reference files',
    'manifests': 'Deployment manifests',
    'scripts': 'Shell scripts',
    'resume_info': 'Resume & profile documents',
    'reports': 'Generated reports',
    'prompts': 'Prompt templates',
}

# File extension to type mapping
EXTENSION_TYPES = {
    '.py': 'Python',
    '.md': 'Markdown',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.json': 'JSON',
    '.j2': 'Jinja2 Template',
    '.jinja2': 'Jinja2 Template',
    '.sh': 'Shell',
    '.bash': 'Shell',
    '.html': 'HTML',
    '.css': 'CSS',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.sql': 'SQL',
    '.txt': 'Text',
    '.rst': 'reStructuredText',
    '.toml': 'TOML',
    '.ini': 'INI',
    '.cfg': 'Config',
    '.env': 'Environment',
    '.dockerfile': 'Dockerfile',
    '.tf': 'Terraform',
}


@dataclass
class DirectoryInfo:
    """Information about a directory."""
    path: str
    name: str
    purpose: str
    file_count: int
    dir_count: int
    total_size: int
    files_by_extension: Dict[str, int] = field(default_factory=dict)
    subdirectories: List[str] = field(default_factory=list)
    depth: int = 0


@dataclass
class FileStats:
    """Overall file statistics."""
    total_files: int = 0
    total_dirs: int = 0
    total_size: int = 0
    by_extension: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_location: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class ArchitectureCatalogGenerator:
    """Generates the Architecture Catalog."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.yaml_output = self.root_path / "PLANNING" / "architecture" / "current_structure.yaml"
        self.md_output = self.root_path / "ARCHITECTURE_CATALOG.md"
        self.history_dir = self.root_path / "PLANNING" / "architecture" / "history"

        self.directories: Dict[str, DirectoryInfo] = {}
        self.stats = FileStats()
        self.tree_string = ""

    def should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        name = path.name
        if name in SKIP_DIRS:
            return True
        if name.startswith('.') and name not in {'.claude', '.github', '.saf'}:
            return True
        return False

    def get_purpose(self, rel_path: str) -> str:
        """Get purpose description for a directory."""
        # Check known purposes first
        if rel_path in KNOWN_PURPOSES:
            return KNOWN_PURPOSES[rel_path]

        # Try to read from README.md
        readme_path = self.root_path / rel_path / "README.md"
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding='utf-8')
                # Try to extract first meaningful line after title
                lines = content.split('\n')
                for line in lines[1:10]:  # Check first 10 lines after title
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('```'):
                        # Clean up markdown
                        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
                        line = re.sub(r'[*_`]', '', line)
                        if len(line) > 10 and len(line) < 100:
                            return line[:80] + ('...' if len(line) > 80 else '')
            except Exception:
                pass

        return "Directory"

    def scan_directory(self, path: Path, depth: int = 0) -> Optional[DirectoryInfo]:
        """Scan a directory and collect information."""
        if self.should_skip(path):
            return None

        rel_path = str(path.relative_to(self.root_path))
        if rel_path == '.':
            rel_path = ''

        info = DirectoryInfo(
            path=rel_path or '.',
            name=path.name or self.root_path.name,
            purpose=self.get_purpose(rel_path) if rel_path else 'Repository Root',
            file_count=0,
            dir_count=0,
            total_size=0,
            depth=depth
        )

        try:
            entries = list(path.iterdir())
        except PermissionError:
            return None

        for entry in sorted(entries, key=lambda x: (not x.is_dir(), x.name.lower())):
            if self.should_skip(entry):
                continue

            if entry.is_file():
                info.file_count += 1
                self.stats.total_files += 1

                try:
                    size = entry.stat().st_size
                    info.total_size += size
                    self.stats.total_size += size
                except OSError:
                    pass

                ext = entry.suffix.lower() or '.no_ext'
                info.files_by_extension[ext] = info.files_by_extension.get(ext, 0) + 1
                self.stats.by_extension[ext] += 1

                # Track by top-level location
                if rel_path:
                    top_level = rel_path.split('/')[0]
                    self.stats.by_location[top_level] += 1

            elif entry.is_dir():
                subdir_info = self.scan_directory(entry, depth + 1)
                if subdir_info:
                    info.subdirectories.append(subdir_info.path)
                    info.dir_count += 1
                    self.stats.total_dirs += 1

        self.directories[rel_path or '.'] = info
        return info

    def generate_tree_string(self, max_depth: int = 3) -> str:
        """Generate ASCII tree visualization."""
        lines = [f"{self.root_path.name}/"]

        def add_tree_level(dir_path: str, prefix: str, depth: int):
            if depth > max_depth:
                return

            info = self.directories.get(dir_path)
            if not info:
                return

            # Get subdirectories
            subdirs = []
            for subdir_path in info.subdirectories:
                subdir_info = self.directories.get(subdir_path)
                if subdir_info:
                    subdirs.append(subdir_info)

            # Sort subdirectories
            subdirs.sort(key=lambda x: x.name.lower())

            for i, subdir in enumerate(subdirs):
                is_last = i == len(subdirs) - 1
                connector = "└── " if is_last else "├── "

                # Add comment with purpose (shortened)
                purpose = subdir.purpose[:30] + '...' if len(subdir.purpose) > 30 else subdir.purpose
                file_info = f" ({subdir.file_count} files)" if subdir.file_count > 0 else ""

                lines.append(f"{prefix}{connector}{subdir.name}/{file_info}")

                # Recurse if has subdirectories
                if subdir.subdirectories and depth < max_depth:
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    add_tree_level(subdir.path, new_prefix, depth + 1)

        add_tree_level('.', "", 0)
        return '\n'.join(lines)

    def generate_yaml(self) -> Dict:
        """Generate YAML data structure."""
        # Sort extensions by count
        sorted_extensions = sorted(
            self.stats.by_extension.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Sort locations by count
        sorted_locations = sorted(
            self.stats.by_location.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Build directory list
        dir_list = []
        for path, info in sorted(self.directories.items(), key=lambda x: x[0]):
            dir_data = {
                'path': info.path,
                'name': info.name,
                'purpose': info.purpose,
                'file_count': info.file_count,
                'dir_count': info.dir_count,
                'depth': info.depth,
            }
            if info.files_by_extension:
                dir_data['files_by_extension'] = dict(info.files_by_extension)
            if info.subdirectories:
                dir_data['subdirectories'] = info.subdirectories
            dir_list.append(dir_data)

        return {
            'metadata': {
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'generator': 'tools/generate_architecture_catalog.py',
                'version': '1.0.0',
                'root_path': str(self.root_path),
            },
            'statistics': {
                'total_directories': self.stats.total_dirs + 1,  # +1 for root
                'total_files': self.stats.total_files,
                'total_size_bytes': self.stats.total_size,
                'by_extension': dict(sorted_extensions),
                'by_location': dict(sorted_locations),
            },
            'quick_navigation': {
                'agent_definitions': '.claude/agents/',
                'custom_guidelines': '.claude/guidelines/',
                'issue_tracking': 'issues/',
                'python_tools': 'tools/',
                'logs_audit': 'LogBook/',
                'planning': 'PLANNING/',
                'ci_cd': '.github/workflows/',
            },
            'tree_structure': self.tree_string,
            'directories': dir_list,
        }

    def generate_markdown(self, yaml_data: Dict) -> str:
        """Generate markdown catalog."""
        stats = yaml_data['statistics']
        nav = yaml_data['quick_navigation']

        # Format file size
        size_mb = stats['total_size_bytes'] / (1024 * 1024)

        lines = [
            "# Architecture Catalog",
            "",
            f"> **Last Updated:** {yaml_data['metadata']['generated_at']}",
            f"> **Generated By:** `{yaml_data['metadata']['generator']}`",
            f"> **Data Source:** `PLANNING/architecture/current_structure.yaml`",
            "",
            "---",
            "",
            "## Statistics Dashboard",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Directories | {stats['total_directories']} |",
            f"| Total Files | {stats['total_files']} |",
            f"| Total Size | {size_mb:.1f} MB |",
        ]

        # Add top extensions
        ext_counts = stats['by_extension']
        for ext, count in list(ext_counts.items())[:5]:
            ext_name = EXTENSION_TYPES.get(ext, ext.upper().replace('.', ''))
            lines.append(f"| {ext_name} Files | {count} |")

        lines.extend([
            "",
            "### By Top-Level Directory",
            "",
            "| Directory | Files | Purpose |",
            "|-----------|-------|---------|",
        ])

        # Add top-level directories
        for loc, count in list(stats['by_location'].items())[:15]:
            purpose = KNOWN_PURPOSES.get(loc, 'Directory')[:40]
            lines.append(f"| `{loc}/` | {count} | {purpose} |")

        lines.extend([
            "",
            "---",
            "",
            "## Directory Tree (Quick Reference)",
            "",
            "```",
            self.tree_string,
            "```",
            "",
            "---",
            "",
            "## Quick Navigation Guide",
            "",
            "| Looking for... | Go to... |",
            "|----------------|----------|",
            f"| Agent definitions | `{nav['agent_definitions']}` |",
            f"| Custom guidelines | `{nav['custom_guidelines']}` |",
            f"| Issue tracking | `{nav['issue_tracking']}` |",
            f"| Python tools | `{nav['python_tools']}` |",
            f"| Logs & audit trail | `{nav['logs_audit']}` |",
            f"| Planning docs | `{nav['planning']}` |",
            f"| CI/CD workflows | `{nav['ci_cd']}` |",
            "",
            "---",
            "",
            "## Directory Details",
            "",
        ])

        # Add details for top-level directories
        top_level_dirs = [d for d in yaml_data['directories'] if d['depth'] == 1]
        top_level_dirs.sort(key=lambda x: x['name'].lower())

        for dir_info in top_level_dirs:
            name = dir_info['name']
            purpose = dir_info['purpose']
            file_count = dir_info['file_count']
            subdirs = dir_info.get('subdirectories', [])

            lines.extend([
                f"### {name}/ ({file_count} files)",
                f"> {purpose}",
                "",
            ])

            if subdirs:
                lines.append(f"<details>")
                lines.append(f"<summary>Show {len(subdirs)} subdirectories</summary>")
                lines.append("")
                lines.append("| Directory | Files | Purpose |")
                lines.append("|-----------|-------|---------|")

                for subdir_path in subdirs[:20]:
                    subdir_info = self.directories.get(subdir_path)
                    if subdir_info:
                        subdir_name = subdir_info.name
                        subdir_purpose = subdir_info.purpose[:50]
                        lines.append(f"| `{subdir_name}/` | {subdir_info.file_count} | {subdir_purpose} |")

                if len(subdirs) > 20:
                    lines.append(f"| *...and {len(subdirs) - 20} more* | | |")

                lines.append("")
                lines.append("</details>")

            lines.append("")

        # File type distribution
        lines.extend([
            "---",
            "",
            "## File Type Distribution",
            "",
            "| Extension | Count | Type |",
            "|-----------|-------|------|",
        ])

        for ext, count in list(ext_counts.items())[:15]:
            ext_type = EXTENSION_TYPES.get(ext, 'Other')
            lines.append(f"| `{ext}` | {count} | {ext_type} |")

        if len(ext_counts) > 15:
            lines.append(f"| *...and {len(ext_counts) - 15} more* | | |")

        # Component registry
        lines.extend([
            "",
            "---",
            "",
            "## Component Registry",
            "",
            "<details>",
            "<summary>All directories (click to expand)</summary>",
            "",
            "| Path | Files | Subdirs | Purpose |",
            "|------|-------|---------|---------|",
        ])

        for dir_info in yaml_data['directories'][:100]:
            path = dir_info['path']
            if path == '.':
                continue
            purpose = dir_info['purpose'][:40]
            lines.append(f"| `{path}/` | {dir_info['file_count']} | {dir_info['dir_count']} | {purpose} |")

        if len(yaml_data['directories']) > 100:
            lines.append(f"| *...and {len(yaml_data['directories']) - 100} more* | | | |")

        lines.extend([
            "",
            "</details>",
            "",
            "---",
            "",
            "## Metadata",
            "",
            f"- **Version:** {yaml_data['metadata']['version']}",
            f"- **Generator:** `{yaml_data['metadata']['generator']}`",
            "- **Data:** `PLANNING/architecture/current_structure.yaml`",
            "",
        ])

        return '\n'.join(lines)

    def save_snapshot(self):
        """Save historical snapshot."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        snapshot_path = self.history_dir / f"{date_str}-structure.yaml"

        if self.yaml_output.exists():
            shutil.copy2(self.yaml_output, snapshot_path)

        # Clean old snapshots (keep 30)
        snapshots = sorted(self.history_dir.glob('*-structure.yaml'), reverse=True)
        for old_snapshot in snapshots[30:]:
            old_snapshot.unlink()

    def compute_checksum(self) -> str:
        """Compute checksum of all directories and files."""
        hasher = hashlib.sha256()

        for path in sorted(self.root_path.rglob('*')):
            if self.should_skip(path):
                continue
            rel_path = str(path.relative_to(self.root_path))
            hasher.update(rel_path.encode())
            if path.is_file():
                try:
                    hasher.update(str(path.stat().st_mtime).encode())
                except OSError:
                    pass

        return hasher.hexdigest()[:16]

    def is_stale(self) -> bool:
        """Check if catalog needs regeneration."""
        if not self.yaml_output.exists():
            return True

        try:
            with open(self.yaml_output) as f:
                existing = yaml.safe_load(f)

            existing_checksum = existing.get('metadata', {}).get('checksum', '')
            current_checksum = self.compute_checksum()

            return existing_checksum != current_checksum
        except Exception:
            return True

    def generate(self, force: bool = False) -> bool:
        """Main generation method."""
        print(f"Architecture Catalog Generator")
        print(f"Root: {self.root_path}")
        print()

        if not force and not self.is_stale():
            print("Catalog is up to date. Use --force to regenerate.")
            return True

        print("Scanning directory tree...")
        self.scan_directory(self.root_path)

        print(f"Found {self.stats.total_dirs + 1} directories, {self.stats.total_files} files")
        print()

        print("Generating tree visualization...")
        self.tree_string = self.generate_tree_string(max_depth=2)

        print("Generating YAML output...")
        yaml_data = self.generate_yaml()
        yaml_data['metadata']['checksum'] = self.compute_checksum()

        # Ensure output directory exists
        self.yaml_output.parent.mkdir(parents=True, exist_ok=True)

        with open(self.yaml_output, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"  -> {self.yaml_output}")

        print("Generating Markdown output...")
        md_content = self.generate_markdown(yaml_data)

        with open(self.md_output, 'w') as f:
            f.write(md_content)
        print(f"  -> {self.md_output}")

        print("Saving historical snapshot...")
        self.save_snapshot()

        print()
        print("Generation complete!")
        print(f"  Directories: {self.stats.total_dirs + 1}")
        print(f"  Files: {self.stats.total_files}")
        print(f"  Size: {self.stats.total_size / (1024*1024):.1f} MB")

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Generate Architecture Catalog',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 tools/generate_architecture_catalog.py --force
    python3 tools/generate_architecture_catalog.py --check
        """
    )

    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force regeneration even if not stale'
    )

    parser.add_argument(
        '--check', '-c',
        action='store_true',
        help='Check if catalog is stale (exit 0 if up-to-date, 1 if stale)'
    )

    parser.add_argument(
        '--root',
        type=str,
        default=None,
        help='Root directory (default: script parent directory)'
    )

    args = parser.parse_args()

    # Determine root path
    if args.root:
        root_path = Path(args.root).resolve()
    else:
        # Assume script is in tools/ directory
        root_path = Path(__file__).resolve().parent.parent

    if not root_path.exists():
        print(f"Error: Root path does not exist: {root_path}")
        sys.exit(1)

    generator = ArchitectureCatalogGenerator(str(root_path))

    if args.check:
        if generator.is_stale():
            print("Catalog is STALE - regeneration needed")
            sys.exit(1)
        else:
            print("Catalog is UP TO DATE")
            sys.exit(0)

    success = generator.generate(force=args.force)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
