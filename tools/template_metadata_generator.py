#!/usr/bin/env python3
"""
Template Metadata Generator - Automated template.yaml Creation

Generates or updates template metadata files (template.yaml) for the system templates.
Automates the creation of metadata ensuring all required fields are populated
and formatted correctly.

Usage:
    python3 tools/template_metadata_generator.py <template-dir>
    python3 tools/template_metadata_generator.py --all
    python3 tools/template_metadata_generator.py templates/django-api/
    python3 tools/template_metadata_generator.py <dir> --update
    python3 tools/template_metadata_generator.py --validate <template-dir>

Exit Codes:
    0 - Success
    1 - Validation failed
    2 - Error (missing directory, invalid structure, etc.)

Referenced in:
    - TEMPLATE_VERSIONING_AND_DEPRECATION_POLICY.md:2230

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class TemplateVariable:
    """Template variable definition"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Optional[Any] = None
    choices: Optional[List[str]] = None

@dataclass
class TemplateMetadata:
    """Complete template metadata structure"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "the system Team"
    created: str = ""
    last_modified: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    status: str = "active"
    dependencies: Dict[str, str] = field(default_factory=dict)
    variables: List[Dict[str, Any]] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    hooks: Dict[str, str] = field(default_factory=dict)
    compatibility: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML output"""
        result = {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'created': self.created,
            'last_modified': self.last_modified,
            'category': self.category,
            'status': self.status,
        }

        if self.tags:
            result['tags'] = self.tags
        if self.dependencies:
            result['dependencies'] = self.dependencies
        if self.variables:
            result['variables'] = self.variables
        if self.files:
            result['files'] = self.files
        if self.outputs:
            result['outputs'] = self.outputs
        if self.hooks:
            result['hooks'] = self.hooks
        if self.compatibility:
            result['compatibility'] = self.compatibility

        return result

class TemplateMetadataGenerator:
    """Generator for template metadata files"""

    # Common template categories
    CATEGORIES = {
        'backend': ['api', 'server', 'service', 'rest', 'graphql'],
        'frontend': ['ui', 'web', 'react', 'vue', 'angular', 'component'],
        'fullstack': ['app', 'application', 'project'],
        'cli': ['command', 'cli', 'tool', 'utility'],
        'library': ['lib', 'package', 'module'],
        'config': ['config', 'configuration', 'settings'],
        'infrastructure': ['docker', 'k8s', 'kubernetes', 'terraform', 'deploy'],
        'data': ['database', 'db', 'migration', 'model'],
        'test': ['test', 'spec', 'e2e', 'unit', 'integration'],
    }

    # File extensions to language/framework mapping
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript-react',
        '.jsx': 'javascript-react',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.cs': 'csharp',
        '.swift': 'swift',
        '.kt': 'kotlin',
    }

    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        'django': [r'django', r'from django', r'settings\.py'],
        'flask': [r'from flask', r'Flask\('],
        'fastapi': [r'from fastapi', r'FastAPI\('],
        'react': [r'from [\'"]react[\'"]', r'React\.Component'],
        'vue': [r'from [\'"]vue[\'"]', r'Vue\.component'],
        'express': [r'require\([\'"]express[\'"]', r'express\(\)'],
        'rails': [r'Rails\.application', r'class.*<.*ApplicationController'],
        'spring': [r'@SpringBootApplication', r'org\.springframework'],
    }

    def __init__(self, template_dir: Path, verbose: bool = False):
        self.template_dir = template_dir
        self.verbose = verbose
        self.existing_metadata = None

    def log(self, message: str):
        """Log message if verbose mode enabled"""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def load_existing_metadata(self) -> Optional[TemplateMetadata]:
        """Load existing template.yaml if present"""
        metadata_file = self.template_dir / 'template.yaml'
        if not metadata_file.exists():
            metadata_file = self.template_dir / 'template.yml'

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, 'r') as f:
                data = yaml.safe_load(f)

            if not data:
                return None

            self.existing_metadata = data
            return self._dict_to_metadata(data)
        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse existing metadata: {e}")
            return None

    def _dict_to_metadata(self, data: Dict[str, Any]) -> TemplateMetadata:
        """Convert dictionary to TemplateMetadata"""
        return TemplateMetadata(
            name=data.get('name', ''),
            version=data.get('version', '1.0.0'),
            description=data.get('description', ''),
            author=data.get('author', 'the system Team'),
            created=data.get('created', ''),
            last_modified=data.get('last_modified', ''),
            category=data.get('category', 'general'),
            tags=data.get('tags', []),
            status=data.get('status', 'active'),
            dependencies=data.get('dependencies', {}),
            variables=data.get('variables', []),
            files=data.get('files', []),
            outputs=data.get('outputs', []),
            hooks=data.get('hooks', {}),
            compatibility=data.get('compatibility', {}),
        )

    def infer_name(self) -> str:
        """Infer template name from directory"""
        return self.template_dir.name.replace('_', '-').lower()

    def infer_description(self) -> str:
        """Infer description from README or directory name"""
        # Try README
        for readme_name in ['README.md', 'README.txt', 'README']:
            readme_path = self.template_dir / readme_name
            if readme_path.exists():
                content = readme_path.read_text()
                # Extract first paragraph
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    # Skip headers and empty lines
                    if line and not line.startswith('#') and not line.startswith('```'):
                        # Clean markdown formatting
                        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
                        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean)
                        clean = re.sub(r'\*([^*]+)\*', r'\1', clean)
                        if len(clean) > 20:  # Meaningful description
                            return clean[:200] if len(clean) > 200 else clean

        # Fallback to directory name
        name = self.template_dir.name.replace('_', ' ').replace('-', ' ')
        return f"Template for {name}"

    def infer_category(self) -> str:
        """Infer template category from content"""
        name_lower = self.template_dir.name.lower()

        for category, keywords in self.CATEGORIES.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return category

        # Check file content for clues
        detected_frameworks = self.detect_frameworks()
        if 'django' in detected_frameworks or 'flask' in detected_frameworks or 'fastapi' in detected_frameworks:
            return 'backend'
        if 'react' in detected_frameworks or 'vue' in detected_frameworks:
            return 'frontend'

        return 'general'

    def infer_tags(self) -> List[str]:
        """Infer tags from template content"""
        tags: Set[str] = set()

        # From directory name
        name_parts = re.split(r'[-_]', self.template_dir.name.lower())
        for part in name_parts:
            if len(part) > 2:
                tags.add(part)

        # From file extensions
        for ext, lang in self.EXTENSION_MAP.items():
            if list(self.template_dir.rglob(f'*{ext}')):
                tags.add(lang)

        # From detected frameworks
        tags.update(self.detect_frameworks())

        # Limit and sort
        return sorted(list(tags))[:10]

    def detect_frameworks(self) -> Set[str]:
        """Detect frameworks used in template"""
        frameworks: Set[str] = set()

        # Check common files
        for pattern_file in self.template_dir.rglob('*'):
            if pattern_file.is_file() and pattern_file.suffix in ['.py', '.js', '.ts', '.rb', '.java']:
                try:
                    content = pattern_file.read_text(errors='ignore')
                    for framework, patterns in self.FRAMEWORK_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, content):
                                frameworks.add(framework)
                                break
                except:
                    pass

        return frameworks

    def detect_dependencies(self) -> Dict[str, str]:
        """Detect dependencies from package files"""
        deps: Dict[str, str] = {}

        # Python requirements
        for req_file in ['requirements.txt', 'requirements-dev.txt', 'setup.py', 'pyproject.toml']:
            req_path = self.template_dir / req_file
            if req_path.exists():
                content = req_path.read_text()
                if req_file == 'requirements.txt':
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse package==version or package>=version
                            match = re.match(r'^([a-zA-Z0-9_-]+)([<>=!]+)?(.+)?', line)
                            if match:
                                pkg = match.group(1)
                                ver = match.group(3) if match.group(3) else '*'
                                deps[pkg] = ver.strip()

        # Node package.json
        pkg_json = self.template_dir / 'package.json'
        if pkg_json.exists():
            try:
                import json
                data = json.loads(pkg_json.read_text())
                for key in ['dependencies', 'devDependencies']:
                    if key in data:
                        deps.update(data[key])
            except:
                pass

        return deps

    def detect_variables(self) -> List[Dict[str, Any]]:
        """Detect template variables from file content"""
        variables: Dict[str, Dict[str, Any]] = {}

        # Common variable patterns
        patterns = [
            r'\{\{\s*(\w+)\s*\}\}',  # Jinja2 {{ variable }}
            r'\$\{(\w+)\}',          # Shell ${VARIABLE}
            r'<%= (\w+) %>',         # ERB <%= variable %>
            r'\{\{>\s*(\w+)\s*\}\}', # Mustache {{> partial}}
        ]

        for template_file in self.template_dir.rglob('*'):
            if template_file.is_file():
                # Skip binary and large files
                if template_file.suffix in ['.png', '.jpg', '.gif', '.ico', '.woff', '.woff2']:
                    continue
                if template_file.stat().st_size > 100000:  # 100KB limit
                    continue

                try:
                    content = template_file.read_text(errors='ignore')
                    for pattern in patterns:
                        matches = re.findall(pattern, content)
                        for var_name in matches:
                            if var_name not in variables:
                                variables[var_name] = {
                                    'name': var_name,
                                    'type': self._infer_variable_type(var_name),
                                    'description': self._infer_variable_description(var_name),
                                    'required': self._is_likely_required(var_name),
                                }
                except:
                    pass

        return list(variables.values())

    def _infer_variable_type(self, var_name: str) -> str:
        """Infer variable type from name"""
        name_lower = var_name.lower()

        if any(x in name_lower for x in ['port', 'count', 'size', 'limit', 'timeout', 'retries']):
            return 'integer'
        if any(x in name_lower for x in ['enabled', 'disabled', 'debug', 'verbose', 'is_', 'has_']):
            return 'boolean'
        if any(x in name_lower for x in ['list', 'items', 'array', 'tags']):
            return 'list'
        if any(x in name_lower for x in ['config', 'options', 'settings', 'metadata']):
            return 'object'

        return 'string'

    def _infer_variable_description(self, var_name: str) -> str:
        """Generate description from variable name"""
        # Convert snake_case/camelCase to words
        words = re.sub(r'([A-Z])', r' \1', var_name)
        words = words.replace('_', ' ').strip().lower()
        return f"The {words}"

    def _is_likely_required(self, var_name: str) -> bool:
        """Determine if variable is likely required"""
        required_patterns = ['name', 'app', 'project', 'host', 'database', 'db_name']
        name_lower = var_name.lower()
        return any(p in name_lower for p in required_patterns)

    def list_template_files(self) -> List[str]:
        """List all template files relative to template directory"""
        files: List[str] = []

        for file_path in sorted(self.template_dir.rglob('*')):
            if file_path.is_file():
                # Skip hidden files and metadata
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                if file_path.name in ['template.yaml', 'template.yml', 'metadata.yaml']:
                    continue

                relative = file_path.relative_to(self.template_dir)
                files.append(str(relative))

        return files

    def generate(self, update: bool = False) -> TemplateMetadata:
        """Generate template metadata"""
        today = datetime.now().strftime('%Y-%m-%d')

        # Load existing if updating
        existing = None
        if update:
            existing = self.load_existing_metadata()

        # Generate new metadata
        metadata = TemplateMetadata(
            name=existing.name if existing and existing.name else self.infer_name(),
            version=existing.version if existing else '1.0.0',
            description=existing.description if existing and existing.description else self.infer_description(),
            author=existing.author if existing else 'the system Team',
            created=existing.created if existing and existing.created else today,
            last_modified=today,
            category=existing.category if existing else self.infer_category(),
            tags=existing.tags if existing and existing.tags else self.infer_tags(),
            status=existing.status if existing else 'active',
            dependencies=existing.dependencies if existing else self.detect_dependencies(),
            variables=existing.variables if existing else self.detect_variables(),
            files=self.list_template_files(),  # Always refresh file list
            outputs=existing.outputs if existing else [],
            hooks=existing.hooks if existing else {},
            compatibility=existing.compatibility if existing else {},
        )

        return metadata

    def save(self, metadata: TemplateMetadata, output_file: Optional[Path] = None) -> Path:
        """Save metadata to file"""
        if output_file is None:
            output_file = self.template_dir / 'template.yaml'

        data = metadata.to_dict()

        with open(output_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        return output_file

    def validate(self, metadata: TemplateMetadata) -> List[str]:
        """Validate metadata completeness"""
        errors: List[str] = []

        # Required fields
        if not metadata.name:
            errors.append("Missing required field: name")
        if not metadata.version:
            errors.append("Missing required field: version")
        if not metadata.description:
            errors.append("Missing required field: description")

        # Version format
        if metadata.version and not re.match(r'^\d+\.\d+\.\d+', metadata.version):
            errors.append(f"Invalid version format: {metadata.version} (expected semver)")

        # Category validation
        valid_categories = list(self.CATEGORIES.keys()) + ['general']
        if metadata.category not in valid_categories:
            errors.append(f"Invalid category: {metadata.category} (expected one of: {valid_categories})")

        # Status validation
        valid_statuses = ['active', 'deprecated', 'experimental', 'draft', 'archived']
        if metadata.status not in valid_statuses:
            errors.append(f"Invalid status: {metadata.status} (expected one of: {valid_statuses})")

        # Date format
        date_pattern = r'^\d{4}-\d{2}-\d{2}'
        if metadata.created and not re.match(date_pattern, metadata.created):
            errors.append(f"Invalid created date format: {metadata.created}")
        if metadata.last_modified and not re.match(date_pattern, metadata.last_modified):
            errors.append(f"Invalid last_modified date format: {metadata.last_modified}")

        # Variable validation
        for i, var in enumerate(metadata.variables):
            if not isinstance(var, dict):
                errors.append(f"Variable {i}: must be a dictionary")
                continue
            if 'name' not in var:
                errors.append(f"Variable {i}: missing 'name' field")
            if 'type' not in var:
                errors.append(f"Variable {var.get('name', i)}: missing 'type' field")

        # Files validation - check if listed files exist
        for file_path in metadata.files[:5]:  # Check first 5
            full_path = self.template_dir / file_path
            if not full_path.exists():
                errors.append(f"Listed file does not exist: {file_path}")

        return errors

def process_template(template_dir: Path, update: bool = False,
                     validate_only: bool = False, verbose: bool = False) -> bool:
    """Process a single template directory"""
    generator = TemplateMetadataGenerator(template_dir, verbose=verbose)

    if validate_only:
        existing = generator.load_existing_metadata()
        if not existing:
            print(f"  ❌ No metadata found: {template_dir}")
            return False

        errors = generator.validate(existing)
        if errors:
            print(f"  ❌ Validation failed: {template_dir}")
            for error in errors:
                print(f"    - {error}")
            return False
        else:
            print(f"  ✅ Valid: {template_dir}")
            return True

    # Generate metadata
    metadata = generator.generate(update=update)

    # Validate
    errors = generator.validate(metadata)
    if errors:
        print(f"  ⚠️  Generated with warnings: {template_dir}")
        for error in errors:
            print(f"    - {error}")

    # Save
    output_file = generator.save(metadata)
    print(f"  ✅ Generated: {output_file}")

    return True

def find_templates(base_dir: Path) -> List[Path]:
    """Find all template directories"""
    templates: List[Path] = []

    # Look for directories that look like templates
    # Heuristics: contain template files, have certain structure

    # Check templates/ directory
    templates_dir = base_dir / 'templates'
    if templates_dir.exists():
        for subdir in templates_dir.iterdir():
            if subdir.is_dir() and not subdir.name.startswith('.'):
                templates.append(subdir)

    # Check .task/templates/
    task_templates = base_dir / '.task' / 'templates'
    if task_templates.exists():
        for subdir in task_templates.iterdir():
            if subdir.is_dir() and not subdir.name.startswith('.'):
                templates.append(subdir)

    # If no templates directory, check if base_dir itself is a template
    if not templates:
        # Look for template indicators
        indicators = [
            base_dir / 'template.yaml',
            base_dir / 'template.yml',
            base_dir / 'wiring.yaml',
        ]
        template_patterns = list(base_dir.glob('*.j2')) + list(base_dir.glob('*.jinja2'))

        if any(i.exists() for i in indicators) or template_patterns:
            templates.append(base_dir)

    return templates

def main():
    parser = argparse.ArgumentParser(
        description='Generate or update template metadata files (template.yaml)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s templates/django-api/
    %(prog)s --all
    %(prog)s templates/react-app/ --update
    %(prog)s --validate templates/my-template/

Output:
    Creates template.yaml with inferred metadata including:
    - name, version, description, author
    - category, tags, status
    - dependencies (from requirements.txt, package.json)
    - variables (detected from template syntax)
    - file listing
        """
    )

    parser.add_argument('template_dir', type=Path, nargs='?',
                        help='Template directory to process')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Process all templates in templates/ directory')
    parser.add_argument('--update', '-u', action='store_true',
                        help='Update existing metadata (preserve manual edits)')
    parser.add_argument('--validate', '-V', action='store_true',
                        help='Validate metadata only, do not generate')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output file path (default: template.yaml in template dir)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be generated without saving')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON instead of YAML')

    args = parser.parse_args()

    # Determine templates to process
    if args.all:
        base_dir = Path.cwd()
        templates = find_templates(base_dir)
        if not templates:
            print("No templates found in templates/ directory")
            sys.exit(2)
        print(f"Found {len(templates)} templates")
    elif args.template_dir:
        if not args.template_dir.exists():
            print(f"Error: Directory not found: {args.template_dir}", file=sys.stderr)
            sys.exit(2)
        if not args.template_dir.is_dir():
            print(f"Error: Not a directory: {args.template_dir}", file=sys.stderr)
            sys.exit(2)
        templates = [args.template_dir]
    else:
        parser.print_help()
        sys.exit(2)

    # Process templates
    success_count = 0
    fail_count = 0

    for template_dir in templates:
        print(f"\nProcessing: {template_dir}")

        if args.dry_run:
            generator = TemplateMetadataGenerator(template_dir, verbose=args.verbose)
            metadata = generator.generate(update=args.update)

            if args.json:
                import json
                print(json.dumps(metadata.to_dict(), indent=2))
            else:
                print("--- Generated metadata (dry-run) ---")
                print(yaml.dump(metadata.to_dict(), default_flow_style=False, sort_keys=False))
            success_count += 1
            continue

        success = process_template(
            template_dir,
            update=args.update,
            validate_only=args.validate,
            verbose=args.verbose
        )

        if success:
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print(f"\n{'='*40}")
    print(f"Processed: {success_count + fail_count} templates")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")

    sys.exit(0 if fail_count == 0 else 1)

if __name__ == '__main__':
    main()
