#!/usr/bin/env python3
"""
the system Template Scanner Tool

Scans and analyzes Jinja2 templates used in the system, extracting variables,
blocks, includes, and validating template syntax and structure.

Version: 1.0.0
Created: 2025-12-25
Author: Builder Agent
"""

import os
import re
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict

@dataclass
class TemplateVariable:
    """A variable used in a template."""
    name: str
    locations: List[int]  # Line numbers
    filters: List[str]
    default: Optional[str] = None
    required: bool = True

@dataclass
class TemplateBlock:
    """A block defined in a template."""
    name: str
    start_line: int
    end_line: int
    content_lines: int
    is_override: bool = False

@dataclass
class TemplateInclude:
    """An include/import in a template."""
    path: str
    line: int
    type: str  # include, import, extends, from

@dataclass
class TemplateMacro:
    """A macro defined in a template."""
    name: str
    args: List[str]
    line: int
    doc: Optional[str] = None

@dataclass
class TemplateMetadata:
    """Complete metadata for a template."""
    path: str
    name: str
    type: str  # jinja2, markdown, yaml
    syntax_valid: bool
    line_count: int
    size_bytes: int
    variables: List[TemplateVariable]
    blocks: List[TemplateBlock]
    includes: List[TemplateInclude]
    macros: List[TemplateMacro]
    regions: List[str]
    extends: Optional[str]
    errors: List[str]

@dataclass
class ScanSummary:
    """Summary of template scan."""
    timestamp: str
    root_path: str
    total_templates: int
    valid_templates: int
    invalid_templates: int
    templates_by_type: Dict[str, int]
    total_variables: int
    total_blocks: int
    total_macros: int
    unused_variables: List[str]
    undefined_variables: List[str]
    templates: List[TemplateMetadata]

class TemplateScanner:
    """Scans and analyzes Jinja2 templates."""

    # Template file extensions
    TEMPLATE_EXTENSIONS = ['.jinja2', '.j2', '.jinja', '.html.j2']

    # Jinja2 syntax patterns
    PATTERNS = {
        'variable': r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*(?:\|[^}]+)?\}\}',
        'variable_with_filter': r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*([^}]+)\}\}',
        'block_start': r'\{%\s*block\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%\}',
        'block_end': r'\{%\s*endblock\s*(?:[a-zA-Z_][a-zA-Z0-9_]*)?\s*%\}',
        'extends': r'\{%\s*extends\s+["\']([^"\']+)["\']\s*%\}',
        'include': r'\{%\s*include\s+["\']([^"\']+)["\']\s*%\}',
        'import': r'\{%\s*import\s+["\']([^"\']+)["\']\s*%\}',
        'from_import': r'\{%\s*from\s+["\']([^"\']+)["\']\s+import',
        'macro_start': r'\{%\s*macro\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*%\}',
        'macro_end': r'\{%\s*endmacro\s*%\}',
        'set_variable': r'\{%\s*set\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=',
        'for_loop': r'\{%\s*for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([^%]+)\s*%\}',
        'if_statement': r'\{%\s*if\s+([^%]+)\s*%\}',
        'comment': r'\{#.*?#\}',
        'region_start': r'#\s*(?:BEGIN|START)\s+REGION[:\s]+([^\n]+)',
        'region_end': r'#\s*(?:END)\s+REGION',
    }

    def __init__(self, root_path: str, config: Optional[Dict] = None):
        """Initialize scanner."""
        self.root_path = Path(root_path).resolve()
        self.config = config or {}
        self.templates: List[TemplateMetadata] = []
        self.all_variables: Set[str] = set()
        self.defined_variables: Set[str] = set()

    def scan(self) -> ScanSummary:
        """Scan all templates in the root path."""
        self.templates = []
        self.all_variables = set()
        self.defined_variables = set()

        # Find all template files
        template_files = self._find_templates()

        # Scan each template
        for template_path in template_files:
            try:
                metadata = self._scan_template(template_path)
                self.templates.append(metadata)

                # Track variables
                for var in metadata.variables:
                    self.all_variables.add(var.name)

            except Exception as e:
                self.templates.append(TemplateMetadata(
                    path=str(template_path.relative_to(self.root_path)),
                    name=template_path.stem,
                    type=self._get_template_type(template_path),
                    syntax_valid=False,
                    line_count=0,
                    size_bytes=0,
                    variables=[],
                    blocks=[],
                    includes=[],
                    macros=[],
                    regions=[],
                    extends=None,
                    errors=[str(e)],
                ))

        # Calculate statistics
        valid_count = sum(1 for t in self.templates if t.syntax_valid)
        invalid_count = len(self.templates) - valid_count

        templates_by_type: Dict[str, int] = {}
        total_variables = 0
        total_blocks = 0
        total_macros = 0

        for template in self.templates:
            templates_by_type[template.type] = templates_by_type.get(template.type, 0) + 1
            total_variables += len(template.variables)
            total_blocks += len(template.blocks)
            total_macros += len(template.macros)

        # Find unused and undefined variables
        unused = list(self.defined_variables - self.all_variables)
        undefined = list(self.all_variables - self.defined_variables - self._get_builtin_variables())

        return ScanSummary(
            timestamp=datetime.now().isoformat(),
            root_path=str(self.root_path),
            total_templates=len(self.templates),
            valid_templates=valid_count,
            invalid_templates=invalid_count,
            templates_by_type=templates_by_type,
            total_variables=total_variables,
            total_blocks=total_blocks,
            total_macros=total_macros,
            unused_variables=unused,
            undefined_variables=undefined[:50],  # Limit to 50
            templates=self.templates,
        )

    def _find_templates(self) -> List[Path]:
        """Find all template files."""
        templates = []

        for ext in self.TEMPLATE_EXTENSIONS:
            templates.extend(self.root_path.glob(f'**/*{ext}'))

        # Also check templates directory for non-jinja files
        templates_dir = self.root_path / 'templates'
        if templates_dir.exists():
            templates.extend(templates_dir.glob('**/*.md'))
            templates.extend(templates_dir.glob('**/*.yaml'))
            templates.extend(templates_dir.glob('**/*.yml'))

        return sorted(set(templates))

    def _get_template_type(self, path: Path) -> str:
        """Determine template type from extension."""
        suffix = path.suffix.lower()

        if suffix in ['.jinja2', '.j2', '.jinja']:
            return 'jinja2'
        elif suffix == '.md':
            return 'markdown'
        elif suffix in ['.yaml', '.yml']:
            return 'yaml'
        elif suffix == '.html':
            return 'html'
        else:
            return 'unknown'

    def _scan_template(self, path: Path) -> TemplateMetadata:
        """Scan a single template file."""
        rel_path = str(path.relative_to(self.root_path))
        stat = path.stat()

        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = path.read_text(encoding='latin-1')

        lines = content.split('\n')
        errors = []

        # Extract components
        variables = self._extract_variables(content, lines)
        blocks = self._extract_blocks(content, lines)
        includes = self._extract_includes(content, lines)
        macros = self._extract_macros(content, lines)
        regions = self._extract_regions(content)
        extends = self._extract_extends(content)

        # Validate syntax
        syntax_valid, syntax_errors = self._validate_syntax(content)
        errors.extend(syntax_errors)

        return TemplateMetadata(
            path=rel_path,
            name=path.stem,
            type=self._get_template_type(path),
            syntax_valid=syntax_valid,
            line_count=len(lines),
            size_bytes=stat.st_size,
            variables=variables,
            blocks=blocks,
            includes=includes,
            macros=macros,
            regions=regions,
            extends=extends,
            errors=errors,
        )

    def _extract_variables(self, content: str, lines: List[str]) -> List[TemplateVariable]:
        """Extract all variables from template."""
        variables: Dict[str, TemplateVariable] = {}

        for line_num, line in enumerate(lines, 1):
            # Find all variable usages
            for match in re.finditer(self.PATTERNS['variable'], line):
                var_name = match.group(1).split('.')[0]  # Get root variable

                if var_name in variables:
                    variables[var_name].locations.append(line_num)
                else:
                    variables[var_name] = TemplateVariable(
                        name=var_name,
                        locations=[line_num],
                        filters=[],
                    )

            # Find variables with filters
            for match in re.finditer(self.PATTERNS['variable_with_filter'], line):
                var_name = match.group(1)
                filter_str = match.group(2)

                if var_name in variables:
                    # Parse filters
                    filters = [f.strip().split('(')[0] for f in filter_str.split('|')]
                    variables[var_name].filters.extend(filters)

            # Find set statements (defined variables)
            for match in re.finditer(self.PATTERNS['set_variable'], line):
                var_name = match.group(1)
                self.defined_variables.add(var_name)

            # Find for loop variables
            for match in re.finditer(self.PATTERNS['for_loop'], line):
                loop_var = match.group(1)
                self.defined_variables.add(loop_var)

        return list(variables.values())

    def _extract_blocks(self, content: str, lines: List[str]) -> List[TemplateBlock]:
        """Extract all blocks from template."""
        blocks = []
        block_stack: List[Tuple[str, int]] = []

        for line_num, line in enumerate(lines, 1):
            # Find block starts
            for match in re.finditer(self.PATTERNS['block_start'], line):
                block_name = match.group(1)
                block_stack.append((block_name, line_num))

            # Find block ends
            for match in re.finditer(self.PATTERNS['block_end'], line):
                if block_stack:
                    block_name, start_line = block_stack.pop()
                    blocks.append(TemplateBlock(
                        name=block_name,
                        start_line=start_line,
                        end_line=line_num,
                        content_lines=line_num - start_line - 1,
                    ))

        return blocks

    def _extract_includes(self, content: str, lines: List[str]) -> List[TemplateInclude]:
        """Extract all includes from template."""
        includes = []

        for line_num, line in enumerate(lines, 1):
            # Include
            for match in re.finditer(self.PATTERNS['include'], line):
                includes.append(TemplateInclude(
                    path=match.group(1),
                    line=line_num,
                    type='include',
                ))

            # Import
            for match in re.finditer(self.PATTERNS['import'], line):
                includes.append(TemplateInclude(
                    path=match.group(1),
                    line=line_num,
                    type='import',
                ))

            # From import
            for match in re.finditer(self.PATTERNS['from_import'], line):
                includes.append(TemplateInclude(
                    path=match.group(1),
                    line=line_num,
                    type='from',
                ))

        return includes

    def _extract_macros(self, content: str, lines: List[str]) -> List[TemplateMacro]:
        """Extract all macros from template."""
        macros = []

        for line_num, line in enumerate(lines, 1):
            for match in re.finditer(self.PATTERNS['macro_start'], line):
                macro_name = match.group(1)
                args_str = match.group(2)
                args = [a.strip().split('=')[0] for a in args_str.split(',') if a.strip()]

                # Look for docstring in next line
                doc = None
                if line_num < len(lines):
                    next_line = lines[line_num]
                    doc_match = re.search(r'\{#\s*(.+?)\s*#\}', next_line)
                    if doc_match:
                        doc = doc_match.group(1)

                macros.append(TemplateMacro(
                    name=macro_name,
                    args=args,
                    line=line_num,
                    doc=doc,
                ))

        return macros

    def _extract_regions(self, content: str) -> List[str]:
        """Extract protected regions."""
        regions = []

        for match in re.finditer(self.PATTERNS['region_start'], content):
            regions.append(match.group(1).strip())

        return regions

    def _extract_extends(self, content: str) -> Optional[str]:
        """Extract parent template (extends)."""
        match = re.search(self.PATTERNS['extends'], content)
        return match.group(1) if match else None

    def _validate_syntax(self, content: str) -> Tuple[bool, List[str]]:
        """Validate template syntax."""
        errors = []

        # Check for balanced braces
        open_tags = len(re.findall(r'\{%', content))
        close_tags = len(re.findall(r'%\}', content))
        if open_tags != close_tags:
            errors.append(f"Unbalanced template tags: {open_tags} open, {close_tags} close")

        open_vars = len(re.findall(r'\{\{', content))
        close_vars = len(re.findall(r'\}\}', content))
        if open_vars != close_vars:
            errors.append(f"Unbalanced variable braces: {open_vars} open, {close_vars} close")

        # Check for balanced blocks
        block_starts = len(re.findall(r'\{%\s*block\s+', content))
        block_ends = len(re.findall(r'\{%\s*endblock', content))
        if block_starts != block_ends:
            errors.append(f"Unbalanced blocks: {block_starts} starts, {block_ends} ends")

        # Check for balanced for loops
        for_starts = len(re.findall(r'\{%\s*for\s+', content))
        for_ends = len(re.findall(r'\{%\s*endfor', content))
        if for_starts != for_ends:
            errors.append(f"Unbalanced for loops: {for_starts} starts, {for_ends} ends")

        # Check for balanced if statements
        if_starts = len(re.findall(r'\{%\s*if\s+', content))
        if_ends = len(re.findall(r'\{%\s*endif', content))
        if if_starts != if_ends:
            errors.append(f"Unbalanced if statements: {if_starts} starts, {if_ends} ends")

        # Check for balanced macros
        macro_starts = len(re.findall(r'\{%\s*macro\s+', content))
        macro_ends = len(re.findall(r'\{%\s*endmacro', content))
        if macro_starts != macro_ends:
            errors.append(f"Unbalanced macros: {macro_starts} starts, {macro_ends} ends")

        return len(errors) == 0, errors

    def _get_builtin_variables(self) -> Set[str]:
        """Get set of built-in Jinja2 variables."""
        return {
            'loop', 'self', 'super', 'varargs', 'kwargs',
            'true', 'false', 'none', 'True', 'False', 'None',
        }

def format_output(summary: ScanSummary, format: str) -> str:
    """Format scan summary for output."""
    if format == 'json':
        return json.dumps(asdict(summary), indent=2, default=str)

    elif format == 'table':
        lines = [
            f"{'Path':<50} {'Type':<10} {'Valid':<6} {'Vars':<5} {'Blocks':<6}",
            "-" * 80,
        ]
        for t in summary.templates:
            valid_str = "Yes" if t.syntax_valid else "No"
            lines.append(f"{t.path[:48]:<50} {t.type:<10} {valid_str:<6} {len(t.variables):<5} {len(t.blocks):<6}")
        return '\n'.join(lines)

    else:  # summary
        lines = [
            "=" * 60,
            "the system Template Scan Results",
            "=" * 60,
            f"Timestamp:        {summary.timestamp}",
            f"Root Path:        {summary.root_path}",
            f"Total Templates:  {summary.total_templates}",
            f"Valid:            {summary.valid_templates}",
            f"Invalid:          {summary.invalid_templates}",
            "",
            "By Type:",
        ]
        for t, count in sorted(summary.templates_by_type.items()):
            lines.append(f"  {t:<15} {count:>5}")

        lines.extend([
            "",
            f"Total Variables:  {summary.total_variables}",
            f"Total Blocks:     {summary.total_blocks}",
            f"Total Macros:     {summary.total_macros}",
        ])

        if summary.undefined_variables:
            lines.append(f"\nPossibly Undefined Variables ({len(summary.undefined_variables)}):")
            for var in summary.undefined_variables[:10]:
                lines.append(f"  - {var}")

        if summary.unused_variables:
            lines.append(f"\nPossibly Unused Variables ({len(summary.unused_variables)}):")
            for var in summary.unused_variables[:10]:
                lines.append(f"  - {var}")

        # Show templates with errors
        error_templates = [t for t in summary.templates if t.errors]
        if error_templates:
            lines.append(f"\nTemplates with Errors ({len(error_templates)}):")
            for t in error_templates[:5]:
                lines.append(f"  {t.path}:")
                for err in t.errors[:3]:
                    lines.append(f"    - {err}")

        return '\n'.join(lines)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='the system Template Scanner - Analyze Jinja2 templates'
    )
    parser.add_argument(
        'root',
        nargs='?',
        default='.',
        help='Root directory to scan (default: current directory)'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'summary', 'table'],
        default='summary',
        help='Output format (default: summary)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file (default: stdout)'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate templates, exit with error if any invalid'
    )

    args = parser.parse_args()

    scanner = TemplateScanner(args.root)
    summary = scanner.scan()

    output = format_output(summary, args.format)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results saved to {args.output}")
    else:
        print(output)

    if args.validate_only and summary.invalid_templates > 0:
        print(f"\nValidation failed: {summary.invalid_templates} invalid templates")
        exit(1)

if __name__ == '__main__':
    main()
