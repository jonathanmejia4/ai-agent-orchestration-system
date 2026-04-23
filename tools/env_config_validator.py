#!/usr/bin/env python3
"""
the system Environment Configuration Validator

Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Core Tool

This tool validates environment configuration for the system deployments:
- Validates .env files against templates
- Checks for required environment variables
- Detects potential security issues (exposed secrets, weak values)
- Supports multiple environments (dev, staging, production)
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

class Severity(Enum):
    """Validation issue severity."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class EnvironmentType(Enum):
    """Environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"
    LOCAL = "local"

@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    severity: Severity
    variable: str
    message: str
    suggestion: Optional[str] = None

@dataclass
class EnvVariable:
    """Represents an environment variable definition."""
    name: str
    value: Optional[str] = None
    required: bool = True
    sensitive: bool = False
    pattern: Optional[str] = None
    min_length: int = 0
    allowed_values: Optional[List[str]] = None
    description: str = ""
    default: Optional[str] = None

@dataclass
class ValidationResult:
    """Result of environment validation."""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    variables_found: Set[str] = field(default_factory=set)
    variables_missing: Set[str] = field(default_factory=set)
    environment: Optional[EnvironmentType] = None

class EnvConfigValidator:
    """Validates environment configuration files."""

    # Common sensitive variable patterns
    SENSITIVE_PATTERNS = [
        r".*_KEY$",
        r".*_SECRET$",
        r".*_PASSWORD$",
        r".*_TOKEN$",
        r".*_API_KEY$",
        r".*_PRIVATE.*",
        r".*_CREDENTIAL.*",
        r"^AWS_.*",
        r"^GITHUB_.*",
        r"^DATABASE_.*PASSWORD.*",
    ]

    # Weak value patterns (for sensitive variables)
    WEAK_VALUE_PATTERNS = [
        r"^password$",
        r"^123456",
        r"^admin$",
        r"^test$",
        r"^changeme$",
        r"^secret$",
        r"^default$",
        r"^example$",
        r"^placeholder$",
        r"^TODO",
        r"^FIXME",
        r"^xxx+$",
    ]

    # Common the system required variables
    REQUIRED_VARIABLES = [
        EnvVariable(
            name="SYSTEM_ENV",
            allowed_values=["development", "staging", "production", "test"],
            description="the system environment identifier"
        ),
        EnvVariable(
            name="LOG_LEVEL",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            required=False,
            description="Logging level"
        ),
    ]

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.custom_requirements: List[EnvVariable] = []

    def parse_env_file(self, filepath: Path) -> Dict[str, str]:
        """Parse a .env file into key-value pairs."""
        variables = {}

        if not filepath.exists():
            return variables

        with open(filepath) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Handle export prefix
                if line.startswith("export "):
                    line = line[7:]

                # Parse key=value
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    variables[key] = value

        return variables

    def is_sensitive_variable(self, name: str) -> bool:
        """Check if a variable name suggests sensitive content."""
        name_upper = name.upper()
        for pattern in self.SENSITIVE_PATTERNS:
            if re.match(pattern, name_upper):
                return True
        return False

    def is_weak_value(self, value: str) -> bool:
        """Check if a value appears to be a weak/placeholder value."""
        value_lower = value.lower()
        for pattern in self.WEAK_VALUE_PATTERNS:
            if re.match(pattern, value_lower, re.IGNORECASE):
                return True
        return False

    def detect_environment(self, variables: Dict[str, str]) -> Optional[EnvironmentType]:
        """Detect environment type from variables."""
        env_indicators = [
            "SYSTEM_ENV", "NODE_ENV", "ENVIRONMENT", "ENV",
            "RAILS_ENV", "FLASK_ENV", "APP_ENV"
        ]

        for indicator in env_indicators:
            if indicator in variables:
                value = variables[indicator].lower()
                try:
                    return EnvironmentType(value)
                except ValueError:
                    if "prod" in value:
                        return EnvironmentType.PRODUCTION
                    elif "stag" in value:
                        return EnvironmentType.STAGING
                    elif "dev" in value:
                        return EnvironmentType.DEVELOPMENT
                    elif "test" in value:
                        return EnvironmentType.TEST

        return None

    def load_template(self, template_path: Path) -> List[EnvVariable]:
        """Load variable requirements from a template file."""
        requirements = []

        if not template_path.exists():
            return requirements

        with open(template_path) as f:
            for line in f:
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Parse comments for metadata
                description = ""
                required = True
                sensitive = False

                if line.startswith("#"):
                    # This is a comment, might describe next variable
                    continue

                if "=" in line:
                    key, _, default = line.partition("=")
                    key = key.strip()
                    default = default.strip() if default.strip() else None

                    # Check if marked as optional
                    if key.startswith("# "):
                        key = key[2:]
                        required = False

                    requirements.append(EnvVariable(
                        name=key,
                        default=default,
                        required=required,
                        sensitive=self.is_sensitive_variable(key)
                    ))

        return requirements

    def validate(
        self,
        env_file: Path,
        template_file: Optional[Path] = None,
        environment: Optional[EnvironmentType] = None,
        strict: bool = False
    ) -> ValidationResult:
        """Validate an environment file."""
        issues: List[ValidationIssue] = []

        # Parse env file
        variables = self.parse_env_file(env_file)

        if not variables:
            issues.append(ValidationIssue(
                severity=Severity.ERROR,
                variable="",
                message=f"Environment file not found or empty: {env_file}"
            ))
            return ValidationResult(valid=False, issues=issues)

        # Detect environment
        detected_env = environment or self.detect_environment(variables)
        is_production = detected_env == EnvironmentType.PRODUCTION

        # Load requirements
        requirements = list(self.REQUIRED_VARIABLES)
        requirements.extend(self.custom_requirements)

        if template_file:
            requirements.extend(self.load_template(template_file))

        # Build requirement lookup
        req_lookup = {req.name: req for req in requirements}
        required_names = {req.name for req in requirements if req.required}

        # Track found variables
        found_names = set(variables.keys())

        # Check required variables
        missing = required_names - found_names
        for name in missing:
            req = req_lookup.get(name)
            issues.append(ValidationIssue(
                severity=Severity.ERROR,
                variable=name,
                message=f"Required variable '{name}' is missing",
                suggestion=f"Add {name}={req.default or 'value'}" if req else None
            ))

        # Validate each variable
        for name, value in variables.items():
            req = req_lookup.get(name)

            # Check for empty values
            if not value:
                if req and req.required:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        variable=name,
                        message=f"Required variable '{name}' has empty value"
                    ))
                else:
                    issues.append(ValidationIssue(
                        severity=Severity.WARNING,
                        variable=name,
                        message=f"Variable '{name}' has empty value"
                    ))
                continue

            # Check sensitive variables for weak values
            if self.is_sensitive_variable(name):
                if self.is_weak_value(value):
                    severity = Severity.ERROR if is_production else Severity.WARNING
                    issues.append(ValidationIssue(
                        severity=severity,
                        variable=name,
                        message=f"Sensitive variable '{name}' has weak/placeholder value",
                        suggestion="Use a strong, unique value"
                    ))

                # Check minimum length for sensitive values
                if len(value) < 8 and is_production:
                    issues.append(ValidationIssue(
                        severity=Severity.WARNING,
                        variable=name,
                        message=f"Sensitive variable '{name}' value is short ({len(value)} chars)",
                        suggestion="Consider using a longer value for better security"
                    ))

            # Validate against requirements
            if req:
                # Check allowed values
                if req.allowed_values and value not in req.allowed_values:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        variable=name,
                        message=f"Value '{value}' not in allowed values: {req.allowed_values}",
                        suggestion=f"Use one of: {', '.join(req.allowed_values)}"
                    ))

                # Check pattern
                if req.pattern and not re.match(req.pattern, value):
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        variable=name,
                        message=f"Value does not match required pattern: {req.pattern}"
                    ))

                # Check minimum length
                if req.min_length and len(value) < req.min_length:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        variable=name,
                        message=f"Value too short (min {req.min_length} chars)"
                    ))

        # Check for potential secrets in values (basic detection)
        for name, value in variables.items():
            # Check for common secret patterns in values
            if re.match(r"^[A-Za-z0-9+/]{32,}={0,2}$", value):
                # Looks like base64 encoded data
                if not self.is_sensitive_variable(name):
                    issues.append(ValidationIssue(
                        severity=Severity.INFO,
                        variable=name,
                        message=f"Value looks like encoded data but variable isn't marked sensitive"
                    ))

        # Production-specific checks
        if is_production:
            # Check for debug/development indicators
            debug_vars = ["DEBUG", "DEV_MODE", "DEVELOPMENT", "VERBOSE"]
            for var in debug_vars:
                if var in variables:
                    value = variables[var].lower()
                    if value in ["true", "1", "yes", "on"]:
                        issues.append(ValidationIssue(
                            severity=Severity.ERROR,
                            variable=var,
                            message=f"Debug mode enabled in production: {var}={variables[var]}",
                            suggestion=f"Set {var}=false for production"
                        ))

        # Determine validity
        has_errors = any(i.severity == Severity.ERROR for i in issues)
        is_valid = not has_errors if not strict else len(issues) == 0

        return ValidationResult(
            valid=is_valid,
            issues=issues,
            variables_found=found_names,
            variables_missing=missing,
            environment=detected_env
        )

    def compare_environments(
        self,
        env1_file: Path,
        env2_file: Path
    ) -> Dict[str, any]:
        """Compare two environment files."""
        vars1 = self.parse_env_file(env1_file)
        vars2 = self.parse_env_file(env2_file)

        keys1 = set(vars1.keys())
        keys2 = set(vars2.keys())

        return {
            "only_in_first": keys1 - keys2,
            "only_in_second": keys2 - keys1,
            "in_both": keys1 & keys2,
            "different_values": [
                k for k in keys1 & keys2
                if vars1[k] != vars2[k] and not self.is_sensitive_variable(k)
            ]
        }

    def generate_template(
        self,
        env_file: Path,
        output: Optional[Path] = None
    ) -> str:
        """Generate a template from an existing env file."""
        variables = self.parse_env_file(env_file)
        lines = [
            "# Environment Configuration Template",
            "# Generated from: " + str(env_file),
            "# ",
            "# Instructions:",
            "# 1. Copy this file to .env",
            "# 2. Fill in the values",
            "# 3. Never commit .env to version control",
            "",
        ]

        # Group by sensitivity
        sensitive_vars = {}
        regular_vars = {}

        for name, value in sorted(variables.items()):
            if self.is_sensitive_variable(name):
                sensitive_vars[name] = value
            else:
                regular_vars[name] = value

        if regular_vars:
            lines.append("# === Configuration ===")
            for name, value in regular_vars.items():
                lines.append(f"{name}={value}")
            lines.append("")

        if sensitive_vars:
            lines.append("# === Sensitive (replace with real values) ===")
            for name, _ in sensitive_vars.items():
                lines.append(f"{name}=REPLACE_ME")
            lines.append("")

        content = "\n".join(lines)

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w") as f:
                f.write(content)

        return content

    def format_result(self, result: ValidationResult, verbose: bool = False) -> str:
        """Format validation result for display."""
        lines = []

        # Summary
        status = "✅ VALID" if result.valid else "❌ INVALID"
        lines.append(f"Validation Result: {status}")

        if result.environment:
            lines.append(f"Environment: {result.environment.value}")

        lines.append(f"Variables found: {len(result.variables_found)}")

        if result.variables_missing:
            lines.append(f"Variables missing: {len(result.variables_missing)}")

        lines.append("")

        # Issues by severity
        errors = [i for i in result.issues if i.severity == Severity.ERROR]
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        infos = [i for i in result.issues if i.severity == Severity.INFO]

        if errors:
            lines.append("ERRORS:")
            for issue in errors:
                lines.append(f"  ❌ [{issue.variable}] {issue.message}")
                if issue.suggestion:
                    lines.append(f"     → {issue.suggestion}")

        if warnings:
            lines.append("\nWARNINGS:")
            for issue in warnings:
                lines.append(f"  ⚠️  [{issue.variable}] {issue.message}")
                if verbose and issue.suggestion:
                    lines.append(f"     → {issue.suggestion}")

        if verbose and infos:
            lines.append("\nINFO:")
            for issue in infos:
                lines.append(f"  ℹ️  [{issue.variable}] {issue.message}")

        return "\n".join(lines)

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="the system Environment Configuration Validator"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate an env file")
    validate_parser.add_argument("env_file", help="Path to .env file")
    validate_parser.add_argument("--template", help="Template file for requirements")
    validate_parser.add_argument("--env", choices=["development", "staging", "production", "test"],
                                 help="Override environment detection")
    validate_parser.add_argument("--strict", action="store_true",
                                 help="Fail on any issues (not just errors)")
    validate_parser.add_argument("--verbose", "-v", action="store_true",
                                 help="Show all issues including info")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two env files")
    compare_parser.add_argument("file1", help="First env file")
    compare_parser.add_argument("file2", help="Second env file")

    # Template command
    template_parser = subparsers.add_parser("template", help="Generate template from env file")
    template_parser.add_argument("env_file", help="Source env file")
    template_parser.add_argument("--output", "-o", help="Output template file")

    args = parser.parse_args()

    validator = EnvConfigValidator()

    if args.command == "validate":
        env_path = Path(args.env_file)
        template_path = Path(args.template) if args.template else None
        env_type = EnvironmentType(args.env) if args.env else None

        result = validator.validate(
            env_file=env_path,
            template_file=template_path,
            environment=env_type,
            strict=args.strict
        )

        print(validator.format_result(result, verbose=args.verbose))
        sys.exit(0 if result.valid else 1)

    elif args.command == "compare":
        comparison = validator.compare_environments(
            Path(args.file1),
            Path(args.file2)
        )

        print(f"Comparing {args.file1} and {args.file2}")
        print("-" * 50)

        if comparison["only_in_first"]:
            print(f"\nOnly in {args.file1}:")
            for var in sorted(comparison["only_in_first"]):
                print(f"  - {var}")

        if comparison["only_in_second"]:
            print(f"\nOnly in {args.file2}:")
            for var in sorted(comparison["only_in_second"]):
                print(f"  + {var}")

        if comparison["different_values"]:
            print("\nDifferent values (non-sensitive):")
            for var in sorted(comparison["different_values"]):
                print(f"  ~ {var}")

        print(f"\nVariables in both: {len(comparison['in_both'])}")

    elif args.command == "template":
        output_path = Path(args.output) if args.output else None
        template = validator.generate_template(
            Path(args.env_file),
            output_path
        )

        if output_path:
            print(f"Template written to: {output_path}")
        else:
            print(template)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
