"""
SAF Schema Validator

Validates schema completeness, correspondence, coverage, and compliance
with Schema-Driven Module Generation Policy.

Usage:
    python tools/schema_validator.py --validate schemas/user.schema.yaml
    python tools/schema_validator.py --check-correspondence .
    python tools/schema_validator.py --measure-coverage .
    python tools/schema_validator.py --score-completeness schemas/user.schema.yaml
    python tools/schema_validator.py --check-dependencies schemas/user.schema.yaml
    python tools/schema_validator.py --verify-brick .
"""

import os
import sys
import yaml
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime

# Path validation for security
try:
    from tools.utils.path_validator import validate_path
except ImportError:
    # Fallback if running from different directory
    def validate_path(user_path: str, repo_root: Path = None) -> Path:
        """Validate path is within repository bounds."""
        if repo_root is None:
            repo_root = Path.cwd()
        resolved = Path(user_path).resolve()
        repo_resolved = repo_root.resolve()
        try:
            resolved.relative_to(repo_resolved)
        except ValueError:
            raise ValueError(
                f"Path '{user_path}' is outside repository bounds.\n"
                f"Resolved to: {resolved}\n"
                f"Repo root: {repo_resolved}"
            )
        return resolved

class SchemaValidator:
    """Validate schemas and schema-driven generation compliance."""

    def __init__(self, brick_dir: str = '.'):
        """Initialize validator with brick directory."""
        self.brick_dir = Path(brick_dir)
        self.brick_path = self.brick_dir / '.brick'
        self.schemas_dir = self.brick_dir / 'schemas'

    def validate_schema(self, schema_path: str) -> Dict[str, Any]:
        """Validate schema completeness and correctness."""
        print(f"Validating schema: {schema_path}\n")

        schema_file = Path(schema_path)
        if not schema_file.exists():
            return {
                'status': 'fail',
                'error': f'Schema file not found: {schema_path}'
            }

        # Load schema
        with open(schema_file, 'r') as f:
            try:
                schema = yaml.safe_load(f)
            except yaml.YAMLError as e:
                return {
                    'status': 'fail',
                    'error': f'Invalid YAML: {e}'
                }

        # Validate schema
        result = {
            'schema_path': str(schema_file),
            'status': 'pass',
            'checks': {},
            'issues': [],
            'warnings': []
        }

        # Check 1: Schema metadata
        metadata_check = self._check_schema_metadata(schema)
        result['checks']['metadata'] = metadata_check
        if not metadata_check['passed']:
            result['status'] = 'fail'
            result['issues'].extend(metadata_check['issues'])

        # Check 2: Schema type
        schema_type = schema.get('schema', {}).get('type')
        if schema_type:
            result['schema_type'] = schema_type

            # Type-specific checks
            if schema_type == 'structural':
                structural_check = self._check_structural_schema(schema)
                result['checks']['structural'] = structural_check
                if not structural_check['passed']:
                    result['status'] = 'fail'
                    result['issues'].extend(structural_check['issues'])

            elif schema_type == 'behavioral':
                behavioral_check = self._check_behavioral_schema(schema)
                result['checks']['behavioral'] = behavioral_check
                if not behavioral_check['passed']:
                    result['status'] = 'fail'
                    result['issues'].extend(behavioral_check['issues'])

            elif schema_type == 'integration':
                integration_check = self._check_integration_schema(schema)
                result['checks']['integration'] = integration_check
                if not integration_check['passed']:
                    result['status'] = 'fail'
                    result['issues'].extend(integration_check['issues'])

        # Check 3: Schema versioning
        versioning_check = self._check_schema_versioning(schema)
        result['checks']['versioning'] = versioning_check
        if not versioning_check['passed']:
            result['status'] = 'fail'
            result['issues'].extend(versioning_check['issues'])

        # Print results
        self._print_validation_results(result)

        return result

    def check_correspondence(self, brick_dir: str = '.') -> Dict[str, Any]:
        """Check schema-artifact correspondence."""
        print("Checking schema-artifact correspondence...\n")

        brick_path = Path(brick_dir)
        result = {
            'status': 'pass',
            'artifacts_checked': 0,
            'schema_traced': 0,
            'missing_trace': [],
            'invalid_trace': [],
            'issues': []
        }

        # Find all generated artifacts
        generated_files = self._find_generated_files(brick_path)

        for file_path in generated_files:
            result['artifacts_checked'] += 1

            # Check for schema source in provenance header
            schema_source = self._extract_schema_source(file_path)

            if not schema_source:
                result['missing_trace'].append(str(file_path))
                result['status'] = 'fail'
                continue

            result['schema_traced'] += 1

            # Verify schema exists
            schema_path = brick_path / schema_source
            if not schema_path.exists():
                result['invalid_trace'].append({
                    'file': str(file_path),
                    'schema': schema_source,
                    'error': 'Schema file not found'
                })
                result['status'] = 'fail'

        # Print results
        print("Schema-Artifact Correspondence Report")
        print("=" * 60)
        print(f"Artifacts checked: {result['artifacts_checked']}")
        print(f"Schema-traced: {result['schema_traced']}")
        print(f"Missing trace: {len(result['missing_trace'])}")
        print(f"Invalid trace: {len(result['invalid_trace'])}")
        print(f"\nStatus: {result['status'].upper()}\n")

        if result['missing_trace']:
            print("Files missing schema trace:")
            for file_path in result['missing_trace']:
                print(f"  ❌ {file_path}")
            print()

        if result['invalid_trace']:
            print("Files with invalid schema trace:")
            for item in result['invalid_trace']:
                print(f"  ❌ {item['file']}")
                print(f"     Schema: {item['schema']}")
                print(f"     Error: {item['error']}")
            print()

        return result

    def measure_coverage(self, brick_dir: str = '.', target: float = 95.0) -> Dict[str, Any]:
        """Measure schema coverage (% of code traced to schema).

        Args:
            brick_dir: Directory to measure coverage in
            target: Coverage target percentage (default: 95.0)
        """
        print("Measuring schema coverage...\n")

        brick_path = Path(brick_dir)
        result = {
            'status': 'pass',
            'total_lines': 0,
            'schema_traced_lines': 0,
            'manual_lines': 0,
            'exception_lines': 0,
            'coverage_percent': 0.0,
            'target_percent': target
        }

        # Find all generated/source files
        source_files = self._find_source_files(brick_path)

        for file_path in source_files:
            lines = self._count_file_lines(file_path)
            result['total_lines'] += lines

            # Check if schema-traced or exception
            schema_source = self._extract_schema_source(file_path)
            exception_marker = self._extract_exception_marker(file_path)

            if schema_source:
                result['schema_traced_lines'] += lines
            elif exception_marker:
                result['exception_lines'] += lines
            else:
                result['manual_lines'] += lines

        # Calculate coverage
        if result['total_lines'] > 0:
            result['coverage_percent'] = (
                (result['schema_traced_lines'] / result['total_lines']) * 100
            )

        # Check against target
        if result['coverage_percent'] < result['target_percent']:
            result['status'] = 'fail'

        # Print results
        print("Schema Coverage Report")
        print("=" * 60)
        print(f"Total lines: {result['total_lines']}")
        print(f"Schema-traced lines: {result['schema_traced_lines']}")
        print(f"Exception lines: {result['exception_lines']}")
        print(f"Manual lines: {result['manual_lines']}")
        print(f"\nCoverage: {result['coverage_percent']:.1f}%")
        print(f"Target: {result['target_percent']:.1f}%")
        print(f"\nStatus: {result['status'].upper()}\n")

        return result

    def score_completeness(self, schema_path: str) -> Dict[str, Any]:
        """Score schema completeness (0-100)."""
        print(f"Scoring schema completeness: {schema_path}\n")

        schema_file = Path(schema_path)
        if not schema_file.exists():
            return {
                'status': 'fail',
                'error': f'Schema file not found: {schema_path}'
            }

        # Load schema
        with open(schema_file, 'r') as f:
            schema = yaml.safe_load(f)

        result = {
            'schema_path': str(schema_file),
            'score': 0,
            'max_score': 100,
            'checks': {},
            'status': 'pass'
        }

        schema_type = schema.get('schema', {}).get('type', 'unknown')
        checks_passed = 0
        total_checks = 0

        # Rule 1: All fields must be typed (20 points)
        total_checks += 1
        if self._all_fields_typed(schema, schema_type):
            checks_passed += 1
            result['checks']['fields_typed'] = 'PASS'
        else:
            result['checks']['fields_typed'] = 'FAIL'

        # Rule 2: All constraints must be explicit (20 points)
        total_checks += 1
        if self._all_constraints_explicit(schema, schema_type):
            checks_passed += 1
            result['checks']['constraints_explicit'] = 'PASS'
        else:
            result['checks']['constraints_explicit'] = 'FAIL'

        # Rule 3: All relationships must be defined (20 points)
        total_checks += 1
        if self._all_relationships_defined(schema, schema_type):
            checks_passed += 1
            result['checks']['relationships_defined'] = 'PASS'
        else:
            result['checks']['relationships_defined'] = 'FAIL'

        # Rule 4: Metadata complete (20 points)
        total_checks += 1
        metadata_check = self._check_schema_metadata(schema)
        if metadata_check['passed']:
            checks_passed += 1
            result['checks']['metadata_complete'] = 'PASS'
        else:
            result['checks']['metadata_complete'] = 'FAIL'

        # Rule 5: Versioning correct (20 points)
        total_checks += 1
        versioning_check = self._check_schema_versioning(schema)
        if versioning_check['passed']:
            checks_passed += 1
            result['checks']['versioning_correct'] = 'PASS'
        else:
            result['checks']['versioning_correct'] = 'FAIL'

        # Calculate score
        result['score'] = int((checks_passed / total_checks) * 100)

        if result['score'] < 100:
            result['status'] = 'fail'

        # Print results
        print("Schema Completeness Score")
        print("=" * 60)
        print(f"Schema: {schema_path}")
        print(f"Type: {schema_type}")
        print(f"\nChecks:")
        for check, status in result['checks'].items():
            symbol = "✅" if status == "PASS" else "❌"
            print(f"  {symbol} {check}: {status}")
        print(f"\nScore: {result['score']}/{result['max_score']}")
        print(f"Status: {result['status'].upper()}\n")

        return result

    def check_dependencies(self, schema_path: str) -> Dict[str, Any]:
        """Check schema dependencies are valid."""
        print(f"Checking schema dependencies: {schema_path}\n")

        schema_file = Path(schema_path)
        if not schema_file.exists():
            return {
                'status': 'fail',
                'error': f'Schema file not found: {schema_path}'
            }

        # Load schema
        with open(schema_file, 'r') as f:
            schema = yaml.safe_load(f)

        result = {
            'schema_path': str(schema_file),
            'status': 'pass',
            'dependencies': [],
            'missing': [],
            'circular': []
        }

        # Extract dependencies
        depends_on = schema.get('schema', {}).get('depends_on', [])

        for dep in depends_on:
            result['dependencies'].append(dep)

            # Check if dependency exists
            dep_path = self.brick_dir / dep.split('@')[0]
            if not dep_path.exists():
                result['missing'].append(dep)
                result['status'] = 'fail'

        # Check for circular dependencies
        circular = self._detect_circular_dependencies(schema_file, set())
        if circular:
            result['circular'] = circular
            result['status'] = 'fail'

        # Print results
        print("Schema Dependencies Report")
        print("=" * 60)
        print(f"Dependencies: {len(result['dependencies'])}")
        print(f"Missing: {len(result['missing'])}")
        print(f"Circular: {len(result['circular'])}")
        print(f"\nStatus: {result['status'].upper()}\n")

        if result['missing']:
            print("Missing dependencies:")
            for dep in result['missing']:
                print(f"  ❌ {dep}")
            print()

        if result['circular']:
            print("Circular dependencies detected:")
            for cycle in result['circular']:
                print(f"  ❌ {' → '.join(cycle)}")
            print()

        return result

    def verify_brick(self, brick_dir: str = '.') -> Dict[str, Any]:
        """Verify entire brick for schema compliance."""
        print("Verifying brick schema compliance...\n")

        result = {
            'status': 'pass',
            'schemas_found': 0,
            'schemas_valid': 0,
            'correspondence_pass': False,
            'coverage_pass': False,
            'coverage_percent': 0.0,
            'issues': []
        }

        brick_path = Path(brick_dir)
        schemas_dir = brick_path / 'schemas'

        # Find all schemas
        if schemas_dir.exists():
            schema_files = list(schemas_dir.glob('**/*.yaml'))
            result['schemas_found'] = len(schema_files)

            # Validate each schema
            for schema_file in schema_files:
                validation = self.validate_schema(str(schema_file))
                if validation['status'] == 'pass':
                    result['schemas_valid'] += 1
                else:
                    result['status'] = 'fail'
                    result['issues'].append(f"Schema validation failed: {schema_file}")

        # Check correspondence
        correspondence = self.check_correspondence(str(brick_path))
        result['correspondence_pass'] = (correspondence['status'] == 'pass')
        if not result['correspondence_pass']:
            result['status'] = 'fail'
            result['issues'].append("Schema-artifact correspondence check failed")

        # Measure coverage
        coverage = self.measure_coverage(str(brick_path))
        result['coverage_percent'] = coverage['coverage_percent']
        result['coverage_pass'] = (coverage['status'] == 'pass')
        if not result['coverage_pass']:
            result['status'] = 'fail'
            result['issues'].append(f"Schema coverage below target: {coverage['coverage_percent']:.1f}% < {coverage['target_percent']:.1f}%")

        # Print summary
        print("\n" + "=" * 60)
        print("BRICK SCHEMA COMPLIANCE SUMMARY")
        print("=" * 60)
        print(f"Schemas found: {result['schemas_found']}")
        print(f"Schemas valid: {result['schemas_valid']}")
        print(f"Correspondence check: {'✅ PASS' if result['correspondence_pass'] else '❌ FAIL'}")
        print(f"Coverage check: {'✅ PASS' if result['coverage_pass'] else '❌ FAIL'} ({result['coverage_percent']:.1f}%)")
        print(f"\nOverall Status: {result['status'].upper()}")

        if result['issues']:
            print(f"\nIssues:")
            for issue in result['issues']:
                print(f"  ❌ {issue}")

        print("=" * 60 + "\n")

        return result

    # Helper methods

    def _check_schema_metadata(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Check schema metadata completeness."""
        required_fields = ['name', 'version', 'type', 'created_at']
        metadata = schema.get('schema', {})

        issues = []
        for field in required_fields:
            if field not in metadata:
                issues.append(f"Missing metadata field: {field}")

        return {
            'passed': len(issues) == 0,
            'issues': issues
        }

    def _check_structural_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Check structural schema completeness."""
        issues = []

        entities = schema.get('entities', {})
        if not entities:
            issues.append("No entities defined in structural schema")

        for entity_name, entity in entities.items():
            fields = entity.get('fields', {})
            if not fields:
                issues.append(f"Entity '{entity_name}' has no fields")

            for field_name, field_def in fields.items():
                # Check field has type
                if isinstance(field_def, dict):
                    if 'type' not in field_def:
                        issues.append(f"Field '{entity_name}.{field_name}' missing type")
                elif not isinstance(field_def, str):
                    issues.append(f"Field '{entity_name}.{field_name}' has invalid definition")

        return {
            'passed': len(issues) == 0,
            'issues': issues
        }

    def _check_behavioral_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Check behavioral schema completeness."""
        issues = []

        validations = schema.get('validations', {})
        state_machine = schema.get('state_machine', {})

        if not validations and not state_machine:
            issues.append("Behavioral schema has neither validations nor state_machine")

        # Check validations
        for field_name, validation in validations.items():
            rules = validation.get('rules', [])
            if not rules:
                issues.append(f"Validation for '{field_name}' has no rules")

            for rule in rules:
                if 'type' not in rule:
                    issues.append(f"Validation rule for '{field_name}' missing type")
                if 'message' not in rule:
                    issues.append(f"Validation rule for '{field_name}' missing message")

        # Check state machine
        if state_machine:
            states = state_machine.get('states', [])
            if not states:
                issues.append("State machine has no states defined")

            for state in states:
                if 'name' not in state:
                    issues.append("State missing name")

        return {
            'passed': len(issues) == 0,
            'issues': issues
        }

    def _check_integration_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Check integration schema completeness."""
        issues = []

        # Check if OpenAPI schema
        if 'openapi' in schema:
            paths = schema.get('paths', {})
            if not paths:
                issues.append("OpenAPI schema has no paths defined")

            for path, methods in paths.items():
                for method, operation in methods.items():
                    if method.startswith('x-'):
                        continue  # Skip extensions

                    if 'responses' not in operation:
                        issues.append(f"{method.upper()} {path} missing responses")

        return {
            'passed': len(issues) == 0,
            'issues': issues
        }

    def _check_schema_versioning(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Check schema versioning correctness."""
        issues = []

        version = schema.get('schema', {}).get('version')
        if not version:
            issues.append("Schema missing version")
        else:
            # Check semantic versioning format
            if not re.match(r'^\d+\.\d+\.\d+$', version):
                issues.append(f"Invalid version format: {version} (expected: X.Y.Z)")

        return {
            'passed': len(issues) == 0,
            'issues': issues
        }

    def _all_fields_typed(self, schema: Dict[str, Any], schema_type: str) -> bool:
        """Check if all fields have types."""
        if schema_type != 'structural':
            return True  # Only applies to structural schemas

        entities = schema.get('entities', {})
        for entity_name, entity in entities.items():
            fields = entity.get('fields', {})
            for field_name, field_def in fields.items():
                if isinstance(field_def, dict):
                    if 'type' not in field_def:
                        return False
                elif not isinstance(field_def, str):
                    return False

        return True

    def _all_constraints_explicit(self, schema: Dict[str, Any], schema_type: str) -> bool:
        """Check if constraints are explicit."""
        # Simplified check - look for constraint keywords
        schema_str = yaml.dump(schema)
        constraint_keywords = ['nullable', 'required', 'unique', 'max_length', 'min_length', 'pattern', 'format']
        return any(keyword in schema_str for keyword in constraint_keywords)

    def _all_relationships_defined(self, schema: Dict[str, Any], schema_type: str) -> bool:
        """Check if relationships are defined."""
        if schema_type != 'structural':
            return True  # Only applies to structural schemas

        # Look for references keyword
        schema_str = yaml.dump(schema)
        return 'references' in schema_str or 'relationships' not in schema_str

    def _find_generated_files(self, brick_path: Path) -> List[Path]:
        """Find all generated files in brick."""
        generated_files = []
        exclude_dirs = {'.git', 'node_modules', '.brick', 'LogBook', 'PLANNING'}

        for ext in ['.py', '.ts', '.js', '.sql']:
            for file_path in brick_path.rglob(f'*{ext}'):
                # Skip excluded directories
                if any(part in exclude_dirs for part in file_path.parts):
                    continue
                generated_files.append(file_path)

        return generated_files

    def _find_source_files(self, brick_path: Path) -> List[Path]:
        """Find all source files for coverage measurement."""
        return self._find_generated_files(brick_path)

    def _extract_schema_source(self, file_path: Path) -> Optional[str]:
        """Extract schema source from file provenance header."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # Read first 1000 chars
                match = re.search(r'@saf:schema-source=([^\s\n]+)', content)
                if match:
                    return match.group(1).split('@')[0]  # Remove version
        except FileNotFoundError:
            print(f"Warning: File not found: {file_path}", file=sys.stderr)
        except PermissionError:
            print(f"Warning: Permission denied: {file_path}", file=sys.stderr)
        except (UnicodeDecodeError, OSError) as e:
            print(f"Warning: Cannot read {file_path}: {e}", file=sys.stderr)
        return None

    def _extract_exception_marker(self, file_path: Path) -> Optional[str]:
        """Extract exception marker from file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)
                match = re.search(r'@saf:exception=([^\s\n]+)', content)
                if match:
                    return match.group(1)
        except FileNotFoundError:
            print(f"Warning: File not found: {file_path}", file=sys.stderr)
        except PermissionError:
            print(f"Warning: Permission denied: {file_path}", file=sys.stderr)
        except (UnicodeDecodeError, OSError) as e:
            print(f"Warning: Cannot read {file_path}: {e}", file=sys.stderr)
        return None

    def _count_file_lines(self, file_path: Path) -> int:
        """Count non-blank lines in file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for line in f if line.strip())
        except FileNotFoundError:
            print(f"Warning: File not found: {file_path}", file=sys.stderr)
            return 0
        except PermissionError:
            print(f"Warning: Permission denied: {file_path}", file=sys.stderr)
            return 0
        except (UnicodeDecodeError, OSError) as e:
            print(f"Warning: Cannot read {file_path}: {e}", file=sys.stderr)
            return 0

    def _detect_circular_dependencies(self, schema_file: Path, visited: Set[Path]) -> List[List[str]]:
        """Detect circular dependencies in schema using DFS.

        Args:
            schema_file: The schema file to check for circular dependencies
            visited: Set of already visited paths in current DFS traversal

        Returns:
            List of cycles found, where each cycle is a list of file paths
        """
        cycles = []

        def dfs(current: Path, path: List[str], seen: Set[Path]):
            """Depth-first search to detect cycles."""
            if current in seen:
                # Found a cycle - extract the cycle from path
                current_str = str(current)
                if current_str in path:
                    cycle_start = path.index(current_str)
                    cycles.append(path[cycle_start:] + [current_str])
                return

            seen.add(current)
            path.append(str(current))

            # Load schema and check depends_on field
            try:
                with open(current, 'r') as f:
                    schema = yaml.safe_load(f)

                if schema is None:
                    return

                # Check for depends_on in schema metadata
                depends_on = []
                if isinstance(schema, dict):
                    depends_on = schema.get('depends_on', [])
                    if not depends_on:
                        depends_on = schema.get('schema', {}).get('depends_on', [])

                for dep in depends_on:
                    if isinstance(dep, str):
                        # Handle format: "brick_id@version" or just "brick_id"
                        dep_name = dep.split('@')[0] if '@' in dep else dep
                        dep_path = self.brick_dir / dep_name if self.brick_dir else Path(dep_name)

                        # Try common schema file extensions
                        for ext in ['.yaml', '.yml', '.json', '']:
                            candidate = Path(str(dep_path) + ext)
                            if candidate.exists():
                                dfs(candidate, path.copy(), seen.copy())
                                break
            except (yaml.YAMLError, FileNotFoundError, PermissionError):
                pass

        dfs(schema_file, [], set())
        return cycles

    def _print_validation_results(self, result: Dict[str, Any]):
        """Print validation results."""
        print("Schema Validation Report")
        print("=" * 60)
        print(f"Schema: {result['schema_path']}")
        if 'schema_type' in result:
            print(f"Type: {result['schema_type']}")

        print(f"\nChecks:")
        for check_name, check_result in result['checks'].items():
            status = "✅ PASS" if check_result.get('passed', False) else "❌ FAIL"
            print(f"  {status} {check_name}")

        print(f"\nStatus: {result['status'].upper()}")

        if result['issues']:
            print(f"\nIssues:")
            for issue in result['issues']:
                print(f"  ❌ {issue}")

        if result['warnings']:
            print(f"\nWarnings:")
            for warning in result['warnings']:
                print(f"  ⚠️  {warning}")

        print()

def main():
    """Run schema validator based on command-line arguments."""
    validator = SchemaValidator()

    def get_validated_path(idx: int, default: str = '.') -> str:
        """Get and validate path argument."""
        raw_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else default
        try:
            validated = validate_path(raw_path)
            return str(validated)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    if '--validate' in sys.argv:
        idx = sys.argv.index('--validate')
        if idx + 1 < len(sys.argv):
            schema_path = get_validated_path(idx)
            result = validator.validate_schema(schema_path)
            sys.exit(0 if result['status'] == 'pass' else 1)

    elif '--check-correspondence' in sys.argv:
        idx = sys.argv.index('--check-correspondence')
        brick_dir = get_validated_path(idx, '.')
        result = validator.check_correspondence(brick_dir)
        sys.exit(0 if result['status'] == 'pass' else 1)

    elif '--measure-coverage' in sys.argv:
        idx = sys.argv.index('--measure-coverage')
        brick_dir = get_validated_path(idx, '.')
        # Check for --target option
        target = 95.0
        if '--target' in sys.argv:
            try:
                target_idx = sys.argv.index('--target')
                target = float(sys.argv[target_idx + 1])
                if target < 0 or target > 100:
                    print("Error: --target must be between 0 and 100", file=sys.stderr)
                    sys.exit(1)
            except (IndexError, ValueError):
                print("Error: --target requires a numeric value (e.g., --target 80.0)", file=sys.stderr)
                sys.exit(1)
        result = validator.measure_coverage(brick_dir, target)
        sys.exit(0 if result['status'] == 'pass' else 1)

    elif '--score-completeness' in sys.argv:
        idx = sys.argv.index('--score-completeness')
        if idx + 1 < len(sys.argv):
            schema_path = get_validated_path(idx)
            result = validator.score_completeness(schema_path)
            sys.exit(0 if result['status'] == 'pass' else 1)

    elif '--check-dependencies' in sys.argv:
        idx = sys.argv.index('--check-dependencies')
        if idx + 1 < len(sys.argv):
            schema_path = get_validated_path(idx)
            result = validator.check_dependencies(schema_path)
            sys.exit(0 if result['status'] == 'pass' else 1)

    elif '--verify-brick' in sys.argv:
        idx = sys.argv.index('--verify-brick')
        brick_dir = get_validated_path(idx, '.')
        result = validator.verify_brick(brick_dir)
        sys.exit(0 if result['status'] == 'pass' else 1)

    elif '--file' in sys.argv and '--schema' in sys.argv:
        # Validate a file against a JSON/YAML schema
        file_idx = sys.argv.index('--file')
        schema_idx = sys.argv.index('--schema')
        file_path = get_validated_path(file_idx)
        schema_path = get_validated_path(schema_idx)

        try:
            from jsonschema import Draft7Validator
        except ImportError:
            print("Warning: jsonschema not installed, skipping validation")
            sys.exit(0)

        # Load schema
        try:
            with open(schema_path, 'r') as f:
                if schema_path.endswith('.json'):
                    schema = json.load(f)
                else:
                    schema = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading schema {schema_path}: {e}")
            sys.exit(1)

        # Load file to validate
        try:
            with open(file_path, 'r') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading file {file_path}: {e}")
            sys.exit(1)

        # Validate
        v = Draft7Validator(schema)
        errors = list(v.iter_errors(data))
        if errors:
            print(f"Validation failed for {file_path}:")
            for err in errors[:5]:
                print(f"  - {err.message} at {list(err.path)}")
            sys.exit(1)
        else:
            print(f"✓ {file_path} valid against {schema_path}")
            sys.exit(0)

    elif '--dir' in sys.argv:
        # Batch validate schemas in directory
        dir_idx = sys.argv.index('--dir')
        dir_path = get_validated_path(dir_idx, '.')
        file_format = 'yaml'
        if '--format' in sys.argv:
            fmt_idx = sys.argv.index('--format')
            if fmt_idx + 1 < len(sys.argv):
                file_format = sys.argv[fmt_idx + 1]

        # Find and validate all schema files
        schema_dir = Path(dir_path)
        ext_map = {'yaml': ['.yaml', '.yml'], 'json': ['.json']}
        extensions = ext_map.get(file_format, ['.yaml', '.yml'])

        schema_files = []
        for ext in extensions:
            schema_files.extend(schema_dir.glob(f'*{ext}'))

        if not schema_files:
            print(f"No {file_format} files found in {dir_path}")
            sys.exit(0)

        all_passed = True
        for schema_file in sorted(schema_files):
            result = validator.validate_schema(str(schema_file))
            if result['status'] != 'pass':
                all_passed = False

        sys.exit(0 if all_passed else 1)

    else:
        print("SAF Schema Validator")
        print("\nUsage:")
        print("  --validate <schema>          Validate schema completeness")
        print("  --check-correspondence <dir> Check schema-artifact correspondence")
        print("  --measure-coverage <dir>     Measure schema coverage")
        print("  --score-completeness <schema> Score schema completeness")
        print("  --check-dependencies <schema> Check schema dependencies")
        print("  --verify-brick <dir>         Verify entire brick compliance")
        print("  --file <file> --schema <schema>  Validate file against JSON/YAML schema")
        print("  --dir <dir> [--format yaml|json]  Batch validate schemas in directory")
        print("\nOptions:")
        print("  --target <percent>           Coverage target (default: 95.0)")
        print("  --format <type>              File format for --dir (yaml or json)")
        print("\nExamples:")
        print("  python tools/schema_validator.py --validate schemas/user.schema.yaml")
        print("  python tools/schema_validator.py --verify-brick .")
        print("  python tools/schema_validator.py --measure-coverage . --target 80.0")
        print("  python tools/schema_validator.py --file brick.yaml --schema brick_schema.yaml")
        print("  python tools/schema_validator.py --dir PLANNING/schemas/ --format yaml")
        sys.exit(1)

if __name__ == '__main__':
    main()
