#!/usr/bin/env python3
"""
Causal Mapper - Map Input Parameters to Output Files

Traces the causal chain from input parameters through templates to output files.
Enables traceability: "If I change this input, which files will be regenerated?"

Usage:
    # Build causal map from SSOT
    python3 tools/causal_mapper.py .task/wiring.yaml

    # Query which files are affected by a parameter
    python3 tools/causal_mapper.py .task/wiring.yaml --param entity_name

    # Output as JSON
    python3 tools/causal_mapper.py .task/wiring.yaml --json

    # Include template analysis
    python3 tools/causal_mapper.py .task/wiring.yaml --templates templates/

    # Generate visual graph (DOT format)
    python3 tools/causal_mapper.py .task/wiring.yaml --dot

Exit Codes:
    0 - Success
    1 - Parameter not found or no dependencies
    2 - Error (missing files, invalid YAML, etc.)

Referenced in:
    - SPEC_TO_DIFF_PREVIEWS_POLICY.md:1137, 1547

Author: System
Created: 2025-12-23
"""

import argparse
import sys
import os
import re
import yaml
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict

@dataclass
class TemplateInfo:
    """Information about a template"""
    name: str
    path: str
    parameters: Set[str] = field(default_factory=set)
    outputs: List[str] = field(default_factory=list)

@dataclass
class CausalLink:
    """A causal link from parameter to output"""
    parameter: str
    template: str
    output_file: str
    dependency_type: str = "direct"  # direct, indirect, conditional

@dataclass
class CausalMap:
    """Complete causal dependency map"""
    task_id: str
    task_name: str
    generated_at: str
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    templates: Dict[str, TemplateInfo] = field(default_factory=dict)
    links: List[CausalLink] = field(default_factory=list)
    output_files: List[str] = field(default_factory=list)

    # Derived indexes
    param_to_outputs: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    output_to_params: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    param_to_templates: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

class CausalMapper:
    """Maps input parameters to output files through templates"""

    # Pattern for template variable references
    VARIABLE_PATTERN = re.compile(r'\{\{([A-Z][A-Z0-9_]*)\}\}')

    # Pattern for conditional blocks
    CONDITIONAL_PATTERN = re.compile(r'\{%\s*if\s+([A-Z][A-Z0-9_]*)')

    # Pattern for loop blocks
    LOOP_PATTERN = re.compile(r'\{%\s*for\s+\w+\s+in\s+([A-Z][A-Z0-9_]*)')

    def __init__(self, templates_dir: Optional[Path] = None, verbose: bool = False):
        self.templates_dir = templates_dir or Path('templates')
        self.verbose = verbose

    def load_ssot(self, ssot_path: Path) -> Dict[str, Any]:
        """Load SSOT wiring file"""
        if not ssot_path.exists():
            raise FileNotFoundError(f"SSOT file not found: {ssot_path}")

        with open(ssot_path, 'r') as f:
            return yaml.safe_load(f)

    def extract_parameters_from_template(self, template_path: Path) -> Set[str]:
        """Extract all parameter references from a template file"""
        if not template_path.exists():
            return set()

        content = template_path.read_text()
        params = set()

        # Direct variable references
        params.update(self.VARIABLE_PATTERN.findall(content))

        # Conditional references
        params.update(self.CONDITIONAL_PATTERN.findall(content))

        # Loop references
        params.update(self.LOOP_PATTERN.findall(content))

        return params

    def scan_templates_directory(self) -> Dict[str, TemplateInfo]:
        """Scan templates directory and extract parameter usage"""
        templates = {}

        if not self.templates_dir.exists():
            return templates

        for template_path in self.templates_dir.rglob('*.jinja2'):
            rel_path = str(template_path.relative_to(self.templates_dir))
            params = self.extract_parameters_from_template(template_path)

            templates[rel_path] = TemplateInfo(
                name=template_path.stem,
                path=rel_path,
                parameters=params
            )

        # Also scan .template files
        for template_path in self.templates_dir.rglob('*.template'):
            rel_path = str(template_path.relative_to(self.templates_dir))
            params = self.extract_parameters_from_template(template_path)

            templates[rel_path] = TemplateInfo(
                name=template_path.stem,
                path=rel_path,
                parameters=params
            )

        return templates

    def extract_parameters_from_ssot(self, ssot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract all parameters defined in SSOT"""
        params = {}

        # From variables section
        if 'variables' in ssot:
            for name, value in ssot['variables'].items():
                params[name] = {
                    'value': value,
                    'source': 'variables',
                    'type': type(value).__name__
                }

        # From identity section
        identity = ssot.get('identity', {})
        for key in ['task_id', 'task_name', 'spec_ref', 'schema_ref']:
            if key in identity:
                param_name = key.upper()
                params[param_name] = {
                    'value': identity[key],
                    'source': 'identity',
                    'type': 'string'
                }

        # From interfaces section
        interfaces = ssot.get('interfaces', {})
        if 'api' in interfaces:
            for api in interfaces['api']:
                for key in ['method', 'path', 'request', 'response']:
                    if key in api:
                        param_name = f"API_{key.upper()}"
                        if param_name not in params:
                            params[param_name] = {
                                'value': api[key],
                                'source': 'interfaces.api',
                                'type': 'string'
                            }

        return params

    def extract_outputs_from_ssot(self, ssot: Dict[str, Any]) -> List[str]:
        """Extract all output files from SSOT wiring section"""
        outputs = []
        wiring = ssot.get('wiring', {})

        for key, value in wiring.items():
            if isinstance(value, str):
                outputs.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        outputs.append(item)
                    elif isinstance(item, dict) and 'path' in item:
                        outputs.append(item['path'])

        return outputs

    def extract_template_mappings(self, ssot: Dict[str, Any]) -> Dict[str, str]:
        """Extract template to output file mappings from SSOT"""
        mappings = {}

        # Check for explicit template mappings
        generation = ssot.get('generation', {})
        if 'templates' in generation:
            for template_spec in generation['templates']:
                if isinstance(template_spec, dict):
                    template = template_spec.get('template', '')
                    output = template_spec.get('output', '')
                    if template and output:
                        mappings[template] = output

        return mappings

    def build_causal_map(self, ssot_path: Path) -> CausalMap:
        """Build complete causal dependency map"""
        ssot = self.load_ssot(ssot_path)

        # Create causal map
        identity = ssot.get('identity', {})
        causal_map = CausalMap(
            task_id=identity.get('task_id', 'unknown'),
            task_name=identity.get('task_name', 'unknown'),
            generated_at=datetime.now().isoformat()
        )

        # Extract parameters
        causal_map.parameters = self.extract_parameters_from_ssot(ssot)

        # Extract output files
        causal_map.output_files = self.extract_outputs_from_ssot(ssot)

        # Scan templates
        causal_map.templates = self.scan_templates_directory()

        # Get template to output mappings
        template_mappings = self.extract_template_mappings(ssot)

        # Build causal links
        for template_name, template_info in causal_map.templates.items():
            output_file = template_mappings.get(template_name)

            for param in template_info.parameters:
                # Determine dependency type
                if param in causal_map.parameters:
                    dep_type = "direct"
                else:
                    dep_type = "indirect"

                link = CausalLink(
                    parameter=param,
                    template=template_name,
                    output_file=output_file or f"<from {template_name}>",
                    dependency_type=dep_type
                )
                causal_map.links.append(link)

                # Build indexes
                if output_file:
                    causal_map.param_to_outputs[param].add(output_file)
                    causal_map.output_to_params[output_file].add(param)
                causal_map.param_to_templates[param].add(template_name)

        # Also add direct links for outputs without templates
        for output in causal_map.output_files:
            if output not in causal_map.output_to_params:
                # Infer parameters from output path patterns
                for param in causal_map.parameters:
                    param_lower = param.lower()
                    if param_lower in output.lower():
                        causal_map.param_to_outputs[param].add(output)
                        causal_map.output_to_params[output].add(param)

        return causal_map

    def query_parameter_impact(self, causal_map: CausalMap, param: str) -> Dict[str, Any]:
        """Query which files are affected by a specific parameter"""
        result = {
            'parameter': param,
            'found': False,
            'affected_files': [],
            'affected_templates': [],
            'dependency_chain': []
        }

        # Check both exact match and case-insensitive
        param_upper = param.upper()
        if param_upper in causal_map.param_to_outputs:
            result['found'] = True
            result['affected_files'] = list(causal_map.param_to_outputs[param_upper])
            result['affected_templates'] = list(causal_map.param_to_templates.get(param_upper, []))

            # Build dependency chain
            for link in causal_map.links:
                if link.parameter == param_upper:
                    result['dependency_chain'].append({
                        'parameter': link.parameter,
                        'template': link.template,
                        'output': link.output_file,
                        'type': link.dependency_type
                    })

        elif param in causal_map.parameters:
            result['found'] = True
            result['affected_files'] = list(causal_map.param_to_outputs.get(param, []))
            result['affected_templates'] = list(causal_map.param_to_templates.get(param, []))

        return result

    def generate_dot_graph(self, causal_map: CausalMap) -> str:
        """Generate DOT format graph for visualization"""
        lines = [
            'digraph CausalMap {',
            '  rankdir=LR;',
            '  node [shape=box];',
            '',
            '  // Parameters (input)',
            '  subgraph cluster_params {',
            '    label="Parameters";',
            '    style=filled;',
            '    color=lightblue;',
        ]

        for param in causal_map.parameters:
            lines.append(f'    "{param}" [shape=ellipse, style=filled, fillcolor=lightgreen];')

        lines.extend([
            '  }',
            '',
            '  // Templates',
            '  subgraph cluster_templates {',
            '    label="Templates";',
            '    style=filled;',
            '    color=lightyellow;',
        ])

        for template_name in causal_map.templates:
            safe_name = template_name.replace('/', '_').replace('.', '_')
            lines.append(f'    "{safe_name}" [label="{template_name}"];')

        lines.extend([
            '  }',
            '',
            '  // Output Files',
            '  subgraph cluster_outputs {',
            '    label="Output Files";',
            '    style=filled;',
            '    color=lightpink;',
        ])

        for output in causal_map.output_files:
            safe_name = output.replace('/', '_').replace('.', '_')
            lines.append(f'    "{safe_name}" [label="{output}", shape=note];')

        lines.extend([
            '  }',
            '',
            '  // Edges',
        ])

        # Add edges for links
        seen_edges = set()
        for link in causal_map.links:
            template_safe = link.template.replace('/', '_').replace('.', '_')
            output_safe = link.output_file.replace('/', '_').replace('.', '_')

            # Param -> Template
            edge1 = f'"{link.parameter}" -> "{template_safe}"'
            if edge1 not in seen_edges:
                lines.append(f'  {edge1};')
                seen_edges.add(edge1)

            # Template -> Output
            edge2 = f'"{template_safe}" -> "{output_safe}"'
            if edge2 not in seen_edges:
                lines.append(f'  {edge2};')
                seen_edges.add(edge2)

        lines.append('}')

        return '\n'.join(lines)

    def generate_yaml_output(self, causal_map: CausalMap) -> str:
        """Generate YAML format output"""
        output = {
            'causal_map': {
                'task_id': causal_map.task_id,
                'task_name': causal_map.task_name,
                'generated_at': causal_map.generated_at,
                'parameters': {
                    name: {
                        'source': info.get('source', 'unknown'),
                        'type': info.get('type', 'unknown'),
                        'affects': list(causal_map.param_to_outputs.get(name, [])),
                        'templates': list(causal_map.param_to_templates.get(name, []))
                    }
                    for name, info in causal_map.parameters.items()
                },
                'output_files': [
                    {
                        'path': output,
                        'depends_on': list(causal_map.output_to_params.get(output, []))
                    }
                    for output in causal_map.output_files
                ],
                'summary': {
                    'total_parameters': len(causal_map.parameters),
                    'total_templates': len(causal_map.templates),
                    'total_outputs': len(causal_map.output_files),
                    'total_links': len(causal_map.links)
                }
            }
        }

        return yaml.dump(output, default_flow_style=False, sort_keys=False)

def main():
    parser = argparse.ArgumentParser(
        description='Map input parameters to output files through templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s .task/wiring.yaml
    %(prog)s .task/wiring.yaml --param entity_name
    %(prog)s .task/wiring.yaml --json
    %(prog)s .task/wiring.yaml --dot > graph.dot
        """
    )

    parser.add_argument('ssot', type=Path, help='Path to SSOT wiring.yaml')
    parser.add_argument('--param', '-p', type=str,
                        help='Query impact of specific parameter')
    parser.add_argument('--templates', '-t', type=Path,
                        help='Templates directory')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    parser.add_argument('--yaml', action='store_true',
                        help='Output as YAML (default)')
    parser.add_argument('--dot', action='store_true',
                        help='Output as DOT graph format')
    parser.add_argument('--output', '-o', type=Path,
                        help='Output file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Validate inputs
    if not args.ssot.exists():
        print(f"Error: SSOT file not found: {args.ssot}", file=sys.stderr)
        sys.exit(2)

    # Create mapper
    templates_dir = args.templates or Path('templates')
    mapper = CausalMapper(templates_dir=templates_dir, verbose=args.verbose)

    # Build causal map
    try:
        causal_map = mapper.build_causal_map(args.ssot)
    except Exception as e:
        print(f"Error: Failed to build causal map: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)

    # Handle parameter query
    if args.param:
        result = mapper.query_parameter_impact(causal_map, args.param)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result['found']:
                print(f"Parameter: {result['parameter']}")
                print(f"\nAffected Files ({len(result['affected_files'])}):")
                for f in result['affected_files']:
                    print(f"  - {f}")
                print(f"\nThrough Templates ({len(result['affected_templates'])}):")
                for t in result['affected_templates']:
                    print(f"  - {t}")
            else:
                print(f"Parameter '{args.param}' not found in causal map")
                sys.exit(1)
        sys.exit(0)

    # Generate output
    if args.dot:
        output = mapper.generate_dot_graph(causal_map)
    elif args.json:
        output_data = {
            'task_id': causal_map.task_id,
            'task_name': causal_map.task_name,
            'generated_at': causal_map.generated_at,
            'parameters': {
                name: {
                    'source': info.get('source'),
                    'affects': list(causal_map.param_to_outputs.get(name, []))
                }
                for name, info in causal_map.parameters.items()
            },
            'outputs': [
                {
                    'path': out,
                    'depends_on': list(causal_map.output_to_params.get(out, []))
                }
                for out in causal_map.output_files
            ],
            'links': [
                {
                    'param': l.parameter,
                    'template': l.template,
                    'output': l.output_file,
                    'type': l.dependency_type
                }
                for l in causal_map.links
            ]
        }
        output = json.dumps(output_data, indent=2)
    else:
        output = mapper.generate_yaml_output(causal_map)

    # Write or print output
    if args.output:
        args.output.write_text(output)
        print(f"Causal map written to: {args.output}")
    else:
        print(output)

if __name__ == '__main__':
    main()
