"""
the system Traceability Checker

Enforces traceability by construction rules:
- Verify the system headers present
- Verify manifests complete
- Validate spec references
- Check approval status
- Verify lineage chains

Usage:
    python tools/traceability_checker.py --check-headers
    python tools/traceability_checker.py --verify-manifests
    python tools/traceability_checker.py --validate-specs
    python tools/traceability_checker.py --check-approvals
    python tools/traceability_checker.py --verify-lineage
    python tools/traceability_checker.py --all
    python tools/traceability_checker.py --task <task_id> [--check]
"""

import os
import sys
import yaml
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any

class TraceabilityChecker:
    """Enforce traceability by construction."""

    REQUIRED_TAGS = [
        'task-id',
        'template',
        'spec-ref',
        'generated-at',
        'critic'
    ]

    OPTIONAL_TAGS = [
        'task-name',
        'task-version',
        'template-commit',
        'spec-commit',
        'generator',
        'parameter-pack',
        'variants',
        'critic-commit',
        'approved-at',
        'derived-from',
        'derived-relationship',
        'promoted-to',
        'promoted-at'
    ]

    # Default file extensions to search
    DEFAULT_EXTENSIONS = ['.py', '.ts', '.js', '.jsx', '.tsx', '.java',
                          '.go', '.rs', '.cpp', '.c', '.h']

    # Default directories to search
    DEFAULT_SEARCH_DIRS = ['src', 'lib', 'app', 'services']

    def __init__(self, root_path: str = '.', extensions: list = None, search_dirs: list = None):
        """Initialize checker with project root path.

        Args:
            root_path: Project root directory
            extensions: List of file extensions to search (e.g., ['.py', '.ts'])
            search_dirs: List of directories to search (e.g., ['src', 'lib'])
        """
        self.root = Path(root_path)
        self.extensions = extensions or self.DEFAULT_EXTENSIONS
        self.search_dirs = search_dirs or self.DEFAULT_SEARCH_DIRS

    def check_headers(self, files: List[Path] = None) -> Dict[str, Any]:
        """Verify all generated files have the system headers."""
        if files is None:
            files = self.find_generated_files()

        results = {
            'passed': [],
            'failed': [],
            'missing_tags': {},
            'total': len(files)
        }

        for file in files:
            header = self.extract_saf_header(file)

            if not header:
                results['failed'].append(str(file))
                results['missing_tags'][str(file)] = 'No the system header found'
                continue

            missing = []
            for tag in self.REQUIRED_TAGS:
                if tag not in header:
                    missing.append(tag)

            if missing:
                results['failed'].append(str(file))
                results['missing_tags'][str(file)] = missing
            else:
                results['passed'].append(str(file))

        return results

    def verify_manifests(self) -> Dict[str, Any]:
        """Check all tasks have complete manifests."""
        task_dirs = self.find_task_directories()

        results = {
            'passed': [],
            'failed': [],
            'issues': {},
            'total': len(task_dirs)
        }

        required_files = ['task.yaml']
        required_fields = [
            'task_id',
            'spec_ref',
            'template_refs',
            'outputs',
            'critic_verdict'
        ]

        for task_dir in task_dirs:
            task_path = task_dir / '.task'

            # Check required files exist
            missing_files = []
            for req_file in required_files:
                if not (task_path / req_file).exists():
                    missing_files.append(req_file)

            if missing_files:
                results['failed'].append(str(task_dir))
                results['issues'][str(task_dir)] = \
                    f'Missing files: {", ".join(missing_files)}'
                continue

            # Load and validate manifest
            try:
                manifest_path = task_path / 'task.yaml'
                with open(manifest_path, 'r') as f:
                    manifest = yaml.safe_load(f)

                # Check required fields
                missing_fields = [
                    f for f in required_fields
                    if f not in manifest or not manifest[f]
                ]

                if missing_fields:
                    results['failed'].append(str(task_dir))
                    results['issues'][str(task_dir)] = \
                        f'Missing fields: {", ".join(missing_fields)}'
                else:
                    results['passed'].append(str(task_dir))

            except Exception as e:
                results['failed'].append(str(task_dir))
                results['issues'][str(task_dir)] = f'Error loading manifest: {e}'

        return results

    def validate_specs(self) -> Dict[str, Any]:
        """Verify all spec references are valid."""
        manifests = self.load_all_manifests()

        results = {
            'passed': [],
            'failed': [],
            'invalid_refs': {},
            'total': len(manifests)
        }

        for manifest_path, manifest in manifests.items():
            spec_ref = manifest.get('spec_ref')

            if not spec_ref:
                results['failed'].append(manifest_path)
                results['invalid_refs'][manifest_path] = 'No spec_ref field'
                continue

            # Resolve spec path (handle absolute and relative)
            if spec_ref.startswith('/'):
                spec_path = self.root / spec_ref.lstrip('/')
            else:
                spec_path = self.root / spec_ref

            if not spec_path.exists():
                results['failed'].append(manifest_path)
                results['invalid_refs'][manifest_path] = \
                    f'Spec not found: {spec_ref}'
            else:
                results['passed'].append(manifest_path)

        return results

    def check_approvals(self) -> Dict[str, Any]:
        """Check all tasks have Critic approval."""
        manifests = self.load_all_manifests()

        results = {
            'passed': [],
            'failed': [],
            'not_approved': {},
            'total': len(manifests)
        }

        for manifest_path, manifest in manifests.items():
            verdict = manifest.get('critic_verdict')

            if verdict != 'approved':
                results['failed'].append(manifest_path)
                results['not_approved'][manifest_path] = \
                    verdict or 'No verdict'
            else:
                results['passed'].append(manifest_path)

        return results

    def verify_lineage(self) -> Dict[str, Any]:
        """Verify lineage chains are intact."""
        manifests = self.load_all_manifests()

        results = {
            'passed': [],
            'failed': [],
            'broken_chains': {},
            'total': len(manifests)
        }

        for manifest_path, manifest in manifests.items():
            derived_from = manifest.get('derived_from')

            if derived_from:
                parent_id = derived_from.get('golden_task_id')

                if not parent_id:
                    results['failed'].append(manifest_path)
                    results['broken_chains'][manifest_path] = \
                        'derived_from missing golden_task_id'
                elif not self.task_exists(parent_id):
                    results['failed'].append(manifest_path)
                    results['broken_chains'][manifest_path] = \
                        f'Parent task not found: {parent_id}'
                else:
                    results['passed'].append(manifest_path)
            else:
                # No derived_from is okay (original task)
                results['passed'].append(manifest_path)

        return results

    def extract_saf_header(self, file_path: Path) -> Dict[str, str]:
        """Extract the system provenance tags from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read first 3000 chars (enough for header)
                content = f.read(3000)

            header = {}
            # Match @saf:key=value patterns
            for match in re.finditer(r'@saf:([a-z-]+)=([^\s\n]+)', content):
                key = match.group(1)
                value = match.group(2)
                header[key] = value

            return header

        except FileNotFoundError:
            print(f"Warning: File not found: {file_path}", file=sys.stderr)
            return {}
        except PermissionError:
            print(f"Warning: Permission denied: {file_path}", file=sys.stderr)
            return {}
        except (UnicodeDecodeError, OSError) as e:
            print(f"Warning: Cannot read {file_path}: {e}", file=sys.stderr)
            return {}

    def find_generated_files(self) -> List[Path]:
        """Find all generated files in project.

        Uses self.extensions and self.search_dirs configured at init time,
        or via --extensions and --dirs CLI options.
        """
        generated = []

        for search_dir in self.search_dirs:
            dir_path = self.root / search_dir
            if not dir_path.exists():
                continue

            for root, dirs, files in os.walk(dir_path):
                # Skip node_modules, venv, etc.
                dirs[:] = [d for d in dirs if d not in
                          ['node_modules', 'venv', '__pycache__', '.git']]

                for file in files:
                    if any(file.endswith(ext) for ext in self.extensions):
                        generated.append(Path(root) / file)

        return generated

    def find_task_directories(self) -> List[Path]:
        """Find all directories containing .task/ subdirectory."""
        task_dirs = []

        for root, dirs, files in os.walk(self.root):
            # Skip hidden and irrelevant directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and
                      d not in ['node_modules', 'venv', '__pycache__']]

            if '.task' in dirs:
                task_dirs.append(Path(root))

        return task_dirs

    def load_all_manifests(self) -> Dict[str, Dict[str, Any]]:
        """Load all task manifests."""
        manifests = {}

        for task_dir in self.find_task_directories():
            manifest_path = task_dir / '.task' / 'task.yaml'

            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = yaml.safe_load(f)
                        if manifest:
                            manifests[str(manifest_path)] = manifest
                except Exception as e:
                    print(f"Warning: Could not load {manifest_path}: {e}")

        return manifests

    def task_exists(self, task_id: str) -> bool:
        """Check if task with given ID exists."""
        manifests = self.load_all_manifests()
        return any(
            m.get('task_id') == task_id
            for m in manifests.values()
        )

    def find_task_by_id(self, task_id: str) -> Tuple[Path, Dict[str, Any]]:
        """Find task directory and manifest by task ID."""
        for task_dir in self.find_task_directories():
            manifest_path = task_dir / '.task' / 'task.yaml'
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = yaml.safe_load(f)
                        if manifest and manifest.get('task_id') == task_id:
                            return task_dir, manifest
                except FileNotFoundError:
                    continue  # File was deleted after exists() check
                except PermissionError:
                    print(f"Warning: Permission denied: {manifest_path}", file=sys.stderr)
                except (yaml.YAMLError, OSError) as e:
                    print(f"Warning: Cannot load {manifest_path}: {e}", file=sys.stderr)
        return None, None

    def check_task(self, task_id: str) -> Dict[str, Any]:
        """Run all traceability checks for a specific task."""
        task_dir, manifest = self.find_task_by_id(task_id)

        results = {
            'task_id': task_id,
            'found': task_dir is not None,
            'checks': {}
        }

        if not task_dir:
            results['error'] = f"Task '{task_id}' not found"
            return results

        results['task_dir'] = str(task_dir)

        # Check manifest completeness
        manifest_check = {'passed': True, 'issues': []}
        required_fields = ['task_id', 'spec_ref', 'template_refs', 'outputs', 'critic_verdict']
        for field in required_fields:
            if field not in manifest or not manifest[field]:
                manifest_check['passed'] = False
                manifest_check['issues'].append(f"Missing field: {field}")
        results['checks']['manifest'] = manifest_check

        # Check spec reference
        spec_check = {'passed': True, 'issues': []}
        spec_ref = manifest.get('spec_ref')
        if not spec_ref:
            spec_check['passed'] = False
            spec_check['issues'].append("No spec_ref field")
        else:
            spec_path = self.root / spec_ref.lstrip('/')
            if not spec_path.exists():
                spec_check['passed'] = False
                spec_check['issues'].append(f"Spec not found: {spec_ref}")
        results['checks']['spec'] = spec_check

        # Check approval status
        approval_check = {'passed': True, 'issues': []}
        verdict = manifest.get('critic_verdict')
        if verdict != 'approved':
            approval_check['passed'] = False
            approval_check['issues'].append(f"Not approved (verdict: {verdict or 'none'})")
        results['checks']['approval'] = approval_check

        # Check lineage
        lineage_check = {'passed': True, 'issues': []}
        derived_from = manifest.get('derived_from')
        if derived_from:
            parent_id = derived_from.get('golden_task_id')
            if not parent_id:
                lineage_check['passed'] = False
                lineage_check['issues'].append("derived_from missing golden_task_id")
            elif not self.task_exists(parent_id):
                lineage_check['passed'] = False
                lineage_check['issues'].append(f"Parent task not found: {parent_id}")
        results['checks']['lineage'] = lineage_check

        # Check headers in outputs
        header_check = {'passed': True, 'issues': []}
        outputs = manifest.get('outputs', [])
        for output in outputs:
            output_path = task_dir / output
            if output_path.exists():
                header = self.extract_saf_header(output_path)
                if not header:
                    header_check['passed'] = False
                    header_check['issues'].append(f"No the system header: {output}")
                else:
                    missing_tags = [t for t in self.REQUIRED_TAGS if t not in header]
                    if missing_tags:
                        header_check['passed'] = False
                        header_check['issues'].append(f"{output} missing: {', '.join(missing_tags)}")
        results['checks']['headers'] = header_check

        # Overall result
        results['all_passed'] = all(c['passed'] for c in results['checks'].values())

        return results

    def run_all_checks(self) -> Dict[str, Dict[str, Any]]:
        """Run all traceability checks."""
        return {
            'headers': self.check_headers(),
            'manifests': self.verify_manifests(),
            'specs': self.validate_specs(),
            'approvals': self.check_approvals(),
            'lineage': self.verify_lineage()
        }

def print_results(name: str, results: Dict[str, Any]) -> bool:
    """Print check results and return True if passed."""
    total = results.get('total', 0)
    passed = len(results.get('passed', []))
    failed = len(results.get('failed', []))

    print(f"\n{name}:")
    print(f"  Total: {total}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")

    if failed > 0:
        print(f"\n  Failed items:")

        # Print specific failure details
        if 'missing_tags' in results:
            for item, tags in results['missing_tags'].items():
                print(f"    ❌ {item}")
                if isinstance(tags, list):
                    print(f"       Missing tags: {', '.join(tags)}")
                else:
                    print(f"       {tags}")

        elif 'issues' in results:
            for item, issue in results['issues'].items():
                print(f"    ❌ {item}")
                print(f"       {issue}")

        elif 'invalid_refs' in results:
            for item, reason in results['invalid_refs'].items():
                print(f"    ❌ {item}")
                print(f"       {reason}")

        elif 'not_approved' in results:
            for item, verdict in results['not_approved'].items():
                print(f"    ❌ {item}")
                print(f"       Verdict: {verdict}")

        elif 'broken_chains' in results:
            for item, reason in results['broken_chains'].items():
                print(f"    ❌ {item}")
                print(f"       {reason}")

        return False

    return True

def print_task_results(results: Dict[str, Any]) -> bool:
    """Print task-specific check results."""
    task_id = results.get('task_id')

    print(f"\n{'=' * 60}")
    print(f"Traceability Check for Task: {task_id}")
    print(f"{'=' * 60}")

    if not results.get('found'):
        print(f"\n❌ Error: {results.get('error', 'Task not found')}")
        return False

    print(f"Location: {results.get('task_dir')}")

    all_passed = True
    for check_name, check_result in results.get('checks', {}).items():
        passed = check_result.get('passed', False)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{check_name.title()}: {status}")

        if not passed:
            all_passed = False
            for issue in check_result.get('issues', []):
                print(f"  - {issue}")

    print(f"\n{'=' * 60}")
    if all_passed:
        print(f"✅ All traceability checks PASSED for {task_id}")
    else:
        print(f"❌ Some traceability checks FAILED for {task_id}")
    print(f"{'=' * 60}")

    return all_passed

def main():
    """Run traceability checks based on command-line arguments."""
    # Parse optional configuration
    extensions = None
    search_dirs = None

    if '--extensions' in sys.argv:
        try:
            ext_idx = sys.argv.index('--extensions')
            ext_str = sys.argv[ext_idx + 1]
            extensions = [e.strip() if e.startswith('.') else f'.{e.strip()}'
                         for e in ext_str.split(',')]
        except (IndexError, ValueError):
            print("Error: --extensions requires comma-separated list (e.g., --extensions .py,.ts,.go)")
            sys.exit(1)

    if '--dirs' in sys.argv:
        try:
            dirs_idx = sys.argv.index('--dirs')
            dirs_str = sys.argv[dirs_idx + 1]
            search_dirs = [d.strip() for d in dirs_str.split(',')]
        except (IndexError, ValueError):
            print("Error: --dirs requires comma-separated list (e.g., --dirs src,lib,cmd)")
            sys.exit(1)

    checker = TraceabilityChecker(extensions=extensions, search_dirs=search_dirs)

    # Handle --task option
    if '--task' in sys.argv:
        try:
            task_idx = sys.argv.index('--task')
            task_id = sys.argv[task_idx + 1]
        except (IndexError, ValueError):
            print("Error: --task requires a task ID argument")
            print("Usage: python tools/traceability_checker.py --task <task_id>")
            sys.exit(1)

        results = checker.check_task(task_id)
        passed = print_task_results(results)
        sys.exit(0 if passed else 1)

    if '--check-headers' in sys.argv:
        results = checker.check_headers()
        passed = print_results("Header Check", results)
        sys.exit(0 if passed else 1)

    elif '--verify-manifests' in sys.argv:
        results = checker.verify_manifests()
        passed = print_results("Manifest Verification", results)
        sys.exit(0 if passed else 1)

    elif '--validate-specs' in sys.argv:
        results = checker.validate_specs()
        passed = print_results("Spec Validation", results)
        sys.exit(0 if passed else 1)

    elif '--check-approvals' in sys.argv:
        results = checker.check_approvals()
        passed = print_results("Approval Check", results)
        sys.exit(0 if passed else 1)

    elif '--verify-lineage' in sys.argv:
        results = checker.verify_lineage()
        passed = print_results("Lineage Verification", results)
        sys.exit(0 if passed else 1)

    elif '--all' in sys.argv:
        print("=" * 60)
        print("the system Traceability Verification")
        print("=" * 60)

        all_results = checker.run_all_checks()
        all_passed = True

        for check_name, results in all_results.items():
            passed = print_results(check_name.title(), results)
            all_passed = all_passed and passed

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ All traceability checks PASSED")
            print("=" * 60)
            sys.exit(0)
        else:
            print("❌ Some traceability checks FAILED")
            print("=" * 60)
            sys.exit(1)

    else:
        print("the system Traceability Checker")
        print("\nUsage:")
        print("  --check-headers       Verify the system headers present")
        print("  --verify-manifests    Check manifest completeness")
        print("  --validate-specs      Validate spec references")
        print("  --check-approvals     Check Critic approval status")
        print("  --verify-lineage      Verify lineage chains intact")
        print("  --all                 Run all checks")
        print("  --task <task_id>    Run all checks for a specific task")
        print("\nOptions:")
        print("  --extensions <list>   File extensions to search (comma-separated)")
        print("                        Default: .py,.ts,.js,.jsx,.tsx,.java,.go,.rs,.cpp,.c,.h")
        print("  --dirs <list>         Directories to search (comma-separated)")
        print("                        Default: src,lib,app,services")
        print("\nExamples:")
        print("  python tools/traceability_checker.py --all")
        print("  python tools/traceability_checker.py --task 3.2.1")
        print("  python tools/traceability_checker.py --all --extensions .py,.rb,.go")
        print("  python tools/traceability_checker.py --all --dirs cmd,pkg,internal")
        sys.exit(1)

if __name__ == '__main__':
    main()
