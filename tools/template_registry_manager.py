#!/usr/bin/env python3
"""
the system Template Registry Manager

Version: 1.0.0
Last Updated: 2025-12-24
Owner: PM
Classification: HIGH - Core Tool

This tool manages the template registry for the system, including:
- Template registration and discovery
- Template validation against schemas
- Template versioning and lifecycle
- Template usage tracking
"""

import os
import sys
import yaml
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

class TemplateType(Enum):
    """Supported template types."""
    TASK = "task"
    WORK_ORDER = "work_order"
    ACTION_PLAN = "action_plan"
    LOGBOOK_ENTRY = "logbook_entry"
    AGENT_PROMPT = "agent_prompt"
    SCHEMA = "schema"
    WORKFLOW = "workflow"
    DOCUMENTATION = "documentation"
    TEST = "test"
    OTHER = "other"

class TemplateStatus(Enum):
    """Template lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

@dataclass
class Template:
    """Represents a registered template."""
    template_id: str
    name: str
    type: TemplateType
    version: str
    path: str
    status: TemplateStatus
    description: str
    schema_ref: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "system"
    checksum: str = ""
    usage_count: int = 0
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if not self.updated_at:
            self.updated_at = self.created_at

class TemplateRegistryManager:
    """Manages the the system template registry."""

    REGISTRY_FILE = "templates/registry.yaml"
    TEMPLATE_DIRS = [
        "templates",
        "PLANNING/templates",
        ".claude/templates",
        "tasks/.templates"
    ]

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.registry_path = self.project_root / self.REGISTRY_FILE
        self.registry: Dict[str, Template] = {}
        self.load_registry()

    def load_registry(self) -> None:
        """Load registry from file."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path) as f:
                    data = yaml.safe_load(f) or {}

                for tid, tdata in data.get("templates", {}).items():
                    try:
                        self.registry[tid] = Template(
                            template_id=tid,
                            name=tdata.get("name", tid),
                            type=TemplateType(tdata.get("type", "other")),
                            version=tdata.get("version", "1.0.0"),
                            path=tdata.get("path", ""),
                            status=TemplateStatus(tdata.get("status", "active")),
                            description=tdata.get("description", ""),
                            schema_ref=tdata.get("schema_ref"),
                            created_at=tdata.get("created_at", ""),
                            updated_at=tdata.get("updated_at", ""),
                            created_by=tdata.get("created_by", "system"),
                            checksum=tdata.get("checksum", ""),
                            usage_count=tdata.get("usage_count", 0),
                            tags=tdata.get("tags", []),
                            dependencies=tdata.get("dependencies", [])
                        )
                    except Exception as e:
                        print(f"Warning: Failed to load template {tid}: {e}")
            except yaml.YAMLError as e:
                print(f"Error loading registry: {e}")

    def save_registry(self) -> None:
        """Save registry to file."""
        # Ensure directory exists
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Build registry data
        data = {
            "version": "1.0.0",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "templates": {}
        }

        for tid, template in self.registry.items():
            data["templates"][tid] = {
                "name": template.name,
                "type": template.type.value,
                "version": template.version,
                "path": template.path,
                "status": template.status.value,
                "description": template.description,
                "schema_ref": template.schema_ref,
                "created_at": template.created_at,
                "updated_at": template.updated_at,
                "created_by": template.created_by,
                "checksum": template.checksum,
                "usage_count": template.usage_count,
                "tags": template.tags,
                "dependencies": template.dependencies
            }

        with open(self.registry_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def compute_checksum(self, filepath: Path) -> str:
        """Compute SHA256 checksum of a file."""
        if not filepath.exists():
            return ""

        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]  # Short hash

    def discover_templates(self) -> List[Path]:
        """Discover templates in standard directories."""
        templates = []

        for dir_name in self.TEMPLATE_DIRS:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                # Find template files
                for ext in ["*.yaml", "*.yml", "*.md", "*.j2", "*.jinja2"]:
                    templates.extend(dir_path.glob(f"**/{ext}"))

        # Filter out registry file and non-template files
        templates = [
            t for t in templates
            if t.name != "registry.yaml"
            and not t.name.startswith(".")
            and "test" not in t.name.lower()
        ]

        return templates

    def infer_template_type(self, filepath: Path) -> TemplateType:
        """Infer template type from path and content."""
        name_lower = filepath.name.lower()
        path_str = str(filepath).lower()

        if "task" in name_lower or "task" in path_str:
            return TemplateType.TASK
        elif "work_order" in name_lower or "workorder" in name_lower:
            return TemplateType.WORK_ORDER
        elif "action_plan" in name_lower or "actionplan" in name_lower:
            return TemplateType.ACTION_PLAN
        elif "logbook" in name_lower or "log_entry" in name_lower:
            return TemplateType.LOGBOOK_ENTRY
        elif "agent" in name_lower or "prompt" in name_lower:
            return TemplateType.AGENT_PROMPT
        elif "schema" in name_lower or filepath.suffix in [".yaml", ".yml"]:
            return TemplateType.SCHEMA
        elif "workflow" in name_lower:
            return TemplateType.WORKFLOW
        elif filepath.suffix == ".md":
            return TemplateType.DOCUMENTATION
        elif "test" in name_lower:
            return TemplateType.TEST
        else:
            return TemplateType.OTHER

    def register_template(
        self,
        filepath: Path,
        name: Optional[str] = None,
        template_type: Optional[TemplateType] = None,
        description: str = "",
        tags: Optional[List[str]] = None
    ) -> Template:
        """Register a new template."""
        filepath = Path(filepath)
        if not filepath.is_absolute():
            filepath = self.project_root / filepath

        if not filepath.exists():
            raise FileNotFoundError(f"Template file not found: {filepath}")

        # Generate template ID
        relative_path = filepath.relative_to(self.project_root)
        template_id = str(relative_path).replace("/", "_").replace(".", "_")

        # Infer name if not provided
        if not name:
            name = filepath.stem.replace("_", " ").replace("-", " ").title()

        # Infer type if not provided
        if not template_type:
            template_type = self.infer_template_type(filepath)

        # Compute checksum
        checksum = self.compute_checksum(filepath)

        # Create template
        template = Template(
            template_id=template_id,
            name=name,
            type=template_type,
            version="1.0.0",
            path=str(relative_path),
            status=TemplateStatus.ACTIVE,
            description=description or f"Template: {name}",
            checksum=checksum,
            tags=tags or []
        )

        # Add to registry
        self.registry[template_id] = template
        self.save_registry()

        return template

    def auto_register(self, dry_run: bool = False) -> List[Template]:
        """Auto-discover and register all templates."""
        discovered = self.discover_templates()
        registered = []

        for filepath in discovered:
            relative_path = filepath.relative_to(self.project_root)
            template_id = str(relative_path).replace("/", "_").replace(".", "_")

            # Skip already registered
            if template_id in self.registry:
                continue

            if dry_run:
                print(f"Would register: {relative_path}")
            else:
                try:
                    template = self.register_template(filepath)
                    registered.append(template)
                    print(f"Registered: {template.template_id}")
                except Exception as e:
                    print(f"Failed to register {relative_path}: {e}")

        return registered

    def update_template(self, template_id: str, **kwargs) -> Optional[Template]:
        """Update an existing template."""
        if template_id not in self.registry:
            return None

        template = self.registry[template_id]

        # Update fields
        for key, value in kwargs.items():
            if hasattr(template, key):
                if key == "type" and isinstance(value, str):
                    value = TemplateType(value)
                elif key == "status" and isinstance(value, str):
                    value = TemplateStatus(value)
                setattr(template, key, value)

        template.updated_at = datetime.utcnow().isoformat() + "Z"

        # Recompute checksum if path changed
        if "path" in kwargs:
            filepath = self.project_root / template.path
            template.checksum = self.compute_checksum(filepath)

        self.save_registry()
        return template

    def deprecate_template(self, template_id: str, reason: str = "") -> bool:
        """Mark a template as deprecated."""
        if template_id not in self.registry:
            return False

        self.registry[template_id].status = TemplateStatus.DEPRECATED
        self.registry[template_id].updated_at = datetime.utcnow().isoformat() + "Z"
        if reason:
            self.registry[template_id].description += f" [DEPRECATED: {reason}]"

        self.save_registry()
        return True

    def get_template(self, template_id: str) -> Optional[Template]:
        """Get a template by ID."""
        return self.registry.get(template_id)

    def search_templates(
        self,
        query: Optional[str] = None,
        template_type: Optional[TemplateType] = None,
        status: Optional[TemplateStatus] = None,
        tags: Optional[List[str]] = None
    ) -> List[Template]:
        """Search templates with filters."""
        results = list(self.registry.values())

        if query:
            query_lower = query.lower()
            results = [
                t for t in results
                if query_lower in t.name.lower()
                or query_lower in t.description.lower()
                or query_lower in t.template_id.lower()
            ]

        if template_type:
            results = [t for t in results if t.type == template_type]

        if status:
            results = [t for t in results if t.status == status]

        if tags:
            results = [t for t in results if any(tag in t.tags for tag in tags)]

        return results

    def validate_template(self, template_id: str) -> Tuple[bool, List[str]]:
        """Validate a template against its schema."""
        if template_id not in self.registry:
            return False, ["Template not found in registry"]

        template = self.registry[template_id]
        issues = []

        # Check file exists
        filepath = self.project_root / template.path
        if not filepath.exists():
            issues.append(f"Template file not found: {template.path}")
            return False, issues

        # Check checksum
        current_checksum = self.compute_checksum(filepath)
        if current_checksum != template.checksum:
            issues.append(f"Checksum mismatch - template may have been modified")

        # Validate YAML syntax if applicable
        if filepath.suffix in [".yaml", ".yml"]:
            try:
                with open(filepath) as f:
                    content = yaml.safe_load(f)
            except yaml.YAMLError as e:
                issues.append(f"Invalid YAML: {e}")
                return False, issues

            # Validate against schema_ref if specified
            if template.schema_ref:
                schema_path = self.project_root / template.schema_ref
                if not schema_path.exists():
                    issues.append(f"Schema not found: {template.schema_ref}")
                else:
                    try:
                        with open(schema_path) as sf:
                            schema = yaml.safe_load(sf)
                        # Basic structural validation (jsonschema optional)
                        if schema and isinstance(schema, dict):
                            required_fields = schema.get('required', [])
                            if content and isinstance(content, dict):
                                for field in required_fields:
                                    if field not in content:
                                        issues.append(f"Missing required field: {field}")
                    except Exception as e:
                        issues.append(f"Schema validation error: {e}")

        return len(issues) == 0, issues

    def record_usage(self, template_id: str) -> bool:
        """Record that a template was used."""
        if template_id not in self.registry:
            return False

        self.registry[template_id].usage_count += 1
        self.save_registry()
        return True

    def list_templates(
        self,
        format: str = "table",
        template_type: Optional[TemplateType] = None
    ) -> str:
        """List all templates in specified format."""
        templates = self.search_templates(template_type=template_type)

        if format == "json":
            return json.dumps(
                [asdict(t) for t in templates],
                indent=2,
                default=str
            )

        elif format == "yaml":
            data = [asdict(t) for t in templates]
            for item in data:
                item["type"] = item["type"].value if hasattr(item["type"], "value") else item["type"]
                item["status"] = item["status"].value if hasattr(item["status"], "value") else item["status"]
            return yaml.dump(data, default_flow_style=False)

        else:  # table format
            lines = []
            lines.append(f"{'ID':<40} {'Type':<15} {'Status':<12} {'Uses':<6} {'Name':<30}")
            lines.append("-" * 105)

            for t in sorted(templates, key=lambda x: x.name):
                lines.append(
                    f"{t.template_id[:40]:<40} "
                    f"{t.type.value:<15} "
                    f"{t.status.value:<12} "
                    f"{t.usage_count:<6} "
                    f"{t.name[:30]:<30}"
                )

            lines.append("-" * 105)
            lines.append(f"Total: {len(templates)} templates")

            return "\n".join(lines)

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        templates = list(self.registry.values())

        type_counts = {}
        for t in templates:
            type_counts[t.type.value] = type_counts.get(t.type.value, 0) + 1

        status_counts = {}
        for t in templates:
            status_counts[t.status.value] = status_counts.get(t.status.value, 0) + 1

        total_usage = sum(t.usage_count for t in templates)

        return {
            "total_templates": len(templates),
            "by_type": type_counts,
            "by_status": status_counts,
            "total_usage": total_usage,
            "most_used": sorted(templates, key=lambda x: x.usage_count, reverse=True)[:5]
        }

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="the system Template Registry Manager"
    )

    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List registered templates")
    list_parser.add_argument("--format", choices=["table", "json", "yaml"], default="table")
    list_parser.add_argument("--type", help="Filter by template type")

    # Register command
    register_parser = subparsers.add_parser("register", help="Register a template")
    register_parser.add_argument("path", help="Path to template file")
    register_parser.add_argument("--name", help="Template name")
    register_parser.add_argument("--type", help="Template type")
    register_parser.add_argument("--description", help="Template description")
    register_parser.add_argument("--tags", help="Comma-separated tags")

    # Auto-register command
    auto_parser = subparsers.add_parser("auto", help="Auto-register all templates")
    auto_parser.add_argument("--dry-run", action="store_true", help="Show what would be registered")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a template")
    validate_parser.add_argument("template_id", help="Template ID to validate")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search templates")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--format", choices=["table", "json"], default="table")

    # Stats command
    subparsers.add_parser("stats", help="Show registry statistics")

    # Deprecate command
    deprecate_parser = subparsers.add_parser("deprecate", help="Deprecate a template")
    deprecate_parser.add_argument("template_id", help="Template ID to deprecate")
    deprecate_parser.add_argument("--reason", default="", help="Deprecation reason")

    args = parser.parse_args()

    manager = TemplateRegistryManager(args.project_root)

    if args.command == "list":
        template_type = TemplateType(args.type) if args.type else None
        print(manager.list_templates(format=args.format, template_type=template_type))

    elif args.command == "register":
        tags = args.tags.split(",") if args.tags else None
        template_type = TemplateType(args.type) if args.type else None
        template = manager.register_template(
            filepath=args.path,
            name=args.name,
            template_type=template_type,
            description=args.description or "",
            tags=tags
        )
        print(f"Registered template: {template.template_id}")

    elif args.command == "auto":
        registered = manager.auto_register(dry_run=args.dry_run)
        if not args.dry_run:
            print(f"Registered {len(registered)} new templates")

    elif args.command == "validate":
        valid, issues = manager.validate_template(args.template_id)
        if valid:
            print(f"✅ Template {args.template_id} is valid")
        else:
            print(f"❌ Template {args.template_id} has issues:")
            for issue in issues:
                print(f"  - {issue}")
        sys.exit(0 if valid else 1)

    elif args.command == "search":
        results = manager.search_templates(query=args.query)
        if args.format == "json":
            print(json.dumps([asdict(t) for t in results], indent=2, default=str))
        else:
            for t in results:
                print(f"{t.template_id}: {t.name} ({t.type.value})")

    elif args.command == "stats":
        stats = manager.get_statistics()
        print("Template Registry Statistics")
        print("=" * 40)
        print(f"Total templates: {stats['total_templates']}")
        print(f"Total usage: {stats['total_usage']}")
        print("\nBy Type:")
        for ttype, count in stats['by_type'].items():
            print(f"  {ttype}: {count}")
        print("\nBy Status:")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")
        print("\nMost Used:")
        for t in stats['most_used']:
            print(f"  {t.name}: {t.usage_count} uses")

    elif args.command == "deprecate":
        if manager.deprecate_template(args.template_id, args.reason):
            print(f"Deprecated template: {args.template_id}")
        else:
            print(f"Template not found: {args.template_id}")
            sys.exit(1)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
